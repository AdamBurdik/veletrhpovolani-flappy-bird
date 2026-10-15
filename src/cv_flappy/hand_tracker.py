import math
import threading
import time
import urllib.request
from dataclasses import dataclass

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from .config import (
    CLAHE_CLIP_LIMIT,
    CLAHE_GRID,
    FIST_CURLED_FINGERS,
    GESTURE_HOLD_FRAMES,
    HAND_DETECTION_CONFIDENCE,
    HAND_LANDMARKER_PATH,
    HAND_LANDMARKER_URL,
    HAND_MAP_HIGH,
    HAND_MAP_LOW,
    HAND_PRESENCE_CONFIDENCE,
    HAND_SMOOTHING,
    HAND_TRACKING_CONFIDENCE,
    PINCH_ENGAGE_RATIO,
    PINCH_RELEASE_RATIO,
    PINCH_SMOOTHING,
    VISION_CLAHE,
)

HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
)


@dataclass
class HandState:
    hand_y: float
    gesture: str | None
    landmarks: list[tuple[float, float]]


def map_hand_to_playfield(
    hand_y: float, top: float, bottom: float
) -> float:
    t = (hand_y - HAND_MAP_LOW) / (HAND_MAP_HIGH - HAND_MAP_LOW)
    t = min(1.0, max(0.0, t))
    return top + t * (bottom - top)


def playfield_to_hand(y: float, top: float, bottom: float) -> float:
    """Inverse of map_hand_to_playfield: a playfield height -> hand_y."""
    if bottom <= top:
        return HAND_MAP_LOW
    t = (y - top) / (bottom - top)
    t = min(1.0, max(0.0, t))
    return HAND_MAP_LOW + t * (HAND_MAP_HIGH - HAND_MAP_LOW)


def _dist(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _hand_scale(landmarks) -> float:
    palm_width = _dist(landmarks[5], landmarks[17])
    wrist_middle = _dist(landmarks[0], landmarks[9])
    return max(palm_width, wrist_middle, 1e-6)


def pinch_ratio(landmarks) -> float:
    """Scale-invariant thumb-to-finger distance; small means pinching.

    Averages several joint pairs so a single noisy landmark (common in dim
    light) can't spoof or break the reading. Values are normalised by the
    hand's own size, so distance to the camera doesn't matter.
    """
    scale = _hand_scale(landmarks)
    pairs = ((4, 8), (3, 8), (4, 7))
    total = sum(_dist(landmarks[a], landmarks[b]) for a, b in pairs)
    return (total / len(pairs)) / scale


def fist_curled_fingers(landmarks) -> int:
    wrist = landmarks[0]
    return sum(
        1
        for tip, pip in ((8, 6), (12, 10), (16, 14), (20, 18))
        if _dist(wrist, landmarks[tip]) < _dist(wrist, landmarks[pip])
    )


def detect_gesture(landmarks) -> str | None:
    """'fist' when the fist is closed, 'pinch' when fingers touch, else None.

    Stateless and immediate; HandTracker applies smoothing and debouncing on
    top of these raw measures.
    """
    if fist_curled_fingers(landmarks) >= FIST_CURLED_FINGERS:
        return "fist"
    if pinch_ratio(landmarks) < PINCH_ENGAGE_RATIO:
        return "pinch"
    return None


def ensure_model(path, url: str) -> None:
    if path.exists():
        return
    print(f"Downloading hand landmark model to {path} ...")
    try:
        urllib.request.urlretrieve(url, path)
    except OSError as exc:
        raise RuntimeError(
            f"Could not download the hand landmark model from {url}. "
            f"Download it manually and place it at {path}."
        ) from exc


class HandTracker:
    def __init__(
        self,
        smoothing: float = HAND_SMOOTHING,
        model_path=HAND_LANDMARKER_PATH,
        model_url: str = HAND_LANDMARKER_URL,
    ):
        ensure_model(model_path, model_url)
        options = vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=HAND_DETECTION_CONFIDENCE,
            min_hand_presence_confidence=HAND_PRESENCE_CONFIDENCE,
            min_tracking_confidence=HAND_TRACKING_CONFIDENCE,
        )
        self.landmarker = vision.HandLandmarker.create_from_options(options)
        self.smoothing = smoothing
        self._smoothed_y: float | None = None
        self._pinch_smoothed: float | None = None
        self._gesture: str | None = None
        self._pending: str | None = None
        self._pending_count = 0
        self._last_timestamp_ms = 0
        self._clahe = (
            cv2.createCLAHE(
                clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=(CLAHE_GRID, CLAHE_GRID)
            )
            if VISION_CLAHE
            else None
        )

    def _preprocess(self, rgb_frame: np.ndarray) -> np.ndarray:
        if self._clahe is None:
            return rgb_frame
        lab = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2LAB)
        lightness, a, b = cv2.split(lab)
        lightness = self._clahe.apply(lightness)
        return cv2.cvtColor(cv2.merge((lightness, a, b)), cv2.COLOR_LAB2RGB)

    def _update_gesture(self, landmarks) -> str | None:
        if fist_curled_fingers(landmarks) >= FIST_CURLED_FINGERS:
            candidate = "fist"
        else:
            ratio = pinch_ratio(landmarks)
            if self._pinch_smoothed is None:
                self._pinch_smoothed = ratio
            else:
                self._pinch_smoothed = (
                    PINCH_SMOOTHING * ratio
                    + (1.0 - PINCH_SMOOTHING) * self._pinch_smoothed
                )
            threshold = (
                PINCH_RELEASE_RATIO
                if self._gesture == "pinch"
                else PINCH_ENGAGE_RATIO
            )
            candidate = "pinch" if self._pinch_smoothed < threshold else None

        if candidate == self._gesture:
            self._pending = None
            self._pending_count = 0
        else:
            if candidate == self._pending:
                self._pending_count += 1
            else:
                self._pending = candidate
                self._pending_count = 1
            if self._pending_count >= GESTURE_HOLD_FRAMES:
                self._gesture = candidate
                self._pending = None
                self._pending_count = 0
        return self._gesture

    def process(self, rgb_frame: np.ndarray) -> HandState | None:
        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB, data=self._preprocess(rgb_frame)
        )
        timestamp_ms = int(time.monotonic() * 1000)
        if timestamp_ms <= self._last_timestamp_ms:
            timestamp_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = timestamp_ms
        result = self.landmarker.detect_for_video(mp_image, timestamp_ms)
        if not result.hand_landmarks:
            self._smoothed_y = None
            self._pinch_smoothed = None
            self._gesture = None
            self._pending = None
            self._pending_count = 0
            return None
        hand = result.hand_landmarks[0]
        raw_y = hand[9].y
        if self._smoothed_y is None:
            self._smoothed_y = raw_y
        else:
            self._smoothed_y = (
                self.smoothing * raw_y + (1.0 - self.smoothing) * self._smoothed_y
            )
        world = (
            result.hand_world_landmarks[0]
            if result.hand_world_landmarks
            else hand
        )
        gesture = self._update_gesture(world)
        points = [(point.x, point.y) for point in hand]
        return HandState(self._smoothed_y, gesture, points)

    def close(self) -> None:
        self.landmarker.close()


class HandWorker:
    """Runs hand tracking on a background thread so the render loop never
    blocks on MediaPipe inference.

    The main loop hands in the newest camera frame with ``submit`` and reads the
    latest result with ``latest`` (non-blocking). Stale frames are dropped, so
    the renderer always runs at its own pace while tracking catches up.
    """

    def __init__(self, tracker: HandTracker):
        self._tracker = tracker
        self._lock = threading.Lock()
        self._frame = None
        self._state: HandState | None = None
        self._has_frame = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def submit(self, frame) -> None:
        with self._lock:
            self._frame = frame
        self._has_frame.set()

    def latest(self) -> HandState | None:
        with self._lock:
            return self._state

    def _run(self) -> None:
        while not self._stop.is_set():
            self._has_frame.wait(timeout=0.1)
            if self._stop.is_set():
                break
            with self._lock:
                frame = self._frame
                self._frame = None
                self._has_frame.clear()
            if frame is None:
                continue
            state = self._tracker.process(frame)
            with self._lock:
                self._state = state

    def stop(self) -> None:
        self._stop.set()
        self._has_frame.set()
        self._thread.join(timeout=2.0)

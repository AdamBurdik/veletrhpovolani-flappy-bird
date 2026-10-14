import math
import time
import urllib.request

import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from .config import (
    FIST_CURLED_FINGERS,
    HAND_LANDMARKER_PATH,
    HAND_LANDMARKER_URL,
    HAND_MAP_HIGH,
    HAND_MAP_LOW,
    HAND_SMOOTHING,
    PINCH_RATIO,
)


def map_hand_to_playfield(
    hand_y: float, top: float, bottom: float
) -> float:
    t = (hand_y - HAND_MAP_LOW) / (HAND_MAP_HIGH - HAND_MAP_LOW)
    t = min(1.0, max(0.0, t))
    return top + t * (bottom - top)


def _dist(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def detect_gesture(landmarks) -> str | None:
    """'fist' when the fist is closed, 'pinch' when fingers touch, else None."""
    wrist = landmarks[0]
    curled = 0
    for tip, pip in ((8, 6), (12, 10), (16, 14), (20, 18)):
        if _dist(wrist, landmarks[tip]) < _dist(wrist, landmarks[pip]):
            curled += 1
    if curled >= FIST_CURLED_FINGERS:
        return "fist"
    palm = _dist(wrist, landmarks[9])
    if _dist(landmarks[4], landmarks[8]) < palm * PINCH_RATIO:
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
            min_hand_detection_confidence=0.6,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.landmarker = vision.HandLandmarker.create_from_options(options)
        self.smoothing = smoothing
        self._smoothed_y: float | None = None
        self._last_timestamp_ms = 0

    def process(self, rgb_frame: np.ndarray) -> tuple[float, str | None] | None:
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        timestamp_ms = int(time.monotonic() * 1000)
        if timestamp_ms <= self._last_timestamp_ms:
            timestamp_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = timestamp_ms
        result = self.landmarker.detect_for_video(mp_image, timestamp_ms)
        if not result.hand_landmarks:
            self._smoothed_y = None
            return None
        landmarks = result.hand_landmarks[0]
        raw_y = landmarks[9].y
        if self._smoothed_y is None:
            self._smoothed_y = raw_y
        else:
            self._smoothed_y = (
                self.smoothing * raw_y + (1.0 - self.smoothing) * self._smoothed_y
            )
        return self._smoothed_y, detect_gesture(landmarks)

    def close(self) -> None:
        self.landmarker.close()

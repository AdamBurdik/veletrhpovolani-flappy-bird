import threading
import time
from dataclasses import dataclass, field

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from .config import (
    CLAHE_CLIP_LIMIT,
    CLAHE_GRID,
    POSE_DETECTION_CONFIDENCE,
    POSE_LANDMARKER_PATH,
    POSE_LANDMARKER_URL,
    POSE_PRESENCE_CONFIDENCE,
    POSE_TRACKING_CONFIDENCE,
    SQUAT_HEAD_GAP_MIN_RATIO,
    SQUAT_MAX_SHOULDER_W,
    SQUAT_MIN_LANDMARK_VISIBILITY,
    SQUAT_MIN_SHOULDER_W,
    SQUAT_SMOOTHING,
    SQUAT_TORSO_MIN_RATIO,
    VISION_CLAHE,
)
from .hand_tracker import ensure_model

NOSE = 0
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
LEFT_ANKLE = 27
RIGHT_ANKLE = 28

BODY_INDICES = (
    NOSE,
    LEFT_SHOULDER,
    RIGHT_SHOULDER,
    LEFT_ELBOW,
    RIGHT_ELBOW,
    LEFT_WRIST,
    RIGHT_WRIST,
    LEFT_HIP,
    RIGHT_HIP,
    LEFT_KNEE,
    RIGHT_KNEE,
    LEFT_ANKLE,
    RIGHT_ANKLE,
)

BODY_CONNECTIONS = (
    (0, 1), (0, 2),
    (1, 2),
    (1, 3), (3, 5),
    (2, 4), (4, 6),
    (1, 7), (2, 8), (7, 8),
    (7, 9), (9, 11),
    (8, 10), (10, 12),
)


@dataclass
class BodyState:
    body_y: float
    valid: bool
    too_close: bool
    too_far: bool
    bending: bool
    landmarks: list[tuple[float, float]] = field(default_factory=list)
    visibility: list[float] = field(default_factory=list)


def _mid_y(a, b) -> float:
    return (a.y + b.y) / 2.0


class BodyTracker:
    """Tracks the whole body with MediaPipe Pose.

    The control height comes from the hips (a squat moves them, bending over
    does not), while the shoulders and nose are used to reject the bend-over
    cheat and the shoulder width is used as a distance gate.
    """

    def __init__(
        self,
        smoothing: float = SQUAT_SMOOTHING,
        model_path=POSE_LANDMARKER_PATH,
        model_url: str = POSE_LANDMARKER_URL,
    ):
        ensure_model(model_path, model_url, "pose landmark model")
        options = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=POSE_DETECTION_CONFIDENCE,
            min_pose_presence_confidence=POSE_PRESENCE_CONFIDENCE,
            min_tracking_confidence=POSE_TRACKING_CONFIDENCE,
        )
        self.landmarker = vision.PoseLandmarker.create_from_options(options)
        self.smoothing = smoothing
        self._smoothed_y: float | None = None
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

    def process(self, rgb_frame: np.ndarray) -> BodyState | None:
        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB, data=self._preprocess(rgb_frame)
        )
        timestamp_ms = int(time.monotonic() * 1000)
        if timestamp_ms <= self._last_timestamp_ms:
            timestamp_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = timestamp_ms
        result = self.landmarker.detect_for_video(mp_image, timestamp_ms)
        if not result.pose_landmarks:
            self._smoothed_y = None
            return None

        pose = result.pose_landmarks[0]
        landmarks = [(pose[i].x, pose[i].y) for i in BODY_INDICES]
        visibility = [float(pose[i].visibility) for i in BODY_INDICES]

        required = (
            NOSE,
            LEFT_SHOULDER,
            RIGHT_SHOULDER,
            LEFT_HIP,
            RIGHT_HIP,
        )
        visible = all(
            float(pose[i].visibility) >= SQUAT_MIN_LANDMARK_VISIBILITY
            for i in required
        )

        shoulder_w = abs(pose[RIGHT_SHOULDER].x - pose[LEFT_SHOULDER].x) or 1e-6
        shoulder_mid_y = _mid_y(pose[LEFT_SHOULDER], pose[RIGHT_SHOULDER])
        hip_mid_y = _mid_y(pose[LEFT_HIP], pose[RIGHT_HIP])
        torso_len = abs(hip_mid_y - shoulder_mid_y)
        head_gap = shoulder_mid_y - pose[NOSE].y

        too_close = shoulder_w > SQUAT_MAX_SHOULDER_W
        too_far = shoulder_w < SQUAT_MIN_SHOULDER_W
        bending = (
            torso_len < SQUAT_TORSO_MIN_RATIO * shoulder_w
            or head_gap < SQUAT_HEAD_GAP_MIN_RATIO * shoulder_w
        )

        raw_y = hip_mid_y
        if self._smoothed_y is None:
            self._smoothed_y = raw_y
        else:
            self._smoothed_y = (
                self.smoothing * raw_y + (1.0 - self.smoothing) * self._smoothed_y
            )

        valid = visible and not too_close and not too_far and not bending
        return BodyState(
            body_y=self._smoothed_y,
            valid=valid,
            too_close=too_close,
            too_far=too_far,
            bending=bending,
            landmarks=landmarks,
            visibility=visibility,
        )

    def close(self) -> None:
        self.landmarker.close()


class BodyWorker:
    """Runs pose tracking on a background thread, like ``HandWorker``.

    The main loop submits the newest camera frame and reads the latest result
    without ever blocking on inference.
    """

    def __init__(self, tracker: BodyTracker):
        self._tracker = tracker
        self._lock = threading.Lock()
        self._frame = None
        self._state: BodyState | None = None
        self._has_frame = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def submit(self, frame) -> None:
        with self._lock:
            self._frame = frame
        self._has_frame.set()

    def latest(self) -> BodyState | None:
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

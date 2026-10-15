import threading

import cv2
import numpy as np
import pygame

from .config import CAM_HEIGHT, CAM_WIDTH


class Camera:
    def __init__(self, index: int = 0, width: int = CAM_WIDTH, height: int = CAM_HEIGHT):
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
        if self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.ok = self.cap.isOpened()

    def read(self) -> np.ndarray | None:
        if not self.ok:
            return None
        grabbed, frame = self.cap.read()
        if not grabbed:
            return None
        frame = cv2.flip(frame, 1)
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    def close(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None


def frame_to_surface(frame: np.ndarray) -> pygame.Surface:
    return pygame.surfarray.make_surface(frame.swapaxes(0, 1))


class CameraWorker:
    """Reads the camera on a background thread so the render loop never blocks
    on ``VideoCapture.read``.

    A webcam typically delivers 30 fps, and a blocking read in the main loop
    would cap the whole game (and screensaver) to that rate. Here the loop just
    grabs the newest decoded frame with ``latest`` and renders at its own pace.
    """

    def __init__(self, camera: Camera):
        self._camera = camera
        self._lock = threading.Lock()
        self._frame = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def latest(self) -> np.ndarray | None:
        with self._lock:
            return self._frame

    def _run(self) -> None:
        while not self._stop.is_set():
            frame = self._camera.read()
            if self._stop.is_set():
                break
            if frame is not None:
                with self._lock:
                    self._frame = frame

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)

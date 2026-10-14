import cv2
import numpy as np
import pygame


class Camera:
    def __init__(self, index: int = 0, width: int = 640, height: int = 480):
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

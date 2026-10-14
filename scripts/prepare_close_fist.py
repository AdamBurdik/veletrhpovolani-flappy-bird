"""Bake assets/close_fist.gif into a 2-tone black-and-white sprite sheet.

Run once (and again if the source GIF changes):

    uv run python scripts/prepare_close_fist.py

Reads ``assets/close_fist.gif`` and writes ``assets/close_fist_bw.png``:
the flat background is removed (transparent) and the hand is reduced to a
2-tone stencil (solid white body, solid black outlines). Frames are packed
into a grid sprite sheet for cheap loading with pygame.
"""

from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets" / "close_fist.gif"
DST = ROOT / "assets" / "close_fist_bw.png"

BG = np.array([240, 250, 177])
BG_TOLERANCE = 30
LUMA_THRESHOLD = 140
FRAME_HEIGHT = 200
PAD = 10
COLS = 8
ROWS = 7


def _ensure_even(value: int) -> int:
    return value + (value & 1)


def load_frames() -> list[np.ndarray]:
    im = Image.open(SRC)
    frames = []
    for i in range(im.n_frames):
        im.seek(i)
        frames.append(np.array(im.convert("RGB")))
    if len(frames) > 1 and np.array_equal(frames[0], frames[-1]):
        frames.pop()
    return frames


def foreground_bbox(frames: list[np.ndarray]) -> tuple[int, int, int, int]:
    min_x = min_y = 10**9
    max_x = max_y = -1
    for frame in frames:
        mask = np.abs(frame.astype(int) - BG).sum(axis=2) > BG_TOLERANCE
        ys, xs = np.where(mask)
        if xs.size:
            min_x, max_x = min(min_x, xs.min()), max(max_x, xs.max())
            min_y, max_y = min(min_y, ys.min()), max(max_y, ys.max())
    return min_x, min_y, max_x, max_y


def to_bw(frame: np.ndarray) -> Image.Image:
    rgb = frame.astype(int)
    background = np.abs(rgb - BG).sum(axis=2) <= BG_TOLERANCE
    luma = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]

    rgba = np.zeros((*frame.shape[:2], 4), dtype=np.uint8)
    ink = (~background) & (luma < LUMA_THRESHOLD)
    paper = (~background) & (luma >= LUMA_THRESHOLD)
    rgba[ink] = (0, 0, 0, 255)
    rgba[paper] = (255, 255, 255, 255)
    return Image.fromarray(rgba, "RGBA")


def main() -> None:
    frames = load_frames()
    if len(frames) != COLS * ROWS:
        raise SystemExit(
            f"Expected {COLS * ROWS} frames for a {COLS}x{ROWS} grid, got {len(frames)}."
        )

    x0, y0, x1, y1 = foreground_bbox(frames)
    left = max(0, x0 - PAD)
    top = max(0, y0 - PAD)
    right = min(frames[0].shape[1], x1 + 1 + PAD)
    bottom = min(frames[0].shape[0], y1 + 1 + PAD)
    crop = (left, top, right, bottom)

    width = _ensure_even(round((right - left) * FRAME_HEIGHT / (bottom - top)))
    height = _ensure_even(FRAME_HEIGHT)

    sheet = Image.new("RGBA", (COLS * width, ROWS * height), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        cell = to_bw(frame).crop(crop).resize((width, height), Image.LANCZOS)
        cell.putalpha(cell.getchannel("A").point(lambda a: 255 if a > 128 else 0))
        sheet.paste(cell, ((index % COLS) * width, (index // COLS) * height))

    sheet.save(DST)
    print(
        f"Wrote {DST.relative_to(ROOT)}: {COLS}x{ROWS} frames of "
        f"{width}x{height}px ({sheet.width}x{sheet.height})."
    )


if __name__ == "__main__":
    main()

# cv-flappy

Flappy Bird played with your hand over a web camera. The bird's height follows
your hand's height in the camera frame. After a game over you can enter your
name and your score is saved to a local JSON leaderboard.

## Requirements

- Python 3.14+
- A webcam

## Install

```sh
uv sync
```

The hand landmark model (`hand_landmarker.task`, ~8 MB) is downloaded
automatically to the run directory on first start if not present.

## Run

```sh
uv run cv-flappy
```

## How to play

1. **Menu** — hover your hand over the upper half for **easy** or the lower
   half for **hard** (highlighted live), then **close your fist or pinch** to
   start. Keyboard works too: 1 / 2 to choose, SPACE to start.
2. **Easy** — an intro screen shows a hand moving up and down and waits for you
   to **pinch** before the countdown starts (SPACE / ENTER also work). Then raise
   or lower your open hand and the bird follows its height. If the camera loses
   your hand, the bird hovers in place.
3. **Hard** — an intro screen shows the hand closing into a fist and waits for
   you to **close your fist** before the countdown starts (SPACE / ENTER also
   work). Then the pipe gaps follow your hand's height (highly sensitive); the
   bird falls with gravity and you flap by closing your fist or pinching.
4. Pipes get faster as you score. Game over: type your name (max 12 chars)
   and press ENTER to save it, or ESC to skip. ENTER or a **pinch** goes back
   to the menu.

When you confirm a name, a neural TTS voice (Piper, `cs_CZ-jirka-medium`) says
it back. The voice lives in `models/` and loads in the background at startup;
if the model or voice isn't available the game just stays silent.

The intro screen is shown for at least 2 seconds before it can be dismissed,
so the same pinch/fist that picked the mode can't skip it.

The window is resizable (drag its edges) and **F11** toggles fullscreen.
Sound effects play when you flap (hard mode), score a point, and crash.
Missing assets or an unavailable audio device simply disable sound without
affecting the game.
The leaderboard panel on the right is always visible with separate **EASY**
and **HARD** boards (top 5 each); the camera preview sits on the left with a
live line showing your hand height.

### Wayland / Hyprland note

If fullscreen misbehaves on your Wayland compositor, force the XWayland
backend instead:

```sh
SDL_VIDEODRIVER=x11 uv run cv-flappy
```

The game logic runs on a fixed 960x640 virtual playfield scaled to fit the
window, so gameplay is identical at any resolution.

The leaderboard is stored as `leaderboard.json` in the directory the game is
run from (`{"easy": [...], "hard": [...]}`, top 50 entries per board, newest
date included).

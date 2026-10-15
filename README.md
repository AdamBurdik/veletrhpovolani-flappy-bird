> [!NOTE]
> This project was written entirely by AI. Please read the LICENCE before.

# cv-flappy

Flappy Bird played with your hand over a web camera. The bird's height follows
your hand's height in the camera frame. After a game over you say your name and
your score is saved to a local JSON leaderboard.

## Licence

The **source code** is licensed under the [MIT License](LICENCE).

This covers the code only:

- `src/`
- `scripts/`

It does **not** cover the models and assets:

- `assets/`
- `models/`
- `hand_landmarker.task`
- `pose_landmarker_lite.task`

These files may come from third parties and may have their own licences.
Their origin has not been verified.
If you want to reuse or redistribute them, please do your own research.

## Requirements

- Python 3.14+
- A webcam
- A microphone (for voice name entry)
- An internet connection and a Groq API key (for voice name entry)

## Install

```sh
uv sync
```

The hand landmark model (`hand_landmarker.task`, ~8 MB) is downloaded
automatically to the run directory on first start if not present. The pose
model used by squat mode (`pose_landmarker_lite.task`, ~5 MB) is downloaded the
same way.

Voice name entry calls a speech-to-text API. Put your key in a `.env` file in
the run directory, or export it:

```sh
echo 'GROQ_KEY=gsk_...' > .env
```

## Run

```sh
uv run cv-flappy
```

## How to play

1. **Menu** — hover your hand over a third of the screen to pick **easy**
   (top), **hard** (middle) or **squat** (bottom) (highlighted live), then
   **close your fist or pinch** to start. Keyboard works too: 1 / 2 / 3 to
   choose, SPACE to start.
2. **Easy** — an intro screen shows a hand moving up and down and waits for you
   to **move your hand up and down** before the countdown starts (SPACE / ENTER
   also work). Then raise or lower your open hand and the bird follows its
   height. If the camera loses your hand, the bird hovers in place.
3. **Hard** — an intro screen shows the hand closing into a fist and waits for
   you to **close your fist** before the countdown starts (SPACE / ENTER also
   work). Then the pipe gaps follow your hand's height (highly sensitive); the
   bird falls with gravity and you flap by closing your fist or pinching.
4. **Squat** — the bird's height follows your **torso**: stand tall and it rises,
   squat down and it drops. The intro waits for you to **squat up and down**
   before the countdown starts. Your whole body is tracked with MediaPipe Pose
   (the pose model is downloaded automatically like the hand model), and the
   height is driven by your **hips**, so bending over at the waist does nothing.
   If you lean/bend instead of squatting, or crowd the camera, the bird freezes
   and a **STEP BACK** / **USE YOUR LEGS - DON'T BEND** warning appears until
   you get back into range. Squat mode is skipped if the pose model can't be
   loaded (e.g. offline on first run).
5. Pipes get faster as you score. Game over: the game starts listening and you
   **say your name** (Czech). Press ENTER to save it, BACKSPACE to clear it and
   listen again, or ESC to skip. Typing on the keyboard still works as a
   fallback. Either way you go straight back to the menu after saving/skipping.

When you confirm a name, a neural TTS voice (Piper, `cs_CZ-jirka-medium`) says
it back. The voice lives in `models/` and loads in the background at startup;
if the model or voice isn't available the game just stays silent.

Speech-to-text uses a cloud API, so it needs a key and an internet connection.
Two providers are supported and selected with `STT_PROVIDER` in `config.py` (or
the `CV_FLAPPY_STT_PROVIDER` env var):

- **`groq`** (default) — OpenAI-compatible transcription,
  `whisper-large-v3` by default. Key from `GROQ_KEY`.
- **`gemini`** — Google AI Studio `gemini-2.5-flash`. Key from `GEMINI_API_KEY`
  or `GOOGLE_API_KEY`.

The game records from the default microphone, stops after a short silence,
normalises the clip, and uploads it; the recognised text goes in the name box.
The fallback chain is the selected provider, then the keyboard: if no key is
set, the API is unreachable, or nothing is recognised, you just type the name.
The remaining knobs (`STT_LANGUAGE`, `STT_PROMPT`, recording length, model
names) live in `config.py` (`STT_*`). Keys are read from a `.env` file in the
run directory if present; that file is git-ignored.

The intro screen is shown for at least 2 seconds before it can be dismissed,
so the same pinch/fist that picked the mode can't skip it; in easy mode you
must then actually move your hand up and down, and in squat mode you must
squat up and down.

Gesture detection is tuned for poor light: the pinch measure is normalised by
the hand's own size and averaged over several finger joints, gestures are
smoothed and debounced across consecutive frames with hysteresis, and dim
frames are contrast-enhanced (CLAHE) before tracking. The knobs live in
`config.py` (`PINCH_ENGAGE_RATIO`, `GESTURE_HOLD_FRAMES`, `VISION_CLAHE`, ...).

### Screensaver

After 30 seconds with no hand and no input on the menu (or game-over screen),
the game switches to an attract mode; you can also start it any time with
**0**. A ghost hand plays itself, steering the bird through the pipes on a loop
over the full window (the camera fills the background, dimmed darker than in
normal play), with an animated hand cue and a `DEMO` banner. Move your hand
**up and down** (or press any key) to wake it back to the menu, with a ~1
second grace so the waking input can't start a game.

Hand tracking runs on a background thread so the screensaver keeps rendering at
60 fps even while it watches for that wake gesture. It's silent, saves nothing,
and is configured in `config.py` under `SCREENSAVER_*` (`SCREENSAVER_TIMEOUT`,
`SCREENSAVER_WAKE_SWING`, `SCREENSAVER_DEMO_MODE`, `CAMERA_DIM_SCREENSAVER`,
...).

The window is resizable (drag its edges) and **F11** toggles fullscreen.
Sound effects play when you flap (hard mode), score a point, and crash.
Missing assets or an unavailable audio device simply disable sound without
affecting the game.
The leaderboard panel on the right is always visible with separate **EASY**,
**HARD** and **SQUAT** boards (top 5 each); the camera preview sits on the left
with a live line showing your hand (or torso in squat mode) height. On top of the
preview the tracked body is drawn as a skeleton with joint dots, recoloured by
gesture (green = neutral, gold = pinch, red = fist) for hands, or by validity
(green = good posture, red = out of range / bending) for the squat pose, so you
can see exactly what the tracker sees.

### Wayland / Hyprland note

If fullscreen misbehaves on your Wayland compositor, force the XWayland
backend instead:

```sh
SDL_VIDEODRIVER=x11 uv run cv-flappy
```

The game logic runs on a fixed 960x640 virtual playfield scaled to fit the
window, so gameplay is identical at any resolution.

The leaderboard is stored as `leaderboard.json` in the directory the game is
run from (`{"easy": [...], "hard": [...], "squat": [...]}`, top 50 entries per
board, newest date included).

import os
from pathlib import Path


def _load_dotenv() -> None:
    path = Path.cwd() / ".env"
    if not path.is_file():
        path = Path(__file__).resolve().parents[2] / ".env"
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


_load_dotenv()

FPS = 60
WINDOW_TITLE = "cv-flappy"
DEFAULT_WINDOW_SIZE = (1280, 800)

VIRTUAL_PLAYFIELD_W = 960
VIRTUAL_PLAYFIELD_H = 640
GROUND_H = 44
GROUND_Y = VIRTUAL_PLAYFIELD_H - GROUND_H

MARGIN = 16
LB_W_FRAC = 0.17
LB_MIN_W = 190
LB_MAX_W = 300
CAM_W_FRAC = 0.19
CAM_MIN_W = 200
CAM_MAX_W = 320

BIRD_X = 170
BIRD_RADIUS = 14
PLAYFIELD_MAP_MARGIN = 70

GRAVITY = 1400.0
MAX_FALL_SPEED = 700.0
FLAP_STRENGTH = -420.0
FLAP_COOLDOWN = 0.15
PIPE_FOLLOW_SMOOTHING = 0.12
PIPE_HARD_Y_RANDOM = 140.0
PIPE_HARD_Y_RANDOM_LATE_PER_POINT = 6.0
PIPE_HARD_Y_RANDOM_MAX = 360.0
PINCH_ENGAGE_RATIO = 0.5
PINCH_RELEASE_RATIO = 0.75
PINCH_SMOOTHING = 0.5
FIST_CURLED_FINGERS = 3
GESTURE_HOLD_FRAMES = 2
CAM_WIDTH = 960
CAM_HEIGHT = 540
HAND_DETECTION_CONFIDENCE = 0.4
HAND_PRESENCE_CONFIDENCE = 0.4
HAND_TRACKING_CONFIDENCE = 0.4
VISION_CLAHE = True
CLAHE_CLIP_LIMIT = 2.0
CLAHE_GRID = 8

PIPE_WIDTH = 60
PIPE_CAP_H = 14
PIPE_GAP = 190
PIPE_SPEED = 160.0
PIPE_SPEED_MAX = 600.0
PIPE_SPEEDUP_PER_POINT = 4.0
PIPE_LATE_SCORE = 40
PIPE_LATE_SPEEDUP_PER_POINT = 14.0
PIPE_SPACING = 270
PIPE_GAP_MARGIN = 40

HAND_SMOOTHING = 0.35
HAND_MAP_LOW = 0.15
HAND_MAP_HIGH = 0.85
MENU_SELECT_FRAMES = 10
MENU_PINCH_SECONDS = 1.2

COUNTDOWN_SECONDS = 3
GAME_OVER_INPUT_DELAY = 0.5

SCREENSAVER_ENABLED = True
SCREENSAVER_TIMEOUT = 30.0
SCREENSAVER_WAKE_DELAY = 1.0
SCREENSAVER_RESTART_DELAY = 1.5
SCREENSAVER_DEMO_MODE = "easy"
SCREENSAVER_MUTE = True
SCREENSAVER_SHOW_CAMERA = False
SCREENSAVER_SHOW_LEADERBOARD = False
SCREENSAVER_GHOST_HAND = False
SCREENSAVER_WOBBLE = 14.0
SCREENSAVER_WAKE_SWING = 0.25
SCREENSAVER_TARGET_SMOOTHING = 0.10

CAMERA_DIM_MENU = 160
CAMERA_DIM_PLAY = 120
CAMERA_DIM_SCREENSAVER = 190

_PKG_ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"
ASSETS_DIR = _PKG_ASSETS_DIR if _PKG_ASSETS_DIR.is_dir() else Path.cwd() / "assets"

SOUND_ENABLED = True
SOUND_VOLUME = 0.5
SFX_FLAP = "flap.mp3"
SFX_POINT = "point.mp3"
SFX_DIE = "die-sfx.mp3"

INTRO_SHEET = "close_fist_bw.png"
INTRO_COLS = 8
INTRO_ROWS = 7
INTRO_FRAME_W = 202
INTRO_FRAME_H = 200
INTRO_FPS = 25
INTRO_MIN_SECONDS = 2.0
INTRO_MOVE_SWING = 0.25

_PKG_MODELS_DIR = Path(__file__).resolve().parents[2] / "models"
MODELS_DIR = _PKG_MODELS_DIR if _PKG_MODELS_DIR.is_dir() else Path.cwd() / "models"

TTS_ENABLED = True
TTS_VOICE = "cs_CZ-jirka-medium.onnx"
TTS_MODEL_PATH = MODELS_DIR / TTS_VOICE
TTS_CONFIG_PATH = MODELS_DIR / (TTS_VOICE + ".json")

LEADERBOARD_PATH = Path.cwd() / "leaderboard.json"
HAND_LANDMARKER_PATH = Path.cwd() / "hand_landmarker.task"
HAND_LANDMARKER_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
MAX_LEADERBOARD_ENTRIES = 50
TOP_N_PER_BOARD = 5
MAX_NAME_LENGTH = 12

STT_ENABLED = True
STT_PROVIDER = os.environ.get("CV_FLAPPY_STT_PROVIDER", "groq").strip().lower()
GROQ_KEY = os.environ.get("GROQ_KEY") or os.environ.get("GROQ_API_KEY") or ""
STT_GROQ_URL = os.environ.get(
    "CV_FLAPPY_GROQ_URL", "https://api.groq.com/openai/v1/audio/transcriptions"
)
STT_GROQ_MODEL = os.environ.get("CV_FLAPPY_GROQ_MODEL", "whisper-large-v3")
GEMINI_KEY = (
    os.environ.get("GEMINI_API_KEY")
    or os.environ.get("GOOGLE_API_KEY")
    or ""
)
STT_GEMINI_MODEL = os.environ.get("CV_FLAPPY_GEMINI_MODEL", "gemini-2.5-flash")
STT_GEMINI_URL = os.environ.get(
    "CV_FLAPPY_GEMINI_URL",
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
)
STT_LANGUAGE = "cs"
STT_PROMPT = "Jméno hráče:"
STT_SAMPLE_RATE = 16000
STT_DEVICE = None
STT_RECORD_SECONDS = 5.0
STT_SILENCE_SECONDS = 0.8
STT_SPEECH_THRESHOLD = 0.02
STT_TIMEOUT = 20.0
STT_NORMALIZE = True

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BG_DARK = (18, 22, 30)
SKY_TOP = (86, 152, 225)
SKY_BOTTOM = (176, 226, 244)
SUN = (255, 236, 120)
SUN_HALO = (255, 246, 190)
CLOUD = (255, 255, 255)
GREEN = (111, 196, 69)
DARK_GREEN = (74, 135, 46)
PIPE_LIGHT = (163, 224, 116)
GRASS = (106, 190, 48)
BROWN = (146, 102, 60)
DARK_BROWN = (110, 78, 46)
YELLOW = (255, 204, 0)
ORANGE = (243, 156, 18)
RED = (231, 76, 60)
GRAY = (150, 150, 150)
PANEL_BORDER = (230, 230, 230)
BOX_BG = (25, 30, 40)
INPUT_BOX = (60, 70, 90)
GOLD = (255, 215, 0)
SILVER = (211, 211, 211)
BRONZE = (205, 127, 50)

HAND_IDLE_COLOR = (111, 196, 69)
HAND_PINCH_COLOR = (255, 215, 0)
HAND_FIST_COLOR = (231, 76, 60)
HAND_TIP_COLOR = (255, 255, 255)
LANDMARK_RADIUS = 3
LANDMARK_LINE_WIDTH = 2

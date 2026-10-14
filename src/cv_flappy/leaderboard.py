import json
from datetime import date

from .config import LEADERBOARD_PATH, MAX_LEADERBOARD_ENTRIES

DIFFICULTIES = ("easy", "hard")


def _read() -> dict:
    try:
        with open(LEADERBOARD_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(data, dict):
        return {
            key: value
            for key, value in data.items()
            if key in DIFFICULTIES and isinstance(value, list)
        }
    if isinstance(data, list):
        return {"easy": data}
    return {}


def load(difficulty: str = "easy") -> list[dict]:
    board = _read().get(difficulty, [])
    return [
        entry
        for entry in board
        if isinstance(entry, dict)
        and isinstance(entry.get("name"), str)
        and isinstance(entry.get("score"), int)
    ]


def save(name: str, score: int, difficulty: str = "easy") -> list[dict]:
    data = _read()
    board = data.get(difficulty, [])
    board.append(
        {"name": name, "score": score, "date": date.today().isoformat()}
    )
    board.sort(key=lambda entry: entry["score"], reverse=True)
    data[difficulty] = board[:MAX_LEADERBOARD_ENTRIES]
    with open(LEADERBOARD_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return data[difficulty]


def top(difficulty: str, n: int) -> list[dict]:
    return load(difficulty)[:n]

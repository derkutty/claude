"""Verlauf aller hochgeladenen Videos – damit sich Themen nicht wiederholen
und Claude aus den Aufrufzahlen lernen kann."""

import json

from .config import HISTORY_PATH


def load_history() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))


def save_history(history: list[dict]) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

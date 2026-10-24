"""Formate gegeneinander testen und das beste bevorzugen.

Gemessen werden die Aufrufe jedes Videos 3 Tage nach dem Upload – so haben ältere Videos keinen Vorteil.
Testphase: Die Formate wechseln sich ab, bis jedes genug bewertete Videos hat.
Danach: Das Format mit den meisten Aufrufen (Median) bekommt den Großteil der Uploads,
der Rest testet weiter die anderen, falls sich der Geschmack des Publikums ändert.
"""

import random
from datetime import datetime, timedelta, timezone
from statistics import median

from .config import ROOT

RATING_AGE = timedelta(days=3)
REPORT_PATH = ROOT / "data" / "report.md"


def snapshot_ratings(history: list[dict], now: datetime) -> None:
    """Aufrufzahl festhalten, sobald ein Video 3 Tage alt ist (einmalig pro Video)."""
    for h in history:
        if "views_3d" not in h and isinstance(h.get("views"), int):
            if now - datetime.fromisoformat(h["date"]) >= RATING_AGE:
                h["views_3d"] = h["views"]


def _ratings(history: list[dict], fmt: str) -> list[int]:
    return [h["views_3d"] for h in history if h.get("format") == fmt and "views_3d" in h]


def leader(formats: list[str], history: list[dict], min_rated: int) -> str | None:
    """Das beste Format, sobald jedes Format genug bewertete Videos hat – sonst None (Testphase)."""
    if any(len(_ratings(history, f)) < min_rated for f in formats):
        return None
    return max(formats, key=lambda f: median(_ratings(history, f)))


def choose_format(cfg: dict, history: list[dict]) -> str:
    exp = cfg["experiment"]
    formats = exp["formats"]
    if len(formats) == 1:
        return formats[0]
    best = leader(formats, history, exp["min_videos_per_format"])
    if best is None:
        # Testphase: immer das Format, von dem es bisher am wenigsten Videos gibt.
        counts = {f: sum(1 for h in history if h.get("format") == f) for f in formats}
        return min(formats, key=lambda f: (counts[f], formats.index(f)))
    if random.random() < exp["explore_share"]:
        return random.choice([f for f in formats if f != best])
    return best


def write_report(cfg: dict, history: list[dict], labels: dict[str, str]) -> None:
    exp = cfg["experiment"]
    formats = exp["formats"]
    need = exp["min_videos_per_format"]
    best = leader(formats, history, need)

    lines = ["# Format-Test", ""]
    if len(formats) == 1:
        lines.append(f"Es läuft nur noch ein Format: **{labels.get(formats[0], formats[0])}**.")
    elif best is None:
        missing = sum(max(0, need - len(_ratings(history, f))) for f in formats)
        lines.append(f"**Testphase.** Es fehlen noch {missing} bewertete Videos, bis ausgewertet wird. "
                     "Ein Video gilt als bewertet, wenn es 3 Tage online ist.")
    else:
        share = round((1 - exp["explore_share"]) * 100)
        lines.append(f"**Aktueller Gewinner: {labels.get(best, best)}** – bekommt etwa {share} % der Uploads.")
    lines += ["", "| Format | Videos | davon bewertet | Aufrufe nach 3 Tagen (Median) | Bestes Video |", "|---|---|---|---|---|"]
    for f in formats:
        videos = [h for h in history if h.get("format") == f]
        rated = _ratings(history, f)
        top = max((h for h in videos if "views_3d" in h), key=lambda h: h["views_3d"], default=None)
        top_text = f'„{top["title"]}“ ({top["views_3d"]})' if top else "–"
        lines.append(f"| {labels.get(f, f)} | {len(videos)} | {len(rated)} | {round(median(rated)) if rated else '–'} | {top_text} |")
    lines += ["", f"Zuletzt aktualisiert: {datetime.now(timezone.utc):%d.%m.%Y %H:%M} UTC", ""]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")

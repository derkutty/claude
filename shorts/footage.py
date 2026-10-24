"""Hochkant-Stock-Videos von Pexels (kostenlos, kommerziell nutzbar, keine Namensnennung nötig)."""

import random
from pathlib import Path

import requests

SEARCH_URL = "https://api.pexels.com/videos/search"
FALLBACK_QUERIES = ["abstract background", "nature aerial", "city night"]


def _best_file(video: dict) -> dict | None:
    files = [f for f in video["video_files"] if f.get("height") and f.get("width") and f["height"] > f["width"]]
    if not files:
        return None
    # Möglichst nah an 1920 px Höhe, aber nicht riesig (spart Download-Zeit).
    return min(files, key=lambda f: abs(f["height"] - 1920))


def _search(query: str, api_key: str) -> list[dict]:
    resp = requests.get(
        SEARCH_URL,
        headers={"Authorization": api_key},
        params={"query": query, "orientation": "portrait", "size": "medium", "per_page": 15},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("videos", [])


def fetch_clip(query: str, min_seconds: float, api_key: str, used_ids: set[int], out: Path) -> Path:
    """Lädt ein passendes Clip-Video herunter. Bevorzugt Clips, die lang genug für die Szene sind."""
    for q in [query, *FALLBACK_QUERIES]:
        candidates = [v for v in _search(q, api_key) if v["id"] not in used_ids and _best_file(v)]
        if not candidates:
            continue
        long_enough = [v for v in candidates if v.get("duration", 0) >= min_seconds]
        # Unter den ersten Treffern zufällig wählen, damit nicht jedes Video gleich aussieht.
        video = random.choice((long_enough or candidates)[:5])
        used_ids.add(video["id"])
        with requests.get(_best_file(video)["link"], stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(out, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        return out
    raise RuntimeError(f"Kein Stock-Video für '{query}' gefunden.")

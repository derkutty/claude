"""Sprecherstimme mit edge-tts (kostenlos) inklusive Wort-Zeitstempeln für die Untertitel."""

import asyncio
from dataclasses import dataclass
from pathlib import Path

import edge_tts

from .render import probe_duration

TICKS_PER_SECOND = 10_000_000  # edge-tts liefert Zeiten in 100-ns-Einheiten


@dataclass
class Word:
    text: str
    start: float
    end: float


@dataclass
class SceneAudio:
    path: Path
    duration: float
    words: list[Word]  # Zeiten relativ zum Beginn der Szene


async def _synthesize(text: str, voice: str, rate: str, out: Path) -> list[Word]:
    communicate = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    words: list[Word] = []
    with open(out, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / TICKS_PER_SECOND
                words.append(Word(chunk["text"], start, start + chunk["duration"] / TICKS_PER_SECOND))
    return words


def _speak(text: str, voice_cfg: dict, out: Path) -> list[Word]:
    voices = [voice_cfg["name"], *([voice_cfg["fallback"]] if voice_cfg.get("fallback") else [])]
    for i, name in enumerate(voices):
        try:
            words = asyncio.run(_synthesize(text, name, voice_cfg["rate"], out))
            if out.stat().st_size > 0:
                return words
        except Exception as e:
            if i == len(voices) - 1:
                raise
            print(f"Warnung: Stimme {name} nicht verfügbar ({e}), nehme {voices[i + 1]}.")
    raise RuntimeError(f"Keine Sprachausgabe für: {text!r}")


def synthesize_scenes(narrations: list[str], voice_cfg: dict, workdir: Path) -> list[SceneAudio]:
    scenes = []
    for i, text in enumerate(narrations):
        out = workdir / f"voice_{i:02d}.mp3"
        words = _speak(text, voice_cfg, out)
        # Kleine Pause nach jedem Satz, damit der Schnitt nicht mitten im Ausklingen passiert.
        duration = max(probe_duration(out), words[-1].end if words else 0) + 0.15
        scenes.append(SceneAudio(out, duration, words))
    return scenes

"""Gemeinsamer Ablauf für Rätsel-Formate: Intro → (Frage, Countdown, Auflösung) × n → Outro."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image

from .. import render, voice
from ..config import MUSIC_DIR

Draw = Callable[[Image.Image], None]


@dataclass
class Round:
    question_speech: str
    answer_speech: str
    draw_question: Callable[[Image.Image, int], None]  # bekommt die aktuelle Countdown-Zahl
    draw_reveal: Draw


def build(intro_speech: str, draw_intro: Draw, rounds: list[Round], outro_speech: str, draw_outro: Draw,
          background: Image.Image, countdown_seconds: int, cfg: dict, workdir: Path) -> Path:
    video_cfg = cfg["video"]
    speeches = [intro_speech]
    for r in rounds:
        speeches += [r.question_speech, r.answer_speech]
    speeches.append(outro_speech)
    audio = iter(voice.synthesize_scenes(speeches, cfg["voice"]["name"], cfg["voice"]["rate"], workdir))
    sfx = render.make_sfx(workdir)

    segments: list[Path] = []

    def add(draw: Draw, duration: float, sounds: list[tuple[Path, float]]) -> None:
        i = len(segments)
        img = background.copy()
        draw(img)
        png = workdir / f"seg_{i:03d}.png"
        img.convert("RGB").save(png)
        segments.append(render.segment(png, duration, sounds, video_cfg, workdir / f"seg_{i:03d}.mp4"))

    a = next(audio)
    add(draw_intro, a.duration + 0.2, [(a.path, 0.0)])
    for r in rounds:
        q = next(audio)
        add(lambda img: r.draw_question(img, countdown_seconds), q.duration + 0.2,
            [(sfx["whoosh"], 0.0), (q.path, 0.15)])
        for n in range(countdown_seconds, 0, -1):
            add(lambda img, n=n: r.draw_question(img, n), 1.0, [(sfx["tick"], 0.0)])
        ans = next(audio)
        add(r.draw_reveal, ans.duration + 0.9, [(sfx["ding"], 0.0), (ans.path, 0.35)])
    o = next(audio)
    add(draw_outro, o.duration + 0.6, [(o.path, 0.0)])

    return render.concat_segments(segments, MUSIC_DIR, video_cfg, workdir / "short.mp4")

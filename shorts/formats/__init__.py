"""Die verschiedenen Video-Formate. Jedes Modul hat NAME, LABEL und create(cfg, history, workdir) -> Short."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Short:
    topic: str
    title: str
    hook: str
    description: str
    tags: list[str]
    video: Path
    hashtags: list[str] = field(default_factory=list)


def registry() -> dict:
    from . import emoji, facts, laender, quiz
    return {m.NAME: m for m in (laender, quiz, emoji, facts)}

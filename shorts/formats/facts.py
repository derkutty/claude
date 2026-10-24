"""Fakten mit Sprecherstimme, echten Stock-Videoclips (Pexels) und Wort-für-Wort-Untertiteln."""

from pathlib import Path

from .. import footage, render, voice
from ..claude import FACT_RULE, ask_json, channel_context
from ..config import FONTS_DIR, MUSIC_DIR, require_env
from . import Short

NAME = "fakten"
LABEL = "Fakten mit Videoclips"

SYSTEM = f"""Du schreibst Skripte für YouTube Shorts, die Menschen bis zum Ende ansehen und teilen.

Was ein Short erfolgreich macht:
- Der erste Satz entscheidet. Er öffnet eine Neugierlücke oder widerspricht einer Erwartung, \
in höchstens 12 Wörtern, ohne Begrüßung oder Vorrede.
- Jeder folgende Satz liefert etwas Neues oder steigert die Spannung; nichts wiederholt sich.
- Die Auflösung kommt spät, aber sie kommt – der Titel darf nichts versprechen, was das Video nicht hält.
- Der letzte Satz leitet natürlich zurück zum Anfang, damit das Video beim Loopen nahtlos wirkt.
- Kurze, gesprochene Sätze. Zahlen so schreiben, wie man sie spricht.

{FACT_RULE}

Die search_query jeder Szene beschreibt ein Bild, das es als Stock-Video wirklich gibt \
(z. B. "brain scan", "ocean waves aerial", "person sleeping bed") – keine abstrakten Begriffe."""

SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string", "description": "Kurzes Thema in 3–6 Wörtern, für die Duplikat-Erkennung."},
        "title": {"type": "string", "description": "YouTube-Titel, max. 70 Zeichen, ohne Hashtags."},
        "hook": {"type": "string", "description": "Der erste Satz des Videos (identisch mit scenes[0].narration)."},
        "scenes": {
            "type": "array",
            "description": "4–8 Szenen. Jede Szene ist ein gesprochener Satz plus passendes Stock-Video.",
            "items": {
                "type": "object",
                "properties": {
                    "narration": {"type": "string", "description": "Gesprochener Text dieser Szene."},
                    "search_query": {
                        "type": "string",
                        "description": "2–4 englische Suchbegriffe für ein passendes, konkretes Stock-Video (Pexels).",
                    },
                },
                "required": ["narration", "search_query"],
                "additionalProperties": False,
            },
        },
        "description": {"type": "string", "description": "YouTube-Beschreibung, 1–3 Sätze, ohne Hashtags."},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "5–12 Such-Tags ohne #."},
    },
    "required": ["topic", "title", "hook", "scenes", "description", "tags"],
    "additionalProperties": False,
}


def create(cfg: dict, history: list[dict], workdir: Path) -> Short:
    fcfg = cfg["formats"][NAME]
    pexels_key = require_env("PEXELS_API_KEY")
    seconds = fcfg["target_seconds"]
    prompt = (
        f"Themen: {fcfg['themes']}\n"
        f"Ziel-Länge: etwa {seconds} Sekunden gesprochen (ca. {int(seconds * 2.6)} Wörter).\n"
        + channel_context(cfg, history)
        + "\n\nSchreib das Skript für das nächste Short."
    )
    data = ask_json(SYSTEM, prompt, SCHEMA)
    scenes = data["scenes"]
    if not scenes:
        raise RuntimeError("Claude hat ein Skript ohne Szenen geliefert.")

    audio = voice.synthesize_scenes([s["narration"] for s in scenes], cfg["voice"], workdir)

    used_ids: set[int] = set()
    scene_videos = []
    for i, (scene, a) in enumerate(zip(scenes, audio)):
        raw = footage.fetch_clip(scene["search_query"], a.duration, pexels_key, used_ids, workdir / f"raw_{i:02d}.mp4")
        scene_videos.append(render.render_scene(raw, a.duration, cfg["video"], workdir / f"scene_{i:02d}.mp4"))

    words, offset = [], 0.0
    for a in audio:
        words += [voice.Word(w.text, w.start + offset, w.end + offset) for w in a.words]
        offset += a.duration
    voice_track = render.concat_voice([a.path for a in audio], [a.duration for a in audio], workdir / "voice.wav")
    captions = render.write_captions(words, cfg["video"], workdir / "captions.ass")
    video = render.assemble(scene_videos, voice_track, captions, MUSIC_DIR, FONTS_DIR, cfg["video"], workdir / "short.mp4")
    return Short(data["topic"], data["title"], data["hook"], data["description"], data["tags"], video, fcfg["hashtags"])

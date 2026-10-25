"""So funktioniert's: animierte Erklär-Grafiken zu Fragen, die sich jeder schon mal gestellt hat.

Jede Szene ist ein Baustein (Strichmännchen-Statistik, große Zahl, Balken, Vergleich, Symbol) mit
Überschrift und Untertitel, der Wort für Wort mit der Stimme mitläuft. Claude recherchiert vorher
mit der Websuche; die Quellen landen in der Beschreibung.
"""

import json
from pathlib import Path

from .. import render, voice, web
from ..claude import FACT_RULE, ask_json, channel_context, research
from ..config import MUSIC_DIR
from . import Short

NAME = "erklaert"
LABEL = "So funktioniert's"
TEMPLATE = Path(__file__).with_name("erklaert.html")
PALETTE = {"accent": "#e3ff3b", "people": "#7dd3fc"}

RESEARCH_SYSTEM = f"""Du bereitest animierte Erklär-Shorts für YouTube vor. Jedes Video beantwortet eine \
Frage, die sich viele heimlich stellen – über den eigenen Körper, Psychologie, Beziehungen und Dating, \
Alltagsphänomene oder Länder und Kulturen. Beispiele: "Warum stinkt der eigene Furz weniger?", \
"Wieso verlieben wir uns in bestimmte Menschen?", "Warum sind Niederländer so groß?"

Die besten Fragen sind ein bisschen peinlich oder überraschend, betreffen fast jeden und haben eine \
klare, belegte Antwort – idealerweise mit einer Zahl aus einer Studie, die man als Grafik zeigen kann.

Recherchiere mit der Websuche, bevor du etwas festlegst: nur Erkenntnisse aus seriösen Quellen \
(Studien, Fachgesellschaften, Statistikämter, große Medien, die Studien zitieren). Findest du keine \
belastbare Antwort, nimm eine andere Frage.

Bei Ländern, Kulturen, Geschlechtern oder anderen Gruppen: erklären statt bewerten. Keine Klischees, \
keine Abwertung, keine Verallgemeinerungen über Menschen – nur belegte Hintergründe (Geschichte, \
Klima, Gene, Studien). Keine Gesundheitsratschläge über allgemein anerkanntes Wissen hinaus.

{FACT_RULE}

Antworte mit Notizen: die Frage, die Antwort in 4–6 Schritten, alle Zahlen mit Quelle und Jahr, \
und die Quellen-URLs."""

SYSTEM = """Du machst aus Recherche-Notizen das Skript für ein animiertes Erklär-Short von etwa \
30 Sekunden. Kurz, direkt, ein bisschen frech – wie ein Freund, der etwas Verblüffendes erzählt.

- question: die Frage des Videos, wird als Titel genutzt.
- title: YouTube-Titel, max. 70 Zeichen, ohne Hashtags, darf die Frage sein.
- hook: der gesprochene Satz der ersten Szene.
- scenes: 5 bis 7 Szenen. Die erste Szene ist "titel" und stellt die Frage. Danach baust du die \
Antwort Schritt für Schritt auf; die letzte Szene liefert die Auflösung oder eine Pointe, die zum \
Kommentieren einlädt.
  - type: "titel" (großes Emoji + Frage), "symbol" (großes Emoji für einen Gedanken), \
"menschen" (Strichmännchen, von denen einige hervorgehoben sind – für Anteile wie "3 von 10"), \
"zahl" (eine große Zahl), "balken" (2–4 Werte im Vergleich), "vergleich" (zwei Seiten gegenüber).
  - headline: 2–6 Wörter, groß im Bild. Das wichtigste Wort mit *Sternchen* markieren, z. B. "*HÄLFTE* ALLER LIKES".
  - narration: was gesprochen wird, höchstens 14 Wörter. Zahlen so schreiben, wie man sie spricht.
  - emoji: für titel/symbol ein passendes Emoji, sonst leer.
  - total/highlight: für menschen (total 10 oder 20, highlight = wie viele hervorgehoben), sonst 0.
  - number/decimals/unit: für zahl (und unit/decimals auch für balken), sonst 0 bzw. leer.
  - label: für menschen/zahl die Erklärung unter der Grafik (z. B. "der Männer bekommen *50 %* der Likes"), sonst leer.
  - items: für balken 2–4 Einträge (label, value, emoji optional), für vergleich genau 2 Einträge \
(emoji, label, sub = kurze Unterzeile), sonst leer.
- sources: nur URLs aus den Notizen.
Übernimm nur Zahlen und Fakten, die in den Notizen stehen."""

ITEM = {
    "type": "object",
    "properties": {
        "label": {"type": "string"},
        "value": {"type": "number"},
        "emoji": {"type": "string"},
        "sub": {"type": "string"},
    },
    "required": ["label", "value", "emoji", "sub"],
    "additionalProperties": False,
}
SCENE = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["titel", "symbol", "menschen", "zahl", "balken", "vergleich"]},
        "headline": {"type": "string"},
        "narration": {"type": "string"},
        "emoji": {"type": "string"},
        "total": {"type": "integer"},
        "highlight": {"type": "integer"},
        "number": {"type": "number"},
        "decimals": {"type": "integer", "enum": [0, 1, 2]},
        "unit": {"type": "string"},
        "label": {"type": "string"},
        "items": {"type": "array", "items": ITEM},
    },
    "required": ["type", "headline", "narration", "emoji", "total", "highlight", "number", "decimals",
                 "unit", "label", "items"],
    "additionalProperties": False,
}
SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string", "description": "Thema in 2–6 Wörtern, für die Duplikat-Erkennung."},
        "question": {"type": "string"},
        "title": {"type": "string"},
        "hook": {"type": "string"},
        "scenes": {"type": "array", "items": SCENE},
        "description": {"type": "string", "description": "YouTube-Beschreibung, 1–2 Sätze, ohne Hashtags und ohne Quellen."},
        "sources": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "5–12 Such-Tags ohne #."},
    },
    "required": ["topic", "question", "title", "hook", "scenes", "description", "sources", "tags"],
    "additionalProperties": False,
}


def _valid(data: dict) -> bool:
    scenes = data["scenes"]
    if not 4 <= len(scenes) <= 8 or scenes[0]["type"] != "titel":
        return False
    for s in scenes:
        if len(s["narration"].split()) > 18:
            return False
        if s["type"] == "menschen" and not (s["total"] in (10, 20) and 0 < s["highlight"] <= s["total"]):
            return False
        if s["type"] == "balken" and not 2 <= len(s["items"]) <= 4:
            return False
        if s["type"] == "vergleich" and len(s["items"]) != 2:
            return False
    return True


def _write(cfg: dict, history: list[dict]) -> dict:
    fcfg = cfg["formats"][NAME]
    notes = research(
        RESEARCH_SYSTEM,
        f"Themenbereiche: {fcfg['themes']}\n" + channel_context(cfg, history)
        + "\n\nWähle die nächste Frage und recherchiere sie.",
    )
    prompt = f"Sprache: {cfg['channel']['language']}\n\nRecherche-Notizen:\n{notes}"
    for _ in range(2):
        data = ask_json(SYSTEM, prompt, SCHEMA)
        if _valid(data):
            return data
    raise RuntimeError("Claude hat kein gültiges Erklär-Skript geliefert.")


def _caption_words(text: str, timed: list, offset: float) -> list[dict]:
    """Wörter für den Mitlauf-Untertitel: Originaltext (mit Satzzeichen), Zeiten von der Stimme."""
    tokens = text.split()
    if len(tokens) == len(timed):
        return [{"text": tok, "start": w.start + offset} for tok, w in zip(tokens, timed)]
    return [{"text": w.text, "start": w.start + offset} for w in timed]


def create(cfg: dict, history: list[dict], workdir: Path) -> Short:
    data = _write(cfg, history)
    video_cfg = cfg["video"]
    scenes = data["scenes"]
    page_data = {
        "series": cfg["formats"][NAME]["series_label"],
        "number": len(history) + 1,
        "locale": cfg["upload"]["language_code"],
        "palette": PALETTE,
        "scenes": scenes,
    }
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*DATA*/", json.dumps(page_data, ensure_ascii=False))

    audio = voice.synthesize_scenes([s["narration"] for s in scenes], cfg["voice"], workdir)
    sfx = render.make_sfx(workdir)

    segments, start = [], 0.0
    with web.page(html, video_cfg) as pg:
        for i, (scene, a) in enumerate(zip(scenes, audio)):
            voice_delay = 0.15
            duration = max(2.6, a.duration + voice_delay + 0.35)
            state = {"index": i, "words": _caption_words(scene["narration"], a.words, voice_delay)}
            sounds = [(a.path, voice_delay), (sfx["whoosh"], 0.0)]
            if scene["type"] in ("menschen", "zahl", "balken"):
                sounds.append((sfx["ding"], 1.1))
            silent = web.record(pg, state, duration, start, video_cfg, workdir / f"scene_{i:02d}_raw.mp4")
            segments.append(render.add_sounds(silent, duration, sounds, video_cfg, workdir / f"scene_{i:02d}.mp4"))
            start += duration
    video = render.concat_segments(segments, MUSIC_DIR, video_cfg, workdir / "short.mp4")

    description = data["description"]
    if data["sources"]:
        description += "\n\nQuellen:\n" + "\n".join(data["sources"])
    return Short(data["topic"], data["title"], data["hook"], description, data["tags"], video,
                 cfg["formats"][NAME]["hashtags"])

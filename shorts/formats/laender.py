"""Länder-Check: Ranking oder Vergleich mehrerer Länder, mit Flaggen, animierten Zahlen und Balken.

Claude recherchiert die Zahlen vorher mit der Websuche; die Quellen landen in der Videobeschreibung.
Die Szenen sind eine HTML-Seite (laender.html), die Chromium Bild für Bild aufnimmt.
"""

import json
import random
from pathlib import Path

from .. import render, voice, web
from ..claude import FACT_RULE, ask_json, channel_context, research
from ..config import MUSIC_DIR
from . import Short

NAME = "laender"
LABEL = "Länder-Check"
TEMPLATE = Path(__file__).with_name("laender.html")

PALETTES = [
    {"accent": "#facc15", "accent2": "#38bdf8", "bg1": "#0b1020", "bg2": "#1b1446"},
    {"accent": "#34d399", "accent2": "#818cf8", "bg1": "#04131a", "bg2": "#0f2f3d"},
    {"accent": "#fb923c", "accent2": "#f472b6", "bg1": "#140a1f", "bg2": "#3b0d3a"},
    {"accent": "#a3e635", "accent2": "#22d3ee", "bg1": "#08130b", "bg2": "#11331f"},
    {"accent": "#f87171", "accent2": "#fbbf24", "bg1": "#1a0909", "bg2": "#3d1212"},
]

RESEARCH_SYSTEM = f"""Du bereitest Länder-Shorts für YouTube vor. Es gibt zwei Arten:
- "ranking": Länder werden nach einer Zahl verglichen (z. B. Schlaf pro Nacht, Kaffee pro Kopf, Urlaubstage).
- "vergleich": Wie unterschiedlich etwas in verschiedenen Ländern ist (z. B. typisches Frühstück, \
wie man "Prost" sagt, Glückszahlen).

Wähle ein Thema, das überrascht und mit dem sich das Publikum vergleichen will. Wenn es passt, \
gehört das eigene Land des Publikums dazu – "Wo steht Deutschland?" funktioniert besonders gut.

Recherchiere mit der Websuche, bevor du etwas festlegst:
- Bei "ranking": nur aktuelle Zahlen aus verlässlichen Quellen (OECD, Weltbank, UN, WHO, Eurostat, \
nationale Statistikämter, große Studien). Alle Länder mit derselben Kennzahl aus derselben Quelle und \
demselben Jahr, damit der Vergleich fair ist.
- Bei "vergleich": nur gut belegte, verbreitete Gepflogenheiten, keine Klischees.
- Findest du keine verlässlichen Daten, nimm ein anderes Thema.

{FACT_RULE}

Antworte mit deinen Ergebnissen als Notizen: Thema, Art, Frage, für jedes Land den Wert (mit Einheit \
und Jahr) bzw. die Ausprägung, einen kurzen überraschenden Fakt, und die Quellen-URLs."""

SYSTEM = """Du machst aus Recherche-Notizen das Skript für ein Länder-Short.

- hook: höchstens 9 Wörter, macht neugierig auf das Ergebnis ("Platz eins hätte ich nie erwartet!").
- question: die Frage, die oben im Video steht, höchstens 8 Wörter.
- items: in der Reihenfolge, in der sie gezeigt werden. Bei "ranking" zuerst der letzte Platz, zum \
Schluss Platz 1 – so bleibt es spannend.
- spoken: was zu diesem Land gesprochen wird, höchstens 18 Wörter, natürlich und lebendig. Bei \
"ranking" nennt der Satz Platz, Land und Wert; Zahlen so schreiben, wie man sie spricht.
- fact: ein kurzer überraschender Satz (höchstens 12 Wörter), der unter der Zahl angezeigt wird.
- headline: bei "vergleich" die Ausprägung in 1–4 Wörtern (wird groß angezeigt); bei "ranking" leer lassen.
- value: bei "ranking" die Zahl (ohne Einheit); bei "vergleich" 0.
- outro: fordert auf zu kommentieren, z. B. "Hättest du das gedacht? Schreib's in die Kommentare!"
- sources: nur URLs aus den Notizen.
Übernimm nur Zahlen und Fakten, die in den Notizen stehen."""

SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string", "description": "Thema in 2–6 Wörtern, für die Duplikat-Erkennung."},
        "title": {"type": "string", "description": "YouTube-Titel, max. 70 Zeichen, ohne Hashtags."},
        "mode": {"type": "string", "enum": ["ranking", "vergleich"]},
        "hook": {"type": "string"},
        "question": {"type": "string"},
        "unit": {"type": "string", "description": "Einheit hinter der Zahl, z. B. 'Stunden pro Nacht'. Bei 'vergleich' leer."},
        "decimals": {"type": "integer", "enum": [0, 1, 2], "description": "Nachkommastellen der Zahlen."},
        "place_word": {"type": "string", "description": "Wort für 'Platz' in der Videosprache, in Großbuchstaben."},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "country": {"type": "string", "description": "Ländername in der Videosprache."},
                    "iso2": {"type": "string", "description": "ISO-3166-Ländercode, zwei Großbuchstaben (z. B. DE)."},
                    "value": {"type": "number"},
                    "headline": {"type": "string"},
                    "fact": {"type": "string"},
                    "spoken": {"type": "string"},
                },
                "required": ["country", "iso2", "value", "headline", "fact", "spoken"],
                "additionalProperties": False,
            },
        },
        "outro": {"type": "string"},
        "description": {"type": "string", "description": "YouTube-Beschreibung, 1–2 Sätze, ohne Hashtags und ohne Quellen."},
        "sources": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "5–12 Such-Tags ohne #."},
    },
    "required": ["topic", "title", "mode", "hook", "question", "unit", "decimals", "place_word", "items",
                 "outro", "description", "sources", "tags"],
    "additionalProperties": False,
}


def flag(iso2: str) -> str:
    """Flaggen-Emoji aus dem Ländercode bauen – zuverlässiger, als Claude Flaggen schreiben zu lassen."""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso2.upper())


def _write(cfg: dict, history: list[dict]) -> dict:
    fcfg = cfg["formats"][NAME]
    n = fcfg["countries"]
    notes = research(
        RESEARCH_SYSTEM,
        f"Themenbereiche: {fcfg['themes']}\nAnzahl Länder: genau {n}\n" + channel_context(cfg, history)
        + "\n\nWähle das nächste Thema und recherchiere es.",
    )
    prompt = f"Anzahl Länder: genau {n}\nSprache: {cfg['channel']['language']}\n\nRecherche-Notizen:\n{notes}"
    for _ in range(2):
        data = ask_json(SYSTEM, prompt, SCHEMA)
        items = data["items"]
        if len(items) == n and all(len(i["iso2"]) == 2 and i["iso2"].isalpha() for i in items):
            return data
    raise RuntimeError("Claude hat kein gültiges Länder-Skript geliefert.")


def create(cfg: dict, history: list[dict], workdir: Path) -> Short:
    data = _write(cfg, history)
    video_cfg = cfg["video"]
    items = data["items"]
    n = len(items)
    page_data = {
        "mode": data["mode"],
        "question": data["question"],
        "hook": data["hook"],
        "outro": data["outro"],
        "unit": data["unit"],
        "decimals": data["decimals"],
        "place_word": data["place_word"],
        "locale": cfg["upload"]["language_code"],
        "palette": random.choice(PALETTES),
        "items": [{**it, "flag": flag(it["iso2"]), "rank": n - k, "index": k} for k, it in enumerate(items)],
    }
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*DATA*/", json.dumps(page_data, ensure_ascii=False))

    speeches = [data["hook"], *[it["spoken"] for it in items], data["outro"]]
    audio = voice.synthesize_scenes(speeches, cfg["voice"], workdir)
    sfx = render.make_sfx(workdir)

    plan = [({"scene": "intro"}, audio[0].duration + 0.5, [(audio[0].path, 0.1), (sfx["whoosh"], 0.0)])]
    for k in range(n):
        a = audio[k + 1]
        plan.append(({"scene": "item", "index": k}, max(3.4, a.duration + 0.9),
                     [(sfx["whoosh"], 0.0), (a.path, 0.25), (sfx["ding"], 1.25)]))
    a = audio[-1]
    plan.append(({"scene": "outro"}, max(4.5, a.duration + 1.4), [(a.path, 0.6)]))

    segments, start = [], 0.0
    with web.page(html, video_cfg) as pg:
        for i, (state, duration, sounds) in enumerate(plan):
            silent = web.record(pg, state, duration, start, video_cfg, workdir / f"scene_{i:02d}_raw.mp4")
            segments.append(render.add_sounds(silent, duration, sounds, video_cfg, workdir / f"scene_{i:02d}.mp4"))
            start += duration
    video = render.concat_segments(segments, MUSIC_DIR, video_cfg, workdir / "short.mp4")

    description = data["description"]
    if data["sources"]:
        description += "\n\nQuellen:\n" + "\n".join(data["sources"])
    return Short(data["topic"], data["title"], data["hook"], description, data["tags"], video,
                 cfg["formats"][NAME]["hashtags"])

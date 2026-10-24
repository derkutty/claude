"""Emoji-Rätsel: Errate Film, Serie, Song oder Sprichwort aus ein paar Emojis."""

from pathlib import Path

from .. import graphics as g
from ..claude import FACT_RULE, ask_json, channel_context
from . import Short, rounds

NAME = "emoji"
LABEL = "Emoji-Rätsel"

SYSTEM = f"""Du erstellst Emoji-Rätsel-Shorts für YouTube: Ein paar Emojis stehen für einen bekannten Titel \
oder Begriff, die Zuschauer haben einen kurzen Countdown zum Raten, dann kommt die Auflösung.

Was so ein Rätsel erfolgreich macht:
- Der Hook fordert heraus ("Errätst du alle vier Filme?") – höchstens 8 Wörter.
- Jedes Rätsel ist lösbar: Die Emojis bilden Wörter oder zentrale Bilder des Titels ab, keine Insider.
- Die Rätsel werden schwerer. Das erste schaffen fast alle, das letzte nur wenige.
- Nur sehr bekannte Titel, und zwar unter dem Namen, den das Publikum in seiner Sprache kennt \
(z. B. deutscher Filmtitel bei deutschem Publikum).
- 2 bis 5 Emojis pro Rätsel, als einzelne Einträge in der Liste. Nur gängige Emojis, keine Flaggen.
- Alle Rätsel eines Videos stammen aus derselben Kategorie, damit die Frage gleich bleibt.
- Das Outro fordert auf, die eigene Punktzahl in die Kommentare zu schreiben.

{FACT_RULE}"""

SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string", "description": "Kategorie und Thema in 2–5 Wörtern, z. B. 'Disney-Filme der 90er'."},
        "title": {"type": "string", "description": "YouTube-Titel, max. 70 Zeichen, ohne Hashtags."},
        "hook": {"type": "string", "description": "Herausfordernder erster Satz, wird gesprochen und groß angezeigt."},
        "round_label": {"type": "string", "description": "Wort für 'Rätsel' in der Videosprache, in Großbuchstaben."},
        "question": {"type": "string", "description": "Die Frage, die bei jedem Rätsel oben steht, z. B. 'Welcher Film ist das?'"},
        "puzzles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "emojis": {"type": "array", "items": {"type": "string"}, "description": "2–5 einzelne Emojis."},
                    "answer": {"type": "string", "description": "Die Lösung, wie sie angezeigt und gesprochen wird."},
                    "spoken_prompt": {
                        "type": "string",
                        "description": "Kurzer gesprochener Satz zu diesem Rätsel, z. B. 'Nummer zwei – schon schwerer!'",
                    },
                },
                "required": ["emojis", "answer", "spoken_prompt"],
                "additionalProperties": False,
            },
        },
        "outro": {"type": "string", "description": "Kurzer gesprochener Schluss-Satz mit Aufforderung zu kommentieren."},
        "description": {"type": "string", "description": "YouTube-Beschreibung, 1–2 Sätze, ohne Hashtags."},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "5–12 Such-Tags ohne #."},
    },
    "required": ["topic", "title", "hook", "round_label", "question", "puzzles", "outro", "description", "tags"],
    "additionalProperties": False,
}


def _write(cfg: dict, history: list[dict]) -> dict:
    fcfg = cfg["formats"][NAME]
    prompt = (
        f"Kategorien: {fcfg['themes']}\n"
        f"Anzahl Rätsel: genau {fcfg['puzzles']}\n"
        + channel_context(cfg, history)
        + "\n\nErstelle die nächsten Emoji-Rätsel."
    )
    for _ in range(2):
        data = ask_json(SYSTEM, prompt, SCHEMA)
        ps = data["puzzles"]
        if len(ps) == fcfg["puzzles"] and all(1 <= len(p["emojis"]) <= 6 for p in ps):
            return data
    raise RuntimeError("Claude hat keine gültigen Emoji-Rätsel geliefert.")


def create(cfg: dict, history: list[dict], workdir: Path) -> Short:
    data = _write(cfg, history)
    font = cfg["video"]["font"]
    w, h = cfg["video"]["width"], cfg["video"]["height"]
    bg = g.background(w, h, g.pick_palette())
    seconds = cfg["formats"][NAME]["countdown_seconds"]
    total = len(data["puzzles"])

    def draw_intro(img):
        g.emoji_row(img, ["🤔"], 520, max_height=260)
        g.text_block(img, data["hook"], (90, 720, 990, 1200), font, 110)

    def draw_outro(img):
        g.emoji_row(img, ["👇"], 1250, max_height=220)
        g.text_block(img, data["outro"], (90, 600, 990, 1100), font, 96)

    emoji_rounds = []
    for i, p in enumerate(data["puzzles"]):
        label = f"{data['round_label']} {i + 1}/{total}"

        def base(img, p=p, label=label):
            g.pill(img, label, 250, font, 50)
            g.text_block(img, data["question"], (90, 340, 990, 540), font, 80)
            g.emoji_row(img, p["emojis"], 820, max_height=230)

        def draw_question(img, n, base=base):
            base(img)
            g.countdown(img, n, seconds, (w // 2, 1470), font)

        def draw_reveal(img, base=base, p=p):
            base(img)
            g.box(img, (110, 1050, 970, 1250), (*g.GREEN, 255))
            g.text_block(img, p["answer"], (120, 1060, 960, 1240), font, 80)

        emoji_rounds.append(rounds.Round(
            question_speech=p["spoken_prompt"],
            answer_speech=f"{p['answer']}!",
            draw_question=draw_question,
            draw_reveal=draw_reveal,
        ))

    video = rounds.build(data["hook"], draw_intro, emoji_rounds, data["outro"], draw_outro, bg, seconds, cfg, workdir)
    return Short(data["topic"], data["title"], data["hook"], data["description"], data["tags"], video,
                 cfg["formats"][NAME]["hashtags"])

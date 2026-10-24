"""Quiz-Rätsel: Frage mit drei Antworten, Countdown, Auflösung – mehrere Fragen pro Short."""

import random
from pathlib import Path

from .. import graphics as g
from ..claude import FACT_RULE, ask_json, channel_context
from . import Short, rounds

NAME = "quiz"
LABEL = "Quiz-Rätsel"

SYSTEM = f"""Du erstellst Quiz-Shorts für YouTube: mehrere Fragen mit je drei Antwortmöglichkeiten, \
nach jeder Frage ein kurzer Countdown, dann die Auflösung.

Was so ein Quiz erfolgreich macht:
- Der Hook fordert heraus ("Nur jeder Zehnte schafft alle drei!") – höchstens 8 Wörter.
- Die Fragen werden schwerer. Die erste schaffen die meisten, die letzte nur wenige.
- Die falschen Antworten sind plausibel, damit man wirklich nachdenken muss.
- Die richtige Antwort überrascht oft ein bisschen – das sorgt für Kommentare.
- Fragen sind kurz (höchstens 12 Wörter), Antworten sehr kurz (höchstens 4 Wörter).
- Die Erklärung zur Auflösung ist ein einziger kurzer Satz (höchstens 12 Wörter).
- Das Outro fordert auf, die eigene Punktzahl in die Kommentare zu schreiben.

{FACT_RULE}"""

SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string", "description": "Thema des Quiz in 2–5 Wörtern, z. B. 'Tiere der Tiefsee'."},
        "title": {"type": "string", "description": "YouTube-Titel, max. 70 Zeichen, ohne Hashtags."},
        "hook": {"type": "string", "description": "Herausfordernder erster Satz, wird gesprochen und groß angezeigt."},
        "round_label": {"type": "string", "description": "Wort für 'Frage' in der Videosprache, in Großbuchstaben."},
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}, "description": "Genau drei Antworten."},
                    "correct": {"type": "integer", "enum": [0, 1, 2], "description": "Index der richtigen Antwort."},
                    "explanation": {"type": "string"},
                },
                "required": ["question", "options", "correct", "explanation"],
                "additionalProperties": False,
            },
        },
        "outro": {"type": "string", "description": "Kurzer gesprochener Schluss-Satz mit Aufforderung zu kommentieren."},
        "description": {"type": "string", "description": "YouTube-Beschreibung, 1–2 Sätze, ohne Hashtags."},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "5–12 Such-Tags ohne #."},
    },
    "required": ["topic", "title", "hook", "round_label", "questions", "outro", "description", "tags"],
    "additionalProperties": False,
}

LETTERS = "ABC"


def _write(cfg: dict, history: list[dict]) -> dict:
    fcfg = cfg["formats"][NAME]
    prompt = (
        f"Themenbereiche: {fcfg['themes']}\n"
        f"Anzahl Fragen: genau {fcfg['questions']}\n"
        + channel_context(cfg, history)
        + "\n\nErstelle das nächste Quiz."
    )
    for _ in range(2):
        data = ask_json(SYSTEM, prompt, SCHEMA)
        qs = data["questions"]
        if len(qs) == fcfg["questions"] and all(len(q["options"]) == 3 for q in qs):
            return data
    raise RuntimeError("Claude hat kein gültiges Quiz geliefert (falsche Anzahl Fragen oder Antworten).")


def create(cfg: dict, history: list[dict], workdir: Path) -> Short:
    data = _write(cfg, history)
    font = cfg["video"]["font"]
    w, h = cfg["video"]["width"], cfg["video"]["height"]
    bg = g.background(w, h, g.pick_palette())
    seconds = cfg["formats"][NAME]["countdown_seconds"]
    total = len(data["questions"])

    def draw_intro(img):
        g.emoji_row(img, ["🧠"], 520, max_height=260)
        g.text_block(img, data["hook"], (90, 720, 990, 1200), font, 110)

    def draw_outro(img):
        g.emoji_row(img, ["👇"], 1250, max_height=220)
        g.text_block(img, data["outro"], (90, 600, 990, 1100), font, 96)

    quiz_rounds = []
    for i, q in enumerate(data["questions"]):
        # Reihenfolge mischen, damit die richtige Antwort nicht immer an derselben Stelle steht.
        order = random.sample(range(3), 3)
        options = [q["options"][j] for j in order]
        correct = order.index(q["correct"])
        label = f"{data['round_label']} {i + 1}/{total}"

        def base(img, q=q, options=options, label=label, states=None):
            g.pill(img, label, 250, font, 50)
            g.text_block(img, q["question"], (90, 330, 990, 720), font, 84)
            for k, opt in enumerate(options):
                y = 770 + k * 195
                g.option_row(img, LETTERS[k], opt, (110, y, 970, y + 160), font, (states or ["neutral"] * 3)[k])

        def draw_question(img, n, base=base):
            base(img)
            g.countdown(img, n, seconds, (w // 2, 1470), font)

        def draw_reveal(img, base=base, correct=correct, q=q):
            base(img, states=["correct" if k == correct else "dimmed" for k in range(3)])
            g.text_block(img, q["explanation"], (110, 1360, 970, 1560), font, 60, color=g.YELLOW)

        quiz_rounds.append(rounds.Round(
            question_speech=q["question"],
            answer_speech=f"{options[correct]}! {q['explanation']}",
            draw_question=draw_question,
            draw_reveal=draw_reveal,
        ))

    video = rounds.build(data["hook"], draw_intro, quiz_rounds, data["outro"], draw_outro, bg, seconds, cfg, workdir)
    return Short(data["topic"], data["title"], data["hook"], data["description"], data["tags"], video,
                 cfg["formats"][NAME]["hashtags"])

"""Thema und Skript für das nächste Short mit Claude erzeugen."""

import json

import anthropic
from pydantic import BaseModel

MODEL = "claude-opus-5-5"


class Scene(BaseModel):
    narration: str
    search_query: str


class Script(BaseModel):
    topic: str
    title: str
    hook: str
    scenes: list[Scene]
    description: str
    tags: list[str]


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

SYSTEM = """Du schreibst Skripte für YouTube Shorts, die Menschen bis zum Ende ansehen und teilen.

Was ein Short erfolgreich macht:
- Der erste Satz entscheidet. Er öffnet eine Neugierlücke oder widerspricht einer Erwartung, \
in höchstens 12 Wörtern, ohne Begrüßung oder Vorrede.
- Jeder folgende Satz liefert etwas Neues oder steigert die Spannung; nichts wiederholt sich.
- Die Auflösung kommt spät, aber sie kommt – der Titel darf nichts versprechen, was das Video nicht hält.
- Der letzte Satz leitet natürlich zurück zum Anfang, damit das Video beim Loopen nahtlos wirkt.
- Kurze, gesprochene Sätze. Zahlen so schreiben, wie man sie spricht.

Die Fakten müssen stimmen. Verwende nur gut belegte, allgemein anerkannte Erkenntnisse; \
wenn etwas umstritten ist, wähle ein anderes Thema. Ein falscher Fakt kostet den Kanal mehr \
als ein langweiliger.

Die search_query jeder Szene beschreibt ein Bild, das es als Stock-Video wirklich gibt \
(z. B. "brain scan", "ocean waves aerial", "person sleeping bed") – keine abstrakten Begriffe."""


def _feedback_block(history: list[dict], n: int) -> str:
    with_views = [h for h in history if isinstance(h.get("views"), int)]
    if len(with_views) < 4:
        return ""
    ranked = sorted(with_views, key=lambda h: h["views"], reverse=True)
    fmt = lambda h: f'- {h["views"]} Aufrufe: "{h["title"]}" – Hook: "{h["hook"]}"'
    best = "\n".join(fmt(h) for h in ranked[:n])
    worst = "\n".join(fmt(h) for h in ranked[-n:])
    return (
        "\n\nSo liefen die bisherigen Videos dieses Kanals. Leite daraus ab, welche Themen und "
        f"Hooks bei diesem Publikum funktionieren, und nutze das.\n\nAm besten:\n{best}\n\nAm schlechtesten:\n{worst}"
    )


def generate_script(cfg: dict, history: list[dict]) -> Script:
    channel, script_cfg = cfg["channel"], cfg["script"]
    past_topics = [h["topic"] for h in history[-200:]]
    seconds = script_cfg["target_seconds"]

    prompt = (
        f"Nische des Kanals: {channel['niche']}\n"
        f"Zielgruppe: {channel['audience']}\n"
        f"Sprache: {channel['language']}\n"
        f"Ziel-Länge: etwa {seconds} Sekunden gesprochen (ca. {int(seconds * 2.6)} Wörter).\n\n"
        "Diese Themen gab es schon – wähle etwas klar anderes:\n"
        + ("\n".join(f"- {t}" for t in past_topics) or "- (noch keine)")
        + _feedback_block(history, script_cfg["feedback_videos"])
        + "\n\nSchreib das Skript für das nächste Short."
    )

    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        thinking={"type": "adaptive"},
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude hat die Anfrage abgelehnt: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("Antwort wurde abgeschnitten (max_tokens erreicht).")

    text = next(b.text for b in response.content if b.type == "text")
    script = Script.model_validate(json.loads(text))
    if not script.scenes:
        raise RuntimeError("Claude hat ein Skript ohne Szenen geliefert.")
    return script

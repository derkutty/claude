"""Gemeinsamer Aufruf der Claude-API mit garantiert gültigem JSON als Antwort."""

import json

import anthropic

MODEL = "claude-opus-5-5"

FACT_RULE = (
    "Alles muss stimmen. Verwende nur gut belegte, allgemein anerkannte Fakten und eindeutige Antworten; "
    "wenn etwas umstritten ist oder es mehrere richtige Antworten geben könnte, nimm etwas anderes. "
    "Ein falscher Inhalt kostet den Kanal mehr als ein langweiliger."
)


def ask_json(system: str, prompt: str, schema: dict) -> dict:
    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        thinking={"type": "adaptive"},
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": schema}},
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude hat die Anfrage abgelehnt: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("Antwort wurde abgeschnitten (max_tokens erreicht).")
    return json.loads(next(b.text for b in response.content if b.type == "text"))


def research(system: str, prompt: str, max_searches: int = 8) -> str:
    """Claude recherchiert mit der Websuche und antwortet mit Fließtext (inkl. Quellen-URLs)."""
    client = anthropic.Anthropic()
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": max_searches}]
    messages = [{"role": "user", "content": prompt}]
    for _ in range(5):
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            system=system,
            tools=tools,
            messages=messages,
        )
        if response.stop_reason == "refusal":
            raise RuntimeError(f"Claude hat die Recherche abgelehnt: {response.stop_details}")
        if response.stop_reason != "pause_turn":
            return "\n".join(b.text for b in response.content if b.type == "text")
        # Lange Suchen pausieren serverseitig; mit derselben Unterhaltung geht es weiter.
        messages = [messages[0], {"role": "assistant", "content": response.content}]
    raise RuntimeError("Recherche wurde nicht fertig.")


def channel_context(cfg: dict, history: list[dict], n_feedback: int = 5) -> str:
    """Kanal-Infos, bisherige Themen und Aufrufzahlen dieses Formats für den Prompt."""
    channel = cfg["channel"]
    past = [h["topic"] for h in history[-200:]]
    text = (
        f"Sprache: {channel['language']}\n"
        f"Zielgruppe: {channel['audience']}\n\n"
        "Diese Themen gab es in diesem Format schon – wähle etwas klar anderes:\n"
        + ("\n".join(f"- {t}" for t in past) or "- (noch keine)")
    )
    rated = [h for h in history if isinstance(h.get("views_3d", h.get("views")), int)]
    if len(rated) >= 4:
        views = lambda h: h.get("views_3d", h.get("views"))
        ranked = sorted(rated, key=views, reverse=True)
        fmt = lambda h: f'- {views(h)} Aufrufe: "{h["title"]}" – Hook: "{h["hook"]}"'
        text += (
            "\n\nSo liefen die bisherigen Videos in diesem Format. Leite daraus ab, welche Themen und Hooks "
            "bei diesem Publikum funktionieren, und nutze das.\n\nAm besten:\n"
            + "\n".join(fmt(h) for h in ranked[:n_feedback])
            + "\n\nAm schlechtesten:\n"
            + "\n".join(fmt(h) for h in ranked[-n_feedback:])
        )
    return text

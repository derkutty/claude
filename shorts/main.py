"""Ein komplettes Short erzeugen und hochladen.

    python -m shorts.main                  # Format automatisch wählen, erzeugen, veröffentlichen
    python -m shorts.main --no-upload      # nur erzeugen (Video liegt danach in build/)
    python -m shorts.main --format quiz    # ein bestimmtes Format erzwingen

Mit [upload] mode = "manual" lädt das Programm nicht selbst hoch, sondern legt Video, Titel und
Beschreibung in build/release/ ab; der Workflow macht daraus eine GitHub-Release zum Herunterladen.
"""

import argparse
import os
import shutil
from datetime import datetime, timedelta, timezone

from . import experiment, state, youtube
from .config import BUILD_DIR, load_config, require_env
from .formats import registry


def main() -> None:
    formats = registry()
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-upload", action="store_true", help="Video nur erzeugen, nicht hochladen.")
    parser.add_argument("--format", choices=sorted(formats), help="Bestimmtes Format statt automatischer Wahl.")
    args = parser.parse_args()

    cfg = load_config()
    history = state.load_history()
    require_env("ANTHROPIC_API_KEY")
    now = datetime.now(timezone.utc)

    # GitHub startet geplante Läufe manchmal Stunden zu spät. Ist inzwischen schon ein Video
    # entstanden (z. B. weil der Lauf von Hand nachgeholt wurde), nicht noch eins erzeugen.
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and history:
        last = datetime.fromisoformat(history[-1]["date"])
        if now - last < timedelta(hours=4):
            print(f"Übersprungen: Letztes Video ist erst {now - last} alt (verspäteter geplanter Lauf).")
            return

    yt = None
    if not args.no_upload:
        yt = youtube.client()
        try:
            youtube.link_manual_uploads(yt, history)
            youtube.refresh_stats(yt, history)
        except Exception as e:  # Statistiken sind nur Feedback – kein Grund, den Lauf abzubrechen.
            print(f"Warnung: Statistiken konnten nicht geladen werden: {e}")
        experiment.snapshot_ratings(history, now)

    name = args.format or experiment.choose_format(cfg, history)
    fmt = formats[name]
    print(f"Format: {fmt.LABEL}")

    workdir = BUILD_DIR / now.strftime("%Y%m%d-%H%M%S")
    workdir.mkdir(parents=True, exist_ok=True)
    short = fmt.create(cfg, [h for h in history if h.get("format") == name], workdir)
    print(f"Thema: {short.topic}\nTitel: {short.title}\nVideo: {short.video}")

    if yt is None:
        print("Upload übersprungen (--no-upload).")
        return

    hashtags = " ".join([*cfg["channel"]["hashtags"], *short.hashtags])
    description = f"{short.description}\n\n{hashtags}"
    if cfg["upload"]["mode"] == "manual":
        video_id = None
        write_release(short, description, now)
        print("Zum Hochladen bereitgelegt (GitHub-Release).")
    else:
        video_id = youtube.upload(yt, short.video, short.title, description, short.tags, cfg["upload"])
        print(f"Hochgeladen: https://youtube.com/shorts/{video_id}")
    history.append({
        "date": now.isoformat(timespec="seconds"),
        "format": name,
        "topic": short.topic,
        "title": short.title,
        "hook": short.hook,
        "video_id": video_id,
    })
    state.save_history(history)
    experiment.write_report(cfg, history, {k: m.LABEL for k, m in formats.items()})


def write_release(short, description: str, now: datetime) -> None:
    """Video plus Texte zum Kopieren ablegen; der Workflow erstellt daraus eine GitHub-Release."""
    out = BUILD_DIR / "release"
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy(short.video, out / "short.mp4")
    (out / "tag.txt").write_text(f"short-{now:%Y%m%d-%H%M}", encoding="utf-8")
    (out / "title.txt").write_text(short.title, encoding="utf-8")
    fence = "```"
    (out / "notes.md").write_text(
        "So lädst du dieses Short hoch:\n\n"
        "1. Unten bei **Assets** auf **short.mp4** tippen und speichern.\n"
        "2. YouTube-App: **+** → **Short** → Video auswählen.\n"
        "3. **Titel** von unten einfügen und **genau so lassen** – daran erkennt der Bot das Video wieder.\n"
        "4. **Zielgruppe auswählen** → **Nein, nicht speziell für Kinder** → **Short hochladen**.\n"
        "5. Danach in der App **YouTube Studio**: Inhalte → das Short → Bearbeiten (Stift) → "
        "**Beschreibung** von unten einfügen → Speichern.\n\n"
        f"**Titel**\n{fence}\n{short.title}\n{fence}\n\n"
        f"**Beschreibung**\n{fence}\n{description}\n{fence}\n\n"
        f"**Tags** (optional, bei Shorts kaum wichtig)\n{fence}\n{', '.join(short.tags)}\n{fence}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

"""Ein komplettes Short erzeugen und hochladen.

    python -m shorts.main                  # Format automatisch wählen, erzeugen, hochladen
    python -m shorts.main --no-upload      # nur erzeugen (Video liegt danach in build/)
    python -m shorts.main --format quiz    # ein bestimmtes Format erzwingen
"""

import argparse
from datetime import datetime, timezone

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

    yt = None
    if not args.no_upload:
        yt = youtube.client()
        try:
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
    video_id = youtube.upload(yt, short.video, short.title, f"{short.description}\n\n{hashtags}", short.tags, cfg["upload"])
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


if __name__ == "__main__":
    main()

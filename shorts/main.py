"""Ein komplettes Short erzeugen und hochladen.

    python -m shorts.main              # erzeugen + hochladen
    python -m shorts.main --no-upload  # nur erzeugen (Video liegt danach in build/)
"""

import argparse
import json
from datetime import datetime, timezone

from . import footage, ideas, render, state, voice, youtube
from .config import BUILD_DIR, FONTS_DIR, MUSIC_DIR, load_config, require_env


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-upload", action="store_true", help="Video nur erzeugen, nicht hochladen.")
    args = parser.parse_args()

    cfg = load_config()
    history = state.load_history()
    pexels_key = require_env("PEXELS_API_KEY")
    require_env("ANTHROPIC_API_KEY")

    yt = None
    if not args.no_upload:
        yt = youtube.client()
        try:
            youtube.refresh_stats(yt, history)
        except Exception as e:  # Statistiken sind nur Feedback – kein Grund, den Lauf abzubrechen.
            print(f"Warnung: Statistiken konnten nicht geladen werden: {e}")

    print("1/5 Skript schreiben …")
    script = ideas.generate_script(cfg, history)
    print(f"    Thema: {script.topic}\n    Titel: {script.title}")

    now = datetime.now(timezone.utc)
    workdir = BUILD_DIR / now.strftime("%Y%m%d-%H%M%S")
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "script.json").write_text(script.model_dump_json(indent=2), encoding="utf-8")

    print("2/5 Stimme erzeugen …")
    audio = voice.synthesize_scenes(
        [s.narration for s in script.scenes], cfg["voice"]["name"], cfg["voice"]["rate"], workdir
    )

    print("3/5 Stock-Videos laden und schneiden …")
    used_ids: set[int] = set()
    scene_videos = []
    for i, (scene, a) in enumerate(zip(script.scenes, audio)):
        raw = footage.fetch_clip(scene.search_query, a.duration, pexels_key, used_ids, workdir / f"raw_{i:02d}.mp4")
        scene_videos.append(render.render_scene(raw, a.duration, cfg["video"], workdir / f"scene_{i:02d}.mp4"))

    print("4/5 Zusammensetzen …")
    words, offset = [], 0.0
    for a in audio:
        words += [voice.Word(w.text, w.start + offset, w.end + offset) for w in a.words]
        offset += a.duration
    voice_track = render.concat_voice([a.path for a in audio], [a.duration for a in audio], workdir / "voice.wav")
    captions = render.write_captions(words, cfg["video"], workdir / "captions.ass")
    final = render.assemble(scene_videos, voice_track, captions, MUSIC_DIR, FONTS_DIR, cfg["video"], workdir / "short.mp4")
    print(f"    Fertig: {final} ({render.probe_duration(final):.1f} s)")

    entry = {
        "date": now.isoformat(timespec="seconds"),
        "topic": script.topic,
        "title": script.title,
        "hook": script.hook,
        "video_id": None,
    }
    if yt is None:
        print("5/5 Upload übersprungen (--no-upload).")
        return

    print("5/5 Hochladen …")
    description = f"{script.description}\n\n{' '.join(cfg['channel']['hashtags'])}"
    entry["video_id"] = youtube.upload(yt, final, script.title, description, script.tags, cfg["upload"])
    print(f"    https://youtube.com/shorts/{entry['video_id']}")
    history.append(entry)
    state.save_history(history)


if __name__ == "__main__":
    main()

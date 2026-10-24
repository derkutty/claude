"""Clips, Stimme, Musik und Untertitel mit ffmpeg zu einem fertigen 9:16-Short zusammensetzen."""

import json
import random
import re
import subprocess
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None) -> None:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg fehlgeschlagen:\n{' '.join(cmd)}\n{result.stderr[-3000:]}")


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])


def render_scene(src: Path, duration: float, video_cfg: dict, out: Path) -> Path:
    """Clip auf 9:16 zuschneiden und auf die exakte Szenenlänge bringen (bei Bedarf geloopt)."""
    w, h, fps = video_cfg["width"], video_cfg["height"], video_cfg["fps"]
    run([
        "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src), "-t", f"{duration:.3f}",
        "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},setsar=1",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(out),
    ])
    return out


def concat_voice(paths: list[Path], durations: list[float], out: Path) -> Path:
    """Szenen-Audios hintereinanderhängen, jede exakt auf ihre Szenenlänge gepolstert."""
    inputs, chains = [], []
    for i, (p, d) in enumerate(zip(paths, durations)):
        inputs += ["-i", str(p)]
        chains.append(f"[{i}:a]aresample=48000,apad,atrim=0:{d:.3f},asetpts=PTS-STARTPTS[a{i}]")
    graph = ";".join(chains) + ";" + "".join(f"[a{i}]" for i in range(len(paths))) + f"concat=n={len(paths)}:v=0:a=1[out]"
    run(["ffmpeg", "-y", *inputs, "-filter_complex", graph, "-map", "[out]", "-c:a", "pcm_s16le", str(out)])
    return out


def _ts(seconds: float) -> str:
    cs = max(0, round(seconds * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _clean(text: str) -> str:
    return re.sub(r"[{}\\]", "", text).upper()


def write_captions(words: list, video_cfg: dict, out: Path) -> Path:
    """Große, mittige Wort-für-Wort-Untertitel mit kleinem Pop-Effekt (ASS-Format).

    `words` sind Word-Objekte mit Zeiten relativ zum Video-Anfang."""
    w, h = video_cfg["width"], video_cfg["height"]
    n = max(1, video_cfg["words_per_caption"])
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{video_cfg["font"]},{video_cfg["font_size"]},&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,7,4,5,80,80,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    chunks = [words[i:i + n] for i in range(0, len(words), n)]
    lines = []
    for i, chunk in enumerate(chunks):
        start = chunk[0].start
        end = chunk[-1].end + 0.4
        if i + 1 < len(chunks):
            end = min(end, chunks[i + 1][0].start)
        text = " ".join(_clean(wd.text) for wd in chunk)
        # Zahlen gelb hervorheben – die bleiben am ehesten hängen.
        text = re.sub(r"(\S*\d\S*)", r"{\\c&H00D7FF&}\1{\\c&HFFFFFF&}", text)
        pop = r"{\fscx85\fscy85\t(0,90,\fscx100\fscy100)}"
        lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Default,,0,0,0,,{pop}{text}")
    out.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    return out


def pick_music(music_dir: Path) -> Path | None:
    if not music_dir.exists():
        return None
    music = sorted(p for p in music_dir.glob("*") if p.suffix.lower() in {".mp3", ".m4a", ".wav", ".ogg"})
    return random.choice(music) if music else None


def make_sfx(workdir: Path) -> dict[str, Path]:
    """Ticken für den Countdown und ein 'Ding' für die Auflösung, direkt mit ffmpeg erzeugt."""
    sounds = {
        "tick": "sine=frequency=1100:duration=0.06,afade=t=out:st=0.02:d=0.04,volume=0.5",
        "ding": "sine=frequency=1320:duration=0.5,afade=t=out:st=0.05:d=0.45,volume=0.6",
        "whoosh": "anoisesrc=d=0.35:c=pink:a=0.25,highpass=f=800,afade=t=in:d=0.1,afade=t=out:st=0.1:d=0.25",
    }
    out = {}
    for name, graph in sounds.items():
        path = workdir / f"sfx_{name}.wav"
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", graph, "-ar", "48000", "-ac", "2", str(path)])
        out[name] = path
    return out


def segment(image: Path, duration: float, sounds: list[tuple[Path, float]], video_cfg: dict, out: Path) -> Path:
    """Ein Standbild mit Ton (Liste aus (Datei, Startzeit)) als exakt `duration` Sekunden langes Stück."""
    fps = video_cfg["fps"]
    cmd = ["ffmpeg", "-y", "-loop", "1", "-framerate", str(fps), "-t", f"{duration:.3f}", "-i", str(image),
           "-f", "lavfi", "-t", f"{duration:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
    chains, labels = [], ["[1:a]"]
    for i, (path, delay) in enumerate(sounds):
        cmd += ["-i", str(path)]
        ms = int(delay * 1000)
        chains.append(f"[{i + 2}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[s{i}]")
        labels.append(f"[s{i}]")
    graph = ";".join(chains + [f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:normalize=0[a]"])
    cmd += ["-filter_complex", graph, "-map", "0:v", "-map", "[a]",
            "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-tune", "stillimage",
            "-r", str(fps), "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(out)]
    run(cmd)
    return out


def concat_segments(segments: list[Path], music_dir: Path, video_cfg: dict, out: Path) -> Path:
    """Fertige Stücke aneinanderhängen und leise Hintergrundmusik darunterlegen."""
    concat_list = out.parent / "segments.txt"
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in segments), encoding="utf-8")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list)]
    music = pick_music(music_dir)
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music), "-filter_complex",
                f"[1:a]volume={video_cfg['music_volume']}[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
                "-map", "0:v", "-map", "[a]"]
    cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out)]
    run(cmd)
    return out


def assemble(scene_videos: list[Path], voice: Path, captions: Path, music_dir: Path, fonts_dir: Path,
             video_cfg: dict, out: Path) -> Path:
    workdir = out.parent
    concat_list = workdir / "scenes.txt"
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in scene_videos), encoding="utf-8")

    music = pick_music(music_dir)
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-i", str(voice)]
    vf = f"[0:v]subtitles={captions.name}:fontsdir={fonts_dir.resolve()}[v]"
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        af = f"[2:a]volume={video_cfg['music_volume']}[m];[1:a][m]amix=inputs=2:duration=first:normalize=0[a]"
    else:
        af = "[1:a]anull[a]"
    cmd += [
        "-filter_complex", f"{vf};{af}", "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(video_cfg["fps"]),
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", str(out.resolve()),
    ]
    run(cmd, cwd=workdir)
    return out

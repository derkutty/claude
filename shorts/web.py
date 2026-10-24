"""HTML-Szenen mit Chromium Bild für Bild aufnehmen.

Die Seite muss eine Funktion `window.show(state, t, T)` haben: `state` beschreibt die Szene,
`t` sind die Sekunden seit Szenenbeginn, `T` die Sekunden seit Videobeginn (für durchlaufende
Hintergrund-Animationen). So ist jedes Bild exakt reproduzierbar, egal wie schnell der Rechner ist.
"""

import base64
import json
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import sync_playwright


@contextmanager
def page(html: str, video_cfg: dict):
    with sync_playwright() as p:
        # CHROMIUM_PATH nur nötig, wenn Chromium nicht über `playwright install` installiert wurde.
        browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
        pg = browser.new_page(viewport={"width": video_cfg["width"], "height": video_cfg["height"]})
        pg.set_content(html, wait_until="load")
        pg.evaluate("document.fonts.ready")
        try:
            yield pg
        finally:
            browser.close()


def record(pg, state: dict, duration: float, start: float, video_cfg: dict, out: Path) -> Path:
    """Eine Szene als stummes Video aufnehmen."""
    fps = video_cfg["fps"]
    frames = max(1, round(duration * fps))
    ffmpeg = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", str(out)],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    state_js = json.dumps(state)
    # Direkt über das DevTools-Protokoll ist die Aufnahme etwas schneller als mit page.screenshot().
    cdp = pg.context.new_cdp_session(pg)
    for i in range(frames):
        t = i / fps
        pg.evaluate(f"show({state_js}, {t:.4f}, {start + t:.4f})")
        shot = cdp.send("Page.captureScreenshot", {"format": "jpeg", "quality": 92})
        ffmpeg.stdin.write(base64.b64decode(shot["data"]))
    cdp.detach()
    _, err = ffmpeg.communicate()
    if ffmpeg.returncode != 0:
        raise RuntimeError(f"ffmpeg fehlgeschlagen beim Aufnehmen:\n{err.decode()[-2000:]}")
    return out

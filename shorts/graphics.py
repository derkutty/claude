"""Bilder für die Rätsel-Formate mit Pillow zeichnen: Verlauf, Text, Emojis, Countdown."""

import random
import subprocess
from contextlib import contextmanager
from functools import cache

from PIL import Image, ImageDraw, ImageFont, features

from .config import FONTS_DIR

# Mitgelieferte Kopie bevorzugen (siehe assets/vendor-fonts/README.md), sonst die Systemschrift.
_VENDOR_EMOJI = FONTS_DIR.parent / "vendor-fonts" / "NotoColorEmoji.ttf"
EMOJI_FONT = str(_VENDOR_EMOJI) if _VENDOR_EMOJI.exists() else "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
EMOJI_NATIVE_SIZE = 109  # Noto Color Emoji gibt es nur in dieser Größe; danach wird skaliert.

# Farbverläufe (oben, unten). Pro Video wird einer zufällig gewählt.
PALETTES = [
    ((88, 28, 135), (15, 23, 42)),
    ((14, 116, 144), (8, 47, 73)),
    ((190, 18, 60), (76, 5, 25)),
    ((21, 128, 61), (5, 46, 22)),
    ((194, 65, 12), (67, 20, 7)),
    ((30, 64, 175), (23, 37, 84)),
]
WHITE = (255, 255, 255)
GREEN = (34, 197, 94)
YELLOW = (250, 204, 21)


@cache
def font_path(name: str) -> str:
    """Eigene Schrift aus assets/fonts/ bevorzugen, sonst die Systemschrift über fontconfig."""
    own = sorted(p for p in FONTS_DIR.glob("*") if p.suffix.lower() in {".ttf", ".otf"})
    if own:
        return str(own[0])
    return subprocess.run(["fc-match", "-f", "%{file}", f"{name}:bold"], capture_output=True, text=True, check=True).stdout


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_path(name), size)


def pick_palette() -> tuple:
    return random.choice(PALETTES)


def background(w: int, h: int, palette: tuple) -> Image.Image:
    top, bottom = palette
    grad = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / (h - 1)
        grad.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    return grad.resize((w, h)).convert("RGBA")


@contextmanager
def _layer(img: Image.Image):
    """Auf einer durchsichtigen Ebene zeichnen und sie danach überblenden.

    Direkt auf `img` würden halbdurchsichtige Farben die Pixel ersetzen statt sie zu mischen."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    yield ImageDraw.Draw(layer)
    img.alpha_composite(layer)


def _wrap(draw: ImageDraw.ImageDraw, text: str, fnt, max_width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if draw.textlength(candidate, font=fnt) <= max_width or not line:
            line = candidate
        else:
            lines.append(line)
            line = word
    return lines + ([line] if line else [])


def text_block(img: Image.Image, text: str, box: tuple[int, int, int, int], font_name: str,
               max_size: int, color=WHITE, min_size: int = 36) -> None:
    """Text zentriert in die Box schreiben und so weit verkleinern, bis er passt."""
    measure = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    for size in range(max_size, min_size - 1, -4):
        fnt = font(font_name, size)
        lines = _wrap(measure, text, fnt, x1 - x0)
        line_h = int(size * 1.2)
        if line_h * len(lines) <= y1 - y0 and all(measure.textlength(l, font=fnt) <= x1 - x0 for l in lines):
            break
    y = y0 + ((y1 - y0) - line_h * len(lines)) // 2
    with _layer(img) as draw:
        for l in lines:
            w = draw.textlength(l, font=fnt)
            draw.text((x0 + ((x1 - x0) - w) / 2, y), l, font=fnt, fill=color,
                      stroke_width=max(2, size // 18), stroke_fill=(0, 0, 0))
            y += line_h


def box(img: Image.Image, rect: tuple[int, int, int, int], fill: tuple) -> None:
    with _layer(img) as draw:
        draw.rounded_rectangle(rect, radius=36, fill=fill)


def pill(img: Image.Image, text: str, center_y: int, font_name: str, size: int,
         fill=(255, 255, 255, 40), color=WHITE) -> None:
    fnt = font(font_name, size)
    with _layer(img) as draw:
        w = draw.textlength(text, font=fnt)
        pad_x, pad_y = size * 0.8, size * 0.45
        cx = img.width / 2
        draw.rounded_rectangle((cx - w / 2 - pad_x, center_y - size / 2 - pad_y, cx + w / 2 + pad_x, center_y + size / 2 + pad_y),
                               radius=int(size), fill=fill)
        draw.text((cx, center_y), text, font=fnt, fill=color, anchor="mm")


def option_row(img: Image.Image, label: str, text: str, box: tuple[int, int, int, int], font_name: str,
               state: str = "neutral") -> None:
    """Eine Antwortmöglichkeit. state: neutral, correct oder dimmed."""
    fill = {"neutral": (255, 255, 255, 38), "correct": (*GREEN, 255), "dimmed": (0, 0, 0, 60)}[state]
    x0, y0, x1, y1 = box
    badge = 92
    bx, by = x0 + 30, (y0 + y1 - badge) // 2
    with _layer(img) as draw:
        draw.rounded_rectangle(box, radius=36, fill=fill)
        draw.ellipse((bx, by, bx + badge, by + badge), fill=(255, 255, 255, 230 if state != "dimmed" else 90))
        draw.text((bx + badge / 2, by + badge / 2), label, font=font(font_name, 54), fill=(15, 23, 42), anchor="mm")
    color = WHITE if state != "dimmed" else (255, 255, 255, 110)
    text_block(img, text, (bx + badge + 30, y0 + 14, x1 - 30, y1 - 14), font_name, 58, color=color, min_size=32)


def countdown(img: Image.Image, number: int, total: int, center: tuple[int, int], font_name: str) -> None:
    cx, cy = center
    r = 105
    with _layer(img) as draw:
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(0, 0, 0, 90))
        # Ring zeigt die verbleibende Zeit.
        draw.arc((cx - r, cy - r, cx + r, cy + r), start=-90, end=-90 + 360 * number / total, fill=YELLOW, width=16)
        draw.text((cx, cy), str(number), font=font(font_name, 110), fill=WHITE, anchor="mm")


@cache
def _emoji_glyph(emoji: str) -> Image.Image:
    # Raqm setzt zusammengesetzte Emojis (z. B. 🧑‍🚀) korrekt zusammen; ohne Raqm geht es auch, nur schlichter.
    layout = ImageFont.Layout.RAQM if features.check("raqm") else ImageFont.Layout.BASIC
    fnt = ImageFont.truetype(EMOJI_FONT, EMOJI_NATIVE_SIZE, layout_engine=layout)
    left, top, right, bottom = fnt.getbbox(emoji)
    glyph = Image.new("RGBA", (right - left, bottom - top), (0, 0, 0, 0))
    ImageDraw.Draw(glyph).text((-left, -top), emoji, font=fnt, embedded_color=True)
    return glyph


def emoji_row(img: Image.Image, emojis: list[str], center_y: int, max_height: int = 210) -> None:
    """Emojis groß und zentriert in eine Reihe setzen; bei vielen Emojis werden sie kleiner."""
    if not emojis:
        return
    gap = 30
    max_width = img.width - 160
    height = min(max_height, int((max_width - gap * (len(emojis) - 1)) / len(emojis)))
    glyphs = [_emoji_glyph(e) for e in emojis]
    glyphs = [g.resize((round(g.width * height / g.height), height), Image.LANCZOS) for g in glyphs]
    total = sum(g.width for g in glyphs) + gap * (len(glyphs) - 1)
    x = (img.width - total) // 2
    for g in glyphs:
        img.alpha_composite(g, (x, center_y - height // 2))
        x += g.width + gap

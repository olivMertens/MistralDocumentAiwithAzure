"""Generate sample images (printed + handwriting) for the model comparison demo.

Usage:
    uv run python scripts/generate_sample_images.py

Creates two PNGs in ``data/`` that share the *same* text so you can clearly see the
accuracy gap between Mistral Document AI v25.05 and v25.12 in the "Compare Models" view:

- ``data/sample_printed_note.png``      — clean printed text (easy baseline)
- ``data/sample_handwritten_note.png``  — the same note rendered in a handwriting
  font with per-line slant + jitter on faint ruled paper (the hard case)

The note deliberately mixes dates, currency, an invoice number and a phone number —
all common OCR stumbling blocks.
"""

from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Shared note content (same text in both images).
LINES: list[str] = [
    "Meeting Notes - 24 June 2026",
    "",
    "Action items:",
    "  - Ship the OCR demo to staging by Friday",
    "  - Compare v25.05 vs v25.12 on handwriting",
    "  - Budget approved: $12,450.00",
    "",
    "Reminder: invoice #A-1093 is due 30/06.",
    "Call Dr. Smith re: results - (555) 017-2243.",
    "",
    "Thanks!  - Olivier",
]

# Candidate handwriting fonts (Windows first, then common cross-platform options).
HANDWRITING_FONTS = [
    r"C:\Windows\Fonts\Inkfree.ttf",      # Ink Free (Windows 10/11 handwriting font)
    r"C:\Windows\Fonts\segoesc.ttf",      # Segoe Script
    r"C:\Windows\Fonts\comic.ttf",        # Comic Sans MS
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
    "/Library/Fonts/Comic Sans MS.ttf",
]
PRINTED_FONTS = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
]

INK = (26, 26, 58)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    """Return the first available TrueType font, else PIL's default bitmap font."""
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _new_canvas(width: int, height: int, ruled: bool) -> Image.Image:
    """Create a paper-like canvas, optionally with faint ruled lines."""
    bg = (253, 253, 247) if ruled else (255, 255, 255)
    img = Image.new("RGB", (width, height), bg)
    if ruled:
        draw = ImageDraw.Draw(img)
        for y in range(80, height, 56):
            draw.line([(40, y), (width - 40, y)], fill=(223, 223, 233), width=1)
        draw.line([(70, 40), (70, height - 40)], fill=(233, 205, 205), width=2)
    return img


def render_printed(path: Path) -> None:
    font = _load_font(PRINTED_FONTS, 30)
    img = _new_canvas(1000, 700, ruled=False)
    draw = ImageDraw.Draw(img)
    y = 60
    for line in LINES:
        draw.text((80, y), line, font=font, fill=INK)
        y += 56
    img.save(path)
    print(f"  wrote {path.name}")


def render_handwritten(path: Path) -> None:
    rng = random.Random(7)
    font = _load_font(HANDWRITING_FONTS, 36)
    width, height = 1000, 760
    img = _new_canvas(width, height, ruled=True)
    y = 64
    for line in LINES:
        if line.strip():
            # Render each line on its own layer so it can be slanted independently.
            layer = Image.new("RGBA", (width, 80), (0, 0, 0, 0))
            ldraw = ImageDraw.Draw(layer)
            jitter = rng.randint(-3, 3)
            ldraw.text((80 + jitter, 8), line, font=font, fill=INK + (255,))
            layer = layer.rotate(rng.uniform(-2.2, 2.2), expand=False, resample=Image.BICUBIC)
            img.paste(layer, (0, y - 8), layer)
        y += 60
    img.save(path)
    print(f"  wrote {path.name}")


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    print(f"Generating sample images in {DATA_DIR} ...")
    render_printed(DATA_DIR / "sample_printed_note.png")
    render_handwritten(DATA_DIR / "sample_handwritten_note.png")
    print("Done. Open the 'Compare Models' page and pick one of these samples.")


if __name__ == "__main__":
    main()

"""Generate sample images for the OCR model-comparison demo.

Usage:
    uv run python scripts/generate_sample_images.py

Produces a curated set of PNGs in ``data/`` ranging from easy to very hard so the
"Compare Models" page can showcase how Mistral Document AI v25.12 improves on v25.05 —
especially for **handwriting** and **multilingual** text:

- ``sample_printed_note.png``        printed English note ...................... easy
- ``sample_handwritten_en.png``      English handwriting ...................... medium
- ``sample_handwritten_fr.png``      French handwriting (accents) ............. hard
- ``sample_handwritten_es.png``      Spanish handwriting (ñ, ¿¡) .............. hard
- ``sample_handwritten_de.png``      German handwriting (ä ö ü ß) ............. hard
- ``sample_handwritten_it.png``      Italian handwriting ...................... hard
- ``sample_printed_zh.png``          Chinese (printed) ........................ medium
- ``sample_printed_ja.png``          Japanese (printed) ....................... medium
- ``sample_printed_ko.png``          Korean (printed) ......................... medium
- ``sample_handwritten_hard.png``    messy / rotated handwriting .............. very hard

Each sample carries dates, currency and reference numbers — common OCR stumbling
blocks. Samples whose font is unavailable on this machine are skipped gracefully.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INK = (26, 26, 58)

# Font candidate lists (first existing one wins). Windows paths first.
HANDWRITING = [
    r"C:\Windows\Fonts\Inkfree.ttf",       # Ink Free
    r"C:\Windows\Fonts\segoesc.ttf",       # Segoe Script
    r"C:\Windows\Fonts\comic.ttf",         # Comic Sans MS
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
]
PRINTED = [
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
CJK_ZH = [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simsun.ttc"]
CJK_JA = [r"C:\Windows\Fonts\msgothic.ttc", r"C:\Windows\Fonts\YuGothM.ttc"]
CJK_KO = [r"C:\Windows\Fonts\malgun.ttf", r"C:\Windows\Fonts\gulim.ttc"]


@dataclass
class Sample:
    filename: str
    lines: list[str]
    fonts: list[str]
    style: str = "handwritten"  # handwritten | printed | hard
    size: int = 34


SAMPLES: list[Sample] = [
    Sample(
        "sample_printed_note.png",
        [
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
        ],
        PRINTED,
        style="printed",
        size=30,
    ),
    Sample(
        "sample_handwritten_en.png",
        [
            "Shopping list - Saturday",
            "  - 2 kg of apples ..... $4.50",
            "  - Coffee beans (500 g)",
            "  - Birthday card for Mum",
            "Pay invoice #A-1093 before 30/06.",
            "Meet Sarah at 6:30 pm, table 12.",
        ],
        HANDWRITING,
    ),
    Sample(
        "sample_handwritten_fr.png",
        [
            "Notes de réunion - 24 juin 2026",
            "  - Préparer la présentation",
            "  - Budget approuvé : 12 450,00 €",
            "  - Réserver l'hôtel à Genève",
            "Appeler le Dr Lefèvre à 14 h 30.",
            "N'oublie pas la facture n° A-1093.",
        ],
        HANDWRITING,
    ),
    Sample(
        "sample_handwritten_es.png",
        [
            "Notas de la reunión - 24 junio 2026",
            "  - Enviar el informe al señor Núñez",
            "  - Presupuesto: 12.450,00 €",
            "¿Llamar al médico mañana? ¡Sí!",
            "La reunión es el miércoles a las 9.",
            "Factura n.º A-1093 vence el 30/06.",
        ],
        HANDWRITING,
    ),
    Sample(
        "sample_handwritten_de.png",
        [
            "Besprechungsnotizen - 24. Juni 2026",
            "  - Präsentation für Düsseldorf",
            "  - Budget genehmigt: 12.450,00 €",
            "Größe und Maße noch prüfen.",
            "Über die Straße zur Bäckerei gehen.",
            "Rechnung Nr. A-1093 bis 30.06.",
        ],
        HANDWRITING,
    ),
    Sample(
        "sample_handwritten_it.png",
        [
            "Note della riunione - 24 giugno 2026",
            "  - Però è già molto tardi",
            "  - Budget approvato: 12.450,00 €",
            "Chiamare il dottor Rossi alle 15.",
            "La città è bellissima in autunno.",
            "Fattura n. A-1093 entro il 30/06.",
        ],
        HANDWRITING,
    ),
    Sample(
        "sample_printed_zh.png",
        [
            "会议记录 - 2026年6月24日",
            "  - 准备演示文稿",
            "  - 预算已批准：¥12,450.00",
            "  - 预订日内瓦的酒店",
            "下午2点30分给李医生打电话。",
            "发票编号 A-1093，6月30日到期。",
        ],
        CJK_ZH,
        style="printed",
        size=32,
    ),
    Sample(
        "sample_printed_ja.png",
        [
            "会議メモ - 2026年6月24日",
            "  - プレゼン資料を準備する",
            "  - 予算承認：¥12,450",
            "  - ジュネーブのホテルを予約",
            "午後2時30分に田中先生へ電話。",
            "請求書番号 A-1093、6月30日締切。",
        ],
        CJK_JA,
        style="printed",
        size=32,
    ),
    Sample(
        "sample_printed_ko.png",
        [
            "회의록 - 2026년 6월 24일",
            "  - 발표 자료 준비하기",
            "  - 예산 승인: ₩12,450",
            "  - 제네바 호텔 예약",
            "오후 2시 30분에 김 선생님께 전화.",
            "송장 번호 A-1093, 6월 30일 마감.",
        ],
        CJK_KO,
        style="printed",
        size=32,
    ),
    Sample(
        "sample_handwritten_hard.png",
        [
            "Dr's note - urgent!!",
            "patient: M. Dubois  (DOB 03/11/54)",
            "Rx: amoxicillin 500mg x3/day",
            "review bloods in 2 wks, BP 130/85",
            "ref #A-1093 - call ext. 2243 asap",
            "sign: ~illegible~  $1,240 due",
        ],
        HANDWRITING,
        style="hard",
        size=36,
    ),
]


def _load_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont | None:
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return None


def _canvas(width: int, height: int, ruled: bool) -> Image.Image:
    bg = (253, 253, 247) if ruled else (255, 255, 255)
    img = Image.new("RGB", (width, height), bg)
    if ruled:
        d = ImageDraw.Draw(img)
        for y in range(80, height, 58):
            d.line([(40, y), (width - 40, y)], fill=(223, 223, 233), width=1)
        d.line([(70, 40), (70, height - 40)], fill=(233, 205, 205), width=2)
    return img


def _render(sample: Sample, font: ImageFont.FreeTypeFont) -> Image.Image:
    width = 1040
    line_h = sample.size + 26
    height = 120 + line_h * len(sample.lines)
    ruled = sample.style in {"handwritten", "hard"}
    img = _canvas(width, height, ruled)

    if sample.style == "printed":
        draw = ImageDraw.Draw(img)
        y = 56
        for line in sample.lines:
            draw.text((80, y), line, font=font, fill=INK)
            y += line_h
        return img

    # Handwritten / hard: render each line on its own layer with slant + jitter.
    rng = random.Random(13 if sample.style == "hard" else 7)
    slant = 4.0 if sample.style == "hard" else 2.2
    ink = (60, 60, 90) if sample.style == "hard" else INK  # fainter for "hard"
    y = 56
    for line in sample.lines:
        if line.strip():
            layer = Image.new("RGBA", (width, line_h + 24), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            jx = rng.randint(-4, 6)
            ld.text((80 + jx, 10), line, font=font, fill=ink + (255,))
            layer = layer.rotate(
                rng.uniform(-slant, slant), expand=False, resample=Image.BICUBIC
            )
            img.paste(layer, (0, y - 12), layer)
        y += line_h
    return img


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    print(f"Generating sample images in {DATA_DIR} ...")
    written, skipped = 0, 0
    for sample in SAMPLES:
        font = _load_font(sample.fonts, sample.size)
        if font is None:
            print(f"  skip  {sample.filename} (no suitable font on this machine)")
            skipped += 1
            continue
        img = _render(sample, font)
        img.save(DATA_DIR / sample.filename)
        print(f"  wrote {sample.filename}")
        written += 1
    print(f"Done. {written} written, {skipped} skipped.")
    print("Open the 'Compare Models' page and pick a sample to compare v25.05 vs v25.12.")


if __name__ == "__main__":
    main()

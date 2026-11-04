"""Kartenraenge per Formvergleich mit gezeichneten Schrift-Vorlagen erkennen.

Windows-OCR ist fuer ganze Woerter gebaut; isolierte Einzelzeichen (A, 7, Q auf grossen Karten)
liefert es oft gar nicht (gemessen 26.10.2026 an einer 6er-Tisch-Aufnahme: 3 von 7 Raengen).
Hier werden die 13 Raenge in mehreren Standardschriften gezeichnet, genauso normiert wie die
Glyphen aus dem Bild (cards._normalize_glyph) und per Korrelation verglichen. Das Seitenverhaeltnis
geht mit ein ('10' ist breit, '7' schmal).

Bewusst KEINE Vorlagen aus dem PokerTH-Export: der bleibt unabhaengige Referenz fuer den Vergleich.
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

GLYPH_SIZE = (20, 28)
RANK_TEXT = {"2": "2", "3": "3", "4": "4", "5": "5", "6": "6", "7": "7", "8": "8", "9": "9", "T": "10",
             "J": "J", "Q": "Q", "K": "K", "A": "A"}
FONT_DIR = Path("C:/Windows/Fonts")
FONTS = ["arialbd.ttf", "arial.ttf", "segoeuib.ttf", "segoeui.ttf", "verdanab.ttf", "verdana.ttf",
         "tahomabd.ttf", "tahoma.ttf", "calibrib.ttf", "calibri.ttf", "bahnschrift.ttf", "ARIALN.TTF", "ARIALNB.TTF",
         # schmale und Serifenschriften (PokerTH-Q ist schmal mit langem Schwanz)
         "times.ttf", "timesbd.ttf", "georgia.ttf", "georgiab.ttf", "cambriab.ttf", "constan.ttf", "constanb.ttf",
         "pala.ttf", "palab.ttf", "framd.ttf", "trebuc.ttf", "trebucbd.ttf", "Candara.ttf", "Candarab.ttf",
         "corbel.ttf", "corbelb.ttf", "seguisb.ttf", "micross.ttf",
         "DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "DejaVuSerif.ttf"]
ASPECT_WEIGHT = 0.6


def _norm(g: np.ndarray) -> np.ndarray:
    f = g.astype(np.float32)
    return (f - f.mean()) / (f.std() + 1e-6)


@lru_cache(maxsize=1)
def font_templates() -> list[tuple[str, np.ndarray, float, str]]:
    """(Rang, normierte Glyphe, Seitenverhaeltnis b/h, Schrift) fuer alle verfuegbaren Schriften."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return []
    out = []
    dirs = [FONT_DIR, Path("/usr/share/fonts/truetype/dejavu")]
    for name in FONTS:
        path = next((d / name for d in dirs if (d / name).exists()), None)
        if path is None:
            continue
        font = ImageFont.truetype(str(path), 120)
        for label, text in RANK_TEXT.items():
            img = Image.new("L", (360, 220), 0)
            ImageDraw.Draw(img).text((20, 20), text, fill=255, font=font)
            a = (np.array(img) > 127).astype(np.uint8) * 255
            ys, xs = np.where(a > 0)
            if len(xs) < 5:
                continue
            crop = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            g = cv2.resize(crop, GLYPH_SIZE, interpolation=cv2.INTER_AREA)
            out.append((label, _norm(g), crop.shape[1] / crop.shape[0], name))
    return out


def match_rank(glyph: np.ndarray, aspect: float) -> tuple[str | None, float, float]:
    """(Rang, Score, Abstand zum zweitbesten Rang). glyph: normiert wie cards._normalize_glyph."""
    tmpls = font_templates()
    if not tmpls or glyph is None or aspect <= 0:
        return None, 0.0, 0.0
    g = _norm(glyph)
    best: dict[str, float] = {}
    for label, t, ta, _ in tmpls:
        s = float((g * t).mean()) - ASPECT_WEIGHT * abs(math.log(aspect / ta))
        if s > best.get(label, -9):
            best[label] = s
    ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)
    second = ranked[1][1] if len(ranked) > 1 else -1.0
    return ranked[0][0], ranked[0][1], ranked[0][1] - second

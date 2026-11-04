"""Recognize card ranks by shape comparison with drawn font templates.

Windows OCR is built for whole words; isolated single characters (A, 7, Q on large cards)
often not detected at all (measured 26.10.2026 on a 6-player table recording: 3 of 7 ranks).
Here the 13 ranks are drawn in several standard fonts, normalized identically to the
glyphs from the image (cards._normalize_glyph) and compared by correlation. Aspect ratio
is included ('10' is wide, '7' narrow).

Deliberately NO templates from the PokerTH export: that remains an independent reference for comparison.
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
         # narrow and serif fonts (PokerTH-Q is narrow with long tail)
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
    """(Rank, normalized glyph, aspect ratio w/h, font) for all available fonts."""
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
    """(Rank, score, distance to second-best rank). glyph: normalized as cards._normalize_glyph."""
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

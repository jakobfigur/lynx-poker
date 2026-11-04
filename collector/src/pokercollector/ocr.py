""" OCR layer. Standard: Windows.Media.Ocr (no additional software needed).

All rectangles in results are frame coordinates, not crop coordinates.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from typing import Protocol

import cv2
import numpy as np

from .geometry import Rect

OCR_VERSION = "winocr-1"


@dataclass(frozen=True)
class OcrLine:
    text: str
    rect: Rect


@dataclass
class OcrResult:
    lines: list[OcrLine] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(l.text for l in self.lines)


class OcrBackend(Protocol):
    name: str

    def recognize(self, img: np.ndarray) -> list[tuple[str, tuple[float, float, float, float]]]:
        """ Lines (text, (x, y, w, h)) in image coordinates of the passed image."""


class WindowsOcr:
    name = "windows.media.ocr"

    def __init__(self, language: str | None = None):
        from winrt.windows.globalization import Language
        from winrt.windows.media.ocr import OcrEngine

        if language:
            self._engine = OcrEngine.try_create_from_language(Language(language))
        else:
            self._engine = OcrEngine.try_create_from_user_profile_languages()
        try:
            self._max_dim = int(OcrEngine.max_image_dimension)
        except Exception:                      # older winrt bindings
            self._max_dim = 4000
        if self._engine is None:
            raise RuntimeError('Windows OCR not available (no OCR language installed?)')
        self._loop = asyncio.new_event_loop()

    def recognize(self, img: np.ndarray):
        from winrt.windows.graphics.imaging import BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap
        from winrt.windows.storage.streams import DataWriter

        if img.ndim == 2:
            bgra = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
        else:
            bgra = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
        h, w = bgra.shape[:2]
        if w < 8 or h < 8:
            return []
        # Windows OCR rejects images that are too large (OcrEngine.MaxImageDimension) -> scale down proportionally
        limit = self._max_dim
        if max(w, h) > limit:
            f = limit / max(w, h)
            bgra = cv2.resize(bgra, (max(8, int(w * f)), max(8, int(h * f))), interpolation=cv2.INTER_AREA)
            h, w = bgra.shape[:2]
        writer = DataWriter()
        writer.write_bytes(np.ascontiguousarray(bgra).tobytes())
        bmp = SoftwareBitmap.create_copy_from_buffer(
            writer.detach_buffer(), BitmapPixelFormat.BGRA8, w, h, BitmapAlphaMode.PREMULTIPLIED
        )
        res = self._loop.run_until_complete(self._engine.recognize_async(bmp))
        out = []
        for line in res.lines:
            xs, ys, x2s, y2s = [], [], [], []
            for word in line.words:
                r = word.bounding_rect
                xs.append(r.x)
                ys.append(r.y)
                x2s.append(r.x + r.width)
                y2s.append(r.y + r.height)
            if xs:
                out.append((line.text, (min(xs), min(ys), max(x2s) - min(xs), max(y2s) - min(ys))))
        return out


class FakeOcr:
    """ For tests: returns preset texts depending on image hash or always the same ones."""

    name = "fake"

    def __init__(self, fixed: list[tuple[str, tuple[float, float, float, float]]] | None = None):
        self.fixed = fixed or []

    def recognize(self, img):
        return list(self.fixed)


def default_backend() -> OcrBackend:
    return WindowsOcr()


class RegionOcr:
    """ OCR on image crops with preprocessing and change cache.

    The cache compares a reduced grayscale image of the area with the last
    call for the same key and returns the previous result if content is (almost) identical.
    This keeps unchanged areas cheap.
    """

    def __init__(self, backend: OcrBackend, upscale: float = 3.0, cache_tolerance: float = 1.5):
        self.backend = backend
        self.upscale = upscale
        self.cache_tolerance = cache_tolerance
        self._fail_until: dict = {}         # key -> time until fallback variants are not run again
        self.retry_s = 1.0
        self._cache: dict[str, tuple[np.ndarray, OcrResult]] = {}
        self.calls = 0
        self.cache_hits = 0

    @staticmethod
    def _thumb(img: np.ndarray) -> np.ndarray:
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
        return cv2.resize(g, (48, 16), interpolation=cv2.INTER_AREA).astype(np.int16)

    PAD = 16

    def _recognize(self, crop: np.ndarray, r: Rect, s: float, invert: bool = False) -> OcrResult:
        big = cv2.resize(crop, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC) if s != 1 else crop
        # Windows OCR loses text stuck directly at the image edge -> fill border
        big = cv2.copyMakeBorder(big, self.PAD, self.PAD, self.PAD, self.PAD, cv2.BORDER_REPLICATE)
        if invert:
            # Brightness (max. channel): yellow and white text become equally bright,
            # then inverted -> dark text on light background
            g = big.max(axis=2) if big.ndim == 3 else big
            big = 255 - g
        self.calls += 1
        lines = []
        for text, (x, y, w, h) in self.backend.recognize(big):
            x, y = x - self.PAD, y - self.PAD
            lines.append(OcrLine(text, Rect(int(r.x + x / s), int(r.y + y / s), max(1, int(w / s)), max(1, int(h / s)))))
        return OcrResult(lines)

    def _cached(self, key: str | None, crop: np.ndarray) -> OcrResult | None:
        if key is None:
            return None
        thumb = self._thumb(crop)
        cached = self._cache.get(key)
        if cached is not None and cached[0].shape == thumb.shape:
            if float(np.abs(cached[0] - thumb).mean()) <= self.cache_tolerance:
                self.cache_hits += 1
                return cached[1]
        return None

    def read(self, frame: np.ndarray, rect: Rect, key: str | None = None, upscale: float | None = None,
             accept=None) -> OcrResult:
        """ Reads an area. With `accept` (function OcrResult -> bool) further variants (scaling, inversion) are tried
        on failure; the first accepted result wins, otherwise the standard variant's result."""
        r = rect.clip(frame.shape[1], frame.shape[0])
        if r.w < 4 or r.h < 4:
            return OcrResult()
        crop = r.crop(frame)
        hit = self._cached(key, crop)
        if hit is not None:
            return hit
        s = upscale or self.upscale
        result = self._recognize(crop, r, s)
        if accept is not None and not accept(result):
            # Up to four additional OCR runs per area: for persistently unreadable areas (folded panels,
            # empty pot display) only retry every retry_s seconds - otherwise it eats up analysis time
            import time as _time
            now = _time.monotonic()
            if key is None or self._fail_until.get(key, 0.0) <= now:
                ok = False
                for vs, inv in ((2.0, False), (4.0, False), (s, True), (2.0, True)):
                    if vs == s and not inv:
                        continue
                    alt = self._recognize(crop, r, vs, inv)
                    if accept(alt):
                        result, ok = alt, True
                        break
                if key is not None:
                    if ok:
                        self._fail_until.pop(key, None)
                    else:
                        self._fail_until[key] = now + self.retry_s
        if key is not None:
            self._cache[key] = (self._thumb(crop), result)
        return result

    def read_glyph_tiled(self, glyph_ink: np.ndarray, repeats: int = 3,
                         heights: tuple[int, ...] = (120, 80, 160), accept=None) -> str:
        """ Reads a single character (binary ink = 255) by placing it multiple times side-by-side;
        Windows OCR does not recognize isolated single characters otherwise. The glyph
        is normalized to fixed heights so that the result does not depend on the table scale."""
        if glyph_ink.size == 0:
            return ""
        gh, gw = glyph_ink.shape[:2]
        if gh < 3 or gw > 4 * gh:
            # not a single character (e.g. a flat stroke, recognized as rank) - upscaling would create giant images
            return ""
        text = ""
        for target_h in heights:
            f = target_h / glyph_ink.shape[0]
            g = cv2.resize(glyph_ink, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
            g = 255 - ((g > 127).astype(np.uint8) * 255)
            gap = np.full((g.shape[0], max(20, g.shape[1] // 2)), 255, np.uint8)
            parts = []
            for _ in range(repeats):
                parts += [g, gap]
            tiled = np.hstack(parts[:-1])
            tiled = cv2.copyMakeBorder(tiled, 60, 60, 60, 60, cv2.BORDER_CONSTANT, value=255)
            self.calls += 1
            text = " ".join(t for t, _ in self.backend.recognize(tiled))
            if accept is None or accept(text):
                return text
        return text


def image_digest(img: np.ndarray) -> str:
    return hashlib.sha1(np.ascontiguousarray(img).tobytes()).hexdigest()[:16]

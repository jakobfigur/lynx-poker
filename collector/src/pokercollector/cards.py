"""Card recognition: slot state (empty / backside / open), rank and suit.

Rank: first learned templates (templates/rank/<R>/*.png), otherwise Windows OCR with
 tiled characters. Suit: red/black from the ink, shape by templates or
 a contour heuristic. The heuristic is only tested on spades and hearts against real
 screenshots; diamonds/clubs need real examples (see README).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from .geometry import Rect
from .glyphs import match_rank
from .ocr import RegionOcr
from .poker import RANKS, normalize_rank
from .profile import Profile

CARDS_VERSION = "cards-1"
GLYPH_SIZE = (20, 28)  # (w, h) normalized glyph size


@dataclass
class CardRead:
    rect: Rect
    card: str | None          # e.g. '6s'; None if unreadable
    rank: str | None
    suit: str | None
    color: str | None         # 'red' | 'black'
    confidence: float
    method: str
    rank_glyph: np.ndarray | None = field(default=None, repr=False)
    suit_glyph: np.ndarray | None = field(default=None, repr=False)


@dataclass
class SlotRead:
    state: str                # 'empty' | 'backs' | 'faces' | 'folded'
    backs: int
    faces: list[CardRead]


def _normalize_glyph(ink: np.ndarray) -> np.ndarray | None:
    ys, xs = np.where(ink > 0)
    if len(xs) < 5:
        return None
    g = ink[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return cv2.resize(g, GLYPH_SIZE, interpolation=cv2.INTER_AREA)


class TemplateStore:
    """Learned glyph templates saved on the hard drive (PNG, 255 = ink)."""

    def __init__(self, root: Path | None):
        self.root = root
        self.rank: dict[str, list[np.ndarray]] = {}
        self.suit: dict[str, list[np.ndarray]] = {}
        if root and root.exists():
            for kind, store in (("rank", self.rank), ("suit", self.suit)):
                base = root / kind
                if not base.exists():
                    continue
                for label_dir in base.iterdir():
                    if not label_dir.is_dir():
                        continue
                    for f in label_dir.glob("*.png"):
                        img = cv2.imread(str(f), cv2.IMREAD_GRAYSCALE)
                        if img is not None:
                            store.setdefault(label_dir.name, []).append(
                                cv2.resize(img, GLYPH_SIZE, interpolation=cv2.INTER_AREA))

    def match(self, kind: str, glyph: np.ndarray) -> tuple[str | None, float, float]:
        """(best label, score, distance to second-best label)."""
        store = self.rank if kind == "rank" else self.suit
        if not store:
            return None, 0.0, 0.0
        g = glyph.astype(np.float32)
        g = (g - g.mean()) / (g.std() + 1e-6)
        scores = {}
        for label, tmpls in store.items():
            best = -1.0
            for t in tmpls:
                tf = t.astype(np.float32)
                tf = (tf - tf.mean()) / (tf.std() + 1e-6)
                best = max(best, float((g * tf).mean()))
            scores[label] = best
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        second = ranked[1][1] if len(ranked) > 1 else -1.0
        return ranked[0][0], ranked[0][1], ranked[0][1] - second

    def add(self, kind: str, label: str, glyph: np.ndarray, name: str) -> Path | None:
        if self.root is None:
            return None
        d = self.root / kind / label
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{name}.png"
        cv2.imwrite(str(p), glyph)
        (self.rank if kind == "rank" else self.suit).setdefault(label, []).append(
            cv2.resize(glyph, GLYPH_SIZE, interpolation=cv2.INTER_AREA))
        return p


def _suit_heuristic(glyph_ink: np.ndarray, color: str) -> tuple[str | None, float]:
    contours, _ = cv2.findContours(glyph_ink, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None, 0.0
    c = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(c)
    if w < 4 or h < 4:
        return None, 0.0
    shape = np.zeros_like(glyph_ink)
    cv2.drawContours(shape, [c], -1, 255, -1)
    shape = shape[y:y + h, x:x + w]
    widths = (shape > 0).sum(axis=1) / w
    top = float(widths[: max(1, h // 5)].mean())      # upper fifth
    bottom = float(widths[-max(1, h // 5):].mean())   # lower fifth
    area = cv2.contourArea(c)
    hull_area = cv2.contourArea(cv2.convexHull(c))
    solidity = area / hull_area if hull_area else 0
    if color == "red":
        # Heart: wide top with two arcs; Diamond: pointed top and bottom
        if top > 0.45:
            return "h", 0.6
        if top < 0.3 and bottom < 0.3:
            return "d", 0.5
        return None, 0.0
    # Black: Spade has one tip at the top, Club has three round leaves (lower solidity)
    if top < 0.3 and solidity > 0.8:
        return "s", 0.5
    if solidity < 0.8:
        return "c", 0.4
    return None, 0.0


def _rank_text_ok(text: str) -> bool:
    compact = text.replace(" ", "").upper()
    if not compact:
        return False
    if set(compact) <= set("10OIL"):
        return True
    return any(normalize_rank(ch) for ch in compact)


class CardReader:
    def __init__(self, profile: Profile, ocr: RegionOcr | None, templates: TemplateStore | None = None):
        self.profile = profile
        self.ocr = ocr
        self.templates = templates or TemplateStore(None)
        self._rank_cache: dict[bytes, tuple[str | None, float, str]] = {}

    def _face_rects(self, hsv: np.ndarray, region: Rect, scale: float) -> list[Rect]:
        cfg = self.profile["card"]
        lo, hi = self.profile.hsv("card", "face_hsv")
        sub = region.clip(hsv.shape[1], hsv.shape[0]).crop(hsv)
        mask = cv2.inRange(sub, lo, hi)
        red = cv2.bitwise_or(cv2.inRange(sub, *self.profile.hsv("card", "back_red_hsv_1")),
                             cv2.inRange(sub, *self.profile.hsv("card", "back_red_hsv_2")))
        # Rank/color are dark or red -> fill holes inside each card.
        # No extensive closing: this would merge closely placed cards at small scale.
        raw_white = mask.copy()
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        mask = np.zeros_like(mask)
        cv2.drawContours(mask, contours, -1, 255, -1)
        n, _, stats, _ = cv2.connectedComponentsWithStats(mask)
        rects = []
        for i in range(1, n):
            x, y, w, h, a = stats[i]
            if w >= cfg["min_face_w"] * scale and h >= cfg["min_face_h"] * scale and 0.45 <= w / h <= 0.95:
                # striped backs are largely red, face-up cards barely
                red_share = float((red[y:y + h, x:x + w] > 0).mean())
                # face-up card: predominantly white; back side: stripes, only about half white
                white_share = float((raw_white[y:y + h, x:x + w] > 0).mean())
                if a >= 0.7 * w * h and red_share < 0.25 and white_share > 0.6:
                    rects.append(Rect(int(region.x + x), int(region.y + y), int(w), int(h)))
        rects.sort(key=lambda r: r.x)
        return rects

    def _count_backs(self, hsv: np.ndarray, region: Rect, scale: float) -> int:
        sub = region.clip(hsv.shape[1], hsv.shape[0]).crop(hsv)
        m1 = cv2.inRange(sub, *self.profile.hsv("card", "back_red_hsv_1"))
        m2 = cv2.inRange(sub, *self.profile.hsv("card", "back_red_hsv_2"))
        mask = cv2.bitwise_or(m1, m2)
        # close striped pattern to surfaces
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        n, _, stats, _ = cv2.connectedComponentsWithStats(mask)
        cfg = self.profile["card"]
        count = 0
        for i in range(1, n):
            x, y, w, h, a = stats[i]
            if w >= cfg["min_face_w"] * scale * 0.8 and h >= cfg["min_face_h"] * scale * 0.8:
                # adjacent card backs can merge
                count += max(1, int(round(w / (h * 0.72))))
        return count

    def read_face(self, frame: np.ndarray, rect: Rect) -> CardRead:
        card = rect.crop(frame)
        h, w = card.shape[:2]
        m = max(2, int(round(min(w, h) * 0.07)))
        inner = card[m:h - m, m:w - m]
        gray = cv2.cvtColor(inner, cv2.COLOR_BGR2GRAY)
        ink = (gray < 150).astype(np.uint8) * 255
        rows = np.where(ink.sum(axis=1) > 0)[0]
        if len(rows) < 6:
            return CardRead(rect, None, None, None, None, 0.0, 'no ink')
        # Rank top, color below: largest line gap separates both
        prof = ink.sum(axis=1) > 0
        split = None
        first, last = rows.min(), rows.max()
        gap_start = None
        best_gap = 0
        for yy in range(first, last + 1):
            if not prof[yy]:
                if gap_start is None:
                    gap_start = yy
            elif gap_start is not None:
                if yy - gap_start > best_gap:
                    best_gap = yy - gap_start
                    split = (gap_start + yy) // 2
                gap_start = None
        if split is None:
            split = first + int((last - first) * 0.55)
        rank_ink = ink[:split]
        suit_ink = ink[split:]

        # Color from the ink pixels
        b, g, r = [inner[..., i][ink > 0].astype(int) for i in range(3)]
        red_share = float(((r - np.maximum(g, b)) > 60).mean()) if len(r) else 0.0
        color = "red" if red_share > 0.5 else "black"

        rank_glyph = _normalize_glyph(rank_ink)
        suit_glyph = _normalize_glyph(suit_ink)
        rank, rank_conf, method_parts = None, 0.0, []
        if rank_glyph is not None:
            label, score, margin = self.templates.match("rank", rank_glyph)
            font = None
            if not (label is not None and score > 0.75 and margin > 0.1):
                ys, xs = np.where(rank_ink > 0)
                aspect = (xs.max() - xs.min() + 1) / (ys.max() - ys.min() + 1) if len(xs) else 0.0
                font = match_rank(rank_glyph, aspect)
            if label is not None and score > 0.75 and margin > 0.1:
                rank, rank_conf = label, min(1.0, score)
                method_parts.append("rank:template")
            elif font and font[0] is not None and font[1] > 0.55 and font[2] > 0.08:
                # Shape comparison with font templates (fallback if no learned templates match yet)
                rank, rank_conf = font[0], min(0.8, font[1])
                method_parts.append("rank:font")
            elif self.ocr is not None:
                key = cv2.resize(rank_glyph, (10, 14)).tobytes()
                if key in self._rank_cache:
                    rank, rank_conf, how = self._rank_cache[key]
                else:
                    ys, xs = np.where(rank_ink > 0)
                    crop = rank_ink[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
                    text = self.ocr.read_glyph_tiled(crop, accept=_rank_text_ok)
                    tokens = [normalize_rank(t) for t in text.split()]
                    if not any(tokens) and text:
                        # '666' without spaces -> single characters; '101010' -> '10'
                        compact = text.replace(" ", "")
                        if compact and set(compact) <= set("10OIl"):
                            tokens = ["T"]
                        else:
                            tokens = [normalize_rank(ch) for ch in compact]
                    votes = Counter(t for t in tokens if t)
                    if votes:
                        top, n = votes.most_common(1)[0]
                        rank, rank_conf = top, 0.5 + 0.4 * n / max(1, len(tokens))
                    how = "rank:ocr-tiled"
                    self._rank_cache[key] = (rank, rank_conf, how)
                method_parts.append(how)
        suit, suit_conf = None, 0.0
        if suit_glyph is not None:
            label, score, margin = self.templates.match("suit", suit_glyph)
            if label is not None and score > 0.75 and margin > 0.1:
                suit, suit_conf = label, min(1.0, score)
                method_parts.append("suit:template")
            else:
                suit, suit_conf = _suit_heuristic(suit_ink, color)
                method_parts.append("suit:heuristic")
            if suit and ((suit in "hd") != (color == "red")):
                suit, suit_conf = None, 0.0
                method_parts.append("suit:color-conflict")
        card_str = rank + suit if rank and suit else None
        conf = min(rank_conf, suit_conf) if card_str else 0.0
        return CardRead(rect, card_str, rank, suit, color, conf, "+".join(method_parts) or "none",
                        rank_glyph, suit_glyph)

    def read_region(self, frame: np.ndarray, hsv: np.ndarray, region: Rect, scale: float) -> SlotRead:
        faces = [self.read_face(frame, r) for r in self._face_rects(hsv, region, scale)]
        backs = self._count_backs(hsv, region, scale)
        if faces:
            state = "faces"
        elif backs:
            state = "backs"
        else:
            state = "empty"
        return SlotRead(state, backs, faces)


def valid_rank(r: str | None) -> bool:
    return r is not None and r in RANKS

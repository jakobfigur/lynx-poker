"""Frame -> TableSnapshot: all visible fields with raw value, confidence and image region.

Field keys (examples):
  table.found, info.street, info.game_hand, info.blinds, info.total, info.bets, pot.total,
  board.cards, board.count, hero.to_act, hero.buttons,
  seat.<n>.present|name|stack|bet|folded|active|cards_state|cards|action_label|marker
Values are JSON-capable and comparable (lists/tuples as lists).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from . import parse
from .cards import CARDS_VERSION, CardReader
from .geometry import Rect
from .layout import SeatMemory, TableLayout, detect_layout
from .ocr import OCR_VERSION, RegionOcr
from .profile import Profile

ANALYZER_VERSION = f"analyzer-1/{OCR_VERSION}/{CARDS_VERSION}"


@dataclass
class FieldObs:
    value: Any
    raw: Any = None
    confidence: float = 1.0
    rect: Rect | None = None
    method: str = ""
    note: str = ""


@dataclass
class TableSnapshot:
    frame_index: int
    t_mono: float
    t_wall: float
    fields: dict[str, FieldObs] = field(default_factory=dict)
    layout: TableLayout | None = None
    card_reads: list = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def get(self, key: str, default=None):
        f = self.fields.get(key)
        return f.value if f is not None else default

    def set(self, key: str, value, **kw):
        self.fields[key] = FieldObs(value, **kw)


_STACK_LIKE = re.compile(r"[$S§]\s*[0-9OolI]|^\s*[0-9][0-9 .,]*\s*$")


def _up(base: float, scale: float) -> float:
    """Choose OCR magnification so that text size is independent of the table scale and remains constant."""
    return float(min(5.0, max(1.5, base / max(scale, 0.1))))


def _strict_money(text: str) -> bool:
    """Amount with currency sign, not just digits (digits often partial misreads)."""
    p = parse.extract_money(text)
    return p.ok and 'without currency symbol' not in p.note


def _has_money(res) -> bool:
    return any(_strict_money(l.text) for l in res.lines)


def _has_name_and_stack(res) -> bool:
    money = [l for l in res.lines if _strict_money(l.text)]
    return bool(money) and len(res.lines) > len(money)


def _panel_regions(profile: Profile, hero: bool) -> dict[str, list[float]]:
    return profile["panel_regions"]["hero" if hero else "seat"]


def _yellow_border_share(hsv: np.ndarray, rect: Rect, profile: Profile, scale: float) -> float:
    band = max(2, int(round(4 * scale)))
    outer = rect.expand(band).clip(hsv.shape[1], hsv.shape[0])
    sub = outer.crop(hsv)
    lo, hi = profile.hsv("active_border_hsv")
    mask = cv2.inRange(sub, lo, hi)
    ring = np.zeros(mask.shape, np.uint8)
    ring[:] = 255
    ring[2 * band:-2 * band or None, 2 * band:-2 * band or None] = 0
    total = int((ring > 0).sum())
    return float(((mask > 0) & (ring > 0)).sum()) / total if total else 0.0


def _panel_tint(frame: np.ndarray, hsv: np.ndarray, rect: Rect) -> float:
    """Mean (G - B) of the dark panel background pixels. Hidden (folded)
    panels let the green felt shine through -> positive value."""
    r = rect.clip(frame.shape[1], frame.shape[0])
    sub = r.crop(frame).astype(int)
    hs = r.crop(hsv)
    #only dark, low-saturation pixels: exclude felt edges and yellow text
    bg = (hs[..., 2] < 90) & (hs[..., 1] < 150)
    if bg.sum() < 20:
        return 0.0
    return float(np.median(sub[..., 1][bg] - sub[..., 0][bg]))


class FrameAnalyzer:
    def __init__(self, profile: Profile, ocr: RegionOcr, cards: CardReader):
        self.profile = profile
        self.ocr = ocr
        self.cards = cards
        self.seat_memory = SeatMemory(profile["anchor_tolerance"])

    def reset(self):
        """New session/new table: forget learned seat positions."""
        self.seat_memory.reset()

    def analyze(self, frame: np.ndarray, frame_index: int = 0, t_mono: float = 0.0, t_wall: float = 0.0) -> TableSnapshot:
        snap = TableSnapshot(frame_index, t_mono, t_wall)
        lay = detect_layout(frame, self.profile, self.seat_memory)
        snap.layout = lay
        snap.warnings.extend(lay.warnings)
        snap.set("table.found", lay.found, method="layout")
        if not lay.found:
            return snap
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        s = lay.scale
        snap.set("table.scale", round(s, 3), method="layout")

        self._info_row(frame, lay, snap)
        self._pot(frame, lay, snap)
        self._board(frame, hsv, lay, snap)
        self._action_bar(frame, lay, snap)

        markers = {m.kind: m for m in lay.markers}
        #Marker BEFORE the seats (like _priority offline): a new dealer button is reported     so before the new blinds
        #and the live reconstruction sees the same order as the post-analysis
        for kind in ("D", "SB", "BB"):
            m = markers.get(kind)
            snap.set(f"marker.{kind}", m.seat if m else None, rect=m.rect if m else None,
                     method="color-circle", confidence=0.9 if m and m.seat is not None else 0.0)
        for n in range(10):
            panel = lay.seats.get(n)
            snap.set(f"seat.{n}.present", panel is not None, method="layout",
                     rect=panel.full_rect if panel else None)
            if panel is None:
                continue
            self._seat(frame, hsv, lay, panel, snap)
        return snap

    # ---- Regions -------------------------------------------------------

    def _info_row(self, frame, lay: TableLayout, snap: TableSnapshot):
        if lay.info_left:
            res = self.ocr.read(frame, lay.info_left, key="info.left", upscale=2.0)
            for line in res.lines:
                low = line.text.lower()
                if "gesamt" in low:
                    p = parse.parse_labeled_money(line.text, "gesamt")
                    snap.set("info.total", p.value, raw=line.text, rect=line.rect, method="ocr",
                             confidence=0.9 if p.ok and not p.corrected else (0.6 if p.ok else 0.0), note=p.note)
                elif "eins" in low:
                    p = parse.parse_labeled_money(line.text, "eins")
                    snap.set("info.bets", p.value, raw=line.text, rect=line.rect, method="ocr",
                             confidence=0.9 if p.ok and not p.corrected else (0.6 if p.ok else 0.0), note=p.note)
        if lay.info_center:
            res = self.ocr.read(frame, lay.info_center, key="info.center", upscale=2.0)
            for line in res.lines:
                p = parse.parse_blinds(line.text)
                if p.ok:
                    snap.set("info.blinds", [p.value["sb"], p.value["bb"]], raw=line.text, rect=line.rect,
                             method="ocr", confidence=0.85 if not p.corrected else 0.6)
                    snap.set("info.blinds_extra", p.value["extra"], raw=line.text, rect=line.rect, method="ocr",
                             confidence=0.5)
                    break
        if lay.info_right:
            res = self.ocr.read(frame, lay.info_right, key="info.right", upscale=2.0)
            for line in res.lines:
                ps = parse.parse_street(line.text)
                if ps.ok and "info.street" not in snap.fields:
                    snap.set("info.street", ps.value, raw=line.text, rect=line.rect, method="ocr",
                             confidence=0.9 if not ps.corrected else 0.6)
                    continue
                pg = parse.parse_game_hand(line.text)
                if pg.ok:
                    snap.set("info.game_hand", list(pg.value), raw=line.text, rect=line.rect, method="ocr",
                             confidence=0.9 if not pg.corrected else 0.6)

    def _pot(self, frame, lay: TableLayout, snap: TableSnapshot):
        res = self.ocr.read(frame, lay.pot, key="pot", upscale=_up(2.0, lay.scale), accept=_has_money)
        for line in res.lines:
            p = parse.extract_money(line.text)
            if p.ok:
                snap.set("pot.total", p.value, raw=line.text, rect=line.rect, method="ocr",
                         confidence=0.9 if not p.corrected else 0.6)
                return
        snap.set("pot.total", None, raw=res.text or None, rect=lay.pot, method="ocr", confidence=0.0,
                 note='no pot readable')

    def _board(self, frame, hsv, lay: TableLayout, snap: TableSnapshot):
        """Board cards searched directly as card areas in the table center (size/distance depend on
        layout), sorted left to right."""
        f = lay.felt
        top = lay.pot.y2 if lay.pot else int(f.y + 0.3 * f.h)
        hero = lay.seats.get(0)
        bottom = min(hero.rect.y if hero else f.y2, int(f.y + 0.7 * f.h))
        union = Rect(int(f.x + 0.22 * f.w), top, int(0.56 * f.w), max(1, bottom - top))
        slot_read = self.cards.read_region(frame, hsv, union, lay.scale)
        faces = sorted(slot_read.faces, key=lambda c: c.rect.x)[:5]
        snap.card_reads.extend(("board", c) for c in faces)
        cards: list[str | None] = [c.card or "??" for c in faces] + [None] * (5 - len(faces))
        confs = [c.confidence for c in faces]
        count = len(faces)
        snap.set("board.count", count, method="card-detect", rect=union,
                 confidence=0.9 if count in (0, 3, 4, 5) else 0.3,
                 note="" if count in (0, 3, 4, 5) else 'unusual number of cards on the board')
        snap.set("board.cards", cards, method="card-read", rect=union,
                 confidence=min(confs) if confs else (0.9 if count == 0 else 0.0))

    def _action_bar(self, frame, lay: TableLayout, snap: TableSnapshot):
        snap.set("hero.to_act", lay.action_bar is not None, rect=lay.action_bar, method="layout",
                 confidence=0.8)
        if lay.action_bar is None:
            snap.set("hero.buttons", None, method="layout")
            return
        res = self.ocr.read(frame, lay.action_bar, key="actionbar", upscale=1.5)
        buttons = []
        lines = sorted(res.lines, key=lambda l: (l.rect.x // 40, l.rect.y))
        #Button label (e.g. 'Call') and amount ('$20') are in two lines underneath
        used = set()
        for i, line in enumerate(lines):
            act = parse.parse_action_label(line.text)
            if not act.ok or i in used:
                continue
            amount = None
            pb = parse.parse_button(line.text)
            if pb.ok and pb.value[1] is not None:
                amount = pb.value[1]
            else:
                for j, other in enumerate(lines):
                    if j == i or j in used:
                        continue
                    if abs(other.rect.cx - line.rect.cx) < 40 * lay.scale and 0 < other.rect.y - line.rect.y < 30 * lay.scale:
                        pm = parse.parse_money(other.text)
                        if pm.ok:
                            amount = pm.value
                            used.add(j)
                            break
            #Quick-action buttons ('All-In', '1/2', 'Pot') lie above the large buttons
            big = line.rect.y > lay.action_bar.y + lay.action_bar.h * 0.45
            buttons.append({"action": act.value, "amount": amount, "primary": big, "raw": line.text})
        #Bar detected, no button read = a statement (no buttons), no read error: otherwise the
        #old call button remains until unknown_after_ms and 'your turn' lights after the click
        snap.set("hero.buttons", [b for b in buttons if b["primary"]], raw=res.text, method="ocr",
                 rect=lay.action_bar, confidence=0.8 if buttons else 0.5)

    def _seat(self, frame, hsv, lay: TableLayout, panel, snap: TableSnapshot):
        n = panel.seat
        s = lay.scale
        regions = _panel_regions(self.profile, panel.hero)
        r_cards = panel.rect.sub(*regions["cards"], scale=s)
        r_text = panel.rect.sub(*regions["text"], scale=s)
        #Text is right-aligned (Stack): read up to the measured right panel edge, even if
        #the panel was recognized wider by adjacent elements (e.g. SB button)
        r_text = Rect(r_text.x, r_text.y, panel.rect.x2 - r_text.x, r_text.h)

        #Name + Stack: text lines in the lower panel part
        res = self.ocr.read(frame, r_text, key=f"seat.{n}.text", upscale=_up(3.0, s), accept=_has_name_and_stack)
        name_lines, stack = [], None
        for line in sorted(res.lines, key=lambda l: l.rect.y):
            p = parse.extract_money(line.text) if _STACK_LIKE.search(line.text) else None
            if p is not None and p.ok:
                stack = (p, line)
            else:
                name_lines.append(line)
        if name_lines:
            text = " ".join(l.text for l in name_lines)
            snap.set(f"seat.{n}.name", text, raw=text, rect=name_lines[0].rect, method="ocr",
                     confidence=0.7 if not text.endswith("...") else 0.5,
                     note="abgeschnitten" if text.endswith("...") else "")
        if stack:
            p, line = stack
            conf = 0.9 if not p.corrected else 0.6
            if 'without currency symbol' in p.note:
                conf = 0.3
            snap.set(f"seat.{n}.stack", p.value, raw=line.text, rect=line.rect, method="ocr",
                     confidence=conf, note=p.note)
        else:
            snap.set(f"seat.{n}.stack", None, raw=res.text or None, rect=r_text, method="ocr",
                     confidence=0.0, note='no stack readable')

        #Bet in the line below the panel
        if panel.has_bet_row:
            r_bet = panel.rect.sub(*regions["bet"], scale=s)
            r_bet = Rect(r_bet.x, r_bet.y, panel.rect.x2 - r_bet.x, r_bet.h)
            rb = self.ocr.read(frame, r_bet, key=f"seat.{n}.bet", upscale=_up(3.0, s), accept=_has_money)
            bet = None
            for line in rb.lines:
                p = parse.extract_money(line.text)
                if p.ok:
                    bet = (p, line)
                    break
            if bet:
                p, line = bet
                snap.set(f"seat.{n}.bet", p.value, raw=line.text, rect=line.rect, method="ocr",
                         confidence=0.9 if not p.corrected else 0.6)
            else:
                snap.set(f"seat.{n}.bet", None, raw=rb.text or None, rect=r_bet, method="ocr",
                         confidence=0.0, note='bet line visible, amount unreadable')
        else:
            snap.set(f"seat.{n}.bet", 0, rect=panel.rect, method="no-bet-row", confidence=0.8)

        #Cards, fold, action label
        slot = self.cards.read_region(frame, hsv, r_cards, s)
        snap.card_reads.extend((f"seat.{n}", c) for c in slot.faces)
        rc = self.ocr.read(frame, r_cards, key=f"seat.{n}.cards", upscale=_up(3.0, s))
        label = None
        for line in rc.lines:
            p = parse.parse_action_label(line.text)
            if p.ok:
                label = (p.value, line)
                break
        tint = _panel_tint(frame, hsv, panel.rect)
        folded_by_tint = tint > self.profile["fold_tint_threshold"]
        folded_by_label = label is not None and label[0] == "fold"
        snap.set(f"seat.{n}.folded", folded_by_label or folded_by_tint,
                 raw={"tint": round(tint, 1), "label": label[1].text if label else None},
                 rect=panel.rect, method="label+tint",
                 confidence=0.95 if folded_by_label and folded_by_tint else 0.7)
        if label is not None:
            snap.set(f"seat.{n}.action_label", label[0], raw=label[1].text, rect=label[1].rect,
                     method="ocr", confidence=0.85)
        else:
            snap.set(f"seat.{n}.action_label", None, method="ocr", confidence=0.6)

        state = "folded" if (folded_by_label or folded_by_tint) else slot.state
        snap.set(f"seat.{n}.cards_state", state, raw={"backs": slot.backs, "faces": len(slot.faces)},
                 rect=r_cards, method="card-detect", confidence=0.8)
        if slot.faces:
            cards = [c.card or "??" for c in slot.faces]
            snap.set(f"seat.{n}.cards", cards, rect=r_cards, method=slot.faces[0].method,
                     confidence=min(c.confidence for c in slot.faces))
        else:
            snap.set(f"seat.{n}.cards", None, rect=r_cards, method="card-detect", confidence=0.8)

        share = _yellow_border_share(hsv, panel.rect, self.profile, s)
        snap.set(f"seat.{n}.active", share > 0.12, raw=round(share, 3), rect=panel.rect,
                 method="border-color", confidence=0.8)

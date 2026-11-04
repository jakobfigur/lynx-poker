"""Findet Tisch, Sitz-Panels, Board-Karten, Marker und Aktionsleiste im Frame.

Alles wird pro Frame aus sichtbaren Bildmerkmalen bestimmt. Sitze werden NICHT an festen
Profil-Positionen gesucht (die Anordnung haengt bei PokerTH von der Spielerzahl ab), sondern:
alle Spieler-Panels finden, das eigene (groesstes Panel unten in der Mitte) wird Sitz 0, die
uebrigen werden im Uhrzeigersinn um die Tischmitte nummeriert (= Aktionsreihenfolge).
SeatMemory merkt sich die Positionen ueber die Frames, damit Nummern stabil bleiben, auch wenn
ein Panel verschwindet (Spieler ausgeschieden). Massstab = gemessene Panelbreite / Referenz.
Geprueft an 10er- (Testbild) und 6er-Tisch (Aufnahme 26.10.2026).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from .geometry import Rect
from .profile import Profile


@dataclass
class SeatPanel:
    seat: int
    rect: Rect            # Haupt-Panel ohne Einsatzzeile
    full_rect: Rect       # inkl. Einsatzzeile, falls vorhanden
    has_bet_row: bool
    hero: bool


@dataclass
class Marker:
    kind: str             # 'D' | 'SB' | 'BB'
    rect: Rect
    seat: int | None
    distance: float


@dataclass
class TableLayout:
    found: bool
    felt: Rect | None = None
    scale: float = 1.0
    seats: dict[int, SeatPanel] = field(default_factory=dict)
    board_slots: list[Rect] = field(default_factory=list)
    pot: Rect | None = None
    info_left: Rect | None = None
    info_center: Rect | None = None
    info_right: Rect | None = None
    action_bar: Rect | None = None
    markers: list[Marker] = field(default_factory=list)
    unmatched_panels: list[Rect] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class SeatMemory:
    """Gelernte Sitzpositionen eines Tisches (relativ zum Filz). Index in `positions` = Sitznummer."""

    def __init__(self, tol: float = 0.06):
        self.tol = tol
        self.positions: list[tuple[float, float]] = []

    def reset(self):
        self.positions = []

    def assign(self, centers: list[tuple[float, float]], hero: int | None) -> list[int]:
        """Sitznummer je Panel-Mittelpunkt. Erste Belegung: eigener Platz 0, dann im Uhrzeigersinn."""
        if not centers:
            return []
        if not self.positions:
            cx = sum(c[0] for c in centers) / len(centers)
            cy = sum(c[1] for c in centers) / len(centers)
            h = hero if hero is not None else max(range(len(centers)), key=lambda i: centers[i][1])
            a0 = np.arctan2(centers[h][1] - cy, centers[h][0] - cx)
            # Bildschirm-y zeigt nach unten: steigender Winkel = im Uhrzeigersinn
            order = sorted(range(len(centers)),
                           key=lambda i: (np.arctan2(centers[i][1] - cy, centers[i][0] - cx) - a0) % (2 * np.pi))
            self.positions = [centers[i] for i in order]
        out = [-1] * len(centers)
        pairs = sorted((((c[0] - p[0]) ** 2 + (c[1] - p[1]) ** 2) ** 0.5, i, j)
                       for i, c in enumerate(centers) for j, p in enumerate(self.positions))
        used_c, used_p = set(), set()
        for d, i, j in pairs:
            if d > self.tol or i in used_c or j in used_p:
                continue
            out[i] = j
            used_c.add(i)
            used_p.add(j)
            px, py = self.positions[j]
            self.positions[j] = (0.9 * px + 0.1 * centers[i][0], 0.9 * py + 0.1 * centers[i][1])
        for i, c in enumerate(centers):
            if out[i] < 0 and len(self.positions) < 10:
                out[i] = len(self.positions)          # neuer Platz: naechste freie Nummer (stabil)
                self.positions.append(c)
        return out


def _felt_rect(hsv: np.ndarray, profile: Profile) -> Rect | None:
    lo, hi = profile.hsv("felt_hsv")
    mask = cv2.inRange(hsv, lo, hi)
    h, w = mask.shape
    row_cov = mask.mean(axis=1) / 255.0
    rows = np.where(row_cov > 0.45)[0]
    if len(rows) < h * 0.25:
        return None
    y0, y1 = int(rows.min()), int(rows.max())
    col_cov = mask[y0:y1 + 1].mean(axis=0) / 255.0
    cols = np.where(col_cov > 0.45)[0]
    if len(cols) < w * 0.25:
        return None
    x0, x1 = int(cols.min()), int(cols.max())
    return Rect(x0, y0, x1 - x0 + 1, y1 - y0 + 1)


def _dark_components(hsv: np.ndarray, felt: Rect, profile: Profile, min_area: int) -> list[Rect]:
    lo, hi = profile.hsv("panel_hsv")
    dark = cv2.inRange(hsv, lo, hi)
    region = np.zeros_like(dark)
    region[felt.y:felt.y2, felt.x:felt.x2] = 255
    dark = cv2.bitwise_and(dark, region)
    dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(dark)
    out = []
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        if a < min_area:
            continue
        # Duenne Randzeilen oben/unten abschneiden: Schatten fliegender Karten haengen
        # sonst schmal am Panel und verschieben die Kante. Mittlere Zeilen sind wegen
        # Avatar/Karten loechrig und werden nicht angefasst.
        cov = (labels[y:y + h, x:x + w] == i).mean(axis=1)
        top, bottom = 0, h - 1
        while top < bottom and cov[top] < 0.3:
            top += 1
        while bottom > top and cov[bottom] < 0.3:
            bottom -= 1
        y, h = y + top, bottom - top + 1
        out.append(Rect(int(x), int(y), int(w), int(h)))
    return out


def _find_markers(hsv: np.ndarray, felt: Rect, layout: TableLayout, profile: Profile) -> list[Marker]:
    m = profile["markers"]
    s = layout.scale
    diam = m["diameter"] * s
    blocked = np.zeros(hsv.shape[:2], np.uint8)
    for p in layout.seats.values():
        r = p.full_rect.expand(2)
        blocked[max(r.y, 0):r.y2, max(r.x, 0):r.x2] = 255
    for r in layout.board_slots:
        blocked[max(r.y, 0):r.y2, max(r.x, 0):r.x2] = 255
    if layout.action_bar:
        r = layout.action_bar
        blocked[r.y:r.y2, r.x:r.x2] = 255
    felt_mask = np.zeros_like(blocked)
    felt_mask[felt.y:felt.y2, felt.x:felt.x2] = 255
    allowed = cv2.bitwise_and(felt_mask, cv2.bitwise_not(blocked))

    masks = {
        "D": cv2.inRange(hsv, *profile.hsv("markers", "dealer_hsv")),
        "SB": cv2.inRange(hsv, *profile.hsv("markers", "sb_hsv")),
        "BB": cv2.bitwise_or(cv2.inRange(hsv, *profile.hsv("markers", "bb_hsv")),
                             cv2.inRange(hsv, *profile.hsv("markers", "bb_hsv_2"))),
    }
    found: list[Marker] = []
    for kind, mask in masks.items():
        mask = cv2.bitwise_and(mask, allowed)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best = None
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if not (0.6 * diam <= w <= 1.4 * diam and 0.6 * diam <= h <= 1.4 * diam):
                continue
            if not 0.8 <= w / h <= 1.25:
                continue
            # Konvexe Huelle: die Beschriftung (D/SB/BB) schneidet Loecher in die Farbmaske
            hull = cv2.convexHull(c)
            area = cv2.contourArea(hull)
            perim = cv2.arcLength(hull, True)
            circ = 4 * np.pi * area / (perim * perim) if perim else 0
            # Kreis ~0.9, Quadrat ~0.785: Schwelle trennt fliegende Karten von Buttons
            if circ < 0.8:
                continue
            score = circ
            if best is None or score > best[0]:
                best = (score, Rect(x, y, w, h))
        if best is None:
            continue
        rect = best[1]
        seat, dist = None, float("inf")
        for p in layout.seats.values():
            r = p.rect
            dx = max(r.x - rect.cx, 0, rect.cx - r.x2)
            dy = max(r.y - rect.cy, 0, rect.cy - r.y2)
            d = (dx * dx + dy * dy) ** 0.5
            if d < dist:
                seat, dist = p.seat, d
        if dist > m["max_distance"] * s:
            seat = None
        found.append(Marker(kind, rect, seat, dist))
    return found


def detect_layout(frame: np.ndarray, profile: Profile, memory: SeatMemory | None = None) -> TableLayout:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    felt = _felt_rect(hsv, profile)
    if felt is None:
        return TableLayout(found=False, warnings=["kein Pokertisch (Filz) erkannt"])
    ref = profile["reference"]
    lay = TableLayout(found=True, felt=felt)

    # Grobe Mindestflaeche aus Filzbreite (Referenz: Panel 133 px bei Filz 1905 px)
    est_scale = felt.w / 1905.0
    comps = _dark_components(hsv, felt, profile, min_area=int(4000 * est_scale * est_scale))

    bar_cfg = profile["action_bar"]
    panels = []
    for r in comps:
        if r.w >= bar_cfg["min_width"] * est_scale and r.h >= bar_cfg["min_height"] * est_scale * 0.8:
            if lay.action_bar is None or r.area > lay.action_bar.area:
                lay.action_bar = r
            continue
        aspect = r.w / r.h if r.h else 0
        if 0.9 <= aspect <= 1.9:
            panels.append(r)
        elif r.w > 3 * r.h:
            continue  # duenne Streifen (z. B. Fensterrand)
        else:
            lay.unmatched_panels.append(r)

    # Eigenes Panel: unten, waagerecht am naechsten zur Mitte (PokerTH zeigt den eigenen Platz immer dort).
    # Nicht "groesstes Panel": ein Nachbar mit Einsatzzeile kann groesser sein.
    lower = [i for i, r in enumerate(panels) if r.cy > felt.y + 0.5 * felt.h and abs(r.cx - felt.cx) < 0.12 * felt.w]
    hero_i = min(lower, key=lambda i: abs(panels[i].cx - felt.cx)) if lower else None
    others = [p.w for i, p in enumerate(panels) if i != hero_i]
    if others:
        lay.scale = float(np.median(others)) / ref["panel_w"]
    elif hero_i is not None:
        lay.scale = panels[hero_i].w / ref["hero_panel_w"]
    else:
        lay.scale = est_scale
        lay.warnings.append("Massstab aus Filzbreite geschaetzt (keine Panels)")
    s = lay.scale

    memory = memory or SeatMemory(profile["anchor_tolerance"])
    centers = [((r.cx - felt.x) / felt.w, (r.y + min(r.h, ref["panel_h"] * s) / 2 - felt.y) / felt.h) for r in panels]
    seat_ids = memory.assign(centers, hero_i)
    for i, (r, n) in enumerate(zip(panels, seat_ids)):
        if n < 0:
            lay.unmatched_panels.append(r)
            continue
        hero = i == hero_i
        main_h = int(round((ref["hero_panel_h"] if hero else ref["panel_h"]) * s))
        has_bet = r.h >= main_h + ref["bet_row_h"] * s * 0.6
        main = Rect(r.x, r.y, r.w, min(r.h, main_h))
        lay.seats[n] = SeatPanel(n, main, r, has_bet, hero)
    if lay.unmatched_panels:
        lay.warnings.append(f"{len(lay.unmatched_panels)} Panel(s) ohne Sitz")

    lay.board_slots = [
        Rect(int(felt.x + b[0] * felt.w), int(felt.y + b[1] * felt.h), int(b[2] * felt.w), int(b[3] * felt.h))
        for b in profile["board_slots"]
    ]
    p = profile["pot"]
    lay.pot = Rect(int(felt.x + p[0] * felt.w), int(felt.y + p[1] * felt.h), int(p[2] * felt.w), int(p[3] * felt.h))

    info = profile["info_row"]
    top = int(felt.y - info["height"] * s)
    if top >= 0:
        lay.info_left = Rect(felt.x, top, 0, 0).sub(*info["left"], scale=s)
        lay.info_center = Rect(int(felt.cx), top, 0, 0).sub(*info["center"], scale=s)
        lay.info_right = Rect(felt.x2, top, 0, 0).sub(*info["right"], scale=s)
    else:
        lay.warnings.append("Infozeile oberhalb des Filzes nicht im Bild")

    lay.markers = _find_markers(hsv, felt, lay, profile)
    return lay

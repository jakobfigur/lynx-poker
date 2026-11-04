"""Einfache Rechteck-Geometrie in Pixelkoordinaten (x, y, Breite, Hoehe)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def x2(self) -> int:
        return self.x + self.w

    @property
    def y2(self) -> int:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    @property
    def area(self) -> int:
        return max(0, self.w) * max(0, self.h)

    def clip(self, width: int, height: int) -> "Rect":
        x = min(max(self.x, 0), width)
        y = min(max(self.y, 0), height)
        x2 = min(max(self.x2, 0), width)
        y2 = min(max(self.y2, 0), height)
        return Rect(x, y, x2 - x, y2 - y)

    def crop(self, img: np.ndarray) -> np.ndarray:
        r = self.clip(img.shape[1], img.shape[0])
        return img[r.y:r.y2, r.x:r.x2]

    def offset(self, dx: int, dy: int) -> "Rect":
        return Rect(self.x + dx, self.y + dy, self.w, self.h)

    def expand(self, d: int) -> "Rect":
        return Rect(self.x - d, self.y - d, self.w + 2 * d, self.h + 2 * d)

    def sub(self, rx: float, ry: float, rw: float, rh: float, scale: float = 1.0) -> "Rect":
        """Teilrechteck relativ zur linken oberen Ecke, Masse in Referenzpixeln * scale."""
        return Rect(
            int(round(self.x + rx * scale)),
            int(round(self.y + ry * scale)),
            int(round(rw * scale)),
            int(round(rh * scale)),
        )

    def contains(self, x: float, y: float) -> bool:
        return self.x <= x < self.x2 and self.y <= y < self.y2

    def iou(self, other: "Rect") -> float:
        ix = max(0, min(self.x2, other.x2) - max(self.x, other.x))
        iy = max(0, min(self.y2, other.y2) - max(self.y, other.y))
        inter = ix * iy
        union = self.area + other.area - inter
        return inter / union if union else 0.0

    def as_list(self) -> list[int]:
        return [self.x, self.y, self.w, self.h]

    @staticmethod
    def from_list(v) -> "Rect":
        return Rect(int(v[0]), int(v[1]), int(v[2]), int(v[3]))

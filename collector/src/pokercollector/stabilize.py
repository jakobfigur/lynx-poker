""" Temporal stabilization of individual fields.

A new value is considered stable only after being read in `min_frames` consecutive
analyses and for at least `min_ms` duration. Short-lived values are not averaged out
but reported as 'transient'. Unreadable values (None with
confidence 0) replace a stable value only after `unknown_after_ms`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .analyzer import FieldObs, TableSnapshot

# Fields that can legitimately change very rapidly between frames and
# therefore require only 1 frame confirmation.
FAST_FIELDS = ("hero.to_act",)


def _key(v: Any) -> str:
    return json.dumps(v, sort_keys=True, default=str)


@dataclass
class FieldEvent:
    kind: str                 # 'change' | 'transient' | 'unknown'
    field: str
    old: Any
    new: Any
    t_first: float            # Monotonic time of first observation of the new value
    t_confirmed: float
    frame_first: int
    frame_confirmed: int
    confidence: float
    raw: Any = None
    rect: list[int] | None = None
    method: str = ""
    note: str = ""


@dataclass
class _Track:
    stable: Any = None
    stable_key: str | None = None
    has_stable: bool = False
    cand: Any = None
    cand_key: str | None = None
    cand_count: int = 0
    cand_t0: float = 0.0
    cand_f0: int = 0
    cand_obs: FieldObs | None = None
    unreadable_since: float | None = None
    unreadable_f0: int = 0


@dataclass
class Stabilizer:
    min_frames: int = 2
    min_ms: float = 150.0
    unknown_after_ms: float = 1500.0
    min_confidence: float = 0.3
    tracks: dict[str, _Track] = field(default_factory=dict)

    def state(self) -> dict[str, Any]:
        return {k: t.stable for k, t in self.tracks.items() if t.has_stable}

    def update(self, snap: TableSnapshot) -> list[FieldEvent]:
        events: list[FieldEvent] = []
        t = snap.t_mono * 1000.0
        for name, obs in snap.fields.items():
            tr = self.tracks.setdefault(name, _Track())
            unreadable = obs.value is None and obs.confidence <= 0.0
            if unreadable or obs.confidence < self.min_confidence:
                if tr.unreadable_since is None:
                    tr.unreadable_since = t
                    tr.unreadable_f0 = snap.frame_index
                if tr.has_stable and tr.stable is not None and t - tr.unreadable_since >= self.unknown_after_ms:
                    events.append(FieldEvent("unknown", name, tr.stable, None, tr.unreadable_since / 1000.0,
                                             snap.t_mono, tr.unreadable_f0, snap.frame_index, 0.0,
                                             raw=obs.raw, rect=obs.rect.as_list() if obs.rect else None,
                                             method=obs.method, note=obs.note or 'unreadable for a longer time'))
                    tr.stable, tr.stable_key = None, _key(None)
                continue
            tr.unreadable_since = None
            k = _key(obs.value)
            if tr.has_stable and k == tr.stable_key:
                if tr.cand_key is not None and tr.cand_count > 0:
                    self._transient(tr, name, snap, events)
                tr.cand_key, tr.cand_count = None, 0
                continue
            if k != tr.cand_key:
                if tr.cand_key is not None and tr.cand_count > 0:
                    self._transient(tr, name, snap, events)
                tr.cand, tr.cand_key, tr.cand_count = obs.value, k, 1
                tr.cand_t0, tr.cand_f0, tr.cand_obs = t, snap.frame_index, obs
            else:
                tr.cand_count += 1
                if obs.confidence > (tr.cand_obs.confidence if tr.cand_obs else 0):
                    tr.cand_obs = obs
            need_frames = 1 if name in FAST_FIELDS else self.min_frames
            need_ms = 0.0 if name in FAST_FIELDS else self.min_ms
            if tr.cand_count >= need_frames and (t - tr.cand_t0) >= need_ms:
                best = tr.cand_obs or obs
                events.append(FieldEvent("change", name, tr.stable if tr.has_stable else None, tr.cand,
                                         tr.cand_t0 / 1000.0, snap.t_mono, tr.cand_f0, snap.frame_index,
                                         best.confidence, raw=best.raw,
                                         rect=best.rect.as_list() if best.rect else None,
                                         method=best.method, note=best.note))
                tr.stable, tr.stable_key, tr.has_stable = tr.cand, tr.cand_key, True
                tr.cand_key, tr.cand_count = None, 0
        return events

    def _transient(self, tr: _Track, name: str, snap: TableSnapshot, events: list[FieldEvent]):
        o = tr.cand_obs
        events.append(FieldEvent("transient", name, tr.stable, tr.cand, tr.cand_t0 / 1000.0, snap.t_mono,
                                 tr.cand_f0, snap.frame_index, o.confidence if o else 0.0,
                                 raw=o.raw if o else None, rect=o.rect.as_list() if o and o.rect else None,
                                 method=o.method if o else "", note='only briefly seen, not confirmed'))

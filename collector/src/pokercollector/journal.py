"""Sitzungsordner, append-only Beobachtungsjournal (JSONL), Belegbilder, SQLite-Index.

Layout einer Sitzung:
  sessions/<UTC-Zeit>_<uuid8>/
    session.json            Metadaten, Segmente, Luecken, Fehler (wird fortgeschrieben)
    video/segment_0001.mp4  Aufnahmesegmente (falls aufgenommen)
    video/segment_0001.frames.jsonl   Zeitstempel je Frame
    observations.jsonl      unveraenderliche Feldereignisse mit Provenienz
    evidence/               Bildausschnitte als Beleg je Ereignis
    hands.json              Rekonstruktion (versioniert, jederzeit neu erzeugbar)
    index.sqlite            durchsuchbarer Index (aus JSONL neu erzeugbar)
    manifest.json           SHA-256 abgeschlossener Dateien
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from . import __version__
from .geometry import Rect

SCHEMA_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _json_default(o):
    if dataclasses.is_dataclass(o):
        return dataclasses.asdict(o)
    if isinstance(o, Rect):
        return o.as_list()
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, Path):
        return str(o)
    raise TypeError(f"nicht serialisierbar: {type(o)}")


def dumps(o) -> str:
    return json.dumps(o, ensure_ascii=False, default=_json_default)


class Session:
    def __init__(self, root: Path, meta: dict[str, Any]):
        self.root = root
        self.meta = meta
        (root / "evidence").mkdir(parents=True, exist_ok=True)
        (root / "video").mkdir(parents=True, exist_ok=True)
        self._obs = open(root / "observations.jsonl", "a", encoding="utf-8")
        self._seq = 0
        self._lock = threading.RLock()      # Analyse- und Hauptthread schreiben beide (error/gap/write_event)

    # ---- Anlage / Laden --------------------------------------------------

    @staticmethod
    def create(base: Path, source: dict[str, Any], profile_id: str, analyzer_version: str,
               extra: dict[str, Any] | None = None) -> "Session":
        sid = str(uuid.uuid4())
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        root = base / f"{stamp}_{sid[:8]}"
        root.mkdir(parents=True, exist_ok=False)
        meta = {
            "schema_version": SCHEMA_VERSION,
            "session_id": sid,
            "created_utc": _utc_now(),
            "ended_utc": None,
            "software_version": __version__,
            "analyzer_version": analyzer_version,
            "profile": profile_id,
            "source": source,
            "segments": [],
            "gaps": [],
            "errors": [],
            "stats": {},
        }
        meta.update(extra or {})
        s = Session(root, meta)
        s.save_meta()
        return s

    @staticmethod
    def open(root: Path) -> "Session":
        meta = json.loads((root / "session.json").read_text("utf-8"))
        return Session(root, meta)

    def save_meta(self):
        with self._lock:
            tmp = self.root / "session.json.tmp"
            tmp.write_text(json.dumps(self.meta, ensure_ascii=False, indent=2, default=_json_default), "utf-8")
            os.replace(tmp, self.root / "session.json")

    # ---- Protokoll -------------------------------------------------------

    def gap(self, t_start: float, t_end: float, reason: str):
        with self._lock:
            self.meta["gaps"].append({"t_start": t_start, "t_end": t_end, "reason": reason,
                                      "logged_utc": _utc_now()})
            self.save_meta()

    def error(self, message: str, **kw):
        with self._lock:
            self.meta["errors"].append({"message": message, "utc": _utc_now(), **kw})
            self.save_meta()

    def write_event(self, event, frame: np.ndarray | None = None, segment: str | None = None,
                    save_evidence: bool = True) -> dict:
        with self._lock:
            self._seq += 1
            rec = dataclasses.asdict(event) if dataclasses.is_dataclass(event) else dict(event)
            rec["seq"] = self._seq
            rec["segment"] = segment
            rec["logged_utc"] = _utc_now()
            if save_evidence and frame is not None and rec.get("rect"):
                r = Rect.from_list(rec["rect"]).expand(6)
                crop = r.crop(frame)
                if crop.size:
                    name = f"{self._seq:07d}_{rec['field'].replace('.', '_')}.png"
                    cv2.imwrite(str(self.root / "evidence" / name), crop)
                    rec["evidence"] = f"evidence/{name}"
            self._obs.write(dumps(rec) + "\n")
            self._obs.flush()
            return rec

    def close(self):
        self._obs.close()
        self.meta["ended_utc"] = _utc_now()
        self.save_meta()
        build_index(self.root)
        write_manifest(self.root)


def read_events(root: Path) -> list[dict]:
    p = root / "observations.jsonl"
    if not p.exists():
        return []
    out = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    # Letzte Zeile nach Absturz evtl. unvollstaendig: ueberspringen, nicht reparieren
                    out.append({"kind": "corrupt_line", "raw": line[:200]})
    return out


def build_index(root: Path):
    db = root / "index.sqlite"
    if db.exists():
        db.unlink()
    con = sqlite3.connect(db)
    con.execute("""CREATE TABLE events(seq INTEGER PRIMARY KEY, kind TEXT, field TEXT, old TEXT, new TEXT,
                   t_first REAL, t_confirmed REAL, frame_first INTEGER, frame_confirmed INTEGER,
                   confidence REAL, raw TEXT, method TEXT, note TEXT, evidence TEXT, segment TEXT)""")
    rows = []
    for e in read_events(root):
        if "seq" not in e:
            continue
        rows.append((e["seq"], e.get("kind"), e.get("field"), dumps(e.get("old")), dumps(e.get("new")),
                     e.get("t_first"), e.get("t_confirmed"), e.get("frame_first"), e.get("frame_confirmed"),
                     e.get("confidence"), dumps(e.get("raw")), e.get("method"), e.get("note"),
                     e.get("evidence"), e.get("segment")))
    con.executemany("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    hands = root / "hands.json"
    if hands.exists():
        data = json.loads(hands.read_text("utf-8"))
        con.execute("""CREATE TABLE hands(idx INTEGER, game INTEGER, hand INTEGER, status TEXT,
                       t_start REAL, t_end REAL, json TEXT)""")
        for i, h in enumerate(data.get("hands", [])):
            con.execute("INSERT INTO hands VALUES (?,?,?,?,?,?,?)",
                        (i, h.get("game_no"), h.get("hand_no"), h.get("status"), h.get("t_start"),
                         h.get("t_end"), dumps(h)))
    con.commit()
    con.close()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(root: Path):
    files = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name != "manifest.json" and "evidence" not in p.parts:
            files[str(p.relative_to(root)).replace("\\", "/")] = sha256_file(p)
    (root / "manifest.json").write_text(json.dumps({"created_utc": _utc_now(), "files": files}, indent=2), "utf-8")


def verify_manifest(root: Path) -> list[str]:
    m = json.loads((root / "manifest.json").read_text("utf-8"))
    problems = []
    for rel, digest in m["files"].items():
        p = root / rel
        if not p.exists():
            problems.append(f"fehlt: {rel}")
        elif sha256_file(p) != digest:
            problems.append(f"geaendert: {rel}")
    return problems


def monotonic() -> float:
    return time.perf_counter()

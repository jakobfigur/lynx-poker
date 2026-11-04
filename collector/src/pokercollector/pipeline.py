""" Connects source -> analysis -> stabilization -> journal -> reconstruction.

Offline (video/images): every `step`-th image is analyzed, the original video is
referenced by path + SHA-256 and not copied.

Live (window): capture has priority. Frames go immediately to the recorder; the
analysis runs in its own thread with limited queue. If analysis is too slow,
analysis frames are dropped (counted), never video frames. The queue holds only the
latest image: an older, not yet analyzed frame is discarded to keep analysis (and thus the
suggestion) never seconds behind the screen.
Session starts automatically once the table is stably detected, and ends if
it is not visible for longer.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

from .analyzer import ANALYZER_VERSION, FrameAnalyzer, TableSnapshot
from .capture import Frame, SegmentRecorder
from .cards import CardReader, TemplateStore
from .journal import Session, read_events, sha256_file
from .layout import detect_layout
from .ocr import RegionOcr, default_backend
from .profile import Profile
from .reconstruct import RECONSTRUCT_VERSION, reconstruct
from .stabilize import Stabilizer


def make_analyzer(profile: Profile, templates_dir: Path | None = None, ocr_backend=None) -> FrameAnalyzer:
    ocr = RegionOcr(ocr_backend or default_backend())
    return FrameAnalyzer(profile, ocr, CardReader(profile, ocr, TemplateStore(templates_dir)))


def write_hands(session_root: Path) -> list:
    hands = reconstruct(read_events(session_root))
    data = {"reconstruct_version": RECONSTRUCT_VERSION, "created": time.time(),
            "hands": [h.to_dict() for h in hands]}
    tmp = session_root / "hands.json.tmp"
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    tmp.replace(session_root / "hands.json")
    return hands


@dataclass
class RunStats:
    frames_seen: int = 0
    frames_analyzed: int = 0
    frames_skipped_analysis: int = 0
    frames_source_lost: int = 0
    analysis_errors: int = 0
    event_errors: int = 0          # Errors in reconstruction/bot/bar (analysis continues)
    events: int = 0
    analysis_ms: list[float] = field(default_factory=list)

    def summary(self) -> dict:
        ms = np.array(self.analysis_ms) if self.analysis_ms else np.array([0.0])
        return {"frames_seen": self.frames_seen, "frames_analyzed": self.frames_analyzed,
                "frames_skipped_analysis": self.frames_skipped_analysis,
                "frames_source_lost": self.frames_source_lost, "analysis_errors": self.analysis_errors, "event_errors": self.event_errors,
                "events": self.events,
                "analysis_ms_median": round(float(np.median(ms)), 1),
                "analysis_ms_p95": round(float(np.percentile(ms, 95)), 1)}


def _log_events(session: Session, stab: Stabilizer, snap: TableSnapshot, frame: np.ndarray,
                segment: str | None, stats: RunStats, on_event: Callable | None):
    for ev in stab.update(snap):
        rec = session.write_event(ev, frame, segment=segment)
        stats.events += 1
        if on_event:
            on_event(rec, stab)


def run_offline(source, sessions_dir: Path, profile: Profile, analyzer: FrameAnalyzer,
                on_event: Callable | None = None, progress: Callable | None = None) -> Path:
    desc = source.describe()
    if desc.get("type") == "video":
        desc["sha256"] = sha256_file(Path(desc["path"]))
    session = Session.create(sessions_dir, desc, profile.id, ANALYZER_VERSION, {"mode": "offline"})
    if hasattr(analyzer, "reset"):
        analyzer.reset()
    stab = Stabilizer()
    stats = RunStats()
    last_t = None
    expected_dt = None
    try:
        for fr in source:
            stats.frames_seen += 1
            if not fr.source_ok:
                stats.frames_source_lost += 1
                session.error(fr.note, frame=fr.index)
                continue
            if last_t is not None:
                dt = fr.t_mono - last_t
                expected_dt = dt if expected_dt is None else min(expected_dt, dt)
                if expected_dt and dt > max(1.0, 4 * expected_dt):
                    session.gap(last_t, fr.t_mono, f"Time jump {dt:.2f}s between analyzed frames")
            last_t = fr.t_mono
            t0 = time.perf_counter()
            try:
                snap = analyzer.analyze(fr.image, fr.index, fr.t_mono, fr.t_wall)
            except Exception as e:
                stats.analysis_errors += 1
                if stats.analysis_errors <= 20:
                    session.error(f"Analysis error: {type(e).__name__}: {e}", frame=fr.index)
                continue
            stats.analysis_ms.append((time.perf_counter() - t0) * 1000)
            stats.frames_analyzed += 1
            seg = f"external:{desc.get('path', '')}" if desc.get("type") == "video" else fr.note
            _log_events(session, stab, snap, fr.image, seg, stats, on_event)
            if progress:
                progress(fr, snap, stats)
    finally:
        session.meta["stats"] = stats.summary()
        session.meta["ocr"] = {"calls": analyzer.ocr.calls, "cache_hits": analyzer.ocr.cache_hits}
        session.close()
        write_hands(session.root)
        from .journal import build_index, write_manifest
        build_index(session.root)
        write_manifest(session.root)
    return session.root


class LiveRunner:
    """ Automatic sessions for a live window."""

    def __init__(self, source, sessions_dir: Path, profile: Profile, analyzer: FrameAnalyzer,
                 fps: float, detect_frames: int = 5, stop_after_s: float = 20.0, segment_s: float = 120.0,
                 record_video: bool = True, on_status: Callable | None = None, on_event: Callable | None = None):
        self.source = source
        self.sessions_dir = sessions_dir
        self.profile = profile
        self.analyzer = analyzer
        self.fps = fps
        self.detect_frames = detect_frames
        self.stop_after_s = stop_after_s
        self.segment_s = segment_s
        self.record_video = record_video
        self.on_status = on_status or (lambda s, d: None)
        self.on_event = on_event
        self.status = 'waiting'

    def _set_status(self, s: str, detail: str = ""):
        if s != self.status:
            self.status = s
        self.on_status(s, detail)

    def run(self):
        detected = 0
        session: Session | None = None
        recorder: SegmentRecorder | None = None
        q: queue.Queue = queue.Queue(maxsize=1)      # only the latest image (lowest delay)
        stats = RunStats()
        stab = Stabilizer()
        worker = None
        last_seen_t = None
        lost_since = None
        stop_worker = threading.Event()

        def analysis_loop():
            while not stop_worker.is_set() or not q.empty():
                try:
                    fr, seg = q.get(timeout=0.2)
                except queue.Empty:
                    continue
                t0 = time.perf_counter()
                try:
                    snap = self.analyzer.analyze(fr.image, fr.index, fr.t_mono, fr.t_wall)
                except Exception as e:          # a bad image must never end the capture
                    stats.analysis_errors += 1
                    if stats.analysis_errors <= 20:
                        session.error(f"Analysis error: {type(e).__name__}: {e}", frame=fr.index)
                    continue
                stats.analysis_ms.append((time.perf_counter() - t0) * 1000)
                stats.frames_analyzed += 1
                try:
                    _log_events(session, stab, snap, fr.image, seg, stats, self.on_event)
                except Exception as e:          # Reconstruction, bot or bar must never end the analysis
                    stats.event_errors += 1
                    if stats.event_errors <= 20:
                        try:
                            session.error(f"Event error: {type(e).__name__}: {e}", frame=fr.index)
                        except Exception:
                            pass
                    self._set_status('Analysis delayed', f"error {type(e).__name__}: {e}"[:90])
                    continue
                lag = time.time() - fr.t_wall if fr.t_wall else 0.0
                self._set_status("Aufnahme" if lag < 1.5 else 'Analysis delayed',
                                 f"Frame age {lag:.1f} s, analysis {stats.analysis_ms[-1]:.0f} ms, "
                                 f"skipped {stats.frames_skipped_analysis}"
                                 + (f", errors {stats.event_errors}" if stats.event_errors else ""))

        def end_session(reason: str):
            nonlocal session, recorder, worker, stab, stats
            if session is None:
                return
            stop_worker.set()
            if worker:
                worker.join()
            if recorder:
                recorder.close()
                session.meta["segments"] = recorder.segments
            session.meta["stats"] = stats.summary()
            session.meta["end_reason"] = reason
            session.close()
            write_hands(session.root)
            from .journal import build_index, write_manifest
            build_index(session.root)
            write_manifest(session.root)
            self._set_status('waiting', f"session ended ({reason}): {session.root}")
            session, recorder, worker = None, None, None
            stab, stats = Stabilizer(), RunStats()

        try:
            for fr in self.source:
                if session is not None:
                    stats.frames_seen += 1
                if not fr.source_ok:
                    if session is not None:
                        stats.frames_source_lost += 1
                        if lost_since is None:
                            lost_since = fr.t_mono
                            session.error(fr.note, t=fr.t_mono)
                        if fr.t_mono - lost_since > self.stop_after_s:
                            session.gap(lost_since, fr.t_mono, fr.note)
                            end_session('Source lost')
                            lost_since = None
                    self._set_status('Source lost', fr.note)
                    detected = 0
                    continue
                if session is None:
                    # Preliminary check only in RAM: recording starts only after stable detection
                    lay = detect_layout(fr.image, self.profile)
                    ok = lay.found and len(lay.seats) >= 2
                    detected = detected + 1 if ok else 0
                    self._set_status('waiting' if not ok else 'table detected', f"{detected}/{self.detect_frames}")
                    if detected >= self.detect_frames:
                        session = Session.create(self.sessions_dir, self.source.describe(), self.profile.id,
                                                 ANALYZER_VERSION, {"mode": "live"})
                        self.analyzer.reset()
                        if self.record_video:
                            recorder = SegmentRecorder(session.root / "video", self.fps, self.segment_s)
                        stop_worker.clear()
                        worker = threading.Thread(target=analysis_loop, daemon=True)
                        worker.start()
                        last_seen_t = fr.t_mono
                        self._set_status("Aufnahme", str(session.root))
                    else:
                        continue
                if lost_since is not None:
                    session.gap(lost_since, fr.t_mono, 'Source lost')
                    lost_since = None
                seg = None
                if recorder:
                    try:
                        seg, _ = recorder.write(fr)
                    except Exception as e:  # Memory full, encoder error ...
                        session.error(f"Recording error: {e}", t=fr.t_mono)
                        recorder = None
                try:
                    q.put_nowait((fr, seg))
                except queue.Full:
                    try:
                        q.get_nowait()                  # discard older image, analyze latest
                    except queue.Empty:
                        pass
                    stats.frames_skipped_analysis += 1
                    try:
                        q.put_nowait((fr, seg))
                    except queue.Full:
                        pass
                # Table still visible? Favorable check over the felt
                lay = detect_layout(fr.image, self.profile) if fr.index % max(1, int(self.fps)) == 0 else None
                if lay is not None:
                    if lay.found:
                        last_seen_t = fr.t_mono
                    elif fr.t_mono - last_seen_t > self.stop_after_s:
                        session.gap(last_seen_t, fr.t_mono, 'table no longer visible')
                        end_session('table no longer visible')
                        detected = 0
        except KeyboardInterrupt:
            pass
        finally:
            end_session('ended')

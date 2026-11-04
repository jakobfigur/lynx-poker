"""Bildquellen und segmentierte Aufnahme.

- VideoFileSource: vorhandene Aufnahme (OBS, Xbox Game Bar, ...) Frame fuer Frame
- ImageDirSource: Ordner mit Screenshots
- WindowSource: Live-Aufnahme des Client-Bereichs eines gewaehlten Fensters per
  Bildschirmausschnitt (mss). Es wird nur gelesen, niemals geklickt oder getippt.
  Grenze: Liegt ein anderes Fenster darueber, wird dessen Inhalt aufgenommen; das
  wird ueber das Vordergrundfenster erkannt und als Luecke gemeldet. Echte
  Fensteraufnahme unabhaengig von Ueberdeckung braucht Windows.Graphics.Capture
  (geplanter C#-Adapter).
- Masken: eigene Anzeigen (die Lynx-Leiste) sind normale, fuer jede Bildschirmaufnahme sichtbare Fenster.
  Damit der Collector sie nicht mitliest, wird ihre Flaeche in jedem aufgenommenen Bild durch die
  Umgebungsfarbe ersetzt (apply_masks) und je Bild im Sidecar vermerkt. Was unter der Leiste liegt, ist
  verdeckt; die Leiste gehoert deshalb neben den Tisch, nicht darauf.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np


@dataclass
class Frame:
    index: int
    t_mono: float          # Sekunden, monoton (Video: Position im Video)
    t_wall: float          # Unix-Zeit (Video: geschaetzt aus Dateizeit, falls bekannt)
    image: np.ndarray
    source_ok: bool = True
    note: str = ""
    masked: list = field(default_factory=list)   # ausgeschnittene eigene Anzeigen [[x, y, w, h], ...] im Bild


# ---- Masken fuer eigene Anzeigen ---------------------------------------------

_MASK_WINDOWS: set[int] = set()
_MASK_LOCK = threading.Lock()
MASK_RING_PX = 3            # Breite des Rings um die Maske, aus dem die Fuellfarbe stammt


def register_mask_window(hwnd: int) -> None:
    """Fenster (z. B. die Lynx-Leiste) ab jetzt aus jeder WindowSource-Aufnahme ausschneiden."""
    if hwnd:
        with _MASK_LOCK:
            _MASK_WINDOWS.add(int(hwnd))


def unregister_mask_window(hwnd: int) -> None:
    with _MASK_LOCK:
        _MASK_WINDOWS.discard(int(hwnd))


def mask_windows() -> list[int]:
    with _MASK_LOCK:
        return sorted(_MASK_WINDOWS)


def apply_masks(img: np.ndarray, origin: tuple[int, int], rects: list[tuple[int, int, int, int]],
                ring: int = MASK_RING_PX) -> list[list[int]]:
    """Schneidet Bildschirm-Rechtecke (x, y, w, h) aus `img` aus, dessen linke obere Ecke bei `origin` liegt.

    Jede Flaeche wird mit dem Median eines schmalen Rings um sie herum gefuellt (meist Filzgruen), damit
    Tisch- und Kartenerkennung dort nichts finden. Aendert `img` an Ort und Stelle und gibt die tatsaechlich
    ausgeschnittenen Rechtecke in Bildkoordinaten zurueck (leer, wenn keine Maske im Bild liegt)."""
    h, w = img.shape[:2]
    ox, oy = origin
    done: list[list[int]] = []
    for rx, ry, rw, rh in rects:
        x0, y0 = max(0, rx - ox), max(0, ry - oy)
        x1, y1 = min(w, rx - ox + rw), min(h, ry - oy + rh)
        if x1 <= x0 or y1 <= y0:
            continue
        rx0, ry0, rx1, ry1 = max(0, x0 - ring), max(0, y0 - ring), min(w, x1 + ring), min(h, y1 + ring)
        outer = img[ry0:ry1, rx0:rx1].reshape(-1, img.shape[2] if img.ndim == 3 else 1)
        inside = np.zeros((ry1 - ry0, rx1 - rx0), bool)
        inside[y0 - ry0:y1 - ry0, x0 - rx0:x1 - rx0] = True
        ring_px = outer[~inside.reshape(-1)]
        fill = np.median(ring_px, axis=0).astype(img.dtype) if len(ring_px) else np.full(outer.shape[1], 128, img.dtype)
        img[y0:y1, x0:x1] = fill if img.ndim == 3 else fill[0]
        done.append([int(x0), int(y0), int(x1 - x0), int(y1 - y0)])
    return done


class VideoFileSource:
    def __init__(self, path: str | Path, step_s: float | None = None, start_wall: float | None = None):
        self.path = Path(path)
        self.cap = cv2.VideoCapture(str(self.path))
        if not self.cap.isOpened():
            raise RuntimeError(f"Video nicht lesbar: {self.path}")
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 0.0
        self.count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self.step_s = step_s
        self.start_wall = start_wall if start_wall is not None else self.path.stat().st_mtime - (
            self.count / self.fps if self.fps else 0)

    def describe(self) -> dict:
        return {"type": "video", "path": str(self.path), "fps": self.fps, "frames": self.count,
                "step_s": self.step_s}

    def __iter__(self) -> Iterator[Frame]:
        idx = -1
        next_t = 0.0
        while True:
            ok, img = self.cap.read()
            if not ok:
                break
            idx += 1
            pos_ms = self.cap.get(cv2.CAP_PROP_POS_MSEC)
            t = pos_ms / 1000.0 if pos_ms > 0 or idx == 0 else (idx / self.fps if self.fps else float(idx))
            if self.step_s and t + 1e-6 < next_t:
                continue
            next_t = t + (self.step_s or 0)
            yield Frame(idx, t, self.start_wall + t, img)
        self.cap.release()


class SessionVideoSource:
    """Spielt die Video-Abschnitte einer Live-Sitzung nacheinander ab - mit den ECHTEN Aufnahmezeiten
    je Bild aus segment_XXXX.frames.jsonl (fuer die Nachauswertung, z. B. nach einem Analysefehler)."""

    def __init__(self, session_dir: str | Path):
        self.root = Path(session_dir)
        meta = json.loads((self.root / "session.json").read_text("utf-8"))
        self.segments = [self.root / s["file"] for s in meta.get("segments", [])]
        if not self.segments:
            self.segments = sorted((self.root / "video").glob("segment_*.mp4"))
        if not self.segments:
            raise RuntimeError(f"keine Video-Abschnitte in {self.root}")

    def describe(self) -> dict:
        return {"type": "session-video", "path": str(self.root), "segments": [str(s) for s in self.segments]}

    def __iter__(self) -> Iterator[Frame]:
        for seg in self.segments:
            times = [json.loads(line) for line in seg.with_suffix(".frames.jsonl").read_text("utf-8").splitlines()
                     if line.strip()] if seg.with_suffix(".frames.jsonl").exists() else []
            cap = cv2.VideoCapture(str(seg))
            i = 0
            while True:
                ok, img = cap.read()
                if not ok:
                    break
                if i < len(times):
                    t = times[i]
                    yield Frame(int(t["frame"]), float(t["t_mono"]), float(t["t_wall"]), img, note=seg.name,
                                masked=t.get("masked", []))
                i += 1
            cap.release()


class ImageDirSource:
    def __init__(self, path: str | Path, interval_s: float = 1.0):
        p = Path(path)
        self.files = [p] if p.is_file() else sorted(
            f for f in p.iterdir() if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp"))
        self.interval_s = interval_s

    def describe(self) -> dict:
        return {"type": "images", "files": [str(f) for f in self.files], "interval_s": self.interval_s}

    def __iter__(self) -> Iterator[Frame]:
        for i, f in enumerate(self.files):
            img = cv2.imread(str(f))
            if img is None:
                yield Frame(i, i * self.interval_s, f.stat().st_mtime, np.zeros((10, 10, 3), np.uint8), False,
                            f"unlesbar: {f.name}")
                continue
            yield Frame(i, i * self.interval_s, f.stat().st_mtime, img, note=f.name)


# ---- Fenster (Windows) ----------------------------------------------------

@dataclass
class WindowInfo:
    hwnd: int
    title: str
    rect: tuple[int, int, int, int]  # Client-Bereich in Bildschirmpixeln (x, y, w, h)
    minimized: bool
    foreground: bool


def _user32():
    import ctypes
    from ctypes import wintypes

    u = ctypes.windll.user32
    u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u.IsWindowVisible.argtypes = [wintypes.HWND]
    u.IsIconic.argtypes = [wintypes.HWND]
    u.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    u.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    return u


_dpi_set = False


def _ensure_dpi_aware():
    """Physische Pixel verwenden, sonst passen Fensterkoordinaten bei 125 % Skalierung nicht."""
    global _dpi_set
    if _dpi_set or sys.platform != "win32":
        return
    import ctypes
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass
    _dpi_set = True


def list_windows(title_filter: str = "") -> list[WindowInfo]:
    import ctypes
    from ctypes import wintypes

    _ensure_dpi_aware()
    u = _user32()
    fg = u.GetForegroundWindow()
    out: list[WindowInfo] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        if not u.IsWindowVisible(hwnd):
            return True
        n = u.GetWindowTextLengthW(hwnd)
        if n == 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        u.GetWindowTextW(hwnd, buf, n + 1)
        title = buf.value
        if title_filter.lower() not in title.lower():
            return True
        info = window_info(hwnd, title, fg)
        if info:
            out.append(info)
        return True

    u.EnumWindows(cb, 0)
    return out


def window_info(hwnd: int, title: str = "", fg: int | None = None) -> WindowInfo | None:
    import ctypes
    from ctypes import wintypes

    u = _user32()
    if not u.IsWindow(hwnd):
        return None
    rc = wintypes.RECT()
    if not u.GetClientRect(hwnd, ctypes.byref(rc)):
        return None
    pt = wintypes.POINT(0, 0)
    u.ClientToScreen(hwnd, ctypes.byref(pt))
    if fg is None:
        fg = u.GetForegroundWindow()
    if not title:
        n = u.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        u.GetWindowTextW(hwnd, buf, n + 1)
        title = buf.value
    return WindowInfo(int(hwnd), title, (pt.x, pt.y, rc.right - rc.left, rc.bottom - rc.top),
                      bool(u.IsIconic(hwnd)), int(fg or 0) == int(hwnd))


def window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """Ganzes Fenster in Bildschirmpixeln (x, y, w, h); None, wenn geschlossen, unsichtbar oder minimiert."""
    import ctypes
    from ctypes import wintypes

    if sys.platform != "win32":
        return None
    u = _user32()
    if not u.IsWindow(hwnd) or not u.IsWindowVisible(hwnd) or u.IsIconic(hwnd):
        return None
    rc = wintypes.RECT()
    if not u.GetWindowRect(hwnd, ctypes.byref(rc)):
        return None
    return rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top


class WindowSource:
    """Liest den Client-Bereich eines Fensters mit fester Bildrate."""

    def __init__(self, hwnd: int, fps: float = 10.0, max_seconds: float | None = None,
                 require_foreground: bool = True):
        import mss

        _ensure_dpi_aware()
        self.hwnd = hwnd
        self.fps = fps
        self.max_seconds = max_seconds
        self.require_foreground = require_foreground
        self.sct = mss.mss()
        self.stop_requested = False
        self.on_mask = None          # Rueckruf(rects), sobald zum ersten Mal eine eigene Anzeige im Bild liegt
        self._mask_seen = False

    def describe(self) -> dict:
        info = window_info(self.hwnd)
        return {"type": "window", "hwnd": self.hwnd, "title": info.title if info else None,
                "fps": self.fps, "method": "mss-screen-region",
                "limit": "Ueberdeckung durch andere Fenster wird als Luecke gemeldet, nicht aufgenommen",
                "masks": "eigene Anzeigen (Lynx-Leiste) werden ausgeschnitten und mit der Umgebungsfarbe gefuellt; "
                         "je Bild im Sidecar als 'masked' vermerkt"}

    def __iter__(self) -> Iterator[Frame]:
        period = 1.0 / self.fps
        t0 = time.perf_counter()
        idx = 0
        next_t = t0
        while not self.stop_requested:
            now = time.perf_counter()
            if self.max_seconds and now - t0 > self.max_seconds:
                break
            if now < next_t:
                time.sleep(next_t - now)
            next_t += period
            if time.perf_counter() - next_t > 5 * period:
                next_t = time.perf_counter() + period  # nicht nachholen, Rueckstand wird als Luecke sichtbar
            info = window_info(self.hwnd)
            t = time.perf_counter() - t0
            if info is None:
                yield Frame(idx, t, time.time(), np.zeros((10, 10, 3), np.uint8), False, "Fenster geschlossen")
                break
            if info.minimized or info.rect[2] < 50 or info.rect[3] < 50:
                yield Frame(idx, t, time.time(), np.zeros((10, 10, 3), np.uint8), False, "Fenster minimiert")
                idx += 1
                continue
            if self.require_foreground and not info.foreground:
                yield Frame(idx, t, time.time(), np.zeros((10, 10, 3), np.uint8), False,
                            "Fenster nicht im Vordergrund (moeglicherweise verdeckt)")
                idx += 1
                continue
            x, y, w, h = info.rect
            try:
                shot = self.sct.grab({"left": x, "top": y, "width": w, "height": h})
                img = cv2.cvtColor(np.asarray(shot), cv2.COLOR_BGRA2BGR)
            except Exception as e:            # Bildschirmsperre, Monitorwechsel: Luecke statt Programmende
                yield Frame(idx, t, time.time(), np.zeros((10, 10, 3), np.uint8), False,
                            f"Aufnahmefehler: {type(e).__name__}: {e}"[:120])
                idx += 1
                continue
            owned = mask_windows()
            masked = apply_masks(img, (x, y), [r for r in map(window_rect, owned) if r]) if owned else []
            if masked and not self._mask_seen:
                self._mask_seen = True
                if self.on_mask:
                    try:
                        self.on_mask(masked)
                    except Exception:
                        pass
            yield Frame(idx, t, time.time(), img, masked=masked)
            idx += 1


# ---- Segmentierte Aufnahme --------------------------------------------------

class SegmentRecorder:
    """Schreibt Frames in kurze Videosegmente plus Zeitstempel-Sidecar (JSONL).

    Segmente werden bei Groessenwechsel oder nach `segment_s` Sekunden geschlossen,
    damit ein Absturz hoechstens das laufende Segment betrifft.
    """

    def __init__(self, video_dir: Path, fps: float, segment_s: float = 120.0, codec: str = "mp4v"):
        self.dir = video_dir
        self.fps = fps
        self.segment_s = segment_s
        self.codec = codec
        self.writer = None
        self.sidecar = None
        self.seg_index = 0
        self.seg_t0 = 0.0
        self.seg_size = None
        self.segments: list[dict] = []
        self.frames_in_segment = 0

    @property
    def current_segment(self) -> str | None:
        return self.segments[-1]["file"] if self.segments and self.writer is not None else None

    def _open(self, size: tuple[int, int], t: float):
        self.close()
        self.seg_index += 1
        name = f"segment_{self.seg_index:04d}.mp4"
        path = self.dir / name
        self.writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*self.codec), self.fps, size)
        if not self.writer.isOpened():
            raise RuntimeError(f"Videoencoder '{self.codec}' nicht verfuegbar")
        self.sidecar = open(self.dir / f"segment_{self.seg_index:04d}.frames.jsonl", "w", encoding="utf-8")
        self.seg_t0 = t
        self.seg_size = size
        self.frames_in_segment = 0
        self.segments.append({"file": f"video/{name}", "t_start": t, "t_end": None, "frames": 0,
                              "width": size[0], "height": size[1], "fps_nominal": self.fps, "codec": self.codec})

    def write(self, frame: Frame) -> tuple[str, int]:
        h, w = frame.image.shape[:2]
        if self.writer is None or self.seg_size != (w, h) or frame.t_mono - self.seg_t0 >= self.segment_s:
            self._open((w, h), frame.t_mono)
        self.writer.write(frame.image)
        rec = {"i": self.frames_in_segment, "frame": frame.index,
               "t_mono": round(frame.t_mono, 4), "t_wall": round(frame.t_wall, 4)}
        if frame.masked:
            rec["masked"] = frame.masked          # Flaeche eigener Anzeigen, im Video bereits ausgeschnitten
        self.sidecar.write(json.dumps(rec) + "\n")
        self.frames_in_segment += 1
        seg = self.segments[-1]
        seg["frames"] = self.frames_in_segment
        seg["t_end"] = frame.t_mono
        return seg["file"], self.frames_in_segment - 1

    def close(self):
        if self.writer is not None:
            self.writer.release()
            self.writer = None
        if self.sidecar is not None:
            self.sidecar.close()
            self.sidecar = None

"""Systemhilfen: Standby waehrend langer Laeufe verhindern."""

from __future__ import annotations

import sys
from contextlib import contextmanager

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002


@contextmanager
def keep_awake(enabled: bool = True):
    """Verhindert Leerlauf-Standby, solange der Block laeuft (Windows SetThreadExecutionState).
    Auf Geraeten mit 'Modern Standby' fuehrt das Abschalten des Bildschirms zum Standby,
    deshalb wird auch der Bildschirm wach gehalten. Danach gilt wieder die normale Einstellung."""
    if not enabled or sys.platform != "win32":
        yield False
        return
    import ctypes
    k = ctypes.windll.kernel32
    ok = k.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED) != 0
    try:
        yield ok
    finally:
        k.SetThreadExecutionState(ES_CONTINUOUS)

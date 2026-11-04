""" System utilities: prevent standby during long runs."""

from __future__ import annotations

import sys
from contextlib import contextmanager

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002


@contextmanager
def keep_awake(enabled: bool = True):
    """ Prevents idle standby as long as the block is running (Windows SetThreadExecutionState).
    On devices with 'Modern Standby', turning off the screen leads to standby,
    so the screen is also kept awake. Afterwards, normal settings apply again."""
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

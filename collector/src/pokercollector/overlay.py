""" Lynx bar: small floating field above the taskbar (next to clock and battery) with the suggestion.

- Always on top, never takes focus (the browser window remains active), has no taskbar button.
- Is a normal window visible in every screen capture. To prevent the collector from reading it,
  it registers its window during capture (capture.register_mask_window): WindowSource cuts out the area
  from each image and fills it with the ambient color. What lies beneath it is not seen by the collector,
  so it belongs next to the table (default: bottom right above the taskbar). Until 2.11.2026 the bar excluded
  itself from all captures via WDA_EXCLUDEFROMCAPTURE; replaced for the release.
- It's your turn: bar lights up in the color of the action, short tone (fold low, check/call medium,
  raise high, all-in double). Otherwise pale with the last suggestion.
- Dragging with the mouse moves it (position is remembered), right-click: toggle tone, reset position.

Pure display: no click, no key, nothing goes to the browser.
Tk runs in its own thread; updates come via a queue (thread-safe).
"""

from __future__ import annotations

import ctypes
import json
import queue
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path

OVERLAY_VERSION = "leiste-2"
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE, WS_EX_TOPMOST = 0x80, 0x08000000, 0x8

COLORS = {          # background active, font
    "fold": ("#8a2b2b", "#ffffff"),
    "check": ("#2b6a3a", "#ffffff"),
    "call": ("#2b6a3a", "#ffffff"),
    "raise": ("#b8860b", "#111111"),
    "allin": ("#c0392b", "#ffffff"),
    "none": ("#3a3a3a", "#dddddd"),
}
IDLE_BG, IDLE_FG, DIM_FG = "#1e1e1e", "#9a9a9a", "#6f6f6f"
STATUS_DOT = {"ok": "#3ddc84", "warn": "#f5c542", "err": "#ff5252", "off": "#555555"}
TONES = {"fold": [(392, 90)], "check": [(587, 90)], "call": [(587, 90)], "raise": [(880, 90)],
         "allin": [(880, 80), (1175, 120)]}


@dataclass
class Advice:
    """ What the bar displays."""
    kind: str                         # fold | check | call | raise | allin | none
    text: str                         # large line, e.g. "RAISE to 360  (3.5 BB)"
    detail: str = ""                  # small line: cards, pot, alternatives
    alternatives: list[tuple[str, float]] = field(default_factory=list)


def advice_from(sug, obs, agent=None) -> Advice:
    """ Suggestion (action) + observation -> display. Amounts in chips and big blinds."""
    if sug is None:
        return Advice("none", 'no recommendation', 'own cards not reliably recognized')
    bb = obs.big_blind or 1

    def in_bb(x):
        return f"{x / bb:.1f} BB"

    if sug.kind == "fold":
        kind, text = ("check", "CHECK") if obs.can_check else ("fold", "FOLD")
    elif sug.kind == "check" or (sug.kind == "call" and obs.to_call == 0):
        kind, text = "check", "CHECK"
    elif sug.kind == "call":
        kind, text = "call", f"CALL {obs.to_call}  ({in_bb(obs.to_call)})"
    else:
        amt = sug.amount or 0
        if obs.max_raise_to is not None and amt >= obs.max_raise_to:
            kind, text = "allin", f"ALL-IN {amt}  ({in_bb(amt)})"
        else:
            verb = "BET" if obs.current_bet == 0 else 'RAISE to'
            kind, text = "raise", f"{verb} {amt}  ({in_bb(amt)})"
    alts = alternatives(agent, obs) if agent is not None else []
    cards = " ".join(obs.hole_cards) + (" | " + " ".join(obs.board) if obs.board else "")
    warn = [w for k, w in WARNINGS.items() if k in (obs.uncertain or [])]
    detail = ("⚠ " + ", ".join(warn) + ' - suggestion uncertain   ' if warn else "") + f"{cards}   Pot {obs.pot}"
    if obs.to_call:
        detail += f", to call {obs.to_call}"
    if alts:
        detail += "   " + "  ".join(f"{n} {p:.0%}" for n, p in alts[:3])
    return Advice(kind, text, detail, alts)


ACTION_LABELS = {"fold": "Fold", "call": "Call", "raise_half": '½ Pot', "raise_pot": "Pot", "raise_2pot": '2× Pot',
          "allin": "All-in", "raise_third": '⅓ Pot', "raise_min": "Min-Raise"}
WARNINGS = {'Pot unknown or inconsistent': 'Pot not recognized',
            'Amount to call estimated from bets': 'Call amount estimated'}


def alternatives(agent, obs=None) -> list[tuple[str, float]]:
    """ Probabilities of actions (largest first), if the bot guesses them."""
    last = getattr(agent, "last", None)
    if isinstance(last, dict) and "probs" in last:                 # Search (husearch)
        out = []
        for (k, amt), p in zip(last["actions"], last["probs"]):
            out.append((k.capitalize() if amt is None else f"{amt}", float(p)))
    else:
        probs = getattr(agent, "last_probs", None)
        if probs is None:
            return []
        from .ai.features import action_names
        names = dict(ACTION_LABELS)
        if obs is not None and obs.can_check:
            names["call"] = "Check"
        out = [(names.get(n, n), float(p)) for n, p in zip(action_names(len(probs)), probs)]
    return sorted((x for x in out if x[1] >= 0.02), key=lambda x: -x[1])


def settings_path() -> Path:
    from .ai.nn_agent import rl_root
    return rl_root().parent / "live" / "leiste.json"


def _work_area() -> tuple[int, int, int, int]:
    """ Screen area without taskbar (left, top, right, bottom)."""
    class RECT(ctypes.Structure):
        _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long), ("r", ctypes.c_long), ("b", ctypes.c_long)]
    r = RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0)        # SPI_GETWORKAREA
    return r.l, r.t, r.r, r.b


def _beep(kind: str):
    import winsound
    for f, ms in TONES.get(kind, []):
        winsound.Beep(f, ms)


class Leiste:
    W, H = 430, 64

    def __init__(self, sound: bool = True, title: str = "Lynx"):
        self.q: queue.Queue = queue.Queue()
        self.sound = sound
        self.title = title
        self.ready = threading.Event()
        self.hwnd = 0
        self.masked_in_capture = False      # Area is cut from collector captures
        self._thread = threading.Thread(target=self._run, name="lynx-leiste", daemon=True)

    # --- from outside (any thread) ---------------------------------------------------------------
    def start(self) -> "Leiste":
        self._thread.start()
        self.ready.wait(5)
        return self

    def show(self, adv: Advice, beep: bool = True):
        """ New suggestion: it's your turn."""
        self.q.put(("advice", adv, beep))

    def idle(self):
        """ Not (anymore) your turn: bar pale, last suggestion remains readable."""
        self.q.put(("idle",))

    def status(self, level: str, text: str):
        """ Status point: ok | warn | err | off, with short text (tooltip-like bottom right)."""
        self.q.put(("status", level, text))

    def close(self):
        self.q.put(("quit",))

    # --- Tk thread --------------------------------------------------------------------------------------
    def _run(self):
        import tkinter as tk
        root = tk.Tk()
        self.root = root
        root.title(self.title)
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.94)
        root.configure(bg=IDLE_BG)
        x, y = self._load_pos()
        root.geometry(f"{self.W}x{self.H}+{x}+{y}")
        self.big = tk.Label(root, text='Lynx waiting for the table', font=('Segoe UI Semibold', 17), bg=IDLE_BG,
                            fg=IDLE_FG, anchor="w")
        self.big.place(x=12, y=4, width=self.W - 40, height=32)
        self.small = tk.Label(root, text="", font=('Segoe UI', 9), bg=IDLE_BG, fg=DIM_FG, anchor="w")
        self.small.place(x=12, y=38, width=self.W - 24, height=20)
        self.dot = tk.Canvas(root, width=12, height=12, bg=IDLE_BG, highlightthickness=0)
        self.dot.place(x=self.W - 22, y=10)
        self.dot_id = self.dot.create_oval(1, 1, 11, 11, fill=STATUS_DOT["off"], outline="")
        self.menu = tk.Menu(root, tearoff=0)
        self.menu.add_command(label='Sound off', command=self._toggle_sound)
        self.menu.add_command(label='Reset position', command=self._reset_pos)
        for w in (root, self.big, self.small, self.dot):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag)
            w.bind("<ButtonRelease-1>", self._drag_end)
            w.bind("<Button-3>", self._popup)
        self._label_sound()
        root.update_idletasks()
        self._style_window()
        self.ready.set()
        root.after(40, self._pump)
        root.mainloop()
        # Free Tk objects here in the Tk thread; if the main thread cleans them only on exit, Tcl aborts with
        # "Tcl_AsyncDelete: async handler deleted by the wrong thread" (exit code 3).
        import gc
        self.root = self.big = self.small = self.dot = self.menu = None
        del root
        gc.collect()

    def _style_window(self):
        if sys.platform != "win32":
            return
        u = ctypes.windll.user32
        hwnd = u.GetParent(self.root.winfo_id()) or self.root.winfo_id()
        self.hwnd = hwnd
        ex = u.GetWindowLongW(hwnd, GWL_EXSTYLE)
        u.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TOPMOST)
        from .capture import register_mask_window
        register_mask_window(hwnd)
        self.masked_in_capture = True

    def _paint(self, bg: str, fg: str, small_fg: str):
        for w in (self.root, self.big, self.small, self.dot):
            w.configure(bg=bg)
        self.big.configure(fg=fg)
        self.small.configure(fg=small_fg)

    def _pump(self):
        try:
            while True:
                msg = self.q.get_nowait()
                if msg[0] == "advice":
                    adv, beep = msg[1], msg[2]
                    bg, fg = COLORS.get(adv.kind, COLORS["none"])
                    self.big.configure(text=adv.text)
                    self.small.configure(text=adv.detail)
                    self._paint(bg, fg, fg)
                    if beep and self.sound and adv.kind in TONES:
                        threading.Thread(target=_beep, args=(adv.kind,), daemon=True).start()
                elif msg[0] == "idle":
                    self._paint(IDLE_BG, IDLE_FG, DIM_FG)
                elif msg[0] == "status":
                    self.dot.itemconfigure(self.dot_id, fill=STATUS_DOT.get(msg[1], STATUS_DOT["off"]))
                elif msg[0] == "quit":
                    from .capture import unregister_mask_window
                    unregister_mask_window(self.hwnd)
                    self.root.destroy()
                    return
        except queue.Empty:
            pass
        self.root.after(40, self._pump)

    # Move / menu
    def _drag_start(self, e):
        self._dx, self._dy = e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y()

    def _drag(self, e):
        self.root.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")

    def _drag_end(self, _e):
        self._save_pos(self.root.winfo_x(), self.root.winfo_y())

    def _popup(self, e):
        self.menu.tk_popup(e.x_root, e.y_root)

    def _toggle_sound(self):
        self.sound = not self.sound
        self._label_sound()

    def _label_sound(self):
        self.menu.entryconfigure(0, label='Sound off' if self.sound else 'Sound on')

    def _default_pos(self) -> tuple[int, int]:
        try:
            _, _, r, b = _work_area()
        except Exception:
            r, b = self.root.winfo_screenwidth(), self.root.winfo_screenheight() - 48
        return r - self.W - 12, b - self.H - 8

    def _reset_pos(self):
        x, y = self._default_pos()
        self.root.geometry(f"+{x}+{y}")
        self._save_pos(x, y)

    def _load_pos(self) -> tuple[int, int]:
        try:
            d = json.loads(settings_path().read_text("utf-8"))
            return int(d["x"]), int(d["y"])
        except Exception:
            return self._default_pos()

    def _save_pos(self, x: int, y: int):
        try:
            p = settings_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"x": x, "y": y}), "utf-8")
        except OSError:
            pass

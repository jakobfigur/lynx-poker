""" Parser for OCR texts of the PokerTH web interface.

OCR typically confuses $/S, 0/O, 1/l/I. The parsers only normalize
within expected patterns and report when they had to correct.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_DIGIT_FIXES = str.maketrans({"O": "0", "o": "0", "D": "0", "Q": "0", "l": "1", "I": "1", "|": "1", "i": "1",
                              "S": "5", "s": "5", "B": "8", "Z": "2", "z": "2"})


@dataclass(frozen=True)
class Parsed:
    value: Any
    ok: bool
    corrected: bool = False
    note: str = ""


def _fix_digits(s: str) -> tuple[str, bool]:
    fixed = s.translate(_DIGIT_FIXES)
    return fixed, fixed != s


def parse_money(text: str | None) -> Parsed:
    """'$3 000', 'S3 000', '$O', '$2.980', '3000' -> int chips."""
    if not text:
        return Parsed(None, False, note="leer")
    t = text.strip().replace(" ", " ").replace(" ", " ")
    corrected = False
    # Currency sign at the start: $ or read as S. '5' is deliberately not
    # interpreted as '$' because that could falsify real amounts.
    m = re.match(r"^\s*([$Ss§])\s*(.*)$", t)
    if m:
        if m.group(1) != "$":
            corrected = True
        body = m.group(2)
    else:
        body = t
    # Thousand separators (space, dot, comma, apostrophe) removed if groups of 3
    body = body.strip()
    if not body:
        return Parsed(None, False, corrected, 'no amount')
    if re.search(r"[kKmM]$", body):
        mult = 1000 if body[-1] in "kK" else 1_000_000
        num, c2 = _fix_digits(body[:-1].replace(",", ".").replace(" ", ""))
        try:
            return Parsed(int(round(float(num) * mult)), True, corrected or c2, "k/M-Suffix")
        except ValueError:
            return Parsed(None, False, corrected, f"unreadable: {text!r}")
    groups = re.split(r"[ .,'’]", body)
    groups = [g for g in groups if g != ""]
    if len(groups) > 1 and not all(len(g) == 3 for g in groups[1:]):
        return Parsed(None, False, corrected, f"unklare Gruppierung: {text!r}")
    digits, c2 = _fix_digits("".join(groups))
    if not digits.isdigit():
        return Parsed(None, False, corrected, f"unreadable: {text!r}")
    return Parsed(int(digits), True, corrected or c2)


_MONEY_IN_TEXT = re.compile(r"[$S§]\s*[0-9OolI](?:[0-9OolI]|[ .,'](?=[0-9OolI]{3}))*")


def extract_money(text: str | None) -> Parsed:
    """ Finds the first amount with currency sign in a line ('• $20' -> 20).
    Without currency sign a pure digits line is read as uncertain amount."""
    if not text:
        return Parsed(None, False, note="leer")
    m = _MONEY_IN_TEXT.search(text)
    if m:
        p = parse_money(m.group(0))
        if p.ok and m.start() > 0:
            return Parsed(p.value, True, p.corrected, (p.note + ' text before amount ignored').strip())
        return p
    if re.fullmatch(r"\s*[0-9][0-9 .,]*\s*", text):
        p = parse_money(text)
        if p.ok:
            return Parsed(p.value, True, True, 'read without currency symbol')
    return Parsed(None, False, note=f"no amount: {text!r}")


_STREETS = {
    "preflop": "preflop",
    "flop": "flop",
    "turn": "turn",
    "river": "river",
    "showdown": "showdown",
}


def parse_street(text: str | None) -> Parsed:
    if not text:
        return Parsed(None, False, note="leer")
    key = re.sub(r"[^a-z]", "", text.lower())
    if key in _STREETS:
        return Parsed(_STREETS[key], True)
    for k, v in _STREETS.items():
        if k in key:
            return Parsed(v, True, True, f"Teiltreffer in {text!r}")
    return Parsed(None, False, note=f"unknown street: {text!r}")


def parse_game_hand(text: str | None) -> Parsed:
    """'Game: 1 Hand: 12' -> (1, 12)."""
    if not text:
        return Parsed(None, False, note="leer")
    m = re.search(r"spiel\W*([0-9OolI]+).*?hand\W*([0-9OolI]+)", text, re.IGNORECASE)
    if not m:
        return Parsed(None, False, note=f"no pattern: {text!r}")
    g, c1 = _fix_digits(m.group(1))
    h, c2 = _fix_digits(m.group(2))
    return Parsed((int(g), int(h)), True, c1 or c2)


def parse_blinds(text: str | None) -> Parsed:
    """'10/20 ↑8' (OCR often '10/20+8') -> {'sb':10,'bb':20,'extra':'8'}."""
    if not text:
        return Parsed(None, False, note="leer")
    m = re.search(r"([0-9OolI]+)\s*/\s*([0-9OolI]+)(.*)$", text)
    if not m:
        return Parsed(None, False, note=f"no pattern: {text!r}")
    sb, c1 = _fix_digits(m.group(1))
    bb, c2 = _fix_digits(m.group(2))
    extra = re.sub(r"^[\s+↑^tT]+", "", m.group(3)).strip() or None
    return Parsed({"sb": int(sb), "bb": int(bb), "extra": extra}, True, c1 or c2)


def parse_labeled_money(text: str | None, label: str) -> Parsed:
    """'Bets: $30' with label='eins' -> 30."""
    if not text:
        return Parsed(None, False, note="leer")
    norm = text.lower().replace("ä", "a")
    if label not in norm:
        return Parsed(None, False, note=f"label {label!r} missing")
    _, _, rest = text.partition(":")
    return parse_money(rest if rest else text)


_ACTION_WORDS = [
    ("allin", "allin"),
    ("all-in", "allin"),
    ("fold", "fold"),
    ("check", "check"),
    ("call", "call"),
    ("bet", "bet"),
    ("raise", "raise"),
    ("smallblind", "post_sb"),
    ("bigblind", "post_bb"),
]


def _edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def parse_action_label(text: str | None) -> Parsed:
    if not text:
        return Parsed(None, False, note="leer")
    key = re.sub(r"[^a-z]", "", text.lower())
    for word, action in _ACTION_WORDS:
        w = re.sub(r"[^a-z]", "", word)
        if key == w or key.startswith(w):
            return Parsed(action, True)
    # OCR misread like 'Cali' -> 'call' (only words of 4+ characters, max 1 error)
    for word, action in _ACTION_WORDS:
        w = re.sub(r"[^a-z]", "", word)
        if len(w) >= 4 and len(key) == len(w) and _edit_distance(key, w) <= 1:
            return Parsed(action, True, True, f"unscharf: {text!r}")
    return Parsed(None, False, note=f"no action: {text!r}")


def parse_button(text: str | None) -> Parsed:
    """ Action button 'Call $20' / 'Raise $40' / 'Check' / 'Bet $20' -> (action, amount|None)."""
    if not text:
        return Parsed(None, False, note="leer")
    act = parse_action_label(text.split()[0] if text.split() else text)
    if not act.ok:
        return Parsed(None, False, note=act.note)
    amount = None
    m = re.search(r"[$S]\s*[0-9OolI][0-9OolI .,]*", text)
    if m:
        p = parse_money(m.group(0))
        amount = p.value if p.ok else None
    return Parsed((act.value, amount), True)

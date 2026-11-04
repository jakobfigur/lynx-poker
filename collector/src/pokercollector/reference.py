"""Import des PokerTH-Handverlaufs als unabhaengige Referenz.

Wird NIE von der visuellen Erfassung gelesen, nur von `compare`.

Bekanntes Format (PokerTH-Desktop-Log, SQLite, '.pdb'):
  Game(UniqueGameID, GameID, ...), Player(UniqueGameID, Seat, Player),
  Hand(UniqueGameID, HandID, Dealer_Seat, Sb_Amount, Sb_Seat, Bb_Amount, Bb_Seat,
       Seat_<n>_Cash, Seat_<n>_Card_1, Seat_<n>_Card_2, ..., BoardCard_1..5),
  Action(ActionID, UniqueGameID, HandID, BeRo, Player, Action, Amount)
Kartencodierung angenommen 0..51 = Rang 2..A je Farbe in Reihenfolge d, h, s, c.

ACHTUNG: Schema und Kartencodierung sind aus der PokerTH-Quelle uebernommen und
NICHT an einem echten Export des Web-Clients geprueft. `inspect` zeigt das echte
Schema; bei Abweichung hier die Zuordnung anpassen.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path

REFERENCE_PARSER_VERSION = "pokerth-sqlite-1 (ungeprueft)"
CARD_SUIT_ORDER = "dhsc"
RANKS = "23456789TJQKA"
STREETS = ["preflop", "flop", "turn", "river"]

ACTION_MAP = {
    "posts small blind": "post_sb",
    "posts big blind": "post_bb",
    "folds": "fold",
    "checks": "check",
    "calls": "call",
    "bets": "bet",
    "is all in with": "allin",
    "raises": "raise",
    "wins": "collect",
    "wins (side pot)": "collect",
    "shows": "show",
    "has": "show",
    "starts as dealer": "dealer",
    "sits out": "sitout",
    "wins game": "wins_game",
    "has left the game": "leave",
}


class ReferenceFormatError(Exception):
    pass


def decode_card(v) -> str | None:
    if v is None or v == "" or (isinstance(v, int) and v < 0):
        return None
    if isinstance(v, str):
        s = v.strip()
        if len(s) == 2 and s[0].upper() in RANKS + "1" and s[1].lower() in "shdc":
            return s[0].upper() + s[1].lower()
        if not s.lstrip("-").isdigit():
            return None
        v = int(s)
    if not 0 <= v < 52:
        return None
    return RANKS[v % 13] + CARD_SUIT_ORDER[v // 13]


@dataclass
class RefAction:
    street: str
    seat: int
    name: str | None
    type: str
    amount: int | None
    raw: str


@dataclass
class RefHand:
    game_id: int | None
    hand_id: int
    dealer_seat: int | None
    sb_seat: int | None
    bb_seat: int | None
    blinds: list[int | None]
    seats: dict[int, dict] = field(default_factory=dict)       # seat -> name, cash, cards
    board: list[str | None] = field(default_factory=list)
    actions: list[RefAction] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def inspect(path: Path) -> dict[str, list[str]]:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return {t: [c[1] for c in con.execute(f'PRAGMA table_info("{t}")')] for t in tables}
    finally:
        con.close()


def _find(schema: dict[str, list[str]], name: str) -> str:
    for t in schema:
        if t.lower() == name.lower():
            return t
    raise ReferenceFormatError(f"Tabelle '{name}' fehlt. Vorhanden: {schema}")


def _col(cols: list[str], *names: str) -> str | None:
    low = {c.lower(): c for c in cols}
    for n in names:
        if n.lower() in low:
            return low[n.lower()]
    return None


def load_pokerth_log(path: Path) -> list[RefHand]:
    path = Path(path)
    try:
        schema = inspect(path)
    except sqlite3.DatabaseError as e:
        raise ReferenceFormatError(f"keine SQLite-Datei: {e}") from e
    t_hand, t_action = _find(schema, "Hand"), _find(schema, "Action")
    t_player = _find(schema, "Player") if any(t.lower() == "player" for t in schema) else None
    hc, ac = schema[t_hand], schema[t_action]
    game_col = _col(hc, "UniqueGameID", "GameID")
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        names: dict[tuple, str] = {}
        if t_player:
            pc = schema[t_player]
            pg = _col(pc, "UniqueGameID", "GameID")
            for r in con.execute(f'SELECT * FROM "{t_player}"'):
                names[(r[pg] if pg else None, int(r[_col(pc, "Seat")]))] = r[_col(pc, "Player", "Name")]
        hands: dict[tuple, RefHand] = {}
        for r in con.execute(f'SELECT * FROM "{t_hand}"'):
            g = r[game_col] if game_col else None
            hid = int(r[_col(hc, "HandID")])
            h = RefHand(
                game_id=g, hand_id=hid,
                dealer_seat=r[_col(hc, "Dealer_Seat")] if _col(hc, "Dealer_Seat") else None,
                sb_seat=r[_col(hc, "Sb_Seat")] if _col(hc, "Sb_Seat") else None,
                bb_seat=r[_col(hc, "Bb_Seat")] if _col(hc, "Bb_Seat") else None,
                blinds=[r[_col(hc, "Sb_Amount")] if _col(hc, "Sb_Amount") else None,
                        r[_col(hc, "Bb_Amount")] if _col(hc, "Bb_Amount") else None],
            )
            for n in range(1, 11):
                cash = _col(hc, f"Seat_{n}_Cash")
                if cash is None or r[cash] is None:
                    continue
                c1, c2 = _col(hc, f"Seat_{n}_Card_1"), _col(hc, f"Seat_{n}_Card_2")
                cards = [decode_card(r[c1]) if c1 else None, decode_card(r[c2]) if c2 else None]
                h.seats[n] = {"name": names.get((g, n)), "cash": r[cash],
                              "cards": cards if all(cards) else None}
            h.board = [decode_card(r[c]) if (c := _col(hc, f"BoardCard_{i}")) else None for i in range(1, 6)]
            hands[(g, hid)] = h
        order_col = _col(ac, "ActionID")
        q = f'SELECT * FROM "{t_action}"' + (f' ORDER BY "{order_col}"' if order_col else "")
        a_game = _col(ac, "UniqueGameID", "GameID")
        for r in con.execute(q):
            key = (r[a_game] if a_game else None, int(r[_col(ac, "HandID")]))
            h = hands.get(key)
            if h is None:
                continue
            bero = r[_col(ac, "BeRo")] if _col(ac, "BeRo") else 0
            street = STREETS[bero] if isinstance(bero, int) and 0 <= bero < 4 else "showdown"
            raw = str(r[_col(ac, "Action")] or "")
            typ = ACTION_MAP.get(raw.strip().lower(), "other:" + raw)
            seat = int(r[_col(ac, "Player", "Seat")])
            amt = r[_col(ac, "Amount")] if _col(ac, "Amount") else None
            h.actions.append(RefAction(street, seat, names.get((key[0], seat)), typ, amt, raw))
        return [hands[k] for k in sorted(hands, key=lambda k: (str(k[0]), k[1]))]
    finally:
        con.close()


# ---- Text-Log des PokerTH-Web-Clients ("Log-File for PokerTH web ...", .txt) --------------------
# Geprueft an einem echten Export (26.10.2026). Betraege wie im Log: 'bets $X' = Einsatz AUF X
# (Strassensumme), 'calls $X' = zusaetzlich gezahlt, 'is all in with $X' = Strassensumme.

TEXT_PARSER_VERSION = "pokerth-web-text-1"
_HAND_RE = re.compile(r"^-+ Game: (\d+) \| Hand: (\d+) -+$")
_SEAT_RE = re.compile(r"^Seat (\d+): (.+) \(\$(\d+)\)$")
_LEVEL_RE = re.compile(r"^BLIND LEVEL: \$(\d+) / \$(\d+)$")
_BLINDS_RE = re.compile(r"^BLINDS: (.+) \(\$(\d+)\), (.+) \(\$(\d+)\)$")
_STREET_RE = re.compile(r"^(PREFLOP|FLOP|TURN|RIVER)(?: \[board cards (.+)\])?$")
_TEXT_ACTIONS = [
    (re.compile(r"^folds\.$"), "fold"), (re.compile(r"^checks\.$"), "check"),
    (re.compile(r"^calls \$(\d+)\.$"), "call"), (re.compile(r"^bets \$(\d+)\.$"), "bet"),
    (re.compile(r"^raises \$(\d+)\.$"), "raise"), (re.compile(r"^is all in with \$(\d+)\.$"), "allin"),
    (re.compile(r"^shows \[ ?(\S\S),(\S\S)\].*$"), "show"), (re.compile(r"^wins \$(\d+)( \(side pot\))?$"), "collect"),
    (re.compile(r"^sits out$"), "sitout"), (re.compile(r"^starts as dealer\.$"), "dealer"),
    (re.compile(r"^has left the game\.?$"), "leave"), (re.compile(r"^wins game.*$"), "wins_game"),
]


def _norm_text_card(c: str) -> str | None:
    c = c.strip()
    if len(c) == 3 and c.startswith("10"):
        c = "T" + c[2]
    return c if len(c) == 2 and c[0] in RANKS and c[1] in "shdc" else None


def load_pokerth_text_log(path: Path) -> list[RefHand]:
    hands: list[RefHand] = []
    cur: RefHand | None = None
    street = "preflop"
    names: dict[str, int] = {}
    for raw in Path(path).read_text("utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _HAND_RE.match(line)
        if m:
            cur = RefHand(int(m.group(1)), int(m.group(2)), None, None, None, [None, None])
            hands.append(cur)
            street, names = "preflop", {}
            continue
        if cur is None:
            continue
        if (m := _SEAT_RE.match(line)):
            seat = int(m.group(1))
            cur.seats[seat] = {"name": m.group(2), "cash": int(m.group(3)), "cards": None}
            names[m.group(2)] = seat
            continue
        if (m := _LEVEL_RE.match(line)):
            cur.blinds = [int(m.group(1)), int(m.group(2))]
            continue
        if (m := _BLINDS_RE.match(line)):
            cur.sb_seat, cur.bb_seat = names.get(m.group(1)), names.get(m.group(3))
            cur.actions.append(RefAction("preflop", cur.sb_seat, m.group(1), "post_sb", int(m.group(2)), line))
            cur.actions.append(RefAction("preflop", cur.bb_seat, m.group(3), "post_bb", int(m.group(4)), line))
            continue
        if (m := _STREET_RE.match(line)):
            street = m.group(1).lower()
            if m.group(2):
                cur.board = [_norm_text_card(c) for c in m.group(2).split(",")]
            continue
        who = next((n for n in sorted(names, key=len, reverse=True) if line.startswith(n + " ")), None)
        if who is None:
            continue
        rest = line[len(who) + 1:]
        for rx, kind in _TEXT_ACTIONS:
            m = rx.match(rest)
            if not m:
                continue
            seat = names[who]
            if kind == "dealer":
                cur.dealer_seat = seat
            elif kind == "show":
                cur.seats[seat]["cards"] = [_norm_text_card(m.group(1)), _norm_text_card(m.group(2))]
                cur.actions.append(RefAction(street, seat, who, "show", None, line))
            else:
                amt = int(m.group(1)) if m.groups() and m.group(1) and m.group(1).isdigit() else None
                cur.actions.append(RefAction(street, seat, who, kind, amt, line))
            break
    return hands


def load_reference(path: Path) -> list[RefHand]:
    """Erkennt das Format: SQLite (.pdb) oder Text-Log des Web-Clients."""
    path = Path(path)
    head = path.read_bytes()[:64]
    if head.startswith(b"SQLite format"):
        return load_pokerth_log(path)
    if b"Log-File for PokerTH" in head or path.suffix.lower() == ".txt":
        return load_pokerth_text_log(path)
    return load_pokerth_log(path)

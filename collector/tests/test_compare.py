import sqlite3

from helpers import EventStream, standard_hand, table

from pokercollector.compare import compare
from pokercollector.reconstruct import reconstruct
from pokercollector.reference import decode_card, load_pokerth_log

NAMES = ["jakob", "Calling Carl", "Lucky Luna", "Re-raise Ronald"]


def make_log(path, hero_cards=(30, 20), raise_amount=60):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE Player(UniqueGameID INTEGER, Seat INTEGER, Player TEXT)")
    cols = ["UniqueGameID", "HandID", "Dealer_Seat", "Sb_Amount", "Sb_Seat", "Bb_Amount", "Bb_Seat"]
    for n in range(1, 11):
        cols += [f"Seat_{n}_Cash", f"Seat_{n}_Card_1", f"Seat_{n}_Card_2"]
    cols += [f"BoardCard_{i}" for i in range(1, 6)]
    con.execute(f"CREATE TABLE Hand({', '.join(cols)})")
    con.execute("CREATE TABLE Action(ActionID INTEGER, UniqueGameID INTEGER, HandID INTEGER, BeRo INTEGER, "
                "Player INTEGER, Action TEXT, Amount INTEGER)")
    for i, n in enumerate(NAMES):
        con.execute("INSERT INTO Player VALUES (1, ?, ?)", (i + 1, n))
    row = {c: None for c in cols}
    row.update(UniqueGameID=1, HandID=1, Dealer_Seat=1, Sb_Amount=10, Sb_Seat=2, Bb_Amount=20, Bb_Seat=3,
               BoardCard_1=25, BoardCard_2=44, BoardCard_3=0, BoardCard_4=-1, BoardCard_5=-1)
    cards = {1: hero_cards, 2: (51, 50), 3: (49, 48), 4: (47, 46)}
    for s in range(1, 5):
        row[f"Seat_{s}_Cash"] = 3000
        row[f"Seat_{s}_Card_1"], row[f"Seat_{s}_Card_2"] = cards[s]
    con.execute(f"INSERT INTO Hand VALUES ({', '.join('?' * len(cols))})", [row[c] for c in cols])
    acts = [(0, 2, "posts small blind", 10), (0, 3, "posts big blind", 20), (0, 4, "folds", 0),
            (0, 1, "calls", 20), (0, 2, "bets", raise_amount), (0, 3, "folds", 0), (0, 1, "calls", 60),
            (1, 2, "checks", 0), (1, 1, "bets", 100), (1, 2, "folds", 0), (1, 1, "wins", 240)]
    for i, (bero, seat, act, amt) in enumerate(acts):
        con.execute("INSERT INTO Action VALUES (?, 1, 1, ?, ?, ?, ?)", (i, bero, seat, act, amt))
    con.commit()
    con.close()


def visual_hands():
    es = table(EventStream(), names=("jakob", "Calling Carl", "Lucky Luna", "Re-raise Ro..."))
    standard_hand(es)
    es.at(10.5, seat__0__cards=["6s", "9h"])
    es.at(12.0, info__game_hand=[1, 2])
    return [h.to_dict() for h in reconstruct(es.events)][:1]


def test_decode_card():
    assert decode_card(0) == "2d" and decode_card(12) == "Ad" and decode_card(25) == "Ah"
    assert decode_card(30) == "6s" and decode_card(51) == "Ac" and decode_card(-1) is None


def test_compare_perfect_match(tmp_path):
    db = tmp_path / "log.pdb"
    make_log(db)
    ref = load_pokerth_log(db)
    res = compare(visual_hands(), ref).to_dict()
    assert res["seat_map"] == {"0": 1, "1": 2, "2": 3, "3": 4}
    f = res["fields"]
    assert f["action"]["match"] == 10 and f["action"]["missing"] == 0 and f["action"]["extra"] == 0
    assert f["action_amount"]["mismatch"] == 0
    assert f["hero_cards"]["match"] == 1
    assert f["shown_cards"]["not_visible"] == 3 and f["shown_cards"]["mismatch"] == 0
    assert f["board"]["match"] == 3
    assert f["dealer"]["match"] == 1 and f["winner"]["match"] == 1
    assert res["amount_semantics"] == {"referenz=gesamt_auf": 6}


def test_compare_detects_errors(tmp_path):
    db = tmp_path / "log.pdb"
    make_log(db, hero_cards=(31, 20), raise_amount=80)
    res = compare(visual_hands(), load_pokerth_log(db)).to_dict()
    f = res["fields"]
    assert f["hero_cards"]["mismatch"] == 1
    assert f["action_amount"]["mismatch"] == 1
    issues = " ".join(res["details"][0]["issues"])
    assert "Cards seat 0" in issues and "reference 80" in issues

from pokercollector import parse


def test_money_variants():
    assert parse.parse_money('$3 000').value == 3000
    assert parse.parse_money("$3000").value == 3000
    p = parse.parse_money('S3 000')
    assert p.value == 3000 and p.corrected
    assert parse.parse_money("$O").value == 0
    assert parse.parse_money('$2 980').value == 2980
    assert parse.parse_money("$1.5k").value == 1500
    assert not parse.parse_money('$3 00').ok          # wrong grouping
    assert not parse.parse_money("Falcon").ok


def test_money_does_not_eat_leading_five():
    assert parse.parse_money("5000").value == 5000


def test_extract_money_ignores_chip_icon():
    assert parse.extract_money('• $20').value == 20
    assert parse.extract_money('e $10').value == 10
    assert parse.extract_money("9$10").value == 10
    p = parse.extract_money("000")
    assert p.ok and 'without currency symbol' in p.note


def test_info_row():
    assert parse.parse_game_hand('game: 1 hand: 12').value == (1, 12)
    assert parse.parse_game_hand('Game: 1 Hand: 0').value == (1, 0)
    assert parse.parse_street('Pre - Flop').value == "preflop"
    assert parse.parse_street("River").value == "river"
    b = parse.parse_blinds("10/20+8").value
    assert b == {"sb": 10, "bb": 20, "extra": "8"}
    assert parse.parse_labeled_money('Bets: $30', "eins").value == 30
    assert parse.parse_labeled_money('Total: $0', "gesamt").value == 0


def test_actions():
    assert parse.parse_action_label("Fold").value == "fold"
    assert parse.parse_action_label("All-In").value == "allin"
    assert parse.parse_action_label("Cali").value == "call"
    assert not parse.parse_action_label("Pot").ok
    assert parse.parse_button('Call $20').value == ("call", 20)
    assert parse.parse_button("Check").value == ("check", None)

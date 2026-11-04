import itertools

import pytest

from pokercollector.ai.agents import make_agent
from pokercollector.ai.engine import Hand
from pokercollector.ai.human import HumanAgent, QuitGame
from pokercollector.ai.league import League, display, rate_plackett_luce
from pokercollector.ai.play import load_sessions, play_cash, play_tournament_session, stats_markdown
from pokercollector.ai.pushfold import decision_ev
from pokercollector.ai.tournament import BlindSchedule, TournamentConfig

FAST = TournamentConfig(start_stack=400, blinds=BlindSchedule(10, 20, hands_per_level=5))


def test_plackett_luce_basics():
    r = [(25.0, 25 / 3)] * 4
    new = rate_plackett_luce(r, [1, 2, 3, 4])
    mus = [m for m, _ in new]
    assert mus == sorted(mus, reverse=True)                  # winner increases most
    assert all(s < 25 / 3 for _, s in new)                   # uncertainty decreases
    assert sum(m - 25 for m in mus) == pytest.approx(0, abs=1e-6)
    tie = rate_plackett_luce([(25.0, 8.0), (25.0, 8.0)], [1, 1])
    assert tie[0][0] == pytest.approx(tie[1][0])
    upset = rate_plackett_luce([(20.0, 2.0), (30.0, 2.0)], [1, 2])
    assert upset[0][0] > 20 and upset[1][0] < 30
    assert display(25) == 1500


def test_custom_style_spec():
    a = make_agent("tag?bluff=0.3:tagx")
    assert a.name == "tagx" and a.style.bluff == 0.3
    with pytest.raises(ValueError):
        make_agent("tag?foo=1")
    with pytest.raises(ValueError):
        make_agent("random?bluff=1")


def test_league_rounds_benchmark_and_report(tmp_path):
    lg = League(tmp_path)
    for n, s in [("tag", "tag"), ("rock", "rock"), ("rnd", "random"), ("tag-v2", "tag?bluff=0.3")]:
        lg.add(n, s)
    games = lg.run(3, table=4, config=FAST, seed=1)
    assert len(games) == 3 and all(len(g["participants"]) == 4 for g in games)
    assert all(lg.players[n].games == 3 for n in lg.players)
    assert (tmp_path / "games.jsonl").exists()
    hist = lg.history()
    assert len(hist["tag"]) == 3
    assert "pushfold" in games[0] and "tag" in games[0]["pushfold"]
    b = lg.benchmark("tag", hands=10, tournaments=1, config=FAST)
    assert b["cash"]["hands"] == 60 and "roi_pct" in b["sng"]
    md = lg.leaderboard_markdown()
    assert "tag-v2" in md and "Benchmark" in md
    assert "<svg" in lg.report_html()
    lg2 = League(tmp_path)                                   # loads from disk
    assert lg2.players["tag"].games == 3


def test_decision_ev():
    aa = decision_ev(["As", "Ah"], {"kind": "first_in", "behind": 1, "stack_bb": 10}, "fold")
    assert aa["best"] == "push" and aa["ev_loss"] > 0.5
    ok = decision_ev(["As", "Ah"], {"kind": "first_in", "behind": 1, "stack_bb": 10}, "push")
    assert ok["ev_loss"] == 0
    bad = decision_ev(["7c", "2d"], {"kind": "facing_push", "behind": 1, "index": 0, "stack_bb": 15}, "call")
    assert bad["best"] == "fold" and bad["ev_loss"] > 0


def scripted(answers):
    it = iter(answers)

    def inp(prompt=""):
        try:
            return next(it)
        except StopIteration:
            raise QuitGame()
    return inp


def test_human_parse():
    h = Hand([1000] * 3, 0, 10, 20, seed=1)
    o = h.observation(0)
    hu = HumanAgent(output_fn=lambda *a: None)
    assert hu.parse("f", o).kind == "fold"
    assert hu.parse("c", o).kind == "call"
    assert hu.parse("r", o).amount == 40
    assert hu.parse("r 100", o).amount == 100
    assert hu.parse("a", o).amount == 1000
    assert hu.parse("p", o).amount == 20 + 30 + 20
    with pytest.raises(ValueError):
        hu.parse("r 5", o)
    with pytest.raises(ValueError):
        hu.parse("blabla", o)
    with pytest.raises(ValueError):
        hu.parse("k", o)                                      # Check with open bet
    with pytest.raises(QuitGame):
        hu.parse("q", o)


def test_cash_session_with_scripted_human(tmp_path):
    out = []
    human = HumanAgent("du", input_fn=scripted(["x", "c"] + ["c", "f", "r", "c"] * 30), output_fn=out.append,
                       coach=True)
    bots = [make_agent("tag:tag", 1), make_agent("station:station", 2)]
    path = play_cash(human, bots, tmp_path, hands=15, seed=3)
    sessions = load_sessions(tmp_path)
    assert len(sessions) == 1 and sessions[0]["end"]["hands"] >= 1
    md = stats_markdown(sessions, "du")
    assert "**du**" in md and "tag" in md
    text = "\n".join(map(str, out))
    assert "unknown input" in text and "Your cards" in text
    # Visibility: Opponent cards appear only at 'show' (Showdown)
    assert "Your result" in text


def test_tournament_session_human_always_folds(tmp_path):
    human = HumanAgent("du", input_fn=lambda p="": "f", output_fn=lambda *a: None)
    bots = [make_agent("tag:tag", 1), make_agent("rock:rock", 2)]
    path, res = play_tournament_session(human, bots, tmp_path, FAST, seed=5)
    assert res is not None and res.finished
    assert res.places[0] >= 2                                 # those who only fold/check do not win
    s = load_sessions(tmp_path)[0]
    assert s["end"]["places"][0] == res.places[0]           # Session file matches result

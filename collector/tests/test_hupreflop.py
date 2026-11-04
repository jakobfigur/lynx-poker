import random

import numpy as np

from pokercollector.ai import hupreflop as hp
from pokercollector.ai.agents import make_agent
from pokercollector.ai.engine import Hand
from pokercollector.ai.observation import Action
from pokercollector.ai.pushfold import IDX


def test_gleichgewicht_konvergiert_und_ist_plausibel():
    root, _ = hp.solve(100, iterations=300)
    assert hp.exploitability(root) < 0.01                 # < 1 BB je 100 Haende
    a = hp._avg(root)
    labels = [k for k, _ in root.labels]
    fold, raise_ = labels.index("fold"), labels.index("raise")
    assert a[fold, IDX["72o"]] > 0.8                      # Muell weg
    assert a[fold, IDX["AA"]] < 0.01 and a[raise_:, IDX["KK"]].sum() + a[fold + 1, IDX["KK"]] > 0.99


def test_tatsaechliche_groesse_wird_eingefuegt():
    root, path = hp.build(200, [("raise", 2.0)])
    assert len(path) == 2                                 # Wurzel + aktuelle Entscheidung (BB)
    assert ("raise", 2.0) in root.labels
    assert path[-1].player == 1 and path[-1].labels[0] == ("fold", 1.0)


def test_decide_auf_echter_lage():
    h = Hand([20000, 20000], 0, 50, 100, deck=None, hand_id="p")    # Button = SB = Platz 0
    h.apply(0, Action.raise_to(300))                     # SB eroeffnet auf 3 BB
    obs = h.observation(1)
    assert hp.history_path(obs) == [("raise", 3.0)]
    out = hp.decide(obs, random.Random(1))
    assert out is not None
    (kind, x), labels, p = out
    assert abs(p.sum() - 1) < 1e-6 and ("raise", 3.0) not in labels


def test_suchbot_nutzt_preflop_heads_up():
    # Preflop-Loeser seit 30.10. nicht mehr Standard (Nachtdiagnose: -25 Punkte im Turnierformat), explizit zuschalten
    a = make_agent("hus?bp=lynx-3-300&iters=10&iters_river=20&streets=preflop,turn,river:hus", 1)
    h = Hand([4000, 4000], 0, 50, 100, seed=5, hand_id="q")
    obs = h.observation(h.to_act)
    act = a.act(obs)
    assert a.last is not None and abs(float(np.sum(a.last["probs"])) - 1) < 1e-6
    assert act.kind in ("fold", "call", "check", "raise")

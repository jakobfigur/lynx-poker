"""Fold-Modell fuer das Menschenmodell (H11 Schritt 2b): was Normalspieler weglegen, und mit welchen Karten sie bleiben.

Problem: human-1 (humandata/train_human) kennt nur Entscheidungen mit gezeigten Karten - und wer foldet, zeigt
nicht. Als Gegnermodell in der Suche waren seine Ranges darum zu breit (Messung H: -20 auf mensch480).

Loesung aus den kartenfreien Zeilen (humandata.extract_public, 55 Mio Entscheidungen inkl. Folds):
  f(s)    = P(fold | oeffentlicher Zustand s)                      (alle Entscheidungen, Logit-MLP)
  g(c|s)  = P(Handklasse c | s, weitergespielt)                    (Zeilen mit Karten, Softmax ueber 169 Klassen)
Bayes-Rest: P(weiter | c, s) = g(c|s) * (1 - f(s)) / P(c|s). P(c|s) ist unsere aktuelle Range-Schaetzung fuer
diesen Spieler (bpranges fuehrt sie mit; am ersten Preflop-Zug gleichverteilt, dann exakt). Der Faktor wird auf
[0, 1] begrenzt und je Kombination angewendet, BEVOR human-1 die beobachtete Aktion bewertet:
  w[c] *= P(weiter | c, s) * P(a | c, s, weiter).
Verzerrung: g ist aus Showdown-Haenden (spaetere Folder fehlen) - River fast unverzerrt, Flop/Turn unterschaetzen
aufgegebene Bluffs. Alles kartenfrei und ohne Personenbezug.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np

from .observation import Observation
from .tables import all_classes

HUMANFOLD_VERSION = "humanfold-1"
N_CLASSES = 169
PUBLIC_DIM = 20
_CLASSES = all_classes()


def _log1p(x):
    return np.log1p(np.maximum(x, 0.0))


def public_vector_arrays(street, position, n_players, n_live, pot_bb, to_call_bb, stack_bb, raises_street,
                         raises_pre, facing, aggressor, board_paired, board_suited, board_high) -> np.ndarray:
    """Kartenfreier Zustand als float32[n, PUBLIC_DIM]; identisch fuer Training (Spalten der public-Scherben)
    und Einsatz (aus einer Observation, public_vector)."""
    street = np.asarray(street, np.int64)
    n = street.shape[0]
    x = np.zeros((n, PUBLIC_DIM), np.float32)
    x[np.arange(n), np.clip(street, 0, 3)] = 1.0                                   # 0-3 Strasse
    pot = np.maximum(np.asarray(pot_bb, np.float32), 0.5)
    stack = np.maximum(np.asarray(stack_bb, np.float32), 0.0)
    to_call = np.maximum(np.asarray(to_call_bb, np.float32), 0.0)
    live = np.maximum(np.asarray(n_live, np.float32), 2.0)
    x[:, 4] = np.asarray(position, np.float32) / np.maximum(np.asarray(n_players, np.float32) - 1, 1)
    x[:, 5] = np.asarray(n_players, np.float32) / 10.0
    x[:, 6] = live / 10.0
    x[:, 7] = _log1p(pot) / 4.0
    x[:, 8] = _log1p(to_call) / 4.0
    x[:, 9] = to_call / (pot + to_call + 1e-6)
    x[:, 10] = _log1p(stack) / 5.0
    x[:, 11] = np.minimum(stack / pot, 20.0) / 20.0
    x[:, 12] = np.minimum(np.asarray(raises_street, np.float32), 4.0) / 4.0
    x[:, 13] = np.minimum(np.asarray(raises_pre, np.float32), 4.0) / 4.0
    x[:, 14] = np.asarray(facing, np.float32)
    x[:, 15] = np.asarray(aggressor, np.float32)
    x[:, 16] = np.asarray(board_paired, np.float32)
    x[:, 17] = np.asarray(board_suited, np.float32) / 5.0
    x[:, 18] = np.maximum(np.asarray(board_high, np.float32), 0.0) / 12.0
    x[:, 19] = (live == 2).astype(np.float32)
    return x


def public_vector(obs: Observation) -> np.ndarray:
    """Kartenfreier Zustand des handelnden Spielers aus einer Observation (float32[PUBLIC_DIM])."""
    from ..poker import RANKS
    n = obs.num_seats
    live = [s for s in range(n) if obs.in_hand[s] and not obs.folded[s]]
    st_acts = obs.street_actions()
    aggressors = [a.seat for a in obs.history if a.kind in ("bet", "raise")]
    b = obs.board
    ranks = [c[0] for c in b]
    suits = [c[1] for c in b]
    bb = obs.big_blind or 1
    street = {"preflop": 0, "flop": 1, "turn": 2, "river": 3}[obs.street]
    return public_vector_arrays(
        [street], [obs.position()], [sum(obs.in_hand)], [len(live)], [obs.pot / bb], [obs.to_call / bb],
        [obs.my_stack / bb], [sum(1 for a in st_acts if a.kind in ("bet", "raise"))],
        [sum(1 for a in obs.street_actions("preflop") if a.kind in ("bet", "raise"))], [int(obs.to_call > 0)],
        [int(bool(aggressors) and aggressors[-1] == obs.seat)], [int(len(set(ranks)) < len(ranks)) if b else 0],
        [max((suits.count(s) for s in set(suits)), default=0)], [max((RANKS.index(r) for r in ranks), default=-1)])[0]


def _forward(w: dict, prefix: str, x: np.ndarray) -> np.ndarray:
    h = np.maximum(x @ w[prefix + "w1"].T + w[prefix + "b1"], 0)
    h = np.maximum(h @ w[prefix + "w2"].T + w[prefix + "b2"], 0)
    return h @ w[prefix + "w3"].T + w[prefix + "b3"]


class HumanFold:
    """Geladenes Fold-Modell: p_fold(x), p_class(x) und der Weiterspiel-Faktor je Kombination."""

    def __init__(self, w: dict):
        self.w = w
        from .bpranges import COMBO_CLASS
        self.combo_class = COMBO_CLASS
        self.class_count = np.bincount(COMBO_CLASS, minlength=N_CLASSES).astype(np.float64)

    @classmethod
    def load(cls, path: Path | str) -> "HumanFold":
        z = np.load(path, allow_pickle=False)
        return cls({k: z[k] for k in z.files if k != "meta"})

    def p_fold(self, x: np.ndarray) -> np.ndarray:
        x = np.atleast_2d(x).astype(np.float32)
        return 1.0 / (1.0 + np.exp(-_forward(self.w, "f_", x)[:, 0]))

    def p_class(self, x: np.ndarray) -> np.ndarray:
        x = np.atleast_2d(x).astype(np.float32)
        lg = _forward(self.w, "g_", x)
        lg -= lg.max(1, keepdims=True)
        p = np.exp(lg)
        return p / p.sum(1, keepdims=True)

    def continue_factor(self, obs: Observation, range_weights: np.ndarray) -> np.ndarray:
        """P(weiter | Kombination, Zustand) in [0, 1] je der 1326 Kombinationen: Bayes-Rest aus g, f und der
        aktuellen Range des Spielers (unnormiert erlaubt)."""
        x = public_vector(obs)[None]
        f = float(self.p_fold(x)[0])
        g = self.p_class(x)[0].astype(np.float64)
        w = np.maximum(range_weights.astype(np.float64), 0.0)
        tot = w.sum()
        if tot <= 0:
            return np.ones(len(w))
        w = w / tot
        cls_w = np.bincount(self.combo_class, weights=w, minlength=N_CLASSES)        # P(c | s) je Klasse
        factor_cls = np.where(cls_w > 1e-12, g * (1.0 - f) / np.maximum(cls_w, 1e-12), 0.0)
        factor_cls = np.clip(factor_cls, 0.0, 1.0)
        return factor_cls[self.combo_class]


def train(rows_dir: Path | str, out: Path | str, max_rows: int = 4_000_000, epochs: int = 3, hidden_f: int = 64,
          hidden_g: int = 256, batch: int = 8192, lr: float = 2e-3, seed: int = 0, log=print,
          max_shards: int | None = None) -> dict:
    """Beide Teilmodelle aus den public-Scherben trainieren (torch, CPU reicht), als .npz speichern.
    max_shards begrenzt den Speicher (55 Mio Zeilen x 18 Felder waeren ~4 GB)."""
    import torch
    from torch import nn
    from .humandata import load_public
    torch.manual_seed(seed)
    d = load_public(rows_dir, max_shards)
    n_all = len(d["kind"])
    rng = np.random.default_rng(seed)
    X = public_vector_arrays(d["street"], d["position"], d["n_players"], d["n_live"], d["pot_bb"], d["to_call_bb"],
                             d["stack_bb"], d["raises_street"], d["raises_pre"], d["facing"], d["aggressor"],
                             d["board_paired"], d["board_suited"], d["board_high"])
    y_fold = (d["kind"] == 0).astype(np.float32)
    known = d["hole_class"] >= 0
    idx_f = rng.permutation(n_all)[:max_rows]
    idx_g = np.nonzero(known)[0]
    rng.shuffle(idx_g)
    hold_f, tr_f = idx_f[: len(idx_f) // 50], idx_f[len(idx_f) // 50:]
    hold_g, tr_g = idx_g[: len(idx_g) // 50], idx_g[len(idx_g) // 50:]
    log(f"{n_all} Zeilen; Fold-Modell {len(tr_f)} Training, Klassenmodell {len(tr_g)} Training (mit Karten)")

    def mlp(h, out_dim):
        return nn.Sequential(nn.Linear(PUBLIC_DIM, h), nn.ReLU(), nn.Linear(h, h), nn.ReLU(), nn.Linear(h, out_dim))

    Xt = torch.from_numpy(X)
    t0 = time.time()
    hist = {}

    def fit(net, idx_tr, idx_ho, target, loss_fn, name, metric):
        opt = torch.optim.Adam(net.parameters(), lr=lr)
        for ep in range(epochs):
            order = rng.permutation(idx_tr)
            for i in range(0, len(order), batch):
                j = torch.from_numpy(order[i:i + batch])
                loss = loss_fn(net(Xt[j]), target[j])
                opt.zero_grad()
                loss.backward()
                opt.step()
            with torch.no_grad():
                jh = torch.from_numpy(idx_ho)
                lh = loss_fn(net(Xt[jh]), target[jh]).item()
                m = metric(net(Xt[jh]), target[jh])
            hist.setdefault(name, []).append({"epoch": ep + 1, "holdout_loss": lh, "metric": m})
            log(f"  {name} Epoche {ep + 1}/{epochs}: Hold-out {lh:.4f}, {m}, {time.time() - t0:.0f}s")

    net_f = mlp(hidden_f, 1)
    yf = torch.from_numpy(y_fold)
    fit(net_f, tr_f, hold_f, yf, lambda o, t: nn.functional.binary_cross_entropy_with_logits(o[:, 0], t), "fold",
        lambda o, t: f"Fold-Rate {float(t.mean()):.3f} vorhergesagt {float(torch.sigmoid(o[:, 0]).mean()):.3f}")
    net_g = mlp(hidden_g, N_CLASSES)
    yg = torch.from_numpy(d["hole_class"].astype(np.int64))
    base_nll = -math.log(1.0 / N_CLASSES)
    fit(net_g, tr_g, hold_g, yg, lambda o, t: nn.functional.cross_entropy(o, t), "klasse",
        lambda o, t: f"NLL gegen gleichverteilt {base_nll:.3f}")
    w = {}
    for prefix, net in (("f_", net_f), ("g_", net_g)):
        sd = {k: v.detach().cpu().numpy().astype(np.float32) for k, v in net.state_dict().items()}
        for i, name in ((0, "1"), (2, "2"), (4, "3")):
            w[prefix + "w" + name] = sd[f"{i}.weight"]
            w[prefix + "b" + name] = sd[f"{i}.bias"]
    meta = {"version": HUMANFOLD_VERSION, "rows": int(n_all), "rows_fold": int(len(tr_f)), "rows_class": int(len(tr_g)),
            "epochs": epochs, "hidden_f": hidden_f, "hidden_g": hidden_g, "hist": hist, "t": time.strftime("%Y-%m-%d %H:%M:%S")}
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez(out, **w, meta=json.dumps(meta))
    return {"out": str(out), **{k: v for k, v in meta.items() if k != "hist"}, "hist": hist}

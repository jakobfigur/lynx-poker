"""The learning bot: small neural network (features -> action probabilities + value).

Network: N_FEATURES -> hidden -> hidden (ReLU) -> policy (6 logits) and value (1 number).
Learned with PyTorch (rl.py); played with a numpy copy of the weights. This is faster for
individual decisions and runs in many processes without thread contention.

League specification: 'nn?run=<run>@<checkpoint>' (without @ = newest), run is under data\\rl\\.
Play is mixed (sampling according to probabilities), with randomness derived from the situation
like other bots: same situation -> same decision (duplicate-fair).
greedy=1 always picks the most probable action.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from .agents import BaseAgent
from .features import FEATURE_SIZES, FEATURES_VERSION, N_ACTIONS, action_mask, features, to_action
from .observation import Action, Observation

NN_VERSION = "nn-mlp-1"
_CACHE: dict[tuple, dict] = {}


def rl_root() -> Path:
    env = os.environ.get("POKERCOLLECTOR_DATA")
    base = Path(env) if env else Path(__file__).resolve().parents[4] / "data"
    return base / "rl"


def build_net(hidden: int = 128, version: str = FEATURES_VERSION, n_actions: int = N_ACTIONS):
    """Network for one feature version (input size from FEATURE_SIZES) and number of actions (6 or 8)."""
    import torch.nn as nn
    n_in = FEATURE_SIZES[version]

    class PolicyNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.body = nn.Sequential(nn.Linear(n_in, hidden), nn.ReLU(), nn.Linear(hidden, hidden), nn.ReLU())
            self.pi = nn.Linear(hidden, n_actions)
            self.v = nn.Linear(hidden, 1)

        def forward(self, x, mask):
            h = self.body(x)
            logits = self.pi(h).masked_fill(~mask, -1e9)
            return logits, self.v(h).squeeze(-1)

    net = PolicyNet()
    net.features_version = version
    return net


def numpy_weights(net) -> dict:
    sd = {k: v.detach().cpu().numpy().astype(np.float32) for k, v in net.state_dict().items()}
    return {"w1": sd["body.0.weight"], "b1": sd["body.0.bias"], "w2": sd["body.2.weight"], "b2": sd["body.2.bias"],
            "wp": sd["pi.weight"], "bp": sd["pi.bias"], "wv": sd["v.weight"], "bv": sd["v.bias"],
            "features": getattr(net, "features_version", "feat-1"), "n_actions": int(sd["pi.bias"].shape[0])}


def forward_np(w: dict, x: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, float]:
    """Probabilities (masked) and value for ONE situation."""
    h = np.maximum(w["w1"] @ x + w["b1"], 0)
    h = np.maximum(w["w2"] @ h + w["b2"], 0)
    logits = w["wp"] @ h + w["bp"]
    logits = np.where(mask, logits, -1e9)
    logits -= logits.max()
    p = np.exp(logits) * mask
    p /= p.sum()
    return p, float((w["wv"] @ h + w["bv"])[0])


def sharpen(p: np.ndarray, temp: float) -> np.ndarray:
    """Sharpen probabilities with temperature temp: p^(1/temp), renormalized (temp 1 = unchanged,
    temp -> 0 = greedy). Intermediate between mixed play (low exploitation loss) and greedy (no spread loss)."""
    if temp <= 0:
        out = np.zeros_like(p)
        out[int(np.argmax(p))] = 1.0
        return out
    with np.errstate(divide="ignore"):
        q = np.where(p > 0, np.exp(np.log(np.where(p > 0, p, 1.0)) / temp), 0.0)
    s = q.sum()
    return q / s if s > 0 else p


NEW_ACTION_TEMPLATE = {6: 2, 7: 2}      # new actions start as copy of 'raise_half' ...
NEW_ACTION_OFFSET = -2.0                # ... with smaller initial probability (logit -2)


def widen_net(net, version: str, n_actions: int | None = None):
    """Same network for a larger feature version and/or more actions. New inputs
    get weight 0 (plays initially as before); new actions start as copy of raise 1/2 pot
    with logit -2, thus rare, and are discovered in training."""
    import torch
    old = getattr(net, "features_version", "feat-1")
    if FEATURE_SIZES[version] < FEATURE_SIZES[old]:
        raise ValueError(f"{version} is less than {old}")
    old_na = net.pi.out_features
    n_actions = n_actions or old_na
    if n_actions < old_na:
        raise ValueError('fewer actions than before')
    new = build_net(net.pi.in_features, version, n_actions)
    sd = net.state_dict()
    with torch.no_grad():
        w = torch.zeros(new.body[0].weight.shape)
        w[:, :sd["body.0.weight"].shape[1]] = sd["body.0.weight"]
        sd = {**sd, "body.0.weight": w}
        if n_actions > old_na:
            wp, bp = sd["pi.weight"], sd["pi.bias"]
            rows = [wp] + [wp[NEW_ACTION_TEMPLATE[i]:NEW_ACTION_TEMPLATE[i] + 1] for i in range(old_na, n_actions)]
            bias = [bp] + [bp[NEW_ACTION_TEMPLATE[i]:NEW_ACTION_TEMPLATE[i] + 1] + NEW_ACTION_OFFSET
                           for i in range(old_na, n_actions)]
            sd = {**sd, "pi.weight": torch.cat(rows), "pi.bias": torch.cat(bias)}
    new.load_state_dict(sd)
    return new


def save_checkpoint(path: Path, net, meta: dict, extra: dict | None = None):
    import torch
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    version = getattr(net, "features_version", "feat-1")
    torch.save({"nn_version": NN_VERSION, "features": version, "n_features": FEATURE_SIZES[version],
                "hidden": net.pi.in_features, "n_actions": net.pi.out_features, "state_dict": net.state_dict(),
                "meta": meta, **(extra or {})}, tmp)
    tmp.replace(path)


def load_checkpoint(path: Path) -> dict:
    import torch
    ck = torch.load(path, map_location="cpu", weights_only=True)
    v = ck.get("features")
    if v not in FEATURE_SIZES or ck.get("n_features") != FEATURE_SIZES[v]:
        raise ValueError(f"{path}: unknown feature version {v} ({ck.get('n_features')} features)")
    return ck


def net_from_checkpoint(ck: dict):
    net = build_net(ck["hidden"], ck["features"], ck.get("n_actions", N_ACTIONS))
    net.load_state_dict(ck["state_dict"])
    return net


def checkpoint_path(run: str, ckpt: str | int = "latest") -> Path:
    d = rl_root() / run
    if str(ckpt) == "latest":
        cands = sorted(d.glob("ckpt_*.pt"))
        if not cands:
            raise FileNotFoundError(f"no checkpoint in {d}")
        return cands[-1]
    return d / f"ckpt_{int(ckpt):06d}.pt"


def load_weights(run: str, ckpt: str | int = "latest") -> dict:
    p = checkpoint_path(run, ckpt)
    key = (str(p), p.stat().st_mtime)
    if key not in _CACHE:
        _CACHE[key] = numpy_weights(net_from_checkpoint(load_checkpoint(p)))
    return _CACHE[key]


class NNAgent(BaseAgent):
    name = "nn"

    def __init__(self, weights: dict, seed: int = 0, greedy: bool = False, name: str | None = None,
                 fold_model=None, temp: float = 1.0):
        super().__init__(seed, name)
        self.w = weights
        self.greedy = greedy
        self.temp = float(temp)               # Temperature: p ~ p^(1/T); 1 = as learned, <1 sharper, ->0 greedy
        self.last_probs = None
        self.last_p_fold = None
        self.tracker = None
        self.fold_model = fold_model          # humanfold.HumanFold: networks without fold data (human-1) discard this
        if weights.get("features") == "feat-3":
            from .opponents import OpponentTracker
            self.tracker = OpponentTracker()

    def p_fold_hand(self, obs: Observation) -> float:
        """P(Fold | state, own hand) from fold model: 1 minus continuation factor of own
        combination in uniformly distributed range (Bayesian remainder from g(c|s), f(s)); 0 without open bet."""
        if self.fold_model is None or obs.to_call <= 0:
            return 0.0
        from .bpranges import COMBO_CARDS
        from .ranges import dead_mask
        fac = self.fold_model.continue_factor(obs, (~dead_mask(obs.board)).astype(np.float64))
        mine = set(obs.hole_cards)
        k = next(i for i, cs in enumerate(COMBO_CARDS) if set(cs) == mine)
        return float(1.0 - fac[k])

    def hand_over(self, rec, seat):
        if self.tracker is not None:
            self.tracker.update(rec, seat)

    def inputs(self, obs: Observation) -> tuple[np.ndarray, np.ndarray]:
        """Features and action mask exactly as used by act() (for teacher data, teacher.py)."""
        na = self.w.get("n_actions", N_ACTIONS)
        opp = self.tracker.features(obs) if self.tracker is not None else None
        return features(obs, version=self.w.get("features", "feat-1"), opp=opp), action_mask(obs, na)

    def act(self, obs: Observation) -> Action:
        if len(obs.hole_cards) != 2:
            return self.passive(obs)
        na = self.w.get("n_actions", N_ACTIONS)
        x, mask = self.inputs(obs)
        p, _ = forward_np(self.w, x, mask)
        self.last_probs = p
        rng = self.rng(obs)
        if self.fold_model is not None:
            self.last_p_fold = self.p_fold_hand(obs)
            if self.last_p_fold > 0 and rng.random() < self.last_p_fold:
                return Action.fold()
            if obs.to_call > 0 and p[0] > 0:          #Subtract network fold: continue means call/raise
                p = p * mask
                p[0] = 0.0
                p = p / p.sum() if p.sum() > 0 else np.where(mask, 1.0 / mask.sum(), 0.0)
        if self.greedy:
            idx = int(np.argmax(p))
        else:
            if self.temp != 1.0:
                p = sharpen(p, self.temp)
            u = rng.random()
            idx = int(min(np.searchsorted(np.cumsum(p), u, side="right"), na - 1))
            while not mask[idx]:          # Rounding at the edge
                idx -= 1
        return to_action(obs, idx)


def make_nn_agent(params: str, seed: int = 0) -> NNAgent:
    kv = dict(p.partition("=")[::2] for p in params.split("&") if p)
    unknown = set(kv) - {"run", "ckpt", "greedy", "fold", "temp"}
    if unknown or "run" not in kv:
        raise ValueError("nn-Bot: 'nn?run=<Run>@<Checkpoint>' (without @ = latest), optional '&greedy=1', '&temp=<T>' (temperature, 1 = as trained, 0.5 = sharper, 0 = greedy), '&fold=<Fold-Model>' (data/humans/<name>.npz, e.g. for human bot human-1)")
    run, _, ck = kv["run"].partition("@")     #'@' instead of '&ckpt=': no '&' which would break cmd parsing
    fold_model = None
    if "fold" in kv:
        from .husearch import load_opp_fold
        fold_model = load_opp_fold(kv["fold"])
    return NNAgent(load_weights(run, ck or kv.get("ckpt", "latest")), seed, greedy=kv.get("greedy") == "1",
                   fold_model=fold_model, temp=float(kv.get("temp", 1.0)))

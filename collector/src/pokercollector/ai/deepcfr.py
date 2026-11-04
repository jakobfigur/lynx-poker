"""Deep CFR: CFR with neural networks instead of a table (Brown, Lerer, Gross, Sandholm 2019).

Like table CFR (cfr.py), the bot plays against itself and tries all actions at each own decision.
Instead of maintaining regret per coarse situation class in a table,
a network (advantage network) learns to predict it from 46 features. Similar situations share knowledge – table CFR needed hundreds of visits for each of ~77,000 classes.

Per iteration t:
  1. Runs (external sampling) with current strategy = regret matching on the advantage network predictions. At own nodes: play all actions, store measured regret (action value - mixture value) with weight t.
     At opponent nodes: store the played mixture with weight t for the average strategy.
  2. Train advantage network on all collected regret values (weighted MSE).
At end (and in between): train strategy network on stored mixtures. This is the average strategy approaching equilibrium. It has exactly the format of our other networks (nn_agent) and thus plays directly in league and test bench: 'nn?run=<run>@<it>'.

Memory: reservoir sampling of fixed size (like the original) - old and new data remain evenly represented, memory use does not grow.
Storage: data\\rl\\<run>\\ with deepcfr.json, log.jsonl, adv.pt (advantage net + buffer state),
buffers.npz, ckpt_<it>.pt (strategy nets).
"""

from __future__ import annotations

import json
import random
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .cfr import abstract_mask, random_hand
from .engine import Hand
from .features import N_ACTIONS, N_FEATURES, action_mask, features, to_action
from .nn_agent import build_net, numpy_weights, save_checkpoint
from .observation import clamp_action

DEEPCFR_VERSION = "deepcfr-1"


@dataclass
class DeepCFRConfig:
    hidden: int = 128
    traversals: int = 600          # per process and iteration
    adv_capacity: int = 1_500_000  # Reservoir advantage data
    strat_capacity: int = 1_500_000
    adv_steps: int = 600           # Training steps for advantage network per iteration (warm start)
    strat_steps: int = 3000        # Training steps for strategy network at each snapshot
    batch: int = 4096
    lr: float = 1e-3
    value_scale: float = 0.05      # Regret in BB * value_scale (network targets around 1 instead of 20)
    snapshot_every: int = 10
    seed: int = 1


def _adv_np(w: dict, x: np.ndarray) -> np.ndarray:
    h = np.maximum(w["w1"] @ x + w["b1"], 0)
    h = np.maximum(w["w2"] @ h + w["b2"], 0)
    return w["wp"] @ h + w["bp"]


def strategy_from_adv(adv: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Regret matching on predicted advantages. All <= 0: best allowed action (Deep-CFR rule)."""
    pos = np.where(mask, np.maximum(adv, 0.0), 0.0)
    s = pos.sum()
    if s > 0:
        return pos / s
    out = np.zeros(N_ACTIONS)
    out[int(np.argmax(np.where(mask, adv, -np.inf)))] = 1.0
    return out


class _Traverser:
    def __init__(self, w: dict | None, rng: random.Random, t: int, scale: float):
        self.w, self.rng, self.t, self.scale = w, rng, t, scale
        self.adv: list[tuple] = []        # (x, legal_mask, regret*scale)
        self.strat: list[tuple] = []      # (x, legal_mask, sigma)
        self.nodes = 0

    def policy(self, x, amask):
        if self.w is None:
            return amask / amask.sum()
        return strategy_from_adv(_adv_np(self.w, x), amask)

    def traverse(self, h: Hand, p: int) -> float:
        if h.done:
            return h.record.results[p].net / h.bb
        s = h.to_act
        obs = h.observation(s)
        x = features(obs)
        legal = action_mask(obs)
        amask = abstract_mask(obs)
        sigma = self.policy(x, amask)
        self.nodes += 1
        if s == p:
            vals = np.zeros(N_ACTIONS)
            for a in np.flatnonzero(amask):
                h2 = h.clone()
                h2.apply(s, clamp_action(obs, to_action(obs, int(a))))
                vals[a] = self.traverse(h2, p)
            ev = float(sigma @ vals)
            self.adv.append((x, legal, np.where(amask, vals - ev, 0.0) * self.scale))
            return ev
        self.strat.append((x, legal, sigma))
        a = self.rng.choices(range(N_ACTIONS), weights=sigma)[0]
        h.apply(s, clamp_action(obs, to_action(obs, a)))
        return self.traverse(h, p)


def _job(args):
    w, n, t, scale, seed = args
    rng = random.Random(seed)
    tr = _Traverser(w, rng, t, scale)
    for _ in range(n):
        h = random_hand(rng)
        tr.traverse(h, rng.randrange(h.n))

    def pack(rows):
        if not rows:
            return np.zeros((0, N_FEATURES), np.float32), np.zeros((0, N_ACTIONS), bool), np.zeros((0, N_ACTIONS), np.float32)
        return (np.stack([r[0] for r in rows]).astype(np.float32), np.stack([r[1] for r in rows]),
                np.stack([r[2] for r in rows]).astype(np.float32))
    return pack(tr.adv), pack(tr.strat), tr.nodes


class Reservoir:
    """Uniform sampling over all seen data points (Algorithm R), fixed size."""

    def __init__(self, capacity: int, rng: np.random.Generator):
        self.cap = capacity
        self.x = np.zeros((capacity, N_FEATURES), np.float32)
        self.m = np.zeros((capacity, N_ACTIONS), bool)
        self.y = np.zeros((capacity, N_ACTIONS), np.float32)
        self.t = np.zeros(capacity, np.float32)
        self.n = 0          # filled
        self.seen = 0       # total seen
        self.rng = rng

    def add(self, x, m, y, t: int):
        k = len(x)
        if k == 0:
            return
        free = min(k, self.cap - self.n)
        if free:
            sl = slice(self.n, self.n + free)
            self.x[sl], self.m[sl], self.y[sl], self.t[sl] = x[:free], m[:free], y[:free], t
            self.n += free
        rest = k - free
        if rest:
            # slot j for the i-th new point with probability cap/(seen+i+1)
            idx = self.seen + free + np.arange(rest)
            r = (self.rng.random(rest) * (idx + 1)).astype(np.int64)
            keep = r < self.cap
            src = free + np.flatnonzero(keep)
            dst = r[keep]
            self.x[dst], self.m[dst], self.y[dst], self.t[dst] = x[src], m[src], y[src], t
        self.seen += k

    def state(self) -> dict:
        return {"x": self.x[:self.n], "m": self.m[:self.n], "y": self.y[:self.n], "t": self.t[:self.n],
                "seen": np.array(self.seen)}

    def load(self, d: dict, prefix: str):
        n = len(d[prefix + "t"])
        self.x[:n], self.m[:n], self.y[:n], self.t[:n] = d[prefix + "x"], d[prefix + "m"], d[prefix + "y"], d[prefix + "t"]
        self.n = n
        self.seen = int(d[prefix + "seen"])


def _train_adv(net, buf: Reservoir, cfg: DeepCFRConfig, gen) -> float:
    import torch
    opt = torch.optim.Adam(net.parameters(), lr=cfg.lr)
    X, M, Y, T = (torch.from_numpy(a[:buf.n]) for a in (buf.x, buf.m, buf.y, buf.t))
    w_all = T / T.mean()
    total = 0.0
    for _ in range(cfg.adv_steps):
        idx = torch.randint(0, buf.n, (min(cfg.batch, buf.n),), generator=gen)
        h = net.body(X[idx])
        pred = net.pi(h)
        err = torch.where(M[idx], (pred - Y[idx]) ** 2, torch.zeros_like(pred)).sum(-1)
        loss = (err * w_all[idx]).mean()
        opt.zero_grad()
        loss.backward()
        opt.step()
        total += float(loss.detach())
    return total / cfg.adv_steps


def train_strategy(buf: Reservoir, cfg: DeepCFRConfig, gen):
    """ Average strategy: network learns the stored mixtures (weighted by t, linear CFR)."""
    import torch
    net = build_net(cfg.hidden)
    opt = torch.optim.Adam(net.parameters(), lr=cfg.lr)
    X, M, Y, T = (torch.from_numpy(a[:buf.n]) for a in (buf.x, buf.m, buf.y, buf.t))
    w_all = T / T.mean()
    loss_sum = 0.0
    for _ in range(cfg.strat_steps):
        idx = torch.randint(0, buf.n, (min(cfg.batch, buf.n),), generator=gen)
        logits, _ = net(X[idx], M[idx])
        logp = torch.log_softmax(logits, -1)
        ce = -(Y[idx] * torch.where(M[idx], logp, torch.zeros_like(logp))).sum(-1)
        loss = (ce * w_all[idx]).mean()
        opt.zero_grad()
        loss.backward()
        opt.step()
        loss_sum += float(loss.detach())
    return net, loss_sum / cfg.strat_steps


def train_deepcfr(run_dir: Path, iterations: int, cfg: DeepCFRConfig | None = None, workers: int | None = None,
                  progress=None, on_snapshot=None) -> dict:
    import os
    import torch
    run_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = run_dir / "deepcfr.json"
    if cfg_path.exists():
        saved = json.loads(cfg_path.read_text("utf-8"))["config"]
        cfg = DeepCFRConfig(**{k: v for k, v in saved.items() if k in DeepCFRConfig.__dataclass_fields__})
    else:
        cfg = cfg or DeepCFRConfig()
        cfg_path.write_text(json.dumps({"version": DEEPCFR_VERSION, "config": asdict(cfg)}, indent=2), "utf-8")
    torch.manual_seed(cfg.seed)
    gen = torch.Generator().manual_seed(cfg.seed)
    nrng = np.random.default_rng(cfg.seed)
    adv_buf = Reservoir(cfg.adv_capacity, nrng)
    strat_buf = Reservoir(cfg.strat_capacity, nrng)
    adv_net = build_net(cfg.hidden)
    start = 0
    if (run_dir / "adv.pt").exists() and (run_dir / "buffers.npz").exists():
        st = torch.load(run_dir / "adv.pt", map_location="cpu", weights_only=True)
        adv_net.load_state_dict(st["state_dict"])
        start = st["iteration"]
        with np.load(run_dir / "buffers.npz") as z:      # Close file: Windows otherwise does not replace
            d = {k: z[k] for k in z.files}
        adv_buf.load(d, "a_")
        strat_buf.load(d, "s_")
    n_jobs = workers or os.cpu_count() or 4
    t0 = time.perf_counter()
    last = {}
    with ProcessPoolExecutor(n_jobs) as ex:
        for t in range(start + 1, iterations + 1):
            w = numpy_weights(adv_net) if t > 1 else None
            t_r = time.perf_counter()
            res = list(ex.map(_job, [(w, cfg.traversals, t, cfg.value_scale, cfg.seed * 1_000_003 + t * 7919 + j)
                                     for j in range(n_jobs)]))
            nodes = 0
            for (ax, am, ay), (sx, sm, sy), nd in res:
                adv_buf.add(ax, am, ay, t)
                strat_buf.add(sx, sm, sy, t)
                nodes += nd
            t_roll = time.perf_counter() - t_r
            t_tr = time.perf_counter()
            adv_loss = _train_adv(adv_net, adv_buf, cfg, gen)
            t_tr = time.perf_counter() - t_tr
            last = {"iteration": t, "nodes": nodes, "traversals": n_jobs * cfg.traversals,
                    "adv_samples": adv_buf.n, "adv_seen": adv_buf.seen, "strat_samples": strat_buf.n,
                    "adv_loss": round(adv_loss, 5), "rollout_s": round(t_roll, 1), "train_s": round(t_tr, 1),
                    "elapsed_s": round(time.perf_counter() - t0, 1)}
            if t % cfg.snapshot_every == 0 or t == iterations:
                snet, sloss = train_strategy(strat_buf, cfg, gen)
                save_checkpoint(run_dir / f"ckpt_{t:06d}.pt", snet, {"phase": "deepcfr", "iteration": t,
                                                                     "strategy_loss": round(sloss, 5)})
                last["strategy_loss"] = round(sloss, 5)
                torch.save({"state_dict": adv_net.state_dict(), "iteration": t}, run_dir / "adv.tmp")
                (run_dir / "adv.tmp").replace(run_dir / "adv.pt")
                a, s = adv_buf.state(), strat_buf.state()
                tmp = run_dir / "buffers.tmp.npz"
                np.savez(tmp, **{"a_" + k: v for k, v in a.items()}, **{"s_" + k: v for k, v in s.items()})
                tmp.replace(run_dir / "buffers.npz")
                if on_snapshot:
                    on_snapshot(t, last, ex)
            with open(run_dir / "log.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(last) + "\n")
            if progress:
                progress(last)
    return last

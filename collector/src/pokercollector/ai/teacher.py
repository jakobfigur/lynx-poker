"""Suche als Lehrer (Expert Iteration, Hebel H5): die Heads-up-Suche spielt, das Netz lernt ihre Entscheidungen.

Warum: Die Suche (husearch) loest Turn und River im Teilspiel exakt und ist damit dem Netz an den gesuchten
Stellen ueberlegen (gegen Slumbot: hus-5 +-0 statt Netz-typischem River-Verlust; auf hu480 gleichauf). Live und an
vollen Tischen bleibt aber oft keine Zeit zum Suchen. Also soll das Netz die Such-Entscheidungen verinnerlichen:

  1. collect():  Matches Suche gegen verschiedene Gegner in verschiedenen Stacktiefen; an jeder GESUCHTEN
                 Entscheidung werden die Netzeingaben des Schuelers (features + Maske) und die volle
                 Aktionsverteilung der Suche (auf das 8er-Aktionsraster abgebildet, weiche Ziele) gespeichert.
  2. fit():      der Schueler (z. B. lynx-4@300) wird auf diese weichen Ziele nachtrainiert, mit KL-Leine an
                 sein Ausgangsnetz (piKL wie im PPO), damit er an den nicht gesuchten Stellen nicht abdriftet.
  3. Gate:       der neue Checkpoint muss im Pruefstand (bench compare) und gegen Slumbot bestehen.

Nur gesuchte Entscheidungen zaehlen (Blueprint-Zuege des Lehrers lehren nichts Neues). Formate: Cash heads-up mit
Stacks 20-200 BB (auto=1 waehlt die Suchkonfiguration je Hand). Alles synthetisch, keine fremden Haende.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from .features import from_action
from .observation import Action, Observation

TEACHER_VERSION = "teacher-1"


class TeacherRecorder:
    """Huelle um einen HUSearchAgent: spielt wie er, merkt sich jede gesuchte Entscheidung als Lehrerbeispiel."""

    def __init__(self, search_agent, student, name: str = "lehrer"):
        self.inner = search_agent
        self.student = student                  # NNAgent (liefert inputs(obs) im Schueler-Merkmalsraum)
        self.name = name
        self.rows: list[dict] = []
        self.seed = getattr(search_agent, "seed", 0)

    def hand_over(self, rec, seat):
        if hasattr(self.inner, "hand_over"):
            self.inner.hand_over(rec, seat)
        if hasattr(self.student, "hand_over"):
            self.student.hand_over(rec, seat)

    def act(self, obs: Observation) -> Action:
        a = self.inner.act(obs)
        last = getattr(self.inner, "last", None)
        if last and last.get("actions") and last.get("nodes", 0) > 0:      # gesucht (Preflop-Loeser: nodes 0)
            x, mask = self.student.inputs(obs)
            na = len(mask)
            target = np.zeros(na, np.float32)
            for (kind, amt), p in zip(last["actions"], last["probs"]):
                if kind == "fold":
                    act = Action.fold()
                elif kind == "check":
                    act = Action.check()
                elif kind == "call":
                    act = Action.call()
                else:
                    act = Action.raise_to(int(amt))
                target[from_action(obs, act, na)] += float(p)
            target *= mask
            if target.sum() > 0:
                target /= target.sum()
                self.rows.append({"x": x.astype(np.float32), "mask": mask, "target": target,
                                  "street": {"preflop": 0, "flop": 1, "turn": 2, "river": 3}[obs.street],
                                  "stack_bb": float(obs.stack_bb), "pot_bb": obs.pot / (obs.big_blind or 1),
                                  "nodes": int(last["nodes"])})
        return a


def resolve_opponent(name: str) -> str:
    """'mensch-N' -> Stil-Spezifikation aus data/humans/mensch-25nl.json (wie bench 'mensch'); sonst unveraendert."""
    if name.startswith("mensch-"):
        from .humanbots import load_bots
        bots = {b["name"]: b["spec"] for b in load_bots()}
        if name not in bots:
            raise ValueError(f"unbekannter Mensch-Bot '{name}' (vorhanden: {', '.join(sorted(bots))})")
        return bots[name]
    return name


def collect(search_spec: str, student_spec: str, opponents: list[str], hands: int, stacks_bb: list[int],
            out: Path | str, seed: int = 1, progress=None) -> dict:
    """Je Gegner und Stacktiefe ein Match (duplicate) Suche gegen Gegner; Lehrerbeispiele in eine .npz."""
    from .agents import make_agent
    from .evaluate import run_match
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    log = []
    t0 = time.time()
    k = 0
    for stack in stacks_bb:
        for opp in opponents:
            k += 1
            student = make_agent(f"{student_spec}:schueler", seed + k)
            rec = TeacherRecorder(make_agent(f"{search_spec}:lehrer", seed + k), student)
            gegner = make_agent(f"{resolve_opponent(opp)}:gegner", seed + 1000 + k)
            res = run_match([rec, gegner], hands, seed=seed + 10 * k, small_blind=50, big_blind=100, stack_bb=stack)
            r = {x["agent"]: x for x in res["results"]}
            log.append({"opp": opp, "stack_bb": stack, "hands": r["lehrer"]["hands"], "bb100": r["lehrer"]["bb_per_100"],
                        "rows": len(rec.rows), "secs": res["elapsed_s"]})
            rows.extend(rec.rows)
            if progress:
                progress(k, len(stacks_bb) * len(opponents), log[-1], len(rows), time.time() - t0)
    if not rows:
        raise RuntimeError("keine gesuchten Entscheidungen gesammelt")
    data = {key: np.stack([r[key] for r in rows]) for key in ("x", "mask", "target")}
    for key in ("street", "stack_bb", "pot_bb", "nodes"):
        data[key] = np.array([r[key] for r in rows])
    meta = {"version": TEACHER_VERSION, "search": search_spec, "student": student_spec, "opponents": opponents,
            "stacks_bb": stacks_bb, "hands_per_match": hands, "seed": seed, "rows": len(rows), "matches": log,
            "elapsed_s": time.time() - t0, "t": time.strftime("%Y-%m-%d %H:%M:%S")}
    np.savez_compressed(out, **data, meta=json.dumps(meta))
    return meta


def load(paths: list[Path | str]) -> dict:
    parts = [np.load(p, allow_pickle=False) for p in paths]
    d = {k: np.concatenate([p[k] for p in parts]) for k in ("x", "mask", "target", "street", "stack_bb", "pot_bb")}
    d["meta"] = [json.loads(str(p["meta"])) for p in parts]
    return d


def fit(student_run: str, student_ckpt: int | str, paths: list[Path | str], out_run: str, epochs: int = 10,
        batch: int = 512, lr: float = 3e-4, kl_coef: float = 0.5, holdout: float = 0.1, seed: int = 0,
        log=print) -> dict:
    """Schueler auf die weichen Lehrerziele nachtrainieren: Verlust = Kreuzentropie(Ziel, Schueler)
    + kl_coef * KL(Anker || Schueler), Anker = Schueler vor dem Training (eingefroren). Ergebnis
    data/rl/<out_run>/ckpt_000001.pt im nn_agent-Format (gleiche Merkmale, gleiche Aktionen)."""
    import copy
    import torch
    from torch import nn
    from .nn_agent import checkpoint_path, load_checkpoint, net_from_checkpoint, rl_root, save_checkpoint
    torch.manual_seed(seed)
    ck = load_checkpoint(checkpoint_path(student_run, student_ckpt))
    net = net_from_checkpoint(ck)
    anchor = copy.deepcopy(net).eval()
    for p in anchor.parameters():
        p.requires_grad_(False)
    d = load(paths)
    if d["x"].shape[1] != ck["n_features"]:
        raise ValueError(f"Lehrerdaten haben {d['x'].shape[1]} Merkmale, Schueler {ck['n_features']}")
    n = len(d["target"])
    rng = np.random.default_rng(seed)
    perm = rng.permutation(n)
    n_val = max(1, int(n * holdout))
    va, tr = perm[:n_val], perm[n_val:]
    X = torch.from_numpy(d["x"].astype(np.float32))
    M = torch.from_numpy(d["mask"])
    T = torch.from_numpy(d["target"].astype(np.float32))
    opt = torch.optim.Adam(net.parameters(), lr=lr)

    def losses(idx):
        xb, mb, tb = X[idx], M[idx], T[idx]
        logits, _ = net(xb, mb)
        logp = torch.log_softmax(logits, -1)
        ce = -(tb * torch.where(mb, logp, torch.zeros_like(logp))).sum(-1).mean()
        with torch.no_grad():
            a_logits, _ = anchor(xb, mb)
            a_logp = torch.log_softmax(a_logits, -1)
        kl = (torch.exp(a_logp) * torch.where(mb, a_logp - logp, torch.zeros_like(logp))).sum(-1).mean()
        return ce, kl

    def evaluate():
        net.eval()
        with torch.no_grad():
            ce, kl = losses(torch.from_numpy(va))
            logits, _ = net(X[va], M[va])
            agree = (logits.argmax(-1) == T[va].argmax(-1)).float().mean().item()
            a_logits, _ = anchor(X[va], M[va])
            agree0 = (a_logits.argmax(-1) == T[va].argmax(-1)).float().mean().item()
        net.train()
        return ce.item(), kl.item(), agree, agree0

    ce0, kl0, ag0, _ = evaluate()
    log(f"Start: Kreuzentropie {ce0:.4f}, Uebereinstimmung mit der Suche {ag0:.1%} (Hold-out {n_val} von {n})")
    hist = [{"epoch": 0, "val_ce": ce0, "val_kl": kl0, "agree": ag0}]
    net.train()
    for ep in range(epochs):
        order = rng.permutation(tr)
        for i in range(0, len(order), batch):
            idx = torch.from_numpy(order[i:i + batch])
            ce, kl = losses(idx)
            loss = ce + kl_coef * kl
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
        ce, kl, agree, agree0 = evaluate()
        hist.append({"epoch": ep + 1, "val_ce": ce, "val_kl": kl, "agree": agree})
        log(f"Epoche {ep + 1}/{epochs}: Kreuzentropie {ce:.4f}, KL zum Anker {kl:.4f}, Uebereinstimmung {agree:.1%} (Anker {agree0:.1%})")
    out_dir = rl_root() / out_run
    meta = {"phase": "teacher", "iteration": 1, "student": f"{student_run}@{student_ckpt}", "rows": int(n),
            "kl_coef": kl_coef, "epochs": epochs, "hist": hist, "sources": [str(p) for p in paths],
            "teacher_meta": d["meta"]}
    save_checkpoint(out_dir / "ckpt_000001.pt", net, meta)
    (out_dir / "teacher.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), "utf-8")
    return {"out": str(out_dir / "ckpt_000001.pt"), "n": n, "hist": hist}

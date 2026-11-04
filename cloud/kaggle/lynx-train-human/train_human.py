"""Kaggle script: Human-Politics network (H11) from HandHQ showdown decisions (dataset lynx-human-actions).
Input per line: 49 features (feat-2, like the blueprint), action mask (8), chosen action. The network has exactly
the architecture of nn_agent.build_net (body.0, body.2, pi, v), so the checkpoint runs as 'nn?run=human-1@1'
and is used in bpranges as opponent model (ranges=human). Hold-out: every 50th hand. Result: ckpt_000001.pt + train_human.json."""
import glob
import json
import os
import time

import numpy as np
import torch
from torch import nn

HIDDEN = int(os.environ.get("HIDDEN", "512"))
EPOCHS = int(os.environ.get("EPOCHS", "8"))
BATCH = int(os.environ.get("BATCH", "4096"))
LR = float(os.environ.get("LR", "2e-3"))
N_ACTIONS = 8
STREETS = ["preflop", "flop", "turn", "river"]
ACTIONS = ["fold", "call/check", "r_half", "r_pot", "r_2pot", "allin", "r_third", "r_min"]

dev = "cuda" if torch.cuda.is_available() else "cpu"
print('torch', torch.__version__, 'device', dev, torch.cuda.get_device_name(0) if dev == "cuda" else "", flush=True)
files = sorted(glob.glob("/kaggle/input/**/human-*.npz", recursive=True))
print('Shards:', len(files), flush=True)
parts = [np.load(f) for f in files]
x = np.concatenate([p["x"] for p in parts]).astype(np.float16)
mask = np.concatenate([p["mask"] for p in parts])
a = np.concatenate([p["a"] for p in parts]).astype(np.int64)
street = np.concatenate([p["street"] for p in parts]).astype(np.int64)
hand = np.concatenate([p["hand"] for p in parts]).astype(np.int64)
del parts
n = len(a)
hold = (hand % 50) == 0
tr, va = np.nonzero(~hold)[0], np.nonzero(hold)[0]
print(f"{n} lines, training {len(tr)}, hold-out {len(va)} ({hold.mean():.1%} of lines, every 50th hand)", flush=True)
print('Total actions:', {ACTIONS[i]: int(c) for i, c in enumerate(np.bincount(a, minlength=N_ACTIONS))}, flush=True)

X = torch.from_numpy(x)
M = torch.from_numpy(mask)
A = torch.from_numpy(a)
S = torch.from_numpy(street)


class PolicyNet(nn.Module):
    def __init__(self, n_in, hidden, n_actions):
        super().__init__()
        self.body = nn.Sequential(nn.Linear(n_in, hidden), nn.ReLU(), nn.Linear(hidden, hidden), nn.ReLU())
        self.pi = nn.Linear(hidden, n_actions)
        self.v = nn.Linear(hidden, 1)

    def forward(self, x, mask):
        h = self.body(x)
        return self.pi(h).masked_fill(~mask, -1e9), self.v(h).squeeze(-1)


net = PolicyNet(x.shape[1], HIDDEN, N_ACTIONS).to(dev)
opt = torch.optim.AdamW(net.parameters(), lr=LR, weight_decay=1e-5)
steps = EPOCHS * ((len(tr) + BATCH - 1) // BATCH)
sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=LR, total_steps=steps, pct_start=0.1)


def evaluate(idx):
    net.eval()
    nll = np.zeros(4); acc = np.zeros(4); cnt = np.zeros(4)
    with torch.no_grad():
        for i in range(0, len(idx), 16384):
            j = idx[i:i + 16384]
            xb, mb, ab, sb = X[j].to(dev).float(), M[j].to(dev), A[j].to(dev), S[j].to(dev)
            logits, _ = net(xb, mb)
            logp = torch.log_softmax(logits, -1)
            l = -logp.gather(1, ab[:, None])[:, 0]
            hit = (logits.argmax(-1) == ab).float()
            for s in range(4):
                sel = sb == s
                nll[s] += l[sel].sum().item(); acc[s] += hit[sel].sum().item(); cnt[s] += sel.sum().item()
    net.train()
    return nll / np.maximum(cnt, 1), acc / np.maximum(cnt, 1), cnt


# Reference line: action frequency per street (limited to mask) -> NLL
freq = np.stack([np.bincount(a[(street == s) & ~hold], minlength=N_ACTIONS) + 1.0 for s in range(4)])
freq = freq / freq.sum(1, keepdims=True)
base = np.zeros(4); cnt0 = np.zeros(4)
for s in range(4):
    sel = va[street[va] == s]
    p = freq[s][None, :] * mask[sel]
    p = p / p.sum(1, keepdims=True)
    base[s] = -np.log(np.maximum(p[np.arange(len(sel)), a[sel]], 1e-9)).mean(); cnt0[s] = len(sel)
print('Reference line NLL (frequencies per street):', {STREETS[s]: round(float(base[s]), 4) for s in range(4)}, flush=True)

hist = []
t0 = time.time()
rng = np.random.default_rng(0)
for ep in range(EPOCHS):
    order = rng.permutation(tr)
    run = 0.0
    for i in range(0, len(order), BATCH):
        j = order[i:i + BATCH]
        xb, mb, ab = X[j].to(dev).float(), M[j].to(dev), A[j].to(dev)
        logits, _ = net(xb, mb)
        loss = nn.functional.cross_entropy(logits, ab)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        nn.utils.clip_grad_norm_(net.parameters(), 1.0)
        opt.step(); sched.step()
        run += loss.item() * len(j)
    nll, acc, cnt = evaluate(va)
    tot = float((nll * cnt).sum() / cnt.sum())
    hist.append({"epoch": ep + 1, "train_nll": run / len(tr), "val_nll": tot,
                 "val_nll_street": nll.tolist(), "val_acc_street": acc.tolist(), "secs": time.time() - t0})
    print(f"Epoch {ep + 1}/{EPOCHS}: Training {run / len(tr):.4f}, Hold-out NLL {tot:.4f} "
          + " ".join(f"{STREETS[s]} {nll[s]:.3f}/{acc[s]:.1%}" for s in range(4)) + f", {time.time() - t0:.0f}s", flush=True)

sd = {k: v.detach().cpu() for k, v in net.state_dict().items()}
meta = {"phase": "human-bc", "iteration": 1, "source": 'HandHQ showdown decisions (lynx-human-actions)', "rows": int(n),
        "train_rows": int(len(tr)), "holdout_rows": int(len(va)), "hidden": HIDDEN, "epochs": EPOCHS,
        "baseline_nll_street": base.tolist(), "hist": hist}
torch.save({"nn_version": "nn-mlp-1", "features": "feat-2", "n_features": int(x.shape[1]), "hidden": HIDDEN,
            "n_actions": N_ACTIONS, "state_dict": sd, "meta": meta}, "/kaggle/working/ckpt_000001.pt")
json.dump(meta, open("/kaggle/working/train_human.json", "w"), indent=1)
print(json.dumps({k: v for k, v in meta.items() if k != "hist"}), flush=True)

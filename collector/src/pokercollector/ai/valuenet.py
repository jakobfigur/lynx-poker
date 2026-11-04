"""Wertnetz fuer die Suche (Meilenstein 3): oeffentlicher Zustand + beide Ranges -> kontrafaktische Werte je
Kombination fuer beide Spieler (in Pot-Einheiten), wie sie die exakte CFR+-Loesung liefert (valuedata.py).

Diese Datei ist absichtlich EIGENSTAENDIG (nur numpy + torch, keine Paket-Importe), damit dieselbe Datei
unveraendert als Trainingsskript auf Kaggle laeuft:  python valuenet.py train --data "*.npz" --out vnet.pt
Privat: Daten sind synthetische, geloeste Kunst-Situationen; nichts davon stammt aus echten Haenden.

Eingabe (2712): Board als 52-Bit-Belegung, Strasse (3), log(Pot in BB), log(Stack in BB), log(SPR), wer zuerst
handelt (oop), Range Spieler 0 (1326), Range Spieler 1 (1326).
Ausgabe (2652): v0 (1326), v1 (1326). Verlust: Huber auf gueltigen Kombinationen (nicht vom Board blockiert) plus
Strafe auf die Nullsummen-Verletzung r0.v0 + r1.v1 (muss 0 sein). Beim Vorhersagen wird die Nullsumme exakt
hergestellt (haelftige Korrektur beider Seiten, wie in ReBeL).
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import time
from pathlib import Path

import numpy as np

try:
    import torch
    from torch import nn
except ImportError:       # pragma: no cover
    torch = None
    nn = None

VALUENET_VERSION = "vnet-1"
N_COMBOS = 1326
N_IN = 52 + 3 + 4 + 2 * N_COMBOS
N_OUT = 2 * N_COMBOS

# Kombinationen in derselben Reihenfolge wie ranges.COMBOS: alle Paare (a, b) mit a < b ueber 52 Karten
_COMBOS = np.array([(a, b) for a in range(52) for b in range(a + 1, 52)], np.int64)


def combo_mask(board: np.ndarray) -> np.ndarray:
    """[n, 1326] True fuer Kombinationen ohne Boardkarte. board: int8[n, 5], -1 = leer."""
    n = board.shape[0]
    blocked = np.zeros((n, 52), bool)
    for k in range(board.shape[1]):
        col = board[:, k]
        ok = col >= 0
        blocked[np.nonzero(ok)[0], col[ok]] = True
    return ~(blocked[:, _COMBOS[:, 0]] | blocked[:, _COMBOS[:, 1]])


def features(board: np.ndarray, pot_bb: np.ndarray, stack_bb: np.ndarray, oop: np.ndarray, r0: np.ndarray,
             r1: np.ndarray) -> np.ndarray:
    """float32[n, N_IN]."""
    n = board.shape[0]
    x = np.zeros((n, N_IN), np.float32)
    for k in range(board.shape[1]):
        col = board[:, k]
        ok = col >= 0
        x[np.nonzero(ok)[0], col[ok]] = 1.0
    ncards = (board >= 0).sum(1)
    x[np.arange(n), 52 + np.clip(ncards - 3, 0, 2)] = 1.0            # Flop/Turn/River
    pot = np.maximum(pot_bb.astype(np.float32), 0.5)
    stack = np.maximum(stack_bb.astype(np.float32), 0.5)
    x[:, 55] = np.log(pot) / 4.0
    x[:, 56] = np.log(stack) / 4.0
    x[:, 57] = np.log(stack / pot) / 3.0
    x[:, 58] = oop.astype(np.float32)
    x[:, 59:59 + N_COMBOS] = r0.astype(np.float32) * 100.0            # Gewichte ~1/1326 -> Groessenordnung 0.1
    x[:, 59 + N_COMBOS:] = r1.astype(np.float32) * 100.0
    return x


class ValueMLP(nn.Module if nn else object):
    def __init__(self, width: int = 1024, depth: int = 3):
        super().__init__()
        layers, d = [], N_IN
        for _ in range(depth):
            layers += [nn.Linear(d, width), nn.LayerNorm(width), nn.GELU()]
            d = width
        layers.append(nn.Linear(d, N_OUT))
        self.net = nn.Sequential(*layers)
        self.width, self.depth = width, depth

    def forward(self, x):
        return self.net(x)


def zero_sum_fix(v0: np.ndarray, v1: np.ndarray, r0: np.ndarray, r1: np.ndarray,
                 mask: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Nullsumme exakt herstellen: Fehler e = r0.v0 + r1.v1 haelftig auf beide Seiten verteilen (ReBeL), nur auf
    den gueltigen Kombinationen (mask), so skaliert, dass r.v sich je Seite um genau e/2 aendert."""
    if mask is None:
        mask = np.ones_like(v0, dtype=bool)
    m = mask.astype(np.float64)
    e = (r0 * v0).sum(-1, keepdims=True) + (r1 * v1).sum(-1, keepdims=True)
    s0 = np.maximum((r0 * m).sum(-1, keepdims=True), 1e-12)
    s1 = np.maximum((r1 * m).sum(-1, keepdims=True), 1e-12)
    return v0 - e / 2.0 / s0 * m, v1 - e / 2.0 / s1 * m


class ValueNet:
    """Geladenes Netz fuer die Suche: predict(...) liefert v0, v1 in Pot-Einheiten (Nullsumme exakt)."""

    def __init__(self, model, device: str = "cpu", threads: int | None = 2):
        self.model = model.to(device).eval()
        self.device = device
        if threads and device == "cpu":
            # kleine Matrizen: mehr Faeden kosten nur Start-Overhead und streiten mit dem numba-Kernel um die Kerne
            torch.set_num_threads(int(threads))

    @classmethod
    def load(cls, path: Path | str, device: str = "cpu", threads: int | None = 2) -> "ValueNet":
        ck = torch.load(path, map_location=device, weights_only=False)
        m = ValueMLP(ck.get("width", 1024), ck.get("depth", 3))
        m.load_state_dict(ck["state"])
        return cls(m, device, threads)

    @torch.no_grad()
    def predict(self, board, pot_bb, stack_bb, oop, r0, r1) -> tuple[np.ndarray, np.ndarray]:
        x = torch.from_numpy(features(board, pot_bb, stack_bb, oop, r0, r1)).to(self.device)
        y = self.model(x).cpu().numpy().astype(np.float64)
        mask = combo_mask(board)
        v0, v1 = y[:, :N_COMBOS] * mask, y[:, N_COMBOS:] * mask
        return zero_sum_fix(v0, v1, r0.astype(np.float64), r1.astype(np.float64), mask)


# ---------------------------------------------------------------- Training (lokal klein, auf Kaggle gross)

def load_shards(paths: list[str]) -> dict:
    parts = [np.load(p, allow_pickle=False) for p in paths]
    keys = ("board", "pot_bb", "stack_bb", "oop", "r0", "r1", "v0", "v1")
    d = {k: np.concatenate([p[k] for p in parts]) for k in keys}
    d["meta"] = [json.loads(str(p["meta"])) for p in parts]
    return d


def train(paths: list[str], out: Path | str, epochs: int = 10, batch: int = 512, lr: float = 1e-3,
          width: int = 1024, depth: int = 3, holdout: float = 0.02, device: str | None = None, seed: int = 0,
          zs_weight: float = 1.0, log=print, resume: str | None = None) -> dict:
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(seed)
    d = load_shards(paths)
    n = d["board"].shape[0]
    # Speicher (500k Situationen auf Kaggle, ~29 GB RAM): Eingaben und Ziele als float16 halten (x 2,7 GB, y 2,6 GB),
    # Maske einmal als bool (0,7 GB), Ranges NICHT getrennt speichern (stecken in x als r*100). Je Batch wird auf
    # dem Geraet nach float32 gewandelt. Vorher: alles float32 und doppelt -> ~27 GB, zu viel.
    x = np.empty((n, N_IN), np.float16)
    for i in range(0, n, 20000):
        j = slice(i, min(n, i + 20000))
        x[j] = features(d["board"][j], d["pot_bb"][j], d["stack_bb"][j], d["oop"][j], d["r0"][j], d["r1"][j])
    y = np.concatenate([d["v0"].astype(np.float16), d["v1"].astype(np.float16)], 1)
    mask1 = combo_mask(d["board"])
    shards_meta = [m.get("street") for m in d["meta"]]
    del d
    rng = np.random.default_rng(seed)
    perm = rng.permutation(n)
    n_val = max(1, int(n * holdout)) if n > 10 else 1
    va, tr = perm[:n_val], perm[n_val:]
    X, Y, M1 = (torch.from_numpy(a) for a in (x, y, mask1))

    def batch_tensors(j):
        xb = X[j].to(device).float()
        mb1 = M1[j].to(device).float()
        return xb, Y[j].to(device).float(), torch.cat([mb1, mb1], 1), xb[:, 59:] / 100.0

    model = ValueMLP(width, depth).to(device)
    if resume:
        ck = torch.load(resume, map_location=device, weights_only=False)
        model.load_state_dict(ck["state"])
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-5)
    steps = max(1, epochs * math.ceil(len(tr) / batch))
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=steps, pct_start=0.1)
    huber = nn.SmoothL1Loss(reduction="none", beta=0.1)
    hist = []
    t0 = time.time()

    def evaluate(idx):
        model.eval()
        tot = cnt = zs = 0.0
        with torch.no_grad():
            for i in range(0, len(idx), 4096):
                j = idx[i:i + 4096]
                xb, yb, mb, rb = batch_tensors(j)
                p = model(xb) * mb
                tot += ((p - yb).abs() * mb).sum().item()
                cnt += mb.sum().item()
                zs += (p * rb).sum(1).abs().mean().item() * len(j)
        model.train()
        return tot / max(cnt, 1), zs / max(len(idx), 1)

    model.train()
    for ep in range(epochs):
        order = rng.permutation(tr)
        run = 0.0
        for i in range(0, len(order), batch):
            j = order[i:i + batch]
            xb, yb, mb, rb = batch_tensors(j)
            p = model(xb)
            loss = (huber(p, yb) * mb).sum() / mb.sum().clamp_min(1)
            zs = ((p * mb) * rb).sum(1).pow(2).mean()
            (loss + zs_weight * zs).backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            opt.zero_grad(set_to_none=True)
            sched.step()
            run += loss.item() * len(j)
        mae, zsv = evaluate(va)
        hist.append({"epoch": ep + 1, "train_loss": run / max(len(tr), 1), "val_mae_pot": mae, "val_zero_sum": zsv,
                     "secs": time.time() - t0})
        log(f"Epoche {ep + 1}/{epochs}: Verlust {hist[-1]['train_loss']:.4f}, Hold-out MAE {mae:.4f} Pot, "
            f"Nullsumme {zsv:.4f}, {time.time() - t0:.0f}s")
        torch.save({"version": VALUENET_VERSION, "state": model.state_dict(), "width": width, "depth": depth,
                    "n_train": int(len(tr)), "hist": hist, "shards": shards_meta}, out)
    return {"n": n, "val_mae_pot": hist[-1]["val_mae_pot"], "hist": hist, "out": str(out), "device": device}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Wertnetz trainieren (lokal oder Kaggle)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("train")
    p.add_argument("--data", required=True, help="Glob auf .npz-Scherben, z. B. '/kaggle/input/lynx-vdata/river-*.npz'")
    p.add_argument("--out", default="vnet.pt")
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--batch", type=int, default=512)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--width", type=int, default=1024)
    p.add_argument("--depth", type=int, default=3)
    p.add_argument("--resume")
    a = ap.parse_args(argv)
    paths = sorted(glob.glob(a.data))
    if not paths:
        raise SystemExit(f"keine Dateien fuer {a.data}")
    res = train(paths, a.out, a.epochs, a.batch, a.lr, a.width, a.depth, resume=a.resume)
    print(json.dumps({k: v for k, v in res.items() if k != "hist"}, ensure_ascii=False))


if __name__ == "__main__":
    main()

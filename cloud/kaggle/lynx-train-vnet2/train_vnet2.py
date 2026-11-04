"""Kaggle script (31.10., stage 2): Value network vnet-2 for River AND Turn trained from three private datasets:
lynx-vdata (river-*.npz), lynx-vdata-leaf (river-leaf-*.npz), lynx-vdata-turn (turn-leaf-*.npz).
The features encode the street (board cards + flop/turn/river bit), one net learns both.
One shard each River-Leaf and Turn-Leaf is held out as a clean test (MAE per street in test.json).
Result: /kaggle/working/vnet-2.pt (checkpoint per epoch), train.json, test.json."""
import glob
import json
import os
import sys
import time

import numpy as np
import torch

for root, dirs, files in os.walk("/kaggle/input"):
    print(root, dirs, files[:10], flush=True)
hits = glob.glob("/kaggle/input/**/valuenet.py", recursive=True)
if not hits:
    raise SystemExit('valuenet.py not found in dataset')
DATA = os.path.dirname(hits[0])
sys.path.insert(0, DATA)
from valuenet import ValueMLP, combo_mask, features, load_shards, train  # noqa: E402

EPOCHS = int(os.environ.get("EPOCHS", "60"))
WIDTH = int(os.environ.get("WIDTH", "2048"))
DEPTH = int(os.environ.get("DEPTH", "3"))
BATCH = int(os.environ.get("BATCH", "1024"))
LR = float(os.environ.get("LR", "1e-3"))
TURN_REPEAT = int(os.environ.get("TURN_REPEAT", "1"))   # 1.11.: 9 Turn shards (~200k lines) are simply enough
RIVER_SHARDS = int(os.environ.get("RIVER_SHARDS", "12"))  # 1.11.: Kaggle RAM limit (~1.1 million lines): 20 River + 19 Leaf + 9 Turn x2 = OOM "Killed"
RESUME = os.environ.get("RESUME") or None                # Path of a checkpoint (e.g. vnet-river-1) as start

print('torch', torch.__version__, 'cuda', torch.cuda.is_available(),
      torch.cuda.get_device_name(0) if torch.cuda.is_available() else "-", flush=True)
river = sorted(glob.glob("/kaggle/input/**/river-[0-9]*.npz", recursive=True))[:RIVER_SHARDS]
leaf = sorted(glob.glob("/kaggle/input/**/river-leaf-*.npz", recursive=True))
turn = sorted(glob.glob("/kaggle/input/**/turn-leaf-*.npz", recursive=True))
print(f"Fragments: river {len(river)}, river-leaf {len(leaf)}, turn-leaf {len(turn)}", flush=True)
if not turn:
    raise SystemExit('no turn-leaf shards found')
test = {"river-leaf": leaf[-1:], "turn-leaf": turn[-1:]}
train_paths = river + leaf[:-1] + turn[:-1] * TURN_REPEAT
print('Training:', len(train_paths), 'Paths (Turn x', TURN_REPEAT, '), Test:', test, flush=True)

t0 = time.time()
res = train(train_paths, "/kaggle/working/vnet-2.pt", epochs=EPOCHS, batch=BATCH, lr=LR, width=WIDTH, depth=DEPTH,
            resume=RESUME, log=lambda m: print("  " + m, flush=True))
res["wall_s"] = time.time() - t0
res["turn_repeat"] = TURN_REPEAT
res["n_shards"] = {"river": len(river), "river-leaf": len(leaf) - 1, "turn-leaf": len(turn) - 1}
json.dump(res, open("/kaggle/working/train.json", "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "hist"}), flush=True)

# Clean test per street on the held-back fragments (same measure as hold-out: MAE in pot over live combos)
dev = "cuda" if torch.cuda.is_available() else "cpu"
ck = torch.load("/kaggle/working/vnet-2.pt", map_location=dev, weights_only=False)
model = ValueMLP(ck["width"], ck["depth"]).to(dev)
model.load_state_dict(ck["state"])
model.eval()
out = {}
for street, paths in test.items():
    d = load_shards(paths)
    n = d["board"].shape[0]
    tot = cnt = zs = 0.0
    with torch.no_grad():
        for i in range(0, n, 4096):
            j = slice(i, min(n, i + 4096))
            x = torch.from_numpy(features(d["board"][j], d["pot_bb"][j], d["stack_bb"][j], d["oop"][j],
                                          d["r0"][j], d["r1"][j])).to(dev)
            y = torch.from_numpy(np.concatenate([d["v0"][j], d["v1"][j]], 1).astype(np.float32)).to(dev)
            m1 = torch.from_numpy(combo_mask(d["board"][j])).to(dev).float()
            m = torch.cat([m1, m1], 1)
            p = model(x) * m
            tot += ((p - y).abs() * m).sum().item()
            cnt += m.sum().item()
            zs += (p * (x[:, 59:] / 100.0)).sum(1).abs().mean().item() * (j.stop - j.start)
    out[street] = {"n": int(n), "mae_pot": tot / max(cnt, 1), "zero_sum": zs / max(n, 1), "paths": paths}
    print(f"TEST {street}: {n} rows, MAE {out[street]['mae_pot']:.4f} pot, zero sum {out[street]['zero_sum']:.4f}",
          flush=True)
json.dump(out, open("/kaggle/working/test.json", "w"), indent=1)

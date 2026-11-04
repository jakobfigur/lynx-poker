"""Kaggle-Skript: Wertnetz (River) aus den Scherben im privaten Dataset lynx-vdata trainieren.
Ergebnis: /kaggle/working/vnet-river.pt (Checkpoint je Epoche) + train.json."""
import glob
import json
import os
import sys
import time

import torch

for root, dirs, files in os.walk("/kaggle/input"):
    print(root, dirs, files[:10], flush=True)
hits = glob.glob("/kaggle/input/**/valuenet.py", recursive=True)
if not hits:
    raise SystemExit("valuenet.py nicht im Dataset gefunden")
DATA = os.path.dirname(hits[0])
sys.path.insert(0, DATA)
from valuenet import train  # noqa: E402

# Tranche 1 (30.10.): 500k River-Situationen, volles Netz 1024x3, Batch 1024, 30 Epochen OneCycle
EPOCHS = int(os.environ.get("EPOCHS", "60"))
WIDTH = int(os.environ.get("WIDTH", "2048"))
DEPTH = int(os.environ.get("DEPTH", "3"))
BATCH = int(os.environ.get("BATCH", "1024"))
LR = float(os.environ.get("LR", "1e-3"))
SHARDS = int(os.environ.get("SHARDS", "0"))        # 0 = alle; sonst nur die ersten n Scherben (Lernkurve)

print("torch", torch.__version__, "cuda", torch.cuda.is_available(),
      torch.cuda.get_device_name(0) if torch.cuda.is_available() else "-", flush=True)
paths = sorted(glob.glob("/kaggle/input/**/river-*.npz", recursive=True)) or sorted(glob.glob(f"{DATA}/*.npz"))
if SHARDS:
    paths = paths[:SHARDS]
print("Scherben:", len(paths), paths[:3], "...", flush=True)
t0 = time.time()
res = train(paths, "/kaggle/working/vnet-river.pt", epochs=EPOCHS, batch=BATCH, lr=LR, width=WIDTH, depth=DEPTH,
            log=lambda m: print("  " + m, flush=True))
res["wall_s"] = time.time() - t0
json.dump(res, open("/kaggle/working/train.json", "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "hist"}), flush=True)

# Value Network: Data on Hetzner Cloud, Training on Kaggle (Milestone 3)

Status 29.10.2026, draft. Everything private: Hetzner server exists only for the run, Kaggle notebook and dataset
remain private (default). Going public: our code (Hetzner), training script `valuenet.py`, and
synthetic data (Kaggle). No recordings, no hands from Jakob.

## A. Data on Hetzner Cloud (Status 29.10 evening: Access verified, tool built)

Access: Token `data/cloud/hetzner.token` (project "lynx", verified), SSH key `data/cloud/lynx_hetzner`
(registered at Hetzner as "lynx-hetzner"). No `hcloud`/`rsync` needed: `cloud/hetzner.py` communicates with the API
directly (standard library) and uses `ssh`/`scp` from Git for Windows.

Server type: desired **cx53** (16 vCPU Intel shared, 32 GB, €0.056/h gross, 0.35 ct per core-hour). **As of 30.10., the entire cx series at all three German/Finnish locations is sold out** (HTTP 412 `resource_unavailable`,
"error during placement") and cpx51 is no longer offered; orderable was **cpx62** (16 vCPU AMD shared, 32 GB,
€0.248/h, 1.55 ct per core-hour → tranche 500k approx. €0.95 instead of €0.25). `hetzner.py types --location fsn1` now shows
the column "orderable", `create` checks this beforehand and lists alternatives. Dedicated ccx cores cost 3.3 ct per
core-hour and are only worthwhile if shared cores are measurably throttled (compare seconds per situation on the 1000 test against the laptop).

```
set PY=tools\python\cpython-3.12.12-windows-x86_64-none\python.exe
%PY% cloud\hetzner.py types                        Prices
%PY% cloud\hetzner.py create lynx-vdata-1 --type cpx62 --location fsn1   create (default cx53/nbg1), upload code,
                                                   server-setup.sh (apt, uv, uv sync, smoke test 20 situations)
%PY% cloud\hetzner.py ssh lynx-vdata-1 "nohup /opt/lynx/cloud/run-vdata.sh river 0 20 25000 > /opt/lynx/data/vdata.log 2>&1 &"
%PY% cloud\hetzner.py ssh lynx-vdata-1 "tail -5 /opt/lynx/data/vdata.log; ls -la /opt/lynx/data/valuenet"
%PY% cloud\hetzner.py pull lynx-vdata-1 /opt/lynx/data/valuenet/ data\valuenet\hetzner-1
%PY% cloud\hetzner.py delete lynx-vdata-1          Costs stop immediately
%PY% cloud\hetzner.py list                         lists running servers and current costs
```

**Caution Git-Bash:** MSYS converts arguments like `/opt/lynx/...` into `C:/Users/.../Git/opt/lynx/...`. This caused
the first 1000-test to be lost on 30.10 (scp could not find the path, server was already deleted). `hetzner.py` now
reverts this for `pull`/`ssh` and `pull` aborts if nothing arrives (do **not** delete server then); also set `export MSYS_NO_PATHCONV=1` in Git-Bash. This problem does not occur from `cmd.exe`/PowerShell. Always in order:
pull → verify locally (`ls`, load file) → only then `delete`.

`run-vdata.sh <street> <von> <bis> <n>` computes shards `von..bis-1` with each `n` situations (seeds continuous,
`nproc` processes single-threaded), skips completed shards (resume) and writes `.npz` to
`/opt/lynx/data/valuenet/`. Tranche 1 = shards 0–19 (500,000 River situations, ≈ 0.43 s/situation/core →
≈ 60 core hours ≈ 4 h on a cx53 ≈ €0.25), tranche 2 = shards 20–39.

Procedure: first `run-vdata.sh river 0 1 1000` (1000-test, check runtime per situation and hold-out MAE locally),
**inform Jakob before starting a server**, then tranche 1.

## B. Training on Kaggle (free, T4, ≈ 30 GPU h per week) – end-to-end verified 29.10. 21:12

Account **YOUR_KAGGLE_USER**, access `data/cloud/kaggle.token` (env var `KAGGLE_API_TOKEN`), CLI without
installation: `tools\uv\uv.exe tool run --from kaggle kaggle ...` (set cache `UV_CACHE_DIR`). All private.

1. **Dataset** `YOUR_KAGGLE_USER/lynx-vdata` (private, exists; contains `valuenet.py` + shards). Copy new shards to the
   folder `cloud/kaggle/lynx-vdata/` (or link) and upload as a new version:
   ```
   kaggle datasets version -p cloud\kaggle\lynx-vdata -m "Tranche 1" --dir-mode skip
   ```
   (first creation was `kaggle datasets create -p ...`; always upload `valuenet.py`, which is the training script.)
   On Kaggle it is located under `/kaggle/input/datasets/YOUR_KAGGLE_USER/lynx-vdata/` (not `/kaggle/input/lynx-vdata`).
2. **Script kernel** `YOUR_KAGGLE_USER/lynx-train-river` (`cloud/kaggle/lynx-train-river/`: `kernel-metadata.json` with
   `enable_gpu`, `dataset_sources`; `train_river.py` looks for `valuenet.py` in the dataset and calls `train(...)`).
   Adjust parameters via constants in the script (EPOCHS, WIDTH, DEPTH, BATCH, LR), then:
   ```
   kaggle kernels push -p cloud\kaggle\lynx-train-river
   kaggle kernels status YOUR_KAGGLE_USER/lynx-train-river
   kaggle kernels output YOUR_KAGGLE_USER/lynx-train-river -p data\valuenet\kaggle-out
   ```
   Trial: 3000 situations, 256×2, 20 epochs → 10 s on the T4, hold-out MAE 0.20 Pot
   (`data/valuenet/vnet-river-probe-kaggle.pt`). Script kernel time limit 12 h; checkpoint per epoch,
   resume with `--resume` via a second version.
3. Memory: 500,000 × 2712 float32 ≈ 5.4 GB features + targets 2.6 GB → fits in 30 GB RAM of GPU kernel;
   at 1 million situations, build features batchwise (TODO in `valuenet.train`).
4. Result `vnet-river-1.pt` (≈ 30 MB) download to `data/valuenet/`, then locally:
   ```
   pc.cmd bench tournament ... (no) → search with network: "hus?bp=lynx-4-300&streets=preflop,turn,river&vnet=vnet-river-1"
   ```
5. Measurement series: hu480 paired against network and hus-1/hus-2, slumbot cleaned, GTO Wizard AIVAT.

## C. Acceptance criteria River network
- Hold-out MAE < 0.015 Pot (1.5% of pot) per combination.
- Oracle test (`test_husearch_leaf.py`) with real net instead of oracle: EV deviation from full Turn tree
  < 0.05 Pot on 50 random Turn situations.
- Turn decision live < 0.5 s at 100 iterations.

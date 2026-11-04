# Wertnetz: Daten auf Hetzner Cloud, Training auf Kaggle (Meilenstein 3)

Stand 29.10.2026, Entwurf. Alles privat: Hetzner-Server existiert nur für den Lauf, Kaggle-Notebook und -Dataset
bleiben privat (Standard). Nach draußen gehen: unser Code (Hetzner), das Trainingsskript `valuenet.py` und die
synthetischen Daten (Kaggle). Keine Aufnahmen, keine Hände von Jakob.

## A. Daten auf Hetzner Cloud (Stand 29.10. abends: Zugang geprüft, Werkzeug gebaut)

Zugang: Token `data/cloud/hetzner.token` (Projekt „lynx“, geprüft), SSH-Schlüssel `data/cloud/lynx_hetzner`
(bei Hetzner als „lynx-hetzner“ hinterlegt). Kein `hcloud`/`rsync` nötig: `cloud/hetzner.py` spricht die API
direkt (Standardbibliothek) und nutzt `ssh`/`scp` aus Git für Windows.

Servertyp: Wunsch **cx53** (16 vCPU Intel shared, 32 GB, 0,056 €/h brutto, 0,35 ct je Kern-Stunde). **Stand 30.10.
ist die ganze cx-Reihe an allen drei deutschen/finnischen Standorten ausverkauft** (HTTP 412 `resource_unavailable`,
„error during placement“) und cpx51 wird nicht mehr angeboten; bestellbar war **cpx62** (16 vCPU AMD shared, 32 GB,
0,248 €/h, 1,55 ct je Kern-Stunde → Tranche 500k ≈ 0,95 € statt 0,25 €). `hetzner.py types --location fsn1` zeigt
jetzt die Spalte „bestellbar“, `create` prüft das vorab und nennt Alternativen. Dedizierte ccx-Kerne kosten 3,3 ct je
Kern-Stunde und lohnen nur, wenn die shared-Kerne messbar gedrosselt werden (beim 1000er-Test vergleichen: Sekunden je
Situation gegen den Laptop).

```
set PY=tools\python\cpython-3.12.12-windows-x86_64-none\python.exe
%PY% cloud\hetzner.py types                        Preise
%PY% cloud\hetzner.py create lynx-vdata-1 --type cpx62 --location fsn1   anlegen (Standard cx53/nbg1), Code hochladen,
                                                   server-setup.sh (apt, uv, uv sync, Rauchtest 20 Situationen)
%PY% cloud\hetzner.py ssh lynx-vdata-1 "nohup /opt/lynx/cloud/run-vdata.sh river 0 20 25000 > /opt/lynx/data/vdata.log 2>&1 &"
%PY% cloud\hetzner.py ssh lynx-vdata-1 "tail -5 /opt/lynx/data/vdata.log; ls -la /opt/lynx/data/valuenet"
%PY% cloud\hetzner.py pull lynx-vdata-1 /opt/lynx/data/valuenet/ data\valuenet\hetzner-1
%PY% cloud\hetzner.py delete lynx-vdata-1          Kosten enden sofort
%PY% cloud\hetzner.py list                         zeigt laufende Server und bisherige Kosten
```

**Achtung Git-Bash:** MSYS wandelt Argumente wie `/opt/lynx/...` in `C:/Users/.../Git/opt/lynx/...` um. Darüber ging am
30.10. der erste 1000er-Test verloren (scp fand den Pfad nicht, Server war schon gelöscht). `hetzner.py` macht das für
`pull`/`ssh` jetzt rückgängig und `pull` bricht ab, wenn nichts ankommt (dann Server **nicht** löschen); in Git-Bash
zusätzlich `export MSYS_NO_PATHCONV=1` setzen. Aus `cmd.exe`/PowerShell gibt es das Problem nicht. Reihenfolge immer:
pull → lokal prüfen (`ls`, Datei laden) → erst dann `delete`.

`run-vdata.sh <street> <von> <bis> <n>` rechnet Scherben `von..bis-1` mit je `n` Situationen (Seeds fortlaufend,
`nproc` Prozesse à 1 Faden), überspringt fertige Scherben (Wiederaufnahme) und schreibt `.npz` nach
`/opt/lynx/data/valuenet/`. Tranche 1 = Scherben 0–19 (500 000 River-Situationen, ≈ 0,43 s/Situation/Kern →
≈ 60 Kernstunden ≈ 4 h auf einem cx53 ≈ 0,25 €), Tranche 2 = Scherben 20–39.

Ablauf: zuerst `run-vdata.sh river 0 1 1000` (1000er-Test, Laufzeit je Situation und Hold-out-MAE lokal prüfen),
**vor dem Start eines Servers Jakob Bescheid geben**, danach Tranche 1.

## B. Training auf Kaggle (gratis, T4, ≈ 30 GPU-h je Woche) – Ende-zu-Ende geprüft 29.10. 21:12

Konto **YOUR_KAGGLE_USER**, Zugang `data/cloud/kaggle.token` (Umgebungsvariable `KAGGLE_API_TOKEN`), CLI ohne
Installation: `tools\uv\uv.exe tool run --from kaggle kaggle ...` (Cache `UV_CACHE_DIR` setzen). Alles privat.

1. **Dataset** `YOUR_KAGGLE_USER/lynx-vdata` (privat, existiert; enthält `valuenet.py` + Scherben). Neue Scherben in den
   Ordner `cloud/kaggle/lynx-vdata/` kopieren (bzw. verknüpfen) und als neue Version hochladen:
   ```
   kaggle datasets version -p cloud\kaggle\lynx-vdata -m "Tranche 1" --dir-mode skip
   ```
   (erste Anlage war `kaggle datasets create -p ...`; `valuenet.py` immer mit hochladen, es ist das Trainingsskript.)
   Auf Kaggle liegt es unter `/kaggle/input/datasets/YOUR_KAGGLE_USER/lynx-vdata/` (nicht `/kaggle/input/lynx-vdata`).
2. **Skript-Kernel** `YOUR_KAGGLE_USER/lynx-train-river` (`cloud/kaggle/lynx-train-river/`: `kernel-metadata.json` mit
   `enable_gpu`, `dataset_sources`; `train_river.py` sucht `valuenet.py` im Dataset und ruft `train(...)`).
   Parameter über die Konstanten im Skript (EPOCHS, WIDTH, DEPTH, BATCH, LR) anpassen, dann:
   ```
   kaggle kernels push -p cloud\kaggle\lynx-train-river
   kaggle kernels status YOUR_KAGGLE_USER/lynx-train-river
   kaggle kernels output YOUR_KAGGLE_USER/lynx-train-river -p data\valuenet\kaggle-out
   ```
   Probe: 3000 Situationen, 256×2, 20 Epochen → 10 s auf der T4, Hold-out-MAE 0,20 Pot
   (`data/valuenet/vnet-river-probe-kaggle.pt`). Laufzeitgrenze eines Skript-Kernels 12 h; Checkpoint je Epoche,
   Fortsetzung mit `--resume` über eine zweite Version.
3. Speicher: 500 000 × 2712 float32 ≈ 5,4 GB Merkmale + Ziele 2,6 GB → passt in die 30 GB RAM des GPU-Kernels;
   bei 1 Mio. Situationen Merkmale batchweise aufbauen (TODO in `valuenet.train`).
4. Ergebnis `vnet-river-1.pt` (≈ 30 MB) herunterladen nach `data/valuenet/`, dann lokal:
   ```
   pc.cmd bench turnier ... (nein) → Suche mit Netz: "hus?bp=lynx-4-300&streets=preflop,turn,river&vnet=vnet-river-1"
   ```
5. Messreihe: hu480 gepaart gegen Netz und hus-1/hus-2, Slumbot bereinigt, GTO Wizard AIVAT.

## C. Abnahmekriterien River-Netz
- Hold-out-MAE < 0,015 Pot (1,5 % des Pots) je Kombination.
- Orakel-Test (`test_husearch_leaf.py`) mit echtem Netz statt Orakel: EV-Abweichung zum vollen Turn-Baum
  < 0,05 Pot auf 50 zufälligen Turn-Situationen.
- Turn-Entscheidung live < 0,5 s bei 100 Iterationen.

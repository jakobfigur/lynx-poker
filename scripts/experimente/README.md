# Experiment Scripts

Here are the scripts with which the training and measurements from the [Case Study](../../docs/CASE-STUDY.md) were actually run, unchanged except for replaced paths. They document how the numbers were generated; to rerun, they must be adapted.

- **Environment:** written for Windows with Git Bash and the portable setup on a USB stick (`tools\uv\uv.exe`, project folder as root). `<Projektordner>` and `<scratchpad>` stand for the original absolute paths.
- **Python scripts** (`bench_*.py`, `confirm_lynx3.py`) are platform-neutral. Invocation from `collector/`: `uv run --project . python ../scripts/experimente/<skript>.py`. Scripts using a process pool require the `if __name__ == "__main__"` guard under Windows (it is present).
- **Shell scripts** (`train_*.sh`, `night*.sh`, `morning.sh`, `measure.sh` …) run training phases with Gate, select the title defender from `data/league/players.json`, and continue from an existing checkpoint. The recipes are more readable in Part 2, Section 10 of the [technical documentation](../../docs/TECHNICAL_DOCUMENTATION.md).
- **`.cmd` wrappers** start measurements independently and write their output to `data/bench/*.txt`.

| Script | Run |
| --- | --- |
| `train_h1.sh`, `train_h1b.sh` | pros-h1, later „Lynx“ (Oct 27) |
| `train_lynx2.sh` | lynx-2, training with 40 % human-bots (Oct 27) |
| `train_lynx3.sh`, `morgen_lynx3.sh`, `confirm_lynx3.py` | lynx-3 in sections up to 1500 iterations, confirmations, slumbot (night Oct 27/28) |
| `night_lynx4.sh` | lynx-4 with ICM reward (night Oct 28/29) |
| `bench_hus*.py`, `bench_diag_nacht.py` | measurement series of heads-up search (Oct 29–30) |
| `bench_humanopp*.py`, `bench_humanopp3.cmd` | search and networks against the human-bot (Oct 31/Nov 1) |
| `bench_lynx5t_sets.*`, `bench_temp.cmd`, `exploit_greedy.cmd` | test bench, temperature and exploiter test for greedy (Oct 31) |
| `slumbot_long.sh`, `measure.sh`, `morning.sh`, `night.sh`, `night2.sh`, `pause_and_humans.sh` | slumbot long runs, test bench series, HandHQ evaluation |

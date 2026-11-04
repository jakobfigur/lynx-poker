# Experiment-Skripte

Hier liegen die Skripte, mit denen die Trainings und Messungen aus der [Case Study](../../docs/CASE-STUDY.md) tatsächlich gelaufen sind, unverändert bis auf ersetzte Pfade. Sie dokumentieren, wie die Zahlen entstanden; zum erneuten Ausführen müssen sie angepasst werden.

- **Umgebung:** geschrieben für Windows mit Git Bash und das portable Setup auf einem USB-Stick (`tools\uv\uv.exe`, Projektordner als Wurzel). `<Projektordner>` und `<scratchpad>` stehen für die ursprünglichen absoluten Pfade.
- **Python-Skripte** (`bench_*.py`, `confirm_lynx3.py`) sind plattformneutral. Aufruf aus `collector/`: `uv run --project . python ../scripts/experimente/<skript>.py`. Skripte mit Prozess-Pool brauchen unter Windows den `if __name__ == "__main__"`-Schutz (ist vorhanden).
- **Shell-Skripte** (`train_*.sh`, `night*.sh`, `morning.sh`, `measure.sh` …) laufen Trainingsabschnitte mit Gate, wählen den Titelverteidiger aus `data/league/players.json` und setzen an einem vorhandenen Stand fort. Die Rezepte stehen lesbarer in Teil 2, Abschnitt 10 der [technischen Dokumentation](../../docs/TECHNISCHE-DOKUMENTATION.md).
- **`.cmd`-Hüllen** starten Messungen losgelöst und schreiben ihre Ausgabe nach `data/bench/*.txt`.

| Skript | Lauf |
| --- | --- |
| `train_h1.sh`, `train_h1b.sh` | pros-h1, später „Lynx“ (27.10.) |
| `train_lynx2.sh` | lynx-2, Training mit 40 % Mensch-Bots (27.10.) |
| `train_lynx3.sh`, `morgen_lynx3.sh`, `confirm_lynx3.py` | lynx-3 in Abschnitten bis 1500 Iterationen, Bestätigungen, Slumbot (Nacht 27./28.10.) |
| `night_lynx4.sh` | lynx-4 mit ICM-Belohnung (Nacht 28./29.10.) |
| `bench_hus*.py`, `bench_diag_nacht.py` | Messreihe der Heads-up-Suche (29.–30.10.) |
| `bench_humanopp*.py`, `bench_humanopp3.cmd` | Suche und Netze gegen den Menschen-Bot (31.10./1.11.) |
| `bench_lynx5t_sets.*`, `bench_temp.cmd`, `exploit_greedy.cmd` | Prüfstand, Temperatur und Ausbeuter-Test für greedy (31.10.) |
| `slumbot_long.sh`, `measure.sh`, `morning.sh`, `night.sh`, `night2.sh`, `pause_and_humans.sh` | Slumbot-Langläufe, Prüfstand-Serien, HandHQ-Auswertung |

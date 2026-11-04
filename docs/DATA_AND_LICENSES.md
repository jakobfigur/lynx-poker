# Data, Models, and Licenses

As of 3.11.2026 · Jakob Figur

The repository contains all the code, a test image, and a small starter package of trained models (about 2.5 MB). Raw data, recordings, value network training data, and access credentials are deliberately not included; this document explains what is missing, why, and how to generate or obtain it yourself.

## Starter Package in the Repository

| File under `data/` | Content | Purpose |
| --- | --- | --- |
| `league/players.json` | League: 18 players with specifications and ratings (network bots without league games) | League names like `lynx-4-300` in all commands |
| `rl/pros-1/ckpt_000000.pt` | Behavioral clone from 10,000 Pluribus hands (league `pros-bc`) | Opponents in the `mix` and format test sets, start of exploitability tests |
| `rl/pros-2/ckpt_000300.pt`, `rl/pros-r1/ckpt_000300.pt`, `rl/pros-r3/ckpt_000200.pt` | Early PPO generations (Oct 26–27) | League opponents, generation comparison |
| `rl/pros-h1/ckpt_000600.pt` | First version named "Lynx" (Oct 27) | League `lynx`, `pros-h1` |
| `rl/lynx-2/ckpt_000500.pt`, `rl/lynx-3/ckpt_000300.pt` | Generations with human bots in training (Oct 27/28) | League `lynx-2`, `lynx-3-300` |
| `rl/lynx-4/ckpt_000300.pt`, `rl/lynx-4/best.json` | Best all-round bot, standard for live advice (Oct 29) | League `lynx-4-300`, blueprint of the search |
| `rl/lynx-5t/ckpt_000001.pt`, `rl/lynx-5t/teacher.json` | Student of the search, strongest player against human reconstruction (Oct 31) | `nn?run=lynx-5t@1&greedy=1` |
| `rl/human-1/ckpt_000001.pt`, `rl/human-1/train_human.json` | Policy network learned from 7.35 million showdown decisions by HandHQ players | Human bot, opponent model for the search |
| `humans/mensch-25nl.json` | Six style bots adapted to HandHQ player types | Test set `mensch480`, training with human opponents |
| `humans/human-fold-1.npz` | Fold model derived from 55.5 million decisions without private-card observations | Human bot with folds `nn?run=human-1@1&fold=human-fold-1` |

The models contain only network weights or style parameters, no player names or hand histories. The release script also verifies the contents of `.pt` and `.npz` files for paths, names, and credentials.

## Not in the Repository

| What | Why not | How to generate or obtain |
| --- | --- | --- |
| Recordings (`data/sessions/`, 3.2 GB) | Screen videos of own games, large | `pc.cmd live` or `pc.cmd analyze <video>` |
| Card templates (`data/templates/`) | Cropped images from PokerTH graphics | `pc.cmd harvest-cards <screenshots>` (interactive, Part 1 Section 4 of the technical documentation) |
| Value network training data (`data/valuenet/`, 8 GB) | Size | `pc.cmd train valuedata ...` locally or `cloud/run-vdata.sh` on a server |
| Value networks `vnet-river-1.pt`, `vnet-2b.pt` (each 77 MB) | Size | Download from the [v0.1.0 release](https://github.com/jakobfigur/lynx-poker/releases/tag/v0.1.0); verify the published SHA-256 checksums and place the files in `data/valuenet/` |
| PHH raw data (`data/external/`, 9.3 GB) | Third-party source | [uoftcprg/phh-dataset](https://github.com/uoftcprg/phh-dataset), commands in Part 2 Section 9 of the technical documentation |
| Evaluations of human data (`data/humans/actions/`, 543 MB) | Size, derived from third-party data | `pc.cmd data humandata`, `pc.cmd data humanpublic` |
| Teacher data (`data/teacher/`) | Intermediate product | `cloud/run-teacher.sh` or `pc.cmd train teacher-collect` |
| Training runs and checkpoints (`data/rl/*` except starter pack, 620 MB) | Size | Recipes in Part 2 Section 10, original scripts in `scripts/experimente/` |
| Measurement logs (`data/bench/`, Slumbot and GTO Wizard hands) | Logs from external services | `pc.cmd bench run`, `bench slumbot`, `bench gtow` |
| Access credentials (`data/cloud/`, `data/bench/gtow/api_key.txt`) | Secret | Create your own credentials (Part 2 Section 9); `.gitignore` double protects these paths |

## Third-Party Sources and Licenses

| Source | Use in Lynx | License or Terms |
| --- | --- | --- |
| [PHH-Dataset](https://github.com/uoftcprg/phh-dataset) (Universal, Open, Free, and Transparent Computer Poker Research Group) | Pluribus hands for behavioral cloning and engine testing; HandHQ hands for human statistics, human bots and human model | Repository under MIT license; raw data not redistributed |
| Pluribus hands (Brown & Sandholm, *Science* 2019, Supplement) | 10,000 hands, via the PHH Dataset | Scientific publication |
| HandHQ hand histories (July 2009, 25NL, anonymized) | Statistics, player types, training data for `human-1` and `human-fold-1` | Via the PHH Dataset; original source's own terms not independently reviewed |
| [PokerTH](https://www.pokerth.net/) | Game environment (play money), whose UI the collector reads and whose log it uses as a reference | Free software; Lynx contains no PokerTH code, only a test image of the UI (`collector/testdata/`) |
| [Slumbot](https://www.slumbot.com/) | External benchmark via public API (`ai/slumbot.py`) | Use of the API; no Slumbot data in the repository |
| GTO Wizard Researcher API | Second benchmark, client in `ai/gtow.py` (access not yet granted) | Provider's terms; own key required |
| Python packages (numpy, opencv-python, mss, torch, numba, pillow, winrt, pytest) | Runtime and tests | BSD, MIT, Apache 2.0 or HPND; compatible with Lynx's MIT license |

Lynx itself is under the MIT license (`LICENSE`). The license covers code, documentation, and the starter pack; third-party data retains their own terms.

## Usage Note

Lynx was developed and tested exclusively against PokerTH (play money) and public research benchmarks. Bots and real-time advice are prohibited on real-money platforms and may be illegal; Lynx is not intended for that purpose. The live advice only displays suggestions and never clicks automatically.

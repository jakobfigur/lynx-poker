# CLI Reference

Automatically generated from the argparse parser of `pokercollector` (`scripts/gen_reference.py`). Usage on Windows with `pc.cmd <command> ...`, on Linux/macOS with `./pc.sh <command> ...`.

## Command Overview

- `calibrate`
- `analyze`
- `windows`
- `live`
- `live-replay`
- `leiste-demo`
- `reconstruct`
- `report`
- `inspect-reference`
- `compare`
- `advise`
- `harvest-cards`
- `verify`
- `sim`
  - `sim agents`
  - `sim match`
  - `sim hand`
  - `sim tournament`
  - `sim pushfold`
  - `sim review`
- `play`
- `play-stats`
- `league`
  - `league show`
  - `league add`
  - `league retire`
  - `league run`
  - `league bench`
- `train`
  - `train cem`
  - `train gate`
  - `train bc`
  - `train cfr`
  - `train deepcfr`
  - `train exploit`
  - `train humans-fit`
  - `train valuedata`
  - `train valuenet`
  - `train teacher-collect`
  - `train teacher-fit`
  - `train humanfold`
  - `train rl`
- `bench`
  - `bench run`
  - `bench show`
  - `bench slumbot`
  - `bench gtow`
  - `bench ziele`
  - `bench turnier`
  - `bench compare`
- `data`
  - `data pluribus`
  - `data humans`
  - `data humandata`
  - `data humanpublic`
  - `data agree`

## `pokercollector`

```text
usage: pokercollector [-h] [--profile PROFILE] [--allow-sleep]
                      {calibrate,analyze,windows,live,live-replay,leiste-demo,reconstruct,report,inspect-reference,compare,advise,harvest-cards,verify,sim,play,play-stats,league,train,bench,data}
                      ...

Visual capture of PokerTH games

positional arguments:
  {calibrate,analyze,windows,live,live-replay,leiste-demo,reconstruct,report,inspect-reference,compare,advise,harvest-cards,verify,sim,play,play-stats,league,train,bench,data}
    calibrate           Analyze screenshot, generate overlay image
    analyze             Evaluate video or screenshot folder (new session)
    windows             List windows
    live                Capture windows live, automatically start/stop sessions
    live-replay         play back recorded session like live: suggestions + opponent model
    leiste-demo         demonstrate Lynx bar without table (colors, sounds, position)
    reconstruct         reconstruct hands of a session
    report              output hand report of a session
    inspect-reference   show schema of a PokerTH log file
    compare             compare session with PokerTH export
    advise              baseline recommendation for a screenshot
    harvest-cards       learn card templates from screenshots (interactive)
    verify              check checksums of a session
    sim                 simulator, bots and evaluation
    play                you against the bots (terminal)
    play-stats          evaluation of your matches against the bots
    league              league, rating, benchmark
    train               improve bots themselves
    bench               Test bench: fixed test sets for each candidate
    data                Read and evaluate foreign hand histories (PHH)

options:
  -h, --help            show this help message and exit
  --profile PROFILE     Path to a table profile (JSON); default: built-in PokerTH web profile
  --allow-sleep         Allow standby during the run (default: keep awake so long runs do not abort)
```

## `pokercollector calibrate`

```text
usage: pokercollector calibrate [-h] [--out OUT] image

positional arguments:
  image

options:
  -h, --help  show this help message and exit
  --out OUT
```

## `pokercollector analyze`

```text
usage: pokercollector analyze [-h] [--step STEP] [--interval INTERVAL] input

positional arguments:
  input

options:
  -h, --help           show this help message and exit
  --step STEP          Seconds between analyzed video frames
  --interval INTERVAL  Assumed interval between screenshots
```

## `pokercollector windows`

```text
usage: pokercollector windows [-h] [filter]

positional arguments:
  filter

options:
  -h, --help  show this help message and exit
```

## `pokercollector live`

```text
usage: pokercollector live [-h] [--window WINDOW] [--hwnd HWND] [--fps FPS] [--segment SEGMENT]
                           [--stop-after STOP_AFTER] [--max-seconds MAX_SECONDS] [--no-video]
                           [--allow-background] [--advice] [--leiste] [--still] [--kein-eintrag] [--mischen]
                           [--agent AGENT]

options:
  -h, --help            show this help message and exit
  --window WINDOW       Part of the window title
  --hwnd HWND
  --fps FPS
  --segment SEGMENT     Segment length in seconds
  --stop-after STOP_AFTER
                        Session ends after this many seconds without table
  --max-seconds MAX_SECONDS
  --no-video            journal only, no video recording
  --allow-background    also record when the window is not in the foreground (risk: obscured content)
  --advice              show suggestion when it’s your turn
  --leiste              additionally show suggestion in the Lynx bar above the taskbar (with sound; sets
                        --advice)
  --still               bar without sound
  --kein-eintrag        do not automatically enter recognized end of turn into target board
  --mischen             draw suggestion from mixed strategy instead of the most likely action
  --agent AGENT         league name or agent for suggestions (default lynx-4-300 = best bot)
```

## `pokercollector live-replay`

```text
usage: pokercollector live-replay [-h] [--agent AGENT] session

positional arguments:
  session        folder, part of name or 'last'

options:
  -h, --help     show this help message and exit
  --agent AGENT  league name or agent
```

## `pokercollector leiste-demo`

```text
usage: pokercollector leiste-demo [-h] [--still] [--sekunden SEKUNDEN]

options:
  -h, --help           show this help message and exit
  --still              without sound
  --sekunden SEKUNDEN  display duration per example
```

## `pokercollector reconstruct`

```text
usage: pokercollector reconstruct [-h] session

positional arguments:
  session     folder, part of name or 'last'

options:
  -h, --help  show this help message and exit
```

## `pokercollector report`

```text
usage: pokercollector report [-h] session

positional arguments:
  session

options:
  -h, --help  show this help message and exit
```

## `pokercollector inspect-reference`

```text
usage: pokercollector inspect-reference [-h] file

positional arguments:
  file

options:
  -h, --help  show this help message and exit
```

## `pokercollector compare`

```text
usage: pokercollector compare [-h] session reference

positional arguments:
  session
  reference

options:
  -h, --help  show this help message and exit
```

## `pokercollector advise`

```text
usage: pokercollector advise [-h] image

positional arguments:
  image

options:
  -h, --help  show this help message and exit
```

## `pokercollector harvest-cards`

```text
usage: pokercollector harvest-cards [-h] images [images ...]

positional arguments:
  images

options:
  -h, --help  show this help message and exit
```

## `pokercollector verify`

```text
usage: pokercollector verify [-h] session

positional arguments:
  session

options:
  -h, --help  show this help message and exit
```

## `pokercollector sim`

```text
usage: pokercollector sim [-h] {agents,match,hand,tournament,pushfold,review} ...

positional arguments:
  {agents,match,hand,tournament,pushfold,review}
    agents              available bots
    match               Evaluate bots against each other
    hand                play and show a hand
    tournament          Sit&Go tournaments (like PokerTH) between bots
    pushfold            display Nash push/fold ranges
    review              compare own decisions of a session with an agent

options:
  -h, --help            show this help message and exit
```

### `pokercollector sim agents`

```text
usage: pokercollector sim agents [-h]

options:
  -h, --help  show this help message and exit
```

### `pokercollector sim match`

```text
usage: pokercollector sim match [-h] [--agents AGENTS] [--seed SEED] [--sb SB] [--bb BB] [--stack STACK]
                                [--hands HANDS] [--no-duplicate] [--show SHOW]

options:
  -h, --help       show this help message and exit
  --agents AGENTS  comma-separated list, e.g. tag,tag:tag2,random
  --seed SEED
  --sb SB
  --bb BB
  --stack STACK    starting stack in big blinds
  --hands HANDS    number of card sheets
  --no-duplicate
  --show SHOW      output this many hand histories
```

### `pokercollector sim hand`

```text
usage: pokercollector sim hand [-h] [--agents AGENTS] [--seed SEED] [--sb SB] [--bb BB] [--stack STACK]
                               [--button BUTTON]

options:
  -h, --help       show this help message and exit
  --agents AGENTS  comma-separated list, e.g. tag,tag:tag2,random
  --seed SEED
  --sb SB
  --bb BB
  --stack STACK    starting stack in big blinds
  --button BUTTON
```

### `pokercollector sim tournament`

```text
usage: pokercollector sim tournament [-h] [--agents AGENTS] [--tournaments TOURNAMENTS] [--seed SEED]
                                     [--stack STACK] [--blinds BLINDS] [--level-hands LEVEL_HANDS]
                                     [--payouts PAYOUTS] [--no-duplicate]

options:
  -h, --help            show this help message and exit
  --agents AGENTS
  --tournaments TOURNAMENTS
                        number of card schemas (x number of players for duplicates)
  --seed SEED
  --stack STACK         starting chips
  --blinds BLINDS       starting blinds SB/BB
  --level-hands LEVEL_HANDS
                        hands until blinds double
  --payouts PAYOUTS     percent per place, e.g. 100 (winner takes all)
  --no-duplicate
```

### `pokercollector sim pushfold`

```text
usage: pokercollector sim pushfold [-h] [--stack STACK] [--behind BEHIND] [--caller CALLER] [--overview]

options:
  -h, --help       show this help message and exit
  --stack STACK    effective stack in BB
  --behind BEHIND  players behind the pusher (1 = SB vs BB)
  --caller CALLER  which caller (0 = first behind pusher)
  --overview       push percentages for all stacks/positions
```

### `pokercollector sim review`

```text
usage: pokercollector sim review [-h] [--agent AGENT] session

positional arguments:
  session

options:
  -h, --help     show this help message and exit
  --agent AGENT
```

## `pokercollector play`

```text
usage: pokercollector play [-h] [--mode {cash,tournament}] [--opponents OPPONENTS] [--name NAME]
                           [--blinds BLINDS] [--stack STACK] [--level-hands LEVEL_HANDS] [--payouts PAYOUTS]
                           [--stack-bb STACK_BB] [--hands HANDS] [--seed SEED] [--coach] [--unrated]
                           [--ascii]

options:
  -h, --help            show this help message and exit
  --mode {cash,tournament}
  --opponents OPPONENTS
                        bots/league players, comma-separated list
  --name NAME
  --blinds BLINDS
  --stack STACK         tournament: starting chips
  --level-hands LEVEL_HANDS
  --payouts PAYOUTS
  --stack-bb STACK_BB   cash: stack in BB (rebuy to this value)
  --hands HANDS         cash: maximum number of hands
  --seed SEED
  --coach               show push/fold hint after your decision
  --unrated             do not register tournament in the league
  --ascii               card suits as letters
```

## `pokercollector play-stats`

```text
usage: pokercollector play-stats [-h] [--name NAME]

options:
  -h, --help   show this help message and exit
  --name NAME
```

## `pokercollector league`

```text
usage: pokercollector league [-h] {show,add,retire,run,bench} ...

positional arguments:
  {show,add,retire,run,bench}
    show                table + progress graph (report.html)
    add                 enter bot version, e.g. add tag-v2 'tag?bluff=0.2'
    retire              remove bot from automatic rounds
    run                 play league games between bots
    bench               benchmark against fixed opponents (all bots or one)

options:
  -h, --help            show this help message and exit
```

### `pokercollector league show`

```text
usage: pokercollector league show [-h]

options:
  -h, --help  show this help message and exit
```

### `pokercollector league add`

```text
usage: pokercollector league add [-h] [--note NOTE] name spec

positional arguments:
  name
  spec

options:
  -h, --help   show this help message and exit
  --note NOTE
```

### `pokercollector league retire`

```text
usage: pokercollector league retire [-h] name

positional arguments:
  name

options:
  -h, --help  show this help message and exit
```

### `pokercollector league run`

```text
usage: pokercollector league run [-h] [--rounds ROUNDS] [--table TABLE] [--stack STACK]
                                 [--level-hands LEVEL_HANDS] [--seed SEED]

options:
  -h, --help            show this help message and exit
  --rounds ROUNDS
  --table TABLE
  --stack STACK
  --level-hands LEVEL_HANDS
  --seed SEED
```

### `pokercollector league bench`

```text
usage: pokercollector league bench [-h] [--hands HANDS] [--tournaments TOURNAMENTS] [name]

positional arguments:
  name

options:
  -h, --help            show this help message and exit
  --hands HANDS
  --tournaments TOURNAMENTS
```

## `pokercollector train`

```text
usage: pokercollector train [-h]
                            {cem,gate,bc,cfr,deepcfr,exploit,humans-fit,valuedata,valuenet,teacher-collect,teacher-fit,humanfold,rl}
                            ...

positional arguments:
  {cem,gate,bc,cfr,deepcfr,exploit,humans-fit,valuedata,valuenet,teacher-collect,teacher-fit,humanfold,rl}
    cem                 optimize style parameters, recording check, possibly add to league
    gate                Qualification match: candidate against title defender
    bc                  Learning bot, step 1: imitate teacher bot -> Checkpoint 0
    cfr                 Equilibrium via Monte-Carlo CFR (Pluribus method)
    deepcfr             Deep CFR: equilibrium with neural networks instead of table
    exploit             Exploitability test: how strongly can a bot be exploited deliberately?
    humans-fit          Human bots: Adapt style bots to real player types (data humans)
    valuedata           Value network data: Solve situations exactly at the start of the street (milestone
                        3)
    valuenet            Train value network from value data shards (locally small; large on Kaggle)
    teacher-collect     Search as teacher (H5): Collect search decisions as soft targets
    teacher-fit         Search as teacher (H5): further train student on collected targets (with KL loss)
    humanfold           Fold model from the card-free HandHQ lines (H11 step 2b)
    rl                  Learning bot, step 2: self-play with PPO (continues a run)

options:
  -h, --help            show this help message and exit
```

### `pokercollector train cem`

```text
usage: pokercollector train cem [-h] [--start START] [--generations GENERATIONS] [--population POPULATION]
                                [--schemes SCHEMES] [--gate-schemes GATE_SCHEMES] [--champion CHAMPION]
                                [--name NAME] [--seed SEED] [--resume RESUME] [--opponents {league,fixed}]

options:
  -h, --help            show this help message and exit
  --start START         starting style
  --generations GENERATIONS
  --population POPULATION
  --schemes SCHEMES     Card schemas per generation (x6 tournaments)
  --gate-schemes GATE_SCHEMES
  --champion CHAMPION   League player the candidate must beat
  --name NAME           Name in the league (default: opt-<date>)
  --seed SEED
  --resume RESUME       Continue training folder (data\train\...)
  --opponents {league,fixed}
                        league = tables from all active league bots, strong more often, with self-play
                        (default); fixed = always rock/tag/lag/station/maniac
```

### `pokercollector train gate`

```text
usage: pokercollector train gate [-h] [--from FROM_DIR] [--champion CHAMPION] [--schemes SCHEMES]
                                 [--seed SEED] [--opponents {league,fixed}]
                                 [candidate]

positional arguments:
  candidate             Bot specification in quotes, e.g. "tag?push_bb=15&bluff=0.2"

options:
  -h, --help            show this help message and exit
  --from FROM_DIR       Take candidate from a training folder (result.json)
  --champion CHAMPION
  --schemes SCHEMES
  --seed SEED           Different seed = different, fresh card schemas
  --opponents {league,fixed}
```

### `pokercollector train bc`

```text
usage: pokercollector train bc [-h] [--teacher TEACHER] [--run RUN] [--bc-tournaments BC_TOURNAMENTS]
                               [--dataset DATASET] [--players PLAYERS] [--epochs EPOCHS]
                               [--features FEATURES]

options:
  -h, --help            show this help message and exit
  --teacher TEACHER
  --run RUN             Name of run under data\rl (default: nn-<date>)
  --bc-tournaments BC_TOURNAMENTS
  --dataset DATASET     Instead of teacher bot: dataset under data\datasets, e.g. pluribus
  --players PLAYERS     Only these players from the dataset, comma-separated, e.g. Pluribus
  --epochs EPOCHS
  --features FEATURES   Feature version of the dataset (default: latest)
```

### `pokercollector train cfr`

```text
usage: pokercollector train cfr [-h] [--run RUN] [--rounds ROUNDS] [--traversals TRAVERSALS]
                                [--bench-every BENCH_EVERY] [--seed SEED]

options:
  -h, --help            show this help message and exit
  --run RUN
  --rounds ROUNDS       Target round (total number)
  --traversals TRAVERSALS
                        Iterations per process and round
  --bench-every BENCH_EVERY
  --seed SEED
```

### `pokercollector train deepcfr`

```text
usage: pokercollector train deepcfr [-h] [--run RUN] [--iterations ITERATIONS] [--traversals TRAVERSALS]
                                    [--snapshot-every SNAPSHOT_EVERY] [--seed SEED] [--buffer BUFFER]

options:
  -h, --help            show this help message and exit
  --run RUN
  --iterations ITERATIONS
                        Target iteration (total number)
  --traversals TRAVERSALS
                        Iterations per process and iteration
  --snapshot-every SNAPSHOT_EVERY
  --seed SEED
  --buffer BUFFER       Entries per data buffer (RAM approx. 220 MB per 1 million; 2 buffers)
```

### `pokercollector train exploit`

```text
usage: pokercollector train exploit [-h] [--init INIT] [--iterations ITERATIONS] [--schemes SCHEMES] target

positional arguments:
  target                Bot specification, e.g. rock or "nn?run=pros-1@200"

options:
  -h, --help            show this help message and exit
  --init INIT           Start point of exploiter (run@checkpoint)
  --iterations ITERATIONS
  --schemes SCHEMES
```

### `pokercollector train humans-fit`

```text
usage: pokercollector train humans-fit [-h] [--source SOURCE] [--name NAME] [--generations GENERATIONS]
                                       [--population POPULATION] [--hands HANDS]

options:
  -h, --help            show this help message and exit
  --source SOURCE       data\humans\<source>.json
  --name NAME           Result data\humans\<name>.json
  --generations GENERATIONS
  --population POPULATION
  --hands HANDS         Hands per measurement
```

### `pokercollector train valuedata`

```text
usage: pokercollector train valuedata [-h] [--n N] [--seed SEED] [--iters ITERS] [--workers WORKERS]
                                      [--threads THREADS] [--out OUT] [--vnet VNET]
                                      {river,turn,flop,river-leaf,turn-leaf}

positional arguments:
  {river,turn,flop,river-leaf,turn-leaf}
                        Street at the start of which evaluation is done; river-leaf = river starts from real
                        turn searches (up to 24 rows per seed), turn-leaf = turn starts from real flop
                        searches, river via value network (up to 12 rows per seed)

options:
  -h, --help            show this help message and exit
  --n N                 Situations in this shard
  --seed SEED           First seed (shards: seed, seed+n, ...)
  --iters ITERS         CFR+ iterations (default river 300, turn 150, flop 60)
  --workers WORKERS     Processes
  --threads THREADS     Numba threads per process (default: all)
  --out OUT             Target file .npz (default data\valuenet\<street>-<seed>.npz)
  --vnet VNET           River value network as leaf (turn/flop/turn-leaf; default with turn-leaf: vnet-
                        river-1)
```

### `pokercollector train valuenet`

```text
usage: pokercollector train valuenet [-h] --data DATA [--out OUT] [--epochs EPOCHS] [--batch BATCH]
                                     [--lr LR] [--width WIDTH] [--depth DEPTH] [--resume RESUME]

options:
  -h, --help       show this help message and exit
  --data DATA      Glob on .npz shards, e.g. data\valuenet\river-*.npz
  --out OUT        Name under data\valuenet\<out>.pt or path
  --epochs EPOCHS
  --batch BATCH
  --lr LR
  --width WIDTH
  --depth DEPTH
  --resume RESUME  Checkpoint from which to continue training
```

### `pokercollector train teacher-collect`

```text
usage: pokercollector train teacher-collect [-h] [--search SEARCH] [--student STUDENT]
                                            [--opponents OPPONENTS] [--stacks STACKS] [--hands HANDS]
                                            [--seed SEED] --out OUT

options:
  -h, --help            show this help message and exit
  --search SEARCH       Specification of the search (teacher)
  --student STUDENT     Student network (determines feature space)
  --opponents OPPONENTS
                        Opponent specifications, comma-separated
  --stacks STACKS       Stack depths in BB, comma-separated
  --hands HANDS         Card decks per match (duplicate -> twice as many hands)
  --seed SEED
  --out OUT             Target file .npz (e.g. data\teacher\t1-seed1.npz)
```

### `pokercollector train teacher-fit`

```text
usage: pokercollector train teacher-fit [-h] --data DATA [--student STUDENT] --out-run OUT_RUN
                                        [--epochs EPOCHS] [--batch BATCH] [--lr LR] [--kl KL]

options:
  -h, --help         show this help message and exit
  --data DATA        Glob on teacher-.npz, e.g. data\teacher\t1-*.npz
  --student STUDENT  <run>@<checkpoint>
  --out-run OUT_RUN  New run under data\rl\<out-run> (ckpt_000001.pt)
  --epochs EPOCHS
  --batch BATCH
  --lr LR
  --kl KL            Weight of the KL loss on the anchor (0 = off)
```

### `pokercollector train humanfold`

```text
usage: pokercollector train humanfold [-h] [--rows ROWS] [--out OUT] [--max-rows MAX_ROWS]
                                      [--max-shards MAX_SHARDS] [--epochs EPOCHS]

options:
  -h, --help            show this help message and exit
  --rows ROWS           Folder with public-*.npz (default data\humans\actions)
  --out OUT             Name under data\humans\<out>.npz
  --max-rows MAX_ROWS
  --max-shards MAX_SHARDS
                        Memory: limit shards
  --epochs EPOCHS
```

### `pokercollector train rl`

```text
usage: pokercollector train rl [-h] [--run RUN] [--teacher TEACHER] [--bc-tournaments BC_TOURNAMENTS]
                               [--iterations ITERATIONS] [--tournaments TOURNAMENTS] [--champion CHAMPION]
                               [--gate-schemes GATE_SCHEMES] [--name NAME] [--seed SEED]
                               [--anchor-coef ANCHOR_COEF] [--anchor ANCHOR] [--random-share RANDOM_SHARE]
                               [--exploit-every EXPLOIT_EVERY] [--exploit-iters EXPLOIT_ITERS]
                               [--random-formats] [--lr LR] [--bench-every BENCH_EVERY]
                               [--bench-sets BENCH_SETS] [--bench-ref BENCH_REF] [--widen-from WIDEN_FROM]
                               [--features FEATURES] [--actions ACTIONS]
                               [--anchor-min-players ANCHOR_MIN_PLAYERS] [--table-weights TABLE_WEIGHTS]
                               [--human-share HUMAN_SHARE] [--self-play-seats SELF_PLAY_SEATS] [--icm ICM]

options:
  -h, --help            show this help message and exit
  --run RUN             Continue or name run (data\rl\<run>)
  --teacher TEACHER     New run: first imitate this bot (recommended: rock)
  --bc-tournaments BC_TOURNAMENTS
  --iterations ITERATIONS
                        Target iteration (total number, not additional)
  --tournaments TOURNAMENTS
                        Sit&Gos per iteration
  --champion CHAMPION
  --gate-schemes GATE_SCHEMES
                        0 = no admission test at the end
  --name NAME           Name in the league upon passing the exam
  --seed SEED
  --anchor-coef ANCHOR_COEF
                        Leash: Penalty for deviation from the anchor strategy (e.g., 0.3); 0 = off
  --anchor ANCHOR       Anchor '<run>:<ckpt>', default: Checkpoint 0 of this run
  --random-share RANDOM_SHARE
                        Proportion of table seats with random style bots, e.g., 0.3 (always new playing
                        styles)
  --exploit-every EXPLOIT_EVERY
                        Train and include exploiter as opponent every N iterations (0 = off)
  --exploit-iters EXPLOIT_ITERS
                        Training iterations per exploiter
  --random-formats      Per tournament randomly 2-10 players, 20-200 BB, blind speed 5-20 hands, payout
  --lr LR               Learning rate (also applies when resuming)
  --bench-every BENCH_EVERY
                        Every N iterations to the test stage (0 = never)
  --bench-sets BENCH_SETS
                        Test sets of the test stage, e.g., "praezise,pluribus"
  --bench-ref BENCH_REF
                        Comparison bot (name at the test stage), best version -> best.json
  --widen-from WIDEN_FROM
                        New run: start from '<run>@<ckpt>', network widened to --features
  --features FEATURES   With --widen-from: feature version, e.g., feat-3
  --actions ACTIONS     With --widen-from: number of actions (8 = act-2)
  --anchor-min-players ANCHOR_MIN_PLAYERS
                        Leash starts only from this many players
  --table-weights TABLE_WEIGHTS
                        With --random-formats: table size weights, e.g., "2:4,3:3,6:2"
  --human-share HUMAN_SHARE
                        Proportion of table seats with human bots (real player types, train humans-fit)
  --self-play-seats SELF_PLAY_SEATS
                        Per opponent seat probability for a prior own version
  --icm ICM             Proportion of ICM reward (change of tournament equity instead of chips), e.g., 1.0
```

## `pokercollector bench`

```text
usage: pokercollector bench [-h] {run,show,slumbot,gtow,ziele,turnier,compare} ...

positional arguments:
  {run,show,slumbot,gtow,ziele,turnier,compare}
    run                 Put candidates on the test bench
    show                Table of all results
    slumbot             Play heads-up against Slumbot (slumbot.com): absolute benchmark
    gtow                Play heads-up against GTO Wizard AI (benchmark.gtowizard.com): second benchmark,
                        AIVAT
    ziele               Scoreboard of our goals (GOALS.md) for a bot
    turnier             Enter result of a real PokerTH tournament (goal 1)
    compare             Compare two paired entries (all common test sets)

options:
  -h, --help            show this help message and exit
```

### `pokercollector bench run`

```text
usage: pokercollector bench run [-h] [--name NAME] [--sets SETS] [--exploit] spec

positional arguments:
  spec         League name (e.g. opt-1) or bot, e.g. "nn?run=pros-1@200"

options:
  -h, --help   show this help message and exit
  --name NAME  Name in the table (default: as specified)
  --sets SETS  Test sets, comma-separated; formats: hu48,3max48,10max48,turbo48,deep48,pokerth48 (or
               "formats"); larger e.g. mix960,pokerth480 (or "precise")
  --exploit    Additionally exploitability test (approx. 10 min)
```

### `pokercollector bench show`

```text
usage: pokercollector bench show [-h]

options:
  -h, --help  show this help message and exit
```

### `pokercollector bench slumbot`

```text
usage: pokercollector bench slumbot [-h] [--name NAME] [--hands HANDS] [--workers WORKERS] spec

positional arguments:
  spec               League name or bot, e.g. "nn?run=pros-r1@300"

options:
  -h, --help         show this help message and exit
  --name NAME        Name of result file (default: as specified); continues
  --hands HANDS      Additional hands (0 = evaluation only)
  --workers WORKERS  Parallel Slumbot sessions
```

### `pokercollector bench gtow`

```text
usage: pokercollector bench gtow [-h] [--name NAME] [--hands HANDS] [--workers WORKERS] [--key KEY]
                                 [--server]
                                 spec

positional arguments:
  spec               League name or bot, e.g. lynx-4-300

options:
  -h, --help         show this help message and exit
  --name NAME        Name of result file (default: as specified); continues
  --hands HANDS      Additional hands (0 = evaluation only)
  --workers WORKERS  Parallel hands (provider client uses 5)
  --key KEY          API key (otherwise GTOW_API_KEY or data/bench/gtow/api_key.txt)
  --server           Additionally retrieve server statistics (AIVAT)
```

### `pokercollector bench ziele`

```text
usage: pokercollector bench ziele [-h] [--name NAME] [--messen] [--exploit] [--slumbot SLUMBOT]
                                  [--workers WORKERS]
                                  [bot]

positional arguments:
  bot                League name or bot

options:
  -h, --help         show this help message and exit
  --name NAME        Name on the test bench (default: same as bot)
  --messen           Measure human480, nash240, kurz240 anew (approx. 15-30 min)
  --exploit          Additionally exploitability test (approx. 10-20 min)
  --slumbot SLUMBOT  Name of Slumbot result file (default: same as --name)
  --workers WORKERS
```

### `pokercollector bench turnier`

```text
usage: pokercollector bench turnier [-h] [--spieler SPIELER] [--bot BOT] [--notiz NOTIZ] [--ersetzt] platz

positional arguments:
  platz              Own place (1 = won)

options:
  -h, --help         show this help message and exit
  --spieler SPIELER  Players at start (default 6)
  --bot BOT          Which Lynx advised
  --notiz NOTIZ      e.g. 'against PokerTH bots' or 'online'
  --ersetzt          Replace last entry of this bot (e.g. incorrect automatic recognition) instead of
                     appending
```

### `pokercollector bench compare`

```text
usage: pokercollector bench compare [-h] a b

positional arguments:
  a           Name in the table
  b           Name in the table

options:
  -h, --help  show this help message and exit
```

## `pokercollector data`

```text
usage: pokercollector data [-h] {pluribus,humans,humandata,humanpublic,agree} ...

positional arguments:
  {pluribus,humans,humandata,humanpublic,agree}
    pluribus            Replay Pluribus hands -> data\datasets\pluribus.npz
    humans              Real Players (HandHQ): Frequencies per player and player types
    humandata           HandHQ showdown decisions with known cards as features + action (H11 human model)
    humanpublic         HandHQ: ALL card-free decisions with folds (fold model, H11 step 2b)
    agree               How often does a network make the decisions in the dataset?

options:
  -h, --help            show this help message and exit
```

### `pokercollector data pluribus`

```text
usage: pokercollector data pluribus [-h] [--source SOURCE]

options:
  -h, --help       show this help message and exit
  --source SOURCE  Folder with .phh files (default: data\external\phh-dataset\data\pluribus)
```

### `pokercollector data humans`

```text
usage: pokercollector data humans [-h] [--sets SETS] [--name NAME] [--types TYPES] [--min-hands MIN_HANDS]
                                  [--max-files MAX_FILES] [--workers WORKERS]

options:
  -h, --help            show this help message and exit
  --sets SETS           Folder under data\external\phh-dataset\data\handhq, comma-separated (default: all)
  --name NAME           Result data\humans\<name>.json
  --types TYPES         Number of player types
  --min-hands MIN_HANDS
                        Players with fewer hands do not count towards types
  --max-files MAX_FILES
                        only the first N files (test)
  --workers WORKERS     parallel processes (RAM!)
```

### `pokercollector data humandata`

```text
usage: pokercollector data humandata [-h] [--sets SETS] [--out OUT] [--max-files MAX_FILES]
                                     [--files-per-shard FILES_PER_SHARD] [--workers WORKERS]

options:
  -h, --help            show this help message and exit
  --sets SETS           Folder under data\external\phh-dataset\data\handhq, comma-separated (default: all)
  --out OUT             Target folder (default data\humans\actions)
  --max-files MAX_FILES
                        only the first N files (test)
  --files-per-shard FILES_PER_SHARD
                        Files per shard human-<nr>.npz
  --workers WORKERS     Parallel processes
```

### `pokercollector data humanpublic`

```text
usage: pokercollector data humanpublic [-h] [--sets SETS] [--out OUT] [--max-files MAX_FILES]
                                       [--files-per-shard FILES_PER_SHARD] [--workers WORKERS]

options:
  -h, --help            show this help message and exit
  --sets SETS           Folder under data\external\phh-dataset\data\handhq, comma-separated (default: all)
  --out OUT             Target folder (default data\humans\actions, files public-<nr>.npz)
  --max-files MAX_FILES
                        only the first N files (test)
  --files-per-shard FILES_PER_SHARD
  --workers WORKERS     Parallel processes
```

### `pokercollector data agree`

```text
usage: pokercollector data agree [-h] [--ckpt CKPT] [--dataset DATASET] [--players PLAYERS] run

positional arguments:
  run

options:
  -h, --help         show this help message and exit
  --ckpt CKPT        Checkpoint(s), comma-separated, e.g. 0,100,200
  --dataset DATASET
  --players PLAYERS
```

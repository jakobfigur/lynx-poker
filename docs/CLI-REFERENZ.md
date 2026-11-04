# CLI-Referenz

Automatisch erzeugt aus dem argparse-Parser von `pokercollector` (`scripts/gen_reference.py`). Aufruf unter Windows mit `pc.cmd <befehl> ...`, unter Linux/macOS mit `./pc.sh <befehl> ...`.

## Befehlsuebersicht

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

Visuelle Erfassung von PokerTH-Partien

positional arguments:
  {calibrate,analyze,windows,live,live-replay,leiste-demo,reconstruct,report,inspect-reference,compare,advise,harvest-cards,verify,sim,play,play-stats,league,train,bench,data}
    calibrate           Screenshot analysieren, Overlay-Bild erzeugen
    analyze             Video oder Screenshot-Ordner auswerten (neue Sitzung)
    windows             Fenster auflisten
    live                Fenster live erfassen, Sitzungen automatisch starten/beenden
    live-replay         Aufgezeichnete Sitzung wie live abspielen: Vorschlaege + Gegnermodell
    leiste-demo         Lynx-Leiste ohne Tisch vorfuehren (Farben, Toene, Position)
    reconstruct         Haende einer Sitzung neu rekonstruieren
    report              Handbericht einer Sitzung ausgeben
    inspect-reference   Schema einer PokerTH-Logdatei anzeigen
    compare             Sitzung mit PokerTH-Export vergleichen
    advise              Baseline-Empfehlung fuer einen Screenshot
    harvest-cards       Kartenvorlagen aus Screenshots lernen (interaktiv)
    verify              Pruefsummen einer Sitzung pruefen
    sim                 Simulator, Bots und Bewertung
    play                Du gegen die Bots (Terminal)
    play-stats          Auswertung deiner Partien gegen die Bots
    league              Liga, Rating, Benchmark
    train               Bots selbst verbessern
    bench               Pruefstand: feste Testsets fuer jeden Kandidaten
    data                Fremde Handhistorien (PHH) einlesen und auswerten

options:
  -h, --help            show this help message and exit
  --profile PROFILE     Pfad zu einem Tischprofil (JSON); Standard: eingebautes PokerTH-Web-Profil
  --allow-sleep         Standby waehrend des Laufs erlauben (Standard: wach halten, damit lange Laeufe nicht
                        abbrechen)
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
  --step STEP          Sekunden zwischen analysierten Videoframes
  --interval INTERVAL  angenommener Abstand zwischen Screenshots
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
  --window WINDOW       Teil des Fenstertitels
  --hwnd HWND
  --fps FPS
  --segment SEGMENT     Segmentlaenge in Sekunden
  --stop-after STOP_AFTER
                        Sitzung endet nach so vielen Sekunden ohne Tisch
  --max-seconds MAX_SECONDS
  --no-video            nur Journal, kein Video speichern
  --allow-background    auch aufnehmen, wenn das Fenster nicht im Vordergrund ist (Risiko: verdeckte
                        Inhalte)
  --advice              Vorschlag anzeigen, wenn du dran bist
  --leiste              Vorschlag zusaetzlich in der Lynx-Leiste ueber der Taskleiste (mit Ton; setzt
                        --advice)
  --still               Leiste ohne Ton
  --kein-eintrag        erkanntes Turnierende nicht automatisch in die Zieltafel eintragen
  --mischen             Vorschlag aus der gemischten Strategie ziehen statt der wahrscheinlichsten Aktion
  --agent AGENT         Liga-Name oder Agent fuer Vorschlaege (Standard lynx-4-300 = bester Bot)
```

## `pokercollector live-replay`

```text
usage: pokercollector live-replay [-h] [--agent AGENT] session

positional arguments:
  session        Ordner, Teil des Namens oder 'last'

options:
  -h, --help     show this help message and exit
  --agent AGENT  Liga-Name oder Agent
```

## `pokercollector leiste-demo`

```text
usage: pokercollector leiste-demo [-h] [--still] [--sekunden SEKUNDEN]

options:
  -h, --help           show this help message and exit
  --still              ohne Ton
  --sekunden SEKUNDEN  Anzeigedauer je Beispiel
```

## `pokercollector reconstruct`

```text
usage: pokercollector reconstruct [-h] session

positional arguments:
  session     Ordner, Teil des Namens oder 'last'

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
    agents              verfuegbare Bots
    match               Bots gegeneinander bewerten
    hand                eine Hand spielen und zeigen
    tournament          Sit&Go-Turniere (wie PokerTH) zwischen Bots
    pushfold            Nash-Push/Fold-Ranges anzeigen
    review              eigene Entscheidungen einer Sitzung mit einem Agenten vergleichen

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
  --agents AGENTS  Komma-Liste, z. B. tag,tag:tag2,random
  --seed SEED
  --sb SB
  --bb BB
  --stack STACK    Startstack in Big Blinds
  --hands HANDS    Anzahl Kartenblaetter
  --no-duplicate
  --show SHOW      so viele Handverlaeufe ausgeben
```

### `pokercollector sim hand`

```text
usage: pokercollector sim hand [-h] [--agents AGENTS] [--seed SEED] [--sb SB] [--bb BB] [--stack STACK]
                               [--button BUTTON]

options:
  -h, --help       show this help message and exit
  --agents AGENTS  Komma-Liste, z. B. tag,tag:tag2,random
  --seed SEED
  --sb SB
  --bb BB
  --stack STACK    Startstack in Big Blinds
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
                        Anzahl Kartenschemata (x Spielerzahl bei Duplicate)
  --seed SEED
  --stack STACK         Startchips
  --blinds BLINDS       Start-Blinds SB/BB
  --level-hands LEVEL_HANDS
                        Haende bis zur Verdopplung der Blinds
  --payouts PAYOUTS     Prozent je Platz, z. B. 100 (Sieger bekommt alles)
  --no-duplicate
```

### `pokercollector sim pushfold`

```text
usage: pokercollector sim pushfold [-h] [--stack STACK] [--behind BEHIND] [--caller CALLER] [--overview]

options:
  -h, --help       show this help message and exit
  --stack STACK    effektiver Stack in BB
  --behind BEHIND  Spieler hinter dem Pusher (1 = SB gegen BB)
  --caller CALLER  welcher Caller (0 = erster hinter dem Pusher)
  --overview       Push-Prozente fuer alle Stacks/Positionen
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
                        Bots/Ligaspieler, Komma-Liste
  --name NAME
  --blinds BLINDS
  --stack STACK         Turnier: Startchips
  --level-hands LEVEL_HANDS
  --payouts PAYOUTS
  --stack-bb STACK_BB   Cash: Stack in BB (Rebuy auf diesen Wert)
  --hands HANDS         Cash: maximale Handzahl
  --seed SEED
  --coach               nach deiner Entscheidung Push/Fold-Hinweis zeigen
  --unrated             Turnier nicht in die Liga eintragen
  --ascii               Kartenfarben als Buchstaben
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
    show                Tabelle + Verlaufsgrafik (report.html)
    add                 Bot-Version eintragen, z. B. add tag-v2 'tag?bluff=0.2'
    retire              Bot aus automatischen Runden nehmen
    run                 Ligaspiele zwischen den Bots austragen
    bench               Benchmark gegen feste Gegner (alle Bots oder einer)

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
    cem                 Stil-Parameter optimieren, Aufnahmepruefung, ggf. in die Liga
    gate                Aufnahmepruefung: Kandidat gegen Titelverteidiger
    bc                  Lernender Bot, Schritt 1: Lehrer-Bot nachahmen -> Checkpoint 0
    cfr                 Gleichgewicht per Monte-Carlo-CFR (Pluribus-Verfahren)
    deepcfr             Deep CFR: Gleichgewicht mit neuronalen Netzen statt Tabelle
    exploit             Ausbeuter-Test: wie stark laesst sich ein Bot gezielt ausnutzen?
    humans-fit          Mensch-Bots: Stilbots an echte Spielertypen (data humans) anpassen
    valuedata           Wertnetz-Daten: Situationen zu Strassenbeginn exakt loesen (Meilenstein 3)
    valuenet            Wertnetz aus valuedata-Scherben trainieren (lokal klein; gross auf Kaggle)
    teacher-collect     Suche als Lehrer (H5): Suchentscheidungen als weiche Ziele sammeln
    teacher-fit         Suche als Lehrer (H5): Schueler auf gesammelte Ziele nachtrainieren (mit KL-Leine)
    humanfold           Fold-Modell aus den kartenfreien HandHQ-Zeilen (H11 Schritt 2b)
    rl                  Lernender Bot, Schritt 2: Selbstspiel mit PPO (setzt einen Lauf fort)

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
  --start START         Ausgangsstil
  --generations GENERATIONS
  --population POPULATION
  --schemes SCHEMES     Kartenschemata je Generation (x6 Turniere)
  --gate-schemes GATE_SCHEMES
  --champion CHAMPION   Ligaspieler, den der Kandidat schlagen muss
  --name NAME           Name in der Liga (Standard: opt-<Datum>)
  --seed SEED
  --resume RESUME       Trainingsordner (data\train\...) fortsetzen
  --opponents {league,fixed}
                        league = Tische aus allen aktiven Ligabots, starke oefter, mit Self-Play (Standard);
                        fixed = immer rock/tag/lag/station/maniac
```

### `pokercollector train gate`

```text
usage: pokercollector train gate [-h] [--from FROM_DIR] [--champion CHAMPION] [--schemes SCHEMES]
                                 [--seed SEED] [--opponents {league,fixed}]
                                 [candidate]

positional arguments:
  candidate             Bot-Spezifikation in Anfuehrungszeichen, z. B. "tag?push_bb=15&bluff=0.2"

options:
  -h, --help            show this help message and exit
  --from FROM_DIR       Kandidat aus einem Trainingsordner (result.json) nehmen
  --champion CHAMPION
  --schemes SCHEMES
  --seed SEED           anderer Seed = andere, frische Kartenschemata
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
  --run RUN             Name des Laufs unter data\rl (Standard: nn-<Datum>)
  --bc-tournaments BC_TOURNAMENTS
  --dataset DATASET     statt Lehrer-Bot: Datensatz unter data\datasets, z. B. pluribus
  --players PLAYERS     nur diese Spieler des Datensatzes, Komma-getrennt, z. B. Pluribus
  --epochs EPOCHS
  --features FEATURES   Merkmalsversion des Datensatzes (Standard: aktuelle)
```

### `pokercollector train cfr`

```text
usage: pokercollector train cfr [-h] [--run RUN] [--rounds ROUNDS] [--traversals TRAVERSALS]
                                [--bench-every BENCH_EVERY] [--seed SEED]

options:
  -h, --help            show this help message and exit
  --run RUN
  --rounds ROUNDS       Zielrunde (Gesamtzahl)
  --traversals TRAVERSALS
                        Durchlaeufe je Prozess und Runde
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
                        Ziel-Iteration (Gesamtzahl)
  --traversals TRAVERSALS
                        Durchlaeufe je Prozess und Iteration
  --snapshot-every SNAPSHOT_EVERY
  --seed SEED
  --buffer BUFFER       Eintraege je Datenpuffer (RAM ca. 220 MB je 1 Mio.; 2 Puffer)
```

### `pokercollector train exploit`

```text
usage: pokercollector train exploit [-h] [--init INIT] [--iterations ITERATIONS] [--schemes SCHEMES] target

positional arguments:
  target                Bot-Spezifikation, z. B. rock oder "nn?run=pros-1@200"

options:
  -h, --help            show this help message and exit
  --init INIT           Startpunkt des Ausbeuters (Lauf@Checkpoint)
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
  --name NAME           Ergebnis data\humans\<name>.json
  --generations GENERATIONS
  --population POPULATION
  --hands HANDS         Haende je Messung
```

### `pokercollector train valuedata`

```text
usage: pokercollector train valuedata [-h] [--n N] [--seed SEED] [--iters ITERS] [--workers WORKERS]
                                      [--threads THREADS] [--out OUT] [--vnet VNET]
                                      {river,turn,flop,river-leaf,turn-leaf}

positional arguments:
  {river,turn,flop,river-leaf,turn-leaf}
                        Strasse, zu deren Beginn bewertet wird; river-leaf = River-Anfaenge aus echten Turn-
                        Suchen (je Seed bis 24 Zeilen), turn-leaf = Turn-Anfaenge aus echten Flop-Suchen,
                        River per Wertnetz (je Seed bis 12 Zeilen)

options:
  -h, --help            show this help message and exit
  --n N                 Situationen in dieser Scherbe
  --seed SEED           erster Seed (Scherben: seed, seed+n, ...)
  --iters ITERS         CFR+-Iterationen (Standard river 300, turn 150, flop 60)
  --workers WORKERS     Prozesse
  --threads THREADS     numba-Faeden je Prozess (Standard: alle)
  --out OUT             Zieldatei .npz (Standard data\valuenet\<street>-<seed>.npz)
  --vnet VNET           River-Wertnetz als Blatt (turn/flop/turn-leaf; Standard bei turn-leaf: vnet-river-1)
```

### `pokercollector train valuenet`

```text
usage: pokercollector train valuenet [-h] --data DATA [--out OUT] [--epochs EPOCHS] [--batch BATCH]
                                     [--lr LR] [--width WIDTH] [--depth DEPTH] [--resume RESUME]

options:
  -h, --help       show this help message and exit
  --data DATA      Glob auf .npz-Scherben, z. B. data\valuenet\river-*.npz
  --out OUT        Name unter data\valuenet\<out>.pt oder Pfad
  --epochs EPOCHS
  --batch BATCH
  --lr LR
  --width WIDTH
  --depth DEPTH
  --resume RESUME  Checkpoint, von dem weitertrainiert wird
```

### `pokercollector train teacher-collect`

```text
usage: pokercollector train teacher-collect [-h] [--search SEARCH] [--student STUDENT]
                                            [--opponents OPPONENTS] [--stacks STACKS] [--hands HANDS]
                                            [--seed SEED] --out OUT

options:
  -h, --help            show this help message and exit
  --search SEARCH       Spezifikation der Suche (Lehrer)
  --student STUDENT     Schueler-Netz (bestimmt den Merkmalsraum)
  --opponents OPPONENTS
                        Gegner-Spezifikationen, Komma-getrennt
  --stacks STACKS       Stacktiefen in BB, Komma-getrennt
  --hands HANDS         Kartenblaetter je Match (duplicate -> doppelt so viele Haende)
  --seed SEED
  --out OUT             Zieldatei .npz (z. B. data\teacher\t1-seed1.npz)
```

### `pokercollector train teacher-fit`

```text
usage: pokercollector train teacher-fit [-h] --data DATA [--student STUDENT] --out-run OUT_RUN
                                        [--epochs EPOCHS] [--batch BATCH] [--lr LR] [--kl KL]

options:
  -h, --help         show this help message and exit
  --data DATA        Glob auf Lehrer-.npz, z. B. data\teacher\t1-*.npz
  --student STUDENT  <Lauf>@<Checkpoint>
  --out-run OUT_RUN  neuer Lauf unter data\rl\<out-run> (ckpt_000001.pt)
  --epochs EPOCHS
  --batch BATCH
  --lr LR
  --kl KL            Gewicht der KL-Leine an den Anker (0 = aus)
```

### `pokercollector train humanfold`

```text
usage: pokercollector train humanfold [-h] [--rows ROWS] [--out OUT] [--max-rows MAX_ROWS]
                                      [--max-shards MAX_SHARDS] [--epochs EPOCHS]

options:
  -h, --help            show this help message and exit
  --rows ROWS           Ordner mit public-*.npz (Standard data\humans\actions)
  --out OUT             Name unter data\humans\<out>.npz
  --max-rows MAX_ROWS
  --max-shards MAX_SHARDS
                        Speicher: Scherben begrenzen
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
  --run RUN             Lauf fortsetzen bzw. benennen (data\rl\<run>)
  --teacher TEACHER     neuer Lauf: zuerst diesen Bot nachahmen (empfohlen: rock)
  --bc-tournaments BC_TOURNAMENTS
  --iterations ITERATIONS
                        Ziel-Iteration (Gesamtzahl, nicht zusaetzlich)
  --tournaments TOURNAMENTS
                        Sit&Gos je Iteration
  --champion CHAMPION
  --gate-schemes GATE_SCHEMES
                        0 = keine Aufnahmepruefung am Ende
  --name NAME           Name in der Liga bei bestandener Pruefung
  --seed SEED
  --anchor-coef ANCHOR_COEF
                        Leine: Strafe fuer Abweichung von der Ankerstrategie (z. B. 0.3); 0 = aus
  --anchor ANCHOR       Anker '<lauf>:<ckpt>', Standard: Checkpoint 0 dieses Laufs
  --random-share RANDOM_SHARE
                        Anteil Tischplaetze mit Zufalls-Stilbots, z. B. 0.3 (immer neue Spielweisen)
  --exploit-every EXPLOIT_EVERY
                        alle N Iterationen Ausbeuter trainieren und als Gegner aufnehmen (0 = aus)
  --exploit-iters EXPLOIT_ITERS
                        Trainingsiterationen je Ausbeuter
  --random-formats      je Turnier zufaellig 2-10 Spieler, 20-200 BB, Blind-Tempo 5-20 Haende, Auszahlung
  --lr LR               Lernrate (gilt auch beim Fortsetzen)
  --bench-every BENCH_EVERY
                        alle N Iterationen auf den Pruefstand (0 = nie)
  --bench-sets BENCH_SETS
                        Testsets des Pruefstands, z. B. "praezise,pluribus"
  --bench-ref BENCH_REF
                        Vergleichsbot (Name auf dem Pruefstand), bester Stand -> best.json
  --widen-from WIDEN_FROM
                        neuer Lauf: Start von '<lauf>@<ckpt>', Netz aufgeweitet auf --features
  --features FEATURES   mit --widen-from: Merkmalsversion, z. B. feat-3
  --actions ACTIONS     mit --widen-from: Aktionszahl (8 = act-2)
  --anchor-min-players ANCHOR_MIN_PLAYERS
                        Leine erst ab so vielen Spielern
  --table-weights TABLE_WEIGHTS
                        mit --random-formats: Tischgroessen-Gewichte, z. B. "2:4,3:3,6:2"
  --human-share HUMAN_SHARE
                        Anteil Tischplaetze mit Mensch-Bots (echte Spielertypen, train humans-fit)
  --self-play-seats SELF_PLAY_SEATS
                        je Gegnerplatz Wahrscheinlichkeit fuer eine fruehere eigene Version
  --icm ICM             Anteil ICM-Belohnung (Aenderung des Turnier-Eigenkapitals statt Chips), z. B. 1.0
```

## `pokercollector bench`

```text
usage: pokercollector bench [-h] {run,show,slumbot,gtow,ziele,turnier,compare} ...

positional arguments:
  {run,show,slumbot,gtow,ziele,turnier,compare}
    run                 Kandidaten auf den Pruefstand stellen
    show                Tabelle aller Ergebnisse
    slumbot             Heads-up gegen Slumbot (slumbot.com) spielen: absoluter Massstab
    gtow                Heads-up gegen GTO Wizard AI (benchmark.gtowizard.com) spielen: 2. Massband, AIVAT
    ziele               Anzeigetafel unserer Ziele (ZIELE.md) fuer einen Bot
    turnier             Ergebnis eines echten PokerTH-Turniers eintragen (Ziel 1)
    compare             Zwei Eintraege gepaart vergleichen (alle gemeinsamen Testsets)

options:
  -h, --help            show this help message and exit
```

### `pokercollector bench run`

```text
usage: pokercollector bench run [-h] [--name NAME] [--sets SETS] [--exploit] spec

positional arguments:
  spec         Liga-Name (z. B. opt-1) oder Bot, z. B. "nn?run=pros-1@200"

options:
  -h, --help   show this help message and exit
  --name NAME  Name in der Tabelle (Standard: wie angegeben)
  --sets SETS  Testsets, Komma-getrennt; Formate: hu48,3max48,10max48,turbo48,deep48,pokerth48 (oder
               "formate"); groesser z. B. mix960,pokerth480 (oder "praezise")
  --exploit    zusaetzlich Ausbeuter-Test (ca. 10 min)
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
  spec               Liga-Name oder Bot, z. B. "nn?run=pros-r1@300"

options:
  -h, --help         show this help message and exit
  --name NAME        Name der Ergebnisdatei (Standard: wie angegeben); setzt fort
  --hands HANDS      weitere Haende (0 = nur Auswertung)
  --workers WORKERS  parallele Slumbot-Sitzungen
```

### `pokercollector bench gtow`

```text
usage: pokercollector bench gtow [-h] [--name NAME] [--hands HANDS] [--workers WORKERS] [--key KEY]
                                 [--server]
                                 spec

positional arguments:
  spec               Liga-Name oder Bot, z. B. lynx-4-300

options:
  -h, --help         show this help message and exit
  --name NAME        Name der Ergebnisdatei (Standard: wie angegeben); setzt fort
  --hands HANDS      weitere Haende (0 = nur Auswertung)
  --workers WORKERS  parallele Haende (Anbieter-Client nutzt 5)
  --key KEY          API-Schluessel (sonst GTOW_API_KEY oder data/bench/gtow/api_key.txt)
  --server           zusaetzlich die Serverstatistik (AIVAT) abrufen
```

### `pokercollector bench ziele`

```text
usage: pokercollector bench ziele [-h] [--name NAME] [--messen] [--exploit] [--slumbot SLUMBOT]
                                  [--workers WORKERS]
                                  [bot]

positional arguments:
  bot                Liga-Name oder Bot

options:
  -h, --help         show this help message and exit
  --name NAME        Name auf dem Pruefstand (Standard: wie bot)
  --messen           mensch480, nash240, kurz240 neu messen (ca. 15-30 min)
  --exploit          zusaetzlich Ausbeuter-Test (ca. 10-20 min)
  --slumbot SLUMBOT  Name der Slumbot-Ergebnisdatei (Standard: wie --name)
  --workers WORKERS
```

### `pokercollector bench turnier`

```text
usage: pokercollector bench turnier [-h] [--spieler SPIELER] [--bot BOT] [--notiz NOTIZ] [--ersetzt] platz

positional arguments:
  platz              eigener Platz (1 = gewonnen)

options:
  -h, --help         show this help message and exit
  --spieler SPIELER  Spieler am Start (Standard 6)
  --bot BOT          welcher Lynx beraten hat
  --notiz NOTIZ      z. B. 'gegen PokerTH-Bots' oder 'online'
  --ersetzt          den letzten Eintrag dieses Bots (z. B. falsche automatische Erkennung) ersetzen statt
                     anhaengen
```

### `pokercollector bench compare`

```text
usage: pokercollector bench compare [-h] a b

positional arguments:
  a           Name in der Tabelle
  b           Name in der Tabelle

options:
  -h, --help  show this help message and exit
```

## `pokercollector data`

```text
usage: pokercollector data [-h] {pluribus,humans,humandata,humanpublic,agree} ...

positional arguments:
  {pluribus,humans,humandata,humanpublic,agree}
    pluribus            Pluribus-Haende nachspielen -> data\datasets\pluribus.npz
    humans              Echte Spieler (HandHQ): Haeufigkeiten je Spieler und Spielertypen
    humandata           HandHQ-Showdown-Entscheidungen mit bekannten Karten als Merkmale+Aktion (H11
                        Menschenmodell)
    humanpublic         HandHQ: ALLE Entscheidungen kartenfrei mit Folds (Fold-Modell, H11 Schritt 2b)
    agree               Wie oft trifft ein Netz die Entscheidungen im Datensatz?

options:
  -h, --help            show this help message and exit
```

### `pokercollector data pluribus`

```text
usage: pokercollector data pluribus [-h] [--source SOURCE]

options:
  -h, --help       show this help message and exit
  --source SOURCE  Ordner mit .phh-Dateien (Standard: data\external\phh-dataset\data\pluribus)
```

### `pokercollector data humans`

```text
usage: pokercollector data humans [-h] [--sets SETS] [--name NAME] [--types TYPES] [--min-hands MIN_HANDS]
                                  [--max-files MAX_FILES] [--workers WORKERS]

options:
  -h, --help            show this help message and exit
  --sets SETS           Ordner unter data\external\phh-dataset\data\handhq, Komma-getrennt (Standard: alle)
  --name NAME           Ergebnis data\humans\<name>.json
  --types TYPES         Anzahl Spielertypen
  --min-hands MIN_HANDS
                        Spieler mit weniger Haenden zaehlen nicht fuer Typen
  --max-files MAX_FILES
                        nur die ersten N Dateien (Test)
  --workers WORKERS     parallele Prozesse (RAM!)
```

### `pokercollector data humandata`

```text
usage: pokercollector data humandata [-h] [--sets SETS] [--out OUT] [--max-files MAX_FILES]
                                     [--files-per-shard FILES_PER_SHARD] [--workers WORKERS]

options:
  -h, --help            show this help message and exit
  --sets SETS           Ordner unter data\external\phh-dataset\data\handhq, Komma-getrennt (Standard: alle)
  --out OUT             Zielordner (Standard data\humans\actions)
  --max-files MAX_FILES
                        nur die ersten N Dateien (Test)
  --files-per-shard FILES_PER_SHARD
                        Dateien je Scherbe human-<nr>.npz
  --workers WORKERS     parallele Prozesse
```

### `pokercollector data humanpublic`

```text
usage: pokercollector data humanpublic [-h] [--sets SETS] [--out OUT] [--max-files MAX_FILES]
                                       [--files-per-shard FILES_PER_SHARD] [--workers WORKERS]

options:
  -h, --help            show this help message and exit
  --sets SETS           Ordner unter data\external\phh-dataset\data\handhq, Komma-getrennt (Standard: alle)
  --out OUT             Zielordner (Standard data\humans\actions, Dateien public-<nr>.npz)
  --max-files MAX_FILES
                        nur die ersten N Dateien (Test)
  --files-per-shard FILES_PER_SHARD
  --workers WORKERS     parallele Prozesse
```

### `pokercollector data agree`

```text
usage: pokercollector data agree [-h] [--ckpt CKPT] [--dataset DATASET] [--players PLAYERS] run

positional arguments:
  run

options:
  -h, --help         show this help message and exit
  --ckpt CKPT        Checkpoint(s), Komma-getrennt, z. B. 0,100,200
  --dataset DATASET
  --players PLAYERS
```

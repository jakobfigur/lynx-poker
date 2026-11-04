# API Reference

Automatically generated from the source code (`scripts/gen_reference.py`): 64 modules, 16920 lines. Per module: purpose, constants, classes with methods, functions with signature and first docstring line. The explanation of the relationships is in `TECHNICAL_DOCUMENTATION.md`.

## Contents

- pokercollector (capture, reconstruction, operation): `__init__`, `advisor`, `analyzer`, `capture`, `cards`, `cli`, `compare`, `fastpoker`, `geometry`, `glyphs`, `journal`, `layout`, `ocr`, `overlay`, `parse`, `pipeline`, `poker`, `profile`, `__init__`, `reconstruct`, `reference`, `report`, `stabilize`, `system`
- pokercollector.ai (AI: engine, bots, training, search, value nets): `__init__`, `agents`, `bench`, `bpranges`, `cfr`, `confirm`, `deepcfr`, `engine`, `evaluate`, `features`, `gtow`, `human`, `humanbots`, `humandata`, `humanfold`, `humans`, `hupreflop`, `husearch`, `icm`, `league`, `live`, `nn_agent`, `observation`, `opponents`, `optimize`, `phh`, `play`, `pushfold`, `ranges`, `recording`, `replay`, `rl`, `search`, `slumbot`, `tables`, `teacher`, `tournament`, `valuedata`, `valuenet`, `ziele`

## pokercollector (capture, reconstruction, operation)

### `pokercollector`

File `collector/src/pokercollector/__init__.py` · 2 lines

### `pokercollector.advisor`

File `collector/src/pokercollector/advisor.py` · 126 lines

Baseline decision aid: equity against random hands + pot odds.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `ADVISOR_VERSION` | `'baseline-equity-1'` | 17 |

**Class `GameState`** · line 21


**Class `Advice`** · line 34

- `to_dict(self)` · L. 44

**Funktionen**

- `state_from_snapshot_state(st: dict, hero_seat: int=0) -> GameState` · L. 48: Builds the game state from the stabilized field state (Stabilizer.state()).
- `advise(gs: GameState, iterations: int=2500, seed: int=0, margin: float=0.05) -> Advice` · L. 82

### `pokercollector.analyzer`

File `collector/src/pokercollector/analyzer.py` · 352 lines

Frame -> TableSnapshot: all visible fields with raw value, confidence and image region.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `ANALYZER_VERSION` | `f'analyzer-1/{OCR_VERSION}/{CARDS_VERSION}'` | 26 |
| `_STACK_LIKE` | `re.compile('[$S§]\\s*[0-9OolI]¦^\\s*[0-9][0-9 .,]*\\s*$')` | 57 |

**Class `FieldObs`** · line 30


**Class `TableSnapshot`** · line 40

- `get(self, key: str, default=None)` · L. 49
- `set(self, key: str, value, **kw)` · L. 53

**Class `FrameAnalyzer`** · line 110

- `__init__(self, profile: Profile, ocr: RegionOcr, cards: CardReader)` · L. 111
- `reset(self)` · L. 117: New session/new table: forget learned seat positions.
- `analyze(self, frame: np.ndarray, frame_index: int=0, t_mono: float=0.0, t_wall: float=0.0) -> TableSnapshot` · L. 121
- internal methods: `_info_row`, `_pot`, `_board`, `_action_bar`, `_seat`

Internal helpers: `_up`, `_strict_money`, `_has_money`, `_has_name_and_stack`, `_panel_regions`, `_yellow_border_share`, `_panel_tint`

### `pokercollector.capture`

File `collector/src/pokercollector/capture.py` · 431 lines

Image sources and segmented capture.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `_MASK_WINDOWS` | `set()` | 44 |
| `_MASK_LOCK` | `threading.Lock()` | 45 |
| `MASK_RING_PX` | `3` | 46 |

**Class `Frame`** · line 32


**Class `VideoFileSource`** · line 92

- `__init__(self, path: str | Path, step_s: float | None=None, start_wall: float | None=None)` · L. 93
- `describe(self) -> dict` · L. 104
- internal methods: `__iter__`

**Class `SessionVideoSource`** · line 125
: Plays video segments of a live session sequentially - with the REAL capture times per image from segment_XXXX.frames.jsonl (for post-analysis, e.g. after an analysis error).

- `__init__(self, session_dir: str | Path)` · L. 129
- `describe(self) -> dict` · L. 138
- internal methods: `__iter__`

**Class `ImageDirSource`** · line 159

- `__init__(self, path: str | Path, interval_s: float=1.0)` · L. 160
- `describe(self) -> dict` · L. 166
- internal methods: `__iter__`

**Class `WindowInfo`** · line 182


**Class `WindowSource`** · line 293
: Reads the client area of a window at fixed frame rate.

- `__init__(self, hwnd: int, fps: float=10.0, max_seconds: float | None=None, require_foreground: bool=True)` · L. 296
- `describe(self) -> dict` · L. 310
- internal methods: `__iter__`

**Class `SegmentRecorder`** · line 369
: Writes frames to short video segments plus timestamp sidecar (JSONL).

- `__init__(self, video_dir: Path, fps: float, segment_s: float=120.0, codec: str='mp4v')` · L. 376
- `current_segment(self) -> str | None` · L. 390
- `write(self, frame: Frame) -> tuple[str, int]` · L. 408
- `close(self)` · L. 424
- internal methods: `_open`

**Funktionen**

- `register_mask_window(hwnd: int) -> None` · L. 49: From now on, cut out windows (e.g. the Lynx bar) from every WindowSource capture.
- `unregister_mask_window(hwnd: int) -> None` · L. 56
- `mask_windows() -> list[int]` · L. 61
- `apply_masks(img: np.ndarray, origin: tuple[int, int], rects: list[tuple[int, int, int, int]], ring: int=MASK_RING_PX) -> list[list[int]]` · L. 66: Cuts out screen rectangles (x, y, w, h) from `img`, whose upper-left corner lies at `origin`.
- `list_windows(title_filter: str='') -> list[WindowInfo]` · L. 224
- `window_info(hwnd: int, title: str='', fg: int | None=None) -> WindowInfo | None` · L. 254
- `window_rect(hwnd: int) -> tuple[int, int, int, int] | None` · L. 277: Whole window in screen pixels (x, y, w, h); None if closed, invisible or minimized.

Internal helpers: `_user32`, `_ensure_dpi_aware`

### `pokercollector.cards`

File `collector/src/pokercollector/cards.py` · 307 lines

Card recognition: slot state (empty / backside / open), rank and suit.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `CARDS_VERSION` | `'cards-1'` | 24 |
| `GLYPH_SIZE` | `(20, 28)` | 25 |

**Class `CardRead`** · line 29


**Class `SlotRead`** · line 42


**Class `TemplateStore`** · line 56
: Learned glyph templates saved on the hard drive (PNG, 255 = ink).

- `__init__(self, root: Path | None)` · L. 59
- `match(self, kind: str, glyph: np.ndarray) -> tuple[str | None, float, float]` · L. 77: (best label, score, distance to second-best label).
- `add(self, kind: str, label: str, glyph: np.ndarray, name: str) -> Path | None` · L. 96

**Class `CardReader`** · line 149

- `__init__(self, profile: Profile, ocr: RegionOcr | None, templates: TemplateStore | None=None)` · L. 150
- `read_face(self, frame: np.ndarray, rect: Rect) -> CardRead` · L. 201
- `read_region(self, frame: np.ndarray, hsv: np.ndarray, region: Rect, scale: float) -> SlotRead` · L. 293
- internal methods: `_face_rects`, `_count_backs`

**Funktionen**

- `valid_rank(r: str | None) -> bool` · L. 305

Internal helpers: `_normalize_glyph`, `_suit_heuristic`, `_rank_text_ok`

### `pokercollector.cli`

File `collector/src/pokercollector/cli.py` · 1460 lines

Command line. Call: pokercollector <command> ... (or start.cmd on the stick).

**Funktionen**

- `data_dir() -> Path` · L. 17
- `sessions_dir() -> Path` · L. 25
- `templates_dir() -> Path` · L. 31
- `cmd_calibrate(a)` · L. 53
- `cmd_analyze(a)` · L. 73
- `cmd_windows(a)` · L. 104
- `cmd_live(a)` · L. 125
- `cmd_humans_fit(a)` · L. 241
- `cmd_leiste_demo(a)` · L. 258
- `cmd_live_replay(a)` · L. 278
- `cmd_reconstruct(a)` · L. 295
- `cmd_report(a)` · L. 307
- `cmd_inspect_reference(a)` · L. 312
- `cmd_compare(a)` · L. 318
- `cmd_advise(a)` · L. 333
- `cmd_harvest_cards(a)` · L. 352: Saves rank/suit glyphs of recognized exposed cards as templates.
- `cmd_sim_agents(a)` · L. 388
- `cmd_sim_match(a)` · L. 396
- `cmd_sim_hand(a)` · L. 425
- `cmd_sim_tournament(a)` · L. 437
- `cmd_sim_pushfold(a)` · L. 472
- `cmd_sim_review(a)` · L. 487
- `cmd_play(a)` · L. 510
- `cmd_play_stats(a)` · L. 554
- `cmd_league(a)` · L. 559
- `cmd_data(a)` · L. 611
- `cmd_bench(a)` · L. 690
- `cmd_cfr(a)` · L. 793
- `cmd_deepcfr(a)` · L. 820
- `cmd_exploit(a)` · L. 843
- `cmd_train_nn(a)` · L. 860
- `cmd_valuedata(a)` · L. 940
- `cmd_teacher(a)` · L. 953
- `cmd_humanfold(a)` · L. 975
- `cmd_valuenet(a)` · L. 984
- `cmd_train(a)` · L. 999
- `cmd_verify(a)` · L. 1055
- `main(argv=None)` · L. 1062

Internal helpers: `_session_path`, `_analyzer`, `_pick_window`, `_agent_spec`, `_print_suggestion`, `_league`, `_league_pool`, `_pool_text`

### `pokercollector.compare`

File `collector/src/pokercollector/compare.py` · 282 lines

Field-wise comparison of the visual reconstruction with the reference export.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `COMPARE_VERSION` | `'compare-1'` | 17 |
| `_ACTION_TYPES` | `{'fold', 'check', 'call', 'bet', 'raise', 'post_sb', 'post_bb', 'alli…` | 96 |

**Class `FieldTally`** · line 52

- `add(self, kind: str)` · L. 59
- `as_dict(self)` · L. 62

**Class `CompareResult`** · line 74

- `to_dict(self)` · L. 83

**Funktionen**

- `map_seats(visual_hands: list[dict], ref_hands: list[RefHand]) -> dict[int, int]` · L. 27: Visual seat -> reference seat via player names (prefix, since names may be truncated).
- `compare(visual_hands: list[dict], ref_hands: list[RefHand], hero_seat_visual: int=0) -> CompareResult` · L. 135

Internal helpers: `_norm_name`, `_align`

### `pokercollector.fastpoker`

File `collector/src/pokercollector/fastpoker.py` · 203 lines

Fast hand evaluation and Monte-Carlo equity (numba, machine code).

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `CARD_INDEX` | `{c: i for i, c in enumerate(FULL_DECK)}` | 19 |

**Funktionen**

- `eval_cards(cards, n)` · L. 63
- `to_ints(cards: list[str]) -> np.ndarray` · L. 190
- `evaluate_fast(cards: list[str]) -> int` · L. 194
- `mc_stats(hole: list[str], board: list[str], opponents: int, iterations: int, seed: int, dead: list[str] | None=None) -> tuple[float, float, int, int]` · L. 198: (Sum, sum of squares, wins, splits). dead: additionally known cards (rare, Python path).

Internal helpers: `_straight_high`, `_top`, `_mc`

### `pokercollector.geometry`

File `collector/src/pokercollector/geometry.py` · 79 lines

Simple rectangular geometry in pixel coordinates (x, y, width, height).

**Class `Rect`** · line 11

- `x2(self) -> int` · L. 18
- `y2(self) -> int` · L. 22
- `cx(self) -> float` · L. 26
- `cy(self) -> float` · L. 30
- `area(self) -> int` · L. 34
- `clip(self, width: int, height: int) -> 'Rect'` · L. 37
- `crop(self, img: np.ndarray) -> np.ndarray` · L. 44
- `offset(self, dx: int, dy: int) -> 'Rect'` · L. 48
- `expand(self, d: int) -> 'Rect'` · L. 51
- `sub(self, rx: float, ry: float, rw: float, rh: float, scale: float=1.0) -> 'Rect'` · L. 54: Subrectangle relative to the top-left corner, dimensions in reference pixels * scale.
- `contains(self, x: float, y: float) -> bool` · L. 63
- `iou(self, other: 'Rect') -> float` · L. 66
- `as_list(self) -> list[int]` · L. 73
- `from_list(v) -> 'Rect'` · L. 77

### `pokercollector.glyphs`

File `collector/src/pokercollector/glyphs.py` · 81 lines

Recognize card ranks by shape comparison with drawn font templates.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `GLYPH_SIZE` | `(20, 28)` | 21 |
| `RANK_TEXT` | `{'2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '8'…` | 22 |
| `FONT_DIR` | `Path('C:/Windows/Fonts')` | 24 |
| `FONTS` | `['arialbd.ttf', 'arial.ttf', 'segoeuib.ttf', 'segoeui.ttf', 'verdanab…` | 25 |
| `ASPECT_WEIGHT` | `0.6` | 32 |

**Funktionen**

- `font_templates() -> list[tuple[str, np.ndarray, float, str]]` · L. 41: (Rank, normalized glyph, aspect ratio w/h, font) for all available fonts.
- `match_rank(glyph: np.ndarray, aspect: float) -> tuple[str | None, float, float]` · L. 67: (Rank, score, distance to second-best rank). glyph: normalized as cards._normalize_glyph.

Internal helpers: `_norm`

### `pokercollector.journal`

File `collector/src/pokercollector/journal.py` · 223 lines

Session folder, append-only observation journal (JSONL), evidence images, SQLite index.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `SCHEMA_VERSION` | `1` | 35 |

**Class `Session`** · line 60

- `__init__(self, root: Path, meta: dict[str, Any])` · L. 61
- `create(base: Path, source: dict[str, Any], profile_id: str, analyzer_version: str, extra: dict[str, Any] | None=None) -> 'Session'` · L. 73
- `open(root: Path) -> 'Session'` · L. 99
- `save_meta(self)` · L. 103
- `gap(self, t_start: float, t_end: float, reason: str)` · L. 111
- `error(self, message: str, **kw)` · L. 117
- `write_event(self, event, frame: np.ndarray | None=None, segment: str | None=None, save_evidence: bool=True) -> dict` · L. 122
- `close(self)` · L. 141

**Funktionen**

- `dumps(o) -> str` · L. 56
- `read_events(root: Path) -> list[dict]` · L. 149
- `build_index(root: Path)` · L. 166
- `sha256_file(p: Path) -> str` · L. 193
- `write_manifest(root: Path)` · L. 201
- `verify_manifest(root: Path) -> list[str]` · L. 209
- `monotonic() -> float` · L. 221

Internal helpers: `_utc_now`, `_json_default`

### `pokercollector.layout`

File `collector/src/pokercollector/layout.py` · 280 lines

Finds table, seat panels, board cards, markers, and action bar in the frame.

**Class `SeatPanel`** · line 24


**Class `Marker`** · line 33


**Class `TableLayout`** · line 41


**Class `SeatMemory`** · line 57
: Learned seating positions of a table (relative to the felt). Index in `positions` = seat number.

- `__init__(self, tol: float=0.06)` · L. 60
- `reset(self)` · L. 64
- `assign(self, centers: list[tuple[float, float]], hero: int | None) -> list[int]` · L. 67: Seat number per panel center. First assignment: own seat 0, then clockwise.

**Funktionen**

- `detect_layout(frame: np.ndarray, profile: Profile, memory: SeatMemory | None=None) -> TableLayout` · L. 206

Internal helpers: `_felt_rect`, `_dark_components`, `_find_markers`

### `pokercollector.ocr`

File `collector/src/pokercollector/ocr.py` · 234 lines

OCR layer. Standard: Windows.Media.Ocr (no additional software needed).

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `OCR_VERSION` | `'winocr-1'` | 18 |

**Class `OcrLine`** · line 22


**Class `OcrResult`** · line 28

- `text(self) -> str` · L. 32

**Class `OcrBackend`** (Protocol) · line 36

- `recognize(self, img: np.ndarray) -> list[tuple[str, tuple[float, float, float, float]]]` · L. 39: Lines (text, (x, y, w, h)) in image coordinates of the passed image.

**Class `WindowsOcr`** · line 43

- `__init__(self, language: str | None=None)` · L. 46
- `recognize(self, img: np.ndarray)` · L. 62

**Class `FakeOcr`** · line 99
: For tests: returns preset texts depending on image hash or always the same ones.

- `__init__(self, fixed: list[tuple[str, tuple[float, float, float, float]]] | None=None)` · L. 104
- `recognize(self, img)` · L. 107

**Class `RegionOcr`** · line 115
: OCR on image crops with preprocessing and change cache.

- `__init__(self, backend: OcrBackend, upscale: float=3.0, cache_tolerance: float=1.5)` · L. 123
- `read(self, frame: np.ndarray, rect: Rect, key: str | None=None, upscale: float | None=None, accept=None) -> OcrResult` · L. 167: Reads an area. With `accept` (function OcrResult -> bool) further variants (scaling, inversion) are tried
- `read_glyph_tiled(self, glyph_ink: np.ndarray, repeats: int=3, heights: tuple[int, ...]=(120, 80, 160), accept=None) -> str` · L. 203: Reads a single character (binary ink = 255) by placing it multiple times side-by-side;
- internal methods: `_thumb`, `_recognize`, `_cached`

**Funktionen**

- `default_backend() -> OcrBackend` · L. 111
- `image_digest(img: np.ndarray) -> str` · L. 232

### `pokercollector.overlay`

File `collector/src/pokercollector/overlay.py` · 295 lines

Lynx bar: small floating field above the taskbar (next to clock and battery) with the suggestion.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `OVERLAY_VERSION` | `'leiste-2'` | 27 |
| `GWL_EXSTYLE` | `-20` | 28 |
| `COLORS` | `{'fold': ('#8a2b2b', '#ffffff'), 'check': ('#2b6a3a', '#ffffff'), 'ca…` | 31 |
| `STATUS_DOT` | `{'ok': '#3ddc84', 'warn': '#f5c542', 'err': '#ff5252', 'off': '#55555…` | 40 |
| `TONES` | `{'fold': [(392, 90)], 'check': [(587, 90)], 'call': [(587, 90)], 'rai…` | 41 |
| `ACTION_LABELS` | `{'fold': 'Fold', 'call': 'Call', 'raise_half': '½ Pot', 'raise_pot': …` | 87 |
| `WARNINGS` | `{'Pot unknown or inconsistent': 'Pot not recognized', 'Amount to call…` | 89 |

**Class `Advice`** · line 46
: What the bar displays.


**Class `Leiste`** · line 132

- `__init__(self, sound: bool=True, title: str='Lynx')` · L. 135
- `start(self) -> 'Leiste'` · L. 145
- `show(self, adv: Advice, beep: bool=True)` · L. 150: New suggestion: it's your turn.
- `idle(self)` · L. 154: Not (anymore) your turn: bar pale, last suggestion remains readable.
- `status(self, level: str, text: str)` · L. 158: Status point: ok | warn | err | off, with short text (tooltip-like bottom right).
- `close(self)` · L. 162
- internal methods: `_run`, `_style_window`, `_paint`, `_pump`, `_drag_start`, `_drag`, `_drag_end`, `_popup`, `_toggle_sound`, `_label_sound`, `_default_pos`, `_reset_pos`, `_load_pos`, `_save_pos`

**Funktionen**

- `advice_from(sug, obs, agent=None) -> Advice` · L. 54: Suggestion (action) + observation -> display. Amounts in chips and big blinds.
- `alternatives(agent, obs=None) -> list[tuple[str, float]]` · L. 93: Probabilities of actions (largest first), if the bot guesses them.
- `settings_path() -> Path` · L. 112

Internal helpers: `_work_area`, `_beep`

### `pokercollector.parse`

File `collector/src/pokercollector/parse.py` · 196 lines

Parser for OCR texts of the PokerTH web interface.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `_DIGIT_FIXES` | `str.maketrans({'O': '0', 'o': '0', 'D': '0', 'Q': '0', 'l': '1', 'I':…` | 13 |
| `_MONEY_IN_TEXT` | `re.compile("[$S§]\\s*[0-9OolI](?:[0-9OolI]¦[ .,'](?=[0-9OolI]{3}))*")` | 66 |
| `_STREETS` | `{'preflop': 'preflop', 'flop': 'flop', 'turn': 'turn', 'river': 'rive…` | 87 |
| `_ACTION_WORDS` | `[('allin', 'allin'), ('all-in', 'allin'), ('fold', 'fold'), ('check',…` | 144 |

**Class `Parsed`** · line 18


**Funktionen**

- `parse_money(text: str | None) -> Parsed` · L. 30: '$3 000', 'S3 000', '$O', '$2.980', '3000' -> int chips.
- `extract_money(text: str | None) -> Parsed` · L. 69: Finds the first amount with currency sign in a line ('• $20' -> 20).
- `parse_street(text: str | None) -> Parsed` · L. 96
- `parse_game_hand(text: str | None) -> Parsed` · L. 108: 'Game: 1 Hand: 12' -> (1, 12).
- `parse_blinds(text: str | None) -> Parsed` · L. 120: '10/20 ↑8' (OCR often '10/20+8') -> {'sb':10,'bb':20,'extra':'8'}.
- `parse_labeled_money(text: str | None, label: str) -> Parsed` · L. 133: 'Bets: $30' with label='eins' -> 30.
- `parse_action_label(text: str | None) -> Parsed` · L. 167
- `parse_button(text: str | None) -> Parsed` · L. 183: Action button 'Call $20' / 'Raise $40' / 'Check' / 'Bet $20' -> (action, amount|None).

Internal helpers: `_fix_digits`, `_edit_distance`

### `pokercollector.pipeline`

File `collector/src/pokercollector/pipeline.py` · 294 lines

Connects source -> analysis -> stabilization -> journal -> reconstruction.

**Class `RunStats`** · line 54

- `summary(self) -> dict` · L. 64

**Class `LiveRunner`** · line 133
: Automatic sessions for a live window.

- `__init__(self, source, sessions_dir: Path, profile: Profile, analyzer: FrameAnalyzer, fps: float, detect_frames: int=5, stop_after_s: float=20.0, segment_s: fl…` · L. 136
- `run(self)` · L. 157
- internal methods: `_set_status`

**Funktionen**

- `make_analyzer(profile: Profile, templates_dir: Path | None=None, ocr_backend=None) -> FrameAnalyzer` · L. 38
- `write_hands(session_root: Path) -> list` · L. 43
- `run_offline(source, sessions_dir: Path, profile: Profile, analyzer: FrameAnalyzer, on_event: Callable | None=None, progress: Callable | None=None) -> Path` · L. 83

Internal helpers: `_log_events`

### `pokercollector.poker`

File `collector/src/pokercollector/poker.py` · 184 lines

Cards, 7-card hand evaluation, and Monte Carlo equity.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `RANKS` | `'23456789TJQKA'` | 13 |
| `SUITS` | `'shdc'` | 14 |
| `SUIT_SYMBOLS` | `{'s': '♠', 'h': '♥', 'd': '♦', 'c': '♣'}` | 15 |
| `FULL_DECK` | `[r + s for r in RANKS for s in SUITS]` | 16 |
| `CATEGORY_NAMES` | `['High Card', 'Pair', 'Two Pair', 'Three of a Kind', 'Straight', 'Flu…` | 18 |

**Class `EquityResult`** · line 103


**Funktionen**

- `is_card(c: str | None) -> bool` · L. 24
- `normalize_rank(token: str) -> str | None` · L. 28
- `evaluate(cards: list[str]) -> tuple` · L. 48: Evaluates 5-7 cards. Larger tuple = stronger hand. Element 0 = category.
- `describe(value: tuple) -> str` · L. 98
- `equity_vs_random(hero: list[str], board: list[str], opponents: int, iterations: int=3000, seed: int | None=0, dead: list[str] | None=None) -> EquityResult` · L. 113: Monte Carlo equity against `opponents` random hands.
- `pot_odds(to_call: int, pot: int) -> float` · L. 179: Required equity for a profitable call without future bets.

Internal helpers: `_straight_high`

### `pokercollector.profile`

File `collector/src/pokercollector/profile.py` · 42 lines

Load versioned table profiles.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `DEFAULT_PROFILE` | `'pokerth_web_v1.json'` | 12 |

**Class `Profile`** · line 15

- `__init__(self, data: dict[str, Any], path: str)` · L. 16
- `id(self) -> str` · L. 23
- `hsv(self, *keys) -> tuple[np.ndarray, np.ndarray]` · L. 29
- `load(path: str | Path | None=None) -> 'Profile'` · L. 36
- internal methods: `__getitem__`

### `pokercollector.profiles`

File `collector/src/pokercollector/profiles/__init__.py` · 1 lines

### `pokercollector.reconstruct`

File `collector/src/pokercollector/reconstruct.py` · 755 lines

Rule-based hand reconstruction from stabilized field events.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `RECONSTRUCT_VERSION` | `'reconstruct-2'` | 23 |
| `STREETS` | `['preflop', 'flop', 'turn', 'river']` | 24 |
| `BOARD_TO_STREET` | `{0: 'preflop', 3: 'flop', 4: 'turn', 5: 'river'}` | 25 |
| `NUM_SEATS` | `10` | 26 |
| `TURN_GRACE_S` | `0.9` | 27 |
| `SWEEP_WINDOW_S` | `2.0` | 28 |
| `SETTLE_S` | `2.5` | 31 |
| `LATE_S` | `1.5` | 33 |
| `ADOPT_S` | `30.0` | 35 |
| `MIN_HAND_S` | `4.0` | 36 |
| `_SETTLE_PROPS` | `('bet', 'folded', 'action_label', 'active', 'stack')` | 37 |
| `_FIELD_PRIORITY` | `[('table.', 0), ('info.game_hand', 1), ('marker.', 2), ('info.blinds'…` | 730 |

**Class `Action`** · line 41


**Class `SeatInfo`** · line 58


**Class `Hand`** · line 70

- `to_dict(self) -> dict` · L. 89

**Class `_StreetState`** · line 95

- `__init__(self, name: str, t: float)` · L. 96

**Class `Reconstructor`** · line 105

- `__init__(self, num_seats: int=NUM_SEATS)` · L. 106
- `feed(self, ev: dict)` · L. 603
- `finish(self, t_end: float | None=None) -> list[Hand]` · L. 724
- internal methods: `_name`, `_in_hand`, `_seat_info`, `_add_action`, `_first_to_act`, `_check_order`, `_start_hand`, `_settle`, `_finish_hand`, `_close_street`, `_flush_close`, `_new_street`, `_bet_change`, `_bet_change_now`, `_apply_bet`, `_late_for_prev`, `_fold`, `_label`, `_active_change`, `_resolve_pending`, `_stack_change`, `_seat_event`

**Funktionen**

- `reconstruct(events: list[dict]) -> list[Hand]` · L. 747

Internal helpers: `_priority`

### `pokercollector.reference`

File `collector/src/pokercollector/reference.py` · 271 lines

Import of the PokerTH hand history as an independent reference.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `REFERENCE_PARSER_VERSION` | `'pokerth-sqlite-1 (ungeprueft)'` | 24 |
| `CARD_SUIT_ORDER` | `'dhsc'` | 25 |
| `RANKS` | `'23456789TJQKA'` | 26 |
| `STREETS` | `['preflop', 'flop', 'turn', 'river']` | 27 |
| `ACTION_MAP` | `{'posts small blind': 'post_sb', 'posts big blind': 'post_bb', 'folds…` | 29 |
| `TEXT_PARSER_VERSION` | `'pokerth-web-text-1'` | 183 |
| `_HAND_RE` | `re.compile('^-+ Game: (\\d+) \\¦ Hand: (\\d+) -+$')` | 184 |
| `_SEAT_RE` | `re.compile('^Seat (\\d+): (.+) \\(\\$(\\d+)\\)$')` | 185 |
| `_LEVEL_RE` | `re.compile('^BLIND LEVEL: \\$(\\d+) / \\$(\\d+)$')` | 186 |
| `_BLINDS_RE` | `re.compile('^BLINDS: (.+) \\(\\$(\\d+)\\), (.+) \\(\\$(\\d+)\\)$')` | 187 |
| `_STREET_RE` | `re.compile('^(PREFLOP¦FLOP¦TURN¦RIVER)(?: \\[board cards (.+)\\])?$')` | 188 |
| `_TEXT_ACTIONS` | `[(re.compile('^folds\\.$'), 'fold'), (re.compile('^checks\\.$'), 'che…` | 189 |

**Class `ReferenceFormatError`** (Exception) · line 49


**Class `RefAction`** · line 69


**Class `RefHand`** · line 79

- `to_dict(self)` · L. 90

**Funktionen**

- `decode_card(v) -> str | None` · L. 53
- `inspect(path: Path) -> dict[str, list[str]]` · L. 94
- `load_pokerth_log(path: Path) -> list[RefHand]` · L. 118
- `load_pokerth_text_log(path: Path) -> list[RefHand]` · L. 206
- `load_reference(path: Path) -> list[RefHand]` · L. 262: Recognizes the format: SQLite (.pdb) or text log of the web client.

Internal helpers: `_find`, `_col`, `_norm_text_card`

### `pokercollector.report`

File `collector/src/pokercollector/report.py` · 121 lines

Calibration overlay and human-readable reports (Markdown).

**Funktionen**

- `overlay(frame: np.ndarray, snap: TableSnapshot) -> np.ndarray` · L. 15
- `hands_markdown(session_root: Path) -> str` · L. 65
- `compare_markdown(result: dict) -> str` · L. 103

Internal helpers: `_cards`

### `pokercollector.stabilize`

File `collector/src/pokercollector/stabilize.py` · 121 lines

Temporal stabilization of individual fields.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `FAST_FIELDS` | `('hero.to_act',)` | 19 |

**Class `FieldEvent`** · line 27


**Class `_Track`** · line 44


**Class `Stabilizer`** · line 59

- `state(self) -> dict[str, Any]` · L. 66
- `update(self, snap: TableSnapshot) -> list[FieldEvent]` · L. 69
- internal methods: `_transient`

Internal helpers: `_key`

### `pokercollector.system`

File `collector/src/pokercollector/system.py` · 28 lines

System utilities: prevent standby during long runs.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `ES_CONTINUOUS` | `2147483648` | 8 |
| `ES_SYSTEM_REQUIRED` | `1` | 9 |
| `ES_DISPLAY_REQUIRED` | `2` | 10 |

**Funktionen**

- `keep_awake(enabled: bool=True)` · L. 14: Prevents idle standby as long as the block is running (Windows SetThreadExecutionState).

## pokercollector.ai (AI: engine, bots, training, search, value nets)

### `pokercollector.ai`

File `collector/src/pokercollector/ai/__init__.py` · 2 lines

Simulation, player-view interface, bots and evaluation (levels 1-3 of AI).

### `pokercollector.ai.agents`

File `collector/src/pokercollector/ai/agents.py` · 328 lines

Opponent pool: rule-based bots with adjustable style plus baseline agents.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `AGENTS_VERSION` | `'agents-1'` | 24 |
| `STYLES` | `{'station': Style(vpip=0.6, pfr=0.03, value_margin=0.3, raise_margin=…` | 148 |
| `REGISTRY` | `{'random': lambda seed=0: RandomAgent(seed), 'caller': lambda seed=0:…` | 274 |

**Class `BaseAgent`** · line 82

- `__init__(self, seed: int=0, name: str | None=None)` · L. 85
- `rng(self, obs: Observation) -> random.Random` · L. 90
- `act(self, obs: Observation) -> Action` · L. 93
- `passive(obs: Observation) -> Action` · L. 97
- `raise_to(obs: Observation, amount: float) -> Action` · L. 101

**Class `RandomAgent`** (BaseAgent) · line 108
: Randomly among allowed actions - lower bound for each evaluation.

- `act(self, obs)` · L. 112

**Class `CallAgent`** (BaseAgent) · line 121
: Always checks or calls (deterministic, for tests).

- `act(self, obs)` · L. 125

**Class `Style`** · line 130


**Class `StyleBot`** (BaseAgent) · line 162

- `__init__(self, style: str, seed: int=0, iterations: int=120, name: str | None=None)` · L. 163
- `act(self, obs)` · L. 239
- internal methods: `_push_fold`, `_preflop`, `_postflop`

**Class `EquityAgent`** (BaseAgent) · line 246
: The baseline from advisor.py as an agent: equity against random hands vs. pot odds.

- `__init__(self, seed: int=0, iterations: int=300, name: str | None=None)` · L. 250
- `act(self, obs)` · L. 255

**Funktionen**

- `mc_equity(hole: list[str], board: list[str], opponents: int, iterations: int, rng: random.Random) -> float` · L. 27: Equity against `opponents` random hands (small Monte Carlo).
- `push_fold_spot(obs: Observation) -> dict` · L. 54: Assigns a preflop situation to the push/fold model.
- `make_agent(spec: str, seed: int=0) -> BaseAgent` · L. 282: 'tag', 'tag:Name' (Name for distinction) or with own style values

### `pokercollector.ai.bench`

File `collector/src/pokercollector/ai/bench.py` · 321 lines

Test bench: every candidate goes through the same fixed test sets - comparable over weeks.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `BENCH_VERSION` | `'bench-1'` | 37 |
| `MIX_PLAYERS` | `['rock', 'tag', 'lag', 'station', 'maniac', 'equity', 'tag?vpip=0.082…` | 38 |
| `MIX_WEIGHTS` | `[3, 3, 2, 1, 1, 1, 3, 3]` | 42 |
| `FORMAT_SETS` | `{'hu48': (1, TournamentConfig(start_stack=1000, blinds=BlindSchedule(…` | 45 |
| `PRECISE_SETS` | `('mix960', 'pokerth480', 'hu480', '10max240')` | 56 |
| `_SIZED` | `re.compile('^(fest¦mix¦hu¦3max¦10max¦turbo¦deep¦pokerth¦mensch¦nash¦k…` | 57 |
| `HUMAN_BOTS` | `'mensch-25nl'` | 58 |
| `ENDGAME_CONFIG` | `TournamentConfig(start_stack=400, blinds=BlindSchedule(10, 20, 10), p…` | 60 |
| `NASH_BOT` | `'tag?push_bb=40&nash_stack_factor=1'` | 61 |

**Funktionen**

- `parse_set(name: str) -> tuple[str, int]` · L. 64: 'mix960' -> ('mix96', 960): base set (determines cards and tables) and number of schemas.
- `is_tournament_set(name: str) -> bool` · L. 77
- `set_config(name: str) -> TournamentConfig` · L. 81
- `bench_set(name: str) -> list[tuple[int, list[str]]]` · L. 90
- `run_set(spec: str, name: str, ex, config=None, on_chunk=None, partial: Path | None=None) -> dict` · L. 152: 24 blocks in parallel. on_chunk(done, total, interim) after each block; partial = file where
- `run_cash(spec: str, hands: int=300) -> dict` · L. 184
- `bench_dir() -> Path` · L. 192
- `run_bench(spec: str, name: str, sets=('fest48', 'mix96', 'cash', 'pluribus'), exploit: bool=False, ex=None, workers: int | None=None, progress=None, on_chunk=N…` · L. 197: progress(set, result) for each finished set; on_chunk(done, total, interim) for each block;
- `load_results() -> list[dict]` · L. 241
- `paired_diff(a: dict, b: dict, s: str) -> dict | None` · L. 248: Paired comparison of two results on the same test set (same schemas).
- `write_report() -> str` · L. 255
- `compare(name_a: str, name_b: str) -> list[tuple[str, dict, dict, dict]]` · L. 303: Paired comparison of two test bench entries on all common tournament test sets:

Internal helpers: `_chunk`, `_summary`

### `pokercollector.ai.bpranges`

File `collector/src/pokercollector/ai/bpranges.py` · 194 lines

Blueprint ranges for the heads-up search (husearch.py).

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `CLASSES` | `all_classes()` | 30 |
| `CLASS_ID` | `{c: i for i, c in enumerate(CLASSES)}` | 31 |
| `COMBO_CLASS` | `np.array([CLASS_ID[hand_class([FULL_DECK[i], FULL_DECK[j]])] for i, j…` | 32 |
| `CLASS_CARDS` | `[example_cards(c) for c in CLASSES]` | 33 |
| `COMBO_CARDS` | `[[FULL_DECK[i], FULL_DECK[j]] for i, j in COMBOS]` | 34 |
| `_CACHE` | `{}` | 36 |
| `_CACHE_MAX` | `512` | 37 |

**Funktionen**

- `forward_batch(w: dict, x: np.ndarray, mask: np.ndarray) -> np.ndarray` · L. 40: Network probabilities for many situations (rows) with a common action mask.
- `blueprint_ranges(obs: Observation, hero: int, opp: int, blueprint, bp_streets: tuple[str, ...]=('preflop',), opp_weights: dict | None=None, opp_fold=None) -> t…` · L. 113: Ranges (sum 1) of hero and opp at BEGINNING of current street from the blueprint network.

Internal helpers: `_action`, `_deck_for`, `_blueprint_probs`, `_apply_blueprint`, `_apply_heuristic`, `_cache_key`, `_compute`

### `pokercollector.ai.cfr`

File `collector/src/pokercollector/ai/cfr.py` · 291 lines

Equilibrium instead of exploitation: Monte-Carlo CFR like the blueprint of Pluribus.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `CFR_VERSION` | `'mccfr-1'` | 40 |
| `HAND_BUCKETS_PRE` | `20` | 41 |
| `HAND_BUCKETS_POST` | `12` | 42 |
| `_RADIX` | `(4, 20, 6, 5, 5, 5, 4, 2)` | 43 |
| `_POLICY_CACHE` | `{}` | 241 |

**Class `_Worker`** · line 111

- `__init__(self, regrets: dict, rng: random.Random)` · L. 112
- `traverse(self, h: Hand, p: int) -> float` · L. 120

**Class `CFRAgent`** (BaseAgent) · line 255
: Plays the average strategy. Unknown situation: simple equity rule (counted).

- `__init__(self, policy: dict, seed: int=0, name: str | None=None)` · L. 259
- `act(self, obs: Observation)` · L. 266

**Funktionen**

- `abstract_mask(obs: Observation) -> np.ndarray` · L. 46
- `infokey(obs: Observation, cache: dict | None=None) -> int` · L. 60
- `decode(code: int) -> dict` · L. 90
- `regret_matching(reg: np.ndarray | None, mask: np.ndarray) -> np.ndarray` · L. 99
- `random_hand(rng: random.Random) -> Hand` · L. 147
- `save_average(path: Path, strategy: dict)` · L. 187
- `train_cfr(run_dir: Path, rounds: int, traversals: int=400, workers: int | None=None, seed: int=1, progress=None) -> dict` · L. 197: rounds: target round (total number). Per round: workers x traversals runs with strategy at
- `load_policy(run: str) -> dict` · L. 244
- `make_cfr_agent(params: str, seed: int=0) -> CFRAgent` · L. 286

Internal helpers: `_bucket`, `_job`, `_save_state`, `_load_state`

### `pokercollector.ai.confirm`

File `collector/src/pokercollector/ai/confirm.py` · 40 lines

One-time confirmation of two bots against human bots on FRESH tables and cards.

**Funktionen**

- `human_tables(schemes: int, seed: str, bots_name: str='mensch-25nl') -> list[tuple[int, list[str]]]` · L. 18
- `confirm_vs_humans(spec_a: str, spec_b: str, schemes: int=600, seed: str='1', workers: int | None=None) -> dict` · L. 25

### `pokercollector.ai.deepcfr`

File `collector/src/pokercollector/ai/deepcfr.py` · 274 lines

Deep CFR: CFR with neural networks instead of a table (Brown, Lerer, Gross, Sandholm 2019).

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `DEEPCFR_VERSION` | `'deepcfr-1'` | 35 |

**Class `DeepCFRConfig`** · line 39


**Class `_Traverser`** · line 70

- `__init__(self, w: dict | None, rng: random.Random, t: int, scale: float)` · L. 71
- `policy(self, x, amask)` · L. 77
- `traverse(self, h: Hand, p: int) -> float` · L. 82

**Class `Reservoir`** · line 123
: Uniform sampling over all seen data points (Algorithm R), fixed size.

- `__init__(self, capacity: int, rng: np.random.Generator)` · L. 126
- `add(self, x, m, y, t: int)` · L. 136
- `state(self) -> dict` · L. 156
- `load(self, d: dict, prefix: str)` · L. 160

**Funktionen**

- `strategy_from_adv(adv: np.ndarray, mask: np.ndarray) -> np.ndarray` · L. 59: Regret matching on predicted advantages. All <= 0: best allowed action (Deep-CFR rule).
- `train_strategy(buf: Reservoir, cfg: DeepCFRConfig, gen)` · L. 186: Average strategy: network learns the stored mixtures (weighted by t, linear CFR).
- `train_deepcfr(run_dir: Path, iterations: int, cfg: DeepCFRConfig | None=None, workers: int | None=None, progress=None, on_snapshot=None) -> dict` · L. 207

Internal helpers: `_adv_np`, `_job`, `_train_adv`

### `pokercollector.ai.engine`

File `collector/src/pokercollector/ai/engine.py` · 349 lines

No-Limit Hold'em dealer for 2-10 players.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `ENGINE_VERSION` | `'nlhe-engine-1'` | 25 |

**Class `IllegalAction`** (Exception) · line 34


**Class `SeatResult`** · line 39

- `net(self) -> int` · L. 48

**Class `HandRecord`** · line 53


**Class `Hand`** · line 68
: A single hand. Flow: h = Hand(...); while not h.done: h.apply(seat, agent.act(h.observation(seat))).

- `__init__(self, stacks: list[int], button: int, small_blind: int, big_blind: int, seed: int | None=None, deck: list[str] | None=None, hand_id: str='', names: li…` · L. 71
- `clone(self) -> 'Hand'` · L. 116: Fast copy of game state (CFR plays every own action from a point).
- `legal(self, s: int) -> dict` · L. 169
- `observation(self, s: int) -> Observation` · L. 182
- `apply(self, s: int, action: Action)` · L. 196
- internal methods: `_next`, `_can_act`, `_live`, `_put`, `_post_blinds`, `_needs_action`, `_round_complete`, `_advance`, `_next_street`, `_run_out`, `_finish`

**Funktionen**

- `play_hand(agents: list, stacks: list[int], button: int, small_blind: int, big_blind: int, seed: int | None=None, hand_id: str='', names=None, on_illegal: str='…` · L. 328: Plays a hand with given agents (index = seat). Illegal actions

### `pokercollector.ai.evaluate`

File `collector/src/pokercollector/ai/evaluate.py` · 189 lines

Evaluation of agents over many hands.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `EVAL_VERSION` | `'eval-1'` | 25 |
| `_T975` | `[12.71, 4.3, 3.18, 2.78, 2.57, 2.45, 2.36, 2.31, 2.26, 2.23, 2.2, 2.1…` | 28 |

**Class `AgentStats`** · line 41

- `result(self, big_blind: int, hands_per_unit: float) -> dict` · L. 54

**Funktionen**

- `t95(n: int) -> float` · L. 32: Factor for a 95% interval with n samples (small n: t-distribution).
- `run_match(agents: list, hands: int, seed: int=1, small_blind: int=10, big_blind: int=20, stack_bb: int=100, duplicate: bool=True, progress=None, keep_records: …` · L. 102: agents: list of agent objects (2-10). hands: number of decks.
- `report_markdown(res: dict) -> str` · L. 146
- `hand_text(rec: HandRecord) -> str` · L. 163: Readable hand history (for debugging).
- `save_result(res: dict, path: Path)` · L. 186

Internal helpers: `_tally`

### `pokercollector.ai.features`

File `collector/src/pokercollector/ai/features.py` · 232 lines

What the learning bot sees: Observation -> fixed-length numeric vector, plus action set.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `FEATURES_VERSION` | `'feat-2'` | 35 |
| `FEATURE_SIZES` | `{'feat-1': 46, 'feat-2': 49, 'feat-3': 57}` | 36 |
| `RANGE_EQUITY_ITERATIONS` | `120` | 37 |
| `ACTIONS` | `('fold', 'call', 'raise_half', 'raise_pot', 'raise_2pot', 'allin')` | 38 |
| `ACTIONS_8` | `ACTIONS + ('raise_third', 'raise_min')` | 39 |
| `RAISE_FRACTIONS` | `{2: 0.5, 3: 1.0, 4: 2.0}` | 40 |
| `RAISE_FRACTIONS_8` | `{**RAISE_FRACTIONS, 6: 1 / 3}` | 41 |
| `MIN_RAISE` | `7` | 42 |
| `N_ACTIONS` | `len(ACTIONS)` | 43 |
| `EQUITY_ITERATIONS` | `100` | 48 |
| `_STREET` | `{'preflop': 0, 'flop': 1, 'turn': 2, 'river': 3}` | 50 |
| `N_FEATURES` | `FEATURE_SIZES[FEATURES_VERSION]` | 161 |
| `EFF_STACK_INDEX` | `24` | 162 |
| `PLAYERS_INDEX` | `29` | 163 |

**Funktionen**

- `action_names(n: int=N_ACTIONS) -> tuple[str, ...]` · L. 46
- `equity_of(obs: Observation, rng: random.Random | None=None) -> float` · L. 57
- `features(obs: Observation, equity: float | None=None, version: str=FEATURES_VERSION, opp: np.ndarray | None=None) -> np.ndarray` · L. 65: opp: opponent features from OpponentTracker.features(obs) (only feat-3; None = no observations).
- `version_for_width(n: int) -> str` · L. 166
- `eff_stack_bb(x: np.ndarray) -> np.ndarray` · L. 173
- `action_mask(obs: Observation, n: int=N_ACTIONS) -> np.ndarray` · L. 177
- `to_action(obs: Observation, idx: int) -> Action` · L. 198
- `from_action(obs: Observation, action: Action, n: int=N_ACTIONS) -> int` · L. 210: Maps a (legal) action of another bot to the next discrete action

Internal helpers: `_log_scaled`, `_range_features`, `_features_v1`, `_raise_amount`

### `pokercollector.ai.gtow`

File `collector/src/pokercollector/ai/gtow.py` · 281 lines

Measure against GTO Wizard AI (benchmark.gtowizard.com) - second external benchmark besides Slumbot.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `API` | `'https://researcher.gtowizard.com'` | 38 |
| `GAME` | `'HUNL 200BB'` | 39 |
| `GTOW_VERSION` | `'gtow-1'` | 40 |
| `KEY_FILE` | `'api_key.txt'` | 41 |

**Class `GtowError`** (RuntimeError) · line 44


**Funktionen**

- `results_dir() -> Path` · L. 48
- `api_key(explicit: str | None=None) -> str` · L. 53
- `history_to_text(history: list[str]) -> str` · L. 92: ['b300', 'c', '_', 'k', 'b500'] -> 'b300c/kb500' (Slumbot notation for slumbot.replay).
- `parse_cards(s: str | None) -> list[str]` · L. 107: 'AhKd', 'Ah Kd', 'Ah,Kd' -> ['Ah', 'Kd']; None/'' -> []. Tens as 'T' (also '10' is understood).
- `split_players(players: list[dict]) -> tuple[dict, dict]` · L. 117: (we, GTO Wizard). Recognition through the name, otherwise through the visible Hole Cards.
- `client_pos(position: str) -> int` · L. 130: 1 = Small Blind/Button (acts first preflop), 0 = Big Blind - like slumbot.replay.
- `rebuild(resp: dict, seed: int=0) -> tuple[Hand, dict, dict]` · L. 140: Rebuild game state of the API inside the engine. Returns (Hand, we, Bot).
- `to_act_request(obs, action: Action, gs: dict) -> dict` · L. 149: Engine action -> ActRequest. The bet size is the street total (like raise_to), capped in raise_range.
- `play_hand(agent, key: str, seed: int) -> dict` · L. 170
- `load_hands(name: str) -> list[dict]` · L. 209
- `summarize(hands: list[dict]) -> dict` · L. 216
- `server_results(key: str) -> dict` · L. 226: Statistics of the server (AIVAT over all our hands, decisive for the ranking).
- `request_access(email: str, organization: str, bot_name: str, key: str, reason: str) -> dict` · L. 232: Apply for access. The key (>= 32 characters) is chosen by yourself; it is valid after approval via email.
- `run(spec: str, name: str, hands: int, workers: int=2, key: str | None=None, progress=None) -> dict` · L. 241: Plays up to `hands` further hands with `workers` parallel hands (the provider client uses 5).

Internal helpers: `_request`

### `pokercollector.ai.human`

File `collector/src/pokercollector/ai/human.py` · 194 lines

You as player: Terminal interface over the same Observation/Action interface.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `SUIT_SYM` | `{'s': '♠', 'h': '♥', 'd': '♦', 'c': '♣'}` | 12 |
| `SUIT_ASCII` | `{'s': 's', 'h': 'h', 'd': 'd', 'c': 'c'}` | 13 |
| `KIND_DE` | `{'post_sb': 'posts Small Blind', 'post_bb': 'posts Big Blind', 'fold'…` | 14 |

**Class `QuitGame`** (Exception) · line 18


**Class `HumanAgent`** · line 22

- `__init__(self, name: str='du', input_fn=input, output_fn=print, ascii_only: bool=False, coach: bool=False)` · L. 23
- `card(self, c: str | None) -> str` · L. 35
- `cards(self, cs) -> str` · L. 42
- `render(self, obs: Observation)` · L. 65
- `act(self, obs: Observation) -> Action` · L. 111
- `parse(self, raw: str, obs: Observation) -> Action | None` · L. 127
- `hand_over(self, rec, seat: int)` · L. 182
- internal methods: `_seat_name`, `_show_new_actions`, `_prompt`, `_coach`

### `pokercollector.ai.humanbots`

File `collector/src/pokercollector/ai/humanbots.py` · 188 lines

Human bots: Style bots whose frequencies correspond to real player types (humans.py, HandHQ).

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `FIT_SPACE` | `{**RANDOM_SPACE, 'bet_size': (0.3, 1.1), 'respect': (0.0, 1.0), 'stic…` | 24 |
| `HUMANBOTS_VERSION` | `'humanbots-1'` | 26 |
| `FIT_KEYS` | `{'vpip': 3.0, 'pfr': 3.0, 'threebet': 2.0, 'agg': 1.0, 'ftb': 1.5, 'c…` | 27 |
| `MEASURE_TABLE` | `['tag', 'rock', 'lag', 'station', 'tag']` | 28 |
| `STACK_BB` | `100` | 29 |

**Funktionen**

- `record_to_phh(rec) -> dict` · L. 32: HandRecord from the engine -> PHH-like dict (p1 = Small Blind, as in HandHQ).
- `measure(spec: str, hands: int=600, seed: int=0, table: list[str] | None=None) -> dict` · L. 78: Frequencies of the bot `spec` over `hands` 6-max cash hands (100 BB, stacks new every hand).
- `distance(st: dict, target: dict) -> float` · L. 94
- `spec_from(x: dict) -> str` · L. 103
- `fit_type(target: dict, generations: int=10, population: int=16, hands: int=600, seed: int=0, ex=None, progress=None, table: list[str] | None=None, start: dict …` · L. 115: CEM on style parameters (limits FIT_SPACE), start near target values for vpip/pfr.
- `fit_all(humans_file: Path, out_name: str, generations: int=10, population: int=16, hands: int=600, workers: int | None=None, progress=None, rounds: int=2) -> P…` · L. 156: Round 1 measures against old style bots; from round 2 the human bots of the preliminary round sit at the table
- `load_bots(name: str='mensch-25nl') -> list[dict]` · L. 184

Internal helpers: `_eval`, `_params`

### `pokercollector.ai.humandata`

File `collector/src/pokercollector/ai/humandata.py` · 383 lines

HandHQ showdown decisions with known cards -> training data for a human policy network (lever H11).

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `HUMANDATA_VERSION` | `'humandata-1'` | 36 |
| `FEATURES` | `'feat-2'` | 37 |
| `N_ACTIONS` | `8` | 38 |
| `SCALE` | `100` | 39 |
| `STREETS` | `{'preflop': 0, 'flop': 1, 'turn': 2, 'river': 3}` | 40 |
| `CLASS_ID` | `{c: i for i, c in enumerate(all_classes())}` | 41 |
| `META_FIELDS` | `('street', 'position', 'n_players', 'n_live', 'pot_bb', 'to_call_bb',…` | 42 |
| `KIND_ID` | `{'fold': 0, 'check': 1, 'call': 2, 'raise': 3}` | 44 |
| `PUBLIC_FIELDS` | `('street', 'position', 'n_players', 'n_live', 'pot_bb', 'to_call_bb',…` | 243 |

**Funktionen**

- `replay_handhq(hand: dict, hand_no: int=0, version: str=FEATURES, n_actions: int=N_ACTIONS)` · L. 66: Replay one HandHQ hand. Return (ok, problem, samples); samples = list
- `iter_file(path: Path)` · L. 141
- `extract(files: list[Path], out_dir: Path | str, workers: int=2, files_per_shard: int=50, version: str=FEATURES, n_actions: int=N_ACTIONS, progress=None) -> dict` · L. 189: Replay all files, every files_per_shard files one shard human-<nr>.npz (already existing shards
- `load(out_dir: Path | str, max_shards: int | None=None) -> dict` · L. 225: Merge shards (x float16, mask, a, metadata; player gets renumbered per shard ->
- `public_rows(hand: dict, hand_no: int=0)` · L. 248: All decisions of a HandHQ hand as card-free state lines (hole_class -1 = unknown).
- `extract_public(files: list[Path], out_dir: Path | str, workers: int=2, files_per_shard: int=50, progress=None) -> dict` · L. 348: All decisions (with and without cards) as card-free lines, shards public-<nr>.npz.
- `load_public(out_dir: Path | str, max_shards: int | None=None) -> dict` · L. 379

Internal helpers: `_split`, `_deck`, `_process_files`, `_process_public`

### `pokercollector.ai.humanfold`

File `collector/src/pokercollector/ai/humanfold.py` · 207 lines

Fold model for the human model (H11 step 2b): which hands normal players fold and which they continue with.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `HUMANFOLD_VERSION` | `'humanfold-1'` | 29 |
| `N_CLASSES` | `169` | 30 |
| `PUBLIC_DIM` | `20` | 31 |
| `_CLASSES` | `all_classes()` | 32 |

**Class `HumanFold`** · line 96
: Loaded fold model: p_fold(x), p_class(x) and continuation factor per combination.

- `__init__(self, w: dict)` · L. 99
- `load(cls, path: Path | str) -> 'HumanFold'` · L. 106
- `p_fold(self, x: np.ndarray) -> np.ndarray` · L. 110
- `p_class(self, x: np.ndarray) -> np.ndarray` · L. 114
- `continue_factor(self, obs: Observation, range_weights: np.ndarray) -> np.ndarray` · L. 121: P(continue | combination, state) in [0,1] for all 1326 combinations: Bayes remainder from g, f and the

**Funktionen**

- `public_vector_arrays(street, position, n_players, n_live, pot_bb, to_call_bb, stack_bb, raises_street, raises_pre, facing, aggressor, board_paired, board_suite…` · L. 39: Card-free state as float32[n, PUBLIC_DIM]; identical for training (columns of public shards)
- `public_vector(obs: Observation) -> np.ndarray` · L. 70: Card-free state of the acting player from one observation (float32[PUBLIC_DIM]).
- `train(rows_dir: Path | str, out: Path | str, max_rows: int=4000000, epochs: int=3, hidden_f: int=64, hidden_g: int=256, batch: int=8192, lr: float=0.002, seed:…` · L. 138: Train both submodels from the public shards (torch, CPU suffices), save as .npz.

Internal helpers: `_log1p`, `_forward`

### `pokercollector.ai.humans`

File `collector/src/pokercollector/ai/humans.py` · 336 lines

Real humans as benchmark: player types from HandHQ (PHH dataset, 21.6 million online hands 2009).

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `HUMANS_VERSION` | `'humans-1'` | 27 |
| `STAT_KEYS` | `('vpip', 'pfr', 'threebet', 'f3b', 'agg', 'ftb', 'cbet', 'wtsd', 'wsd…` | 28 |
| `TYPE_FEATURES` | `('vpip', 'pfr', 'agg', 'ftb', 'threebet', 'cbet', 'wtsd')` | 268 |

**Class `HumanStats`** · line 51

- `__init__(self)` · L. 52
- `add_hand(self, h: dict)` · L. 85
- `stats(self, min_hands: int=0) -> dict[str, dict]` · L. 215
- internal methods: `_winnings`

**Funktionen**

- `handhq_dir() -> Path` · L. 31
- `iter_hands(path: Path)` · L. 36: All hands of a .phhs file (TOML, sections [1], [2], ...).
- `collect(dirs: list[Path], max_files: int | None=None, progress=None, workers: int | None=None) -> HumanStats` · L. 242: Evaluate all .phhs files, distributed across multiple processes (counters are then summed).
- `player_types(stats: dict[str, dict], k: int=6, min_hands: int=300, seed: int=0) -> list[dict]` · L. 271: k-Means on the frequencies of players with enough hands -> types with proportion and means.
- `type_name(m: dict) -> str` · L. 309
- `save(name: str, hs: HumanStats, types: list[dict]) -> Path` · L. 327

Internal helpers: `_counter`, `_collect_chunk`

### `pokercollector.ai.hupreflop`

File `collector/src/pokercollector/ai/hupreflop.py` · 298 lines

Heads-up Preflop: Equilibrium via CFR+ over the 169 starting hand classes, recalculated at every decision.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `HUPREFLOP_VERSION` | `'hupre-1'` | 29 |
| `OPEN_TO` | `2.5` | 30 |
| `ISO_TO` | `4.0` | 31 |
| `RERAISE` | `{1: 3.0, 2: 2.3, 3: 2.2}` | 32 |
| `MAX_FRACTION` | `0.45` | 33 |
| `OOP_REALIZE` | `0.8` | 34 |
| `ITERATIONS` | `800` | 35 |
| `SAME_SIZE` | `0.04` | 36 |
| `ALPHA` | `1.3` | 51 |

**Class `Node`** · line 40


**Funktionen**

- `build(S: float, path: list[tuple[str, float]]=()) -> tuple[Node, list[Node]]` · L. 63: Tree for effective stack S (BB). path: actual actions so far (Type, on BB).
- `solve(S: float, path=(), iterations: int=ITERATIONS)` · L. 185
- `exploitability(root: Node) -> float` · L. 194: (BR_SB + BR_BB) / 2 in BB per hand (0 = equilibrium).
- `strategy(S2: int, path: tuple) -> tuple[list, np.ndarray]` · L. 203: Strategy (actions, probabilities per class) at the current node. S2 = stack in half BB.
- `path_ranges(S2: int, path: tuple) -> tuple[np.ndarray, np.ndarray] | None` · L. 213: Equilibrium ranges (169 classes, unnormalized, prior 1 per class) of SB and BB AFTER the preflop sequence
- `stack_key(S: float) -> int` · L. 232: Stack discretization as in decide(): half BB, full BB from 30 BB, step 2 from 60 BB (cache hits).
- `equilibrium_ranges(obs) -> tuple[np.ndarray, np.ndarray] | None` · L. 241: Equilibrium ranges (169 classes) of (SB, BB) at the start of the current postflop street or
- `history_path(obs) -> list[tuple[str, float]] | None` · L. 257: Preflop history as (Type, on BB); None if not a normal heads-up preflop.
- `effective_stack_bb(obs) -> float` · L. 273
- `decide(obs, rng) -> tuple[tuple[str, float], list, np.ndarray] | None` · L. 278: Action (Type, on BB) for own hand plus all actions/probabilities, or None.

Internal helpers: `_realized_share`, `_same`, `_sigma`, `_walk`, `_avg`, `_br`

### `pokercollector.ai.husearch`

File `collector/src/pokercollector/ai/husearch.py` · 1066 lines

Heads-up runtime search: Turn and River are solved anew at every decision (CFR over ranges), preflop at heads-up table the preflop solver is used (hupreflop.py).

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `HUSEARCH_VERSION` | `'hus-2'` | 47 |
| `N_COMBOS` | `len(COMBOS)` | 48 |
| `LEAF_EVERY` | `10` | 50 |
| `AUTO_DEEP_BB` | `80` | 51 |
| `SIZE_PRESETS` | `{'narrow': {(5, 5): {'bet': (0.33, 0.75, 1.5), 'raise': (1.0,)}, (4, …` | 55 |
| `SIZES_RIVER` | `SIZE_PRESETS['narrow'][5, 5]` | 74 |
| `SIZES_TURN` | `SIZE_PRESETS['narrow'][4, 4]` | 75 |
| `SIZES_RIVER_IN_TURN` | `SIZE_PRESETS['narrow'][4, 5]` | 76 |
| `K_TURN_DEFAULT` | `6` | 80 |
| `K_RIVER_DEFAULT` | `6` | 81 |
| `MAX_RAISES` | `4` | 82 |
| `SAME_SIZE` | `0.04` | 83 |
| `ALLIN_SNAP` | `0.85` | 84 |
| `PARALLEL_MIN_NODES` | `256` | 645 |
| `GAMMA` | `2.0` | 727 |

**Class `State`** · line 88


**Class `Tree`** · line 102


**Class `HUSearchAgent`** (BaseAgent) · line 859
: Blueprint net where no search is done; heads-up re-solving by CFR on chosen streets (flop with drawn turn/river cards, turn with all river cards, river exactly).

- `__init__(self, blueprint: BaseAgent, iters_turn: int=120, iters_river: int=300, streets: tuple[str, ...]=('turn', 'river'), seed: int=0, iters_flop: int=40, k_…` · L. 864
- `hand_over(self, rec, seat)` · L. 887
- `applies(self, obs: Observation) -> bool` · L. 891
- `preflop(self, obs: Observation) -> Action | None` · L. 896: Heads-up table preflop: equilibrium from hupreflop (None = not applicable).
- `choose_format(self, obs: Observation) -> None` · L. 917: auto: deep cash (no tournament, effective stack >= 80 BB) -> Preflop solver + equilibrium ranges
- `act(self, obs: Observation) -> Action` · L. 929

**Funktionen**

- `chance_cards(board: tuple[int, ...], k: int | None, rng) -> list[int]` · L. 211: Cards for a chance node: all not on the board (k None) or k of them drawn.
- `build_tree(root: State, path: tuple=(), k_turn: int | None=None, k_river: int | None=None, preset: str='narrow', seed: int=0, leaf_street: int | None=None) -> …` · L. 220: Build tree breadth-first: children of a node are contiguous, parents before children.
- `average_reaches(tree: Tree, avg: np.ndarray, r0: np.ndarray, r1: np.ndarray) -> tuple[np.ndarray, np.ndarray]` · L. 330: Reach (= unnormalized range) of both players at EVERY node under the average strategy avg
- `tree_levels(first: np.ndarray, nch: np.ndarray) -> np.ndarray` · L. 355: Level boundaries: the tree is built breadth-first, children are after all nodes of their parent level.
- `board_tables(boards: list[tuple[int, ...]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]` · L. 368: Per board: hand values of all combinations (-1 = blocked) and ascending order of valid ones.
- `leaf_values(tree: Tree, valuenet, reach: np.ndarray, own: np.ndarray, bb: int) -> np.ndarray` · L. 730: Leaf values from the valuenet: per leaf the (normalized) ranges of both players from current reaches,
- `solve(root: State, r0: np.ndarray, r1: np.ndarray, iters: int=200, exploit: bool=False, gamma: float=GAMMA, path: tuple=(), k_turn: int | None=None, k_river: i…` · L. 755: Solves the subgame from root. Returns: tree, average strategy at current node (end of
- `public_ranges(obs: Observation, hero: int, opp: int) -> tuple[np.ndarray, np.ndarray]` · L. 812: Ranges of both players at BEGINNING of the current street, only from public information - the
- `root_state(obs: Observation) -> tuple[State, int, tuple]` · L. 824: State at the start of the current street (0 = us, 1 = opponent) and actions since then.
- `hand_index(cards: list[str]) -> int` · L. 854
- `warmup(streets: tuple[str, ...]=('flop', 'turn', 'river')) -> None` · L. 987: Kernel for the requested streets translated once or loaded from cache (otherwise the first
- `load_valuenet(name: str)` · L. 999: Load value network: path or name under data/valuenet/<name>.pt.
- `set_threads(n: int) -> None` · L. 1010: Limit numba threads per process (affects process-wide; no effect without numba).
- `make_husearch_agent(params: str, seed: int=0) -> HUSearchAgent` · L. 1019
- `load_opp_fold(name: str)` · L. 1053: Fold model (humanfold.HumanFold) from data/humans/<name>.npz or path.
- `load_opp_weights(spec: str) -> dict` · L. 1061: Opponent model '<Run>@<Checkpoint>' (e.g. human-1@1, human network from HandHQ) as numpy weights.

Internal helpers: `_sizes`, `_children`, `_after_check`, `_after_call`, `_after_raise`, `_put`, `_street_end`, `_matches`, `_fold_sums`, `_showdown`, `_solve`, `_solve_small`, `_solve_any`, `_best_response`

### `pokercollector.ai.icm`

File `collector/src/pokercollector/ai/icm.py` · 50 lines

ICM (Independent Chip Model, Malmuth-Harville): tournament equity from the stacks.

**Funktionen**

- `icm_equity(stacks: list[int] | list[float], prizes: list[float], seat: int) -> float` · L. 12: Expected payout (in buy-ins) for `seat` given these stacks. Eliminated (0) have 0.
- `icm_equities(stacks: list[int] | list[float], prizes: list[float]) -> list[float]` · L. 43
- `prizes_from(payouts, players: int) -> list[float]` · L. 47: Payout shares (0.5, 0.3, 0.2) -> prizes in buy-ins with `players` buy-ins prize pool.

### `pokercollector.ai.league`

File `collector/src/pokercollector/ai/league.py` · 296 lines

League with rating, benchmark against fixed opponents and development progression.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `LEAGUE_VERSION` | `'league-1'` | 29 |
| `BETA` | `SIGMA0 / 2` | 31 |
| `KAPPA` | `0.0001` | 32 |
| `GAUNTLET` | `['rock', 'tag', 'station', 'maniac', 'lag']` | 33 |

**Class `Player`** · line 41

- `rating(self) -> float` · L. 53
- `rating_sd(self) -> float` · L. 57
- `conservative(self) -> float` · L. 61

**Class `League`** · line 89

- `__init__(self, root: Path)` · L. 90
- `save(self)` · L. 99
- `add(self, name: str, spec: str | None, kind: str='bot', note: str='') -> Player` · L. 105
- `ensure_defaults(self)` · L. 115
- `agent(self, name: str, seed: int)` · L. 120
- `record_game(self, participants: list[str], ranks: list[float], payouts: list[float], kind: str, extra: dict | None=None)` · L. 126
- `play_round(self, names: list[str], config: TournamentConfig, seed: int) -> dict` · L. 142: A duplicate Sit&Go scheme: all rotations, rank by sum of payouts.
- `run(self, rounds: int, table: int=6, config: TournamentConfig | None=None, seed: int | None=None, progress=None) -> list[dict]` · L. 162: Bots (no humans) in random seatings; those who played less get preference.
- `benchmark(self, name: str, hands: int=300, tournaments: int=10, seed: int=4242, config: TournamentConfig | None=None) -> dict` · L. 183: Fixed opponent group, fixed seed: comparable across versions.
- `games(self) -> list[dict]` · L. 210
- `benchmarks(self) -> list[dict]` · L. 214
- `history(self) -> dict[str, list[tuple[int, float, float]]]` · L. 218: Rating progression per player: (league game no., rating, sigma in display points).
- `pushfold_quality(self) -> dict[str, dict]` · L. 226
- `leaderboard_markdown(self) -> str` · L. 237
- `report_html(self) -> str` · L. 260

**Funktionen**

- `display(mu: float) -> float` · L. 36
- `rate_plackett_luce(ratings: list[tuple[float, float]], ranks: list[float]) -> list[tuple[float, float]]` · L. 65: Weng-Lin Plackett-Luce update. ratings: (mu, sigma) per player; ranks: smaller = better,

### `pokercollector.ai.live`

File `collector/src/pokercollector/ai/live.py` · 523 lines

Live connection Collector -> Bot: proposals with hand history and opponent model.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `HISTORY_KINDS` | `('post_sb', 'post_bb', 'fold', 'check', 'call', 'bet', 'raise')` | 23 |
| `SETTLE_S` | `0.7` | 24 |
| `BUST_S` | `20.0` | 25 |
| `SAME_AMOUNT` | `0.25` | 26 |

**Class `TournamentWatch`** · line 143
: Detects tournament end from completed reconstructed hands (image content only): - own stack after hand 0 -> eliminated; place = 1 + opponents still having chips. Confirmed once next hand starts without own chips or session ends (a single OCR dropout '0' should not end tournament). - only self has c…

- `__init__(self, hero_seat: int=0)` · L. 157
- `on_hand(self, h: dict) -> dict | None` · L. 185: A finished hand (Reconstructor dict). Gives a result as soon as it is determined.
- `on_state(self, state: dict, now: float | None=None) -> dict | None` · L. 241: Table state after each event: if one stack shows all chips of the tournament, it is over; if
- `activity(self, field: str, value) -> None` · L. 305: Opponent’s play activity (bet, highlighting, action label) or own buttons: the hand
- `flush(self) -> dict | None` · L. 315: Session end: an yet unconfirmed elimination counts.
- internal methods: `_reset`, `_result`

**Class `LiveBot`** · line 322

- `__init__(self, agent, hero_seat: int=0, num_seats: int=10, on_result=None)` · L. 323
- `on_event(self, ev: dict, state: dict, now: float)` · L. 347: Process one event (now = time in seconds, same clock as poll()).
- `poll(self, now: float)` · L. 367: Returns (suggestion, observation, opponents) as soon as a new decision situation is calm, otherwise None.
- `playable(self, state: dict) -> bool` · L. 396: Only real decisions: table recognized and own stack readable > 0. After own all-in, after
- `same_as_shown(self, sug, obs) -> bool` · L. 404: Same street, same type, amount barely different: do not retrigger the bar (no flickering
- `feed(self, ev: dict)` · L. 418: Every collector event (as in observations.jsonl) in input order.
- `close(self)` · L. 437: Session end: finish open hand and report an unconfirmed result.
- `session_ended(self)` · L. 447: Recording ended (table gone for longer): report open result, restart reconstruction fresh for next
- `observation(self, state: dict) -> Observation` · L. 462
- `opponents(self, obs: Observation) -> list[tuple[str, dict]]` · L. 488: Opponents in hand with their statistics (name, values) for display.
- `suggest(self, state: dict)` · L. 497
- internal methods: `_relevant`, `_drain`

**Funktionen**

- `fix_dollar_misreads(state: dict, chips: int | None) -> dict` · L. 29: Check implausible numbers in the image against tournament chips.
- `drop_stale_bets(obs: Observation, hand: dict) -> Observation` · L. 56: Bets in the image that the current hand knows no action of the seat for are remnants of a previous
- `sane(sug, obs)` · L. 81: Adjust proposal to the recognized situation: raise never beyond own stack (then all-in), raise not
- `decision_buttons(buttons) -> bool` · L. 99: Action buttons offer call or check (only 'fold' = default).
- `is_decision(state: dict, hero_seat: int=0) -> bool` · L. 104: It's your turn: own seat highlighted AND call/check buttons visible. Buttons alone
- `public_history(hand: dict, num_seats: int=10) -> list[PublicAction]` · L. 110: Public history of a (ongoing) reconstructed hand in the engine format.
- `replay_session(events: list[dict], agent, hero_seat: int=0)` · L. 504: Plays a recorded session as live: returns every suggestion that would have been seen live

Internal helpers: `_alive`

### `pokercollector.ai.nn_agent`

File `collector/src/pokercollector/ai/nn_agent.py` · 243 lines

The learning bot: small neural network (features -> action probabilities + value).

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `NN_VERSION` | `'nn-mlp-1'` | 24 |
| `_CACHE` | `{}` | 25 |
| `NEW_ACTION_TEMPLATE` | `{6: 2, 7: 2}` | 88 |
| `NEW_ACTION_OFFSET` | `-2.0` | 89 |

**Class `NNAgent`** (BaseAgent) · line 164

- `__init__(self, weights: dict, seed: int=0, greedy: bool=False, name: str | None=None, fold_model=None, temp: float=1.0)` · L. 167
- `p_fold_hand(self, obs: Observation) -> float` · L. 181: P(Fold | state, own hand) from fold model: 1 minus continuation factor of own
- `hand_over(self, rec, seat)` · L. 193
- `inputs(self, obs: Observation) -> tuple[np.ndarray, np.ndarray]` · L. 197: Features and action mask exactly as used by act() (for teacher data, teacher.py).
- `act(self, obs: Observation) -> Action` · L. 203

**Funktionen**

- `rl_root() -> Path` · L. 28
- `build_net(hidden: int=128, version: str=FEATURES_VERSION, n_actions: int=N_ACTIONS)` · L. 34: Network for one feature version (input size from FEATURE_SIZES) and number of actions (6 or 8).
- `numpy_weights(net) -> dict` · L. 56
- `forward_np(w: dict, x: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, float]` · L. 63: Probabilities (masked) and value for ONE situation.
- `sharpen(p: np.ndarray, temp: float) -> np.ndarray` · L. 75: Sharpen probabilities with temperature temp: p^(1/temp), renormalized (temp 1 = unchanged,
- `widen_net(net, version: str, n_actions: int | None=None)` · L. 92: Same network for a larger feature version and/or more actions. New inputs
- `save_checkpoint(path: Path, net, meta: dict, extra: dict | None=None)` · L. 120
- `load_checkpoint(path: Path) -> dict` · L. 131
- `net_from_checkpoint(ck: dict)` · L. 140
- `checkpoint_path(run: str, ckpt: str | int='latest') -> Path` · L. 146
- `load_weights(run: str, ckpt: str | int='latest') -> dict` · L. 156
- `make_nn_agent(params: str, seed: int=0) -> NNAgent` · L. 231

### `pokercollector.ai.observation`

File `collector/src/pokercollector/ai/observation.py` · 160 lines

The common interface: what a player sees (Observation) and what he does (Action).

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `STREETS` | `('preflop', 'flop', 'turn', 'river')` | 13 |

**Class `Action`** · line 17

- `fold() -> 'Action'` · L. 25
- `check() -> 'Action'` · L. 29
- `call() -> 'Action'` · L. 33
- `raise_to(amount: int) -> 'Action'` · L. 37
- internal methods: `__str__`

**Class `PublicAction`** · line 42


**Class `Observation`** · line 52

- `stack_bb(self) -> float` · L. 85: Effective own stack (including chips already bet) in big blinds.
- `pot(self) -> int` · L. 90: Entire pot including all bets on the table.
- `my_stack(self) -> int` · L. 95
- `my_bet(self) -> int` · L. 99
- `current_bet(self) -> int` · L. 103
- `opponents_in_hand(self) -> int` · L. 107
- `active_opponents(self) -> int` · L. 112: Opponents who can still act (not folded, not all-in).
- `position(self) -> int` · L. 117: 0 = button, 1 = cutoff, ... (distance counterclockwise from the button among players with cards).
- `street_actions(self, street: str | None=None) -> list[PublicAction]` · L. 124
- `raises_this_street(self) -> int` · L. 128
- `legal(self) -> list[str]` · L. 131

**Class `Agent`** (Protocol) · line 139

- `act(self, obs: Observation) -> Action` · L. 142

**Funktionen**

- `clamp_action(obs: Observation, action: Action) -> Action` · L. 146: Makes an agent action legal (e.g., raise beyond stack -> all-in).

### `pokercollector.ai.opponents`

File `collector/src/pokercollector/ai/opponents.py` · 149 lines

Opponent model: statistics per opponent over previous hands (like a HUD).

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `PRIOR` | `{'vpip': (0.28, 8.0), 'pfr': (0.16, 8.0), 'agg': (0.45, 6.0), 'ftb': …` | 23 |
| `CONF_HANDS` | `20.0` | 24 |
| `OPP_FEATURES` | `8` | 25 |
| `_KEYS` | `('vpip', 'pfr', 'agg', 'ftb')` | 26 |
| `DEFAULT_FEATURES` | `np.array([PRIOR['vpip'][0], PRIOR['pfr'][0], PRIOR['agg'][0], PRIOR['…` | 33 |

**Class `OpponentTracker`** · line 37

- `__init__(self, fuzzy: bool=False)` · L. 38
- `update(self, rec, me: int)` · L. 69: After each hand (simulator, HandRecord): evaluate history (me = own seat, does not count).
- `update_collector(self, hand: dict, me: int)` · L. 74: After each hand (collector, reconstructed hand as a dict like in hands.json).
- `stats(self, key: str) -> dict` · L. 119
- `features(self, obs: Observation) -> np.ndarray` · L. 132
- internal methods: `_key`, `_cnt`, `_count`

**Funktionen**

- `describe(st: dict) -> str` · L. 145: Brief display like a HUD: 'H 23 VPIP 35 % PFR 12 % Agg 40 % FvB 55 %'.

Internal helpers: `_prior_stats`

### `pokercollector.ai.optimize`

File `collector/src/pokercollector/ai/optimize.py` · 285 lines

Self-improvement, step 1: optimization of style parameters of a bot.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `OPT_VERSION` | `'cem-1'` | 36 |
| `SPACE` | `{'vpip': (0.08, 0.6, False), 'pfr': (0.03, 0.45, False), 'value_margi…` | 39 |
| `DEFAULT_POOL` | `['rock', 'tag', 'lag', 'station', 'maniac']` | 51 |
| `DEFAULT_CONFIG` | `TournamentConfig(start_stack=3000, blinds=BlindSchedule(10, 20, 10))` | 52 |
| `RANDOM_SPACE` | `{'vpip': (0.05, 0.9), 'pfr': (0.0, 0.6), 'value_margin': (-0.05, 0.4)…` | 81 |

**Class `LeaguePool`** · line 96
: Opponent selection from the league. players: [(name, spec, mu)], bots only. Weight exp((mu - mu_max) / temperature), at least `floor`: stronger opponents appear more often, weak ones never disappear completely (else bot forgets how to exploit them). random_share: fraction of seats occupied by rando…

- `__init__(self, players: list[tuple[str, str, float]], table: int=5, temperature: float=15.0, floor: float=0.1, self_play: float=0.2, random_share: float=0.0)` · L. 103
- `add(self, name: str, spec: str, weight: float=1.0)` · L. 116
- `shares(self) -> dict[str, float]` · L. 120
- `sample(self, rng: random.Random, self_spec: str | None=None, size: int | None=None) -> list[str]` · L. 124: A table of `size` (default: table) opponents, weighted and without replacement as long as enough

**Funktionen**

- `params_from_style(name: str) -> dict` · L. 55
- `spec_from_params(params: dict, base: str='tag') -> str` · L. 60
- `random_style_spec(rng: random.Random) -> str` · L. 88: A style bot with rolled values. Same RNG state -> same bot (Duplicate-fair).
- `matchup_payouts(spec: str, matchups: list[tuple[int, list[str]]], config: TournamentConfig) -> list[float]` · L. 145: Net payout (buy-ins, averaged over seat rotations) of the candidate per (layout, opponent table).
- `scheme_payouts(spec: str, pool: list[str], schemes: list[int], config: TournamentConfig) -> list[float]` · L. 161: Like matchup_payouts, all layouts against the same fixed pool.
- `pool_desc(pool)` · L. 178
- `run_cem(generations: int=8, population: int=12, schemes_per_gen: int=12, start: str='tag', pool: list[str] | LeaguePool | None=None, config: TournamentConfig=D…` · L. 185
- `gate(candidate_spec: str, champion_spec: str, schemes: int=40, seed: int=777, pool: list[str] | LeaguePool | None=None, config: TournamentConfig=DEFAULT_CONFIG…` · L. 263: Paired comparison on fresh card layouts (in LeaguePool also freshly drawn tables,

Internal helpers: `_norm`, `_denorm`, `_eval_job`, `_matchups`

### `pokercollector.ai.phh`

File `collector/src/pokercollector/ai/phh.py` · 220 lines

Import foreign hand histories in PHH format (Poker Hand History, Univ. Toronto).

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `PHH_VERSION` | `'phh-1'` | 29 |
| `BB_TO_REWARD` | `1 / 15` | 158 |

**Class `ReplayResult`** · line 33


**Funktionen**

- `load_phh(path: Path) -> dict` · L. 39
- `replay(hand: dict, hand_no: int=0) -> ReplayResult` · L. 62: Replays a PHH hand in our engine and collects every decision.
- `build_dataset(files: list[Path], progress=None) -> tuple[dict, dict]` · L. 124: Replay all files. Result: arrays like in imitation + validation report.
- `datasets_dir() -> Path` · L. 161
- `dataset_file(name: str, version: str=FEATURES_VERSION) -> Path` · L. 166: feat-1 named like before '<name>.npz', newer versions '<name>-<version>.npz'.
- `save_dataset(name: str, data: dict, report: dict, version: str=FEATURES_VERSION) -> Path` · L. 171
- `load_dataset(name: str, players: list[str] | None=None, version: str=FEATURES_VERSION) -> dict` · L. 181
- `forward_batch(w: dict, X: np.ndarray, M: np.ndarray) -> np.ndarray` · L. 197
- `agreement(w: dict, data: dict) -> dict` · L. 209: How well does a network predict the decisions in the dataset?

Internal helpers: `_split`, `_build_deck`

### `pokercollector.ai.play`

File `collector/src/pokercollector/ai/play.py` · 209 lines

Game sessions human versus bots and their evaluation.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `PLAY_VERSION` | `'play-1'` | 24 |

**Class `SessionWriter`** · line 40

- `__init__(self, path: Path, meta: dict)` · L. 41
- `write(self, obj: dict)` · L. 47
- `close(self, end: dict)` · L. 51

**Funktionen**

- `rec_from_dict(d: dict) -> HandRecord` · L. 31
- `play_cash(human: HumanAgent, bots: list, out_dir: Path, hands: int=1000, stack_bb: int=100, blinds: tuple[int, int]=(10, 20), seed: int | None=None) -> Path` · L. 56: Cash game: stacks remain; anyone falling below 1 BB automatically rebuys.
- `play_tournament_session(human: HumanAgent, bots: list, out_dir: Path, config: TournamentConfig, seed: int | None=None) -> tuple[Path, object]` · L. 93
- `load_sessions(play_dir: Path) -> list[dict]` · L. 134
- `player_stats(sessions: list[dict]) -> dict` · L. 153: Key figures per player name over all sessions (human and bots).
- `stats_markdown(sessions: list[dict], human: str='du') -> str` · L. 180

Internal helpers: `_rec_to_dict`

### `pokercollector.ai.pushfold`

File `collector/src/pokercollector/ai/pushfold.py` · 338 lines

Push/Fold equilibrium (Nash) for short stacks.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `PUSHFOLD_VERSION` | `'pushfold-1'` | 32 |
| `MATRIX_FILE` | `'hand_vs_hand.json'` | 33 |
| `TABLE_FILE` | `'pushfold_nash.json'` | 34 |
| `CLASSES` | `all_classes()` | 35 |
| `IDX` | `{c: i for i, c in enumerate(CLASSES)}` | 36 |
| `STACKS` | `[1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 1…` | 37 |
| `MAX_BEHIND` | `8` | 38 |
| `_ENC` | `'0123456789X'` | 193 |

**Class `PushFoldGame`** · line 129
: Pusher + k callers, all with effective stack S (in BB).

- `__init__(self, S: float, k: int, E: np.ndarray, W: np.ndarray)` · L. 132
- `pusher_ev(self, calls: list[np.ndarray]) -> np.ndarray` · L. 139: EV (net, BB) of pushing per pusher hand against call probabilities per caller.
- `caller_ev(self, push: np.ndarray, i: int) -> np.ndarray` · L. 154: EV (net) of calling per caller hand against the push range (earlier caller folded).
- `solve(self, iterations: int=600) -> dict` · L. 161
- `exploitability(self, push: np.ndarray, calls: list[np.ndarray]) -> dict` · L. 173: Gain (BB per hand of the respective player) of a perfect counter-strategy per role.
- `range_pct(self, strat: np.ndarray) -> float` · L. 189

**Funktionen**

- `class_combos_concrete(cls: str) -> tuple[tuple[str, str], ...]` · L. 44
- `combo_weights() -> np.ndarray` · L. 57: W[a, b] = number of compatible (card-independent) combination pairs of class a and b.
- `build_matrix(samples: int=3000, seed: int=11, processes: int | None=None, progress=None) -> dict` · L. 93
- `matrix() -> tuple[np.ndarray, np.ndarray]` · L. 114
- `build_table(iterations: int=600, progress=None) -> dict` · L. 204
- `nash_table() -> dict` · L. 233
- `push_probability(hole: list[str], stack_bb: float, behind: int) -> float | None` · L. 247: Equilibrium probability for push as first player with `behind` players behind.
- `call_probability(hole: list[str], stack_bb: float, behind_at_push: int, my_index: int) -> float | None` · L. 256: Equilibrium call against a push. behind_at_push = player behind the pusher,
- `range_classes(stack_bb: float, behind: int, role: str='push', caller: int=0) -> list[str]` · L. 266
- `grid_text(stack_bb: float, behind: int, role: str='push', caller: int=0) -> str` · L. 273: 13x13 grid: top right suited, bottom left offsuit, diagonal pairs.
- `decision_ev(hole: list[str], spot: dict, chose: str) -> dict | None` · L. 310: Evaluates a push/fold decision against opponents playing Nash.

Internal helpers: `_equity_row`, `_blinds`, `_encode`, `_decode`, `_entry`, `_game_and_nash`

### `pokercollector.ai.ranges`

File `collector/src/pokercollector/ai/ranges.py` · 256 lines

Ranges: which hands is an opponent likely to have after their previous actions?

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `RANGES_VERSION` | `'ranges-1'` | 30 |
| `COMBOS` | `np.array([(i, j) for i in range(52) for j in range(i + 1, 52)], np.in…` | 31 |
| `COMBO_PCT` | `np.array([preflop_percentile([FULL_DECK[i], FULL_DECK[j]]) for i, j i…` | 32 |
| `OPEN_Q` | `(0.3, 0.1, 0.045, 0.03)` | 33 |
| `CALL_Q` | `(0.6, 0.35, 0.14, 0.06)` | 34 |
| `COMBO_HAS` | `np.zeros((52, len(COMBOS)), bool)` | 42 |
| `PRE_RAISE` | `[_sig((q - COMBO_PCT) / 0.03) for q in OPEN_Q]` | 45 |
| `PRE_CALL` | `[_sig((q - COMBO_PCT) / 0.05) for q in CALL_Q]` | 46 |
| `OPEN_Q_HU` | `(0.85, 0.15, 0.06, 0.035)` | 48 |
| `CALL_Q_HU` | `(0.9, 0.7, 0.45, 0.12)` | 49 |
| `PRE_RAISE_HU` | `[_sig((q - COMBO_PCT) / 0.05) for q in OPEN_Q_HU]` | 50 |
| `PRE_CALL_HU` | `[_sig((q - COMBO_PCT) / 0.06) for q in CALL_Q_HU]` | 51 |

**Funktionen**

- `dead_mask(cards: list[str]) -> np.ndarray` · L. 54
- `board_strength(board: tuple[str, ...]) -> np.ndarray` · L. 81: Strength of each combination on this board as percentile (0 weakest .. 1 strongest).
- `board_factors(board: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray, np.ndarray]` · L. 95: Factors for Bet/Raise, Call, Check on this board (precomputed, cached).
- `opponent_ranges(obs: Observation, heads_up: bool=False) -> dict[int, np.ndarray]` · L. 101: Weights (sum 1) over the 1326 combinations for every opponent still in hand.
- `equity_vs_ranges(obs: Observation, iterations: int=200, seed: int=0, ranges: dict[int, np.ndarray] | None=None) -> float` · L. 221
- `sample_hands(ranges: dict[int, np.ndarray], dead: list[str], rng: np.random.Generator, tries: int=50) -> dict[int, list[str]] | None` · L. 233: Draws consistent opponent hands from the ranges (for search: possible 'worlds').
- `range_summary(r: np.ndarray) -> dict` · L. 252: For display/tests: how tight is the range (weight proportion in top 10% / 30%)?

Internal helpers: `_sig`, `_strengths`, `_mc_vs_ranges`

### `pokercollector.ai.recording`

File `collector/src/pokercollector/ai/recording.py` · 81 lines

Logs decisions of any agent (bot or human) and evaluates push/fold situations against the Nash equilibrium.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `PF_MAX_BB` | `15` | 12 |

**Class `DecisionLog`** · line 31

- `summary(self) -> dict` · L. 36

**Class `RecordingAgent`** · line 46
: Wrapper around an agent; forwards everything and logs.

- `__init__(self, agent, log: DecisionLog | None=None)` · L. 49
- `name(self)` · L. 54
- `name(self, v)` · L. 58
- `act(self, obs: Observation) -> Action` · L. 61
- `hand_over(self, rec, seat)` · L. 77

**Funktionen**

- `classify_pf_choice(obs: Observation, action: Action, spot: dict) -> str | None` · L. 15

### `pokercollector.ai.replay`

File `collector/src/pokercollector/ai/replay.py` · 199 lines

Bridge Collector -> Observation.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `BOARD_COUNT` | `{'preflop': 0, 'flop': 3, 'turn': 4, 'river': 5}` | 15 |
| `DECISION_TYPES` | `('fold', 'check', 'call', 'bet', 'raise')` | 16 |

**Funktionen**

- `decision_points(hand: dict, hero_seat: int=0, num_seats: int=10) -> list[tuple[Observation, dict]]` · L. 19
- `live_pot(st: dict, bets: list[int], bb: int, unc: list[str]) -> int | None` · L. 97: Pot including ongoing bets. Two sources in the image: the pot display in center of the table (pot.total,
- `observation_from_table_state(st: dict, hero_seat: int=0, num_seats: int=10) -> Observation` · L. 115: Live: player perspective from the stabilized field state of the collector.
- `review_hands(hands: list[dict], agent, hero_seat: int=0) -> list[dict]` · L. 181: Asks the agent at each own decision and compares proposal and true action.

### `pokercollector.ai.rl`

File `collector/src/pokercollector/ai/rl.py` · 638 lines

How the bot learns: first imitation (Behavior Cloning), then self-play with PPO.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `RL_VERSION` | `'ppo-1'` | 44 |

**Class `RLConfig`** · line 48


**Class `_Collector`** · line 87
: Joint bookkeeping: decisions per hand, reward at end of hand.

- `__init__(self, scale: float, start_stack: int, icm: float=0.0)` · L. 90
- `hand_over(self, rec, seat)` · L. 130
- internal methods: `_begin`, `_reward`

**Class `_Learner`** (_Collector) · line 141

- `__init__(self, w: dict, rng: random.Random, scale: float, start_stack: int, name: str='learner', icm: float=0.0)` · L. 142
- `hand_over(self, rec, seat)` · L. 151
- `act(self, obs)` · L. 156

**Class `_Teacher`** (_Collector) · line 168

- `__init__(self, agent, scale: float, start_stack: int)` · L. 169
- `act(self, obs)` · L. 174
- `hand_over(self, rec, seat)` · L. 180

**Funktionen**

- `behavior_clone(run_dir: Path, teacher: str='rock', tournaments: int=600, epochs: int=10, hidden: int=128, config: TournamentConfig=DEFAULT_CONFIG, seed: int=1,…` · L. 240
- `fit_bc(run_dir: Path, data: dict, source: dict, epochs: int=10, hidden: int=128, seed: int=1, progress=None, label_smoothing: float=0.05, t0: float | None=None…` · L. 257: Train network on collected decisions (x, mask, a, r) -> ckpt_000000.pt.
- `gae(r: np.ndarray, v: np.ndarray, done: np.ndarray, lam: float) -> tuple[np.ndarray, np.ndarray]` · L. 319: Advantages and target values, gamma = 1 within a hand, episode ends at done.
- `snapshot_spec(run: str, it: int) -> str` · L. 341
- `eval_fixed(spec: str, cfg: RLConfig, config: TournamentConfig, ex) -> float` · L. 345: ROI against fixed pool with always the same card schemes (learning curve, no gating).
- `train_ppo(run_dir: Path, iterations: int, pool: LeaguePool | list[str], cfg: RLConfig | None=None, config: TournamentConfig=DEFAULT_CONFIG, workers: int | None…` · L. 367: e.g., existing process pool (e.g., for exploiter within a run) - saves RAM.
- `exploit_test(target: str, init_ckpt: Path, iterations: int=40, schemes: int=48, seed: int=9, config: TournamentConfig=DEFAULT_CONFIG, workers: int | None=None,…` · L. 600: Exploitability: an exploiter learns only against 5 copies of the test subject (PPO, no leash).
- `new_run_dir(prefix: str='nn') -> Path` · L. 636

Internal helpers: `_pack`, `_concat`, `_rollout_job`, `_bc_job`, `_accuracy`, `_write_jsonl`, `_eval_chunk`, `_run_name`, `_ppo_update`

### `pokercollector.ai.search`

File `collector/src/pokercollector/ai/search.py` · 164 lines

Search during play - basis for Pluribus-like lookahead.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `SEARCH_VERSION` | `'search-1'` | 34 |

**Class `SearchAgent`** (BaseAgent) · line 89
: Rollout search over a blueprint strategy. last_q: estimated value per action (BB) - also usable for live recommendations. min_gain: minimum advantage (BB) over blueprint choice.

- `__init__(self, blueprint: str, worlds: int=24, min_gain: float=0.25, seed: int=0, name: str | None=None)` · L. 94
- `act(self, obs: Observation) -> Action` · L. 105

**Funktionen**

- `world_from_obs(obs: Observation, opp_hands: dict[int, list[str]], rng: random.Random, hand_id: str='world') -> Hand` · L. 37: Complete game state that looks the same to player obs.seat as obs.
- `play_out(h: Hand, agents, seat: int) -> float` · L. 78: Plays out the hand to the end with given agents (list per seat or one agent for all).
- `make_search_agent(params: str, seed: int=0) -> SearchAgent` · L. 158: 'search?bp=pros-2@300,worlds=24' (bp = net run@checkpoint; ',' or '&' separate - ',' is cmd-safe).

### `pokercollector.ai.slumbot`

File `collector/src/pokercollector/ai/slumbot.py` · 272 lines

Measurement against Slumbot (slumbot.com) - a strong public heads-up bot as absolute benchmark.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `API` | `'https://slumbot.com/api'` | 36 |
| `SLUMBOT_VERSION` | `'slumbot-1'` | 38 |

**Class `SlumbotError`** (RuntimeError) · line 42


**Funktionen**

- `parse_action(action: str) -> list[list[tuple[str, int | None]]]` · L. 63: 'b200c/kb300' -> [[('b',200),('c',None)], [('k',None),('b',300)]]
- `replay(action: str, client_pos: int, hole: list[str], board: list[str], bot_hole: list[str] | None=None, seed: int=0) -> Hand` · L. 85: Reconstructs game state in engine. Unknown cards (opponents, upcoming board cards) random.
- `to_incr(obs, action: Action) -> str` · L. 114
- `allin_ev(h: Hand, hole: list[str], bot_hole: list[str]) -> float | None` · L. 144: Net (chips) for us after all-in EV, if all-in occurred before the river and cards were shown.
- `play_hand(agent, token: str | None, seed: int) -> dict` · L. 159
- `results_dir() -> Path` · L. 186
- `load_hands(name: str) -> list[dict]` · L. 191
- `summarize(hands: list[dict]) -> dict` · L. 209
- `adjusted(hands: list[dict]) -> dict` · L. 218: All-in EV adjusted with card luck (baseline, expectation 0) as control variable.
- `run(spec: str, name: str, hands: int, workers: int=4, progress=None) -> dict` · L. 235: Play up to `hands` more hands with `workers` parallel Slumbot sessions.

Internal helpers: `_post`, `_equity`, `_stat`

### `pokercollector.ai.tables`

File `collector/src/pokercollector/ai/tables.py` · 118 lines

Preflop equity table: 169 starting hand classes against 1-9 random opponents.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `TABLE_FILE` | `'preflop_equity.json'` | 17 |

**Funktionen**

- `hand_class(cards: list[str]) -> str` · L. 20: ['As','Kd'] -> 'AKo', ['Th','Ts'] -> 'TT', ['9c','8c'] -> '98s'.
- `all_classes() -> list[str]` · L. 30
- `class_combos(cls: str) -> int` · L. 42
- `example_cards(cls: str) -> list[str]` · L. 46
- `build_preflop_table(iterations: int=1500, heads_up_iterations: int=8000, seed: int=7, max_opponents: int=9, progress=None) -> dict` · L. 72: Column '1 opponent' more precise as it determines the ranking of starting hands.
- `save_table(table: dict, path: Path)` · L. 88
- `preflop_table() -> dict` · L. 93
- `preflop_equity(cards: list[str], opponents: int) -> float` · L. 98
- `preflop_percentile(cards: list[str]) -> float` · L. 116

Internal helpers: `_equity`, `_percentiles`

### `pokercollector.ai.teacher`

File `collector/src/pokercollector/ai/teacher.py` · 204 lines

Search as teacher (Expert Iteration, leverage H5): the heads-up search plays, the network learns its decisions.

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `TEACHER_VERSION` | `'teacher-1'` | 29 |

**Class `TeacherRecorder`** · line 32
: Wrapper around a HUSearchAgent: plays as it does, remembers every searched decision as a teaching example.

- `__init__(self, search_agent, student, name: str='lehrer')` · L. 35
- `hand_over(self, rec, seat)` · L. 42
- `act(self, obs: Observation) -> Action` · L. 48

**Funktionen**

- `resolve_opponent(name: str) -> str` · L. 75: 'mensch-N' -> style specification from data/humans/mensch-25nl.json (like bench 'mensch'); otherwise unchanged.
- `collect(search_spec: str, student_spec: str, opponents: list[str], hands: int, stacks_bb: list[int], out: Path | str, seed: int=1, progress=None) -> dict` · L. 86: One match (duplicate) per opponent and stack depth: search against opponent; teacher examples into one .npz.
- `load(paths: list[Path | str]) -> dict` · L. 122
- `fit(student_run: str, student_ckpt: int | str, paths: list[Path | str], out_run: str, epochs: int=10, batch: int=512, lr: float=0.0003, kl_coef: float=0.5, hol…` · L. 129: Retrain student on soft teacher targets: loss = cross-entropy(target, student)

### `pokercollector.ai.tournament`

File `collector/src/pokercollector/ai/tournament.py` · 305 lines

Tournament mode (Sit & Go like PokerTH).

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `TOURNAMENT_VERSION` | `'tournament-1'` | 26 |
| `POKERTH_DEFAULT` | `TournamentConfig(start_stack=1000, blinds=BlindSchedule(10, 20, 9))` | 68 |
| `PLAYER_WEIGHTS` | `{2: 1.5, 3: 1.0, 4: 1.0, 5: 1.0, 6: 2.0, 7: 1.0, 8: 1.0, 9: 1.5, 10: …` | 71 |
| `HANDS_PER_LEVEL` | `(5, 6, 8, 9, 10, 12, 15, 20)` | 72 |

**Class `BlindSchedule`** · line 30

- `at(self, hand_no: int) -> dict` · L. 37: Blinds for hand number hand_no (0-based).

**Class `TournamentConfig`** · line 54

- `payout_for_place(self, place: int, players: int) -> float` · L. 60: Payout in buy-ins: prize money = players * buy-ins.

**Class `TournamentResult`** · line 96


**Class `TournamentStats`** · line 187

- `result(self, per_unit_tournaments: int) -> dict` · L. 196

**Funktionen**

- `random_players(rng, weights: dict[int, float] | None=None) -> int` · L. 75
- `random_config(rng, players: int) -> TournamentConfig` · L. 80: Start stack 20-200 BB (log-uniform, often 50 BB like in PokerTH), blind tempo 5-20 hands,
- `play_tournament(agents: list, config: TournamentConfig=TournamentConfig(), seed: int=0, keep_records: bool=False, on_hand=None, stop=None) -> TournamentResult` · L. 129: stop(stacks) -> True ends after the hand (e.g. training: learning bot is out).
- `run_tournaments(agents: list, count: int, config: TournamentConfig=TournamentConfig(), seed: int=1, duplicate: bool=True, progress=None, keep_example: bool=Fal…` · L. 211: count tournaments; with duplicate=True each tournament card setup
- `tournaments_markdown(res: dict) -> str` · L. 276
- `tournament_text(res: TournamentResult) -> str` · L. 297

Internal helpers: `_assign_places`

### `pokercollector.ai.valuedata`

File `collector/src/pokercollector/ai/valuedata.py` · 263 lines

Training data for the value network of the search (Milestone 3, level 1b).

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `VALUEDATA_VERSION` | `'vdata-1'` | 31 |
| `BB` | `100` | 32 |
| `STREET_CARDS` | `{'flop': 3, 'turn': 4, 'river': 5}` | 33 |
| `ITERS_DEFAULT` | `{'flop': 60, 'turn': 150, 'river': 300, 'river-leaf': 300, 'turn-leaf…` | 34 |
| `LEAF_TURN_ITERS` | `60` | 39 |
| `LEAF_PER_TURN` | `24` | 40 |
| `LEAF_MIN_MASS` | `1e-06` | 41 |
| `TL_FLOP_ITERS` | `40` | 46 |
| `TL_K_TURN` | `8` | 47 |
| `TL_K_RIVER` | `4` | 48 |
| `TL_PER_FLOP` | `12` | 49 |
| `_VNET` | `{}` | 50 |

**Funktionen**

- `sample_ranges(rng: np.random.Generator, board: list[str]) -> tuple[np.ndarray, np.ndarray]` · L. 53: Two board-dependent ranges (sum 1). Mix of uniform, tight/loose (soft strength threshold),
- `sample_state(rng: np.random.Generator, street: str) -> tuple[State, list[str], float, float]` · L. 79: State at street start: pot 2..80 BB, stack/pot 0.25..8 (log-uniform), both stacks
- `get_vnet(name: str | None)` · L. 95: Load River value network once per process (None = no net, exact).
- `solve_sample(seed: int, street: str, iters: int, vnet: str | None=None) -> dict` · L. 105
- `solve_leaf_samples(seed: int, iters: int=300, iters_turn: int=LEAF_TURN_ITERS, max_per_turn: int=LEAF_PER_TURN) -> list[dict]` · L. 136: River situations from a real Turn search: Turn state + synthetic start ranges, full turn tree
- `solve_turn_leaf_samples(seed: int, iters: int=150, vnet: str | None='vnet-river-1', iters_flop: int=TL_FLOP_ITERS, max_per_flop: int=TL_PER_FLOP) -> list[dict]` · L. 174: Turn situations from a real flop search: Flop state + synthetic start ranges, flop tree with
- `data_dir() -> Path` · L. 205
- `generate(street: str, n: int, out: Path | str, seed: int=0, iters: int | None=None, workers: int=1, threads: int | None=None, progress=None, vnet: str | None=N…` · L. 210: Solve n situations and write as one .npz shard. Seeds seed..seed+n-1 (reproducible).
- `load(path: Path | str) -> dict` · L. 258

Internal helpers: `_river_row`, `_roots_rows`, `_worker`

### `pokercollector.ai.valuenet`

File `collector/src/pokercollector/ai/valuenet.py` · 240 lines

Value network for the search (Milestone 3): public state + both ranges -> counterfactual values per combo for both players (in pot units) as exact CFR+ solution delivers (valuedata.py).

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `VALUENET_VERSION` | `'vnet-1'` | 32 |
| `N_COMBOS` | `1326` | 33 |
| `N_IN` | `52 + 3 + 4 + 2 * N_COMBOS` | 34 |
| `N_OUT` | `2 * N_COMBOS` | 35 |
| `_COMBOS` | `np.array([(a, b) for a in range(52) for b in range(a + 1, 52)], np.in…` | 38 |

**Class `ValueMLP`** (nn.Module if nn else object) · line 74

- `__init__(self, width: int=1024, depth: int=3)` · L. 75
- `forward(self, x)` · L. 85

**Class `ValueNet`** · line 102
: Loaded network for search: predict(...) returns v0, v1 in pot units (exact zero-sum).

- `__init__(self, model, device: str='cpu', threads: int | None=2)` · L. 105
- `load(cls, path: Path | str, device: str='cpu', threads: int | None=2) -> 'ValueNet'` · L. 113
- `predict(self, board, pot_bb, stack_bb, oop, r0, r1) -> tuple[np.ndarray, np.ndarray]` · L. 120

**Funktionen**

- `combo_mask(board: np.ndarray) -> np.ndarray` · L. 41: [n, 1326] True for combos without board card. board: int8[n, 5], -1 = empty.
- `features(board: np.ndarray, pot_bb: np.ndarray, stack_bb: np.ndarray, oop: np.ndarray, r0: np.ndarray, r1: np.ndarray) -> np.ndarray` · L. 52: float32[n, N_IN].
- `zero_sum_fix(v0: np.ndarray, v1: np.ndarray, r0: np.ndarray, r1: np.ndarray, mask: np.ndarray | None=None) -> tuple[np.ndarray, np.ndarray]` · L. 89: Enforce exact zero-sum: error e = r0.v0 + r1.v1 distributed evenly on both sides (ReBeL), only on
- `load_shards(paths: list[str]) -> dict` · L. 130
- `train(paths: list[str], out: Path | str, epochs: int=10, batch: int=512, lr: float=0.001, width: int=1024, depth: int=3, holdout: float=0.02, device: str | Non…` · L. 138
- `main(argv=None)` · L. 218

### `pokercollector.ai.ziele`

File `collector/src/pokercollector/ai/ziele.py` · 166 lines

Our targets (GOALS.md in the project folder) and the scoreboard: where does a bot rank per benchmark?

**Konstanten**

| Name | Value | Line |
| --- | --- | --- |
| `ZIELE_VERSION` | `'ziele-1'` | 22 |
| `MEASURE_SETS` | `('mensch480', 'nash240', 'kurz240')` | 23 |
| `PAYOUTS` | `TournamentConfig().payouts` | 24 |
| `GOALS` | `{1: ('Real PokerTH games', ['50 tournaments, ROI > 0', '200 tournamen…` | 27 |

**Funktionen**

- `pokerth_log() -> Path` · L. 36
- `add_tournament(place: int, players: int, bot: str, note: str='', **extra) -> dict` · L. 40: extra: further information (e.g. hands, session, source 'auto'), is recorded.
- `remove_last_tournament(bot: str) -> dict | None` · L. 53: Remove last entry for this bot (correction of an incorrect automatic detection).
- `pokerth_summary(bot: str | None=None) -> dict | None` · L. 67
- `latest(name: str) -> dict` · L. 89: Latest values per test set for this name (later entries overwrite earlier ones).
- `scoreboard(name: str, slumbot_name: str | None=None, pokerth_bot: str | None=None) -> list[dict]` · L. 143
- `scoreboard_text(name: str, rows: list[dict]) -> str` · L. 157

Internal helpers: `_stage`

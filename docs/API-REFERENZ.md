# API-Referenz

Automatisch erzeugt aus dem Quelltext (`scripts/gen_reference.py`): 64 Module, 16966 Zeilen. Pro Modul: Zweck, Konstanten, Klassen mit Methoden, Funktionen mit Signatur und erster Docstring-Zeile. Die Erklaerung der Zusammenhaenge steht in `TECHNISCHE-DOKUMENTATION.md`.

## Inhalt

- pokercollector (Erfassung, Rekonstruktion, Bedienung): `__init__`, `advisor`, `analyzer`, `capture`, `cards`, `cli`, `compare`, `fastpoker`, `geometry`, `glyphs`, `journal`, `layout`, `ocr`, `overlay`, `parse`, `pipeline`, `poker`, `profile`, `__init__`, `reconstruct`, `reference`, `report`, `stabilize`, `system`
- pokercollector.ai (KI: Engine, Bots, Training, Suche, Wertnetze): `__init__`, `agents`, `bench`, `bpranges`, `cfr`, `confirm`, `deepcfr`, `engine`, `evaluate`, `features`, `gtow`, `human`, `humanbots`, `humandata`, `humanfold`, `humans`, `hupreflop`, `husearch`, `icm`, `league`, `live`, `nn_agent`, `observation`, `opponents`, `optimize`, `phh`, `play`, `pushfold`, `ranges`, `recording`, `replay`, `rl`, `search`, `slumbot`, `tables`, `teacher`, `tournament`, `valuedata`, `valuenet`, `ziele`

## pokercollector (Erfassung, Rekonstruktion, Bedienung)

### `pokercollector`

Datei `collector/src/pokercollector/__init__.py` · 2 Zeilen

### `pokercollector.advisor`

Datei `collector/src/pokercollector/advisor.py` · 126 Zeilen

Baseline-Entscheidungshilfe: Equity gegen zufaellige Haende + Pot Odds.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `ADVISOR_VERSION` | `'baseline-equity-1'` | 17 |

**Klasse `GameState`** · Zeile 21


**Klasse `Advice`** · Zeile 34

- `to_dict(self)` · Z. 44

**Funktionen**

- `state_from_snapshot_state(st: dict, hero_seat: int=0) -> GameState` · Z. 48: Baut den Spielzustand aus dem stabilisierten Feldzustand (Stabilizer.state()).
- `advise(gs: GameState, iterations: int=2500, seed: int=0, margin: float=0.05) -> Advice` · Z. 82

### `pokercollector.analyzer`

Datei `collector/src/pokercollector/analyzer.py` · 352 Zeilen

Frame -> TableSnapshot: alle sichtbaren Felder mit Rohwert, Konfidenz und Bildbereich.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `ANALYZER_VERSION` | `f'analyzer-1/{OCR_VERSION}/{CARDS_VERSION}'` | 26 |
| `_STACK_LIKE` | `re.compile('[$S§]\\s*[0-9OolI]¦^\\s*[0-9][0-9 .,]*\\s*$')` | 57 |

**Klasse `FieldObs`** · Zeile 30


**Klasse `TableSnapshot`** · Zeile 40

- `get(self, key: str, default=None)` · Z. 49
- `set(self, key: str, value, **kw)` · Z. 53

**Klasse `FrameAnalyzer`** · Zeile 110

- `__init__(self, profile: Profile, ocr: RegionOcr, cards: CardReader)` · Z. 111
- `reset(self)` · Z. 117: Neue Sitzung/neuer Tisch: gelernte Sitzpositionen vergessen.
- `analyze(self, frame: np.ndarray, frame_index: int=0, t_mono: float=0.0, t_wall: float=0.0) -> TableSnapshot` · Z. 121
- interne Methoden: `_info_row`, `_pot`, `_board`, `_action_bar`, `_seat`

Interne Helfer: `_up`, `_strict_money`, `_has_money`, `_has_name_and_stack`, `_panel_regions`, `_yellow_border_share`, `_panel_tint`

### `pokercollector.capture`

Datei `collector/src/pokercollector/capture.py` · 432 Zeilen

Bildquellen und segmentierte Aufnahme.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `_MASK_WINDOWS` | `set()` | 44 |
| `_MASK_LOCK` | `threading.Lock()` | 45 |
| `MASK_RING_PX` | `3` | 46 |

**Klasse `Frame`** · Zeile 32


**Klasse `VideoFileSource`** · Zeile 92

- `__init__(self, path: str | Path, step_s: float | None=None, start_wall: float | None=None)` · Z. 93
- `describe(self) -> dict` · Z. 104
- interne Methoden: `__iter__`

**Klasse `SessionVideoSource`** · Zeile 125
: Spielt die Video-Abschnitte einer Live-Sitzung nacheinander ab - mit den ECHTEN Aufnahmezeiten je Bild aus segment_XXXX.frames.jsonl (fuer die Nachauswertung, z. B. nach einem Analysefehler).

- `__init__(self, session_dir: str | Path)` · Z. 129
- `describe(self) -> dict` · Z. 138
- interne Methoden: `__iter__`

**Klasse `ImageDirSource`** · Zeile 159

- `__init__(self, path: str | Path, interval_s: float=1.0)` · Z. 160
- `describe(self) -> dict` · Z. 166
- interne Methoden: `__iter__`

**Klasse `WindowInfo`** · Zeile 182


**Klasse `WindowSource`** · Zeile 293
: Liest den Client-Bereich eines Fensters mit fester Bildrate.

- `__init__(self, hwnd: int, fps: float=10.0, max_seconds: float | None=None, require_foreground: bool=True)` · Z. 296
- `describe(self) -> dict` · Z. 310
- interne Methoden: `__iter__`

**Klasse `SegmentRecorder`** · Zeile 370
: Schreibt Frames in kurze Videosegmente plus Zeitstempel-Sidecar (JSONL).

- `__init__(self, video_dir: Path, fps: float, segment_s: float=120.0, codec: str='mp4v')` · Z. 377
- `current_segment(self) -> str | None` · Z. 391
- `write(self, frame: Frame) -> tuple[str, int]` · Z. 409
- `close(self)` · Z. 425
- interne Methoden: `_open`

**Funktionen**

- `register_mask_window(hwnd: int) -> None` · Z. 49: Fenster (z. B. die Lynx-Leiste) ab jetzt aus jeder WindowSource-Aufnahme ausschneiden.
- `unregister_mask_window(hwnd: int) -> None` · Z. 56
- `mask_windows() -> list[int]` · Z. 61
- `apply_masks(img: np.ndarray, origin: tuple[int, int], rects: list[tuple[int, int, int, int]], ring: int=MASK_RING_PX) -> list[list[int]]` · Z. 66: Schneidet Bildschirm-Rechtecke (x, y, w, h) aus `img` aus, dessen linke obere Ecke bei `origin` liegt.
- `list_windows(title_filter: str='') -> list[WindowInfo]` · Z. 224
- `window_info(hwnd: int, title: str='', fg: int | None=None) -> WindowInfo | None` · Z. 254
- `window_rect(hwnd: int) -> tuple[int, int, int, int] | None` · Z. 277: Ganzes Fenster in Bildschirmpixeln (x, y, w, h); None, wenn geschlossen, unsichtbar oder minimiert.

Interne Helfer: `_user32`, `_ensure_dpi_aware`

### `pokercollector.cards`

Datei `collector/src/pokercollector/cards.py` · 307 Zeilen

Kartenerkennung: Slot-Zustand (leer / Rueckseite / offen), Rang und Farbe.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `CARDS_VERSION` | `'cards-1'` | 24 |
| `GLYPH_SIZE` | `(20, 28)` | 25 |

**Klasse `CardRead`** · Zeile 29


**Klasse `SlotRead`** · Zeile 42


**Klasse `TemplateStore`** · Zeile 56
: Gelernte Glyphen-Vorlagen auf der Festplatte (PNG, 255 = Tinte).

- `__init__(self, root: Path | None)` · Z. 59
- `match(self, kind: str, glyph: np.ndarray) -> tuple[str | None, float, float]` · Z. 77: (bestes Label, Score, Abstand zum zweitbesten Label).
- `add(self, kind: str, label: str, glyph: np.ndarray, name: str) -> Path | None` · Z. 96

**Klasse `CardReader`** · Zeile 149

- `__init__(self, profile: Profile, ocr: RegionOcr | None, templates: TemplateStore | None=None)` · Z. 150
- `read_face(self, frame: np.ndarray, rect: Rect) -> CardRead` · Z. 201
- `read_region(self, frame: np.ndarray, hsv: np.ndarray, region: Rect, scale: float) -> SlotRead` · Z. 293
- interne Methoden: `_face_rects`, `_count_backs`

**Funktionen**

- `valid_rank(r: str | None) -> bool` · Z. 305

Interne Helfer: `_normalize_glyph`, `_suit_heuristic`, `_rank_text_ok`

### `pokercollector.cli`

Datei `collector/src/pokercollector/cli.py` · 1465 Zeilen

Kommandozeile. Aufruf: pokercollector <befehl> ... (oder start.cmd auf dem Stick).

**Funktionen**

- `data_dir() -> Path` · Z. 17
- `sessions_dir() -> Path` · Z. 25
- `templates_dir() -> Path` · Z. 31
- `cmd_calibrate(a)` · Z. 53
- `cmd_analyze(a)` · Z. 73
- `cmd_windows(a)` · Z. 104
- `cmd_live(a)` · Z. 125
- `cmd_humans_fit(a)` · Z. 242
- `cmd_leiste_demo(a)` · Z. 259
- `cmd_live_replay(a)` · Z. 280
- `cmd_reconstruct(a)` · Z. 297
- `cmd_report(a)` · Z. 309
- `cmd_inspect_reference(a)` · Z. 314
- `cmd_compare(a)` · Z. 320
- `cmd_advise(a)` · Z. 335
- `cmd_harvest_cards(a)` · Z. 354: Speichert Rang-/Farb-Glyphen erkannter offener Karten als Vorlagen.
- `cmd_sim_agents(a)` · Z. 390
- `cmd_sim_match(a)` · Z. 398
- `cmd_sim_hand(a)` · Z. 427
- `cmd_sim_tournament(a)` · Z. 439
- `cmd_sim_pushfold(a)` · Z. 474
- `cmd_sim_review(a)` · Z. 489
- `cmd_play(a)` · Z. 512
- `cmd_play_stats(a)` · Z. 556
- `cmd_league(a)` · Z. 561
- `cmd_data(a)` · Z. 613
- `cmd_bench(a)` · Z. 692
- `cmd_cfr(a)` · Z. 795
- `cmd_deepcfr(a)` · Z. 822
- `cmd_exploit(a)` · Z. 845
- `cmd_train_nn(a)` · Z. 862
- `cmd_valuedata(a)` · Z. 942
- `cmd_teacher(a)` · Z. 955
- `cmd_humanfold(a)` · Z. 977
- `cmd_valuenet(a)` · Z. 986
- `cmd_train(a)` · Z. 1001
- `cmd_verify(a)` · Z. 1057
- `main(argv=None)` · Z. 1064

Interne Helfer: `_session_path`, `_analyzer`, `_pick_window`, `_agent_spec`, `_print_suggestion`, `_league`, `_league_pool`, `_pool_text`

### `pokercollector.compare`

Datei `collector/src/pokercollector/compare.py` · 282 Zeilen

Feldweiser Vergleich der visuellen Rekonstruktion mit dem Referenzexport.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `COMPARE_VERSION` | `'compare-1'` | 17 |
| `_ACTION_TYPES` | `{'fold', 'check', 'call', 'bet', 'raise', 'post_sb', 'post_bb', 'alli…` | 96 |

**Klasse `FieldTally`** · Zeile 52

- `add(self, kind: str)` · Z. 59
- `as_dict(self)` · Z. 62

**Klasse `CompareResult`** · Zeile 74

- `to_dict(self)` · Z. 83

**Funktionen**

- `map_seats(visual_hands: list[dict], ref_hands: list[RefHand]) -> dict[int, int]` · Z. 27: Visueller Sitz -> Referenzsitz ueber Spielernamen (Praefix, da Namen abgeschnitten sein koennen).
- `compare(visual_hands: list[dict], ref_hands: list[RefHand], hero_seat_visual: int=0) -> CompareResult` · Z. 135

Interne Helfer: `_norm_name`, `_align`

### `pokercollector.fastpoker`

Datei `collector/src/pokercollector/fastpoker.py` · 203 Zeilen

Schnelle Handbewertung und Monte-Carlo-Equity (numba, Maschinencode).

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `CARD_INDEX` | `{c: i for i, c in enumerate(FULL_DECK)}` | 19 |

**Funktionen**

- `eval_cards(cards, n)` · Z. 63
- `to_ints(cards: list[str]) -> np.ndarray` · Z. 190
- `evaluate_fast(cards: list[str]) -> int` · Z. 194
- `mc_stats(hole: list[str], board: list[str], opponents: int, iterations: int, seed: int, dead: list[str] | None=None) -> tuple[float, float, int, int]` · Z. 198: (Summe, Quadratsumme, Siege, Splits). dead: zusaetzlich bekannte Karten (selten, Python-Weg).

Interne Helfer: `_straight_high`, `_top`, `_mc`

### `pokercollector.geometry`

Datei `collector/src/pokercollector/geometry.py` · 79 Zeilen

Einfache Rechteck-Geometrie in Pixelkoordinaten (x, y, Breite, Hoehe).

**Klasse `Rect`** · Zeile 11

- `x2(self) -> int` · Z. 18
- `y2(self) -> int` · Z. 22
- `cx(self) -> float` · Z. 26
- `cy(self) -> float` · Z. 30
- `area(self) -> int` · Z. 34
- `clip(self, width: int, height: int) -> 'Rect'` · Z. 37
- `crop(self, img: np.ndarray) -> np.ndarray` · Z. 44
- `offset(self, dx: int, dy: int) -> 'Rect'` · Z. 48
- `expand(self, d: int) -> 'Rect'` · Z. 51
- `sub(self, rx: float, ry: float, rw: float, rh: float, scale: float=1.0) -> 'Rect'` · Z. 54: Teilrechteck relativ zur linken oberen Ecke, Masse in Referenzpixeln * scale.
- `contains(self, x: float, y: float) -> bool` · Z. 63
- `iou(self, other: 'Rect') -> float` · Z. 66
- `as_list(self) -> list[int]` · Z. 73
- `from_list(v) -> 'Rect'` · Z. 77

### `pokercollector.glyphs`

Datei `collector/src/pokercollector/glyphs.py` · 81 Zeilen

Kartenraenge per Formvergleich mit gezeichneten Schrift-Vorlagen erkennen.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `GLYPH_SIZE` | `(20, 28)` | 21 |
| `RANK_TEXT` | `{'2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '8'…` | 22 |
| `FONT_DIR` | `Path('C:/Windows/Fonts')` | 24 |
| `FONTS` | `['arialbd.ttf', 'arial.ttf', 'segoeuib.ttf', 'segoeui.ttf', 'verdanab…` | 25 |
| `ASPECT_WEIGHT` | `0.6` | 32 |

**Funktionen**

- `font_templates() -> list[tuple[str, np.ndarray, float, str]]` · Z. 41: (Rang, normierte Glyphe, Seitenverhaeltnis b/h, Schrift) fuer alle verfuegbaren Schriften.
- `match_rank(glyph: np.ndarray, aspect: float) -> tuple[str | None, float, float]` · Z. 67: (Rang, Score, Abstand zum zweitbesten Rang). glyph: normiert wie cards._normalize_glyph.

Interne Helfer: `_norm`

### `pokercollector.journal`

Datei `collector/src/pokercollector/journal.py` · 226 Zeilen

Sitzungsordner, append-only Beobachtungsjournal (JSONL), Belegbilder, SQLite-Index.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `SCHEMA_VERSION` | `1` | 35 |

**Klasse `Session`** · Zeile 60

- `__init__(self, root: Path, meta: dict[str, Any])` · Z. 61
- `create(base: Path, source: dict[str, Any], profile_id: str, analyzer_version: str, extra: dict[str, Any] | None=None) -> 'Session'` · Z. 73
- `open(root: Path) -> 'Session'` · Z. 99
- `save_meta(self)` · Z. 103
- `gap(self, t_start: float, t_end: float, reason: str)` · Z. 111
- `error(self, message: str, **kw)` · Z. 117
- `write_event(self, event, frame: np.ndarray | None=None, segment: str | None=None, save_evidence: bool=True) -> dict` · Z. 122
- `close(self)` · Z. 141

**Funktionen**

- `dumps(o) -> str` · Z. 56
- `read_events(root: Path) -> list[dict]` · Z. 149
- `build_index(root: Path)` · Z. 166
- `sha256_file(p: Path) -> str` · Z. 196
- `write_manifest(root: Path)` · Z. 204
- `verify_manifest(root: Path) -> list[str]` · Z. 212
- `monotonic() -> float` · Z. 224

Interne Helfer: `_utc_now`, `_json_default`

### `pokercollector.layout`

Datei `collector/src/pokercollector/layout.py` · 280 Zeilen

Findet Tisch, Sitz-Panels, Board-Karten, Marker und Aktionsleiste im Frame.

**Klasse `SeatPanel`** · Zeile 24


**Klasse `Marker`** · Zeile 33


**Klasse `TableLayout`** · Zeile 41


**Klasse `SeatMemory`** · Zeile 57
: Gelernte Sitzpositionen eines Tisches (relativ zum Filz). Index in `positions` = Sitznummer.

- `__init__(self, tol: float=0.06)` · Z. 60
- `reset(self)` · Z. 64
- `assign(self, centers: list[tuple[float, float]], hero: int | None) -> list[int]` · Z. 67: Sitznummer je Panel-Mittelpunkt. Erste Belegung: eigener Platz 0, dann im Uhrzeigersinn.

**Funktionen**

- `detect_layout(frame: np.ndarray, profile: Profile, memory: SeatMemory | None=None) -> TableLayout` · Z. 206

Interne Helfer: `_felt_rect`, `_dark_components`, `_find_markers`

### `pokercollector.ocr`

Datei `collector/src/pokercollector/ocr.py` · 235 Zeilen

OCR-Schicht. Standard: Windows.Media.Ocr (kein Zusatzprogramm noetig).

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `OCR_VERSION` | `'winocr-1'` | 18 |

**Klasse `OcrLine`** · Zeile 22


**Klasse `OcrResult`** · Zeile 28

- `text(self) -> str` · Z. 32

**Klasse `OcrBackend`** (Protocol) · Zeile 36

- `recognize(self, img: np.ndarray) -> list[tuple[str, tuple[float, float, float, float]]]` · Z. 39: Zeilen (Text, (x, y, w, h)) in Bildkoordinaten des uebergebenen Bildes.

**Klasse `WindowsOcr`** · Zeile 43

- `__init__(self, language: str | None=None)` · Z. 46
- `recognize(self, img: np.ndarray)` · Z. 62

**Klasse `FakeOcr`** · Zeile 99
: Fuer Tests: liefert vorgegebene Texte je nach Bild-Hash oder immer dieselben.

- `__init__(self, fixed: list[tuple[str, tuple[float, float, float, float]]] | None=None)` · Z. 104
- `recognize(self, img)` · Z. 107

**Klasse `RegionOcr`** · Zeile 115
: OCR auf Bildausschnitten mit Vorverarbeitung und Aenderungs-Cache.

- `__init__(self, backend: OcrBackend, upscale: float=3.0, cache_tolerance: float=1.5)` · Z. 123
- `read(self, frame: np.ndarray, rect: Rect, key: str | None=None, upscale: float | None=None, accept=None) -> OcrResult` · Z. 167: Liest einen Bereich. Mit `accept` (Funktion OcrResult -> bool) werden bei
- `read_glyph_tiled(self, glyph_ink: np.ndarray, repeats: int=3, heights: tuple[int, ...]=(120, 80, 160), accept=None) -> str` · Z. 204: Liest ein einzelnes Zeichen (binaere Tinte=255), indem es mehrfach nebeneinander
- interne Methoden: `_thumb`, `_recognize`, `_cached`

**Funktionen**

- `default_backend() -> OcrBackend` · Z. 111
- `image_digest(img: np.ndarray) -> str` · Z. 233

### `pokercollector.overlay`

Datei `collector/src/pokercollector/overlay.py` · 295 Zeilen

Lynx-Leiste: kleines schwebendes Feld ueber der Taskleiste (neben Uhr und Akku) mit dem Vorschlag.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `OVERLAY_VERSION` | `'leiste-2'` | 27 |
| `GWL_EXSTYLE` | `-20` | 28 |
| `COLORS` | `{'fold': ('#8a2b2b', '#ffffff'), 'check': ('#2b6a3a', '#ffffff'), 'ca…` | 31 |
| `STATUS_DOT` | `{'ok': '#3ddc84', 'warn': '#f5c542', 'err': '#ff5252', 'off': '#55555…` | 40 |
| `TONES` | `{'fold': [(392, 90)], 'check': [(587, 90)], 'call': [(587, 90)], 'rai…` | 41 |
| `GERMAN` | `{'fold': 'Fold', 'call': 'Call', 'raise_half': '½ Pot', 'raise_pot': …` | 87 |
| `WARNINGS` | `{'Pot unbekannt oder widerspruechlich': 'Pot nicht erkannt', 'zu call…` | 89 |

**Klasse `Advice`** · Zeile 46
: Was die Leiste anzeigt.


**Klasse `Leiste`** · Zeile 132

- `__init__(self, sound: bool=True, title: str='Lynx')` · Z. 135
- `start(self) -> 'Leiste'` · Z. 145
- `show(self, adv: Advice, beep: bool=True)` · Z. 150: Neuer Vorschlag: du bist dran.
- `idle(self)` · Z. 154: Nicht (mehr) dran: Leiste blass, letzter Vorschlag bleibt lesbar.
- `status(self, level: str, text: str)` · Z. 158: Statuspunkt: ok | warn | err | off, mit kurzem Text (Tooltip-artig rechts unten).
- `close(self)` · Z. 162
- interne Methoden: `_run`, `_style_window`, `_paint`, `_pump`, `_drag_start`, `_drag`, `_drag_end`, `_popup`, `_toggle_sound`, `_label_sound`, `_default_pos`, `_reset_pos`, `_load_pos`, `_save_pos`

**Funktionen**

- `advice_from(sug, obs, agent=None) -> Advice` · Z. 54: Vorschlag (Action) + Observation -> Anzeige. Betraege in Chips und Big Blinds.
- `alternatives(agent, obs=None) -> list[tuple[str, float]]` · Z. 93: Wahrscheinlichkeiten der Aktionen (groesste zuerst), wenn der Bot sie verraet.
- `settings_path() -> Path` · Z. 112

Interne Helfer: `_work_area`, `_beep`

### `pokercollector.parse`

Datei `collector/src/pokercollector/parse.py` · 196 Zeilen

Parser fuer OCR-Texte der PokerTH-Web-Oberflaeche.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `_DIGIT_FIXES` | `str.maketrans({'O': '0', 'o': '0', 'D': '0', 'Q': '0', 'l': '1', 'I':…` | 13 |
| `_MONEY_IN_TEXT` | `re.compile("[$S§]\\s*[0-9OolI](?:[0-9OolI]¦[ .,'](?=[0-9OolI]{3}))*")` | 66 |
| `_STREETS` | `{'preflop': 'preflop', 'flop': 'flop', 'turn': 'turn', 'river': 'rive…` | 87 |
| `_ACTION_WORDS` | `[('allin', 'allin'), ('all-in', 'allin'), ('fold', 'fold'), ('check',…` | 144 |

**Klasse `Parsed`** · Zeile 18


**Funktionen**

- `parse_money(text: str | None) -> Parsed` · Z. 30: '$3 000', 'S3 000', '$O', '$2.980', '3000' -> int Chips.
- `extract_money(text: str | None) -> Parsed` · Z. 69: Sucht den ersten Betrag mit Waehrungszeichen in einer Zeile ('• $20' -> 20).
- `parse_street(text: str | None) -> Parsed` · Z. 96
- `parse_game_hand(text: str | None) -> Parsed` · Z. 108: 'Spiel: 1 Hand: 12' -> (1, 12).
- `parse_blinds(text: str | None) -> Parsed` · Z. 120: '10/20 ↑8' (OCR oft '10/20+8') -> {'sb':10,'bb':20,'extra':'8'}.
- `parse_labeled_money(text: str | None, label: str) -> Parsed` · Z. 133: 'Einsätze: $30' mit label='eins' -> 30.
- `parse_action_label(text: str | None) -> Parsed` · Z. 167
- `parse_button(text: str | None) -> Parsed` · Z. 183: Aktionsknopf 'Call $20' / 'Raise $40' / 'Check' / 'Bet $20' -> (aktion, betrag|None).

Interne Helfer: `_fix_digits`, `_edit_distance`

### `pokercollector.pipeline`

Datei `collector/src/pokercollector/pipeline.py` · 294 Zeilen

Verbindet Quelle -> Analyse -> Stabilisierung -> Journal -> Rekonstruktion.

**Klasse `RunStats`** · Zeile 54

- `summary(self) -> dict` · Z. 64

**Klasse `LiveRunner`** · Zeile 133
: Automatische Sitzungen fuer ein Live-Fenster.

- `__init__(self, source, sessions_dir: Path, profile: Profile, analyzer: FrameAnalyzer, fps: float, detect_frames: int=5, stop_after_s: float=20.0, segment_s: fl…` · Z. 136
- `run(self)` · Z. 157
- interne Methoden: `_set_status`

**Funktionen**

- `make_analyzer(profile: Profile, templates_dir: Path | None=None, ocr_backend=None) -> FrameAnalyzer` · Z. 38
- `write_hands(session_root: Path) -> list` · Z. 43
- `run_offline(source, sessions_dir: Path, profile: Profile, analyzer: FrameAnalyzer, on_event: Callable | None=None, progress: Callable | None=None) -> Path` · Z. 83

Interne Helfer: `_log_events`

### `pokercollector.poker`

Datei `collector/src/pokercollector/poker.py` · 184 Zeilen

Karten, 7-Karten-Handbewertung und Monte-Carlo-Equity.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `RANKS` | `'23456789TJQKA'` | 13 |
| `SUITS` | `'shdc'` | 14 |
| `SUIT_SYMBOLS` | `{'s': '♠', 'h': '♥', 'd': '♦', 'c': '♣'}` | 15 |
| `FULL_DECK` | `[r + s for r in RANKS for s in SUITS]` | 16 |
| `CATEGORY_NAMES` | `['High Card', 'Pair', 'Two Pair', 'Three of a Kind', 'Straight', 'Flu…` | 18 |

**Klasse `EquityResult`** · Zeile 103


**Funktionen**

- `is_card(c: str | None) -> bool` · Z. 24
- `normalize_rank(token: str) -> str | None` · Z. 28
- `evaluate(cards: list[str]) -> tuple` · Z. 48: Bewertet 5-7 Karten. Groesseres Tupel = staerkere Hand. Element 0 = Kategorie.
- `describe(value: tuple) -> str` · Z. 98
- `equity_vs_random(hero: list[str], board: list[str], opponents: int, iterations: int=3000, seed: int | None=0, dead: list[str] | None=None) -> EquityResult` · Z. 113: Monte-Carlo-Equity gegen `opponents` zufaellige Haende.
- `pot_odds(to_call: int, pot: int) -> float` · Z. 179: Benoetigte Equity fuer einen profitablen Call ohne zukuenftige Einsaetze.

Interne Helfer: `_straight_high`

### `pokercollector.profile`

Datei `collector/src/pokercollector/profile.py` · 42 Zeilen

Laden versionierter Tischprofile.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `DEFAULT_PROFILE` | `'pokerth_web_v1.json'` | 12 |

**Klasse `Profile`** · Zeile 15

- `__init__(self, data: dict[str, Any], path: str)` · Z. 16
- `id(self) -> str` · Z. 23
- `hsv(self, *keys) -> tuple[np.ndarray, np.ndarray]` · Z. 29
- `load(path: str | Path | None=None) -> 'Profile'` · Z. 36
- interne Methoden: `__getitem__`

### `pokercollector.profiles`

Datei `collector/src/pokercollector/profiles/__init__.py` · 1 Zeilen

### `pokercollector.reconstruct`

Datei `collector/src/pokercollector/reconstruct.py` · 755 Zeilen

Regelbasierte Handrekonstruktion aus stabilisierten Feldereignissen.

**Konstanten**

| Name | Wert | Zeile |
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

**Klasse `Action`** · Zeile 41


**Klasse `SeatInfo`** · Zeile 58


**Klasse `Hand`** · Zeile 70

- `to_dict(self) -> dict` · Z. 89

**Klasse `_StreetState`** · Zeile 95

- `__init__(self, name: str, t: float)` · Z. 96

**Klasse `Reconstructor`** · Zeile 105

- `__init__(self, num_seats: int=NUM_SEATS)` · Z. 106
- `feed(self, ev: dict)` · Z. 603
- `finish(self, t_end: float | None=None) -> list[Hand]` · Z. 724
- interne Methoden: `_name`, `_in_hand`, `_seat_info`, `_add_action`, `_first_to_act`, `_check_order`, `_start_hand`, `_settle`, `_finish_hand`, `_close_street`, `_flush_close`, `_new_street`, `_bet_change`, `_bet_change_now`, `_apply_bet`, `_late_for_prev`, `_fold`, `_label`, `_active_change`, `_resolve_pending`, `_stack_change`, `_seat_event`

**Funktionen**

- `reconstruct(events: list[dict]) -> list[Hand]` · Z. 747

Interne Helfer: `_priority`

### `pokercollector.reference`

Datei `collector/src/pokercollector/reference.py` · 271 Zeilen

Import des PokerTH-Handverlaufs als unabhaengige Referenz.

**Konstanten**

| Name | Wert | Zeile |
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

**Klasse `ReferenceFormatError`** (Exception) · Zeile 49


**Klasse `RefAction`** · Zeile 69


**Klasse `RefHand`** · Zeile 79

- `to_dict(self)` · Z. 90

**Funktionen**

- `decode_card(v) -> str | None` · Z. 53
- `inspect(path: Path) -> dict[str, list[str]]` · Z. 94
- `load_pokerth_log(path: Path) -> list[RefHand]` · Z. 118
- `load_pokerth_text_log(path: Path) -> list[RefHand]` · Z. 206
- `load_reference(path: Path) -> list[RefHand]` · Z. 262: Erkennt das Format: SQLite (.pdb) oder Text-Log des Web-Clients.

Interne Helfer: `_find`, `_col`, `_norm_text_card`

### `pokercollector.report`

Datei `collector/src/pokercollector/report.py` · 121 Zeilen

Kalibrier-Overlay und lesbare Berichte (Markdown).

**Funktionen**

- `overlay(frame: np.ndarray, snap: TableSnapshot) -> np.ndarray` · Z. 15
- `hands_markdown(session_root: Path) -> str` · Z. 65
- `compare_markdown(result: dict) -> str` · Z. 103

Interne Helfer: `_cards`

### `pokercollector.stabilize`

Datei `collector/src/pokercollector/stabilize.py` · 121 Zeilen

Zeitliche Stabilisierung einzelner Felder.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `FAST_FIELDS` | `('hero.to_act',)` | 19 |

**Klasse `FieldEvent`** · Zeile 27


**Klasse `_Track`** · Zeile 44


**Klasse `Stabilizer`** · Zeile 59

- `state(self) -> dict[str, Any]` · Z. 66
- `update(self, snap: TableSnapshot) -> list[FieldEvent]` · Z. 69
- interne Methoden: `_transient`

Interne Helfer: `_key`

### `pokercollector.system`

Datei `collector/src/pokercollector/system.py` · 28 Zeilen

Systemhilfen: Standby waehrend langer Laeufe verhindern.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `ES_CONTINUOUS` | `2147483648` | 8 |
| `ES_SYSTEM_REQUIRED` | `1` | 9 |
| `ES_DISPLAY_REQUIRED` | `2` | 10 |

**Funktionen**

- `keep_awake(enabled: bool=True)` · Z. 14: Verhindert Leerlauf-Standby, solange der Block laeuft (Windows SetThreadExecutionState).

## pokercollector.ai (KI: Engine, Bots, Training, Suche, Wertnetze)

### `pokercollector.ai`

Datei `collector/src/pokercollector/ai/__init__.py` · 2 Zeilen

Simulation, Spielerblick-Schnittstelle, Bots und Bewertung (Stufen 1-3 der KI).

### `pokercollector.ai.agents`

Datei `collector/src/pokercollector/ai/agents.py` · 328 Zeilen

Gegner-Pool: regelbasierte Bots mit einstellbarem Stil plus Baseline-Agenten.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `AGENTS_VERSION` | `'agents-1'` | 24 |
| `STYLES` | `{'station': Style(vpip=0.6, pfr=0.03, value_margin=0.3, raise_margin=…` | 148 |
| `REGISTRY` | `{'random': lambda seed=0: RandomAgent(seed), 'caller': lambda seed=0:…` | 274 |

**Klasse `BaseAgent`** · Zeile 82

- `__init__(self, seed: int=0, name: str | None=None)` · Z. 85
- `rng(self, obs: Observation) -> random.Random` · Z. 90
- `act(self, obs: Observation) -> Action` · Z. 93
- `passive(obs: Observation) -> Action` · Z. 97
- `raise_to(obs: Observation, amount: float) -> Action` · Z. 101

**Klasse `RandomAgent`** (BaseAgent) · Zeile 108
: Zufaellig unter den erlaubten Aktionen - Untergrenze fuer jede Bewertung.

- `act(self, obs)` · Z. 112

**Klasse `CallAgent`** (BaseAgent) · Zeile 121
: Checkt oder callt immer (deterministisch, fuer Tests).

- `act(self, obs)` · Z. 125

**Klasse `Style`** · Zeile 130


**Klasse `StyleBot`** (BaseAgent) · Zeile 162

- `__init__(self, style: str, seed: int=0, iterations: int=120, name: str | None=None)` · Z. 163
- `act(self, obs)` · Z. 239
- interne Methoden: `_push_fold`, `_preflop`, `_postflop`

**Klasse `EquityAgent`** (BaseAgent) · Zeile 246
: Die Baseline aus advisor.py als Agent: Equity gegen Zufallshaende vs. Pot Odds.

- `__init__(self, seed: int=0, iterations: int=300, name: str | None=None)` · Z. 250
- `act(self, obs)` · Z. 255

**Funktionen**

- `mc_equity(hole: list[str], board: list[str], opponents: int, iterations: int, rng: random.Random) -> float` · Z. 27: Equity gegen `opponents` zufaellige Haende (kleines Monte-Carlo).
- `push_fold_spot(obs: Observation) -> dict` · Z. 54: Ordnet eine Preflop-Situation dem Push/Fold-Modell zu.
- `make_agent(spec: str, seed: int=0) -> BaseAgent` · Z. 282: 'tag', 'tag:Name' (Name zur Unterscheidung) oder mit eigenen Stilwerten

### `pokercollector.ai.bench`

Datei `collector/src/pokercollector/ai/bench.py` · 321 Zeilen

Pruefstand: jeder Kandidat durchlaeuft dieselben festen Testsets - vergleichbar ueber Wochen.

**Konstanten**

| Name | Wert | Zeile |
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

- `parse_set(name: str) -> tuple[str, int]` · Z. 64: 'mix960' -> ('mix96', 960): Basis-Set (bestimmt Karten und Tische) und Anzahl Schemata.
- `is_tournament_set(name: str) -> bool` · Z. 77
- `set_config(name: str) -> TournamentConfig` · Z. 81
- `bench_set(name: str) -> list[tuple[int, list[str]]]` · Z. 90
- `run_set(spec: str, name: str, ex, config=None, on_chunk=None, partial: Path | None=None) -> dict` · Z. 152: 24 Blöcke parallel. on_chunk(fertig, gesamt, zwischenstand) nach jedem Block; partial = Datei, in der
- `run_cash(spec: str, hands: int=300) -> dict` · Z. 184
- `bench_dir() -> Path` · Z. 192
- `run_bench(spec: str, name: str, sets=('fest48', 'mix96', 'cash', 'pluribus'), exploit: bool=False, ex=None, workers: int | None=None, progress=None, on_chunk=N…` · Z. 197: progress(set, ergebnis) je fertigem Set; on_chunk(fertig, gesamt, zwischenstand) je Block;
- `load_results() -> list[dict]` · Z. 241
- `paired_diff(a: dict, b: dict, s: str) -> dict | None` · Z. 248: Gepaarter Vergleich zweier Ergebnisse auf demselben Testset (gleiche Schemata).
- `write_report() -> str` · Z. 255
- `compare(name_a: str, name_b: str) -> list[tuple[str, dict, dict, dict]]` · Z. 303: Gepaarter Vergleich zweier Pruefstand-Eintraege auf allen gemeinsamen Turnier-Testsets:

Interne Helfer: `_chunk`, `_summary`

### `pokercollector.ai.bpranges`

Datei `collector/src/pokercollector/ai/bpranges.py` · 199 Zeilen

Blueprint-Ranges fuer die Heads-up-Suche (husearch.py).

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `CLASSES` | `all_classes()` | 34 |
| `CLASS_ID` | `{c: i for i, c in enumerate(CLASSES)}` | 35 |
| `COMBO_CLASS` | `np.array([CLASS_ID[hand_class([FULL_DECK[i], FULL_DECK[j]])] for i, j…` | 36 |
| `CLASS_CARDS` | `[example_cards(c) for c in CLASSES]` | 37 |
| `COMBO_CARDS` | `[[FULL_DECK[i], FULL_DECK[j]] for i, j in COMBOS]` | 38 |
| `_CACHE` | `{}` | 40 |
| `_CACHE_MAX` | `512` | 41 |

**Funktionen**

- `forward_batch(w: dict, x: np.ndarray, mask: np.ndarray) -> np.ndarray` · Z. 44: Wahrscheinlichkeiten des Netzes fuer viele Situationen (Zeilen) mit gemeinsamer Aktionsmaske.
- `blueprint_ranges(obs: Observation, hero: int, opp: int, blueprint, bp_streets: tuple[str, ...]=('preflop',), opp_weights: dict | None=None, opp_fold=None) -> t…` · Z. 117: Ranges (Summe 1) von hero und opp zu BEGINN der aktuellen Strasse aus dem Blueprint-Netz.

Interne Helfer: `_action`, `_deck_for`, `_blueprint_probs`, `_apply_blueprint`, `_apply_heuristic`, `_cache_key`, `_compute`

### `pokercollector.ai.cfr`

Datei `collector/src/pokercollector/ai/cfr.py` · 296 Zeilen

Gleichgewicht statt Ausbeutung: Monte-Carlo-CFR wie beim Blueprint von Pluribus.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `CFR_VERSION` | `'mccfr-1'` | 45 |
| `HAND_BUCKETS_PRE` | `20` | 46 |
| `HAND_BUCKETS_POST` | `12` | 47 |
| `_RADIX` | `(4, 20, 6, 5, 5, 5, 4, 2)` | 48 |
| `_POLICY_CACHE` | `{}` | 246 |

**Klasse `_Worker`** · Zeile 116

- `__init__(self, regrets: dict, rng: random.Random)` · Z. 117
- `traverse(self, h: Hand, p: int) -> float` · Z. 125

**Klasse `CFRAgent`** (BaseAgent) · Zeile 260
: Spielt die Durchschnittsstrategie. Unbekannte Situation: einfache Equity-Regel (gezaehlt).

- `__init__(self, policy: dict, seed: int=0, name: str | None=None)` · Z. 264
- `act(self, obs: Observation)` · Z. 271

**Funktionen**

- `abstract_mask(obs: Observation) -> np.ndarray` · Z. 51
- `infokey(obs: Observation, cache: dict | None=None) -> int` · Z. 65
- `decode(code: int) -> dict` · Z. 95
- `regret_matching(reg: np.ndarray | None, mask: np.ndarray) -> np.ndarray` · Z. 104
- `random_hand(rng: random.Random) -> Hand` · Z. 152
- `save_average(path: Path, strategy: dict)` · Z. 192
- `train_cfr(run_dir: Path, rounds: int, traversals: int=400, workers: int | None=None, seed: int=1, progress=None) -> dict` · Z. 202: rounds: Zielrunde (Gesamtzahl). Je Runde: workers x traversals Durchlaeufe mit der Strategie vom
- `load_policy(run: str) -> dict` · Z. 249
- `make_cfr_agent(params: str, seed: int=0) -> CFRAgent` · Z. 291

Interne Helfer: `_bucket`, `_job`, `_save_state`, `_load_state`

### `pokercollector.ai.confirm`

Datei `collector/src/pokercollector/ai/confirm.py` · 40 Zeilen

Einmalige Bestaetigung zweier Bots gegen Mensch-Bots auf FRISCHEN Tischen und Karten.

**Funktionen**

- `human_tables(schemes: int, seed: str, bots_name: str='mensch-25nl') -> list[tuple[int, list[str]]]` · Z. 18
- `confirm_vs_humans(spec_a: str, spec_b: str, schemes: int=600, seed: str='1', workers: int | None=None) -> dict` · Z. 25

### `pokercollector.ai.deepcfr`

Datei `collector/src/pokercollector/ai/deepcfr.py` · 280 Zeilen

Deep CFR: CFR mit neuronalen Netzen statt Tabelle (Brown, Lerer, Gross, Sandholm 2019).

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `DEEPCFR_VERSION` | `'deepcfr-1'` | 41 |

**Klasse `DeepCFRConfig`** · Zeile 45


**Klasse `_Traverser`** · Zeile 76

- `__init__(self, w: dict | None, rng: random.Random, t: int, scale: float)` · Z. 77
- `policy(self, x, amask)` · Z. 83
- `traverse(self, h: Hand, p: int) -> float` · Z. 88

**Klasse `Reservoir`** · Zeile 129
: Gleichmaessige Stichprobe ueber alle je gesehenen Datenpunkte (Algorithmus R), feste Groesse.

- `__init__(self, capacity: int, rng: np.random.Generator)` · Z. 132
- `add(self, x, m, y, t: int)` · Z. 142
- `state(self) -> dict` · Z. 162
- `load(self, d: dict, prefix: str)` · Z. 166

**Funktionen**

- `strategy_from_adv(adv: np.ndarray, mask: np.ndarray) -> np.ndarray` · Z. 65: Regret Matching auf vorhergesagten Vorteilen. Alles <= 0: bestes erlaubtes Aktion (Deep-CFR-Regel).
- `train_strategy(buf: Reservoir, cfg: DeepCFRConfig, gen)` · Z. 192: Durchschnittsstrategie: Netz lernt die gespeicherten Mischungen (gewichtet mit t, Linear CFR).
- `train_deepcfr(run_dir: Path, iterations: int, cfg: DeepCFRConfig | None=None, workers: int | None=None, progress=None, on_snapshot=None) -> dict` · Z. 213

Interne Helfer: `_adv_np`, `_job`, `_train_adv`

### `pokercollector.ai.engine`

Datei `collector/src/pokercollector/ai/engine.py` · 349 Zeilen

No-Limit-Hold'em-Spielleiter fuer 2-10 Spieler.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `ENGINE_VERSION` | `'nlhe-engine-1'` | 25 |

**Klasse `IllegalAction`** (Exception) · Zeile 34


**Klasse `SeatResult`** · Zeile 39

- `net(self) -> int` · Z. 48

**Klasse `HandRecord`** · Zeile 53


**Klasse `Hand`** · Zeile 68
: Eine einzelne Hand. Ablauf: h = Hand(...); while not h.done: h.apply(seat, agent.act(h.observation(seat))).

- `__init__(self, stacks: list[int], button: int, small_blind: int, big_blind: int, seed: int | None=None, deck: list[str] | None=None, hand_id: str='', names: li…` · Z. 71
- `clone(self) -> 'Hand'` · Z. 116: Schnelle Kopie des Spielstands (CFR spielt von einem Punkt aus jede eigene Aktion durch).
- `legal(self, s: int) -> dict` · Z. 169
- `observation(self, s: int) -> Observation` · Z. 182
- `apply(self, s: int, action: Action)` · Z. 196
- interne Methoden: `_next`, `_can_act`, `_live`, `_put`, `_post_blinds`, `_needs_action`, `_round_complete`, `_advance`, `_next_street`, `_run_out`, `_finish`

**Funktionen**

- `play_hand(agents: list, stacks: list[int], button: int, small_blind: int, big_blind: int, seed: int | None=None, hand_id: str='', names=None, on_illegal: str='…` · Z. 328: Spielt eine Hand mit den gegebenen Agenten (Index = Platz). Unzulaessige Aktionen

### `pokercollector.ai.evaluate`

Datei `collector/src/pokercollector/ai/evaluate.py` · 190 Zeilen

Bewertung von Agenten ueber viele Haende.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `EVAL_VERSION` | `'eval-1'` | 25 |
| `_T975` | `[12.71, 4.3, 3.18, 2.78, 2.57, 2.45, 2.36, 2.31, 2.26, 2.23, 2.2, 2.1…` | 28 |

**Klasse `AgentStats`** · Zeile 41

- `result(self, big_blind: int, hands_per_unit: float) -> dict` · Z. 54

**Funktionen**

- `t95(n: int) -> float` · Z. 32: Faktor fuer ein 95-%-Intervall bei n Stichproben (kleine n: t-Verteilung).
- `run_match(agents: list, hands: int, seed: int=1, small_blind: int=10, big_blind: int=20, stack_bb: int=100, duplicate: bool=True, progress=None, keep_records: …` · Z. 102: agents: Liste von Agent-Objekten (2-10). hands: Anzahl Kartenblaetter.
- `report_markdown(res: dict) -> str` · Z. 146
- `hand_text(rec: HandRecord) -> str` · Z. 164: Lesbarer Handverlauf (fuer Fehlersuche).
- `save_result(res: dict, path: Path)` · Z. 187

Interne Helfer: `_tally`

### `pokercollector.ai.features`

Datei `collector/src/pokercollector/ai/features.py` · 233 Zeilen

Was der lernende Bot sieht: Observation -> Zahlenvektor fester Laenge, plus die Aktionsmenge.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `FEATURES_VERSION` | `'feat-2'` | 36 |
| `FEATURE_SIZES` | `{'feat-1': 46, 'feat-2': 49, 'feat-3': 57}` | 37 |
| `RANGE_EQUITY_ITERATIONS` | `120` | 38 |
| `ACTIONS` | `('fold', 'call', 'raise_half', 'raise_pot', 'raise_2pot', 'allin')` | 39 |
| `ACTIONS_8` | `ACTIONS + ('raise_third', 'raise_min')` | 40 |
| `RAISE_FRACTIONS` | `{2: 0.5, 3: 1.0, 4: 2.0}` | 41 |
| `RAISE_FRACTIONS_8` | `{**RAISE_FRACTIONS, 6: 1 / 3}` | 42 |
| `MIN_RAISE` | `7` | 43 |
| `N_ACTIONS` | `len(ACTIONS)` | 44 |
| `EQUITY_ITERATIONS` | `100` | 49 |
| `_STREET` | `{'preflop': 0, 'flop': 1, 'turn': 2, 'river': 3}` | 51 |
| `N_FEATURES` | `FEATURE_SIZES[FEATURES_VERSION]` | 162 |
| `EFF_STACK_INDEX` | `24` | 163 |
| `PLAYERS_INDEX` | `29` | 164 |

**Funktionen**

- `action_names(n: int=N_ACTIONS) -> tuple[str, ...]` · Z. 47
- `equity_of(obs: Observation, rng: random.Random | None=None) -> float` · Z. 58
- `features(obs: Observation, equity: float | None=None, version: str=FEATURES_VERSION, opp: np.ndarray | None=None) -> np.ndarray` · Z. 66: opp: Gegnermerkmale aus OpponentTracker.features(obs) (nur feat-3; None = keine Beobachtungen).
- `version_for_width(n: int) -> str` · Z. 167
- `eff_stack_bb(x: np.ndarray) -> np.ndarray` · Z. 174
- `action_mask(obs: Observation, n: int=N_ACTIONS) -> np.ndarray` · Z. 178
- `to_action(obs: Observation, idx: int) -> Action` · Z. 199
- `from_action(obs: Observation, action: Action, n: int=N_ACTIONS) -> int` · Z. 211: Ordnet eine (regelkonforme) Aktion eines anderen Bots der naechsten diskreten Aktion zu

Interne Helfer: `_log_scaled`, `_range_features`, `_features_v1`, `_raise_amount`

### `pokercollector.ai.gtow`

Datei `collector/src/pokercollector/ai/gtow.py` · 281 Zeilen

Messung gegen GTO Wizard AI (benchmark.gtowizard.com) - zweites externes Massband neben Slumbot.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `API` | `'https://researcher.gtowizard.com'` | 38 |
| `GAME` | `'HUNL 200BB'` | 39 |
| `GTOW_VERSION` | `'gtow-1'` | 40 |
| `KEY_FILE` | `'api_key.txt'` | 41 |

**Klasse `GtowError`** (RuntimeError) · Zeile 44


**Funktionen**

- `results_dir() -> Path` · Z. 48
- `api_key(explicit: str | None=None) -> str` · Z. 53
- `history_to_text(history: list[str]) -> str` · Z. 92: ['b300', 'c', '_', 'k', 'b500'] -> 'b300c/kb500' (Slumbot-Schreibweise fuer slumbot.replay).
- `parse_cards(s: str | None) -> list[str]` · Z. 107: 'AhKd', 'Ah Kd', 'Ah,Kd' -> ['Ah', 'Kd']; None/'' -> []. Zehner als 'T' (auch '10' wird verstanden).
- `split_players(players: list[dict]) -> tuple[dict, dict]` · Z. 117: (wir, GTO Wizard). Erkennung ueber den Namen, sonst ueber die sichtbaren Hole Cards.
- `client_pos(position: str) -> int` · Z. 130: 1 = Small Blind/Button (handelt preflop zuerst), 0 = Big Blind - wie slumbot.replay.
- `rebuild(resp: dict, seed: int=0) -> tuple[Hand, dict, dict]` · Z. 140: Spielstand der API in der Engine nachbauen. Liefert (Hand, wir, Bot).
- `to_act_request(obs, action: Action, gs: dict) -> dict` · Z. 149: Engine-Aktion -> ActRequest. Einsatzhoehe ist die Strassensumme (wie raise_to), in raise_range gekappt.
- `play_hand(agent, key: str, seed: int) -> dict` · Z. 170
- `load_hands(name: str) -> list[dict]` · Z. 209
- `summarize(hands: list[dict]) -> dict` · Z. 216
- `server_results(key: str) -> dict` · Z. 226: Statistik des Servers (AIVAT ueber alle unsere Haende, massgeblich fuer die Rangliste).
- `request_access(email: str, organization: str, bot_name: str, key: str, reason: str) -> dict` · Z. 232: Zugang beantragen. Den Schluessel (>= 32 Zeichen) waehlt man selbst; er gilt nach Freigabe per E-Mail.
- `run(spec: str, name: str, hands: int, workers: int=2, key: str | None=None, progress=None) -> dict` · Z. 241: Spielt bis zu `hands` weitere Haende mit `workers` parallelen Haenden (der Anbieter-Client nutzt 5).

Interne Helfer: `_request`

### `pokercollector.ai.human`

Datei `collector/src/pokercollector/ai/human.py` · 194 Zeilen

Du als Spieler: Terminal-Oberflaeche ueber dieselbe Observation/Action-Schnittstelle.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `SUIT_SYM` | `{'s': '♠', 'h': '♥', 'd': '♦', 'c': '♣'}` | 12 |
| `SUIT_ASCII` | `{'s': 's', 'h': 'h', 'd': 'd', 'c': 'c'}` | 13 |
| `KIND_DE` | `{'post_sb': 'setzt Small Blind', 'post_bb': 'setzt Big Blind', 'fold'…` | 14 |

**Klasse `QuitGame`** (Exception) · Zeile 18


**Klasse `HumanAgent`** · Zeile 22

- `__init__(self, name: str='du', input_fn=input, output_fn=print, ascii_only: bool=False, coach: bool=False)` · Z. 23
- `card(self, c: str | None) -> str` · Z. 35
- `cards(self, cs) -> str` · Z. 42
- `render(self, obs: Observation)` · Z. 65
- `act(self, obs: Observation) -> Action` · Z. 111
- `parse(self, raw: str, obs: Observation) -> Action | None` · Z. 127
- `hand_over(self, rec, seat: int)` · Z. 182
- interne Methoden: `_seat_name`, `_show_new_actions`, `_prompt`, `_coach`

### `pokercollector.ai.humanbots`

Datei `collector/src/pokercollector/ai/humanbots.py` · 188 Zeilen

Mensch-Bots: Stilbots, deren Haeufigkeiten zu echten Spielertypen (humans.py, HandHQ) passen.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `FIT_SPACE` | `{**RANDOM_SPACE, 'bet_size': (0.3, 1.1), 'respect': (0.0, 1.0), 'stic…` | 24 |
| `HUMANBOTS_VERSION` | `'humanbots-1'` | 26 |
| `FIT_KEYS` | `{'vpip': 3.0, 'pfr': 3.0, 'threebet': 2.0, 'agg': 1.0, 'ftb': 1.5, 'c…` | 27 |
| `MEASURE_TABLE` | `['tag', 'rock', 'lag', 'station', 'tag']` | 28 |
| `STACK_BB` | `100` | 29 |

**Funktionen**

- `record_to_phh(rec) -> dict` · Z. 32: HandRecord der Engine -> PHH-artiges dict (p1 = Small Blind, wie in HandHQ).
- `measure(spec: str, hands: int=600, seed: int=0, table: list[str] | None=None) -> dict` · Z. 78: Haeufigkeiten des Bots `spec` ueber `hands` 6er-Cash-Haende (100 BB, Stacks jede Hand neu).
- `distance(st: dict, target: dict) -> float` · Z. 94
- `spec_from(x: dict) -> str` · Z. 103
- `fit_type(target: dict, generations: int=10, population: int=16, hands: int=600, seed: int=0, ex=None, progress=None, table: list[str] | None=None, start: dict …` · Z. 115: CEM ueber die Stilparameter (Grenzen FIT_SPACE), Start nahe der Zielwerte fuer vpip/pfr.
- `fit_all(humans_file: Path, out_name: str, generations: int=10, population: int=16, hands: int=600, workers: int | None=None, progress=None, rounds: int=2) -> P…` · Z. 156: Runde 1 misst gegen die alten Stilbots; ab Runde 2 sitzen die Mensch-Bots der Vorrunde am Tisch
- `load_bots(name: str='mensch-25nl') -> list[dict]` · Z. 184

Interne Helfer: `_eval`, `_params`

### `pokercollector.ai.humandata`

Datei `collector/src/pokercollector/ai/humandata.py` · 383 Zeilen

HandHQ-Showdown-Entscheidungen mit bekannten Karten -> Trainingsdaten fuer ein Menschen-Politiknetz (Hebel H11).

**Konstanten**

| Name | Wert | Zeile |
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

- `replay_handhq(hand: dict, hand_no: int=0, version: str=FEATURES, n_actions: int=N_ACTIONS)` · Z. 66: Eine HandHQ-Hand nachspielen. Rueckgabe (ok, problem, samples); samples = Liste
- `iter_file(path: Path)` · Z. 141
- `extract(files: list[Path], out_dir: Path | str, workers: int=2, files_per_shard: int=50, version: str=FEATURES, n_actions: int=N_ACTIONS, progress=None) -> dict` · Z. 189: Alle Dateien nachspielen, je files_per_shard Dateien eine Scherbe human-<nr>.npz (schon vorhandene Scherben
- `load(out_dir: Path | str, max_shards: int | None=None) -> dict` · Z. 225: Scherben zusammenfuegen (x float16, mask, a, Metadaten; player wird je Scherbe neu nummeriert ->
- `public_rows(hand: dict, hand_no: int=0)` · Z. 248: Alle Entscheidungen einer HandHQ-Hand als kartenfreie Zustandszeilen (hole_class -1 = unbekannt).
- `extract_public(files: list[Path], out_dir: Path | str, workers: int=2, files_per_shard: int=50, progress=None) -> dict` · Z. 348: Alle Entscheidungen (mit und ohne Karten) als kartenfreie Zeilen, Scherben public-<nr>.npz.
- `load_public(out_dir: Path | str, max_shards: int | None=None) -> dict` · Z. 379

Interne Helfer: `_split`, `_deck`, `_process_files`, `_process_public`

### `pokercollector.ai.humanfold`

Datei `collector/src/pokercollector/ai/humanfold.py` · 207 Zeilen

Fold-Modell fuer das Menschenmodell (H11 Schritt 2b): was Normalspieler weglegen, und mit welchen Karten sie bleiben.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `HUMANFOLD_VERSION` | `'humanfold-1'` | 29 |
| `N_CLASSES` | `169` | 30 |
| `PUBLIC_DIM` | `20` | 31 |
| `_CLASSES` | `all_classes()` | 32 |

**Klasse `HumanFold`** · Zeile 96
: Geladenes Fold-Modell: p_fold(x), p_class(x) und der Weiterspiel-Faktor je Kombination.

- `__init__(self, w: dict)` · Z. 99
- `load(cls, path: Path | str) -> 'HumanFold'` · Z. 106
- `p_fold(self, x: np.ndarray) -> np.ndarray` · Z. 110
- `p_class(self, x: np.ndarray) -> np.ndarray` · Z. 114
- `continue_factor(self, obs: Observation, range_weights: np.ndarray) -> np.ndarray` · Z. 121: P(weiter | Kombination, Zustand) in [0, 1] je der 1326 Kombinationen: Bayes-Rest aus g, f und der

**Funktionen**

- `public_vector_arrays(street, position, n_players, n_live, pot_bb, to_call_bb, stack_bb, raises_street, raises_pre, facing, aggressor, board_paired, board_suite…` · Z. 39: Kartenfreier Zustand als float32[n, PUBLIC_DIM]; identisch fuer Training (Spalten der public-Scherben)
- `public_vector(obs: Observation) -> np.ndarray` · Z. 70: Kartenfreier Zustand des handelnden Spielers aus einer Observation (float32[PUBLIC_DIM]).
- `train(rows_dir: Path | str, out: Path | str, max_rows: int=4000000, epochs: int=3, hidden_f: int=64, hidden_g: int=256, batch: int=8192, lr: float=0.002, seed:…` · Z. 138: Beide Teilmodelle aus den public-Scherben trainieren (torch, CPU reicht), als .npz speichern.

Interne Helfer: `_log1p`, `_forward`

### `pokercollector.ai.humans`

Datei `collector/src/pokercollector/ai/humans.py` · 337 Zeilen

Echte Menschen als Massstab: Spielertypen aus HandHQ (PHH-Datensatz, 21,6 Mio. Online-Haende 2009).

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `HUMANS_VERSION` | `'humans-1'` | 28 |
| `STAT_KEYS` | `('vpip', 'pfr', 'threebet', 'f3b', 'agg', 'ftb', 'cbet', 'wtsd', 'wsd…` | 29 |
| `TYPE_FEATURES` | `('vpip', 'pfr', 'agg', 'ftb', 'threebet', 'cbet', 'wtsd')` | 269 |

**Klasse `HumanStats`** · Zeile 52

- `__init__(self)` · Z. 53
- `add_hand(self, h: dict)` · Z. 86
- `stats(self, min_hands: int=0) -> dict[str, dict]` · Z. 216
- interne Methoden: `_winnings`

**Funktionen**

- `handhq_dir() -> Path` · Z. 32
- `iter_hands(path: Path)` · Z. 37: Alle Haende einer .phhs-Datei (TOML, Abschnitte [1], [2], ...).
- `collect(dirs: list[Path], max_files: int | None=None, progress=None, workers: int | None=None) -> HumanStats` · Z. 243: Alle .phhs-Dateien auswerten, verteilt auf mehrere Prozesse (Zaehler werden danach addiert).
- `player_types(stats: dict[str, dict], k: int=6, min_hands: int=300, seed: int=0) -> list[dict]` · Z. 272: k-Means auf den Haeufigkeiten der Spieler mit genug Haenden -> Typen mit Anteil und Mittelwerten.
- `type_name(m: dict) -> str` · Z. 310
- `save(name: str, hs: HumanStats, types: list[dict]) -> Path` · Z. 328

Interne Helfer: `_counter`, `_collect_chunk`

### `pokercollector.ai.hupreflop`

Datei `collector/src/pokercollector/ai/hupreflop.py` · 298 Zeilen

Heads-up Preflop: Gleichgewicht per CFR+ ueber die 169 Starthand-Klassen, in jeder Entscheidung neu.

**Konstanten**

| Name | Wert | Zeile |
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

**Klasse `Node`** · Zeile 40


**Funktionen**

- `build(S: float, path: list[tuple[str, float]]=()) -> tuple[Node, list[Node]]` · Z. 63: Baum fuer effektiven Stack S (BB). path: tatsaechliche Aktionen bisher (Art, auf BB).
- `solve(S: float, path=(), iterations: int=ITERATIONS)` · Z. 185
- `exploitability(root: Node) -> float` · Z. 194: (BR_SB + BR_BB) / 2 in BB je Hand (0 = Gleichgewicht).
- `strategy(S2: int, path: tuple) -> tuple[list, np.ndarray]` · Z. 203: Strategie (Aktionen, Wahrscheinlichkeiten je Klasse) am aktuellen Knoten. S2 = Stack in halben BB.
- `path_ranges(S2: int, path: tuple) -> tuple[np.ndarray, np.ndarray] | None` · Z. 213: Gleichgewichts-Ranges (169 Klassen, unnormiert, Prior 1 je Klasse) von SB und BB NACH dem Preflop-Verlauf
- `stack_key(S: float) -> int` · Z. 232: Stack-Rasterung wie in decide(): halbe BB, ab 30 BB ganze, ab 60 BB Zweierschritte (Cache-Treffer).
- `equilibrium_ranges(obs) -> tuple[np.ndarray, np.ndarray] | None` · Z. 241: Gleichgewichts-Ranges (169 Klassen) von (SB, BB) zu Beginn der aktuellen Postflop-Strasse bzw. am
- `history_path(obs) -> list[tuple[str, float]] | None` · Z. 257: Preflop-Verlauf als (Art, auf BB); None, wenn es kein normales Heads-up-Preflop ist.
- `effective_stack_bb(obs) -> float` · Z. 273
- `decide(obs, rng) -> tuple[tuple[str, float], list, np.ndarray] | None` · Z. 278: Aktion (Art, auf BB) fuer die eigene Hand plus alle Aktionen/Wahrscheinlichkeiten, oder None.

Interne Helfer: `_realized_share`, `_same`, `_sigma`, `_walk`, `_avg`, `_br`

### `pokercollector.ai.husearch`

Datei `collector/src/pokercollector/ai/husearch.py` · 1069 Zeilen

Heads-up-Suche zur Laufzeit: Turn und River werden in jeder Entscheidung neu geloest (CFR ueber Ranges), preflop am Heads-up-Tisch spielt der Preflop-Loeser (hupreflop.py).

**Konstanten**

| Name | Wert | Zeile |
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

**Klasse `State`** · Zeile 88


**Klasse `Tree`** · Zeile 102


**Klasse `HUSearchAgent`** (BaseAgent) · Zeile 859
: Blueprint-Netz, wo nicht gesucht wird; heads-up Neuloesen per CFR auf den gewaehlten Strassen (Flop mit gezogenen Turn-/Rivercards, Turn mit allen Rivercards, River exakt).

- `__init__(self, blueprint: BaseAgent, iters_turn: int=120, iters_river: int=300, streets: tuple[str, ...]=('turn', 'river'), seed: int=0, iters_flop: int=40, k_…` · Z. 864
- `hand_over(self, rec, seat)` · Z. 887
- `applies(self, obs: Observation) -> bool` · Z. 891
- `preflop(self, obs: Observation) -> Action | None` · Z. 896: Heads-up-Tisch preflop: Gleichgewicht aus hupreflop (None = nicht anwendbar).
- `choose_format(self, obs: Observation) -> None` · Z. 917: auto: tiefes Cash (kein Turnier, effektiver Stack >= 80 BB) -> Preflop-Loeser + Gleichgewichts-Ranges
- `act(self, obs: Observation) -> Action` · Z. 929

**Funktionen**

- `chance_cards(board: tuple[int, ...], k: int | None, rng) -> list[int]` · Z. 211: Karten fuer einen Zufallsknoten: alle nicht auf dem Board (k None) oder k davon gezogen.
- `build_tree(root: State, path: tuple=(), k_turn: int | None=None, k_river: int | None=None, preset: str='narrow', seed: int=0, leaf_street: int | None=None) -> …` · Z. 220: Baum breitenweise aufbauen: Kinder eines Knotens liegen zusammenhaengend, Eltern vor Kindern.
- `average_reaches(tree: Tree, avg: np.ndarray, r0: np.ndarray, r1: np.ndarray) -> tuple[np.ndarray, np.ndarray]` · Z. 330: Reach (= unnormierte Range) beider Spieler an JEDEM Knoten unter der Durchschnittsstrategie avg
- `tree_levels(first: np.ndarray, nch: np.ndarray) -> np.ndarray` · Z. 355: Ebenengrenzen: der Baum ist breitenweise gebaut, Kinder liegen hinter allen Knoten ihrer Elternebene.
- `board_tables(boards: list[tuple[int, ...]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]` · Z. 368: Je Board: Handwerte aller Kombinationen (-1 = blockiert) und aufsteigende Reihenfolge der gueltigen.
- `leaf_values(tree: Tree, valuenet, reach: np.ndarray, own: np.ndarray, bb: int) -> np.ndarray` · Z. 730: Blattwerte aus dem Wertnetz: je Blatt die (normierten) Ranges beider Spieler aus den aktuellen Reaches,
- `solve(root: State, r0: np.ndarray, r1: np.ndarray, iters: int=200, exploit: bool=False, gamma: float=GAMMA, path: tuple=(), k_turn: int | None=None, k_river: i…` · Z. 755: Loest das Teilspiel ab root. Rueckgabe: Baum, Durchschnittsstrategie am aktuellen Knoten (Ende von
- `public_ranges(obs: Observation, hero: int, opp: int) -> tuple[np.ndarray, np.ndarray]` · Z. 812: Ranges beider Spieler zu BEGINN der aktuellen Strasse, nur aus oeffentlicher Information - die
- `root_state(obs: Observation) -> tuple[State, int, tuple]` · Z. 824: Zustand zu Beginn der aktuellen Strasse (0 = wir, 1 = Gegner) und die Aktionen seitdem.
- `hand_index(cards: list[str]) -> int` · Z. 854
- `warmup(streets: tuple[str, ...]=('flop', 'turn', 'river')) -> None` · Z. 987: Kernel fuer die gesuchten Strassen einmal uebersetzen bzw. aus dem Cache laden (sonst wartet die erste
- `load_valuenet(name: str)` · Z. 999: Wertnetz laden: Pfad oder Name unter data/valuenet/<name>.pt.
- `set_threads(n: int) -> None` · Z. 1010: Numba-Faeden je Prozess begrenzen (wirkt prozessweit; ohne numba wirkungslos).
- `make_husearch_agent(params: str, seed: int=0) -> HUSearchAgent` · Z. 1019
- `load_opp_fold(name: str)` · Z. 1056: Fold-Modell (humanfold.HumanFold) aus data/humans/<name>.npz oder Pfad.
- `load_opp_weights(spec: str) -> dict` · Z. 1064: Gegnermodell '<Lauf>@<Checkpoint>' (z. B. human-1@1, Menschen-Netz aus HandHQ) als numpy-Gewichte.

Interne Helfer: `_sizes`, `_children`, `_after_check`, `_after_call`, `_after_raise`, `_put`, `_street_end`, `_matches`, `_fold_sums`, `_showdown`, `_solve`, `_solve_small`, `_solve_any`, `_best_response`

### `pokercollector.ai.icm`

Datei `collector/src/pokercollector/ai/icm.py` · 50 Zeilen

ICM (Independent Chip Model, Malmuth-Harville): Turnier-Eigenkapital aus den Stacks.

**Funktionen**

- `icm_equity(stacks: list[int] | list[float], prizes: list[float], seat: int) -> float` · Z. 12: Erwartete Auszahlung (in Buy-ins) fuer `seat` bei diesen Stacks. Ausgeschiedene (0) haben 0.
- `icm_equities(stacks: list[int] | list[float], prizes: list[float]) -> list[float]` · Z. 43
- `prizes_from(payouts, players: int) -> list[float]` · Z. 47: Auszahlungsanteile (0.5, 0.3, 0.2) -> Preise in Buy-ins bei `players` Buy-ins Preisgeld.

### `pokercollector.ai.league`

Datei `collector/src/pokercollector/ai/league.py` · 298 Zeilen

Liga mit Rating, Benchmark gegen feste Gegner und Entwicklungsverlauf.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `LEAGUE_VERSION` | `'league-1'` | 29 |
| `BETA` | `SIGMA0 / 2` | 31 |
| `KAPPA` | `0.0001` | 32 |
| `GAUNTLET` | `['rock', 'tag', 'station', 'maniac', 'lag']` | 33 |

**Klasse `Player`** · Zeile 41

- `rating(self) -> float` · Z. 53
- `rating_sd(self) -> float` · Z. 57
- `conservative(self) -> float` · Z. 61

**Klasse `League`** · Zeile 89

- `__init__(self, root: Path)` · Z. 90
- `save(self)` · Z. 99
- `add(self, name: str, spec: str | None, kind: str='bot', note: str='') -> Player` · Z. 105
- `ensure_defaults(self)` · Z. 115
- `agent(self, name: str, seed: int)` · Z. 120
- `record_game(self, participants: list[str], ranks: list[float], payouts: list[float], kind: str, extra: dict | None=None)` · Z. 126
- `play_round(self, names: list[str], config: TournamentConfig, seed: int) -> dict` · Z. 142: Ein Duplicate-Sit&Go-Schema: alle Rotationen, Rang nach Summe der Auszahlungen.
- `run(self, rounds: int, table: int=6, config: TournamentConfig | None=None, seed: int | None=None, progress=None) -> list[dict]` · Z. 162: Bots (keine Menschen) in zufaelligen Tischbesetzungen; wer wenig gespielt hat, wird bevorzugt.
- `benchmark(self, name: str, hands: int=300, tournaments: int=10, seed: int=4242, config: TournamentConfig | None=None) -> dict` · Z. 183: Feste Gegnergruppe, fester Seed: ueber Versionen vergleichbar.
- `games(self) -> list[dict]` · Z. 210
- `benchmarks(self) -> list[dict]` · Z. 214
- `history(self) -> dict[str, list[tuple[int, float, float]]]` · Z. 218: Rating-Verlauf je Spieler: (Ligaspiel-Nr., Rating, Sigma in Anzeigepunkten).
- `pushfold_quality(self) -> dict[str, dict]` · Z. 226
- `leaderboard_markdown(self) -> str` · Z. 237
- `report_html(self) -> str` · Z. 262

**Funktionen**

- `display(mu: float) -> float` · Z. 36
- `rate_plackett_luce(ratings: list[tuple[float, float]], ranks: list[float]) -> list[tuple[float, float]]` · Z. 65: Weng-Lin Plackett-Luce-Update. ratings: (mu, sigma) je Spieler; ranks: kleiner = besser,

### `pokercollector.ai.live`

Datei `collector/src/pokercollector/ai/live.py` · 525 Zeilen

Live-Anbindung Collector -> Bot: Vorschlaege mit Handverlauf und Gegnermodell.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `HISTORY_KINDS` | `('post_sb', 'post_bb', 'fold', 'check', 'call', 'bet', 'raise')` | 23 |
| `SETTLE_S` | `0.7` | 24 |
| `BUST_S` | `20.0` | 25 |
| `SAME_AMOUNT` | `0.25` | 26 |

**Klasse `TournamentWatch`** · Zeile 144
: Erkennt das Turnierende aus den fertig rekonstruierten Haenden (nur Bildinhalt): - eigener Stack nach der Hand 0 -> ausgeschieden; Platz = 1 + Gegner, die danach noch Chips haben. Bestaetigt, sobald die naechste Hand ohne eigene Chips startet oder die Sitzung endet (ein einzelner OCR-Aussetzer '0' …

- `__init__(self, hero_seat: int=0)` · Z. 159
- `on_hand(self, h: dict) -> dict | None` · Z. 187: Eine fertige Hand (Reconstructor-Dict). Liefert ein Ergebnis, sobald es feststeht.
- `on_state(self, state: dict, now: float | None=None) -> dict | None` · Z. 243: Tischzustand nach jedem Ereignis: zeigt ein Stack alle Chips des Turniers, ist es vorbei; bleibt
- `activity(self, field: str, value) -> None` · Z. 307: Spielaktivitaet eines Gegners (Einsatz, Hervorhebung, Aktionslabel) oder eigene Buttons: die Hand
- `flush(self) -> dict | None` · Z. 317: Sitzungsende: ein noch unbestaetigtes Ausscheiden zaehlt.
- interne Methoden: `_reset`, `_result`

**Klasse `LiveBot`** · Zeile 324

- `__init__(self, agent, hero_seat: int=0, num_seats: int=10, on_result=None)` · Z. 325
- `on_event(self, ev: dict, state: dict, now: float)` · Z. 349: Ein Ereignis verarbeiten (now = Zeit in Sekunden, gleiche Uhr wie bei poll()).
- `poll(self, now: float)` · Z. 369: Liefert (Vorschlag, Observation, Gegner), sobald eine neue Entscheidungslage ruhig ist, sonst None.
- `playable(self, state: dict) -> bool` · Z. 398: Nur echte Entscheidungen: Tisch erkannt und eigener Stack lesbar > 0. Nach dem eigenen All-in, nach
- `same_as_shown(self, sug, obs) -> bool` · Z. 406: Gleiche Strasse, gleiche Art, Betrag kaum anders: die Leiste nicht neu anstossen (kein Flackern
- `feed(self, ev: dict)` · Z. 420: Jedes Collector-Ereignis (wie in observations.jsonl) in Eingangsreihenfolge.
- `close(self)` · Z. 439: Sitzungsende: offene Hand abschliessen und ein unbestaetigtes Ergebnis melden.
- `session_ended(self)` · Z. 449: Aufnahme beendet (Tisch laenger weg): offenes Ergebnis melden, Rekonstruktion fuer die naechste
- `observation(self, state: dict) -> Observation` · Z. 464
- `opponents(self, obs: Observation) -> list[tuple[str, dict]]` · Z. 490: Gegner in der Hand mit ihren Statistiken (Name, Werte) fuer die Anzeige.
- `suggest(self, state: dict)` · Z. 499
- interne Methoden: `_relevant`, `_drain`

**Funktionen**

- `fix_dollar_misreads(state: dict, chips: int | None) -> dict` · Z. 29: Unplausible Zahlen im Bild gegen die Chips des Turniers pruefen.
- `drop_stale_bets(obs: Observation, hand: dict) -> Observation` · Z. 56: Einsaetze im Bild, zu denen die laufende Hand keine Aktion des Platzes kennt, sind Reste einer frueheren
- `sane(sug, obs)` · Z. 82: Vorschlag an die gelesene Lage anpassen: Raise nie ueber den eigenen Stack (dann All-in), Raise nicht
- `decision_buttons(buttons) -> bool` · Z. 100: Die Aktionsbuttons bieten Call oder Check an (nur 'Fold' = Vorauswahl).
- `is_decision(state: dict, hero_seat: int=0) -> bool` · Z. 105: Du bist dran: eigener Platz hervorgehoben UND Call/Check-Buttons sichtbar. Die Buttons allein
- `public_history(hand: dict, num_seats: int=10) -> list[PublicAction]` · Z. 111: Oeffentlicher Verlauf einer (laufenden) rekonstruierten Hand im Format der Engine.
- `replay_session(events: list[dict], agent, hero_seat: int=0)` · Z. 506: Spielt eine aufgezeichnete Sitzung wie live ab: liefert jeden Vorschlag, den man live gesehen

Interne Helfer: `_alive`

### `pokercollector.ai.nn_agent`

Datei `collector/src/pokercollector/ai/nn_agent.py` · 245 Zeilen

Der lernende Bot: kleines neuronales Netz (Merkmale -> Aktionswahrscheinlichkeiten + Wert).

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `NN_VERSION` | `'nn-mlp-1'` | 24 |
| `_CACHE` | `{}` | 25 |
| `NEW_ACTION_TEMPLATE` | `{6: 2, 7: 2}` | 88 |
| `NEW_ACTION_OFFSET` | `-2.0` | 89 |

**Klasse `NNAgent`** (BaseAgent) · Zeile 164

- `__init__(self, weights: dict, seed: int=0, greedy: bool=False, name: str | None=None, fold_model=None, temp: float=1.0)` · Z. 167
- `p_fold_hand(self, obs: Observation) -> float` · Z. 181: P(Fold | Zustand, eigene Hand) aus dem Fold-Modell: 1 minus Weiterspiel-Faktor der eigenen
- `hand_over(self, rec, seat)` · Z. 193
- `inputs(self, obs: Observation) -> tuple[np.ndarray, np.ndarray]` · Z. 197: Merkmale und Aktionsmaske genau so, wie act() sie benutzt (fuer Lehrer-Daten, teacher.py).
- `act(self, obs: Observation) -> Action` · Z. 203

**Funktionen**

- `rl_root() -> Path` · Z. 28
- `build_net(hidden: int=128, version: str=FEATURES_VERSION, n_actions: int=N_ACTIONS)` · Z. 34: Netz fuer eine Merkmalsversion (Eingangsgroesse aus FEATURE_SIZES) und Aktionszahl (6 oder 8).
- `numpy_weights(net) -> dict` · Z. 56
- `forward_np(w: dict, x: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, float]` · Z. 63: Wahrscheinlichkeiten (maskiert) und Wert fuer EINE Situation.
- `sharpen(p: np.ndarray, temp: float) -> np.ndarray` · Z. 75: Wahrscheinlichkeiten mit Temperatur temp schaerfen: p^(1/temp), neu normiert (temp 1 = unveraendert,
- `widen_net(net, version: str, n_actions: int | None=None)` · Z. 92: Gleiches Netz fuer eine groessere Merkmalsversion und/oder mehr Aktionen. Neue Eingaenge
- `save_checkpoint(path: Path, net, meta: dict, extra: dict | None=None)` · Z. 120
- `load_checkpoint(path: Path) -> dict` · Z. 131
- `net_from_checkpoint(ck: dict)` · Z. 140
- `checkpoint_path(run: str, ckpt: str | int='latest') -> Path` · Z. 146
- `load_weights(run: str, ckpt: str | int='latest') -> dict` · Z. 156
- `make_nn_agent(params: str, seed: int=0) -> NNAgent` · Z. 231

### `pokercollector.ai.observation`

Datei `collector/src/pokercollector/ai/observation.py` · 161 Zeilen

Die gemeinsame Schnittstelle: was ein Spieler sieht (Observation) und was er tut (Action).

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `STREETS` | `('preflop', 'flop', 'turn', 'river')` | 14 |

**Klasse `Action`** · Zeile 18

- `fold() -> 'Action'` · Z. 26
- `check() -> 'Action'` · Z. 30
- `call() -> 'Action'` · Z. 34
- `raise_to(amount: int) -> 'Action'` · Z. 38
- interne Methoden: `__str__`

**Klasse `PublicAction`** · Zeile 43


**Klasse `Observation`** · Zeile 53

- `stack_bb(self) -> float` · Z. 86: Effektiver eigener Stack (inkl. gesetzter Chips) in Big Blinds.
- `pot(self) -> int` · Z. 91: Gesamter Pot inkl. aller Einsaetze auf dem Tisch.
- `my_stack(self) -> int` · Z. 96
- `my_bet(self) -> int` · Z. 100
- `current_bet(self) -> int` · Z. 104
- `opponents_in_hand(self) -> int` · Z. 108
- `active_opponents(self) -> int` · Z. 113: Gegner, die noch handeln koennen (nicht gefoldet, nicht all-in).
- `position(self) -> int` · Z. 118: 0 = Button, 1 = Cutoff, ... (Abstand gegen den Uhrzeigersinn vom Button
- `street_actions(self, street: str | None=None) -> list[PublicAction]` · Z. 125
- `raises_this_street(self) -> int` · Z. 129
- `legal(self) -> list[str]` · Z. 132

**Klasse `Agent`** (Protocol) · Zeile 140

- `act(self, obs: Observation) -> Action` · Z. 143

**Funktionen**

- `clamp_action(obs: Observation, action: Action) -> Action` · Z. 147: Macht eine Agentenaktion regelkonform (z. B. Raise ueber Stack -> All-in).

### `pokercollector.ai.opponents`

Datei `collector/src/pokercollector/ai/opponents.py` · 149 Zeilen

Gegnermodell: Statistiken je Gegner ueber die bisherigen Haende (wie ein HUD).

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `PRIOR` | `{'vpip': (0.28, 8.0), 'pfr': (0.16, 8.0), 'agg': (0.45, 6.0), 'ftb': …` | 23 |
| `CONF_HANDS` | `20.0` | 24 |
| `OPP_FEATURES` | `8` | 25 |
| `_KEYS` | `('vpip', 'pfr', 'agg', 'ftb')` | 26 |
| `DEFAULT_FEATURES` | `np.array([PRIOR['vpip'][0], PRIOR['pfr'][0], PRIOR['agg'][0], PRIOR['…` | 33 |

**Klasse `OpponentTracker`** · Zeile 37

- `__init__(self, fuzzy: bool=False)` · Z. 38
- `update(self, rec, me: int)` · Z. 69: Nach jeder Hand (Simulator, HandRecord): Verlauf auswerten (me = eigener Platz, zaehlt nicht).
- `update_collector(self, hand: dict, me: int)` · Z. 74: Nach jeder Hand (Collector, rekonstruierte Hand als dict wie in hands.json).
- `stats(self, key: str) -> dict` · Z. 119
- `features(self, obs: Observation) -> np.ndarray` · Z. 132
- interne Methoden: `_key`, `_cnt`, `_count`

**Funktionen**

- `describe(st: dict) -> str` · Z. 145: Kurzanzeige wie ein HUD: 'H 23 VPIP 35 % PFR 12 % Agg 40 % FvB 55 %'.

Interne Helfer: `_prior_stats`

### `pokercollector.ai.optimize`

Datei `collector/src/pokercollector/ai/optimize.py` · 285 Zeilen

Selbstverbesserung, Schritt 1: Optimierung der Stil-Parameter eines Bots.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `OPT_VERSION` | `'cem-1'` | 36 |
| `SPACE` | `{'vpip': (0.08, 0.6, False), 'pfr': (0.03, 0.45, False), 'value_margi…` | 39 |
| `DEFAULT_POOL` | `['rock', 'tag', 'lag', 'station', 'maniac']` | 51 |
| `DEFAULT_CONFIG` | `TournamentConfig(start_stack=3000, blinds=BlindSchedule(10, 20, 10))` | 52 |
| `RANDOM_SPACE` | `{'vpip': (0.05, 0.9), 'pfr': (0.0, 0.6), 'value_margin': (-0.05, 0.4)…` | 81 |

**Klasse `LeaguePool`** · Zeile 96
: Gegnerauswahl aus der Liga. players: [(name, spec, mu)], nur Bots. Gewicht exp((mu - mu_max) / temperature), mindestens `floor`: starke Gegner kommen oefter dran, schwache verschwinden aber nie ganz (sonst verlernt der Bot, sie auszunehmen). random_share: Anteil der Plaetze, die mit einem Zufalls-S…

- `__init__(self, players: list[tuple[str, str, float]], table: int=5, temperature: float=15.0, floor: float=0.1, self_play: float=0.2, random_share: float=0.0)` · Z. 103
- `add(self, name: str, spec: str, weight: float=1.0)` · Z. 116
- `shares(self) -> dict[str, float]` · Z. 120
- `sample(self, rng: random.Random, self_spec: str | None=None, size: int | None=None) -> list[str]` · Z. 124: Ein Tisch aus `size` (Standard: table) Gegnern, gewichtet und ohne Zuruecklegen, solange genug

**Funktionen**

- `params_from_style(name: str) -> dict` · Z. 55
- `spec_from_params(params: dict, base: str='tag') -> str` · Z. 60
- `random_style_spec(rng: random.Random) -> str` · Z. 88: Ein Stil-Bot mit gewuerfelten Werten. Gleicher rng-Zustand -> gleicher Bot (Duplicate-fair).
- `matchup_payouts(spec: str, matchups: list[tuple[int, list[str]]], config: TournamentConfig) -> list[float]` · Z. 145: Netto-Auszahlung (Buy-ins, Mittel ueber alle Sitzrotationen) des Kandidaten je (Schema, Gegnertisch).
- `scheme_payouts(spec: str, pool: list[str], schemes: list[int], config: TournamentConfig) -> list[float]` · Z. 161: Wie matchup_payouts, alle Schemata gegen denselben festen Pool.
- `pool_desc(pool)` · Z. 178
- `run_cem(generations: int=8, population: int=12, schemes_per_gen: int=12, start: str='tag', pool: list[str] | LeaguePool | None=None, config: TournamentConfig=D…` · Z. 185
- `gate(candidate_spec: str, champion_spec: str, schemes: int=40, seed: int=777, pool: list[str] | LeaguePool | None=None, config: TournamentConfig=DEFAULT_CONFIG…` · Z. 263: Gepaarter Vergleich auf frischen Kartenschemata (bei LeaguePool auch frisch gezogenen Tischen,

Interne Helfer: `_norm`, `_denorm`, `_eval_job`, `_matchups`

### `pokercollector.ai.phh`

Datei `collector/src/pokercollector/ai/phh.py` · 221 Zeilen

Fremde Handhistorien im PHH-Format (Poker Hand History, Univ. Toronto) einlesen.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `PHH_VERSION` | `'phh-1'` | 30 |
| `BB_TO_REWARD` | `1 / 15` | 159 |

**Klasse `ReplayResult`** · Zeile 34


**Funktionen**

- `load_phh(path: Path) -> dict` · Z. 40
- `replay(hand: dict, hand_no: int=0) -> ReplayResult` · Z. 63: Spielt eine PHH-Hand in unserer Engine nach und sammelt jede Entscheidung.
- `build_dataset(files: list[Path], progress=None) -> tuple[dict, dict]` · Z. 125: Alle Dateien nachspielen. Ergebnis: Arrays wie bei der Nachahmung + Pruefbericht.
- `datasets_dir() -> Path` · Z. 162
- `dataset_file(name: str, version: str=FEATURES_VERSION) -> Path` · Z. 167: feat-1 heisst wie bisher '<name>.npz', neuere Versionen '<name>-<version>.npz'.
- `save_dataset(name: str, data: dict, report: dict, version: str=FEATURES_VERSION) -> Path` · Z. 172
- `load_dataset(name: str, players: list[str] | None=None, version: str=FEATURES_VERSION) -> dict` · Z. 182
- `forward_batch(w: dict, X: np.ndarray, M: np.ndarray) -> np.ndarray` · Z. 198
- `agreement(w: dict, data: dict) -> dict` · Z. 210: Wie gut trifft ein Netz die Entscheidungen im Datensatz?

Interne Helfer: `_split`, `_build_deck`

### `pokercollector.ai.play`

Datei `collector/src/pokercollector/ai/play.py` · 210 Zeilen

Spielsitzungen Mensch gegen Bots und deren Auswertung.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `PLAY_VERSION` | `'play-1'` | 24 |

**Klasse `SessionWriter`** · Zeile 40

- `__init__(self, path: Path, meta: dict)` · Z. 41
- `write(self, obj: dict)` · Z. 47
- `close(self, end: dict)` · Z. 51

**Funktionen**

- `rec_from_dict(d: dict) -> HandRecord` · Z. 31
- `play_cash(human: HumanAgent, bots: list, out_dir: Path, hands: int=1000, stack_bb: int=100, blinds: tuple[int, int]=(10, 20), seed: int | None=None) -> Path` · Z. 56: Cash-Game: Stacks bleiben bestehen; wer unter 1 BB faellt, kauft automatisch nach (rebuy).
- `play_tournament_session(human: HumanAgent, bots: list, out_dir: Path, config: TournamentConfig, seed: int | None=None) -> tuple[Path, object]` · Z. 93
- `load_sessions(play_dir: Path) -> list[dict]` · Z. 134
- `player_stats(sessions: list[dict]) -> dict` · Z. 153: Kennzahlen je Spielername ueber alle Sitzungen (Mensch und Bots).
- `stats_markdown(sessions: list[dict], human: str='du') -> str` · Z. 180

Interne Helfer: `_rec_to_dict`

### `pokercollector.ai.pushfold`

Datei `collector/src/pokercollector/ai/pushfold.py` · 338 Zeilen

Push/Fold-Gleichgewicht (Nash) fuer kurze Stacks.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `PUSHFOLD_VERSION` | `'pushfold-1'` | 32 |
| `MATRIX_FILE` | `'hand_vs_hand.json'` | 33 |
| `TABLE_FILE` | `'pushfold_nash.json'` | 34 |
| `CLASSES` | `all_classes()` | 35 |
| `IDX` | `{c: i for i, c in enumerate(CLASSES)}` | 36 |
| `STACKS` | `[1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 1…` | 37 |
| `MAX_BEHIND` | `8` | 38 |
| `_ENC` | `'0123456789X'` | 193 |

**Klasse `PushFoldGame`** · Zeile 129
: Pusher + k Caller, alle mit effektivem Stack S (in BB).

- `__init__(self, S: float, k: int, E: np.ndarray, W: np.ndarray)` · Z. 132
- `pusher_ev(self, calls: list[np.ndarray]) -> np.ndarray` · Z. 139: EV (netto, BB) des Pushens je Pusher-Hand gegen Call-Wahrscheinlichkeiten je Caller.
- `caller_ev(self, push: np.ndarray, i: int) -> np.ndarray` · Z. 154: EV (netto) des Callens je Caller-Hand gegen die Push-Range (frueherer Caller hat gefoldet).
- `solve(self, iterations: int=600) -> dict` · Z. 161
- `exploitability(self, push: np.ndarray, calls: list[np.ndarray]) -> dict` · Z. 173: Gewinn (BB je Hand des jeweiligen Spielers) einer perfekten Gegenstrategie je Rolle.
- `range_pct(self, strat: np.ndarray) -> float` · Z. 189

**Funktionen**

- `class_combos_concrete(cls: str) -> tuple[tuple[str, str], ...]` · Z. 44
- `combo_weights() -> np.ndarray` · Z. 57: W[a, b] = Anzahl kompatibler (kartenfremder) Kombinationspaare von Klasse a und b.
- `build_matrix(samples: int=3000, seed: int=11, processes: int | None=None, progress=None) -> dict` · Z. 93
- `matrix() -> tuple[np.ndarray, np.ndarray]` · Z. 114
- `build_table(iterations: int=600, progress=None) -> dict` · Z. 204
- `nash_table() -> dict` · Z. 233
- `push_probability(hole: list[str], stack_bb: float, behind: int) -> float | None` · Z. 247: Gleichgewichts-Wahrscheinlichkeit fuer Push als erster Spieler mit `behind` Spielern dahinter.
- `call_probability(hole: list[str], stack_bb: float, behind_at_push: int, my_index: int) -> float | None` · Z. 256: Gleichgewichts-Call gegen einen Push. behind_at_push = Spieler hinter dem Pusher,
- `range_classes(stack_bb: float, behind: int, role: str='push', caller: int=0) -> list[str]` · Z. 266
- `grid_text(stack_bb: float, behind: int, role: str='push', caller: int=0) -> str` · Z. 273: 13x13-Raster: oben rechts suited, unten links offsuit, Diagonale Paare.
- `decision_ev(hole: list[str], spot: dict, chose: str) -> dict | None` · Z. 310: Bewertet eine Push/Fold-Entscheidung gegen Gegner, die Nash spielen.

Interne Helfer: `_equity_row`, `_blinds`, `_encode`, `_decode`, `_entry`, `_game_and_nash`

### `pokercollector.ai.ranges`

Datei `collector/src/pokercollector/ai/ranges.py` · 257 Zeilen

Ranges: welche Haende hat ein Gegner nach seinen bisherigen Aktionen wahrscheinlich?

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `RANGES_VERSION` | `'ranges-1'` | 31 |
| `COMBOS` | `np.array([(i, j) for i in range(52) for j in range(i + 1, 52)], np.in…` | 32 |
| `COMBO_PCT` | `np.array([preflop_percentile([FULL_DECK[i], FULL_DECK[j]]) for i, j i…` | 33 |
| `OPEN_Q` | `(0.3, 0.1, 0.045, 0.03)` | 34 |
| `CALL_Q` | `(0.6, 0.35, 0.14, 0.06)` | 35 |
| `COMBO_HAS` | `np.zeros((52, len(COMBOS)), bool)` | 43 |
| `PRE_RAISE` | `[_sig((q - COMBO_PCT) / 0.03) for q in OPEN_Q]` | 46 |
| `PRE_CALL` | `[_sig((q - COMBO_PCT) / 0.05) for q in CALL_Q]` | 47 |
| `OPEN_Q_HU` | `(0.85, 0.15, 0.06, 0.035)` | 49 |
| `CALL_Q_HU` | `(0.9, 0.7, 0.45, 0.12)` | 50 |
| `PRE_RAISE_HU` | `[_sig((q - COMBO_PCT) / 0.05) for q in OPEN_Q_HU]` | 51 |
| `PRE_CALL_HU` | `[_sig((q - COMBO_PCT) / 0.06) for q in CALL_Q_HU]` | 52 |

**Funktionen**

- `dead_mask(cards: list[str]) -> np.ndarray` · Z. 55
- `board_strength(board: tuple[str, ...]) -> np.ndarray` · Z. 82: Staerke jeder Kombination auf diesem Board als Perzentil (0 schwaechste .. 1 staerkste).
- `board_factors(board: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray, np.ndarray]` · Z. 96: Faktoren fuer Bet/Raise, Call, Check auf diesem Board (vorberechnet, gecacht).
- `opponent_ranges(obs: Observation, heads_up: bool=False) -> dict[int, np.ndarray]` · Z. 102: Gewichte (Summe 1) ueber die 1326 Kombinationen fuer jeden Gegner, der noch in der Hand ist.
- `equity_vs_ranges(obs: Observation, iterations: int=200, seed: int=0, ranges: dict[int, np.ndarray] | None=None) -> float` · Z. 222
- `sample_hands(ranges: dict[int, np.ndarray], dead: list[str], rng: np.random.Generator, tries: int=50) -> dict[int, list[str]] | None` · Z. 234: Zieht konsistente Gegnerhaende aus den Ranges (fuer die Suche: moegliche 'Welten').
- `range_summary(r: np.ndarray) -> dict` · Z. 253: Fuer Anzeige/Tests: wie eng ist die Range (Anteil Gewicht in den oberen 10 % / 30 %)?

Interne Helfer: `_sig`, `_strengths`, `_mc_vs_ranges`

### `pokercollector.ai.recording`

Datei `collector/src/pokercollector/ai/recording.py` · 81 Zeilen

Protokolliert Entscheidungen eines beliebigen Agenten (Bot oder Mensch) und bewertet Push/Fold-Situationen gegen das Nash-Gleichgewicht.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `PF_MAX_BB` | `15` | 12 |

**Klasse `DecisionLog`** · Zeile 31

- `summary(self) -> dict` · Z. 36

**Klasse `RecordingAgent`** · Zeile 46
: Huelle um einen Agenten; leitet alles weiter und protokolliert.

- `__init__(self, agent, log: DecisionLog | None=None)` · Z. 49
- `name(self)` · Z. 54
- `name(self, v)` · Z. 58
- `act(self, obs: Observation) -> Action` · Z. 61
- `hand_over(self, rec, seat)` · Z. 77

**Funktionen**

- `classify_pf_choice(obs: Observation, action: Action, spot: dict) -> str | None` · Z. 15

### `pokercollector.ai.replay`

Datei `collector/src/pokercollector/ai/replay.py` · 199 Zeilen

Bruecke Collector -> Observation.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `BOARD_COUNT` | `{'preflop': 0, 'flop': 3, 'turn': 4, 'river': 5}` | 15 |
| `DECISION_TYPES` | `('fold', 'check', 'call', 'bet', 'raise')` | 16 |

**Funktionen**

- `decision_points(hand: dict, hero_seat: int=0, num_seats: int=10) -> list[tuple[Observation, dict]]` · Z. 19
- `live_pot(st: dict, bets: list[int], bb: int, unc: list[str]) -> int | None` · Z. 97: Pot inkl. laufender Einsaetze. Zwei Quellen im Bild: die Pot-Anzeige in der Tischmitte (pot.total,
- `observation_from_table_state(st: dict, hero_seat: int=0, num_seats: int=10) -> Observation` · Z. 115: Live: Spielerblick aus dem stabilisierten Feldzustand des Collectors.
- `review_hands(hands: list[dict], agent, hero_seat: int=0) -> list[dict]` · Z. 181: Fragt den Agenten an jeder eigenen Entscheidung und stellt Vorschlag und echte Aktion gegenueber.

### `pokercollector.ai.rl`

Datei `collector/src/pokercollector/ai/rl.py` · 638 Zeilen

Wie der Bot lernt: erst Nachahmung (Behavior Cloning), dann Selbstspiel mit PPO.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `RL_VERSION` | `'ppo-1'` | 44 |

**Klasse `RLConfig`** · Zeile 48


**Klasse `_Collector`** · Zeile 87
: Gemeinsame Buchfuehrung: Entscheidungen je Hand, Belohnung bei Handende.

- `__init__(self, scale: float, start_stack: int, icm: float=0.0)` · Z. 90
- `hand_over(self, rec, seat)` · Z. 130
- interne Methoden: `_begin`, `_reward`

**Klasse `_Learner`** (_Collector) · Zeile 141

- `__init__(self, w: dict, rng: random.Random, scale: float, start_stack: int, name: str='learner', icm: float=0.0)` · Z. 142
- `hand_over(self, rec, seat)` · Z. 151
- `act(self, obs)` · Z. 156

**Klasse `_Teacher`** (_Collector) · Zeile 168

- `__init__(self, agent, scale: float, start_stack: int)` · Z. 169
- `act(self, obs)` · Z. 174
- `hand_over(self, rec, seat)` · Z. 180

**Funktionen**

- `behavior_clone(run_dir: Path, teacher: str='rock', tournaments: int=600, epochs: int=10, hidden: int=128, config: TournamentConfig=DEFAULT_CONFIG, seed: int=1,…` · Z. 240
- `fit_bc(run_dir: Path, data: dict, source: dict, epochs: int=10, hidden: int=128, seed: int=1, progress=None, label_smoothing: float=0.05, t0: float | None=None…` · Z. 257: Netz auf gesammelte Entscheidungen trainieren (x, mask, a, r) -> ckpt_000000.pt.
- `gae(r: np.ndarray, v: np.ndarray, done: np.ndarray, lam: float) -> tuple[np.ndarray, np.ndarray]` · Z. 319: Vorteile und Zielwerte, gamma = 1 innerhalb einer Hand, Episodenende bei done.
- `snapshot_spec(run: str, it: int) -> str` · Z. 341
- `eval_fixed(spec: str, cfg: RLConfig, config: TournamentConfig, ex) -> float` · Z. 345: ROI gegen den festen Pool auf immer denselben Kartenschemata (Lernkurve, kein Gate).
- `train_ppo(run_dir: Path, iterations: int, pool: LeaguePool | list[str], cfg: RLConfig | None=None, config: TournamentConfig=DEFAULT_CONFIG, workers: int | None…` · Z. 367: ex: vorhandener Prozess-Pool (z. B. fuer Ausbeuter innerhalb eines Laufs) - spart RAM.
- `exploit_test(target: str, init_ckpt: Path, iterations: int=40, schemes: int=48, seed: int=9, config: TournamentConfig=DEFAULT_CONFIG, workers: int | None=None,…` · Z. 600: Ausnutzbarkeit: ein Ausbeuter lernt nur gegen 5 Kopien des Pruflings (PPO, ohne Leine).
- `new_run_dir(prefix: str='nn') -> Path` · Z. 636

Interne Helfer: `_pack`, `_concat`, `_rollout_job`, `_bc_job`, `_accuracy`, `_write_jsonl`, `_eval_chunk`, `_run_name`, `_ppo_update`

### `pokercollector.ai.search`

Datei `collector/src/pokercollector/ai/search.py` · 166 Zeilen

Suche waehrend des Spiels - Grundlage fuer Pluribus-artiges Vorausrechnen.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `SEARCH_VERSION` | `'search-1'` | 36 |

**Klasse `SearchAgent`** (BaseAgent) · Zeile 91
: Rollout-Suche ueber eine Blueprint-Strategie. last_q: geschaetzter Wert je Aktion (BB) - auch fuer Live-Empfehlungen nutzbar. min_gain: Mindestvorteil (BB) gegenueber der Blueprint-Wahl.

- `__init__(self, blueprint: str, worlds: int=24, min_gain: float=0.25, seed: int=0, name: str | None=None)` · Z. 96
- `act(self, obs: Observation) -> Action` · Z. 107

**Funktionen**

- `world_from_obs(obs: Observation, opp_hands: dict[int, list[str]], rng: random.Random, hand_id: str='world') -> Hand` · Z. 39: Vollstaendiger Spielstand, der fuer den Spieler obs.seat genauso aussieht wie obs.
- `play_out(h: Hand, agents, seat: int) -> float` · Z. 80: Spielt die Hand mit den gegebenen Agenten (Liste je Platz oder ein Agent fuer alle) zu Ende.
- `make_search_agent(params: str, seed: int=0) -> SearchAgent` · Z. 160: 'search?bp=pros-2@300,worlds=24' (bp = Netz-Lauf@Checkpoint; ',' oder '&' trennen - ',' ist cmd-sicher).

### `pokercollector.ai.slumbot`

Datei `collector/src/pokercollector/ai/slumbot.py` · 272 Zeilen

Messung gegen Slumbot (slumbot.com) - ein starker, oeffentlicher Heads-up-Bot als absoluter Massstab.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `API` | `'https://slumbot.com/api'` | 36 |
| `SLUMBOT_VERSION` | `'slumbot-1'` | 38 |

**Klasse `SlumbotError`** (RuntimeError) · Zeile 42


**Funktionen**

- `parse_action(action: str) -> list[list[tuple[str, int | None]]]` · Z. 63: 'b200c/kb300' -> [[('b',200),('c',None)], [('k',None),('b',300)]]
- `replay(action: str, client_pos: int, hole: list[str], board: list[str], bot_hole: list[str] | None=None, seed: int=0) -> Hand` · Z. 85: Baut den Spielstand in der Engine nach. Unbekannte Karten (Gegner, kommende Boardkarten) zufaellig.
- `to_incr(obs, action: Action) -> str` · Z. 114
- `allin_ev(h: Hand, hole: list[str], bot_hole: list[str]) -> float | None` · Z. 144: Netto (Chips) fuer uns nach All-in-EV, wenn vor dem River all-in gegangen und aufgedeckt wurde.
- `play_hand(agent, token: str | None, seed: int) -> dict` · Z. 159
- `results_dir() -> Path` · Z. 186
- `load_hands(name: str) -> list[dict]` · Z. 191
- `summarize(hands: list[dict]) -> dict` · Z. 209
- `adjusted(hands: list[dict]) -> dict` · Z. 218: All-in-EV mit dem Kartenglueck (baseline, Erwartung 0) als Kontrollvariable bereinigt.
- `run(spec: str, name: str, hands: int, workers: int=4, progress=None) -> dict` · Z. 235: Spielt bis zu `hands` weitere Haende mit `workers` parallelen Slumbot-Sitzungen.

Interne Helfer: `_post`, `_equity`, `_stat`

### `pokercollector.ai.tables`

Datei `collector/src/pokercollector/ai/tables.py` · 118 Zeilen

Preflop-Equity-Tabelle: 169 Starthand-Klassen gegen 1-9 zufaellige Gegner.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `TABLE_FILE` | `'preflop_equity.json'` | 17 |

**Funktionen**

- `hand_class(cards: list[str]) -> str` · Z. 20: ['As','Kd'] -> 'AKo', ['Th','Ts'] -> 'TT', ['9c','8c'] -> '98s'.
- `all_classes() -> list[str]` · Z. 30
- `class_combos(cls: str) -> int` · Z. 42
- `example_cards(cls: str) -> list[str]` · Z. 46
- `build_preflop_table(iterations: int=1500, heads_up_iterations: int=8000, seed: int=7, max_opponents: int=9, progress=None) -> dict` · Z. 72: Spalte '1 Gegner' genauer, weil sie die Rangfolge der Starthaende bestimmt.
- `save_table(table: dict, path: Path)` · Z. 88
- `preflop_table() -> dict` · Z. 93
- `preflop_equity(cards: list[str], opponents: int) -> float` · Z. 98
- `preflop_percentile(cards: list[str]) -> float` · Z. 116

Interne Helfer: `_equity`, `_percentiles`

### `pokercollector.ai.teacher`

Datei `collector/src/pokercollector/ai/teacher.py` · 204 Zeilen

Suche als Lehrer (Expert Iteration, Hebel H5): die Heads-up-Suche spielt, das Netz lernt ihre Entscheidungen.

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `TEACHER_VERSION` | `'teacher-1'` | 29 |

**Klasse `TeacherRecorder`** · Zeile 32
: Huelle um einen HUSearchAgent: spielt wie er, merkt sich jede gesuchte Entscheidung als Lehrerbeispiel.

- `__init__(self, search_agent, student, name: str='lehrer')` · Z. 35
- `hand_over(self, rec, seat)` · Z. 42
- `act(self, obs: Observation) -> Action` · Z. 48

**Funktionen**

- `resolve_opponent(name: str) -> str` · Z. 75: 'mensch-N' -> Stil-Spezifikation aus data/humans/mensch-25nl.json (wie bench 'mensch'); sonst unveraendert.
- `collect(search_spec: str, student_spec: str, opponents: list[str], hands: int, stacks_bb: list[int], out: Path | str, seed: int=1, progress=None) -> dict` · Z. 86: Je Gegner und Stacktiefe ein Match (duplicate) Suche gegen Gegner; Lehrerbeispiele in eine .npz.
- `load(paths: list[Path | str]) -> dict` · Z. 122
- `fit(student_run: str, student_ckpt: int | str, paths: list[Path | str], out_run: str, epochs: int=10, batch: int=512, lr: float=0.0003, kl_coef: float=0.5, hol…` · Z. 129: Schueler auf die weichen Lehrerziele nachtrainieren: Verlust = Kreuzentropie(Ziel, Schueler)

### `pokercollector.ai.tournament`

Datei `collector/src/pokercollector/ai/tournament.py` · 305 Zeilen

Turniermodus (Sit & Go wie bei PokerTH).

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `TOURNAMENT_VERSION` | `'tournament-1'` | 26 |
| `POKERTH_DEFAULT` | `TournamentConfig(start_stack=1000, blinds=BlindSchedule(10, 20, 9))` | 68 |
| `PLAYER_WEIGHTS` | `{2: 1.5, 3: 1.0, 4: 1.0, 5: 1.0, 6: 2.0, 7: 1.0, 8: 1.0, 9: 1.5, 10: …` | 71 |
| `HANDS_PER_LEVEL` | `(5, 6, 8, 9, 10, 12, 15, 20)` | 72 |

**Klasse `BlindSchedule`** · Zeile 30

- `at(self, hand_no: int) -> dict` · Z. 37: Blinds fuer Hand Nummer hand_no (0-basiert).

**Klasse `TournamentConfig`** · Zeile 54

- `payout_for_place(self, place: int, players: int) -> float` · Z. 60: Auszahlung in Buy-ins: Preisgeld = players Buy-ins.

**Klasse `TournamentResult`** · Zeile 96


**Klasse `TournamentStats`** · Zeile 187

- `result(self, per_unit_tournaments: int) -> dict` · Z. 196

**Funktionen**

- `random_players(rng, weights: dict[int, float] | None=None) -> int` · Z. 75
- `random_config(rng, players: int) -> TournamentConfig` · Z. 80: Startstack 20-200 BB (log-gleichverteilt, oft 50 BB wie bei PokerTH), Blind-Tempo 5-20 Haende,
- `play_tournament(agents: list, config: TournamentConfig=TournamentConfig(), seed: int=0, keep_records: bool=False, on_hand=None, stop=None) -> TournamentResult` · Z. 129: stop(stacks) -> True bricht nach der Hand ab (z. B. Training: lernender Bot ist raus).
- `run_tournaments(agents: list, count: int, config: TournamentConfig=TournamentConfig(), seed: int=1, duplicate: bool=True, progress=None, keep_example: bool=Fal…` · Z. 211: count Turniere; mit duplicate=True wird jedes Turnier-Kartenschema mit allen
- `tournaments_markdown(res: dict) -> str` · Z. 276
- `tournament_text(res: TournamentResult) -> str` · Z. 297

Interne Helfer: `_assign_places`

### `pokercollector.ai.valuedata`

Datei `collector/src/pokercollector/ai/valuedata.py` · 264 Zeilen

Trainingsdaten fuer das Wertnetz der Suche (Meilenstein 3, Stufe 1b).

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `VALUEDATA_VERSION` | `'vdata-1'` | 32 |
| `BB` | `100` | 33 |
| `STREET_CARDS` | `{'flop': 3, 'turn': 4, 'river': 5}` | 34 |
| `ITERS_DEFAULT` | `{'flop': 60, 'turn': 150, 'river': 300, 'river-leaf': 300, 'turn-leaf…` | 35 |
| `LEAF_TURN_ITERS` | `60` | 40 |
| `LEAF_PER_TURN` | `24` | 41 |
| `LEAF_MIN_MASS` | `1e-06` | 42 |
| `TL_FLOP_ITERS` | `40` | 47 |
| `TL_K_TURN` | `8` | 48 |
| `TL_K_RIVER` | `4` | 49 |
| `TL_PER_FLOP` | `12` | 50 |
| `_VNET` | `{}` | 51 |

**Funktionen**

- `sample_ranges(rng: np.random.Generator, board: list[str]) -> tuple[np.ndarray, np.ndarray]` · Z. 54: Zwei boardbezogene Ranges (Summe 1). Mischung aus gleichverteilt, dicht/locker (weiche Staerkeschwelle),
- `sample_state(rng: np.random.Generator, street: str) -> tuple[State, list[str], float, float]` · Z. 80: Zustand zu Strassenbeginn: Pot 2..80 BB, Stack/Pot 0.25..8 (logarithmisch gleichverteilt), beide Stacks
- `get_vnet(name: str | None)` · Z. 96: River-Wertnetz je Prozess einmal laden (None = ohne Netz, exakt).
- `solve_sample(seed: int, street: str, iters: int, vnet: str | None=None) -> dict` · Z. 106
- `solve_leaf_samples(seed: int, iters: int=300, iters_turn: int=LEAF_TURN_ITERS, max_per_turn: int=LEAF_PER_TURN) -> list[dict]` · Z. 137: River-Situationen aus einer echten Turn-Suche: Turn-Zustand + synthetische Start-Ranges, voller Turn-Baum
- `solve_turn_leaf_samples(seed: int, iters: int=150, vnet: str | None='vnet-river-1', iters_flop: int=TL_FLOP_ITERS, max_per_flop: int=TL_PER_FLOP) -> list[dict]` · Z. 175: Turn-Situationen aus einer echten Flop-Suche: Flop-Zustand + synthetische Start-Ranges, Flop-Baum mit
- `data_dir() -> Path` · Z. 206
- `generate(street: str, n: int, out: Path | str, seed: int=0, iters: int | None=None, workers: int=1, threads: int | None=None, progress=None, vnet: str | None=N…` · Z. 211: n Situationen loesen und als eine .npz-Scherbe schreiben. Seeds seed..seed+n-1 (reproduzierbar).
- `load(path: Path | str) -> dict` · Z. 259

Interne Helfer: `_river_row`, `_roots_rows`, `_worker`

### `pokercollector.ai.valuenet`

Datei `collector/src/pokercollector/ai/valuenet.py` · 241 Zeilen

Wertnetz fuer die Suche (Meilenstein 3): oeffentlicher Zustand + beide Ranges -> kontrafaktische Werte je Kombination fuer beide Spieler (in Pot-Einheiten), wie sie die exakte CFR+-Loesung liefert (valuedata.py).

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `VALUENET_VERSION` | `'vnet-1'` | 33 |
| `N_COMBOS` | `1326` | 34 |
| `N_IN` | `52 + 3 + 4 + 2 * N_COMBOS` | 35 |
| `N_OUT` | `2 * N_COMBOS` | 36 |
| `_COMBOS` | `np.array([(a, b) for a in range(52) for b in range(a + 1, 52)], np.in…` | 39 |

**Klasse `ValueMLP`** (nn.Module if nn else object) · Zeile 75

- `__init__(self, width: int=1024, depth: int=3)` · Z. 76
- `forward(self, x)` · Z. 86

**Klasse `ValueNet`** · Zeile 103
: Geladenes Netz fuer die Suche: predict(...) liefert v0, v1 in Pot-Einheiten (Nullsumme exakt).

- `__init__(self, model, device: str='cpu', threads: int | None=2)` · Z. 106
- `load(cls, path: Path | str, device: str='cpu', threads: int | None=2) -> 'ValueNet'` · Z. 114
- `predict(self, board, pot_bb, stack_bb, oop, r0, r1) -> tuple[np.ndarray, np.ndarray]` · Z. 121

**Funktionen**

- `combo_mask(board: np.ndarray) -> np.ndarray` · Z. 42: [n, 1326] True fuer Kombinationen ohne Boardkarte. board: int8[n, 5], -1 = leer.
- `features(board: np.ndarray, pot_bb: np.ndarray, stack_bb: np.ndarray, oop: np.ndarray, r0: np.ndarray, r1: np.ndarray) -> np.ndarray` · Z. 53: float32[n, N_IN].
- `zero_sum_fix(v0: np.ndarray, v1: np.ndarray, r0: np.ndarray, r1: np.ndarray, mask: np.ndarray | None=None) -> tuple[np.ndarray, np.ndarray]` · Z. 90: Nullsumme exakt herstellen: Fehler e = r0.v0 + r1.v1 haelftig auf beide Seiten verteilen (ReBeL), nur auf
- `load_shards(paths: list[str]) -> dict` · Z. 131
- `train(paths: list[str], out: Path | str, epochs: int=10, batch: int=512, lr: float=0.001, width: int=1024, depth: int=3, holdout: float=0.02, device: str | Non…` · Z. 139
- `main(argv=None)` · Z. 219

### `pokercollector.ai.ziele`

Datei `collector/src/pokercollector/ai/ziele.py` · 166 Zeilen

Unsere Ziele (ZIELE.md im Projektordner) und die Anzeigetafel: wo steht ein Bot je Benchmark?

**Konstanten**

| Name | Wert | Zeile |
| --- | --- | --- |
| `ZIELE_VERSION` | `'ziele-1'` | 22 |
| `MEASURE_SETS` | `('mensch480', 'nash240', 'kurz240')` | 23 |
| `PAYOUTS` | `TournamentConfig().payouts` | 24 |
| `GOALS` | `{1: ('Echte PokerTH-Partien', ['50 Turniere, ROI > 0', '200 Turniere,…` | 27 |

**Funktionen**

- `pokerth_log() -> Path` · Z. 36
- `add_tournament(place: int, players: int, bot: str, note: str='', **extra) -> dict` · Z. 40: extra: weitere Angaben (z. B. Haende, Sitzung, Quelle 'auto'), werden mitgeschrieben.
- `remove_last_tournament(bot: str) -> dict | None` · Z. 53: Letzten Eintrag dieses Bots entfernen (Korrektur einer falschen automatischen Erkennung).
- `pokerth_summary(bot: str | None=None) -> dict | None` · Z. 67
- `latest(name: str) -> dict` · Z. 89: Neueste Werte je Testset fuer diesen Namen (spaetere Eintraege ueberschreiben fruehere).
- `scoreboard(name: str, slumbot_name: str | None=None, pokerth_bot: str | None=None) -> list[dict]` · Z. 143
- `scoreboard_text(name: str, rows: list[dict]) -> str` · Z. 157

Interne Helfer: `_stage`

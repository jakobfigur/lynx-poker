"""Kommandozeile. Aufruf: pokercollector <befehl> ... (oder start.cmd auf dem Stick)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import cv2

from .profile import Profile


def data_dir() -> Path:
    env = os.environ.get("POKERCOLLECTOR_DATA")
    if env:
        return Path(env)
    # src/pokercollector/cli.py -> collector/ -> Projektordner auf dem Stick
    return Path(__file__).resolve().parents[3] / "data"


def sessions_dir() -> Path:
    p = data_dir() / "sessions"
    p.mkdir(parents=True, exist_ok=True)
    return p


def templates_dir() -> Path:
    return data_dir() / "templates"


def _session_path(arg: str) -> Path:
    p = Path(arg)
    if p.exists():
        return p
    if arg == "last":
        cands = sorted(d for d in sessions_dir().iterdir() if d.is_dir())
    else:
        cands = sorted(sessions_dir().glob(f"*{arg}*"))
    if not cands:
        sys.exit(f"Sitzung nicht gefunden: {arg}")
    return cands[-1]


def _analyzer(profile: Profile):
    from .pipeline import make_analyzer
    return make_analyzer(profile, templates_dir())


def cmd_calibrate(a):
    profile = Profile.load(a.profile)
    img = cv2.imread(a.image)
    if img is None:
        sys.exit(f"Bild nicht lesbar: {a.image}")
    an = _analyzer(profile)
    t = time.perf_counter()
    snap = an.analyze(img)
    ms = (time.perf_counter() - t) * 1000
    from .report import overlay
    out = Path(a.out or Path(a.image).with_suffix(".overlay.png"))
    cv2.imwrite(str(out), overlay(img, snap))
    for k, f in sorted(snap.fields.items()):
        flag = "" if f.confidence >= 0.6 else "  <-- unsicher"
        print(f"{k:24s} {json.dumps(f.value, ensure_ascii=False):42s} {f.confidence:.2f} {f.note}{flag}")
    for w in snap.warnings:
        print("WARNUNG:", w)
    print(f"\nAnalyse {ms:.0f} ms, Massstab {snap.get('table.scale')}, Overlay: {out}")


def cmd_analyze(a):
    from .capture import ImageDirSource, SessionVideoSource, VideoFileSource
    from .pipeline import run_offline
    from .report import hands_markdown

    profile = Profile.load(a.profile)
    p = Path(a.input)
    if not p.exists() and (sessions_dir() / a.input).exists():
        p = sessions_dir() / a.input
    if p.is_dir() and (p / "session.json").exists():
        src = SessionVideoSource(p)            # Live-Sitzung neu auswerten (alle Video-Abschnitte)
    elif p.is_dir() or p.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp"):
        src = ImageDirSource(p, a.interval)
    else:
        src = VideoFileSource(p, step_s=a.step)
    an = _analyzer(profile)
    last = [0.0]

    def progress(fr, snap, stats):
        if time.time() - last[0] > 2:
            last[0] = time.time()
            gh = snap.get("info.game_hand")
            print(f"  t={fr.t_mono:7.1f}s  Frames {stats.frames_analyzed}  Ereignisse {stats.events}  Hand {gh}",
                  flush=True)

    root = run_offline(src, sessions_dir(), profile, an, progress=progress)
    (root / "hands.md").write_text(hands_markdown(root), "utf-8")
    meta = json.loads((root / "session.json").read_text("utf-8"))
    print(f"\nSitzung: {root}\nStatistik: {meta['stats']}\nBericht: {root / 'hands.md'}")


def cmd_windows(a):
    from .capture import list_windows
    for w in list_windows(a.filter or ""):
        print(f"{w.hwnd:>10}  {w.rect[2]}x{w.rect[3]}  {'(minimiert) ' if w.minimized else ''}{w.title}")


def _pick_window(title: str | None, hwnd: int | None) -> int:
    from .capture import list_windows
    if hwnd:
        return hwnd
    wins = [w for w in list_windows(title or "") if not w.minimized and w.rect[2] > 200]
    if not wins:
        sys.exit(f"Kein sichtbares Fenster mit '{title}' im Titel. 'pokercollector windows' zeigt alle.")
    if len(wins) > 1:
        print("Mehrere passende Fenster - bitte mit --hwnd waehlen:")
        for w in wins:
            print(f"  --hwnd {w.hwnd}   {w.rect[2]}x{w.rect[3]}  {w.title}")
        sys.exit(2)
    return wins[0].hwnd


def cmd_live(a):
    from .capture import WindowSource
    from .pipeline import LiveRunner

    profile = Profile.load(a.profile)
    hwnd = _pick_window(a.window, a.hwnd)
    src = WindowSource(hwnd, fps=a.fps, max_seconds=a.max_seconds, require_foreground=not a.allow_background)
    print(f"Fenster {hwnd}: {src.describe()['title']}")
    print("Status: wartet auf Tisch. Beenden mit Strg+C. Es wird nichts geklickt oder getippt.\n")

    def on_status(s, d):
        print(f"\r[{time.strftime('%H:%M:%S')}] {s:20s} {d[:90]:90s}", end="", flush=True)

    from .ai.agents import make_agent
    from .ai.live import LiveBot
    agent = make_agent(_agent_spec(a.agent), 0)
    if hasattr(agent, "greedy") and not a.mischen:
        agent.greedy = True        # Berater: wahrscheinlichste Aktion statt Ziehen aus der gemischten Strategie
    leiste = None

    def on_result(res):
        # Turnierende am Bildschirm erkannt -> Zieltafel (data/ziele/pokerth.jsonl)
        note = "automatisch erkannt" + (", Turnierbeginn verpasst" if res["start_verpasst"] else "")
        msg = f"Turnier vorbei: Platz {res['platz']} von {res['spieler']} nach {res['haende']} Haenden"
        if a.kein_eintrag:
            print(f"\n{msg} (nicht eingetragen: --kein-eintrag)")
        else:
            from .ai.ziele import add_tournament, pokerth_summary
            add_tournament(res["platz"], res["spieler"], a.agent, note, quelle="auto", haende=res["haende"],
                           spiel=res["spiel"], letzte_hand=res["letzte_hand"])
            s = pokerth_summary(a.agent)
            print(f"\n{msg} - eingetragen. Bisher {s['n']} Turnier(e), ROI {s['roi']:+.1f} %, "
                  f"{s['wins']} Sieg(e). Korrektur: pc.cmd bench turnier ...")
        if leiste:
            leiste.status("ok", msg)

    bot = LiveBot(agent, on_result=on_result)
    a.advice = a.advice or a.leiste
    if a.leiste:
        from .overlay import Leiste
        leiste = Leiste(sound=not a.still, title=f"Lynx ({a.agent})").start()
        print("Leiste: normales, sichtbares Fenster. Der Collector schneidet ihre Flaeche aus seinen Bildern aus; "
              "sie gehoert neben den Tisch, nicht darauf.")

        def on_mask(rects):
            x, y, w, h = rects[0]
            print(f"\nHinweis: Leiste liegt im PokerTH-Fenster ({w}x{h} px bei {x},{y}) und wird dort ausgeschnitten. "
                  "Was darunter liegt, sieht der Collector nicht.")
        src.on_mask = on_mask
    shown = {"deciding": False}
    status_level = {"Aufnahme": "ok", "Tisch erkannt": "warn", "Analyse verzoegert": "warn",
                    "Quelle verloren": "err", "wartet": "off"}

    def show(out):
        if out and a.advice:
            sug, obs, opps = out
            print(f"\n--- Du bist dran ({obs.street}) ---")
            _print_suggestion(agent, sug, obs, opps)
            if leiste:
                from .overlay import advice_from
                leiste.show(advice_from(sug, obs, agent))
                shown["deciding"] = True
        if leiste and shown["deciding"] and not bot.deciding:
            leiste.idle()
            shown["deciding"] = False

    def on_event(rec, stab):
        # Rekonstruktion + Gegnermodell laufen immer mit, auch ohne --advice
        show(bot.on_event(rec, stab.state(), time.monotonic()))

    def on_status(s, d, _print_status=on_status):
        _print_status(s, d)
        if leiste:
            leiste.status(status_level.get(s, "warn"), s)
        if s == "wartet" and d.startswith("Sitzung beendet"):
            bot.session_ended()                   # offenes Turnierergebnis melden, Rekonstruktion frisch
            return
        show(bot.poll(time.monotonic()))          # je analysiertem Bild: ist die Lage inzwischen ruhig?

    try:
        LiveRunner(src, sessions_dir(), profile, _analyzer(profile), fps=a.fps, stop_after_s=a.stop_after,
                   segment_s=a.segment, record_video=not a.no_video, on_status=on_status,
                   on_event=on_event).run()
    finally:
        bot.close()
        if leiste:
            leiste.close()
    print()


def _agent_spec(spec: str) -> str:
    """Liga-Name (z. B. pros-r1) oder Bot-Spezifikation."""
    lg = _league()
    return lg.players[spec].spec if spec in lg.players and lg.players[spec].spec else spec


def _print_suggestion(agent, sug, obs, opps):
    if sug is None:
        print("Keine Empfehlung: eigene Karten nicht sicher erkannt")
        return
    from .ai.opponents import describe
    print(f"Vorschlag ({agent.name}): {sug}   [{' '.join(obs.hole_cards)} | {' '.join(obs.board) or '-'}"
          f" | Pot {obs.pot}, zu zahlen {obs.to_call}]")
    probs = getattr(agent, "last_probs", None)
    if probs is not None:
        from .ai.features import action_names
        print("  Wahrscheinlichkeiten: " + ", ".join(f"{n} {p:.0%}" for n, p in zip(action_names(len(probs)), probs)
                                                    if p >= 0.01))
    adv = getattr(agent, "last_advice", None)
    for r in (adv.reasoning if adv else []):
        print("  -", r)
    for name, st in opps:
        print(f"  {name:16s} {describe(st)}")
    for u in obs.uncertain:
        print("  ! unsicher:", u)


def cmd_humans_fit(a):
    from .ai.humanbots import fit_all
    from .ai.nn_agent import rl_root
    src = rl_root().parent / "humans" / f"{a.source}.json"
    if not src.exists():
        sys.exit(f"{src} fehlt - erst 'pc.cmd data humans'")
    p = fit_all(src, a.name, a.generations, a.population, a.hands, progress=lambda m: print(m, flush=True))
    import json as _json
    for b in _json.loads(p.read_text("utf-8"))["bots"]:
        t, s = b["target"], b["stats_check"]
        print(f"{b['name']} {b['type']} ({b['share']:.0%}): Abstand {b['distance_check']:.4f}")
        print("   Mensch: " + "  ".join(f"{k} {t[k]:.0%}" for k in t))
        print("   Bot:    " + "  ".join(f"{k} {s.get(k, float('nan')):.0%}" for k in t))
        print(f"   {b['spec']}")
    print(f"-> {p}")


def cmd_leiste_demo(a):
    from .overlay import Advice, Leiste
    lz = Leiste(sound=not a.still, title="Lynx (Demo)").start()
    print("Leiste unten rechts (sichtbares Fenster; live schneidet der Collector ihre Flaeche aus seinen Bildern aus). "
          "Ziehen zum Verschieben, Rechtsklick fuer Ton/Position.")
    lz.status("ok", "Aufnahme")
    demo = [("raise", "RAISE auf 360  (3,6 BB)", "Ah Kd   Pot 120, zu zahlen 40   Pot 64%  Call 30%  Fold 6%"),
            ("call", "CALL 120  (1,2 BB)", "Qs Qd | 9h 7h 2c   Pot 480, zu zahlen 120   Call 71%  Raise 22%"),
            ("check", "CHECK", "8c 7c | Kd 9s 4h 2d   Pot 600   Check 88%  ⅓ Pot 12%"),
            ("fold", "FOLD", "Td 4s   Pot 300, zu zahlen 200   Fold 93%"),
            ("allin", "ALL-IN 1840  (18,4 BB)", "As Ah   Pot 560, zu zahlen 300   All-in 80%  Call 20%")]
    try:
        for kind, text, detail in demo:
            lz.show(Advice(kind, text, detail))
            time.sleep(a.sekunden)
            lz.idle()
            time.sleep(1.0)
    finally:
        lz.close()


def cmd_live_replay(a):
    from .ai.agents import make_agent
    from .ai.live import replay_session
    from .journal import read_events
    root = _session_path(a.session)
    agent = make_agent(_agent_spec(a.agent), 0)
    n = 0
    for sug, obs, opps, ev in replay_session(read_events(root), agent):
        n += 1
        print(f"\n--- Du bist dran (Hand {obs.hand_id}, {obs.street}, Ereignis {ev['seq']}) ---")
        if obs.history:
            print("  Verlauf: " + " ".join(f"{x.seat}:{x.kind}{'' if x.amount_to is None else ' ' + str(x.amount_to)}"
                                         for x in obs.history if x.street == obs.street))
        _print_suggestion(agent, sug, obs, opps)
    print(f"\n{n} Entscheidungen in {root.name}")


def cmd_reconstruct(a):
    from .journal import build_index
    from .pipeline import write_hands
    from .report import hands_markdown

    root = _session_path(a.session)
    hands = write_hands(root)
    build_index(root)
    (root / "hands.md").write_text(hands_markdown(root), "utf-8")
    print(f"{len(hands)} Haende rekonstruiert -> {root / 'hands.md'}")


def cmd_report(a):
    from .report import hands_markdown
    print(hands_markdown(_session_path(a.session)))


def cmd_inspect_reference(a):
    from .reference import inspect
    for t, cols in inspect(Path(a.file)).items():
        print(f"{t}: {', '.join(cols)}")


def cmd_compare(a):
    from .compare import compare
    from .reference import load_reference
    from .report import compare_markdown

    root = _session_path(a.session)
    visual = json.loads((root / "hands.json").read_text("utf-8"))["hands"]
    ref = load_reference(Path(a.reference))
    res = compare(visual, ref).to_dict()
    (root / "compare.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), "utf-8")
    md = compare_markdown(res)
    (root / "compare.md").write_text(md, "utf-8")
    print(md)


def cmd_advise(a):
    from .advisor import advise, state_from_snapshot_state

    profile = Profile.load(a.profile)
    img = cv2.imread(a.image)
    snap = _analyzer(profile).analyze(img)
    st = {k: f.value for k, f in snap.fields.items()}
    gs = state_from_snapshot_state(st)
    adv = advise(gs)
    print(f"Zustand: Karten {gs.hero_cards}, Board {gs.board}, Gegner {gs.opponents}, Pot {gs.pot}, "
          f"zu callen {gs.to_call}")
    print(f"Empfehlung (Baseline): {adv.recommendation or 'keine'}  Alternativen: {adv.alternatives}")
    for r in adv.reasoning:
        print("  -", r)
    print("Annahmen:")
    for r in adv.assumptions:
        print("  -", r)


def cmd_harvest_cards(a):
    """Speichert Rang-/Farb-Glyphen erkannter offener Karten als Vorlagen."""
    from .cards import TemplateStore

    profile = Profile.load(a.profile)
    store = TemplateStore(templates_dir())
    an = _analyzer(profile)
    for path in a.images:
        img = cv2.imread(path)
        if img is None:
            print("unlesbar:", path)
            continue
        snap = an.analyze(img)
        for where, cr in snap.card_reads:
            if cr.rank_glyph is None or cr.suit_glyph is None:
                continue
            crop_path = templates_dir() / "_last_card.png"
            crop_path.parent.mkdir(parents=True, exist_ok=True)
            x, y, w, h = cr.rect.x, cr.rect.y, cr.rect.w, cr.rect.h
            cv2.imwrite(str(crop_path), cv2.resize(img[y:y + h, x:x + w], None, fx=4, fy=4,
                                                   interpolation=cv2.INTER_NEAREST))
            guess = cr.card or "??"
            ans = input(f"{Path(path).name} {where}: erkannt {guess} (Bild: {crop_path}). "
                        f"Richtig? [Enter=ja / Karte z.B. Td / s=ueberspringen] ").strip()
            if ans.lower() == "s":
                continue
            label = ans if ans else guess
            if len(label) != 2 or label == "??":
                print("  uebersprungen (kein gueltiges Label)")
                continue
            name = f"{int(time.time() * 1000)}"
            store.add("rank", label[0].upper(), cr.rank_glyph, name)
            store.add("suit", label[1].lower(), cr.suit_glyph, name)
            print(f"  gespeichert als {label[0].upper()}{label[1].lower()}")


def cmd_sim_agents(a):
    from .ai.agents import REGISTRY, STYLES
    for k in sorted(REGISTRY):
        st = STYLES.get(k)
        extra = f"  (spielt ~{st.vpip:.0%} der Starthaende, eroeffnet ~{st.pfr:.0%}, Bluff {st.bluff:.0%})" if st else ""
        print(f"{k:8s}{extra}")


def cmd_sim_match(a):
    from .ai.agents import make_agent
    from .ai.evaluate import hand_text, report_markdown, run_match, save_result

    specs = [s.strip() for s in a.agents.split(",") if s.strip()]
    agents = [make_agent(s, a.seed) for s in specs]
    last = [0.0]

    def progress(k, total, played, el):
        if time.time() - last[0] > 2 or k == total:
            last[0] = time.time()
            print(f"\r  Blatt {k}/{total}  Haende {played}  {played / el:.0f}/s", end="", flush=True)

    res = run_match(agents, a.hands, seed=a.seed, small_blind=a.sb, big_blind=a.bb, stack_bb=a.stack,
                    duplicate=not a.no_duplicate, progress=progress, keep_records=a.show)
    print("\n")
    md = report_markdown(res)
    print(md)
    for rec in res["records"]:
        print()
        print(hand_text(rec))
    out = data_dir() / "sim"
    out.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    save_result(res, out / f"match_{stamp}.json")
    (out / f"match_{stamp}.md").write_text(md, "utf-8")
    print(f"\nGespeichert: {out / f'match_{stamp}.md'}")


def cmd_sim_hand(a):
    from .ai.agents import make_agent
    from .ai.engine import play_hand
    from .ai.evaluate import hand_text

    specs = [s.strip() for s in a.agents.split(",")]
    agents = [make_agent(s, a.seed) for s in specs]
    rec = play_hand(agents, [a.stack * a.bb] * len(agents), a.button % len(agents), a.sb, a.bb,
                    seed=a.seed, hand_id=str(a.seed))
    print(hand_text(rec))


def cmd_sim_tournament(a):
    from .ai.agents import make_agent
    from .ai.tournament import (BlindSchedule, TournamentConfig, run_tournaments, tournament_text,
                                tournaments_markdown)

    specs = [s.strip() for s in a.agents.split(",") if s.strip()]
    agents = [make_agent(s, a.seed) for s in specs]
    sb, bb = (int(x) for x in a.blinds.split("/"))
    payouts = tuple(float(x) / 100 for x in a.payouts.split(",")) if a.payouts else (1.0,)
    if abs(sum(payouts) - 1.0) > 1e-6:
        sys.exit(f"Auszahlungen muessen 100 % ergeben, nicht {sum(payouts):.0%}")
    cfg = TournamentConfig(start_stack=a.stack, blinds=BlindSchedule(sb, bb, a.level_hands), payouts=payouts)
    last = [0.0]

    def progress(k, total, played, el):
        if time.time() - last[0] > 2 or k == total:
            last[0] = time.time()
            print(f"\r  Schema {k}/{total}  Turniere {played}  {el:.0f}s", end="", flush=True)

    res = run_tournaments(agents, a.tournaments, cfg, seed=a.seed, duplicate=not a.no_duplicate,
                          progress=progress, keep_example=True)
    print("\n")
    md = tournaments_markdown(res)
    print(md)
    print()
    print(tournament_text(res["example"]))
    out = data_dir() / "sim"
    out.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    data = {k: v for k, v in res.items() if k != "example"}
    (out / f"tournament_{stamp}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
    (out / f"tournament_{stamp}.md").write_text(md, "utf-8")
    print(f"\nGespeichert: {out / f'tournament_{stamp}.md'}")


def cmd_sim_pushfold(a):
    from .ai.pushfold import grid_text, nash_table
    t = nash_table()
    if a.overview:
        print("Push-Range in % (erster Spieler) je Stack und Spieler dahinter:")
        print("BB    " + " ".join(f"{k:>5d}" for k in range(1, t["max_behind"] + 1)))
        for S in t["stacks_bb"]:
            row = [t["entries"][f"{k}|{S:g}"]["push_pct"] for k in range(1, t["max_behind"] + 1)]
            print(f"{S:<5g} " + " ".join(f"{v:5.1f}" for v in row))
        return
    print(grid_text(a.stack, a.behind, "push"))
    print()
    print(grid_text(a.stack, a.behind, "call", a.caller))


def cmd_sim_review(a):
    from .ai.agents import make_agent
    from .ai.replay import review_hands

    root = _session_path(a.session)
    hands = json.loads((root / "hands.json").read_text("utf-8"))["hands"]
    rows = review_hands(hands, make_agent(a.agent, 0))
    same = sum(1 for r in rows if r.get("same"))
    for r in rows:
        mark = "=" if r.get("same") else ("?" if r["suggested"] is None else "≠")
        print(f"Hand {r['hand']:8s} {r['street']:7s} {' '.join(r.get('cards') or []):6s} "
              f"{' '.join(r.get('board') or []):15s} gespielt: {r['actual']:12s} {mark} {a.agent}: {r['suggested']}"
              + (f"   [unsicher: {'; '.join(r['uncertain'])}]" if r["uncertain"] else ""))
    print(f"\n{len(rows)} Entscheidungen, {same} gleich wie {a.agent}.")


def _league():
    from .ai.league import League
    lg = League(data_dir() / "league")
    lg.ensure_defaults()
    return lg


def cmd_play(a):
    from .ai.human import HumanAgent
    from .ai.play import play_cash, play_tournament_session
    from .ai.tournament import BlindSchedule, TournamentConfig

    names = [s.strip() for s in a.opponents.split(",") if s.strip()]
    if a.name in names:
        sys.exit(f"Dein Name '{a.name}' kollidiert mit einem Gegner")
    lg = _league()
    bots = []
    for i, nm in enumerate(names):
        if nm in lg.players and lg.players[nm].kind == "bot":
            bots.append(lg.agent(nm, i + 1))
        else:
            from .ai.agents import make_agent
            bots.append(make_agent(nm if ":" in nm else f"{nm}:{nm}", i + 1))
    if len({b.name for b in bots}) != len(bots):
        sys.exit("Gegnernamen muessen eindeutig sein, z. B. tag,tag:tag2")
    human = HumanAgent(a.name, ascii_only=a.ascii, coach=a.coach)
    out = data_dir() / "play"
    sb, bb = (int(x) for x in a.blinds.split("/"))
    if a.mode == "cash":
        path = play_cash(human, bots, out, hands=a.hands, stack_bb=a.stack_bb, blinds=(sb, bb), seed=a.seed)
        print(f"\nGespeichert: {path}\nAuswertung: pc.cmd play-stats")
        return
    payouts = tuple(float(x) / 100 for x in a.payouts.split(","))
    cfg = TournamentConfig(start_stack=a.stack, blinds=BlindSchedule(sb, bb, a.level_hands), payouts=payouts)
    path, res = play_tournament_session(human, bots, out, cfg, seed=a.seed)
    print(f"\nGespeichert: {path}")
    if res is not None and not a.unrated:
        if a.name not in lg.players:
            lg.add(a.name, None, kind="human", note="Mensch")
        unknown = [b.name for b in bots if b.name not in lg.players]
        if unknown:
            print(f"Nicht gewertet: {', '.join(unknown)} sind keine Ligaspieler ('pc.cmd league add ...').")
            return
        before = lg.players[a.name].rating
        lg.record_game([a.name] + [b.name for b in bots], list(res.places), list(res.payouts), "human_sng",
                       {"seed": res.seed})
        p = lg.players[a.name]
        print(f"Dein Rating: {before:.0f} -> {p.rating:.0f} (± {p.rating_sd:.0f}), "
              f"sicher {p.conservative:.0f}, {p.games} gewertete Turniere")


def cmd_play_stats(a):
    from .ai.play import load_sessions, stats_markdown
    print(stats_markdown(load_sessions(data_dir() / "play"), a.name))


def cmd_league(a):
    lg = _league()
    if a.leaguecmd == "add":
        p = lg.add(a.name, a.spec, note=a.note or "")
        print(f"Neu in der Liga: {p.name} = {p.spec}")
    elif a.leaguecmd == "retire":
        lg.players[a.name].active = False
        lg.save()
        print(f"{a.name} spielt in automatischen Runden nicht mehr mit (Rating bleibt).")
    elif a.leaguecmd == "run":
        from .ai.league import display
        from .ai.tournament import BlindSchedule, TournamentConfig
        cfg = TournamentConfig(start_stack=a.stack, blinds=BlindSchedule(10, 20, a.level_hands))

        def progress(k, n, g):
            order = [nm for _, nm in sorted(zip(g["ranks"], g["participants"]))]
            print(f"  Spiel {k}/{n}: {' > '.join(order)}", flush=True)

        lg.run(a.rounds, a.table, cfg, seed=a.seed, progress=progress)
        print()
        print(lg.leaderboard_markdown())
    elif a.leaguecmd == "bench":
        targets = [a.name] if a.name else [p.name for p in lg.players.values() if p.kind == "bot" and p.active]
        for nm in targets:
            r = lg.benchmark(nm, hands=a.hands, tournaments=a.tournaments)
            print(f"{nm:14s} Cash {r['cash']['bb_per_100']:+7.1f} bb/100 {r['cash']['ci95']}   "
                  f"SNG ROI {r['sng']['roi_pct']:+6.1f} % {r['sng']['ci95']}   "
                  f"Push/Fold-Verlust {r['pushfold']['pf_ev_loss_per_spot_bb']} BB/Spot", flush=True)
    else:  # show
        md = lg.leaderboard_markdown()
        (lg.root / "report.md").write_text(md, "utf-8")
        (lg.root / "report.html").write_text(lg.report_html(), "utf-8")
        print(md)
        print(f"\nVerlauf als Grafik: {lg.root / 'report.html'}")


def _league_pool(lg, exclude=(), self_play: float = 0.2):
    from .ai.optimize import LeaguePool
    players = [(p.name, p.spec, p.mu) for p in lg.players.values()
               if p.kind == "bot" and p.active and p.spec and p.name not in exclude]
    return LeaguePool(players, self_play=self_play)


def _pool_text(pool) -> str:
    from .ai.optimize import LeaguePool
    if not isinstance(pool, LeaguePool):
        return "fest " + "/".join(pool)
    shares = sorted(pool.shares().items(), key=lambda kv: -kv[1])
    extra = f"; Zufalls-Stilbots {pool.random_share:.0%} der Plaetze" if pool.random_share else ""
    return "Liga (" + ", ".join(f"{n} {v:.0%}" for n, v in shares) + f"; Self-Play {pool.self_play:.0%}{extra})"


def cmd_data(a):
    from .ai.phh import agreement, build_dataset, load_dataset, save_dataset
    if a.datacmd == "humans":
        from .ai import humans
        root = humans.handhq_dir()
        dirs = [root / d for d in a.sets.split(",")] if a.sets else sorted(p for p in root.iterdir() if p.is_dir())
        missing = [d for d in dirs if not d.exists()]
        if missing:
            sys.exit("Nicht vorhanden: " + ", ".join(d.name for d in missing))
        print(f"HandHQ: {', '.join(d.name for d in dirs)}", flush=True)
        hs = humans.collect(dirs, max_files=a.max_files, workers=a.workers, progress=lambda i, n, h: print(
            f"  {i}/{n} Dateien, {h.used} Haende, {len(h.c)} Spieler", flush=True))
        types = humans.player_types(hs.stats(), k=a.types, min_hands=a.min_hands)
        p = humans.save(a.name, hs, types)
        print(f"{hs.used} Haende ({hs.skipped} uebersprungen), {len(hs.c)} Spieler -> {p}")
        print(f"Spielertypen (Spieler mit >= {a.min_hands} Haenden, Anteil nach Haenden):")
        for t in types:
            m = t["mean"]
            print(f"  {t['share']:5.1%} {humans.type_name(m):32s} " + "  ".join(f"{k} {m[k]:.0%}" for k in m)
                  + f"   {t['bb100']:+.1f} bb/100")
        return
    if a.datacmd == "humandata":
        from .ai import humandata, humans
        root = humans.handhq_dir()
        dirs = [root / d for d in a.sets.split(",")] if a.sets else sorted(p for p in root.iterdir() if p.is_dir())
        files = [f for d in dirs for f in sorted(d.rglob("*.phhs"))]
        if a.max_files:
            files = files[:a.max_files]
        out = Path(a.out) if a.out else data_dir() / "humans" / "actions"
        print(f"HandHQ-Showdown-Entscheidungen: {len(files)} Dateien, {a.workers} Prozesse -> {out}", flush=True)
        rep = humandata.extract(files, out, workers=a.workers, files_per_shard=a.files_per_shard,
                                progress=lambda k, n, t, s: print(
                                    f"  Scherbe {k + 1}/{n}: {t['hands']} Haende, {t['with_cards']} mit Karten, "
                                    f"{t['ok']} nachgespielt, {t['decisions']} Entscheidungen, {s:.0f}s", flush=True))
        print(json.dumps({k: v for k, v in rep.items() if k != "problems"}, ensure_ascii=False))
        print("Probleme:", rep["problems"])
        return
    if a.datacmd == "humanpublic":
        from .ai import humandata, humans
        root = humans.handhq_dir()
        dirs = [root / d for d in a.sets.split(",")] if a.sets else sorted(p for p in root.iterdir() if p.is_dir())
        files = [f for d in dirs for f in sorted(d.rglob("*.phhs"))]
        if a.max_files:
            files = files[:a.max_files]
        out = Path(a.out) if a.out else data_dir() / "humans" / "actions"
        print(f"HandHQ alle Entscheidungen (kartenfrei, mit Folds): {len(files)} Dateien, {a.workers} Prozesse -> {out}", flush=True)
        rep = humandata.extract_public(files, out, workers=a.workers, files_per_shard=a.files_per_shard,
                                       progress=lambda k, n, t, s: print(
                                           f"  Scherbe {k + 1}/{n}: {t['hands']} Haende, {t['ok']} nachgespielt, "
                                           f"{t['decisions']} Entscheidungen, {s:.0f}s", flush=True))
        print(json.dumps({k: v for k, v in rep.items() if k != "problems"}, ensure_ascii=False))
        print("Probleme:", rep["problems"])
        return
    if a.datacmd == "pluribus":
        src = Path(a.source) if a.source else data_dir() / "external" / "phh-dataset" / "data" / "pluribus"
        files = sorted(src.rglob("*.phh"))
        if not files:
            sys.exit(f"Keine .phh-Dateien in {src}. Holen mit:\n  git clone --depth 1 --filter=blob:none --sparse "
                     "https://github.com/uoftcprg/phh-dataset.git\n  git -c safe.directory=* sparse-checkout set data/pluribus")
        print(f"{len(files)} Haende aus {src} werden in unserer Engine nachgespielt ...", flush=True)
        data, rep = build_dataset(files, progress=lambda k, n: print(f"  {k}/{n}", flush=True))
        path = save_dataset("pluribus", data, rep)
        print(f"  {rep['ok']}/{rep['hands']} Haende stimmen mit der Engine ueberein, {rep['decisions']} Entscheidungen")
        for p, k in sorted(rep["by_player"].items(), key=lambda kv: -kv[1]):
            print(f"    {p:10s} {k:6d}")
        for ex in rep["examples"]:
            print(f"  Problem: {ex}")
        print(f"Gespeichert: {path}")
        return
    if a.datacmd == "agree":
        from .ai.nn_agent import load_weights
        for ck in a.ckpt.split(","):
            w = load_weights(a.run, ck)
            data = load_dataset(a.dataset, a.players.split(",") if a.players else None, version=w["features"])
            r = agreement(w, data)
            print(f"{a.run} ckpt {ck:>6s}: trifft {r['top1']:.1%} der Entscheidungen von "
                  f"{a.players or 'allen'} (mittlere Wahrscheinlichkeit {r['prob']:.1%})  {r['per_action']}")


def cmd_bench(a):
    from .ai.bench import run_bench, write_report
    if a.benchcmd == "show":
        print(write_report())
        return
    if a.benchcmd == "slumbot":
        from .ai import slumbot
        lg = _league()
        name = a.name or a.spec
        spec = lg.players[a.spec].spec if a.spec in lg.players and lg.players[a.spec].spec else a.spec

        def show(n, sm):
            r, e, b = sm["roh"], sm["allin_ev"], sm["bereinigt"]
            print(f"  {sm['hands']:6d} Haende  roh {r['bb100']:+7.1f} bb/100 [{r['ci95'][0]:+.0f}; {r['ci95'][1]:+.0f}]"
                  f"  All-in-EV {e['bb100']:+7.1f} [{e['ci95'][0]:+.0f}; {e['ci95'][1]:+.0f}]"
                  f"  bereinigt {b['bb100']:+7.1f} [{b['ci95'][0]:+.0f}; {b['ci95'][1]:+.0f}]"
                  f" (Kartenglueck {b.get('glueck_bb100', float('nan')):+.0f})"
                  + (f"  ({sm['engine_mismatch']} Abweichungen Engine!)" if sm["engine_mismatch"] else ""), flush=True)

        if a.hands > 0:
            print(f"Slumbot: {name} = {spec}, {a.hands} Haende, {a.workers} parallele Sitzungen", flush=True)
            slumbot.run(spec, name, a.hands, workers=a.workers, progress=show)
        show(0, slumbot.summarize(slumbot.load_hands(name)))
        return
    if a.benchcmd == "gtow":
        from .ai import gtow
        lg = _league()
        name = a.name or a.spec
        spec = lg.players[a.spec].spec if a.spec in lg.players and lg.players[a.spec].spec else a.spec

        def show(n, sm):
            r, v, e = sm["roh"], sm["aivat"], sm["allin_ev"]
            print(f"  {sm['hands']:6d} Haende  roh {r['bb100']:+7.1f} bb/100 [{r['ci95'][0]:+.0f}; {r['ci95'][1]:+.0f}]"
                  f"  AIVAT {v['bb100']:+7.1f} [{v['ci95'][0]:+.0f}; {v['ci95'][1]:+.0f}]"
                  f"  All-in-EV {e['bb100']:+7.1f}"
                  + (f"  ({sm['engine_mismatch']} Abweichungen Engine!)" if sm["engine_mismatch"] else ""), flush=True)

        if a.hands > 0:
            print(f"GTO Wizard AI: {name} = {spec}, {a.hands} Haende, {a.workers} parallele Haende", flush=True)
            gtow.run(spec, name, a.hands, workers=a.workers, key=a.key, progress=show)
        show(0, gtow.summarize(gtow.load_hands(name)))
        if a.server:
            print("Server: " + json.dumps(gtow.server_results(gtow.api_key(a.key)), ensure_ascii=False))
        return
    if a.benchcmd == "turnier":
        from .ai.ziele import add_tournament, pokerth_summary, remove_last_tournament
        if a.ersetzt:
            alt = remove_last_tournament(a.bot)
            print("Ersetzt: " + (json.dumps(alt, ensure_ascii=False) if alt else "kein Eintrag vorhanden"))
        rec = add_tournament(a.platz, a.spieler, a.bot, a.notiz or "")
        s = pokerth_summary(a.bot)
        print(f"Eingetragen: Platz {rec['platz']} von {rec['spieler']} ({rec['bot']}). Bisher {s['n']} Turniere, "
              f"ROI {s['roi']:+.1f} %, Siege {s['wins']} ({s['win_rate']:.0%})")
        return
    if a.benchcmd == "ziele":
        from .ai.ziele import MEASURE_SETS, scoreboard, scoreboard_text
        lg = _league()
        spec = lg.players[a.bot].spec if a.bot in lg.players and lg.players[a.bot].spec else a.bot
        name = a.name or a.bot
        if a.messen or a.exploit:
            print(f"Messe {name} = {spec}: {', '.join(MEASURE_SETS)}{' + Ausbeuter' if a.exploit else ''} ...",
                  flush=True)
            run_bench(spec, name, sets=MEASURE_SETS if a.messen else (), exploit=a.exploit, workers=a.workers)
        print(scoreboard_text(name, scoreboard(name, a.slumbot, a.bot)))
        return
    if a.benchcmd == "compare":
        from .ai.bench import compare
        try:
            res = compare(a.a, a.b)
        except KeyError as e:
            sys.exit(str(e))
        print(f"{a.a} minus {a.b} (gepaart, gleiche Karten und Tische):")
        for s, ra, rb, d in res:
            sig = "  *" if d["ci95"][0] > 0 or d["ci95"][1] < 0 else ""
            print(f"  {s:11s} {ra['roi']:+6.1f} % vs {rb['roi']:+6.1f} %   Differenz {d['roi']:+5.1f} "
                  f"[{d['ci95'][0]:+.1f}; {d['ci95'][1]:+.1f}]  n={d['n']}{sig}")
        if not res:
            print("  keine gemeinsamen Testsets")
        return
    from .ai.bench import FORMAT_SETS, PRECISE_SETS
    groups = {"formate": FORMAT_SETS, "praezise": PRECISE_SETS}
    sets = tuple(x for part in a.sets.split(",") for x in groups.get(part, [part]))
    lg = _league()
    a.name = a.name or a.spec
    if a.spec in lg.players and lg.players[a.spec].spec:      # Liga-Name statt Spezifikation (ohne '&')
        a.spec = lg.players[a.spec].spec
    print(f"Pruefstand fuer {a.name} = {a.spec}: {', '.join(sets)}{' + Ausbeuter-Test' if a.exploit else ''}",
          flush=True)

    def progress(s, r):
        if "roi" in r:
            print(f"  {s:8s} ROI {r['roi']:+.1f} % [{r['ci95'][0]:+.1f}; {r['ci95'][1]:+.1f}]", flush=True)
        elif "bb_per_100" in r:
            print(f"  {s:8s} {r['bb_per_100']:+.1f} bb/100 {r['ci95']}", flush=True)
        elif "top1" in r:
            print(f"  {s:8s} trifft {r['top1']:.1%} der Pluribus-Entscheidungen", flush=True)
        elif "exploiter_roi" in r:
            print(f"  {s:8s} Ausbeuter {r['exploiter_roi']:+.1f} % {r['ci95']}", flush=True)

    run_bench(a.spec, a.name, sets=sets, exploit=a.exploit, progress=progress)
    print(write_report())


def cmd_cfr(a):
    from .ai.bench import run_bench
    from .ai.cfr import train_cfr
    from .ai.nn_agent import rl_root
    run_dir = rl_root() / a.run
    print(f"CFR-Lauf {run_dir}: bis Runde {a.rounds}, je Runde {a.traversals} Durchlaeufe pro Prozess, "
          f"Pruefstand alle {a.bench_every} Runden", flush=True)

    def progress(e):
        if e["round"] % 5 == 0:
            print(f"  Runde {e['round']:4d}: {e['infosets']:7d} Infosets, {e['traversals_per_s']:6.0f} Durchlaeufe/s, "
                  f"{e['elapsed_s']:.0f}s", flush=True)

    done = 0
    log = run_dir / "log.jsonl"
    if log.exists():
        lines = [line for line in log.read_text("utf-8").splitlines() if line.strip()]
        done = json.loads(lines[-1])["round"] if lines else 0
    while done < a.rounds:
        target = min(a.rounds, (done // a.bench_every + 1) * a.bench_every)
        last = train_cfr(run_dir, target, traversals=a.traversals, seed=a.seed, progress=progress)
        done = last["round"]
        b = run_bench(f"cfr?run={a.run}", f"{a.run}@{done}", sets=("fest48", "mix96"))
        print(f"  Pruefstand Runde {done}: mix96 {b['mix96']['roi']:+.1f} %, fest48 {b['fest48']['roi']:+.1f} %",
              flush=True)


def cmd_deepcfr(a):
    from .ai.bench import run_bench
    from .ai.deepcfr import DeepCFRConfig, train_deepcfr
    from .ai.nn_agent import rl_root
    run_dir = rl_root() / a.run
    cfg = DeepCFRConfig(traversals=a.traversals, snapshot_every=a.snapshot_every, seed=a.seed,
                        adv_capacity=a.buffer, strat_capacity=a.buffer)
    print(f"Deep-CFR-Lauf {run_dir}: bis Iteration {a.iterations}, {a.traversals} Durchlaeufe je Prozess, "
          f"Strategie-Netz + Pruefstand alle {a.snapshot_every} Iterationen", flush=True)

    def progress(e):
        print(f"  It {e['iteration']:4d}: {e['adv_samples']:8d} Bedauerns-Daten (gesehen {e['adv_seen']}), "
              f"Verlust {e['adv_loss']:.4f}, Spielen {e['rollout_s']:.0f}s, Netz {e['train_s']:.0f}s", flush=True)

    def snapshot(t, e, ex):
        b = run_bench(f"nn?run={a.run}@{t}", f"{a.run}@{t}", sets=("fest48", "mix96", "pluribus"), ex=ex)
        plu = f", wie Pluribus {b['pluribus']['top1']:.0%}" if "pluribus" in b else ""
        print(f"  Pruefstand It {t}: mix96 {b['mix96']['roi']:+.1f} %, fest48 {b['fest48']['roi']:+.1f} %{plu}",
              flush=True)

    train_deepcfr(run_dir, a.iterations, cfg, progress=progress, on_snapshot=snapshot)


def cmd_exploit(a):
    from .ai.nn_agent import checkpoint_path
    from .ai.rl import exploit_test
    run, _, ck = a.init.partition("@")
    init = checkpoint_path(run, ck or 0)
    print(f"Ausbeuter-Test fuer {a.target}: Start {init.parent.name}@{ck or 0}, {a.iterations} Iterationen "
          f"gegen 5 Kopien, dann {a.schemes} frische Kartenschemata", flush=True)

    def progress(e):
        if e["iteration"] % 10 == 0:
            print(f"  It {e['iteration']:4d}: {e['bb_per_hand']:+.3f} BB/Hand ({e['elapsed_s']:.0f}s)", flush=True)

    r = exploit_test(a.target, init, iterations=a.iterations, schemes=a.schemes, progress=progress)
    print(f"  Ausbeuter ROI {r['exploiter_roi']:+.1f} % (95 %: {r['ci95'][0]:+.1f} .. {r['ci95'][1]:+.1f}), "
          f"ungeuebter Startpunkt {r['start_roi']:+.1f} %  -> je hoeher, desto ausnutzbarer ist {a.target}")


def cmd_train_nn(a):
    from .ai.nn_agent import rl_root
    from .ai.optimize import gate
    from .ai.rl import RLConfig, behavior_clone, new_run_dir, snapshot_spec, train_ppo
    lg = _league()
    run_dir = rl_root() / a.run if a.run else new_run_dir()
    print(f"Lauf: {run_dir}", flush=True)
    log = lambda msg: print(msg, flush=True)
    if a.traincmd == "bc" and a.dataset:
        from .ai.phh import load_dataset
        from .ai.rl import fit_bc
        players = a.players.split(",") if a.players else None
        from .ai.features import FEATURES_VERSION
        data = load_dataset(a.dataset, players, version=a.features or FEATURES_VERSION)
        print(f"Nachahmung aus Datensatz '{a.dataset}' ({a.players or 'alle Spieler'}): {len(data['a'])} Entscheidungen",
              flush=True)
        meta = fit_bc(run_dir, data, {"dataset": a.dataset, "players": players}, epochs=a.epochs, progress=log)
        print(f"  Trefferquote {meta['holdout_accuracy']:.1%} -> {run_dir / 'ckpt_000000.pt'}")
        return
    if a.traincmd == "bc" or (a.teacher and not (run_dir / "ckpt_000000.pt").exists()):
        print(f"Nachahmung von '{a.teacher or 'rock'}' ...", flush=True)
        meta = behavior_clone(run_dir, teacher=a.teacher or "rock", tournaments=a.bc_tournaments, progress=log)
        print(f"  {meta['decisions']} Entscheidungen, Trefferquote {meta['holdout_accuracy']:.1%} "
              f"({meta['elapsed_s']:.0f}s) -> {run_dir / 'ckpt_000000.pt'}")
        if a.traincmd == "bc":
            print(f"In die Liga: pc.cmd league add nn-bc \"{snapshot_spec(run_dir.name, 0)}\"")
            return
    if getattr(a, "widen_from", None) and not (run_dir / "ckpt_000000.pt").exists():
        from .ai.nn_agent import checkpoint_path, load_checkpoint, net_from_checkpoint, save_checkpoint, widen_net
        src_run, _, src_ck = a.widen_from.partition("@")
        src = net_from_checkpoint(load_checkpoint(checkpoint_path(src_run, src_ck or "latest")))
        net = widen_net(src, a.features or src.features_version, a.actions)
        save_checkpoint(run_dir / "ckpt_000000.pt", net, {"phase": "widen", "from": a.widen_from,
                                                          "features": net.features_version})
        print(f"Start: {a.widen_from} aufgeweitet {src.features_version} -> {net.features_version}, "
              f"{src.pi.out_features} -> {net.pi.out_features} Aktionen", flush=True)
    if a.champion not in lg.players or lg.players[a.champion].spec is None:
        sys.exit(f"Titelverteidiger '{a.champion}' ist kein Bot in der Liga")
    cfg = RLConfig(tournaments=a.tournaments, seed=a.seed, anchor_coef=a.anchor_coef, anchor=a.anchor or "",
                   random_share=a.random_share, exploit_every=a.exploit_every, exploit_iters=a.exploit_iters,
                   random_formats=a.random_formats, lr=a.lr, bench_every=a.bench_every,
                   bench_sets=a.bench_sets, bench_ref=a.bench_ref or "", anchor_min_players=a.anchor_min_players,
                   table_weights=a.table_weights or "", self_play_seats=a.self_play_seats,
                   human_share=a.human_share, icm=a.icm)
    pool = _league_pool(lg, self_play=cfg.self_play)
    pool.random_share = cfg.random_share
    print(f"PPO: bis Iteration {a.iterations}, {cfg.tournaments} Sit&Gos je Iteration\n"
          f"Gegner: {_pool_text(pool)}, Self-Play = eine fruehere Version am Tisch", flush=True)

    def progress(e):
        ev = f"  ROI vs fester Pool {e['eval_roi']:+.1f} %" if "eval_roi" in e else ""
        if "pluribus_top1" in e:
            ev += f", wie Pluribus {e['pluribus_top1']:.0%}"
        print(f"  It {e['iteration']:4d}: {e['decisions']:6d} Entsch., {e['bb_per_hand']:+.3f} BB/Hand, "
              f"Entropie {e.get('entropy', 0):.2f}, KL {e.get('approx_kl', 0):+.4f} "
              f"({e['rollout_s']:.0f}s Spielen, {e['elapsed_s']:.0f}s gesamt){ev}", flush=True)

    res = train_ppo(run_dir, a.iterations, pool, cfg, progress=progress)
    cand = snapshot_spec(run_dir.name, res["snapshots"][-1])
    if not a.gate_schemes:
        print(f"Fertig. Kandidat: {cand}")
        return
    champ_spec = lg.players[a.champion].spec
    gate_pool = _league_pool(lg, exclude={a.champion}, self_play=0.0)
    print(f"\nAufnahmepruefung {cand} gegen '{a.champion}' auf {a.gate_schemes} frischen Kartenschemata ...",
          flush=True)
    g = gate(cand, champ_spec, schemes=a.gate_schemes, pool=gate_pool, seed=200_000 + a.seed * 1000 + res["iterations"])
    (run_dir / f"gate_{res['iterations']:06d}.json").write_text(json.dumps(g, indent=2), "utf-8")
    print(f"  Kandidat ROI {g['candidate_roi']:+.1f} %, {a.champion} ROI {g['champion_roi']:+.1f} %, "
          f"Differenz {g['diff_roi']:+.1f} % (95 %: {g['ci95'][0]:+.1f} .. {g['ci95'][1]:+.1f})")
    if g["passed"]:
        name = a.name or f"nn-{time.strftime('%m%d-%H%M')}"
        lg.add(name, cand, note=f"PPO {run_dir.name} It {res['iterations']}, Gate vs {a.champion} "
                                f"{g['diff_roi']:+.1f} % {g['ci95']}")
        print(f"  BESTANDEN -> in die Liga eingetragen als '{name}'.")
    else:
        print("  Nicht bestanden - nichts eingetragen. Weitertrainieren: "
              f"pc.cmd train rl --run {run_dir.name} --iterations {res['iterations'] * 2}")


def cmd_valuedata(a):
    from .ai.valuedata import data_dir, generate
    out = Path(a.out) if a.out else data_dir() / f"{a.street}-{a.seed:08d}.npz"
    print(f"Wertnetz-Daten {a.street}: {a.n} Situationen ab Seed {a.seed}, {a.workers} Prozesse -> {out}", flush=True)

    def progress(k, n, secs):
        print(f"  {k}/{n} geloest, {secs:.0f}s, {secs / k:.2f}s je Situation", flush=True)
    m = generate(a.street, a.n, out, seed=a.seed, iters=a.iters, workers=a.workers, threads=a.threads,
                 progress=progress, vnet=a.vnet)
    print(json.dumps({k: m[k] for k in ("n", "errors", "iters", "secs_per_sample", "nodes_mean", "elapsed_s", "path")},
                     ensure_ascii=False))


def cmd_teacher(a):
    from .ai import teacher
    if a.traincmd == "teacher-collect":
        opps = [o for o in a.opponents.split(",") if o]
        stacks = [int(s) for s in a.stacks.split(",") if s]
        print(f"Lehrer {a.search}\nSchueler {a.student}\nGegner {opps}, Stacks {stacks} BB, {a.hands} Blaetter je Match -> {a.out}", flush=True)
        meta = teacher.collect(a.search, a.student, opps, a.hands, stacks, a.out, seed=a.seed,
                               progress=lambda k, n, m, rows, s: print(
                                   f"  Match {k}/{n}: {m['opp']} {m['stack_bb']} BB: {m['bb100']:+.1f} bb/100, "
                                   f"{m['rows']} Zeilen ({rows} gesamt), {s:.0f}s", flush=True))
        print(json.dumps({k: v for k, v in meta.items() if k != "matches"}, ensure_ascii=False))
        return
    import glob
    paths = sorted(glob.glob(a.data))
    if not paths:
        sys.exit(f"keine Lehrerdaten fuer {a.data}")
    run, _, ck = a.student.partition("@")
    res = teacher.fit(run, ck or "latest", paths, a.out_run, epochs=a.epochs, batch=a.batch, lr=a.lr, kl_coef=a.kl,
                      log=lambda m: print("  " + m, flush=True))
    print(f"-> {res['out']} ({res['n']} Zeilen)")


def cmd_humanfold(a):
    from .ai import humanfold
    rows = Path(a.rows) if a.rows else data_dir() / "humans" / "actions"
    out = data_dir() / "humans" / f"{a.out}.npz"
    res = humanfold.train(rows, out, max_rows=a.max_rows, epochs=a.epochs, max_shards=a.max_shards,
                          log=lambda m: print(m, flush=True))
    print(json.dumps({k: v for k, v in res.items() if k != "hist"}, ensure_ascii=False))


def cmd_valuenet(a):
    import glob
    from .ai.valuedata import data_dir
    from .ai.valuenet import train
    paths = sorted(glob.glob(a.data))
    if not paths:
        sys.exit(f"keine Scherben fuer {a.data}")
    out = Path(a.out) if a.out.endswith(".pt") or "\\" in a.out or "/" in a.out else data_dir() / f"{a.out}.pt"
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"Wertnetz: {len(paths)} Scherben -> {out}", flush=True)
    res = train(paths, out, a.epochs, a.batch, a.lr, a.width, a.depth, resume=a.resume,
                log=lambda m: print("  " + m, flush=True))
    print(json.dumps({k: v for k, v in res.items() if k != "hist"}, ensure_ascii=False))


def cmd_train(a):
    from .ai.optimize import DEFAULT_POOL, gate, run_cem
    lg = _league()
    out = data_dir() / "train" / time.strftime("%Y%m%d-%H%M%S")
    champ_name = a.champion
    if champ_name not in lg.players or lg.players[champ_name].spec is None:
        sys.exit(f"Titelverteidiger '{champ_name}' ist kein Bot in der Liga")
    champ_spec = lg.players[champ_name].spec
    league = a.opponents == "league"
    # Aufnahmepruefung ohne den Titelverteidiger als Gegner (er saesse sonst gegen sich selbst)
    gate_pool = _league_pool(lg, exclude={champ_name}, self_play=0.0) if league else DEFAULT_POOL
    if a.traincmd == "gate":
        cand = a.candidate
        if a.from_dir:
            cand = json.loads((Path(a.from_dir) / "result.json").read_text("utf-8"))["center"]["spec"]
        if not cand:
            sys.exit("Kandidat angeben oder --from <Trainingsordner>")
        print(f"Kandidat: {cand}\nTitelverteidiger: {champ_name} = {champ_spec}\n"
              f"Gegner: {_pool_text(gate_pool)}", flush=True)
        r = gate(cand, champ_spec, schemes=a.schemes, seed=a.seed, pool=gate_pool)
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return
    pool = _league_pool(lg) if league else DEFAULT_POOL
    print(f"Training (CEM): Start {a.start}, {a.generations} Generationen x {a.population} Kandidaten, "
          f"{a.schemes} Kartenschemata je Generation\nGegner: {_pool_text(pool)}")

    def progress(e):
        print(f"  Gen {e['generation']:2d}: bester ROI {e['best_roi']:+6.1f} %, Mittel {e['mean_roi']:+6.1f} %, "
              f"Zentrum {e['center_roi']:+6.1f} %, Streuung {e['std_mean']:.3f}  ({e['elapsed_s']:.0f}s)", flush=True)

    if a.resume:
        out = Path(a.resume)
        print(f"Setze Training fort aus {out}")
    res = run_cem(a.generations, a.population, a.schemes, start=a.start, seed=a.seed, out_dir=out,
                  progress=progress, resume=bool(a.resume), pool=pool)
    (out / "result.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), "utf-8")
    cand = res["center"]["spec"]
    print(f"\nKandidat (Zentrum der Verteilung): {cand}")
    print(f"Aufnahmepruefung gegen '{champ_name}' auf {a.gate_schemes} frischen Kartenschemata ...", flush=True)
    print(f"  Gegner: {_pool_text(gate_pool)}", flush=True)
    # eigener Pruefsatz je Trainings-Seed: ein immer gleicher Satz wuerde ueber viele Laeufe
    # selbst zum Auswahlkriterium und damit "abgenutzt"
    g = gate(cand, champ_spec, schemes=a.gate_schemes, pool=gate_pool, seed=100_000 + a.seed)
    (out / "gate.json").write_text(json.dumps(g, indent=2), "utf-8")
    print(f"  Kandidat ROI {g['candidate_roi']:+.1f} %, {champ_name} ROI {g['champion_roi']:+.1f} %, "
          f"Differenz {g['diff_roi']:+.1f} % (95 %: {g['ci95'][0]:+.1f} .. {g['ci95'][1]:+.1f})")
    if g["passed"]:
        name = a.name or f"opt-{time.strftime('%m%d-%H%M')}"
        lg.add(name, cand, note=f"CEM aus {a.start} gegen {'Liga' if league else 'festen Pool'}, "
                                f"Gate vs {champ_name} {g['diff_roi']:+.1f} % {g['ci95']}")
        print(f"  BESTANDEN -> in die Liga eingetragen als '{name}'. Weiter mit: pc.cmd league run --rounds 30")
    else:
        print("  Nicht bestanden - Vorsprung nicht belastbar. Nichts eingetragen.")
    print(f"Protokoll: {out}")


def cmd_verify(a):
    from .journal import verify_manifest
    probs = verify_manifest(_session_path(a.session))
    print("OK - alle Dateien unveraendert" if not probs else "\n".join(probs))
    sys.exit(1 if probs else 0)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pokercollector", description="Visuelle Erfassung von PokerTH-Partien")
    ap.add_argument("--profile", help="Pfad zu einem Tischprofil (JSON); Standard: eingebautes PokerTH-Web-Profil")
    ap.add_argument("--allow-sleep", action="store_true",
                    help="Standby waehrend des Laufs erlauben (Standard: wach halten, damit lange Laeufe nicht abbrechen)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("calibrate", help="Screenshot analysieren, Overlay-Bild erzeugen")
    p.add_argument("image")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_calibrate)

    p = sub.add_parser("analyze", help="Video oder Screenshot-Ordner auswerten (neue Sitzung)")
    p.add_argument("input")
    p.add_argument("--step", type=float, default=0.2, help="Sekunden zwischen analysierten Videoframes")
    p.add_argument("--interval", type=float, default=1.0, help="angenommener Abstand zwischen Screenshots")
    p.set_defaults(fn=cmd_analyze)

    p = sub.add_parser("windows", help="Fenster auflisten")
    p.add_argument("filter", nargs="?")
    p.set_defaults(fn=cmd_windows)

    p = sub.add_parser("live", help="Fenster live erfassen, Sitzungen automatisch starten/beenden")
    p.add_argument("--window", default="PokerTH", help="Teil des Fenstertitels")
    p.add_argument("--hwnd", type=int)
    p.add_argument("--fps", type=float, default=8.0)
    p.add_argument("--segment", type=float, default=120.0, help="Segmentlaenge in Sekunden")
    p.add_argument("--stop-after", type=float, default=20.0, help="Sitzung endet nach so vielen Sekunden ohne Tisch")
    p.add_argument("--max-seconds", type=float)
    p.add_argument("--no-video", action="store_true", help="nur Journal, kein Video speichern")
    p.add_argument("--allow-background", action="store_true",
                   help="auch aufnehmen, wenn das Fenster nicht im Vordergrund ist (Risiko: verdeckte Inhalte)")
    p.add_argument("--advice", action="store_true", help="Vorschlag anzeigen, wenn du dran bist")
    p.add_argument("--leiste", action="store_true",
                   help="Vorschlag zusaetzlich in der Lynx-Leiste ueber der Taskleiste (mit Ton; setzt --advice)")
    p.add_argument("--still", action="store_true", help="Leiste ohne Ton")
    p.add_argument("--kein-eintrag", action="store_true",
                   help="erkanntes Turnierende nicht automatisch in die Zieltafel eintragen")
    p.add_argument("--mischen", action="store_true",
                   help="Vorschlag aus der gemischten Strategie ziehen statt der wahrscheinlichsten Aktion")
    p.add_argument("--agent", default="lynx-4-300",
                   help="Liga-Name oder Agent fuer Vorschlaege (Standard lynx-4-300 = bester Bot)")
    p.set_defaults(fn=cmd_live)

    p = sub.add_parser("live-replay", help="Aufgezeichnete Sitzung wie live abspielen: Vorschlaege + Gegnermodell")
    p.add_argument("session", help="Ordner, Teil des Namens oder 'last'")
    p.add_argument("--agent", default="lynx-4-300", help="Liga-Name oder Agent")
    p.set_defaults(fn=cmd_live_replay)
    p = sub.add_parser("leiste-demo", help="Lynx-Leiste ohne Tisch vorfuehren (Farben, Toene, Position)")
    p.add_argument("--still", action="store_true", help="ohne Ton")
    p.add_argument("--sekunden", type=float, default=3.0, help="Anzeigedauer je Beispiel")
    p.set_defaults(fn=cmd_leiste_demo)

    p = sub.add_parser("reconstruct", help="Haende einer Sitzung neu rekonstruieren")
    p.add_argument("session", help="Ordner, Teil des Namens oder 'last'")
    p.set_defaults(fn=cmd_reconstruct)

    p = sub.add_parser("report", help="Handbericht einer Sitzung ausgeben")
    p.add_argument("session")
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("inspect-reference", help="Schema einer PokerTH-Logdatei anzeigen")
    p.add_argument("file")
    p.set_defaults(fn=cmd_inspect_reference)

    p = sub.add_parser("compare", help="Sitzung mit PokerTH-Export vergleichen")
    p.add_argument("session")
    p.add_argument("reference")
    p.set_defaults(fn=cmd_compare)

    p = sub.add_parser("advise", help="Baseline-Empfehlung fuer einen Screenshot")
    p.add_argument("image")
    p.set_defaults(fn=cmd_advise)

    p = sub.add_parser("harvest-cards", help="Kartenvorlagen aus Screenshots lernen (interaktiv)")
    p.add_argument("images", nargs="+")
    p.set_defaults(fn=cmd_harvest_cards)

    p = sub.add_parser("verify", help="Pruefsummen einer Sitzung pruefen")
    p.add_argument("session")
    p.set_defaults(fn=cmd_verify)

    sim = sub.add_parser("sim", help="Simulator, Bots und Bewertung").add_subparsers(dest="simcmd", required=True)
    p = sim.add_parser("agents", help="verfuegbare Bots")
    p.set_defaults(fn=cmd_sim_agents)
    for name, fn, hlp in (("match", cmd_sim_match, "Bots gegeneinander bewerten"),
                          ("hand", cmd_sim_hand, "eine Hand spielen und zeigen")):
        p = sim.add_parser(name, help=hlp)
        p.add_argument("--agents", default="tag,station,rock,lag,maniac,equity",
                       help="Komma-Liste, z. B. tag,tag:tag2,random")
        p.add_argument("--seed", type=int, default=1)
        p.add_argument("--sb", type=int, default=10)
        p.add_argument("--bb", type=int, default=20)
        p.add_argument("--stack", type=int, default=100, help="Startstack in Big Blinds")
        if name == "match":
            p.add_argument("--hands", type=int, default=500, help="Anzahl Kartenblaetter")
            p.add_argument("--no-duplicate", action="store_true")
            p.add_argument("--show", type=int, default=0, help="so viele Handverlaeufe ausgeben")
        else:
            p.add_argument("--button", type=int, default=0)
        p.set_defaults(fn=fn)
    p = sim.add_parser("tournament", help="Sit&Go-Turniere (wie PokerTH) zwischen Bots")
    p.add_argument("--agents", default="tag,station,rock,lag,maniac,equity")
    p.add_argument("--tournaments", type=int, default=20, help="Anzahl Kartenschemata (x Spielerzahl bei Duplicate)")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--stack", type=int, default=3000, help="Startchips")
    p.add_argument("--blinds", default="10/20", help="Start-Blinds SB/BB")
    p.add_argument("--level-hands", type=int, default=10, help="Haende bis zur Verdopplung der Blinds")
    p.add_argument("--payouts", default="50,30,20", help="Prozent je Platz, z. B. 100 (Sieger bekommt alles)")
    p.add_argument("--no-duplicate", action="store_true")
    p.set_defaults(fn=cmd_sim_tournament)
    p = sim.add_parser("pushfold", help="Nash-Push/Fold-Ranges anzeigen")
    p.add_argument("--stack", type=float, default=10, help="effektiver Stack in BB")
    p.add_argument("--behind", type=int, default=1, help="Spieler hinter dem Pusher (1 = SB gegen BB)")
    p.add_argument("--caller", type=int, default=0, help="welcher Caller (0 = erster hinter dem Pusher)")
    p.add_argument("--overview", action="store_true", help="Push-Prozente fuer alle Stacks/Positionen")
    p.set_defaults(fn=cmd_sim_pushfold)
    p = sim.add_parser("review", help="eigene Entscheidungen einer Sitzung mit einem Agenten vergleichen")
    p.add_argument("session")
    p.add_argument("--agent", default="equity")
    p.set_defaults(fn=cmd_sim_review)

    p = sub.add_parser("play", help="Du gegen die Bots (Terminal)")
    p.add_argument("--mode", choices=["cash", "tournament"], default="tournament")
    p.add_argument("--opponents", default="tag,rock,lag,station,maniac", help="Bots/Ligaspieler, Komma-Liste")
    p.add_argument("--name", default="du")
    p.add_argument("--blinds", default="10/20")
    p.add_argument("--stack", type=int, default=3000, help="Turnier: Startchips")
    p.add_argument("--level-hands", type=int, default=10)
    p.add_argument("--payouts", default="50,30,20")
    p.add_argument("--stack-bb", type=int, default=100, help="Cash: Stack in BB (Rebuy auf diesen Wert)")
    p.add_argument("--hands", type=int, default=1000, help="Cash: maximale Handzahl")
    p.add_argument("--seed", type=int)
    p.add_argument("--coach", action="store_true", help="nach deiner Entscheidung Push/Fold-Hinweis zeigen")
    p.add_argument("--unrated", action="store_true", help="Turnier nicht in die Liga eintragen")
    p.add_argument("--ascii", action="store_true", help="Kartenfarben als Buchstaben")
    p.set_defaults(fn=cmd_play)

    p = sub.add_parser("play-stats", help="Auswertung deiner Partien gegen die Bots")
    p.add_argument("--name", default="du")
    p.set_defaults(fn=cmd_play_stats)

    lgp = sub.add_parser("league", help="Liga, Rating, Benchmark").add_subparsers(dest="leaguecmd", required=True)
    p = lgp.add_parser("show", help="Tabelle + Verlaufsgrafik (report.html)")
    p.set_defaults(fn=cmd_league)
    p = lgp.add_parser("add", help="Bot-Version eintragen, z. B. add tag-v2 'tag?bluff=0.2'")
    p.add_argument("name")
    p.add_argument("spec")
    p.add_argument("--note")
    p.set_defaults(fn=cmd_league)
    p = lgp.add_parser("retire", help="Bot aus automatischen Runden nehmen")
    p.add_argument("name")
    p.set_defaults(fn=cmd_league)
    p = lgp.add_parser("run", help="Ligaspiele zwischen den Bots austragen")
    p.add_argument("--rounds", type=int, default=20)
    p.add_argument("--table", type=int, default=6)
    p.add_argument("--stack", type=int, default=3000)
    p.add_argument("--level-hands", type=int, default=10)
    p.add_argument("--seed", type=int)
    p.set_defaults(fn=cmd_league)
    p = lgp.add_parser("bench", help="Benchmark gegen feste Gegner (alle Bots oder einer)")
    p.add_argument("name", nargs="?")
    p.add_argument("--hands", type=int, default=300)
    p.add_argument("--tournaments", type=int, default=10)
    p.set_defaults(fn=cmd_league)

    tr = sub.add_parser("train", help="Bots selbst verbessern").add_subparsers(dest="traincmd", required=True)
    p = tr.add_parser("cem", help="Stil-Parameter optimieren, Aufnahmepruefung, ggf. in die Liga")
    p.add_argument("--start", default="tag", help="Ausgangsstil")
    p.add_argument("--generations", type=int, default=8)
    p.add_argument("--population", type=int, default=12)
    p.add_argument("--schemes", type=int, default=12, help="Kartenschemata je Generation (x6 Turniere)")
    p.add_argument("--gate-schemes", type=int, default=48)
    p.add_argument("--champion", default="tag", help="Ligaspieler, den der Kandidat schlagen muss")
    p.add_argument("--name", help="Name in der Liga (Standard: opt-<Datum>)")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--resume", help="Trainingsordner (data\\train\\...) fortsetzen")
    p.add_argument("--opponents", choices=["league", "fixed"], default="league",
                   help="league = Tische aus allen aktiven Ligabots, starke oefter, mit Self-Play (Standard); "
                        "fixed = immer rock/tag/lag/station/maniac")
    p.set_defaults(fn=cmd_train)
    p = tr.add_parser("gate", help="Aufnahmepruefung: Kandidat gegen Titelverteidiger")
    p.add_argument("candidate", nargs="?", help="Bot-Spezifikation in Anfuehrungszeichen, z. B. \"tag?push_bb=15&bluff=0.2\"")
    p.add_argument("--from", dest="from_dir", help="Kandidat aus einem Trainingsordner (result.json) nehmen")
    p.add_argument("--champion", default="tag")
    p.add_argument("--schemes", type=int, default=48)
    p.add_argument("--seed", type=int, default=777, help="anderer Seed = andere, frische Kartenschemata")
    p.add_argument("--opponents", choices=["league", "fixed"], default="league")
    p.set_defaults(fn=cmd_train)
    p = tr.add_parser("bc", help="Lernender Bot, Schritt 1: Lehrer-Bot nachahmen -> Checkpoint 0")
    p.add_argument("--teacher", default="rock")
    p.add_argument("--run", help="Name des Laufs unter data\\rl (Standard: nn-<Datum>)")
    p.add_argument("--bc-tournaments", type=int, default=600)
    p.add_argument("--dataset", help="statt Lehrer-Bot: Datensatz unter data\\datasets, z. B. pluribus")
    p.add_argument("--players", help="nur diese Spieler des Datensatzes, Komma-getrennt, z. B. Pluribus")
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--features", default=None, help="Merkmalsversion des Datensatzes (Standard: aktuelle)")
    p.set_defaults(fn=cmd_train_nn)
    bp = sub.add_parser("bench", help="Pruefstand: feste Testsets fuer jeden Kandidaten").add_subparsers(
        dest="benchcmd", required=True)
    p = bp.add_parser("run", help="Kandidaten auf den Pruefstand stellen")
    p.add_argument("spec", help="Liga-Name (z. B. opt-1) oder Bot, z. B. \"nn?run=pros-1@200\"")
    p.add_argument("--name", help="Name in der Tabelle (Standard: wie angegeben)")
    p.add_argument("--sets", default="fest48,mix96,cash,pluribus",
                   help="Testsets, Komma-getrennt; Formate: hu48,3max48,10max48,turbo48,deep48,pokerth48 (oder \"formate\"); "
                        "groesser z. B. mix960,pokerth480 (oder \"praezise\")")
    p.add_argument("--exploit", action="store_true", help="zusaetzlich Ausbeuter-Test (ca. 10 min)")
    p.set_defaults(fn=cmd_bench)
    p = bp.add_parser("show", help="Tabelle aller Ergebnisse")
    p.set_defaults(fn=cmd_bench)
    p = bp.add_parser("slumbot", help="Heads-up gegen Slumbot (slumbot.com) spielen: absoluter Massstab")
    p.add_argument("spec", help="Liga-Name oder Bot, z. B. \"nn?run=pros-r1@300\"")
    p.add_argument("--name", help="Name der Ergebnisdatei (Standard: wie angegeben); setzt fort")
    p.add_argument("--hands", type=int, default=1000, help="weitere Haende (0 = nur Auswertung)")
    p.add_argument("--workers", type=int, default=4, help="parallele Slumbot-Sitzungen")
    p.set_defaults(fn=cmd_bench)
    p = bp.add_parser("gtow", help="Heads-up gegen GTO Wizard AI (benchmark.gtowizard.com) spielen: 2. Massband, AIVAT")
    p.add_argument("spec", help="Liga-Name oder Bot, z. B. lynx-4-300")
    p.add_argument("--name", help="Name der Ergebnisdatei (Standard: wie angegeben); setzt fort")
    p.add_argument("--hands", type=int, default=500, help="weitere Haende (0 = nur Auswertung)")
    p.add_argument("--workers", type=int, default=2, help="parallele Haende (Anbieter-Client nutzt 5)")
    p.add_argument("--key", help="API-Schluessel (sonst GTOW_API_KEY oder data/bench/gtow/api_key.txt)")
    p.add_argument("--server", action="store_true", help="zusaetzlich die Serverstatistik (AIVAT) abrufen")
    p.set_defaults(fn=cmd_bench)
    p = bp.add_parser("ziele", help="Anzeigetafel unserer Ziele (ZIELE.md) fuer einen Bot")
    p.add_argument("bot", nargs="?", default="lynx-4-300", help="Liga-Name oder Bot")
    p.add_argument("--name", help="Name auf dem Pruefstand (Standard: wie bot)")
    p.add_argument("--messen", action="store_true", help="mensch480, nash240, kurz240 neu messen (ca. 15-30 min)")
    p.add_argument("--exploit", action="store_true", help="zusaetzlich Ausbeuter-Test (ca. 10-20 min)")
    p.add_argument("--slumbot", help="Name der Slumbot-Ergebnisdatei (Standard: wie --name)")
    p.add_argument("--workers", type=int, default=None)
    p.set_defaults(fn=cmd_bench)
    p = bp.add_parser("turnier", help="Ergebnis eines echten PokerTH-Turniers eintragen (Ziel 1)")
    p.add_argument("platz", type=int, help="eigener Platz (1 = gewonnen)")
    p.add_argument("--spieler", type=int, default=6, help="Spieler am Start (Standard 6)")
    p.add_argument("--bot", default="lynx-4-300", help="welcher Lynx beraten hat")
    p.add_argument("--notiz", help="z. B. 'gegen PokerTH-Bots' oder 'online'")
    p.add_argument("--ersetzt", action="store_true",
                   help="den letzten Eintrag dieses Bots (z. B. falsche automatische Erkennung) ersetzen statt anhaengen")
    p.set_defaults(fn=cmd_bench)
    p = bp.add_parser("compare", help="Zwei Eintraege gepaart vergleichen (alle gemeinsamen Testsets)")
    p.add_argument("a", help="Name in der Tabelle")
    p.add_argument("b", help="Name in der Tabelle")
    p.set_defaults(fn=cmd_bench)
    p = tr.add_parser("cfr", help="Gleichgewicht per Monte-Carlo-CFR (Pluribus-Verfahren)")
    p.add_argument("--run", default="cfr-1")
    p.add_argument("--rounds", type=int, default=200, help="Zielrunde (Gesamtzahl)")
    p.add_argument("--traversals", type=int, default=1500, help="Durchlaeufe je Prozess und Runde")
    p.add_argument("--bench-every", type=int, default=25)
    p.add_argument("--seed", type=int, default=1)
    p.set_defaults(fn=cmd_cfr)
    p = tr.add_parser("deepcfr", help="Deep CFR: Gleichgewicht mit neuronalen Netzen statt Tabelle")
    p.add_argument("--run", default="dcfr-1")
    p.add_argument("--iterations", type=int, default=100, help="Ziel-Iteration (Gesamtzahl)")
    p.add_argument("--traversals", type=int, default=600, help="Durchlaeufe je Prozess und Iteration")
    p.add_argument("--snapshot-every", type=int, default=10)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--buffer", type=int, default=1_000_000,
                   help="Eintraege je Datenpuffer (RAM ca. 220 MB je 1 Mio.; 2 Puffer)")
    p.set_defaults(fn=cmd_deepcfr)
    p = tr.add_parser("exploit", help="Ausbeuter-Test: wie stark laesst sich ein Bot gezielt ausnutzen?")
    p.add_argument("target", help="Bot-Spezifikation, z. B. rock oder \"nn?run=pros-1@200\"")
    p.add_argument("--init", default="pros-1@0", help="Startpunkt des Ausbeuters (Lauf@Checkpoint)")
    p.add_argument("--iterations", type=int, default=40)
    p.add_argument("--schemes", type=int, default=48)
    p.set_defaults(fn=cmd_exploit)
    dp = sub.add_parser("data", help="Fremde Handhistorien (PHH) einlesen und auswerten").add_subparsers(
        dest="datacmd", required=True)
    p = dp.add_parser("pluribus", help="Pluribus-Haende nachspielen -> data\\datasets\\pluribus.npz")
    p.add_argument("--source", help="Ordner mit .phh-Dateien (Standard: data\\external\\phh-dataset\\data\\pluribus)")
    p.set_defaults(fn=cmd_data)
    p = dp.add_parser("humans", help="Echte Spieler (HandHQ): Haeufigkeiten je Spieler und Spielertypen")
    p.add_argument("--sets", help="Ordner unter data\\external\\phh-dataset\\data\\handhq, Komma-getrennt (Standard: alle)")
    p.add_argument("--name", default="handhq", help="Ergebnis data\\humans\\<name>.json")
    p.add_argument("--types", type=int, default=6, help="Anzahl Spielertypen")
    p.add_argument("--min-hands", type=int, default=300, help="Spieler mit weniger Haenden zaehlen nicht fuer Typen")
    p.add_argument("--max-files", type=int, help="nur die ersten N Dateien (Test)")
    p.add_argument("--workers", type=int, default=4, help="parallele Prozesse (RAM!)")
    p.set_defaults(fn=cmd_data)
    p = dp.add_parser("humandata", help="HandHQ-Showdown-Entscheidungen mit bekannten Karten als Merkmale+Aktion (H11 Menschenmodell)")
    p.add_argument("--sets", help="Ordner unter data\\external\\phh-dataset\\data\\handhq, Komma-getrennt (Standard: alle)")
    p.add_argument("--out", help="Zielordner (Standard data\\humans\\actions)")
    p.add_argument("--max-files", type=int, help="nur die ersten N Dateien (Test)")
    p.add_argument("--files-per-shard", type=int, default=50, help="Dateien je Scherbe human-<nr>.npz")
    p.add_argument("--workers", type=int, default=2, help="parallele Prozesse")
    p.set_defaults(fn=cmd_data)
    p = dp.add_parser("humanpublic", help="HandHQ: ALLE Entscheidungen kartenfrei mit Folds (Fold-Modell, H11 Schritt 2b)")
    p.add_argument("--sets", help="Ordner unter data\\external\\phh-dataset\\data\\handhq, Komma-getrennt (Standard: alle)")
    p.add_argument("--out", help="Zielordner (Standard data\\humans\\actions, Dateien public-<nr>.npz)")
    p.add_argument("--max-files", type=int, help="nur die ersten N Dateien (Test)")
    p.add_argument("--files-per-shard", type=int, default=50)
    p.add_argument("--workers", type=int, default=4, help="parallele Prozesse")
    p.set_defaults(fn=cmd_data)
    p = dp.add_parser("agree", help="Wie oft trifft ein Netz die Entscheidungen im Datensatz?")
    p.add_argument("run")
    p.add_argument("--ckpt", default="latest", help="Checkpoint(s), Komma-getrennt, z. B. 0,100,200")
    p.add_argument("--dataset", default="pluribus")
    p.add_argument("--players", default="Pluribus")
    p.set_defaults(fn=cmd_data)
    p = tr.add_parser("humans-fit", help="Mensch-Bots: Stilbots an echte Spielertypen (data humans) anpassen")
    p.add_argument("--source", default="handhq-25nl", help="data\\humans\\<source>.json")
    p.add_argument("--name", default="mensch-25nl", help="Ergebnis data\\humans\\<name>.json")
    p.add_argument("--generations", type=int, default=10)
    p.add_argument("--population", type=int, default=16)
    p.add_argument("--hands", type=int, default=600, help="Haende je Messung")
    p.set_defaults(fn=cmd_humans_fit)
    p = tr.add_parser("valuedata", help="Wertnetz-Daten: Situationen zu Strassenbeginn exakt loesen (Meilenstein 3)")
    p.add_argument("street", choices=["river", "turn", "flop", "river-leaf", "turn-leaf"],
                   help="Strasse, zu deren Beginn bewertet wird; river-leaf = River-Anfaenge aus echten Turn-Suchen (je Seed bis 24 Zeilen), "
                        "turn-leaf = Turn-Anfaenge aus echten Flop-Suchen, River per Wertnetz (je Seed bis 12 Zeilen)")
    p.add_argument("--n", type=int, default=1000, help="Situationen in dieser Scherbe")
    p.add_argument("--seed", type=int, default=0, help="erster Seed (Scherben: seed, seed+n, ...)")
    p.add_argument("--iters", type=int, help="CFR+-Iterationen (Standard river 300, turn 150, flop 60)")
    p.add_argument("--workers", type=int, default=1, help="Prozesse")
    p.add_argument("--threads", type=int, help="numba-Faeden je Prozess (Standard: alle)")
    p.add_argument("--out", help="Zieldatei .npz (Standard data\\valuenet\\<street>-<seed>.npz)")
    p.add_argument("--vnet", help="River-Wertnetz als Blatt (turn/flop/turn-leaf; Standard bei turn-leaf: vnet-river-1)")
    p.set_defaults(fn=cmd_valuedata)
    p = tr.add_parser("valuenet", help="Wertnetz aus valuedata-Scherben trainieren (lokal klein; gross auf Kaggle)")
    p.add_argument("--data", required=True, help="Glob auf .npz-Scherben, z. B. data\\valuenet\\river-*.npz")
    p.add_argument("--out", default="vnet-river-1", help="Name unter data\\valuenet\\<out>.pt oder Pfad")
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--batch", type=int, default=512)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--width", type=int, default=1024)
    p.add_argument("--depth", type=int, default=3)
    p.add_argument("--resume", help="Checkpoint, von dem weitertrainiert wird")
    p.set_defaults(fn=cmd_valuenet)
    p = tr.add_parser("teacher-collect", help="Suche als Lehrer (H5): Suchentscheidungen als weiche Ziele sammeln")
    p.add_argument("--search", default="hus?bp=lynx-4-300&auto=1&iters=60&iters_river=150&threads=3&vnet=kaggle-t2-big/vnet-river",
                   help="Spezifikation der Suche (Lehrer)")
    p.add_argument("--student", default="nn?run=lynx-4@300", help="Schueler-Netz (bestimmt den Merkmalsraum)")
    p.add_argument("--opponents", default="nn?run=lynx-4@300,station,mensch-2,mensch-4",
                   help="Gegner-Spezifikationen, Komma-getrennt")
    p.add_argument("--stacks", default="25,50,100,200", help="Stacktiefen in BB, Komma-getrennt")
    p.add_argument("--hands", type=int, default=50, help="Kartenblaetter je Match (duplicate -> doppelt so viele Haende)")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--out", required=True, help="Zieldatei .npz (z. B. data\\teacher\\t1-seed1.npz)")
    p.set_defaults(fn=cmd_teacher)
    p = tr.add_parser("teacher-fit", help="Suche als Lehrer (H5): Schueler auf gesammelte Ziele nachtrainieren (mit KL-Leine)")
    p.add_argument("--data", required=True, help="Glob auf Lehrer-.npz, z. B. data\\teacher\\t1-*.npz")
    p.add_argument("--student", default="lynx-4@300", help="<Lauf>@<Checkpoint>")
    p.add_argument("--out-run", required=True, help="neuer Lauf unter data\\rl\\<out-run> (ckpt_000001.pt)")
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--batch", type=int, default=512)
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--kl", type=float, default=0.5, help="Gewicht der KL-Leine an den Anker (0 = aus)")
    p.set_defaults(fn=cmd_teacher)
    p = tr.add_parser("humanfold", help="Fold-Modell aus den kartenfreien HandHQ-Zeilen (H11 Schritt 2b)")
    p.add_argument("--rows", help="Ordner mit public-*.npz (Standard data\\humans\\actions)")
    p.add_argument("--out", default="human-fold-1", help="Name unter data\\humans\\<out>.npz")
    p.add_argument("--max-rows", type=int, default=4_000_000)
    p.add_argument("--max-shards", type=int, default=40, help="Speicher: Scherben begrenzen")
    p.add_argument("--epochs", type=int, default=3)
    p.set_defaults(fn=cmd_humanfold)
    p = tr.add_parser("rl", help="Lernender Bot, Schritt 2: Selbstspiel mit PPO (setzt einen Lauf fort)")
    p.add_argument("--run", help="Lauf fortsetzen bzw. benennen (data\\rl\\<run>)")
    p.add_argument("--teacher", help="neuer Lauf: zuerst diesen Bot nachahmen (empfohlen: rock)")
    p.add_argument("--bc-tournaments", type=int, default=600)
    p.add_argument("--iterations", type=int, default=100, help="Ziel-Iteration (Gesamtzahl, nicht zusaetzlich)")
    p.add_argument("--tournaments", type=int, default=96, help="Sit&Gos je Iteration")
    p.add_argument("--champion", default="rock")
    p.add_argument("--gate-schemes", type=int, default=120, help="0 = keine Aufnahmepruefung am Ende")
    p.add_argument("--name", help="Name in der Liga bei bestandener Pruefung")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--anchor-coef", type=float, default=0.0,
                   help="Leine: Strafe fuer Abweichung von der Ankerstrategie (z. B. 0.3); 0 = aus")
    p.add_argument("--anchor", help="Anker '<lauf>:<ckpt>', Standard: Checkpoint 0 dieses Laufs")
    p.add_argument("--random-share", type=float, default=0.0,
                   help="Anteil Tischplaetze mit Zufalls-Stilbots, z. B. 0.3 (immer neue Spielweisen)")
    p.add_argument("--exploit-every", type=int, default=0,
                   help="alle N Iterationen Ausbeuter trainieren und als Gegner aufnehmen (0 = aus)")
    p.add_argument("--exploit-iters", type=int, default=30, help="Trainingsiterationen je Ausbeuter")
    p.add_argument("--random-formats", action="store_true",
                   help="je Turnier zufaellig 2-10 Spieler, 20-200 BB, Blind-Tempo 5-20 Haende, Auszahlung")
    p.add_argument("--lr", type=float, default=3e-4, help="Lernrate (gilt auch beim Fortsetzen)")
    p.add_argument("--bench-every", type=int, default=50, help="alle N Iterationen auf den Pruefstand (0 = nie)")
    p.add_argument("--bench-sets", default="fest48,mix96,pluribus",
                   help="Testsets des Pruefstands, z. B. \"praezise,pluribus\"")
    p.add_argument("--bench-ref", help="Vergleichsbot (Name auf dem Pruefstand), bester Stand -> best.json")
    p.add_argument("--widen-from", help="neuer Lauf: Start von '<lauf>@<ckpt>', Netz aufgeweitet auf --features")
    p.add_argument("--features", default=None, help="mit --widen-from: Merkmalsversion, z. B. feat-3")
    p.add_argument("--actions", type=int, default=None, help="mit --widen-from: Aktionszahl (8 = act-2)")
    p.add_argument("--anchor-min-players", type=int, default=0, help="Leine erst ab so vielen Spielern")
    p.add_argument("--table-weights", help="mit --random-formats: Tischgroessen-Gewichte, z. B. \"2:4,3:3,6:2\"")
    p.add_argument("--human-share", type=float, default=0.0,
                   help="Anteil Tischplaetze mit Mensch-Bots (echte Spielertypen, train humans-fit)")
    p.add_argument("--self-play-seats", type=float, default=0.0,
                   help="je Gegnerplatz Wahrscheinlichkeit fuer eine fruehere eigene Version")
    p.add_argument("--icm", type=float, default=0.0,
                   help="Anteil ICM-Belohnung (Aenderung des Turnier-Eigenkapitals statt Chips), z. B. 1.0")
    p.set_defaults(fn=cmd_train_nn)

    a = ap.parse_args(argv)
    from .system import keep_awake
    with keep_awake(not a.allow_sleep):
        a.fn(a)


if __name__ == "__main__":
    main()

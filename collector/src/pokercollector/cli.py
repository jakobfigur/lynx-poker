"""Command line. Call: pokercollector <command> ... (or start.cmd on the stick)."""

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
    # src/pokercollector/cli.py -> collector/ -> project folder on the stick
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
        sys.exit(f"Session not found: {arg}")
    return cands[-1]


def _analyzer(profile: Profile):
    from .pipeline import make_analyzer
    return make_analyzer(profile, templates_dir())


def cmd_calibrate(a):
    profile = Profile.load(a.profile)
    img = cv2.imread(a.image)
    if img is None:
        sys.exit(f"Image not readable: {a.image}")
    an = _analyzer(profile)
    t = time.perf_counter()
    snap = an.analyze(img)
    ms = (time.perf_counter() - t) * 1000
    from .report import overlay
    out = Path(a.out or Path(a.image).with_suffix(".overlay.png"))
    cv2.imwrite(str(out), overlay(img, snap))
    for k, f in sorted(snap.fields.items()):
        flag = "" if f.confidence >= 0.6 else '  <-- uncertain'
        print(f"{k:24s} {json.dumps(f.value, ensure_ascii=False):42s} {f.confidence:.2f} {f.note}{flag}")
    for w in snap.warnings:
        print('WARNING:', w)
    print(f"\nAnalysis {ms:.0f} ms, scale {snap.get('table.scale')}, overlay: {out}")


def cmd_analyze(a):
    from .capture import ImageDirSource, SessionVideoSource, VideoFileSource
    from .pipeline import run_offline
    from .report import hands_markdown

    profile = Profile.load(a.profile)
    p = Path(a.input)
    if not p.exists() and (sessions_dir() / a.input).exists():
        p = sessions_dir() / a.input
    if p.is_dir() and (p / "session.json").exists():
        src = SessionVideoSource(p)            # Re-evaluate live session (all video segments)
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
            print(f"  t={fr.t_mono:7.1f}s  frames {stats.frames_analyzed}  events {stats.events}  hand {gh}",
                  flush=True)

    root = run_offline(src, sessions_dir(), profile, an, progress=progress)
    (root / "hands.md").write_text(hands_markdown(root), "utf-8")
    meta = json.loads((root / "session.json").read_text("utf-8"))
    print(f"\nSession: {root}\nStatistics: {meta['stats']}\nReport: {root / 'hands.md'}")


def cmd_windows(a):
    from .capture import list_windows
    for w in list_windows(a.filter or ""):
        print(f"{w.hwnd:>10}  {w.rect[2]}x{w.rect[3]}  {'(minimized) ' if w.minimized else ''}{w.title}")


def _pick_window(title: str | None, hwnd: int | None) -> int:
    from .capture import list_windows
    if hwnd:
        return hwnd
    wins = [w for w in list_windows(title or "") if not w.minimized and w.rect[2] > 200]
    if not wins:
        sys.exit(f"No visible window with '{title}' in title. 'pokercollector windows' shows all." )
    if len(wins) > 1:
        print('Multiple matching windows - please choose with --hwnd:')
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
    print(f"Window {hwnd}: {src.describe()['title']}")
    print('Status: waiting for table. Quit with Ctrl+C. Nothing will be clicked or typed.\n')

    def on_status(s, d):
        print(f"\r[{time.strftime('%H:%M:%S')}] {s:20s} {d[:90]:90s}", end="", flush=True)

    from .ai.agents import make_agent
    from .ai.live import LiveBot
    agent = make_agent(_agent_spec(a.agent), 0)
    if hasattr(agent, "greedy") and not a.mischen:
        agent.greedy = True        # Advisor: most likely action instead of sampling from the mixed strategy
    leiste = None

    def on_result(res):
        # End of turn detected on screen -> target board (data/ziele/pokerth.jsonl)
        note = 'automatically detected' + (', missed tournament start' if res["start_verpasst"] else "")
        msg = f"Tournament finished: Place {res['platz']} of {res['spieler']} after {res['haende']} hands"
        if a.kein_eintrag:
            print(f"\n{msg} (not recorded: --no-entry)")
        else:
            from .ai.ziele import add_tournament, pokerth_summary
            add_tournament(res["platz"], res["spieler"], a.agent, note, quelle="auto", haende=res["haende"],
                           spiel=res["spiel"], letzte_hand=res["letzte_hand"])
            s = pokerth_summary(a.agent)
            print(f"\n{msg} - recorded. So far {s['n']} tournament(s), ROI {s['roi']:+.1f}%, "
                  f"{s['wins']} win(s). Correction: pc.cmd bench tournament ...")
        if leiste:
            leiste.status("ok", msg)

    bot = LiveBot(agent, on_result=on_result)
    a.advice = a.advice or a.leiste
    if a.leiste:
        from .overlay import Leiste
        leiste = Leiste(sound=not a.still, title=f"Lynx ({a.agent})").start()
        print('Bar: normal, visible window. The collector cuts out its area from its images; it belongs next to the table, not on it.')

        def on_mask(rects):
            x, y, w, h = rects[0]
            print(f"\nNote: bar is located inside the PokerTH window ({w}x{h} px at {x},{y}) and is cut out there. "
                  "What lies underneath is not seen by the collector.")
        src.on_mask = on_mask
    shown = {"deciding": False}
    status_level = {"Aufnahme": "ok", 'Table recognized': "warn", 'Analysis delayed': "warn",
                    'Source lost': "err", 'waiting': "off"}

    def show(out):
        if out and a.advice:
            sug, obs, opps = out
            print(f"\n--- Your turn ({obs.street}) ---")
            _print_suggestion(agent, sug, obs, opps)
            if leiste:
                from .overlay import advice_from
                leiste.show(advice_from(sug, obs, agent))
                shown["deciding"] = True
        if leiste and shown["deciding"] and not bot.deciding:
            leiste.idle()
            shown["deciding"] = False

    def on_event(rec, stab):
        # Reconstruction + opponent model always run, even without --advice
        show(bot.on_event(rec, stab.state(), time.monotonic()))

    def on_status(s, d, _print_status=on_status):
        _print_status(s, d)
        if leiste:
            leiste.status(status_level.get(s, "warn"), s)
        if s == 'waiting' and d.startswith('Session ended'):
            bot.session_ended()                   # Report open tournament result, reconstruction fresh
            return
        show(bot.poll(time.monotonic()))          # per analyzed image: has the situation become stable?

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
    """League name (e.g., pros-r1) or bot specification."""
    lg = _league()
    return lg.players[spec].spec if spec in lg.players and lg.players[spec].spec else spec


def _print_suggestion(agent, sug, obs, opps):
    if sug is None:
        print('No recommendation: own cards not reliably recognized')
        return
    from .ai.opponents import describe
    print(f"Suggestion ({agent.name}): {sug}   [{' '.join(obs.hole_cards)} | {' '.join(obs.board) or '-'}"
          f" | Pot {obs.pot}, to call {obs.to_call}]")
    probs = getattr(agent, "last_probs", None)
    if probs is not None:
        from .ai.features import action_names
        print('  Probabilities: ' + ", ".join(f"{n} {p:.0%}" for n, p in zip(action_names(len(probs)), probs)
                                                    if p >= 0.01))
    adv = getattr(agent, "last_advice", None)
    for r in (adv.reasoning if adv else []):
        print('  -', r)
    for name, st in opps:
        print(f"  {name:16s} {describe(st)}")
    for u in obs.uncertain:
        print('  ! uncertain:', u)


def cmd_humans_fit(a):
    from .ai.humanbots import fit_all
    from .ai.nn_agent import rl_root
    src = rl_root().parent / "humans" / f"{a.source}.json"
    if not src.exists():
        sys.exit(f"{src} missing - first run 'pc.cmd data humans'")
    p = fit_all(src, a.name, a.generations, a.population, a.hands, progress=lambda m: print(m, flush=True))
    import json as _json
    for b in _json.loads(p.read_text("utf-8"))["bots"]:
        t, s = b["target"], b["stats_check"]
        print(f"{b['name']} {b['type']} ({b['share']:.0%}): distance {b['distance_check']:.4f}")
        print('   Human: ' + "  ".join(f"{k} {t[k]:.0%}" for k in t))
        print('   Bot:    ' + "  ".join(f"{k} {s.get(k, float('nan')):.0%}" for k in t))
        print(f"   {b['spec']}")
    print(f"-> {p}")


def cmd_leiste_demo(a):
    from .overlay import Advice, Leiste
    lz = Leiste(sound=not a.still, title='Lynx (Demo)').start()
    print('Bar bottom right (visible window; collector cuts out its area from its images live). Drag to move, right-click for sound/position.')
    lz.status("ok", "Aufnahme")
    demo = [("raise", 'RAISE to 360  (3.6 BB)', 'Ah Kd   Pot 120, to call 40   Pot 64%  Call 30%  Fold 6%'),
            ("call", 'CALL 120  (1.2 BB)', 'Qs Qd | 9h 7h 2c   Pot 480, to call 120   Call 71%  Raise 22%'),
            ("check", "CHECK", '8c 7c | Kd 9s 4h 2d   Pot 600   Check 88%  ⅓ Pot 12%'),
            ("fold", "FOLD", 'Td 4s   Pot 300, to call 200   Fold 93%'),
            ("allin", 'ALL-IN 1840  (18.4 BB)', 'As Ah   Pot 560, to call 300   All-in 80%  Call 20%')]
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
        print(f"\n--- Your turn (Hand {obs.hand_id}, {obs.street}, event {ev['seq']}) ---")
        if obs.history:
            print('  History: ' + " ".join(f"{x.seat}:{x.kind}{'' if x.amount_to is None else ' ' + str(x.amount_to)}"
                                         for x in obs.history if x.street == obs.street))
        _print_suggestion(agent, sug, obs, opps)
    print(f"\n{n} decisions in {root.name}")


def cmd_reconstruct(a):
    from .journal import build_index
    from .pipeline import write_hands
    from .report import hands_markdown

    root = _session_path(a.session)
    hands = write_hands(root)
    build_index(root)
    (root / "hands.md").write_text(hands_markdown(root), "utf-8")
    print(f"{len(hands)} hands reconstructed -> {root / 'hands.md'}")


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
    print(f"State: Cards {gs.hero_cards}, Board {gs.board}, Opponents {gs.opponents}, Pot {gs.pot}, "
          f"to call {gs.to_call}")
    print(f"Recommendation (Baseline): {adv.recommendation or 'none'}  Alternatives: {adv.alternatives}")
    for r in adv.reasoning:
        print('  -', r)
    print('Assumptions:')
    for r in adv.assumptions:
        print('  -', r)


def cmd_harvest_cards(a):
    """Saves rank/suit glyphs of recognized exposed cards as templates."""
    from .cards import TemplateStore

    profile = Profile.load(a.profile)
    store = TemplateStore(templates_dir())
    an = _analyzer(profile)
    for path in a.images:
        img = cv2.imread(path)
        if img is None:
            print('unreadable:', path)
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
            ans = input(f"{Path(path).name} {where}: recognized {guess} (image: {crop_path}). "
                        f"Correct? [Enter=yes / card e.g. Td / s=skip] ").strip()
            if ans.lower() == "s":
                continue
            label = ans if ans else guess
            if len(label) != 2 or label == "??":
                print('  skipped (no valid label)')
                continue
            name = f"{int(time.time() * 1000)}"
            store.add("rank", label[0].upper(), cr.rank_glyph, name)
            store.add("suit", label[1].lower(), cr.suit_glyph, name)
            print(f"  saved as {label[0].upper()}{label[1].lower()}")


def cmd_sim_agents(a):
    from .ai.agents import REGISTRY, STYLES
    for k in sorted(REGISTRY):
        st = STYLES.get(k)
        extra = f"  (plays ~{st.vpip:.0%} of starting hands, opens ~{st.pfr:.0%}, Bluff {st.bluff:.0%})" if st else ""
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
            print(f"\r  Hand {k}/{total}  Hands played {played}  {played / el:.0f}/s", end="", flush=True)

    res = run_match(agents, a.hands, seed=a.seed, small_blind=a.sb, big_blind=a.bb, stack_bb=a.stack,
                    duplicate=not a.no_duplicate, progress=progress, keep_records=a.show)
    print('\n')
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
    print(f"\nSaved: {out / f'match_{stamp}.md'}")


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
        sys.exit(f"Payouts must total 100%, not {sum(payouts):.0%}")
    cfg = TournamentConfig(start_stack=a.stack, blinds=BlindSchedule(sb, bb, a.level_hands), payouts=payouts)
    last = [0.0]

    def progress(k, total, played, el):
        if time.time() - last[0] > 2 or k == total:
            last[0] = time.time()
            print(f"\r  Scheme {k}/{total}  Tournaments played {played}  {el:.0f}s", end="", flush=True)

    res = run_tournaments(agents, a.tournaments, cfg, seed=a.seed, duplicate=not a.no_duplicate,
                          progress=progress, keep_example=True)
    print('\n')
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
    print(f"\nSaved: {out / f'tournament_{stamp}.md'}")


def cmd_sim_pushfold(a):
    from .ai.pushfold import grid_text, nash_table
    t = nash_table()
    if a.overview:
        print('Push range in % (first player) per stack and players behind:')
        print('BB    ' + " ".join(f"{k:>5d}" for k in range(1, t["max_behind"] + 1)))
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
              f"{' '.join(r.get('board') or []):15s} played: {r['actual']:12s} {mark} {a.agent}: {r['suggested']}"
              + (f"   [uncertain: {'; '.join(r['uncertain'])}]" if r["uncertain"] else ""))
    print(f"\n{len(rows)} decisions, {same} same as {a.agent}.")


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
        sys.exit(f"Your name '{a.name}' conflicts with an opponent")
    lg = _league()
    bots = []
    for i, nm in enumerate(names):
        if nm in lg.players and lg.players[nm].kind == "bot":
            bots.append(lg.agent(nm, i + 1))
        else:
            from .ai.agents import make_agent
            bots.append(make_agent(nm if ":" in nm else f"{nm}:{nm}", i + 1))
    if len({b.name for b in bots}) != len(bots):
        sys.exit('Opponent names must be unique, e.g. tag,tag:tag2')
    human = HumanAgent(a.name, ascii_only=a.ascii, coach=a.coach)
    out = data_dir() / "play"
    sb, bb = (int(x) for x in a.blinds.split("/"))
    if a.mode == "cash":
        path = play_cash(human, bots, out, hands=a.hands, stack_bb=a.stack_bb, blinds=(sb, bb), seed=a.seed)
        print(f"\nSaved: {path}\nEvaluation: pc.cmd play-stats")
        return
    payouts = tuple(float(x) / 100 for x in a.payouts.split(","))
    cfg = TournamentConfig(start_stack=a.stack, blinds=BlindSchedule(sb, bb, a.level_hands), payouts=payouts)
    path, res = play_tournament_session(human, bots, out, cfg, seed=a.seed)
    print(f"\nSaved: {path}")
    if res is not None and not a.unrated:
        if a.name not in lg.players:
            lg.add(a.name, None, kind="human", note="Mensch")
        unknown = [b.name for b in bots if b.name not in lg.players]
        if unknown:
            print(f"Not accounted for: {', '.join(unknown)} are not league players ('pc.cmd league add ...').")
            return
        before = lg.players[a.name].rating
        lg.record_game([a.name] + [b.name for b in bots], list(res.places), list(res.payouts), "human_sng",
                       {"seed": res.seed})
        p = lg.players[a.name]
        print(f"Your rating: {before:.0f} -> {p.rating:.0f} (± {p.rating_sd:.0f}), "
              f"conservative {p.conservative:.0f}, {p.games} rated tournaments")


def cmd_play_stats(a):
    from .ai.play import load_sessions, stats_markdown
    print(stats_markdown(load_sessions(data_dir() / "play"), a.name))


def cmd_league(a):
    lg = _league()
    if a.leaguecmd == "add":
        p = lg.add(a.name, a.spec, note=a.note or "")
        print(f"New to the league: {p.name} = {p.spec}")
    elif a.leaguecmd == "retire":
        lg.players[a.name].active = False
        lg.save()
        print(f"{a.name} no longer participates in automatic rounds (rating remains).")
    elif a.leaguecmd == "run":
        from .ai.league import display
        from .ai.tournament import BlindSchedule, TournamentConfig
        cfg = TournamentConfig(start_stack=a.stack, blinds=BlindSchedule(10, 20, a.level_hands))

        def progress(k, n, g):
            order = [nm for _, nm in sorted(zip(g["ranks"], g["participants"]))]
            print(f"  Game {k}/{n}: {' > '.join(order)}", flush=True)

        lg.run(a.rounds, a.table, cfg, seed=a.seed, progress=progress)
        print()
        print(lg.leaderboard_markdown())
    elif a.leaguecmd == "bench":
        targets = [a.name] if a.name else [p.name for p in lg.players.values() if p.kind == "bot" and p.active]
        for nm in targets:
            r = lg.benchmark(nm, hands=a.hands, tournaments=a.tournaments)
            print(f"{nm:14s} Cash {r['cash']['bb_per_100']:+7.1f} bb/100 {r['cash']['ci95']}   "
                  f"SNG ROI {r['sng']['roi_pct']:+6.1f} % {r['sng']['ci95']}   "
                  f"Push/Fold loss {r['pushfold']['pf_ev_loss_per_spot_bb']} BB/spot", flush=True)
    else:  # show
        md = lg.leaderboard_markdown()
        (lg.root / "report.md").write_text(md, "utf-8")
        (lg.root / "report.html").write_text(lg.report_html(), "utf-8")
        print(md)
        print(f"\nProgress as graphic: {lg.root / 'report.html'}")


def _league_pool(lg, exclude=(), self_play: float = 0.2):
    from .ai.optimize import LeaguePool
    players = [(p.name, p.spec, p.mu) for p in lg.players.values()
               if p.kind == "bot" and p.active and p.spec and p.name not in exclude]
    return LeaguePool(players, self_play=self_play)


def _pool_text(pool) -> str:
    from .ai.optimize import LeaguePool
    if not isinstance(pool, LeaguePool):
        return 'fixed ' + "/".join(pool)
    shares = sorted(pool.shares().items(), key=lambda kv: -kv[1])
    extra = f"; Random-style bots {pool.random_share:.0%} of seats" if pool.random_share else ""
    return 'League (' + ", ".join(f"{n} {v:.0%}" for n, v in shares) + f"; Self-Play {pool.self_play:.0%}{extra})"


def cmd_data(a):
    from .ai.phh import agreement, build_dataset, load_dataset, save_dataset
    if a.datacmd == "humans":
        from .ai import humans
        root = humans.handhq_dir()
        dirs = [root / d for d in a.sets.split(",")] if a.sets else sorted(p for p in root.iterdir() if p.is_dir())
        missing = [d for d in dirs if not d.exists()]
        if missing:
            sys.exit('Not present: ' + ", ".join(d.name for d in missing))
        print(f"HandHQ: {', '.join(d.name for d in dirs)}", flush=True)
        hs = humans.collect(dirs, max_files=a.max_files, workers=a.workers, progress=lambda i, n, h: print(
            f"  {i}/{n} files, {h.used} hands, {len(h.c)} players", flush=True))
        types = humans.player_types(hs.stats(), k=a.types, min_hands=a.min_hands)
        p = humans.save(a.name, hs, types)
        print(f"{hs.used} hands ({hs.skipped} skipped), {len(hs.c)} players -> {p}")
        print(f"Player types (players with >= {a.min_hands} hands, share by hands):")
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
        print(f"HandHQ showdown decisions: {len(files)} files, {a.workers} processes -> {out}", flush=True)
        rep = humandata.extract(files, out, workers=a.workers, files_per_shard=a.files_per_shard,
                                progress=lambda k, n, t, s: print(
                                    f"  Shard {k + 1}/{n}: {t['hands']} hands, {t['with_cards']} with cards, "
                                    f"{t['ok']} replayed, {t['decisions']} decisions, {s:.0f}s", flush=True))
        print(json.dumps({k: v for k, v in rep.items() if k != "problems"}, ensure_ascii=False))
        print('Issues:', rep["problems"])
        return
    if a.datacmd == "humanpublic":
        from .ai import humandata, humans
        root = humans.handhq_dir()
        dirs = [root / d for d in a.sets.split(",")] if a.sets else sorted(p for p in root.iterdir() if p.is_dir())
        files = [f for d in dirs for f in sorted(d.rglob("*.phhs"))]
        if a.max_files:
            files = files[:a.max_files]
        out = Path(a.out) if a.out else data_dir() / "humans" / "actions"
        print(f"HandHQ all decisions (cardless, with folds): {len(files)} files, {a.workers} processes -> {out}", flush=True)
        rep = humandata.extract_public(files, out, workers=a.workers, files_per_shard=a.files_per_shard,
                                       progress=lambda k, n, t, s: print(
                                           f"  Shard {k + 1}/{n}: {t['hands']} hands, {t['ok']} replayed, "
                                           f"{t['decisions']} decisions, {s:.0f}s", flush=True))
        print(json.dumps({k: v for k, v in rep.items() if k != "problems"}, ensure_ascii=False))
        print('Issues:', rep["problems"])
        return
    if a.datacmd == "pluribus":
        src = Path(a.source) if a.source else data_dir() / "external" / "phh-dataset" / "data" / "pluribus"
        files = sorted(src.rglob("*.phh"))
        if not files:
            sys.exit(f"No .phh files in {src}. Get with:\n  git clone --depth 1 --filter=blob:none --sparse "
                     "https://github.com/uoftcprg/phh-dataset.git\n  git -c safe.directory=* sparse-checkout set data/pluribus")
        print(f"{len(files)} hands from {src} will be replayed in our engine ...", flush=True)
        data, rep = build_dataset(files, progress=lambda k, n: print(f"  {k}/{n}", flush=True))
        path = save_dataset("pluribus", data, rep)
        print(f"  {rep['ok']}/{rep['hands']} hands match the engine, {rep['decisions']} decisions")
        for p, k in sorted(rep["by_player"].items(), key=lambda kv: -kv[1]):
            print(f"    {p:10s} {k:6d}")
        for ex in rep["examples"]:
            print(f"  Problem: {ex}")
        print(f"Saved: {path}")
        return
    if a.datacmd == "agree":
        from .ai.nn_agent import load_weights
        for ck in a.ckpt.split(","):
            w = load_weights(a.run, ck)
            data = load_dataset(a.dataset, a.players.split(",") if a.players else None, version=w["features"])
            r = agreement(w, data)
            print(f"{a.run} ckpt {ck:>6s}: matches {r['top1']:.1%} of decisions from "
                  f"{a.players or 'all'} (mean probability {r['prob']:.1%})  {r['per_action']}")


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
            print(f"  {sm['hands']:6d} hands  raw {r['bb100']:+7.1f} bb/100 [{r['ci95'][0]:+.0f}; {r['ci95'][1]:+.0f}]"
                  f"  All-in EV {e['bb100']:+7.1f} [{e['ci95'][0]:+.0f}; {e['ci95'][1]:+.0f}]"
                  f"  adjusted {b['bb100']:+7.1f} [{b['ci95'][0]:+.0f}; {b['ci95'][1]:+.0f}]"
                  f" (Card luck {b.get('luck_bb100', float('nan')):+.0f})"
                  + (f"  ({sm['engine_mismatch']} engine deviations!)" if sm["engine_mismatch"] else ""), flush=True)

        if a.hands > 0:
            print(f"Slumbot: {name} = {spec}, {a.hands} hands, {a.workers} parallel sessions", flush=True)
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
            print(f"  {sm['hands']:6d} hands  raw {r['bb100']:+7.1f} bb/100 [{r['ci95'][0]:+.0f}; {r['ci95'][1]:+.0f}]"
                  f"  AIVAT {v['bb100']:+7.1f} [{v['ci95'][0]:+.0f}; {v['ci95'][1]:+.0f}]"
                  f"  All-in EV {e['bb100']:+7.1f}"
                  + (f"  ({sm['engine_mismatch']} engine deviations!)" if sm["engine_mismatch"] else ""), flush=True)

        if a.hands > 0:
            print(f"GTO Wizard AI: {name} = {spec}, {a.hands} hands, {a.workers} parallel hands", flush=True)
            gtow.run(spec, name, a.hands, workers=a.workers, key=a.key, progress=show)
        show(0, gtow.summarize(gtow.load_hands(name)))
        if a.server:
            print('Server: ' + json.dumps(gtow.server_results(gtow.api_key(a.key)), ensure_ascii=False))
        return
    if a.benchcmd == "turnier":
        from .ai.ziele import add_tournament, pokerth_summary, remove_last_tournament
        if a.ersetzt:
            alt = remove_last_tournament(a.bot)
            print('Replaced: ' + (json.dumps(alt, ensure_ascii=False) if alt else 'no entry available'))
        rec = add_tournament(a.platz, a.spieler, a.bot, a.notiz or "")
        s = pokerth_summary(a.bot)
        print(f"Registered: Rank {rec['platz']} of {rec['spieler']} ({rec['bot']}). So far {s['n']} tournaments, "
              f"ROI {s['roi']:+.1f} %, wins {s['wins']} ({s['win_rate']:.0%})")
        return
    if a.benchcmd == "ziele":
        from .ai.ziele import MEASURE_SETS, scoreboard, scoreboard_text
        lg = _league()
        spec = lg.players[a.bot].spec if a.bot in lg.players and lg.players[a.bot].spec else a.bot
        name = a.name or a.bot
        if a.messen or a.exploit:
            print(f"Measuring {name} = {spec}: {', '.join(MEASURE_SETS)}{' + exploiter' if a.exploit else ''} ...",
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
        print(f"{a.a} minus {a.b} (paired, same cards and tables):")
        for s, ra, rb, d in res:
            sig = "  *" if d["ci95"][0] > 0 or d["ci95"][1] < 0 else ""
            print(f"  {s:11s} {ra['roi']:+6.1f} % vs {rb['roi']:+6.1f} %   Difference {d['roi']:+5.1f} "
                  f"[{d['ci95'][0]:+.1f}; {d['ci95'][1]:+.1f}]  n={d['n']}{sig}")
        if not res:
            print('  no common test sets')
        return
    from .ai.bench import FORMAT_SETS, PRECISE_SETS
    groups = {"formate": FORMAT_SETS, "praezise": PRECISE_SETS}
    sets = tuple(x for part in a.sets.split(",") for x in groups.get(part, [part]))
    lg = _league()
    a.name = a.name or a.spec
    if a.spec in lg.players and lg.players[a.spec].spec:      # League name instead of specification (without '&')
        a.spec = lg.players[a.spec].spec
    print(f"Test bench for {a.name} = {a.spec}: {', '.join(sets)}{' + exploiter test' if a.exploit else ''}",
          flush=True)

    def progress(s, r):
        if "roi" in r:
            print(f"  {s:8s} ROI {r['roi']:+.1f} % [{r['ci95'][0]:+.1f}; {r['ci95'][1]:+.1f}]", flush=True)
        elif "bb_per_100" in r:
            print(f"  {s:8s} {r['bb_per_100']:+.1f} bb/100 {r['ci95']}", flush=True)
        elif "top1" in r:
            print(f"  {s:8s} hits {r['top1']:.1%} of the Pluribus decisions", flush=True)
        elif "exploiter_roi" in r:
            print(f"  {s:8s} Exploiter {r['exploiter_roi']:+.1f} % {r['ci95']}", flush=True)

    run_bench(a.spec, a.name, sets=sets, exploit=a.exploit, progress=progress)
    print(write_report())


def cmd_cfr(a):
    from .ai.bench import run_bench
    from .ai.cfr import train_cfr
    from .ai.nn_agent import rl_root
    run_dir = rl_root() / a.run
    print(f"CFR run {run_dir}: up to round {a.rounds}, {a.traversals} traversals per process per round, "
          f"benchmark every {a.bench_every} rounds", flush=True)

    def progress(e):
        if e["round"] % 5 == 0:
            print(f"  Round {e['round']:4d}: {e['infosets']:7d} infosets, {e['traversals_per_s']:6.0f} traversals/s, "
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
        print(f"  Benchmark round {done}: mix96 {b['mix96']['roi']:+.1f} %, fest48 {b['fest48']['roi']:+.1f} %",
              flush=True)


def cmd_deepcfr(a):
    from .ai.bench import run_bench
    from .ai.deepcfr import DeepCFRConfig, train_deepcfr
    from .ai.nn_agent import rl_root
    run_dir = rl_root() / a.run
    cfg = DeepCFRConfig(traversals=a.traversals, snapshot_every=a.snapshot_every, seed=a.seed,
                        adv_capacity=a.buffer, strat_capacity=a.buffer)
    print(f"Deep-CFR run {run_dir}: up to iteration {a.iterations}, {a.traversals} traversals per process, "
          f"strategy net + benchmark every {a.snapshot_every} iterations", flush=True)

    def progress(e):
        print(f"  Iteration {e['iteration']:4d}: {e['adv_samples']:8d} regret data (seen {e['adv_seen']}), "
              f"loss {e['adv_loss']:.4f}, playing {e['rollout_s']:.0f}s, net {e['train_s']:.0f}s", flush=True)

    def snapshot(t, e, ex):
        b = run_bench(f"nn?run={a.run}@{t}", f"{a.run}@{t}", sets=("fest48", "mix96", "pluribus"), ex=ex)
        plu = f", like Pluribus {b['pluribus']['top1']:.0%}" if "pluribus" in b else ""
        print(f"  Benchmark Iteration {t}: mix96 {b['mix96']['roi']:+.1f} %, fest48 {b['fest48']['roi']:+.1f} %{plu}",
              flush=True)

    train_deepcfr(run_dir, a.iterations, cfg, progress=progress, on_snapshot=snapshot)


def cmd_exploit(a):
    from .ai.nn_agent import checkpoint_path
    from .ai.rl import exploit_test
    run, _, ck = a.init.partition("@")
    init = checkpoint_path(run, ck or 0)
    print(f"Exploiter test for {a.target}: start {init.parent.name}@{ck or 0}, {a.iterations} iterations "
          f"against 5 copies, then {a.schemes} fresh card schemes", flush=True)

    def progress(e):
        if e["iteration"] % 10 == 0:
            print(f"  It {e['iteration']:4d}: {e['bb_per_hand']:+.3f} BB/hand ({e['elapsed_s']:.0f}s)", flush=True)

    r = exploit_test(a.target, init, iterations=a.iterations, schemes=a.schemes, progress=progress)
    print(f"  Exploiter ROI {r['exploiter_roi']:+.1f} % (95 %: {r['ci95'][0]:+.1f} .. {r['ci95'][1]:+.1f}), "
          f"untrained baseline {r['start_roi']:+.1f} %  -> the higher, the more exploitable {a.target} is")


def cmd_train_nn(a):
    from .ai.nn_agent import rl_root
    from .ai.optimize import gate
    from .ai.rl import RLConfig, behavior_clone, new_run_dir, snapshot_spec, train_ppo
    lg = _league()
    run_dir = rl_root() / a.run if a.run else new_run_dir()
    print(f"Run: {run_dir}", flush=True)
    log = lambda msg: print(msg, flush=True)
    if a.traincmd == "bc" and a.dataset:
        from .ai.phh import load_dataset
        from .ai.rl import fit_bc
        players = a.players.split(",") if a.players else None
        from .ai.features import FEATURES_VERSION
        data = load_dataset(a.dataset, players, version=a.features or FEATURES_VERSION)
        print(f"Imitation from dataset '{a.dataset}' ({a.players or 'all players'}): {len(data['a'])} decisions",
              flush=True)
        meta = fit_bc(run_dir, data, {"dataset": a.dataset, "players": players}, epochs=a.epochs, progress=log)
        print(f"  Hit rate {meta['holdout_accuracy']:.1%} -> {run_dir / 'ckpt_000000.pt'}")
        return
    if a.traincmd == "bc" or (a.teacher and not (run_dir / "ckpt_000000.pt").exists()):
        print(f"Imitation of '{a.teacher or 'rock'}' ...", flush=True)
        meta = behavior_clone(run_dir, teacher=a.teacher or "rock", tournaments=a.bc_tournaments, progress=log)
        print(f"  {meta['decisions']} decisions, hit rate {meta['holdout_accuracy']:.1%} "
              f"({meta['elapsed_s']:.0f}s) -> {run_dir / 'ckpt_000000.pt'}")
        if a.traincmd == "bc":
            print(f"Add to league: pc.cmd league add nn-bc \"{snapshot_spec(run_dir.name, 0)}\"")
            return
    if getattr(a, "widen_from", None) and not (run_dir / "ckpt_000000.pt").exists():
        from .ai.nn_agent import checkpoint_path, load_checkpoint, net_from_checkpoint, save_checkpoint, widen_net
        src_run, _, src_ck = a.widen_from.partition("@")
        src = net_from_checkpoint(load_checkpoint(checkpoint_path(src_run, src_ck or "latest")))
        net = widen_net(src, a.features or src.features_version, a.actions)
        save_checkpoint(run_dir / "ckpt_000000.pt", net, {"phase": "widen", "from": a.widen_from,
                                                          "features": net.features_version})
        print(f"Start: {a.widen_from} expanded {src.features_version} -> {net.features_version}, "
              f"{src.pi.out_features} -> {net.pi.out_features} actions", flush=True)
    if a.champion not in lg.players or lg.players[a.champion].spec is None:
        sys.exit(f"Titleholder '{a.champion}' is not a bot in the league")
    cfg = RLConfig(tournaments=a.tournaments, seed=a.seed, anchor_coef=a.anchor_coef, anchor=a.anchor or "",
                   random_share=a.random_share, exploit_every=a.exploit_every, exploit_iters=a.exploit_iters,
                   random_formats=a.random_formats, lr=a.lr, bench_every=a.bench_every,
                   bench_sets=a.bench_sets, bench_ref=a.bench_ref or "", anchor_min_players=a.anchor_min_players,
                   table_weights=a.table_weights or "", self_play_seats=a.self_play_seats,
                   human_share=a.human_share, icm=a.icm)
    pool = _league_pool(lg, self_play=cfg.self_play)
    pool.random_share = cfg.random_share
    print(f"PPO: up to iteration {a.iterations}, {cfg.tournaments} Sit&Go per iteration\n"
          f"Opponents: {_pool_text(pool)}, self-play = an earlier version at the table", flush=True)

    def progress(e):
        ev = f"  ROI vs fixed Pool {e['eval_roi']:+.1f} %" if "eval_roi" in e else ""
        if "pluribus_top1" in e:
            ev += f", like Pluribus {e['pluribus_top1']:.0%}"
        print(f"  Iteration {e['iteration']:4d}: {e['decisions']:6d} decisions, {e['bb_per_hand']:+.3f} BB/hand, "
              f"entropy {e.get('entropy', 0):.2f}, KL {e.get('approx_kl', 0):+.4f} "
              f"({e['rollout_s']:.0f}s playing, {e['elapsed_s']:.0f}s total){ev}", flush=True)

    res = train_ppo(run_dir, a.iterations, pool, cfg, progress=progress)
    cand = snapshot_spec(run_dir.name, res["snapshots"][-1])
    if not a.gate_schemes:
        print(f"Done. Candidate: {cand}")
        return
    champ_spec = lg.players[a.champion].spec
    gate_pool = _league_pool(lg, exclude={a.champion}, self_play=0.0)
    print(f"\nQualification test {cand} vs '{a.champion}' on {a.gate_schemes} fresh card schemes ...",
          flush=True)
    g = gate(cand, champ_spec, schemes=a.gate_schemes, pool=gate_pool, seed=200_000 + a.seed * 1000 + res["iterations"])
    (run_dir / f"gate_{res['iterations']:06d}.json").write_text(json.dumps(g, indent=2), "utf-8")
    print(f"  Candidate ROI {g['candidate_roi']:+.1f} %, {a.champion} ROI {g['champion_roi']:+.1f} %, "
          f"difference {g['diff_roi']:+.1f} % (95 %: {g['ci95'][0]:+.1f} .. {g['ci95'][1]:+.1f})")
    if g["passed"]:
        name = a.name or f"nn-{time.strftime('%m%d-%H%M')}"
        lg.add(name, cand, note=f"PPO {run_dir.name} It {res['iterations']}, Gate vs {a.champion} "
                                f"{g['diff_roi']:+.1f} % {g['ci95']}")
        print(f"  PASSED -> registered in the league as '{name}'.")
    else:
        print("  Failed - nothing registered. Continue training: "
              f"pc.cmd train rl --run {run_dir.name} --iterations {res['iterations'] * 2}")


def cmd_valuedata(a):
    from .ai.valuedata import data_dir, generate
    out = Path(a.out) if a.out else data_dir() / f"{a.street}-{a.seed:08d}.npz"
    print(f"Value net data {a.street}: {a.n} situations from seed {a.seed}, {a.workers} processes -> {out}", flush=True)

    def progress(k, n, secs):
        print(f"  {k}/{n} solved, {secs:.0f}s, {secs / k:.2f}s per situation", flush=True)
    m = generate(a.street, a.n, out, seed=a.seed, iters=a.iters, workers=a.workers, threads=a.threads,
                 progress=progress, vnet=a.vnet)
    print(json.dumps({k: m[k] for k in ("n", "errors", "iters", "secs_per_sample", "nodes_mean", "elapsed_s", "path")},
                     ensure_ascii=False))


def cmd_teacher(a):
    from .ai import teacher
    if a.traincmd == "teacher-collect":
        opps = [o for o in a.opponents.split(",") if o]
        stacks = [int(s) for s in a.stacks.split(",") if s]
        print(f"Teacher {a.search}\nStudent {a.student}\nOpponents {opps}, stacks {stacks} BB, {a.hands} boards per match -> {a.out}", flush=True)
        meta = teacher.collect(a.search, a.student, opps, a.hands, stacks, a.out, seed=a.seed,
                               progress=lambda k, n, m, rows, s: print(
                                   f"  Match {k}/{n}: {m['opp']} {m['stack_bb']} BB: {m['bb100']:+.1f} bb/100, "
                                   f"{m['rows']} rows ({rows} total), {s:.0f}s", flush=True))
        print(json.dumps({k: v for k, v in meta.items() if k != "matches"}, ensure_ascii=False))
        return
    import glob
    paths = sorted(glob.glob(a.data))
    if not paths:
        sys.exit(f"No teacher data for {a.data}")
    run, _, ck = a.student.partition("@")
    res = teacher.fit(run, ck or "latest", paths, a.out_run, epochs=a.epochs, batch=a.batch, lr=a.lr, kl_coef=a.kl,
                      log=lambda m: print("  " + m, flush=True))
    print(f"-> {res['out']} ({res['n']} rows)")


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
        sys.exit(f"No shards for {a.data}")
    out = Path(a.out) if a.out.endswith(".pt") or "\\" in a.out or "/" in a.out else data_dir() / f"{a.out}.pt"
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"Value net: {len(paths)} shards -> {out}", flush=True)
    res = train(paths, out, a.epochs, a.batch, a.lr, a.width, a.depth, resume=a.resume,
                log=lambda m: print("  " + m, flush=True))
    print(json.dumps({k: v for k, v in res.items() if k != "hist"}, ensure_ascii=False))


def cmd_train(a):
    from .ai.optimize import DEFAULT_POOL, gate, run_cem
    lg = _league()
    out = data_dir() / "train" / time.strftime("%Y%m%d-%H%M%S")
    champ_name = a.champion
    if champ_name not in lg.players or lg.players[champ_name].spec is None:
        sys.exit(f"Titleholder '{champ_name}' is not a bot in the league")
    champ_spec = lg.players[champ_name].spec
    league = a.opponents == "league"
    # Qualification test without the titleholder as opponent (otherwise they would be playing against themselves)
    gate_pool = _league_pool(lg, exclude={champ_name}, self_play=0.0) if league else DEFAULT_POOL
    if a.traincmd == "gate":
        cand = a.candidate
        if a.from_dir:
            cand = json.loads((Path(a.from_dir) / "result.json").read_text("utf-8"))["center"]["spec"]
        if not cand:
            sys.exit('Specify candidate or --from <training folder>')
        print(f"Candidate: {cand}\nTitleholder: {champ_name} = {champ_spec}\n"
              f"Opponents: {_pool_text(gate_pool)}", flush=True)
        r = gate(cand, champ_spec, schemes=a.schemes, seed=a.seed, pool=gate_pool)
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return
    pool = _league_pool(lg) if league else DEFAULT_POOL
    print(f"Training (CEM): start {a.start}, {a.generations} generations x {a.population} candidates, "
          f"{a.schemes} card schemes per generation\nOpponents: {_pool_text(pool)}")

    def progress(e):
        print(f"  Gen {e['generation']:2d}: best ROI {e['best_roi']:+6.1f} %, mean {e['mean_roi']:+6.1f} %, "
              f"center {e['center_roi']:+6.1f} %, spread {e['std_mean']:.3f}  ({e['elapsed_s']:.0f}s)", flush=True)

    if a.resume:
        out = Path(a.resume)
        print(f"Continuing training from {out}")
    res = run_cem(a.generations, a.population, a.schemes, start=a.start, seed=a.seed, out_dir=out,
                  progress=progress, resume=bool(a.resume), pool=pool)
    (out / "result.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), "utf-8")
    cand = res["center"]["spec"]
    print(f"\nCandidate (distribution center): {cand}")
    print(f"Qualification test against '{champ_name}' on {a.gate_schemes} fresh card schemes ...", flush=True)
    print(f"  Opponents: {_pool_text(gate_pool)}", flush=True)
    # own test set per training seed: the same set over many runs would itself become a selection criterion and thus "worn out"
    # themselves as a selection criterion and thus "worn out"
    g = gate(cand, champ_spec, schemes=a.gate_schemes, pool=gate_pool, seed=100_000 + a.seed)
    (out / "gate.json").write_text(json.dumps(g, indent=2), "utf-8")
    print(f"  Candidate ROI {g['candidate_roi']:+.1f} %, {champ_name} ROI {g['champion_roi']:+.1f} %, "
          f"difference {g['diff_roi']:+.1f} % (95 %: {g['ci95'][0]:+.1f} .. {g['ci95'][1]:+.1f})")
    if g["passed"]:
        name = a.name or f"opt-{time.strftime('%m%d-%H%M')}"
        lg.add(name, cand, note=f"CEM from {a.start} against {'League' if league else 'fixed pool'}, "
                                f"Gate vs {champ_name} {g['diff_roi']:+.1f} % {g['ci95']}")
        print(f"  PASSED -> registered in the league as '{name}'. Continue with: pc.cmd league run --rounds 30")
    else:
        print('  Failed - lead not reliable. Nothing registered.')
    print(f"Log: {out}")


def cmd_verify(a):
    from .journal import verify_manifest
    probs = verify_manifest(_session_path(a.session))
    print('OK - all files unchanged' if not probs else "\n".join(probs))
    sys.exit(1 if probs else 0)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pokercollector", description='Visual capture of PokerTH games')
    ap.add_argument("--profile", help='Path to a table profile (JSON); default: built-in PokerTH web profile')
    ap.add_argument("--allow-sleep", action="store_true",
                    help='Allow standby during the run (default: keep awake so long runs do not abort)')
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("calibrate", help='Analyze screenshot, generate overlay image')
    p.add_argument("image")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_calibrate)

    p = sub.add_parser("analyze", help='Evaluate video or screenshot folder (new session)')
    p.add_argument("input")
    p.add_argument("--step", type=float, default=0.2, help='Seconds between analyzed video frames')
    p.add_argument("--interval", type=float, default=1.0, help='Assumed interval between screenshots')
    p.set_defaults(fn=cmd_analyze)

    p = sub.add_parser("windows", help='List windows')
    p.add_argument("filter", nargs="?")
    p.set_defaults(fn=cmd_windows)

    p = sub.add_parser("live", help='Capture windows live, automatically start/stop sessions')
    p.add_argument("--window", default="PokerTH", help='Part of the window title')
    p.add_argument("--hwnd", type=int)
    p.add_argument("--fps", type=float, default=8.0)
    p.add_argument("--segment", type=float, default=120.0, help='Segment length in seconds')
    p.add_argument("--stop-after", type=float, default=20.0, help='Session ends after this many seconds without table')
    p.add_argument("--max-seconds", type=float)
    p.add_argument("--no-video", action="store_true", help='journal only, no video recording')
    p.add_argument("--allow-background", action="store_true",
                   help='also record when the window is not in the foreground (risk: obscured content)')
    p.add_argument("--advice", action="store_true", help='show suggestion when it’s your turn')
    p.add_argument("--leiste", action="store_true",
                   help='additionally show suggestion in the Lynx bar above the taskbar (with sound; sets --advice)')
    p.add_argument("--still", action="store_true", help='bar without sound')
    p.add_argument("--kein-eintrag", action="store_true",
                   help='do not automatically enter recognized end of turn into target board')
    p.add_argument("--mischen", action="store_true",
                   help='draw suggestion from mixed strategy instead of the most likely action')
    p.add_argument("--agent", default="lynx-4-300",
                   help='league name or agent for suggestions (default lynx-4-300 = best bot)')
    p.set_defaults(fn=cmd_live)

    p = sub.add_parser("live-replay", help='play back recorded session like live: suggestions + opponent model')
    p.add_argument("session", help="folder, part of name or 'last'")
    p.add_argument("--agent", default="lynx-4-300", help='league name or agent')
    p.set_defaults(fn=cmd_live_replay)
    p = sub.add_parser("leiste-demo", help='demonstrate Lynx bar without table (colors, sounds, position)')
    p.add_argument("--still", action="store_true", help='without sound')
    p.add_argument("--sekunden", type=float, default=3.0, help='display duration per example')
    p.set_defaults(fn=cmd_leiste_demo)

    p = sub.add_parser("reconstruct", help='reconstruct hands of a session')
    p.add_argument("session", help="folder, part of name or 'last'")
    p.set_defaults(fn=cmd_reconstruct)

    p = sub.add_parser("report", help='output hand report of a session')
    p.add_argument("session")
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("inspect-reference", help='show schema of a PokerTH log file')
    p.add_argument("file")
    p.set_defaults(fn=cmd_inspect_reference)

    p = sub.add_parser("compare", help='compare session with PokerTH export')
    p.add_argument("session")
    p.add_argument("reference")
    p.set_defaults(fn=cmd_compare)

    p = sub.add_parser("advise", help='baseline recommendation for a screenshot')
    p.add_argument("image")
    p.set_defaults(fn=cmd_advise)

    p = sub.add_parser("harvest-cards", help='learn card templates from screenshots (interactive)')
    p.add_argument("images", nargs="+")
    p.set_defaults(fn=cmd_harvest_cards)

    p = sub.add_parser("verify", help='check checksums of a session')
    p.add_argument("session")
    p.set_defaults(fn=cmd_verify)

    sim = sub.add_parser("sim", help='simulator, bots and evaluation').add_subparsers(dest="simcmd", required=True)
    p = sim.add_parser("agents", help='available bots')
    p.set_defaults(fn=cmd_sim_agents)
    for name, fn, hlp in (("match", cmd_sim_match, 'Evaluate bots against each other'),
                          ("hand", cmd_sim_hand, 'play and show a hand')):
        p = sim.add_parser(name, help=hlp)
        p.add_argument("--agents", default="tag,station,rock,lag,maniac,equity",
                       help='comma-separated list, e.g. tag,tag:tag2,random')
        p.add_argument("--seed", type=int, default=1)
        p.add_argument("--sb", type=int, default=10)
        p.add_argument("--bb", type=int, default=20)
        p.add_argument("--stack", type=int, default=100, help='starting stack in big blinds')
        if name == "match":
            p.add_argument("--hands", type=int, default=500, help='number of card sheets')
            p.add_argument("--no-duplicate", action="store_true")
            p.add_argument("--show", type=int, default=0, help='output this many hand histories')
        else:
            p.add_argument("--button", type=int, default=0)
        p.set_defaults(fn=fn)
    p = sim.add_parser("tournament", help='Sit&Go tournaments (like PokerTH) between bots')
    p.add_argument("--agents", default="tag,station,rock,lag,maniac,equity")
    p.add_argument("--tournaments", type=int, default=20, help='number of card schemas (x number of players for duplicates)')
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--stack", type=int, default=3000, help='starting chips')
    p.add_argument("--blinds", default="10/20", help='starting blinds SB/BB')
    p.add_argument("--level-hands", type=int, default=10, help='hands until blinds double')
    p.add_argument("--payouts", default="50,30,20", help='percent per place, e.g. 100 (winner takes all)')
    p.add_argument("--no-duplicate", action="store_true")
    p.set_defaults(fn=cmd_sim_tournament)
    p = sim.add_parser("pushfold", help='display Nash push/fold ranges')
    p.add_argument("--stack", type=float, default=10, help='effective stack in BB')
    p.add_argument("--behind", type=int, default=1, help='players behind the pusher (1 = SB vs BB)')
    p.add_argument("--caller", type=int, default=0, help='which caller (0 = first behind pusher)')
    p.add_argument("--overview", action="store_true", help='push percentages for all stacks/positions')
    p.set_defaults(fn=cmd_sim_pushfold)
    p = sim.add_parser("review", help='compare own decisions of a session with an agent')
    p.add_argument("session")
    p.add_argument("--agent", default="equity")
    p.set_defaults(fn=cmd_sim_review)

    p = sub.add_parser("play", help='you against the bots (terminal)')
    p.add_argument("--mode", choices=["cash", "tournament"], default="tournament")
    p.add_argument("--opponents", default="tag,rock,lag,station,maniac", help='bots/league players, comma-separated list')
    p.add_argument("--name", default="du")
    p.add_argument("--blinds", default="10/20")
    p.add_argument("--stack", type=int, default=3000, help='tournament: starting chips')
    p.add_argument("--level-hands", type=int, default=10)
    p.add_argument("--payouts", default="50,30,20")
    p.add_argument("--stack-bb", type=int, default=100, help='cash: stack in BB (rebuy to this value)')
    p.add_argument("--hands", type=int, default=1000, help='cash: maximum number of hands')
    p.add_argument("--seed", type=int)
    p.add_argument("--coach", action="store_true", help='show push/fold hint after your decision')
    p.add_argument("--unrated", action="store_true", help='do not register tournament in the league')
    p.add_argument("--ascii", action="store_true", help='card suits as letters')
    p.set_defaults(fn=cmd_play)

    p = sub.add_parser("play-stats", help='evaluation of your matches against the bots')
    p.add_argument("--name", default="du")
    p.set_defaults(fn=cmd_play_stats)

    lgp = sub.add_parser("league", help='league, rating, benchmark').add_subparsers(dest="leaguecmd", required=True)
    p = lgp.add_parser("show", help='table + progress graph (report.html)')
    p.set_defaults(fn=cmd_league)
    p = lgp.add_parser("add", help="enter bot version, e.g. add tag-v2 'tag?bluff=0.2'")
    p.add_argument("name")
    p.add_argument("spec")
    p.add_argument("--note")
    p.set_defaults(fn=cmd_league)
    p = lgp.add_parser("retire", help='remove bot from automatic rounds')
    p.add_argument("name")
    p.set_defaults(fn=cmd_league)
    p = lgp.add_parser("run", help='play league games between bots')
    p.add_argument("--rounds", type=int, default=20)
    p.add_argument("--table", type=int, default=6)
    p.add_argument("--stack", type=int, default=3000)
    p.add_argument("--level-hands", type=int, default=10)
    p.add_argument("--seed", type=int)
    p.set_defaults(fn=cmd_league)
    p = lgp.add_parser("bench", help='benchmark against fixed opponents (all bots or one)')
    p.add_argument("name", nargs="?")
    p.add_argument("--hands", type=int, default=300)
    p.add_argument("--tournaments", type=int, default=10)
    p.set_defaults(fn=cmd_league)

    tr = sub.add_parser("train", help='improve bots themselves').add_subparsers(dest="traincmd", required=True)
    p = tr.add_parser("cem", help='optimize style parameters, recording check, possibly add to league')
    p.add_argument("--start", default="tag", help='starting style')
    p.add_argument("--generations", type=int, default=8)
    p.add_argument("--population", type=int, default=12)
    p.add_argument("--schemes", type=int, default=12, help='Card schemas per generation (x6 tournaments)')
    p.add_argument("--gate-schemes", type=int, default=48)
    p.add_argument("--champion", default="tag", help='League player the candidate must beat')
    p.add_argument("--name", help='Name in the league (default: opt-<date>)')
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--resume", help='Continue training folder (data\\train\\...)')
    p.add_argument("--opponents", choices=["league", "fixed"], default="league",
                   help='league = tables from all active league bots, strong more often, with self-play (default); fixed = always rock/tag/lag/station/maniac')
    p.set_defaults(fn=cmd_train)
    p = tr.add_parser("gate", help='Qualification match: candidate against title defender')
    p.add_argument("candidate", nargs="?", help='Bot specification in quotes, e.g. "tag?push_bb=15&bluff=0.2"')
    p.add_argument("--from", dest="from_dir", help='Take candidate from a training folder (result.json)')
    p.add_argument("--champion", default="tag")
    p.add_argument("--schemes", type=int, default=48)
    p.add_argument("--seed", type=int, default=777, help='Different seed = different, fresh card schemas')
    p.add_argument("--opponents", choices=["league", "fixed"], default="league")
    p.set_defaults(fn=cmd_train)
    p = tr.add_parser("bc", help='Learning bot, step 1: imitate teacher bot -> Checkpoint 0')
    p.add_argument("--teacher", default="rock")
    p.add_argument("--run", help='Name of run under data\\rl (default: nn-<date>)')
    p.add_argument("--bc-tournaments", type=int, default=600)
    p.add_argument("--dataset", help='Instead of teacher bot: dataset under data\\datasets, e.g. pluribus')
    p.add_argument("--players", help='Only these players from the dataset, comma-separated, e.g. Pluribus')
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--features", default=None, help='Feature version of the dataset (default: latest)')
    p.set_defaults(fn=cmd_train_nn)
    bp = sub.add_parser("bench", help='Test bench: fixed test sets for each candidate').add_subparsers(
        dest="benchcmd", required=True)
    p = bp.add_parser("run", help='Put candidates on the test bench')
    p.add_argument("spec", help='League name (e.g. opt-1) or bot, e.g. "nn?run=pros-1@200"')
    p.add_argument("--name", help='Name in the table (default: as specified)')
    p.add_argument("--sets", default="fest48,mix96,cash,pluribus",
                   help='Test sets, comma-separated; formats: hu48,3max48,10max48,turbo48,deep48,pokerth48 (or "formats"); larger e.g. mix960,pokerth480 (or "precise")')
    p.add_argument("--exploit", action="store_true", help='Additionally exploitability test (approx. 10 min)')
    p.set_defaults(fn=cmd_bench)
    p = bp.add_parser("show", help='Table of all results')
    p.set_defaults(fn=cmd_bench)
    p = bp.add_parser("slumbot", help='Play heads-up against Slumbot (slumbot.com): absolute benchmark')
    p.add_argument("spec", help='League name or bot, e.g. "nn?run=pros-r1@300"')
    p.add_argument("--name", help='Name of result file (default: as specified); continues')
    p.add_argument("--hands", type=int, default=1000, help='Additional hands (0 = evaluation only)')
    p.add_argument("--workers", type=int, default=4, help='Parallel Slumbot sessions')
    p.set_defaults(fn=cmd_bench)
    p = bp.add_parser("gtow", help='Play heads-up against GTO Wizard AI (benchmark.gtowizard.com): second benchmark, AIVAT')
    p.add_argument("spec", help='League name or bot, e.g. lynx-4-300')
    p.add_argument("--name", help='Name of result file (default: as specified); continues')
    p.add_argument("--hands", type=int, default=500, help='Additional hands (0 = evaluation only)')
    p.add_argument("--workers", type=int, default=2, help='Parallel hands (provider client uses 5)')
    p.add_argument("--key", help='API key (otherwise GTOW_API_KEY or data/bench/gtow/api_key.txt)')
    p.add_argument("--server", action="store_true", help='Additionally retrieve server statistics (AIVAT)')
    p.set_defaults(fn=cmd_bench)
    p = bp.add_parser("ziele", help='Scoreboard of our goals (GOALS.md) for a bot')
    p.add_argument("bot", nargs="?", default="lynx-4-300", help='League name or bot')
    p.add_argument("--name", help='Name on the test bench (default: same as bot)')
    p.add_argument("--messen", action="store_true", help='Measure human480, nash240, kurz240 anew (approx. 15-30 min)')
    p.add_argument("--exploit", action="store_true", help='Additionally exploitability test (approx. 10-20 min)')
    p.add_argument("--slumbot", help='Name of Slumbot result file (default: same as --name)')
    p.add_argument("--workers", type=int, default=None)
    p.set_defaults(fn=cmd_bench)
    p = bp.add_parser("turnier", help='Enter result of a real PokerTH tournament (goal 1)')
    p.add_argument("platz", type=int, help='Own place (1 = won)')
    p.add_argument("--spieler", type=int, default=6, help='Players at start (default 6)')
    p.add_argument("--bot", default="lynx-4-300", help='Which Lynx advised')
    p.add_argument("--notiz", help="e.g. 'against PokerTH bots' or 'online'")
    p.add_argument("--ersetzt", action="store_true",
                   help='Replace last entry of this bot (e.g. incorrect automatic recognition) instead of appending')
    p.set_defaults(fn=cmd_bench)
    p = bp.add_parser("compare", help='Compare two paired entries (all common test sets)')
    p.add_argument("a", help='Name in the table')
    p.add_argument("b", help='Name in the table')
    p.set_defaults(fn=cmd_bench)
    p = tr.add_parser("cfr", help='Equilibrium via Monte-Carlo CFR (Pluribus method)')
    p.add_argument("--run", default="cfr-1")
    p.add_argument("--rounds", type=int, default=200, help='Target round (total number)')
    p.add_argument("--traversals", type=int, default=1500, help='Iterations per process and round')
    p.add_argument("--bench-every", type=int, default=25)
    p.add_argument("--seed", type=int, default=1)
    p.set_defaults(fn=cmd_cfr)
    p = tr.add_parser("deepcfr", help='Deep CFR: equilibrium with neural networks instead of table')
    p.add_argument("--run", default="dcfr-1")
    p.add_argument("--iterations", type=int, default=100, help='Target iteration (total number)')
    p.add_argument("--traversals", type=int, default=600, help='Iterations per process and iteration')
    p.add_argument("--snapshot-every", type=int, default=10)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--buffer", type=int, default=1_000_000,
                   help='Entries per data buffer (RAM approx. 220 MB per 1 million; 2 buffers)')
    p.set_defaults(fn=cmd_deepcfr)
    p = tr.add_parser("exploit", help='Exploitability test: how strongly can a bot be exploited deliberately?')
    p.add_argument("target", help='Bot specification, e.g. rock or "nn?run=pros-1@200"')
    p.add_argument("--init", default="pros-1@0", help='Start point of exploiter (run@checkpoint)')
    p.add_argument("--iterations", type=int, default=40)
    p.add_argument("--schemes", type=int, default=48)
    p.set_defaults(fn=cmd_exploit)
    dp = sub.add_parser("data", help='Read and evaluate foreign hand histories (PHH)').add_subparsers(
        dest="datacmd", required=True)
    p = dp.add_parser("pluribus", help='Replay Pluribus hands -> data\\datasets\\pluribus.npz')
    p.add_argument("--source", help='Folder with .phh files (default: data\\external\\phh-dataset\\data\\pluribus)')
    p.set_defaults(fn=cmd_data)
    p = dp.add_parser("humans", help='Real Players (HandHQ): Frequencies per player and player types')
    p.add_argument("--sets", help='Folder under data\\external\\phh-dataset\\data\\handhq, comma-separated (default: all)')
    p.add_argument("--name", default="handhq", help='Result data\\humans\\<name>.json')
    p.add_argument("--types", type=int, default=6, help='Number of player types')
    p.add_argument("--min-hands", type=int, default=300, help='Players with fewer hands do not count towards types')
    p.add_argument("--max-files", type=int, help='only the first N files (test)')
    p.add_argument("--workers", type=int, default=4, help='parallel processes (RAM!)')
    p.set_defaults(fn=cmd_data)
    p = dp.add_parser("humandata", help='HandHQ showdown decisions with known cards as features + action (H11 human model)')
    p.add_argument("--sets", help='Folder under data\\external\\phh-dataset\\data\\handhq, comma-separated (default: all)')
    p.add_argument("--out", help='Target folder (default data\\humans\\actions)')
    p.add_argument("--max-files", type=int, help='only the first N files (test)')
    p.add_argument("--files-per-shard", type=int, default=50, help='Files per shard human-<nr>.npz')
    p.add_argument("--workers", type=int, default=2, help='Parallel processes')
    p.set_defaults(fn=cmd_data)
    p = dp.add_parser("humanpublic", help='HandHQ: ALL card-free decisions with folds (fold model, H11 step 2b)')
    p.add_argument("--sets", help='Folder under data\\external\\phh-dataset\\data\\handhq, comma-separated (default: all)')
    p.add_argument("--out", help='Target folder (default data\\humans\\actions, files public-<nr>.npz)')
    p.add_argument("--max-files", type=int, help='only the first N files (test)')
    p.add_argument("--files-per-shard", type=int, default=50)
    p.add_argument("--workers", type=int, default=4, help='Parallel processes')
    p.set_defaults(fn=cmd_data)
    p = dp.add_parser("agree", help='How often does a network make the decisions in the dataset?')
    p.add_argument("run")
    p.add_argument("--ckpt", default="latest", help='Checkpoint(s), comma-separated, e.g. 0,100,200')
    p.add_argument("--dataset", default="pluribus")
    p.add_argument("--players", default="Pluribus")
    p.set_defaults(fn=cmd_data)
    p = tr.add_parser("humans-fit", help='Human bots: Adapt style bots to real player types (data humans)')
    p.add_argument("--source", default="handhq-25nl", help='data\\humans\\<source>.json')
    p.add_argument("--name", default="mensch-25nl", help='Result data\\humans\\<name>.json')
    p.add_argument("--generations", type=int, default=10)
    p.add_argument("--population", type=int, default=16)
    p.add_argument("--hands", type=int, default=600, help='Hands per measurement')
    p.set_defaults(fn=cmd_humans_fit)
    p = tr.add_parser("valuedata", help='Value network data: Solve situations exactly at the start of the street (milestone 3)')
    p.add_argument("street", choices=["river", "turn", "flop", "river-leaf", "turn-leaf"],
                   help='Street at the start of which evaluation is done; river-leaf = river starts from real turn searches (up to 24 rows per seed), turn-leaf = turn starts from real flop searches, river via value network (up to 12 rows per seed)')
    p.add_argument("--n", type=int, default=1000, help='Situations in this shard')
    p.add_argument("--seed", type=int, default=0, help='First seed (shards: seed, seed+n, ...)')
    p.add_argument("--iters", type=int, help='CFR+ iterations (default river 300, turn 150, flop 60)')
    p.add_argument("--workers", type=int, default=1, help='Processes')
    p.add_argument("--threads", type=int, help='Numba threads per process (default: all)')
    p.add_argument("--out", help='Target file .npz (default data\\valuenet\\<street>-<seed>.npz)')
    p.add_argument("--vnet", help='River value network as leaf (turn/flop/turn-leaf; default with turn-leaf: vnet-river-1)')
    p.set_defaults(fn=cmd_valuedata)
    p = tr.add_parser("valuenet", help='Train value network from value data shards (locally small; large on Kaggle)')
    p.add_argument("--data", required=True, help='Glob on .npz shards, e.g. data\\valuenet\\river-*.npz')
    p.add_argument("--out", default="vnet-river-1", help='Name under data\\valuenet\\<out>.pt or path')
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--batch", type=int, default=512)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--width", type=int, default=1024)
    p.add_argument("--depth", type=int, default=3)
    p.add_argument("--resume", help='Checkpoint from which to continue training')
    p.set_defaults(fn=cmd_valuenet)
    p = tr.add_parser("teacher-collect", help='Search as teacher (H5): Collect search decisions as soft targets')
    p.add_argument("--search", default="hus?bp=lynx-4-300&auto=1&iters=60&iters_river=150&threads=3&vnet=kaggle-t2-big/vnet-river",
                   help='Specification of the search (teacher)')
    p.add_argument("--student", default="nn?run=lynx-4@300", help='Student network (determines feature space)')
    p.add_argument("--opponents", default="nn?run=lynx-4@300,station,mensch-2,mensch-4",
                   help='Opponent specifications, comma-separated')
    p.add_argument("--stacks", default="25,50,100,200", help='Stack depths in BB, comma-separated')
    p.add_argument("--hands", type=int, default=50, help='Card decks per match (duplicate -> twice as many hands)')
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--out", required=True, help='Target file .npz (e.g. data\\teacher\\t1-seed1.npz)')
    p.set_defaults(fn=cmd_teacher)
    p = tr.add_parser("teacher-fit", help='Search as teacher (H5): further train student on collected targets (with KL loss)')
    p.add_argument("--data", required=True, help='Glob on teacher-.npz, e.g. data\\teacher\\t1-*.npz')
    p.add_argument("--student", default="lynx-4@300", help='<run>@<checkpoint>')
    p.add_argument("--out-run", required=True, help='New run under data\\rl\\<out-run> (ckpt_000001.pt)')
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--batch", type=int, default=512)
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--kl", type=float, default=0.5, help='Weight of the KL loss on the anchor (0 = off)')
    p.set_defaults(fn=cmd_teacher)
    p = tr.add_parser("humanfold", help='Fold model from the card-free HandHQ lines (H11 step 2b)')
    p.add_argument("--rows", help='Folder with public-*.npz (default data\\humans\\actions)')
    p.add_argument("--out", default="human-fold-1", help='Name under data\\humans\\<out>.npz')
    p.add_argument("--max-rows", type=int, default=4_000_000)
    p.add_argument("--max-shards", type=int, default=40, help='Memory: limit shards')
    p.add_argument("--epochs", type=int, default=3)
    p.set_defaults(fn=cmd_humanfold)
    p = tr.add_parser("rl", help='Learning bot, step 2: self-play with PPO (continues a run)')
    p.add_argument("--run", help='Continue or name run (data\\rl\\<run>)')
    p.add_argument("--teacher", help='New run: first imitate this bot (recommended: rock)')
    p.add_argument("--bc-tournaments", type=int, default=600)
    p.add_argument("--iterations", type=int, default=100, help='Target iteration (total number, not additional)')
    p.add_argument("--tournaments", type=int, default=96, help='Sit&Gos per iteration')
    p.add_argument("--champion", default="rock")
    p.add_argument("--gate-schemes", type=int, default=120, help='0 = no admission test at the end')
    p.add_argument("--name", help='Name in the league upon passing the exam')
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--anchor-coef", type=float, default=0.0,
                   help='Leash: Penalty for deviation from the anchor strategy (e.g., 0.3); 0 = off')
    p.add_argument("--anchor", help="Anchor '<run>:<ckpt>', default: Checkpoint 0 of this run")
    p.add_argument("--random-share", type=float, default=0.0,
                   help='Proportion of table seats with random style bots, e.g., 0.3 (always new playing styles)')
    p.add_argument("--exploit-every", type=int, default=0,
                   help='Train and include exploiter as opponent every N iterations (0 = off)')
    p.add_argument("--exploit-iters", type=int, default=30, help='Training iterations per exploiter')
    p.add_argument("--random-formats", action="store_true",
                   help='Per tournament randomly 2-10 players, 20-200 BB, blind speed 5-20 hands, payout')
    p.add_argument("--lr", type=float, default=3e-4, help='Learning rate (also applies when resuming)')
    p.add_argument("--bench-every", type=int, default=50, help='Every N iterations to the test stage (0 = never)')
    p.add_argument("--bench-sets", default="fest48,mix96,pluribus",
                   help='Test sets of the test stage, e.g., "praezise,pluribus"')
    p.add_argument("--bench-ref", help='Comparison bot (name at the test stage), best version -> best.json')
    p.add_argument("--widen-from", help="New run: start from '<run>@<ckpt>', network widened to --features")
    p.add_argument("--features", default=None, help='With --widen-from: feature version, e.g., feat-3')
    p.add_argument("--actions", type=int, default=None, help='With --widen-from: number of actions (8 = act-2)')
    p.add_argument("--anchor-min-players", type=int, default=0, help='Leash starts only from this many players')
    p.add_argument("--table-weights", help='With --random-formats: table size weights, e.g., "2:4,3:3,6:2"')
    p.add_argument("--human-share", type=float, default=0.0,
                   help='Proportion of table seats with human bots (real player types, train humans-fit)')
    p.add_argument("--self-play-seats", type=float, default=0.0,
                   help='Per opponent seat probability for a prior own version')
    p.add_argument("--icm", type=float, default=0.0,
                   help='Proportion of ICM reward (change of tournament equity instead of chips), e.g., 1.0')
    p.set_defaults(fn=cmd_train_nn)

    a = ap.parse_args(argv)
    from .system import keep_awake
    with keep_awake(not a.allow_sleep):
        a.fn(a)


if __name__ == "__main__":
    main()

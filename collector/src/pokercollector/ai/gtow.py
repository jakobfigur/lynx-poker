"""Messung gegen GTO Wizard AI (benchmark.gtowizard.com) - zweites externes Massband neben Slumbot.

Format: Heads-up No-Limit, Cash, Blinds 50/100, beide Stacks zu Beginn jeder Hand 20000 (200 BB) - wie Slumbot.
Gegner: GTO Wizard AI (ehemals Ruse AI), rechnet jede Situation in Echtzeit; schlaegt Slumbot um 19,4 bb/100
(arXiv 2603.23660). Bewertung mit AIVAT (Burch u. a. 2016): erwartungstreue Varianzreduktion, etwa dreifach
kleinere Streuung als rohe Gewinne.

API (https://researcher.gtowizard.com, OpenAPI unter /openapi.json, Schluessel im Header X-API-Key):
  POST /hands {"game_name": "HUNL 200BB"}        -> Spielstand (hand_id, game, game_state)
  POST /hands/{hand_id}/act {"action": "f|k|c|b", "amount": N}   -> Spielstand nach unserem Zug UND der Antwort
  GET  /results?game_name=...                    -> Serverstatistik (total_hands, aivat_score, ...)
  POST /users/request {...}                      -> Zugang beantragen (Schluessel waehlt man selbst, >= 32 Zeichen)
Verlauf (game_state.action_history) als Liste: 'f', 'k', 'c', 'bX' (Einsatz AUF X, Strassensumme) und '_' als
Strassenwechsel - also dasselbe Schema wie bei Slumbot ('/' statt '_'). Deshalb wird der Spielstand mit
slumbot.replay in der Engine nachgebaut, und to_incr liefert unseren Zug.

Regeln des Anbieters: nur Haende spielen und Ergebnisse sehen, keine Solver-Funktionen; 100 000 Haende je Nutzer
und Monat; Zugang kann entzogen werden. Es gehen ausschliesslich unsere Spielzuege nach draussen.
Jede Hand wird sofort in data/bench/gtow/<name>.jsonl geschrieben (fortsetzbar). Nur Massband, kein Trainingsziel.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .agents import make_agent
from .engine import Hand
from .observation import Action, clamp_action
from .slumbot import BB, CLIENT, _stat, allin_ev, replay

API = "https://researcher.gtowizard.com"
GAME = "HUNL 200BB"
GTOW_VERSION = "gtow-1"
KEY_FILE = "api_key.txt"             # unter data/bench/gtow/, alternativ Umgebungsvariable GTOW_API_KEY


class GtowError(RuntimeError):
    pass


def results_dir() -> Path:
    from .nn_agent import rl_root
    return rl_root().parent / "bench" / "gtow"


def api_key(explicit: str | None = None) -> str:
    key = explicit or os.environ.get("GTOW_API_KEY")
    if not key:
        p = results_dir() / KEY_FILE
        if p.exists():
            key = p.read_text("utf-8").strip()
    if not key:
        raise GtowError(f"kein API-Schluessel: --key, GTOW_API_KEY oder {results_dir() / KEY_FILE}")
    return key


def _request(method: str, path: str, data: dict | None = None, key: str | None = None,
             retries: int = 8) -> dict | list:
    body = json.dumps(data).encode() if data is not None else None
    # eigener User-Agent: die Standardkennung von urllib wird vom Schutz des Anbieters abgewiesen (403, Code 1010)
    headers = {"Content-Type": "application/json", "Accept": "application/json",
               "User-Agent": f"pokercollector-lynx/{GTOW_VERSION} (benchmark client)"}
    if key:
        headers["X-API-Key"] = key
    for k in range(retries):
        try:
            req = urllib.request.Request(f"{API}{path}", body, headers, method=method)
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            if e.code in (502, 503, 504) and k < retries - 1:      # Engine beschaeftigt: warten
                time.sleep(min(60, 2 ** k))
                continue
            detail = e.read().decode("utf-8", "replace")[:500]
            raise GtowError(f"HTTP {e.code} bei {method} {path}: {detail}") from None
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError):
            if k == retries - 1:
                raise
            time.sleep(min(60, 2 ** k))
    raise AssertionError


# ---------------------------------------------------------------- Uebersetzung Spielstand <-> Engine

def history_to_text(history: list[str]) -> str:
    """['b300', 'c', '_', 'k', 'b500'] -> 'b300c/kb500' (Slumbot-Schreibweise fuer slumbot.replay)."""
    parts, cur = [], []
    for tok in history:
        if tok == "_":
            parts.append("".join(cur))
            cur = []
        elif tok in ("f", "k", "c") or (tok.startswith("b") and tok[1:].isdigit()):
            cur.append(tok)
        else:
            raise GtowError(f"unbekannter Verlaufseintrag {tok!r}")
    parts.append("".join(cur))
    return "/".join(parts)


def parse_cards(s: str | None) -> list[str]:
    """'AhKd', 'Ah Kd', 'Ah,Kd' -> ['Ah', 'Kd']; None/'' -> []. Zehner als 'T' (auch '10' wird verstanden)."""
    if not s:
        return []
    t = s.replace(",", "").replace(" ", "").replace("10", "T")
    if len(t) % 2:
        raise GtowError(f"Karten nicht lesbar: {s!r}")
    return [t[i:i + 2] for i in range(0, len(t), 2)]


def split_players(players: list[dict]) -> tuple[dict, dict]:
    """(wir, GTO Wizard). Erkennung ueber den Namen, sonst ueber die sichtbaren Hole Cards."""
    bot = [p for p in players if "wizard" in p["name"].lower() or "gto" in p["name"].lower()]
    if len(bot) == 1 and len(players) == 2:
        me = players[0] if players[1] is bot[0] else players[1]
        return me, bot[0]
    seen = [p for p in players if p.get("hole_cards")]
    if len(seen) == 1 and len(players) == 2:
        me = seen[0]
        return me, players[0] if players[1] is me else players[1]
    raise GtowError(f"Spieler nicht zuzuordnen: {players}")


def client_pos(position: str) -> int:
    """1 = Small Blind/Button (handelt preflop zuerst), 0 = Big Blind - wie slumbot.replay."""
    p = position.lower().replace("_", "").replace("-", "").replace(" ", "")
    if p in ("sb", "btn", "button", "smallblind", "dealer", "ip", "p0", "0"):
        return 1
    if p in ("bb", "bigblind", "oop", "p1", "1"):
        return 0
    raise GtowError(f"unbekannte Position {position!r}")


def rebuild(resp: dict, seed: int = 0) -> tuple[Hand, dict, dict]:
    """Spielstand der API in der Engine nachbauen. Liefert (Hand, wir, Bot)."""
    gs = resp["game_state"]
    me, bot = split_players(gs["players"])
    h = replay(history_to_text(gs["action_history"]), client_pos(me["position"]), parse_cards(me["hole_cards"]),
               parse_cards(gs["board_cards"]), parse_cards(bot.get("hole_cards")) or None, seed=seed)
    return h, me, bot


def to_act_request(obs, action: Action, gs: dict) -> dict:
    """Engine-Aktion -> ActRequest. Einsatzhoehe ist die Strassensumme (wie raise_to), in raise_range gekappt."""
    a = clamp_action(obs, action)
    legal = set(gs.get("legal_actions") or ())
    if a.kind == "fold":
        return {"action": "f"} if "f" in legal or not legal else {"action": "k"}
    if a.kind == "check" or (a.kind == "call" and obs.to_call == 0):
        return {"action": "k"} if "k" in legal or not legal else {"action": "c"}
    if a.kind == "call":
        return {"action": "c"} if "c" in legal or not legal else {"action": "k"}
    rr = gs.get("raise_range")
    amt = int(round(a.amount))
    if rr:
        amt = max(int(round(rr["min"])), min(int(round(rr["max"])), amt))
    if legal and "b" not in legal:                       # darf nicht mehr setzen -> mitgehen
        return {"action": "c"} if "c" in legal else {"action": "k"}
    return {"action": "b", "amount": amt}


# ---------------------------------------------------------------- eine Hand

def play_hand(agent, key: str, seed: int) -> dict:
    r = _request("POST", "/hands", {"game_name": GAME}, key)
    hand_id = r["hand_id"]
    decisions = 0
    while not r["game_state"]["is_hand_over"]:
        gs = r["game_state"]
        if gs.get("player_to_act") not in (None, "user"):
            raise GtowError(f"Hand {hand_id}: GTO Wizard am Zug, aber Hand nicht vorbei: {gs}")
        h, me, bot = rebuild(r, seed)
        if h.done or h.to_act != CLIENT:
            raise GtowError(f"Hand {hand_id}: Spielstand passt nicht zur Engine: {gs['action_history']}")
        obs = h.observation(CLIENT)
        req = to_act_request(obs, agent.act(obs), gs)
        decisions += 1
        r = _request("POST", f"/hands/{hand_id}/act", req, key)
    gs = r["game_state"]
    me, bot = split_players(gs["players"])
    hole, board = parse_cards(me["hole_cards"]), parse_cards(gs["board_cards"])
    bot_hole = parse_cards(bot.get("hole_cards")) or None
    out = {"hand_id": hand_id, "client_pos": client_pos(me["position"]), "hole": hole, "board": board,
           "bot_hole": bot_hole, "action": history_to_text(gs["action_history"]),
           "winnings": gs.get("winnings"), "aivat": gs.get("aivat_score"), "decisions": decisions,
           "bot_folded": gs.get("has_gto_wizard_folded")}
    # Gegenprobe: Engine rechnet dasselbe Ergebnis aus (prueft die Uebersetzung) - nur wenn alle Karten bekannt
    # sind oder die Hand ohne Showdown endete
    try:
        h = replay(out["action"], out["client_pos"], hole, board, bot_hole, seed=seed)
        if h.done and h.record is not None and (bot_hole or not h.record.went_to_showdown):
            out["engine_net"] = h.record.results[CLIENT].net
            if bot_hole:
                ev = allin_ev(h, hole, bot_hole)
                out["allin_ev"] = round(ev, 1) if ev is not None else None
    except (ValueError, KeyError, IndexError, AssertionError) as e:   # Gegenprobe darf die Messung nie stoppen
        out["engine_error"] = str(e)[:200]
    return out


# ---------------------------------------------------------------- Auswertung

def load_hands(name: str) -> list[dict]:
    p = results_dir() / f"{name}.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text("utf-8").splitlines() if x.strip()]


def summarize(hands: list[dict]) -> dict:
    raw = [h["winnings"] for h in hands if h.get("winnings") is not None]
    aiv = [h["aivat"] for h in hands if h.get("aivat") is not None]
    ev = [h["allin_ev"] if h.get("allin_ev") is not None else h["winnings"] for h in hands
          if h.get("winnings") is not None]
    mism = sum(1 for h in hands if "engine_net" in h and h["engine_net"] != h["winnings"])
    return {"roh": _stat(raw), "aivat": _stat(aiv), "allin_ev": _stat(ev), "hands": len(hands),
            "engine_mismatch": mism, "bot_folds": sum(1 for h in hands if h.get("bot_folded"))}


def server_results(key: str) -> dict:
    """Statistik des Servers (AIVAT ueber alle unsere Haende, massgeblich fuer die Rangliste)."""
    r = _request("GET", f"/results?game_name={urllib.request.quote(GAME)}", None, key)
    return r if isinstance(r, dict) else {"raw": r}


def request_access(email: str, organization: str, bot_name: str, key: str, reason: str) -> dict:
    """Zugang beantragen. Den Schluessel (>= 32 Zeichen) waehlt man selbst; er gilt nach Freigabe per E-Mail."""
    if len(key) < 32:
        raise GtowError("API-Schluessel muss mindestens 32 Zeichen haben")
    r = _request("POST", "/users/request", {"email": email, "organization": organization, "bot_name": bot_name,
                                            "api_key": key, "reason_for_joining": reason})
    return r if isinstance(r, dict) else {"raw": r}


def run(spec: str, name: str, hands: int, workers: int = 2, key: str | None = None, progress=None) -> dict:
    """Spielt bis zu `hands` weitere Haende mit `workers` parallelen Haenden (der Anbieter-Client nutzt 5)."""
    key = api_key(key)
    d = results_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}.jsonl"
    done0 = len(load_hands(name))
    per = [hands // workers + (1 if i < hands % workers else 0) for i in range(workers)]
    lock = threading.Lock()
    count = [0]
    stop = threading.Event()

    def worker(i: int):
        agent = make_agent(f"{spec}:cand", 1000 + i)
        errors = 0
        for k in range(per[i]):
            if stop.is_set():
                return
            try:
                res = play_hand(agent, key, seed=(done0 + i * 100_003 + k) & 0x7FFFFFFF)
            except GtowError as e:
                errors += 1
                msg = str(e)
                print(f"  Hand {i}/{k}: {msg[:200]}", flush=True)
                if "HTTP 401" in msg or "HTTP 403" in msg or errors > 20:
                    stop.set()                   # Schluessel ungueltig oder Dauerfehler: alle anhalten
                    raise
                time.sleep(2)
                continue
            res["spec"], res["t"] = spec, time.strftime("%Y-%m-%d %H:%M:%S")
            with lock:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(res) + "\n")
                count[0] += 1
                if progress and count[0] % 50 == 0:
                    progress(count[0], summarize(load_hands(name)))

    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(worker, range(workers)))
    return summarize(load_hands(name))

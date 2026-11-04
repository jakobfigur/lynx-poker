"""Kalibrier-Overlay und lesbare Berichte (Markdown)."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from .analyzer import TableSnapshot
from .poker import SUIT_SYMBOLS


def overlay(frame: np.ndarray, snap: TableSnapshot) -> np.ndarray:
    img = frame.copy()
    lay = snap.layout
    if lay is None or not lay.found:
        cv2.putText(img, "KEIN TISCH ERKANNT", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
        return img

    def box(r, color, label=None, thick=2):
        if r is None:
            return
        cv2.rectangle(img, (r.x, r.y), (r.x2, r.y2), color, thick)
        if label:
            y = r.y - 4 if r.y > 14 else r.y2 + 14
            cv2.putText(img, label, (r.x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3)
            cv2.putText(img, label, (r.x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

    box(lay.felt, (0, 255, 0), "Filz", 1)
    for r in (lay.info_left, lay.info_center, lay.info_right):
        box(r, (255, 200, 0), None, 1)
    box(lay.pot, (0, 255, 255), f"Pot {snap.get('pot.total')}")
    for i, r in enumerate(lay.board_slots):
        c = (snap.get("board.cards") or [None] * 5)[i]
        box(r, (255, 0, 255), c or "-", 1)
    if lay.action_bar:
        box(lay.action_bar, (0, 128, 255), "Du bist dran")
    for m in lay.markers:
        box(m.rect, (255, 255, 255), f"{m.kind}->{m.seat}", 1)
    for n, p in lay.seats.items():
        g = lambda k: snap.get(f"seat.{n}.{k}")
        color = (0, 0, 255) if g("folded") else ((0, 255, 255) if g("active") else (255, 255, 0))
        label = f"#{n} {g('name')} {g('stack')}"
        if g("bet"):
            label += f" bet {g('bet')}"
        if g("cards"):
            label += " " + " ".join(g("cards"))
        box(p.full_rect, color, label)
    for r in lay.unmatched_panels:
        box(r, (0, 0, 255), "?", 1)
    info = f"Spiel/Hand {snap.get('info.game_hand')}  {snap.get('info.street')}  Blinds {snap.get('info.blinds')}"
    cv2.putText(img, info, (10, img.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
    cv2.putText(img, info, (10, img.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    return img


def _cards(cs) -> str:
    if not cs:
        return "-"
    return " ".join((c[0] + SUIT_SYMBOLS.get(c[1], c[1])) if c and len(c) == 2 and c != "??" else "??" for c in cs)


def hands_markdown(session_root: Path) -> str:
    meta = json.loads((session_root / "session.json").read_text("utf-8"))
    data = json.loads((session_root / "hands.json").read_text("utf-8"))
    lines = [f"# Sitzung {meta['session_id']}", "",
             f"- Quelle: `{meta['source'].get('type')}` {meta['source'].get('path') or meta['source'].get('title') or ''}",
             f"- Profil: {meta['profile']}, Analyzer: {meta['analyzer_version']}, "
             f"Rekonstruktion: {data['reconstruct_version']}",
             f"- Statistik: {meta.get('stats')}",
             f"- Luecken: {len(meta.get('gaps', []))}, Fehler: {len(meta.get('errors', []))}", ""]
    hands = data["hands"]
    complete = sum(1 for h in hands if h["status"] == "complete")
    lines.append(f"**{len(hands)} Haende, davon {complete} vollstaendig.**")
    lines.append("")
    for h in hands:
        lines.append(f"## Spiel {h['game_no']} Hand {h['hand_no']} - {h['status']}")
        if h["status_reasons"]:
            lines.append("Gruende: " + "; ".join(h["status_reasons"]))
        lines.append(f"Dealer {h['dealer']}, SB {h['sb_seat']}, BB {h['bb_seat']}, Blinds {h['blinds']}, "
                     f"Board {_cards(h['board'])}")
        for s, si in h["seats"].items():
            if si.get("cards"):
                lines.append(f"- Sitz {s} {si.get('name')}: {_cards(si['cards'])} ({si.get('cards_source')})")
        lines.append("")
        lines.append("| Strasse | Sitz | Name | Aktion | auf | + | Quelle | Konf. | Notiz |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for a in h["actions"]:
            lines.append(f"| {a['street']} | {a['seat']} | {a['name'] or ''} | {a['type']}{' (all-in)' if a['allin'] else ''}"
                         f" | {a['amount_to'] if a['amount_to'] is not None else ''} | {a['added'] if a['added'] is not None else ''}"
                         f" | {a['source']} | {a['confidence']:.2f} | {a['note']} |")
        if h["contradictions"]:
            lines.append("")
            lines.append("Widersprueche: " + "; ".join(h["contradictions"]))
        if h["gaps"]:
            lines.append("Luecken: " + "; ".join(h["gaps"]))
        lines.append("")
    return "\n".join(lines)


def compare_markdown(result: dict) -> str:
    lines = ["# Vergleich visuell vs. Export", "",
             f"Haende visuell {result['hands_visual']}, Referenz {result['hands_reference']}, "
             f"zugeordnet {result['hands_matched']}", "",
             f"Sitzzuordnung (visuell -> Referenz): {result['seat_map']}", "",
             "| Feld | Treffer | Abweichung | fehlt | zusaetzlich | nicht sichtbar | Precision | Recall |",
             "|---|---|---|---|---|---|---|---|"]
    for k, v in result["fields"].items():
        lines.append(f"| {k} | {v['match']} | {v['mismatch']} | {v['missing']} | {v['extra']} | {v['not_visible']}"
                     f" | {v['precision'] if v['precision'] is not None else '-'}"
                     f" | {v['recall'] if v['recall'] is not None else '-'} |")
    lines += ["", f"Betragssemantik der Referenz (gezaehlte Treffer): {result['amount_semantics']}", ""]
    for d in result["details"]:
        if d["issues"]:
            lines.append(f"## Hand {d['visual_hand']} ({d['status']})")
            lines += [f"- {i}" for i in d["issues"]]
            lines.append("")
    return "\n".join(lines)

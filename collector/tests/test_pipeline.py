"""Ende-zu-Ende: Video -> Analyse -> Journal -> Rekonstruktion, plus Recorder."""

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from pokercollector.capture import Frame, SegmentRecorder, VideoFileSource
from pokercollector.journal import read_events, verify_manifest
from pokercollector.profile import Profile

IMG = Path(__file__).parent.parent / "testdata" / "pokerth_preflop_hand1.png"


def write_video(path: Path, frames: list[np.ndarray], fps=5):
    h, w = frames[0].shape[:2]
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for f in frames:
        vw.write(f)
    vw.release()


def test_recorder_segments(tmp_path):
    rec = SegmentRecorder(tmp_path, fps=5, segment_s=1.0)
    img = np.zeros((120, 160, 3), np.uint8)
    for i in range(12):
        rec.write(Frame(i, i * 0.2, 1000 + i * 0.2, img))
    rec.close()
    assert len(rec.segments) == 3
    assert sum(s["frames"] for s in rec.segments) == 12
    side = (tmp_path / "segment_0001.frames.jsonl").read_text().splitlines()
    assert json.loads(side[0])["t_mono"] == 0.0
    assert VideoFileSource(tmp_path / "segment_0001.mp4").count == 5


def test_offline_session_end_to_end(tmp_path):
    try:
        from pokercollector.pipeline import make_analyzer, run_offline
        an = make_analyzer(Profile.load())
    except Exception as e:
        pytest.skip(f"Windows-OCR nicht verfuegbar: {e}")
    img = cv2.imread(str(IMG))
    blank = np.zeros_like(img)
    video = tmp_path / "in.mp4"
    write_video(video, [blank, blank] + [img] * 6)
    root = run_offline(VideoFileSource(video, step_s=0.2), tmp_path / "sessions", Profile.load(), an)

    events = read_events(root)
    changed = {e["field"]: e["new"] for e in events if e["kind"] == "change"}
    assert changed["info.game_hand"] == [1, 1]
    assert changed["seat.0.cards"] == ["6s", "9h"]
    assert changed["seat.2.bet"] == 20
    assert any(e.get("evidence") for e in events)
    assert (root / "index.sqlite").exists()

    hands = json.loads((root / "hands.json").read_text("utf-8"))["hands"]
    assert len(hands) == 1
    h = hands[0]
    assert (h["dealer"], h["sb_seat"], h["bb_seat"]) == (0, 1, 2)
    types = [(a["seat"], a["type"]) for a in h["actions"]]
    assert (1, "post_sb") in types and (2, "post_bb") in types and (3, "fold") in types
    assert h["status"] == "partial"           # Hand endet im Video nicht
    # Einstieg mitten in der Hand: Startstacks aus Stack + gesetzten Blinds abgeleitet
    assert h["seats"]["1"]["start_stack"] == 3000 and h["seats"]["2"]["start_stack"] == 3000
    assert h["contradictions"] == []
    assert verify_manifest(root) == []

""" Masks for own displays: the Lynx bar is visible but cut out from collector captures
    (replaces hiding via WDA_EXCLUDEFROMCAPTURE since 11/3/2026)."""
import json

import numpy as np

from pokercollector import capture
from pokercollector.capture import Frame, SegmentRecorder, apply_masks

FELT = (40, 120, 30)        # BGR, felt green


def _table(w=200, h=120):
    img = np.zeros((h, w, 3), np.uint8)
    img[:] = FELT
    return img


def test_maske_fuellt_mit_umgebungsfarbe_und_meldet_rechteck():
    img = _table()
    img[90:110, 150:195] = (30, 30, 30)              # the bar at bottom right of the image
    # Window at (500, 300) on screen, bar at (650, 390), 45x20
    done = apply_masks(img, (500, 300), [(650, 390, 45, 20)])
    assert done == [[150, 90, 45, 20]]
    assert (img == FELT).all()                        # felt is now at its place


def test_maske_ausserhalb_oder_teilweise_im_bild():
    img = _table()
    before = img.copy()
    assert apply_masks(img, (0, 0), [(300, 300, 50, 20)]) == []        # completely outside: nothing happens
    assert (img == before).all()
    img[100:120, 180:200] = (200, 200, 200)
    done = apply_masks(img, (0, 0), [(180, 100, 60, 40)])              # protrudes to the right and bottom
    assert done == [[180, 100, 20, 20]]
    assert (img[100:120, 180:200] == FELT).all()


def test_maske_ueber_dem_ganzen_bild_faellt_auf_grau():
    img = _table(20, 10)
    assert apply_masks(img, (0, 0), [(-5, -5, 40, 30)]) == [[0, 0, 20, 10]]
    assert (img == 128).all()


def test_graustufenbild():
    img = np.full((40, 60), 90, np.uint8)
    img[10:20, 10:30] = 250
    assert apply_masks(img, (0, 0), [(10, 10, 20, 10)]) == [[10, 10, 20, 10]]
    assert (img == 90).all()


def test_anmelden_abmelden_und_vermerk_im_sidecar(tmp_path):
    capture.register_mask_window(4242)
    try:
        assert 4242 in capture.mask_windows()
    finally:
        capture.unregister_mask_window(4242)
    assert 4242 not in capture.mask_windows()
    rec = SegmentRecorder(tmp_path, fps=5)
    rec.write(Frame(0, 0.0, 0.0, _table(), masked=[[150, 90, 45, 20]]))
    rec.write(Frame(1, 0.2, 0.2, _table()))
    rec.close()
    lines = [json.loads(x) for x in (tmp_path / "segment_0001.frames.jsonl").read_text("utf-8").splitlines()]
    assert lines[0]["masked"] == [[150, 90, 45, 20]]
    assert "masked" not in lines[1]

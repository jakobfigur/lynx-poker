from pokercollector.analyzer import FieldObs, TableSnapshot
from pokercollector.stabilize import Stabilizer


def snap(i, t, **fields):
    s = TableSnapshot(i, t, t)
    for k, v in fields.items():
        s.fields[k.replace("__", ".")] = v if isinstance(v, FieldObs) else FieldObs(v, confidence=0.9)
    return s


def test_change_needs_confirmation_and_transients_are_reported():
    st = Stabilizer(min_frames=2, min_ms=100)
    assert st.update(snap(0, 0.0, pot__total=30)) == []
    ev = st.update(snap(1, 0.2, pot__total=30))
    assert [(e.kind, e.new, e.t_first) for e in ev] == [("change", 30, 0.0)]
    # a single misreader is not adopted, but reported
    assert st.update(snap(2, 0.4, pot__total=80)) == []
    ev = st.update(snap(3, 0.6, pot__total=30))
    assert [(e.kind, e.new) for e in ev] == [("transient", 80)]
    assert st.state()["pot.total"] == 30


def test_unreadable_becomes_unknown_only_after_timeout():
    st = Stabilizer(min_frames=1, min_ms=0, unknown_after_ms=1000)
    st.update(snap(0, 0.0, seat__1__stack=3000))
    unread = FieldObs(None, confidence=0.0)
    assert st.update(snap(1, 0.5, seat__1__stack=unread)) == []
    ev = st.update(snap(2, 1.6, seat__1__stack=unread))
    assert [(e.kind, e.old) for e in ev] == [("unknown", 3000)]


def test_fast_field_switches_immediately():
    st = Stabilizer(min_frames=3, min_ms=500)
    ev = st.update(snap(0, 0.0, hero__to_act=True))
    assert [(e.kind, e.new) for e in ev] == [("change", True)]

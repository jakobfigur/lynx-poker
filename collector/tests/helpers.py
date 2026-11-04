' Produces synthetic, stabilized field events as in the journal.'


class EventStream:
    def __init__(self):
        self.events = []
        self.cur = {}

    def at(self, t, **fields):
        for k, v in fields.items():
            name = k.replace("__", ".")
            self.events.append({
                "seq": len(self.events) + 1, "kind": "change", "field": name, "old": self.cur.get(name),
                "new": v, "t_first": t, "t_confirmed": t + 0.15, "frame_first": int(t * 10),
                "frame_confirmed": int(t * 10) + 2, "confidence": 0.9,
            })
            self.cur[name] = v
        return self


def table(es: EventStream, t=0.0, names=("jakob", "Calling Carl", "Lucky Luna", "Re-raise Ron"), stack=3000):
    for s, n in enumerate(names):
        es.at(t, **{f"seat__{s}__present": True, f"seat__{s}__name": n, f"seat__{s}__stack": stack,
                    f"seat__{s}__bet": 0, f"seat__{s}__folded": False})
    return es


def standard_hand(es: EventStream, t0=0.0, hand_no=1, skip_hero_flop=False):
    ' Dealer 0 (Hero), SB 1, BB 2, seat 3 UTG. Blinds 10/20.\n    Preflop: 3 fold, 0 call, 1 raise to 60, 2 fold, 0 call.\n    Flop: 1 check, 0 bet 100, 1 fold. Hero wins 240.'
    T = lambda d: t0 + d
    es.at(T(0.0), marker__D=0, marker__SB=1, marker__BB=2, info__blinds=[10, 20])
    es.at(T(0.1), info__game_hand=[1, hand_no], info__street="preflop", board__count=0)
    es.at(T(0.3), seat__1__bet=10, seat__1__stack=2990)
    es.at(T(0.35), seat__2__bet=20, seat__2__stack=2980)
    es.at(T(1.0), seat__3__active=True)
    es.at(T(1.5), seat__3__folded=True)
    es.at(T(1.6), seat__3__active=False)
    es.at(T(2.0), hero__to_act=True)
    es.at(T(2.5), seat__0__bet=20, seat__0__stack=2980)
    es.at(T(2.6), hero__to_act=False)
    es.at(T(3.0), seat__1__active=True)
    es.at(T(3.5), seat__1__bet=60, seat__1__stack=2940)
    es.at(T(3.6), seat__1__active=False)
    es.at(T(4.0), seat__2__active=True)
    es.at(T(4.5), seat__2__folded=True)
    es.at(T(4.6), seat__2__active=False)
    es.at(T(5.0), hero__to_act=True)
    es.at(T(5.4), seat__0__bet=60, seat__0__stack=2940)
    es.at(T(5.5), hero__to_act=False)
    es.at(T(6.0), board__count=3, board__cards=["Ah", "7c", "2d", None, None], info__street="flop",
          seat__0__bet=0, seat__1__bet=0, seat__2__bet=0, pot__total=140)
    es.at(T(7.0), seat__1__active=True)
    es.at(T(7.6), seat__1__active=False)
    if not skip_hero_flop:
        es.at(T(8.0), hero__to_act=True)
        es.at(T(8.4), seat__0__bet=100, seat__0__stack=2840)
        es.at(T(8.6), hero__to_act=False)
    es.at(T(9.0), seat__1__active=True)
    es.at(T(9.5), seat__1__folded=True)
    es.at(T(9.6), seat__1__active=False)
    es.at(T(10.0), seat__0__stack=3080 if not skip_hero_flop else 2980, seat__0__bet=0)
    return es

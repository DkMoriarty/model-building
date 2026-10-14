"""Exact physics plans for FIRST GAME's computer-world rounds and the race.

World units; y grows downward; gravity G. Every function returns event
times plus the numbers the scene draws from, and asserts that the story's
outcomes (a clean jump, a clipped block, a near miss, a car over the edge)
follow from the physics rather than from a hand-placed pose.
"""

from __future__ import annotations

import math

G = 1800.0
JUMP = -900.0          # jump speed, as typed in the game's code
PELVIS = 105.0         # pelvis above the feet for a standing Spark
BLOCK = 70.0           # runner block: 70 x 70


def runner(t0: float, x0: float, legs: list[tuple[float, float, str]]) -> dict:
    """
    Spark runs right from x0 at t0. `legs` = (run time before the jump, speed,
    outcome): outcome 'clear' places a block so the jump clears it with room
    to spare; 'clip' places it so the feet clip its top front corner (the
    stumble: forward roll, 1.2 s on the ground, then up and running).
    Returns segments of x(t) and the blocks.
    """
    t, x = t0, x0
    events, blocks, segs = [], [], []
    for i, (run, v, outcome) in enumerate(legs):
        segs.append({"t": round(t, 4), "x": round(x, 2), "v": v, "until": round(t + run, 4), "kind": "run"})
        t += run
        x += v * run
        # Feet height above the ground during a jump: h(s) = -JUMP s - G s^2 / 2.
        air = 2 * -JUMP / G
        if outcome == "clear":
            # Put the block where the feet are highest: centred under the apex.
            xb = x + v * air / 2 - BLOCK / 2
            h_in = -JUMP * ((xb - x) / v) - G * ((xb - x) / v) ** 2 / 2
            assert h_in > BLOCK + 20, "the jump must clear the block's front edge"
            events.append({"kind": "jump", "t": round(t, 4), "x": round(x, 2)})
            segs.append({"t": round(t, 4), "x": round(x, 2), "v": v, "until": round(t + air, 4), "kind": "jump"})
            blocks.append({"x": round(xb, 2), "i": i})
            t += air
            x += v * air
            events.append({"kind": "land", "t": round(t, 4), "x": round(x, 2)})
        else:
            # A late jump: the block's front edge is reached while the feet are still low.
            s_hit = 0.05
            xb = x + v * s_hit
            h = -JUMP * s_hit - G * s_hit**2 / 2
            assert h < BLOCK - 20, "a clip must really hit the block"
            events.append({"kind": "jump", "t": round(t, 4), "x": round(x, 2)})
            events.append({"kind": "clip", "t": round(t + s_hit, 4), "x": round(xb, 2)})
            blocks.append({"x": round(xb + 4, 2), "i": i})
            # Forward roll over the block, down the far side, 1.2 s to recover.
            segs.append({"t": round(t, 4), "x": round(x, 2), "v": v * 0.5, "until": round(t + 1.2, 4), "kind": "tumble"})
            t += 1.2
            x += v * 0.5 * 1.2
            events.append({"kind": "up", "t": round(t, 4), "x": round(x, 2)})
    segs.append({"t": round(t, 4), "x": round(x, 2), "v": legs[-1][1], "until": round(t + 1.2, 4), "kind": "run"})
    events.append({"kind": "finish", "t": round(t + 1.2, 4), "x": round(x + legs[-1][1] * 1.2, 2)})
    return {"segments": segs, "events": events, "blocks": blocks}


def dodge(t0: float, drops: list[tuple[float, float]], floor: float = 300.0, top: float = -720.0, size: float = 80.0, react: float = 0.2, half: float = 520.0, aim: bool = False) -> dict:
    """
    Blocks fall from rest at `top` and land on `floor` after sqrt(2 d / G);
    a warning mark shows where, from the moment it drops. `drops` = (drop
    time after t0, x). Spark reacts `react` s after each warning: if the
    block would land within reach of where Spark stands, Spark moves to the
    nearest safe spot (running at 360 u/s, or diving at 900 u/s when running
    can't make it in time). Every landing is checked to miss Spark by at least
    size/2 + 30. The closest call is reported as the near miss.

    With `aim`, each drop's x is an offset from where Spark is standing when
    it drops: the Shadow aims at him, so he has to keep moving.
    """
    fall = math.sqrt(2 * (floor - size / 2 - top) / G)
    safe = size / 2 + 60
    pending = sorted(((t0 + dt, bx) for dt, bx in drops))
    landings = [(td + fall, bx) for td, bx in pending]

    def pos(moves: list[dict], t: float) -> float:
        xx = 0.0
        for m in moves:
            if t >= m["until"]:
                xx = m["to"]
            elif t >= m["t"]:
                u = (t - m["t"]) / (m["until"] - m["t"])
                xx = m["from"] + (m["to"] - m["from"]) * u
        return xx

    def all_safe(moves: list[dict], after: float) -> bool:
        return all(abs(pos(moves, ot) - ox) >= size / 2 + 30 for ot, ox in landings if ot >= after - 1e-9)

    moves: list[dict] = []
    if aim:
        aimed = []
        for td, off in pending:
            # Aim at where Spark is (decided incrementally, one drop at a time).
            landings = [(t + fall, x) for t, x in aimed]
            bx = max(-half + 40, min(half - 40, pos(moves, td) + off))
            aimed.append((td, bx))
            landings.append((td + fall, bx))
            tl = td + fall
            if all_safe(moves, td):
                continue
            start = max(td + react, moves[-1]["until"] if moves else t0)
            x = pos(moves, start)
            options = []
            for dx in range(-int(half), int(half) + 1, 20):
                tx = float(dx)
                d = abs(tx - x)
                for kind, speed in (("run", 360.0), ("dive", 900.0)):
                    end = start + d / speed
                    if end > tl - 0.02:
                        continue
                    trial = moves + [{"t": round(start, 4), "from": round(x, 2), "to": tx, "until": round(end, 4), "kind": kind}]
                    if all_safe(trial, td):
                        options.append((d + (0 if kind == "run" else 1e6), trial))
                        break
            assert options, f"no safe move for the block at {bx}"
            moves = min(options, key=lambda o: o[0])[1]
        pending = aimed
        landings = [(td + fall, bx) for td, bx in pending]
    for td, bx in ([] if aim else pending):
        tl = td + fall
        if all_safe(moves, td):
            continue
        start = max(td + react, moves[-1]["until"] if moves else t0)
        x = pos(moves, start)
        options = []
        for dx in range(-int(half), int(half) + 1, 20):
            tx = float(dx)
            d = abs(tx - x)
            for kind, speed in (("run", 360.0), ("dive", 900.0)):
                end = start + d / speed
                if end > tl - 0.02:
                    continue
                trial = moves + [{"t": round(start, 4), "from": round(x, 2), "to": tx, "until": round(end, 4), "kind": kind}]
                if all_safe(trial, td):
                    options.append((d + (0 if kind == "run" else 1e6), trial))
                    break
        assert options, f"no safe move for the block at {bx}"
        moves = min(options, key=lambda o: o[0])[1]

    def spark_x(t: float) -> float:
        return pos(moves, t)

    blocks, events = [], []
    for i, (td, bx) in enumerate(pending):
        tl = td + fall
        gap = abs(spark_x(tl) - bx)
        assert gap >= size / 2 + 30, f"block {i} lands on Spark (gap {gap:.0f})"
        blocks.append({"drop": round(td, 4), "land": round(tl, 4), "x": bx, "gap": round(gap, 1)})
        events.append({"kind": "drop", "t": round(td, 4), "x": bx})
        events.append({"kind": "land", "t": round(tl, 4), "x": bx, "gap": round(gap, 1)})
    near = min(blocks, key=lambda b: b["gap"])
    return {"moves": moves, "blocks": blocks, "events": events, "fall": round(fall, 4), "top": top, "floor": floor, "size": size, "nearMiss": near}


CAR_HALF = 110.0       # half a car's length (Spark's and the red ones)


def race(t0: float) -> dict:
    """
    Side-on race on a two-lane road (near lane: Spark; far lane: room to
    overtake) to a broken bridge, then a ramp jump over the gap.

    Spark accelerates at 600 u/s^2 to 900 u/s. Two red cars come from behind
    at 1100 u/s; each bump is a rear collision between equal masses with
    restitution 0.5 (Spark gains speed, the rammer loses it), after which the
    rammer pulls into the far lane and Spark eases back to 900. At the edge
    Spark brakes at 1400 u/s^2 and stops with his front bumper 60 units short
    of the lip; the red cars in the far lane react 0.25 s later and brake at
    900 u/s^2, but their stopping distance is longer than the road they have,
    so both go over. Then Spark backs up, takes an 800-unit run at the lip
    (a 25 degree kicker) and jumps the gap; the key hangs 900 units past the
    landing, the door 970 units after that, where he stops.

    Positions are car centres along the road, from Spark's start (x = 0).
    Every phase is constant acceleration (x = x0 + v0 s + a s^2 / 2), a
    smooth hand-off (cubic Hermite between two (x, v) states), or flight.
    """
    ev: dict[str, float] = {}
    spark: list[dict] = []

    def acc(t: float, dur: float, x0: float, v0: float, a: float) -> tuple[float, float]:
        spark.append({"kind": "acc", "t": round(t, 4), "until": round(t + dur, 4), "x0": round(x0, 3), "v0": round(v0, 3), "a": a})
        return x0 + v0 * dur + a * dur * dur / 2, v0 + a * dur

    a = 600.0
    ev["go"] = t0
    x, v = acc(t0, 1.5, 0.0, 0.0, a)
    ev["cruise"] = t0 + 1.5
    ev["bump1"] = ev["cruise"] + 1.6
    x, v = acc(ev["cruise"], 1.6, x, v, 0.0)
    e = 0.5

    def bump(u_s: float, u_r: float) -> tuple[float, float]:
        return (u_s + u_r + e * (u_r - u_s)) / 2, (u_s + u_r - e * (u_r - u_s)) / 2

    # Red car A rams at 1100 u/s, red car B at 1150.
    rams = {"A": 1100.0, "B": 1150.0}
    v_s, v_rA = bump(v, rams["A"])
    x_b1 = x
    # Spark lifts off the throttle: back to 900 u/s at 250 u/s^2.
    t_ease = (v_s - 900.0) / 250.0
    x, v = acc(ev["bump1"], t_ease, x, v_s, -250.0)
    ev["bump2"] = ev["bump1"] + 1.4
    x, v = acc(ev["bump1"] + t_ease, 1.4 - t_ease, x, v, 0.0)
    v_s2, v_rB = bump(v, rams["B"])
    x_b2 = x
    ev["brake"] = ev["bump2"] + 1.2
    x, v = acc(ev["bump2"], 1.2, x, v_s2, 0.0)
    x_brake = x
    brake = 1400.0
    t_stop = v_s2 / brake
    ev["stop"] = ev["brake"] + t_stop
    x, v = acc(ev["brake"], t_stop, x, v_s2, -brake)
    x_stop = x
    lip = x_stop + CAR_HALF + 60  # the lip of the kicker: Spark's centre is here at take-off
    d_stop = x_stop - x_brake

    # After ramming, each red car pulls into the far lane and speeds up to
    # draw level: A almost alongside Spark when he brakes, B a car behind it,
    # both at 1050 u/s. They react 0.25 s later and brake at 900 u/s^2.
    react, red_brake = 0.25, 900.0
    reds = []
    for name, behind, vb, bt, xb, v_after in (("A", 60.0, 1050.0, ev["bump1"], x_b1, v_rA), ("B", 360.0, 1100.0, ev["bump2"], x_b2, v_rB)):
        xc = x_brake - behind  # centre at the brake
        room = lip - (xc + CAR_HALF)
        need = vb * react + vb * vb / (2 * red_brake)
        assert need > room + 40, f"red car {name} must not be able to stop ({need:.0f} vs {room:.0f})"
        rest = room - vb * react
        v_edge = math.sqrt(vb * vb - 2 * red_brake * rest)
        t_edge = react + (vb - v_edge) / red_brake
        u_r = rams[name]
        phases = [
            {"kind": "acc", "t": round(bt - 6.0, 4), "until": round(bt, 4), "x0": round(xb - 2 * CAR_HALF - u_r * 6.0, 3), "v0": u_r, "a": 0.0},
            {"kind": "hermite", "t": round(bt, 4), "until": round(ev["brake"], 4), "x0": round(xb - 2 * CAR_HALF, 3), "v0": round(v_after, 3), "x1": round(xc, 3), "v1": vb},
            {"kind": "acc", "t": round(ev["brake"], 4), "until": round(ev["brake"] + react, 4), "x0": round(xc, 3), "v0": vb, "a": 0.0},
            {"kind": "acc", "t": round(ev["brake"] + react, 4), "until": round(ev["brake"] + t_edge, 4), "x0": round(xc + vb * react, 3), "v0": vb, "a": -red_brake},
        ]
        # Over the lip at the kicker's 25 degrees, then a free fall into the gap.
        ang = math.radians(25)
        phases.append({"kind": "fly", "t": round(ev["brake"] + t_edge, 4), "until": round(ev["brake"] + t_edge + 1.6, 4), "x0": round(lip - CAR_HALF, 3), "vx": round(v_edge * math.cos(ang), 3), "vy": round(-v_edge * math.sin(ang), 3)})
        span = (v_edge * math.cos(ang)) * 2 * v_edge * math.sin(ang) / G
        assert span < 520 - 2 * CAR_HALF, "a red car must fall short of the far side"
        lanes = [{"t": round(bt + 0.1, 4), "to": 1, "d": 0.35}]
        reds.append({"name": name, "phases": phases, "lanes": lanes, "overEdge": round(ev["brake"] + t_edge, 4), "vEdge": round(v_edge, 2), "room": round(room, 2), "need": round(need, 2), "ram": u_r, "after": round(v_after, 2)})
    ev["overEdge"] = min(r["overEdge"] for r in reds)
    ev["overEdge2"] = max(r["overEdge"] for r in reds)
    ev["fallGone"] = ev["overEdge2"] + 1.0
    # Spark backs up so that an 800-unit run ends on the lip.
    ev["reverse"] = ev["fallGone"] + 0.4
    run_from = lip - 800.0
    spark.append({"kind": "ease", "t": round(ev["stop"], 4), "until": round(ev["reverse"], 4), "x0": round(x_stop, 3), "x1": round(x_stop, 3)})
    ev["run"] = ev["reverse"] + 2.4
    spark.append({"kind": "ease", "t": round(ev["reverse"], 4), "until": round(ev["run"], 4), "x0": round(x_stop, 3), "x1": round(run_from, 3)})
    run_a = 1200.0
    t_run = math.sqrt(2 * 800 / run_a)
    v_take = run_a * t_run
    ev["ramp"] = ev["run"] + t_run
    acc(ev["run"], t_run, run_from, 0.0, run_a)
    ang = math.radians(25)
    vx, vy = v_take * math.cos(ang), -v_take * math.sin(ang)
    t_fly = 2 * -vy / G
    span = vx * t_fly
    assert span > 520 + 2 * CAR_HALF, f"the jump must clear the gap (span {span:.0f})"
    ev["landJump"] = ev["ramp"] + t_fly
    spark.append({"kind": "fly", "t": round(ev["ramp"], 4), "until": round(ev["landJump"], 4), "x0": round(lip, 3), "vx": round(vx, 3), "vy": round(vy, 3)})
    x_land = lip + span
    # Landing: the suspension takes the vertical speed; the horizontal speed carries on.
    acc(ev["landJump"], 900 / vx, x_land, vx, 0.0)
    ev["key"] = ev["landJump"] + 900 / vx
    x_key = x_land + 900
    dec = vx / 1.4
    acc(ev["key"], 1.4, x_key, vx, -dec)
    ev["doorArrive"] = ev["key"] + 1.4
    x_door = x_key + vx * 1.4 / 2
    return {
        "events": {k: round(t, 4) for k, t in ev.items()},
        "spark": spark,
        "reds": reds,
        "numbers": {
            "carHalf": CAR_HALF, "accel": a, "cruise": 900.0, "afterBump1Spark": v_s, "afterBump2Spark": v_s2,
            "brake": brake, "dStop": d_stop, "xStop": x_stop, "lip": lip, "gap": 520.0, "takeoff": v_take, "rampAngle": 25,
            "span": span, "flight": t_fly, "xLand": x_land, "xKey": x_key, "xDoor": x_door, "g": G,
        },
    }

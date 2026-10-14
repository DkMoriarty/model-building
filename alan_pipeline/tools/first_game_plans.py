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


def race(t0: float) -> dict:
    """
    Side-on race on a straight road to a cliff edge, then a ramp jump.

    Spark accelerates at 600 u/s^2 to 900 u/s. Two red cars come from behind
    at 1100 u/s; each bump is a collision between equal masses with
    restitution 0.5 (Spark gains speed, the rammer loses it). At the edge
    Spark brakes at 1400 u/s^2 and stops 60 units short; the red cars, still
    closing at speed and braking only at 900 u/s^2, cannot stop in time and
    go over (stopping distance v^2 / 2a > the room they have). Then Spark
    backs up, takes a run at the ramp, and jumps the gap.
    """
    ev = {}
    # Spark: 0 -> 900 u/s over 1.5 s (600 u/s^2), then cruise.
    a = 600.0
    ev["go"] = t0
    ev["cruise"] = t0 + 1.5
    x_cruise = 0.5 * a * 1.5**2  # 675
    v = 900.0
    # Bumps: rammers at 1100 u/s, equal mass, restitution e = 0.5.
    e = 0.5
    u_r, u_s = 1100.0, 900.0
    v_s = (u_s + u_r + e * (u_r - u_s)) / 2      # Spark after the bump
    v_r = (u_s + u_r - e * (u_r - u_s)) / 2      # rammer after
    ev["bump1"] = ev["cruise"] + 1.6
    ev["bump2"] = ev["bump1"] + 1.4
    # After the bumps Spark is moving at v_s (1050); the edge lies ahead.
    # Spark brakes at 1400 u/s^2: stopping distance v^2 / 2a.
    brake = 1400.0
    d_stop = v_s**2 / (2 * brake)
    t_stop = v_s / brake
    ev["brake"] = ev["bump2"] + 1.2
    ev["stop"] = ev["brake"] + t_stop
    # The red cars are 140 units behind Spark when he brakes, at 1000 u/s, and
    # react 0.25 s later, braking at 900 u/s^2.
    gap_behind, v_red, react, red_brake = 140.0, 1000.0, 0.25, 900.0
    room = gap_behind + d_stop + 60  # to the edge
    red_need = v_red * react + v_red**2 / (2 * red_brake)
    assert red_need > room + 100, "the red cars must not be able to stop"
    # The red car reaches the edge when v_red t - red_brake (t - react)^2 / 2 = room.
    t_edge = react
    while v_red * t_edge - 0.5 * red_brake * max(0.0, t_edge - react) ** 2 < room:
        t_edge += 1 / 600
    v_edge = v_red - red_brake * (t_edge - react)
    ev["overEdge"] = ev["brake"] + t_edge
    # Ballistic fall into the void: gone from frame after ~1 s.
    ev["fallGone"] = ev["overEdge"] + 1.0
    # Spark backs up 800 units (2.4 s), then takes a run: 0 -> 1386 u/s at 1200 u/s^2 over 800 units.
    ev["reverse"] = ev["fallGone"] + 0.6
    ev["run"] = ev["reverse"] + 2.4
    t_run = math.sqrt(2 * 800 / 1200.0)
    v_take = 1200.0 * t_run
    ev["ramp"] = ev["run"] + t_run
    # The ramp launches at 25 degrees; gap 520 units; land on the far side, same height.
    ang = math.radians(25)
    vx, vy = v_take * math.cos(ang), -v_take * math.sin(ang)
    t_fly = 2 * -vy / G
    span = vx * t_fly
    assert span > 520 + 120, f"the jump must clear the gap (span {span:.0f})"
    ev["landJump"] = ev["ramp"] + t_fly
    # On to the key, 900 units further at v_take.
    ev["key"] = ev["landJump"] + 900 / v_take
    ev["doorArrive"] = ev["key"] + 1.4
    return {
        "events": {k: round(t, 4) for k, t in ev.items()},
        "numbers": {
            "accel": a, "cruise": v, "xCruise": x_cruise, "rammer": u_r, "afterBumpSpark": v_s, "afterBumpRammer": v_r,
            "brake": brake, "dStop": d_stop, "redSpeed": v_red, "redBrake": red_brake, "room": room, "redNeed": red_need,
            "vEdge": v_edge, "takeoff": v_take, "rampAngle": 25, "span": span, "flight": t_fly, "gap": 520,
        },
    }

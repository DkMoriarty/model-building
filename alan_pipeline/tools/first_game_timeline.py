#!/usr/bin/env python3
"""Build audio/first_game/story.json: FIRST GAME, timed by real physics.

    python tools/first_game_timeline.py && python tools/build_space_audio.py --episode first_game

Spark codes a first program (hello world), invents ping pong line by line,
plays it, falls asleep, and wakes up inside it. Every ball flight comes from
tools/pong.py: constant speed, true wall reflections, 1.5x speed per hit,
collisions checked once per frame (so a fast enough ball really can skip
through a paddle). Typing runs at 12 characters a second, one click per
character. The code, the rallies and the constants are written into
story.json, passed through to cues.json, and drawn by the scene as is.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pong  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CPS = 12.0
ENTER = 0.1

CODE = {
    "c1": 'print("hello world")',
    "c2": "ball = circle(0, 0)",
    "c3": "ball.move(300, 200)",
    "c4": "bounce(ball, walls)",
    "c5": "paddle = bar(-560)",
    "c6": "ball.speed = 3000",
    "c7": "ball.speed = 600",
    "c8": "cpu = bar(560)",
    "c9": "ball.onHit = v => v*1.5",
    "c10": "cpu.speed = 99",
}


def box_bounce(t0: float, x: float, y: float, vx: float, vy: float, until: float, walls_x: bool = True) -> tuple[list[dict], list[float]]:
    """A ball in a closed box (all four walls), from t0 to `until`."""
    segs, hits = [], []
    lim_y = pong.WALL - pong.BALL_R
    lim_x = 640 - pong.BALL_R
    t = t0
    while t < until - 1e-9:
        tx = ((lim_x if vx > 0 else -lim_x) - x) / vx if (walls_x and vx) else math.inf
        ty = ((lim_y if vy > 0 else -lim_y) - y) / vy if vy else math.inf
        dt = min(tx, ty, until - t)
        segs.append({"t": round(t, 5), "x": round(x, 3), "y": round(y, 3), "vx": vx, "vy": vy, "until": round(t + dt, 5)})
        x += vx * dt
        y += vy * dt
        t += dt
        if t >= until - 1e-9:
            break
        hits.append(round(t, 5))
        if dt == tx:
            vx = -vx
        else:
            vy = -vy
    return segs, hits


def main() -> None:
    E: dict[str, float] = {}
    S: list[dict] = []
    R: dict[str, dict] = {}

    def ev(name: str, t: float) -> float:
        E[name] = round(t, 4)
        return E[name]

    def sfx(kind: str, at: str, **kw) -> None:
        S.append({"type": kind, "at": at, **kw})

    def typing(cue: str, start: float) -> float:
        text = CODE[cue]
        ev(cue, start)
        for i in range(len(text)):
            sfx("key", cue, offset=round(i / CPS, 4), gain=0.5)
        enter = ev(cue + "Enter", start + len(text) / CPS)
        sfx("enter", cue + "Enter")
        return ev(cue + "Run", enter + ENTER)

    def rally(name: str, r: pong.Rally, volume: float = 1.0) -> float:
        """Register a rally: segments for the picture, a sound for every bounce."""
        R[name] = {"segments": r.segments, "events": [{"kind": k, "t": round(t, 5), **{a: round(b, 3) for a, b in d.items()}} for k, t, d in r.events]}
        n = {"hit": 0, "wall": 0}
        for k, t, d in r.events:
            if k in ("hit", "wall", "tunnel", "goal", "serve"):
                key = f"{name}_{k}{n.get(k, 0)}"
                n[k] = n.get(k, 0) + 1
                ev(key, t)
                kind = {"hit": "pong", "wall": "wallbeep", "tunnel": "glitch", "goal": "score", "serve": "pong"}[k]
                sfx(kind, key, gain=volume)
        return r.t

    # ---- the want: NO GAME
    for k, t in [("open", 0.0), ("press1", 2.4), ("press2", 3.6), ("press3", 4.8), ("slump", 5.7), ("lookKeys", 7.2), ("idea", 8.4), ("title", 9.6), ("titleOut", 12.6)]:
        ev(k, t)
    for k in ["press1", "press2", "press3"]:
        sfx("click", k, gain=0.6)
        sfx("beep", k, offset=0.05, gain=0.6)
    sfx("click", "idea", gain=0.6)

    # ---- close on the screen: code above, output below
    ev("zoomCode", 13.0)
    t = typing("c1", 13.6)
    sfx("blip", "c1Run", gain=0.5)
    ev("smile", t + 0.8)
    t = typing("c2", t + 1.8)
    sfx("pop", "c2Run", gain=0.4)
    t = typing("c3", t + 1.2)
    # ball.move(300, 200): it drifts down-right and leaves the screen.
    exit_t = (pong.WALL + 20) / 200
    R["move"] = {"segments": [{"t": t, "x": 0, "y": 0, "vx": 300, "vy": 200, "until": round(t + exit_t, 5)}], "events": []}
    ev("ballGone", t + exit_t)
    ev("whereGone", E["ballGone"] + 0.3)
    t = typing("c4", E["whereGone"] + 1.4)
    segs, hits = box_bounce(t, 0, 0, 300, 200, t + 4.0)
    R["box"] = {"segments": segs, "events": [{"kind": "wall", "t": h} for h in hits]}
    for i, h in enumerate(hits):
        ev(f"box_wall{i}", h)
        sfx("wallbeep", f"box_wall{i}", gain=0.7)
    ev("hypno", t + 1.6)
    t = typing("c5", t + 4.0)
    sfx("pop", "c5Run", gain=0.4)
    # The paddle: Spark plays it with the arrow keys. The right side is still a wall.
    segs, hits = box_bounce(t + 0.4, 300, -100, -600, 60, t + 0.4 + (300 - (-pong.PADDLE_X + pong.PADDLE_HALF_W + pong.BALL_R)) / 600, walls_x=False)
    t_hit = segs[-1]["until"]
    y_hit = segs[-1]["y"] + segs[-1]["vy"] * (t_hit - segs[-1]["t"])
    segs2, hits2 = box_bounce(t_hit, -pong.PADDLE_X + pong.PADDLE_HALF_W + pong.BALL_R, y_hit, 600, 160, t_hit + 2.2)
    R["paddle"] = {"segments": segs + segs2, "events": [{"kind": "hit", "t": t_hit, "side": -1, "y": round(y_hit, 3)}] + [{"kind": "wall", "t": h} for h in hits + hits2]}
    ev("paddleHit", t_hit)
    sfx("pong", "paddleHit")
    for i, h in enumerate(hits + hits2):
        ev(f"paddle_wall{i}", h)
        sfx("wallbeep", f"paddle_wall{i}", gain=0.7)
    ev("nod", t_hit + 0.4)
    # ball.speed = 3000: at 50 units a frame the ball skips over the 12-unit paddle.
    t = typing("c6", t_hit + 2.6)
    r = pong.find(t + 0.3, +1, 0, [("serve", 4), ("tunnel", 0)], speed0=3000, speeds=(0, 0))
    end = rally("glitch", r)
    ev("doubleTake", end + 0.3)
    ev("laughG", E["doubleTake"] + 1.0)
    t = typing("c7", E["laughG"] + 1.2)
    t = typing("c8", t + 0.8)
    sfx("pop", "c8Run", gain=0.4)
    t = typing("c9", t + 1.0)
    ev("ahHa", t + 0.4)
    # Pull back: Spark plays its first game, and scores.
    ev("zoomOut", t + 1.4)
    play = ev("play", E["zoomOut"] + 1.0)
    r = pong.find(play + 0.3, +1, 0, [("serve", 12), ("hit", -18), ("hit", 22), ("hit", 34), ("miss", 0)], speeds=(pong.REACH, 80))
    end = rally("first", r)
    ev("point1", end)
    ev("cheer", end + 0.3)

    # ---- into the night: an unbeatable opponent
    ev("zoomCode2", E["cheer"] + 2.0)
    t = typing("c10", E["zoomCode2"] + 0.6)
    ev("grin", t + 0.6)
    ev("clock1", E["grin"] + 1.4)
    sfx("tick", "clock1")
    play2 = ev("play2", E["clock1"] + 1.6)
    r = pong.find(play2 + 0.3, +1, 0, [("serve", -14), ("hit", 30), ("hit", -20), ("hit", 25), ("hit", -38), ("miss", 0)], speeds=(pong.REACH, 99 * 60))
    end = rally("lose", r)
    ev("gameOverMini", end + 0.3)
    sfx("gameover", "gameOverMini", gain=0.7)
    ev("laugh", end + 0.9)
    ev("yawn", E["laugh"] + 1.8)
    ev("droop", E["yawn"] + 1.8)
    ev("pull", E["droop"] + 1.2)
    sfx("riser", "pull", length=1.2, gain=0.6)
    ev("suck", E["pull"] + 1.2)
    sfx("whoosh", "suck")
    ev("inside", E["suck"] + 1.4)
    sfx("thud", "inside")

    # ---- inside the game: Spark is the left paddle
    ev("lookHands", E["inside"] + 1.0)
    ev("lookBack", E["lookHands"] + 1.2)
    ev("seeDoor", E["lookBack"] + 1.8)
    # Level 1: a slow opponent. One point wins it.
    l1 = ev("l1", E["seeDoor"] + 1.6)
    r = pong.find(l1 + 0.6, -1, 0, [("serve", -10), ("hit", 15), ("hit", 34), ("miss", 0)], speeds=(pong.REACH, 70))
    end = rally("l1", r)
    ev("clear1", end + 0.2)
    sfx("fanfare", "clear1")
    ev("wipe1", E["clear1"] + 1.4)
    sfx("whoosh", "wipe1", gain=0.5)
    # Level 2: faster. One point.
    l2 = ev("l2", E["wipe1"] + 0.6)
    r = pong.find(l2 + 0.8, +1, 40, [("serve", 16), ("hit", -26), ("hit", 20), ("hit", -36), ("miss", 0)], speeds=(pong.REACH, 130))
    end = rally("l2", r)
    ev("clear2", end + 0.2)
    sfx("fanfare", "clear2")
    ev("wipe2", E["clear2"] + 1.4)
    sfx("whoosh", "wipe2", gain=0.5)
    # Level 3: the unbeatable paddle (cpu.speed = 99). First to three.
    l3 = ev("l3", E["wipe2"] + 0.6)
    ev("gulp", l3 + 1.0)
    p1 = ev("p1", E["gulp"] + 1.4)
    r = pong.find(p1 + 0.3, +1, 0, [("serve", 18), ("hit", -20), ("hit", 25), ("hit", -15), ("hit", 40), ("miss", 0)], speeds=(pong.REACH, 99 * 60))
    end = rally("p1", r)
    ev("react1", end + 0.6)
    p2 = ev("p2", E["react1"] + 1.4)
    r = pong.find(p2 + 0.3, +1, -60, [("serve", -16), ("hit", 22), ("hit", -25), ("hit", 18), ("hit", -42), ("miss", 0)], speeds=(pong.REACH, 99 * 60))
    end = rally("p2", r)
    ev("react2", end + 0.6)
    p3 = ev("p3", E["react2"] + 1.6)
    # Spark reaches every ball this time... and the fast one goes straight through.
    r = pong.find(p3 + 0.3, +1, 0, [("serve", 20), ("hit", -25), ("hit", 30), ("hit", -20), ("hit", 15), ("tunnel", 0)], speeds=(pong.REACH, 99 * 60))
    end = rally("p3", r)
    ev("gameOver", end + 0.4)
    sfx("gameover", "gameOver")
    ev("stare", E["gameOver"] + 0.8)
    ev("slumpGO", E["stare"] + 1.6)
    ev("count3", E["slumpGO"] + 2.4)
    ev("count2", E["count3"] + 1.2)
    ev("memory", E["count2"] + 0.3)
    ev("count1", E["count2"] + 1.2)
    for k in ["count3", "count2", "count1"]:
        sfx("tick", k, gain=0.9)
    sfx("glitch", "memory", gain=0.6)
    ev("press", E["count1"] + 0.6)
    sfx("oneup", "press")
    # The plan: Spark serves, so the fifth, fastest hit is Spark's.
    p4 = ev("p4", E["press"] + 1.6)
    r = pong.find(p4 + 0.6, -1, 0, [("serve", -20), ("hit", 25), ("hit", -30), ("hit", 20), ("hit", -10), ("tunnel", 0)], speeds=(pong.REACH, 99 * 60))
    end = rally("p4", r)
    ev("door", end + 0.1)
    sfx("fanfare", "door", gain=1.1)

    # ---- the dream breaks
    ev("crack", E["door"] + 1.4)
    ev("crack2", E["crack"] + 0.6)
    ev("shatter", E["crack2"] + 0.6)
    for k in ["crack", "crack2"]:
        sfx("crack", k)
    sfx("shatter", "shatter")
    sfx("boom", "shatter", gain=0.6)

    # ---- awake: the same plan, on the real screen
    ev("wake", E["shatter"] + 2.4)
    sfx("thud", "wake", gain=0.6)
    ev("clock3", E["wake"] + 1.2)
    sfx("tick", "clock3")
    ev("lookScreen", E["clock3"] + 1.2)
    ev("grinKnow", E["lookScreen"] + 1.2)
    ev("grab", E["grinKnow"] + 1.2)
    sfx("click", "grab", gain=0.5)
    m = ev("final", E["grab"] + 1.2)
    r = pong.find(m + 0.6, -1, 0, [("serve", -20), ("hit", 25), ("hit", -30), ("hit", 20), ("hit", -10), ("tunnel", 0)], speeds=(pong.REACH, 99 * 60))
    end = rally("final", r, 0.8)
    ev("win", end + 0.1)
    sfx("fanfare", "win")
    ev("leapChair", E["win"] + 0.6)
    sfx("thud", "leapChair", gain=0.5)
    ev("cheer2", E["leapChair"] + 1.2)
    ev("end", E["cheer2"] + 3.0)
    duration = round(E["end"] + 1.6, 1)

    M = [
        {"section": "night", "from": 0, "to": E["zoomCode"]},
        {"section": "code", "from": E["zoomCode"], "to": E["pull"]},
        {"section": "chip", "from": E["inside"], "to": E["l3"]},
        {"section": "chipTense", "from": E["l3"], "to": E["gameOver"]},
        {"section": "chipFinal", "from": E["press"], "to": E["crack"]},
        {"section": "morning", "from": E["wake"], "to": duration},
    ]
    impacts = ["press1", "press2", "press3", "idea", "c1Run", "c2Run", "c5Run", "c8Run", "paddleHit", "box_", "paddle_", "glitch_", "first_", "lose_", "l1_", "l2_", "p1_", "p2_", "p3_", "p4_", "final_", "clear", "gameOver", "suck", "inside", "count", "memory", "press", "door", "crack", "shatter", "wake", "grab", "win", "leapChair", "clock"]
    story = {
        "title": "First Game",
        "bpm": 100,
        "sampleRate": 48000,
        "duration": duration,
        "voices": {},
        "lines": [],
        "events": E,
        "sfx": S,
        "music": M,
        "silences": [{"from": E["gameOver"] + 0.6, "to": E["count3"]}, {"from": E["shatter"] + 0.2, "to": E["wake"]}],
        "physics": {"wall": pong.WALL, "ballR": pong.BALL_R, "paddleX": pong.PADDLE_X, "paddleHalfW": pong.PADDLE_HALF_W, "paddleHalfH": pong.PADDLE_HALF_H, "goalX": pong.GOAL_X, "fps": pong.FPS, "reach": pong.REACH},
        "code": CODE,
        "rallies": R,
        "audit": {
            "impacts": impacts,
            "holds": ["title", "slump", "lookKeys", "smile", "whereGone", "hypno", "nod", "doubleTake", "laughG", "ahHa", "cheer", "grin", "laugh", "yawn", "droop", "lookHands", "lookBack", "seeDoor", "gulp", "react1", "react2", "stare", "slumpGO", "grinKnow", "cheer2", "end", "zoomOut", "point1", "l1", "l2", "l3"],
            "declared": [[0, 2.0, "fade in on the dark room"], [E["crack"], E["wake"], "the dream breaks: cracks, shards, white"]],
        },
    }
    (ROOT / "audio/first_game/story.json").write_text(json.dumps(story, indent=1) + "\n")
    print(f"{len(E)} events, {len(S)} sounds, {len(R)} rallies, {duration} s")


if __name__ == "__main__":
    main()

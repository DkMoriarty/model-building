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
import first_game_plans as plans  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CPS = 12.0
ENTER = 0.1

SHADOW = ["YOU BEAT ME.", "NOW PLAY FOR REAL.", "WIN 3 GAMES - GO HOME.", "LOSE - YOU ARE DELETED."]

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
        assert name not in E, f"cue {name} is defined twice"
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

    # ---- the computer loses, and wakes up: it types by itself
    ev("tremble", E["cheer"] + 1.6)
    sfx("glitch", "tremble", gain=0.5)
    ev("zoomCode2", E["tremble"] + 0.8)
    def selftype(cue: str, start: float, text: str) -> float:
        CODE[cue] = text
        ev(cue, start)
        for i in range(len(text)):
            sfx("tick", cue, offset=round(i / CPS, 4), gain=0.45)
        enter = ev(cue + "Enter", start + len(text) / CPS)
        sfx("enter", cue + "Enter", gain=0.8)
        return ev(cue + "Run", enter + ENTER)
    t = selftype("s1", E["zoomCode2"] + 0.6, "cpu.learn()")
    sfx("blip", "s1Run", gain=0.5)
    ev("handsOff", E["s1"] + 0.3)
    t = selftype("s2", t + 1.0, "cpu.angry = true")
    sfx("boom", "s2Run", gain=0.4)
    t = selftype("s3", t + 1.0, "pull(spark)")
    ev("pull", t)
    sfx("riser", "pull", length=1.2, gain=0.7)
    ev("suck", E["pull"] + 1.2)
    sfx("whoosh", "suck")

    # ---- the binary world
    land = ev("land", E["suck"] + 0.9 + 0.1 + math.sqrt(2 * (195 - -520) / plans.G))
    sfx("thud", "land")
    ev("look", land + 1.0)
    ev("walk", E["look"] + 1.6)
    ev("touch", E["walk"] + 2.6)
    sfx("tick", "touch", gain=0.8)
    sfx("blip", "touch", gain=0.4)
    ev("wonder", E["touch"] + 1.4)
    ev("glitch", E["wonder"] + 2.4)
    sfx("glitch", "glitch", gain=0.8)
    ev("rise", E["glitch"] + 0.3)
    sfx("riser", "rise", length=1.2, gain=0.6)
    ev("eye", E["rise"] + 1.4)
    sfx("violet", "eye", gain=0.7)
    t = E["eye"] + 0.8
    for i, line in enumerate(SHADOW):
        cue = f"say{i + 1}"
        ev(cue, t)
        for k in range(len(line)):
            sfx("tick", cue, offset=round(k / CPS, 4), gain=0.5)
        t += len(line) / CPS + 1.4
    ev("stepBack", E["say4"] + 0.4)
    ev("door0", E["say3"] + 0.6)
    sfx("pop", "door0", gain=0.5)
    ev("setFeet", t - 0.2)
    ev("portal1", E["setFeet"] + 1.2)
    sfx("whoosh", "portal1", gain=0.6)

    # ---- round 1: ping pong against the Shadow (first point lost, second won by the glitch)
    r1 = ev("r1", E["portal1"] + 1.2)
    r = pong.find(r1 + 1.2, +1, 0, [("serve", 18), ("hit", -20), ("hit", 25), ("hit", -15), ("hit", 40), ("miss", 0)], speeds=(pong.REACH, 99 * 60))
    end = rally("r1a", r)
    ev("r1react", end + 0.4)
    r1b = ev("r1b", E["r1react"] + 1.6)
    r = pong.find(r1b + 0.6, -1, 0, [("serve", -20), ("hit", 25), ("hit", -30), ("hit", 20), ("hit", -10), ("tunnel", 0)], speeds=(pong.REACH, 99 * 60))
    end = rally("r1b", r)
    ev("win1", end + 0.1)
    sfx("fanfare", "win1")
    ev("light1", E["win1"] + 1.0)
    sfx("ding", "light1")
    ev("portal2", E["light1"] + 1.2)
    sfx("whoosh", "portal2", gain=0.6)

    # ---- round 2: the runner (speed rising; one late jump clips a block)
    r2 = ev("r2", E["portal2"] + 1.2)
    run = plans.runner(r2 + 1.0, -700, [(1.0, 320, "clear"), (0.7, 320, "clear"), (0.6, 400, "clear"), (0.5, 480, "clip"), (0.6, 480, "clear"), (0.5, 520, "clear")])
    R["runner"] = run
    n = {"jump": 0, "land": 0, "clip": 0, "up": 0}
    for e_ in run["events"]:
        k = e_["kind"]
        if k == "finish":
            ev("win2", e_["t"])
            sfx("fanfare", "win2")
            continue
        key = f"run_{k}{n[k]}"
        n[k] += 1
        ev(key, e_["t"])
        sfx({"jump": "jump8", "land": "thud", "clip": "hurt", "up": "blip"}[k], key, gain={"land": 0.3}.get(k, 0.7))
    ev("light2", E["win2"] + 1.0)
    sfx("ding", "light2")
    ev("portal3", E["light2"] + 1.2)
    sfx("whoosh", "portal3", gain=0.6)

    # ---- round 3: dodge (the Shadow aims every block at Spark)
    r3 = ev("r3", E["portal3"] + 1.2)
    dg = plans.dodge(r3 + 1.0, [(0.4, 0), (1.3, 0), (2.1, 30), (2.8, -20), (3.4, 0), (3.9, 40), (4.5, 0), (5.0, -30), (5.6, 0), (6.1, 20), (6.6, 0), (7.1, -20), (7.5, 0)], aim=True)
    R["dodge"] = dg
    for i, b_ in enumerate(dg["blocks"]):
        ev(f"dodge_drop{i}", b_["drop"])
        sfx("tick", f"dodge_drop{i}", gain=0.6)
        ev(f"dodge_land{i}", b_["land"])
        sfx("thud", f"dodge_land{i}", gain=0.8)
    for i, m_ in enumerate(dg["moves"]):
        if m_["kind"] == "dive":
            ev(f"dodge_dive{i}", m_["t"])
            sfx("whoosh", f"dodge_dive{i}", gain=0.6)
    ev("win3", r3 + 1.0 + 9.0)
    sfx("fanfare", "win3")
    ev("light3", E["win3"] + 1.0)
    sfx("ding", "light3")

    # ---- the key, the car, the race
    ev("keyhole", E["light3"] + 1.2)
    sfx("tick", "keyhole")
    ev("keyShow", E["keyhole"] + 1.2)
    sfx("glitch", "keyShow", gain=0.5)
    ev("keyGlow", E["keyShow"] + 1.0)
    sfx("violet", "keyGlow", gain=0.6)
    ev("point", E["keyShow"] + 2.6)
    ev("car", E["point"] + 1.0)
    sfx("pop", "car", gain=0.5)
    ev("getIn", E["car"] + 1.2)
    sfx("thud", "getIn", gain=0.4)
    rc = plans.race(E["getIn"] + 1.0)
    R["race"] = rc
    for k, tt in rc["events"].items():
        ev(f"race_{k}", tt)
    sfx("riser", "race_go", length=1.5, gain=0.5)
    sfx("thud", "race_bump1", gain=0.9)
    sfx("thud", "race_bump2", gain=0.9)
    sfx("grind", "race_brake", length=0.7, gain=0.6)
    sfx("fall8", "race_overEdge")
    sfx("fall8", "race_overEdge2", gain=0.7)
    sfx("boom", "race_fallGone", gain=0.5)
    sfx("riser", "race_run", length=1.2, gain=0.6)
    sfx("whoosh", "race_ramp")
    sfx("thud", "race_landJump", gain=0.8)
    sfx("oneup", "race_key")
    ev("unlock", E["race_doorArrive"] + 1.0)
    sfx("click", "unlock")
    sfx("ding", "unlock", offset=0.2)
    ev("doorOpen", E["unlock"] + 0.8)
    sfx("riser", "doorOpen", length=0.8, gain=0.4)
    ev("through", E["doorOpen"] + 1.2)
    sfx("whoosh", "through")

    # ---- home: relief, sunrise, and himself
    ev("home", E["through"] + 0.6)
    sfx("thud", "home", gain=0.6)
    ev("relief", E["home"] + 1.0)
    ev("sunrise", E["relief"] + 2.0)
    ev("turn", E["sunrise"] + 2.4)
    ev("see", E["turn"] + 0.8)
    ev("seeTwice", E["see"] + 0.6)
    ev("dissolve", E["seeTwice"] + 1.2)
    sfx("glitch", "dissolve", gain=0.4)
    ev("wakeUp", E["dissolve"] + 0.6)
    sfx("thud", "wakeUp", gain=0.5)
    ev("stretch", E["wakeUp"] + 1.0)
    ev("end", E["stretch"] + 2.6)
    duration = round(E["end"] + 1.6, 1)

    M = [
        {"section": "night", "from": 0, "to": E["zoomCode"]},
        {"section": "code", "from": E["zoomCode"], "to": E["tremble"]},
        {"section": "hush", "from": E["land"], "to": E["glitch"]},
        {"section": "grow", "from": E["eye"], "to": E["portal1"]},
        {"section": "chip", "from": E["r1"], "to": E["portal2"]},
        {"section": "chipTense", "from": E["r2"], "to": E["portal3"]},
        {"section": "chipTense", "from": E["r3"], "to": E["light3"]},
        {"section": "chipFinal", "from": E["race_go"], "to": E["unlock"]},
        {"section": "morning", "from": E["sunrise"], "to": duration},
    ]
    impacts = ["press1", "press2", "press3", "idea", "c1Run", "c2Run", "c5Run", "c8Run", "paddleHit", "box_", "paddle_", "glitch_", "first_", "r1a_", "r1b_", "tremble", "s1", "s2", "s3", "suck", "land", "touch", "glitch", "eye", "door0", "portal", "win", "light", "run_", "dodge_", "keyhole", "keyShow", "keyGlow", "car", "getIn", "race_bump", "race_brake", "race_overEdge", "race_ramp", "race_landJump", "race_key", "unlock", "through", "home", "dissolve", "wakeUp", "clock"]
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
        "silences": [{"from": E["glitch"] - 0.6, "to": E["glitch"]}, {"from": E["race_brake"] + 0.3, "to": E["race_overEdge"]}],
        "physics": {"wall": pong.WALL, "ballR": pong.BALL_R, "paddleX": pong.PADDLE_X, "paddleHalfW": pong.PADDLE_HALF_W, "paddleHalfH": pong.PADDLE_HALF_H, "goalX": pong.GOAL_X, "fps": pong.FPS, "reach": pong.REACH},
        "code": CODE,
        "shadow": SHADOW,
        "rallies": R,
        "audit": {
            "impacts": impacts,
            "holds": ["title", "slump", "lookKeys", "smile", "whereGone", "hypno", "nod", "doubleTake", "laughG", "ahHa", "cheer", "zoomOut", "point1", "handsOff", "look", "walk", "wonder", "rise", "say1", "say2", "say3", "say4", "stepBack", "setFeet", "r1", "r1react", "r2", "r3", "point", "relief", "sunrise", "turn", "see", "seeTwice", "stretch", "end"],
            "declared": [[0, 2.0, "fade in on the dark room"], [E["suck"], E["land"], "pulled through the screen"]] + [[E[f"portal{i}"], E[f"r{i}"] + 0.4, "a portal fills the frame"] for i in (1, 2, 3)],
        },
    }
    (ROOT / "audio/first_game/story.json").write_text(json.dumps(story, indent=1) + "\n")
    print(f"{len(E)} events, {len(S)} sounds, {len(R)} rallies, {duration} s")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build audio/first_game/story.json: the FIRST GAME timeline, derived from physics.

    python tools/first_game_timeline.py && python tools/build_space_audio.py --episode first_game

Every flight in the game lasts exactly as long as the coded physics says
(style bible K5): gravity G, the jump speed Spark types, the spring
strengths. Typing runs at 12 characters a second, one key click per
character (K2). The code Spark types and the physics constants are written
into story.json, passed through to cues.json, and read by the scene, so
the picture, the timeline and the code on screen can never disagree.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ---- the game's physics (game units: 1280 x 720 screen, ground at y = 250)
PHYS = {
    "g": 1800.0,        # gravity, units/s^2  (hero.vy += 30 per frame at 60 fps)
    "jump": -900.0,     # jump speed, units/s (after the -9000 typo is fixed)
    "typo": -9000.0,
    "spring2": -1000.0, # level 2 spring
    "spring3": -1100.0, # level 3 spring
    "run": 300.0,       # running speed, units/s
    "pelvis": 105.0,    # pelvis height above a surface
    "ground": 250.0,
    "platformTop": 159.0,
    "spikesTop": 305.0,
    "springTop2": 206.0,
    "springTop3": 291.0,
    "ledge": -40.0,
    "slowmo": 0.25,     # time scale while riding the platform down (try 2)
}
CPS = 12.0
ENTER = 0.1  # result fires 6 frames after Enter (K3)

CODE = {
    "typeFloor": "floor = box(0, 250).gap(160)",
    "typeHero": "hero = player(-480, 250)",
    "typeGravity": "hero.vy += 30",
    "typeFix1": "hero.y = min(hero.y, 250)",
    "typeJump": "hero.jump = -9000",
    "typeFlag": "flag = goal(330)",
    "typeLvl2": "level(2, {spring: -1000})",
    "typeLvl3": "level(3, {pit: 760})",
}


def land_time(y0: float, vy: float, y1: float, g: float = PHYS["g"]) -> float:
    """Time for a body at y0 moving at vy to reach y1 on the way down."""
    a, b, c = 0.5 * g, vy, y0 - y1
    return (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a)


def main() -> None:
    P = PHYS
    pel = P["pelvis"]
    ground = P["ground"] - pel
    E: dict[str, float] = {}
    S: list[dict] = []

    def ev(name: str, t: float) -> float:
        E[name] = round(t, 4)
        return E[name]

    def sfx(kind: str, at: str, **kw) -> None:
        S.append({"type": kind, "at": at, **kw})

    def typing(cue: str, start: float, text: str, effect: str | None) -> float:
        """Type `text` from `start`: a click per character, Enter, then the effect."""
        ev(cue, start)
        for i in range(len(text)):
            sfx("key", cue, offset=round(i / CPS, 4), gain=0.5)
        enter = ev(cue + "Enter", start + len(text) / CPS)
        sfx("enter", cue + "Enter")
        if effect:
            ev(effect, enter + ENTER)
        return enter + ENTER

    # ---- the want
    for k, t in [("open", 0.0), ("press1", 2.4), ("press2", 3.6), ("press3", 4.8), ("slump", 5.7), ("lookKeys", 7.2), ("idea", 8.4), ("title", 9.6), ("titleOut", 12.6)]:
        ev(k, t)
    for k in ["press1", "press2", "press3"]:
        sfx("click", k, gain=0.6)
        sfx("beep", k, offset=0.05, gain=0.6)
    sfx("click", "idea", gain=0.6)

    # ---- coding, close on the screen (K1-K4)
    t = ev("zoomCode1", 13.0)
    t = typing("typeFloor", t + 0.5, CODE["typeFloor"], "floor")
    sfx("pop", "floor", gain=0.4)
    t = typing("typeHero", t + 1.0, CODE["typeHero"], "hero")
    sfx("pop", "hero", gain=0.4)
    sfx("blip", "hero", gain=0.5)
    # Gravity, with no floor collision: the hero drops straight through (bug 1).
    t = typing("typeGravity", t + 1.0, CODE["typeGravity"], "fallBug")
    sfx("fall8", "fallBug")
    t = ev("zoomOut1", t + 1.0)
    ev("facepalm", t + 0.6)
    t = ev("zoomCode2", t + 1.8)
    t = typing("typeFix1", t + 0.5, CODE["typeFix1"], "fix1")
    sfx("ding", "fix1", gain=0.5)
    t = typing("typeJump", t + 1.0, CODE["typeJump"], None)
    # Spark tries the jump: at -9000 the hero leaves the top of the screen in 2 frames (bug 2).
    t = ev("zoomOut2", t + 0.6)
    ev("jumpBug", t + 0.9)
    sfx("click", "jumpBug", gain=0.5)
    sfx("jump8", "jumpBug", gain=0.6)
    ev("lookUp", E["jumpBug"] + 0.5)
    # The fix: cursor back to the number, delete one zero (K6).
    t = ev("zoomCode3", E["lookUp"] + 1.6)
    ev("editTypo", t + 0.6)
    sfx("key", "editTypo", gain=0.6)
    ev("fix2", E["editTypo"] + 0.4)
    sfx("enter", "fix2")
    # Re-run and jump: up 225 units and down in exactly 1.0 s.
    ev("jumpOk", E["fix2"] + 0.8)
    sfx("jump8", "jumpOk", gain=0.6)
    flat = 2 * -P["jump"] / P["g"]
    ev("landOk", E["jumpOk"] + flat)
    sfx("thud", "landOk", gain=0.3)
    t = typing("typeFlag", E["landOk"] + 0.8, CODE["typeFlag"], "flag")
    sfx("pop", "flag", gain=0.4)
    sfx("blip", "flag", gain=0.4)
    # Play level 1 for real.
    t = ev("zoomOut3", t + 1.0)
    play2 = ev("play2", t + 0.8)
    sfx("click", "play2", gain=0.5)
    run1 = (-150 - -480) / P["run"]
    ev("hop1", play2 + run1)
    sfx("jump8", "hop1")
    ev("hopLand1", E["hop1"] + flat)
    sfx("thud", "hopLand1", gain=0.3)
    ev("clear1", E["hopLand1"] + (300 - 150) / P["run"])
    sfx("fanfare", "clear1")
    ev("cheer", E["clear1"] + 0.6)

    # ---- more levels, into the night
    t = ev("zoomCode4", E["cheer"] + 1.4)
    t = typing("typeLvl2", t + 0.5, CODE["typeLvl2"], "lvl2")
    sfx("ripple", "lvl2")
    ev("clock1", t + 1.2)
    sfx("tick", "clock1")
    t = typing("typeLvl3", E["clock1"] + 1.4, CODE["typeLvl3"], "lvl3")
    sfx("ripple", "lvl3")
    ev("grin", t + 1.2)
    ev("clock2", E["grin"] + 1.2)
    sfx("tick", "clock2")
    play3 = ev("play3", E["clock2"] + 1.2)
    sfx("click", "play3", gain=0.5)
    ev("jump3m", play3 + (-392 - -480) / P["run"] + 0.3)
    sfx("jump8", "jump3m")
    pit = land_time(ground, P["jump"], P["spikesTop"] - pel)
    ev("die1", E["jump3m"] + pit)
    sfx("hurt", "die1")
    ev("gameOverMini", E["die1"] + 0.6)
    sfx("gameover", "gameOverMini", gain=0.7)
    ev("laugh", E["gameOverMini"] + 0.6)
    ev("yawn", E["laugh"] + 1.8)
    ev("droop", E["yawn"] + 1.8)
    ev("pull", E["droop"] + 1.2)
    sfx("riser", "pull", length=1.2, gain=0.6)
    ev("suck", E["pull"] + 1.2)
    sfx("whoosh", "suck")
    fall_in = math.sqrt(2 * (ground - -500) / P["g"])
    ev("inside", E["suck"] + 0.9 + 0.1 + fall_in)
    sfx("thud", "inside")

    # ---- inside: level 1
    ev("lookHands", E["inside"] + 1.2)
    ev("lookBack", E["lookHands"] + 1.2)
    ev("point", E["lookBack"] + 1.8)
    go1 = ev("go1", E["point"] + 1.2)
    ev("jumpL1", go1 + (-150 - -480) / P["run"])
    sfx("jump8", "jumpL1")
    ev("landL1", E["jumpL1"] + flat)
    sfx("thud", "landL1", gain=0.3)
    ev("flagL1", E["landL1"] + (300 - 150) / P["run"])
    sfx("fanfare", "flagL1")
    ev("wipe1", E["flagL1"] + 1.2)
    sfx("whoosh", "wipe1", gain=0.5)

    # ---- level 2: the ball, the spring
    l2 = ev("l2start", E["wipe1"] + 0.6)
    ev("ball", l2 + 0.6)
    sfx("roll", "ball", length=3.0, gain=0.5)
    ev("jumpBall", E["ball"] + 1.8)
    sfx("jump8", "jumpBall")
    ev("landBall", E["jumpBall"] + flat)
    sfx("thud", "landBall", gain=0.3)
    ev("spring1", E["landBall"] + (60 - 50) / P["run"] + 0.2)
    sfx("boing", "spring1")
    up2 = land_time(P["springTop2"] - pel, P["spring2"], P["ledge"] - pel)
    ev("landLedge", E["spring1"] + up2)
    sfx("thud", "landLedge", gain=0.5)
    ev("flagL2", E["landLedge"] + (425 - 320) / P["run"] + 0.2)
    sfx("fanfare", "flagL2")
    ev("wipe2", E["flagL2"] + 1.2)
    sfx("whoosh", "wipe2", gain=0.5)

    # ---- level 3: the door home
    l3 = ev("l3start", E["wipe2"] + 0.6)
    ev("seeDoor", l3 + 1.2)
    ev("gulp", E["seeDoor"] + 1.4)
    # try 1
    try1 = ev("try1", E["gulp"] + 1.2)
    ev("jump1", try1 + 0.5 + (-392 - -480) / P["run"] + 0.2)
    sfx("jump8", "jump1")
    ev("hurt1", E["jump1"] + pit)
    sfx("hurt", "hurt1")
    ev("respawn1", E["hurt1"] + 1.2)
    sfx("blip", "respawn1", gain=0.4)
    ev("react1", E["respawn1"] + 0.6)
    # try 2: onto the platform, ride it down (slow motion), see the spring
    try2 = ev("try2", E["react1"] + 1.2)
    ev("jump2", try2 + (-392 - -480) / P["run"] + 0.5)
    sfx("jump8", "jump2")
    ev("land2", E["jump2"] + land_time(ground, P["jump"], P["platformTop"] - pel))
    sfx("thud", "land2", gain=0.4)
    ev("shake2", E["land2"] + 0.6)
    sfx("rattle", "shake2")
    ev("drop2", E["shake2"] + 0.6)
    sfx("fall8", "drop2")
    ride = math.sqrt(2 * (P["spikesTop"] - P["platformTop"]) / P["g"]) / P["slowmo"]
    ev("seeSpring", E["drop2"] + ride * 0.45)
    sfx("ding", "seeSpring", gain=0.35)
    ev("hurt2", E["drop2"] + ride)
    sfx("hurt", "hurt2")
    ev("respawn2", E["hurt2"] + 1.2)
    sfx("blip", "respawn2", gain=0.4)
    ev("think", E["respawn2"] + 0.6)
    # try 3: a longer, faster run-up; still the pit
    try3 = ev("try3", E["think"] + 1.4)
    ev("jump3", try3 + 0.55 + (-392 - -540) / 400 + 0.3)
    sfx("jump8", "jump3")
    ev("hurt3", E["jump3"] + pit)
    sfx("hurt", "hurt3")
    ev("gameOver", E["hurt3"] + 0.6)
    sfx("gameover", "gameOver")
    ev("slumpGO", E["gameOver"] + 1.2)
    ev("count3", E["slumpGO"] + 2.4)
    ev("count2", E["count3"] + 1.2)
    ev("memory", E["count2"] + 0.3)
    ev("count1", E["count2"] + 1.2)
    for k in ["count3", "count2", "count1"]:
        sfx("tick", k, gain=0.9)
    sfx("ding", "memory", gain=0.5)
    # The punch: a full jump, the fist meets the sign at the top (0.5 s).
    ev("jumpPunch", E["count1"] + 0.3)
    sfx("jump8", "jumpPunch")
    ev("punch", E["jumpPunch"] + flat / 2)
    sfx("oneup", "punch")
    ev("heart1", E["punch"] + 0.6)
    sfx("blip", "heart1", gain=0.5)
    # try 4: the plan
    try4 = ev("try4", E["heart1"] + 1.2)
    ev("jump4", try4 + (-392 - -470) / P["run"] + 0.3)
    sfx("jump8", "jump4")
    ev("land4", E["jump4"] + land_time(ground, P["jump"], P["platformTop"] - pel))
    sfx("thud", "land4", gain=0.4)
    ev("shake4", E["land4"] + 0.6)
    sfx("rattle", "shake4")
    ev("drop4", E["shake4"] + 0.6)
    sfx("fall8", "drop4")
    # Leap off the falling platform after 0.15 s; its downward speed adds to the jump.
    lead = 0.15
    plat_y = P["platformTop"] - pel + 0.5 * P["g"] * lead**2
    vy = P["jump"] + P["g"] * lead
    ev("leap4", E["drop4"] + lead)
    sfx("jump8", "leap4")
    ev("boing4", E["leap4"] + land_time(plat_y, vy, P["springTop3"] - pel))
    sfx("boing", "boing4", gain=1.2)
    ev("soar", E["boing4"] + 0.3)
    ev("landExit", E["boing4"] + land_time(P["springTop3"] - pel, P["spring3"], ground))
    sfx("thud", "landExit", gain=0.6)
    ev("door", E["landExit"] + (470 - 440) / P["run"] + 0.8)
    sfx("fanfare", "door", gain=1.1)

    # ---- the dream breaks
    ev("crack", E["door"] + 1.2)
    ev("crack2", E["crack"] + 0.6)
    ev("shatter", E["crack2"] + 0.6)
    for k in ["crack", "crack2"]:
        sfx("crack", k)
    sfx("shatter", "shatter")
    sfx("boom", "shatter", gain=0.6)

    # ---- awake
    ev("wake", E["shatter"] + 2.4)
    sfx("thud", "wake", gain=0.6)
    ev("clock3", E["wake"] + 1.2)
    sfx("tick", "clock3")
    ev("lookScreen", E["clock3"] + 1.2)
    ev("grinKnow", E["lookScreen"] + 1.2)
    ev("grab", E["grinKnow"] + 1.2)
    sfx("click", "grab", gain=0.5)
    # The same plan, tiny, on the screen: same physics, same durations.
    m = ev("m_run", E["grab"] + 1.2)
    sfx("click", "m_run", gain=0.5)
    ev("m_jump", m + (-392 - -480) / P["run"] + 0.3)
    sfx("jump8", "m_jump", gain=0.6)
    ev("m_land", E["m_jump"] + (E["land4"] - E["jump4"]))
    sfx("thud", "m_land", gain=0.3)
    ev("m_drop", E["m_land"] + 1.2)
    sfx("fall8", "m_drop", gain=0.6)
    ev("m_leap", E["m_drop"] + lead)
    sfx("jump8", "m_leap", gain=0.6)
    ev("m_boing", E["m_leap"] + (E["boing4"] - E["leap4"]))
    sfx("boing", "m_boing", gain=0.8)
    ev("m_land2", E["m_boing"] + (E["landExit"] - E["boing4"]))
    sfx("thud", "m_land2", gain=0.3)
    ev("m_win", E["m_land2"] + (E["door"] - E["landExit"]))
    sfx("fanfare", "m_win")
    ev("leapChair", E["m_win"] + 0.6)
    sfx("thud", "leapChair", gain=0.5)
    ev("cheer2", E["leapChair"] + 1.2)
    ev("end", E["cheer2"] + 3.0)
    duration = round(E["end"] + 1.6, 1)

    M = [
        {"section": "night", "from": 0, "to": E["zoomCode1"]},
        {"section": "code", "from": E["zoomCode1"], "to": E["pull"]},
        {"section": "chip", "from": E["inside"], "to": E["l3start"]},
        {"section": "chipTense", "from": E["l3start"], "to": E["gameOver"]},
        {"section": "chipFinal", "from": E["heart1"], "to": E["crack"]},
        {"section": "morning", "from": E["wake"], "to": duration},
    ]
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
        "physics": PHYS,
        "code": CODE,
        "audit": {
            "impacts": ["press", "idea", "floor", "hero", "fallBug", "fix", "jumpBug", "jumpOk", "landOk", "flag", "hop", "clear1", "lvl", "clock", "die1", "gameOver", "suck", "inside", "jumpL1", "landL1", "flagL", "jumpBall", "landBall", "spring1", "landLedge", "jump", "hurt", "respawn", "land2", "shake", "drop", "seeSpring", "count", "memory", "punch", "heart1", "land4", "leap4", "boing4", "landExit", "door", "crack", "shatter", "wake", "grab", "m_", "leapChair", "editTypo"],
            "holds": ["title", "slump", "lookKeys", "cheer", "grin", "laugh", "yawn", "droop", "lookHands", "lookBack", "point", "seeDoor", "gulp", "react1", "think", "slumpGO", "soar", "grinKnow", "cheer2", "end", "lookUp", "facepalm", "zoomOut1", "zoomOut2", "zoomOut3"],
            "declared": [[0, 2.0, "fade in on the dark room"], [E["shatter"], E["wake"], "the dream breaks: white"]],
        },
    }
    (ROOT / "audio/first_game/story.json").write_text(json.dumps(story, indent=1) + "\n")
    print(f"{len(E)} events, {len(S)} sounds, {duration} s; inside fall {fall_in:.2f} s, pit jump {pit:.3f} s, ride {ride:.2f} s")


if __name__ == "__main__":
    main()

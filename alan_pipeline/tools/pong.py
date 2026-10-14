"""Exact ping pong physics for FIRST GAME (used by first_game_timeline.py).

Game units: a 1280 x 330 court (wide, arcade style), origin at the centre. The ball moves in
straight lines at constant speed and reflects off the top and bottom walls
(the angle of incidence equals the angle of reflection). A paddle hit sends it
back at a chosen angle and 1.5x the speed. Collisions are checked the way a
real game checks them: once per frame (60 per second), at the ball's position
on that frame. A ball fast enough to move further in one frame than the
paddle is thick can skip straight through it. That glitch is the story.
"""

from __future__ import annotations

import math

FPS = 60
WALL = 165.0          # top and bottom walls, |y| (a wide 1280 x 330 court)
BALL_R = 8.0
PADDLE_X = 560.0      # paddle centre, |x|
PADDLE_HALF_W = 6.0   # 12 units thick
PADDLE_HALF_H = 45.0
GOAL_X = 660.0        # off the court, |x|
SPEEDUP = 1.5
REACH = 180.0         # how fast Spark can move the paddle, units/s
PADDLE_LIMIT = WALL - PADDLE_HALF_H  # a paddle's centre can't go past the walls


class Rally:
    """A sequence of straight segments, plus named events, from a start time."""

    def __init__(self, t0: float):
        self.t = t0
        self.segments: list[dict] = []
        self.events: list[tuple[str, float, dict]] = []

    def seg(self, x: float, y: float, vx: float, vy: float, until: float) -> None:
        self.segments.append({"t": round(self.t, 5), "x": round(x, 3), "y": round(y, 3), "vx": round(vx, 4), "vy": round(vy, 4), "until": round(until, 5)})

    def fly(self, x: float, y: float, vx: float, vy: float, to_x: float) -> tuple[float, float, float]:
        """Fly to the plane x = to_x, reflecting off the walls. Returns (y, vy, t_arrive)."""
        lim = WALL - BALL_R
        while True:
            t_plane = (to_x - x) / vx
            t_wall = math.inf
            if vy > 0:
                t_wall = (lim - y) / vy
            elif vy < 0:
                t_wall = (-lim - y) / vy
            if t_wall < t_plane - 1e-9:
                self.seg(x, y, vx, vy, self.t + t_wall)
                x += vx * t_wall
                y += vy * t_wall
                self.t += t_wall
                self.events.append(("wall", self.t, {"y": y}))
                vy = -vy
            else:
                self.seg(x, y, vx, vy, self.t + t_plane)
                y += vy * t_plane
                self.t += t_plane
                return y, vy, self.t


def frame_hits_paddle(seg_x: float, vx: float, t_seg: float, t_from: float, t_to: float, paddle_x: float) -> bool:
    """Does any rendered frame in [t_from, t_to] put the ball inside the paddle's x-span?"""
    k0 = math.ceil(t_from * FPS - 1e-9)
    k1 = math.floor(t_to * FPS + 1e-9)
    for k in range(k0, k1 + 1):
        t = k / FPS
        x = seg_x + vx * (t - t_seg)
        if abs(x - paddle_x) <= PADDLE_HALF_W + BALL_R:
            return True
    return False


def paddle_at(y0: float, target: float, speed: float, t_from: float, t_to: float) -> float:
    """
    Where a paddle is at t_to if it chases `target` at `speed` from t_from,
    stepping once per frame exactly as the scene does.
    """
    k0 = math.ceil(t_from * FPS - 1e-9)
    k1 = math.floor(t_to * FPS + 1e-9)
    y = y0
    step = speed / FPS
    goal = max(-PADDLE_LIMIT, min(PADDLE_LIMIT, target))
    for _ in range(max(0, k1 - k0 + 1)):
        d = goal - y
        y += max(-step, min(step, d))
    return y


MARGIN = 10.0  # a hit must be covered, and a miss missed, by at least this much


def play(t0: float, server: int, y0: float, shots: list[tuple[str, float]], speed0: float = 600.0, speeds: tuple[float, float] = (REACH, REACH), search: bool = True) -> Rally:
    """
    Play one rally. `server` is -1 (Spark, left) or +1 (computer, right).
    `shots[i]` is what happens when the ball reaches a paddle:
      ("serve", angle) only as shots[0]: the serve's angle (degrees, + = down)
      ("hit", angle)   the paddle there hits it back at about `angle`
      ("miss", 0)      the paddle there can't get there in time
      ("tunnel", 0)    the paddle is there, but no frame lands inside it
    Each paddle chases the ball's next arrival on its side at its top speed
    (`speeds` = left, right), frame by frame, like the scene. When `search`
    is on, each angle is nudged (up to 30 degrees) until every outcome is
    physically true: hits covered, misses out of reach, tunnels covered but
    skipped. Raises ValueError if no angle works.
    """
    r = Rally(t0)
    speed = speed0
    side = server
    pad = {-1: 0.0, 1: 0.0}
    pad_t = {-1: t0, 1: t0}
    x = side * (PADDLE_X - PADDLE_HALF_W - BALL_R)
    y = y0
    kind, ang = shots[0]
    assert kind == "serve"
    r.events.append(("serve", r.t, {"side": side, "y": y}))
    hint = ang
    for i, (kind, _a) in enumerate(shots[1:]):
        nxt_side = -side
        tries = [hint] + [hint + d * sg for d in range(2, 31, 2) for sg in (1, -1)] if search else [hint]
        ok = None
        for a in tries:
            if abs(a) > 55:
                continue
            trial = Rally(r.t)
            vx = -side * speed * math.cos(math.radians(a))
            vy = speed * math.sin(math.radians(a))
            plane = nxt_side * (PADDLE_X - PADDLE_HALF_W - BALL_R)
            ya, vya, t_arr = trial.fly(x, y, vx, vy, plane)
            pspeed = speeds[0] if nxt_side < 0 else speeds[1]
            py = paddle_at(pad[nxt_side], ya, pspeed, pad_t[nxt_side], t_arr)
            gap = abs(py - ya) - (PADDLE_HALF_H + BALL_R)
            seg = trial.segments[-1]
            span = (2 * (PADDLE_HALF_W + BALL_R)) / abs(vx)
            framed = frame_hits_paddle(seg["x"], seg["vx"], seg["t"], t_arr - 1e-6, t_arr + span, nxt_side * PADDLE_X)
            if kind == "hit" and gap <= -MARGIN and framed:
                ok = (a, trial, ya, vya, t_arr, vx, py)
            elif kind == "miss" and gap >= MARGIN:
                ok = (a, trial, ya, vya, t_arr, vx, py)
            elif kind == "tunnel" and gap <= -MARGIN:
                t_goal = (nxt_side * GOAL_X - plane) / vx
                if not frame_hits_paddle(plane, vx, t_arr, t_arr - 2 / FPS, t_arr + span + 2 / FPS, nxt_side * PADDLE_X):
                    ok = (a, trial, ya, vya, t_arr, vx, py)
            if ok:
                break
        if not ok:
            raise ValueError(f"shot {i + 1} ({kind}) has no physical angle")
        a, trial, ya, vya, t_arr, vx, py = ok
        r.segments += trial.segments
        r.events += trial.events
        r.t = t_arr
        if i == 0:
            r.events[0][2]["angle"] = a
        pad[nxt_side] = py
        pad_t[nxt_side] = t_arr
        side = nxt_side
        x = side * (PADDLE_X - PADDLE_HALF_W - BALL_R)
        y = ya
        if kind == "hit":
            r.events.append(("hit", t_arr, {"side": side, "y": y, "speed": speed, "paddle": py}))
            speed *= SPEEDUP
            hint = _a
            continue
        t_goal = (side * GOAL_X - x) / vx
        r.seg(x, y, vx, vya, t_arr + t_goal)
        r.events.append(("tunnel" if kind == "tunnel" else "miss", t_arr, {"side": side, "y": y, "speed": speed, "paddle": py}))
        r.t = t_arr + t_goal
        r.events.append(("goal", r.t, {"side": side, "y": y + vya * t_goal}))
        return r
    return r


def find(t0: float, server: int, y0: float, shots: list[tuple[str, float]], speed0: float = 600.0, speeds: tuple[float, float] = (REACH, REACH), tries: int = 4000) -> Rally:
    """
    Search for a rally in which every outcome is physically true. Each try
    nudges the serve time (1/600 s steps: which frames the ball is drawn on
    decides a collision, as in a real game), the serve height, and the
    scripted angles (a deterministic pseudo-random walk). The first rally that
    works is returned, so the result is the same on every machine.
    """
    import random

    rng = random.Random(1729)
    last = None
    for i in range(tries):
        dt = (i % 60) / 600
        jitter = 0 if i < 60 else min(30, 4 + i // 100)
        cand = [(k, a + (rng.uniform(-jitter, jitter) if k in ("serve", "hit") else 0)) for k, a in shots]
        y = y0 + (0 if i < 60 else rng.uniform(-60, 60))
        try:
            return play(t0 + dt, server, y, cand, speed0, speeds)
        except ValueError as e:
            last = e
    raise ValueError(f"no rally satisfies the script: {last}")

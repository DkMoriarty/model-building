import {Node} from '@motion-canvas/2d';
import {ThreadGenerator, useLogger, useTime, Vector2} from '@motion-canvas/core';
import {physics} from './cues';

/**
 * Exact ballistic motion under the game's gravity (style bible K5). The
 * timeline was built from the same constants (tools/first_game_timeline.py),
 * so a flight that starts on its cue lands on its cue; if it would not, we
 * say so instead of cheating the arc.
 */
export const GRAV = physics.g;

/** Time for a body at y0 moving at vy to reach y1 on the way down. */
export function landTime(y0: number, vy: number, y1: number, g = GRAV): number {
  const a = 0.5 * g;
  const b = vy;
  const c = y0 - y1;
  return (-b + Math.sqrt(b * b - 4 * a * c)) / (2 * a);
}

/**
 * Fly `n` from `from` with vertical speed `vy` until it comes down to height
 * `toY` at horizontal position `toX`. The horizontal speed is whatever covers
 * the distance in the flight time (constant, no air in this game). Checks the
 * landing against `landAt` (a cue) to within one frame. `scale` slows time
 * (slow motion) without changing the path.
 */
export function* ballistic(n: Node, from: Vector2, vy: number, toX: number, toY: number, landAt?: number, scale = 1): ThreadGenerator {
  const T = landTime(from.y, vy, toY);
  const vx = (toX - from.x) / T;
  const t0 = useTime();
  if (landAt !== undefined && Math.abs(t0 + T / scale - landAt) > 1.5 / 60) {
    useLogger().warn(`physics: flight lands at ${(t0 + T / scale).toFixed(3)}s, cue is ${landAt.toFixed(3)}s`);
  }
  while ((useTime() - t0) * scale < T - 1e-6) {
    const t = (useTime() - t0) * scale;
    n.position(new Vector2(from.x + vx * t, from.y + vy * t + 0.5 * GRAV * t * t));
    yield;
  }
  n.position(new Vector2(toX, toY));
}

/** Free fall from rest (or with `vy`) for `d` seconds of game time. */
export function* freeFall(n: Node, vy = 0, d = 2, scale = 1): ThreadGenerator {
  const from = n.position();
  const t0 = useTime();
  while ((useTime() - t0) * scale < d) {
    const t = (useTime() - t0) * scale;
    n.position(new Vector2(from.x, from.y + vy * t + 0.5 * GRAV * t * t));
    yield;
  }
}

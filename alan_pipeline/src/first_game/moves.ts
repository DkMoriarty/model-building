import {Node} from '@motion-canvas/2d';
import {all, easeInCubic, easeInQuad, easeOutCubic, linear, ThreadGenerator, useTime, Vector2, waitFor} from '@motion-canvas/core';
import {Pose, StickFigure} from '../components/StickFigure';
import {SPARK_COLOR} from '../first_light/components/Spark';
import {STAND} from '../first_light/acts/dark';
import {PELVIS} from './components/Game';
import {ballistic, freeFall} from './physics';

/**
 * Platformer moves for a figure that lives inside a level (level-local
 * game units). Every move ends exactly on its cue time, so the same
 * choreography runs full size inside the game and tiny on the monitor.
 */
export const TUCK: Pose = {torso: 10, head: -6, leftHip: -70, leftKnee: 90, rightHip: -40, rightKnee: 70, leftShoulder: -120, leftElbow: -30, rightShoulder: -60, rightElbow: -40};
export const FLAIL: Pose = {torso: -10, head: -20, leftHip: -20, leftKnee: 30, rightHip: 20, rightKnee: 40, leftShoulder: -160, leftElbow: -10, rightShoulder: -150, rightElbow: -20};
export const SOAR: Pose = {torso: 6, head: -10, leftHip: -10, leftKnee: 20, rightHip: 10, rightKnee: 30, leftShoulder: -100, leftElbow: 0, rightShoulder: -80, rightElbow: 0};
export const LAND: Pose = {torso: 16, leftHip: -40, leftKnee: 60, rightHip: -30, rightKnee: 50, leftShoulder: 20, rightShoulder: 10};

/** Pelvis position for a figure standing on a surface at (x, y). */
export const on = (x: number, y: number) => new Vector2(x, y - PELVIS);

/** Run (fast walk) to x, the last footfall on `arriveAt`. */
export function* runTo(fig: StickFigure, x: number, arriveAt: number): ThreadGenerator {
  const steps = Math.max(1, Math.round(Math.abs(x - fig.x()) / 85));
  yield* fig.walkTo(x, {arriveAt, steps, settle: false});
}

/**
 * Jump on a parabola from the current pelvis to `to`, rising `h` above the
 * higher end, landing at absolute time `landAt`. A 3-frame crouch first,
 * a tuck in the air, a 2-frame squash on landing.
 */
export function* jumpTo(fig: StickFigure, to: Vector2, landAt: number, h: number, air: Pose = TUCK, squash = true): ThreadGenerator {
  yield* fig.pose({torso: 20, leftHip: -40, leftKnee: 60, rightHip: -30, rightKnee: 50}, 3 / 60, easeInCubic);
  yield* flight(fig, fig.position(), to, landAt, h, air);
  if (squash) yield* fig.pose(LAND, 2 / 60);
}

/** The airborne part only: a quadratic arc that lands on `landAt`. */
export function* flight(fig: Node, a: Vector2, b: Vector2, landAt: number, h: number, air?: Pose): ThreadGenerator {
  const t0 = useTime();
  const d = Math.max(1 / 60, landAt - t0);
  const peak = Math.min(a.y, b.y) - h;
  const ctrlY = 2 * peak - (a.y + b.y) / 2;
  const tasks: ThreadGenerator[] = [];
  if (air && fig instanceof StickFigure) tasks.push(fig.pose(air, Math.min(0.2, d / 2), easeOutCubic));
  tasks.push(
    (function* () {
      while (useTime() < landAt - 1e-6) {
        const u = Math.min(1, (useTime() - t0) / d);
        fig.position(new Vector2(a.x + (b.x - a.x) * u, (1 - u) * (1 - u) * a.y + 2 * u * (1 - u) * ctrlY + u * u * b.y));
        yield;
      }
      fig.position(b);
    })(),
  );
  yield* all(...tasks);
}

/**
 * Hurt, game style: flash red and white, pop up, then drop out of the bottom
 * of the screen and vanish.
 */
export function* hurt(fig: StickFigure): ThreadGenerator {
  fig.setPose(FLAIL);
  const flash = (function* () {
    for (let i = 0; i < 8; i++) {
      fig.color(i % 2 ? '#ffffff' : '#ef476f');
      yield* waitFor(3 / 60);
    }
    fig.color(SPARK_COLOR);
  })();
  // The game's hurt bounce: up at 600 units/s, then gravity takes it off the screen.
  yield* all(flash, freeFall(fig, -600, 1.0), fig.rotation(200, 1.0, linear));
  fig.opacity(0);
  fig.rotation(0);
}

/** Respawn at `at`, blinking three times. */
export function* respawn(fig: StickFigure, at: Vector2): ThreadGenerator {
  fig.position(at);
  fig.setPose(STAND);
  fig.rotation(0);
  for (let i = 0; i < 6; i++) {
    fig.opacity(i % 2 ? 0.2 : 1);
    yield* waitFor(4 / 60);
  }
  fig.opacity(1);
}

export {easeOutCubic};

/** Run to the take-off point so the 3-frame crouch ends exactly on `takeoffAt`. */
export function* runUp(fig: StickFigure, x: number, takeoffAt: number): ThreadGenerator {
  yield* runTo(fig, x, takeoffAt - 3 / 60);
  yield* fig.pose({torso: 20, leftHip: -40, leftKnee: 60, rightHip: -30, rightKnee: 50}, 3 / 60, easeInCubic);
}

/** An exact jump: leaves now with vertical speed `vy`, lands at (toX, toY) on `landAt`. */
export function* leap(fig: StickFigure, vy: number, toX: number, toY: number, landAt: number, air: Pose = TUCK, squash = true): ThreadGenerator {
  yield* all(fig.pose(air, 0.15, easeOutCubic), ballistic(fig, fig.position(), vy, toX, toY, landAt));
  if (squash) yield* fig.pose(LAND, 2 / 60);
}

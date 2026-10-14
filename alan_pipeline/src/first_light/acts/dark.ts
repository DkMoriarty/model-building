import {all, chain, easeInCubic, easeInOutCubic, easeInOutSine, easeOutBack, easeOutCubic, linear, ThreadGenerator, Vector2, waitFor} from '@motion-canvas/core';
import {Pose} from '../../components/StickFigure';
import {Bulb, Wire} from '../components/Circuit';
import {bolt, smoke} from '../components/Fx';
import {SPARK_COLOR} from '../components/Spark';
import {at, Cue, syncTo} from '../cues';
import {attach, FLOOR, plant, reach, SIT_Y, Stage, worldOf} from '../stage';

/** Sitting on the floor, knees up, facing right. */
export const SIT: Pose = {torso: 4, head: 0, leftHip: -84, leftKnee: 8, rightHip: -112, rightKnee: 96, leftShoulder: 20, leftElbow: -40, rightShoulder: -30, rightElbow: -70};
export const STAND: Pose = {torso: 0, head: 0, leftHip: 6, leftKnee: 4, rightHip: -6, rightKnee: 4, leftShoulder: 12, leftElbow: -12, rightShoulder: -12, rightElbow: -14};

/** Where the dangling cable ends (world). */
export const TIP = new Vector2(150, 150);

export interface DarkProps {
  bulb: Bulb;
  cable: Wire;
  /** Cable drop offset: 0 = hanging in place, negative = still above frame. */
  drop: () => number;
}

/** The opening and the bookend share this framing: a medium close-up on Spark. */
export function openingFrame(s: Stage): void {
  s.zoom(2);
  // Spark sits at x = 0 on the 0.38 lead-room line, facing right.
  s.cam(new Vector2(115, 175));
}

/**
 * 0 - 17 s. Dark. Spark turns a dead bulb over, holds it up: nothing. A cable
 * drops into frame; Spark touches the bulb to it and the beads take the
 * shortest way down, through Spark. Title.
 */
export function* dark(s: Stage, bulb: Bulb, cable: Wire, drop: (v: number, d: number) => ThreadGenerator): ThreadGenerator {
  const spark = s.spark.body;
  spark.setPose(SIT);
  spark.position([0, SIT_Y]);
  spark.opacity(1);
  openingFrame(s);
  bulb.scale(0.8);
  // The toy: the bulb lives in Spark's right hand.
  attach(s, bulb, spark.bones.rightFist, new Vector2(4, -6));
  s.spawn(s.blackout.opacity(0, 1.5, easeInOutSine));

  yield* toyBeats(s, bulb, 'turn', 'tap1', 'holdUp', 'sigh');

  // A cable drops into frame from the dark above, and stops with a bounce.
  yield* syncTo('wire', 0.55);
  yield* drop(0, 0.55);
  yield* syncTo('notice', 0.1);
  yield* spark.pose({head: -16, torso: 2}, 0.2, easeOutCubic);
  // Up: a 4-frame crouch, then stand.
  yield* syncTo('stand', 0);
  yield* spark.pose({torso: 20}, 4 / 60, easeInCubic);
  const standY = (() => {
    const y0 = spark.y();
    spark.setPose({...STAND, rightShoulder: -50, rightElbow: -70});
    spark.y(0);
    plant(s, spark);
    const y = spark.y();
    spark.setPose({...SIT, torso: 20, head: -16, rightShoulder: -50, rightElbow: -70});
    spark.y(y0);
    return y;
  })();
  yield* all(spark.pose({...STAND, rightShoulder: -50, rightElbow: -70, head: -10}, 0.5, easeOutCubic), spark.y(standY, 0.5, easeOutCubic), spark.x(10, 0.5));

  // Reach: the bulb's base meets the cable tip on the beat.
  yield* syncTo('reach', 0.6);
  const touch = reach(s, spark, 'rightArm', TIP.add([-6, 14]), {...STAND, head: -8, torso: 6});
  yield* spark.pose(touch, 0.6, easeInOutCubic);

  // ZAP. The beads take the shortest way to the floor: through Spark.
  yield* syncTo('zap');
  cable.speed(900);
  s.spawn(bolt(s.fx, TIP, worldOf(s, spark.bones.chest), '#ffd27a', 0.3, 5));
  s.spawn(bolt(s.fx, worldOf(s, spark.bones.chest), worldOf(s, spark.bones.leftFoot), '#ffd27a', 0.3, 4));
  s.spawn(bolt(s.fx, worldOf(s, spark.bones.chest), worldOf(s, spark.bones.rightFoot), '#ffd27a', 0.3, 4));
  s.spawn(shakeMinor(s, 8, 4));
  // Shock freeze: 12 frames, spread-eagled, flashing white.
  spark.setPose({torso: -6, head: -10, leftShoulder: -130, leftElbow: 10, rightShoulder: -120, rightElbow: 0, leftHip: 20, leftKnee: 0, rightHip: -20, rightKnee: 0});
  for (let i = 0; i < 6; i++) {
    spark.color(i % 2 ? SPARK_COLOR : '#ffffff');
    yield* waitFor(2 / 60);
  }
  spark.color(SPARK_COLOR);
  cable.speed(0);
  // The goggles drop over the eyes; Spark sits down hard.
  yield* syncTo('goggles', 0.1);
  yield* s.spark.goggles(1, 0.1, easeInCubic);
  s.spawn(smoke(s.fx, worldOf(s, spark.bones.head).add([0, -30])));
  yield* syncTo('thud', 0.35);
  yield* all(spark.pose({...SIT, rightShoulder: -40, rightElbow: -60, head: 10}, 0.35, easeInCubic), spark.y(SIT_Y, 0.35, easeInCubic), spark.x(-10, 0.35));
  s.spawn(shakeMinor(s, 6, 4));
  // Peek at the bulb through the goggles: still dark.
  yield* syncTo('peek', 0.3);
  yield* spark.pose({rightShoulder: -78, rightElbow: -80, head: 26, torso: 10}, 0.5, easeInOutSine);

  // Title over the hold, scene dimmed behind it.
  yield* syncTo('title', 0);
  yield* all(s.title.opacity(1, 0.6), s.blackout.opacity(0.7, 0.6));
  yield* syncTo('titleOut', 0);
  yield* all(s.title.opacity(0, 0.6), s.blackout.opacity(0, 0.6));
}

/**
 * The toy beats, shared by the opening and the bookend: turn the bulb over,
 * tap it, hold it up to the dark, sigh.
 */
export function* toyBeats(s: Stage, bulb: Bulb, turn: Cue, tap: Cue, hold: Cue, sigh: Cue): ThreadGenerator {
  const spark = s.spark.body;
  // Turn it over (curiosity), then a tap.
  yield* syncTo(turn, 0.6);
  yield* spark.pose({rightShoulder: -70, rightElbow: -80, head: 14}, 0.6, easeInOutCubic);
  yield* bulb.rotation(180, 0.5, easeInOutCubic);
  yield* bulb.rotation(360, 0.4, easeInOutCubic);
  bulb.rotation(0);
  yield* syncTo(tap, 0.15);
  yield* spark.pose({leftShoulder: -62, leftElbow: -96}, 0.15, easeInCubic);
  yield* spark.pose({leftShoulder: -40, leftElbow: -70}, 0.2, easeOutCubic);

  // The want: hold it up to the dark. Nothing happens.
  yield* syncTo(hold, 0.4);
  yield* spark.pose({rightShoulder: -160, rightElbow: -10, head: -22, torso: -6, leftShoulder: 20, leftElbow: -30}, 0.4, easeOutCubic);
  yield* syncTo(sigh, 0.3);
  yield* spark.pose({rightShoulder: -50, rightElbow: -70, head: 22, torso: 14}, 0.6, easeInOutSine);

}

/** Minor-tier shake: single-frame jolts of `px`, decaying, for `frames` frames. */
export function* shakeMinor(s: Stage, px: number, frames: number): ThreadGenerator {
  for (let i = 0; i < frames; i++) {
    const a = (i * 2.4) % (Math.PI * 2);
    s.shake(new Vector2(Math.cos(a), Math.sin(a)).scale(px * (1 - i / frames)));
    yield;
  }
  s.shake(Vector2.zero);
}

export {chain, easeOutBack, linear, FLOOR};

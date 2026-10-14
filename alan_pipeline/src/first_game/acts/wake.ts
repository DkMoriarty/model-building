import {all, easeInCubic, easeInOutCubic, easeInOutSine, easeOutBack, easeOutCubic, ThreadGenerator, Vector2, waitFor} from '@motion-canvas/core';
import {STAND} from '../../first_light/acts/dark';
import {hop, standHeight} from '../../first_light/acts/sandbox';
import {Stage, worldOf} from '../../first_light/stage';
import {G, GAME_COLORS} from '../components/Game';
import {CLOCK_AT, Room, SCREEN, SCREEN_SCALE, SEAT} from '../components/Room';
import {at, syncTo} from '../cues';
import {LAND, leap, on, runTo, runUp, SOAR} from '../moves';
import {physics as P} from '../cues';
import {confetti, Monitor, SIT_CHAIR} from './room';
import {Pose} from '../../components/StickFigure';



/**
 * 110.4 - 130 s. Awake at the desk: morning. On the screen, level 3, the
 * tiny Spark at the start with three hearts. Spark knows the way now:
 * the platform, the leap, the spring. YOU WIN, for real. Spark leaps out of
 * the chair.
 */
export function* wakeAct(s: Stage, room: Room, m: Monitor): ThreadGenerator {
  const spark = s.spark.body;
  // Back in the room, asleep on the desk.
  spark.remove();
  s.cast.add(spark);
  spark.scale([0.8, 0.8]);
  spark.rotation(0);
  spark.opacity(1);
  spark.face(1);
  spark.position(SEAT.add([0, -3]));
  const ASLEEP: Pose = {...SIT_CHAIR, torso: 56, head: 34, leftShoulder: -100, leftElbow: -40, rightShoulder: -96, rightElbow: -50};
  spark.setPose(ASLEEP);
  room.morning(1);
  room.hours(31);
  s.room(0.9);
  s.lightColor('#ffe8b0');
  s.lightAt(new Vector2(-440, -110));
  s.cam(new Vector2(150, 60));
  s.zoom(1.35);
  m.noGame.opacity(0);
  m.code.opacity(0);
  m.preview.position(Vector2.zero);
  m.preview.scale(SCREEN_SCALE);
  const level = m.levels[2];
  m.show(3);
  m.say(null);
  m.hearts.opacity(1);
  const mini = m.mini;
  const pad = room.pad;
  pad.position(new Vector2(150, 187));

  // ---- Wake: a jolt, goggles flip up.
  yield* syncTo('wake', 0);
  s.spawn(s.whiteout.opacity(0, 0.3, easeOutCubic));
  yield* all(spark.pose({...SIT_CHAIR, torso: -14, head: -24, leftShoulder: -120, rightShoulder: -130, leftElbow: -40, rightElbow: -30}, 0.12, easeOutBack), s.spark.goggles(0, 0.12));
  s.spawn(shakeOnce(s));
  // The clock: 7 in the morning (pull back to explain).
  yield* syncTo('clock3', 0.3);
  yield* spark.pose({...SIT_CHAIR, head: -34, torso: -4}, 0.3, easeOutCubic);
  yield* all(s.cam(CLOCK_AT.add([60, 30]), 0.5, easeInOutCubic), s.zoom(2.8, 0.5, easeInOutCubic));
  yield* waitFor(0.2);
  // The screen: level 3, the tiny Spark waiting at the start.
  yield* syncTo('lookScreen', 0.5);
  yield* all(s.cam(new Vector2(225, 70), 0.5, easeInOutCubic), s.zoom(2.1, 0.5, easeInOutCubic), spark.pose({...SIT_CHAIR, torso: 16, head: -16}, 0.5, easeInOutCubic));
  // A look at the pad, then up again: a knowing grin.
  yield* syncTo('grinKnow', 0);
  yield* spark.pose({head: 30, torso: 20}, 0.3, easeOutCubic);
  yield* waitFor(0.3);
  yield* spark.pose({head: -18, torso: -6, leftShoulder: -40, leftElbow: -120, rightShoulder: -36, rightElbow: -110}, 0.3, easeOutBack);
  // Grab the pad.
  yield* syncTo('grab', 0.3);
  const HOLD: Pose = {...SIT_CHAIR, torso: 10, head: -14, leftShoulder: -40, leftElbow: -70, rightShoulder: -46, rightElbow: -64};
  yield* spark.pose(HOLD, 0.3, easeInOutCubic);
  pad.position(() => worldOf(s, spark.bones.rightFist).add(worldOf(s, spark.bones.leftFist)).scale(0.5).add([6, -4]));

  // ---- The winning run, tiny, on the screen. Each press is a thumb jab.
  const jab = () => s.spawn(spark.joints.rightElbow(-80, 0.06).to(-64, 0.08));
  const plat = level.platform!;
  const spring = level.spring!;
  plat.position([-160, 170]);
  plat.opacity(1);
  yield* syncTo('m_run', 0);
  jab();
  yield* runUp(mini, -392, at('m_jump'));
  jab();
  yield* leap(mini, P.jump, -160, P.platformTop - P.pelvis, at('m_land'));
  mini.position(() => on(-160, plat.y() - 11));
  yield* waitFor(0.55);
  yield* shake(plat, 0.6);
  yield* syncTo('m_drop', 0);
  s.spawn(fall(plat, 170, P.g, at('m_drop') + 1.2, at('m_drop')));
  yield* syncTo('m_leap', 0);
  jab();
  mini.position(mini.position());
  yield* leap(mini, P.jump + P.g * (at('m_leap') - at('m_drop')), -60, P.springTop3 - P.pelvis, at('m_boing'), undefined, false);
  s.spawn(spring.squash(1, 0.04).to(0, 0.14, easeOutBack));
  yield* leap(mini, P.spring3, 440, G.ground - P.pelvis, at('m_land2'), SOAR, false);
  mini.setPose(LAND);
  yield* mini.pose(STAND, 0.25);
  yield* runTo(mini, 470, at('m_win') - 0.1);
  yield* syncTo('m_win', 0);
  m.say('YOU WIN', GAME_COLORS.door);
  s.spawn(confetti(level.root, new Vector2(480, -40)));

  // ---- Out of the chair: a leap, arms up.
  s.spawn(all(s.cam(new Vector2(150, 60), 0.5, easeInOutCubic), s.zoom(1.35, 0.5, easeInOutCubic)));
  yield* syncTo('leapChair', 0.45);
  pad.position(pad.position());
  const standY = standHeight(s, spark);
  yield* all(spark.pose(STAND, 0.2, easeOutCubic), spark.y(standY, 0.2), spark.x(SEAT.x - 60, 0.4, easeOutCubic));
  yield* hop(spark, 46);
  yield* syncTo('cheer2', 0);
  for (let i = 0; i < 4; i++) {
    yield* spark.pose({...STAND, torso: i % 2 ? 6 : -6, head: -16, leftShoulder: i % 2 ? -160 : -60, rightShoulder: i % 2 ? -60 : -160, leftElbow: -20, rightElbow: -20}, 0.6, easeInOutSine);
  }
  yield* syncTo('end', 0);
  yield* s.blackout.opacity(1, 0.8, easeInCubic);
  void SCREEN;
}

function* shakeOnce(s: Stage): ThreadGenerator {
  for (let i = 0; i < 4; i++) {
    s.shake(new Vector2(i % 2 ? 6 : -6, 0).scale(1 - i / 4));
    yield;
  }
  s.shake(Vector2.zero);
}

function* fall(n: import('@motion-canvas/2d').Node, y0: number, g: number, until: number, t0 = s0()): ThreadGenerator {
  const bottom = P.spikesTop + 11;
  while (s0() < until - 1e-6) {
    const t = s0() - t0;
    n.y(Math.min(bottom, y0 + 0.5 * g * t * t));
    yield;
  }
}
import {useTime} from '@motion-canvas/core';
const s0 = () => useTime();

function* shake(n: import('@motion-canvas/2d').Node, d: number): ThreadGenerator {
  const x0 = n.x();
  for (let t = 0, i = 0; t < d; t += 1 / 60, i++) {
    n.x(x0 + (i % 4 < 2 ? 3 : -3));
    yield;
  }
  n.x(x0);
}

export {easeInOutCubic};

import {all, easeInCubic, easeInOutCubic, easeInOutSine, easeOutBack, easeOutCubic, ThreadGenerator, useTime, Vector2, waitFor} from '@motion-canvas/core';
import {Pose} from '../../components/StickFigure';
import {STAND} from '../../first_light/acts/dark';
import {hop, standHeight} from '../../first_light/acts/sandbox';
import {Stage, worldOf} from '../../first_light/stage';
import {playRally, PONG_COLORS} from '../components/Pong';
import {CLOCK_AT, PAD_AT, Room, SEAT} from '../components/Room';
import {at, rallies, syncTo} from '../cues';
import {camTo, HOLD, Monitor, SIT_CHAIR, SPEED} from './room';

/**
 * Awake at the desk: morning. On the screen, the game at 0 - 0. Spark knows
 * the trick now: serve, so the fastest hit is yours. The ball skips through
 * the computer's paddle on the real screen. YOU WIN. Out of the chair.
 */
export function* wakeAct(s: Stage, room: Room, m: Monitor): ThreadGenerator {
  const spark = s.spark.body;
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
  m.say(null);
  m.court.scoreL(0);
  m.court.scoreR(0);
  m.court.leftY(0);
  m.court.rightY(0);
  m.court.ball.opacity(0);
  const pad = room.pad;
  pad.position(PAD_AT);

  // ---- Wake: a jolt, goggles flip up.
  yield* syncTo('wake', 0);
  s.spawn(s.whiteout.opacity(0, 0.3, easeOutCubic));
  yield* all(spark.pose({...SIT_CHAIR, torso: -14, head: -24, leftShoulder: -120, rightShoulder: -130, leftElbow: -40, rightElbow: -30}, 0.12, easeOutBack), s.spark.goggles(0, 0.12));
  // The clock: seven in the morning. It was a dream.
  yield* syncTo('clock3', 0.3);
  yield* spark.pose({...SIT_CHAIR, head: -34, torso: -4}, 0.3, easeOutCubic);
  yield* all(s.cam(CLOCK_AT.add([60, 30]), 0.5, easeInOutCubic), s.zoom(2.8, 0.5, easeInOutCubic));
  yield* waitFor(0.2);
  // The screen: the game, 0 - 0.
  yield* syncTo('lookScreen', 0.5);
  yield* all(camTo(s, {cam: new Vector2(225, 70), zoom: 2.1}, 0.5), spark.pose({...SIT_CHAIR, torso: 16, head: -16}, 0.5, easeInOutCubic));
  // A look at the pad, then a knowing grin.
  yield* syncTo('grinKnow', 0);
  yield* spark.pose({head: 30, torso: 20}, 0.3, easeOutCubic);
  yield* waitFor(0.3);
  yield* spark.pose({head: -18, torso: -6, leftShoulder: -40, leftElbow: -120, rightShoulder: -36, rightElbow: -110}, 0.3, easeOutBack);
  yield* syncTo('grab', 0.3);
  yield* spark.pose(HOLD, 0.3, easeInOutCubic);
  pad.position(() => worldOf(s, spark.bones.rightFist).add(worldOf(s, spark.bones.leftFist)).scale(0.5).add([6, -4]));

  // ---- The same plan, for real: Spark serves; the fifth hit skips through.
  const r = rallies['final'];
  yield* syncTo('final', 0);
  s.spawn(
    (function* () {
      for (const e of r.events.filter(e => e.side === -1 && (e.kind === 'hit' || e.kind === 'serve'))) {
        while (useTime() < e.t - 0.06) yield;
        yield* spark.joints.rightElbow(-80, 0.06).to(HOLD.rightElbow!, 0.1);
      }
    })(),
  );
  yield* playRally(m.court, r, at('win') - 1 / 60, {left: SPEED.spark, right: SPEED.cpu99}, 'final', true);
  yield* syncTo('win', 0);
  m.court.scoreL(1);
  m.say('YOU WIN', '#ffd166');

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
  void PONG_COLORS;
}

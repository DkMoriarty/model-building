import {Rect} from '@motion-canvas/2d';
import {all, easeInCubic, easeInOutCubic, easeInOutSine, easeOutBack, easeOutCubic, ThreadGenerator, Vector2, waitFor} from '@motion-canvas/core';
import {Pose} from '../../components/StickFigure';
import {SIT, STAND} from '../../first_light/acts/dark';
import {standHeight} from '../../first_light/acts/sandbox';
import {createSpark} from '../../first_light/components/Spark';
import {reach, SIT_Y, Stage, worldOf} from '../../first_light/stage';
import {Room, SEAT, WINDOW_AT} from '../components/Room';
import {WORLD} from '../components/World';
import {syncTo} from '../cues';
import {Monitor, SIT_CHAIR} from './room';

const DOORWAY_X = -800;
const SPARK_X = -640;
const ASLEEP: Pose = {...SIT_CHAIR, torso: 56, head: 34, leftShoulder: -100, leftElbow: -40, rightShoulder: -96, rightElbow: -50};

/**
 * 162 - 176 s. Home: Spark steps out of the light into his room and sinks
 * down, a hand on his chest. Relief. The sun comes up in the window. He
 * turns, and sees himself at the desk, asleep. The dreamer dissolves; the
 * real Spark wakes up and stretches.
 */
export function* homeAct(s: Stage, room: Room, m: Monitor): ThreadGenerator {
  const spark = s.spark.body;
  // The room at dawn, the computer showing the game Spark wrote.
  room.hours(6.4);
  m.red?.opacity(0);
  m.label.opacity(0);
  m.code.opacity(0);
  m.output.position([0, 0]);
  m.court.showScore(1);
  m.court.scoreL(1);
  m.court.scoreR(0);
  m.court.ball.opacity(0);
  m.court.leftY(0);
  m.court.rightY(0);
  room.pad.position(room.pad.position());
  s.room(0.55);
  s.lightColor('#8ecae6');
  s.lightAt(WINDOW_AT);
  // The sleeper: Spark, at the desk, where he fell asleep.
  const sleeper = createSpark({scale: 0.8});
  s.cast.add(sleeper.body);
  sleeper.body.position(SEAT.add([0, -3]));
  sleeper.body.setPose(ASLEEP);
  sleeper.goggles(1);
  // The way in: a doorway of light that closes behind him.
  const doorway = new Rect({x: DOORWAY_X, y: 300 - 120, width: 120, height: 240, radius: [60, 60, 0, 0], fill: '#fff3d6', shadowColor: WORLD.gold, shadowBlur: 60});
  s.props.add(doorway);
  spark.remove();
  s.cast.add(spark);
  spark.scale([0.8, 0.8]);
  spark.rotation(0);
  spark.opacity(1);
  spark.face(1);
  spark.setPose(STAND);
  const standY = standHeight(s, spark, STAND);
  spark.position(new Vector2(DOORWAY_X, standY));
  s.cam(new Vector2(-600, 125));
  s.zoom(2.0);

  // ---- Out of the light: two steps, and down on his knees.
  yield* syncTo('home', 0);
  s.spawn(s.whiteout.opacity(0, 0.4, easeOutCubic));
  yield* spark.walkTo(SPARK_X, {steps: 2, duration: 0.45, settle: false});
  const KNEEL: Pose = {torso: 20, head: 10, leftHip: -90, leftKnee: 150, rightHip: -20, rightKnee: 110, leftShoulder: 10, leftElbow: -20, rightShoulder: 0, rightElbow: -20};
  s.spawn(doorway.opacity(0, 0.8, easeInCubic));
  yield* all(spark.pose(KNEEL, 0.15, easeInCubic), spark.y(standY + 52, 0.15, easeInCubic));
  // ---- Relief: he sits back, a hand on his chest, and breathes out.
  yield* syncTo('relief', 0);
  yield* all(spark.pose(SIT, 0.4, easeInOutSine), spark.y(SIT_Y, 0.4, easeInOutSine));
  const chest = worldOf(s, spark.bones.chest).add([10, -6]);
  const HAND: Pose = {...SIT, ...reach(s, spark, 'rightArm', chest, SIT), head: -18, torso: -6};
  yield* spark.pose(HAND, 0.3, easeOutCubic);
  for (let i = 0; i < 1; i++) {
    yield* spark.pose({torso: -12, head: -26}, 0.5, easeInOutSine);
    yield* spark.pose({torso: 2, head: -10}, 0.5, easeInOutSine);
  }
  // ---- Sunrise in the window.
  yield* syncTo('sunrise', 0);
  s.spawn(all(room.morning(1, 2.4, easeInOutSine), s.room(1, 2.4), s.lightColor('#ffe8b0', 2.4)));
  yield* spark.pose({...SIT, head: -30, torso: -4}, 0.8, easeInOutSine);
  // ---- He turns to the desk, and sees himself there, asleep.
  yield* syncTo('turn', 0);
  yield* spark.pose({...SIT, head: 0, torso: 4}, 0.4, easeInOutSine);
  yield* syncTo('see', 0);
  yield* all(s.cam(new Vector2(-260, 80), 0.6, easeInOutCubic), s.zoom(1.2, 0.6, easeInOutCubic));
  yield* syncTo('seeTwice', 0);
  yield* spark.pose({head: 24, torso: 10}, 0.12, easeOutCubic);
  yield* spark.pose({head: -12, torso: -14, leftShoulder: -40, leftElbow: -110}, 0.15, easeOutBack);
  // ---- The dreamer dissolves into pixels that drift into the sleeper.
  yield* syncTo('dissolve', 0);
  const head = worldOf(s, sleeper.body.bones.head);
  for (let i = 0; i < 26; i++) {
    const from = worldOf(s, spark.bones.chest).add([((i % 6) - 2.5) * 14, (Math.floor(i / 6) - 2) * 20]);
    const px = new Rect({position: from, width: 10, height: 10, fill: i % 3 ? '#2ec4b6' : '#9ff0e6'});
    s.fx.add(px);
    s.spawn(all(px.position(head.add([((i % 5) - 2) * 6, ((i % 3) - 1) * 6]), 0.6 + (i % 4) * 0.05, easeInOutCubic), px.opacity(0, 0.75, easeInCubic)));
  }
  yield* spark.opacity(0, 0.4, easeInCubic);
  // ---- Awake: a jolt upright, goggles up.
  yield* syncTo('wakeUp', 0);
  const me = sleeper.body;
  yield* all(me.pose({...SIT_CHAIR, torso: -14, head: -24, leftShoulder: -120, rightShoulder: -130, leftElbow: -40, rightElbow: -30}, 0.12, easeOutBack), sleeper.goggles(0, 0.12));
  yield* me.pose({...SIT_CHAIR, head: -30, torso: -2}, 0.4, easeOutCubic);
  // ---- A long stretch towards the sun.
  yield* syncTo('stretch', 0);
  yield* me.pose({...SIT_CHAIR, torso: -16, head: -34, leftShoulder: -170, rightShoulder: -165, leftElbow: -10, rightElbow: -14}, 0.7, easeInOutSine);
  yield* waitFor(0.6);
  yield* me.pose({...SIT_CHAIR, head: -10}, 0.6, easeInOutSine);
  yield* syncTo('end', 0);
  yield* s.blackout.opacity(1, 1.2, easeInCubic);
}

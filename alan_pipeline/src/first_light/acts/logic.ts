import {Circle, Line, Node, Rect} from '@motion-canvas/2d';
import {all, easeInCubic, easeInOutCubic, easeInOutSine, easeOutBack, easeOutCubic, linear, ThreadGenerator, Vector2, waitFor} from '@motion-canvas/core';
import {Pose} from '../../components/StickFigure';
import {withAlpha} from '../../figureSpec';
import {BAD_RED, BEAD, Bulb, Switch, TIER, Wire} from '../components/Circuit';
import {shards, sparkBurst} from '../components/Fx';
import {at, syncTo} from '../cues';
import {FLOOR, reach, SIT_Y, Stage, worldOf} from '../stage';
import {SIT, STAND} from './dark';
import {standHeight} from './sandbox';
import {shakeMinor} from './dark';

/** The wall loop: corners, in world space. */
const L = -560;
const R = -40;
const T = -40;
const B = 262;
const LAMP = new Vector2(-300, T);

export interface WallLoop {
  bulb: Bulb;
  wires: Wire[];
}

/**
 * 50 - 78 s. Logic, by accident. On the wall Spark builds the loop into
 * switches: two in a row need both (a hand and a toe), two side by side need
 * either, a red one cuts the light when pressed. Then Spark lets the lamp
 * press its own red switch through a coil: it blinks by itself, faster and
 * hotter, until it bursts.
 */
export function* logic(s: Stage, hideOld: () => void): ThreadGenerator {
  const spark = s.spark.body;
  // ---- the cut: a new set-up on the wall, Spark mid-action pinning a wire.
  yield* syncTo('board', 0);
  hideOld();
  s.cam(new Vector2(-300, 120));
  s.zoom(1.6);
  const group = new Node({});
  s.props.add(group);
  // Power box on the left side: the loop passes through it.
  group.add(new Rect({x: L, y: 60, width: 46, height: 70, radius: 6, fill: '#1b1b22', stroke: '#9a9aa6', lineWidth: TIER.structure}));
  group.add(new Line({points: [[L - 8, 40], [L + 8, 40]], stroke: BEAD, lineWidth: TIER.detail}));
  group.add(new Line({points: [[L, 72], [L, 88]], stroke: BEAD, lineWidth: TIER.detail}));
  group.add(new Line({points: [[L - 8, 80], [L + 8, 80]], stroke: BEAD, lineWidth: TIER.detail}));
  // The main loop, one wire from the box all the way round (clockwise).
  const loop = s.wire(
    new Wire({
      points: () => [new Vector2(L, 25), new Vector2(L, T), new Vector2(R, T), new Vector2(R, B), new Vector2(L, B), new Vector2(L, 95)],
      spacing: 32,
      pool: 60,
      time: () => s.time(),
    }),
  );
  group.add(loop);
  const bulb = new Bulb({position: LAMP.add([0, 16]), rotation: 180, radius: 26});
  group.add(bulb);
  s.lightAt(() => worldOf(s, bulb, bulb.glassCentre));
  // S1 on the left side near the floor, S2 on the floor wire far to the right.
  const s1 = new Switch({position: [L, 225], rotation: -90});
  const s2 = new Switch({position: [-325, B], rotation: 0});
  group.add([s1, s2]);
  // Bypass branch for the OR demo (drawn on later).
  const bypass = s.wire(
    new Wire({
      points: () => [new Vector2(L, 195), new Vector2(L - 70, 195), new Vector2(L - 70, B), new Vector2(L, B)],
      spacing: 32,
      pool: 12,
      time: () => s.time(),
    }),
  );
  bypass.trim(0);
  bypass.beads(0);
  const s3 = new Switch({position: [L - 70, 228], rotation: -90, opacity: 0});
  group.add([bypass, s3]);
  const nsw = new Switch({position: [L, 225], rotation: -90, cap: BAD_RED, closed: 1, opacity: 0});
  group.add(nsw);
  const coil = new Node({position: [L - 46, 240], opacity: 0});
  coil.add(new Line({points: Array.from({length: 14}, (_, i) => [i % 2 ? -10 : 10, -24 + i * 3.6] as [number, number]), stroke: '#b5651d', lineWidth: TIER.structure}));
  coil.add(new Circle({size: 46, fill: () => withAlpha(BAD_RED, 0.0)}));
  group.add(coil);

  // Lamp state from the switches, applied every frame (truth table, honest).
  let mode: 'and' | 'or' | 'not' = 'and';
  const lit = () => {
    if (bulb.glass() < 0.5) return false;
    if (mode === 'and') return s1.closed() > 0.5 && s2.closed() > 0.5;
    if (mode === 'or') return (s1.closed() > 0.5 || s3.closed() > 0.5) && s2.closed() > 0.5;
    return nsw.closed() > 0.5 && s2.closed() > 0.5;
  };
  bulb.glow(() => (lit() ? 1 : 0));
  loop.speed(() => (lit() ? 300 : 0));
  bypass.speed(() => (mode === 'or' && s3.closed() > 0.5 && lit() ? 300 : 0));
  s.room(() => (lit() ? 1 : 0.12));

  // Spark mid-pin at the right side when we cut in.
  spark.face(-1);
  spark.x(-140);
  spark.setPose({...STAND, rightShoulder: -150, rightElbow: -20, head: -20});
  spark.y(standHeight(s, spark, {...STAND, rightShoulder: -150, rightElbow: -20, head: -20}));
  const standY = spark.y();

  // ---- AND: S1 alone, nothing. S2 alone, nothing (S1 springs back).
  yield* syncTo('and1', 0.9);
  yield* spark.walkTo(-505, {arriveAt: at('and1') - 0.25, steps: 4, settle: false});
  const crouch: Pose = {...STAND, torso: 30, head: 10, leftHip: -40, leftKnee: 60, rightHip: -20, rightKnee: 50};
  const crouchY = standHeight(s, spark, crouch);
  yield* all(spark.pose(reach(s, spark, 'rightArm', press(s1), crouch), 0.25, easeInCubic), spark.y(crouchY, 0.25));
  s1.closed(1);
  yield* spark.pose({head: -40}, 0.3, easeOutCubic);
  yield* waitFor(0.25);
  s1.closed(0);
  yield* spark.pose({...STAND, head: -10}, 0.25);
  yield* spark.y(standY, 0.1);
  yield* spark.walkTo(-370, {arriveAt: at('and2') - 0.25, steps: 3, mode: 'auto', settle: false});
  yield* all(spark.pose(reach(s, spark, 'rightArm', press(s2), crouch), 0.25, easeInCubic), spark.y(crouchY, 0.25));
  s2.closed(1);
  yield* spark.pose({head: -40}, 0.3, easeOutCubic);
  yield* waitFor(0.3);
  s2.closed(0);
  // Both at once: too far apart for two hands. Lie down: a hand and a toe.
  yield* spark.face(-1, 0.1);
  yield* syncTo('andBoth', 0.9);
  spark.y(crouchY);
  const pelvis = new Vector2(-420, FLOOR - 10);
  yield* all(spark.position(pelvis, 0.5, easeInCubic), spark.rotation(-90, 0.5, easeInCubic), spark.pose({...STAND, torso: 0, head: 0}, 0.5));
  const lie: Pose = {torso: 0, head: -30, leftShoulder: -170, leftElbow: 0, leftHip: 4, leftKnee: 6};
  const handPose = reach(s, spark, 'rightArm', press(s1), lie);
  const toePose0 = reach(s, spark, 'rightLeg', press(s2).add([0, 2]), handPose);
  // The free leg lies along the floor beside the stretched one.
  const toePose = reach(s, spark, 'leftLeg', new Vector2(pelvis.x + 95, FLOOR - 8), toePose0);
  yield* spark.pose(toePose, 0.4 - 0.02, easeInOutCubic);
  s1.closed(1);
  s2.closed(1);
  // It works: wobble at full stretch.
  yield* spark.pose({head: -60, leftShoulder: -140}, 0.4, easeOutCubic);
  yield* spark.pose({leftShoulder: -175}, 0.3, easeInOutSine);
  yield* spark.pose({leftShoulder: -150}, 0.3, easeInOutSine);
  // The toe slips: dark again.
  yield* syncTo('andFall', 0.15);
  yield* spark.pose({rightHip: 10, rightKnee: 4, rightShoulder: -150, rightElbow: -10}, 0.15, easeInCubic);
  s1.closed(0);
  s2.closed(0);
  s.spawn(shakeMinor(s, 5, 4));

  // ---- OR: S2 latched shut; a bypass with S3 beside S1. Either one lights it.
  yield* syncTo('or1', 1.0);
  yield* all(spark.rotation(0, 0.5, easeOutCubic), spark.position(new Vector2(-480, crouchY), 0.5, easeOutCubic), spark.pose(crouch, 0.5));
  s2.closed(1, 0.2);
  mode = 'or';
  yield* syncTo('or1', 0);
  s3.opacity(1);
  s3.scale(0);
  yield* all(bypass.trim(1, 0.5, easeOutCubic), s3.scale(1, 0.4, easeOutBack));
  bypass.beads(1);
  yield* syncTo('orA', 0.2);
  yield* spark.pose(reach(s, spark, 'rightArm', press(s1), crouch), 0.2, easeInCubic);
  s1.closed(1);
  yield* waitFor(0.5);
  s1.closed(0);
  yield* syncTo('orB', 0.25);
  yield* spark.pose(reach(s, spark, 'rightArm', press(s3), crouch), 0.25, easeInCubic);
  s3.closed(1);
  yield* spark.pose({head: 20}, 0.3, easeOutCubic);
  yield* spark.pose({head: -10}, 0.3, easeOutCubic);
  s3.closed(0);

  // ---- NOT: a red switch that is shut until pressed.
  yield* syncTo('not1', 0.3);
  yield* all(bypass.trim(0, 0.3), s3.scale(0, 0.3), s1.scale(0, 0.3));
  bypass.beads(0);
  mode = 'not';
  nsw.opacity(1);
  nsw.scale(0);
  yield* nsw.scale(1, 0.3, easeOutBack);
  yield* syncTo('notPress', 0.2);
  yield* spark.pose(reach(s, spark, 'rightArm', press(nsw), crouch), 0.2, easeInCubic);
  nsw.closed(0);
  yield* syncTo('notTilt', 0);
  yield* spark.pose({head: 34, torso: 22}, 0.3, easeOutCubic);
  yield* syncTo('notPress2', 0.4);
  nsw.closed(1);
  yield* spark.pose(crouch, 0.2);
  yield* spark.pose(reach(s, spark, 'rightArm', press(nsw), crouch), 0.2, easeInCubic);
  nsw.closed(0);
  yield* waitFor(0.6);
  nsw.closed(1);
  yield* spark.pose({...crouch, rightShoulder: -20, rightElbow: -40}, 0.25);

  // ---- The lamp presses its own red switch through a coil: it blinks.
  yield* syncTo('coil', 0.3);
  coil.opacity(1);
  coil.scale(0);
  yield* coil.scale(1, 0.3, easeOutBack);
  yield* syncTo('blinkStart', 0.5);
  yield* all(spark.pose({...STAND, head: -20}, 0.4), spark.y(standY, 0.4), spark.x(-430, 0.4));
  // The relay clicks on the same schedule as the buzzer sound: from 8th
  // notes (0.3 s) to a rattle (0.06 s), each click flipping the switch.
  const start = at('blinkStart');
  const clicks: number[] = [];
  for (let t = 0, period = 0.3; t < 6 - 0.05; t += period, period = Math.max(0.06, period * 0.93)) clicks.push(start + t);
  s.spawn(heatUp(s, bulb));
  s.spawn(worry(s));
  for (const c of clicks) {
    yield* syncTo(c);
    nsw.closed(nsw.closed() > 0.5 ? 0 : 1);
  }

  // ---- POP.
  yield* syncTo('pop', 0);
  const glass = worldOf(s, bulb, bulb.glassCentre);
  bulb.glass(0);
  bulb.glow(0);
  loop.speed(0);
  s.room(0.06);
  s.whiteout.opacity(0.6);
  s.spawn(shakeMinor(s, 10, 6));
  s.spawn(sparkBurst(s.fx, glass, BEAD, 0.8, 12));
  s.spawn(shards(s.fx, glass, FLOOR - 3, BEAD, 12, 2.5));
  yield* waitFor(2 / 60);
  s.whiteout.opacity(0);
  yield* spark.pose({torso: -16, head: -30, leftShoulder: -110, rightShoulder: -120, leftElbow: -60, rightElbow: -60}, 0.12, easeOutCubic);

  // Dark again. Sit; slump.
  yield* syncTo('sit2', 0.35);
  yield* spark.face(1, 0.1);
  yield* all(spark.pose({...SIT, head: 16, rightShoulder: 10, rightElbow: -20}, 0.25, easeInCubic), spark.y(SIT_Y, 0.25, easeInCubic));
  yield* syncTo('sigh2', 0.5);
  yield* spark.pose({torso: 22, head: 30, leftShoulder: 10, rightShoulder: 6}, 1.0, easeInOutSine);

  function press(sw: Switch): Vector2 {
    return worldOf(s, sw, sw.button);
  }
}

function* heatUp(s: Stage, bulb: Bulb): ThreadGenerator {
  yield* syncTo('overheat');
  yield* bulb.heat(1, at('pop') - at('overheat'), easeInCubic);
}

function* worry(s: Stage): ThreadGenerator {
  const spark = s.spark.body;
  yield* syncTo('blinkStart', 0);
  // Delight first: a little dance to the clicks.
  for (let i = 0; i < 4; i++) {
    yield* spark.pose({torso: i % 2 ? 6 : -6, head: i % 2 ? -14 : -24, leftShoulder: i % 2 ? -60 : 10, rightShoulder: i % 2 ? 10 : -60}, 0.3, easeInOutSine);
  }
  // Then worry: hands up, backing off.
  yield* syncTo('overheat', 0);
  yield* all(spark.pose({torso: -12, head: -26, leftShoulder: -100, leftElbow: -70, rightShoulder: -100, rightElbow: -70}, 0.4, easeOutCubic), spark.x(spark.x() + 50, 1.6, easeInOutSine));
}

export {linear};

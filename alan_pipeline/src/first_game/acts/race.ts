import {Node, Txt} from '@motion-canvas/2d';
import {all, easeInCubic, easeInOutCubic, easeInOutSine, easeOutBack, easeOutCubic, ThreadGenerator, useTime, Vector2, waitFor} from '@motion-canvas/core';
import {Pose, StickFigure} from '../../components/StickFigure';
import {STAND} from '../../first_light/acts/dark';
import {arc, standHeight} from '../../first_light/acts/sandbox';
import {smoke, sparkBurst} from '../../first_light/components/Fx';
import {reach, Stage, worldOf} from '../../first_light/stage';
import {Typography} from '../../styles';
import {Car, goldKey, HomeDoor, LANE_Y, Shadow, WORLD} from '../components/World';
import {at, Cue, G, RacePhase, racePlan, syncTo} from '../cues';
import {DOOR_X, Hub, KICK_LEN, KICK_RISE, ROAD_X0, shake, SPARK_HUB_X} from './world';

const N = racePlan.numbers;
const LIP = ROAD_X0 + N.lip;
/** Where the door re-forms: at the end of the road, past the gap and the key. */
export const DOOR_FAR = new Vector2(ROAD_X0 + N.xDoor + 260, 300 - KICK_RISE);
const KEY_AT = new Vector2(ROAD_X0 + N.xKey, 300 - KICK_RISE - 170);
const SEATED: Pose = {torso: -4, head: -6, leftHip: -84, leftKnee: 70, rightHip: -90, rightKnee: 76, leftShoulder: -60, leftElbow: -50, rightShoulder: -64, rightElbow: -46};
const rc = (e: string) => racePlan.events[e];

/** Position along the road (and height, and pitch) for a list of phases at time t. */
function evalPhases(phases: RacePhase[], t: number): {x: number; y: number; v: number; rot: number; flying: boolean} {
  let p = phases[0];
  if (t < p.t) return state(p, p.t);
  for (const q of phases) {
    p = q;
    if (t <= q.until + 1e-9) break;
  }
  return state(p, Math.min(t, p.until));
}
function state(p: RacePhase, t: number): {x: number; y: number; v: number; rot: number; flying: boolean} {
  const s = t - p.t;
  const d = p.until - p.t;
  if (p.kind === 'acc') return {x: p.x0 + p.v0 * s + (p.a * s * s) / 2, y: 0, v: p.v0 + p.a * s, rot: 0, flying: false};
  if (p.kind === 'ease') {
    const u = d > 0 ? s / d : 1;
    const k = 0.5 - 0.5 * Math.cos(Math.PI * u);
    return {x: p.x0 + (p.x1 - p.x0) * k, y: 0, v: d > 0 ? ((p.x1 - p.x0) * Math.PI * Math.sin(Math.PI * u)) / (2 * d) : 0, rot: 0, flying: false};
  }
  if (p.kind === 'hermite') {
    const u = s / d;
    const h00 = 2 * u ** 3 - 3 * u ** 2 + 1;
    const h10 = u ** 3 - 2 * u ** 2 + u;
    const h01 = -2 * u ** 3 + 3 * u ** 2;
    const h11 = u ** 3 - u ** 2;
    const x = h00 * p.x0 + h10 * d * p.v0 + h01 * p.x1 + h11 * d * p.v1;
    const dx = (6 * u * u - 6 * u) * p.x0 + (3 * u * u - 4 * u + 1) * d * p.v0 + (-6 * u * u + 6 * u) * p.x1 + (3 * u * u - 2 * u) * d * p.v1;
    return {x, y: 0, v: dx / d, rot: 0, flying: false};
  }
  const vy = p.vy + G * s;
  return {x: p.x0 + p.vx * s, y: p.vy * s + (G * s * s) / 2, v: p.vx, rot: (Math.atan2(vy, p.vx) * 180) / Math.PI, flying: true};
}

/** Height of the road under a car centre at road position x (the kicker rises to the lip; past the gap, the deck is raised). */
function roadY(x: number): number {
  const lip = N.lip;
  if (x >= lip - KICK_LEN && x <= lip) return -(x - (lip - KICK_LEN)) * (KICK_RISE / KICK_LEN);
  if (x > lip + N.gap) return -KICK_RISE;
  return 0;
}

/**
 * 137 - 162 s. The door shows a keyhole, then breaks into bits that fly to
 * the far end of the road, past a broken bridge; the key glows in front of
 * it. A car. The race: red cars ram Spark twice; at the edge he brakes, they
 * can't, and go over. He backs up, takes a run at the kicker, jumps the gap,
 * grabs the key, stops at the door, unlocks it, and steps through.
 */
export function* raceAct(s: Stage, hub: Hub): ThreadGenerator {
  const spark = s.spark.body;
  const door = hub.door;
  const standY = standHeight(s, spark, STAND);

  // ---- The keyhole appears.
  yield* syncTo('keyhole', 0.15);
  yield* spark.pose({...STAND, torso: 8, head: -10, rightShoulder: -40, rightElbow: -30}, 0.15, easeOutCubic);
  door.keyhole(1);
  s.spawn(sparkBurst(s.fx, new Vector2(DOOR_X + 34, 300 - 110), WORLD.gold, 0.5, 8));

  // ---- The door breaks into bits that stream away down the road; the camera follows them.
  yield* syncTo('keyShow', 0);
  const bits = new Node({});
  s.fx.add(bits);
  for (let i = 0; i < 28; i++) {
    const b = new Txt({text: i % 2 ? '1' : '0', fontFamily: Typography.mono, fontWeight: 800, fontSize: 40, fill: WORLD.gold, position: new Vector2(DOOR_X + ((i % 4) - 1.5) * 30, 300 - 20 - Math.floor(i / 4) * 32)});
    bits.add(b);
    const to = DOOR_FAR.add([((i % 4) - 1.5) * 30, -20 - Math.floor(i / 4) * 32]);
    s.spawn(all(b.position(to, 0.8 + (i % 5) * 0.04, easeInOutCubic), b.opacity(0, 0.2).wait(0.5).to(1, 0.1).wait(0.1).to(0, 0.2)));
  }
  door.opacity(0);
  const view = new Vector2((LIP + DOOR_FAR.x) / 2, 40);
  yield* all(s.cam(view, 0.7, easeInOutCubic), s.zoom(0.6, 0.7, easeInOutCubic));
  door.position(DOOR_FAR);
  yield* door.opacity(1, 0.2);
  bits.remove();
  // The key appears in front of the door, glowing, bobbing.
  yield* syncTo('keyGlow', 0);
  const key = goldKey({position: KEY_AT, scale: 0});
  s.props.add(key);
  yield* key.scale(1.6, 0.3, easeOutBack);
  const bob = () => KEY_AT.add([0, 8 * Math.sin(s.time() * 4)]);
  key.position(bob);
  // Back to Spark: he points at it.
  yield* syncTo('point', 0.5);
  yield* all(s.cam(new Vector2(SPARK_HUB_X + 300, 40), 0.5, easeInOutCubic), s.zoom(1.1, 0.5, easeInOutCubic));
  yield* spark.pose({...STAND, head: -10, rightShoulder: -95, rightElbow: 0, torso: -2}, 0.2, easeOutCubic);

  // ---- A car.
  const car = new Car({color: '#2ec4b6', x: ROAD_X0, y: LANE_Y[0], scale: 0});
  s.cast.add(car);
  car.moveToBottom();
  yield* syncTo('car', 0);
  yield* car.scale(1, 0.3, easeOutBack);
  yield* spark.pose({...STAND, torso: 10, head: -16}, 0.3, easeInOutSine);
  // In he gets: a hop onto the seat.
  yield* syncTo('getIn', 0.5);
  const seatWorld = worldOf(s, car.seat);
  yield* all(arc(spark, spark.position(), seatWorld, 60, 0.5), spark.pose(SEATED, 0.5, easeInOutSine));
  spark.remove();
  car.seat.add(spark);
  spark.position(Vector2.zero);
  const wheel = new Vector2(ROAD_X0 + 22, LANE_Y[0] - 92);
  const DRIVE: Pose = {...reach(s, spark, 'rightArm', wheel, SEATED), ...pick(reach(s, spark, 'leftArm', wheel.add([-4, 4]), SEATED), ['leftShoulder', 'leftElbow'])};
  yield* spark.pose(DRIVE, 0.3);

  // ---- The red cars, each driven by a small Shadow.
  const reds = racePlan.reds.map(r => {
    const c = new Car({color: WORLD.red});
    const driver = new Shadow({scale: 0.22, y: 34});
    driver.look(1);
    c.seat.add(driver);
    s.props.add(c);
    return {plan: r, car: c};
  });
  const laneOf = (lanes: {t: number; to: number; d: number}[], t: number) => {
    let l = 0;
    for (const c of lanes) {
      if (t >= c.t + c.d) l = c.to;
      else if (t >= c.t) l = l + (c.to - l) * easeInOutSine((t - c.t) / c.d);
    }
    return l;
  };

  // ---- The race, frame by frame from the plan.
  yield* syncTo('race_go', 0);
  const end = rc('doorArrive');
  const bumps = [rc('bump1'), rc('bump2')];
  let bumped = 0;
  let keyTaken = false;
  const camFrom = s.cam();
  const zoomFrom = s.zoom();
  while (useTime() < end - 1e-6) {
    const t = useTime();
    const st = evalPhases(racePlan.spark, t);
    // In flight the car leaves from the top of the kicker; on the road it follows the deck.
    const yOff = st.flying ? roadY(N.lip) + st.y : roadY(st.x);
    car.position(new Vector2(ROAD_X0 + st.x, LANE_Y[0] + yOff));
    const onKick = !st.flying && st.x >= N.lip - KICK_LEN && st.x <= N.lip;
    const braking = t >= rc('brake') && t < rc('stop');
    car.rotation(st.flying ? st.rot : onKick ? -N.rampAngle : braking ? 3 : 0);
    car.travelled(st.x);
    for (const r of reds) {
      const q = evalPhases(r.plan.phases, t);
      const lane = laneOf(r.plan.lanes, t);
      const yy = LANE_Y[0] + (LANE_Y[1] - LANE_Y[0]) * lane;
      const ry = q.flying ? roadY(N.lip - N.carHalf) + q.y : roadY(q.x);
      r.car.position(new Vector2(ROAD_X0 + q.x, yy + ry));
      r.car.scale(1 - 0.08 * lane);
      r.car.rotation(q.flying ? Math.min(75, q.rot + (t - r.plan.overEdge) * 60) : q.x >= N.lip - KICK_LEN && q.x <= N.lip ? -N.rampAngle : 0);
      r.car.travelled(q.x);
      r.car.opacity(t < r.plan.phases[0].t ? 0 : 1);
    }
    // Bumps: a jolt and a burst at the contact.
    if (bumped < bumps.length && t >= bumps[bumped]) {
      const contact = car.position().add([-N.carHalf, -40]);
      s.spawn(sparkBurst(s.fx, contact, '#ffd166', 0.8, 10));
      s.spawn(shake(s, 9, 8));
      s.spawn(jolt(spark, DRIVE));
      bumped++;
    }
    // The key: an arm up just before, and it's in his fist.
    if (!keyTaken && t >= rc('key') - 0.25) {
      keyTaken = true;
      s.spawn(spark.pose({...DRIVE, rightShoulder: -165, rightElbow: -10, head: -20}, 0.25, easeOutCubic));
      s.spawn(
        (function* () {
          while (useTime() < rc('key')) yield;
          key.position(() => worldOf(s, spark.bones.rightFist));
          s.spawn(sparkBurst(s.fx, worldOf(s, spark.bones.rightFist), WORLD.gold, 0.8, 12));
        })(),
      );
    }
    if (t >= rc('brake') && t < rc('brake') + 1 / 60) s.spawn(smoke(s.fx, car.position().add([-70, -6]), 4));
    // Camera: ahead of the car, lifting a little with the jump.
    const w = easeInOutCubic(Math.min(1, (t - rc('go')) / 0.8));
    s.cam(camFrom.add(new Vector2(car.x() + 300, 100 + 0.5 * (car.y() - LANE_Y[0])).sub(camFrom).scale(w)));
    s.zoom(zoomFrom + (0.85 - zoomFrom) * w);
    yield;
  }
  reds.forEach(r => r.car.remove());

  // ---- At the door: out of the car, key in the lock.
  const standFar = standY - KICK_RISE;
  spark.remove();
  s.cast.add(spark);
  spark.scale([0.8, 0.8]);
  spark.rotation(0);
  spark.position(worldOf(s, car.seat));
  const out = new Vector2(DOOR_FAR.x - 40, standFar);
  s.spawn(all(s.cam(new Vector2(DOOR_FAR.x - 160, 40), 0.8, easeInOutCubic), s.zoom(1.3, 0.8, easeInOutCubic)));
  yield* all(arc(spark, spark.position(), out, 50, 0.5), spark.pose({...STAND, rightShoulder: -150, rightElbow: -30}, 0.5, easeInOutSine));
  yield* syncTo('unlock', 0.3);
  const hole = DOOR_FAR.add([34, -110]);
  yield* spark.pose(reach(s, spark, 'rightArm', hole, {...STAND, torso: 6}), 0.3, easeOutCubic);
  key.position(hole);
  key.scale(0.9);
  yield* key.rotation(90, 0.15, easeInOutCubic);
  door.lights.forEach(l => s.spawn(l(0.2, 0.08).to(1, 0.08)));
  s.spawn(sparkBurst(s.fx, hole, WORLD.gold, 0.6, 8));
  yield* syncTo('doorOpen', 0);
  key.remove();
  s.lightColor(WORLD.gold);
  s.lightAt(DOOR_FAR.add([0, -120]));
  s.spawn(s.room(0.9, 0.6));
  yield* all(door.open(1, 0.6, easeInOutCubic), spark.walkTo(DOOR_FAR.x - 90, {mode: 'backward', steps: 1, duration: 0.4}));
  yield* spark.pose({...STAND, head: -12, torso: -6}, 0.3);
  // Through: into the light, and home.
  yield* syncTo('through', 0);
  s.spawn(all(s.cam(DOOR_FAR.add([0, -120]), 0.6, easeInCubic), s.zoom(4.2, 0.6, easeInCubic), s.whiteout.opacity(1, 0.6, easeInCubic)));
  yield* spark.walkTo(DOOR_FAR.x, {steps: 2, duration: 0.55, settle: false});
}

/** A bump: the head whips back, then settles. */
function* jolt(fig: StickFigure, base: Pose): ThreadGenerator {
  yield* fig.pose({...base, head: 26, torso: -18}, 0.06);
  yield* fig.pose(base, 0.3, easeOutCubic);
}

function pick(p: Pose, keys: (keyof Pose)[]): Pose {
  return Object.fromEntries(keys.map(k => [k, p[k]])) as Pose;
}

export {easeInCubic, waitFor};
export type {Cue};

import {Circle} from '@motion-canvas/2d';
import {all, Vector2Signal, easeInCubic, easeInOutCubic, easeInOutSine, easeOutBack, easeOutCubic, linear, ThreadGenerator, Vector2, waitFor} from '@motion-canvas/core';
import {Pose, StickFigure} from '../../components/StickFigure';
import {BEAD, Bulb, crate, Switch, Wire} from '../components/Circuit';
import {G, bolt, sparkBurst} from '../components/Fx';
import {at, syncTo} from '../cues';
import {attach, detach, FLOOR, plant, reach, SIT_Y, Stage, worldOf} from '../stage';
import {SIT, STAND, TIP} from './dark';

/** Leads, parts and the lamp built in the sandbox, handed on to the next act. */
export interface Lamp {
  bulb: Bulb;
  leadA: Wire;
  leadB: Wire;
  sw: Switch;
}

/** Light on/off: bulb, beads and the room light switch together, on the cue frame. */
export function setLit(s: Stage, lamp: {bulb: Bulb; wires: Wire[]}, on: boolean, speed = 260): void {
  lamp.bulb.glow(on ? 1 : 0);
  s.room(on ? 1 : 0.12);
  lamp.wires.forEach((w, i) => w.speed(on ? (i % 2 ? -speed : speed) : 0));
}

/** A small hop of joy: 3-frame crouch, 0.3 s flight on a parabola, 2-frame squash. */
export function* hop(fig: StickFigure, height = 40): ThreadGenerator {
  const y0 = fig.y();
  yield* fig.pose({torso: 18, leftHip: -30, leftKnee: 50, rightHip: -36, rightKnee: 56}, 3 / 60, easeInCubic);
  const flight = 0.3;
  yield* all(
    fig.y(y0 - height, flight / 2, easeOutCubic).to(y0, flight / 2, easeInCubic),
    fig.pose({torso: -6, leftHip: 10, leftKnee: 20, rightHip: -14, rightKnee: 26, leftShoulder: -150, rightShoulder: -140}, flight / 2, easeOutCubic),
  );
  yield* fig.pose({torso: 12, leftHip: -20, leftKnee: 36, rightHip: -24, rightKnee: 40}, 2 / 60);
}

/**
 * 17 - 50 s. Sandbox. The cable is two leads. One lead alone: the beads press
 * and stop. Both leads: the loop closes and the bulb lights. Spark pinches a
 * lead on the beat (a switch is born), fetches a real switch from the crate,
 * and juggles a loose bead until it bites.
 */
export function* sandbox(s: Stage, bulb: Bulb, leadA: Wire, leadB: Wire, aEnd: Vector2Signal<void>, bEnd: Vector2Signal<void>, splay: (v: number, d: number) => ThreadGenerator, out: Partial<Lamp>): ThreadGenerator {
  const spark = s.spark.body;
  const box = crate({x: -400, y: FLOOR, opacity: () => 0.1 + 0.9 * s.room()});
  s.props.add(box);

  yield* syncTo('gogglesUp', 0.2);
  yield* all(s.spark.goggles(0, 0.2, easeOutCubic), spark.pose({head: -10}, 0.2));

  // Up, and the camera eases out: the cable end splits into two leads.
  yield* syncTo('leads', 0.9);
  const standY = standHeight(s, spark);
  s.spawn(all(s.zoom(1.5, 1.6, easeInOutCubic), s.cam(new Vector2(70, 150), 1.6, easeInOutCubic)));
  yield* all(spark.pose({...STAND, rightShoulder: -50, rightElbow: -70, head: -14}, 0.5, easeOutCubic), spark.y(standY, 0.5, easeOutCubic), spark.x(60, 0.5));
  yield* syncTo('leads', 0);
  yield* splay(1, 0.5);
  yield* spark.pose({head: -24, torso: -4}, 0.4, easeOutCubic);

  // One lead to the bulb: the beads press against it and stop.
  yield* syncTo('try1', 0.6);
  const shell = () => worldOf(s, bulb, bulb.shellContact.scale(1));
  const touchA = reach(s, spark, 'rightArm', TIP.add([-10, 30]), {...STAND, head: -6});
  yield* spark.pose(touchA, 0.6, easeInOutCubic);
  leadA.speed(0);
  leadA.jitter(2.2);
  aEnd(shell);
  yield* syncTo('tilt', 0.3);
  yield* spark.pose({head: 24}, 0.3, easeOutCubic);
  yield* waitFor(0.6);
  yield* spark.pose({head: -6}, 0.3, easeInOutSine);

  // Both leads: the loop closes. First light.
  yield* syncTo('try2', 0);
  const tip = () => worldOf(s, bulb, bulb.tipContact);
  bEnd(tip);
  leadA.jitter(0);
  yield* syncTo('light', 0);
  s.lightAt(() => worldOf(s, bulb, bulb.glassCentre));
  setLit(s, {bulb, wires: [leadA, leadB]}, true);
  leadB.beads(1);
  // Awe: a 1.5 s hold, frozen, lit from the front.
  yield* spark.pose({head: -10, torso: -8, leftShoulder: -40, leftElbow: -40}, 0.2, easeOutCubic);
  yield* syncTo('bounce1', 0.38);
  yield* hop(spark, 34);
  yield* spark.pose({...STAND, ...touchA, head: -8}, 0.2, easeOutCubic);

  // Hang the lamp on its leads and step back.
  yield* syncTo('hang', 0.3);
  detach(bulb);
  yield* all(spark.pose({...STAND, head: -14}, 0.4, easeInOutCubic));

  // Pinch the return lead on the beat: off, on, off, on. A switch, by hand.
  const pinchAt = () => leadB.pointAt(leadB.path().total - 70);
  const pinch = reach(s, spark, 'leftArm', pinchAt(), {...STAND, head: -16, torso: 4});
  const away: Pose = {...pinch, leftShoulder: (pinch.leftShoulder ?? 0) + 14, leftElbow: (pinch.leftElbow ?? 0) + 18, torso: 0};
  for (const [k, on] of [
    ['pinch1', false],
    ['release1', true],
    ['pinch2', false],
    ['release2', true],
    ['pinch3', false],
    ['release3', true],
  ] as const) {
    yield* syncTo(k, 0.12);
    yield* spark.pose(on ? away : pinch, 0.12, on ? easeOutCubic : easeInCubic);
    setLit(s, {bulb, wires: [leadA, leadB]}, on);
  }

  // A real switch: fetch one from the crate.
  yield* syncTo('crate', 1.4);
  s.spawn(all(s.cam(new Vector2(-110, 150), 1.4, easeInOutCubic), s.zoom(1.35, 1.4, easeInOutCubic)));
  yield* spark.walkTo(-300, {arriveAt: at('crate'), steps: 5});
  yield* spark.face(-1, 0.1);
  for (const [k, part] of [
    ['rummage1', 'spring'],
    ['rummage2', 'bolt'],
  ] as const) {
    yield* syncTo(k, 0.55);
    s.spawn(spark.pose({torso: 46, leftShoulder: -80, rightShoulder: -60, head: 20}, 0.12, easeInCubic));
    yield* waitFor(0.15);
    s.spawn(toss(s, part, new Vector2(-400, FLOOR - 40), new Vector2(k === 'rummage1' ? -200 : -150, FLOOR - 4), 0.4));
    yield* spark.pose({torso: 30, leftShoulder: -150, rightShoulder: -130}, 0.15, easeOutCubic);
  }
  const sw = new Switch({scale: 0.9});
  s.props.add(sw);
  attach(s, sw, spark.bones.rightFist, new Vector2(0, -10));
  sw.opacity(0);
  yield* syncTo('found', 0.25);
  sw.opacity(1);
  yield* spark.pose({...STAND, rightShoulder: -165, rightElbow: -10, head: -20, torso: -6}, 0.25, easeOutBack);
  yield* waitFor(0.4);
  s.spawn(all(s.cam(new Vector2(70, 150), 1.0, easeInOutCubic), s.zoom(1.5, 1.0, easeInOutCubic)));
  yield* spark.walkTo(90, {arriveAt: at('install') - 0.35, steps: 5, settle: false});
  // Install it in the return lead: the light goes out (the loop is cut).
  const mount = pinchAt();
  yield* syncTo('install', 0.3);
  yield* spark.pose(reach(s, spark, 'rightArm', mount.add([-8, 0]), {...STAND, head: -16}), 0.3, easeInOutCubic);
  detach(sw);
  sw.position(mount);
  sw.rotation(-90);
  sw.closed(0);
  setLit(s, {bulb, wires: [leadA, leadB]}, false);
  // A bead falls out of the cut and rolls along the floor.
  const loose = new Circle({position: mount, size: 9, fill: BEAD, shadowColor: 'rgba(255,210,122,0.9)', shadowBlur: 10});
  s.props.add(loose);
  s.spawn(fallAndRoll(loose, mount, new Vector2(40, FLOOR - 5)));
  // Flip it: light.
  yield* syncTo('flip1', 0.15);
  const press = worldOf(s, sw, sw.button);
  yield* spark.pose(reach(s, spark, 'rightArm', press, {...STAND, head: -16}), 0.15, easeInCubic);
  sw.closed(1);
  setLit(s, {bulb, wires: [leadA, leadB]}, true);
  yield* spark.pose({...STAND, head: -10, leftShoulder: -20, rightShoulder: -40, rightElbow: -60, torso: -4}, 0.3, easeOutCubic);

  // The loose bead: pick it up and juggle it on the beat, until it bites.
  yield* syncTo('scoop', 1.0);
  yield* spark.walkTo(70, {arriveAt: at('scoop') - 0.55, steps: 1, settle: false});
  yield* spark.face(-1, 0.05);
  const scoop = reach(s, spark, 'rightArm', loose.position(), {...STAND, torso: 52, head: 30, leftHip: -30, leftKnee: 40, rightHip: -20, rightKnee: 30});
  yield* spark.pose(scoop, 0.5, easeInOutCubic);
  attach(s, loose, spark.bones.rightFist);
  const JUG: Pose = {...STAND, torso: 0, head: 20, leftShoulder: -60, leftElbow: -50, rightShoulder: -60, rightElbow: -50};
  yield* spark.pose(JUG, 0.35, easeOutCubic);
  const hands = [spark.bones.rightFist, spark.bones.leftFist];
  let from = 0;
  for (const k of ['jug1', 'jug2', 'jug3'] as const) {
    yield* syncTo(k, 0.5);
    const a = worldOf(s, hands[from]);
    const b = worldOf(s, hands[1 - from]);
    detach(loose);
    yield* arc(loose, a, b, 70, 0.5);
    attach(s, loose, hands[1 - from]);
    from = 1 - from;
  }
  // The bead bites: a small zap in the left palm.
  yield* syncTo('jugZap', 0);
  s.spawn(sparkBurst(s.fx, loose.position(), BEAD, 0.4, 6));
  s.spawn(bolt(s.fx, loose.position(), worldOf(s, spark.bones.chest), BEAD, 0.15, 3));
  detach(loose);
  yield* spark.pose({leftShoulder: -20, leftElbow: -10, torso: -10, head: 0}, 0.1, easeOutCubic);
  // Shake the hand out; the bead hops back into the lead it came from.
  const shakes: ThreadGenerator[] = [];
  for (let i = 0; i < 6; i++) shakes.push(spark.joints.leftElbow(i % 2 ? -70 : -10, 0.1));
  s.spawn(chainAll(shakes));
  yield* syncTo('merge', 0.6);
  yield* arc(loose, loose.position(), mount.add([0, -30]), 60, 0.6);
  yield* loose.size(0, 0.1);
  loose.remove();

  // Rest: sit and look up at the light.
  yield* syncTo('rest', 0.4);
  yield* spark.face(1, 0.1);
  yield* all(spark.pose({...SIT, rightShoulder: 10, rightElbow: -30, head: -24, torso: -4}, 0.4, easeInOutCubic), spark.y(SIT_Y, 0.4, easeInCubic));
  yield* syncTo('board', 0.9);
  yield* spark.pose({head: 10}, 0.6, easeInOutSine);

  out.sw = sw;
}

/** Pelvis height that puts a standing Spark's feet on the floor. */
export function standHeight(s: Stage, fig: StickFigure, pose: Pose = STAND): number {
  const saved = fig.y();
  const savedPose = Object.fromEntries(Object.keys(pose).map(k => [k, fig.joints[k as keyof Pose]()]));
  fig.setPose(pose);
  fig.y(0);
  plant(s, fig);
  const y = fig.y();
  fig.setPose(savedPose as Pose);
  fig.y(saved);
  return y;
}

/** A parabolic arc from a to b peaking `h` above the higher end. */
export function* arc(n: Circle | import('@motion-canvas/2d').Node, a: Vector2, b: Vector2, h: number, d: number): ThreadGenerator {
  const top = Math.min(a.y, b.y) - h;
  for (let t = 0; t <= d + 1e-6; t += 1 / 60) {
    const u = Math.min(1, t / d);
    const x = a.x + (b.x - a.x) * u;
    // Quadratic Bezier through the apex height: honest constant-gravity arc.
    const y = (1 - u) * (1 - u) * a.y + 2 * u * (1 - u) * (2 * top - (a.y + b.y) / 2) + u * u * b.y;
    n.position(new Vector2(x, y));
    yield;
  }
  n.position(b);
}

function* chainAll(tasks: ThreadGenerator[]): ThreadGenerator {
  for (const t of tasks) yield* t;
}

/** A part thrown over the shoulder: flies on a parabola and lands with a tink. */
function* toss(s: Stage, kind: 'spring' | 'bolt', from: Vector2, to: Vector2, d: number): ThreadGenerator {
  const node =
    kind === 'spring'
      ? new Circle({size: 18, stroke: '#c9c9d3', lineWidth: 3, lineDash: [4, 3]})
      : new Circle({size: 12, fill: '#9a9aa6'});
  node.position(from);
  s.props.add(node);
  s.spawn(node.rotation(720, d, linear));
  yield* arc(node, from, to, 120, d);
}

/** Fall under gravity, bounce once, then roll to a stop at `rest`. */
function* fallAndRoll(n: Circle, from: Vector2, rest: Vector2): ThreadGenerator {
  let p = from;
  let v = new Vector2(-60, 0);
  let bounced = false;
  for (let t = 0; t < 1.2; t += 1 / 60) {
    v = v.add(new Vector2(0, G / 60));
    p = p.add(v.scale(1 / 60));
    if (p.y > rest.y) {
      p = new Vector2(p.x, rest.y);
      if (bounced) break;
      v = new Vector2(v.x, -v.y * 0.35);
      bounced = true;
    }
    n.position(p);
    yield;
  }
  yield* n.position(rest, 0.6, easeOutCubic);
}

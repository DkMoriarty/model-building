import {Circle, Line, Node, Rect} from '@motion-canvas/2d';
import {all, createSignal, easeInCubic, easeInOutCubic, easeInOutSine, easeOutBack, easeOutCubic, linear, ThreadGenerator, useLogger, useTime, Vector2, waitFor} from '@motion-canvas/core';
import {Pose} from '../../components/StickFigure';
import {withAlpha} from '../../figureSpec';
import {Board} from '../components/Board';
import {BEAD, Bulb, Dial, Eye, MIND, socket, TIER, Wire} from '../components/Circuit';
import {G, bolt, shards, sparkBurst} from '../components/Fx';
import {at, Cue, syncTo} from '../cues';
import {attach, FLOOR, reach, SIT_Y, Stage, worldOf} from '../stage';
import {BOARD_AT, CARD_SPOT, delayed, dialOf, Lab} from './board';
import {openingFrame, shakeMinor, SIT, STAND, toyBeats} from './dark';
import {arc, hop, standHeight} from './sandbox';

/** The auto-trials: noisy and clean cards, each with its true label. */
const AUTO: [Cue, number[], boolean][] = [
  ['auto1', [0, 1, 1, 1, 0, 1, 1, 1, 0], true],
  ['auto2', [0, 1, 1, 1, 1, 1, 0, 1, 0], false],
  ['auto3', [1, 1, 1, 1, 0, 1, 1, 1, 1], true],
  ['auto4', [0, 1, 0, 1, 1, 1, 0, 1, 0], false],
  ['auto5', [1, 1, 1, 1, 0, 1, 0, 1, 1], true],
  ['auto6', [0, 1, 0, 1, 1, 1, 0, 1, 0], false],
];
const SOCKET_AT = new Vector2(905, 250);
const WALL_SOCKET = new Vector2(330, 236);
const MASTER = new Vector2(330, 130);

/**
 * 124 - 181 s. The accident, the growth, the over-reach and the bookend.
 * Spark trips over the judge's loose lead; it lands in the dial motors, so
 * every NO now turns the dials by itself. The machine learns without Spark.
 * Fed more power it copies itself and learns Spark's shape; cranked to the
 * maximum, it surges and every bulb blows. In the dark, Spark sits with a
 * dead bulb, as at the start, and the bulb lights by itself. Violet.
 */
export function* mind(s: Stage, lab: Lab): ThreadGenerator {
  const spark = s.spark.body;
  const board = lab.board;
  const standY = spark.y();

  // ---- Celebrate, back-step, trip over the loose lead.
  yield* syncTo('celebrate', 0.38);
  yield* hop(spark, 30);
  yield* spark.pose(STAND, 0.15);
  s.spawn(spark.walkTo(410, {mode: 'backward', arriveAt: at('trip'), steps: 2, settle: false}));
  yield* syncTo('trip', 0);
  yield* spark.pose({torso: -30, head: -30, leftShoulder: -120, rightShoulder: -100, leftElbow: -20, rightElbow: -20, leftHip: -50, leftKnee: 10, rightHip: 20, rightKnee: 30}, 0.12, easeOutCubic);
  yield* syncTo('fall', 0.3);
  yield* all(spark.pose({...SIT, torso: -20, head: -10, leftShoulder: 40, rightShoulder: 40, leftElbow: -20, rightElbow: -20}, 0.3, easeInCubic), spark.y(SIT_Y, 0.3, easeInCubic), spark.x(380, 0.3));
  s.spawn(shakeMinor(s, 8, 5));
  // The lead whips up; its plug sails over and lands in the dial motors' socket.
  const sock = socket({position: SOCKET_AT, scale: 0.5});
  s.props.add(sock);
  const plugAt = Vector2.createSignal(lab.plug.position());
  const anchor = new Vector2(1250, FLOOR - 4);
  lab.looseLine.points(() => {
    const p = plugAt();
    const sag = new Vector2((anchor.x + p.x) / 2, FLOOR - 4);
    return [anchor, sag, p];
  });
  lab.plug.position(() => plugAt());
  yield* arc(proxy(plugAt), plugAt(), SOCKET_AT.add([0, 10]), 160, at('drape') - at('fall') - 2 / 60);
  yield* syncTo('drape', 0);
  s.spawn(sparkBurst(s.fx, SOCKET_AT, MIND, 0.5, 8));
  board.dials.forEach((d, i) => s.spawn(delayed(i * 0.03, d.motor(1, 0.08).to(0.25, 0.4))));
  // The easel's crank, nudged by the lead, starts turning.
  const crank = new Node({position: lab.easel.position().add([0, 120])});
  crank.add(new Circle({size: 22, stroke: '#8a7a6a', lineWidth: TIER.structure}));
  crank.add(new Line({points: [[0, 0], [0, -11]], stroke: '#8a7a6a', lineWidth: TIER.structure}));
  s.props.add(crank);
  crank.rotation(() => (s.time() - at('drape')) * 240);

  // ---- The machine practises alone. Spark watches from the floor.
  yield* syncTo('watch', 0.4);
  yield* spark.pose({torso: 6, head: -6, leftShoulder: 20, rightShoulder: 30, rightElbow: -60}, 0.4, easeInOutSine);
  const w = lab.w;
  for (const [cue, shape, label] of AUTO) {
    yield* syncTo(cue, 0.12);
    lab.cardSlot.scale([0, 1]);
    lab.setCard(shape);
    s.spawn(lab.cardSlot.scale(1, 0.12, easeOutCubic));
    const result: {right?: boolean} = {};
    yield* lab.trial(shape, at(cue), at(cue) + 0.9, label, result);
    if (!result.right) {
      // The NO current now runs the motors: the dials turn by themselves
      // (the perceptron rule: nudge every lit input towards the right answer).
      yield* syncTo(at(cue) + 1.2);
      shape.forEach((v, i) => {
        if (!v) return;
        w[i] += label ? 0.15 : -0.15;
        const d = board.dials[i];
        s.spawn(all(d.value(dialOf(w[i]), 0.25, easeInOutCubic), d.motor(1, 0.05).to(0.25, 0.5)));
      });
    }
  }
  if (Math.abs(w[4] + 0.2) > 1e-6) useLogger().warn(`auto-trials: centre weight ${w[4].toFixed(2)}, expected -0.20`);

  // ---- Violet: the bulb glows by itself, a colour Spark never gave it.
  yield* syncTo('violet', 0);
  board.bulb.tint(MIND);
  yield* board.bulb.glow(0.7, 0.4, easeOutCubic);
  s.spawn(pulse(board.bulb, at('plug')));
  yield* syncTo('grin', 0.3);
  yield* spark.pose({torso: -16, head: -14, leftShoulder: 30, leftElbow: -10, rightShoulder: -150, rightElbow: -30}, 0.3, easeOutBack);
  // Lie back, hands behind the head: free work.
  yield* syncTo('relax', 0.5);
  yield* all(spark.rotation(-70, 0.6, easeInOutCubic), spark.y(SIT_Y + 6, 0.6), spark.pose({torso: 0, head: 10, leftShoulder: -170, leftElbow: -140, rightShoulder: -170, rightElbow: -140, leftHip: -20, leftKnee: 40, rightHip: -60, rightKnee: 90}, 0.6, easeInOutCubic));

  // ---- Feed it: up, unspool the board's power cable, plug it into the wall.
  const wall = socket({position: WALL_SOCKET, scale: 0.7});
  const master = new Dial({position: MASTER, size: 56, value: 0.3});
  s.props.add([wall, master]);
  wall.scale(0);
  master.scale(0);
  yield* syncTo('plug', 1.4);
  yield* all(spark.rotation(0, 0.4, easeOutCubic), spark.pose(STAND, 0.4), spark.y(standY, 0.4), wall.scale(0.7, 0.3, easeOutBack), master.scale(1, 0.3, easeOutBack));
  const cableEnd = Vector2.createSignal(new Vector2(BOARD_AT.x + 60, FLOOR - 4));
  const cable = new Line({points: () => [new Vector2(BOARD_AT.x + 100, FLOOR - 6), new Vector2(cableEnd().x, FLOOR - 6), cableEnd()], stroke: '#3c3c48', lineWidth: TIER.figure, lineCap: 'round'});
  s.props.add(cable);
  yield* spark.face(-1, 0.1);
  yield* spark.walkTo(400, {arriveAt: at('plug') - 0.3, steps: 1, settle: false});
  const into = WALL_SOCKET.add([0, 6]);
  yield* all(spark.pose(reach(s, spark, 'rightArm', into, {...STAND, head: 0}), 0.3, easeInOutCubic), cableEnd(into, 0.3, easeInOutCubic));
  yield* syncTo('plug', 0);
  const boost = createSignal(1);
  board.wires.forEach((wi, i) => {
    wi.beads(1);
    wi.color(MIND);
    wi.speed(() => boost() * (i < 9 ? 260 : 420));
  });
  board.eyes.forEach(e => e.tint(MIND));
  board.bulb.glow(1);
  s.lightColor(MIND);
  s.lightAt(worldOf(s, board.bulb, board.bulb.glassCentre));

  // ---- It copies itself, board after board, into the dark.
  s.spawn(all(s.zoom(0.8, 5, easeInOutCubic), s.cam(new Vector2(880, 0), 5, easeInOutCubic)));
  const spots: [Vector2, number][] = [
    [new Vector2(230, -400), 0.5],
    [new Vector2(900, -420), 0.5],
    [new Vector2(1570, -400), 0.5],
    [new Vector2(1850, 150), 0.45],
  ];
  const copies: Board[] = [];
  for (const [k, cue] of (['copy1', 'copy2', 'copy3', 'copy4'] as const).entries()) {
    yield* syncTo(cue, 0.4);
    const c = new Board({position: BOARD_AT, scale: 1, opacity: 0, time: () => s.time()});
    c.wires.forEach(wi => {
      s.wire(wi);
      wi.beads(1);
      wi.color(MIND);
      wi.speed(() => boost() * 300);
    });
    c.eyes.forEach(e => {
      e.tint(MIND);
      e.lit(0.3);
    });
    c.bulb.tint(MIND);
    c.bulb.glow(0.8);
    c.bulb.showLevel(0);
    c.dials.forEach((d, i) => d.value(dialOf(w[i])));
    s.back.add(c);
    copies.push(c);
    const [pos, sc] = spots[k];
    yield* all(c.opacity(0.75, 0.15), c.position(pos, 0.4, easeOutCubic), c.scale(sc, 0.4, easeOutCubic));
  }

  // ---- Every eye turns to Spark at once. Spark freezes.
  yield* syncTo('look', 0);
  const allEyes = [...board.eyes, ...copies.flatMap(c => c.eyes)];
  const head = () => worldOf(s, spark.bones.head);
  for (const e of allEyes) {
    e.lit(Math.max(e.lit(), 0.4));
    e.look(() => head().sub(worldOf(s, e)).normalized);
  }
  spark.setPose({...STAND, torso: -6, head: -14, leftShoulder: 20, rightShoulder: -30, rightElbow: -40});
  yield* syncTo('turnLook', 0);
  yield* spark.face(1, 0.5);
  yield* spark.pose({head: -6}, 0.4, easeInOutSine);
  // It has learned Spark's shape.
  yield* syncTo('learnSpark', 0);
  const figure = [0, 1, 0, 1, 1, 1, 1, 0, 1];
  board.eyes.forEach((e, i) => e.lit(figure[i] ? 1 : 0.15, 0.2));
  lab.setCard(figure);
  copies.forEach(c => c.eyes.forEach((e, i) => e.lit(figure[i] ? 1 : 0.1, 0.2)));
  // Delight, not fear: Spark claps.
  for (let i = 0; i < 3; i++) {
    yield* spark.pose({leftShoulder: -80, leftElbow: -60, rightShoulder: -80, rightElbow: -60}, 0.12);
    yield* spark.pose({leftShoulder: -60, leftElbow: -100, rightShoulder: -60, rightElbow: -100}, 0.12);
  }

  // ---- Smarter: to the master dial, crank it all the way.
  yield* syncTo('toDial', 0);
  yield* spark.face(-1, 0.15);
  yield* spark.walkTo(395, {arriveAt: at('crank') - 0.4, steps: 1, settle: false});
  const knob = MASTER.add([0, 0]);
  yield* spark.pose(reach(s, spark, 'rightArm', knob.add([14, 10]), {...STAND, head: -10}), 0.4, easeInOutCubic);
  for (const [t, v] of [
    [0, 0.45],
    [0.4, 0.6],
    [0.7, 0.75],
    [0.95, 0.88],
    [1.2, 1],
  ] as const) {
    yield* syncTo(at('crank') + t);
    s.spawn(master.value(v, 0.08));
    s.spawn(boost(1 + v * 3, 0.1));
    s.spawn(spark.joints.rightElbow((spark.joints.rightElbow() ?? 0) - 6, 0.08).to(spark.joints.rightElbow(), 0.08));
  }

  // ---- Silence. Everything holds its breath.
  yield* syncTo('max', 0);
  boost(0);
  const bulbs = [board.bulb, ...copies.map(c => c.bulb), lab.lamps[2]];
  bulbs.forEach(b => b.glow(0.25, 0.3));
  s.spawn(s.room(0.3, 0.3));
  yield* spark.pose({...STAND, head: -34, torso: -6, rightShoulder: -60, rightElbow: -40}, 0.4, easeOutCubic);

  // ---- SURGE: 3 frames of white, the major shake, every bulb flares.
  yield* syncTo('surge', 0);
  s.whiteout.opacity(1);
  boost(12);
  bulbs.forEach(b => {
    b.tint(MIND);
    b.glow(1);
    b.scale(b.scale().x * 1.12);
  });
  s.room(1);
  s.spawn(shakeMajor(s, 25, 40));
  s.spawn(spark.pose({torso: -24, head: -40, leftShoulder: -120, rightShoulder: -130, leftElbow: -70, rightElbow: -70}, 0.1, easeOutCubic));
  yield* waitFor(3 / 60);
  s.whiteout.opacity(0);
  // ---- They blow, one after another.
  yield* syncTo('blow', 0);
  // Late shards from the ceiling lamp, landing on their cues in the dark.
  for (const cue of ['tinkle1', 'tinkle2'] as const) s.spawn(lateShard(s, cue));
  for (const [i, b] of bulbs.entries()) {
    const g = worldOf(s, b, b.glassCentre);
    b.glass(0);
    b.glow(0);
    s.spawn(sparkBurst(s.fx, g, MIND, 0.6, 10));
    s.spawn(shards(s.fx, g, FLOOR - 3, MIND, 8, 3));
    if (i < bulbs.length - 1) yield* waitFor(0.15);
  }
  boost(0);
  allEyes.forEach(e => e.lit(0, 0.6));
  [board, ...copies].forEach(c => c.wires.forEach(wi => wi.beads(0, 0.8)));
  yield* s.room(0, 0.8);
  yield* syncTo('dark', 0);
  lab.lamps.forEach(l => l.glow(0));
  yield* all(spark.pose({...SIT, head: 20, torso: 16}, 1.0, easeInOutSine), spark.y(SIT_Y, 1.0, easeInOutSine), spark.face(1, 0.2));

  // ---- The bookend: the first shot again. A dead bulb, the dark.
  yield* syncTo('sitLast', 0);
  s.props.removeChildren();
  s.back.removeChildren();
  s.fx.removeChildren();
  s.room(0);
  spark.setPose(SIT);
  spark.rotation(0);
  spark.position([0, SIT_Y]);
  spark.face(1);
  openingFrame(s);
  const dead = new Bulb({scale: 0.8});
  s.props.add(dead);
  attach(s, dead, spark.bones.rightFist, new Vector2(4, -6));
  // The single eye that will open, waiting shut in the dark behind Spark.
  const eye = new Eye({position: [-190, 70], size: 34, opacity: 0});
  eye.open(0);
  eye.tint(MIND);
  s.props.add(eye);
  yield* toyBeats(s, dead, 'turnLast', 'tapLast', 'holdLast', 'sighLast');
  // It lights by itself. Violet.
  yield* syncTo('glowLast', 0);
  dead.tint(MIND);
  dead.glow(1);
  s.lightColor(MIND);
  s.lightAt(() => worldOf(s, dead, dead.glassCentre));
  s.room(0.8);
  yield* waitFor(0.2);
  yield* spark.pose({head: 26, torso: 10, rightShoulder: -70, rightElbow: -90}, 1.0, easeInOutSine);
  // Behind, in the dark, an eye opens; then it turns to look at Spark.
  yield* syncTo('eye', 0);
  eye.opacity(1);
  eye.look(new Vector2(0, 1));
  yield* all(eye.open(1, 0.5, easeOutCubic), eye.lit(0.8, 0.5));
  yield* syncTo('eyeTurn', 0);
  eye.look(() => worldOf(s, spark.bones.head).sub(eye.position()).normalized);
  // Cut to black.
  yield* syncTo('end', 0);
  s.blackout.opacity(1);
}

/** Major-tier shake: multidirectional, decaying over `frames`. */
function* shakeMajor(s: Stage, px: number, frames: number): ThreadGenerator {
  for (let i = 0; i < frames; i++) {
    const a = i * 2.39996;
    const k = (1 - i / frames) ** 2;
    s.shake(new Vector2(Math.cos(a), Math.sin(a)).scale(px * k));
    yield;
  }
  s.shake(Vector2.zero);
}

/** A slow violet breathing pulse until `until`. */
function* pulse(b: Bulb, until: number): ThreadGenerator {
  while (useTime() < until - 1.3) {
    yield* b.glow(0.45, 0.6, easeInOutSine);
    yield* b.glow(0.75, 0.6, easeInOutSine);
  }
}

/** A shard dropping from the ceiling lamp, timed to land on `cue`. */
function* lateShard(s: Stage, cue: Cue): ThreadGenerator {
  const from = new Vector2(1100, -330);
  const fall = Math.sqrt((2 * (FLOOR - 3 - from.y)) / G);
  yield* syncTo(cue, fall);
  const shard = new Line({points: [[-5, -3], [6, -1], [-1, 5]], closed: true, fill: withAlpha(MIND, 0.4), stroke: '#c9c9d3', lineWidth: 1.5, position: from});
  s.fx.add(shard);
  for (let t = 0; t <= fall + 1e-6; t += 1 / 60) {
    shard.y(from.y + 0.5 * G * t * t);
    yield;
  }
  shard.y(FLOOR - 3);
}

/** A node-like proxy so `arc` can drive a Vector2 signal. */
function proxy(sig: {(): Vector2; (v: Vector2): unknown}) {
  return {position: (v: Vector2) => sig(v)} as unknown as Node;
}

export {Rect, Wire, BEAD, CARD_SPOT, bolt, linear, easeInOutSine};

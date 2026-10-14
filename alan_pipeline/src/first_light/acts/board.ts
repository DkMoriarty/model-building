import {Circle, Line, Node, Rect} from '@motion-canvas/2d';
import {all, createSignal, easeInCubic, easeInOutCubic, easeInOutSine, easeOutBack, easeOutCubic, SimpleSignal, ThreadGenerator, useLogger, Vector2, waitFor} from '@motion-canvas/core';
import {Pose} from '../../components/StickFigure';
import {Board} from '../components/Board';
import {BAD_RED, BEAD, Bulb, card, indicator, OK_GREEN, SHAPES, ShapeName, TIER} from '../components/Circuit';
import {bolt, sparkBurst} from '../components/Fx';
import {at, syncTo} from '../cues';
import {attach, detach, FLOOR, reach, Stage, worldOf} from '../stage';
import {shakeMinor, STAND} from './dark';
import {hop, standHeight} from './sandbox';

/** World positions for the board set. */
export const BOARD_AT = new Vector2(1000, FLOOR);
export const CARD_SPOT = 470;
export const DIAL_SPOT = 800;
export const EASEL = new Vector2(560, 130);

/** Weight -> dial needle (0..1). */
export const dialOf = (w: number) => (w + 0.2) / 0.6;

/** The board, its judge lamps and the learning state, shared with the last act. */
export interface Lab {
  board: Board;
  w: number[];
  judge: {bad: SimpleSignal<number, void>; good: SimpleSignal<number, void>};
  easel: Node;
  cardSlot: Node;
  lamps: Bulb[];
  /** Show a card and run one trial; returns whether the bulb lit. */
  trial(shape: number[], seeAt: number, judgeAt: number, label: boolean, result: {right?: boolean}): ThreadGenerator;
  setCard(shape: number[] | ShapeName): void;
  looseLine: Line;
  plug: Rect;
}

/**
 * 78 - 124 s. Midpoint: Spark pulls the goggles down, lights the room and
 * builds a machine that can learn: eyes, dials (weights), a bulb that fills
 * (threshold), and a judge. Then teaches it, card by card, by turning dials.
 */
export function* boardAct(s: Stage, lab: Partial<Lab>): ThreadGenerator {
  const spark = s.spark.body;

  // Serious now: goggles down, stand.
  yield* syncTo('gogglesDown', 0.25);
  yield* spark.pose({rightShoulder: -150, rightElbow: -90, head: 0, torso: 6}, 0.25, easeOutCubic);
  yield* s.spark.goggles(1, 0.12, easeInCubic);
  const standY = standHeight(s, spark);
  yield* all(spark.pose(STAND, 0.4, easeOutCubic), spark.y(standY, 0.4, easeOutCubic));

  // A pull-cord: the room's ceiling lamps come on, left to right.
  const cordX = spark.x() + 60;
  const cordEnd = createSignal(120);
  const cord = new Line({points: () => [new Vector2(cordX, -700), new Vector2(cordX, cordEnd())], stroke: '#6b6b78', lineWidth: TIER.detail});
  const knob = new Circle({size: 12, fill: '#c9c9d3', position: () => new Vector2(cordX, cordEnd())});
  s.props.add([cord, knob]);
  const lamps: Bulb[] = [];
  for (const x of [-200, 450, 1100]) {
    const b = new Bulb({x, y: -330, rotation: 180, radius: 24});
    s.props.add(new Line({points: [new Vector2(x, -900), new Vector2(x, -345)], stroke: '#6b6b78', lineWidth: TIER.detail}));
    s.props.add(b);
    lamps.push(b);
  }
  yield* syncTo('newBulb', 0.3);
  const grab = reach(s, spark, 'rightArm', new Vector2(cordX, 110), {...STAND, head: -20});
  yield* spark.pose(grab, 0.3, easeInOutCubic);
  yield* all(cordEnd(150, 0.08), spark.pose({...grab, rightShoulder: (grab.rightShoulder ?? 0) + 10}, 0.08));
  s.lightColor(BEAD);
  s.lightAt(new Vector2(450, -330));
  s.room(0.15);
  s.spawn(cordEnd(120, 0.3, easeOutBack));
  for (const [i, b] of lamps.entries()) {
    s.spawn(
      (function* () {
        yield* waitFor(i * 0.12);
        b.glow(1);
      })(),
    );
  }
  s.spawn(s.room(1, 0.4));

  // ---- The arena shifts: pull out and run to the empty wall.
  yield* syncTo('pullOut', 0);
  s.spawn(all(s.cam(new Vector2(880, 150), 2.6, easeInOutCubic), s.zoom(1.35, 2.6, easeInOutCubic)));
  yield* spark.walkTo(560, {arriveAt: at('pullOut') + 2.4, steps: 8, settle: false});
  yield* spark.pose({...STAND, head: -16}, 0.2);

  const board = new Board({position: BOARD_AT, time: () => s.time()});
  board.wires.forEach(w => s.wire(w));
  s.props.add(board);
  board.eyes.forEach(e => e.scale(0));
  board.dials.forEach(d => d.scale(0));
  board.wiresIn.forEach(w => w.trim(0));
  board.wiresOut.forEach(w => w.trim(0));
  board.bulb.scale(0);
  const w = [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1];
  board.dials.forEach((d, i) => d.value(dialOf(w[i])));

  // Eyes: Spark throws both arms up; nine eyes pop in a ripple.
  yield* syncTo('eyes', 0.2);
  yield* spark.pose({leftShoulder: -150, rightShoulder: -160, leftElbow: -20, rightElbow: -20, head: -20}, 0.2, easeOutCubic);
  for (const [i, e] of board.eyes.entries()) s.spawn(delayed(i * 0.06, e.scale(1, 0.25, easeOutBack)));
  // Wires draw on as Spark walks along them.
  yield* syncTo('wires', 0.8);
  s.spawn(spark.walkTo(790, {arriveAt: at('wires'), steps: 3, settle: false}));
  yield* syncTo('wires', 0);
  for (const wi of board.wiresIn) s.spawn(wi.trim(1, 0.5, easeOutCubic));
  for (const wo of board.wiresOut) s.spawn(delayed(0.3, wo.trim(1, 0.8, easeOutCubic)));
  // Dials.
  yield* syncTo('dials', 0.2);
  yield* spark.pose({rightShoulder: -100, rightElbow: -40, head: -20}, 0.2, easeOutCubic);
  for (const [i, d] of board.dials.entries()) s.spawn(delayed(i * 0.06, d.scale(1, 0.25, easeOutBack)));
  // The big bulb: screwed onto its pedestal.
  yield* syncTo('bigBulb', 0.9);
  s.spawn(spark.walkTo(1010, {arriveAt: at('bigBulb') - 0.1, steps: 3, settle: false}));
  yield* syncTo('bigBulb', 0.3);
  board.bulb.scale(1);
  board.bulb.y(-160);
  board.bulb.opacity(0);
  yield* all(board.bulb.opacity(1, 0.15), board.bulb.y(-100, 0.3, easeInCubic), board.bulb.rotation(360, 0.3));
  board.bulb.rotation(0);
  // The judge: a red lamp and a green lamp.
  const bad = createSignal(0);
  const good = createSignal(0);
  const judge = new Node({position: [1250, 60], children: [indicator(BAD_RED, 'NO', () => bad(), {y: -40}), indicator(OK_GREEN, 'YES', () => good(), {y: 60})]});
  s.props.add(judge);
  // Judge wire: from the bulb's pedestal along the floor to the judge.
  s.props.add(new Line({points: [new Vector2(1120, FLOOR - 6), new Vector2(1250, FLOOR - 6), new Vector2(1250, 150)], stroke: '#6b6b78', lineWidth: TIER.structure, end: 0}));
  const judgeWire = s.props.children()[s.props.children().length - 1] as Line;
  // The judge's spare lead: left lying loose along the floor, plug and all.
  const looseLine = new Line({points: [new Vector2(1250, FLOOR - 4), new Vector2(420, FLOOR - 4)], stroke: '#6b6b78', lineWidth: TIER.structure, end: 0});
  const plug = new Rect({position: [420, FLOOR - 8], width: 18, height: 10, radius: 2, fill: '#2a2a33', stroke: '#9a9aa6', lineWidth: TIER.detail, opacity: 0});
  s.props.add([looseLine, plug]);
  yield* syncTo('judge', 0);
  judge.scale(0);
  s.spawn(all(looseLine.end(1, 0.7), delayed(0.6, plug.opacity(1, 0.15))));
  yield* all(judge.scale(1, 0.3, easeOutBack), judgeWire.end(1, 0.4));

  // The easel for the cards, and walk back to admire.
  const easel = new Node({position: EASEL});
  easel.add(new Line({points: [[-26, 60], [0, 0], [26, 60]], stroke: '#8a7a6a', lineWidth: TIER.structure}));
  easel.add(new Line({points: [[0, 0], [0, FLOOR - EASEL.y]], stroke: '#8a7a6a', lineWidth: TIER.structure}));
  easel.add(new Rect({y: 44, width: 84, height: 6, fill: '#8a7a6a'}));
  const cardSlot = new Node({});
  easel.add(cardSlot);
  s.props.add(easel);
  easel.scale(0);
  yield* syncTo('cards', 0.8);
  s.spawn(spark.walkTo(CARD_SPOT, {arriveAt: at('admire'), steps: 6}));
  yield* syncTo('cards', 0);
  yield* easel.scale(1, 0.3, easeOutBack);
  yield* syncTo('admire', 0);
  yield* spark.pose({...STAND, torso: -6, head: -10, leftShoulder: 30, leftElbow: -100, rightShoulder: 30, rightElbow: -100}, 0.3, easeOutCubic);
  yield* syncTo('gogglesUp2', 0.15);
  yield* s.spark.goggles(0, 0.15, easeOutCubic);

  // ---- Trials.
  let current: Node | null = null;
  const setCard = (shape: number[] | ShapeName) => {
    current?.remove();
    const pattern = typeof shape === 'string' ? [...SHAPES[shape]] : shape;
    current = patternCard(pattern);
    cardSlot.add(current);
  };
  const trial = function* (shape: number[], seeAt: number, judgeAt: number, label: boolean, result: {right?: boolean}): ThreadGenerator {
    yield* syncTo(seeAt);
    const lit = shape.map(v => v > 0);
    board.eyes.forEach((e, i) => {
      e.look(new Vector2(-1, 0));
      if (lit[i]) s.spawn(delayed(i * 0.04, e.lit(1, 0.1)));
    });
    board.wiresIn.forEach((wi, i) => {
      wi.beads(lit[i] ? 1 : 0);
      wi.speed(lit[i] ? 220 : 0);
    });
    const sum = shape.reduce((a, v, i) => a + v * w[i], 0);
    board.wiresOut.forEach((wo, i) => {
      const flow = lit[i] ? Math.max(0, w[i]) : 0;
      wo.beads(flow > 0 ? 1 : 0);
      wo.speed(flow * 900);
    });
    const level = Math.max(0, Math.min(1, sum / 2));
    const on = sum > 1;
    yield* board.bulb.level(level, judgeAt - seeAt - 0.1, easeInOutSine);
    if (on) board.bulb.glow(1);
    yield* syncTo(judgeAt);
    const right = on === label;
    result.right = right;
    (right ? good : bad)(1);
    // Reset in the background: eyes off, the level drains, beads stop.
    s.spawn(
      (function* () {
        yield* waitFor(0.5);
        good(0);
        bad(0);
        board.eyes.forEach(e => e.lit(0, 0.2));
        board.wiresIn.forEach(wi => wi.speed(0));
        board.wiresOut.forEach(wo => wo.speed(0));
        board.bulb.glow(0);
        yield* board.bulb.level(0, 0.3);
      })(),
    );
  };
  Object.assign(lab, {board, w, judge: {bad, good}, easel, cardSlot, lamps, trial, setCard, looseLine, plug});

  // Trial 1: a ring. The bulb doesn't fill enough: NO.
  yield* placeCard(s, lab as Lab, 'ring', 'card1');
  yield* runTrial(lab as Lab, SHAPES.ring, 'see1', 'buzz1', true, false);
  yield* flinch(s);
  // Turn a dial by finger: zap. Then with a screwdriver.
  yield* syncTo('dial1', 0.9);
  yield* spark.walkTo(DIAL_SPOT, {arriveAt: at('dial1') - 0.3, steps: 4, settle: false});
  const d0 = worldOf(s, board.dials[0]);
  yield* spark.pose(reach(s, spark, 'rightArm', d0.add([-4, 0]), {...STAND, head: -16}), 0.3, easeInOutCubic);
  yield* syncTo('dialZap', 0);
  s.spawn(sparkBurst(s.fx, d0, BEAD, 0.5, 8));
  s.spawn(bolt(s.fx, d0, worldOf(s, spark.bones.head), BEAD, 0.2, 3));
  s.spawn(shakeMinor(s, 6, 4));
  yield* all(s.spark.goggles(1, 0.08), spark.pose({...STAND, torso: -14, head: -20, rightShoulder: -60, rightElbow: -10}, 0.1, easeOutCubic));
  const driver = screwdriver();
  s.props.add(driver);
  attach(s, driver, spark.bones.rightFist);
  driver.scale(0);
  yield* syncTo('tool', 0.2);
  yield* all(s.spark.goggles(0, 0.2), driver.scale(1, 0.2, easeOutBack));
  const ringIdx = [0, 1, 2, 3, 5, 6, 7, 8];
  const groups = [[0, 1, 2], [3, 5], [6, 7, 8]];
  for (const [g, k] of (['turn1', 'turn2', 'turn3'] as const).entries()) {
    yield* turnDials(s, lab as Lab, groups[g], 0.15, k);
  }
  check(w, ringIdx, 0.25);
  // Trial 2: ring again: YES.
  yield* syncTo('card2', 0.8);
  yield* spark.walkTo(CARD_SPOT, {arriveAt: at('card2') - 0.35, steps: 4, settle: false});
  yield* placeCard(s, lab as Lab, 'ring', 'card2');
  yield* runTrial(lab as Lab, SHAPES.ring, 'see2', 'ding1', true, true);
  yield* syncTo('proud', 0);
  yield* spark.pose({...STAND, torso: -8, head: -14, leftShoulder: 40, leftElbow: -110, rightShoulder: 40, rightElbow: -110}, 0.25, easeOutCubic);
  // Trial 3: a cross. The bulb lights for the wrong shape: NO. Facepalm.
  yield* placeCard(s, lab as Lab, 'cross', 'card3');
  yield* runTrial(lab as Lab, SHAPES.cross, 'see3', 'buzz2', false, false);
  yield* syncTo('facepalm', 0);
  yield* spark.pose({rightShoulder: -150, rightElbow: -130, head: 24, torso: 14}, 0.2, easeOutCubic);
  yield* syncTo('turn4', 1.0);
  yield* spark.walkTo(DIAL_SPOT, {arriveAt: at('turn4') - 0.3, steps: 3, settle: false});
  yield* turnDials(s, lab as Lab, [1, 3, 4], -0.15, 'turn4');
  yield* turnDials(s, lab as Lab, [5, 7], -0.15, 'turn5');
  // Trials 4 and 5: cross dark (YES), ring lit (YES).
  yield* syncTo('card4', 1.2);
  yield* spark.walkTo(CARD_SPOT, {arriveAt: at('card4') - 0.35, steps: 4, settle: false});
  yield* placeCard(s, lab as Lab, 'cross', 'card4');
  yield* runTrial(lab as Lab, SHAPES.cross, 'see4', 'ding2', false, true);
  yield* placeCard(s, lab as Lab, 'ring', 'card5');
  yield* runTrial(lab as Lab, SHAPES.ring, 'card5', 'ding3', true, true, 0.3);
  // A dance on the beat.
  yield* syncTo('dance', 0);
  driver.opacity(0);
  for (let i = 0; i < 2; i++) {
    yield* spark.pose({torso: i % 2 ? 8 : -8, head: i % 2 ? -10 : 10, leftShoulder: i % 2 ? -140 : -40, rightShoulder: i % 2 ? -40 : -140, leftElbow: -30, rightElbow: -30, leftHip: i % 2 ? -10 : 8, rightHip: i % 2 ? 8 : -10}, 0.6, easeInOutSine);
  }
}

/** Spark puts a card on the easel: the old one flips away, the new one flips in. */
function* placeCard(s: Stage, lab: Lab, shape: ShapeName, cue: Parameters<typeof syncTo>[0]): ThreadGenerator {
  const spark = s.spark.body;
  const slot = worldOf(s, lab.cardSlot);
  yield* syncTo(cue, 0.3);
  yield* spark.pose(reach(s, spark, 'rightArm', slot.add([-30, -10]), {...STAND, head: 0}), 0.3, easeInOutCubic);
  lab.setCard(shape);
  lab.cardSlot.scale([0, 1]);
  yield* lab.cardSlot.scale(1, 0.12, easeOutCubic);
  s.spawn(spark.pose({...STAND, head: -10, rightShoulder: -20, rightElbow: -30}, 0.3, easeOutCubic));
}

function* runTrial(lab: Lab, shape: readonly number[], see: Parameters<typeof syncTo>[0], judge: Parameters<typeof syncTo>[0], label: boolean, expect: boolean, seeOffset = 0): ThreadGenerator {
  const result: {right?: boolean} = {};
  yield* lab.trial([...shape], at(see as never) + seeOffset, at(judge as never), label, result);
  const right = result.right;
  if (right !== expect) useLogger().warn(`trial at ${String(judge)}: judge says ${right ? 'YES' : 'NO'}, the story needs ${expect ? 'YES' : 'NO'}`);
}

function* flinch(s: Stage): ThreadGenerator {
  yield* s.spark.body.pose({torso: -14, head: -24, leftShoulder: -60, leftElbow: -90, rightShoulder: -60, rightElbow: -90}, 0.1, easeOutCubic);
  yield* waitFor(0.15);
  yield* s.spark.body.pose(STAND, 0.4, easeInOutSine);
}

/** Turn a group of dials with the screwdriver, on a cue; `dw` is the weight change. */
function* turnDials(s: Stage, lab: Lab, idx: number[], dw: number, cue: Parameters<typeof syncTo>[0]): ThreadGenerator {
  const spark = s.spark.body;
  const first = worldOf(s, lab.board.dials[idx[0]]);
  yield* syncTo(cue, 0.25);
  yield* spark.pose(reach(s, spark, 'rightArm', first.add([-40, 0]), {...STAND, head: -12}), 0.25, easeInOutCubic);
  for (const [k, i] of idx.entries()) {
    lab.w[i] += dw;
    s.spawn(delayed(k * 0.05, lab.board.dials[i].value(dialOf(lab.w[i]), 0.25, easeInOutCubic)));
  }
  yield* waitFor(0.2);
}

function check(w: number[], idx: number[], want: number): void {
  for (const i of idx) if (Math.abs(w[i] - want) > 1e-6) useLogger().warn(`weights: dial ${i} is ${w[i].toFixed(2)}, expected ${want}`);
}

/** A card from any 3 x 3 pattern. */
export function patternCard(pattern: number[]): Node {
  const n = card('ring');
  n.removeChildren();
  n.add(new Rect({width: 66, height: 80, radius: 6, fill: '#eeeae0', stroke: '#9a9aa6', lineWidth: TIER.detail}));
  pattern.forEach((on, i) => {
    if (!on) return;
    n.add(new Rect({x: ((i % 3) - 1) * 17, y: (Math.floor(i / 3) - 1) * 17 - 4, width: 14, height: 14, radius: 2, fill: '#1b1b22'}));
  });
  return n;
}

function screwdriver(): Node {
  return new Node({
    children: [
      new Rect({x: 12, width: 24, height: 10, radius: 4, fill: '#ffb000', stroke: '#8a5a00', lineWidth: TIER.detail}),
      new Line({points: [[24, 0], [48, 0]], stroke: '#c9c9d3', lineWidth: TIER.structure, lineCap: 'round'}),
    ],
  });
}

export function* delayed(t: number, task: ThreadGenerator): ThreadGenerator {
  yield* waitFor(t);
  yield* task;
}

export {detach, easeInOutCubic};

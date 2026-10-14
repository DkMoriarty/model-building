import {Circle, Line, Node, Rect, Txt} from '@motion-canvas/2d';
import {all, createSignal, easeInCubic, easeInOutCubic, easeInOutSine, easeOutBack, easeOutCubic, SimpleSignal, ThreadGenerator, useTime, Vector2, waitFor} from '@motion-canvas/core';
import {Pose, StickFigure} from '../../components/StickFigure';
import {withAlpha} from '../../figureSpec';
import {STAND} from '../../first_light/acts/dark';
import {standHeight} from '../../first_light/acts/sandbox';
import {shards, sparkBurst} from '../../first_light/components/Fx';
import {Stage, toAbs, worldOf} from '../../first_light/stage';
import {Typography} from '../../styles';
import {CodeView} from '../components/CodeView';
import {Court, playRally, PONG, PONG_COLORS} from '../components/Pong';
import {gameText} from '../components/Room';
import {BitBlock, HomeDoor, rand, Shadow, skyEye, WORLD} from '../components/World';
import {at, code, Cue, dodgePlan, G, rallies, runnerPlan, syncTo} from '../cues';
import {SPEED} from './room';
import {Hub, shake, SPARK_HUB_X} from './world';

const R1 = new Vector2(40000, 0);
const R2 = new Vector2(50000, 0);
const R3 = new Vector2(70000, 0);
const R1_ZOOM = 1.25;
/** Spark rides the left paddle, the Shadow the right one: small, standing on a step at its foot. */
const RIDER_SCALE = 0.32;
const RIDER_X = -PONG.paddleX - 30;
const GRIP: Pose = {...STAND, torso: 6, head: -6, leftShoulder: -70, leftElbow: -40, rightShoulder: -60, rightElbow: -50};
const READY: Pose = {...STAND, torso: 10, head: -6, leftHip: 18, leftKnee: 16, rightHip: -22, rightKnee: 20, leftShoulder: -40, leftElbow: -100, rightShoulder: 30, rightElbow: -90};
const CHEER: Pose = {...STAND, torso: -6, head: -20, leftShoulder: -160, rightShoulder: -160, leftElbow: -20, rightElbow: -20};
const UNIVERSE = {r1: '#118ab2', r2: '#06d6a0', r3: '#ffb703'};

interface RoundHud {
  root: Node;
  label: SimpleSignal<string, void>;
  info: SimpleSignal<string, void>;
  center: (text: string | null, color?: string, size?: number) => void;
  eye: Node;
  eyeLook: SimpleSignal<number, void>;
  eyeOpen: SimpleSignal<number, void>;
  lights: Circle[];
}

/** The game frame around every round: title, goal, the three lock lights, and the Shadow's eye. */
function buildHud(s: Stage, door: HomeDoor): RoundHud {
  const root = new Node({opacity: 0});
  const label = createSignal('');
  const info = createSignal('');
  root.add(new Rect({width: 1920, height: 1080, stroke: '#2a2a33', lineWidth: 56}));
  root.add(new Rect({width: 1920 - 56, height: 1080 - 56, radius: 26, stroke: '#8a8a96', lineWidth: 5}));
  root.add(new Rect({y: -440, width: 1200, height: 74, radius: 12, fill: withAlpha('#05070d', 0.75)}));
  const lbl = gameText('', 38, '#f2f2f2', {y: -440});
  lbl.text(() => label());
  root.add(lbl);
  const inf = new Txt({y: -372, text: () => info(), fontFamily: Typography.mono, fontWeight: 800, fontSize: 34, fill: '#ffd166', shadowColor: '#000', shadowBlur: 8});
  root.add(inf);
  // The lock: a little door and its three lights, top right. Same lights as the door's.
  const lock = new Node({position: [760, -400]});
  lock.add(new Rect({width: 190, height: 110, radius: 12, fill: withAlpha('#05070d', 0.8), stroke: '#ffd166', lineWidth: 3}));
  lock.add(gameText('HOME', 22, '#ffd166', {y: -28}));
  const lights = door.lights.map((lit, i) => {
    const c = new Circle({position: [(i - 1) * 50, 18], size: 30, fill: () => (lit() > 0.5 ? '#57e389' : '#10241a'), stroke: '#57e389', lineWidth: 4, shadowColor: '#57e389', shadowBlur: () => 24 * lit()});
    lock.add(c);
    return c;
  });
  root.add(lock);
  const eyeLook = createSignal(0);
  const eyeOpen = createSignal(1);
  const eye = skyEye(() => eyeLook(), () => eyeOpen());
  eye.position([0, -260]);
  eye.opacity(0);
  root.add(eye);
  const center = new Node({y: -40});
  root.add(center);
  s.view.add(root);
  s.hud.moveToTop();
  return {
    root,
    label,
    info,
    eye,
    eyeLook,
    eyeOpen,
    lights,
    center: (text, color = '#f2f2f2', size = 110) => {
      center.removeChildren();
      if (text) center.add(gameText(text, size, color, {shadowColor: '#000', shadowBlur: 16}));
    },
  };
}

/** A portal: a disc of the next universe's colour opens from Spark and fills the frame. */
function* portal(s: Stage, color: string, open: Cue, round: Cue, setup: () => void): ThreadGenerator {
  yield* syncTo(open, 0);
  const from = toAbs(s, worldOf(s, s.spark.body.bones.chest)).transformAsPoint(s.view.worldToLocal());
  const disc = new Circle({position: from, size: 0, fill: color, stroke: '#ffffff', lineWidth: 10, shadowColor: color, shadowBlur: 40});
  s.view.add(disc);
  s.hud.moveToTop();
  yield* disc.size(80, 0.3, easeOutBack);
  yield* waitFor(0.1);
  yield* disc.size(2600, 0.6, easeInCubic);
  yield* syncTo(round, 0);
  setup();
  yield* disc.opacity(0, 0.4, easeOutCubic);
  disc.remove();
}

function* lightUp(s: Stage, hud: RoundHud, door: HomeDoor, i: number, cue: Cue): ThreadGenerator {
  yield* syncTo(cue, 0);
  door.lights[i](1);
  const abs = hud.lights[i].absolutePosition().transformAsPoint(s.view.worldToLocal());
  s.spawn(sparkBurst(s.view, abs, '#57e389', 1.2, 12));
  yield* hud.lights[i].scale(1.8, 0.15, easeOutCubic).to(1, 0.3, easeInOutSine);
}

/**
 * 92 - 139 s. Three games, three universes; the Shadow is in every one.
 * Round 1, ping pong: the Shadow's paddle is too fast, 0 - 1. Spark
 * remembers the glitch, serves, so the fastest hit is his, and the ball
 * skips through the Shadow's paddle. Round 2, a runner: real jumps over
 * blocks, one clipped, up again, the flag. Round 3, dodge: the Shadow aims
 * every falling block at Spark for ten seconds. One lock light per round.
 */
export function* roundsAct(s: Stage, hub: Hub): ThreadGenerator {
  const spark = s.spark.body;
  const hud = buildHud(s, hub.door);

  // ================= ROUND 1: PING PONG =================
  const court = new Court({position: R1});
  s.props.add(court);
  court.ball.opacity(0);
  const foe = new Shadow({scale: 0.3});
  foe.look(-1);
  foe.armL(40);
  court.add(foe);
  const riderY = () => court.leftY() + PONG.paddleHalfH - 103 * (RIDER_SCALE / 0.8);
  court.add(new Line({points: () => [new Vector2(RIDER_X - 22, court.leftY() + PONG.paddleHalfH), new Vector2(-PONG.paddleX, court.leftY() + PONG.paddleHalfH)], stroke: PONG_COLORS.you, lineWidth: 5}));
  court.add(new Line({points: () => [new Vector2(PONG.paddleX, court.rightY() + PONG.paddleHalfH), new Vector2(PONG.paddleX + 60, court.rightY() + PONG.paddleHalfH)], stroke: PONG_COLORS.cpu, lineWidth: 5}));
  foe.position(() => new Vector2(PONG.paddleX + 46, court.rightY() + PONG.paddleHalfH));
  const names = new Node({y: 330, opacity: 0});
  names.add(gameText('SPARK', 30, PONG_COLORS.you, {x: -760}));
  names.add(gameText('SHADOW', 30, PONG_COLORS.cpu, {x: 760}));
  hud.root.add(names);

  yield* portal(s, UNIVERSE.r1, 'portal1', 'r1', () => {
    hub.say(null);
    hub.shadow.opacity(0);
    spark.remove();
    court.add(spark);
    spark.scale([RIDER_SCALE, RIDER_SCALE]);
    spark.face(1);
    spark.position(() => new Vector2(RIDER_X, riderY()));
    spark.setPose(GRIP);
    s.cam(R1);
    s.zoom(R1_ZOOM);
    s.room(0);
    hud.root.opacity(1);
    names.opacity(1);
    hud.label('ROUND 1/3  -  PING PONG');
    hud.info('SCORE 1 POINT TO WIN');
  });
  // Point 1: the Shadow serves; its paddle is everywhere at once. 0 - 1.
  yield* rally(s, court, 'r1a', at('r1react') - 0.3, GRIP);
  court.scoreR(1);
  yield* syncTo('r1react', 0);
  yield* spark.pose({...GRIP, torso: 24, head: 30}, 0.3, easeOutCubic);
  // The memory: the line of code that made the ball skip a paddle.
  const memory = new Node({y: -230, opacity: 0});
  const mem = new CodeView({width: 500, height: 60, time: () => s.time()});
  mem.newLine(code['c6']);
  mem.reveal();
  mem.scale(1.6);
  memory.add(new Rect({width: 860, height: 120, radius: 14, fill: withAlpha('#0b0f18', 0.9), stroke: '#ffd166', lineWidth: 4}));
  memory.add(mem);
  hud.root.add(memory);
  yield* waitFor(0.5);
  memory.opacity(1);
  memory.scale(0.8);
  s.spawn(memory.scale(1, 0.2, easeOutBack));
  s.spawn(skipDemo(memory));
  yield* spark.pose({...GRIP, head: -24, torso: -6}, 0.3, easeOutCubic);
  // Spark's serve: so the fifth, fastest hit is his.
  yield* syncTo('r1b', 0);
  hud.center('YOUR SERVE', PONG_COLORS.you, 90);
  s.spawn(sparkBurst(s.fx, worldOf(s, spark.bones.head).add([0, -40]), '#ffd166', 0.6, 10));
  yield* all(memory.opacity(0, 0.4), spark.pose({...GRIP, head: -10, torso: -4}, 0.3, easeOutBack));
  hud.center(null);
  const tunnel = rallies['r1b'].events.find(e => e.kind === 'tunnel')!;
  s.spawn(
    (function* () {
      while (useTime() < tunnel.t) yield;
      yield* all(foe.open(1.4, 0.1).to(1, 0.3), foe.look(1, 0.15));
    })(),
  );
  yield* rally(s, court, 'r1b', at('win1') - 1 / 60, GRIP, true);
  yield* syncTo('win1', 0);
  court.scoreL(1);
  hud.center('ROUND CLEAR', '#57e389', 110);
  yield* spark.pose({...GRIP, ...pick(CHEER, ['leftShoulder', 'rightShoulder', 'leftElbow', 'rightElbow']), head: -20}, 0.25, easeOutBack);
  yield* lightUp(s, hud, hub.door, 0, 'light1');

  // ================= ROUND 2: RUN =================
  const run = runnerPlan;
  const track = new Node({position: R2});
  s.back.add(track);
  universe(track, UNIVERSE.r2, -1400, run.events[run.events.length - 1].x + 1800, () => s.time());
  for (const b of run.blocks) track.add(new BitBlock({size: 70, color: UNIVERSE.r2, bit: b.i % 2, x: b.x + 35, y: 300 - 35}));
  const finishX = run.events[run.events.length - 1].x;
  track.add(flag(finishX + 40));
  const speed = createSignal(run.segments[0].v);
  let standY = 0;
  yield* portal(s, UNIVERSE.r2, 'portal2', 'r2', () => {
    court.opacity(0);
    names.opacity(0);
    hud.center(null);
    spark.remove();
    s.cast.add(spark);
    spark.scale([0.8, 0.8]);
    spark.face(1);
    spark.setPose(READY);
    standY = standHeight(s, spark, READY);
    spark.position(new Vector2(R2.x + run.segments[0].x, standY));
    s.cam(new Vector2(R2.x + run.segments[0].x + 300, 60));
    s.zoom(1.0);
    hud.label('ROUND 2/3  -  RUN');
    hud.info('REACH THE FLAG');
    hud.eye.opacity(1);
    hud.eye.position([560, -250]);
    hud.eyeLook(-0.6);
  });
  standY = standHeight(s, spark, STAND);
  hud.info(`REACH THE FLAG      speed = ${speed()}`);
  yield* runner(s, R2, standY, speed, v => hud.info(`REACH THE FLAG      speed = ${v}`));
  yield* syncTo('win2', 0);
  hud.center('ROUND CLEAR', '#57e389', 110);
  s.spawn(spark.pose(CHEER, 0.25, easeOutBack));
  yield* spark.x(spark.x() + 80, 0.5, easeOutCubic);
  yield* lightUp(s, hud, hub.door, 1, 'light2');

  // ================= ROUND 3: DODGE =================
  const arena = new Node({position: R3});
  s.back.add(arena);
  universe(arena, UNIVERSE.r3, -1400, 1400, () => s.time());
  const dropLayer = new Node({position: R3});
  s.fx.add(dropLayer);
  const dg = dodgePlan;
  yield* portal(s, UNIVERSE.r3, 'portal3', 'r3', () => {
    track.opacity(0);
    hud.center(null);
    spark.face(1);
    spark.setPose(READY);
    spark.position(new Vector2(R3.x, standHeight(s, spark, READY)));
    s.cam(new Vector2(R3.x - 200, 20));
    s.zoom(1.0);
    hud.label('ROUND 3/3  -  DODGE');
    hud.info('SURVIVE 10 SECONDS');
    hud.eye.position([0, -250]);
  });
  const timer = new Txt({position: [-720, -372], text: () => `TIME ${Math.max(0, at('win3') - s.time()).toFixed(1)}`, fontFamily: Typography.mono, fontWeight: 800, fontSize: 40, fill: '#ffd166'});
  hud.root.add(timer);
  yield* dodge(s, R3, dropLayer, hud);
  yield* syncTo('win3', 0);
  timer.remove();
  hud.center('ROUND CLEAR', '#57e389', 110);
  s.spawn(all(hud.eyeOpen(0, 0.4)));
  yield* spark.pose(CHEER, 0.25, easeOutBack);
  yield* lightUp(s, hud, hub.door, 2, 'light3');
  // A white flash, and back to the hub: the door has all three lights.
  yield* waitFor(0.05);
  yield* s.whiteout.opacity(1, 0.15, easeInCubic);
  hud.root.remove();
  arena.opacity(0);
  dropLayer.remove();
  spark.setPose(STAND);
  spark.face(1);
  spark.position(new Vector2(SPARK_HUB_X, standHeight(s, spark, STAND)));
  s.cam(new Vector2(SPARK_HUB_X + 380, 40));
  s.zoom(1.1);
  s.room(0.35);
  s.lightColor(WORLD.bit);
  for (const b of hub.ripple) b.color(WORLD.bit);
  yield* s.whiteout.opacity(0, 0.25, easeOutCubic);
}

function pick(p: Pose, keys: (keyof Pose)[]): Pose {
  return Object.fromEntries(keys.map(k => [k, p[k]])) as Pose;
}

/** A rally in round 1: Spark's arms pump on each of his hits; the frame trail shows fast balls. */
function* rally(s: Stage, court: Court, name: string, until: number, grip: Pose, trail = false): ThreadGenerator {
  const spark = s.spark.body;
  const r = rallies[name];
  s.spawn(
    (function* () {
      for (const e of r.events.filter(e => e.side === -1 && (e.kind === 'hit' || e.kind === 'serve'))) {
        while (useTime() < e.t - 0.08) yield;
        yield* spark.pose({...grip, torso: 14, leftShoulder: -90, rightShoulder: -80}, 0.08, easeInCubic);
        yield* spark.pose(grip, 0.15, easeOutCubic);
      }
    })(),
  );
  yield* playRally(court, r, until, {left: SPEED.spark, right: SPEED.cpu99}, name, trail);
  court.ball.opacity(0);
}

/** The memory panel's little demo: frame-dots that jump clean over a thin bar. */
function* skipDemo(memory: Node): ThreadGenerator {
  const bar = new Rect({x: 260, y: 0, width: 8, height: 60, fill: PONG_COLORS.you});
  memory.add(bar);
  for (let i = 0; i < 6; i++) {
    memory.add(new Circle({x: 130 + i * 45, y: 0, size: 14, fill: withAlpha(PONG_COLORS.ball, 0.3 + 0.12 * i)}));
    yield* waitFor(0.08);
  }
}

/** A universe: its own sky colour, a floor of bits, and a row of bit towers. */
function universe(n: Node, color: string, from: number, to: number, time: () => number): void {
  n.add(new Rect({x: (from + to) / 2, width: to - from + 3000, height: 4000, fill: '#04070a'}));
  n.add(new Rect({x: (from + to) / 2, y: -200, width: to - from + 3000, height: 1200, fill: withAlpha(color, 0.07)}));
  for (let x = from; x < to; x += 260 + rand() * 200) {
    const h = 200 + Math.floor(rand() * 6) * 60;
    n.add(new Rect({x, y: 300 - h / 2, width: 120, height: h, fill: withAlpha(color, 0.06), stroke: withAlpha(color, 0.3), lineWidth: 3}));
  }
  for (let x = from; x < to; x += 300 + rand() * 120) {
    const phase = rand() * 900;
    const speed = 140 + rand() * 120;
    let txt = '';
    for (let i = 0; i < 16; i++) txt += (rand() < 0.5 ? '0' : '1') + '\n';
    n.add(new Txt({x, text: txt, fontFamily: Typography.mono, fontSize: 22, lineHeight: 26, fill: withAlpha(color, 0.18), y: () => -900 + ((time() * speed + phase) % 1300)}));
  }
  n.add(new Rect({x: (from + to) / 2, y: 500, width: to - from + 3000, height: 400, fill: '#050b10'}));
  n.add(new Line({points: [[from - 1500, 300], [to + 1500, 300]], stroke: color, lineWidth: 5}));
  let row = '';
  for (let i = 0; i < (to - from + 3000) / 30; i++) row += rand() < 0.5 ? '0' : '1';
  n.add(new Txt({x: (from + to) / 2, y: 330, text: row, fontFamily: Typography.mono, fontSize: 30, fill: withAlpha(color, 0.3)}));
}

function flag(x: number): Node {
  const n = new Node({x, y: 300});
  n.add(new Line({points: [[0, 0], [0, -260]], stroke: '#e8e8e8', lineWidth: 6}));
  for (let r = 0; r < 3; r++) for (let c = 0; c < 4; c++) n.add(new Rect({x: 14 + c * 24, y: -248 + r * 24, width: 24, height: 24, fill: (r + c) % 2 ? '#111' : '#f2f2f2'}));
  return n;
}

/** A running gait derived from distance travelled, like a walk with a flight phase. */
function runGait(fig: StickFigure, dist: number, stride = 130): Pose {
  const phi = (Math.PI * dist) / stride;
  const sn = Math.sin(phi);
  return {
    torso: 14,
    head: -8,
    leftHip: -10 - 38 * sn,
    rightHip: -10 + 38 * sn,
    leftKnee: 20 + 60 * Math.max(0, Math.cos(phi)),
    rightKnee: 20 + 60 * Math.max(0, -Math.cos(phi)),
    leftShoulder: 42 * sn,
    rightShoulder: -42 * sn,
    leftElbow: -90,
    rightElbow: -90,
  };
}

const TUCK: Pose = {torso: 10, head: -10, leftHip: -80, leftKnee: 100, rightHip: -50, rightKnee: 80, leftShoulder: -150, rightShoulder: -120, leftElbow: -30, rightElbow: -40};

/** Round 2: Spark's run, driven frame by frame by the plan. Jumps follow h(s) = 900 s - 900 s^2. */
function* runner(s: Stage, at0: Vector2, standY: number, speed: SimpleSignal<number, void>, onSpeed: (v: number) => void): ThreadGenerator {
  const spark = s.spark.body;
  const plan = runnerPlan;
  const end = plan.segments[plan.segments.length - 1].until;
  const clip = plan.events.find(e => e.kind === 'clip')!;
  let dist = 0;
  let lastX = plan.segments[0].x;
  while (useTime() < end - 1e-6) {
    const t = useTime();
    const seg = plan.segments.find(sg => t >= sg.t - 1e-9 && t < sg.until) ?? null;
    if (!seg) {
      yield;
      continue;
    }
    const x = seg.x + seg.v * (t - seg.t);
    dist += Math.abs(x - lastX);
    lastX = x;
    if (seg.v !== speed() && seg.kind === 'run') {
      speed(seg.v);
      onSpeed(seg.v);
    }
    spark.x(at0.x + x);
    spark.rotation(0);
    if (seg.kind === 'run') {
      spark.setPose(runGait(spark, dist));
      spark.y(standY + 4 - 6 * Math.abs(Math.cos((Math.PI * dist) / 130)));
    } else if (seg.kind === 'jump') {
      const u = t - seg.t;
      const h = 900 * u - (G / 2) * u * u;
      spark.setPose(TUCK);
      spark.y(standY - h);
    } else {
      // Tumble: the feet catch the block's front face; Spark rolls over it and stumbles back up.
      const u = t - seg.t;
      if (t < clip.t) {
        spark.setPose(TUCK);
        spark.y(standY - (900 * u - (G / 2) * u * u));
      } else {
        const v = t - clip.t;
        if (v < 0.35) {
          spark.setPose(TUCK);
          spark.rotation((v / 0.35) * 200);
          // Over the block: the tucked body (radius ~45) rolls across its top at y 230.
          spark.y(standY - 43 + 13 * (v / 0.35));
        } else if (v < 0.6) {
          const w = (v - 0.35) / 0.25;
          spark.setPose(TUCK);
          spark.rotation(200 + 160 * w);
          // Down the far side to a roll on the floor (body centre 45 above it).
          spark.y(standY - 30 + 90 * w * w);
        } else {
          const w = Math.min(1, (v - 0.6) / (seg.until - clip.t - 0.6));
          spark.rotation(0);
          const g = runGait(spark, dist);
          spark.setPose({...g, torso: 50 - 36 * w, head: 10 - 18 * w});
          spark.y(standY + 60 * (1 - w));
        }
      }
    }
    s.cam(new Vector2(spark.x() + 300, 60));
    yield;
  }
  spark.rotation(0);
}

/** Round 3: blocks fall from rest under gravity onto marks; Spark runs or dives clear of each. */
function* dodge(s: Stage, at0: Vector2, layer: Node, hud: RoundHud): ThreadGenerator {
  const spark = s.spark.body;
  const plan = dodgePlan;
  const standY = standHeight(s, spark, READY);
  const blocks = plan.blocks.map((b, i) => {
    const mark = new Rect({x: b.x, y: plan.floor - 3, width: plan.size, height: 6, fill: WORLD.red, opacity: 0});
    const blk = new BitBlock({size: plan.size, color: UNIVERSE.r3, bit: i % 2, x: b.x, y: plan.top, opacity: 0});
    layer.add([mark, blk]);
    return {b, mark, blk, done: false};
  });
  const end = at('win3');
  const pos = (t: number) => {
    let x = 0;
    for (const m of plan.moves) {
      if (t >= m.until) x = m.to;
      else if (t >= m.t) x = m.from + ((m.to - m.from) * (t - m.t)) / (m.until - m.t);
    }
    return x;
  };
  let dist = 0;
  let lastX = 0;
  let recover = -1;
  while (useTime() < end - 1e-6) {
    const t = useTime();
    for (const k of blocks) {
      const {b, mark, blk} = k;
      if (k.done) continue;
      if (t >= b.drop) {
        const u = Math.min(t - b.drop, plan.fall);
        blk.opacity(1);
        blk.y(plan.top + 0.5 * G * u * u);
        mark.opacity(0.3 + 0.6 * (u / plan.fall));
        mark.scale.x(0.4 + 0.6 * (u / plan.fall));
      }
      if (t >= b.land - 1e-6) {
        k.done = true;
        blk.remove();
        mark.remove();
        s.spawn(shards(layer, new Vector2(b.x, plan.floor - 4), plan.floor - 4, UNIVERSE.r3, 9, 0.4));
        s.spawn(shake(s, 5, 5));
      }
    }
    const x = pos(t);
    const move = plan.moves.find(m => t >= m.t && t < m.until);
    dist += Math.abs(x - lastX);
    if (Math.abs(x - lastX) > 0.01) spark.scale.x((x > lastX ? 1 : -1) * 0.8);
    lastX = x;
    spark.x(at0.x + x);
    if (move?.kind === 'dive') {
      const dir = move.to > move.from ? 1 : -1;
      spark.setPose({...TUCK, torso: 0, leftShoulder: -170, rightShoulder: -170, leftElbow: 0, rightElbow: 0, leftHip: 10, rightHip: -10, leftKnee: 10, rightKnee: 10});
      spark.rotation(80 * dir);
      spark.y(plan.floor - 40);
      recover = move.until;
    } else if (recover > 0 && t < recover + 0.3) {
      const w = (t - recover) / 0.3;
      spark.rotation(spark.rotation() * (1 - w));
      spark.setPose({...READY, torso: 40 * (1 - w) + 10 * w});
      spark.y(plan.floor - 40 + (standY - (plan.floor - 40)) * w);
    } else if (move) {
      spark.rotation(0);
      spark.setPose(runGait(spark, dist, 110));
      spark.y(standY);
    } else {
      spark.rotation(0);
      spark.setPose(READY);
      spark.y(standY);
    }
    hud.eyeLook(Math.max(-1, Math.min(1, (x - 200) / 500)));
    yield;
  }
  spark.rotation(0);
}

export {easeInOutCubic};

import {Circle, Line, Node, Rect} from '@motion-canvas/2d';
import {all, createSignal, easeInCubic, easeInOutCubic, easeInOutSine, easeOutBack, easeOutCubic, ThreadGenerator, useTime, Vector2, waitFor} from '@motion-canvas/core';
import {Pose} from '../../components/StickFigure';
import {withAlpha} from '../../figureSpec';
import {STAND} from '../../first_light/acts/dark';
import {sparkBurst} from '../../first_light/components/Fx';
import {Stage, worldOf} from '../../first_light/stage';
import {CodeView} from '../components/CodeView';
import {roomPicture} from '../components/Game';
import {Court, playRally, PONG, PONG_COLORS} from '../components/Pong';
import {gameText} from '../components/Room';
import {at, code, Cue, rallies, syncTo} from '../cues';
import {SPEED} from './room';

/** Where the dream court sits in world space; inside, it spans the frame's width. */
export const GAME_AT = new Vector2(6000, 0);
export const INSIDE_ZOOM = 1.25;
/** Spark rides the left paddle: small, standing on a step at its foot, gripping it. */
const RIDER_SCALE = 0.32;
const RIDER_X = -PONG.paddleX - 30;
const GRIP: Pose = {...STAND, torso: 6, head: -6, leftShoulder: -70, leftElbow: -40, rightShoulder: -60, rightElbow: -50};

function buildHud(s: Stage, label: () => string): {hud: Node; center: Node; wipe: Rect; dim: Rect; memory: Node} {
  const hud = new Node({opacity: 0});
  const dim = new Rect({width: 1920, height: 1080, fill: '#000000', opacity: 0});
  const bezel = new Rect({width: 1920, height: 1080, stroke: '#2a2a33', lineWidth: 56});
  const inner = new Rect({width: 1920 - 56, height: 1080 - 56, radius: 26, stroke: '#8a8a96', lineWidth: 5});
  const lbl = gameText('', 40, '#f2f2f2', {y: -400});
  lbl.text(label);
  const names = new Node({y: 330});
  names.add(gameText('SPARK', 30, PONG_COLORS.you, {x: -780}));
  names.add(gameText('CPU', 30, PONG_COLORS.cpu, {x: 800}));
  const center = new Node({y: -40});
  const wipe = new Rect({width: 1920, height: 1080, fill: '#05070d', x: -1920});
  // The memory: the line of code and the frame-skip it caused, recalled.
  const memory = new Node({y: -300, opacity: 0});
  const mem = new CodeView({width: 620, height: 70, time: () => s.time()});
  mem.newLine(code['c6']);
  mem.reveal();
  mem.scale(1.6);
  memory.add(new Rect({width: 1060, height: 150, radius: 14, fill: withAlpha('#0b0f18', 0.9), stroke: '#ffd166', lineWidth: 4}));
  memory.add(mem);
  hud.add([dim, names, lbl, center, memory, wipe, bezel, inner]);
  s.view.add(hud);
  s.hud.moveToTop();
  return {hud, center, wipe, dim, memory: Object.assign(memory, {code: mem})};
}

/**
 * Inside the game. Spark lands as the left paddle, sees the room left behind
 * the glass and the door home behind the computer's paddle. Levels 1 and 2
 * are won. Level 3 is the unbeatable computer: 0-1, 0-2, and 0-3 when the
 * fastest ball skips straight through Spark's paddle. GAME OVER. CONTINUE:
 * Spark remembers the glitch, serves, so the fifth and fastest hit is Spark's,
 * and that ball skips through the computer's paddle into the door. The dream
 * breaks.
 */
export function* insideAct(s: Stage): ThreadGenerator {
  const spark = s.spark.body;
  const labelS = createSignal('LEVEL 1/3');
  const {hud, center, wipe, dim, memory} = buildHud(s, () => labelS());
  const say = (text: string | null, color = '#f2f2f2', size = 96) => {
    center.removeChildren();
    if (text) center.add(gameText(text, size, color, {shadowColor: '#000', shadowBlur: 16}));
  };
  const court = new Court({position: GAME_AT, door: true});
  s.props.add(court);
  court.ball.opacity(0);
  // Spark rides the paddle.
  spark.remove();
  court.add(spark);
  spark.scale([RIDER_SCALE, RIDER_SCALE]);
  spark.rotation(0);
  spark.opacity(1);
  spark.face(1);
  const riderY = () => court.leftY() + PONG.paddleHalfH - 103 * (RIDER_SCALE / 0.8);
  // The step Spark stands on, fixed to the paddle's foot.
  court.add(new Line({points: () => [new Vector2(RIDER_X - 22, court.leftY() + PONG.paddleHalfH), new Vector2(-PONG.paddleX, court.leftY() + PONG.paddleHalfH)], stroke: PONG_COLORS.you, lineWidth: 5}));
  s.cam(GAME_AT);
  s.zoom(INSIDE_ZOOM);
  s.room(0);
  hud.opacity(1);

  // ---- Arrival: dropped in from above onto the paddle's step.
  spark.setPose({...STAND, leftShoulder: -150, rightShoulder: -150});
  spark.position(new Vector2(RIDER_X, -600));
  s.spawn(s.whiteout.opacity(0, 0.5, easeOutCubic));
  yield* spark.position(new Vector2(RIDER_X, riderY()), at('inside') - useTime(), easeInCubic);
  spark.position(() => new Vector2(RIDER_X, riderY()));
  spark.setPose(GRIP);
  s.spawn(shake(s, 8, 4));
  // Hands: gripping a paddle. Spark *is* the paddle now.
  yield* syncTo('lookHands', 0);
  yield* all(s.cam(GAME_AT.add([-470, 0]), 0.5, easeInOutCubic), s.zoom(3.6, 0.5, easeInOutCubic));
  yield* spark.pose({...GRIP, head: 30, torso: 10}, 0.3, easeOutCubic);
  // Behind: the glass, and the room with the empty chair. No way back.
  yield* syncTo('lookBack', 0);
  const glass = new Node({position: [-620, 0], opacity: 0});
  glass.add(new Rect({width: 34, height: 2 * PONG.wall - 20, radius: 6, fill: withAlpha('#8ecae6', 0.12), stroke: withAlpha('#8ecae6', 0.7), lineWidth: 3}));
  glass.add(roomPicture({scale: 0.08, y: 0}));
  court.add(glass);
  yield* all(spark.face(-1, 0.2), glass.opacity(1, 0.4));
  yield* waitFor(0.6);
  yield* spark.face(1, 0.2);
  // Ahead: the door, with the room in it, behind the computer's paddle.
  yield* syncTo('seeDoor', 0);
  yield* all(s.cam(GAME_AT.add([470, 0]), 0.5, easeInOutCubic), s.zoom(3.0, 0.5, easeInOutCubic), glass.opacity(0, 0.4));
  yield* waitFor(0.3);
  yield* all(s.cam(GAME_AT, 0.45, easeInOutCubic), s.zoom(INSIDE_ZOOM, 0.45, easeInOutCubic));
  yield* spark.pose({...GRIP, rightShoulder: -95, rightElbow: 0}, 0.15, easeOutCubic);

  // ---- Level 1: a slow computer.
  yield* syncTo('l1', 0);
  yield* spark.pose(GRIP, 0.2);
  yield* rally(s, court, 'l1', at('clear1'), 70);
  court.scoreL(1);
  say('LEVEL 1 CLEAR', '#06d6a0', 80);
  yield* wipeTo(s, wipe, 'wipe1', () => {
    say(null);
    labelS('LEVEL 2/3');
    court.scoreL(0);
    court.leftY(0);
    court.rightY(0);
  });
  // ---- Level 2: faster.
  yield* syncTo('l2', 0);
  yield* rally(s, court, 'l2', at('clear2'), 130);
  court.scoreL(1);
  say('LEVEL 2 CLEAR', '#06d6a0', 80);
  yield* wipeTo(s, wipe, 'wipe2', () => {
    say(null);
    labelS('LEVEL 3/3  -  FIRST TO 3');
    court.scoreL(0);
    court.leftY(0);
    court.rightY(0);
  });
  // ---- Level 3: speed 99. Gulp.
  yield* syncTo('gulp', 0);
  yield* all(s.cam(GAME_AT.add([470, 0]), 0.4, easeInOutCubic), s.zoom(2.6, 0.4, easeInOutCubic));
  yield* court.rightY(-60, 0.05).to(60, 0.05).to(0, 0.05);
  yield* all(s.cam(GAME_AT, 0.4, easeInOutCubic), s.zoom(INSIDE_ZOOM, 0.4, easeInOutCubic));
  // Point 1 and point 2: the computer's angled returns are out of reach.
  for (const [k, react] of [
    ['p1', 'react1'],
    ['p2', 'react2'],
  ] as const) {
    yield* syncTo(k, 0);
    yield* rally(s, court, k, at(react) - 0.6, SPEED.cpu99);
    court.scoreR(court.scoreR() + 1);
    yield* syncTo(react, 0);
    yield* spark.pose({...GRIP, torso: 24, head: 30}, 0.3, easeOutCubic);
    yield* waitFor(0.5);
    yield* spark.pose(GRIP, 0.3);
  }
  // Point 3: Spark reaches everything, and the fastest ball goes straight through.
  yield* syncTo('p3', 0);
  yield* rally(s, court, 'p3', at('gameOver') - 0.4, SPEED.cpu99, true);
  court.scoreR(3);
  yield* syncTo('gameOver', 0);
  say('GAME OVER', PONG_COLORS.cpu, 120);
  yield* dim.opacity(0.55, 0.4);
  // It went *through*. Spark stares at the paddle, then sits.
  yield* syncTo('stare', 0);
  yield* all(s.cam(GAME_AT.add([-470, 0]), 0.5, easeInOutCubic), s.zoom(3.6, 0.5, easeInOutCubic));
  yield* spark.pose({...GRIP, head: 36, torso: 12, rightShoulder: -20, rightElbow: -100}, 0.3, easeOutCubic);
  yield* syncTo('slumpGO', 0);
  say(null);
  yield* spark.pose({...GRIP, torso: 30, head: 40, leftShoulder: 0, rightShoulder: 0, leftElbow: -20, rightElbow: -20}, 0.6, easeInOutSine);
  // CONTINUE? 3 - 2 - 1. At 2 Spark remembers the line of code and the skip.
  yield* syncTo('count3', 0);
  yield* all(s.cam(GAME_AT, 0.5, easeInOutCubic), s.zoom(INSIDE_ZOOM, 0.5, easeInOutCubic));
  say('CONTINUE?  3', '#ffd166', 90);
  yield* syncTo('count2', 0);
  say('CONTINUE?  2', '#ffd166', 90);
  yield* syncTo('memory', 0);
  memory.opacity(1);
  memory.scale(0.8);
  s.spawn(memory.scale(1, 0.2, easeOutBack));
  s.spawn(skipDemo(memory));
  yield* spark.pose({...GRIP, head: -24, torso: -6}, 0.3, easeOutCubic);
  yield* syncTo('count1', 0);
  say('CONTINUE?  1', '#ffd166', 90);
  // Press: Spark's turn to serve.
  yield* syncTo('press', 0);
  say('YOUR SERVE', '#2ec4b6', 90);
  s.spawn(sparkBurst(s.fx, worldOf(s, spark.bones.head).add([0, -40]), '#ffd166', 0.6, 10));
  yield* all(memory.opacity(0, 0.4), dim.opacity(0, 0.4), spark.pose({...GRIP, head: -10, torso: -4}, 0.3, easeOutBack));
  court.leftY(0);
  court.rightY(0);
  // Point 4: the plan. Spark serves, so the fifth, fastest hit is Spark's.
  yield* syncTo('p4', 0);
  say(null);
  yield* rally(s, court, 'p4', at('door') - 1 / 60, SPEED.cpu99, true);
  // Through the computer's paddle, into the door. YOU WIN.
  yield* syncTo('door', 0);
  court.scoreL(1);
  say('YOU WIN', '#ffd166', 130);
  s.spawn(sparkBurst(s.fx, GAME_AT.add([640, 0]), '#ffd166', 1.4, 16));
  yield* spark.pose({...GRIP, leftShoulder: -160, rightShoulder: -160, leftElbow: -20, rightElbow: -20, head: -20}, 0.25, easeOutBack);

  // ---- The dream breaks: cracks from the door, then the picture shatters.
  const doorScreen = new Vector2(640 * INSIDE_ZOOM, 0);
  yield* syncTo('crack', 0);
  s.spawn(cracks(hud, doorScreen, 7, 0));
  yield* syncTo('crack2', 0);
  s.spawn(cracks(hud, doorScreen, 9, 1));
  yield* syncTo('shatter', 0);
  s.whiteout.opacity(1);
  s.spawn(shatterShards(hud));
  court.opacity(0);
  hud.children().forEach(c => c.opacity(0));
  yield* waitFor(3 / 60);
}

/** A rally inside: Spark's arms pump on each of his hits; the frame trail shows on fast balls. */
function* rally(s: Stage, court: Court, name: string, until: number, cpu: number, trail = false): ThreadGenerator {
  const spark = s.spark.body;
  const r = rallies[name];
  s.spawn(
    (function* () {
      for (const e of r.events.filter(e => e.side === -1 && (e.kind === 'hit' || e.kind === 'serve'))) {
        while (useTime() < e.t - 0.08) yield;
        yield* spark.pose({...GRIP, torso: 14, leftShoulder: -90, rightShoulder: -80}, 0.08, easeInCubic);
        yield* spark.pose(GRIP, 0.15, easeOutCubic);
      }
    })(),
  );
  yield* playRally(court, r, until, {left: SPEED.spark, right: cpu}, name, trail);
  court.ball.opacity(0);
}

function* wipeTo(s: Stage, w: Rect, cue: Cue, between: () => void): ThreadGenerator {
  yield* syncTo(cue, 0.3);
  yield* w.x(0, 0.3, easeInCubic);
  between();
  yield* w.x(1920, 0.3, easeOutCubic);
  w.x(-1920);
}

/** The memory panel's little demo: frame-dots that jump clean over a thin bar. */
function* skipDemo(memory: Node): ThreadGenerator {
  const bar = new Rect({x: 300, y: 0, width: 8, height: 70, fill: PONG_COLORS.you});
  memory.add(bar);
  for (let i = 0; i < 6; i++) {
    const dot = new Circle({x: 140 + i * 50, y: 0, size: 14, fill: withAlpha(PONG_COLORS.ball, 0.3 + 0.12 * i)});
    memory.add(dot);
    yield* waitFor(0.08);
  }
}

function* shake(s: Stage, px: number, frames: number): ThreadGenerator {
  for (let i = 0; i < frames; i++) {
    const a = i * 2.4;
    s.shake(new Vector2(Math.cos(a), Math.sin(a)).scale(px * (1 - i / frames)));
    yield;
  }
  s.shake(Vector2.zero);
}

/** Cracks radiating from a screen point. */
function* cracks(hud: Node, from: Vector2, n: number, seed: number): ThreadGenerator {
  const tasks: ThreadGenerator[] = [];
  for (let i = 0; i < n; i++) {
    const a = ((i + seed * 0.5) / n) * Math.PI * 2 + seed;
    const pts = [from];
    let p = from;
    for (let k = 0; k < 5; k++) {
      p = p.add(new Vector2(Math.cos(a + (k % 2 ? 0.3 : -0.25)), Math.sin(a + (k % 2 ? 0.3 : -0.25))).scale(90 + k * 40));
      pts.push(p);
    }
    const crack = new Line({points: pts, stroke: '#ffffff', lineWidth: 5, end: 0, shadowColor: '#8ecae6', shadowBlur: 10});
    hud.add(crack);
    tasks.push(crack.end(1, 0.25, easeOutCubic));
  }
  yield* all(...tasks);
}

/** The picture breaks into dark shards that fly off the white. */
function* shatterShards(hud: Node): ThreadGenerator {
  const tasks: ThreadGenerator[] = [];
  const holder = new Node({});
  hud.parent()!.add(holder);
  holder.moveToTop();
  for (let i = 0; i < 40; i++) {
    const c = new Vector2(((i % 8) - 3.5) * 240, (Math.floor(i / 8) - 2) * 216);
    const sh = new Line({position: c, points: [[-130, -110], [120, -120], [10, 120]], closed: true, fill: '#07121f', stroke: '#8ecae6', lineWidth: 3, rotation: (i * 47) % 360});
    holder.add(sh);
    const dir = c.normalized.scale(900 + (i % 5) * 200);
    tasks.push(all(sh.position(c.add(dir), 0.9, easeInCubic), sh.rotation(sh.rotation() + 200, 0.9), sh.opacity(0, 0.9, easeInCubic)));
  }
  yield* all(...tasks);
  holder.remove();
}

export {easeInOutCubic};

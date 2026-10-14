import {Circle, Line, Node, Rect} from '@motion-canvas/2d';
import {all, createSignal, easeInCubic, easeInOutCubic, easeInOutSine, easeInQuad, easeOutBack, easeOutCubic, linear, ThreadGenerator, useTime, Vector2, waitFor} from '@motion-canvas/core';
import {Pose} from '../../components/StickFigure';
import {withAlpha} from '../../figureSpec';
import {STAND} from '../../first_light/acts/dark';
import {sparkBurst} from '../../first_light/components/Fx';
import {Stage, worldOf} from '../../first_light/stage';
import {buildLevel, G, GAME_COLORS, heart, Level, PELVIS, roomPicture} from '../components/Game';
import {gameText} from '../components/Room';
import {at, Cue, syncTo} from '../cues';
import {flight, hurt, jumpTo, LAND, leap, on, respawn, runTo, runUp, SOAR, FLAIL, TUCK} from '../moves';
import {ballistic, landTime} from '../physics';
import {physics} from '../cues';
import {confetti} from './room';

/** The CONTINUE sign: where the fist is at the top of a full jump from the start. */
const SIGN = new Vector2(-480 + 6, G.ground - physics.pelvis - (physics.jump * physics.jump) / (2 * physics.g) - 160);

/** Where the game world sits in world space while Spark is inside it. */
export const GAME_AT = new Vector2(6000, 0);
/** Inside, the 1280 x 720 level fills the 1920 x 1080 frame exactly. */
export const INSIDE_ZOOM = 1.5;
/** Platform fall: 150 px in 1.2 s (the game's gentle gravity). */
const P = physics;
const GROUND = G.ground - P.pelvis;
const ON_PLATFORM = P.platformTop - P.pelvis;

export interface Inside {
  hud: Node;
  hearts: number;
}

/** Screen-space HUD while inside: the monitor's bezel around the frame, hearts, the level counter. */
function buildHud(s: Stage, lives: () => number, label: () => string): {hud: Node; center: Node; wipe: Rect; dim: Rect} {
  const hud = new Node({opacity: 0});
  const dim = new Rect({width: 1920, height: 1080, fill: '#000000', opacity: 0});
  // The bezel: we are inside the monitor.
  const bezel = new Rect({width: 1920, height: 1080, stroke: '#2a2a33', lineWidth: 56, radius: 0});
  const inner = new Rect({width: 1920 - 56, height: 1080 - 56, radius: 26, stroke: '#8a8a96', lineWidth: 5});
  const hearts = new Node({position: [-790, -455]});
  for (let i = 0; i < 3; i++) hearts.add(heart({x: i * 46, scale: 1.3, full: () => (lives() > i ? 1 : 0)}));
  const lbl = gameText('', 34, '#f2f2f2', {y: -455});
  lbl.text(label);
  const center = new Node({});
  const wipe = new Rect({width: 1920, height: 1080, fill: '#05070d', x: -1920});
  hud.add([dim, center, hearts, lbl, wipe, bezel, inner]);
  s.view.add(hud);
  s.hud.moveToTop();
  return {hud, center, wipe, dim};
}

/**
 * 52.8 - 110.4 s. Inside the game. Spark sees the bezel and the room left
 * behind, then the goal: the flag. Levels 1 and 2 are cleared (the spring
 * is learned). Level 3 shows the way home: a door with Spark's room in it,
 * beyond a pit of spikes. Fail, fail, fail: GAME OVER. CONTINUE? Spark
 * remembers the spring seen while falling, wins, and the dream shatters.
 */
export function* insideAct(s: Stage): ThreadGenerator {
  const spark = s.spark.body;
  let lives = 3;
  let levelNo = 1;
  const livesSig = () => lives;
  const livesS = createSignal(3);
  const labelS = createSignal('LEVEL 1/3');
  const {hud, center, wipe, dim} = buildHud(s, () => livesS(), () => labelS());
  const say = (text: string | null, color = '#f2f2f2', size = 96) => {
    center.removeChildren();
    if (text) center.add(gameText(text, size, color, {shadowColor: '#000', shadowBlur: 16}));
  };

  // ---- Arrival.
  let level = enter(s, 1);
  s.cam(GAME_AT);
  s.zoom(INSIDE_ZOOM);
  s.room(0);
  spark.remove();
  level.root.add(spark);
  spark.scale([0.8, 0.8]);
  spark.rotation(0);
  spark.opacity(1);
  spark.face(1);
  spark.setPose(FLAIL);
  spark.position(new Vector2(level.start.x, -500));
  hud.opacity(1);
  s.spawn(s.whiteout.opacity(0, 0.5, easeOutCubic));
  // Dropped in from above the frame: free fall, landing on the cue.
  yield* syncTo(at('inside') - landTime(-500, 0, GROUND), 0);
  yield* ballistic(spark, spark.position(), 0, level.start.x, GROUND, at('inside'));
  spark.setPose(LAND);
  s.spawn(shake(s, 8, 4));
  yield* spark.pose(STAND, 0.25, easeOutCubic);
  // Looks at its hands: something is different.
  yield* syncTo('lookHands', 0.25);
  yield* spark.pose({...STAND, head: 26, torso: 6, leftShoulder: -80, leftElbow: -60, rightShoulder: -70, rightElbow: -70}, 0.25, easeOutCubic);
  // Looks back: the room it came from is behind glass, the chair empty.
  yield* syncTo('lookBack', 0.2);
  const glass = new Node({position: [-560, -60], opacity: 0});
  glass.add(new Rect({width: 260, height: 300, radius: 10, fill: withAlpha('#8ecae6', 0.08), stroke: withAlpha('#8ecae6', 0.6), lineWidth: 4}));
  glass.add(roomPicture({scale: 0.55, y: 20, opacity: 0.8}));
  level.root.add(glass);
  yield* all(spark.face(-1, 0.2), glass.opacity(1, 0.4), spark.pose({...STAND, head: -6}, 0.3));
  yield* spark.pose({...STAND, rightShoulder: -90, rightElbow: -10, head: -4}, 0.4, easeOutCubic);
  // Its hand meets glass: a ripple. No way back this way.
  const ripple = new Circle({position: worldOfLevel(spark.bones.rightFist), size: 0, stroke: '#8ecae6', lineWidth: 4});
  level.root.add(ripple);
  yield* all(ripple.size(120, 0.4, easeOutCubic), ripple.opacity(0, 0.4));
  yield* spark.pose(STAND, 0.3);
  // The goal: Spark turns, sees the flag, points at it. LEVEL 1/3.
  yield* syncTo('point', 0.2);
  yield* all(spark.face(1, 0.2), glass.opacity(0, 0.4));
  yield* spark.pose({...STAND, rightShoulder: -95, rightElbow: 0, head: -4, torso: -4}, 0.25, easeOutCubic);

  // ---- Level 1: run, jump the gap, flag.
  yield* syncTo('go1', 0);
  s.spawn(spark.pose(STAND, 0.2));
  yield* runUp(spark, -150, at('jumpL1'));
  yield* leap(spark, P.jump, 150, GROUND, at('landL1'));
  yield* runTo(spark, 300, at('flagL1'));
  say('LEVEL 1 CLEAR', GAME_COLORS.flag, 72);
  s.spawn(confetti(level.root, new Vector2(330, 60)));
  yield* spark.pose({...STAND, leftShoulder: -160, rightShoulder: -160, leftElbow: -20, rightElbow: -20, head: -16}, 0.2, easeOutBack);
  level = yield* wipeTo(s, wipe, 'wipe1', level, 2, () => {
    say(null);
    labelS('LEVEL 2/3');
  });

  // ---- Level 2: a rolling spike ball, then a spring up to the ledge.
  const ball = level.ball!;
  yield* syncTo('ball', 0);
  // The ball rolls at a steady speed and passes under Spark at the top of the jump.
  const v = (700 - -100) / (at('jumpBall') + 0.5 - at('ball'));
  ball.position(() => new Vector2(700 - v * (s.time() - at('ball')), G.ground - 28));
  ball.rotation(() => (-(700 - v * (s.time() - at('ball'))) / 28) * (180 / Math.PI));
  yield* runUp(spark, -250, at('jumpBall'));
  yield* leap(spark, P.jump, 50, GROUND, at('landBall'));
  yield* runTo(spark, 60, at('spring1'));
  const sp = level.spring!;
  // The spring: it squashes and fires on the same frame Spark lands on it.
  s.spawn(sp.squash(1, 0.04).to(0, 0.12, easeOutBack));
  spark.position(new Vector2(60, P.springTop2 - P.pelvis));
  yield* leap(spark, P.spring2, 320, P.ledge - P.pelvis, at('landLedge'), {...SOAR, leftShoulder: -60, rightShoulder: -40, head: -20}, false);
  spark.setPose(LAND);
  s.spawn(shake(s, 6, 4));
  yield* spark.pose(STAND, 0.2);
  yield* runTo(spark, 425, at('flagL2'));
  say('LEVEL 2 CLEAR', GAME_COLORS.flag, 72);
  s.spawn(confetti(level.root, new Vector2(450, -150)));
  ball.position(ball.position());
  level = yield* wipeTo(s, wipe, 'wipe2', level, 3, () => {
    say(null);
    labelS('LEVEL 3/3');
  });

  // ---- Level 3: the door home, beyond the pit.
  const plat = level.platform!;
  const spring = level.spring!;
  const door = level.door!;
  s.spawn(pulseDoor(door));
  yield* syncTo('seeDoor', 0.2);
  yield* spark.pose({...STAND, head: -8, torso: -4}, 0.2);
  // A slow push in on the door: that is the way home.
  yield* all(s.cam(GAME_AT.add([70, 0]), 0.5, easeInOutCubic), s.zoom(1.7, 0.5, easeInOutCubic));
  s.spawn(all(s.cam(GAME_AT, 0.4, easeInOutCubic), s.zoom(INSIDE_ZOOM, 0.4, easeInOutCubic)));
  // Walk to the edge and look down: spikes. Gulp.
  yield* syncTo('gulp', 0.3);
  yield* runTo(spark, -410, at('gulp'));
  yield* spark.pose({...STAND, head: 40, torso: 18, leftShoulder: -20, rightShoulder: -10}, 0.2, easeOutCubic);
  yield* waitFor(0.4);
  yield* spark.pose({...STAND, head: 10, torso: -10, leftShoulder: -60, leftElbow: -80}, 0.25, easeOutCubic);

  // Try 1: a running jump. Short.
  yield* syncTo('try1', 0);
  s.spawn(spark.pose(STAND, 0.15));
  yield* spark.walkTo(-480, {mode: 'backward', arriveAt: at('try1') + 0.5, steps: 2, settle: false});
  yield* runUp(spark, -392, at('jump1'));
  yield* leap(spark, P.jump, -392 + P.run * (at('hurt1') - at('jump1')), P.spikesTop - P.pelvis, at('hurt1'), FLAIL, false);
  lives = 2;
  livesS(2);
  yield* hurt(spark);
  yield* syncTo('respawn1', 0);
  yield* respawn(spark, on(level.start.x, G.ground));
  yield* syncTo('react1', 0);
  yield* spark.pose({...STAND, head: 10, torso: 6, leftShoulder: -30, leftElbow: -120, rightShoulder: -30, rightElbow: -120}, 0.3, easeOutCubic);
  for (let i = 0; i < 2; i++) yield* spark.joints.head(i % 2 ? 10 : -10, 0.15);

  // Try 2: onto the platform. It shakes, it drops; falling, Spark sees the spring.
  yield* syncTo('try2', 0);
  s.spawn(spark.pose(STAND, 0.15));
  yield* runUp(spark, -392, at('jump2'));
  const platTop = () => plat.y() - 11;
  yield* leap(spark, P.jump, -160, ON_PLATFORM, at('land2'));
  spark.position(() => on(-160, platTop()));
  yield* spark.pose(STAND, 0.2);
  yield* syncTo('shake2', 0);
  yield* shakeNode(plat, 0.6);
  yield* syncTo('drop2', 0);
  // Slow motion while it falls: the same gravity, a quarter of the speed.
  s.spawn(fall(plat, 170, P.g, at('hurt2'), P.slowmo, at('drop2')));
  spark.setPose({...FLAIL, head: 30});
  // While falling: the spring, right there beside the spikes. A glint.
  yield* syncTo('seeSpring', 0);
  s.spawn(glint(level.root, spring.top));
  yield* spark.pose({...FLAIL, head: 46, torso: 20}, 0.2, easeOutCubic);
  yield* syncTo('hurt2', 0);
  lives = 1;
  livesS(1);
  spark.position(spark.position());
  plat.opacity(0);
  yield* hurt(spark);
  yield* syncTo('respawn2', 0);
  plat.position([-160, 170]);
  plat.opacity(1);
  yield* respawn(spark, on(level.start.x, G.ground));
  // Thinking: a hand to the chin, looking into the pit.
  yield* syncTo('think', 0);
  yield* spark.pose({...STAND, head: 24, torso: 10, rightShoulder: -40, rightElbow: -150, leftShoulder: 10, leftElbow: -90}, 0.3, easeOutCubic);

  // Try 3: a longer run-up, a bigger jump. Still short. GAME OVER.
  yield* syncTo('try3', 0);
  s.spawn(spark.pose(STAND, 0.15));
  yield* spark.walkTo(-540, {mode: 'backward', arriveAt: at('try3') + 0.55, steps: 2, settle: false});
  yield* runUp(spark, -392, at('jump3'));
  // A faster run-up (400 units/s): further, but not far enough. Nothing could be.
  yield* leap(spark, P.jump, -392 + 400 * (at('hurt3') - at('jump3')), P.spikesTop - P.pelvis, at('hurt3'), FLAIL, false);
  lives = 0;
  livesS(0);
  s.spawn(hurt(spark));
  yield* syncTo('gameOver', 0);
  say('GAME OVER', GAME_COLORS.spike, 120);
  yield* dim.opacity(0.6, 0.4);
  // Defeat, held: Spark sits at the start, head down. Silence.
  yield* syncTo('slumpGO', 0);
  spark.position(on(level.start.x, G.ground).add([0, 52]));
  spark.setPose({torso: 18, head: 40, leftHip: -84, leftKnee: 8, rightHip: -110, rightKnee: 96, leftShoulder: 10, leftElbow: -20, rightShoulder: 6, rightElbow: -20});
  spark.opacity(1);
  say(null);

  // CONTINUE? 3 - 2 - 1: a sign drops in above Spark.
  const sign = new Node({position: [-420, -500]});
  sign.add(new Rect({width: 300, height: 110, radius: 10, fill: '#1b1b22', stroke: GAME_COLORS.door, lineWidth: 6}));
  sign.add(gameText('CONTINUE?', 34, GAME_COLORS.door, {y: -18}));
  const num = gameText('3', 44, '#ffffff', {y: 26});
  sign.add(num);
  level.root.add(sign);
  // Spark is drawn in front of the sign, so the punch reads.
  spark.moveToTop();
  yield* syncTo('count3', 0);
  yield* sign.position([SIGN.x, SIGN.y], 0.3, easeOutBack);
  yield* syncTo('count2', 0);
  num.text('2');
  // The memory: Spark looks up... at the pit. The spring glints again.
  yield* syncTo('memory', 0);
  s.spawn(glint(level.root, spring.top, 1.6));
  yield* spark.pose({head: 10, torso: 0}, 0.3, easeOutCubic);
  yield* syncTo('count1', 0);
  num.text('1');
  // Up, and punch the sign: a full jump, the fist meets it at the top.
  yield* all(spark.pose(STAND, 0.15), spark.position(new Vector2(level.start.x, GROUND), 0.15));
  yield* syncTo('jumpPunch', 3 / 60);
  yield* spark.pose({torso: 20, leftHip: -40, leftKnee: 60, rightHip: -30, rightKnee: 50}, 3 / 60, easeInCubic);
  s.spawn(leap(spark, P.jump, level.start.x, GROUND, at('jumpPunch') + 2 * -P.jump / P.g, {...STAND, rightShoulder: -178, rightElbow: 0, leftShoulder: 20, torso: -4, head: -20}));
  yield* syncTo('punch', 0);
  s.spawn(sparkBurst(level.root, new Vector2(SIGN.x, SIGN.y), GAME_COLORS.door, 1.2, 12));
  s.spawn(dim.opacity(0, 0.3));
  sign.remove();
  yield* syncTo('heart1', 0);
  lives = 1;
  livesS(1);
  yield* spark.pose({...STAND, head: -8}, 0.2);

  // Try 4: the platform, on purpose; leap off it onto the spring; BOING home.
  yield* syncTo('try4', 0);
  yield* runUp(spark, -392, at('jump4'));
  yield* leap(spark, P.jump, -160, ON_PLATFORM, at('land4'));
  spark.position(() => on(-160, platTop()));
  yield* spark.pose({...STAND, head: 30}, 0.2);
  yield* syncTo('shake4', 0);
  yield* shakeNode(plat, 0.6);
  yield* syncTo('drop4', 0);
  s.spawn(fall(plat, 170, P.g, at('drop4') + 1.2, 1, at('drop4')));
  yield* syncTo('leap4', 0);
  // Leap off the falling platform: its downward speed adds to the jump.
  const fallV = P.g * (at('leap4') - at('drop4'));
  spark.position(spark.position());
  yield* leap(spark, P.jump + fallV, -60, P.springTop3 - P.pelvis, at('boing4'), {...STAND, head: 20, leftHip: -20, rightHip: 10}, false);
  s.spawn(spring.squash(1, 0.04).to(0, 0.14, easeOutBack));
  s.spawn(syncThen('soar', spark.pose(SOAR, 0.3, easeOutCubic)));
  yield* leap(spark, P.spring3, 440, GROUND, at('landExit'), SOAR, false);
  spark.setPose(LAND);
  s.spawn(shake(s, 10, 5));
  yield* spark.pose(STAND, 0.25);
  yield* runTo(spark, 470, at('door') - 0.1);
  yield* syncTo('door', 0);
  say('YOU WIN', GAME_COLORS.door, 130);
  s.spawn(confetti(level.root, new Vector2(480, -40)));
  yield* spark.pose({...STAND, leftShoulder: -160, rightShoulder: -160, leftElbow: -20, rightElbow: -20, head: -20}, 0.25, easeOutBack);

  // ---- The dream breaks: cracks from the door, then the whole picture shatters.
  const doorScreen = worldOf(s, door).sub(s.cam()).scale(s.zoom()).add(new Vector2(0, -160));
  yield* syncTo('crack', 0);
  s.spawn(cracks(hud, doorScreen, 7, 0));
  yield* syncTo('crack2', 0);
  s.spawn(cracks(hud, doorScreen, 9, 1));
  yield* syncTo('shatter', 0);
  s.whiteout.opacity(1);
  s.spawn(shatterShards(hud));
  level.root.opacity(0);
  hud.children().forEach(c => c.opacity(0));
  yield* waitFor(3 / 60);
  void livesSig;
  void levelNo;

  function enter(st: Stage, n: 1 | 2 | 3): Level {
    const l = buildLevel(n, {position: GAME_AT});
    st.props.add(l.root);
    levelNo = n;
    return l;
  }
  function worldOfLevel(node: Node): Vector2 {
    return node.absolutePosition().transformAsPoint(level.root.worldToLocal());
  }
  function* wipeTo(st: Stage, w: Rect, cue: Cue, from: Level, n: 1 | 2 | 3, between: () => void) {
    yield* syncTo(cue, 0.3);
    yield* w.x(0, 0.3, easeInCubic);
    from.root.remove();
    spark.remove();
    const next = enter(st, n);
    next.root.add(spark);
    spark.face(1);
    spark.setPose(STAND);
    spark.position(on(next.start.x, G.ground));
    between();
    yield* w.x(1920, 0.3, easeOutCubic);
    w.x(-1920);
    return next;
  }
}

function* syncThen(cue: Cue, task: ThreadGenerator): ThreadGenerator {
  yield* syncTo(cue, 0);
  yield* task;
}

/** Fall under the game's gravity from y0 until `until`. */
/** A platform falling under gravity (optionally in slow motion) until it hits the spikes. */
function* fall(n: Node, y0: number, g: number, until: number, scale = 1, t0 = useTime()): ThreadGenerator {
  const bottom = physics.spikesTop + 11;
  while (useTime() < until - 1e-6) {
    const t = (useTime() - t0) * scale;
    n.y(Math.min(bottom, y0 + 0.5 * g * t * t));
    yield;
  }
  n.y(bottom);
}

function* shakeNode(n: Node, d: number): ThreadGenerator {
  const x0 = n.x();
  for (let t = 0, i = 0; t < d; t += 1 / 60, i++) {
    n.x(x0 + (i % 4 < 2 ? 3 : -3));
    yield;
  }
  n.x(x0);
}

/** Minor-tier camera shake (screen px). */
function* shake(s: Stage, px: number, frames: number): ThreadGenerator {
  for (let i = 0; i < frames; i++) {
    const a = i * 2.4;
    s.shake(new Vector2(Math.cos(a), Math.sin(a)).scale(px * (1 - i / frames)));
    yield;
  }
  s.shake(Vector2.zero);
}

/** A bright four-point glint, drawing the eye to a thing. */
function* glint(parent: Node, at: Vector2, size = 1.2): ThreadGenerator {
  const g = new Node({position: at.add([0, -6]), scale: 0});
  g.add(new Line({points: [[-40, 0], [40, 0]], stroke: '#ffffff', lineWidth: 4}));
  g.add(new Line({points: [[0, -40], [0, 40]], stroke: '#ffffff', lineWidth: 4}));
  g.add(new Circle({size: 70, stroke: GAME_COLORS.spring, lineWidth: 4}));
  parent.add(g);
  yield* g.scale(size, 0.15, easeOutBack);
  yield* g.rotation(45, 0.4, easeInOutSine);
  yield* g.scale(0, 0.2, easeInCubic);
  g.remove();
}

function* pulseDoor(door: Node): ThreadGenerator {
  for (let i = 0; i < 40; i++) {
    yield* door.scale(1.04, 0.5, easeInOutSine);
    yield* door.scale(1, 0.5, easeInOutSine);
  }
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
    const sh = new Line({position: c, points: [[-130, -110], [120, -120], [10, 120]], closed: true, fill: '#0d1b2a', stroke: '#8ecae6', lineWidth: 3, rotation: (i * 47) % 360});
    holder.add(sh);
    const dir = c.normalized.scale(900 + (i % 5) * 200);
    tasks.push(all(sh.position(c.add(dir), 0.9, easeInCubic), sh.rotation(sh.rotation() + 200, 0.9), sh.opacity(0, 0.9, easeInCubic)));
  }
  yield* all(...tasks);
  holder.remove();
}

export {linear, easeInOutCubic, PELVIS};

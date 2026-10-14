import {Node, Rect, Txt} from '@motion-canvas/2d';
import {all, createSignal, easeInCubic, easeInOutCubic, easeInOutSine, easeOutBack, easeOutCubic, ThreadGenerator, useTime, Vector2, waitFor} from '@motion-canvas/core';
import {Pose} from '../../components/StickFigure';
import {detach, reach, Stage, worldOf} from '../../first_light/stage';
import {CodeView} from '../components/CodeView';
import {Court, playRally, PONG, PONG_COLORS} from '../components/Pong';
import {gameText, KEYS, PAD_AT, Room, SCREEN, SCREEN_GLOW, SEAT} from '../components/Room';
import {at, code, Cue, rallies, syncTo} from '../cues';

/** Sitting on the chair, facing the desk. */
export const SIT_CHAIR: Pose = {torso: 4, head: -4, leftHip: -88, leftKnee: 86, rightHip: -94, rightKnee: 92, leftShoulder: -50, leftElbow: -70, rightShoulder: -54, rightElbow: -66};
/** Leaning in to type. */
export const TYPE: Pose = {...SIT_CHAIR, torso: 22, head: -14};
export const HOLD: Pose = {...SIT_CHAIR, torso: 2, head: -10, leftShoulder: -40, leftElbow: -70, rightShoulder: -46, rightElbow: -64};

/** The screen: code in the top half, output in the bottom half (both 352 x 99). */
const HALF = SCREEN.h / 2;
const OUT_SCALE = SCREEN.w / 1280;
export const CPS = 12;
/** Paddle speeds (units/s): Spark's hands on the keys, the computer by default, and at speed 99. */
export const SPEED = {spark: 180, cpu: 80, cpu99: 99 * 60};

/** Camera framings. CODE keeps Spark's head and hands in the shot with the screen. */
const CODE_SHOT = {cam: new Vector2(205, 82), zoom: 2.8};
const OVER = {cam: new Vector2(225, 70), zoom: 2.1};
const WIDE = {cam: new Vector2(150, 60), zoom: 1.35};
export function* camTo(s: Stage, to: {cam: Vector2; zoom: number}, d = 0.5): ThreadGenerator {
  yield* all(s.cam(to.cam, d, easeInOutCubic), s.zoom(to.zoom, d, easeInOutCubic));
}

export interface Monitor {
  room: Room;
  prompt: Node;
  code: CodeView;
  output: Node;
  court: Court;
  hello: Node;
  label: Txt;
  /** Big text over the output (LEVEL CLEAR, GAME OVER, YOU WIN), or none. */
  say(text: string | null, color?: string): void;
  /** The whole screen becomes the game (no code). */
  fullscreen(on: boolean, d?: number): ThreadGenerator;
  /** The red wash over the screen once the computer is angry. */
  red?: Rect;
}

export function buildMonitor(s: Stage, room: Room): Monitor {
  const screen = room.screen;
  const prompt = new Node({});
  prompt.add(gameText('NO GAME', 30, '#e0e0e0'));
  prompt.add(new Rect({y: 28, width: 18, height: 4, fill: '#e0e0e0', opacity: () => (Math.floor(s.time() * 2) % 2 ? 0 : 1)}));
  const code = new CodeView({y: -HALF / 2, width: SCREEN.w, height: HALF, opacity: 0, time: () => s.time()});
  const output = new Node({y: HALF / 2, opacity: 0});
  output.add(new Rect({width: SCREEN.w, height: HALF, fill: '#05070d'}));
  const court = new Court({scale: OUT_SCALE, walls: 'all'});
  court.showLeft(0);
  court.showRight(0);
  court.showScore(0);
  output.add(court);
  const hello = gameText('hello world', 22, '#e8e8e8', {opacity: 0});
  output.add(hello);
  const label = gameText('', 20, '#ffd166', {opacity: 0, y: -28});
  output.add(label);
  const big = new Node({});
  screen.add([prompt, code, output, big]);
  // A thin rule between code and output.
  screen.add(new Rect({width: SCREEN.w, height: 2, fill: '#2a2f3a', opacity: () => code.opacity()}));
  return {
    room,
    prompt,
    code,
    output,
    court,
    hello,
    label,
    say(text, color = '#f2f2f2') {
      big.removeChildren();
      if (text) big.add(gameText(text, 26, color, {shadowColor: '#000', shadowBlur: 8}));
    },
    *fullscreen(on, d = 0.4) {
      // The court already spans the screen's width; full screen just centres it and hides the code.
      yield* all(code.opacity(on ? 0 : 1, d), output.position([0, on ? 0 : HALF / 2], d, easeInOutCubic));
    },
  };
}

/** Spark's hands over the keys, one hand per character, exactly on each key click. */
function* handsOnKeys(s: Stage, start: number, n: number): ThreadGenerator {
  const spark = s.spark.body;
  for (let i = 0; i < n; i++) {
    while (useTime() < start + i / CPS - 0.04) yield;
    const right = i % 2 === 0;
    const x = KEYS.from + 8 + ((i * 37) % (KEYS.to - KEYS.from - 16));
    s.spawn(spark.pose(reach(s, spark, right ? 'rightArm' : 'leftArm', new Vector2(x, KEYS.y - 2), TYPE), 0.04, easeInCubic));
  }
}

/** Type one line of real code on its cue; glyphs, hands and clicks share the clock (K2). */
function* typeLine(s: Stage, m: Monitor, cue: Cue): ThreadGenerator {
  const text = code[cue];
  yield* syncTo(cue, 0.2);
  yield* s.spark.body.pose(TYPE, 0.2, easeInOutCubic);
  m.code.newLine(text);
  s.spawn(handsOnKeys(s, at(cue), text.length));
  yield* m.code.type(at(cue), CPS);
  yield* syncTo(`${cue}Enter` as Cue, 0);
  m.code.enter();
  yield* syncTo(`${cue}Run` as Cue, 0);
}

/** Arrow keys: the right hand rests on the keys while Spark plays the paddle. */
function* arrowKeys(s: Stage, until: number): ThreadGenerator {
  const spark = s.spark.body;
  const pose = reach(s, spark, 'rightArm', new Vector2(KEYS.to - 4, KEYS.y - 2), {...TYPE, head: -18});
  yield* spark.pose(pose, 0.2);
  let i = 0;
  while (useTime() < until - 0.2) {
    yield* spark.joints.rightElbow((pose.rightElbow ?? -60) + (i++ % 2 ? -6 : 6), 0.18, easeInOutSine);
  }
}

/**
 * 0 - 64 s. No game, so Spark writes one. hello world first; then a ball, a
 * move, walls, a paddle; the speed glitch; an opponent and a rule: ping pong.
 * Spark plays and scores. The computer loses, and wakes up: it types by
 * itself, learns, gets angry, and calls pull(spark).
 */
export function* roomAct(s: Stage, room: Room, m: Monitor): ThreadGenerator {
  const spark = s.spark.body;
  spark.setPose(SIT_CHAIR);
  spark.position(SEAT.add([0, -3]));
  s.cam(WIDE.cam);
  s.zoom(WIDE.zoom);
  s.room(0.6);
  s.lightColor(SCREEN_GLOW);
  s.lightAt(SCREEN.centre);
  const pad = room.pad;
  const padAt = () => worldOf(s, spark.bones.rightFist).add(worldOf(s, spark.bones.leftFist)).scale(0.5).add([6, -4]);
  spark.setPose(HOLD);
  pad.position(() => padAt());
  s.spawn(s.blackout.opacity(0, 1.5, easeInOutSine));
  const court = m.court;

  // ---- The want: press, press, press. NO GAME.
  for (const k of ['press1', 'press2', 'press3'] as const) {
    yield* syncTo(k, 0.12);
    yield* spark.pose({...HOLD, rightElbow: -76, head: -14}, 0.12, easeInCubic);
    m.prompt.scale(1.15);
    s.spawn(m.prompt.scale(1, 0.2, easeOutCubic));
    yield* spark.pose(HOLD, 0.15, easeOutCubic);
  }
  yield* syncTo('slump', 0.2);
  yield* spark.pose({...HOLD, torso: 18, head: 26, leftShoulder: -10, rightShoulder: -14}, 0.6, easeInOutSine);
  // Gaze: the keyboard, held; then the idea.
  yield* syncTo('lookKeys', 0.2);
  yield* spark.pose({head: 30, torso: 10}, 0.25, easeOutCubic);
  yield* syncTo('idea', 0.15);
  detach(pad);
  yield* all(spark.pose({...SIT_CHAIR, torso: -6, head: -16, rightShoulder: -150, rightElbow: -60}, 0.15, easeOutBack), pad.position(PAD_AT, 0.25, easeOutCubic));
  yield* s.spark.goggles(1, 0.12, easeInCubic);
  yield* spark.pose(SIT_CHAIR, 0.3);
  yield* syncTo('title', 0);
  yield* all(s.title.opacity(1, 0.6), s.blackout.opacity(0.65, 0.6));
  yield* syncTo('titleOut', 0);
  yield* all(s.title.opacity(0, 0.35), s.blackout.opacity(0, 0.35));

  // ---- Close on the screen: code above, output below (K1-K4).
  yield* syncTo('zoomCode', 0);
  s.spawn(all(m.prompt.opacity(0, 0.3), m.code.opacity(1, 0.3), m.output.opacity(1, 0.3)));
  yield* camTo(s, CODE_SHOT, 0.4);

  // print("hello world"): the computer answers. A first, small win.
  yield* typeLine(s, m, 'c1');
  m.hello.opacity(1);
  yield* syncTo('smile', 0);
  // A small fist pump, close to the body (the shot is tight).
  yield* spark.pose({...SIT_CHAIR, torso: -8, head: -20, rightShoulder: -100, rightElbow: -120}, 0.3, easeOutBack);
  // ball = circle(0, 0): a ball.
  yield* typeLine(s, m, 'c2');
  m.hello.opacity(0);
  court.ball.position(Vector2.zero);
  court.ball.opacity(1);
  court.ball.scale(0);
  s.spawn(court.ball.scale(1, 0.15, easeOutBack));
  // ball.move(300, 200): it drifts away... and off the screen.
  yield* typeLine(s, m, 'c3');
  s.spawn(follow(court, 'move', at('ballGone') + 0.2));
  yield* syncTo('whereGone', 0);
  yield* spark.pose({...SIT_CHAIR, torso: 30, head: 34}, 0.3, easeOutCubic);
  yield* spark.pose({head: -10, torso: 14}, 0.4, easeInOutSine);
  // bounce(ball, walls): now it stays, bouncing off all four walls.
  yield* typeLine(s, m, 'c4');
  s.spawn(follow(court, 'box', at('c5') - 0.4));
  yield* syncTo('hypno', 0);
  for (let i = 0; i < 4; i++) yield* spark.joints.head(i % 2 ? -22 : -4, 0.35, easeInOutSine);
  // paddle = bar(-560): something to hit it with. The arrow keys move it.
  yield* typeLine(s, m, 'c5');
  court.showLeft(1);
  court.leftY(0);
  const r5 = rallies['paddle'];
  s.spawn(arrowKeys(s, r5.segments[r5.segments.length - 1].until));
  s.spawn(playRally(court, r5, r5.segments[r5.segments.length - 1].until, {left: SPEED.spark, right: 0}, 'paddle'));
  yield* syncTo('nod', 0);
  yield* spark.joints.head(-26, 0.2, easeOutCubic);
  yield* spark.joints.head(-12, 0.2, easeInOutSine);
  // ball.speed = 3000: so fast it moves 50 units a frame and skips the 12-unit paddle.
  yield* typeLine(s, m, 'c6');
  const g = rallies['glitch'];
  court.leftY(g.events.find(e => e.kind === 'tunnel')!.y!);
  yield* playRally(court, g, at('doubleTake'), {left: 0, right: 0}, 'glitch', true);
  // A double take: screen, hands, screen. Then a laugh.
  yield* spark.pose({head: 30, torso: 16}, 0.15, easeOutCubic);
  yield* spark.pose({head: -16, torso: 2}, 0.15, easeOutCubic);
  yield* syncTo('laughG', 0);
  for (let i = 0; i < 4; i++) yield* spark.pose({torso: i % 2 ? 0 : -10, head: i % 2 ? -10 : -26}, 0.15, easeInOutSine);
  // ball.speed = 600: back to playable.
  yield* typeLine(s, m, 'c7');
  // cpu = bar(560): an opponent that chases the ball. A score.
  yield* typeLine(s, m, 'c8');
  court.showRight(1);
  court.rightY(0);
  court.showScore(1);
  court.right.scale([1, 0]);
  s.spawn(court.right.scale(1, 0.2, easeOutBack));
  // ball.onHit = v => v*1.5: every hit speeds the ball up.
  yield* typeLine(s, m, 'c9');
  yield* syncTo('ahHa', 0);
  m.label.text('PING PONG');
  m.label.opacity(1);
  yield* spark.pose({...SIT_CHAIR, torso: -12, head: -24, leftShoulder: -160, rightShoulder: -160, leftElbow: -20, rightElbow: -20}, 0.3, easeOutBack);

  // ---- Pull back: Spark plays a first game with the pad. And scores.
  yield* syncTo('zoomOut', 0);
  yield* all(camTo(s, OVER, 0.5), spark.pose(HOLD, 0.5, easeInOutCubic), m.fullscreen(true, 0.5), m.label.opacity(0, 0.3));
  pad.position(() => padAt());
  const first = rallies['first'];
  yield* syncTo('play', 0);
  s.spawn(thumbs(s, first));
  yield* playRally(court, first, at('point1'), {left: SPEED.spark, right: SPEED.cpu}, 'first');
  court.scoreL(1);
  court.ball.opacity(0);
  yield* syncTo('cheer', 0);
  yield* spark.pose({...HOLD, torso: -12, head: -20, leftShoulder: -160, rightShoulder: -160, leftElbow: -20, rightElbow: -20}, 0.25, easeOutBack);
  detach(pad);
  pad.position(PAD_AT);

  // ---- The computer loses, and wakes up. Its paddle trembles.
  yield* syncTo('tremble', 0);
  const red = new Rect({width: SCREEN.w, height: SCREEN.h, fill: PONG_COLORS.cpu, opacity: 0});
  room.screen.add(red);
  m.red = red;
  s.spawn(spark.pose({...HOLD, torso: 14, head: -6}, 0.3, easeOutCubic));
  s.spawn(red.opacity(0.12, 0.3).to(0.04, 0.3));
  for (let i = 0; i < 12; i++) {
    court.rightY(i % 2 ? -10 : 10);
    yield* waitFor(1 / 30);
  }
  court.rightY(0);
  // It types by itself: cpu.learn(). Spark lifts his hands off the keys.
  yield* syncTo('zoomCode2', 0);
  yield* all(camTo(s, CODE_SHOT, 0.35), m.fullscreen(false, 0.35));
  s.spawn(selfType(s, m, 's1'));
  yield* syncTo('handsOff', 0.2);
  yield* spark.pose({...SIT_CHAIR, torso: -8, head: -16, leftShoulder: -100, leftElbow: -120, rightShoulder: -96, rightElbow: -126}, 0.2, easeOutCubic);
  yield* syncTo('s1Run', 0);
  court.showScore(0);
  m.label.text('LEARNING...');
  m.label.fill(PONG_COLORS.cpu);
  m.label.opacity(1);
  // cpu.angry = true: the screen goes red. Spark recoils.
  yield* selfType(s, m, 's2');
  m.label.text('ANGRY');
  s.spawn(red.opacity(0.45, 0.15, easeOutCubic));
  s.spawn(shakeView(s, 6, 8));
  yield* spark.pose({...SIT_CHAIR, torso: -12, head: -10, leftShoulder: -96, leftElbow: -120, rightShoulder: -92, rightElbow: -126}, 0.2, easeOutBack);
  // pull(spark): Spark shakes his head, no, no.
  s.spawn(selfType(s, m, 's3'));
  yield* syncTo('s3', 0);
  for (let i = 0; i < 4; i++) yield* spark.joints.head(i % 2 ? -22 : 2, 0.2, easeInOutSine);
}

/** The computer types a line by itself: no hands, the same 12 characters a second. */
function* selfType(s: Stage, m: Monitor, cue: Cue): ThreadGenerator {
  const text = code[cue];
  yield* syncTo(cue, 0);
  m.code.newLine(text);
  yield* m.code.type(at(cue), CPS);
  yield* syncTo(`${cue}Enter` as Cue, 0);
  m.code.enter();
  yield* syncTo(`${cue}Run` as Cue, 0);
}

function* shakeView(s: Stage, px: number, frames: number): ThreadGenerator {
  for (let i = 0; i < frames; i++) {
    const a = i * 2.4;
    s.shake(new Vector2(Math.cos(a), Math.sin(a)).scale(px * (1 - i / frames)));
    yield;
  }
  s.shake(Vector2.zero);
}

/** Draw a rally's ball until `until` (no paddles involved). */
function* follow(court: Court, name: string, until: number): ThreadGenerator {
  yield* playRally(court, rallies[name], until, {left: 0, right: 0}, name);
}

/** Thumb presses on the pad, on each of Spark's own hits. */
function* thumbs(s: Stage, r: (typeof rallies)[string]): ThreadGenerator {
  const spark = s.spark.body;
  for (const e of r.events.filter(e => e.side === -1 && (e.kind === 'hit' || e.kind === 'serve'))) {
    while (useTime() < e.t - 0.06) yield;
    yield* spark.joints.rightElbow(-80, 0.06).to(HOLD.rightElbow!, 0.1);
  }
}

/**
 * Pull-in: two red pixel hands reach out of the screen, take Spark by the
 * wrists and drag him in. He shrinks into the glass and the screen floods white.
 */
export function* pullIn(s: Stage, m: Monitor): ThreadGenerator {
  const spark = s.spark.body;
  yield* syncTo('pull', 0);
  s.spawn(all(s.cam(SCREEN.centre.add([-150, 40]), 1.2, easeInOutCubic), s.zoom(2.2, 1.2, easeInOutCubic)));
  const hands: Node[] = [];
  const wrists = [spark.bones.leftFist, spark.bones.rightFist];
  for (const [i, fist] of wrists.entries()) {
    const from = SCREEN.centre.add([-SCREEN.w / 2 + 20, -30 + i * 50]);
    const reachT = createSignal(0);
    const hand = new Node({});
    // A chain of pixels from the screen edge to the wrist: an arm made of squares.
    for (let k = 0; k < 9; k++) {
      const u = (k + 1) / 9;
      hand.add(
        new Rect({
          width: 12,
          height: 12,
          fill: k % 2 ? PONG_COLORS.cpu : '#ff8fa3',
          opacity: () => (u <= reachT() ? 1 : 0),
          position: () => {
            const to = worldOf(s, fist);
            return from.add(to.sub(from).scale(u * Math.min(1, reachT() / u)));
          },
        }),
      );
    }
    s.fx.add(hand);
    hands.push(hand);
    s.spawn(reachT(1, 0.5, easeOutCubic));
  }
  m.red?.opacity(0.7);
  yield* waitFor(0.5);
  // Grabbed: arms straight out towards the screen, leaning in against his will.
  yield* spark.pose({torso: 34, head: 10, leftShoulder: -88, rightShoulder: -96, leftElbow: -4, rightElbow: -4, leftHip: -60, rightHip: -40, leftKnee: 40, rightKnee: 30}, 0.6, easeInCubic);
  yield* syncTo('suck', 0);
  const glow = new Rect({position: SCREEN.centre, width: SCREEN.w, height: SCREEN.h, fill: '#ffffff', opacity: 0});
  s.props.add(glow);
  hands.forEach(h => h.remove());
  yield* all(
    spark.position(SCREEN.centre, 0.9, easeInCubic),
    spark.scale([0.05, 0.05], 0.6, easeInCubic),
    spark.rotation(540, 0.9, easeInCubic),
    s.zoom(4.6, 0.9, easeInCubic),
    s.cam(SCREEN.centre, 0.9, easeInCubic),
    glow.opacity(1, 0.9),
  );
  s.whiteout.opacity(1);
  glow.remove();
}

export {PONG};

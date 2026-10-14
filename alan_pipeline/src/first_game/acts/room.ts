import {Circle, Line, Node, Rect} from '@motion-canvas/2d';
import {all, easeInCubic, easeInOutCubic, easeInOutSine, easeOutBack, easeOutCubic, linear, ThreadGenerator, useTime, Vector2, waitFor} from '@motion-canvas/core';
import {Pose, StickFigure} from '../../components/StickFigure';
import {createSpark} from '../../first_light/components/Spark';
import {STAND} from '../../first_light/acts/dark';
import {attach, detach, reach, Stage, worldOf} from '../../first_light/stage';
import {buildLevel, G, GAME_COLORS, Level} from '../components/Game';
import {gameText, KEYS, Room, SCREEN, SCREEN_GLOW, SCREEN_SCALE, SEAT} from '../components/Room';
import {CodeView} from '../components/CodeView';
import {at, code, Cue, physics, syncTo} from '../cues';
import {ballistic, freeFall} from '../physics';
import {hurt, jumpTo, on, runTo} from '../moves';

/** Sitting on the chair, facing the desk. */
export const SIT_CHAIR: Pose = {torso: 4, head: -4, leftHip: -88, leftKnee: 86, rightHip: -94, rightKnee: 92, leftShoulder: -50, leftElbow: -70, rightShoulder: -54, rightElbow: -66};
/** Leaning in to type. */
export const TYPE: Pose = {...SIT_CHAIR, torso: 22, head: -14};
const PREVIEW = {at: new Vector2(0, 41), scale: 0.16};
const CODE_BAND = {y: -60, h: 78};

/** What the monitor is showing. */
export interface Monitor {
  room: Room;
  noGame: Node;
  code: CodeView;
  preview: Node;
  hudText: Node;
  levels: Level[];
  mini: StickFigure;
  hearts: Node;
  /** Put level n on the screen (with the mini hero at its start). */
  show(n: 1 | 2 | 3): Level;
  current(): Level;
  /** Big centred text on the screen, or none. */
  say(text: string | null, color?: string): void;
}

export function buildMonitor(s: Stage, room: Room): Monitor {
  const screen = room.screen;
  const noGame = new Node({});
  noGame.add(gameText('NO GAME', 30, '#e0e0e0'));
  noGame.add(new Rect({y: 28, width: 18, height: 4, fill: '#e0e0e0', opacity: () => (Math.floor(s.time() * 2) % 2 ? 0 : 1)}));
  const code = new CodeView({y: CODE_BAND.y, width: SCREEN.w, height: CODE_BAND.h, opacity: 0, time: () => s.time()});
  const preview = new Node({position: PREVIEW.at, scale: PREVIEW.scale, opacity: 0});
  const hudText = new Node({});
  const hearts = new Node({position: [-150, -82], opacity: 0});
  screen.add([preview, code, noGame, hudText, hearts]);
  for (let i = 0; i < 3; i++) hearts.add(new Circle({x: i * 14, size: 9, fill: GAME_COLORS.spike}));
  const levels = ([1, 2, 3] as const).map(n => {
    const l = buildLevel(n);
    l.root.opacity(0);
    preview.add(l.root);
    return l;
  });
  const mini = createSpark({scale: 0.8}).body;
  let shown = levels[0];
  const m: Monitor = {
    room,
    noGame,
    code,
    preview,
    hudText,
    levels,
    mini,
    hearts,
    show(n) {
      levels.forEach(l => l.root.opacity(l.n === n ? 1 : 0));
      shown = levels[n - 1];
      mini.remove();
      shown.root.add(mini);
      mini.opacity(1);
      mini.setPose(STAND);
      mini.rotation(0);
      mini.position(on(shown.start.x, shown.start.y));
      mini.scale([0.8, 0.8]);
      return shown;
    },
    current: () => shown,
    say(text, color = '#f2f2f2') {
      hudText.removeChildren();
      if (text) hudText.add(gameText(text, 26, color, {shadowColor: '#000', shadowBlur: 8}));
    },
  };
  return m;
}

/** Spark's hands over the keys, one hand per character, exactly on each key click. */
function* handsOnKeys(s: Stage, start: number, n: number, cps: number): ThreadGenerator {
  const spark = s.spark.body;
  for (let i = 0; i < n; i++) {
    while (useTime() < start + i / cps - 0.04) yield;
    const right = i % 2 === 0;
    const x = KEYS.from + 8 + ((i * 37) % (KEYS.to - KEYS.from - 16));
    s.spawn(spark.pose(reach(s, spark, right ? 'rightArm' : 'leftArm', new Vector2(x, KEYS.y - 2), TYPE), 0.04, easeInCubic));
  }
}

/** Type one line of real code on a cue: glyphs, hands and key clicks share the clock. */
function* typeLine(s: Stage, m: Monitor, cue: Cue): ThreadGenerator {
  const text = code[cue];
  m.code.newLine(text);
  const start = at(cue);
  s.spawn(handsOnKeys(s, start, text.length, CPS));
  yield* m.code.type(start, CPS);
  yield* syncTo(`${cue}Enter` as Cue, 0);
  m.code.enter();
}

const CPS = 12;
const OVER = {cam: new Vector2(225, 70), zoom: 2.1};
const WIDE = {cam: new Vector2(150, 60), zoom: 1.35};
const CLOSE = {cam: SCREEN.centre, zoom: 5.0};
function* camTo(s: Stage, to: {cam: Vector2; zoom: number}, d = 0.5): ThreadGenerator {
  yield* all(s.cam(to.cam, d, easeInOutCubic), s.zoom(to.zoom, d, easeInOutCubic));
}

/**
 * 0 - 52.8 s. Spark wants to play; there is no game. So Spark writes one:
 * a floor, a hero (a tiny Spark), two bugs and their fixes, a flag. Level 1
 * is cleared on screen. More levels late into the night; level 3 is made
 * impossible on purpose. Sleepy, Spark leans in... and is pulled inside.
 */
export function* roomAct(s: Stage, room: Room, m: Monitor): ThreadGenerator {
  const spark = s.spark.body;
  spark.setPose(SIT_CHAIR);
  spark.position(SEAT.add([0, -3]));
  s.cam(new Vector2(150, 60));
  s.zoom(1.35);
  s.room(0.6);
  s.lightColor(SCREEN_GLOW);
  s.lightAt(SCREEN.centre);
  // The pad is in Spark's hands at the start: the want is in frame.
  const pad = room.pad;
  const padAt = () => worldOf(s, spark.bones.rightFist).add(worldOf(s, spark.bones.leftFist)).scale(0.5).add([6, -4]);
  const HOLD: Pose = {...SIT_CHAIR, torso: 2, head: -10, leftShoulder: -40, leftElbow: -70, rightShoulder: -46, rightElbow: -64};
  spark.setPose(HOLD);
  pad.position(() => padAt());
  s.spawn(s.blackout.opacity(0, 1.5, easeInOutSine));

  // ---- The want: press, press, press. NO GAME.
  for (const k of ['press1', 'press2', 'press3'] as const) {
    yield* syncTo(k, 0.12);
    yield* spark.pose({...HOLD, rightElbow: -76, head: -14}, 0.12, easeInCubic);
    m.noGame.scale(1.15);
    s.spawn(m.noGame.scale(1, 0.2, easeOutCubic));
    if (k === 'press2') s.spawn(all(spark.joints.leftElbow(-50, 0.08).to(-80, 0.08).to(-70, 0.08), spark.joints.rightElbow(-50, 0.08).to(-80, 0.08).to(-64, 0.08)));
    else yield* spark.pose(HOLD, 0.15, easeOutCubic);
  }
  yield* syncTo('slump', 0.2);
  yield* spark.pose({...HOLD, torso: 18, head: 26, leftShoulder: -10, rightShoulder: -14}, 0.6, easeInOutSine);
  // Gaze: the keyboard (at least 12 frames), then the idea.
  yield* syncTo('lookKeys', 0.2);
  yield* spark.pose({head: 30, torso: 10}, 0.25, easeOutCubic);
  yield* syncTo('idea', 0.15);
  detach(pad);
  yield* all(spark.pose({...SIT_CHAIR, torso: -6, head: -16, rightShoulder: -150, rightElbow: -60}, 0.15, easeOutBack), pad.position(new Vector2(150, 187), 0.25, easeOutCubic));
  yield* s.spark.goggles(1, 0.12, easeInCubic);
  yield* spark.pose(SIT_CHAIR, 0.3);

  // Title over the room, dimmed.
  yield* syncTo('title', 0);
  yield* all(s.title.opacity(1, 0.6), s.blackout.opacity(0.65, 0.6));
  yield* syncTo('titleOut', 0);
  yield* all(s.title.opacity(0, 0.35), s.blackout.opacity(0, 0.35), m.noGame.opacity(0, 0.3));
  const l1 = m.levels[0];
  l1.root.opacity(1);
  l1.grounds.forEach(g => g.opacity(0));
  l1.flag!.opacity(0);
  const mini = m.mini;
  const G0 = on(-480, G.ground);

  // ---- Close on the screen: real code, typed (K1-K4).
  yield* syncTo('zoomCode1', 0);
  s.spawn(all(m.code.opacity(1, 0.3), m.preview.opacity(1, 0.3)));
  yield* all(camTo(s, CLOSE, 0.5), spark.pose(TYPE, 0.4, easeInOutCubic));
  // floor = box(0, 250): the floor appears.
  yield* typeLine(s, m, 'typeFloor');
  yield* syncTo('floor', 0);
  l1.grounds.forEach(g => {
    g.opacity(1);
    g.scale([1, 0]);
    s.spawn(g.scale(1, 0.15, easeOutCubic));
  });
  // hero = player(-480, 250): a tiny Spark.
  yield* typeLine(s, m, 'typeHero');
  yield* syncTo('hero', 0);
  m.show(1);
  l1.flag!.opacity(0);
  mini.scale(0);
  s.spawn(mini.scale(0.8, 0.15, easeOutCubic));
  // hero.vy += 30: gravity, but nothing stops it at the floor. Bug 1, a real one.
  yield* typeLine(s, m, 'typeGravity');
  yield* syncTo('fallBug', 0);
  s.spawn(freeFall(mini, 0, 0.8));
  // Pull back: Spark's reaction.
  yield* syncTo('zoomOut1', 0);
  yield* camTo(s, OVER, 0.4);
  yield* syncTo('facepalm', 0.15);
  yield* spark.pose({...SIT_CHAIR, leftShoulder: -150, leftElbow: -130, head: 20}, 0.15, easeOutCubic);
  // hero.y = min(hero.y, 250): the floor holds. Re-run: the hero stands.
  yield* syncTo('zoomCode2', 0);
  yield* all(camTo(s, CLOSE, 0.5), spark.pose(TYPE, 0.4, easeInOutCubic));
  yield* typeLine(s, m, 'typeFix1');
  yield* syncTo('fix1', 0);
  m.show(1);
  l1.flag!.opacity(0);
  l1.grounds.forEach(g => s.spawn(g.opacity(0.4, 0.06).to(1, 0.06).to(0.4, 0.06).to(1, 0.06)));
  // hero.jump = -9000 (one zero too many).
  yield* typeLine(s, m, 'typeJump');
  // Pull back; pick up the pad; press jump. At -9000 the hero leaves the
  // top of the screen in two frames, exactly as the number says.
  yield* syncTo('zoomOut2', 0);
  yield* all(camTo(s, OVER, 0.5), spark.pose(HOLD, 0.5, easeInOutCubic));
  pad.position(() => padAt());
  yield* syncTo('jumpBug', 0);
  s.spawn(spark.joints.rightElbow(-78, 0.06).to(HOLD.rightElbow!, 0.1));
  s.spawn(freeFall(mini, physics.typo, 0.3));
  yield* syncTo('lookUp', 0.25);
  yield* spark.pose({...HOLD, head: -40, torso: -8}, 0.25, easeOutCubic);
  // The fix: back to the number, delete one zero (K6). Re-run, jump: up
  // 225 and down in exactly one second.
  yield* syncTo('zoomCode3', 0);
  detach(pad);
  pad.position(new Vector2(150, 187));
  yield* all(camTo(s, CLOSE, 0.5), spark.pose(TYPE, 0.4, easeInOutCubic));
  yield* syncTo('editTypo', 0.05);
  const jumpLine = m.code.lineCount() - 1;
  const typoText = code['typeJump'];
  s.spawn(spark.pose(reach(s, spark, 'rightArm', new Vector2(KEYS.to - 6, KEYS.y - 2), TYPE), 0.1));
  yield* m.code.deleteAt(jumpLine, typoText.length - 1, 0.4);
  yield* syncTo('fix2', 0);
  m.code.enter();
  m.show(1);
  l1.flag!.opacity(0);
  yield* syncTo('jumpOk', 0);
  yield* ballistic(mini, G0, physics.jump, -480, G0.y, at('landOk'));
  // flag = goal(330): a goal.
  yield* typeLine(s, m, 'typeFlag');
  yield* syncTo('flag', 0);
  l1.flag!.opacity(1);
  l1.flag!.scale(0);
  s.spawn(l1.flag!.scale(1, 0.2, easeOutBack));
  // Pull back and play level 1 for real.
  yield* syncTo('zoomOut3', 0);
  s.spawn(all(m.preview.position(Vector2.zero, 0.5), m.preview.scale(SCREEN_SCALE, 0.5), m.code.opacity(0, 0.4)));
  yield* all(camTo(s, OVER, 0.5), spark.pose(HOLD, 0.5, easeInOutCubic));
  pad.position(() => padAt());
  yield* syncTo('play2', 0);
  yield* runTo(mini, -150, at('hop1'));
  yield* ballistic(mini, mini.position(), physics.jump, 150, G0.y, at('hopLand1'));
  yield* runTo(mini, 300, at('clear1'));
  m.say('LEVEL CLEAR', GAME_COLORS.flag);
  s.spawn(confetti(l1.root, new Vector2(330, 100)));
  yield* syncTo('cheer', 0);
  yield* spark.pose({...HOLD, torso: -12, head: -20, leftShoulder: -160, rightShoulder: -160, leftElbow: -20, rightElbow: -20}, 0.25, easeOutBack);
  detach(pad);
  pad.position(new Vector2(150, 187));

  // ---- More levels, into the night.
  yield* syncTo('zoomCode4', 0);
  m.say(null);
  s.spawn(all(m.preview.position(PREVIEW.at, 0.4), m.preview.scale(PREVIEW.scale, 0.4), m.code.opacity(1, 0.4)));
  yield* all(camTo(s, CLOSE, 0.5), spark.pose(TYPE, 0.4, easeInOutCubic));
  yield* typeLine(s, m, 'typeLvl2');
  yield* syncTo('lvl2', 0);
  m.show(2);
  // Wide: the clock turns to 11.
  yield* syncTo('clock1', 0.5);
  yield* camTo(s, WIDE, 0.5);
  yield* room.hours(23, 0.8, easeInOutCubic);
  yield* syncTo('typeLvl3', 0.5);
  yield* camTo(s, CLOSE, 0.5);
  yield* typeLine(s, m, 'typeLvl3');
  yield* syncTo('lvl3', 0);
  m.show(3);
  // A sly grin: level 3 is impossible on purpose.
  yield* syncTo('grin', 0.5);
  yield* camTo(s, OVER, 0.5);
  for (let i = 0; i < 3; i++) {
    yield* spark.pose({...TYPE, torso: 4, head: -20, leftShoulder: -70, leftElbow: -90, rightShoulder: -64, rightElbow: -100}, 0.1);
    yield* spark.pose({leftShoulder: -60, rightShoulder: -74}, 0.1);
  }
  yield* syncTo('clock2', 0.5);
  yield* camTo(s, WIDE, 0.5);
  yield* room.hours(26, 0.6, easeInOutCubic);
  // Try it, full screen: the hero jumps into the pit. GAME OVER. Spark laughs.
  yield* syncTo('play3', 0.5);
  s.spawn(all(m.preview.position(Vector2.zero, 0.5), m.preview.scale(SCREEN_SCALE, 0.5), m.code.opacity(0, 0.4)));
  yield* all(camTo(s, OVER, 0.5), spark.pose(HOLD, 0.5, easeInOutCubic));
  pad.position(() => padAt());
  yield* runTo(mini, -392, at('jump3m'));
  yield* ballistic(mini, mini.position(), physics.jump, -392 + physics.run * (at('die1') - at('jump3m')), physics.spikesTop - physics.pelvis, at('die1'));
  s.spawn(hurt(mini));
  yield* syncTo('gameOverMini', 0);
  m.say('GAME OVER', GAME_COLORS.spike);
  yield* syncTo('laugh', 0);
  for (let i = 0; i < 4; i++) {
    yield* spark.pose({torso: i % 2 ? 0 : -10, head: i % 2 ? -10 : -26}, 0.15, easeInOutSine);
  }
  // Sleepy: a yawn, then the head drops towards the screen.
  yield* syncTo('yawn', 0);
  detach(pad);
  pad.position(new Vector2(150, 187));
  yield* spark.pose({...SIT_CHAIR, torso: -14, head: -34, leftShoulder: -170, rightShoulder: -170, leftElbow: -30, rightElbow: -30}, 0.6, easeInOutSine);
  yield* spark.pose(SIT_CHAIR, 0.8, easeInOutSine);
  yield* syncTo('droop', 0);
  yield* spark.pose({...SIT_CHAIR, torso: 30, head: 20, leftShoulder: -10, rightShoulder: -20}, 1.0, easeInOutSine);
}

/** Pixel confetti from a point, inside a level (game units). */
export function* confetti(parent: Node, at: Vector2): ThreadGenerator {
  const colors = ['#06d6a0', '#ffd166', '#ef476f', '#8ecae6', '#ffffff'];
  const tasks: ThreadGenerator[] = [];
  for (let i = 0; i < 24; i++) {
    const a = -Math.PI / 2 + ((i / 23) - 0.5) * 2.4;
    const v = new Vector2(Math.cos(a), Math.sin(a)).scale(260 + (i % 5) * 60);
    const c = new Rect({position: at, width: 14, height: 14, fill: colors[i % colors.length]});
    parent.add(c);
    tasks.push(
      (function* () {
        for (let t = 0; t < 1.4; t += 1 / 60) {
          c.position(at.add(v.scale(t)).add([0, 0.5 * 900 * t * t]));
          c.rotation(t * 400);
          c.opacity(1 - t / 1.4);
          yield;
        }
        c.remove();
      })(),
    );
  }
  yield* all(...tasks);
}

/** The pull: the screen floods with light and Spark is drawn into it. */
export function* pullIn(s: Stage, room: Room): ThreadGenerator {
  const spark = s.spark.body;
  yield* syncTo('pull', 0);
  const glow = new Rect({position: SCREEN.centre, width: SCREEN.w, height: SCREEN.h, fill: '#ffffff', opacity: 0});
  s.props.add(glow);
  s.spawn(all(glow.opacity(0.85, 1.2, easeInCubic), s.room(1, 1.2), s.cam(SCREEN.centre.add([-60, 20]), 1.2, easeInOutCubic), s.zoom(2.4, 1.2, easeInOutCubic)));
  // Pixels reach out of the screen towards Spark.
  for (let i = 0; i < 14; i++) {
    const p = new Rect({position: SCREEN.centre.add([-150 + (i % 4) * 20, -60 + i * 9]), width: 8, height: 8, fill: i % 2 ? '#8ecae6' : '#ffffff'});
    s.fx.add(p);
    s.spawn(all(p.position(worldOf(s, spark.bones.head).add([(i % 5) * 6, (i % 3) * 8]), 1.1, easeInOutSine), p.opacity(0, 1.3)));
  }
  yield* syncTo('suck', 0);
  // Spark is drawn in: stretched, spinning, shrinking into the light.
  spark.setPose({torso: 40, head: 20, leftShoulder: -100, rightShoulder: -110, leftElbow: -10, rightElbow: -10, leftHip: -40, rightHip: -20, leftKnee: 20, rightKnee: 10});
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
  void room;
}

export {Line, waitFor};

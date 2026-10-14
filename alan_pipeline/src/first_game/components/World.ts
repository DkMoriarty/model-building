import {Circle, Gradient, Line, Node, NodeProps, Rect, Txt} from '@motion-canvas/2d';
import {createSignal, SimpleSignal, Vector2} from '@motion-canvas/core';
import {withAlpha} from '../../figureSpec';
import {Typography} from '../../styles';
import {roomPicture} from './Game';

/**
 * The computer world (original designs): binary blocks, the city they build,
 * the Shadow, the door home with its three lock lights, the key and the cars.
 * Every piece is drawn with its origin where it touches the ground.
 */
export const WORLD = {
  sky: '#03060c',
  bit: '#2ec4b6',
  deck: '#0c1a22',
  seam: '#14323a',
  red: '#ef476f',
  eye: '#ff2e4d',
  gold: '#ffd166',
  wood: '#6b4a32',
};
/** The road deck is a band from the far lane's edge to the floor line. */
export const DECK_TOP = 236;
/** Wheels touch the deck here: near lane (Spark) and far lane (overtaking). */
export const LANE_Y = [300, 258];

let seed = 7;
export function rand(): number {
  seed = (seed * 16807) % 2147483647;
  return (seed - 1) / 2147483646;
}

function bits(n: number): string {
  let s = '';
  for (let i = 0; i < n; i++) s += rand() < 0.5 ? '0' : '1';
  return s;
}

/** One binary block: a cube with its bit on the face. Flip it and the glyph changes. */
export class BitBlock extends Node {
  public readonly bit: SimpleSignal<number, this>;
  public readonly color: SimpleSignal<string, this>;
  public readonly glow = createSignal(0);
  public constructor(props: NodeProps & {size: number; bit?: number; color?: string}) {
    const {size, bit = 0, color = WORLD.bit, ...rest} = props;
    super(rest);
    this.bit = createSignal(bit) as SimpleSignal<number, this>;
    this.color = createSignal(color) as SimpleSignal<string, this>;
    this.add(
      new Rect({
        width: size,
        height: size,
        radius: size * 0.08,
        fill: () => withAlpha(this.color(), 0.1 + 0.5 * this.glow()),
        stroke: () => this.color(),
        lineWidth: Math.max(2, size * 0.05),
        shadowColor: () => this.color(),
        shadowBlur: () => 24 * this.glow(),
      }),
    );
    this.add(new Txt({text: () => (this.bit() ? '1' : '0'), fontFamily: Typography.mono, fontWeight: 800, fontSize: size * 0.62, fill: () => this.color(), y: size * 0.03}));
  }
}

/**
 * The city: a dark sky, towers of bits, streams of falling bits, and the
 * deck everything stands on. `from`..`to` is the world x range to build;
 * `gaps` are stretches with no deck (the broken bridge).
 */
export function buildCity(parent: Node, time: () => number, from: number, to: number, gaps: [number, number][] = [], raised: [number, number, number][] = []): Node {
  const city = new Node({});
  parent.add(city);
  city.add(new Rect({x: (from + to) / 2, y: 0, width: to - from + 4000, height: 4000, fill: WORLD.sky}));
  // A soft glow on the horizon.
  city.add(
    new Rect({
      x: (from + to) / 2,
      y: 60,
      width: to - from + 4000,
      height: 600,
      fill: new Gradient({type: 'linear', from: [0, -300], to: [0, 300], stops: [{offset: 0, color: withAlpha(WORLD.bit, 0)}, {offset: 0.8, color: withAlpha(WORLD.bit, 0.08)}, {offset: 1, color: withAlpha(WORLD.bit, 0)}]}),
    }),
  );
  // Falling streams of bits, far back.
  for (let x = from; x < to; x += 230 + rand() * 120) {
    const len = 14 + Math.floor(rand() * 10);
    const speed = 120 + rand() * 160;
    const phase = rand() * 900;
    const col = new Txt({
      x,
      text: bits(len).split('').join('\n'),
      fontFamily: Typography.mono,
      fontSize: 22,
      lineHeight: 26,
      fill: withAlpha(WORLD.bit, 0.16),
      y: () => -900 + ((time() * speed + phase) % 1300),
    });
    city.add(col);
  }
  // Towers: stacks of bits with lit seams.
  for (let x = from; x < to; x += 170 + rand() * 160) {
    const w = 90 + Math.floor(rand() * 4) * 30;
    const h = 260 + Math.floor(rand() * 9) * 70;
    const rows = Math.floor(h / 34);
    const cols = Math.floor(w / 17);
    const tower = new Node({x, y: DECK_TOP - h / 2});
    tower.add(new Rect({width: w, height: h, fill: '#071017', stroke: withAlpha(WORLD.bit, 0.35), lineWidth: 3}));
    const lines: string[] = [];
    for (let r = 0; r < rows; r++) lines.push(bits(cols));
    tower.add(new Txt({text: lines.join('\n'), fontFamily: Typography.mono, fontSize: 24, lineHeight: 34, fill: withAlpha(WORLD.bit, 0.22)}));
    city.add(tower);
  }
  // The deck: a two-lane road surface and a facade of bits below the floor line.
  const pieces: [number, number, number][] = [];
  let x0 = from;
  for (const [a, b] of [...gaps].sort((p, q) => p[0] - q[0])) {
    pieces.push([x0, a, 0]);
    x0 = b;
  }
  pieces.push([x0, to, 0]);
  for (const [a, b, lift] of raised) {
    for (const p of pieces) if (p[0] >= a && p[1] <= b) p[2] = lift;
  }
  for (const [a, b, lift] of pieces) {
    if (b - a < 1) continue;
    const deck = new Node({y: -lift});
    deck.add(new Rect({x: (a + b) / 2, y: (DECK_TOP + 300) / 2, width: b - a, height: 300 - DECK_TOP, fill: WORLD.deck}));
    deck.add(new Line({points: [[a, 279], [b, 279]], stroke: withAlpha('#e8e8e8', 0.35), lineWidth: 4, lineDash: [40, 40]}));
    deck.add(new Line({points: [[a, DECK_TOP], [b, DECK_TOP]], stroke: withAlpha(WORLD.bit, 0.5), lineWidth: 3}));
    deck.add(new Rect({x: (a + b) / 2, y: 300 + 200, width: b - a, height: 400, fill: '#050b10'}));
    deck.add(new Line({points: [[a, 300], [b, 300]], stroke: WORLD.bit, lineWidth: 5}));
    const rows: string[] = [];
    const n = Math.floor((b - a) / 30);
    for (let r = 0; r < 6; r++) rows.push(bits(n));
    deck.add(new Txt({x: (a + b) / 2, y: 300 + 110, text: rows.join('\n'), fontFamily: Typography.mono, fontSize: 30, lineHeight: 36, fill: withAlpha(WORLD.bit, 0.25)}));
    city.add(deck);
  }
  return city;
}

/**
 * The Shadow: a tall, torn silhouette with one red eye. Origin at its feet;
 * 470 units tall at scale 1. `rise` 0..1 lifts it out of the floor (the part
 * below the floor is clipped), `open` opens the eye, `look` slides the pupil
 * (-1..1), and each arm's angle is in degrees from straight down (positive
 * swings the hand towards -x, negative towards +x).
 */
export class Shadow extends Node {
  public readonly rise = createSignal(1);
  public readonly open = createSignal(1);
  public readonly look = createSignal(0);
  public readonly armL = createSignal(12);
  public readonly armR = createSignal(-12);
  public readonly body: Node;
  public static readonly H = 470;

  public constructor(props: NodeProps = {}) {
    super(props);
    const mask = new Rect({width: 1000, height: 1400, y: -700, clip: true});
    this.add(mask);
    this.body = new Node({y: () => 700 + (1 - this.rise()) * (Shadow.H + 40)});
    mask.add(this.body);
    // Torn outline: jagged at the hem and the shoulders.
    const pts: [number, number][] = [];
    const hem = [[-95, 0], [-70, -30], [-55, 0], [-30, -24], [-5, 0], [20, -26], [45, 0], [70, -28], [95, 0]];
    for (const [x, y] of hem) pts.push([x, y]);
    pts.push([88, -120], [104, -200], [92, -280], [118, -318], [84, -350], [70, -400], [52, -446], [20, -470], [-20, -470], [-52, -446], [-70, -400], [-84, -350], [-118, -318], [-92, -280], [-104, -200], [-88, -120]);
    this.body.add(new Line({points: pts, closed: true, fill: '#07070b', stroke: withAlpha(WORLD.red, 0.8), lineWidth: 4, shadowColor: WORLD.red, shadowBlur: 22}));
    const arm = (side: -1 | 1, angle: () => number) =>
      new Node({
        position: [side * 96, -318],
        rotation: () => angle(),
        children: [
          new Line({
            points: [[0, 0], [side * 8, 90], [-side * 4, 170], [0, 250]],
            stroke: '#07070b',
            lineWidth: 18,
            lineCap: 'round',
            lineJoin: 'round',
            shadowColor: WORLD.red,
            shadowBlur: 12,
          }),
          new Line({points: [[-16, 270], [0, 250], [16, 270]], stroke: '#07070b', lineWidth: 8, lineCap: 'round'}),
          new Line({points: [[0, 250], [0, 280]], stroke: '#07070b', lineWidth: 8, lineCap: 'round'}),
        ],
      });
    this.body.add(arm(-1, () => this.armL()));
    this.body.add(arm(1, () => this.armR()));
    const eye = new Node({y: -400});
    eye.add(new Circle({width: 64, height: () => 30 * this.open(), fill: WORLD.eye, shadowColor: WORLD.eye, shadowBlur: 30}));
    eye.add(new Rect({x: () => this.look() * 16, width: 8, height: () => 24 * this.open(), radius: 4, fill: '#120004'}));
    this.body.add(eye);
  }
}

/** The key home: a gold ring, a shaft and teeth, glowing. Origin at its centre. */
export function goldKey(props: NodeProps = {}): Node {
  const k = new Node(props);
  k.add(new Circle({size: 160, fill: new Gradient({type: 'radial', fromRadius: 0, toRadius: 80, stops: [{offset: 0, color: withAlpha(WORLD.gold, 0.45)}, {offset: 1, color: withAlpha(WORLD.gold, 0)}]})}));
  k.add(new Circle({x: -30, size: 34, stroke: WORLD.gold, lineWidth: 8}));
  k.add(new Line({points: [[-13, 0], [40, 0]], stroke: WORLD.gold, lineWidth: 8, lineCap: 'round'}));
  k.add(new Line({points: [[24, 0], [24, 12]], stroke: WORLD.gold, lineWidth: 6}));
  k.add(new Line({points: [[36, 0], [36, 14]], stroke: WORLD.gold, lineWidth: 6}));
  return k;
}

/**
 * The door home: a wooden door (the one real-world thing here) in a lit
 * frame, Spark's room behind it, three lock lights above it and a keyhole
 * that appears when all three are lit. `open` swings the panel on its left
 * hinge (0 shut, 1 open). Origin at the threshold.
 */
export class HomeDoor extends Node {
  public readonly lights = [createSignal(0), createSignal(0), createSignal(0)];
  public readonly keyhole = createSignal(0);
  public readonly open = createSignal(0);
  public static readonly W = 120;
  public static readonly HT = 240;

  public constructor(props: NodeProps = {}) {
    super(props);
    const W = HomeDoor.W;
    const HT = HomeDoor.HT;
    this.add(new Circle({y: -HT / 2, size: 520, fill: new Gradient({type: 'radial', fromRadius: 0, toRadius: 260, stops: [{offset: 0, color: withAlpha(WORLD.gold, 0.22)}, {offset: 1, color: withAlpha(WORLD.gold, 0)}]})}));
    const inside = new Rect({y: -HT / 2, width: W, height: HT, radius: [W / 2, W / 2, 0, 0], clip: true, fill: '#f6e7c1'});
    inside.add(roomPicture({scale: 0.32, y: 30}));
    this.add(inside);
    // The panel, hinged on its left edge: it narrows (and darkens) as it swings open.
    const panel = new Node({x: -W / 2, y: -HT / 2, scale: () => [1 - 0.88 * this.open(), 1]});
    panel.add(new Rect({x: W / 2, width: W, height: HT, radius: [W / 2, W / 2, 0, 0], fill: () => mixHex(WORLD.wood, '#2a1c12', this.open()), stroke: '#3b2a1c', lineWidth: 4}));
    panel.add(new Rect({x: W / 2, y: -30, width: W - 40, height: 70, radius: 6, stroke: '#3b2a1c', lineWidth: 3}));
    panel.add(new Rect({x: W / 2, y: 60, width: W - 40, height: 70, radius: 6, stroke: '#3b2a1c', lineWidth: 3}));
    const hole = new Node({x: W - 26, y: 10, opacity: () => this.keyhole()});
    hole.add(new Circle({size: 16, fill: '#120c06', stroke: WORLD.gold, lineWidth: 3}));
    hole.add(new Line({points: [[-4, 6], [4, 6], [2, 20], [-2, 20]], closed: true, fill: '#120c06'}));
    panel.add(hole);
    this.add(panel);
    this.add(new Rect({y: -HT / 2, width: W + 16, height: HT + 8, radius: [W / 2 + 8, W / 2 + 8, 0, 0], stroke: WORLD.gold, lineWidth: 6, shadowColor: WORLD.gold, shadowBlur: 16}));
    this.lights.forEach((lit, i) =>
      this.add(
        new Circle({
          position: [(i - 1) * 40, -HT - 40],
          size: 26,
          fill: () => (lit() > 0.5 ? '#57e389' : '#10241a'),
          stroke: '#57e389',
          lineWidth: 4,
          shadowColor: '#57e389',
          shadowBlur: () => 24 * lit(),
          scale: () => 1 + 0.25 * Math.sin(Math.min(1, lit()) * Math.PI),
        }),
      ),
    );
  }
}

/**
 * A side-on car (original design), facing +x, origin on the road under its
 * centre, 220 units long. `driver` sits in the open cockpit, between the
 * seat and the body. Wheels turn by distance travelled: rotation = x / r.
 */
export class Car extends Node {
  public readonly seat: Node;
  public readonly travelled = createSignal(0);
  public static readonly HALF = 110;
  public static readonly WHEEL = 26;

  public constructor(props: NodeProps & {color: string}) {
    const {color, ...rest} = props;
    super(rest);
    this.seat = new Node({position: [-22, -46]});
    this.add(new Line({points: [[-60, -46], [-60, -110], [-44, -116]], stroke: '#1d1d24', lineWidth: 10, lineCap: 'round'}));
    this.add(this.seat);
    this.add(new Line({points: [[22, -80], [34, -100]], stroke: '#1d1d24', lineWidth: 6, lineCap: 'round'}));
    this.add(new Circle({position: [22, -92], width: 8, height: 30, rotation: -30, stroke: '#1d1d24', lineWidth: 5}));
    this.add(
      new Line({
        points: [[-110, -24], [-110, -64], [-96, -76], [-50, -76], [-44, -62], [28, -62], [40, -76], [92, -70], [110, -50], [110, -24]],
        closed: true,
        fill: color,
        stroke: '#101014',
        lineWidth: 4,
        lineJoin: 'round',
      }),
    );
    this.add(new Line({points: [[40, -76], [56, -116]], stroke: withAlpha('#d8f3ff', 0.8), lineWidth: 5, lineCap: 'round'}));
    this.add(new Rect({x: 100, y: -46, width: 10, height: 8, radius: 3, fill: '#fff3b0'}));
    for (const x of [-70, 70]) {
      const wheel = new Node({position: [x, -Car.WHEEL], rotation: () => (this.travelled() / Car.WHEEL) * (180 / Math.PI)});
      wheel.add(new Circle({size: Car.WHEEL * 2, fill: '#15151a', stroke: '#3a3a44', lineWidth: 5}));
      wheel.add(new Line({points: [[-16, 0], [16, 0]], stroke: '#8d99ae', lineWidth: 4}));
      wheel.add(new Line({points: [[0, -16], [0, 16]], stroke: '#8d99ae', lineWidth: 4}));
      this.add(wheel);
    }
  }
}

/** The Shadow's eye in the sky (screen space): it watches every game. */
export function skyEye(look: () => number, open: () => number): Node {
  const n = new Node({});
  n.add(new Circle({width: 300, height: 130, fill: new Gradient({type: 'radial', fromRadius: 0, toRadius: 150, stops: [{offset: 0, color: withAlpha(WORLD.eye, 0.35)}, {offset: 1, color: withAlpha(WORLD.eye, 0)}]})}));
  n.add(new Circle({width: 150, height: () => 64 * open(), fill: WORLD.eye, shadowColor: WORLD.eye, shadowBlur: 40}));
  n.add(new Rect({x: () => look() * 40, width: 16, height: () => 52 * open(), radius: 8, fill: '#120004'}));
  return n;
}

export function mixHex(a: string, b: string, t: number): string {
  const pa = parseInt(a.slice(1), 16);
  const pb = parseInt(b.slice(1), 16);
  const ch = (p: number, s: number) => (p >> s) & 255;
  const m = (s: number) => Math.round(ch(pa, s) + (ch(pb, s) - ch(pa, s)) * Math.max(0, Math.min(1, t)));
  return `#${((1 << 24) | (m(16) << 16) | (m(8) << 8) | m(0)).toString(16).slice(1)}`;
}

export {Vector2};

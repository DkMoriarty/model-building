import {Circle, Gradient, Line, Node, NodeProps, Rect, Txt, TxtProps} from '@motion-canvas/2d';
import {createSignal, SimpleSignal, Vector2} from '@motion-canvas/core';
import {withAlpha} from '../../figureSpec';
import {Typography} from '../../styles';
import {TIER} from '../../first_light/components/Circuit';

/** World layout of the room (original set: Spark's desk at night). */
export const FLOOR = 300;
export const SEAT = new Vector2(-60, 248);
export const DESK_Y = 200;
export const KEYS = {from: 10, to: 100, y: DESK_Y - 8};
export const PAD_AT = new Vector2(140, DESK_Y - 13);
export const SCREEN = {centre: new Vector2(340, 50), w: 352, h: 198};
/** Game units (1280 x 720) to screen units. */
export const SCREEN_SCALE = SCREEN.w / 1280;
export const CLOCK_AT = new Vector2(-280, -150);
export const WINDOW_AT = new Vector2(-440, -110);
export const SCREEN_GLOW = '#8ecae6';

const WOOD = '#5c4033';
const EDGE = '#9a8a7a';

/** Desk, chair, monitor, keyboard, controller, wall clock and window. */
export class Room extends Node {
  /** Clip node for the monitor picture; children use screen units, origin at its centre. */
  public readonly screen: Node;
  public readonly screenOn = createSignal(1);
  public readonly pad: Node;
  /** Clock time in hours (e.g. 20 = 8 pm); the hands follow it. */
  public readonly hours: SimpleSignal<number, this>;
  /** 0 = night sky, 1 = morning. */
  public readonly morning = createSignal(0);

  public constructor(props: NodeProps = {}) {
    super(props);
    this.hours = createSignal(20) as SimpleSignal<number, this>;
    // Window first (furthest back).
    const win = new Node({position: WINDOW_AT});
    win.add(
      new Rect({
        width: 200,
        height: 240,
        clip: true,
        fill: () =>
          new Gradient({
            type: 'linear',
            from: [0, -120],
            to: [0, 120],
            stops: [
              {offset: 0, color: mix('#0b1026', '#7fc8f8', this.morning())},
              {offset: 1, color: mix('#1b2347', '#ffe8b0', this.morning())},
            ],
          }),
        children: [
          new Circle({x: 50, y: -60, size: 34, fill: () => (this.morning() > 0.5 ? '#fff3b0' : '#e8e8f0'), shadowColor: 'rgba(255,255,220,0.6)', shadowBlur: 18}),
          ...[
            [-60, -80],
            [-20, -30],
            [30, 20],
            [-70, 40],
            [70, -10],
          ].map(([x, y]) => new Circle({x, y, size: 4, fill: '#ffffff', opacity: () => 1 - this.morning()})),
        ],
      }),
    );
    win.add(new Rect({width: 200, height: 240, stroke: EDGE, lineWidth: TIER.structure}));
    win.add(new Line({points: [[0, -120], [0, 120]], stroke: EDGE, lineWidth: TIER.detail}));
    win.add(new Line({points: [[-100, 0], [100, 0]], stroke: EDGE, lineWidth: TIER.detail}));
    this.add(win);

    // Wall clock: the hour hand turns 30 degrees an hour.
    const clock = new Node({position: CLOCK_AT});
    clock.add(new Circle({size: 84, fill: '#1b1b22', stroke: EDGE, lineWidth: TIER.structure}));
    for (let i = 0; i < 12; i++) {
      const a = (i * Math.PI) / 6;
      clock.add(new Line({points: [[Math.sin(a) * 32, -Math.cos(a) * 32], [Math.sin(a) * 37, -Math.cos(a) * 37]], stroke: EDGE, lineWidth: TIER.detail}));
    }
    clock.add(new Line({points: [[0, 0], [0, -20]], stroke: '#f2f2f2', lineWidth: TIER.structure, lineCap: 'round', rotation: () => (this.hours() % 12) * 30}));
    clock.add(new Line({points: [[0, 0], [0, -30]], stroke: '#f2f2f2', lineWidth: TIER.detail, lineCap: 'round', rotation: () => (this.hours() % 1) * 360}));
    clock.add(new Circle({size: 8, fill: '#f2f2f2'}));
    this.add(clock);

    // Chair (Spark sits facing right).
    const chair = new Node({});
    chair.add(new Line({points: [[SEAT.x - 55, SEAT.y + 4], [SEAT.x + 45, SEAT.y + 4]], stroke: WOOD, lineWidth: TIER.figure, lineCap: 'round'}));
    chair.add(new Line({points: [[SEAT.x - 58, SEAT.y + 4], [SEAT.x - 70, SEAT.y - 130]], stroke: WOOD, lineWidth: TIER.figure, lineCap: 'round'}));
    chair.add(new Line({points: [[SEAT.x - 48, SEAT.y + 6], [SEAT.x - 52, FLOOR]], stroke: WOOD, lineWidth: TIER.structure}));
    chair.add(new Line({points: [[SEAT.x + 38, SEAT.y + 6], [SEAT.x + 42, FLOOR]], stroke: WOOD, lineWidth: TIER.structure}));
    this.add(chair);

    // Desk.
    this.add(new Rect({x: 275, y: DESK_Y + 6, width: 570, height: 12, radius: 3, fill: WOOD, stroke: EDGE, lineWidth: TIER.detail}));
    for (const x of [10, 540]) this.add(new Line({points: [[x, DESK_Y + 12], [x, FLOOR]], stroke: WOOD, lineWidth: TIER.structure}));

    // Monitor: stand, bezel, and the clipped picture.
    this.add(new Rect({x: SCREEN.centre.x, y: DESK_Y - 4, width: 90, height: 8, radius: 3, fill: '#2a2a33'}));
    this.add(new Line({points: [[SCREEN.centre.x, DESK_Y - 4], [SCREEN.centre.x, SCREEN.centre.y + SCREEN.h / 2 + 10]], stroke: '#2a2a33', lineWidth: 12}));
    // Glow the screen throws on the wall around it.
    this.add(
      new Circle({
        position: SCREEN.centre,
        size: 900,
        opacity: () => this.screenOn() * 0.9,
        fill: new Gradient({type: 'radial', fromRadius: 0, toRadius: 450, stops: [{offset: 0, color: withAlpha(SCREEN_GLOW, 0.16)}, {offset: 1, color: withAlpha(SCREEN_GLOW, 0)}]}),
      }),
    );
    this.add(new Rect({position: SCREEN.centre, width: SCREEN.w + 28, height: SCREEN.h + 28, radius: 12, fill: '#16161c', stroke: '#4a4a56', lineWidth: TIER.structure}));
    this.screen = new Rect({position: SCREEN.centre, width: SCREEN.w, height: SCREEN.h, radius: 4, clip: true, fill: '#05070d'});
    this.add(this.screen);
    this.add(new Circle({x: SCREEN.centre.x + SCREEN.w / 2 - 4, y: SCREEN.centre.y + SCREEN.h / 2 + 8, size: 5, fill: () => (this.screenOn() > 0.5 ? '#57e389' : '#333')}));

    // Keyboard (side-on: a slab with a row of key caps).
    const kb = new Node({});
    kb.add(new Rect({x: (KEYS.from + KEYS.to) / 2, y: DESK_Y - 4, width: KEYS.to - KEYS.from + 16, height: 8, radius: 2, fill: '#2a2a33', stroke: '#6b6b78', lineWidth: TIER.detail}));
    for (let x = KEYS.from; x <= KEYS.to; x += 13) kb.add(new Rect({x, y: DESK_Y - 10, width: 9, height: 5, radius: 1, fill: '#4a4a56'}));
    this.add(kb);

    // The game pad: our own design, two grips, a cross and two buttons.
    this.pad = gamePad();
    this.pad.position(PAD_AT);
    this.add(this.pad);
  }
}

/** A game pad (original design). */
export function gamePad(): Node {
  const n = new Node({});
  n.add(new Rect({width: 54, height: 24, radius: 12, fill: '#2b2d42', stroke: '#8d99ae', lineWidth: TIER.detail}));
  n.add(new Rect({x: -14, width: 12, height: 4, fill: '#8d99ae'}));
  n.add(new Rect({x: -14, width: 4, height: 12, fill: '#8d99ae'}));
  n.add(new Circle({x: 12, y: 3, size: 7, fill: '#ef476f'}));
  n.add(new Circle({x: 20, y: -3, size: 7, fill: '#06d6a0'}));
  return n;
}

/** Screen-space text in the game's pixel style. */
export function gameText(text: string, size: number, color = '#f2f2f2', props: TxtProps = {}): Txt {
  return new Txt({text, fontFamily: Typography.mono, fontWeight: 800, fontSize: size, fill: color, letterSpacing: size * 0.12, ...props});
}

function mix(a: string, b: string, t: number): string {
  const pa = parseInt(a.slice(1), 16);
  const pb = parseInt(b.slice(1), 16);
  const ch = (p: number, s: number) => (p >> s) & 255;
  const m = (s: number) => Math.round(ch(pa, s) + (ch(pb, s) - ch(pa, s)) * Math.max(0, Math.min(1, t)));
  return `#${((1 << 24) | (m(16) << 16) | (m(8) << 8) | m(0)).toString(16).slice(1)}`;
}

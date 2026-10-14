import {Circle, Line, Node, NodeProps, Rect, Txt} from '@motion-canvas/2d';
import {createComputed, createSignal, SimpleSignal, Vector2} from '@motion-canvas/core';
import {strokeTiers, withAlpha} from '../../figureSpec';
import {Typography} from '../../styles';

/**
 * Circuit parts for FIRST LIGHT. Electricity is drawn as glowing beads that
 * roll along wires, and only while the wire makes a closed loop. Every part
 * is an original design, drawn on the structure and detail line tiers so
 * Spark (figure tier) always reads first.
 */
export const TIER = strokeTiers();
export const WIRE_GREY = '#6b6b78';
export const BEAD = '#ffd27a';
export const MIND = '#a78bfa';
export const OK_GREEN = '#57e389';
export const BAD_RED = '#ff5d5d';

/** Arc-length parametrised polyline. */
export class Path {
  public readonly lengths: number[] = [0];
  public readonly total: number;
  public constructor(public readonly points: Vector2[]) {
    for (let i = 1; i < points.length; i++) {
      this.lengths.push(this.lengths[i - 1] + points[i].sub(points[i - 1]).magnitude);
    }
    this.total = this.lengths[this.lengths.length - 1];
  }
  public at(d: number): Vector2 {
    if (this.points.length < 2 || this.total <= 0) return this.points[0] ?? Vector2.zero;
    const x = Math.max(0, Math.min(this.total, d));
    let i = 1;
    while (i < this.lengths.length - 1 && this.lengths[i] < x) i++;
    const seg = this.lengths[i] - this.lengths[i - 1] || 1;
    return Vector2.lerp(this.points[i - 1], this.points[i], (x - this.lengths[i - 1]) / seg);
  }
}

export interface WireProps extends NodeProps {
  points: () => Vector2[];
  /** Gap between beads in px. */
  spacing?: number;
  /** Bead pool size (beads beyond the wire's length are hidden). */
  pool?: number;
  /** Show the beads only on this fraction of the wire, from its start (a dangling lead). */
  fill?: number;
  /** Scene clock, for the jitter of beads pressing against a gap. */
  time?: () => number;
}

/**
 * A wire with current. `speed` is how fast the beads roll (px/s); the stage
 * integrates it every frame into `flow`, so beads move exactly when, and only
 * when, the circuit is closed. `beads` (0..1) is their visibility, `color`
 * their glow.
 */
export class Wire extends Node {
  public readonly speed = createSignal(0);
  public readonly flow = createSignal(0);
  public readonly beads = createSignal(1);
  public readonly jitter = createSignal(0);
  public readonly color = createSignal(BEAD);
  public readonly trim = createSignal(1);
  public readonly path: () => Path;
  public readonly line: Line;

  public constructor({points, spacing = 30, pool = 60, fill = 1, time = () => 0, ...props}: WireProps) {
    super(props);
    this.path = createComputed(() => new Path(points()));
    this.line = new Line({
      points,
      stroke: WIRE_GREY,
      lineWidth: TIER.structure,
      lineCap: 'round',
      lineJoin: 'round',
      end: () => this.trim(),
    });
    this.add(this.line);
    for (let i = 0; i < pool; i++) {
      const d = () => {
        const p = this.path();
        const span = p.total * fill;
        if (span <= 0) return -1;
        const raw = i * spacing + this.flow();
        return ((raw % span) + span) % span;
      };
      const visible = () => {
        const p = this.path();
        return i * spacing < p.total * fill && d() >= 0 && d() <= p.total * this.trim();
      };
      const wobble = () => {
        const j = this.jitter();
        if (j <= 0) return Vector2.zero;
        const t = time();
        return new Vector2(Math.sin(t * 37 + i * 2.1), Math.cos(t * 41 + i * 1.3)).scale(j);
      };
      this.add(
        new Circle({
          size: TIER.structure * 1.5,
          fill: () => this.color(),
          shadowColor: () => withAlpha(this.color().startsWith('#') ? this.color() : BEAD, 0.8),
          shadowBlur: 8,
          position: () => this.path().at(d()).add(wobble()),
          opacity: () => (visible() ? this.beads() : 0),
        }),
      );
    }
  }

  /** Point at distance `d` along the wire. */
  public pointAt(d: number): Vector2 {
    return this.path().at(d);
  }
}

export interface BulbProps extends NodeProps {
  radius?: number;
}

/**
 * A light bulb, base down. `glow` 0..1 lights the filament and the glass,
 * `heat` 0..1 tints it towards overheated orange, `level` 0..1 shows a liquid
 * level (the learning bulb fills like a glass), `glass` 0..1 hides the glass
 * when it has burst.
 */
export class Bulb extends Node {
  public readonly glow = createSignal(0);
  public readonly heat = createSignal(0);
  public readonly level = createSignal(0);
  public readonly showLevel = createSignal(0);
  public readonly glass = createSignal(1);
  public readonly tint = createSignal(BEAD);
  public readonly radius: number;

  public constructor({radius = 26, ...props}: BulbProps = {}) {
    super(props);
    this.radius = radius;
    const r = radius;
    const lit = () => this.glow() * this.glass();
    const glowColor = () => (this.heat() > 0.01 ? mixHex(this.tint(), '#ff7b2e', this.heat()) : this.tint());
    // Soft bloom behind the glass; the outline itself stays sharp.
    this.add(
      new Circle({
        y: -r * 1.1,
        size: r * 6,
        fill: () => withAlpha(glowColor(), 0.22 * lit()),
      }),
    );
    this.add(
      new Circle({
        y: -r * 1.1,
        size: r * 3.4,
        fill: () => withAlpha(glowColor(), 0.3 * lit()),
      }),
    );
    // Liquid level (threshold gauge): clipped inside the glass.
    const glassCircle = new Circle({
      y: -r * 1.1,
      size: r * 2,
      clip: true,
      fill: () => withAlpha(glowColor(), 0.12 + 0.6 * lit()),
      opacity: () => this.glass(),
    });
    glassCircle.add(
      new Rect({
        width: r * 2,
        height: () => r * 2 * this.level(),
        y: () => r - r * this.level(),
        fill: () => withAlpha(this.tint(), 0.55),
        opacity: () => this.showLevel(),
      }),
    );
    // Threshold mark: half full.
    glassCircle.add(
      new Line({
        points: [
          [-r, 0],
          [r, 0],
        ],
        stroke: '#ffffff',
        lineWidth: TIER.detail,
        lineDash: [6, 5],
        opacity: () => 0.7 * this.showLevel(),
      }),
    );
    this.add(glassCircle);
    this.add(
      new Circle({
        y: -r * 1.1,
        size: r * 2,
        stroke: () => (lit() > 0.05 ? glowColor() : '#9a9aa6'),
        lineWidth: TIER.structure,
        opacity: () => this.glass(),
      }),
    );
    // Neck and filament.
    this.add(
      new Line({
        points: [
          [-r * 0.45, -r * 0.2],
          [-r * 0.45, -r * 0.9],
          [-r * 0.22, -r * 1.25],
          [0, -r * 0.95],
          [r * 0.22, -r * 1.25],
          [r * 0.45, -r * 0.9],
          [r * 0.45, -r * 0.2],
        ],
        stroke: () => (lit() > 0.05 ? '#ffffff' : '#7a7a86'),
        lineWidth: TIER.detail,
        lineJoin: 'round',
        shadowColor: () => withAlpha(glowColor(), lit()),
        shadowBlur: () => 16 * lit(),
      }),
    );
    // Screw base with threads.
    this.add(
      new Rect({
        y: r * 0.15,
        width: r * 1.0,
        height: r * 0.7,
        radius: r * 0.12,
        fill: '#2a2a33',
        stroke: '#9a9aa6',
        lineWidth: TIER.detail,
      }),
    );
    for (const y of [r * 0.02, r * 0.28]) {
      this.add(
        new Line({
          points: [
            [-r * 0.5, y],
            [r * 0.5, y + r * 0.1],
          ],
          stroke: '#9a9aa6',
          lineWidth: TIER.detail,
        }),
      );
    }
    this.add(new Circle({y: r * 0.6, size: r * 0.3, fill: '#9a9aa6'}));
  }

  /** Contact at the bottom tip (local). */
  public get tipContact(): Vector2 {
    return new Vector2(0, this.radius * 0.66);
  }
  /** Contact on the screw shell (local). */
  public get shellContact(): Vector2 {
    return new Vector2(this.radius * 0.5, this.radius * 0.2);
  }
  /** Centre of the glass (local). */
  public get glassCentre(): Vector2 {
    return new Vector2(0, -this.radius * 1.1);
  }
}

/**
 * A push switch on a wire: two posts and a bridge. `closed` 0..1. A
 * normally-closed (NOT) switch has a red cap and is closed at rest.
 */
export class Switch extends Node {
  public readonly closed: SimpleSignal<number, this>;
  public readonly span: number;

  public constructor({cap = '#d8d8e0', closed = 0, span = 36, ...props}: NodeProps & {cap?: string; closed?: number; span?: number}) {
    super(props);
    this.span = span;
    this.closed = createSignal(closed) as SimpleSignal<number, this>;
    const h = span / 2;
    for (const x of [-h, h]) {
      this.add(new Rect({x, y: 4, width: 10, height: 14, radius: 2, fill: '#2a2a33', stroke: '#9a9aa6', lineWidth: TIER.detail}));
    }
    this.add(
      new Node({
        x: -h,
        rotation: () => -32 * (1 - this.closed()),
        children: [
          new Line({
            points: [
              [0, 0],
              [span, 0],
            ],
            stroke: '#c9c9d3',
            lineWidth: TIER.structure,
            lineCap: 'round',
          }),
          new Circle({x: span * 0.55, y: -9, size: 14, fill: cap, stroke: '#2a2a33', lineWidth: TIER.detail}),
        ],
      }),
    );
  }

  /** Where a finger presses (local). */
  public get button(): Vector2 {
    return new Vector2(this.span * 0.05, -14);
  }
}

/** A dial: the needle shows `value` 0..1 over a 270-degree sweep. A small motor box sits beside it. */
export class Dial extends Node {
  public readonly value: SimpleSignal<number, this>;
  public readonly motor = createSignal(0);

  public constructor({value = 0, size = 34, ...props}: NodeProps & {value?: number; size?: number}) {
    super(props);
    this.value = createSignal(value) as SimpleSignal<number, this>;
    const r = size / 2;
    this.add(new Circle({size, fill: '#1b1b22', stroke: '#9a9aa6', lineWidth: TIER.structure}));
    for (let i = 0; i <= 6; i++) {
      const a = ((-135 + i * 45) * Math.PI) / 180;
      const dir = new Vector2(Math.sin(a), -Math.cos(a));
      this.add(new Line({points: [dir.scale(r * 0.62), dir.scale(r * 0.82)], stroke: '#6b6b78', lineWidth: TIER.detail}));
    }
    this.add(
      new Line({
        points: [
          [0, 0],
          [0, -r * 0.75],
        ],
        rotation: () => -135 + 270 * this.value(),
        stroke: BEAD,
        lineWidth: TIER.structure,
        lineCap: 'round',
      }),
    );
    this.add(new Circle({size: r * 0.4, fill: '#9a9aa6'}));
    // Motor: lights violet while it turns the dial by itself.
    this.add(
      new Rect({
        x: r + 12,
        width: 14,
        height: 18,
        radius: 3,
        fill: () => (this.motor() > 0.05 ? withAlpha(MIND, 0.25 + 0.6 * this.motor()) : '#22222a'),
        stroke: '#6b6b78',
        lineWidth: TIER.detail,
      }),
    );
  }
}

/**
 * A light-eye (photocell): a ring with a pupil. `lit` 0..1 fills it, `look`
 * is the pupil offset direction, `open` 0..1 its vertical opening.
 */
export class Eye extends Node {
  public readonly lit = createSignal(0);
  public readonly look = Vector2.createSignal(Vector2.zero);
  public readonly open = createSignal(1);
  public readonly tint = createSignal(BEAD);

  public constructor({size = 40, ...props}: NodeProps & {size?: number}) {
    super(props);
    const r = size / 2;
    this.add(new Circle({size: size * 1.9, fill: () => withAlpha(this.tint(), 0.18 * this.lit())}));
    const body = new Node({scale: () => [1, Math.max(0.02, this.open())]});
    body.add(new Circle({size, fill: () => (this.lit() > 0.02 ? withAlpha(this.tint(), 0.25 + 0.6 * this.lit()) : '#15151b'), stroke: '#9a9aa6', lineWidth: TIER.structure}));
    body.add(new Circle({size: r * 0.7, fill: '#0a0a0e', position: () => this.look().scale(r * 0.45)}));
    this.add(body);
  }
}

/** Patterns on a 3 x 3 grid, row by row. */
export const SHAPES = {
  ring: [1, 1, 1, 1, 0, 1, 1, 1, 1],
  cross: [0, 1, 0, 1, 1, 1, 0, 1, 0],
  figure: [0, 1, 0, 1, 1, 1, 1, 0, 1],
} as const;
export type ShapeName = keyof typeof SHAPES;

/** A card with a 3 x 3 picture on it. */
export function card(shape: ShapeName, props: NodeProps = {}): Node {
  const n = new Node(props);
  n.add(new Rect({width: 66, height: 80, radius: 6, fill: '#eeeae0', stroke: '#9a9aa6', lineWidth: TIER.detail}));
  SHAPES[shape].forEach((on, i) => {
    if (!on) return;
    n.add(new Rect({x: ((i % 3) - 1) * 17, y: (Math.floor(i / 3) - 1) * 17 - 4, width: 14, height: 14, radius: 2, fill: '#1b1b22'}));
  });
  return n;
}

/** A parts crate: planks, a spool and a few odds and ends sticking out. */
export function crate(props: NodeProps = {}): Node {
  const n = new Node(props);
  n.add(new Rect({y: -20, width: 120, height: 40, radius: 3, fill: '#2b2420', stroke: '#8a7a6a', lineWidth: TIER.structure}));
  n.add(new Line({points: [[-60, -20], [60, -20]], stroke: '#8a7a6a', lineWidth: TIER.detail}));
  n.add(new Circle({x: -30, y: -48, size: 34, stroke: '#b5651d', lineWidth: TIER.structure * 1.4}));
  n.add(new Circle({x: -30, y: -48, size: 10, fill: '#8a7a6a'}));
  n.add(new Line({points: [[16, -40], [40, -66]], stroke: '#c9c9d3', lineWidth: TIER.structure, lineCap: 'round'}));
  n.add(new Line({points: [[30, -40], [56, -58]], stroke: '#9a9aa6', lineWidth: TIER.structure, lineCap: 'round'}));
  n.add(new Bulb({x: 4, y: -44, radius: 9, rotation: -20}));
  return n;
}

/** A wall socket. */
export function socket(props: NodeProps = {}): Node {
  const n = new Node(props);
  n.add(new Rect({width: 46, height: 58, radius: 8, fill: '#1b1b22', stroke: '#9a9aa6', lineWidth: TIER.structure}));
  n.add(new Rect({x: -8, y: -6, width: 5, height: 14, radius: 2, fill: '#0a0a0e'}));
  n.add(new Rect({x: 8, y: -6, width: 5, height: 14, radius: 2, fill: '#0a0a0e'}));
  return n;
}

/** A small indicator lamp with a label below. */
export function indicator(color: string, label: string, on: () => number, props: NodeProps = {}): Node {
  const n = new Node(props);
  n.add(new Circle({size: 64, fill: () => withAlpha(color, 0.25 * on())}));
  n.add(new Circle({size: 28, fill: () => (on() > 0.05 ? color : '#22222a'), stroke: color, lineWidth: TIER.structure}));
  n.add(new Txt({y: 34, text: label, fill: '#6b6b78', fontFamily: Typography.mono, fontSize: 16}));
  return n;
}

/** Linear mix of two #rrggbb colours. */
export function mixHex(a: string, b: string, t: number): string {
  const pa = parseInt(a.slice(1), 16);
  const pb = parseInt(b.slice(1), 16);
  const ch = (p: number, s: number) => (p >> s) & 255;
  const m = (s: number) => Math.round(ch(pa, s) + (ch(pb, s) - ch(pa, s)) * t);
  return `#${((1 << 24) | (m(16) << 16) | (m(8) << 8) | m(0)).toString(16).slice(1)}`;
}

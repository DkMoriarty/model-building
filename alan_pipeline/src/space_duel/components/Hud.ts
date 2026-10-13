import {Circle, Line, Node, NodeProps, Rect, Txt} from '@motion-canvas/2d';
import {all, createSignal, easeOutCubic, SimpleSignal, ThreadGenerator, waitFor} from '@motion-canvas/core';
import {Colors, Typography} from '../../styles';
import {ALIEN_COLOR} from './Fighters';

/** Bottom-centre subtitles for narration (white) and the alien (green, chevrons). */
export class Subtitles extends Node {
  private readonly text: Txt;

  public constructor(props: NodeProps = {}) {
    super({y: 440, ...props});
    this.text = new Txt({
      text: '',
      width: 1500,
      textWrap: true,
      textAlign: 'center',
      fill: Colors.ink,
      fontFamily: Typography.family,
      fontSize: 38,
      lineHeight: 52,
      opacity: 0,
      shadowColor: 'rgba(0,0,0,0.9)',
      shadowBlur: 12,
    });
    this.add(this.text);
  }

  /** Show `text` for exactly [start, end] (absolute seconds) with short fades. */
  public *say(text: string, voice: string, until: number, now: number): ThreadGenerator {
    const alien = voice === 'alien';
    this.text.text(alien ? `‹ ${text} ›` : text);
    this.text.fill(alien ? ALIEN_COLOR : Colors.ink);
    this.text.fontStyle(alien ? 'italic' : 'normal');
    yield* this.text.opacity(1, 0.15);
    yield* waitFor(Math.max(0, until - now - 0.15));
    yield* this.text.opacity(0, 0.25);
  }
}

/**
 * Top-left physics callout: the equation in mono, one line of plain English
 * under it. One at a time; `show` swaps the contents with a quick fade.
 */
export class PhysicsLabel extends Node {
  private readonly eq: Txt;
  private readonly note: Txt;
  private readonly box: Rect;

  public constructor(props: NodeProps = {}) {
    super({x: -900, y: -470, opacity: 0, ...props});
    this.eq = new Txt({
      text: '',
      offset: [-1, -1],
      fill: '#ffd166',
      fontFamily: Typography.mono,
      fontSize: 34,
    });
    this.note = new Txt({
      text: '',
      offset: [-1, -1],
      y: 50,
      fill: Colors.inkMuted,
      fontFamily: Typography.family,
      fontSize: 24,
    });
    this.box = new Rect({
      offset: [-1, -1],
      x: -18,
      y: -14,
      width: () => Math.max(this.eq.width(), this.note.width()) + 36,
      height: 104,
      radius: 8,
      fill: 'rgba(10,10,14,0.72)',
      stroke: 'rgba(255,209,102,0.35)',
      lineWidth: 2,
    });
    this.add([this.box, this.eq, this.note]);
  }

  public *show(eq: string, note: string): ThreadGenerator {
    if (this.opacity() > 0) yield* this.opacity(0, 0.15);
    this.eq.text(eq);
    this.note.text(note);
    yield* this.opacity(1, 0.25);
  }

  public *hide(): ThreadGenerator {
    yield* this.opacity(0, 0.3);
  }
}

/** Centre title card. */
export function titleCard(title: string, subtitle: string): Node {
  return new Node({
    opacity: 0,
    children: [
      new Txt({
        text: title.toUpperCase(),
        fill: Colors.ink,
        fontFamily: Typography.family,
        fontSize: 96,
        fontWeight: 800,
        letterSpacing: 18,
      }),
      new Line({
        points: [
          [-360, 70],
          [360, 70],
        ],
        stroke: Colors.accent,
        lineWidth: 4,
      }),
      new Txt({
        y: 112,
        text: subtitle,
        fill: Colors.inkMuted,
        fontFamily: Typography.mono,
        fontSize: 26,
        letterSpacing: 4,
      }),
    ],
  });
}

/** An analogue dial whose hand angle (degrees) is a signal. */
export class ClockDial extends Node {
  public readonly angle: SimpleSignal<number, this>;

  public constructor({label, color, ...props}: NodeProps & {label: string; color: string}) {
    super(props);
    this.angle = createSignal(0) as SimpleSignal<number, this>;
    const years = () => Math.floor(this.angle() / 360);
    this.add([
      new Circle({size: 150, stroke: color, lineWidth: 4, fill: 'rgba(10,10,14,0.8)'}),
      ...Array.from({length: 12}, (_, i) =>
        new Line({
          rotation: i * 30,
          points: [
            [0, -62],
            [0, -70],
          ],
          stroke: color,
          lineWidth: 3,
        }),
      ),
      new Line({
        rotation: () => this.angle(),
        points: [
          [0, 8],
          [0, -60],
        ],
        stroke: Colors.ink,
        lineWidth: 5,
        lineCap: 'round',
      }),
      new Circle({size: 12, fill: Colors.ink}),
      new Txt({y: 105, text: label, fill: color, fontFamily: Typography.mono, fontSize: 24}),
      new Txt({
        y: 138,
        text: () => `${years()} yr`,
        fill: Colors.ink,
        fontFamily: Typography.mono,
        fontSize: 28,
      }),
    ]);
  }
}

/** Fade + slide-in helper for HUD groups. */
export function* reveal(node: Node, duration = 0.5): ThreadGenerator {
  const y = node.y();
  node.y(y + 20);
  yield* all(node.opacity(1, duration), node.y(y, duration, easeOutCubic));
}

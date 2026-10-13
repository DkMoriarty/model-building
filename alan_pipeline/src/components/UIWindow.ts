import {Node, NodeProps, Rect, Txt} from '@motion-canvas/2d';
import {
  all,
  createSignal,
  SimpleSignal,
  spring,
  Spring,
  ThreadGenerator,
  waitFor,
} from '@motion-canvas/core';
import {Colors, Springs, Stroke, Typography} from '../styles';

export interface UIWindowProps extends NodeProps {
  title?: string;
  body?: string;
  width?: number;
  height?: number;
  accent?: string;
  /** Labels for the buttons along the bottom edge. */
  buttons?: string[];
}

const TITLE_BAR = 52;

/**
 * Flat vector desktop window: title bar, close button, body text, buttons.
 * Starts collapsed (scale 0) and arrives with spring physics via `popIn`.
 */
export class UIWindow extends Node {
  public readonly title: SimpleSignal<string, this>;
  public readonly body: SimpleSignal<string, this>;
  public readonly frame: Rect;
  public readonly buttons: Rect[];

  public constructor({
    title = 'Untitled',
    body = '',
    width = 640,
    height = 300,
    accent = Colors.accent,
    buttons = ['OK'],
    ...props
  }: UIWindowProps = {}) {
    super({scale: 0, ...props});
    this.title = createSignal(title) as SimpleSignal<string, this>;
    this.body = createSignal(body) as SimpleSignal<string, this>;

    this.buttons = buttons.map(
      (label, i) =>
        new Rect({
          width: 150,
          height: 48,
          radius: 6,
          x: width / 2 - 100 - (buttons.length - 1 - i) * 170,
          y: height / 2 - 46,
          fill: i === buttons.length - 1 ? accent : Colors.surfaceRaised,
          stroke: Colors.border,
          lineWidth: Stroke.ui,
          children: [
            new Txt({
              text: label,
              fill: Colors.ink,
              fontFamily: Typography.family,
              fontSize: 22,
              fontWeight: 600,
            }),
          ],
        }),
    );

    this.frame = new Rect({
      width,
      height,
      radius: 10,
      fill: Colors.surface,
      stroke: Colors.border,
      lineWidth: Stroke.ui,
      clip: true,
      shadowColor: 'rgba(0,0,0,0.6)',
      shadowBlur: 40,
      shadowOffsetY: 16,
      children: [
        // Title bar
        new Rect({
          width,
          height: TITLE_BAR,
          y: -height / 2 + TITLE_BAR / 2,
          fill: Colors.surfaceRaised,
        }),
        new Rect({
          width,
          height: 4,
          y: -height / 2 + TITLE_BAR,
          fill: accent,
        }),
        new Txt({
          text: () => this.title(),
          x: -width / 2 + 24,
          y: -height / 2 + TITLE_BAR / 2,
          offsetX: -1,
          fill: Colors.ink,
          fontFamily: Typography.family,
          fontSize: Typography.title,
          fontWeight: 600,
        }),
        // Close button
        new Txt({
          text: '×',
          x: width / 2 - 30,
          y: -height / 2 + TITLE_BAR / 2,
          fill: Colors.inkMuted,
          fontFamily: Typography.family,
          fontSize: 36,
        }),
        // Body
        new Txt({
          text: () => this.body(),
          y: -12,
          width: width - 64,
          textWrap: true,
          textAlign: 'center',
          fill: Colors.ink,
          fontFamily: Typography.family,
          fontSize: Typography.body,
        }),
        ...this.buttons,
      ],
    });
    this.add(this.frame);
  }

  /** Arrive with spring overshoot. */
  public *popIn(physics: Spring = Springs.windowPop): ThreadGenerator {
    yield* spring(physics, this.scale.x(), 1, 0.01, value => this.scale(value));
  }

  /** Collapse out of view. */
  public *popOut(duration = 0.18): ThreadGenerator {
    yield* this.scale(0, duration);
  }

  /** Error-dialog style horizontal shake, decaying. */
  public *shake(intensity = 18, cycles = 4): ThreadGenerator {
    const x = this.x();
    for (let i = 0; i < cycles; i++) {
      const amp = intensity * (1 - i / cycles);
      yield* this.x(x + amp, 0.03);
      yield* this.x(x - amp, 0.03);
    }
    yield* this.x(x, 0.03);
  }

  /** Visually "click" one of the buttons. */
  public *press(index: number): ThreadGenerator {
    const button = this.buttons[index];
    yield* button.scale(0.9, 0.06);
    yield* all(button.scale(1, 0.1), waitFor(0.05));
  }
}

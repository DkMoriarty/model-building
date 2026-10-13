import {Line, Node, NodeProps, Txt} from '@motion-canvas/2d';
import {createSignal, SimpleSignal, Vector2} from '@motion-canvas/core';
import {Typography} from '../../styles';

export interface BladeProps extends NodeProps {
  length?: number;
  color?: string;
}

/** Ghost offsets (in units of `spread`) and their amplitudes |psi|^2 ~ gaussian. */
const BRANCHES = [-3, -2, -1, 1, 2, 3];
const amplitude = (k: number) => Math.exp(-(k * k) / 4.5);

/**
 * One half of the entangled pair. Held in a fist; the blade continues along
 * local +y, so `rotation` is the grip angle relative to the forearm.
 *
 * - `extend` 0..1 draws the blade out of the hilt.
 * - `spread` (degrees) > 0 puts the blade in superposition: ghost copies at
 *   the other possible angles, faded by their probability. 0 = measured.
 * - `spin` shows its entangled spin: 0 = unmeasured (?), 1 = up, -1 = down.
 */
export class Blade extends Node {
  public readonly extend: SimpleSignal<number, this>;
  public readonly spread: SimpleSignal<number, this>;
  public readonly spin: SimpleSignal<number, this>;
  public readonly showSpin: SimpleSignal<number, this>;
  public readonly tipNode: Node;
  public readonly bladeLength: number;

  public constructor({length = 190, color = '#ffffff', ...props}: BladeProps = {}) {
    super(props);
    this.bladeLength = length;
    this.extend = createSignal(1) as SimpleSignal<number, this>;
    this.spread = createSignal(0) as SimpleSignal<number, this>;
    this.spin = createSignal(0) as SimpleSignal<number, this>;
    this.showSpin = createSignal(0) as SimpleSignal<number, this>;

    const edge = (opacity: () => number) =>
      new Line({
        points: () => [
          [0, 14],
          [0, 14 + length * this.extend()],
        ],
        stroke: color,
        lineWidth: 7,
        lineCap: 'round',
        opacity,
        shadowColor: color,
        shadowBlur: 22,
      });

    for (const k of BRANCHES) {
      this.add(
        new Node({
          rotation: () => k * this.spread(),
          children: [edge(() => (this.spread() > 0.05 ? amplitude(k) * Math.min(1, this.spread() / 4) * 0.8 : 0))],
        }),
      );
    }
    this.add(edge(() => 1));
    this.tipNode = new Node({y: () => 14 + length * this.extend()});
    this.add(this.tipNode);
    // Cross-guard and grip.
    this.add(
      new Line({
        points: [
          [-18, 12],
          [18, 12],
        ],
        stroke: '#c9c9d4',
        lineWidth: 6,
        lineCap: 'round',
      }),
    );
    this.add(
      new Line({
        points: [
          [0, -14],
          [0, 12],
        ],
        stroke: '#8a8a96',
        lineWidth: 8,
        lineCap: 'round',
      }),
    );
    this.add(
      new Txt({
        x: 34,
        y: 6,
        rotation: () => -this.absoluteRotation() + this.rotation(),
        text: () => (this.spin() > 0 ? '↑' : this.spin() < 0 ? '↓' : '?'),
        fill: () => (this.spin() === 0 ? '#d0d0d8' : color),
        fontFamily: Typography.mono,
        fontSize: 34,
        fontWeight: 700,
        opacity: () => this.showSpin(),
      }),
    );
  }

  /** Blade tip in world (absolute) coordinates. */
  public tip(): Vector2 {
    return this.tipNode.absolutePosition();
  }
}

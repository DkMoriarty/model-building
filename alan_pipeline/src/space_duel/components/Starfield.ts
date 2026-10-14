import {Circle, Gradient, Node, NodeProps} from '@motion-canvas/2d';
import {createSignal, SimpleSignal, Vector2} from '@motion-canvas/core';
import {prng} from '../physics';

export interface StarfieldProps extends NodeProps {
  seed?: number;
  width?: number;
  height?: number;
}

/**
 * Three parallax layers of stars plus two faint nebulae. Stars are fixed
 * points: with no atmosphere there is nothing to make them twinkle.
 * `pan` shifts the layers by depth to fake camera motion.
 */
export class Starfield extends Node {
  public readonly pan: SimpleSignal<Vector2, this>;

  public constructor({seed = 7, width = 4200, height = 2600, ...props}: StarfieldProps = {}) {
    super(props);
    this.pan = createSignal(Vector2.zero) as SimpleSignal<Vector2, this>;
    const rand = prng(seed);

    const nebula = (x: number, y: number, size: number, color: string) =>
      new Circle({
        x,
        y,
        size,
        fill: new Gradient({
          type: 'radial',
          fromRadius: 0,
          toRadius: size / 2,
          stops: [
            {offset: 0, color},
            {offset: 1, color: 'rgba(0,0,0,0)'},
          ],
        }),
      });
    this.add(
      new Node({
        position: () => this.pan().scale(-0.05),
        children: [
          nebula(-700, -300, 1600, 'rgba(98,52,140,0.16)'),
          nebula(900, 350, 1400, 'rgba(30,110,120,0.12)'),
        ],
      }),
    );

    const layers = [
      {count: 260, depth: 0.15, size: [1.2, 2.2], alpha: [0.25, 0.6]},
      {count: 120, depth: 0.35, size: [2, 3.2], alpha: [0.45, 0.85]},
      {count: 45, depth: 0.7, size: [3, 4.6], alpha: [0.7, 1]},
    ];
    for (const layer of layers) {
      const node = new Node({position: () => this.pan().scale(-layer.depth)});
      for (let i = 0; i < layer.count; i++) {
        const warm = rand();
        node.add(
          new Circle({
            x: (rand() - 0.5) * width,
            y: (rand() - 0.5) * height,
            size: layer.size[0] + rand() * (layer.size[1] - layer.size[0]),
            fill: warm < 0.15 ? '#ffd9b0' : warm < 0.3 ? '#bcd4ff' : '#ffffff',
            opacity: layer.alpha[0] + rand() * (layer.alpha[1] - layer.alpha[0]),
          }),
        );
      }
      this.add(node);
    }
  }
}

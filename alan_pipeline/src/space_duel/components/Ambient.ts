import {Circle, Gradient, Line, Node, NodeProps, Rect} from '@motion-canvas/2d';
import {strokeTiers} from '../../figureSpec';
import {prng} from '../physics';

/**
 * Background life: small original props that drift through the frame. They
 * sit on the structure/detail line tiers and use muted colours, so they fill
 * the frame without competing with the fighters (style bible, section 5).
 */
const TIERS = strokeTiers();

/** The keeper's hex nut: a 0.3 H toy that starts the story. */
export function hexNut(props: NodeProps = {}): Node {
  const r = 9;
  const pts: [number, number][] = Array.from({length: 6}, (_, i) => {
    const a = (Math.PI / 3) * i;
    return [Math.cos(a) * r, Math.sin(a) * r];
  });
  return new Node({
    ...props,
    children: [
      new Line({points: pts, closed: true, fill: '#3a3a44', stroke: '#c9c9d4', lineWidth: TIERS.detail * 1.2}),
      new Circle({size: r * 0.9, stroke: '#c9c9d4', lineWidth: TIERS.detail}),
    ],
  });
}

/** A small comms satellite: boxy bus, two panel wings, one dish. */
export function satellite(props: NodeProps = {}): Node {
  const panel = (x: number) =>
    new Rect({
      x,
      width: 46,
      height: 18,
      fill: '#132344',
      stroke: '#3a5a9a',
      lineWidth: TIERS.detail,
      children: [-11, 0, 11].map(
        px =>
          new Line({
            points: [
              [px, -9],
              [px, 9],
            ],
            stroke: '#3a5a9a',
            lineWidth: TIERS.detail * 0.6,
          }),
      ),
    });
  return new Node({
    ...props,
    children: [
      new Line({
        points: [
          [-52, 0],
          [52, 0],
        ],
        stroke: '#6b6b78',
        lineWidth: TIERS.detail,
      }),
      panel(-40),
      panel(40),
      new Rect({width: 22, height: 26, radius: 3, fill: '#2a2a33', stroke: '#8a8a96', lineWidth: TIERS.detail}),
      new Circle({y: -20, size: 16, startAngle: 200, endAngle: 340, stroke: '#9a9aa8', lineWidth: TIERS.detail}),
      new Circle({x: 8, y: 9, size: 4, fill: '#ff5a5a'}),
    ],
  });
}

/** An irregular debris shard (seeded shape). */
export function shard(seed: number, size = 18, props: NodeProps = {}): Node {
  const rand = prng(seed);
  const n = 5 + Math.floor(rand() * 3);
  const pts: [number, number][] = Array.from({length: n}, (_, i) => {
    const a = (Math.PI * 2 * i) / n + rand() * 0.5;
    const r = size * (0.5 + rand() * 0.6);
    return [Math.cos(a) * r, Math.sin(a) * r];
  });
  return new Node({
    ...props,
    children: [new Line({points: pts, closed: true, fill: '#1c1c22', stroke: '#5c5c6a', lineWidth: TIERS.detail})],
  });
}

/**
 * A distant comet. In space its tail points away from the Sun, not behind
 * its motion, so the tail direction is fixed while it crosses the sky.
 */
export function comet(props: NodeProps = {}): Node {
  return new Node({
    ...props,
    children: [
      new Line({
        points: [
          [0, 0],
          [260, -70],
        ],
        lineWidth: 26,
        lineCap: 'round',
        stroke: new Gradient({
          from: [0, 0],
          to: [260, -70],
          stops: [
            {offset: 0, color: 'rgba(190,220,255,0.35)'},
            {offset: 1, color: 'rgba(190,220,255,0)'},
          ],
        }),
      }),
      new Circle({size: 9, fill: '#e8f2ff', shadowColor: 'rgba(190,220,255,0.6)', shadowBlur: 14}),
    ],
  });
}

/**
 * Foreground dust: sparse specks closer than the action, drifting slowly.
 * They move faster than the stars under camera motion (parallax), which sells
 * depth without adding clutter.
 */
export function dustField(seed = 31, count = 40): {node: Node; specks: Circle[]} {
  const rand = prng(seed);
  const node = new Node({});
  const specks: Circle[] = [];
  for (let i = 0; i < count; i++) {
    const c = new Circle({
      x: (rand() - 0.5) * 2400,
      y: (rand() - 0.5) * 1400,
      size: 1.5 + rand() * 2.5,
      fill: '#cfd6e6',
      opacity: 0.15 + rand() * 0.3,
    });
    specks.push(c);
    node.add(c);
  }
  return {node, specks};
}

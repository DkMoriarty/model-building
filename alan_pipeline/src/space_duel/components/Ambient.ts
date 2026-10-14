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

/**
 * A comms satellite (original design): gold-foil hexagonal bus, two
 * three-panel solar wings on hinged booms, a high-gain dish with a tripod
 * feed, a star tracker, a whip antenna, thrusters and a blinking beacon.
 */
export function satellite(props: NodeProps = {}, time: () => number = () => 0): Node {
  const d = TIERS.detail;
  const cellGrid = (w: number, h: number) => {
    const lines: Line[] = [];
    for (let i = 1; i < 4; i++) {
      lines.push(new Line({points: [[-w / 2 + (w * i) / 4, -h / 2], [-w / 2 + (w * i) / 4, h / 2]], stroke: '#2b4a86', lineWidth: d * 0.6}));
    }
    lines.push(new Line({points: [[-w / 2, 0], [w / 2, 0]], stroke: '#2b4a86', lineWidth: d * 0.6}));
    return lines;
  };
  const wing = (dir: number) =>
    new Node({
      children: [
        // boom + hinge yoke
        new Line({points: [[dir * 14, 0], [dir * 30, 0]], stroke: '#8a8a96', lineWidth: d * 1.2}),
        new Circle({x: dir * 30, size: 6, fill: '#8a8a96'}),
        ...[0, 1, 2].map(
          i =>
            new Rect({
              x: dir * (46 + i * 30),
              width: 28,
              height: 22,
              fill: '#122244',
              stroke: '#4a6db0',
              lineWidth: d,
              children: cellGrid(28, 22),
            }),
        ),
      ],
    });
  const hexPts: [number, number][] = Array.from({length: 6}, (_, i) => {
    const a = (Math.PI / 3) * i + Math.PI / 6;
    return [Math.cos(a) * 15, Math.sin(a) * 15];
  });
  return new Node({
    ...props,
    children: [
      wing(-1),
      wing(1),
      // Gold multi-layer insulation over a hexagonal bus, with creases.
      new Line({
        points: hexPts,
        closed: true,
        fill: new Gradient({
          from: [-15, -15],
          to: [15, 15],
          stops: [
            {offset: 0, color: '#d8b25a'},
            {offset: 0.5, color: '#a9822e'},
            {offset: 1, color: '#6d521a'},
          ],
        }),
        stroke: '#e8cf8a',
        lineWidth: d,
      }),
      new Line({points: [[-8, -10], [4, 2], [10, -6]], stroke: 'rgba(255,240,200,0.45)', lineWidth: d * 0.6}),
      new Line({points: [[-10, 6], [2, 10]], stroke: 'rgba(80,60,20,0.6)', lineWidth: d * 0.6}),
      // High-gain dish with tripod feed.
      new Circle({y: -24, size: [30, 12], fill: '#d9d9e0', stroke: '#9a9aa8', lineWidth: d}),
      new Line({points: [[-10, -26], [0, -36], [10, -26]], stroke: '#9a9aa8', lineWidth: d * 0.7}),
      new Circle({y: -36, size: 4, fill: '#c9c9d4'}),
      new Line({points: [[0, -15], [0, -20]], stroke: '#8a8a96', lineWidth: d}),
      // Star tracker and whip antenna.
      new Rect({x: 10, y: 15, width: 6, height: 9, radius: 2, fill: '#2a2a33', stroke: '#8a8a96', lineWidth: d * 0.7}),
      new Line({points: [[-9, 13], [-16, 30]], stroke: '#9a9aa8', lineWidth: d * 0.6}),
      // Thruster nozzles at the corners.
      ...[[-13, -8], [13, -8], [-13, 8], [13, 8]].map(([x, y]) => new Circle({x, y, size: 3.5, fill: '#5c5c6a'})),
      // Beacon: blinks once a second.
      new Circle({x: -4, y: 15, size: 4, fill: '#ff5a5a', opacity: () => (Math.floor(time()) % 2 === 0 ? 1 : 0.2)}),
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

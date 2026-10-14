import {Circle, Gradient, Line, Node, NodeProps, Rect} from '@motion-canvas/2d';
import {propStroke, strokeTiers} from '../../figureSpec';
import {Colors} from '../../styles';

const TIERS = strokeTiers();
/** Typical framing scale of the station. */
const STATION_SCALE = 0.6;
const structure = propStroke(TIERS.structure, STATION_SCALE);
const detail = propStroke(TIERS.detail, STATION_SCALE);

/**
 * Earth's limb: a huge sphere mostly off-frame, with a thin atmosphere glow
 * and slow cloud bands (Earth turns once a day; the bands creep).
 */
export function earth(props: NodeProps = {}, time: () => number = () => 0): Node {
  const r = 1400;
  const clouds = new Node({
    rotation: () => time() * 0.4,
    // Two short, faint weather arcs: enough to show the planet turning,
    // never enough to read as rings.
    children: [
      [0.9, -128, -108, 9],
      [0.95, -96, -82, 6],
    ].map(
      ([f, a0, a1, w]) =>
        new Circle({
          size: r * 2 * f,
          startAngle: a0,
          endAngle: a1,
          stroke: 'rgba(230,240,255,0.11)',
          lineWidth: w,
          lineCap: 'round',
        }),
    ),
  });
  return new Node({
    ...props,
    children: [
      new Circle({
        size: r * 2 + 60,
        fill: new Gradient({
          type: 'radial',
          fromRadius: r - 10,
          toRadius: r + 30,
          stops: [
            {offset: 0, color: 'rgba(110,180,255,0.55)'},
            {offset: 1, color: 'rgba(110,180,255,0)'},
          ],
        }),
      }),
      new Circle({
        size: r * 2,
        fill: new Gradient({
          type: 'radial',
          from: [-r * 0.3, -r * 0.5],
          fromRadius: 0,
          to: [0, 0],
          toRadius: r,
          stops: [
            {offset: 0, color: '#3d7bd9'},
            {offset: 0.7, color: '#1d3f7a'},
            {offset: 1, color: '#0b1a33'},
          ],
        }),
      }),
      clouds,
    ],
  });
}

export function moon(props: NodeProps = {}): Node {
  return new Node({
    ...props,
    children: [
      new Circle({
        size: 170,
        fill: new Gradient({
          type: 'radial',
          from: [-30, -30],
          fromRadius: 0,
          to: [0, 0],
          toRadius: 85,
          stops: [
            {offset: 0, color: '#d9d9d9'},
            {offset: 1, color: '#5d5d66'},
          ],
        }),
      }),
      new Circle({x: 20, y: 10, size: 26, fill: 'rgba(0,0,0,0.15)'}),
      new Circle({x: -25, y: 30, size: 16, fill: 'rgba(0,0,0,0.12)'}),
      new Circle({x: -10, y: -35, size: 12, fill: 'rgba(0,0,0,0.1)'}),
    ],
  });
}

/**
 * The relay station: hub, truss, two solar wings and a dish. Navigation
 * lights blink on the music's beat (2 per second at 120 bpm); the dish
 * sweeps slowly.
 */
export function station(props: NodeProps = {}, time: () => number = () => 0): Node {
  const blink = (phase: number) => () => (Math.floor(time() * 2 + phase) % 2 === 0 ? 1 : 0.15);
  const panel = (x: number) =>
    new Rect({
      x,
      width: 230,
      height: 74,
      fill: '#13254a',
      stroke: '#3a5a9a',
      lineWidth: detail,
      children: [-75, -25, 25, 75].map(
        px =>
          new Line({
            points: [
              [px, -37],
              [px, 37],
            ],
            stroke: '#3a5a9a',
            lineWidth: detail * 0.7,
          }),
      ),
    });
  return new Node({
    ...props,
    children: [
      new Line({
        points: [
          [-400, 0],
          [400, 0],
        ],
        stroke: '#5c5c6a',
        lineWidth: structure,
      }),
      panel(-290),
      panel(290),
      new Rect({
        width: 150,
        height: 92,
        radius: 18,
        fill: '#2a2a33',
        stroke: '#6b6b78',
        lineWidth: structure,
        children: [
          new Rect({width: 60, height: 14, radius: 7, y: -16, fill: 'rgba(120,200,255,0.5)'}),
          new Circle({x: 50, y: 26, size: 10, fill: Colors.accent, opacity: blink(0)}),
        ],
      }),
      new Line({
        points: [
          [0, -46],
          [0, -90],
        ],
        stroke: '#6b6b78',
        lineWidth: structure,
      }),
      // Wing-tip nav lights: red port, green starboard, alternating.
      new Circle({x: -405, size: 10, fill: '#ff4d4d', opacity: blink(0)}),
      new Circle({x: 405, size: 10, fill: '#4dff88', opacity: blink(1)}),
      new Circle({
        y: -118,
        size: 80,
        rotation: () => Math.sin(time() * 0.35) * 25,
        startAngle: 200,
        endAngle: 340,
        stroke: '#9a9aa8',
        lineWidth: structure,
      }),
    ],
  });
}

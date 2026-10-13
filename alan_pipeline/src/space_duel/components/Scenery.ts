import {Circle, Gradient, Line, Node, NodeProps, Rect} from '@motion-canvas/2d';
import {Colors} from '../../styles';

/** Earth's limb: a huge sphere mostly off-frame, with a thin atmosphere glow. */
export function earth(props: NodeProps = {}): Node {
  const r = 1400;
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

/** The relay station: hub, truss, two solar wings and a dish. */
export function station(props: NodeProps = {}): Node {
  const panel = (x: number) =>
    new Rect({
      x,
      width: 230,
      height: 74,
      fill: '#13254a',
      stroke: '#3a5a9a',
      lineWidth: 3,
      children: [-75, -25, 25, 75].map(
        px =>
          new Line({
            points: [
              [px, -37],
              [px, 37],
            ],
            stroke: '#3a5a9a',
            lineWidth: 2,
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
        lineWidth: 8,
      }),
      panel(-290),
      panel(290),
      new Rect({
        width: 150,
        height: 92,
        radius: 18,
        fill: '#2a2a33',
        stroke: '#6b6b78',
        lineWidth: 4,
        children: [
          new Rect({width: 60, height: 14, radius: 7, y: -16, fill: 'rgba(120,200,255,0.5)'}),
          new Circle({x: 50, y: 26, size: 10, fill: Colors.accent}),
        ],
      }),
      new Line({
        points: [
          [0, -46],
          [0, -90],
        ],
        stroke: '#6b6b78',
        lineWidth: 5,
      }),
      new Circle({
        y: -118,
        size: 80,
        startAngle: 200,
        endAngle: 340,
        stroke: '#9a9aa8',
        lineWidth: 6,
      }),
    ],
  });
}

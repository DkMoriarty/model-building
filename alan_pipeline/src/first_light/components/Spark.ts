import {Circle, Line, Node} from '@motion-canvas/2d';
import {createSignal, SimpleSignal} from '@motion-canvas/core';
import {StickFigure, StickFigureProps} from '../../components/StickFigure';
import {BIPED, proportionsOf, strokeOf} from '../../figureSpec';

export const SPARK_COLOR = '#2ec4b6';

/** Spark: our original tinkerer, a BIPED with a goggles band across the head. */
export interface Spark {
  body: StickFigure;
  /** 0 = goggles pushed up on the forehead, 1 = pulled down over the eyes. */
  goggles: SimpleSignal<number, void>;
}

export function createSpark(props: StickFigureProps = {}): Spark {
  const body = new StickFigure({color: SPARK_COLOR, proportions: proportionsOf(BIPED), ...props});
  const H = BIPED.H;
  const stroke = strokeOf(BIPED);
  const goggles = createSignal(0);
  // Lenses sit on the front of the head (the rig faces +x), so they also show
  // which way Spark is looking.
  const y = () => -H * 0.3 + goggles() * H * 0.3;
  const band = new Line({
    points: () => [
      [-H * 0.48, y() + H * 0.04],
      [H * 0.05, y()],
    ],
    stroke: '#1d4f4a',
    lineWidth: stroke * 0.55,
    lineCap: 'round',
  });
  const lens = (x: number) =>
    new Node({
      children: [
        new Circle({
          x,
          y,
          size: H * 0.34,
          fill: () => (goggles() > 0.5 ? '#0f2624' : '#16302d'),
          stroke: '#9ff0e6',
          lineWidth: stroke * 0.4,
        }),
        new Circle({x: () => x - H * 0.05, y: () => y() - H * 0.05, size: H * 0.07, fill: 'rgba(255,255,255,0.7)'}),
      ],
    });
  body.bones.head.add([band, lens(H * 0.12), lens(H * 0.4)]);
  return {body, goggles};
}

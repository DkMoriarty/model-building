import {Circle, Line, Rect} from '@motion-canvas/2d';
import {StickFigure, StickFigureProps} from '../../components/StickFigure';
import {BIPED, LONG_BIPED, proportionsOf, strokeOf} from '../../figureSpec';
import {Colors} from '../../styles';
import {Blade} from './Blade';

export const ALIEN_COLOR = '#3ddc97';
export const KEEPER_BLADE = '#ff8a8a';
export const ALIEN_BLADE = '#9dfcd6';

/** Masses used for momentum: the alien is heavier, so it recoils less. */
export const MASS = {keeper: 1, alien: 1.5};

/** Shared head unit and weights (docs/STYLE_BIBLE.md, section 2). */
const H = BIPED.H;
const STROKE = strokeOf(BIPED);
/** Blades are props: a touch lighter than limbs so the body stays dominant. */
const BLADE_STROKE = STROKE * 0.85;

export interface Fighter {
  body: StickFigure;
  blade: Blade;
}

/**
 * The keeper (original design): BIPED proportions, a pressure-helmet ring
 * 0.45 H wider than the head, and a thruster pack on the back.
 */
export function createKeeper(props: StickFigureProps = {}): Fighter {
  const body = new StickFigure({color: Colors.accent, proportions: proportionsOf(BIPED), ...props});
  body.bones.head.add(
    new Circle({
      size: H * 1.45,
      stroke: 'rgba(200,230,255,0.5)',
      lineWidth: STROKE * 0.45,
      fill: 'rgba(170,210,255,0.06)',
      children: [new Circle({x: -H * 0.24, y: -H * 0.27, size: [H * 0.22, H * 0.12], rotation: -35, fill: 'rgba(255,255,255,0.45)'})],
    }),
  );
  const torso = body.proportions.torso;
  body.bones.torso.add(
    new Rect({
      x: -H * 0.32,
      y: -torso * 0.6,
      width: H * 0.36,
      height: torso * 0.5,
      radius: H * 0.1,
      fill: '#22222a',
      stroke: Colors.accent,
      lineWidth: STROKE * 0.45,
    }),
  );
  const blade = new Blade({color: KEEPER_BLADE, length: H * 3.2, width: BLADE_STROKE, rotation: -70});
  blade.extend(0);
  body.bones.rightFist.add(blade);
  return {body, blade};
}

/**
 * The traveller (original design): LONG_BIPED proportions, a tall elliptical
 * head (0.85 H x 1.3 H) with one large eye, and two antennae.
 */
export function createAlien(props: StickFigureProps = {}): Fighter {
  const body = new StickFigure({color: ALIEN_COLOR, proportions: proportionsOf(LONG_BIPED), ...props});
  const head = body.bones.head;
  head.size([H * 0.85 - STROKE, H * 1.3 - STROKE]);
  head.y(-(body.proportions.neck + H * 0.65));
  const antenna = (x0: number, x1: number, y1: number) => [
    new Line({
      points: [
        [x0, -H * 0.62],
        [x1, y1],
      ],
      stroke: ALIEN_COLOR,
      lineWidth: STROKE * 0.6,
      lineCap: 'round',
    }),
    new Circle({x: x1, y: y1, size: H * 0.2, fill: ALIEN_COLOR}),
  ];
  head.add([
    new Circle({x: H * 0.12, y: -H * 0.06, size: [H * 0.3, H * 0.42], rotation: 15, fill: '#0b2a1d'}),
    new Circle({x: H * 0.18, y: -H * 0.14, size: H * 0.1, fill: '#ffffff'}),
    ...antenna(-H * 0.1, -H * 0.38, -H * 1.1),
    ...antenna(H * 0.12, H * 0.28, -H * 1.18),
  ]);
  const blade = new Blade({color: ALIEN_BLADE, length: H * 3.6, width: BLADE_STROKE, rotation: -70});
  blade.extend(0);
  body.bones.rightFist.add(blade);
  return {body, blade};
}

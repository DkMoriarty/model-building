import {Circle, Line, Rect} from '@motion-canvas/2d';
import {StickFigure, StickFigureProps} from '../../components/StickFigure';
import {Colors} from '../../styles';
import {Blade} from './Blade';

export const ALIEN_COLOR = '#3ddc97';
export const KEEPER_BLADE = '#ff8a8a';
export const ALIEN_BLADE = '#9dfcd6';

/** Masses used for momentum: the alien is heavier, so it recoils less. */
export const MASS = {keeper: 1, alien: 1.5};

export interface Fighter {
  body: StickFigure;
  blade: Blade;
}

/** The keeper: our stick figure in a pressure helmet with a thruster pack. */
export function createKeeper(props: StickFigureProps = {}): Fighter {
  const body = new StickFigure({color: Colors.accent, ...props});
  const r = body.proportions.headRadius;
  body.bones.head.add(
    new Circle({
      size: r * 2 + 30,
      stroke: 'rgba(200,230,255,0.55)',
      lineWidth: 4,
      fill: 'rgba(170,210,255,0.08)',
      children: [new Circle({x: -12, y: -14, size: [14, 8], rotation: -35, fill: 'rgba(255,255,255,0.5)'})],
    }),
  );
  body.bones.torso.add(
    new Rect({
      x: -20,
      y: -body.proportions.torso * 0.62,
      width: 24,
      height: 66,
      radius: 6,
      fill: '#2a2a33',
      stroke: Colors.accent,
      lineWidth: 3,
    }),
  );
  const blade = new Blade({color: KEEPER_BLADE, rotation: -70});
  blade.extend(0);
  body.bones.rightFist.add(blade);
  return {body, blade};
}

/** The traveller: long limbs, tall head, big eyes, no helmet (it breathes nothing). */
export function createAlien(props: StickFigureProps = {}): Fighter {
  const body = new StickFigure({
    color: ALIEN_COLOR,
    proportions: {headRadius: 30, neck: 22, torso: 150, upperArm: 82, forearm: 82, thigh: 88, shin: 96},
    ...props,
  });
  const head = body.bones.head;
  const r = body.proportions.headRadius;
  head.size([r * 1.7, r * 2.6]);
  head.y(-(body.proportions.neck + r * 1.3));
  head.add([
    new Circle({x: 10, y: -4, size: [18, 26], rotation: 15, fill: '#05140e'}),
    new Circle({x: 14, y: -9, size: 6, fill: '#ffffff'}),
    new Line({
      points: [
        [-6, -r * 1.25],
        [-22, -r * 2.1],
      ],
      stroke: ALIEN_COLOR,
      lineWidth: 5,
      lineCap: 'round',
    }),
    new Circle({x: -22, y: -r * 2.1, size: 12, fill: ALIEN_COLOR}),
    new Line({
      points: [
        [8, -r * 1.25],
        [16, -r * 2.2],
      ],
      stroke: ALIEN_COLOR,
      lineWidth: 5,
      lineCap: 'round',
    }),
    new Circle({x: 16, y: -r * 2.2, size: 12, fill: ALIEN_COLOR}),
  ]);
  const blade = new Blade({color: ALIEN_BLADE, length: 220, rotation: -70});
  blade.extend(0);
  body.bones.rightFist.add(blade);
  return {body, blade};
}

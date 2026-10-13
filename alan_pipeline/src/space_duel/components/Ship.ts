import {Circle, Line, Node, NodeProps, Txt} from '@motion-canvas/2d';
import {createSignal, SimpleSignal} from '@motion-canvas/core';
import {propStroke, strokeTiers} from '../../figureSpec';
import {Typography} from '../../styles';

const TIERS = strokeTiers();
/** The ship is framed at this scale in the close shots. */
const SHIP_SCALE = 0.62;
import {gamma, observedWavelength, wavelengthColor} from '../physics';

export interface ShipProps extends NodeProps {
  /** Rest length in px. */
  length?: number;
}

/** The infrared beacon: invisible at rest, violet when approaching at 0.8c. */
export const BEACON_NM = 1300;
/** Green hull lights: reddening and vanishing as the ship recedes. */
export const HULL_NM = 520;

/**
 * The alien ship, drawn as an observer at rest would measure it:
 * - Lorentz contraction along the motion: scale.x = 1 / gamma(beta)
 * - Relativistic Doppler on its lights: wavelength / sqrt((1+b)/(1-b)) when
 *   approaching (`beta` > 0), times it when receding (`beta` < 0).
 */
export class Ship extends Node {
  /** Signed v/c along the line of sight: + approaching the keeper, - receding. */
  public readonly beta: SimpleSignal<number, this>;
  public readonly flame: SimpleSignal<number, this>;
  public readonly showLabels: SimpleSignal<number, this>;

  public constructor({length = 520, ...props}: ShipProps = {}) {
    super(props);
    this.beta = createSignal(0) as SimpleSignal<number, this>;
    this.flame = createSignal(0) as SimpleSignal<number, this>;
    this.showLabels = createSignal(0) as SimpleSignal<number, this>;
    const h = 92;
    const half = length / 2;
    const nm = (rest: number) => observedWavelength(rest, this.beta());

    const hull = new Node({
      scale: () => [1 / gamma(this.beta()), 1],
      children: [
        // Engine glow (points backwards, -x).
        new Circle({
          x: -half - 30,
          size: () => [120 * this.flame(), 46 * this.flame()],
          fill: 'rgba(255,170,80,0.85)',
          opacity: () => Math.min(1, this.flame()),
        }),
        new Line({
          closed: true,
          points: [
            [half, 0],
            [half * 0.45, -h / 2],
            [-half * 0.7, -h / 2],
            [-half, -h * 0.9],
            [-half * 0.85, 0],
            [-half, h * 0.9],
            [-half * 0.7, h / 2],
            [half * 0.45, h / 2],
          ],
          fill: '#1b2a2a',
          stroke: '#3ddc97',
          lineWidth: propStroke(TIERS.structure, SHIP_SCALE),
        }),
        new Line({
          points: [
            [half * 0.4, -10],
            [-half * 0.6, -10],
          ],
          stroke: 'rgba(61,220,151,0.35)',
          lineWidth: propStroke(TIERS.detail, SHIP_SCALE),
        }),
        // Canopy
        new Circle({x: half * 0.25, size: [90, 40], fill: 'rgba(61,220,151,0.25)', stroke: '#3ddc97', lineWidth: propStroke(TIERS.detail, SHIP_SCALE)}),
        // Hull lights (520 nm) and the IR beacon (1300 nm) at the nose.
        ...[-0.55, -0.2, 0.15].map(
          f =>
            new Circle({
              x: half * f,
              y: h / 2 - 2,
              size: 16,
              fill: () => wavelengthColor(nm(HULL_NM)),
              shadowColor: () => wavelengthColor(nm(HULL_NM)),
              shadowBlur: 12,
            }),
        ),
        new Circle({
          x: half - 12,
          size: 26,
          fill: () => wavelengthColor(nm(BEACON_NM)),
          shadowColor: () => wavelengthColor(nm(BEACON_NM)),
          shadowBlur: 20,
        }),
      ],
    });
    this.add(hull);

    // Readout: counter-rotated and counter-scaled so it stays upright and legible.
    this.add(
      new Node({
        rotation: () => -this.rotation(),
        scale: () => [1 / Math.abs(this.scale.x()), 1 / Math.abs(this.scale.y())],
        children: [
          new Txt({
            y: () => (h * Math.abs(this.scale.y())) / 1 + 40,
            opacity: () => this.showLabels(),
            text: () => {
              const b = Math.abs(this.beta());
              const fmt = (n: number) => (n >= 380 && n <= 780 ? `${n.toFixed(0)} nm` : 'invisible');
              return (
                `v = ${b.toFixed(2)}c   γ = ${gamma(b).toFixed(2)}   L = ${(1 / gamma(b)).toFixed(2)} L₀\n` +
                `beacon ${fmt(nm(BEACON_NM))}   hull lights ${fmt(nm(HULL_NM))}`
              );
            },
            textAlign: 'center',
            fill: '#9fe8c6',
            fontFamily: Typography.mono,
            fontSize: 24,
            lineHeight: 34,
          }),
        ],
      }),
    );
  }
}

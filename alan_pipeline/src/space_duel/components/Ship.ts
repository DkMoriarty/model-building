import {Circle, Line, Node, NodeProps, Rect, Txt} from '@motion-canvas/2d';
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
 * The traveller's ship (original design: layered arrowhead hull, twin
 * nacelles, swept fins), drawn as an observer at rest would measure it:
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

    const structure = propStroke(TIERS.structure, SHIP_SCALE);
    const detail = propStroke(TIERS.detail, SHIP_SCALE);
    const GREEN = '#3ddc97';
    const SEAM = 'rgba(61,220,151,0.35)';
    const line = (pts: [number, number][], stroke = SEAM, width = detail) =>
      new Line({points: pts, stroke, lineWidth: width, lineCap: 'round'});
    const hullLight = (x: number, y: number, size = 12) =>
      new Circle({
        x,
        y,
        size,
        fill: () => wavelengthColor(nm(HULL_NM)),
        shadowColor: () => wavelengthColor(nm(HULL_NM)),
        shadowBlur: 10,
      });

    // Engine plume per nacelle (points backwards, -x).
    const plume = (y: number) =>
      new Circle({
        x: -half - 34,
        y,
        size: () => [110 * this.flame(), 30 * this.flame()],
        fill: 'rgba(255,170,80,0.85)',
        opacity: () => Math.min(1, this.flame()),
        shadowColor: 'rgba(255,170,80,0.5)',
        shadowBlur: 24,
      });

    // Twin nacelles above and below the hull's tail.
    const nacelle = (y: number) =>
      new Node({
        y,
        children: [
          new Rect({x: -half * 0.62, width: half * 0.75, height: h * 0.32, radius: h * 0.16, fill: '#16201f', stroke: GREEN, lineWidth: structure}),
          // nozzle rings
          ...[0, 1, 2].map(i =>
            line(
              [
                [-half + 4 + i * 9, -h * 0.13],
                [-half + 4 + i * 9, h * 0.13],
              ],
              GREEN,
              detail,
            ),
          ),
          // intake slats
          ...[0, 1, 2, 3].map(i =>
            line([
              [-half * 0.4 + i * 12, -h * 0.07],
              [-half * 0.4 + i * 12 + 6, h * 0.07],
            ]),
          ),
        ],
      });

    // Swept fin (dorsal when sign = -1, ventral when +1).
    const fin = (sign: number) =>
      new Node({
        children: [
          new Line({
            closed: true,
            points: [
              [-half * 0.15, sign * h * 0.45],
              [-half * 0.55, sign * h * 1.05],
              [-half * 0.78, sign * h * 1.05],
              [-half * 0.6, sign * h * 0.45],
            ],
            fill: '#15201f',
            stroke: GREEN,
            lineWidth: structure,
          }),
          line([
            [-half * 0.32, sign * h * 0.6],
            [-half * 0.62, sign * h * 0.98],
          ]),
        ],
      });

    const hull = new Node({
      scale: () => [1 / gamma(this.beta()), 1],
      children: [
        plume(-h * 0.55),
        plume(h * 0.55),
        fin(-1),
        fin(1),
        nacelle(-h * 0.55),
        nacelle(h * 0.55),
        // Outer hull: a long arrowhead.
        new Line({
          closed: true,
          points: [
            [half, 0],
            [half * 0.55, -h * 0.42],
            [-half * 0.75, -h * 0.5],
            [-half * 0.95, -h * 0.3],
            [-half * 0.95, h * 0.3],
            [-half * 0.75, h * 0.5],
            [half * 0.55, h * 0.42],
          ],
          fill: '#1b2a2a',
          stroke: GREEN,
          lineWidth: structure,
        }),
        // Inner dorsal plate (a second, darker layer).
        new Line({
          closed: true,
          points: [
            [half * 0.7, 0],
            [half * 0.4, -h * 0.25],
            [-half * 0.6, -h * 0.28],
            [-half * 0.75, 0],
            [-half * 0.6, h * 0.28],
            [half * 0.4, h * 0.25],
          ],
          fill: '#152221',
          stroke: SEAM,
          lineWidth: detail,
        }),
        // Panel seams with rivets.
        ...[-0.35, 0, 0.3].map(f =>
          line([
            [half * f, -h * 0.26],
            [half * f, h * 0.26],
          ]),
        ),
        line([
          [half * 0.4, 0],
          [-half * 0.6, 0],
        ]),
        ...Array.from({length: 7}, (_, i) => new Circle({x: half * (0.3 - i * 0.13), y: -h * 0.36, size: 4, fill: SEAM})),
        ...Array.from({length: 7}, (_, i) => new Circle({x: half * (0.3 - i * 0.13), y: h * 0.36, size: 4, fill: SEAM})),
        // Vents.
        ...[0, 1, 2].map(i => new Rect({x: -half * 0.2 - i * 16, y: h * 0.14, width: 10, height: 4, radius: 2, fill: 'rgba(61,220,151,0.45)'})),
        // Cockpit: framed canopy with a reflection.
        new Circle({x: half * 0.32, size: [96, 40], fill: 'rgba(61,220,151,0.18)', stroke: GREEN, lineWidth: detail}),
        line([
          [half * 0.32, -20],
          [half * 0.32, 20],
        ]),
        new Circle({x: half * 0.36, y: -8, size: [26, 8], rotation: -12, fill: 'rgba(220,255,240,0.35)'}),
        // Sensor spine at the nose.
        line(
          [
            [half * 0.92, 0],
            [half * 1.12, 0],
          ],
          GREEN,
          detail,
        ),
        new Circle({x: half * 1.12, size: 6, fill: GREEN}),
        // Running-light strip (520 nm) and the IR beacon (1300 nm) at the nose.
        ...[-0.6, -0.38, -0.16, 0.06, 0.28].map(f => hullLight(half * f, h * 0.44, 10)),
        hullLight(-half * 0.62, -h * 0.55 - h * 0.16, 9),
        hullLight(-half * 0.62, h * 0.55 + h * 0.16, 9),
        new Circle({
          x: half - 14,
          size: 24,
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

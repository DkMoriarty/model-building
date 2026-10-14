import {Node, NodeProps, Rect} from '@motion-canvas/2d';
import {Vector2} from '@motion-canvas/core';
import {Bulb, Dial, Eye, TIER, Wire} from './Circuit';

/**
 * The learning board (original design): nine light-eyes in a 3 x 3 grid, a
 * dial on each eye's wire (its weight), and one big bulb that fills like a
 * glass and lights when the level passes the halfway mark (the threshold).
 * Local coordinates; the board's origin sits on the floor line.
 */
export class Board extends Node {
  public readonly eyes: Eye[] = [];
  public readonly dials: Dial[] = [];
  public readonly wiresIn: Wire[] = [];
  public readonly wiresOut: Wire[] = [];
  public readonly bulb: Bulb;

  public constructor({time, ...props}: NodeProps & {time: () => number}) {
    super(props);
    const wires = new Node({});
    const parts = new Node({});
    this.add([wires, parts]);
    // Pedestal for the bulb.
    parts.add(new Rect({x: 100, y: -32, width: 40, height: 64, fill: '#1b1b22', stroke: '#6b6b78', lineWidth: TIER.detail}));
    this.bulb = new Bulb({x: 100, y: -100, radius: 55});
    for (let i = 0; i < 9; i++) {
      const r = Math.floor(i / 3);
      const c = i % 3;
      const y = -230 + r * 60;
      const eye = new Eye({x: -360 + c * 60, y});
      const dial = new Dial({x: -140 + c * 45, y, size: 30});
      const ex = -360 + c * 60 + 20;
      const dx = -140 + c * 45 - 15;
      const win = new Wire({points: () => [new Vector2(ex, y), new Vector2(dx, y)], spacing: 22, pool: 16, time});
      const bus = -26 - i * 3;
      const wout = new Wire({
        points: () => [new Vector2(-140 + c * 45, y + 15), new Vector2(-140 + c * 45, bus), new Vector2(100 - 6 + (i % 3) * 6, bus), new Vector2(100 - 6 + (i % 3) * 6, -64)],
        spacing: 24,
        pool: 30,
        time,
      });
      win.beads(0);
      wout.beads(0);
      wires.add([win, wout]);
      parts.add([eye, dial]);
      this.eyes.push(eye);
      this.dials.push(dial);
      this.wiresIn.push(win);
      this.wiresOut.push(wout);
    }
    parts.add(this.bulb);
    this.bulb.showLevel(1);
  }

  /** All the board's wires, for registering with the stage clock. */
  public get wires(): Wire[] {
    return [...this.wiresIn, ...this.wiresOut];
  }
}

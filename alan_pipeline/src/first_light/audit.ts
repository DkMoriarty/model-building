import {Node} from '@motion-canvas/2d';
import {ThreadGenerator, useLogger, useTime, Vector2, waitFor} from '@motion-canvas/core';
import {Stage} from './stage';

/**
 * Subject framing audit for FIRST LIGHT (style bible section 9.1): every
 * 0.1 s, Spark's head, chest, hands and feet must sit inside the 96 px safe
 * margin. Violations are reported once per interval, so `render --strict`
 * fails on them. Deliberate exits from the frame are declared in `exempt`,
 * each with a reason.
 */
const HALF_W = 960;
const HALF_H = 540;
const SAFE = 96;

export function* frameAuditor(s: Stage, until: number, exempt: [number, number, string][] = [], cropFeetAtZoom = Infinity): ThreadGenerator {
  const b = s.spark.body.bones;
  const points: [string, Node][] = [
    ['head', b.head],
    ['chest', b.chest],
    ['left hand', b.leftFist],
    ['right hand', b.rightFist],
    ['left foot', b.leftFoot],
    ['right foot', b.rightFoot],
  ];
  const open = new Map<string, number>();
  const report: string[] = [];
  while (useTime() < until - 1e-6) {
    const t = useTime();
    const excused = exempt.some(([a, b]) => t >= a && t <= b);
    const visible = !excused && s.spark.body.opacity() > 0.1 && s.blackout.opacity() < 0.95;
    for (const [part, node] of points) {
      // A medium close-up crops at the knees by design.
      if (part.endsWith('foot') && s.zoom() >= cropFeetAtZoom) continue;
      const v = node.absolutePosition().transformAsPoint(s.view.worldToLocal());
      const out = visible && (Math.abs(v.x) > HALF_W - SAFE || Math.abs(v.y) > HALF_H - SAFE);
      if (out && !open.has(part)) open.set(part, t);
      if (!out && open.has(part)) {
        const from = open.get(part)!;
        if (t - from >= 0.15) report.push(`frame: F3s Spark ${part} outside the safe margin ${from.toFixed(1)}-${t.toFixed(1)}s`);
        open.delete(part);
      }
    }
    yield* waitFor(0.1);
  }
  for (const r of report) useLogger().warn(r);
}

export {Vector2};

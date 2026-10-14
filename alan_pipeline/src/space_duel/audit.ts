import {Node} from '@motion-canvas/2d';
import {ThreadGenerator, useLogger, useTime, Vector2, waitFor} from '@motion-canvas/core';
import {at} from './cues';
import {Stage} from './stage';

/**
 * Frame accounting, measured from the scene graph (exact, not estimated from
 * pixels). Every 0.1 s it reads where each visible subject actually is on
 * screen and checks the style bible's subject rules (section 9):
 *
 *   F3s  subject points stay inside the 96 px safe margin
 *   F1s  the subjects' centroid stays inside the lead-room band
 *        (|x| <= 25% of width, |y| <= 20% of height from centre)
 *
 * Violations are reported once per continuous interval as warnings, so the
 * probe lists them and `render --strict` fails on them. Deliberate entrances
 * and exits are declared in EXEMPT with a reason: every exception is written
 * down, none is silent.
 */
const HALF_W = 960;
const HALF_H = 540;
const SAFE = 96;

/** [from cue/seconds, to, reason]: windows where subjects may leave the safe area. */
function exemptions(): [number, number, string][] {
  return [
    [at('alienOut'), at('alienOut') + 2.3, 'traveller steps out of the ship'],
    [at('tunnel'), at('recover') + 1.0, 'keeper tumbles after the tunnelled hit'],
    [at('depart'), 200, 'departure: traveller leaves, camera follows the blade'],
  ];
}

interface Interval {
  from: number;
  to: number;
  what: string;
}

export function* frameAuditor(s: Stage, until: number): ThreadGenerator {
  const toView = (p: Vector2) => p.transformAsPoint(s.view.worldToLocal());
  const exempt = exemptions();
  const open = new Map<string, Interval>();
  const closed: Interval[] = [];

  const visible = (n: Node) => {
    let o = 1;
    for (let p: Node | null = n; p; p = p.parent()) o *= p.opacity();
    return o > 0.1;
  };

  const record = (key: string, active: boolean, t: number, what: string) => {
    const cur = open.get(key);
    if (active && !cur) open.set(key, {from: t, to: t, what});
    else if (active && cur) cur.to = t;
    else if (!active && cur) {
      closed.push(cur);
      open.delete(key);
    }
  };

  while (useTime() < until - 1e-6) {
    const t = useTime();
    const isExempt = exempt.some(([a, b]) => t >= a && t <= b);
    const subjects: Vector2[] = [];
    for (const [name, f] of [
      ['keeper', s.keeper],
      ['traveller', s.alien],
    ] as const) {
      if (!visible(f.body)) continue;
      const b = f.body.bones;
      const points: [string, Node][] = [
        ['head', b.head],
        ['chest', b.chest],
        ['left hand', b.leftFist],
        ['right hand', b.rightFist],
        ['left foot', b.leftFoot],
        ['right foot', b.rightFoot],
      ];
      for (const [part, node] of points) {
        const v = toView(node.absolutePosition());
        subjects.push(v);
        const out = Math.abs(v.x) > HALF_W - SAFE || Math.abs(v.y) > HALF_H - SAFE;
        record(`F3s ${name} ${part}`, out && !isExempt, t, `F3s ${name} ${part} outside the safe margin`);
      }
      // The blade tip counts while the blade is in hand and drawn.
      if (f.blade.parent() !== s.fx && visible(f.blade) && f.blade.extend() > 0.5) {
        const v = toView(f.blade.tip());
        const out = Math.abs(v.x) > HALF_W - SAFE || Math.abs(v.y) > HALF_H - SAFE;
        record(`F3s ${name} blade`, out && !isExempt, t, `F3s ${name} blade tip outside the safe margin`);
      }
    }
    if (subjects.length) {
      const c = subjects.reduce((a, v) => a.add(v), Vector2.zero).scale(1 / subjects.length);
      const off = Math.abs(c.x) > HALF_W * 2 * 0.25 || Math.abs(c.y) > HALF_H * 2 * 0.2;
      record('F1s', off && !isExempt, t, `F1s subject centroid outside the lead-room band (${c.x.toFixed(0)}, ${c.y.toFixed(0)})`);
    }
    yield* waitFor(0.1);
  }
  for (const iv of open.values()) closed.push(iv);

  // Ignore single-sample blips (< 0.15 s): sub-perceptual.
  const real = closed.filter(iv => iv.to - iv.from >= 0.15).sort((a, b) => a.from - b.from);
  for (const iv of real) {
    useLogger().warn(`frame: ${iv.what} ${iv.from.toFixed(1)}-${iv.to.toFixed(1)}s`);
  }
}

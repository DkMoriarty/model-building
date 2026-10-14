import {Circle, Line, Node} from '@motion-canvas/2d';
import {all, easeOutCubic, linear, ThreadGenerator, Vector2, waitFor} from '@motion-canvas/core';
import {prng} from '../../space_duel/physics';
import {withAlpha} from '../../figureSpec';

const rand = prng(2026);
/** Gravity in px/s^2 at world scale (a room, unlike the duel's vacuum). */
export const G = 2400;

/** A jagged lightning bolt between two world points, flickering for `life` s. */
export function* bolt(parent: Node, a: Vector2, b: Vector2, color: string, life = 0.25, width = 5): ThreadGenerator {
  const jag = () => {
    const pts: Vector2[] = [a];
    const n = 7;
    const normal = b.sub(a).perpendicular.normalized;
    for (let i = 1; i < n; i++) {
      pts.push(Vector2.lerp(a, b, i / n).add(normal.scale((rand() - 0.5) * 34)));
    }
    pts.push(b);
    return pts;
  };
  const line = new Line({points: jag(), stroke: '#ffffff', lineWidth: width, lineJoin: 'round', shadowColor: withAlpha(color, 0.9), shadowBlur: 18});
  parent.add(line);
  const frames = Math.max(2, Math.round(life * 60 / 3));
  for (let i = 0; i < frames; i++) {
    line.points(jag());
    line.stroke(i % 2 ? color : '#ffffff');
    yield* waitFor(3 / 60);
  }
  line.remove();
}

/** A burst of short sparks that fly out and fall. */
export function* sparkBurst(parent: Node, at: Vector2, color: string, scale = 1, count = 10): ThreadGenerator {
  const tasks: ThreadGenerator[] = [];
  const flash = new Circle({position: at, size: 24 * scale, fill: '#ffffff'});
  parent.add(flash);
  for (let i = 0; i < count; i++) {
    const ang = rand() * Math.PI * 2;
    const v = new Vector2(Math.cos(ang), Math.sin(ang) - 0.4).scale((220 + rand() * 260) * scale);
    const dot = new Line({points: [at, at], stroke: i % 3 ? color : '#ffffff', lineWidth: 3, lineCap: 'round'});
    parent.add(dot);
    tasks.push(
      (function* () {
        const life = 0.35 + rand() * 0.2;
        for (let t = 0; t < life; t += 1 / 60) {
          const p = at.add(v.scale(t)).add(new Vector2(0, 0.5 * G * 0.4 * t * t));
          const q = at.add(v.scale(Math.max(0, t - 0.03))).add(new Vector2(0, 0.5 * G * 0.4 * (t - 0.03) ** 2));
          dot.points([q, p]);
          dot.opacity(1 - t / life);
          yield;
        }
        dot.remove();
      })(),
    );
  }
  yield* all(flash.size(90 * scale, 0.18, easeOutCubic), flash.opacity(0, 0.18), ...tasks);
  flash.remove();
}

/** A puff of smoke rising from a point. */
export function* smoke(parent: Node, at: Vector2, count = 4): ThreadGenerator {
  const tasks: ThreadGenerator[] = [];
  for (let i = 0; i < count; i++) {
    const c = new Circle({position: at.add([(rand() - 0.5) * 16, 0]), size: 14, fill: 'rgba(170,170,180,0.55)'});
    parent.add(c);
    tasks.push(
      (function* () {
        yield* waitFor(i * 0.08);
        yield* all(c.position(c.position().add([(rand() - 0.5) * 40, -90 - rand() * 40]), 1.1, linear), c.size(46 + rand() * 20, 1.1), c.opacity(0, 1.1));
        c.remove();
      })(),
    );
  }
  yield* all(...tasks);
}

/**
 * Glass shards from a burst bulb: they fly out, fall under gravity, bounce
 * once on the floor at `floorY` (losing 60% of their speed), then lie there
 * and fade.
 */
export function* shards(parent: Node, at: Vector2, floorY: number, color: string, count = 9, lie = 1.2): ThreadGenerator {
  const tasks: ThreadGenerator[] = [];
  for (let i = 0; i < count; i++) {
    const ang = -Math.PI * (0.1 + 0.8 * rand());
    let v = new Vector2(Math.cos(ang) * (120 + rand() * 260), Math.sin(ang) * (120 + rand() * 300));
    const shard = new Line({
      points: [
        [-5, -3],
        [6, -1],
        [-1, 5],
      ],
      closed: true,
      fill: withAlpha(color, 0.5),
      stroke: '#e8e8f0',
      lineWidth: 1.5,
      position: at,
    });
    parent.add(shard);
    tasks.push(
      (function* () {
        let p = at;
        let bounced = false;
        const spin = (rand() - 0.5) * 900;
        for (let t = 0; t < 2.2; t += 1 / 60) {
          v = v.add(new Vector2(0, G / 60));
          p = p.add(v.scale(1 / 60));
          if (p.y > floorY) {
            p = new Vector2(p.x, floorY);
            if (bounced) break;
            v = new Vector2(v.x * 0.4, -v.y * 0.4);
            bounced = true;
          }
          shard.position(p);
          shard.rotation(shard.rotation() + spin / 60);
          yield;
        }
        shard.position(new Vector2(p.x, floorY));
        yield* waitFor(lie);
        yield* shard.opacity(0, 0.6);
        shard.remove();
      })(),
    );
  }
  yield* all(...tasks);
}

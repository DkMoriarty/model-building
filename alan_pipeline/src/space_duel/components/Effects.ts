import {Circle, Line, Node} from '@motion-canvas/2d';
import {all, easeOutCubic, linear, ThreadGenerator, Vector2, waitFor} from '@motion-canvas/core';
import {prng} from '../physics';

const rand = prng(99);

/**
 * Blade-contact sparks: a flash plus streaks flying straight out. In vacuum
 * nothing slows them down, so they move at constant speed and only fade as
 * they cool.
 */
export function* sparks(parent: Node, at: Vector2, color: string, scale = 1): ThreadGenerator {
  // `at` is in screen (absolute) space, where blade tips are measured.
  const group = new Node({});
  parent.add(group);
  group.absolutePosition(at);
  const flash = new Circle({size: 30 * scale, fill: '#ffffff'});
  group.add(flash);
  const tasks: ThreadGenerator[] = [];
  const count = 12;
  for (let i = 0; i < count; i++) {
    const angle = (i / count) * Math.PI * 2 + rand() * 0.4;
    const dir = new Vector2(Math.cos(angle), Math.sin(angle));
    const speed = (160 + rand() * 160) * scale; // px over the 0.5 s life
    const line = new Line({
      points: [dir.scale(10), dir.scale(34)],
      stroke: i % 3 === 0 ? '#ffffff' : color,
      lineWidth: 4,
      lineCap: 'round',
    });
    group.add(line);
    tasks.push(
      all(line.points([dir.scale(10 + speed), dir.scale(34 + speed)], 0.5, linear), line.opacity(0, 0.5)),
    );
  }
  yield* all(flash.size(160 * scale, 0.22, easeOutCubic), flash.opacity(0, 0.22), ...tasks);
  group.remove();
}

/**
 * Cold-gas thruster exhaust leaving `source()` along `dir` for `duration`.
 * The gas carries momentum one way; the fighter gains it the other way.
 */
export function* exhaust(parent: Node, source: () => Vector2, dir: Vector2, duration: number): ThreadGenerator {
  const puffs = Math.max(1, Math.round(duration / 0.08));
  const tasks: ThreadGenerator[] = [];
  for (let i = 0; i < puffs; i++) {
    tasks.push(
      (function* () {
        yield* waitFor(i * 0.08);
        // `source()` is in screen (absolute) space; puffs then drift in world space.
        const p = new Circle({size: 14, fill: 'rgba(200,220,255,0.7)'});
        parent.add(p);
        p.absolutePosition(source());
        const jitter = new Vector2((rand() - 0.5) * 40, (rand() - 0.5) * 40);
        yield* all(p.position(p.position().add(dir.scale(160)).add(jitter), 0.6, linear), p.size(46, 0.6), p.opacity(0, 0.6));
        p.remove();
      })(),
    );
  }
  yield* all(...tasks);
}

/**
 * Light from a moving source: each wavefront is a circle centred where the
 * source WAS when it emitted it, growing at c. With the source at 0.8c the
 * fronts pile up ahead of it and spread out behind: the Doppler effect, drawn.
 */
export function* wavefronts(
  parent: Node,
  source: () => Vector2,
  c: number,
  every: number,
  count: number,
  life: number,
  color: string,
  spawn: (task: ThreadGenerator) => void,
): ThreadGenerator {
  for (let i = 0; i < count; i++) {
    const ring = new Circle({position: source(), size: 0, stroke: color, lineWidth: 3, opacity: 0.8});
    parent.add(ring);
    spawn(function* () {
      yield* all(ring.size(2 * c * life, life, linear), ring.opacity(0, life, linear));
      ring.remove();
    }());
    yield* waitFor(every);
  }
}

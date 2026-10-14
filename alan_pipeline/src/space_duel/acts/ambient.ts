import {all, easeInOutCubic, linear, ThreadGenerator, Vector2} from '@motion-canvas/core';
import {comet, satellite, shard} from '../components/Ambient';
import {Cue, duration, syncTo} from '../cues';
import {prng} from '../physics';
import {Stage} from '../stage';

/**
 * Background life for the whole film. Everything moves in straight lines at
 * constant speed and spin (nothing in a vacuum slows it), on long, slow paths
 * so the eye registers motion without being pulled off the action.
 */
export function* ambient(s: Stage): ThreadGenerator {
  const rand = prng(404);

  // A distant comet crawls across the sky for the entire film.
  const c = comet({position: [1250, -430], scale: 0.9, opacity: 0.85});
  s.backdrop.add(c);
  s.spawn(c.position([-1350, -250], duration, linear));

  // Debris: a few shards drifting and tumbling at constant rates.
  for (let i = 0; i < 9; i++) {
    const start = new Vector2((rand() - 0.5) * 2600, (rand() - 0.5) * 1300);
    const velocity = new Vector2((rand() - 0.5) * 18, (rand() - 0.5) * 10);
    const spin = (rand() - 0.5) * 30;
    const d = shard(500 + i, 10 + rand() * 16, {position: start, opacity: 0.7});
    s.backdrop.add(d);
    s.spawn(all(d.position(start.add(velocity.scale(duration)), duration, linear), d.rotation(spin * duration, duration, linear)));
  }

  // Satellites cross at quiet moments: standoff, two fight lulls, departure.
  // Lanes run through the open lower sky, clear of the station and the
  // fighters' silhouettes (no tangents); passing behind Earth's limb on the
  // left gives a free depth cue.
  const passes: [Cue, number, number][] = [
    ['sat1', -1, 330],
    ['sat2', 1, 360],
    ['sat3', -1, 340],
    ['sat4', 1, 350],
  ];
  for (const [cue, dir, y] of passes) {
    s.spawn(
      (function* () {
        yield* syncTo(cue);
        const sat = satellite({position: [dir * 1250, y], scale: 1.5, rotation: dir * 8, opacity: 0.9}, s.time);
        s.backdrop.add(sat);
        yield* all(sat.position([-dir * 1250, y - 50], 16, linear), sat.rotation(-dir * 14, 16, linear));
        sat.remove();
      })(),
    );
  }

  // The schematic diagram (18-48 s) wants a quiet frame: dim the backdrop.
  yield* syncTo('diagram');
  yield* all(s.backdrop.opacity(0.2, 0.8), s.dust.opacity(0.3, 0.8));
  yield* syncTo('arrive');
  yield* all(s.backdrop.opacity(1, 1.0, easeInOutCubic), s.dust.opacity(1, 1.0));
}

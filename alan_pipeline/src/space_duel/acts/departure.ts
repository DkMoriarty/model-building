import {Txt} from '@motion-canvas/2d';
import {all, easeInCubic, easeInOutCubic, easeOutCubic, ThreadGenerator, Vector2} from '@motion-canvas/core';
import {Colors, Typography} from '../../styles';
import {reveal} from '../components/Hud';
import {at, duration, syncTo} from '../cues';
import {everyFrame, Stage} from '../stage';

/** Departure-view light speed (px/s): the ship is gone within seconds. */
const C = 420;

export function* departure(s: Stage): ThreadGenerator {
  const {ship, alien} = s;

  // Wide shot: the traveller returns to its ship.
  yield* syncTo('depart');
  s.world.position(() => s.com().scale(-s.world.scale().x).add(new Vector2(-120, 140)).add(s.shake()));
  yield* all(
    s.world.scale(0.7, 2.0, easeInOutCubic),
    alien.body.opacity(0, 1.6),
    alien.body.scale([-0.3, 0.3], 1.6, easeInCubic),
    s.earth.opacity(1, 2),
    ship.rotation(0, 2.0, easeInOutCubic),
  );

  // It leaves: accelerating away (beta < 0 = receding). Length contracts,
  // and its green hull lights slide to red, then past red out of sight.
  ship.showLabels(1);
  s.spawn(everyFrame(at('drift'), dt => {
    ship.x(ship.x() - ship.beta() * C * dt);
  }));
  yield* all(ship.flame(1.2, 0.3), ship.beta(-0.8, 6, easeInCubic));
  yield* ship.flame(0, 0.6);

  // The lost blade: constant velocity, constant spin. Follow it.
  yield* syncTo('drift');
  const blade = s.freeBlade;
  ship.opacity(0);
  if (blade) {
    s.world.scale(1);
    s.world.position(() => blade.position().scale(-1).add([-160, 60]));
  }
  yield* syncTo('n17.start', -2.5);
  const note = new Txt({
    y: -420,
    text: 'NEWTON I: no force, no change in motion',
    fill: '#ffd166',
    fontFamily: Typography.mono,
    fontSize: 28,
    opacity: 0,
  });
  s.hud.add(note);
  note.moveBelow(s.blackout);
  yield* reveal(note, 0.6);

  // Fade out, title, end.
  yield* syncTo('end');
  const credit = new Txt({
    y: 210,
    text: 'every frame computed from code · no generative video',
    fill: Colors.inkMuted,
    fontFamily: Typography.family,
    fontSize: 24,
    opacity: 0,
  });
  s.hud.add(credit);
  yield* s.blackout.opacity(1, 1.2);
  s.title.moveToTop();
  credit.moveToTop();
  yield* all(reveal(s.title, 0.8), credit.opacity(1, 0.8, easeOutCubic));
  yield* syncTo(duration - 0.05);
}

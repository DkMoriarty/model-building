import {Line, Node, Txt} from '@motion-canvas/2d';
import {all, easeInOutCubic, easeInOutSine, easeOutCubic, linear, ThreadGenerator, useTime, Vector2, waitFor} from '@motion-canvas/core';
import {StickFigure} from '../../components/StickFigure';
import {Colors, Typography} from '../../styles';
import {reveal} from '../components/Hud';
import {wavefronts} from '../components/Effects';
import {station as stationIcon} from '../components/Scenery';
import {at, syncTo} from '../cues';
import {gamma} from '../physics';
import {everyFrame, Stage} from '../stage';

/** Diagram scale: light crosses 90 px per second of screen time. */
const C = 90;
/** One clock revolution = one "year" of the story, compressed to 6 s. */
const YEAR = 6;
const BETA = 0.8;

/** Gentle zero-g float: the figure drifts and turns slowly, limbs loose. */
function floatPose(fig: StickFigure): void {
  fig.setPose({
    torso: 6,
    head: -4,
    leftShoulder: -30,
    leftElbow: -40,
    rightShoulder: 25,
    rightElbow: -30,
    leftHip: -18,
    leftKnee: 30,
    rightHip: 10,
    rightKnee: 22,
  });
}

export function* arrival(s: Stage): ThreadGenerator {
  // 0 - 10.5: the void. Stars only; the camera drifts.
  yield* syncTo('n1.start', 1.5);
  s.spawn(all(s.blackout.opacity(0, 2.5), s.world.position([-60, 20], 18, linear)));

  yield* syncTo('title');
  yield* reveal(s.title, 0.8);
  yield* waitFor(1.9);
  yield* s.title.opacity(0, 0.6);

  // 10.5 - 18: the relay at Earth-Moon L2, its keeper on a tether.
  yield* syncTo('station');
  floatPose(s.keeper.body);
  s.keeper.body.position([-170, 70]);
  s.keeper.body.rotation(-8);
  s.tether.points(() => [s.station.position().add([-60, 10]), s.keeper.body.position()]);
  yield* all(
    s.earth.opacity(1, 1.2),
    s.moon.opacity(1, 1.2),
    s.station.opacity(1, 1.2),
    s.keeper.body.opacity(1, 1.2),
    s.tether.opacity(1, 1.2),
    s.label.show('EARTH–MOON L2', 'gravity of both + the orbit hold a station in step with the Moon'),
  );
  s.spawn(all(
    s.keeper.body.rotation(6, 7, easeInOutSine),
    s.keeper.body.position([-150, 50], 7, easeInOutSine),
  ));

  // 18 - 48: the approach, drawn as a space-time diagram.
  yield* syncTo('diagram');
  yield* approach(s);

  // 48 - 77: the standoff.
  yield* standoff(s);
}

function* approach(s: Stage): ThreadGenerator {
  const stationX = 560;
  const axis = new Line({
    points: [
      [-960, 0],
      [960, 0],
    ],
    stroke: 'rgba(255,255,255,0.12)',
    lineWidth: 2,
  });
  const icon = stationIcon({x: stationX, scale: 0.32});
  const iconLabel = new Txt({
    x: stationX,
    y: 70,
    text: 'keeper',
    fill: Colors.accent,
    fontFamily: Typography.mono,
    fontSize: 22,
  });
  const lightRings = new Node({});
  s.diagram.add([axis, lightRings, icon, iconLabel]);

  // The diagram is screen-aligned: park the camera.
  s.world.position(Vector2.zero);
  s.ship.position([-1500, 0]);
  s.ship.rotation(0);
  s.ship.beta(BETA);
  s.ship.showLabels(1);
  yield* all(
    s.scenery.opacity(0.12, 0.8),
    s.keeper.body.opacity(0, 0.8),
    s.diagram.opacity(1, 0.8),
    s.ship.opacity(1, 0.8),
    s.label.show('v = 0.8 c', 'eight tenths of the speed of light'),
    reveal(s.clocks, 0.8),
  );

  // One integrator moves the ship (dx = beta c dt) and runs both clocks
  // (keeper: dt; traveller: dt / gamma). Every number on screen comes from it.
  const end = at('arrive');
  s.spawn(everyFrame(end, dt => {
    const beta = s.ship.beta();
    s.ship.x(s.ship.x() + beta * C * dt);
    s.keeperClock.angle(s.keeperClock.angle() + (360 / YEAR) * dt);
    s.travelerClock.angle(s.travelerClock.angle() + ((360 / YEAR) * dt) / gamma(beta));
  }));

  // Light from the ship's nose. The first wavefront reaches the keeper at a
  // time we can compute exactly: emitted at t0 from x0, arriving after d / c.
  const nose = () => s.ship.position().add([(260 / gamma(s.ship.beta())) * 0.5 * 0.98, 0]);
  const emitted = nose();
  const imageArrives = useTime() + (stationX - emitted.x) / C;
  s.spawn(wavefronts(lightRings, nose, C, 1.2, 18, 32, 'rgba(160,140,255,0.55)', t => s.spawn(t)));
  s.spawn((function* () {
    yield* syncTo(imageArrives);
    const ping = new Txt({
      x: stationX,
      y: -80,
      text: 'IMAGE ARRIVES',
      fill: '#c3b5ff',
      fontFamily: Typography.mono,
      fontSize: 26,
      opacity: 0,
    });
    s.diagram.add(ping);
    yield* all(ping.opacity(1, 0.2), icon.scale(0.4, 0.2).to(0.32, 0.4));
  })());

  yield* syncTo('n4.start');
  yield* s.label.show('L = L₀ √(1 − v²/c²) = 0.60 L₀', 'length contraction: the ship is shorter along its motion');
  yield* syncTo('n4.start', -5.0);
  yield* s.label.show('λ = λ₀ √((1−β)/(1+β)) = λ₀ / 3', 'its 1300 nm infrared beacon arrives as 433 nm violet');
  yield* syncTo('n5.start');
  yield* s.label.show('Δτ = Δt / γ,   γ = 1.67', 'moving clocks run slow: five years here, three aboard');

  // Flip and burn: point the engine forward and decelerate to rest.
  yield* syncTo('decel', 1.0);
  yield* s.ship.rotation(180, 1.0, easeInOutCubic);
  s.spawn(all(s.ship.beta(0, at('arrive') - at('decel') - 0.5, easeOutCubic), s.ship.flame(1, 0.4)));

  yield* syncTo('n6.start');
  yield* s.label.show('t_ship − t_light = d/v − d/c', 'at 0.8c the ship nearly overtakes its own light');

  yield* syncTo('arrive', 0.6);
  yield* all(s.ship.flame(0, 0.5), s.label.hide());
}

function* standoff(s: Stage): ThreadGenerator {
  const {keeper, alien} = s;
  // Cut to the close view: the ship parked beside the relay.
  yield* syncTo('arrive');
  s.diagram.opacity(0);
  s.clocks.opacity(0);
  s.ship.showLabels(0);
  s.ship.scale(0.62);
  s.ship.position([560, -170]);
  s.ship.rotation(180);
  s.ship.beta(0);
  s.station.position([-80, -260]);
  s.station.scale(0.45);
  s.tether.opacity(0);
  s.world.position([0, 0]);
  s.world.scale(1.15);
  keeper.body.rotation(0);
  keeper.body.position([-330, 90]);
  keeper.body.setPose({torso: 2, leftShoulder: -20, leftElbow: -20, rightShoulder: 10, rightElbow: -20, leftHip: -8, leftKnee: 12, rightHip: 8, rightKnee: 10});
  alien.body.setPose({torso: 0, leftShoulder: 10, leftElbow: -10, rightShoulder: 10, rightElbow: -10, leftHip: -6, leftKnee: 8, rightHip: 6, rightKnee: 8});
  alien.body.position([520, -120]);
  yield* all(s.scenery.opacity(1, 0.4), keeper.body.opacity(1, 0.4), s.world.scale(1, 1.5, easeOutCubic));

  // The traveller steps out of the hatch and drifts to the keeper.
  yield* syncTo('alienOut');
  yield* all(alien.body.opacity(1, 0.6), alien.body.position([300, 90], 2.2, easeInOutCubic));

  yield* syncTo('n7.start');
  yield* s.label.show('|ψ⟩ = (|↑↓⟩ − |↓↑⟩) / √2', 'an entangled pair: one shared state, two blades');

  // Blades out. The traveller's blade flickers: it is in superposition.
  yield* syncTo('drawAlien');
  yield* all(
    alien.body.pose({rightShoulder: -100, rightElbow: -30, torso: 4}, 0.5),
    alien.blade.extend(1, 0.8, easeOutCubic),
    alien.blade.spread(6, 0.8).to(0, 0.6),
    alien.blade.showSpin(1, 0.5),
  );
  yield* syncTo('drawKeeper');
  yield* all(
    keeper.body.pose({rightShoulder: -100, rightElbow: -30, torso: 4}, 0.5),
    keeper.blade.extend(1, 0.8, easeOutCubic),
    keeper.blade.showSpin(1, 0.5),
  );

  yield* syncTo('n8.start');
  yield* s.label.show('vacuum: no medium, no sound', 'what you hear is vibration through blade, glove and bone');

  // Guard stances, then the fight.
  yield* syncTo('fight', 2.5);
  yield* all(
    s.label.hide(),
    keeper.body.pose({torso: 10, rightShoulder: -60, rightElbow: -40, leftShoulder: -40, leftElbow: -70, leftHip: -30, leftKnee: 40, rightHip: 15, rightKnee: 30}, 1.2),
    alien.body.pose({torso: 10, rightShoulder: -60, rightElbow: -40, leftShoulder: -40, leftElbow: -70, leftHip: -30, leftKnee: 40, rightHip: 15, rightKnee: 30}, 1.2),
    s.earth.opacity(0.5, 1.2),
  );
}

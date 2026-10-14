import {Circle, Line, Node, Txt} from '@motion-canvas/2d';
import {all, chain, easeInCubic, easeInOutCubic, easeInOutSine, easeOutCubic, linear, ThreadGenerator, useLogger, useTime, Vector2, waitFor} from '@motion-canvas/core';
import {JOINTS, Pose, StickFigure} from '../../components/StickFigure';
import {hexNut} from '../components/Ambient';
import {FIGURE_SCALE} from '../../figureSpec';
import {Colors, Typography} from '../../styles';
import {reveal} from '../components/Hud';
import {exhaust, wavefronts} from '../components/Effects';
import {station as stationIcon} from '../components/Scenery';
import {at, syncTo} from '../cues';
import {gamma} from '../physics';
import {everyFrame, Stage, toWorldLocal} from '../stage';

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

/** Where `fist` would be (world-local) if `fig` held `pose`; tried and restored in one frame. */
function fistTarget(s: Stage, fig: StickFigure, fist: Node, pose: Pose): Vector2 {
  const saved = Object.fromEntries(JOINTS.map(j => [j, fig.joints[j]()])) as Pose;
  fig.setPose(pose);
  const abs = fist.absolutePosition();
  fig.setPose(saved);
  return toWorldLocal(s, abs);
}

const HOLD_IN_FRONT: Pose = {rightShoulder: -70, rightElbow: -70, head: 18, torso: 8};
const CATCH_HIGH: Pose = {leftShoulder: -150, leftElbow: -25, head: -25};
const PRESENT: Pose = {leftShoulder: -80, leftElbow: -60, head: 10, rightShoulder: 20, rightElbow: -30};

function* nutPlay(s: Stage): ThreadGenerator {
  const keeper = s.keeper.body;
  const nut = hexNut();
  keeper.bones.rightFist.add(nut);

  // He turns the nut over in front of his face.
  yield* syncTo('play');
  yield* keeper.pose(HOLD_IN_FRONT, 0.8, easeInOutCubic);
  s.spawn(nut.rotation(90, 1.0, easeInOutSine));

  // Toss: let go, and it flies in a straight line, spinning at a constant
  // rate, to exactly where his other hand will be on 'catch'.
  yield* syncTo('toss', 0.18);
  yield* keeper.pose({rightShoulder: -120, rightElbow: -20}, 0.18, easeOutCubic);
  nut.reparent(s.world);
  const catchAt = fistTarget(s, keeper, keeper.bones.leftFist, CATCH_HIGH);
  const flight = at('catch') - at('toss');
  // The flight runs in this thread, not spawned: a background tween's final
  // frame would land after the hand-off below and knock the nut out of the
  // palm (it writes world coordinates into the fist's local space).
  yield* all(
    nut.position(catchAt, flight, linear),
    nut.rotation(nut.rotation() + 540, flight, linear),
    keeper.pose({head: -25, rightShoulder: -40, rightElbow: -40}, 0.8, easeInOutSine),
    (function* () {
      yield* syncTo('catch', 0.35);
      yield* keeper.pose(CATCH_HIGH, 0.35, easeOutCubic);
    })(),
  );
  const palm = toWorldLocal(s, keeper.bones.leftFist.absolutePosition());
  if (nut.position().sub(palm).magnitude > 4) useLogger().warn(`nut: catch misses the hand by ${nut.position().sub(palm).magnitude.toFixed(0)} px`);
  nut.reparent(keeper.bones.leftFist);
  nut.position(Vector2.zero);

  // Present it, then let it hover: no friction, so it spins in place.
  yield* syncTo('twirl', 0.7);
  yield* keeper.pose(PRESENT, 0.7, easeInOutCubic);
  nut.reparent(s.world);
  const hover = nut.position();
  // Flick: the right hand comes to exactly where the nut hovers. The hover
  // spin runs in this thread too, so it has ended before the flick spin starts.
  const flickPose: Pose = {rightShoulder: PRESENT.leftShoulder!, rightElbow: PRESENT.leftElbow!};
  const hoverTime = at('flick') - at('twirl');
  yield* all(
    nut.rotation(nut.rotation() + 720 * hoverTime, hoverTime, linear),
    keeper.pose({leftShoulder: -30, leftElbow: -40, head: 14}, 0.6, easeOutCubic),
    (function* () {
      yield* syncTo('flick', 0.25);
      yield* keeper.pose(flickPose, 0.25, easeInCubic);
    })(),
  );
  const tap = toWorldLocal(s, keeper.bones.rightFist.absolutePosition());
  if (tap.sub(hover).magnitude > 4) useLogger().warn(`nut: flick misses by ${tap.sub(hover).magnitude.toFixed(0)} px`);
  const away = new Vector2(-300, -40);
  const life = 20;
  s.spawn(all(nut.position(hover.add(away.scale(life)), life, linear), nut.rotation(nut.rotation() + 400 * life, life, linear)));
  s.spawn(keeper.pose({rightShoulder: -20, rightElbow: -30, head: 0}, 0.6, easeOutCubic));

  // Far off, where it went: a violet pinprick (the ship's beacon, blueshifted).
  yield* syncTo('glint');
  // Pull out to the wide shot: the station, Earth, and the dark beyond.
  s.spawn(all(s.world.scale(1, 1.4, easeInOutCubic), s.world.position([-60, 20], 1.4, easeInOutCubic)));
  const glint = new Circle({position: [-820, -60], size: 0, fill: '#b7a6ff', shadowColor: 'rgba(183,166,255,0.6)', shadowBlur: 20});
  s.world.add(glint);
  s.spawn(glint.size(14, 0.3, easeOutCubic).to(6, 0.6).to(12, 0.6).to(0, 2.0));
  // He turns to look: a held beat of curiosity.
  yield* keeper.face(-1, 0.25);
  yield* keeper.pose({head: -12, torso: -6}, 0.5, easeOutCubic);
}

export function* arrival(s: Stage): ThreadGenerator {
  // 0 - 18: the keeper at the relay, fidgeting with a hex nut. The nut is
  // the first thing to obey the rules this film is about: once let go, it
  // keeps its velocity and its spin. It drifts off toward a violet glint.
  const keeper = s.keeper.body;
  floatPose(keeper);
  // Clear of the solar wing: no tangents between the figure and the station.
  keeper.position([-250, 110]);
  keeper.rotation(-4);
  s.tether.points(() => [s.station.position().add([-60, 10]), keeper.position()]);
  s.earth.opacity(1);
  s.moon.opacity(1);
  s.station.opacity(1);
  keeper.opacity(1);
  s.tether.opacity(1);
  // Medium close-up for the toy beat (figure ~35% of frame height, keeper on
  // the 0.38 lead-room line); it pulls out to the wide shot at the glint.
  const close = 1.8;
  s.world.scale(close);
  s.world.position([-230 - keeper.x() * close, 30 - keeper.y() * close]);
  s.spawn(s.blackout.opacity(0, 2.5));
  yield* nutPlay(s);

  // Title over the curiosity hold.
  // Title over the curiosity hold, with the scene dimmed behind it.
  yield* syncTo('title');
  yield* all(reveal(s.title, 0.8), s.blackout.opacity(0.55, 0.8));
  yield* waitFor(1.6);
  yield* all(s.title.opacity(0, 0.5), s.blackout.opacity(0, 0.5));

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

  yield* syncTo('lblLength');
  yield* s.label.show('L = L₀ √(1 − v²/c²) = 0.60 L₀', 'length contraction: the ship is shorter along its motion');
  yield* syncTo('lblLength', -5.0);
  yield* s.label.show('λ = λ₀ √((1−β)/(1+β)) = λ₀ / 3', 'its 1300 nm infrared beacon arrives as 433 nm violet');
  yield* syncTo('lblTime');
  yield* s.label.show('Δτ = Δt / γ,   γ = 1.67', 'moving clocks run slow: five years here, three aboard');

  // Flip and burn: point the engine forward and decelerate to rest.
  yield* syncTo('decel', 1.0);
  yield* s.ship.rotation(180, 1.0, easeInOutCubic);
  s.spawn(all(s.ship.beta(0, at('arrive') - at('decel') - 0.5, easeOutCubic), s.ship.flame(1, 0.4)));

  yield* syncTo('lblLight');
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
  // He turned to look at the glint; face the traveller again.
  keeper.body.scale([FIGURE_SCALE, FIGURE_SCALE]);
  keeper.body.position([-330, 90]);
  keeper.body.setPose({torso: 2, leftShoulder: -20, leftElbow: -20, rightShoulder: 10, rightElbow: -20, leftHip: -8, leftKnee: 12, rightHip: 8, rightKnee: 10});
  alien.body.setPose({torso: 0, leftShoulder: 10, leftElbow: -10, rightShoulder: 10, rightElbow: -10, leftHip: -6, leftKnee: 8, rightHip: 6, rightKnee: 8});
  alien.body.position([520, -120]);
  yield* all(s.scenery.opacity(1, 0.4), keeper.body.opacity(1, 0.4), s.world.scale(1, 1.5, easeOutCubic));

  // The traveller steps out of the hatch and drifts to the keeper.
  yield* syncTo('alienOut');
  yield* all(alien.body.opacity(1, 0.6), alien.body.position([300, 90], 2.2, easeInOutCubic));

  yield* syncTo('lblPair');
  yield* s.label.show('|ψ⟩ = (|↑↓⟩ − |↓↑⟩) / √2', 'an entangled pair: one shared state, two blades');

  // Blades out. The traveller's blade flickers: it is in superposition.
  yield* syncTo('drawAlien');
  yield* all(
    alien.body.pose({rightShoulder: -100, rightElbow: -30, torso: 4}, 0.5),
    alien.blade.opacity(1, 0.2),
    alien.blade.extend(1, 0.8, easeOutCubic),
    alien.blade.spread(6, 0.8).to(0, 0.6),
  );
  yield* syncTo('drawKeeper');
  yield* all(
    keeper.body.pose({rightShoulder: -100, rightElbow: -30, torso: 4}, 0.5),
    keeper.blade.opacity(1, 0.2),
    keeper.blade.extend(1, 0.8, easeOutCubic),
  );

  yield* syncTo('lblVacuum');
  yield* s.label.show('vacuum: no medium, no sound', 'what you hear is vibration through blade, glove and bone');

  // Guard stances, then the fight.
  // Sizing each other up: a slow orbit around their common centre, heads
  // tilting, then three small tells (blade flicker, re-grip, thruster trim).
  yield* syncTo('sizeUp');
  s.spawn(all(
    keeper.body.position([-300, 70], at('trim') - at('sizeUp') + 1, easeInOutSine),
    alien.body.position([270, 110], at('trim') - at('sizeUp') + 1, easeInOutSine),
    keeper.body.rotation(-4, 3.5, easeInOutSine).to(2, 3.5, easeInOutSine),
    alien.body.rotation(4, 3.5, easeInOutSine).to(-2, 3.5, easeInOutSine),
    keeper.body.pose({head: -10}, 1.2, easeInOutSine),
    alien.body.pose({head: 12}, 1.2, easeInOutSine),
  ));
  yield* syncTo('flicker');
  yield* alien.blade.spread(5, 0.35, easeOutCubic).to(0, 0.45, easeInOutSine);
  yield* syncTo('grip', 0.15);
  yield* all(keeper.blade.rotation(-55, 0.15, easeOutCubic).to(-70, 0.3, easeInOutSine), chain(keeper.body.pose({rightElbow: -45}, 0.15), keeper.body.pose({rightElbow: -30}, 0.3)));
  yield* syncTo('trim');
  s.spawn(exhaust(s.fx, () => keeper.body.bones.torso.absolutePosition(), new Vector2(-1, 0.2), 0.3));
  yield* syncTo('fight', 2.5);
  yield* all(
    s.label.hide(),
    keeper.body.pose({torso: 10, rightShoulder: -60, rightElbow: -40, leftShoulder: -40, leftElbow: -70, leftHip: -30, leftKnee: 40, rightHip: 15, rightKnee: 30}, 1.2),
    alien.body.pose({torso: 10, rightShoulder: -60, rightElbow: -40, leftShoulder: -40, leftElbow: -70, leftHip: -30, leftKnee: 40, rightHip: 15, rightKnee: 30}, 1.2),
    s.earth.opacity(0.5, 1.2),
  );
}

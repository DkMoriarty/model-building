import {Circle, Line, makeScene2D, Node, Txt} from '@motion-canvas/2d';
import {all, easeOutCubic, spring, StrikeSpring, waitFor} from '@motion-canvas/core';
import {StickFigure} from '../components/StickFigure';
import {UIWindow} from '../components/UIWindow';
import {Colors, Springs, Typography} from '../styles';
import {at, beat, playUntil, springContactTime, syncTo} from '../sync';

const GROUND_Y = 300;

export default makeScene2D(function* (view) {
  view.fill(Colors.background);

  // Everything lives under a camera node so impacts can shake the whole frame.
  const camera = new Node({});
  view.add(camera);

  camera.add(
    new Line({
      points: [
        [-960, GROUND_Y],
        [960, GROUND_Y],
      ],
      stroke: Colors.border,
      lineWidth: 4,
    }),
  );

  // Red faces right (default). Blue faces left: same rig, mirrored by scale.x.
  const red = new StickFigure({x: -760, color: Colors.accent});
  red.y(GROUND_Y - red.legLength);
  const blue = new StickFigure({x: 220, color: Colors.victim, scale: [-1, 1]});
  blue.y(GROUND_Y - blue.legLength);
  camera.add([blue, red]);

  const flash = new Circle({size: 0, fill: Colors.impact, opacity: 0});
  camera.add(flash);

  const dialog = new UIWindow({
    title: 'blue.exe',
    body: 'blue.exe has stopped responding.',
    y: -180,
    buttons: ['Debug', 'Close'],
  });
  camera.add(dialog);

  const caption = new Txt({
    text: 'ALAN PIPELINE // TEST 001',
    y: 470,
    fill: Colors.inkMuted,
    fontFamily: Typography.mono,
    fontSize: 22,
    opacity: 0,
  });
  view.add(caption);

  // Each performer runs on its own timeline, synced to the audio markers
  // independently. A long spring on one character can never push another
  // character's beat off the music; syncTo() warns if a track itself overruns.

  function* redTrack() {
    // Walk in: footfalls on eighth notes, the last foot lands on "windup".
    yield* syncTo('walkIn');
    yield* red.walkTo(40, {
      steps: (at('windup') - at('walkIn')) / (beat / 2),
      arriveAt: at('windup'),
      settle: false,
    });

    // Wind-up: anticipation before the hit.
    yield* syncTo('windup');
    yield* red.pose(
      {torso: -10, rightShoulder: 110, rightElbow: -110, leftShoulder: -50, leftElbow: -90},
      0.25,
    );

    // Punch: the spring launches early so the fist CONNECTS on "impact".
    const punchTo = -90;
    yield* syncTo('impact', springContactTime(StrikeSpring, red.joints.rightShoulder(), punchTo));
    yield* red.springPose(StrikeSpring, {
      torso: 18,
      rightShoulder: punchTo,
      rightElbow: 0,
      leftShoulder: 30,
      leftElbow: -40,
    });
    yield* red.pose(
      {torso: 0, rightShoulder: -30, rightElbow: -20, leftShoulder: 14, leftElbow: -10},
      0.4,
    );

    // Uppercut "Close": cock the arm, then connect on "click".
    yield* syncTo('click', 0.3);
    yield* red.pose({rightShoulder: 110, rightElbow: -60, torso: -4}, 0.2);
    yield* syncTo('click', springContactTime(StrikeSpring, 110, 190));
    yield* red.springPose(StrikeSpring, {rightShoulder: 190, rightElbow: 0});

    // Back-pedal two steps, still facing right; last foot lands on "end".
    yield* syncTo('backstep');
    yield* red.walkTo(red.x() - 180, {mode: 'backward', steps: 2, arriveAt: at('end')});
  }

  function* blueTrack() {
    // Hit reaction: head snaps back, torso folds back, knocked backwards.
    // It plays until the collapse needs the body, however long the springs ring.
    yield* syncTo('impact');
    yield* playUntil(
      'land',
      0.25,
      blue.springPose(Springs.recoil, {head: -35, torso: -38, leftShoulder: -110, rightShoulder: -70}),
      spring(Springs.knockback, blue.x(), 640, 2, x => blue.x(x)),
    );
    // Collapse: body hits the floor on "land".
    yield* all(
      blue.pose({torso: -90, head: -20, leftHip: -40, rightHip: -70, leftKnee: 60}, 0.25),
      blue.y(GROUND_Y - 30, 0.25),
    );
  }

  function* fxTrack() {
    yield* syncTo('impact');
    // Set (not tween) so the flash is on screen on the marker frame itself.
    flash.absolutePosition(red.bones.rightFist.absolutePosition());
    flash.opacity(1);
    flash.size(40);
    yield* all(
      flash.opacity(0, 0.25),
      flash.size(220, 0.25, easeOutCubic),
      (function* () {
        for (const [dx, dy] of [
          [22, -10],
          [-18, 8],
          [12, -6],
          [-6, 3],
          [0, 0],
        ]) {
          yield* camera.position([dx, dy], 0.035);
        }
      })(),
    );
  }

  function* uiTrack() {
    yield* syncTo('walkIn');
    yield* caption.opacity(1, 0.4);
    // Crash dialog pops in with spring physics.
    yield* syncTo('popup');
    yield* dialog.popIn();
    yield* dialog.shake();
    // Button press on the uppercut's contact frame.
    yield* syncTo('click');
    yield* dialog.press(1);
    yield* dialog.popOut();
    yield* syncTo('end');
    yield* caption.opacity(0, 0.3);
  }

  yield* all(redTrack(), blueTrack(), fxTrack(), uiTrack());
  yield* waitFor(0.1);
});

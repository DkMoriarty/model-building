import {Circle, Line, makeScene2D, Node, Txt} from '@motion-canvas/2d';
import {
  all,
  easeOutCubic,
  spring,
  StrikeSpring,
  waitFor,
} from '@motion-canvas/core';
import {StickFigure} from '../components/StickFigure';
import {UIWindow} from '../components/UIWindow';
import {Colors, Springs, Typography} from '../styles';
import {syncTo} from '../sync';

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

  // 1. Walk in -------------------------------------------------------------
  yield* syncTo('walkIn');
  yield* all(caption.opacity(1, 0.4), red.walkTo(40, 95, 0.13));

  // 2. Wind-up: anticipation before the hit ---------------------------------
  yield* syncTo('windup');
  yield* red.pose(
    {torso: -14, rightShoulder: 120, rightElbow: 70, leftShoulder: -40},
    0.3,
  );

  // 3. Impact: StrikeSpring drives the punch, landing on the transient -------
  yield* syncTo('impact', 0.06);
  yield* red.springPose(StrikeSpring, {
    torso: 18,
    rightShoulder: -90,
    rightElbow: 0,
    leftShoulder: 30,
  });
  const fist = red.bones.rightFist.absolutePosition();
  flash.absolutePosition(fist);
  yield* all(
    // Flash
    flash.opacity(1, 0).to(0, 0.25),
    flash.size(40, 0).to(220, 0.25, easeOutCubic),
    // Camera shake
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
    // Victim reaction: head snaps, torso folds, knocked back by a spring
    blue.springPose(Springs.recoil, {head: -35, torso: -38, leftShoulder: -110, rightShoulder: -70}),
    spring(Springs.knockback, blue.x(), 640, 2, x => blue.x(x)),
  );

  // 4. Collapse ----------------------------------------------------------------
  yield* syncTo('land', 0.25);
  yield* all(
    blue.pose({torso: -90, head: -20, leftHip: 40, rightHip: 70, leftKnee: -60}, 0.25),
    blue.y(GROUND_Y - 30, 0.25),
    red.pose({torso: 0, rightShoulder: -30, rightElbow: 20, leftShoulder: 18}, 0.4),
  );

  // 5. Crash dialog pops in with spring physics ------------------------------
  yield* syncTo('popup');
  yield* dialog.popIn();
  yield* dialog.shake();

  // 6. Red punches "Close" ------------------------------------------------------
  yield* syncTo('click', 0.3);
  yield* red.pose({rightShoulder: 160, rightElbow: 20, torso: 4}, 0.3);
  yield* all(dialog.press(1), red.springPose(StrikeSpring, {rightShoulder: -150}));
  yield* dialog.popOut();

  yield* syncTo('end');
  yield* all(caption.opacity(0, 0.3), waitFor(0.3));
});

import {Line, Node, Rect, View2D} from '@motion-canvas/2d';
import {createSignal, SimpleSignal, ThreadGenerator, usePlayback, useTime, Vector2} from '@motion-canvas/core';
import {StickFigure} from '../components/StickFigure';
import {Colors} from '../styles';
import {Blade} from './components/Blade';
import {createAlien, createKeeper, Fighter, MASS} from './components/Fighters';
import {ClockDial, PhysicsLabel, Subtitles, titleCard} from './components/Hud';
import {earth, moon, station} from './components/Scenery';
import {Ship} from './components/Ship';
import {Starfield} from './components/Starfield';

/** Everything the acts share: camera, layers and cast. */
export interface Stage {
  view: View2D;
  /** Camera: everything in world space lives under this node. */
  world: Node;
  stars: Starfield;
  scenery: Node;
  earth: Node;
  moon: Node;
  station: Node;
  tether: Line;
  diagram: Node;
  ship: Ship;
  keeper: Fighter;
  alien: Fighter;
  /** Effects layer drawn above the fighters. */
  fx: Node;
  hud: Node;
  subs: Subtitles;
  label: PhysicsLabel;
  title: Node;
  clocks: Node;
  keeperClock: ClockDial;
  travelerClock: ClockDial;
  blackout: Rect;
  /** Fight frame: centre of mass (fixed: no external forces) and separation. */
  com: SimpleSignal<Vector2, void>;
  sep: SimpleSignal<Vector2, void>;
  /** Camera shake offset, added on top of the framing. */
  shake: SimpleSignal<Vector2, void>;
  /** The traveller's blade once it has been knocked free. */
  freeBlade: Blade | null;
  /**
   * Fire-and-forget an effect. Tasks forked with a bare `yield` are cancelled
   * when the generator that forked them returns, freezing a half-finished
   * spark or puff on screen; spawned tasks live as long as the scene.
   */
  spawn(task: ThreadGenerator): void;
  /** Runs spawned tasks; started once by the scene, until `until`. */
  runner(until: number): ThreadGenerator;
}

export function buildStage(view: View2D): Stage {
  view.fill('#050508');
  const stars = new Starfield();
  const world = new Node({});
  stars.pan(() => world.position().scale(-1));
  view.add([stars, world]);

  const earthNode = earth({x: -1150, y: 1650, opacity: 0});
  const moonNode = moon({x: 700, y: -330, opacity: 0});
  const stationNode = station({x: 230, y: 40, scale: 0.8, opacity: 0});
  const tether = new Line({points: [], stroke: 'rgba(200,200,210,0.5)', lineWidth: 3, lineDash: [10, 8], opacity: 0});
  const scenery = new Node({children: [earthNode, moonNode, stationNode, tether]});

  const diagram = new Node({opacity: 0});
  const ship = new Ship({scale: 0.5, opacity: 0});
  const fx = new Node({});

  const keeper = createKeeper({scale: 0.62});
  const alien = createAlien({scale: [-0.62, 0.62]});
  keeper.body.opacity(0);
  alien.body.opacity(0);

  world.add([scenery, diagram, ship, alien.body, keeper.body, fx]);

  const subs = new Subtitles();
  const label = new PhysicsLabel();
  const title = titleCard('The Entangled Blade', 'A FIGHT THE LAWS OF PHYSICS WOULD SIGN OFF ON');
  const keeperClock = new ClockDial({label: 'KEEPER', color: Colors.accent, x: 640});
  const travelerClock = new ClockDial({label: 'TRAVELER', color: '#3ddc97', x: 840});
  const clocks = new Node({y: -390, opacity: 0, children: [keeperClock, travelerClock]});
  const blackout = new Rect({width: 1920, height: 1080, fill: '#000000', opacity: 1});
  const hud = new Node({children: [title, clocks, label, subs, blackout]});
  view.add(hud);
  const queue: ThreadGenerator[] = [];

  return {
    view,
    world,
    stars,
    scenery,
    earth: earthNode,
    moon: moonNode,
    station: stationNode,
    tether,
    diagram,
    ship,
    keeper,
    alien,
    fx,
    hud,
    subs,
    label,
    title,
    clocks,
    keeperClock,
    travelerClock,
    blackout,
    com: createSignal(Vector2.zero),
    sep: createSignal(new Vector2(600, 0)),
    shake: createSignal(Vector2.zero),
    freeBlade: null,
    spawn: task => queue.push(task),
    runner: function* (until: number) {
      while (useTime() < until - 1e-6) {
        while (queue.length) yield queue.shift()!;
        yield;
      }
    },
  };
}

/**
 * Bind both fighters to the centre-of-mass frame. With no external forces the
 * centre of mass never accelerates, so every push between them shows up as
 * displacements in the inverse ratio of their masses: m1 dx1 = -m2 dx2.
 */
export function bindToCentreOfMass(stage: Stage): void {
  const total = MASS.keeper + MASS.alien;
  stage.keeper.body.position(() => stage.com().add(stage.sep().scale(-MASS.alien / total)));
  stage.alien.body.position(() => stage.com().add(stage.sep().scale(MASS.keeper / total)));
}

/** Current separation (alien minus keeper) implied by the fighters' positions. */
export function separationOf(stage: Stage): Vector2 {
  return stage.alien.body.position().sub(stage.keeper.body.position());
}

/** Seconds per rendered frame. */
export function frameTime(): number {
  return usePlayback().framesToSeconds(1);
}

/** Run `step(dt)` once per frame until absolute time `until`. */
export function* everyFrame(until: number, step: (dt: number) => void): ThreadGenerator {
  while (useTime() < until - 1e-6) {
    step(frameTime());
    yield;
  }
}

/**
 * Moment of inertia of a figure about its pelvis, from where its joints are
 * right now: I = sum m r^2 over head, chest, fists, feet and blade tip.
 */
export function inertia(fig: StickFigure, blade?: Blade): number {
  const centre = fig.absolutePosition();
  const points: [Node, number][] = [
    [fig.bones.head, 1.2],
    [fig.bones.chest, 2],
    [fig.bones.leftFist, 0.6],
    [fig.bones.rightFist, 0.6],
    [fig.bones.leftFoot, 0.9],
    [fig.bones.rightFoot, 0.9],
  ];
  let sum = 0;
  for (const [node, m] of points) {
    sum += m * node.absolutePosition().sub(centre).squaredMagnitude;
  }
  if (blade) sum += 0.4 * blade.tip().sub(centre).squaredMagnitude;
  return sum;
}

/** Closest distance between two blades and the point midway between them. */
export function bladeContact(a: Blade, b: Blade): {distance: number; point: Vector2} {
  const p1 = a.absolutePosition();
  const q1 = a.tip();
  const p2 = b.absolutePosition();
  const q2 = b.tip();
  // Closest points between segments p1q1 and p2q2 (sampled: robust and cheap).
  let best = {distance: Infinity, point: Vector2.zero};
  for (let i = 0; i <= 24; i++) {
    const u = p1.lerp(q1, i / 24);
    for (let j = 0; j <= 24; j++) {
      const v = p2.lerp(q2, j / 24);
      const d = u.sub(v).magnitude;
      if (d < best.distance) best = {distance: d, point: u.lerp(v, 0.5)};
    }
  }
  return best;
}

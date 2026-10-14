import {Circle, Gradient, Line, Node, Rect, Txt, View2D} from '@motion-canvas/2d';
import {createSignal, SimpleSignal, ThreadGenerator, useLogger, usePlayback, useTime, Vector2, Vector2Signal} from '@motion-canvas/core';
import {JOINTS, Pose, StickFigure} from '../components/StickFigure';
import {BIPED, FIGURE_SCALE, strokeOf, withAlpha} from '../figureSpec';
import {Typography} from '../styles';
import {BEAD, Wire} from './components/Circuit';
import {createSpark, Spark} from './components/Spark';

/** The floor line, in world space: 0.78 of the frame height at zoom 1. */
export const FLOOR = 300;

/** Everything the acts share: camera, layers, cast and the per-frame clock. */
export interface Stage {
  view: View2D;
  world: Node;
  /** Camera: the world point at the centre of the frame, and the zoom. */
  cam: Vector2Signal<void>;
  zoom: SimpleSignal<number, void>;
  shake: Vector2Signal<void>;
  time: SimpleSignal<number, void>;
  /** Room light 0..1: how much of the room the lamp reveals. */
  room: SimpleSignal<number, void>;
  /** Where the room light comes from (world), and its colour. */
  lightAt: Vector2Signal<void>;
  lightColor: SimpleSignal<string, void>;
  /** Layers in world space, back to front. */
  back: Node;
  props: Node;
  cast: Node;
  fx: Node;
  spark: Spark;
  hud: Node;
  title: Node;
  blackout: Rect;
  whiteout: Rect;
  /** Register a wire so its beads advance every frame. */
  wire(w: Wire): Wire;
  spawn(task: ThreadGenerator): void;
  runner(until: number): ThreadGenerator;
}

export function buildStage(view: View2D, titleText = 'FIRST LIGHT'): Stage {
  view.fill('#060609');
  const time = createSignal(0);
  const cam = Vector2.createSignal(Vector2.zero);
  const zoom = createSignal(1);
  const shake = Vector2.createSignal(Vector2.zero);
  const room = createSignal(0);
  const lightAt = Vector2.createSignal(Vector2.zero);
  const lightColor = createSignal(BEAD);

  const world = new Node({
    position: () => cam().scale(-zoom()).add(shake()),
    scale: () => zoom(),
  });
  const back = new Node({});
  // The pool of light the lamp throws: a radial falloff, never a hard edge.
  back.add(
    new Circle({
      position: () => lightAt(),
      size: 2600,
      opacity: () => room(),
      fill: () =>
        new Gradient({
          type: 'radial',
          fromRadius: 0,
          toRadius: 1300,
          stops: [
            {offset: 0, color: withAlpha(lightColor(), 0.16)},
            {offset: 0.35, color: withAlpha(lightColor(), 0.06)},
            {offset: 1, color: withAlpha(lightColor(), 0)},
          ],
        }),
    }),
  );
  back.add(
    new Line({
      points: [
        [-2400, FLOOR],
        [2400, FLOOR],
      ],
      stroke: '#3a3a44',
      lineWidth: 4,
      opacity: () => 0.25 + 0.75 * room(),
    }),
  );
  const props = new Node({});
  const cast = new Node({});
  const fx = new Node({});
  world.add([back, props, cast, fx]);
  view.add(world);

  const spark = createSpark({scale: FIGURE_SCALE});
  cast.add(spark.body);

  const title = new Node({
    y: -250,
    opacity: 0,
    children: [
      new Txt({text: titleText, fill: '#f2f2f2', fontFamily: Typography.family, fontSize: 96, fontWeight: 800, letterSpacing: 18}),
      new Line({
        points: [
          [-300, 70],
          [300, 70],
        ],
        stroke: BEAD,
        lineWidth: 4,
      }),
    ],
  });
  const whiteout = new Rect({width: 1920, height: 1080, fill: '#ffffff', opacity: 0});
  const blackout = new Rect({width: 1920, height: 1080, fill: '#000000', opacity: 1});
  const hud = new Node({children: [whiteout, title, blackout]});
  view.add(hud);

  const wires: Wire[] = [];
  const queue: ThreadGenerator[] = [];
  return {
    view,
    world,
    cam,
    zoom,
    shake,
    time,
    room,
    lightAt,
    lightColor,
    back,
    props,
    cast,
    fx,
    spark,
    hud,
    title,
    blackout,
    whiteout,
    wire: w => {
      wires.push(w);
      return w;
    },
    spawn: task => queue.push(task),
    runner: function* (until: number) {
      const dt = usePlayback().framesToSeconds(1);
      while (useTime() < until - 1e-6) {
        time(useTime());
        for (const w of wires) {
          const v = w.speed();
          if (v !== 0) w.flow(w.flow() + v * dt);
        }
        while (queue.length) yield queue.shift()!;
        yield;
      }
    },
  };
}

/** World point -> absolute (screen) point. */
export function toAbs(s: Stage, p: Vector2): Vector2 {
  return p.transformAsPoint(s.world.localToWorld());
}
/** Absolute (screen) point -> world point. */
export function toWorld(s: Stage, abs: Vector2): Vector2 {
  return abs.transformAsPoint(s.world.worldToLocal());
}
/** A node's position in world space. */
export function worldOf(s: Stage, n: Node, local: Vector2 = Vector2.zero): Vector2 {
  return toWorld(s, local.transformAsPoint(n.localToWorld()));
}

/** Bind a world-space prop to follow a node (a hand), with an offset. */
export function attach(s: Stage, prop: Node, to: Node, offset: Vector2 = Vector2.zero): void {
  prop.position(() => worldOf(s, to).add(offset));
}
/** Stop following: freeze the prop where it is now. */
export function detach(prop: Node): void {
  prop.position(prop.position());
}

export type Limb = 'leftArm' | 'rightArm' | 'leftLeg' | 'rightLeg';
const LIMB = {
  leftArm: {root: 'leftShoulder', mid: 'leftElbow', bend: -1},
  rightArm: {root: 'rightShoulder', mid: 'rightElbow', bend: -1},
  leftLeg: {root: 'leftHip', mid: 'leftKnee', bend: 1},
  rightLeg: {root: 'rightHip', mid: 'rightKnee', bend: 1},
} as const;

/**
 * Two-bone IK: the pose (on top of `base`) that puts the limb's end exactly
 * on `target` (world space). Solved in the limb root's parent frame, so it
 * holds for any torso lean, figure position or facing. Elbows flex forward
 * (negative), knees flex back (positive), per the rig's sign convention.
 */
export function reach(s: Stage, fig: StickFigure, limb: Limb, target: Vector2, base: Pose = {}): Pose {
  const saved = Object.fromEntries(JOINTS.map(j => [j, fig.joints[j]()])) as Pose;
  fig.setPose(base);
  const arm = limb.endsWith('Arm');
  const parent = arm ? fig.bones.chest : fig;
  const p = fig.proportions;
  const L1 = arm ? p.upperArm : p.thigh;
  const L2 = arm ? p.forearm : p.shin;
  const T = toAbs(s, target).transformAsPoint(parent.worldToLocal());
  fig.setPose(saved);
  const d = Math.min(Math.max(T.magnitude, Math.abs(L1 - L2) + 0.01), L1 + L2 - 0.01);
  const aT = Math.atan2(-T.x, T.y);
  const phi = Math.acos((L1 * L1 + d * d - L2 * L2) / (2 * L1 * d));
  const gamma = Math.acos((L1 * L1 + L2 * L2 - d * d) / (2 * L1 * L2));
  const bendDeg = 180 - (gamma * 180) / Math.PI;
  const {root, mid, bend} = LIMB[limb];
  const rootDeg = ((aT - bend * phi) * 180) / Math.PI;
  return {...base, [root]: rootDeg, [mid]: bend * bendDeg};
}

/** Warn when a hand or foot misses its mark by more than `tol` px (world). */
export function checkReach(s: Stage, what: string, end: Node, target: Vector2, tol = 4): void {
  const miss = worldOf(s, end).sub(target).magnitude;
  if (miss > tol) useLogger().warn(`reach: ${what} misses by ${miss.toFixed(0)} px`);
}

/** Put the lower foot on the floor (standing poses). */
export function plant(s: Stage, fig: StickFigure, floor = FLOOR): void {
  const sole = strokeOf(BIPED) * 0.5 * Math.abs(fig.scale.y());
  const lowest = Math.max(worldOf(s, fig.bones.leftFoot).y, worldOf(s, fig.bones.rightFoot).y);
  fig.y(fig.y() + floor - sole - lowest);
}

/** Pelvis height above the floor when sitting (pelvis on the floor). */
export const SIT_Y = FLOOR - 7;

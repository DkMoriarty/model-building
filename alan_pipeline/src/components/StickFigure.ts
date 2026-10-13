import {Circle, Line, Node, NodeProps} from '@motion-canvas/2d';
import {
  all,
  createSignal,
  easeInOutCubic,
  easeInOutSine,
  linear,
  SimpleSignal,
  spring,
  Spring,
  ThreadGenerator,
  TimingFunction,
} from '@motion-canvas/core';
import {Colors, Stroke} from '../styles';

/**
 * Every rotatable joint on the rig. Angles are in degrees and are LOCAL to the
 * parent bone: 0 means "hanging straight down" for limbs and "straight up" for
 * the torso/head. Positive values rotate clockwise (canvas convention).
 */
export const JOINTS = [
  'torso',
  'head',
  'leftShoulder',
  'leftElbow',
  'rightShoulder',
  'rightElbow',
  'leftHip',
  'leftKnee',
  'rightHip',
  'rightKnee',
] as const;

export type Joint = (typeof JOINTS)[number];
export type Pose = Partial<Record<Joint, number>>;

export interface Proportions {
  headRadius: number;
  neck: number;
  torso: number;
  upperArm: number;
  forearm: number;
  thigh: number;
  shin: number;
}

export interface StickFigureProps extends NodeProps {
  color?: string;
  lineWidth?: number;
  proportions?: Partial<Proportions>;
  pose?: Pose;
}

const DEFAULT_PROPORTIONS: Proportions = {
  headRadius: 34,
  neck: 10,
  torso: 120,
  upperArm: 62,
  forearm: 60,
  thigh: 72,
  shin: 70,
};

/** Relaxed standing pose. */
export const IDLE: Pose = {
  torso: 0,
  head: 0,
  leftShoulder: 18,
  leftElbow: -12,
  rightShoulder: -18,
  rightElbow: 12,
  leftHip: 10,
  leftKnee: -4,
  rightHip: -10,
  rightKnee: 4,
};

/**
 * Hierarchical kinematic stick-figure rig.
 *
 * The node's own position is the pelvis. Bones are nested `Node`s, so every
 * child inherits its parent's full transform matrix (hip -> knee -> foot,
 * torso -> shoulder -> elbow -> fist). Nothing stores absolute coordinates, so
 * there is no floating-point drift between frames: a pose is just ten angles.
 *
 * Each joint is a Motion Canvas signal and can be tweened directly:
 *
 *   yield* fig.joints.rightShoulder(-95, 0.2);
 *   yield* fig.pose({rightShoulder: -95, rightElbow: 0}, 0.2);
 *   yield* fig.springPose(StrikeSpring, {rightShoulder: -95});
 */
export class StickFigure extends Node {
  public readonly joints: Record<Joint, SimpleSignal<number, this>>;
  public readonly color: SimpleSignal<string, this>;
  public readonly proportions: Proportions;

  /** Bone nodes, exposed for attaching props (weapons, effects) to a limb. */
  public readonly bones: {
    torso: Node;
    chest: Node;
    head: Circle;
    leftFist: Node;
    rightFist: Node;
    leftFoot: Node;
    rightFoot: Node;
  };

  public constructor({
    color = Colors.ink,
    lineWidth = Stroke.limb,
    proportions,
    pose,
    ...props
  }: StickFigureProps = {}) {
    super(props);
    const p = {...DEFAULT_PROPORTIONS, ...proportions};
    this.proportions = p;
    this.color = createSignal(color) as SimpleSignal<string, this>;

    const initial = {...IDLE, ...pose};
    this.joints = Object.fromEntries(
      JOINTS.map(joint => [joint, createSignal(initial[joint] ?? 0)]),
    ) as unknown as Record<Joint, SimpleSignal<number, this>>;

    const stroke = () => this.color();
    const bone = (length: number) =>
      new Line({
        points: [
          [0, 0],
          [0, length],
        ],
        stroke,
        lineWidth,
        lineCap: 'round',
      });

    /** Two-segment limb: root joint -> mid joint -> end effector. */
    const limb = (
      rootJoint: Joint,
      midJoint: Joint,
      upper: number,
      lower: number,
    ): {root: Node; end: Node} => {
      const end = new Node({y: lower});
      const mid = new Node({
        y: upper,
        rotation: () => this.joints[midJoint](),
        children: [bone(lower), end],
      });
      const root = new Node({
        rotation: () => this.joints[rootJoint](),
        children: [bone(upper), mid],
      });
      return {root, end};
    };

    const leftArm = limb('leftShoulder', 'leftElbow', p.upperArm, p.forearm);
    const rightArm = limb('rightShoulder', 'rightElbow', p.upperArm, p.forearm);
    const leftLeg = limb('leftHip', 'leftKnee', p.thigh, p.shin);
    const rightLeg = limb('rightHip', 'rightKnee', p.thigh, p.shin);

    const head = new Circle({
      y: -(p.neck + p.headRadius),
      size: p.headRadius * 2,
      stroke,
      lineWidth: Stroke.head,
      fill: Colors.background,
    });

    const chest = new Node({
      y: -p.torso,
      children: [
        leftArm.root,
        rightArm.root,
        new Node({
          rotation: () => this.joints.head(),
          children: [
            new Line({
              points: [
                [0, 0],
                [0, -p.neck],
              ],
              stroke,
              lineWidth,
              lineCap: 'round',
            }),
            head,
          ],
        }),
      ],
    });

    const torso = new Node({
      rotation: () => this.joints.torso(),
      children: [
        new Line({
          points: [
            [0, 0],
            [0, -p.torso],
          ],
          stroke,
          lineWidth,
          lineCap: 'round',
        }),
        chest,
      ],
    });

    // Legs first so the torso/arms draw on top of them.
    this.add([leftLeg.root, rightLeg.root, torso]);

    this.bones = {
      torso,
      chest,
      head,
      leftFist: leftArm.end,
      rightFist: rightArm.end,
      leftFoot: leftLeg.end,
      rightFoot: rightLeg.end,
    };
  }

  /** Distance from pelvis to the soles in the IDLE pose (for ground placement). */
  public get legLength(): number {
    return this.proportions.thigh + this.proportions.shin;
  }

  /** Snap to a pose instantly. */
  public setPose(pose: Pose): void {
    for (const joint of Object.keys(pose) as Joint[]) {
      this.joints[joint](pose[joint]!);
    }
  }

  /** Tween any subset of joints in parallel. */
  public *pose(
    pose: Pose,
    duration: number,
    timing: TimingFunction = easeInOutCubic,
  ): ThreadGenerator {
    yield* all(
      ...(Object.keys(pose) as Joint[]).map(joint =>
        this.joints[joint](pose[joint]!, duration, timing),
      ),
    );
  }

  /**
   * Drive joints with a spring-damper simulation instead of an easing curve.
   * Overshoot and settle come from the physics, which is what sells weight on
   * punches and recoils.
   */
  public *springPose(
    physics: Spring,
    pose: Pose,
    settleDegrees = 0.5,
  ): ThreadGenerator {
    yield* all(
      ...(Object.keys(pose) as Joint[]).map(joint => {
        const signal = this.joints[joint];
        return spring(physics, signal(), pose[joint]!, settleDegrees, value =>
          signal(value),
        );
      }),
    );
  }

  /**
   * Walk to `x` with a procedural gait: legs and arms swing in counter-phase
   * while the pelvis translates linearly, so foot timing is locked to the
   * stride length rather than hand-placed keys.
   */
  public *walkTo(x: number, stride = 90, stepTime = 0.22): ThreadGenerator {
    const distance = x - this.x();
    const steps = Math.max(1, Math.round(Math.abs(distance) / stride));
    const dir = Math.sign(distance) || 1;
    const swing = 28 * dir;
    yield* all(
      this.x(x, steps * stepTime, linear),
      (function* (fig: StickFigure) {
        for (let i = 0; i < steps; i++) {
          const s = i % 2 === 0 ? 1 : -1;
          yield* fig.pose(
            {
              leftHip: swing * s,
              leftKnee: s > 0 ? -6 : -28,
              rightHip: -swing * s,
              rightKnee: s > 0 ? -28 : -6,
              leftShoulder: -swing * s * 0.8,
              rightShoulder: swing * s * 0.8,
              torso: 6 * dir,
            },
            stepTime,
            easeInOutSine,
          );
        }
        yield* fig.pose(IDLE, stepTime);
      })(this),
    );
  }
}

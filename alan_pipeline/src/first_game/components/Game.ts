import {Circle, Gradient, Line, Node, NodeProps, Rect} from '@motion-canvas/2d';
import {createSignal, Vector2} from '@motion-canvas/core';
import {withAlpha} from '../../figureSpec';
import {TIER} from '../../first_light/components/Circuit';

/**
 * Spark's first game (original design). One screen per level, in game
 * units: 1280 x 720, origin at the centre, ground at y = 250. The same
 * level is built twice: small inside the monitor, full size once Spark is
 * inside it.
 */
export const G = {w: 1280, h: 720, ground: 250};
/** Pelvis height above a surface for a standing figure at FIGURE_SCALE. */
export const PELVIS = 105;

export const GAME_COLORS = {
  sky: '#0d1b2a',
  ground: '#1f2a44',
  groundTop: '#8d99ae',
  platform: '#3a506b',
  spike: '#ef476f',
  spring: '#ffd166',
  flag: '#06d6a0',
  door: '#ffd166',
};

export interface Level {
  n: 1 | 2 | 3;
  root: Node;
  flag?: Node;
  spring?: Spring;
  ledge?: {from: number; to: number; y: number};
  platform?: Node;
  ball?: Node;
  door?: Node;
  pit?: {from: number; to: number; floor: number};
  /** Where the hero starts and where the goal is (game units). */
  start: Vector2;
  goal: Vector2;
  /** Ground blocks (level 1 builds them piece by piece on screen). */
  grounds: Node[];
}

export interface Spring {
  node: Node;
  /** 0 = rest, 1 = fully squashed. */
  squash: ReturnType<typeof createSignal<number>>;
  top: Vector2;
}

/** Build level `n`. */
export function buildLevel(n: 1 | 2 | 3, props: NodeProps = {}): Level {
  const root = new Node(props);
  root.add(new Rect({width: G.w, height: G.h, fill: new Gradient({type: 'linear', from: [0, -360], to: [0, 360], stops: [{offset: 0, color: '#0b1324'}, {offset: 1, color: GAME_COLORS.sky}]})}));
  // Pixel stars: a fixed scatter.
  for (let i = 0; i < 18; i++) {
    root.add(new Rect({x: ((i * 397) % 1240) - 620, y: -330 + ((i * 211) % 420), width: 4, height: 4, fill: withAlpha('#ffffff', 0.35)}));
  }
  const level: Level = {n, root, start: new Vector2(-480, G.ground), goal: new Vector2(540, G.ground), grounds: []};
  const ground = (from: number, to: number) => level.grounds.push(block(root, from, to, G.ground, G.h / 2 - G.ground));

  if (n === 1) {
    ground(-640, -90);
    ground(70, 640);
    level.flag = flag(root, 330, G.ground);
    level.goal = new Vector2(330, G.ground);
  } else if (n === 2) {
    ground(-640, 640);
    level.ledge = {from: 230, to: 520, y: -40};
    block(root, 230, 520, -40, 40, GAME_COLORS.platform);
    level.spring = spring(root, 60, G.ground);
    level.flag = flag(root, 450, -40);
    level.goal = new Vector2(450, -40);
    level.ball = spikeBall(root);
    level.ball.position([700, G.ground - 28]);
  } else {
    ground(-640, -380);
    ground(380, 640);
    level.pit = {from: -380, to: 380, floor: 335};
    block(root, -380, 380, 335, 40, '#141b2d');
    // Spikes along the pit floor, except where the spring stands.
    for (let x = -370; x < 370; x += 28) {
      if (Math.abs(x + 60) < 36) continue;
      root.add(new Line({points: [[x, 335], [x + 14, 305], [x + 28, 335]], closed: true, fill: GAME_COLORS.spike, stroke: '#ffffff', lineWidth: 1.5}));
    }
    level.spring = spring(root, -60, 335);
    const p = new Node({position: [-160, 170]});
    p.add(new Rect({width: 140, height: 22, radius: 3, fill: GAME_COLORS.platform, stroke: GAME_COLORS.groundTop, lineWidth: TIER.detail}));
    p.add(new Line({points: [[-60, 0], [60, 0]], stroke: withAlpha('#ffffff', 0.25), lineWidth: 2, lineDash: [10, 8]}));
    root.add(p);
    level.platform = p;
    level.door = exitDoor(root, 480, G.ground);
    level.goal = new Vector2(480, G.ground);
  }
  return level;
}

function block(root: Node, from: number, to: number, top: number, depth: number, fill = GAME_COLORS.ground): Node {
  const n = new Node({});
  n.add(new Rect({x: (from + to) / 2, y: top + depth / 2, width: to - from, height: depth, fill}));
  n.add(new Line({points: [[from, top], [to, top]], stroke: GAME_COLORS.groundTop, lineWidth: TIER.structure}));
  // Brick seams, the game's own texture.
  for (let x = from + 32; x < to; x += 64) n.add(new Line({points: [[x, top + 6], [x, top + Math.min(depth, 40)]], stroke: withAlpha('#ffffff', 0.08), lineWidth: 2}));
  root.add(n);
  return n;
}

function flag(root: Node, x: number, y: number): Node {
  const n = new Node({position: [x, y]});
  n.add(new Line({points: [[0, 0], [0, -150]], stroke: '#e0e0e0', lineWidth: TIER.structure}));
  n.add(new Line({points: [[0, -150], [64, -128], [0, -106]], closed: true, fill: GAME_COLORS.flag}));
  n.add(new Rect({y: -4, width: 26, height: 8, fill: '#e0e0e0'}));
  root.add(n);
  return n;
}

function spring(root: Node, x: number, y: number): Spring {
  const squash = createSignal(0);
  const h = () => 44 * (1 - 0.6 * squash());
  const n = new Node({position: [x, y]});
  n.add(new Rect({y: -4, width: 56, height: 8, fill: '#6b6b78'}));
  n.add(
    new Line({
      points: () => Array.from({length: 7}, (_, i) => new Vector2(i % 2 ? 18 : -18, -8 - (h() - 14) * (i / 6))),
      stroke: GAME_COLORS.spring,
      lineWidth: TIER.structure,
      lineJoin: 'round',
    }),
  );
  n.add(new Rect({y: () => -h(), width: 60, height: 10, radius: 3, fill: GAME_COLORS.spring}));
  root.add(n);
  return {node: n, squash, top: new Vector2(x, y - 44)};
}

function spikeBall(root: Node): Node {
  const n = new Node({});
  for (let i = 0; i < 8; i++) {
    const a = (i * Math.PI) / 4;
    n.add(new Line({points: [[Math.cos(a) * 20, Math.sin(a) * 20], [Math.cos(a) * 36, Math.sin(a) * 36]], stroke: GAME_COLORS.spike, lineWidth: TIER.structure, lineCap: 'round'}));
  }
  n.add(new Circle({size: 46, fill: '#2b2d42', stroke: GAME_COLORS.spike, lineWidth: TIER.structure}));
  root.add(n);
  return n;
}

/** The exit: a glowing door with Spark's real room seen through it. */
function exitDoor(root: Node, x: number, y: number): Node {
  const n = new Node({position: [x, y]});
  n.add(new Circle({y: -110, size: 420, fill: new Gradient({type: 'radial', fromRadius: 0, toRadius: 210, stops: [{offset: 0, color: withAlpha(GAME_COLORS.door, 0.35)}, {offset: 1, color: withAlpha(GAME_COLORS.door, 0)}]})}));
  const frame = new Rect({y: -110, width: 130, height: 220, radius: [60, 60, 0, 0], clip: true, fill: '#f6e7c1'});
  frame.add(roomPicture({y: 40, scale: 0.42}));
  n.add(frame);
  n.add(new Rect({y: -110, width: 130, height: 220, radius: [60, 60, 0, 0], stroke: GAME_COLORS.door, lineWidth: TIER.figure}));
  root.add(n);
  return n;
}

/** A small picture of Spark's room (desk, monitor, empty chair): the way home. */
export function roomPicture(props: NodeProps = {}): Node {
  const n = new Node(props);
  const ink = '#5c4033';
  n.add(new Line({points: [[-200, 120], [200, 120]], stroke: ink, lineWidth: 6}));
  n.add(new Line({points: [[-40, 40], [180, 40]], stroke: ink, lineWidth: 8}));
  n.add(new Line({points: [[-30, 40], [-30, 120]], stroke: ink, lineWidth: 5}));
  n.add(new Line({points: [[170, 40], [170, 120]], stroke: ink, lineWidth: 5}));
  n.add(new Rect({x: 90, y: -40, width: 130, height: 80, radius: 6, fill: '#16161c', stroke: '#4a4a56', lineWidth: 4}));
  n.add(new Line({points: [[-120, 80], [-60, 80]], stroke: ink, lineWidth: 8}));
  n.add(new Line({points: [[-118, 80], [-128, -20]], stroke: ink, lineWidth: 8}));
  n.add(new Line({points: [[-110, 84], [-112, 120]], stroke: ink, lineWidth: 5}));
  n.add(new Line({points: [[-66, 84], [-64, 120]], stroke: ink, lineWidth: 5}));
  return n;
}

/** Hearts for the HUD. */
export function heart(props: NodeProps & {full: () => number}): Node {
  const {full, ...rest} = props;
  const n = new Node(rest);
  n.add(
    new Line({
      points: [[0, 14], [-16, -2], [-16, -10], [-8, -16], [0, -10], [8, -16], [16, -10], [16, -2]],
      closed: true,
      fill: () => (full() > 0.5 ? GAME_COLORS.spike : '#2b2d42'),
      stroke: '#ffffff',
      lineWidth: 2,
    }),
  );
  return n;
}

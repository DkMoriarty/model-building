import {Line, Node, NodeProps, Rect} from '@motion-canvas/2d';

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


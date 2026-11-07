import json, sys, math, numpy as np
from PIL import Image, ImageDraw
d = json.load(open(sys.argv[1])); P = d['palette']; cam = d['camera']; out = sys.argv[2]
zoom = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
W, H = 540, 675
def rgb(h): h = h.lstrip('#'); return np.array([int(h[i:i+2], 16) for i in (0, 2, 4)]) / 255
def qrot(q, v):
    w, x, y, z = q; u = np.array([x, y, z])
    return v + 2 * np.cross(u, np.cross(u, v) + w * v)
e = np.radians([50, 0, -35])
Rx = np.array([[1,0,0],[0,math.cos(e[0]),-math.sin(e[0])],[0,math.sin(e[0]),math.cos(e[0])]])
Rz = np.array([[math.cos(e[2]),-math.sin(e[2]),0],[math.sin(e[2]),math.cos(e[2]),0],[0,0,1]])
L = -(Rz @ Rx @ np.array([0,0,-1.0]))
C = np.array(cam['location']); T = np.array(cam['target'])
if len(sys.argv) > 4: T = np.array([0,0,float(sys.argv[4])]); C = np.array([C[0], C[1], float(sys.argv[4])])
fwd = (T - C); fwd /= np.linalg.norm(fwd); right = np.cross(fwd, [0,0,1]); right /= np.linalg.norm(right); up = np.cross(right, fwd)
f = cam['lens'] / 18 * zoom  # vertical half sensor 18mm (portrait fit)
tris = []
for o in d['objects']:
    V = np.array(o['v']).reshape(-1, 3)
    if o['q']: V = np.array([qrot(o['q'], v) for v in V])
    V = V + o['loc']
    base = rgb(P[o['key']])
    for face in o['f']:
        for k in range(1, len(face) - 1):
            p = V[[face[0], face[k], face[k+1]]]
            n = np.cross(p[1]-p[0], p[2]-p[0]); ln = np.linalg.norm(n)
            if ln == 0: continue
            n /= ln
            rel = p - C; z = rel @ fwd
            if np.any(z <= 0.05): continue
            if np.dot(n, p.mean(0) - C) > 0: n = -n  # double sided
            if o['toon']:
                fac = .955 * max(np.dot(n, L), 0)
                if fac < d['style']['band_split']:
                    if o['key'] in d.get('shadow', {}): c = rgb(d['shadow'][o['key']])
                    else: c = base * d['style']['shadow_amount']; c[2] = base[2]*(d['style']['shadow_amount']+.06); c[0] = max(0, c[0]-.03)
                elif o['hl'] and fac > .92: c = base * 1.12
                else: c = base
            else: c = base
            sx = (rel @ right) / z * f; sy = (rel @ up) / z * f
            pts = [(W/2 + a * H/2, H/2 - b * H/2) for a, b in zip(sx, sy)]
            tris.append((z.mean(), pts, tuple(int(min(1, x)*255) for x in c)))
img = Image.new('RGB', (W, H), tuple(int(x*255) for x in rgb(P['sky'])))
dr = ImageDraw.Draw(img)
for z, pts, c in sorted(tris, key=lambda t: -t[0]): dr.polygon(pts, fill=c)
img.save(out)

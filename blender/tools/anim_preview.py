"""Rough preview of any scene script that records its keyframes in a module-level ANIM dict.

Usage: python anim_preview.py <scene.py> <out_dir> <frame,frame,...> [--camera Camera] [--target Cam_target]
Runs the script on the bpy stand-ins (mock_blender.py), evaluates ANIM at each frame
(smoothstep between keys), and paints flat-shaded triangles with a painter's sort.
Needs numpy and Pillow. Layout and timing check only; not a render.
"""
import math, os, sys
here = os.path.dirname(os.path.abspath(__file__))
script, outdir, frames = sys.argv[1], sys.argv[2], [int(f) for f in sys.argv[3].split(',')]
cam_name = sys.argv[sys.argv.index('--camera') + 1] if '--camera' in sys.argv else 'Camera'
tgt_name = sys.argv[sys.argv.index('--target') + 1] if '--target' in sys.argv else 'Cam_target'
argv_saved = sys.argv; sys.argv = [script]
exec(open(os.path.join(here, 'mock_blender.py')).read())
import numpy as np
from PIL import Image, ImageDraw
ns = {'__name__': '__main__', '__file__': script}
exec(compile(open(script).read(), script, 'exec'), ns)
sys.argv = argv_saved
ANIM = ns.get('ANIM', {})
objs = list(bpy.data.objects); by_name = {o._d['name']: o for o in objs}

def quat_m(q):
    w, x, y, z = q
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
def eul_m(e):
    a, b, c = e
    Rx = np.array([[1,0,0],[0,math.cos(a),-math.sin(a)],[0,math.sin(a),math.cos(a)]])
    Ry = np.array([[math.cos(b),0,math.sin(b)],[0,1,0],[-math.sin(b),0,math.cos(b)]])
    Rz = np.array([[math.cos(c),-math.sin(c),0],[math.sin(c),math.cos(c),0],[0,0,1]])
    return Rz @ Ry @ Rx
def anim_value(name, path, f):
    keys = sorted([(fr, v) for fr, p, v in ANIM.get(name, []) if p == path], key=lambda t: t[0])
    if not keys: return None
    if f <= keys[0][0]: return np.array(keys[0][1])
    for (f0, a), (f1, b) in zip(keys, keys[1:]):
        if f0 <= f <= f1:
            t = 0 if f1 == f0 else (f - f0) / (f1 - f0); t = t * t * (3 - 2 * t)
            return np.array(a) + (np.array(b) - np.array(a)) * t
    return np.array(keys[-1][1])
def static(d, k, default):
    v = d.get(k)
    return default if v is None or type(v) is Stub else v
def local(o, f):
    d = o._d; n = d['name']
    loc = anim_value(n, 'location', f); loc = np.array(list(static(d, 'location', (0, 0, 0))), float) if loc is None else loc
    sc = anim_value(n, 'scale', f); S = np.ones(3) if sc is None else sc
    re = anim_value(n, 'rotation_euler', f)
    if re is not None: R = eul_m(re)
    elif static(d, 'rotation_mode', '') == 'QUATERNION' and static(d, 'rotation_quaternion', None) is not None:
        q = d['rotation_quaternion']; R = quat_m(q.q if hasattr(q, 'q') else q)
    else:
        e = static(d, 'rotation_euler', None); R = eul_m(e) if e is not None else np.eye(3)
    M = np.eye(4); M[:3, :3] = R @ np.diag(S); M[:3, 3] = loc; return M
def world(o, f):
    M = local(o, f); p = o._d.get('parent')
    while p is not None and type(p) is not Stub:
        M = local(p, f) @ M; p = p._d.get('parent')
    return M
def rgb(h): h = h.lstrip('#'); return np.array([int(h[i:i+2], 16) for i in (0, 2, 4)]) / 255

geo = []
for o in objs:
    me = o._d.get('data')
    if not isinstance(me, Mesh) or not me._d['faces']: continue
    m = me._d['materials'][0]; it = m._d.get('_items', {})
    V = np.array(me._d['verts'], float)
    T = np.array([[f[0], f[k], f[k+1]] for f in me._d['faces'] for k in range(1, len(f) - 1)])
    geo.append((o, V, T, rgb(it.get('preview', '#888888')), it.get('emit', 0) > 0))
light = np.array([0.45, -0.55, 0.7]); light /= np.linalg.norm(light)
W, H = 960, 540
lens = static(by_name[cam_name]._d['data']._d, 'lens', 35)
for f in frames:
    C = world(by_name[cam_name], f)[:3, 3]; T_ = world(by_name[tgt_name], f)[:3, 3]
    fwd = T_ - C; fwd /= np.linalg.norm(fwd); right = np.cross(fwd, [0, 0, 1]); right /= np.linalg.norm(right); up = np.cross(right, fwd)
    foc = lens / 18.0
    polys = []
    for o, V, T, col, emit in geo:
        M = world(o, f)
        if np.abs(np.linalg.det(M[:3, :3])) < 1e-9: continue
        P = V @ M[:3, :3].T + M[:3, 3]; tri = P[T]; rel = tri - C; z = rel @ fwd
        ok = np.all(z > 0.3, axis=1)
        if not ok.any(): continue
        tri, rel, z = tri[ok], rel[ok], z[ok]
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); ln = np.linalg.norm(n, axis=1); g = ln > 0
        tri, rel, z, n, ln = tri[g], rel[g], z[g], n[g], ln[g]; n = n / ln[:, None]
        flip = np.sum(n * (tri.mean(1) - C), axis=1) > 0; n[flip] *= -1
        px = W / 2 + (rel @ right) / z * foc * W / 2; py = H / 2 - (rel @ up) / z * foc * W / 2
        shade = np.ones(len(z)) * 1.1 if emit else 0.28 + 0.8 * np.clip(n @ light, 0, 1)
        cols = np.clip(col[None, :] * shade[:, None], 0, 1)
        vis = (px.max(1) > -50) & (px.min(1) < W + 50) & (py.max(1) > -50) & (py.min(1) < H + 50)
        for i in np.nonzero(vis)[0]:
            polys.append((z[i].mean(), [(px[i, k], py[i, k]) for k in range(3)], tuple((cols[i] * 255).astype(int))))
    img = Image.new('RGB', (W, H), (28, 33, 40)); d = ImageDraw.Draw(img)
    for _, pts, c in sorted(polys, key=lambda t: -t[0]): d.polygon(pts, fill=c)
    caps = [c for c in ns.get('CAPTIONS', []) if c[0] <= f < c[1]]
    for c in caps[-1:]:
        d.rectangle((10, H - 58, 10 + 8 * max(len(c[2]), len(c[3])), H - 10), fill=(0, 0, 0))
        d.text((16, H - 52), c[2], fill=(255, 255, 255)); d.text((16, H - 32), c[3], fill=(200, 200, 200))
    d.text((W - 90, 10), f'frame {f}', fill=(255, 255, 255))
    img.save(os.path.join(outdir, f'frame_{f:04d}.png')); print('frame', f, len(polys), 'tris')

"""Run space_dock.py on the Blender stand-ins, then rasterize camera shots."""
import sys, math, random
sys.argv = [sys.argv[0]] + sys.argv[1:]
script, outdir = sys.argv[1], sys.argv[2]
shots = [s.split(':') for s in sys.argv[3].split(',')]  # camera:frame
exec(open(__file__.replace('space_preview.py', 'mock_blender.py')).read())
import numpy as np
from PIL import Image, ImageDraw
ns = {'__name__': '__main__', '__file__': script}
exec(compile(open(script).read(), script, 'exec'), ns)

objs = list(bpy.data.objects)
by_name = {o._d['name']: o for o in objs}

def quat_m(q):
    w, x, y, z = q
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
def eul_m(e):
    a, b, c = e
    Rx = np.array([[1,0,0],[0,math.cos(a),-math.sin(a)],[0,math.sin(a),math.cos(a)]])
    Ry = np.array([[math.cos(b),0,math.sin(b)],[0,1,0],[-math.sin(b),0,math.cos(b)]])
    Rz = np.array([[math.cos(c),-math.sin(c),0],[math.sin(c),math.cos(c),0],[0,0,1]])
    return Rz @ Ry @ Rx
def interp(keys, f):
    for (f0, a), (f1, b) in zip(keys, keys[1:]):
        if f0 <= f <= f1:
            t = (f - f0) / max(f1 - f0, 1); t = t * t * (3 - 2 * t)
            return [x + (y - x) * t for x, y in zip(a, b)]
    return list(keys[-1][1]) if f > keys[-1][0] else list(keys[0][1])

def local(o, f):
    d = o._d; n = d['name']
    loc = list(d.get('location', (0, 0, 0))); R = np.eye(3); S = np.array(d.get('scale', (1, 1, 1)) if not isinstance(d.get('scale'), Stub) else (1,1,1), float)
    q = d.get('rotation_quaternion'); mode = d.get('rotation_mode')
    if mode == 'QUATERNION' and q is not None and not isinstance(q, Stub): R = quat_m(q.q if hasattr(q, 'q') else q)
    elif 'rotation_euler' in d and not isinstance(d['rotation_euler'], Stub): R = eul_m(d['rotation_euler'])
    if n == 'Shuttle':
        k = ns['SHUTTLE_KEYS']
        loc = interp([(a, list(b)) for a, b, c in k], f); R = eul_m(interp([(a, list(c)) for a, b, c in k], f))
    if n.startswith('Passenger'):
        i = int(n[9:]); path = ns['passenger_paths']()[i]
        loc = interp([(a, list(b)) for a, b in path], f)
        S = np.ones(3) if f <= path[-1][0] else np.zeros(3) + 1e-3
    if n == 'Station_ring': R = eul_m((0, 0, math.radians(40) * f / 720))
    if n == 'Ramp_pivot':
        last = max(p[-1][0] for p in ns['passenger_paths']())
        a = ns['RAMP_OPEN'] if f < last + 4 else (ns['RAMP_CLOSED'] if f > last + 34 else ns['RAMP_OPEN'] + (ns['RAMP_CLOSED'] - ns['RAMP_OPEN']) * (f - last - 4) / 30)
        R = eul_m((a, 0, 0))
    if n.startswith('Gear'): S = np.ones(3) if f < ns['GEAR_UP'][1] else np.zeros(3) + 1e-3
    if n.startswith('Plume'):
        s = interp([(a, [b]) for a, b in ns['PLUME_KEYS']], f)[0]
        S = np.array([1, 1, s])
    M = np.eye(4); M[:3, :3] = R @ np.diag(S); M[:3, 3] = list(loc); return M
def world(o, f):
    M = local(o, f); p = o._d.get('parent')
    while p is not None and type(p) is not Stub:
        M = local(p, f) @ M; p = p._d.get('parent')
    return M

def rgb(h): h = h.lstrip('#'); return np.array([int(h[i:i+2], 16) for i in (0, 2, 4)]) / 255
star = np.array(ns['STAR_POS'].__iter__().__class__ and list(ns['STAR_POS']))
sun = star / np.linalg.norm(star)
W, H = 960, 540
rs = random.Random(3)
stars = [(rs.uniform(0, W), rs.uniform(0, H), rs.uniform(0.3, 1)) for _ in range(500)]

# Pre-triangulate meshes
geo = []
for o in objs:
    me = o._d.get('data')
    if not isinstance(me, Mesh) or not me._d['faces']: continue
    m = me._d['materials'][0]; it = m._d.get('_items', {})
    name = m._d['name']
    if name in ('Atmosphere', 'Corona'): continue
    V = np.array(me._d['verts'], float)
    T = np.array([[f[0], f[k], f[k+1]] for f in me._d['faces'] for k in range(1, len(f) - 1)])
    emit = it.get('emit', 0) > 0 or name in ('Strobe', 'Plume', 'M_plume', 'Engine_core')
    geo.append((o, V, T, rgb(it.get('preview', '#888888')), emit, name))

cams = {c[0]: c for c in ns['CAMERAS']}
for cname, fr in shots:
    f = int(fr); name, start, loc, target, lens, parent = cams[cname]
    C = np.array(list(loc), float)
    if parent == 'Shuttle': C = (world(by_name['Shuttle'], f) @ np.array([*C, 1]))[:3]
    T_ = world(by_name['Shuttle'], f)[:3, 3] if target == 'Shuttle' else np.array(list(target), float)
    fwd = T_ - C; fwd /= np.linalg.norm(fwd); right = np.cross(fwd, [0, 0, 1]); right /= np.linalg.norm(right); up = np.cross(right, fwd)
    foc = lens / 18.0  # 36mm sensor width -> horizontal half = 18mm
    polys = []
    for o, V, T, col, emit, mname in geo:
        if mname in ('Engine_core',) and not (252 < f < 700): emit = False
        M = world(o, f)
        P = V @ M[:3, :3].T + M[:3, 3]
        tri = P[T]
        rel = tri - C
        z = rel @ fwd
        ok = np.all(z > 0.5, axis=1)
        if not ok.any(): continue
        tri, rel, z = tri[ok], rel[ok], z[ok]
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        ln = np.linalg.norm(n, axis=1); good = ln > 0
        tri, rel, z, n, ln = tri[good], rel[good], z[good], n[good], ln[good]
        n = n / ln[:, None]
        flip = np.sum(n * (tri.mean(1) - C), axis=1) > 0; n[flip] *= -1
        sx = (rel @ right) / z * foc; sy = (rel @ up) / z * foc
        px = W / 2 + sx * W / 2; py = H / 2 - sy * W / 2
        if mname in ('Plume', 'M_plume') and (o._d['name'].startswith('Plume') and not (252 < f < 700)): continue
        if emit: shade = np.ones(len(z)) * 1.25
        else: shade = 0.12 + 0.95 * np.clip(n @ sun, 0, 1)
        cols = np.clip(col[None, :] * shade[:, None], 0, 1)
        vis = (px.max(1) > -50) & (px.min(1) < W + 50) & (py.max(1) > -50) & (py.min(1) < H + 50)
        for i in np.nonzero(vis)[0]:
            polys.append((z[i].mean(), [(px[i, k], py[i, k]) for k in range(3)], tuple((cols[i] * 255).astype(int))))
    img = Image.new('RGB', (W, H), (4, 5, 12)); d = ImageDraw.Draw(img)
    for x, y, b in stars: d.point((x, y), fill=(int(255 * b),) * 3)
    for _, pts, c in sorted(polys, key=lambda t: -t[0]): d.polygon(pts, fill=c)
    img.save(f'{outdir}/{cname}_{f}.png'); print(cname, f, len(polys), 'tris')

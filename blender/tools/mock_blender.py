"""Run a Blender character script against minimal bpy/bmesh/mathutils stand-ins and export meshes as JSON."""
import sys, types, math, json
import numpy as np

# ---------------- mathutils ----------------
class Vector:
    def __init__(s, v=(0, 0, 0)): s._v = [float(a) for a in v]
    x = property(lambda s: s._v[0], lambda s, a: s._v.__setitem__(0, float(a)))
    y = property(lambda s: s._v[1], lambda s, a: s._v.__setitem__(1, float(a)))
    z = property(lambda s: s._v[2], lambda s, a: s._v.__setitem__(2, float(a)))
    def __iter__(s): return iter(s._v)
    def __len__(s): return len(s._v)
    def __getitem__(s, i): return s._v[i]
    def __add__(s, o): return Vector([a + b for a, b in zip(s, o)])
    __radd__ = __add__
    def __sub__(s, o): return Vector([a - b for a, b in zip(s, o)])
    def __rsub__(s, o): return Vector([b - a for a, b in zip(s, o)])
    def __mul__(s, k): return Vector([a * k for a in s])
    __rmul__ = __mul__
    def __neg__(s): return s * -1
    @property
    def length(s): return math.sqrt(sum(a * a for a in s))
    def normalized(s):
        L = s.length
        return Vector([a / L for a in s]) if L else Vector(s)
    def copy(s): return Vector(s)
    def to_track_quat(s, track, up):
        t = np.array(s.normalized()._v)
        sign = -1 if track.startswith('-') else 1
        ax = 'XYZ'.index(track[-1])
        world_up = np.array([0, 0, 1.0])
        u = world_up - t * np.dot(t, world_up)
        if np.linalg.norm(u) < 1e-6:
            u = np.array([0, 1.0, 0]) - t * t[1]
        u /= np.linalg.norm(u)
        cols = [None, None, None]
        cols[ax] = t * sign
        uax = 'XYZ'.index(up)
        cols[uax] = u
        rem = 3 - ax - uax
        # right-handed: X = Y x Z, Y = Z x X, Z = X x Y
        a, b = (rem + 1) % 3, (rem + 2) % 3
        cols[rem] = np.cross(cols[a], cols[b])
        return Quaternion.from_matrix(np.column_stack(cols))

class Quaternion:
    def __init__(s, a=(1, 0, 0, 0), angle=None):
        if angle is not None:
            ax = np.array(list(a), float); ax /= np.linalg.norm(ax)
            h = angle / 2
            s.q = np.array([math.cos(h), *(ax * math.sin(h))])
        else:
            s.q = np.array(list(a), float)
    @staticmethod
    def from_matrix(m):
        tr = m[0, 0] + m[1, 1] + m[2, 2]
        if tr > 0:
            S = math.sqrt(tr + 1) * 2; w = .25 * S
            x = (m[2, 1] - m[1, 2]) / S; y = (m[0, 2] - m[2, 0]) / S; z = (m[1, 0] - m[0, 1]) / S
        elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
            S = math.sqrt(1 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
            w = (m[2, 1] - m[1, 2]) / S; x = .25 * S; y = (m[0, 1] + m[1, 0]) / S; z = (m[0, 2] + m[2, 0]) / S
        elif m[1, 1] > m[2, 2]:
            S = math.sqrt(1 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
            w = (m[0, 2] - m[2, 0]) / S; x = (m[0, 1] + m[1, 0]) / S; y = .25 * S; z = (m[1, 2] + m[2, 1]) / S
        else:
            S = math.sqrt(1 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
            w = (m[1, 0] - m[0, 1]) / S; x = (m[0, 2] + m[2, 0]) / S; y = (m[1, 2] + m[2, 1]) / S; z = .25 * S
        return Quaternion((w, x, y, z))
    def __matmul__(s, o):
        w1, x1, y1, z1 = s.q; w2, x2, y2, z2 = o.q
        return Quaternion((w1*w2 - x1*x2 - y1*y2 - z1*z2, w1*x2 + x1*w2 + y1*z2 - z1*y2,
                           w1*y2 - x1*z2 + y1*w2 + z1*x2, w1*z2 + x1*y2 - y1*x2 + z1*w2))
    def to_euler(s): return (0, 0, 0)

class Matrix:
    def __init__(s, m): s.m = np.array(m, float)
    @staticmethod
    def Diagonal(d): return Matrix(np.diag(list(d)))
    @staticmethod
    def Rotation(angle, size, axis):
        c, s_ = math.cos(angle), math.sin(angle)
        R = {'X': [[1, 0, 0], [0, c, -s_], [0, s_, c]], 'Y': [[c, 0, s_], [0, 1, 0], [-s_, 0, c]],
             'Z': [[c, -s_, 0], [s_, c, 0], [0, 0, 1]]}[axis]
        m = np.eye(4); m[:3, :3] = R; return Matrix(m)
    @staticmethod
    def Translation(t):
        m = np.eye(4); m[:3, 3] = list(t); return Matrix(m)
    def __matmul__(s, o): return Matrix(s.m @ o.m)
    def apply(s, v):
        r = s.m @ np.array([*v, 1.0]); return r[:3]

mu = types.ModuleType('mathutils'); mu.Vector, mu.Quaternion, mu.Matrix = Vector, Quaternion, Matrix

# ---------------- bmesh ----------------
class BMVert:
    def __init__(s, co): s.co = Vector(co)
class BMesh:
    def __init__(s): s.verts_l, s.faces_l = [], []
    @property
    def verts(s):
        bm = s
        class VS(list):
            def new(self, co):
                v = BMVert(co); bm.verts_l.append(v); return v
        return VS(s.verts_l)
    @property
    def faces(s):
        bm = s
        class FS(list):
            def new(self, vs):
                bm.faces_l.append(list(vs)); return vs
        return FS(s.faces_l)
    def to_mesh(s, me):
        idx = {id(v): i for i, v in enumerate(s.verts_l)}
        me.verts = [list(v.co) for v in s.verts_l]
        me.faces = [[idx[id(v)] for v in f] for f in s.faces_l]
    def free(s): pass

def _outward(bm, start_f):
    # closed-ish convex primitive: flip all new faces if they point inward
    fs = bm.faces_l[start_f:]
    if not fs: return
    c = np.mean([v.co._v for v in bm.verts_l], axis=0); score = 0
    for f in fs:
        p = [np.array(v.co._v) for v in f]
        n = np.cross(p[1] - p[0], p[2] - p[0])
        score += np.dot(n, np.mean(p, axis=0) - c)
    if score < 0:
        for f in fs: f.reverse()

def create_uvsphere(bm, u_segments, v_segments, radius, matrix=None):
    sf = len(bm.faces_l)
    top = BMVert((0, 0, radius)); bot = BMVert((0, 0, -radius))
    rings = []
    for i in range(1, v_segments):
        th = math.pi * i / v_segments
        rings.append([BMVert((radius * math.sin(th) * math.cos(2 * math.pi * j / u_segments),
                              radius * math.sin(th) * math.sin(2 * math.pi * j / u_segments),
                              radius * math.cos(th))) for j in range(u_segments)])
    bm.verts_l += [top] + [v for r in rings for v in r] + [bot]
    U = u_segments
    for j in range(U):
        bm.faces_l.append([top, rings[0][j], rings[0][(j + 1) % U]])
        bm.faces_l.append([bot, rings[-1][(j + 1) % U], rings[-1][j]])
    for i in range(len(rings) - 1):
        for j in range(U):
            bm.faces_l.append([rings[i][j], rings[i + 1][j], rings[i + 1][(j + 1) % U], rings[i][(j + 1) % U]])
    _outward(bm, sf)
    if matrix is not None: transform(bm, matrix, [top] + [v for r in rings for v in r] + [bot])

def create_cone(bm, cap_ends, cap_tris, segments, radius1, radius2, depth, matrix=None):
    sf = len(bm.faces_l); sv = len(bm.verts_l)
    ring = lambda r, z: [BMVert((r * math.cos(2 * math.pi * j / segments), r * math.sin(2 * math.pi * j / segments), z)) for j in range(segments)]
    b = ring(radius1, -depth / 2)
    t = ring(radius2, depth / 2) if radius2 > 0 else [BMVert((0, 0, depth / 2))]
    bm.verts_l += b + t
    S = segments
    for j in range(S):
        if len(t) == 1: bm.faces_l.append([b[j], b[(j + 1) % S], t[0]])
        else: bm.faces_l.append([b[j], b[(j + 1) % S], t[(j + 1) % S], t[j]])
    if cap_ends:
        bm.faces_l.append(list(reversed(b)))
        if len(t) > 1: bm.faces_l.append(list(t))
    if cap_ends: _outward(bm, sf)
    else:
        # open tube: point side faces away from the axis
        f = bm.faces_l[sf]; p = [np.array(v.co._v) for v in f]
        n = np.cross(p[1] - p[0], p[2] - p[0]); m = np.mean(p, axis=0); m[2] = 0
        if np.dot(n, m) < 0:
            for f in bm.faces_l[sf:]: f.reverse()
    if matrix is not None: transform(bm, matrix, bm.verts_l[sv:])

def create_cube(bm, size, matrix=None):
    sf = len(bm.faces_l); sv = len(bm.verts_l); h = size / 2
    V = [BMVert((x, y, z)) for x in (-h, h) for y in (-h, h) for z in (-h, h)]
    bm.verts_l += V
    for f in ([0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]):
        bm.faces_l.append([V[i] for i in f])
    _outward(bm, sf)
    if matrix is not None: transform(bm, matrix, bm.verts_l[sv:])

def delete(bm, geom, context):
    dead = set(map(id, geom))
    bm.verts_l = [v for v in bm.verts_l if id(v) not in dead]
    bm.faces_l = [f for f in bm.faces_l if not any(id(v) in dead for v in f)]

def transform(bm, matrix, verts):
    for v in verts: v.co = Vector(matrix.apply(v.co._v))

bmm = types.ModuleType('bmesh'); bmm.new = BMesh
bmm.ops = types.SimpleNamespace(create_uvsphere=create_uvsphere, create_cone=create_cone, create_cube=create_cube,
                                delete=delete, transform=transform, recalc_face_normals=lambda bm, faces: None)

# ---------------- bpy ----------------
class Stub:
    def __init__(s, name=''): object.__setattr__(s, '_d', {'name': name})
    def __getattr__(s, k):
        if k.startswith('__'): raise AttributeError(k)
        return s._d.setdefault(k, Stub())
    def __setattr__(s, k, v): s._d[k] = v
    def __call__(s, *a, **k): return Stub()
    def __getitem__(s, k): return s._d.setdefault('_items', {}).setdefault(k, Stub())
    def __setitem__(s, k, v): s._d.setdefault('_items', {})[k] = v
    def __iter__(s): return iter([])
    def __contains__(s, k): return False
    def __bool__(s): return True

class Mesh(Stub):
    def __init__(s, name):
        super().__init__(name); s._d.update(materials=[], smooth=False, verts=[], faces=[])
    def shade_smooth(s): s._d['smooth'] = True
class Obj(Stub):
    def __init__(s, name, data):
        super().__init__(name); s._d.update(data=data, mods=[], location=(0, 0, 0), rotation_quaternion=None)
        s._d['modifiers'] = types.SimpleNamespace(new=lambda n, t: s._d['mods'].append(Stub(n)) or s._d['mods'][-1])
class Coll(Stub):
    def __init__(s, name):
        super().__init__(name)
        class OL(list):
            def link(self, o): self.append(o)
        s._d['objs'] = s._d['objects'] = OL()
def blocks(factory):
    return types.SimpleNamespace(new=factory, remove=lambda *a, **k: None, __iter__=None)
class Blocks(list):
    def __init__(s, f): super().__init__(); s.f = f
    def new(s, *a):
        o = s.f(*a); s.append(o); return o
    def remove(s, *a, **k): pass
    def get(s, name):
        for o in s:
            if o._d.get('name') == name: return o
        return None
    def __getitem__(s, k):
        if isinstance(k, str):
            o = s.get(k)
            if o is None: raise KeyError(k)
            return o
        return list.__getitem__(s, k)

COLLS = []
bpy = types.ModuleType('bpy')
bpy.data = types.SimpleNamespace(
    objects=Blocks(lambda n, d: Obj(n, d)), meshes=Blocks(Mesh), materials=Blocks(lambda n: Stub(n)),
    lights=Blocks(lambda n, t: Stub(n)), cameras=Blocks(lambda n: Stub(n)), worlds=Blocks(lambda n: Stub(n)),
    collections=Blocks(lambda n: COLLS.append(Coll(n)) or COLLS[-1]))
bpy.data.materials = Blocks(lambda n: Stub(n))
bpy.data.curves = Blocks(lambda n, t: Stub(n))
bpy.context = types.SimpleNamespace(scene=Stub('Scene'))
bpy.ops = Stub(); bpy.path = types.SimpleNamespace(abspath=lambda p: p)

sys.modules.update(bpy=bpy, bmesh=bmm, mathutils=mu)


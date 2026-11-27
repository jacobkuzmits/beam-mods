"""Small procedural-mesh toolkit shared by the beam-mods generators.

Parts are lists of vertices + triangles with a material slot name; finalize()
welds, drops degenerate triangles and computes auto-smoothed normals.
"""
import math

N_AROUND = 96


class Part:
    def __init__(self, mat):
        self.mat = mat
        self.v = []
        self.f = []

    def add(self, p):
        self.v.append(p)
        return len(self.v) - 1


# ---------------------------------------------------------------- vectors
def sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def dot(a, b): return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def norm(a):
    l = math.sqrt(dot(a, a))
    return (a[0]/l, a[1]/l, a[2]/l) if l > 1e-15 else (0.0, 0.0, 0.0)


# ---------------------------------------------------------------- builders
def lathe(mat, profile, n=N_AROUND, cy=0.0, cz=0.0, phase=0.0):
    """Revolve a closed (x, r) profile loop around an axis parallel to X."""
    p = Part(mat)
    np_ = len(profile)
    idx = []
    for i in range(n):
        a = phase + 2*math.pi*i/n
        ca, sa = math.cos(a), math.sin(a)
        idx.append([p.add((x, cy + r*ca, cz + r*sa)) for x, r in profile])
    for i in range(n):
        i2 = (i + 1) % n
        for j in range(np_):
            j2 = (j + 1) % np_
            a, b, c, d = idx[i][j], idx[i][j2], idx[i2][j2], idx[i2][j]
            p.f += [(a, b, c), (a, c, d)]
    return p


def loft(mat, sections):
    """Skin a list of closed 3D loops (equal point counts) and cap both ends."""
    p = Part(mat)
    rows = [[p.add(q) for q in s] for s in sections]
    k = len(sections[0])
    for r0, r1 in zip(rows, rows[1:]):
        for j in range(k):
            j2 = (j + 1) % k
            p.f += [(r0[j], r0[j2], r1[j2]), (r0[j], r1[j2], r1[j])]
    for row, sec in ((rows[0], sections[0]), (rows[-1], sections[-1])):
        c = tuple(sum(q[i] for q in sec)/k for i in range(3))
        ci = p.add(c)
        for j in range(k):
            p.f.append((ci, row[j], row[(j+1) % k]))
    return p


def orient_outward(p):
    """Flip a closed part's triangles if its signed volume is negative."""
    c = tuple(sum(v[i] for v in p.v)/len(p.v) for i in range(3))
    vol = 0.0
    for a, b, d in p.f:
        vol += dot(sub(p.v[a], c), cross(sub(p.v[b], c), sub(p.v[d], c)))
    if vol < 0:
        p.f = [(a, d, b) for a, b, d in p.f]


# ---------------------------------------------------------------- finalize
def finalize(parts, smooth_deg=35.0):
    """Weld, drop degenerate tris, auto-smooth normals.

    Returns {mat: (positions, normals, tris)} with per-material vertex arrays.
    """
    cos_t = math.cos(math.radians(smooth_deg))
    out = {}
    for p in parts:
        # weld coincident vertices (lathe poles etc.)
        key2i, remap, pos = {}, [], []
        for v in p.v:
            k = (round(v[0], 7), round(v[1], 7), round(v[2], 7))
            if k not in key2i:
                key2i[k] = len(pos)
                pos.append(v)
            remap.append(key2i[k])
        tris, fn, fa = [], [], []
        for a, b, c in p.f:
            a, b, c = remap[a], remap[b], remap[c]
            if a == b or b == c or a == c:
                continue
            n = cross(sub(pos[b], pos[a]), sub(pos[c], pos[a]))
            area = math.sqrt(dot(n, n))
            if area < 1e-12:
                continue
            tris.append((a, b, c))
            fa.append(n)              # area-weighted
            fn.append(norm(n))
        v2f = [[] for _ in pos]
        for fi, t in enumerate(tris):
            for v in t:
                v2f[v].append(fi)
        P, N, T = out.setdefault(p.mat, ([], [], []))
        vkey = {}
        for fi, t in enumerate(tris):
            idx = []
            for v in t:
                acc = [0.0, 0.0, 0.0]
                for g in v2f[v]:
                    if dot(fn[fi], fn[g]) >= cos_t:
                        acc[0] += fa[g][0]; acc[1] += fa[g][1]; acc[2] += fa[g][2]
                nn = norm(acc)
                k = (v, round(nn[0], 4), round(nn[1], 4), round(nn[2], 4))
                if k not in vkey:
                    vkey[k] = len(P)
                    P.append(pos[v])
                    N.append(nn)
                idx.append(vkey[k])
            T.append(tuple(idx))
    return out


def grid(mat, rows, closed_u=False, closed_v=False):
    """Quad-grid surface from rows[i][j] points (i: v direction, j: u direction)."""
    p = Part(mat)
    idx = [[p.add(q) for q in row] for row in rows]
    nv, nu = len(rows), len(rows[0])
    for i in range(nv - 1 + (1 if closed_v else 0)):
        i2 = (i + 1) % nv
        for j in range(nu - 1 + (1 if closed_u else 0)):
            j2 = (j + 1) % nu
            a, b, c, d = idx[i][j], idx[i][j2], idx[i2][j2], idx[i2][j]
            p.f += [(a, b, c), (a, c, d)]
    return p


def merge(mat, parts):
    out = Part(mat)
    for q in parts:
        base = len(out.v)
        out.v += q.v
        out.f += [(a + base, b + base, c + base) for a, b, c in q.f]
    return out


def flip(p):
    p.f = [(a, c, b) for a, b, c in p.f]
    return p

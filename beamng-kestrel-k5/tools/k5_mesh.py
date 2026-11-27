"""Procedural mesh for the Kestrel K5 vintage 5-spoke wheel.

Coordinate convention (matches the Vintage Parts wheels pack meshes):
  * meters, Z-up COLLADA
  * the axle runs along X, the outboard (spoke) face points to +X
  * Y/Z are the radial plane
"""
import math

PCD_R = 0.05715          # 5 x 114.3 mm bolt circle
HUB_R = 0.080            # radius of the raised center boss
SHELL_T = 0.0045         # rim shell thickness
N_AROUND = 96            # segments around the barrel / hub
N_SPOKES = 5

# Per-size layout measured from the pack's CN505 meshes so the new wheel
# sits exactly where those parts' (already tuned) jbeam values expect it.
#   D: rim diameter (in), W: width (in), xi/xo: inboard/outboard flange x,
#   rf: flange top radius, m: hub mounting-face x
SIZES = {
    "15x8":  dict(D=15, W=8,  xi=-0.1065, xo=0.1115, rf=0.2067, m=0.0221),
    "15x9":  dict(D=15, W=9,  xi=-0.1203, xo=0.1226, rf=0.2067, m=0.0333),
    "15x10": dict(D=15, W=10, xi=-0.1373, xo=0.1398, rf=0.2067, m=0.0307),
    "16x8":  dict(D=16, W=8,  xi=-0.1222, xo=0.1066, rf=0.2157, m=0.0126),
    "18x8":  dict(D=18, W=8,  xi=-0.1109, xo=0.1155, rf=0.2387, m=0.0114),
    "18x9":  dict(D=18, W=9,  xi=-0.1195, xo=0.1249, rf=0.2387, m=0.0208),
    "18x10": dict(D=18, W=10, xi=-0.1359, xo=0.1347, rf=0.2424, m=0.0131),
}


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


# ---------------------------------------------------------------- wheel
def barrel_profile(s):
    xi, xo, rf = s["xi"], s["xo"], s["rf"]
    rb = s["D"] * 0.0127
    t = SHELL_T
    xw1 = xi + 0.040
    xw2 = xw1 + 0.040
    outer = [
        (xi, rf-0.004), (xi+0.0015, rf-0.001), (xi+0.004, rf), (xi+0.0065, rf-0.001),
        (xi+0.008, rf-0.004), (xi+0.009, rb+0.002), (xi+0.011, rb), (xi+0.026, rb),
        (xi+0.030, rb-0.003), (xw1, rb-0.020), (xw2, rb-0.020), (xw2+0.010, rb-0.002),
        (xw2+0.013, rb), (xo-0.011, rb), (xo-0.009, rb+0.002), (xo-0.008, rf-0.004),
        (xo-0.0065, rf-0.001), (xo-0.004, rf), (xo-0.0015, rf-0.001), (xo, rf-0.004),
    ]
    face = [(xo-0.0003, rf-0.008), (xo-0.0012, rb-t+0.0025)]
    inner = [
        (xo-0.003, rb-t), (xo-0.012, rb-t), (xo-0.0135, rb-t-0.002),
        (xw2+0.013, rb-t-0.002), (xw2+0.010, rb-t-0.004), (xw2, rb-0.020-t),
        (xw1, rb-0.020-t), (xi+0.030, rb-t-0.003), (xi+0.026, rb-t-0.002),
        (xi+0.004, rb-t-0.002), (xi, rb-t),
    ]
    return outer + face + inner, rb - t - 0.002


def spoke_front_x(s, r, r_end):
    m = s["m"]
    x_hub = m + 0.027
    x_rim = min(s["xo"] - 0.018, m + 0.075)
    u = min(max((r - HUB_R) / (r_end - HUB_R), 0.0), 1.0)
    return x_hub + (x_rim - x_hub) * (0.35*u + 0.65*u*u), u


def spoke(s, theta, r_inner):
    r0 = 0.062
    r_end = r_inner + 0.0032          # bury the tip in the rim shell
    ct, st = math.cos(theta), math.sin(theta)
    secs = []
    n = 26
    for i in range(n + 1):
        # cosine spacing: dense at both ends where the fillets are
        f = 0.5 - 0.5*math.cos(math.pi*i/n)
        r = r0 + (r_end - r0)*f
        xf, u = spoke_front_x(s, r, r_end)
        depth = 0.026 - 0.006*u
        xb = xf - depth
        w = 0.042 + 0.008*u + 0.028*math.exp(-(1-u)/0.07) + 0.012*math.exp(-u/0.12)
        hw = w/2
        hf = hw*0.85
        bev = 0.0035
        prof = [(-hw, xb), (-hf, xf-bev), (-hf+bev, xf), (0.0, xf+0.0035),
                (hf-bev, xf), (hf, xf-bev), (hw, xb)]
        sec = []
        for sd, x in prof:
            a = math.sqrt(max(r*r - sd*sd, 1e-9))
            sec.append((x, a*ct - sd*st, a*st + sd*ct))
        secs.append(sec)
    return loft("face", secs)


def build_wheel(size):
    s = SIZES[size]
    m = s["m"]
    parts = []

    prof, r_inner = barrel_profile(s)
    parts.append(lathe("lip", prof))

    for k in range(N_SPOKES):
        parts.append(spoke(s, math.pi/2 + 2*math.pi*k/N_SPOKES, r_inner))

    hub = [(m, 0.0), (m, HUB_R-0.003), (m+0.003, HUB_R), (m+0.024, HUB_R),
           (m+0.029, HUB_R-0.005), (m+0.031, HUB_R-0.012), (m+0.031, 0.040), (m+0.031, 0.0)]
    parts.append(lathe("face", hub))

    cap = [(m+0.030, 0.0), (m+0.030, 0.036), (m+0.034, 0.0365), (m+0.037, 0.034),
           (m+0.043, 0.028), (m+0.047, 0.020), (m+0.0495, 0.010), (m+0.050, 0.0)]
    parts.append(lathe("chrome", cap, n=64))

    x0, x1 = m+0.030, m+0.044
    nut = [(x0, 0.0), (x0, 0.011), (x1-0.0025, 0.011), (x1, 0.0085),
           (x1+0.003, 0.0045), (x1+0.0038, 0.0)]
    for k in range(N_SPOKES):
        a = math.pi/2 + 2*math.pi*k/N_SPOKES + math.pi/N_SPOKES
        parts.append(lathe("chrome", nut, n=6, cy=PCD_R*math.cos(a), cz=PCD_R*math.sin(a), phase=a))

    for p in parts:
        orient_outward(p)
    return parts


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

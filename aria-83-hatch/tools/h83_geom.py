"""Geometry for the Aria '83 Hatch restyle (v2).

BeamNG vehicle space: front = -Y, left = +X, up = +Z (meters).
Builders return {mesh_name: [meshkit.Part, ...]} for the LEFT side (or
centered parts); build_h83.mirror_lr() makes the right-hand copies.
Material slot names are final BeamNG material names. "ariahatch_main" is the
Aria's own body material: parts using it get their UVs pinned to a fully
painted texel (PAINT_UV) so they take the car's paint.

Shape data comes from raycasts of the Aria (probe_front.py / probe_body.py)
and from Civic reference photos (side profile overlaid at true scale).
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "beamng-kestrel-k5", "tools"))
import meshkit as M  # noqa: E402
import k5_mesh  # noqa: E402

PREFIX = "ariahatch_h83_"
PAINT = "ariahatch_main"
PAINT_UV = (0.01172, 0.43359)   # clean, fully painted region of ariahatch_main
PRISM_MATS = {"h83_glass_taillight", "h83_glass_signal_L", "h83_glass_signal_R", "h83_glass_reverse",
              "h83_glass_parking", "h83_reflector_red"}
PRISM_TILE = 0.064               # one 16x16-cell texture tile = 6.4 cm  (4 mm prisms)


# ============================================================ helpers
def clamp(v, a, b):
    return a if v < a else b if v > b else v


def smooth(t):
    t = clamp(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def spline_table(xs, ys, x):
    """Catmull-Rom through the table points (C1-smooth, so reflections don't band)."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    i = max(k for k in range(len(xs) - 1) if xs[k] <= x)
    t = (x - xs[i]) / (xs[i + 1] - xs[i])
    y0, y1, y2, y3 = ys[max(i - 1, 0)], ys[i], ys[i + 1], ys[min(i + 2, len(ys) - 1)]
    h = xs[i + 1] - xs[i]
    m1 = (y2 - y0) / (xs[min(i + 1, len(xs) - 1)] - xs[max(i - 1, 0)]) * h
    m2 = (y3 - y1) / (xs[min(i + 2, len(xs) - 1)] - xs[i]) * h
    t2, t3 = t * t, t * t * t
    return (2 * t3 - 3 * t2 + 1) * y1 + (t3 - 2 * t2 + t) * m1 + (-2 * t3 + 3 * t2) * y2 + (t3 - t2) * m2


def lerp_table(xs, ys, x):
    if x <= xs[0]:
        return ys[0]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            t = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] + (ys[i] - ys[i - 1]) * t
    return ys[-1]


def orient_by(p, fi, outward):
    a, b, c = p.f[fi]
    n = M.cross(M.sub(p.v[b], p.v[a]), M.sub(p.v[c], p.v[a]))
    if M.dot(n, outward) < 0:
        M.flip(p)
    return p


def orient_each(p, outward_fn):
    nf = []
    for a, b, c in p.f:
        n = M.cross(M.sub(p.v[b], p.v[a]), M.sub(p.v[c], p.v[a]))
        cen = tuple((p.v[a][i] + p.v[b][i] + p.v[c][i]) / 3 for i in range(3))
        nf.append((a, c, b) if M.dot(n, outward_fn(cen)) < 0 else (a, b, c))
    p.f = nf
    return p


def mirror_x(parts):
    out = []
    for p in parts:
        q = M.Part(p.mat)
        q.v = [(-x, y, z) for x, y, z in p.v]
        q.f = [(a, c, b) for a, b, c in p.f]
        out.append(q)
    return out


def closed(p):
    M.orient_outward(p)
    return p


def rrect(w, h, r, n=5):
    pts = []
    cx, cz = w / 2 - r, h / 2 - r
    for sx, sz, a0 in ((1, -1, -90), (1, 1, 0), (-1, 1, 90), (-1, -1, 180)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((sx * cx + r * math.cos(a), sz * cz + r * math.sin(a)))
    return pts


def box(mat, x0, x1, y0, y1, z0, z1):
    sec = lambda x: [(x, y0, z0), (x, y1, z0), (x, y1, z1), (x, y0, z1)]
    return closed(M.loft(mat, [sec(x0), sec(x1)]))


def plate_on(mat, center, u_axis, v_axis, n_out, w, h, depth, r=0.004, bevel=0.0015):
    """Small raised rounded-rect plaque on a surface (closed solid)."""
    outer = rrect(w, h, min(r, w / 2 - 1e-4, h / 2 - 1e-4))
    inner = rrect(w - 2 * bevel, h - 2 * bevel, max(min(r, w / 2, h / 2) - bevel, 1e-4))

    def pt(uv, d):
        return tuple(center[i] + u_axis[i] * uv[0] + v_axis[i] * uv[1] + n_out[i] * d for i in range(3))
    secs = [[pt(q, -0.002) for q in outer], [pt(q, depth - bevel) for q in outer], [pt(q, depth) for q in inner]]
    return closed(M.loft(mat, secs))


# ============================================================ front-clip shape
ZC_Y = [-1.73, -1.68, -1.62, -1.56, -1.50, -1.44, -1.38, -1.32, -1.26, -1.20, -1.14, -1.08, -1.02,
        -0.96, -0.90, -0.84, -0.78]
ZC_Z = [0.766, 0.773, 0.792, 0.806, 0.820, 0.831, 0.843, 0.852, 0.861, 0.868, 0.875, 0.880, 0.885,
        0.890, 0.893, 0.894, 0.897]
CROWN = 0.022
X76_Y = [-1.70, -1.62, -1.56, -1.50, -1.44, -1.38, -1.32, -1.26, -1.20, -1.14, -1.08, -1.02, -0.96,
         -0.90, -0.84, -0.78, -0.72, -0.64]
X76_X = [0.647, 0.650, 0.661, 0.671, 0.680, 0.691, 0.700, 0.709, 0.716, 0.722, 0.726, 0.729, 0.731,
         0.733, 0.734, 0.735, 0.736, 0.737]
D_Z = [0.30, 0.32, 0.36, 0.40, 0.44, 0.48, 0.52, 0.56, 0.60, 0.64, 0.68, 0.72, 0.76]
D_X = [-0.034, -0.026, -0.015, -0.006, 0.002, 0.008, 0.013, 0.016, 0.018, 0.018, 0.017, 0.010, 0.0]
Y_FS = -1.66          # fender side ends / front corner starts
RC = 0.045            # front corner radius (plan)
Y_FRONT = Y_FS - RC   # front face plane
FENDER_REAR = -0.655
TOP_W = 0.032         # fender top strip width at the shoulder
GAP = 0.004
ARCH_F = (-1.135, 0.32, 0.305)
ARCH_R = (1.115, 0.31, 0.295)
BELT_Z = 0.866


def z_center(y):
    return spline_table(ZC_Y, ZC_Z, y)


def z_top(x, y):
    return z_center(y) - CROWN * (x / 0.68) ** 2


def x_side(y, z):
    base = spline_table(X76_Y, X76_X, y)
    f = 0.6 + 0.4 * clamp((y + 1.62) / 0.4, 0, 1)
    if z >= 0.76:
        return base - 0.10 * (z - 0.76)
    return base + f * spline_table(D_Z, D_X, z)


def z_edge(y):
    ze = z_center(y) - CROWN * (0.70 / 0.68) ** 2
    if y > -0.84:
        t = smooth((y + 0.84) / (FENDER_REAR + 0.84))
        ze = ze + (BELT_Z - ze) * t
    return ze


def front_slope(z):
    """How far the lower front (apron) sets back from the front plane."""
    return max(0.0, 0.44 - z) * 0.3


# ============================================================ hood
def hood():
    ze0 = z_edge(Y_FS)
    xs0 = x_side(Y_FS, ze0)
    cx = xs0 - RC

    def corner_shut(theta):
        w = TOP_W * (1 + theta / 90.0)
        rho = RC - w
        a = math.radians(theta)
        return cx + rho * math.cos(a), Y_FS + rho * math.sin(a)

    corner = [corner_shut(-90 + 90 * i / 24) for i in range(25)]

    def half_w(y):
        if y <= corner[0][1]:
            return corner[0][0] - GAP
        if y <= Y_FS:
            for i in range(1, len(corner)):
                if y <= corner[i][1]:
                    t = (y - corner[i - 1][1]) / max(corner[i][1] - corner[i - 1][1], 1e-9)
                    return corner[i - 1][0] + (corner[i][0] - corner[i - 1][0]) * t - GAP
        ze = z_edge(y)
        return x_side(y, ze) - TOP_W - GAP

    y0, y1 = Y_FRONT - 0.004, -0.80
    ys = [y0 + (Y_FS - y0) * (i / 12) ** 1.0 for i in range(12)]
    ys += [Y_FS + (y1 - Y_FS) * i / 60 for i in range(61)]
    ncol = 40
    rows = []
    for y in ys:
        hw = half_w(y)
        rows.append([(hw * (2 * j / ncol - 1), y, z_top(hw * (2 * j / ncol - 1), y)) for j in range(ncol + 1)])
    top = M.grid(PAINT, rows)
    orient_each(top, lambda c: (0, 0, 1))
    # turned-down edge all round (front lip reaches forward over the chrome header)
    loop = [rows[0][j] for j in range(ncol + 1)] + [rows[i][-1] for i in range(1, len(rows))] + \
           [rows[-1][j] for j in range(ncol - 1, -1, -1)] + [rows[i][0] for i in range(len(rows) - 2, 0, -1)]
    lip = []
    for (x, y, z) in loop:
        if y <= y0 + 1e-6:
            lip.append((x, y - 0.012, z - 0.022))
        elif y >= y1 - 1e-6:
            lip.append((x, y + 0.002, z - 0.012))
        else:
            lip.append((x * (1 - 0.006 / max(abs(x), 0.01)), y, z - 0.016))
    skirt = M.grid(PAINT, [loop, lip], closed_u=True)
    orient_each(skirt, lambda c: (c[0], -1.0 if c[1] < -1.65 else (1.0 if c[1] > -0.81 else 0.0), 0.0))
    parts = [top, skirt]

    # louvred cowl vent near the rear edge
    vy0, vy1 = -0.912, -0.852
    band = M.grid("h83_black_trim", [[(x, vy0, z_top(x, vy0) + 0.0012) for x in (-0.44, 0.0, 0.44)],
                                     [(x, vy1, z_top(x, vy1) + 0.0012) for x in (-0.44, 0.0, 0.44)]])
    orient_each(band, lambda c: (0, 0, 1))
    parts.append(band)
    n = 46
    for k in range(n + 1):
        x = -0.43 + 0.86 * k / n
        zb = z_top(x, (vy0 + vy1) / 2) + 0.001
        parts.append(box("h83_black_trim", x - 0.0035, x + 0.0035, vy0 + 0.004, vy1 - 0.004, zb, zb + 0.005))
    return {PREFIX + "hood": parts}


# ============================================================ fenders
def fender_left():
    """Front fender: shoulder flush with the hood, squarer front corner, arch lip."""
    yc, zc, r = ARCH_F
    stations = []
    for i in range(19):                       # front corner, theta -90 -> 0
        stations.append(("c", -90 + 90 * i / 18))
    nside = 150
    for i in range(1, nside + 1):
        stations.append(("s", Y_FS + (FENDER_REAR - Y_FS) * i / nside))

    def z_bot(kind, val):
        if kind == "s" and abs(val - yc) < r:
            return zc + math.sqrt(r * r - (val - yc) ** 2)
        return zc

    def arch_w(kind, val):
        if kind != "s" or abs(val - yc) >= r:
            return 0.0
        return smooth(math.sqrt(1 - ((val - yc) / r) ** 2) * 2.5)

    def pos(kind, val, z, inset=0.0):
        """Point on the outer surface at height z, pushed inward by `inset`."""
        if kind == "s":
            return (x_side(val, z) - inset, val, z), (1.0, 0.0)
        a = math.radians(val)
        cxz = x_side(Y_FS, z) - RC
        n = (math.cos(a), math.sin(a))
        rho = RC - inset
        y = Y_FS + rho * n[1] + front_slope(z) * max(0.0, -n[1])
        return (cxz + rho * n[0], y, z), n

    NZ = 30
    rows = []
    for kind, val in stations:
        y_ref = val if kind == "s" else Y_FS
        ze = z_edge(y_ref)
        w = TOP_W if kind == "s" else TOP_W * (1 + val / 90.0)
        (po, n) = pos(kind, val, ze)
        p_in = (po[0] - n[0] * (w - GAP * 0), po[1] - n[1] * (w - GAP * 0), 0.0)
        p_in = (p_in[0], p_in[1], z_top(p_in[0], p_in[1]))
        sec = [(p_in[0], p_in[1], p_in[2] - 0.016), p_in,
               (po[0] - n[0] * 0.006, po[1] - n[1] * 0.006, ze + 0.0005),
               (po[0] - n[0] * 0.0015, po[1] - n[1] * 0.0015, ze - 0.0015)]
        zb = z_bot(kind, val)
        aw = arch_w(kind, val)
        z_hi = ze - 0.006
        for k in range(NZ + 1):
            z = z_hi + (zb + 0.03 - z_hi) * k / NZ
            sec.append(pos(kind, val, z)[0])
        flare = 0.008 * aw
        for dz, out in ((0.022, 0.6), (0.010, 1.0), (0.0, 1.0)):
            p, _ = pos(kind, val, zb + dz)
            sec.append((p[0] + n[0] * flare * out, p[1] + n[1] * flare * out, p[2]))
        p, _ = pos(kind, val, zb, inset=0.022 + flare)
        sec.append(p)
        rows.append(sec)
    g = M.grid(PAINT, rows)
    test = 2 * ((len(rows[0]) - 1) * (len(stations) // 2) + 1)
    orient_by(g, test, (0, 0, 1))
    # rear edge turned in toward the door gap
    last = rows[-1]
    rear = M.grid(PAINT, [last, [(x - 0.014, y, z) for x, y, z in last]])
    orient_each(rear, lambda c: (0.0, 1.0, 0.0))

    # amber side marker ahead of the wheel arch
    my, mz = -1.535, 0.700
    mx = x_side(my, mz)
    marker = [plate_on("h83_black_trim", (mx, my, mz), (0, 1, 0), (0, 0, 1), (1, 0, 0), 0.112, 0.034, 0.004),
              plate_on("h83_glass_signal_L", (mx + 0.002, my, mz), (0, 1, 0), (0, 0, 1), (1, 0, 0),
                       0.100, 0.024, 0.0055, r=0.003)]
    return ({PREFIX + "fender_FL": [g, rear], PREFIX + "fender_marker_FL": marker},
            (round(mx - 0.01, 3), my, mz))


# ============================================================ front panel / fascia / grille
LAMP_C = (0.5125, 0.673)
LAMP_W, LAMP_H = 0.225, 0.146
LAMP_Z = (LAMP_C[1] - LAMP_H / 2, LAMP_C[1] + LAMP_H / 2)     # 0.600 .. 0.746
GRILLE_X = 0.395
GRILLE_Z = (LAMP_Z[0], 0.708)        # bottom flush with the lamps, top below the lamp tops
HEADER_Z = (GRILLE_Z[1], GRILLE_Z[1] + 0.011)   # short chrome strip over the grille only
SILL_Z = (LAMP_Z[0] - 0.007, LAMP_Z[0])         # chrome strip under lamps + grille


def front_panel():
    ncol, nrow = 40, 14
    rows = []
    for i in range(nrow + 1):
        t = i / nrow
        row = []
        for j in range(ncol + 1):
            f = 2 * j / ncol - 1
            zb = 0.30 + 0.045 * abs(f) ** 6          # apron edge sweeps up into the corners
            z = zb + (SILL_Z[0] + 0.001 - zb) * t
            cx = x_side(Y_FS, z) - RC
            row.append((cx * f, Y_FRONT + front_slope(z), z))
        rows.append(row)
    face = M.grid(PAINT, rows)
    orient_each(face, lambda c: (0, -1, 0.3))
    xg = LAMP_C[0] - LAMP_W / 2 - 0.001
    # body-colour band between the grille's chrome top strip and the hood edge
    up = M.grid(PAINT, [[(x, Y_FRONT, z) for x in (-xg, 0.0, xg)] for z in (HEADER_Z[1] - 0.002, 0.735, 0.752)])
    orient_each(up, lambda c: (0, -1, 0))
    toprow = rows[-1]
    ret = M.grid(PAINT, [toprow, [(x, y + 0.02, z) for x, y, z in toprow]])
    orient_each(ret, lambda c: (0, 0, 1))
    face = M.merge(PAINT, [face, up])
    back = M.grid("h83_black_trim", [[(-0.64, -1.690, 0.58), (0.64, -1.690, 0.58)],
                                     [(-0.64, -1.690, 0.76), (0.64, -1.690, 0.76)]])
    orient_each(back, lambda c: (0, -1, 0))
    return {PREFIX + "frontpanel": [face, ret, back]}


def fascia():
    """Chrome strip over the grille (between the lamps) and a sill strip under lamps + grille."""
    xh = LAMP_C[0] - LAMP_W / 2 + 0.004
    z0, z1 = HEADER_Z
    prof = [(-1.703, z0), (-1.717, z0 + 0.0005), (-1.7215, z0 + 0.003), (-1.7225, (z0 + z1) / 2),
            (-1.7215, z1 - 0.003), (-1.717, z1 - 0.0005), (-1.703, z1)]
    secs = [[(x, y, z) for y, z in prof] for x in (-xh, -xh + 0.004, xh - 0.004, xh)]
    for s, x in ((secs[0], -xh), (secs[-1], xh)):     # rounded ends: pull end sections back
        for k, (px, py, pz) in enumerate(s):
            s[k] = (px, py + 0.004, pz)
    header = closed(M.loft("h83_chrome", secs))
    xs = LAMP_C[0] + LAMP_W / 2 + 0.001
    low = box("h83_chrome", -xs, xs, -1.7195, -1.703, SILL_Z[0], SILL_Z[1])
    return {PREFIX + "fascia_F": [header, low]}


def grille():
    z0, z1 = GRILLE_Z
    parts = []
    # recessed black surround box
    for (xa, xb, za, zb) in ((-GRILLE_X, GRILLE_X, z0, z0 + 0.005), (-GRILLE_X, GRILLE_X, z1 - 0.004, z1),
                             (-GRILLE_X, -GRILLE_X + 0.006, z0, z1), (GRILLE_X - 0.006, GRILLE_X, z0, z1)):
        parts.append(box("h83_grille_black", xa, xb, -1.714, -1.692, za, zb))
    back = M.grid("h83_black_trim", [[(-GRILLE_X, -1.692, z0), (GRILLE_X, -1.692, z0)],
                                     [(-GRILLE_X, -1.692, z1), (GRILLE_X, -1.692, z1)]])
    orient_each(back, lambda c: (0, -1, 0))
    parts.append(back)
    nbar = 7
    for i in range(nbar):
        zc = z0 + 0.012 + i * (z1 - z0 - 0.024) / (nbar - 1)
        # bar with a chamfered top: slightly forward-tilted blade
        sec = lambda x: [(x, -1.693, zc - 0.0035), (x, -1.7125, zc - 0.0035), (x, -1.7135, zc + 0.0015),
                         (x, -1.709, zc + 0.0045), (x, -1.693, zc + 0.0045)]
        parts.append(closed(M.loft("h83_grille_black", [sec(-GRILLE_X + 0.006), sec(GRILLE_X - 0.006)])))
    # generic emblem: chrome rounded square with black inset
    ec = (0.0, -1.7145, (z0 + z1) / 2)
    parts.append(plate_on("h83_chrome", ec, (1, 0, 0), (0, 0, 1), (0, -1, 0), 0.054, 0.044, 0.007, r=0.009))
    parts.append(plate_on("h83_black_trim", (0.0, -1.721, ec[2]), (1, 0, 0), (0, 0, 1), (0, -1, 0),
                          0.040, 0.030, 0.0012, r=0.006))
    return {PREFIX + "grille_F": parts}


# ============================================================ headlights
def headlight_left():
    cx, cz = LAMP_C
    n = 4
    W, H = LAMP_W, LAMP_H

    def rows_at(spec):
        return [[(cx + u, y, cz + v) for u, v in rrect(w, h, rr, n)] for (w, h, rr, y) in spec]

    bez = M.grid("h83_chrome", rows_at([
        (W, H, 0.012, -1.700), (W - 0.004, H - 0.004, 0.011, -1.7175), (W - 0.010, H - 0.010, 0.009, -1.7215),
        (W - 0.018, H - 0.018, 0.008, -1.7215), (W - 0.024, H - 0.024, 0.007, -1.7175)]), closed_u=True)
    orient_by(bez, 2 * (len(rrect(1, 1, 0.1, n)) * 2 + 2), (0, -1, 0))
    ring = M.grid("h83_black_trim", rows_at([
        (W - 0.024, H - 0.024, 0.007, -1.7175), (W - 0.030, H - 0.030, 0.006, -1.716),
        (W - 0.034, H - 0.034, 0.006, -1.712), (W - 0.034, H - 0.034, 0.006, -1.700)]), closed_u=True)
    orient_by(ring, 2 * (len(rrect(1, 1, 0.1, n)) + 2), (0, -1, 0))
    bucket = M.grid("h83_black_trim", rows_at([(W, H, 0.012, -1.700), (W, H, 0.012, -1.660)]), closed_u=True)
    orient_each(bucket, lambda c: (c[0] - cx, 0, c[2] - cz))

    # sealed-beam lens on a regular grid (no diagonal creases): gentle dome, vertical
    # prism flutes and a horizontal prism band through the middle
    lw, lh = W - 0.034, H - 0.034
    nu, nv = 48, 24
    rows = []
    for i in range(nv + 1):
        v = 2 * i / nv - 1
        row = []
        for j in range(nu + 1):
            u = 2 * j / nu - 1
            x, z = cx + u * lw / 2, cz + v * lh / 2
            y = -1.711 - 0.008 * (1 - u * u) * (1 - v * v)
            y += -0.0009 * abs(math.sin(math.pi * (x - cx) / 0.0095))
            if abs(z - cz) < 0.012:
                y -= 0.0012 * (1 - abs(u) ** 8)
            row.append((x, y, z))
        rows.append(row)
    lens = M.grid("h83_glass_headlight", rows)
    orient_each(lens, lambda c: (0, -1, 0))

    refl = M.grid("h83_reflector", rows_at([(lw, lh, 0.006, -1.704), (lw * 0.82, lh * 0.74, 0.02, -1.680),
                                            (lw * 0.5, lh * 0.42, 0.02, -1.664), (0.02, 0.016, 0.006, -1.658)]),
                  closed_u=True)
    orient_by(refl, len(refl.f) - 2, (0, -1, 0))
    bulb = M.lathe("h83_chrome", [(-1.668, 0.0), (-1.668, 0.012), (-1.672, 0.012), (-1.676, 0.006), (-1.677, 0.0)], n=16)
    bulb.v = [(cx + v[1], v[0], cz + v[2]) for v in bulb.v]   # lathe axis X -> lamp axis Y
    closed(bulb)
    return {PREFIX + "headlight_FL": [bez, ring, bucket, refl, bulb], PREFIX + "headlightglass_FL": [lens]}


# ============================================================ bumpers
def superellipse_path(a, b, yc, ex, sign, count=180):
    pts = []
    for i in range(count + 1):
        t = math.pi * i / count
        c, sn = math.cos(t), math.sin(t)
        pts.append((a * math.copysign(abs(c) ** (2 / ex), c), yc + sign * b * abs(sn) ** (2 / ex)))
    nrm = []
    for i in range(len(pts)):
        p0, p1 = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        tx, ty = p1[0] - p0[0], p1[1] - p0[1]
        l = math.hypot(tx, ty)
        nx, ny = ty / l, -tx / l
        if nx * pts[i][0] + ny * (pts[i][1] - yc) < 0:
            nx, ny = -nx, -ny
        nrm.append((nx, ny))
    return pts, nrm


def sweep(mat, pts, nrm, profile, i0=0, i1=None, cap=True):
    i1 = len(pts) - 1 if i1 is None else i1
    secs = [[(pts[i][0] - nrm[i][0] * d, pts[i][1] - nrm[i][1] * d, z) for d, z in profile]
            for i in range(i0, i1 + 1)]
    return closed(M.loft(mat, secs))


def idx_range(pts, pred):
    idx = [i for i, p in enumerate(pts) if pred(p)]
    return min(idx), max(idx)


def bumper_parts(path, z0, z1, lamps):
    """Rubber-faced bumper with bright top strip and a raised rub rib.

    lamps: list of (material, x_from, x_to, z_from, z_to, side) placed on the face."""
    pts, nrm = superellipse_path(**path)
    zm = z1 - 0.014
    body_prof = [(0.11, zm), (0.03, zm), (0.006, zm - 0.002), (0.0, zm - 0.008),
                 (0.0, zm - 0.040), (-0.004, zm - 0.044), (-0.004, zm - 0.054), (0.0, zm - 0.058),
                 (0.0, z0 + 0.018), (0.004, z0 + 0.008), (0.014, z0 + 0.002), (0.03, z0), (0.11, z0)]
    body = sweep("h83_black_plastic", pts, nrm, body_prof)
    strip_prof = [(0.022, z1), (0.006, z1), (0.0005, z1 - 0.003), (-0.0025, z1 - 0.007),
                  (-0.002, zm + 0.001), (0.004, zm - 0.002), (0.022, zm - 0.002)]
    strip = sweep("h83_bumper_strip", pts, nrm, strip_prof)
    parts = {"body": [body, strip], "lamps": []}
    # end caps: rubber bump stops at each end (slightly proud)
    for i0, i1 in ((0, 6), (len(pts) - 7, len(pts) - 1)):
        cap_prof = [(0.02, zm - 0.004), (-0.003, zm - 0.006), (-0.006, zm - 0.02), (-0.006, z0 + 0.02),
                    (-0.003, z0 + 0.008), (0.02, z0 + 0.006)]
        parts["body"].append(sweep("h83_black_trim", pts, nrm, cap_prof, i0, i1))
    for mat, xa, xb, za, zb, side in lamps:
        if side > 0:
            i0, i1 = idx_range(pts, lambda p: xa <= p[0] <= xb and p[1] * path["sign"] > abs(path["yc"]) + 0.05)
        else:
            i0, i1 = idx_range(pts, lambda p: -xb <= p[0] <= -xa and p[1] * path["sign"] > abs(path["yc"]) + 0.05)
        bez = [(0.004, zb + 0.004), (-0.0035, zb + 0.004), (-0.0035, za - 0.004), (0.004, za - 0.004)]
        parts["lamps"].append(sweep("h83_black_trim", pts, nrm, bez, max(i0 - 1, 0), min(i1 + 1, len(pts) - 1)))
        lens_prof = [(0.0, zb), (-0.0045, zb - 0.0015)]
        nz = 6
        for k in range(nz + 1):
            z = zb - 0.0015 - (zb - za - 0.003) * k / nz
            lens_prof.append((-0.0055 if k % 2 == 0 else -0.0045, z))
        lens_prof += [(-0.0045, za + 0.0015), (0.0, za)]
        parts["lamps"].append((mat, sweep(mat, pts, nrm, lens_prof, i0, i1)))
    return parts, pts


FRONT_PATH = dict(a=0.738, b=0.36, yc=-1.43, ex=3.0, sign=-1)
REAR_PATH = dict(a=0.732, b=0.412, yc=1.445, ex=3.0, sign=1)
BUMPER_F_Z = (0.430, 0.552)
BUMPER_R_Z = (0.420, 0.546)


def bumper_front():
    z0, z1 = BUMPER_F_Z
    lamps = []
    for side in (1, -1):
        s = "L" if side > 0 else "R"
        lamps.append(("h83_glass_parking", 0.455, 0.540, 0.450, 0.488, side))
        lamps.append((f"h83_glass_signal_{s}", 0.545, 0.640, 0.450, 0.488, side))
    parts, pts = bumper_parts(FRONT_PATH, z0, z1, lamps)
    out = {PREFIX + "bumper_F": parts["body"], PREFIX + "bumper_lamps_FL": [], PREFIX + "bumper_lamps_FR": []}
    for item in parts["lamps"]:
        if isinstance(item, tuple):
            mat, p = item
        else:
            mat, p = None, item
        cx = sum(v[0] for v in p.v) / len(p.v)
        out[PREFIX + ("bumper_lamps_FL" if cx > 0 else "bumper_lamps_FR")].append(p)
    i = min(range(len(pts)), key=lambda k: abs(pts[k][0] - 0.59) + (0 if pts[k][1] < -1.6 else 9))
    sig = (round(pts[i][0], 3), round(pts[i][1] + 0.012, 3), 0.469)
    return out, sig


def bumper_rear():
    z0, z1 = BUMPER_R_Z
    lamps = [("h83_reflector_red", 0.560, 0.690, 0.468, 0.494, 1), ("h83_reflector_red", 0.560, 0.690, 0.468, 0.494, -1)]
    parts, _ = bumper_parts(REAR_PATH, z0, z1, lamps)
    allp = parts["body"] + [x[1] if isinstance(x, tuple) else x for x in parts["lamps"]]
    return {PREFIX + "bumper_R": allp}


# ============================================================ rear: filler panel + plate
FILL_X = 0.645
FILL_Z = (BUMPER_R_Z[1] - 0.012, 0.657)


def rear_panel_y(x, z):
    return 1.805 - 0.133 * x * x + 0.144 * (z - 0.64) + 0.004


def rear_filler():
    zs = [FILL_Z[0] + (FILL_Z[1] - FILL_Z[0]) * k / 8 for k in range(9)]
    ncol = 48
    rows = [[(FILL_X * (2 * j / ncol - 1), rear_panel_y(FILL_X * (2 * j / ncol - 1), z), z) for j in range(ncol + 1)]
            for z in zs]
    face = M.grid(PAINT, rows)
    orient_each(face, lambda c: (0, 1, 0))
    top = M.grid(PAINT, [rows[-1], [(x, y - 0.02, z) for x, y, z in rows[-1]]])
    orient_each(top, lambda c: (0, 0, 1))
    # black plate-lamp housings either side of the plate
    parts = [face, top]
    for sx in (-1, 1):
        x = sx * 0.165
        z = BUMPER_R_Z[1] + 0.006
        parts.append(plate_on("h83_black_trim", (x, rear_panel_y(x, 0.56) + 0.022, z), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                              0.075, 0.040, 0.016, r=0.006))
    return {PREFIX + "rear_panel": parts}


PLATE_R_Z = 0.601


# ============================================================ taillights (one rectangular corner unit)
TL_C = (0.53, 1.50)           # ray-fan centre (plan): phi=0 hits the rear face at x=0.53
TL_PHI = (0.0, 56.0)
TL_Z = (BUMPER_R_Z[1] + 0.020, 0.748)   # ~0.18 m tall: wider than tall, like the Civic's
TL_GATE_X = 0.626             # tailgate side edge
TL_GATE_Z = 0.656             # tailgate bottom edge
TL_FRAME = 0.010
TL_OFF_EDGE, TL_OFF_FRAME, TL_OFF_LENS, TL_OFF_BACK = 0.002, 0.006, 0.0035, 0.0012   # near-flush
TL_SPLIT_Z = 0.660            # red above, amber/clear below (~53 % red); at the tailgate edge
TL_CLEAR_FRAC = 0.33          # inner share of the lower band that is clear (reverse)


def _cell_edges(c):
    i, j = c
    return {tuple(sorted(e)) for e in (((i, j), (i, j + 1)), ((i, j + 1), (i + 1, j + 1)),
                                       ((i + 1, j + 1), (i + 1, j)), ((i + 1, j), (i, j)))}


def _cells_to_parts(pts, cells, mat_fn, centre, outline_cells):
    """Emit grid cells (by material) plus a black skirt along the OUTER outline of
    `outline_cells` (the whole lamp), restricted to edges owned by `cells`."""
    by = {}
    for (i, j) in cells:
        m = mat_fn(i, j)
        p = by.setdefault(m, M.Part(m))
        a = p.add(pts[i][j]); b = p.add(pts[i][j + 1]); c = p.add(pts[i + 1][j + 1]); d = p.add(pts[i + 1][j])
        p.f += [(a, b, c), (a, c, d)]
    for p in by.values():
        orient_each(p, lambda c: (c[0] - centre[0], c[1] - centre[1], 0.0))
    count = {}
    for c in outline_cells:
        for e in _cell_edges(c):
            count[e] = count.get(e, 0) + 1
    own = set()
    for c in cells:
        own |= _cell_edges(c)
    sk = M.Part("h83_lamp_frame")
    for e, n in count.items():
        if n != 1 or e not in own:
            continue
        (u, v) = e
        q0, q1 = pts[u[0]][u[1]], pts[v[0]][v[1]]
        back = []
        for q in (q0, q1):
            dx, dy = q[0] - centre[0], q[1] - centre[1]
            l = math.hypot(dx, dy)
            back.append((q[0] - dx / l * 0.008, q[1] - dy / l * 0.008, q[2]))
        a = sk.add(q0); b = sk.add(q1); c = sk.add(back[1]); d = sk.add(back[0])
        sk.f += [(a, b, c), (a, c, d)]
    mid = (centre[0] + 0.10, centre[1] + 0.17, (TL_Z[0] + TL_Z[1]) / 2)
    orient_each(sk, lambda c: (c[0] - mid[0], c[1] - mid[1], c[2] - mid[2]))
    return list(by.values()) + ([sk] if sk.f else [])


def taillight_left(raycast):
    """Rectangular lamp conforming to the (smoothed) rear corner, split invisibly into a
    body piece and the part over the tailgate's corner (moves with the tailgate)."""
    cxp, cyp = TL_C
    zb, zt = TL_Z
    nphi = 36
    phis = [TL_PHI[0] + (TL_PHI[1] - TL_PHI[0]) * k / nphi for k in range(nphi + 1)]
    fz = TL_FRAME / (zt - zb)
    vs = sorted({0.0, fz, 1 - fz, 1.0, round((TL_SPLIT_Z - 0.003 - zb) / (zt - zb), 6),
                 round((TL_SPLIT_Z + 0.003 - zb) / (zt - zb), 6)} | {k / 14 for k in range(1, 14)})
    zr = [zb + (zt - zb) * v for v in vs]

    def dirs(phi):
        return math.sin(math.radians(phi)), math.cos(math.radians(phi))

    dist = []
    for z in zr:
        row = []
        for phi in phis:
            dx, dy = dirs(phi)
            h = raycast((cxp + dx * 2.5, cyp + dy * 2.5, z), (-dx, -dy, 0.0))
            if h is None or math.hypot(h[0] - cxp, h[1] - cyp) > 0.45:
                raise RuntimeError(f"taillight ray missed: phi={phi} z={z} hit={h}")
            r_hit = math.hypot(h[0] - cxp, h[1] - cyp)
            # our painted rear panel sits a few mm over the body here: sit on top of it
            if h[0] <= FILL_X and FILL_Z[0] <= z <= FILL_Z[1] and dy > 0.3:
                r_hit = max(r_hit, (rear_panel_y(h[0], z) + 0.001 - cyp) / dy)
            row.append(r_hit)
        sm = [max(row[max(0, j - 3):j + 4]) for j in range(len(row))]          # bridge shut-line grooves
        sm = [sum(sm[max(0, j - 2):j + 3]) / len(sm[max(0, j - 2):j + 3]) for j in range(len(sm))]
        dist.append([max(a, b) for a, b in zip(row, sm)])
    for j in range(len(phis)):                                                  # smooth vertically too
        col = [dist[i][j] for i in range(len(zr))]
        for i in range(len(zr)):
            w = col[max(0, i - 2):i + 3]
            dist[i][j] = max(col[i], sum(w) / len(w))

    nz, nc = len(zr), len(phis)
    pts = []
    for i, z in enumerate(zr):
        row = []
        for j, phi in enumerate(phis):
            dx, dy = dirs(phi)
            edge = i in (0, nz - 1) or j in (0, nc - 1)
            r = dist[i][j] + (0.012 if edge else 0.016)
            row.append((cxp + dx * r, cyp + dy * r, z))
        pts.append(row)
    jsplit = max(2, int(round(TL_CLEAR_FRAC * (nc - 1))))
    i_div = min(range(nz), key=lambda i: abs(zr[i] - (TL_SPLIT_Z - 0.003)))
    # raised frame: points on the frame stand 5 mm proud of the recessed lens
    frame_rows = {i for i, z in enumerate(zr) if z <= zb + TL_FRAME + 1e-6 or z >= zt - TL_FRAME - 1e-6}
    frame_rows |= {i_div, i_div + 1}
    frame_cols = {0, 1, nc - 2, nc - 1, jsplit, jsplit + 1}
    back_pts = [[None] * nc for _ in range(nz)]
    for i in range(nz):
        for j in range(nc):
            dx, dy = dirs(phis[j])
            if i in (0, nz - 1) or j in (0, nc - 1):
                off = TL_OFF_EDGE                         # bevel down into the body
            elif i in frame_rows or j in frame_cols and zr[i] < TL_SPLIT_Z + 0.004 or j in (1, nc - 2):
                off = TL_OFF_FRAME                        # gasket/frame stands proud
            else:
                off = TL_OFF_LENS                         # lens slightly recessed in the frame
            r = dist[i][j] + off
            pts[i][j] = (cxp + dx * r, cyp + dy * r, zr[i])
            rb = dist[i][j] + TL_OFF_BACK
            back_pts[i][j] = (cxp + dx * rb, cyp + dy * rb, zr[i])

    def cell_x(i, j):
        return (pts[i][j][0] + pts[i][j + 1][0] + pts[i + 1][j][0] + pts[i + 1][j + 1][0]) / 4

    def mat(i, j):
        zc = (zr[i] + zr[i + 1]) / 2
        if zc < zb + TL_FRAME or zc > zt - TL_FRAME or j < 1 or j > nc - 3 or i == i_div:
            return "h83_lamp_frame"
        if zc < TL_SPLIT_Z:
            if j == jsplit:
                return "h83_lamp_frame"
            return "h83_glass_reverse" if j < jsplit else "h83_glass_signal_L"
        return "h83_glass_taillight"

    all_cells = {(i, j) for i in range(nz - 1) for j in range(nc - 1)}
    gate_cells = {(i, j) for (i, j) in all_cells
                  if cell_x(i, j) < TL_GATE_X and zr[i] >= TL_SPLIT_Z + 0.003 - 1e-6}
    body = _cells_to_parts(pts, all_cells - gate_cells, mat, TL_C, all_cells)
    gate = _cells_to_parts(pts, gate_cells, mat, TL_C, all_cells) if gate_cells else []
    # mirrored reflector behind the translucent lens areas (gives the lamp depth)
    lens_cells = {c for c in all_cells if mat(*c).startswith("h83_glass")}
    for cells, target in ((lens_cells - gate_cells, body), (lens_cells & gate_cells, gate)):
        if cells:
            refl = M.Part("h83_lamp_back")
            for (i, j) in cells:
                a = refl.add(back_pts[i][j]); b = refl.add(back_pts[i][j + 1])
                c = refl.add(back_pts[i + 1][j + 1]); d = refl.add(back_pts[i + 1][j])
                refl.f += [(a, b, c), (a, c, d)]
            orient_each(refl, lambda q: (q[0] - cxp, q[1] - cyp, 0.0))
            target.append(refl)

    def pt(phi, z):
        dx, dy = dirs(phi)
        i = min(range(nz), key=lambda k: abs(zr[k] - z))
        j = min(range(nc), key=lambda k: abs(phis[k] - phi))
        r = dist[i][j] - 0.004
        return (round(cxp + dx * r, 3), round(cyp + dy * r, 3), round(z, 3))
    bulbs = {"brake": pt(phis[nc // 2], (TL_SPLIT_Z + zt) / 2),
             "signal": pt(phis[min(nc - 2, jsplit + (nc - jsplit) // 2)], (zb + TL_SPLIT_Z) / 2),
             "reverse": pt(phis[max(1, jsplit // 2)], (zb + TL_SPLIT_Z) / 2),
             "plate": (0.20, round(rear_panel_y(0.20, 0.64), 3), 0.640)}
    out = {PREFIX + "taillight_RL": body}
    if gate:
        out[PREFIX + "taillight_gate_RL"] = gate
    return out, bulbs


# ============================================================ side trim (rub strips), markers, fuel door
MOLD_Z = 0.540


def side_trim_left(raycast_door, raycast_body):
    """Black rub strip with a bright insert, split at the panel gaps."""
    segs = [("fender", -0.905, FENDER_REAR - 0.006), ("door", -0.638, 0.386), ("body", 0.402, 0.905)]
    out = {}
    for name, y0, y1 in segs:
        n = max(8, int((y1 - y0) / 0.02))
        pts = []
        for k in range(n + 1):
            y = y0 + (y1 - y0) * k / n
            if name == "fender":
                x = x_side(y, MOLD_Z)
            else:
                h = (raycast_door if name == "door" else raycast_body)((2.0, y, MOLD_Z), (-1, 0, 0))
                if h is None or h[0] < 0.5:
                    raise RuntimeError(f"side trim ray missed {name} at y={y}")
                x = h[0]
            pts.append((x, y))
        prof = [(-0.001, MOLD_Z - 0.013), (0.004, MOLD_Z - 0.012), (0.0065, MOLD_Z - 0.008),
                (0.007, MOLD_Z + 0.008), (0.0045, MOLD_Z + 0.012), (-0.001, MOLD_Z + 0.013)]
        secs = []
        for k, (x, y) in enumerate(pts):
            taper = min(1.0, min(k, n - k) / 1.5) if n > 3 else 1.0
            secs.append([(x + d * max(taper, 0.35), y, z) for d, z in prof])
        rub = closed(M.loft("h83_black_plastic", secs))
        ins = [[(x + 0.0072, y, MOLD_Z - 0.0022), (x + 0.0082, y, MOLD_Z), (x + 0.0072, y, MOLD_Z + 0.0022),
                (x + 0.005, y, MOLD_Z)] for (x, y) in pts[1:-1]]
        insert = closed(M.loft("h83_chrome", ins))
        out[PREFIX + f"trim_{name}_L"] = [rub, insert]

    # rear side marker (amber/red reflector) behind the rear arch, and a round fuel door
    extra = []
    my, mz = 1.52, 0.655
    h = raycast_body((2.0, my, mz), (-1, 0, 0))
    extra.append(plate_on("h83_black_trim", h, (0, 1, 0), (0, 0, 1), (1, 0, 0), 0.085, 0.030, 0.003))
    extra.append(plate_on("h83_reflector_red", (h[0] + 0.0015, h[1], h[2]), (0, 1, 0), (0, 0, 1), (1, 0, 0),
                          0.075, 0.021, 0.0045, r=0.003))
    fy, fz = 1.34, 0.785
    h = raycast_body((2.0, fy, fz), (-1, 0, 0))
    ring = M.lathe("h83_black_trim", [(0.0, 0.0), (0.0, 0.049), (0.0012, 0.049), (0.0012, 0.0)], n=48)
    door = M.lathe(PAINT, [(0.0, 0.0), (0.0, 0.045), (0.0016, 0.0445), (0.0022, 0.040), (0.0024, 0.0)], n=48)
    for p in (ring, door):
        p.v = [(h[0] + v[0], h[1] + v[1], h[2] + v[2]) for v in p.v]
        closed(p)
    extra += [ring, door]
    out[PREFIX + "trim_body_extra_L"] = extra
    return out


# ============================================================ steel wheel (unchanged from v1)
WHEEL = dict(D=13, xi=-0.0784, xo=0.0784, rf=0.1822, m=0.020)


def steel_wheel():
    s = WHEEL
    m = s["m"]
    parts = []
    prof, r_inner = k5_mesh.barrel_profile(s)
    parts.append(M.lathe("h83_wheel_silver", prof, n=72))
    xf = 0.048
    inner = [(m + 0.004, 0.0), (m + 0.004, 0.055), (m + 0.010, 0.066), (m + 0.024, 0.073), (xf, 0.080),
             (xf, 0.083), (xf - 0.003, 0.083), (m + 0.021, 0.075), (m + 0.007, 0.068),
             (m + 0.001, 0.057), (m + 0.001, 0.0)]
    parts.append(M.lathe("h83_wheel_silver", inner, n=72))
    outer = [(xf, 0.120), (xf + 0.004, 0.128), (xf + 0.006, 0.140), (xf + 0.004, 0.152),
             (xf + 0.001, r_inner + 0.003), (xf - 0.002, r_inner + 0.003), (xf + 0.001, 0.152),
             (xf + 0.003, 0.140), (xf + 0.001, 0.128), (xf - 0.003, 0.120)]
    parts.append(M.lathe("h83_wheel_silver", outer, n=72))
    for k in range(8):
        th = 2 * math.pi * k / 8 + math.pi / 8
        ct, st = math.cos(th), math.sin(th)
        secs = []
        for r, w in ((0.080, 0.050), (0.100, 0.054), (0.122, 0.060)):
            crown = 0.002 if r == 0.100 else 0.0
            sec = []
            for sd, x in ((-w / 2, xf - 0.003), (-w / 2, xf + crown), (w / 2, xf + crown), (w / 2, xf - 0.003)):
                a = math.sqrt(r * r - sd * sd)
                sec.append((x, a * ct - sd * st, a * st + sd * ct))
            secs.append(sec)
        parts.append(closed(M.loft("h83_wheel_silver", secs)))
    cap = [(m + 0.004, 0.0), (m + 0.004, 0.031), (m + 0.011, 0.031), (m + 0.017, 0.027),
           (m + 0.021, 0.019), (m + 0.0235, 0.009), (m + 0.024, 0.0)]
    parts.append(M.lathe("h83_chrome", cap, n=48))
    x0, x1 = m + 0.004, m + 0.016
    nut = [(x0, 0.0), (x0, 0.0095), (x1 - 0.002, 0.0095), (x1, 0.0075), (x1 + 0.002, 0.004), (x1 + 0.0026, 0.0)]
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        parts.append(M.lathe("h83_chrome", nut, n=6, cy=0.05 * math.cos(a), cz=0.05 * math.sin(a), phase=a))
    for p in parts:
        M.orient_outward(p)
    return {PREFIX + "steel_13x5": parts}

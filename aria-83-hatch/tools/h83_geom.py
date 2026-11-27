"""Geometry for the Aria '83 Hatch restyle parts.

BeamNG vehicle space: front = -Y, left = +X, up = +Z (meters).
Every builder returns {mesh_name: [meshkit.Part, ...]} for the LEFT side
(or centered parts); mirror_x() makes the right-hand copies.
Material slot names are the final BeamNG material names.
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


# ------------------------------------------------------------ helpers
def orient_by(p, fi, outward):
    """Flip all faces of p so face fi's normal agrees with `outward`."""
    a, b, c = p.f[fi]
    n = M.cross(M.sub(p.v[b], p.v[a]), M.sub(p.v[c], p.v[a]))
    if M.dot(n, outward) < 0:
        M.flip(p)
    return p


def orient_each(p, outward_fn):
    """Flip faces individually so each normal agrees with outward_fn(centroid)."""
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


def rrect(w, h, r, n=6):
    """Rounded rectangle outline (CCW in its plane), starting bottom-right corner arc."""
    pts = []
    cx, cz = w/2 - r, h/2 - r
    for sx, sz, a0 in ((1, -1, -90), (1, 1, 0), (-1, 1, 90), (-1, -1, 180)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((sx*cx + r*math.cos(a), sz*cz + r*math.sin(a)))
    return pts


def ring_rows(outlines):
    """outlines: list of (pts2d, y, cx, cz, scale) -> grid rows in XYZ (x, y, z)."""
    rows = []
    for pts, y, cx, cz in outlines:
        rows.append([(cx + u, y, cz + v) for u, v in pts])
    return rows


def box_x(mat, x0, x1, ymin, ymax, zmin, zmax):
    sec = lambda x: [(x, ymin, zmin), (x, ymax, zmin), (x, ymax, zmax), (x, ymin, zmax)]
    p = M.loft(mat, [sec(x0), sec(x1)])
    M.orient_outward(p)
    return p


# ------------------------------------------------------------ headlights
HL_CX, HL_CZ = 0.506, 0.648


def headlight_left():
    cx, cz = HL_CX, HL_CZ
    n = 6
    o_out = rrect(0.232, 0.160, 0.022, n)
    o_out_s = rrect(0.226, 0.154, 0.019, n)
    o_in_f = rrect(0.204, 0.142, 0.018, n)
    o_in = rrect(0.198, 0.138, 0.016, n)
    bezel = M.grid("h83_chrome", ring_rows([
        (o_out, -1.698, cx, cz), (o_out_s, -1.7165, cx, cz),
        (o_in_f, -1.7175, cx, cz), (o_in, -1.705, cx, cz), (o_in, -1.684, cx, cz)]),
        closed_u=True)
    k = len(o_out)
    orient_by(bezel, 2 * (k + 3), (0, -1, 0))   # a face on the front band

    # sealed-beam lens: concentric rings, domed, with fine vertical flutes
    rows = []
    for kk in [1.0, 0.92, 0.82, 0.7, 0.56, 0.4, 0.22, 0.0]:
        ring = []
        for u, v in rrect(0.200, 0.140, 0.017, n):
            x, z = cx + u * kk, cz + v * kk
            y = -1.686 - 0.007 * (1 - kk * kk) + 0.0007 * math.cos(2 * math.pi * (x - cx) / 0.011)
            ring.append((x, y, z))
        rows.append(ring)
    lens = M.grid("h83_glass_headlight", rows, closed_u=True)
    orient_each(lens, lambda c: (0, -1, 0))

    refl_rows = []
    for (w, h, r), y in (((0.198, 0.138, 0.016), -1.682), ((0.17, 0.11, 0.02), -1.652),
                         ((0.11, 0.07, 0.02), -1.628), ((0.0, 0.0, 0.0), -1.622)):
        if w == 0:
            refl_rows.append([(cx, y, cz)] * len(o_in))
        else:
            refl_rows.append([(cx + u, y, cz + v) for u, v in rrect(w, h, r, n)])
    refl = M.grid("h83_reflector", refl_rows, closed_u=True)
    orient_by(refl, len(refl.f) - 2, (0, -1, 0))
    return {PREFIX + "headlight_FL": [bezel, refl], PREFIX + "headlightglass_FL": [lens]}


# ------------------------------------------------------------ grille
def grille():
    cz = 0.6565
    n = 4
    outer = rrect(0.768, 0.143, 0.008, n)
    outer_s = rrect(0.764, 0.139, 0.007, n)
    inner = rrect(0.752, 0.127, 0.004, n)
    frame = M.grid("h83_chrome", ring_rows([
        (outer, -1.700, 0, cz), (outer_s, -1.7185, 0, cz), (inner, -1.7185, 0, cz), (inner, -1.698, 0, cz)]),
        closed_u=True)
    orient_by(frame, 2 * (len(outer) + 2), (0, -1, 0))
    back = M.grid("h83_grille_black", [[(-0.38, -1.694, cz - 0.068), (0.38, -1.694, cz - 0.068)],
                                       [(-0.38, -1.694, cz + 0.068), (0.38, -1.694, cz + 0.068)]])
    orient_each(back, lambda c: (0, -1, 0))
    parts = [frame, back]
    nslat = 6
    for i in range(nslat):
        z = cz - 0.0525 + i * 0.105 / (nslat - 1)
        parts.append(box_x("h83_grille_black", -0.377, 0.377, -1.713, -1.695, z - 0.0035, z + 0.0035))
    # thin chrome accent on the middle slat pair
    parts.append(box_x("h83_chrome", -0.377, 0.377, -1.7142, -1.712, cz - 0.0015, cz + 0.0015))
    # small fictional emblem plaque
    em = []
    for y in (-1.712, -1.722):
        em.append([(u, y, cz + v) for u, v in rrect(0.074, 0.034, 0.012, 6)])
    plaque = M.loft("h83_chrome", em)
    M.orient_outward(plaque)
    parts.append(plaque)
    return {PREFIX + "grille_F": parts}


# ------------------------------------------------------------ bumpers
def superellipse_path(a, b, yc, ex, sign, count=160):
    """Plan path x(t), y(t) for t in [0, pi]; sign=-1 front (-y), +1 rear."""
    pts = []
    for i in range(count + 1):
        # denser sampling near the corners
        t = math.pi * i / count
        c, sn = math.cos(t), math.sin(t)
        x = a * math.copysign(abs(c) ** (2 / ex), c)
        y = yc + sign * b * abs(sn) ** (2 / ex)
        pts.append((x, y))
    # outward normals
    nrm = []
    for i in range(len(pts)):
        p0 = pts[max(i - 1, 0)]
        p1 = pts[min(i + 1, len(pts) - 1)]
        tx, ty = p1[0] - p0[0], p1[1] - p0[1]
        l = math.hypot(tx, ty)
        nx, ny = ty / l, -tx / l
        px, py = pts[i]
        if nx * px + ny * (py - yc) < 0:
            nx, ny = -nx, -ny
        nrm.append((nx, ny))
    return pts, nrm


def sweep(mat, pts, nrm, profile, i0=0, i1=None):
    i1 = len(pts) - 1 if i1 is None else i1
    secs = []
    for i in range(i0, i1 + 1):
        (x, y), (nx, ny) = pts[i], nrm[i]
        secs.append([(x - nx * d, y - ny * d, z) for d, z in profile])
    p = M.loft(mat, secs)
    M.orient_outward(p)
    return p


BUMPER_PROFILE_F = [(0.10, 0.485), (0.03, 0.488), (0.012, 0.484), (0.003, 0.474), (0.0, 0.458),
                    (0.0, 0.418), (0.008, 0.412), (0.008, 0.396), (0.0, 0.390), (0.0, 0.330),
                    (0.004, 0.312), (0.016, 0.298), (0.04, 0.292), (0.10, 0.292)]
BUMPER_PROFILE_R = [(0.10, 0.475), (0.03, 0.478), (0.012, 0.474), (0.003, 0.464), (0.0, 0.450),
                    (0.0, 0.412), (0.008, 0.406), (0.008, 0.390), (0.0, 0.384), (0.0, 0.335),
                    (0.004, 0.318), (0.016, 0.305), (0.04, 0.300), (0.10, 0.300)]
FRONT_PATH = dict(a=0.742, b=0.372, yc=-1.42, ex=3.2, sign=-1)
REAR_PATH = dict(a=0.732, b=0.425, yc=1.45, ex=3.2, sign=1)


def bumper_front():
    pts, nrm = superellipse_path(**FRONT_PATH)
    body = sweep("h83_black_plastic", pts, nrm, BUMPER_PROFILE_F)
    lens_prof = [(0.006, 0.4615), (-0.0025, 0.4595), (-0.0025, 0.4175), (0.006, 0.4155)]
    idx = [i for i, (x, y) in enumerate(pts) if x > 0.45 and y < -1.52]
    lensL = sweep("h83_glass_signal_L", pts, nrm, lens_prof, min(idx), max(idx))
    idx = [i for i, (x, y) in enumerate(pts) if x < -0.45 and y < -1.52]
    lensR = sweep("h83_glass_signal_R", pts, nrm, lens_prof, min(idx), max(idx))
    i_mid = min(range(len(pts)), key=lambda i: abs(pts[i][0] - 0.60) + (0 if pts[i][1] < -1.5 else 9))
    sig = pts[i_mid]
    return ({PREFIX + "bumper_F": [body], PREFIX + "bumper_signal_FL": [lensL],
             PREFIX + "bumper_signal_FR": [lensR]}, (sig[0], sig[1], 0.4385))


def bumper_rear():
    pts, nrm = superellipse_path(**REAR_PATH)
    body = sweep("h83_black_plastic", pts, nrm, BUMPER_PROFILE_R)
    return {PREFIX + "bumper_R": [body]}


# ------------------------------------------------------------ taillights
TL_C = (0.42, 1.55)          # ray fan center (plan)
TL_PHI = (-31.0, 78.0)       # degrees: 0 = straight back, 90 = straight out to the side
TL_ZB = 0.482
TL_ZT_LOW = 0.655            # top below the tailgate
TL_ZT_HIGH = 0.775           # top of the corner (pillar) section
TL_BORDER = 0.006
TL_DIV = 0.531               # black divider between the amber/clear band and the red


def taillight_left(raycast):
    """raycast(origin, direction) -> hit point (x,y,z) or None, against the bare body."""
    cxp, cyp = TL_C
    phis = []
    nphi = 60
    for i in range(nphi + 1):
        phis.append(TL_PHI[0] + (TL_PHI[1] - TL_PHI[0]) * i / nphi)

    def ray(phi, z):
        d = (math.sin(math.radians(phi)), math.cos(math.radians(phi)))
        o = (cxp + d[0] * 2.5, cyp + d[1] * 2.5, z)
        return raycast(o, (-d[0], -d[1], 0.0)), d

    # column top height depends on whether the hit is on the corner pillar
    cols = []
    for phi in phis:
        h, d = ray(phi, 0.60)
        x = h[0] if h else 0.0
        f = min(max((x - 0.630) / 0.03, 0.0), 1.0)
        f = f * f * (3 - 2 * f)
        cols.append((phi, d, TL_ZB, TL_ZT_LOW + (TL_ZT_HIGH - TL_ZT_LOW) * f, x))

    # z rows (identical count for every column): border | amber/clear band |
    # divider | red ... | border.  Row index 3 is the divider band.
    rows_front, rows_v = [], []
    for phi, d, zb, zt, _ in cols:
        col = []
        zlist = [zb, zb + TL_BORDER, 0.505, TL_DIV, TL_DIV + 0.006, 0.565, 0.595]
        zlist += [0.62 + (zt - TL_BORDER - 0.62) * k / 4 for k in range(5)]
        zlist += [zt]
        hits = []
        for z in zlist:
            zz = z
            # bridge the old lamp pocket (z 0.53..0.60) by interpolating
            if 0.525 < z < 0.605:
                h0, _ = ray(phi, 0.52)
                h1, _ = ray(phi, 0.61)
                t = (z - 0.52) / 0.09
                h = tuple(h0[i] + (h1[i] - h0[i]) * t for i in range(3)) if h0 and h1 else None
            else:
                h, _ = ray(phi, zz)
            hits.append((h, z))
        for h, z in hits:
            if h is None or math.hypot(h[0] - cxp, h[1] - cyp) > 0.45:
                raise RuntimeError(f"taillight ray missed the rear body: phi={phi} z={z} hit={h}")
            col.append((h[0] + d[0] * 0.010, h[1] + d[1] * 0.010, z))
        rows_front.append(col)
        rows_v.append([z for _, z in hits])
    # transpose to rows over phi for each z-index
    nz = len(rows_front[0])
    front_rows = [[rows_front[j][i] for j in range(len(cols))] for i in range(nz)]

    # per-face material by (phi index, z) cell centre
    xs_at = [c[4] for c in cols]

    def cell_mat(j, i):
        if i == 0 or i == nz - 2 or j == 0 or j == len(cols) - 2 or i == 3:
            return "h83_black_trim"   # housing border + divider
        if i < 3:
            return "h83_glass_reverse" if xs_at[j] < 0.42 else "h83_glass_signal_L"
        return "h83_glass_taillight"

    by_mat = {}
    for i in range(nz - 1):
        for j in range(len(cols) - 1):
            m = cell_mat(j, i)
            p = by_mat.setdefault(m, M.Part(m))
            a = p.add(front_rows[i][j]); b = p.add(front_rows[i][j + 1])
            c = p.add(front_rows[i + 1][j + 1]); dd = p.add(front_rows[i + 1][j])
            p.f += [(a, b, c), (a, c, dd)]
    # skirt: outline back toward the body (black)
    outline = ([front_rows[0][j] for j in range(len(cols))] +
               [front_rows[i][-1] for i in range(1, nz)] +
               [front_rows[-1][j] for j in range(len(cols) - 2, -1, -1)] +
               [front_rows[i][0] for i in range(nz - 2, 0, -1)])
    dirs = ([cols[j][1] for j in range(len(cols))] + [cols[-1][1]] * (nz - 1) +
            [cols[j][1] for j in range(len(cols) - 2, -1, -1)] + [cols[0][1]] * (nz - 2))
    back = [(q[0] - d[0] * 0.016, q[1] - d[1] * 0.016, q[2]) for q, d in zip(outline, dirs)]
    skirt = M.grid("h83_black_trim", [outline, back], closed_u=True)
    ctr = (0.58, 1.70, (TL_ZB + TL_ZT_LOW) / 2)
    orient_each(skirt, lambda c: (c[0] - ctr[0], c[1] - ctr[1], c[2] - ctr[2]))
    for p in by_mat.values():
        orient_each(p, lambda c: (c[0] - TL_C[0], c[1] - TL_C[1], 0.0))
    parts = list(by_mat.values()) + [skirt]

    # bulb anchor points (front surface, slightly inside)
    def pt(phi, z):
        h, d = ray(phi, z)
        return (round(h[0] - d[0] * 0.01, 3), round(h[1] - d[1] * 0.01, 3), round(z, 3))
    j_rev = max(j for j in range(len(cols)) if xs_at[j] < 0.38)
    j_sig = min(j for j in range(len(cols)) if xs_at[j] > 0.58)
    bulbs = {
        "brake": pt(30.0, 0.60), "brake_upper": pt(68.0, 0.70),
        "signal": pt(phis[j_sig], 0.505), "reverse": pt(phis[max(j_rev - 2, 1)], 0.505),
        "plate": (0.312, 1.80, 0.545),
    }
    return {PREFIX + "taillight_RL": parts}, bulbs


# ------------------------------------------------------------ steel wheel
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
        b = M.loft("h83_wheel_silver", secs)
        M.orient_outward(b)
        parts.append(b)
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

"""Procedural lamp-lens textures for the '83 Hatch.

h83_lens_prism_n.png : tiling normal map of small square prism "pyramids" (16 x 16
                       cells per tile) like the optics on early-80s tail lamp lenses.

python3 -I make_textures.py OUT_DIR
"""
import math
import os
import sys

from PIL import Image

N = 512
CELLS = 16
STRENGTH = 0.55


def prism_normal():
    img = Image.new("RGB", (N, N))
    px = img.load()
    c = N // CELLS
    for y in range(N):
        v = (y % c + 0.5) / c * 2 - 1
        for x in range(N):
            u = (x % c + 0.5) / c * 2 - 1
            # square pyramid with a small flat top and a thin groove between cells
            au, av = abs(u), abs(v)
            if max(au, av) > 0.9:                       # groove between prisms
                gx, gy = (-math.copysign(1, u) * 0.6 if au >= av else 0.0,
                          -math.copysign(1, v) * 0.6 if av > au else 0.0)
            elif max(au, av) < 0.25:                    # flat top
                gx = gy = 0.0
            elif au >= av:
                gx, gy = math.copysign(1, u) * STRENGTH, 0.0
            else:
                gx, gy = 0.0, math.copysign(1, v) * STRENGTH
            nx, ny, nz = -gx, gy, 1.0
            l = math.sqrt(nx * nx + ny * ny + nz * nz)
            px[x, y] = tuple(int(round((k / l * 0.5 + 0.5) * 255)) for k in (nx, ny, nz))
    return img


if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    prism_normal().save(os.path.join(out, "h83_lens_prism_n.png"))
    print("wrote", os.path.join(out, "h83_lens_prism_n.png"))

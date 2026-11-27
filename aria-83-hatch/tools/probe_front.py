"""Blender: sample hood / fender / door / front surfaces of the Aria for the front-clip rebuild."""
import json, sys, bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
dae, out = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.collada_import(filepath=dae)
def tree(names):
    vs, ps = [], []
    for n in names:
        ob = bpy.data.objects[n]; base = len(vs)
        vs += [ob.matrix_world @ v.co for v in ob.data.vertices]
        ps += [tuple(i + base for i in p.vertices) for p in ob.data.polygons]
    return BVHTree.FromPolygons(vs, ps)
T = {k: tree(v) for k, v in {
    "hood": ["ariahatch_hood_late"], "fender": ["ariahatch_fender_L_late"], "door": ["ariahatch_door_L"],
    "body": ["ariahatch_body"], "front": ["ariahatch_frontpanel_late", "ariahatch_fascia_F_late"],
    "shell": ["ariahatch_hood_late", "ariahatch_fender_L_late", "ariahatch_door_L", "ariahatch_body",
              "ariahatch_frontpanel_late", "ariahatch_windshield"]}.items()}
def hit(t, o, d):
    h = T[t].ray_cast(Vector(o), Vector(d))
    return None if h[0] is None else [round(c, 4) for c in h[0]]
res = {"top": [], "side": [], "front": []}
for i in range(42):
    x = 0.02 * i
    for j in range(60):
        y = -1.80 + 0.02 * j
        h = hit("shell", (x, y, 3), (0, 0, -1))
        if h: res["top"].append([x, y, h[2]])
for j in range(70):
    y = -1.80 + 0.02 * j
    for k in range(45):
        z = 0.20 + 0.02 * k
        h = hit("shell", (3, y, z), (-1, 0, 0))
        if h: res["side"].append([y, z, h[0]])
for i in range(42):
    x = 0.02 * i
    for k in range(45):
        z = 0.20 + 0.02 * k
        h = hit("shell", (x, -4, z), (0, 1, 0))
        if h: res["front"].append([x, z, h[1]])
json.dump(res, open(out, "w"))
print("probe front done", {k: len(v) for k, v in res.items()})

"""Blender: raycast the Aria body to get front/rear/side surface tables.

blender -b --factory-startup --python probe_body.py -- ARIA.dae OUT.json
"""
import json
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

dae, out = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.collada_import(filepath=dae)

SHELL = ["ariahatch_body", "ariahatch_fender_L_late", "ariahatch_fender_R_late", "ariahatch_door_L",
         "ariahatch_door_R", "ariahatch_hood_late", "ariahatch_tailgate", "ariahatch_frontpanel_late",
         "ariahatch_fascia_F_late", "ariahatch_headlight_FL_late", "ariahatch_headlight_FR_late",
         "ariahatch_taillight_RL_late", "ariahatch_taillight_RR_late"]
dg = bpy.context.evaluated_depsgraph_get()
trees = {}
for n in SHELL + ["ariahatch_bumper_F_late", "ariahatch_bumper_R_late"]:
    ob = bpy.data.objects.get(n)
    if ob is None:
        print("missing", n)
        continue
    me = ob.evaluated_get(dg).to_mesh()
    verts = [ob.matrix_world @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    trees[n] = BVHTree.FromPolygons(verts, polys)


def cast(names, origin, direction):
    best = None
    for n in names:
        t = trees.get(n)
        if not t:
            continue
        hit = t.ray_cast(Vector(origin), Vector(direction))
        if hit[0] is not None and (best is None or hit[3] < best[1]):
            best = (hit[0], hit[3], n)
    return best


res = {"rear": [], "front": [], "side": [], "bumperF": [], "bumperR": []}
zs = [round(0.20 + 0.02 * i, 3) for i in range(40)]
xs = [round(0.02 * i, 3) for i in range(42)]
for z in zs:
    for x in xs:
        h = cast(SHELL, (x, 4, z), (0, -1, 0))
        if h:
            res["rear"].append([x, z, round(h[0].y, 4), h[2]])
        h = cast(SHELL, (x, -4, z), (0, 1, 0))
        if h:
            res["front"].append([x, z, round(h[0].y, 4), h[2]])
        h = cast(["ariahatch_bumper_F_late"], (x, -4, z), (0, 1, 0))
        if h:
            res["bumperF"].append([x, z, round(h[0].y, 4)])
        h = cast(["ariahatch_bumper_R_late"], (x, 4, z), (0, -1, 0))
        if h:
            res["bumperR"].append([x, z, round(h[0].y, 4)])
for z in zs:
    for i in range(80):
        y = round(-1.9 + 0.05 * i, 3)
        h = cast(SHELL, (3, y, z), (-1, 0, 0))
        if h:
            res["side"].append([y, z, round(h[0].x, 4), h[2]])
json.dump(res, open(out, "w"))
print("probe done", {k: len(v) for k, v in res.items()})

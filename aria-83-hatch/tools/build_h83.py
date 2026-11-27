"""Blender 4.5: build the Aria '83 Hatch meshes and export hatch83.dae.

blender -b --factory-startup --python build_h83.py -- --aria ARIA.dae --dae OUT.dae --meta OUT.json
"""
import argparse
import json
import os
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import h83_geom as G  # noqa: E402
import meshkit as M  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
ap = argparse.ArgumentParser()
ap.add_argument("--aria", required=True)
ap.add_argument("--dae", required=True)
ap.add_argument("--meta", required=True)
a = ap.parse_args(argv)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.collada_import(filepath=a.aria)
def bvh_of(*names):
    vs, ps = [], []
    for name in names:
        ob = bpy.data.objects[name]
        base = len(vs)
        vs += [ob.matrix_world @ v.co for v in ob.data.vertices]
        ps += [tuple(i + base for i in p.vertices) for p in ob.data.polygons]
    return BVHTree.FromPolygons(vs, ps)


bvh = bvh_of("ariahatch_body")
bvh_door = bvh_of("ariahatch_door_L")
bvh_rear = bvh_of("ariahatch_body", "ariahatch_tailgate")
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
for me in list(bpy.data.meshes):
    bpy.data.meshes.remove(me)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat)


def raycast(o, d, tree=None):
    h = (tree or bvh).ray_cast(Vector(o), Vector(d))
    return tuple(h[0]) if h[0] is not None else None


def raycast_door(o, d):
    return raycast(o, d, bvh_door)


def raycast_rear(o, d):
    return raycast(o, d, bvh_rear)


MATS = {}


def mat(name):
    if name not in MATS:
        MATS[name] = bpy.data.materials.new(name)
    return MATS[name]


def make_object(name, parts):
    groups = M.finalize(parts)
    verts, norms, faces, midx, mats = [], [], [], [], []
    for slot, (P, N, T) in groups.items():
        if slot not in mats:
            mats.append(slot)
        base = len(verts)
        verts += P
        norms += N
        faces += [(i + base, j + base, k + base) for i, j, k in T]
        midx += [mats.index(slot)] * len(T)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    for m in mats:
        me.materials.append(mat(m))
    me.polygons.foreach_set("material_index", midx)
    me.shade_smooth()
    me.normals_split_custom_set_from_vertices(norms)
    uv = me.uv_layers.new(name="UVMap")
    paint_idx = mats.index(G.PAINT) if G.PAINT in mats else -1
    prism_idx = {i for i, m in enumerate(mats) if m in G.PRISM_MATS}
    for poly in me.polygons:
        n = poly.normal
        for li in poly.loop_indices:
            p = verts[me.loops[li].vertex_index]
            if poly.material_index == paint_idx:
                uv.data[li].uv = G.PAINT_UV        # take the car's paint from the Aria's body material
            elif poly.material_index in prism_idx:
                # planar projection on the dominant axis; one tile = PRISM_TILE metres
                k = 1.0 / G.PRISM_TILE
                if abs(n.y) >= abs(n.x) and abs(n.y) >= abs(n.z):
                    uv.data[li].uv = (p[0] * k, p[2] * k)
                elif abs(n.x) >= abs(n.z):
                    uv.data[li].uv = (p[1] * k, p[2] * k)
                else:
                    uv.data[li].uv = (p[0] * k, p[1] * k)
            else:
                uv.data[li].uv = (p[0] * 2 + 0.5, p[2] * 2 + 0.5)
    me.validate(clean_customdata=False)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    print(f"  {name}: {len(verts)} verts, {len(faces)} tris, mats={mats}")
    return ob


def lr(name):
    for a, b in (("_FL", "_FR"), ("_RL", "_RR"), ("_L", "_R")):
        if name.endswith(a):
            return name[: -len(a)] + b
    return name


def add_lr(meshes):
    for name, parts in meshes.items():
        make_object(name, parts)
        mirrored = G.mirror_x(parts)
        for p in mirrored:
            p.mat = p.mat.replace("signal_L", "signal_R")
        make_object(lr(name), mirrored)


meta = {}
print("front clip")
for n, p in G.hood().items():
    make_object(n, p)
fender, meta["fender_marker_L"] = G.fender_left()
add_lr(fender)
for builder in (G.front_panel, G.fascia, G.grille):
    for n, p in builder().items():
        make_object(n, p)
add_lr(G.headlight_left())
print("bumpers")
fb, meta["bumper_signal_L"] = G.bumper_front()
for n, p in fb.items():
    make_object(n, p)
for n, p in G.bumper_rear().items():
    make_object(n, p)
print("rear")
for n, p in G.rear_filler().items():
    make_object(n, p)
tl, meta["taillight_bulbs_L"] = G.taillight_left(raycast_rear)
add_lr(tl)
print("side trim")
add_lr(G.side_trim_left(raycast_door, raycast))
print("wheel")
for n, p in G.steel_wheel().items():
    make_object(n, p)
meta["plate_R_pos"] = (0.0, round(G.rear_panel_y(0.0, G.PLATE_R_Z) + 0.006, 3), G.PLATE_R_Z)

bpy.ops.object.select_all(action="SELECT")
os.makedirs(os.path.dirname(os.path.abspath(a.dae)), exist_ok=True)
r = bpy.ops.wm.collada_export(filepath=a.dae, check_existing=False, selected=True, triangulate=True,
                              sort_by_name=True, apply_global_orientation=False)
print("collada export", r, a.dae)
meta["meshes"] = sorted(o.name for o in bpy.data.objects)
meta["materials"] = sorted(MATS)
json.dump(meta, open(a.meta, "w"), indent=1)
print("meta", meta)

"""Blender 4.5 (COLLADA-capable) build script for the Kestrel K5 wheel.

Usage:
  blender -b --factory-startup --python build_blend.py -- \
      --dae OUT.dae [--renders DIR] [--hdri FILE.exr] [--samples N]
"""
import argparse
import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import k5_mesh as K  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--dae", required=True)
ap.add_argument("--renders")
ap.add_argument("--hdri")
ap.add_argument("--samples", type=int, default=96)
ap.add_argument("--blend")
args = ap.parse_args(argv)

PREFIX = "kestrel_k5"
FINISHES = {          # suffix: material used for the spokes/center
    "s": "kestrel_k5_polished",
    "b": "kestrel_k5_black",
    "c": "kestrel_k5_paint",
}
SLOT_MAT = {"lip": "kestrel_k5_polished", "chrome": "kestrel_k5_chrome"}

# ------------------------------------------------------------ clean scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def principled(name, color, metallic, rough, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    b.inputs["Coat Weight"].default_value = coat
    m.diffuse_color = (*color, 1.0)
    return m


MATS = {
    "kestrel_k5_polished": principled("kestrel_k5_polished", (0.86, 0.87, 0.89), 1.0, 0.13),
    "kestrel_k5_chrome":   principled("kestrel_k5_chrome", (0.95, 0.95, 0.97), 1.0, 0.04),
    "kestrel_k5_black":    principled("kestrel_k5_black", (0.018, 0.018, 0.02), 0.0, 0.32, coat=0.6),
    "kestrel_k5_paint":    principled("kestrel_k5_paint", (0.55, 0.03, 0.025), 0.2, 0.3, coat=1.0),
}


def make_object(name, groups, matmap):
    """groups: {slot: (positions, normals, tris)}; matmap: slot -> material name."""
    verts, norms, faces, mat_idx = [], [], [], []
    mats = []
    for slot, (P, N, T) in groups.items():
        mname = matmap[slot]
        if mname not in mats:
            mats.append(mname)
        mi = mats.index(mname)
        base = len(verts)
        verts += P
        norms += N
        faces += [(a+base, b+base, c+base) for a, b, c in T]
        mat_idx += [mi]*len(T)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    for m in mats:
        me.materials.append(MATS[m])
    me.polygons.foreach_set("material_index", mat_idx)
    me.shade_smooth()
    me.normals_split_custom_set_from_vertices(norms)
    uv = me.uv_layers.new(name="UVMap")
    for loop in me.loops:
        p = verts[loop.vertex_index]
        uv.data[loop.index].uv = (0.5 + p[1]*2.0, 0.5 + p[2]*2.0)
    me.validate(clean_customdata=False)
    me.update()
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    return ob


# ------------------------------------------------------------ build wheels
wheels = {}
for size in K.SIZES:
    groups = K.finalize(K.build_wheel(size))
    for fin, face_mat in FINISHES.items():
        name = f"{PREFIX}_{size}_{fin}"
        mm = dict(SLOT_MAT, face=face_mat)
        wheels[(size, fin)] = make_object(name, groups, mm)
print("built", len(wheels), "wheel objects")

# ------------------------------------------------------------ export
bpy.ops.object.select_all(action="DESELECT")
for ob in wheels.values():
    ob.select_set(True)
bpy.context.view_layer.objects.active = next(iter(wheels.values()))
os.makedirs(os.path.dirname(os.path.abspath(args.dae)), exist_ok=True)
res = bpy.ops.wm.collada_export(
    filepath=args.dae, check_existing=False, selected=True, apply_modifiers=True,
    triangulate=True, sort_by_name=True, use_texture_copies=False,
    export_global_forward_selection="Y", export_global_up_selection="Z",
    apply_global_orientation=False,
)
print("collada export:", res, args.dae)

if args.blend:
    bpy.ops.wm.save_as_mainfile(filepath=args.blend)

if not args.renders:
    sys.exit(0)

# ------------------------------------------------------------ preview renders
os.makedirs(args.renders, exist_ok=True)
tire_mat = MATS["preview_tire"] = principled("preview_tire", (0.025, 0.025, 0.027), 0.0, 0.75)
ground_mat = principled("preview_ground", (0.16, 0.16, 0.17), 0.0, 0.55)


def tire_for(size):
    s = K.SIZES[size]
    xi, xo, rb = s["xi"], s["xo"], s["D"]*0.0127
    h = 0.115 if s["D"] == 15 else (0.105 if s["D"] == 16 else 0.085)
    prof = [(xi+0.006, rb+0.004), (xi-0.010, rb+0.03), (xi-0.018, rb+h*0.62),
            (xi-0.012, rb+h*0.9), (xi+0.012, rb+h), (xo-0.012, rb+h),
            (xo+0.012, rb+h*0.9), (xo+0.018, rb+h*0.62), (xo+0.010, rb+0.03),
            (xo-0.006, rb+0.004), (xo-0.02, rb+0.001), (xi+0.02, rb+0.001)]
    p = K.lathe("tire", prof, n=128)
    K.orient_outward(p)
    g = K.finalize([p], smooth_deg=50)
    ob = make_object(f"preview_tire_{size}", g, {"tire": "preview_tire"})
    return ob, rb + h


world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
wn = world.node_tree.nodes
bg = wn["Background"]
if args.hdri:
    env = wn.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(args.hdri)
    world.node_tree.links.new(env.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.2
else:
    bg.inputs["Color"].default_value = (0.7, 0.7, 0.75, 1)

bpy.ops.mesh.primitive_plane_add(size=20)
ground = bpy.context.active_object
ground.data.materials.append(ground_mat)

sun = bpy.data.objects.new("key", bpy.data.lights.new("key", "SUN"))
sun.data.energy = 2.5
sun.data.angle = math.radians(8)
sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(60))
scene.collection.objects.link(sun)

cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
scene.collection.objects.link(cam)
scene.camera = cam

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = args.samples
scene.cycles.use_denoising = True
scene.render.film_transparent = False
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"


def look_at(ob, target):
    from mathutils import Vector
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def stage(items, cam_loc, target, lens, res, out, with_tires=True, spin=0.0):
    """items: list of ((size, fin), (y, x_offset))."""
    for ob in scene.collection.objects:
        ob.hide_render = ob.name.startswith(("kestrel_k5_", "preview_tire_"))
    extra = []
    for key, (y, xoff) in items:
        size = key[0]
        ob = wheels[key]
        tire_r = 0.33
        if with_tires:
            t, tire_r = tire_for(size)
            extra.append(t)
        else:
            tire_r = K.SIZES[size]["rf"]
        for o in ([ob] + ([extra[-1]] if with_tires else [])):
            o.hide_render = False
            o.location = (xoff, y, tire_r)
            o.rotation_euler = (spin, 0, 0)
    ground.location = (0, 0, 0)
    cam.location = cam_loc
    cam.data.lens = lens
    look_at(cam, target)
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    for o in extra:
        bpy.data.objects.remove(o, do_unlink=True)
    for key, _ in items:
        wheels[key].location = (0, 0, 0)
        wheels[key].rotation_euler = (0, 0, 0)
    print("rendered", out)


R = args.renders
# hero 3/4 shot, colorable (shown in red)
stage([(("15x8", "c"), (0, 0))], (1.25, -0.75, 0.55), (0.02, 0, 0.30), 70,
      (1400, 1050), os.path.join(R, "hero_15x8_colorable.png"))
# finish lineup
stage([(("15x8", "s"), (-0.75, 0)), (("15x8", "b"), (0, 0)), (("15x8", "c"), (0.75, 0))],
      (3.3, -0.25, 0.6), (0.0, 0, 0.30), 50, (1800, 800),
      os.path.join(R, "lineup_finishes.png"), spin=math.radians(18))
# size lineup, no tires, polished
order = ["15x8", "15x9", "15x10", "16x8", "18x8", "18x9", "18x10"]
stage([((sz, "s"), (-1.65 + i*0.55, 0)) for i, sz in enumerate(order)],
      (4.6, -0.6, 1.1), (0.0, 0, 0.22), 50, (2000, 800),
      os.path.join(R, "lineup_sizes.png"), with_tires=False)
# inboard/back side check
stage([(("18x10", "s"), (0, 0))], (-1.0, -0.6, 0.45), (0, 0, 0.25), 70,
      (1000, 800), os.path.join(R, "back_18x10.png"), with_tires=False)

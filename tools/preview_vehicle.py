"""Render a BeamNG vehicle config in Blender (4.5) for visual comparison.

blender -b --factory-startup --python preview_vehicle.py -- \
    --dae A.dae [B.dae ...] --meshes meshes.txt --tex TEXDIR --out OUTDIR \
    [--paint 0.45,0.6,0.8] [--hdri X.exr] [--samples 48] [--wheels wheels.json] \
    [--views fl,rl,fr,side,front,rear] [--blend out.blend]

meshes.txt: one mesh name per line (flexbodies of the resolved config).
wheels.json: [{"mesh": name, "pos": [x,y,z], "flip": bool, "tire_r": r, "tire_w": w}, ...]
BeamNG vehicle space: front = -Y, left = +X, up = +Z.
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--dae", nargs="+", required=True)
ap.add_argument("--meshes", required=True)
ap.add_argument("--tex", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--paint", default="0.42,0.58,0.78")
ap.add_argument("--hdri")
ap.add_argument("--samples", type=int, default=48)
ap.add_argument("--wheels")
ap.add_argument("--views", default="fl,rl,fr,side")
ap.add_argument("--res", default="1400,900")
ap.add_argument("--blend")
ap.add_argument("--prefix", default="")
ap.add_argument("--matjson", nargs="*", default=[], help="BeamNG materials.json files (factor-only materials)")
ap.add_argument("--glow", help="json {daeMaterial: {off: material}} (glowMap)")
a = ap.parse_args(argv)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
for d in a.dae:
    bpy.ops.wm.collada_import(filepath=d)

want = {l.strip() for l in open(a.meshes) if l.strip()}
present = {}
for ob in list(bpy.data.objects):
    if ob.type != "MESH":
        if ob.type in ("LIGHT", "CAMERA"):
            bpy.data.objects.remove(ob, do_unlink=True)
        continue
    present[ob.name] = ob
    ob.hide_render = ob.name not in want
missing = sorted(want - set(present))
print("meshes shown:", len(want & set(present)), "missing:", missing)

paint = tuple(float(c) for c in a.paint.split(",")) + (1.0,)
FACTORS = {}
for f in a.matjson:
    FACTORS.update(json.load(open(f)))
GLOW = json.load(open(a.glow)) if a.glow else {}
tex_cache = {}


def tex(name, colorspace="sRGB"):
    p = os.path.join(a.tex, name + ".png")
    if not os.path.exists(p):
        return None
    if p not in tex_cache:
        img = bpy.data.images.load(p)
        img.colorspace_settings.name = colorspace
        tex_cache[p] = img
    return tex_cache[p]


def setup_material(mat):
    base = mat.name.split(".")[0]
    if base.endswith("-material"):
        base = base[: -len("-material")]
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    I = bsdf.inputs
    I["Roughness"].default_value = 0.45
    low = base.lower()

    def imgnode(img):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = img
        return n

    fb = FACTORS.get(GLOW.get(base, {}).get("off", base))
    if fb:
        st = fb["Stages"][0]
        I["Base Color"].default_value = tuple(st.get("baseColorFactor", [0.5, 0.5, 0.5, 1]))
        I["Metallic"].default_value = st.get("metallicFactor", 0)
        I["Roughness"].default_value = st.get("roughnessFactor", 0.5)
        I["Coat Weight"].default_value = st.get("clearCoatFactor", 0)
        I["Alpha"].default_value = st.get("opacityFactor", 1.0)
        return
    if "glass" in low or low == "mirror" or "windshield" in low:
        I["Base Color"].default_value = (0.02, 0.025, 0.03, 1)
        I["Roughness"].default_value = 0.02
        I["Alpha"].default_value = 0.45
        mat.blend_method = "BLEND" if hasattr(mat, "blend_method") else None
        if "glass_" in low and "int" not in low and "dmg" not in low and low != "ariahatch_glass":
            # lamp lenses
            I["Base Color"].default_value = (0.8, 0.8, 0.8, 1)
            I["Alpha"].default_value = 0.6
        return
    b = tex(base + "_b.color")
    if b is None and base.startswith("kestrel") is False:
        I["Base Color"].default_value = (0.35, 0.35, 0.36, 1)
    if b is not None:
        tb = imgnode(b)
        c = tex(base + "_c.data", "Non-Color")
        if c is not None:
            tc = imgnode(c)
            mix = nt.nodes.new("ShaderNodeMix")
            mix.data_type = "RGBA"
            nt.links.new(tc.outputs["Color"], mix.inputs["Factor"])
            nt.links.new(tb.outputs["Color"], mix.inputs["A"])
            mix.inputs["B"].default_value = paint
            nt.links.new(mix.outputs["Result"], I["Base Color"])
            I["Coat Weight"].default_value = 0.6
        else:
            nt.links.new(tb.outputs["Color"], I["Base Color"])
        o = tex(base + "_o.data", "Non-Color")
        if o is not None:
            to = imgnode(o)
            nt.links.new(to.outputs["Color"], I["Alpha"])
    m = tex(base + "_m.data", "Non-Color")
    if m is not None:
        nt.links.new(imgnode(m).outputs["Color"], I["Metallic"])
    else:
        I["Metallic"].default_value = 0.0
    r = tex(base + "_r.data", "Non-Color")
    if r is not None:
        nt.links.new(imgnode(r).outputs["Color"], I["Roughness"])


for mat in bpy.data.materials:
    setup_material(mat)

# ---------------------------------------------------------------- wheels/tires
tire_mat = bpy.data.materials.new("preview_tire")
tire_mat.use_nodes = True
tb = tire_mat.node_tree.nodes["Principled BSDF"]
tb.inputs["Base Color"].default_value = (0.03, 0.03, 0.03, 1)
tb.inputs["Roughness"].default_value = 0.8
ground_z = None
if a.wheels:
    for w in json.load(open(a.wheels)):
        gz = w["pos"][2] - w["tire_r"]
        ground_z = gz if ground_z is None else min(ground_z, gz)
        pos = Vector(w["pos"])
        src = present.get(w["mesh"])
        if src is not None:
            ob = src.copy()
            scene.collection.objects.link(ob)
            ob.hide_render = False
            ob.location = pos
            if w.get("flip"):
                ob.rotation_euler = (0, 0, math.pi)
        bpy.ops.mesh.primitive_torus_add(
            major_radius=w["tire_r"] - w["tire_w"] * 0.32, minor_radius=w["tire_w"] * 0.5,
            major_segments=96, minor_segments=24, location=pos, rotation=(0, math.pi / 2, 0))
        t = bpy.context.active_object
        t.scale = (1, 1, 1)
        t.data.materials.append(tire_mat)
        bpy.ops.object.shade_smooth()
    for w in json.load(open(a.wheels)):
        if w["mesh"] in present:
            present[w["mesh"]].hide_render = True

# ---------------------------------------------------------------- stage
world = bpy.data.worlds.new("W")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
if a.hdri:
    env = world.node_tree.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(a.hdri)
    world.node_tree.links.new(env.outputs["Color"], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 1.0

bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
gnd = bpy.context.active_object
gm = bpy.data.materials.new("ground")
gm.use_nodes = True
gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.12, 0.12, 0.13, 1)
gm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.7
gnd.data.materials.append(gm)

sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
sun.data.energy = 3.0
sun.data.angle = math.radians(5)
sun.rotation_euler = (math.radians(40), 0, math.radians(-30))
scene.collection.objects.link(sun)

cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
scene.collection.objects.link(cam)
scene.camera = cam
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = a.samples
scene.cycles.use_denoising = True
scene.view_settings.view_transform = "AgX"
scene.render.resolution_x, scene.render.resolution_y = (int(v) for v in a.res.split(","))

# vehicle center from visible meshes
pts = []
for ob in scene.objects:
    if ob.type == "MESH" and not ob.hide_render and ob is not gnd:
        for c in ob.bound_box:
            pts.append(ob.matrix_world @ Vector(c))
mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
ctr = (mn + mx) / 2
print("vehicle bounds", tuple(round(v, 3) for v in mn), tuple(round(v, 3) for v in mx))
gnd.location.z = ground_z if ground_z is not None else mn.z

VIEWS = {  # direction from center (x=left, y=rear), height, lens
    "fl": ((1.0, -1.25), 1.2, 50),
    "fr": ((-1.0, -1.25), 1.2, 50),
    "rl": ((1.0, 1.2), 1.2, 50),
    "rr": ((-1.0, 1.2), 1.2, 50),
    "side": ((1.0, 0.0), 0.9, 50),
    "front": ((0.0, -1.0), 0.9, 60),
    "rear": ((0.0, 1.0), 0.9, 60),
}
os.makedirs(a.out, exist_ok=True)
for v in a.views.split(","):
    (dx, dy), h, lens = VIEWS[v]
    d = Vector((dx, dy, 0)).normalized()
    dist = 7.0 if v in ("fl", "fr", "rl", "rr", "side") else 6.0
    cam.location = ctr + d * dist + Vector((0, 0, h))
    cam.data.lens = lens
    look = (ctr + Vector((0, 0, -0.1))) - cam.location
    cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(a.out, f"{a.prefix}{v}.png")
    bpy.ops.render.render(write_still=True)
    print("rendered", scene.render.filepath)

if a.blend:
    bpy.ops.wm.save_as_mainfile(filepath=a.blend)

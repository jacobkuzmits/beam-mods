import sys, bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
dae = sys.argv[sys.argv.index("--")+1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.collada_import(filepath=dae)
ob = bpy.data.objects["ariahatch_body"]
me = ob.data
t = BVHTree.FromPolygons([ob.matrix_world @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
xs = [0.30 + 0.02*i for i in range(25)]
print("BODY-ONLY rear y; cols x:", " ".join("%5.2f" % x for x in xs))
for k in range(16):
    z = 0.44 + 0.025*k
    row = []
    for x in xs:
        h = t.ray_cast(Vector((x, 4, z)), Vector((0, -1, 0)))
        row.append("%5.3f" % h[0].y if h[0] else "  -  ")
    print("z %.3f " % z + " ".join(row))

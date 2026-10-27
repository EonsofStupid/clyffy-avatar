"""Orbit the head at fixed angles. NO facing detection — every view is labelled by its own angle.

    blender -b --python tools/head_orbit.py -- <model> <out_dir> [steps]

Written because the asymmetry-based facing detector returned 158 deg in one tool and 36 deg in
another from marginally different head bands, and then labelled a three-quarter FRONT view as
"head_back". A detector that disagrees with itself cannot be used to label evidence. Twelve fixed
views need no detector and cannot mislabel anything.
"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC = os.path.abspath(argv[0])
OUT = os.path.abspath(argv[1])
STEPS = int(argv[2]) if len(argv) > 2 else 12
os.makedirs(OUT, exist_ok=True)
TAG = os.path.splitext(os.path.basename(SRC))[0]

bpy.ops.wm.read_factory_settings(use_empty=True)
ext = os.path.splitext(SRC)[1].lower()
if ext == ".fbx":
    bpy.ops.import_scene.fbx(filepath=SRC)
else:
    bpy.ops.import_scene.gltf(filepath=SRC)

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
ob = max(meshes, key=lambda o: len(o.data.vertices))
co = np.array([(o.matrix_world @ v.co)[:] for o in meshes for v in o.data.vertices])
z = co[:, 2]
zlo, zhi = z.min(), z.max()
head = co[z > zlo + 0.70 * (zhi - zlo)]
hc = head.mean(axis=0)
head_r = float(np.abs(head - hc).max())
print(f"{TAG}: head centre {tuple(round(float(v),3) for v in hc)}  radius {head_r:.3f}")

sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = 640
sc.render.resolution_y = 640
w = bpy.data.worlds.new("W"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 1.6
sc.world = w

R = float(zhi - zlo) * 3
cd = bpy.data.cameras.new("C"); cam = bpy.data.objects.new("C", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"; cd.ortho_scale = head_r * 2.5
ctr = Vector((float(hc[0]), float(hc[1]), float(hc[2])))

step = 360 // STEPS
for i in range(STEPS):
    deg = i * step
    a = math.radians(deg)
    cam.location = (ctr.x + math.sin(a) * R, ctr.y - math.cos(a) * R, ctr.z)
    cam.rotation_euler = (math.radians(90), 0, a)
    sc.render.filepath = os.path.join(OUT, f"{TAG}_orbit_{deg:03d}.png")
    bpy.ops.render.render(write_still=True)
print(f"  wrote {STEPS} orbit views")

# top-down too — horn count and symmetry are unambiguous from above
cam.location = (ctr.x, ctr.y, ctr.z + R)
cam.rotation_euler = (0, 0, 0)
sc.render.filepath = os.path.join(OUT, f"{TAG}_orbit_top.png")
bpy.ops.render.render(write_still=True)
print("  wrote top view")

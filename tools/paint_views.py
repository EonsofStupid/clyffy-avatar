"""Textured views on a NON-WHITE background, so white fur cannot read as a hole.

    blender -b --python tools/paint_views.py -- <model> <out_dir> [--body] [angles...]

The 2026-08-05 DECIDE sheet was rendered on a pure white world. Clyffy's muzzle, jaw and cheek
band are WHITE, so on that sheet a third of the head silhouette dropped out into the background
and the model read as having a giant hole in it. The clay audit (tools/hole_audit.py) proved the
geometry there is closed. A white character is never to be judged on a white field again.

Background here is mid grey-green — off every colour the character actually wears (white fur,
brown patches, pink muzzle, blue shirt) — so every part of the silhouette is visible.
"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC = os.path.abspath(argv[0])
OUT = os.path.abspath(argv[1])
BODY = "--body" in argv
# --clay strips the texture and renders a lit grey surface. The paint is what hides a dent: a
# brown patch painted over a crater looks like a brown patch. Judge SHAPE on clay, never on paint.
CLAY = "--clay" in argv
angles = [int(a) for a in argv[2:] if a.lstrip("-").isdigit()] or [0, 45, 90, 135, 180]
os.makedirs(OUT, exist_ok=True)
TAG = os.path.splitext(os.path.basename(SRC))[0]

ext = os.path.splitext(SRC)[1].lower()
if ext == ".blend":
    bpy.ops.wm.open_mainfile(filepath=SRC)
elif ext == ".fbx":
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=SRC)
else:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=SRC)

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
assert meshes, "no mesh"
co = np.array([(o.matrix_world @ v.co)[:] for o in meshes for v in o.data.vertices])
mn, mx = co.min(axis=0), co.max(axis=0)
z = co[:, 2]
zlo, zhi = float(z.min()), float(z.max())

if BODY:
    ctr = Vector(((mn + mx) / 2).tolist())
    scale = float((mx - mn).max()) * 1.15
else:
    head = co[z > zlo + 0.70 * (zhi - zlo)]
    hc = head.mean(axis=0)
    ctr = Vector((float(hc[0]), float(hc[1]), float(hc[2])))
    scale = float(np.abs(head - hc).max()) * 2.5

sc = bpy.context.scene
if CLAY:
    # Workbench, not EEVEE: it has the CAVITY screen-space term, which darkens concavities and is
    # the single most direct way to see a crater. The earlier clay pass used EEVEE diffuse under a
    # uniform world with no lamps, which renders perfectly flat — a dent and a dome look identical
    # in it. That render could not have shown the defect it was asked about.
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "SINGLE"
    sh.single_color = (0.62, 0.62, 0.63)
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.cavity_ridge_factor = 1.0
    sh.cavity_valley_factor = 1.6
    sh.curvature_ridge_factor = 1.0
    sh.curvature_valley_factor = 1.6
    sh.show_shadows = True
else:
    sc.render.engine = "BLENDER_EEVEE"
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = 760
sc.render.resolution_y = 760 if not BODY else 980
# World colour x strength IS the background pixel. The first attempt used 0.42 grey at strength
# 2.6, which clips to 1.0 — a white background again, the exact bug this tool exists to avoid.
# Strength stays at 1.0 so the field renders as the colour asked for, and the model is lit by
# lamps instead of by the world.
w = bpy.data.worlds.new("W"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.40, 0.44, 0.41, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
sc.world = w

# Even, shadowless-looking fill from six directions: relief in these sheets must come from the
# geometry, never from a key light (the lesson recorded in glb_views.py).
for d in ((0, -1, 0), (0, 1, 0), (-1, 0, 0), (1, 0, 0), (0, 0, 1), (0, 0, -1)):
    ld = bpy.data.lights.new(f"L{d}", type="SUN")
    ld.energy = 1.6
    lo = bpy.data.objects.new(f"L{d}", ld)
    sc.collection.objects.link(lo)
    lo.rotation_euler = Vector(d).to_track_quat("-Z", "Y").to_euler()

if CLAY:
    for o in meshes:
        o.data.materials.clear()

cd = bpy.data.cameras.new("C"); cam = bpy.data.objects.new("C", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"; cd.ortho_scale = scale
R = float(zhi - zlo) * 3

for deg in angles:
    a = math.radians(deg)
    cam.location = (ctr.x + math.sin(a) * R, ctr.y - math.cos(a) * R, ctr.z)
    cam.rotation_euler = (math.radians(90), 0, a)
    sc.render.filepath = os.path.join(OUT, f"{TAG}_{'clay' if CLAY else 'paint'}_{deg:03d}.png")
    bpy.ops.render.render(write_still=True)
print(f"  wrote {len(angles)} views to {OUT}")

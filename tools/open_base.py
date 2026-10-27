"""Put ONE model on the operator's screen, framed and shaded so shape is readable.

    blender -b --python tools/open_base.py -- <model> <fwd_deg> <out.blend>

`inspect_bases.py` builds a two-model comparison. This is the single-model version: the base we
are actually committing to, alone, with nothing to confuse it against.

Materials are dropped and the viewport is saved in SOLID + CAVITY, because paint hides shape —
a brown patch painted over a dent looks like a brown patch. Opens framed on the FACE, since that
is the part being kept; NUMPAD 9 flips to the back, which is the part being regenerated.
"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector, Euler

argv = sys.argv[sys.argv.index("--") + 1:]
SRC = os.path.abspath(argv[0])
FWD = float(argv[1])
OUT = os.path.abspath(argv[2])

bpy.ops.wm.read_factory_settings(use_empty=True)
ext = os.path.splitext(SRC)[1].lower()
if ext == ".fbx":
    bpy.ops.import_scene.fbx(filepath=SRC)
elif ext == ".blend":
    bpy.ops.wm.open_mainfile(filepath=SRC)
else:
    bpy.ops.import_scene.gltf(filepath=SRC)

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
ob = max(meshes, key=lambda o: len(o.data.vertices))
for extra in meshes:
    if extra is not ob:
        bpy.data.objects.remove(extra, do_unlink=True)

bpy.ops.object.select_all(action="DESELECT")
ob.select_set(True)
bpy.context.view_layer.objects.active = ob
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# face -Y, so NUMPAD 1 is the front and NUMPAD 9 from there is the back
ob.rotation_euler = (0, 0, math.radians(-FWD))
bpy.ops.object.transform_apply(rotation=True)

co = np.array([v.co[:] for v in ob.data.vertices])
s = 1.0 / float(co[:, 2].max() - co[:, 2].min())
ob.scale = (s, s, s)
bpy.ops.object.transform_apply(scale=True)

co = np.array([v.co[:] for v in ob.data.vertices])
mid = (co.min(axis=0) + co.max(axis=0)) / 2
ob.location = (-float(mid[0]), -float(mid[1]), -float(co[:, 2].min()))
bpy.ops.object.transform_apply(location=True)

ob.data.materials.clear()
ob.name = ob.data.name = "CLYFFY_BASE"

co = np.array([v.co[:] for v in ob.data.vertices])
zlo, zhi = float(co[:, 2].min()), float(co[:, 2].max())
head_z = float(co[co[:, 2] > zlo + 0.70 * (zhi - zlo)][:, 2].mean())

for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type != "VIEW_3D":
            continue
        for space in area.spaces:
            if space.type != "VIEW_3D":
                continue
            sh = space.shading
            sh.type = "SOLID"
            sh.light = "STUDIO"
            sh.color_type = "SINGLE"
            sh.single_color = (0.62, 0.62, 0.63)
            sh.show_cavity = True
            sh.cavity_type = "BOTH"
            sh.cavity_ridge_factor = 1.0
            sh.cavity_valley_factor = 1.6
            sh.curvature_ridge_factor = 1.0
            sh.curvature_valley_factor = 1.6
            sh.show_backface_culling = False
            space.overlay.show_overlays = True
            space.clip_start = 0.001
            space.clip_end = 100.0
            r3d = space.region_3d
            r3d.view_perspective = "ORTHO"
            r3d.view_rotation = Euler((math.radians(90), 0.0, 0.0), "XYZ").to_quaternion()
            r3d.view_location = Vector((0.0, 0.0, head_z))
            r3d.view_distance = 0.85

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"\n{ob.name}: {len(ob.data.vertices)} verts, {len(ob.data.polygons)} faces -> {OUT}")
print("NUMPAD 1 front · NUMPAD 9 flips to the back · NUMPAD 3 side · MMB orbits")

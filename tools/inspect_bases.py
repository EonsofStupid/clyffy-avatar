"""Build a .blend for the OPERATOR to orbit by hand — both bases, side by side, cavity shading on.

    blender -b --python tools/inspect_bases.py -- <out.blend>

Opened on the operator's screen so he can turn the models himself rather than take my word from a
render. The viewport is saved in SOLID + CAVITY shading and textures are dropped, because that is
the only shading in which the defect is visible: the crater in the back of `clyffy_v2` is a closed
surface, so it survives every hole gate, and it is painted over with a brown patch, so it hides
completely in material preview.

Both models are rotated to face the same way (-Y) and scaled to the same height so the backs can be
compared directly. Object names carry the verdict.
"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector, Euler

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = os.path.abspath(argv[0])
DEAD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mesh", "_dead")

bpy.ops.wm.read_factory_settings(use_empty=True)

# (file, forward angle in the fixed-orbit convention, name, x offset)
SPECS = [
    ("clyffy_v2.fbx",       90.0, "A__v2_APPROVED__BACK_IS_A_CRATER", -0.75),
    ("clyffy_open_v1.glb",   0.0, "B__open_v1__back_is_SOUND",         0.75),
]

for fname, fwd_deg, label, xoff in SPECS:
    src = os.path.join(DEAD, fname)
    before = set(bpy.data.objects)
    if fname.lower().endswith(".fbx"):
        bpy.ops.import_scene.fbx(filepath=src)
    else:
        bpy.ops.import_scene.gltf(filepath=src)
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    ob = max(new, key=lambda o: len(o.data.vertices))
    for extra in new:
        if extra is not ob:
            bpy.data.objects.remove(extra, do_unlink=True)

    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # face everything -Y, so "the back" is one direction for both models
    ob.rotation_euler = (0, 0, math.radians(-fwd_deg))
    bpy.ops.object.transform_apply(rotation=True)

    co = np.array([v.co[:] for v in ob.data.vertices])
    h = float(co[:, 2].max() - co[:, 2].min())
    s = 1.0 / h
    ob.scale = (s, s, s)
    bpy.ops.object.transform_apply(scale=True)

    co = np.array([v.co[:] for v in ob.data.vertices])
    mid = (co.min(axis=0) + co.max(axis=0)) / 2
    ob.location = (xoff - float(mid[0]), -float(mid[1]), -float(co[:, 2].min()))
    bpy.ops.object.transform_apply(location=True)

    ob.data.materials.clear()   # paint hides the dent — this file is for SHAPE only
    ob.name = label
    ob.data.name = label
    print(f"  {label}: {len(ob.data.vertices)} verts")

# Save the viewport in the only shading that shows the defect. Every 3D view in the file, so it
# does not matter which workspace tab he lands on.
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
            space.overlay.show_wireframes = False
            space.clip_start = 0.001
            space.clip_end = 100.0
            # Open already framed on the BACKS, which is the whole point of the file. Without this
            # it opens at the default distance with two 1-unit models as specks near the origin.
            r3d = space.region_3d
            r3d.view_perspective = "ORTHO"
            r3d.view_rotation = Euler(
                (math.radians(90), 0.0, math.radians(180)), "XYZ"
            ).to_quaternion()          # Blender's BACK view: camera at +Y looking to -Y
            r3d.view_location = Vector((0.0, 0.0, 0.62))
            r3d.view_distance = 2.4

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"\nwrote {OUT}")
print("Both face -Y. Orbit to the BACK (numpad Ctrl+1) to see the crater on A.")

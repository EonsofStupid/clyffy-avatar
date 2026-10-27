"""Build the retopo workspace: scaffold + reference sheets + an empty retopo mesh, ready to work.

    blender -b --python tools/retopo_setup.py -- <scaffold.glb> <out.blend>

Decision 2026-08-05 (operator): the base is RETOPOLOGIZED BY HAND over the generated scaffold —
the studio pipeline. The scaffold (`work/remesh/meshy.glb`: the approved character, back verified
clean on clay) supplies the SHAPE; the retopo supplies the TOPOLOGY: lip loops around an open
mouth, eye rings, teeth/tongue as separate objects, a back that is right because we made it right.

The file this builds:
  * SCAFFOLD collection — the generated mesh, normalized (fwd -Y, unit height, feet at z=0),
    smooth-shaded, non-selectable so it cannot be edited by accident.
  * REFERENCE collection — the approved sheets as image empties in the ortho views, offset behind
    the model, non-selectable.
  * RETOPO collection — `retopo_head`, an empty mesh with Mirror(X, clipped) + Shrinkwrap(scaffold)
    already stacked, so every vertex laid down lands on the scaffold's surface, mirrored live.
  * Viewport: front ortho, wireframe-on-retopo, face snapping to the scaffold enabled.
"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector, Euler

argv = sys.argv[sys.argv.index("--") + 1:]
SRC = os.path.abspath(argv[0])
OUT = os.path.abspath(argv[1])
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

bpy.ops.wm.read_factory_settings(use_empty=True)
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

# normalize: unit height, centred, feet on the floor. Facing measured at 0 deg (-Y) on this
# scaffold (work/remesh/meshy_clay_000.png is the face), so no rotation is needed.
co = np.array([v.co[:] for v in ob.data.vertices])
s = 1.0 / float(co[:, 2].max() - co[:, 2].min())
ob.scale = (s, s, s)
bpy.ops.object.transform_apply(scale=True)
co = np.array([v.co[:] for v in ob.data.vertices])
mid = (co.min(axis=0) + co.max(axis=0)) / 2
ob.location = (-float(mid[0]), -float(mid[1]), -float(co[:, 2].min()))
bpy.ops.object.transform_apply(location=True)

ob.name = ob.data.name = "SCAFFOLD"
for p in ob.data.polygons:
    p.use_smooth = True

sc = bpy.context.scene
root = sc.collection
def coll(name):
    c = bpy.data.collections.new(name)
    root.children.link(c)
    return c

c_scaf, c_ref, c_ret = coll("SCAFFOLD"), coll("REFERENCE"), coll("RETOPO")
root.objects.unlink(ob)
c_scaf.objects.link(ob)
ob.hide_select = True                     # shape truth, never edited

# reference sheets as image empties behind the model
def sheet(path, name, rot, loc, size=1.2):
    if not os.path.exists(path):
        print(f"  ! missing reference {path}")
        return
    img = bpy.data.images.load(path)
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = "IMAGE"
    e.data = img
    e.empty_display_size = size
    e.rotation_euler = rot
    e.location = loc
    e.hide_select = True
    c_ref.objects.link(e)

AP = os.path.join(ROOT, "reference", "approved")
sheet(os.path.join(AP, "modelsheet_neutral.png"), "ref_neutral",
      Euler((math.radians(90), 0, 0)), Vector((0, 0.9, 0.62)))
sheet(os.path.join(AP, "modelsheet_open.png"), "ref_open",
      Euler((math.radians(90), 0, 0)), Vector((1.6, 0.9, 0.62)))
sheet(os.path.join(AP, "detail_muzzle_profile.png"), "ref_muzzle",
      Euler((math.radians(90), 0, math.radians(90))), Vector((-1.2, 0, 0.62)))

# the retopo object: empty mesh, mirrored and shrinkwrapped
me = bpy.data.meshes.new("retopo_head")
rt = bpy.data.objects.new("retopo_head", me)
c_ret.objects.link(rt)
mir = rt.modifiers.new("Mirror", "MIRROR")
mir.use_axis = (True, False, False)
mir.use_clip = True
sw = rt.modifiers.new("Shrinkwrap", "SHRINKWRAP")
sw.target = ob
sw.wrap_method = "NEAREST_SURFACEPOINT"
sw.offset = 0.002                          # sit a hair above the scaffold so it stays visible

ts = sc.tool_settings
ts.use_snap = True
ts.snap_elements = {"FACE"}
ts.use_snap_align_rotation = False
ts.use_mesh_automerge = True

bpy.context.view_layer.objects.active = rt
rt.select_set(True)

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
            sh.single_color = (0.55, 0.55, 0.57)
            sh.show_cavity = True
            sh.cavity_type = "BOTH"
            space.overlay.show_wireframes = False
            space.clip_start = 0.001
            space.clip_end = 100.0
            r3d = space.region_3d
            r3d.view_perspective = "ORTHO"
            r3d.view_rotation = Euler((math.radians(90), 0, 0), "XYZ").to_quaternion()
            r3d.view_location = Vector((0.0, 0.0, head_z))
            r3d.view_distance = 1.1

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"\nscaffold {len(ob.data.vertices)} verts -> {OUT}")
print("SCAFFOLD + REFERENCE are select-locked. retopo_head has Mirror(X)+Shrinkwrap, face snap on.")

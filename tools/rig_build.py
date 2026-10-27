"""Build the armature and skin the model. The skeleton the whole build has been for.

    blender -b --python tools/rig_build.py -- work/RETOPO_clyffy.blend --write

Bone positions come from the measurements already taken off the scaffold, not from guesses:
  collar 0.630 · chest 0.500 · armpit/arm socket 0.410 · waist 0.300 · hip 0.200 · crotch 0.170
  arm: socket x 0.19 -> wrist x 0.247 at z 0.300, hand tapers out by z 0.250
  leg: hip -> knee (x 0.100, z 0.110) -> ankle (z 0.060) -> hoof (z 0.012)
  tail: root (y 0.17, z 0.245) sweeping out to the tuft (x 0.12, y 0.28, z 0.06)
  jaw hinge: z 0.815, y -0.020 — the v2 rig's estimate, which was measured on a real jaw and is
  the only part of that rig worth carrying over.

BEFORE SKINNING, two modifier problems have to go:
  * Mirror is APPLIED. Automatic weights are computed on base geometry, so a mirrored ear would
    hand the right ear's weights to the left one and both would follow the same bone.
  * Shrinkwrap is REMOVED from the head shell. It pins the mesh to the scaffold; left on, the rig
    would deform the mesh and the modifier would drag it straight back.
"""
import bpy, bmesh, sys, os, math
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
WRITE = "--write" in argv
bpy.ops.wm.open_mainfile(filepath=BLEND)

# ONE mesh from horn to hoof now (tools/join_head_body.py). The head and body used to be separate
# objects and the neck broke up whenever the head turned — two surfaces that must move as one have
# to BE one.
MESHES = ["clyffy_mesh", "clyffy_ear_R", "clyffy_horn_R", "clyffy_eye_R",
          "clyffy_teeth_upper", "clyffy_teeth_lower", "clyffy_tongue"]

# ---- 1. clear the modifiers that fight a rig ----------------------------------------------------
for name in MESHES:
    ob = bpy.data.objects.get(name)
    if not ob:
        continue
    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    for m in list(ob.modifiers):
        if m.type == "MIRROR":
            bpy.ops.object.modifier_apply(modifier=m.name)
            print(f"  {name}: applied Mirror -> {len(ob.data.polygons)} faces")
        elif m.type == "SHRINKWRAP":
            ob.modifiers.remove(m)
            print(f"  {name}: removed Shrinkwrap (it would undo every deformation)")

# ---- 2. the skeleton ----------------------------------------------------------------------------
# name: (head, tail, parent, connected)
B = {}


def bone(n, h, t, p=None, c=False):
    B[n] = (Vector(h), Vector(t), p, c)


bone("root",     (0, 0, 0.00),     (0, 0, 0.10))
bone("hips",     (0, 0, 0.200),    (0, 0, 0.300), "root")
bone("spine",    (0, 0, 0.300),    (0, 0, 0.430), "hips", True)
bone("chest",    (0, 0, 0.430),    (0, 0, 0.560), "spine", True)
bone("neck",     (0, 0, 0.560),    (0, -0.02, 0.680), "chest", True)
bone("head",     (0, -0.02, 0.680), (0, -0.06, 0.870), "neck", True)
# the jaw pivots at the hinge and swings forward-down to the chin
bone("jaw",      (0, -0.020, 0.815), (0, -0.240, 0.735), "head")
bone("ear.R",    (0.105, 0.010, 0.880), (0.190, 0.030, 0.900), "head")
bone("ear.L",    (-0.105, 0.010, 0.880), (-0.190, 0.030, 0.900), "head")

for s, sx in (("R", 1.0), ("L", -1.0)):
    bone(f"shoulder.{s}", (sx * 0.060, 0, 0.560), (sx * 0.170, 0, 0.520), "chest")
    bone(f"upperarm.{s}", (sx * 0.170, 0, 0.520), (sx * 0.235, 0.020, 0.410), f"shoulder.{s}", True)
    bone(f"forearm.{s}",  (sx * 0.235, 0.020, 0.410), (sx * 0.250, 0.015, 0.305),
         f"upperarm.{s}", True)
    bone(f"hand.{s}",     (sx * 0.250, 0.015, 0.305), (sx * 0.258, -0.005, 0.255),
         f"forearm.{s}", True)
    bone(f"thigh.{s}",    (sx * 0.085, 0, 0.195), (sx * 0.100, -0.010, 0.110), "hips")
    bone(f"shin.{s}",     (sx * 0.100, -0.010, 0.110), (sx * 0.102, -0.012, 0.055),
         f"thigh.{s}", True)
    bone(f"foot.{s}",     (sx * 0.102, -0.012, 0.055), (sx * 0.105, -0.070, 0.010),
         f"shin.{s}", True)

bone("tail.001", (0, 0.150, 0.250), (0.015, 0.195, 0.195), "hips")
bone("tail.002", (0.015, 0.195, 0.195), (0.045, 0.235, 0.140), "tail.001", True)
bone("tail.003", (0.045, 0.235, 0.140), (0.085, 0.265, 0.090), "tail.002", True)
bone("tail.004", (0.085, 0.265, 0.090), (0.120, 0.280, 0.058), "tail.003", True)

old = bpy.data.objects.get("clyffy_rig")
if old:
    bpy.data.objects.remove(old, do_unlink=True)
arm = bpy.data.armatures.new("clyffy_rig")
rig = bpy.data.objects.new("clyffy_rig", arm)
bpy.context.scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
eb = {}
for n, (h, t, p, c) in B.items():
    b = arm.edit_bones.new(n)
    b.head, b.tail = h, t
    eb[n] = b
for n, (h, t, p, c) in B.items():
    if p:
        eb[n].parent = eb[p]
        eb[n].use_connect = c
bpy.ops.object.mode_set(mode="OBJECT")
print(f"\narmature: {len(arm.bones)} bones")

# ---- 3. skin -------------------------------------------------------------------------------------
for o in bpy.context.selected_objects:
    o.select_set(False)
skinned = []
for name in MESHES:
    ob = bpy.data.objects.get(name)
    if ob:
        ob.select_set(True)
        skinned.append(name)
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.parent_set(type="ARMATURE_AUTO")
print(f"skinned with automatic weights: {', '.join(skinned)}")

for name in skinned:
    ob = bpy.data.objects[name]
    ngroups = len(ob.vertex_groups)
    unweighted = 0
    for v in ob.data.vertices:
        if not any(g.weight > 0.0 for g in v.groups):
            unweighted += 1
    flag = f"  !! {unweighted} verts have NO weight" if unweighted else "  all verts weighted"
    print(f"  {name:22s} {ngroups:3d} groups{flag}")

if WRITE:
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print("\nsaved")

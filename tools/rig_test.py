"""Pose the rig and render it. A skeleton that has not been posed is not a rig.

    blender -b --python tools/rig_test.py -- work/RETOPO_clyffy.blend

Weights came from Blender's automatic heat-map, which is a starting point and not an answer. The
three things most likely to be wrong are all visible in a pose and invisible at rest:

  * THE NECK JUNCTION. The head shell and the body are two separate meshes that overlap. If their
    weights disagree at all, turning the head pulls them apart and the join opens. This is the
    single biggest risk in the whole assembly and it is why the head turn is in here.
  * THE SHOULDER. Automatic weights routinely bind torso verts to the upper arm; raising the arm
    then drags a lump of chest with it.
  * THE JAW. The lip seam is still WELDED — the mouth cannot open yet, it can only stretch. This
    pose shows exactly how much, which is the measurement the seam split needs.

Read-only: poses are applied, rendered, and never saved.
"""
import bpy, sys, os, math
from mathutils import Vector, Euler

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
bpy.ops.wm.open_mainfile(filepath=BLEND)
rig = bpy.data.objects["clyffy_rig"]
scaf = bpy.data.objects["SCAFFOLD"]

POSES = {
    "rest": {},
    "action": {
        "upperarm.R": (-55, 0, -20), "upperarm.L": (-55, 0, 20),
        "forearm.R": (-30, 0, 0), "forearm.L": (-30, 0, 0),
        "head": (8, 0, 26), "neck": (4, 0, 10),
        "tail.001": (0, 0, -22), "tail.002": (0, 0, -26), "tail.003": (10, 0, -26),
        "spine": (-4, 0, 4),
    },
    "talk": {"jaw": (17, 0, 0), "head": (-4, 0, 0)},
}


def apply(pose):
    for b in rig.pose.bones:
        b.rotation_mode = "XYZ"
        b.rotation_euler = Euler((0, 0, 0))
    for name, deg in pose.items():
        pb = rig.pose.bones.get(name)
        if pb is None:
            print(f"  !! no bone '{name}'")
            continue
        pb.rotation_euler = Euler([math.radians(d) for d in deg])
    bpy.context.view_layer.update()


sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"; sh.color_type = "OBJECT"
sh.show_cavity = True; sh.cavity_type = "BOTH"
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = sc.render.resolution_y = 1000
scaf.hide_render = True
rig.hide_render = True
for o in bpy.data.objects:
    if o.name.startswith("vis_") or o.name.startswith("SCAF_") or o.type == "EMPTY":
        o.hide_render = True
w = bpy.data.worlds.new("WR2"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.38, 0.42, 0.40, 1)
sc.world = w
cd = bpy.data.cameras.new("CR2"); cam = bpy.data.objects.new("CR2", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"; cd.clip_start = 0.001; cd.clip_end = 100.0
OUT = os.path.join(os.path.dirname(BLEND), "rig_test")
os.makedirs(OUT, exist_ok=True)

VIEWS = {
    "front": (Vector((0.0, 0.0, 0.5)), 1.15, 0),
    "q34":   (Vector((0.0, 0.0, 0.5)), 1.15, 40),
    "headq": (Vector((0.0, -0.06, 0.80)), 0.42, 30),   # close on the neck join and the mouth
}

for pname, pose in POSES.items():
    apply(pose)
    for vname, (ctr, scale, deg) in VIEWS.items():
        a = math.radians(deg)
        cd.ortho_scale = scale
        cam.location = (ctr.x + math.sin(a) * 3, ctr.y - math.cos(a) * 3, ctr.z)
        cam.rotation_euler = (math.radians(90), 0, a)
        sc.render.filepath = os.path.join(OUT, f"{pname}_{vname}.png")
        bpy.ops.render.render(write_still=True)
    print(f"rendered pose '{pname}'")

# how far does the jaw actually move the chin, and does the mouth open at all?
apply(POSES["talk"])
dg = bpy.context.evaluated_depsgraph_get()
rt = bpy.data.objects["clyffy_mesh"]
ev = rt.evaluated_get(dg)
me = ev.to_mesh()
posed = [rt.matrix_world @ v.co for v in me.vertices]
ev.to_mesh_clear()
apply({})
dg = bpy.context.evaluated_depsgraph_get()
ev = rt.evaluated_get(dg)
me2 = ev.to_mesh()
restp = [rt.matrix_world @ v.co for v in me2.vertices]
ev.to_mesh_clear()
d = [(p - q).length for p, q in zip(posed, restp)]
print(f"\njaw at 17 deg: head shell moves max {max(d):.4f}, mean {sum(d) / len(d):.4f}")
print(f"  verts moving more than 0.005: {sum(1 for x in d if x > 0.005)} of {len(d)}")
print(f"renders -> {OUT}")

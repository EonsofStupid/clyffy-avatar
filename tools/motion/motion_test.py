import math, os
from mathutils import Euler
unsel(); clutter()
snap("P_pre_motion")
rig = bpy.data.objects["clyffy_rig"]
sc = bpy.context.scene
sc.frame_start, sc.frame_end = 1, 90
sc.render.fps = 30
for b in rig.pose.bones:
    b.rotation_mode = "XYZ"
    b.rotation_euler = Euler((0, 0, 0), "XYZ")
if rig.animation_data:
    rig.animation_data_clear()
rig.animation_data_create()
act = bpy.data.actions.new("clyffy_motion_test")
rig.animation_data.action = act

def key(bone, frame, rx=0.0, ry=0.0, rz=0.0):
    pb = rig.pose.bones[bone]
    pb.rotation_euler = Euler((math.radians(rx), math.radians(ry), math.radians(rz)), "XYZ")
    pb.keyframe_insert("rotation_euler", frame=frame)

# a plain readable beat: settle, look left, jaw talks, look back, ears flick
for f, rz in ((1, 0), (20, 18), (55, 18), (80, -6), (90, 0)):
    key("head", f, rx=(-4 if f in (20, 55) else 0), rz=rz)
for f, rz in ((1, 0), (20, 8), (55, 8), (80, -3), (90, 0)):
    key("neck", f, rz=rz)
# jaw: four syllables
jaw = [(1,0),(24,20),(30,4),(36,22),(42,3),(48,18),(54,2),(60,16),(66,0),(90,0)]
for f, rx in jaw:
    key("jaw", f, rx=rx)
for side, sgn in (("ear.R", 1), ("ear.L", -1)):
    for f, rx, rz in ((1,0,0),(18,-14,6*sgn),(30,6,-3*sgn),(44,-4,2*sgn),(60,0,0),(90,0,0)):
        key(side, f, rx=rx, rz=rz)
for i, b in enumerate(("tail.001","tail.002","tail.003","tail.004")):
    for f, rz in ((1,0),(30,10),(60,-10),(90,0)):
        key(b, f, rz=rz * (1 + i * 0.3))
def _fcurves(a):
    """Blender 5 moved Action.fcurves into layers/strips/channelbags."""
    try:
        return list(a.fcurves)
    except AttributeError:
        out2 = []
        for lay in a.layers:
            for st in lay.strips:
                for cb in getattr(st, "channelbags", []):
                    out2.extend(cb.fcurves)
        return out2
fcs = _fcurves(act)
for fc in fcs:
    for kp in fc.keyframe_points:
        kp.interpolation = "BEZIER"
out.append("action '%s' with %d fcurves over %d frames" % (act.name, len(fcs), sc.frame_end))

D = os.path.join(WORK, "motion"); os.makedirs(D, exist_ok=True)
for f in os.listdir(D):
    if f.endswith(".png"): os.remove(os.path.join(D, f))
look(at=(0, -0.05, 0.80), dist=0.62, yaw=18, pitch=-6)
w, a = _view3d()
a.spaces.active.region_3d.view_perspective = "PERSP"
sc.render.resolution_x = sc.render.resolution_y = 720
sc.render.image_settings.file_format = "PNG"
reg = [r for r in a.regions if r.type == "WINDOW"][0]
for fr in range(1, 91):
    sc.frame_set(fr)
    sc.render.filepath = os.path.join(D, "f%03d.png" % fr)
    with bpy.context.temp_override(window=w, area=a, region=reg):
        bpy.ops.render.opengl(write_still=True, view_context=True)
sc.frame_set(1)
result = {"frames": len([f for f in os.listdir(D) if f.endswith(".png")]), "dir": D}

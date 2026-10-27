"""Close-up of the chin from below-front, framed on the lip seam. Diagnostic only.

    blender -b --python work/face_ab/_chinshot.py -- <mesh.blend> <out.png> [--mats]

`--mats` colours faces BY MATERIAL, so a spike that is really a tooth poking through the skin is
identifiable at a glance instead of guessed at.
"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC = os.path.abspath(argv[0])
OUT = os.path.abspath(argv[1])
MATS = "--mats" in argv
def _o(n, d):
    return float(argv[argv.index(n) + 1]) if n in argv else d
ORTHO = _o("--ortho", 0.26)
DROP = _o("--drop", 0.035)
os.makedirs(os.path.dirname(OUT), exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=SRC)
ob = max([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
me = ob.data
for arm in bpy.data.objects:
    if arm.type == "ARMATURE":
        arm.data.pose_position = "REST"
for o in bpy.data.objects:
    if o.type == "MESH" and o.data.shape_keys:
        for kb in o.data.shape_keys.key_blocks:
            kb.value = 0.0

N = len(me.vertices)
co = np.empty((N, 3)); me.vertices.foreach_get("co", co.ravel())
M = np.array(ob.matrix_world)
co = co @ M[:3, :3].T + M[:3, 3]
z = co[:, 2]

gi = {g.name: g.index for g in ob.vertex_groups}
want = gi["op_lip_seam"]
idx = [v.index for v in me.vertices for g in v.groups if g.group == want and g.weight > 0.5]
lip = co[idx].mean(axis=0)
head_c = co[z > lip[2]].mean(axis=0)
d = lip[:2] - head_c[:2]
FWD = math.degrees(math.atan2(d[0] / np.hypot(*d), -d[1] / np.hypot(*d))) % 360.0
H = float(z.max() - z.min())

if MATS:
    PAL = [(0.80, 0.80, 0.82), (0.90, 0.25, 0.20), (0.15, 0.85, 0.35),
           (0.20, 0.45, 0.95), (0.95, 0.80, 0.15), (0.85, 0.25, 0.85)]
    for i, m in enumerate(me.materials):
        if m is None:
            continue
        m.use_nodes = True
        nt = m.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        emi = nt.nodes.new("ShaderNodeEmission")
        emi.inputs["Color"].default_value = (*PAL[i % len(PAL)], 1.0)
        nt.links.new(emi.outputs["Emission"], out.inputs["Surface"])
    print("  materials:", [m.name if m else None for m in me.materials])
    print("  palette  :", [tuple(round(c, 2) for c in PAL[i % len(PAL)])
                           for i in range(len(me.materials))])

sc = bpy.context.scene
sc.render.engine = "CYCLES" if MATS else "BLENDER_WORKBENCH"
if MATS:
    sc.cycles.samples = 8
    sc.cycles.use_denoising = False
else:
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "TEXTURE" if "--tex" in argv else "SINGLE"
    sh.single_color = (0.72, 0.70, 0.70)
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = 1200
sc.render.resolution_y = 900
w = bpy.data.worlds.new("W"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.06, 1)
sc.world = w

# camera: in front of the face, BELOW the lip, looking slightly up — the operator's screenshot angle
ctr = Vector((float(lip[0]), float(lip[1]), float(lip[2] - DROP * H)))
a = math.radians(FWD)
fwd = Vector((math.sin(a), -math.cos(a), 0.0))
R = 0.34 * H
cd = bpy.data.cameras.new("C"); cam = bpy.data.objects.new("C", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"; cd.ortho_scale = ORTHO * H
cam.location = ctr + fwd * R + Vector((0, 0, -0.10 * H))
look = ctr - cam.location
cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()

sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print(f"chinshot {os.path.basename(SRC)} -> {OUT}  (fwd {FWD:.1f})")

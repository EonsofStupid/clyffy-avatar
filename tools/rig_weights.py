"""Skin the model procedurally. Every weight here is computed; none are heat-solved.

    blender -b --python tools/rig_weights.py -- work/RETOPO_clyffy.blend --write

WHY NOT AUTOMATIC WEIGHTS. Blender's heat solve binds anything that is merely CLOSE, and this
character is nothing but close: short thick arms resting against a barrel torso inside a loose
shirt. Raising an arm 55 degrees dragged half the shirt with it, and the jaw claimed 2012 of 2051
head verts. Both are in the earlier `work/rig_test/` renders.

Distance to the BONE SEGMENT with a per-bone radius cannot bleed, because the radius is an explicit
statement of what that bone owns. The radii are read off the model's own measurements — upper arm
0.075 because it is ~0.075 across at z 0.41, thigh 0.095, tail 0.035.

THE HEAD IS AUTHORED ON TOP, in two zones, because a cow's head is not a column:
  * MUZZLE zone (y < -0.10): skull vs jaw, split about the operator-approved lip seam
  * NECK zone (y > -0.10): the head/neck blend
The two are BLENDED, never switched. A hard switch in a weight field is a tear, and the first
version of this ripped the cheek open along exactly the y = -0.10 line.
"""
import bpy, sys, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
WRITE = "--write" in argv
bpy.ops.wm.open_mainfile(filepath=BLEND)
rig = bpy.data.objects["clyffy_rig"]
SEAM_Z = 0.728

# Radii must OVERLAP. The first set was sized to each limb's actual thickness, which sounds right
# and is wrong: a vertex only receives weight from bones whose capsule contains it, so tightly
# sized capsules leave hard boundary rings where one region stops and the next begins — the neck
# tore along exactly such a ring, at the radius where "neck" ran out and "chest" took over. Each
# radius is now comfortably larger than the part it drives; the squared falloff keeps distant
# bones from actually taking much.
R = {
    "hips": 0.26, "spine": 0.26, "chest": 0.28, "neck": 0.20, "head": 0.26,
    "shoulder.R": 0.15, "upperarm.R": 0.105, "forearm.R": 0.090, "hand.R": 0.075,
    "shoulder.L": 0.15, "upperarm.L": 0.105, "forearm.L": 0.090, "hand.L": 0.075,
    "thigh.R": 0.130, "shin.R": 0.100, "foot.R": 0.085,
    "thigh.L": 0.130, "shin.L": 0.100, "foot.L": 0.085,
    "tail.001": 0.045, "tail.002": 0.045, "tail.003": 0.045, "tail.004": 0.050,
}
SEG = {b.name: (b.head_local.copy(), b.tail_local.copy(), R[b.name])
       for b in rig.data.bones if b.name in R}


def dist_seg(p, a, b):
    ab = b - a
    t = 0.0 if ab.length_squared < 1e-12 else max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
    return (p - (a + ab * t)).length


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def skin(ob, author_head):
    for g in list(ob.vertex_groups):
        ob.vertex_groups.remove(g)
    groups = {}
    for v in ob.data.vertices:
        p = ob.matrix_world @ v.co
        w = {}
        for name, (a, b, r) in SEG.items():
            d = dist_seg(p, a, b)
            if d < r:
                w[name] = smooth(1.0 - d / r) ** 2
        if author_head and p.z > 0.600:
            m = smooth((-0.100 - p.y) / 0.060)
            jaw_m = smooth((SEAM_Z + 0.004 - p.z) / 0.022) * smooth((p.z - 0.678) / 0.014)
            neck_m = smooth((0.690 - p.z) / 0.030) * (1.0 - jaw_m)
            head_m = max(0.0, 1.0 - jaw_m - neck_m)
            t = smooth((p.z - 0.660) / 0.120)
            hw = {"jaw": m * jaw_m,
                  "head": m * head_m + (1.0 - m) * t,
                  "neck": m * neck_m + (1.0 - m) * (1.0 - t)}
            blend = smooth((p.z - 0.600) / 0.090)
            w = {k: val * (1.0 - blend) for k, val in w.items()}
            for k, val in hw.items():
                w[k] = w.get(k, 0.0) + val * blend
        if not w:
            best = min(SEG.items(), key=lambda kv: dist_seg(p, kv[1][0], kv[1][1]))
            w = {best[0]: 1.0}
        tot = sum(w.values())
        for name, val in w.items():
            if val / tot < 0.002:
                continue
            g = groups.get(name)
            if g is None:
                g = groups[name] = ob.vertex_groups.new(name=name)
            g.add([v.index], val / tot, "REPLACE")
    return len(groups)


mesh = bpy.data.objects["clyffy_mesh"]
n = skin(mesh, author_head=True)
print(f"clyffy_mesh: {len(mesh.data.vertices)} verts skinned across {n} bones")

FIXED = {
    "clyffy_teeth_upper": "head", "clyffy_teeth_lower": "jaw", "clyffy_tongue": "jaw",
    "clyffy_eye_R": "head", "clyffy_horn_R": "head",
}
for name, bone in FIXED.items():
    ob = bpy.data.objects.get(name)
    if not ob:
        continue
    for g in list(ob.vertex_groups):
        ob.vertex_groups.remove(g)
    ob.vertex_groups.new(name=bone).add(range(len(ob.data.vertices)), 1.0, "REPLACE")
    print(f"{name}: -> {bone}")

ear = bpy.data.objects.get("clyffy_ear_R")
if ear:
    for g in list(ear.vertex_groups):
        ear.vertex_groups.remove(g)
    gr = ear.vertex_groups.new(name="ear.R")
    gl = ear.vertex_groups.new(name="ear.L")
    gr.add([v.index for v in ear.data.vertices if v.co.x >= 0], 1.0, "REPLACE")
    gl.add([v.index for v in ear.data.vertices if v.co.x < 0], 1.0, "REPLACE")
    print("clyffy_ear_R: split to ear.R / ear.L")

if WRITE:
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print("saved")

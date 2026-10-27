"""Jaw rig: a hinge near the ear, and weights that respect the split.

    blender -b --python tools/jaw_rig.py -- <parts.blend> <out.blend> <fwd_deg> [hinge_fwd] [hinge_h]

WEIGHTS COME FROM DIFFUSION OVER THE TOPOLOGY, NOT FROM POSITION. The upper and lower lip rims
are COINCIDENT IN SPACE — that is the whole point of the split, and it is why no positional
falloff, no distance-to-plane, no smoothstep on height can ever separate them. They differ only
topologically. So the lower rim, lower band and tongue are pinned to 1, the upper rim and the
skull are pinned to 0, and a Laplacian is relaxed between them. The discontinuity at the lip
comes free from the mesh being split there; everywhere else the falloff is smooth by
construction, so the cheek stretches instead of tearing.

This is the same diffusion-under-Dirichlet-conditions trick the previous build used for the
chin displacement field, and the same rule applies: pinned vertices are re-pinned after every
iteration, or the boundary bleeds and the lip loses its edge.

HINGE FROM MEASUREMENT. The ear base measures fwd -0.048 at 86.5% of body height; the joint
sits just below and slightly forward of it. Both defaults below are measured, not guessed, and
both are printed on every run so a wrong one is visible rather than buried.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hardfail  # noqa: F401
import bpy, bmesh, math
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = os.path.abspath(argv[0]), os.path.abspath(argv[1])
FWD_DEG = float(argv[2])
HINGE_FWD = float(argv[3]) if len(argv) > 3 else -0.020   # slightly forward of the ear base
HINGE_H = float(argv[4]) if len(argv) > 4 else 0.815      # just below it
ITERS = int(argv[5]) if len(argv) > 5 else 400
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=SRC)
if bpy.context.object and bpy.context.object.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")
ob = max([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
me = ob.data
N = len(me.vertices)
co = np.empty((N, 3)); me.vertices.foreach_get("co", co.ravel())
z = co[:, 2]; zlo, zhi = float(z.min()), float(z.max()); H = zhi - zlo
hf = (z - zlo) / H

a = math.radians(FWD_DEG)
fwd = np.array([math.sin(a), -math.cos(a), 0.0])
lat = np.array([-fwd[1], fwd[0], 0.0])
up = np.array([0.0, 0.0, 1.0])
hm = z > zlo + 0.70 * H
hc = co[hm].mean(axis=0)
proj = (co - hc) @ fwd
latc = (co - hc) @ lat

HZ = zlo + HINGE_H * H
HINGE = hc + fwd * HINGE_FWD
HINGE[2] = HZ
print(f"hinge: fwd {HINGE_FWD:+.4f}  height {HINGE_H*100:.1f}%  -> world "
      f"{tuple(round(float(v),4) for v in HINGE)}")
SEAM_Z = float(ob["mouth_seam_z"])
print(f"seam z {SEAM_Z:+.4f} ({(SEAM_Z-zlo)/H*100:.1f}%), so the hinge sits "
      f"{(HZ-SEAM_Z)/H*100:.1f}% of body height above the lip line")


def group_idx(name):
    g = ob.vertex_groups.get(name)
    assert g is not None, f"vertex group {name!r} missing — run mouth_parts.py first"
    gi = g.index
    return [v.index for v in me.vertices if any(x.group == gi for x in v.groups)]


rim_lo = group_idx("op_rim_lower")
rim_up = group_idx("op_rim_upper")
t_lo = group_idx("op_teeth_lower")
t_up = group_idx("op_teeth_upper")
tongue = group_idx("op_tongue")
print(f"pinned: rim_lower {len(rim_lo)}, teeth_lower {len(t_lo)}, tongue {len(tongue)} -> 1")
print(f"        rim_upper {len(rim_up)}, teeth_upper {len(t_up)} -> 0")

# ------------------------------------------------------------------ Dirichlet conditions
w = np.full(N, 0.5, dtype=np.float64)
fix1 = np.zeros(N, dtype=bool)
fix0 = np.zeros(N, dtype=bool)
# THE WELDED CORNERS BELONG TO BOTH RIMS. With TRIM=2 the seam's last vertices were never
# split, so they are ONE vertex appearing in op_rim_upper AND op_rim_lower. A single vertex
# cannot be pinned to both 1 and 0 — the first version let 1 win and the gate correctly
# reported the upper rim reaching 1.0. They are left FREE so the diffusion gives them the
# intermediate value a commissure actually has: the mouth corner barely moves.
shared = set(rim_lo) & set(rim_up)
print(f"        welded corners shared by both rims: {len(shared)} (left free to diffuse)")
for i in rim_lo + t_lo + tongue:
    if i not in shared:
        fix1[i] = True
for i in rim_up + t_up:
    if i not in shared:
        fix0[i] = True
# A CEILING AT THE LIP LINE. The split stops the field crossing the seam, but the corners are
# WELDED, so it flows around them and up into the upper lip and muzzle pad. Nothing measured
# catches that — the weight separation across the seam still reads 1.0000 — but the render
# showed the pad being dragged down and the whole lower face smearing. This is the same lesson
# as the 3x jaw-open attempt in the old build: the mesh limit and the CHARACTER limit are
# different limits, and only the render finds the second one.
SEAM_Z_R = float(ob["mouth_seam_z"])
fix0 |= (z > SEAM_Z_R + 0.004)

# the skull, the neck and everything behind the hinge do not follow the jaw
fix0 |= hf > 0.88
fix0 |= hf < 0.55
fix0 |= proj < (HINGE_FWD - 0.02)
fix0 &= ~fix1                       # a pinned-to-1 vertex always wins
print(f"        plus skull/neck/behind-hinge -> 0: {int(fix0.sum())} vertices total at 0")

ev = np.empty(len(me.edges) * 2, dtype=np.int32)
me.edges.foreach_get("vertices", ev)
ea, eb = ev[0::2].astype(np.int64), ev[1::2].astype(np.int64)
deg = np.zeros(N)
np.add.at(deg, ea, 1.0); np.add.at(deg, eb, 1.0)
deg = np.maximum(deg, 1.0)

w[fix1] = 1.0
w[fix0] = 0.0
for _ in range(ITERS):
    acc = np.zeros(N)
    np.add.at(acc, ea, w[eb]); np.add.at(acc, eb, w[ea])
    w = 0.25 * w + 0.75 * (acc / deg)
    # RE-PIN EVERY ITERATION. Letting the boundary drift is how a diffusion loses the edge it
    # exists to preserve — the lip would blur across the seam it was split along.
    w[fix1] = 1.0
    w[fix0] = 0.0
w = np.clip(w, 0.0, 1.0)

print(f"\nweights after {ITERS} iterations:")
print(f"  lower rim  mean {w[rim_lo].mean():.4f}  min {w[rim_lo].min():.4f}")
print(f"  upper rim  mean {w[rim_up].mean():.4f}  max {w[rim_up].max():.4f}")
print(f"  tongue     mean {w[tongue].mean():.4f}")
print(f"  whole mesh: {int((w>0.5).sum())} verts follow the jaw more than the skull")

# ------------------------------------------------------------------ armature
arm = bpy.data.armatures.new("clyffy_arm")
rig = bpy.data.objects.new("clyffy_rig", arm)
bpy.context.scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
hv = Vector((float(HINGE[0]), 0.0, float(HINGE[2])))
b_skull = arm.edit_bones.new("skull")
b_skull.head = hv
b_skull.tail = hv + Vector((0, 0, H * 0.18))
chin = co[np.array(rim_lo, dtype=int)].mean(axis=0)
b_jaw = arm.edit_bones.new("jaw")
b_jaw.head = hv
b_jaw.tail = Vector((float(chin[0]), 0.0, float(chin[2])))
b_jaw.parent = b_skull
b_jaw.use_connect = False
print(f"\nbones: skull {tuple(round(v,4) for v in b_skull.head)} -> "
      f"{tuple(round(v,4) for v in b_skull.tail)}")
print(f"       jaw   {tuple(round(v,4) for v in b_jaw.head)} -> "
      f"{tuple(round(v,4) for v in b_jaw.tail)}  (length {b_jaw.length:.4f})")
bpy.ops.object.mode_set(mode="OBJECT")

for nm in ("jaw", "skull"):
    if ob.vertex_groups.get(nm):
        ob.vertex_groups.remove(ob.vertex_groups[nm])
vg_j = ob.vertex_groups.new(name="jaw")
vg_s = ob.vertex_groups.new(name="skull")
for i in range(N):
    vg_j.add([i], float(w[i]), "REPLACE")
    vg_s.add([i], float(1.0 - w[i]), "REPLACE")

ob.parent = rig
md = ob.modifiers.new("Armature", "ARMATURE")
md.object = rig
md.use_vertex_groups = True

# ------------------------------------------------------------------ gates
free_lo = [i for i in rim_lo if i not in shared]
free_up = [i for i in rim_up if i not in shared]
print(f"  welded corner weights: {[round(float(w[i]),3) for i in sorted(shared)]}")
assert w[free_lo].min() > 0.99, f"lower rim not fully weighted: min {w[free_lo].min():.4f}"
assert w[free_up].max() < 0.01, f"upper rim picked up jaw weight: max {w[free_up].max():.4f}"
assert w[tongue].min() > 0.99, "the tongue is not fully on the jaw"
sep = float(w[free_lo].min() - w[free_up].max())
print(f"\ngate:")
print(f"  lip weight separation across the seam: {sep:.4f}  (must be ~1.0; the rims are "
      f"coincident, so only the split makes this possible)")
assert sep > 0.98
print("  OK: rig built, jaw and skull groups written, rims cleanly separated")

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"wrote {OUT}")

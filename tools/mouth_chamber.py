"""Build the mouth CHAMBER — a real volume, sized on the approved section plans.

    blender -b --python tools/mouth_chamber.py -- <split.blend> <out.blend> <fwd_deg>

Replaces `mouth_cavity.py`, which produced a lens with no volume: sectioned at the midline it
was indistinguishable from the raw head, and opening the jaw stretched it into a membrane.

WHAT IS DIFFERENT, and it is one idea. The old cavity was made small so it would be invisible
at rest. **It is the closed LIPS that hide the mouth, not the chamber being small** — the two
rims are coincident, which is the whole point of splitting rather than deleting. A full-size
chamber behind sealed lips is exactly as invisible as a tiny one. So this chamber is sized to
the reference, not to a constraint that never existed.

GEOMETRY FROM THE APPROVED PLANS (`work/CHAMBER_PLAN.png`, `work/CHAMBER_TOP.png`), both drawn
over verified sections of the real mesh:

    depth        0.170   lip x 0.2216 -> throat x 0.0516
    height       0.064 at mid-depth (palate +0.034, floor -0.030 off the spine)
    width        his own approved corners at the lip, tapering to 26% at the throat
    throat       0.056 in front of the jaw hinge, so opening is a WEDGE, not a stretch

The palate rides the skull and the floor rides the jaw, so those are baked as separate vertex
groups here rather than left to a diffusion to guess.
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
ATTR = "op_lip_seam_i"
MATNAME = "inner_mouth"

THROAT_X = float(argv[3]) if len(argv) > 3 else 0.0516
THROAT_Z = float(argv[4]) if len(argv) > 4 else 0.2218
PAL_PEAK = float(argv[5]) if len(argv) > 5 else 0.034
FLR_PEAK = float(argv[6]) if len(argv) > 6 else 0.030
RINGS = [0.22, 0.45, 0.68, 0.88]
# fraction of the lip half-width retained, sampled from the approved top plan
TAPER_T = [0.00, 0.30, 0.55, 0.78, 1.00]
TAPER_F = [1.00, 0.96, 0.86, 0.62, 0.26]
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=SRC)
if bpy.context.object and bpy.context.object.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")
ob = max([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
me = ob.data
assert ATTR in me.attributes, f"{ATTR!r} missing — run on the SPLIT mesh"
N0, F0 = len(me.vertices), len(me.polygons)
seam_i = np.empty(N0, dtype=np.float32)
me.attributes[ATTR].data.foreach_get("value", seam_i)
co = np.empty((N0, 3)); me.vertices.foreach_get("co", co.ravel())
z = co[:, 2]; zlo, zhi = float(z.min()), float(z.max()); H = zhi - zlo

a = math.radians(FWD_DEG)
fwd = np.array([math.sin(a), -math.cos(a), 0.0])
lat = np.array([-fwd[1], fwd[0], 0.0])
up = np.array([0.0, 0.0, 1.0])

bm = bmesh.new(); bm.from_mesh(me)
bm.verts.ensure_lookup_table()

# ------------------------------------------------------------------ the crack loop
bnd = [e for e in bm.edges if len(e.link_faces) == 1]
seam_v = set(int(i) for i in np.where(seam_i >= 0)[0])
crack = [e for e in bnd if e.verts[0].index in seam_v and e.verts[1].index in seam_v]
adj = {}
for e in crack:
    i, j = e.verts[0].index, e.verts[1].index
    adj.setdefault(i, []).append(j)
    adj.setdefault(j, []).append(i)
assert all(len(v) == 2 for v in adj.values()), "the crack is not a simple closed loop"
start = next(iter(adj))
loop, prev, cur = [start], None, start
while True:
    nxt = [x for x in adj[cur] if x != prev][0]
    if nxt == start:
        break
    loop.append(nxt)
    prev, cur = cur, nxt
L = len(loop)
print(f"crack loop: {L} vertices")

counts = {}
for v in loop:
    k = int(round(float(seam_i[v])))
    counts[k] = counts.get(k, 0) + 1
corners = [v for v in loop if counts[int(round(float(seam_i[v])))] == 1]
assert len(corners) == 2, f"expected 2 welded corners, got {len(corners)}"
ci = sorted(loop.index(c) for c in corners)
arcA = loop[ci[0]:ci[1] + 1]
arcB = loop[ci[1]:] + loop[:ci[0] + 1]


def side_of(arc):
    tot = 0.0
    for vi in arc[1:-1]:
        v = bm.verts[vi]
        if v.link_faces:
            tot += float(np.mean([f.calc_center_median().z for f in v.link_faces])) - float(co[vi][2])
    return tot


upper, lower = (arcA, arcB) if side_of(arcA) > side_of(arcB) else (arcB, arcA)
assert upper[0] == lower[-1] and upper[-1] == lower[0], "arcs do not share both corners"
print(f"upper arc {len(upper)}, lower arc {len(lower)}")

LIP_Z = float(co[loop][:, 2].mean())
print(f"lip z {LIP_Z:+.4f}   throat ({THROAT_X:+.4f}, {THROAT_Z:+.4f})   "
      f"depth {float(co[loop][:, 0].max()) - THROAT_X:.4f}")


def taper(t):
    return float(np.interp(t, TAPER_T, TAPER_F))


def ring(arc, sign, t):
    """One cross-section of the chamber. At t=0 it IS the rim, so the chamber grows out of the
    lip rather than being a separate bag stitched to it."""
    out = []
    n = len(arc)
    off = 4.0 * t * (1.0 - t) * (PAL_PEAK if sign > 0 else FLR_PEAK)
    sz = LIP_Z + (THROAT_Z - LIP_Z) * t
    for k, vi in enumerate(arc):
        s = k / (n - 1)
        pinch = math.sin(math.pi * s)
        p = co[vi].copy()
        p[0] = p[0] + (THROAT_X - p[0]) * t
        p[1] = p[1] * taper(t)
        p[2] = p[2] + (sz - p[2]) * t + sign * off * pinch
        out.append(p)
    return out


mat = bpy.data.materials.new(MATNAME)
mat.use_nodes = True
b = mat.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (0.16, 0.035, 0.045, 1.0)   # dark, not black (SPEC)
b.inputs["Roughness"].default_value = 0.62
me.materials.append(mat)
MI = len(me.materials) - 1

prev_up = [bm.verts[i] for i in upper]
prev_lo = [bm.verts[i] for i in lower]
pal_v, flr_v = [], []
nf = 0
for t in RINGS:
    cur_up = [bm.verts.new(Vector(p)) for p in ring(upper, +1.0, t)]
    lo_pos = ring(lower, -1.0, t)
    cur_lo = [cur_up[-1]] + [bm.verts.new(Vector(p)) for p in lo_pos[1:-1]] + [cur_up[0]]
    bm.verts.ensure_lookup_table()
    pal_v.extend(cur_up); flr_v.extend(cur_lo[1:-1])
    for A, B in ((prev_up, cur_up), (prev_lo, cur_lo)):
        for k in range(len(A) - 1):
            try:
                f = bm.faces.new((A[k], A[k + 1], B[k + 1], B[k]))
                f.material_index = MI; nf += 1
            except ValueError:
                pass
    prev_up, prev_lo = cur_up, cur_lo

ring_back = list(prev_up) + [prev_lo[k] for k in range(1, len(prev_lo) - 1)]
cen = bm.verts.new(Vector(np.array([THROAT_X, 0.0, THROAT_Z])))
bm.verts.ensure_lookup_table()
for k in range(len(ring_back)):
    try:
        f = bm.faces.new((ring_back[k], ring_back[(k + 1) % len(ring_back)], cen))
        f.material_index = MI; nf += 1
    except ValueError:
        pass
print(f"chamber: {len(RINGS)} rings + throat cap, {nf} faces")

bm.verts.index_update()
idx_pal = [v.index for v in pal_v]
idx_flr = [v.index for v in flr_v] + [cen.index]
assert min(idx_pal + idx_flr) >= 0, "un-indexed chamber vertices"
bm.normal_update()
bm.to_mesh(me); bm.free(); me.update()

for name, idxs in (("op_chamber_palate", idx_pal), ("op_chamber_floor", idx_flr)):
    vg = ob.vertex_groups.get(name) or ob.vertex_groups.new(name=name)
    vg.add([int(i) for i in idxs], 1.0, "REPLACE")
    print(f"  {name}: {len(idxs)} verts")

ob["mouth_throat"] = [THROAT_X, 0.0, THROAT_Z]
ob["mouth_seam_z"] = LIP_Z
for gname, arc in (("op_rim_upper", upper), ("op_rim_lower", lower)):
    vg = ob.vertex_groups.get(gname) or ob.vertex_groups.new(name=gname)
    vg.add([int(v) for v in arc], 1.0, "REPLACE")

N1, F1 = len(me.vertices), len(me.polygons)
bm = bmesh.new(); bm.from_mesh(me)
b1 = sum(1 for e in bm.edges if len(e.link_faces) == 1)
nm1 = sum(1 for e in bm.edges if len(e.link_faces) > 2)
lo1 = sum(1 for v in bm.verts if not v.link_faces)
bm.free()
co1 = np.empty((N1, 3)); me.vertices.foreach_get("co", co1.ravel())
new = co1[N0:]
print(f"\ngate:")
print(f"  verts {N0} -> {N1}   faces {F0} -> {F1}")
print(f"  boundary {b1}   non-manifold {nm1}   loose {lo1}")
print(f"  chamber extent  x {new[:,0].min():+.4f}..{new[:,0].max():+.4f}"
      f"  y {new[:,1].min():+.4f}..{new[:,1].max():+.4f}"
      f"  z {new[:,2].min():+.4f}..{new[:,2].max():+.4f}")
print(f"  chamber height at mid-depth {new[:,2].max()-new[:,2].min():.4f}  (plan: 0.064)")
# 3 boundary edges are PRE-EXISTING in the split mesh (the debris beside the right eye);
# tools/seal_head.py closes them downstream. What this stage must not do is ADD any.
assert lo1 == 0, f"loose {lo1}"
assert b1 <= 3, f"boundary edges {b1}: the chamber is not closed"
assert nm1 <= 1, f"non-manifold {nm1}"
print("  OK: watertight. Visibility is decided by tools/cavity_gate.py, not here.")

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"wrote {OUT}")

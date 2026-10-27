"""Find the jaw hinge by MEASURING it, and grow the jaw weights along the mesh.

    blender -b --python tools/jaw_fit.py -- work/RETOPO_clyffy.blend --write

Two guesses at the muzzle deformation have now failed — a z-banded jaw region, then a blended
two-zone version — and both tore the muzzle. Per the rule the horn taught: stop guessing, instrument.

WHAT WAS WRONG WITH THE REGION. A z-plane cannot describe a mandible. The lower jaw is not "the
bottom of the head", it is the part of the surface CONNECTED TO THE LOWER LIP, and on a muzzle that
region wraps forward and up in a shape no height threshold matches. So the region is grown
GEODESICALLY from the split lower lip outward across the mesh. It cannot leak to the upper lip
because `mouth_split.py` already separated those vertices — the mouth is a real gap in the surface
now, and a flood fill simply cannot cross it.

WHAT WAS WRONG WITH THE HINGE. It was carried over from the v2 rig (z 0.815, y -0.020) and never
checked against this head. A hinge in the wrong place forces the jaw to swing THROUGH the cheek
instead of along it, and the surface stretches to keep up. So: sweep candidate hinges, rotate the
jaw region about each, and measure the worst edge STRETCH RATIO in the mesh. The best hinge is the
one that distorts the surface least — which is a number, not an opinion.
"""
import bpy, bmesh, sys, os, math
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
WRITE = "--write" in argv
SEAM_Z = 0.728
GEO_MAX = float(argv[1]) if len(argv) > 1 and not argv[1].startswith("--") else 0.115
TEST_ANGLE = math.radians(20)

bpy.ops.wm.open_mainfile(filepath=BLEND)
mesh = bpy.data.objects["clyffy_mesh"]
rig = bpy.data.objects["clyffy_rig"]

bm = bmesh.new()
bm.from_mesh(mesh.data)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()

# ---- 1. the lower lip: aperture boundary verts sitting below the seam ---------------------------
seed = [v for v in bm.verts
        if any(len(e.link_faces) == 1 for e in v.link_edges)
        and v.co.z < SEAM_Z and v.co.y < -0.12 and v.co.z > 0.690]
print(f"lower-lip seed verts: {len(seed)}")
if not seed:
    print("!! no lower lip found — has tools/mouth_split.py been run?")
    sys.exit(1)

# ---- 2. geodesic growth over the surface --------------------------------------------------------
import heapq
dist = {v: 0.0 for v in seed}
pq = [(0.0, v.index, v) for v in seed]
heapq.heapify(pq)
while pq:
    d, _, v = heapq.heappop(pq)
    if d > dist.get(v, 1e9):
        continue
    for e in v.link_edges:
        o = e.other_vert(v)
        nd = d + e.calc_length()
        if nd < dist.get(o, 1e9) and nd <= GEO_MAX:
            dist[o] = nd
            heapq.heappush(pq, (nd, o.index, o))
print(f"jaw region: {len(dist)} verts within {GEO_MAX} of the lower lip, along the surface")


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


W = {v.index: smooth(1.0 - d / GEO_MAX) for v, d in dist.items()}

# ---- 3. sweep the hinge, measure the distortion --------------------------------------------------
co = {v.index: v.co.copy() for v in bm.verts}
edges = [(e.verts[0].index, e.verts[1].index, e.calc_length())
         for e in bm.edges if (e.verts[0].index in W or e.verts[1].index in W)
         and e.calc_length() > 1e-6]
print(f"measuring stretch on {len(edges)} edges touching the jaw region")


def stretch_for(hinge):
    R = Matrix.Rotation(TEST_ANGLE, 4, "X")
    new = {}
    for i, w in W.items():
        p = co[i]
        rp = hinge + (R @ (p - hinge))
        new[i] = p.lerp(rp, w)
    worst = 1.0
    tot = 0.0
    for a, b, L in edges:
        pa = new.get(a, co[a])
        pb = new.get(b, co[b])
        r = (pa - pb).length / L
        worst = max(worst, r)
        tot += r
    return worst, tot / len(edges)


# The hinge is CONSTRAINED to be behind the mouth corner (y -0.203). Without that the sweep
# happily walks the hinge forward into the middle of the muzzle, because stretch is trivially
# minimised by putting the pivot inside the region that moves — the mouth would then open like a
# hinge halfway along the snout. Minimum distortion is the objective; anatomy is the constraint.
best = None
print(f"\n{'hinge y':>9} {'hinge z':>9} {'worst stretch':>14} {'mean':>8}")
for yi in range(0, 15):
    for zi in range(0, 13):
        h = Vector((0.0, -0.170 + yi * 0.012, 0.720 + zi * 0.010))
        w, m = stretch_for(h)
        if best is None or w < best[0]:
            best = (w, m, h)
for yi in range(0, 15, 4):
    for zi in range(0, 13, 4):
        h = Vector((0.0, -0.170 + yi * 0.012, 0.720 + zi * 0.010))
        w, m = stretch_for(h)
        print(f"{h.y:+9.3f} {h.z:9.3f} {w:14.3f} {m:8.3f}")
worst, mean, hinge = best
print(f"\nBEST HINGE  y {hinge.y:+.3f}  z {hinge.z:.3f}   worst stretch {worst:.3f}, mean {mean:.3f}")
old_w, old_m = stretch_for(Vector((0.0, -0.020, 0.815)))
print(f"  the v2 hinge (y -0.020, z 0.815) gives worst {old_w:.3f}, mean {old_m:.3f}"
      f"  ->  {100.0 * (old_w - worst) / old_w:.0f}% less distortion")
bm.free()

# ---- 4. write the weights and move the bone -------------------------------------------------------
gj = mesh.vertex_groups.get("jaw") or mesh.vertex_groups.new(name="jaw")
others = [g for g in mesh.vertex_groups if g.name in ("head", "neck")]
for i, w in W.items():
    gj.add([i], w, "REPLACE")
    for g in others:
        try:
            cur = next((x.weight for x in mesh.data.vertices[i].groups
                        if x.group == g.index), 0.0)
            g.add([i], cur * (1.0 - w), "REPLACE")
        except (RuntimeError, StopIteration):
            pass
print(f"\njaw weights written on {len(W)} verts, head/neck scaled back by the same amount")

bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
jb = rig.data.edit_bones["jaw"]
jb.head = hinge
jb.tail = Vector((0.0, -0.245, hinge.z - 0.080))
bpy.ops.object.mode_set(mode="OBJECT")
print(f"jaw bone moved to {tuple(round(c, 3) for c in hinge)}")

if WRITE:
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print("saved")

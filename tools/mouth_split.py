"""Split the welded lip seam so the mouth can actually open.

    blender -b --python tools/mouth_split.py -- work/RETOPO_clyffy.blend --write

Everything about the head was built around this moment. The mouth loops were laid concentric to the
seam, the teeth and tongue were built on the same 17 approved points, and the seam itself was left
WELDED — one row of vertices shared by the upper and the lower lip — because a welded seam is easy
to build on and a split one is easy to tear.

Posing the jaw against a welded seam does not open a mouth, it rips the face: the shared vertices
get pulled toward an average and the surrounding surface stretches into a gash
(`work/rig_test/talk_headq.png`, before this ran).

The seam is the operator-approved line from `tools/retopo_lips.py` — 17 points he corrected three
times by eye. Edges are selected by lying ALONG that polyline, not by a z-plane: the seam dips to
z 0.709 at x 0.043 and rises to 0.728 at the corner, so any flat cut would cross it.

After the split the head shell gains a new open boundary — the mouth aperture. That is the point.
"""
import bpy, bmesh, sys, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
WRITE = "--write" in argv
TOL = 0.010

# the operator-approved seam (tools/retopo_lips.py APPROVED_SEAM), mirrored to both sides
SEAM = [(0.0000, -0.2876, 0.7260), (0.0090, -0.2871, 0.7240), (0.0190, -0.2856, 0.7220),
        (0.0280, -0.2831, 0.7200), (0.0370, -0.2792, 0.7150), (0.0430, -0.2748, 0.7090),
        (0.0510, -0.2678, 0.7090), (0.0560, -0.2628, 0.7110), (0.0610, -0.2571, 0.7100),
        (0.0660, -0.2503, 0.7110), (0.0700, -0.2436, 0.7150), (0.0720, -0.2396, 0.7140),
        (0.0770, -0.2280, 0.7180), (0.0780, -0.2249, 0.7200), (0.0820, -0.2137, 0.7230),
        (0.0830, -0.2101, 0.7240), (0.0850, -0.2034, 0.7283)]
PTS = [Vector(p) for p in SEAM] + [Vector((-p[0], p[1], p[2])) for p in SEAM]

bpy.ops.wm.open_mainfile(filepath=BLEND)
rt = bpy.data.objects["clyffy_mesh"]


def near_seam(p):
    return min((p - q).length for q in PTS)


bm = bmesh.new()
bm.from_mesh(rt.data)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()

before_open = sum(1 for e in bm.edges if len(e.link_faces) == 1)
on = [e for e in bm.edges
      if near_seam(e.verts[0].co) < TOL and near_seam(e.verts[1].co) < TOL
      and len(e.link_faces) == 2]
print(f"seam edges found: {len(on)} (within {TOL} of the approved line, interior only)")
if not on:
    print("!! no seam edges — nothing to split")
    sys.exit(1)

xs = [v.co.x for e in on for v in e.verts]
zs = [v.co.z for e in on for v in e.verts]
print(f"  span x[{min(xs):+.4f},{max(xs):+.4f}] z[{min(zs):+.4f},{max(zs):+.4f}]")

bmesh.ops.split_edges(bm, edges=on)
after_open = sum(1 for e in bm.edges if len(e.link_faces) == 1)
print(f"open edges: {before_open} -> {after_open}  (+{after_open - before_open} = the aperture)")

bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(rt.data)
bm.free()

# re-assert the jaw weighting on the freshly split verts: below the seam follows the jaw, above it
# follows the skull, and now they are DIFFERENT vertices so the two can move apart
SEAM_Z = 0.728


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


gj = rt.vertex_groups.get("jaw") or rt.vertex_groups.new(name="jaw")
gh = rt.vertex_groups.get("head") or rt.vertex_groups.new(name="head")
nj = 0
for v in rt.data.vertices:
    p = v.co
    if p.y > -0.055 or p.z > SEAM_Z + 0.012:
        continue
    d = near_seam(p)
    # right at the seam the split is clean, so weight can go hard to one side or the other
    jaw = smooth((SEAM_Z + 0.006 - p.z) / 0.022) * smooth((-0.055 - p.y) / 0.030)
    if d < TOL:
        jaw = 1.0 if p.z < SEAM_Z - 0.001 else 0.0
    if jaw > 0.001:
        gj.add([v.index], jaw, "REPLACE")
        gh.add([v.index], max(0.0, 1.0 - jaw), "REPLACE")
        nj += 1
print(f"jaw weights re-asserted on {nj} verts around the aperture")

if WRITE:
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print("saved")

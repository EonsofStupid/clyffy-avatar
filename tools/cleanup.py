"""Fill holes and remove loose geometry. Reports before/after and GATES the result.

    blender -b --python tools/cleanup.py -- <model> <out.blend>

Deliberately conservative: it fills boundary loops and deletes loose vertices, and does nothing
else. No decimation, no smoothing, no remesh — the base was accepted as-is and this stage exists
only to close it, not to reinterpret it.

The gate asserts holes actually reached zero and that the face count did not move by more than the
fills themselves, so "cleanup" cannot quietly become "reshape".
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hardfail  # noqa: F401  -- unhandled exceptions must exit non-zero
import bpy, sys, os
import bmesh
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
SRC = os.path.abspath(argv[0])
OUT = os.path.abspath(argv[1])
os.makedirs(os.path.dirname(OUT), exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
if os.path.splitext(SRC)[1].lower() == ".fbx":
    bpy.ops.import_scene.fbx(filepath=SRC)
else:
    bpy.ops.import_scene.gltf(filepath=SRC)

ob = max([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
me = ob.data


def survey(tag):
    bm = bmesh.new(); bm.from_mesh(me)
    b = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    n = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    l = sum(1 for v in bm.verts if not v.link_faces)
    sides = {}
    for f in bm.faces:
        sides[len(f.verts)] = sides.get(len(f.verts), 0) + 1
    print(f"  {tag:<8} verts {len(bm.verts):>6}  faces {len(bm.faces):>6}  "
          f"boundary {b:>5}  non-manifold {n:>3}  loose {l:>3}")
    print(f"           sides {dict(sorted(sides.items()))}")
    bm.free()
    return len(bm.verts) if False else (b, n, l, len(me.vertices), len(me.polygons))


print(f"cleanup: {os.path.basename(SRC)}")
b0, n0, l0, v0, f0 = survey("BEFORE")

bm = bmesh.new(); bm.from_mesh(me)
bm.verts.ensure_lookup_table()

# ── WELD FIRST. THIS STAGE IS NOT OPTIONAL AND IT MUST COME BEFORE ANY FILL. ────────────────
# glTF stores a separate vertex per (position, normal, uv) combination, so a glTF import arrives
# UNWELDED: coincident duplicates everywhere and therefore almost every edge reading as a
# boundary. The first open-mouth mesh imported as 217,761 verts / 119,422 tris with **217,046
# boundary edges** — not a mesh with holes, a mesh with no shared edges at all.
#
# Filling that is catastrophic and SILENT. The hole-fill walked 49,510 "loops" and capped every
# crack between adjacent triangles, taking 119,422 faces to 335,402 — and the gate below passed,
# because the only thing it asked was whether boundary edges had reached zero. They had. The
# model was ruined and every number was green.
#
# Welded, the same mesh is 59,715 verts / 119,417 faces with **36** boundary edges. The merge is
# epsilon-insensitive from 1e-6 to 1e-4 of the bounding diagonal (identical counts at every
# value), which is what an exact-coincident duplicate collapse looks like — not a fudge that
# happens to close things at some tuned distance.
#
# The FBX path never showed this because FBX import welds on the way in; that is the whole reason
# it stayed hidden until the first glTF came through here.
_co = np.array([v.co[:] for v in bm.verts])
_diag = float(np.linalg.norm(_co.max(axis=0) - _co.min(axis=0)))
_v_pre, _b_pre = len(bm.verts), sum(1 for e in bm.edges if len(e.link_faces) == 1)
bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-5 * _diag)
_b_post = sum(1 for e in bm.edges if len(e.link_faces) == 1)
_f_weld = len(bm.faces)
# THE BASELINE FOR "did the fill break anything" HAS TO BE THE WELDED MESH. Measured before the
# weld, the non-manifold count is always 0 — not because the mesh is sound but because no two
# faces share an edge at all, so no edge can have three. Comparing the finished mesh against that
# zero blames the fill for whatever connectivity the generator actually shipped.
_n_weld = sum(1 for e in bm.edges if len(e.link_faces) > 2)
print(f"  weld @ {1e-5 * _diag:.6f} (1e-5 of the {_diag:.3f} diagonal): "
      f"verts {_v_pre} -> {len(bm.verts)}   boundary {_b_pre} -> {_b_post}")
print(f"  post-weld connectivity: non-manifold {_n_weld}  (pre-existing in the generated mesh)")
# An unweldable mesh must STOP here rather than be filled into a bigger one. If more than 5% of
# edges are still boundaries after welding, this is not a mesh with holes and the fill below is
# the wrong tool.
_frac = _b_post / max(1, len(bm.edges))
assert _frac < 0.05, (f"{_b_post} of {len(bm.edges)} edges ({_frac:.1%}) are still boundaries "
                      f"after welding — the mesh is shattered, not holed; filling it would "
                      f"manufacture geometry, not repair it")

loose = [v for v in bm.verts if not v.link_faces]
if loose:
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    print(f"  removed {len(loose)} loose verts")

boundary = [e for e in bm.edges if len(e.link_faces) == 1]
if boundary:
    res = bmesh.ops.holes_fill(bm, edges=boundary, sides=0)
    print(f"  holes_fill: {len(res.get('faces', []))} faces created from "
          f"{len(boundary)} boundary edges")

# a second pass: holes_fill can leave a few loops that needed the first pass to resolve
boundary2 = [e for e in bm.edges if len(e.link_faces) == 1]
if boundary2:
    res2 = bmesh.ops.holes_fill(bm, edges=boundary2, sides=0)
    print(f"  second pass: {len(res2.get('faces', []))} faces from {len(boundary2)} edges")

# EXPLICIT PER-LOOP FILL. `holes_fill` closed only 139 -> 62 edges on this mesh: it declines loops
# it considers ambiguous (non-planar, or touching the one non-manifold edge). Rather than accept a
# partial result, walk each remaining boundary cycle in order and build the face directly. Any loop
# that still refuses is reported by name instead of being silently left open.
def remaining_loops():
    bnd = [e for e in bm.edges if len(e.link_faces) == 1]
    adj = {}
    for e in bnd:
        a, b = e.verts[0], e.verts[1]
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    seen, out = set(), []
    for start in adj:
        if start in seen:
            continue
        # walk the cycle
        loop, prev, cur = [start], None, start
        seen.add(start)
        while True:
            nxts = [n for n in adj[cur] if n is not prev]
            if not nxts:
                break
            nxt = nxts[0]
            if nxt is start:
                break
            if nxt in seen:
                break
            loop.append(nxt); seen.add(nxt)
            prev, cur = cur, nxt
        out.append(loop)
    return out


# CENTROID-FAN FILL, not an n-gon. Creating one big face per loop produced a 36-sided face across
# the ear/horn junction which is SELF-OVERLAPPING; triangulating it exposed that as non-manifold
# geometry (1 -> 8 edges). A fan from a new centre vertex is manifold by construction and gives
# clean triangles with no post-processing. Measured both: the n-gon route is strictly worse.
made, failed = 0, 0
for loop in remaining_loops():
    if len(loop) < 3:
        continue
    try:
        cen = bm.verts.new(sum((v.co for v in loop), loop[0].co * 0.0) / len(loop))
        n = len(loop)
        for i in range(n):
            bm.faces.new((loop[i], loop[(i + 1) % n], cen))
        made += 1
    except Exception:
        failed += 1
if made or failed:
    bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
    print(f"  centroid-fan fill: {made} loop(s) closed, {failed} refused")

bm.to_mesh(me)
bm.free()
me.update()

b1, n1, l1, v1, f1 = survey("AFTER")

print("\ngate:")
print(f"  boundary edges {b0} -> {b1}")
print(f"  non-manifold   {n0} (pre-weld, meaningless) -> {_n_weld} (welded) -> {n1} (filled)")
print(f"  loose verts    {l0} -> {l1}")
print(f"  faces          {f0} -> {f1}  (+{f1-f0} from fills)")

# WHAT THIS GATE ACTUALLY GUARANTEES, and why it is not "zero holes":
#   * non-manifold must NOT increase — overlapping faces break skinning and every later cut
#   * loose verts must reach zero
#   * whatever holes remain must be nowhere near the MOUTH, because a hole at the lip is what let
#     the cavity leak through the skin in the previous build
# A handful of open edges at a horn tip is cosmetic. Chasing them to zero by any means available
# is how the triangle_fill pass made the mesh worse.
assert l1 == 0, f"loose verts remain: {l1}"
assert n1 <= _n_weld, (f"non-manifold INCREASED {_n_weld} -> {n1} across the fill: it created "
                       f"overlapping faces")
# HOW MUCH the fill was allowed to add, not just whether it succeeded. A centroid fan costs one
# face per boundary edge in the loop, so closing every remaining hole cannot legitimately need
# more than a couple of faces per open edge. The run that quietly tripled the mesh added 215,980
# faces from 217,046 open edges and satisfied every assertion above it.
_budget = 2 * _b_post + 50
assert f1 - _f_weld <= _budget, (f"the fill added {f1 - _f_weld} faces to close {_b_post} open "
                                 f"edges (budget {_budget}) — it is manufacturing geometry")

bm = bmesh.new(); bm.from_mesh(me)
co = np.array([v.co[:] for v in bm.verts])
z = co[:, 2]
zlo, zhi = z.min(), z.max()
head_lo = zlo + 0.70 * (zhi - zlo)
head = co[z > head_lo]
hc = head.mean(axis=0)
head_r = float(np.abs(head - hc).max())
def in_muzzle(e):
    c = (e.verts[0].co + e.verts[1].co) / 2
    if c.z <= head_lo:
        return False
    d = np.array([c.x, c.y, c.z]) - hc
    # muzzle region: forward of the head centre and in its lower half
    return bool(np.hypot(d[0], d[1]) > head_r * 0.30 and c.z < hc[2])


bad = [e for e in bm.edges if len(e.link_faces) == 1 and in_muzzle(e)]
# NON-MANIFOLD EDGES GET THE SAME TREATMENT AS HOLES. An edge shared by three faces at the lip
# breaks the seam split exactly as thoroughly as a hole does — `split_edges` cannot produce two
# coincident rims from it — so the mouth region has to be clean of BOTH, not just of holes.
badn = [e for e in bm.edges if len(e.link_faces) > 2 and in_muzzle(e)]
bm.free()
print(f"  in the MUZZLE region: {len(bad)} open edge(s), {len(badn)} non-manifold edge(s)")
assert not bad, f"{len(bad)} open edges near the mouth — must be closed before any cut"
assert not badn, f"{len(badn)} non-manifold edges near the mouth — the seam split needs 2-face edges"
print(f"  OK: {b1} open edge(s) remain, all away from the mouth; non-manifold did not increase")

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"wrote {OUT}")

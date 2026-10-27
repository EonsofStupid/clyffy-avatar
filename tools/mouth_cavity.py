"""Build the mouth cavity: extrude the split rim backward into the head and cap it.

    blender -b --python tools/mouth_cavity.py -- <split.blend> <out.blend> <fwd_deg> [depth]

THE RIM IS ALREADY A CLOSED LOOP. Because `mouth_split.py` split rather than deleted, the
crack boundary runs up one side of the seam and back along the other through the two welded
corners: 88 edges, 88 vertices, one closed cycle of zero area. Extruding it is therefore the
ordinary operation of pushing a loop inward — no hole to reconstruct, no rim to rebuild.

THE PROFILE EXPANDS VERTICALLY. The previous build's first cavity was 0.1846 deep, 0.1445
wide and **0.0077 TALL** — a flat tapering slot with no room for teeth (~0.009), let alone a
tongue. A real mouth bag opens out behind the lips so the pocket has volume while the lip line
stays shut at rest. Each ring here is pushed back, tapered laterally, and separated vertically.

THE CORNERS PINCH. The vertical separation is scaled by sin(pi*s) along each arc, so it is
full at the middle of the lip and zero at the corners. That is what a mouth does, and it also
means the bag meets the welded corners without a crease.

DEPTH MUST EXCEED THE WIDEST APERTURE THE JAW WILL REACH, or the jaw swings past the back wall
and you see straight through the head. Reference aperture (modelsheet_open) is roughly 0.42 of
head width against a 0.49 mouth width, so at this seam's 0.1597 width the open aperture is
about 0.137 — the default depth is set above that.

CONTAINMENT IS REPORTED HERE, AND GATED BY `cavity_gate.py`. Two geometric predicates were
tried and BOTH are ill-defined on this mesh; they are recorded so neither is retried:

  closest_point_on_mesh + sign of (p - loc).normal
      Wrong on any non-convex surface. Measured wrong here: it calls the head centroid
      OUTSIDE, because the nearest surface to that point is the inside wall of a NOSTRIL PIT
      and that normal says nothing about which side of the skin the point is on.

  ray parity (odd crossings == inside)
      Sound for a solid. THIS HEAD IS NOT SOLID — it is a hollow shell. A ray through the
      mouth height crosses FOUR surfaces: outer skin at x=+0.2204, an inner wall at +0.1474,
      then empty space, then a back wall only 0.002 thick (-0.1523 to -0.1544). Parity
      therefore reports a point in the hollow as "outside", which is true of the material and
      irrelevant to the question being asked.

The question that matters is not "is this vertex inside solid material" but "can any of it be
SEEN from outside". `cavity_gate.py` answers exactly that, was proven to fail on a leak and
pass on a buried probe before any of this was cut, and detects a protrusion of 0.02% of body
height. It is the gate. What this tool prints is a diagnostic.

The mesh also carries TWO DEBRIS SHELLS, 12 and 9 vertices, buried inside the skull near the
right eye — leftover generator junk, invisible from outside, present since the base was
accepted. Flagged, not removed: that is the operator's call.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hardfail  # noqa: F401  -- unhandled exceptions must exit non-zero
import bpy, bmesh, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = os.path.abspath(argv[0]), os.path.abspath(argv[1])
FWD_DEG = float(argv[2])
DEPTH = float(argv[3]) if len(argv) > 3 else 0.070
# PITCH: degrees to tilt the throat UP from straight-back. Measured room from the midline seam
# (tools/, scratch ray march): straight back only 0.0736 before the muzzle's own internal back
# wall, rising to 0.085 at +30 and 0.124 at +60. This head has NO deep skull behind the mouth —
# at the lip's height the muzzle is a closed mass and behind it is open air under the jaw.
PITCH = float(argv[4]) if len(argv) > 4 else 25.0
VSCALE = float(argv[5]) if len(argv) > 5 else 1.0   # multiplies the vertical half-separations
# how much of the full throat-step the CORNERS take (1.0 = as deep as the midline)
CORNER_T = float(argv[6]) if len(argv) > 6 else 0.30
# INSET: every ring is additionally pushed along the INWARD surface normal by this much.
# Pinching the corners alone made things WORSE (61 px vs 44) because it kept the corner rings
# sitting ON the skin, where they graze through exactly like the gate's 5 px tangency floor.
# Ring vertices must be unambiguously inside the surface, not merely not-outside it.
INSET = float(argv[7]) if len(argv) > 7 else 0.006
ATTR = "op_lip_seam_i"
MATNAME = "inner_mouth"
# (fraction of the way to the throat, vertical half-separation)
#
# RINGS CONVERGE ON A THROAT POINT — they are not a uniform backward push. The first version
# offset every rim vertex straight back by the same depth, which drove the CORNERS as deep as
# the midline even though they start 0.10 further back, and pushed the bag out through the
# back of the jaw (55,475 magenta px from behind) and through the cheek at the corner (4,636
# from the front). Converging on one interior point keeps the bag inside the skull and is what
# a mouth narrowing to a throat actually does.
PROFILE = [(0.25, 0.018),
           (0.50, 0.036),
           (0.72, 0.042),
           (0.88, 0.028)]
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=SRC)
if bpy.context.object and bpy.context.object.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")
ob = max([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
me = ob.data
assert ATTR in me.attributes, f"{ATTR!r} missing — this must run on the SPLIT mesh"

N0, F0 = len(me.vertices), len(me.polygons)
seam_i = np.empty(N0, dtype=np.float32)
me.attributes[ATTR].data.foreach_get("value", seam_i)
co = np.empty((N0, 3)); me.vertices.foreach_get("co", co.ravel())
z = co[:, 2]; zlo, zhi = float(z.min()), float(z.max()); H = zhi - zlo

a = math.radians(FWD_DEG)
fwd = np.array([math.sin(a), -math.cos(a), 0.0])
lat = np.array([-fwd[1], fwd[0], 0.0])
up = np.array([0.0, 0.0, 1.0])

# ------------------------------------------------------------------ containment by parity
# Built from the LARGEST SHELL of the skin as it is BEFORE the cavity is added. The two debris
# shells inside the skull are excluded here; including them would add spurious crossings.
_sb = bmesh.new(); _sb.from_mesh(me)
_sb.verts.ensure_lookup_table()
_seen, _comps = set(), []
for _v in _sb.verts:
    if _v.index in _seen:
        continue
    _st, _c = [_v], []
    _seen.add(_v.index)
    while _st:
        _cur = _st.pop(); _c.append(_cur)
        for _e in _cur.link_edges:
            _o = _e.other_vert(_cur)
            if _o.index not in _seen:
                _seen.add(_o.index); _st.append(_o)
    _comps.append(_c)
_comps.sort(key=len, reverse=True)
print(f"skin shells: {[len(c) for c in _comps]}  -> parity uses the largest only")
_keep = set(v.index for v in _comps[0])
# FromPolygons, not FromBMesh: FromBMesh does NOT take ownership of the bmesh, so freeing it
# leaves a tree that silently reports zero hits. The known-answer check below caught that —
# 0/6 rays from inside the head — and refused to let a dead instrument judge anything.
_bv = [tuple(v.co) for v in _sb.verts]
_bp = [tuple(v.index for v in f.verts) for f in _sb.faces
       if all(v.index in _keep for v in f.verts)]
_sb.free()
BVH = BVHTree.FromPolygons(_bv, _bp, all_triangles=False)
print(f"parity BVH: {len(_bv)} verts, {len(_bp)} faces")

DIRS = [Vector(d) for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0),
                            (0, -1, 0), (0, 0, 1), (0, 0, -1))]


def inside_skin(p):
    """Majority vote over six axis rays. Odd crossings along a ray means inside."""
    votes = 0
    for d in DIRS:
        origin = Vector(p)
        n = 0
        for _ in range(96):
            hit = BVH.ray_cast(origin, d)
            if hit[0] is None:
                break
            n += 1
            origin = hit[0] + d * 1e-5
        votes += (n % 2)
    return votes >= 4, votes


# The predicate is reported against known answers so its unreliability stays visible in every
# run rather than being quietly trusted. It is NOT used as a gate — see the module docstring.
_chk = [("head centroid", co[z > zlo + 0.70 * H].mean(axis=0), True),
        ("far in front of the face", co[z > zlo + 0.70 * H].mean(axis=0) + fwd * 1.0, False),
        ("far above the horns", co[z > zlo + 0.70 * H].mean(axis=0) + up * 1.0, False)]
print("parity predicate vs known answers (diagnostic only, the head is a hollow shell):")
for _nm, _p, _want in _chk:
    _got, _v = inside_skin(_p)
    print(f"  {_nm:<26} inside={_got}  ({_v}/6 rays)   truth {_want}"
          f"   {'agrees' if _got == _want else 'DISAGREES'}")

bm = bmesh.new(); bm.from_mesh(me)
bm.verts.ensure_lookup_table()

# ------------------------------------------------------------------ the crack loop
bnd = [e for e in bm.edges if len(e.link_faces) == 1]
seam_v = set(int(i) for i in np.where(seam_i >= 0)[0])
crack = [e for e in bnd if e.verts[0].index in seam_v and e.verts[1].index in seam_v]
print(f"boundary edges {len(bnd)}, of which on the seam: {len(crack)}")
assert len(crack) >= 4, "no crack found — did mouth_split.py run?"

adj = {}
for e in crack:
    i, j = e.verts[0].index, e.verts[1].index
    adj.setdefault(i, []).append(j)
    adj.setdefault(j, []).append(i)
assert all(len(v) == 2 for v in adj.values()), \
    "the crack is not a simple closed loop: " \
    f"{sorted(set(len(v) for v in adj.values()))} boundary edges per vertex"

start = next(iter(adj))
loop = [start]
prev, cur = None, start
while True:
    nxt = [x for x in adj[cur] if x != prev]
    nxt = nxt[0]
    if nxt == start:
        break
    loop.append(nxt)
    prev, cur = cur, nxt
assert len(loop) == len(adj), f"loop walk covered {len(loop)} of {len(adj)} vertices"
L = len(loop)
print(f"crack loop: {L} vertices, {len(crack)} edges (closed)")

# ------------------------------------------------------------------ corners and the two arcs
# The corners are the seam's endpoints — the two vertices that were NOT duplicated, so each
# appears once in the loop while every other seam index appears twice.
counts = {}
for v in loop:
    k = int(round(float(seam_i[v])))
    counts[k] = counts.get(k, 0) + 1
corners = [v for v in loop if counts[int(round(float(seam_i[v])))] == 1]
assert len(corners) == 2, f"expected 2 welded corners, found {len(corners)}"
ci = sorted(loop.index(c) for c in corners)
arcA = loop[ci[0]:ci[1] + 1]
arcB = loop[ci[1]:] + loop[:ci[0] + 1]
print(f"corners at loop positions {ci}; arcs of {len(arcA)} and {len(arcB)} vertices")


def side_of(arc):
    """Which side of the seam an arc's faces sit on. Both arcs occupy IDENTICAL positions, so
    geometry alone cannot tell them apart — the linked FACES can."""
    tot = 0.0
    for vi in arc[1:-1]:
        v = bm.verts[vi]
        if not v.link_faces:
            continue
        cz = np.mean([f.calc_center_median().z for f in v.link_faces])
        tot += cz - float(co[vi][2])
    return tot


sA, sB = side_of(arcA), side_of(arcB)
print(f"arc face-centroid offset: A {sA:+.5f}  B {sB:+.5f}")
assert sA * sB < 0, "both arcs sit on the same side — cannot tell upper from lower"
upper, lower = (arcA, arcB) if sA > sB else (arcB, arcA)
print(f"upper arc {len(upper)} verts, lower arc {len(lower)} verts")

# THE THROAT POINT: on the midline, directly back from the forward-most seam vertex. Every
# ring is a step from the rim toward this one interior point, so the bag converges instead of
# translating. Placed inside the skull's hollow, which a ray march measured as spanning
# x +0.1474 back to -0.1523 at the mouth height.
_mid = int(min(loop, key=lambda v: abs(float((co[v] - co[loop].mean(axis=0)) @ lat))))
_front = int(max(loop, key=lambda v: float(co[v] @ fwd)))
_pr = math.radians(PITCH)
_dir = -fwd * math.cos(_pr) + up * math.sin(_pr)
THROAT = co[_front] + _dir * DEPTH
THROAT = THROAT - lat * float(THROAT @ lat)          # pin it to the midline
print(f"throat point: fwd {float(THROAT @ fwd):+.4f}  lat {float(THROAT @ lat):+.4f}  "
      f"height {(float(THROAT[2]) - zlo) / H * 100:.1f}%   "
      f"(depth {DEPTH:.3f} at pitch {PITCH:+.0f} deg from the seam front)")


# PRE-SPLIT SMOOTH NORMAL per rim vertex. The split made the normals hard, so the upper rim
# now points up-and-out and the lower down-and-out; using those would fight the vertical
# separation instead of moving into the head. Averaging the faces of BOTH coincident copies
# reconstructs the surface normal the skin had before it was unzipped.
_bynorm = {}
for _vi in loop:
    _k = int(round(float(seam_i[_vi])))
    _bynorm.setdefault(_k, []).append(_vi)
SMOOTH_N = {}
for _k, _vs in _bynorm.items():
    _acc = Vector((0, 0, 0))
    for _vi in _vs:
        for _f in bm.verts[_vi].link_faces:
            _acc += _f.normal
    if _acc.length > 0:
        _acc.normalize()
    for _vi in _vs:
        SMOOTH_N[_vi] = np.array([_acc.x, _acc.y, _acc.z])


def ring_positions(arc, sign, t, half):
    """One ring: each rim vertex stepped a fraction t toward the throat, then separated
    vertically. The separation is pinched to zero at the corners by sin(pi*s), which is what a
    mouth does and also lets the bag meet the welded corners without a crease."""
    out = []
    n = len(arc)
    for k, vi in enumerate(arc):
        s = k / (n - 1) if n > 1 else 0.0
        pinch = math.sin(math.pi * s)
        # THE DEPTH PINCHES AT THE CORNERS TOO, not just the vertical separation. The corners
        # start ~0.10 further back than the midline, so stepping every rim vertex the same
        # fraction toward the throat drove them out through the SIDE of the muzzle — measured
        # by tracing the failing pixel back to x=+0.126 y=-0.074 z=+0.228, the left corner.
        # A mouth is deepest at the middle and shallow at the corners; so is this now.
        t_eff = t * (CORNER_T + (1.0 - CORNER_T) * pinch)
        p = co[vi] * (1.0 - t_eff) + THROAT * t_eff
        p = p - SMOOTH_N[vi] * INSET
        p = p + up * (sign * half * pinch)
        out.append(p)
    return out


# ------------------------------------------------------------------ build the bag
mat = bpy.data.materials.new(MATNAME)
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
# SPEC: "the cavity dark but not black"
bsdf.inputs["Base Color"].default_value = (0.16, 0.035, 0.045, 1.0)
bsdf.inputs["Roughness"].default_value = 0.62
me.materials.append(mat)
MAT_IDX = len(me.materials) - 1
print(f"material {MATNAME!r} in slot {MAT_IDX}")

# THE ARCS SHARE BOTH CORNERS: upper[0] == lower[-1] and upper[-1] == lower[0]. Each ring must
# therefore reuse the upper ring's end vertices for the lower ring's ends, or the bag is left
# open at the corners. The first version welded only one end and the gate caught it — boundary
# edges 14 instead of 3, and 4 loose vertices.
assert upper[0] == lower[-1] and upper[-1] == lower[0], \
    "the two arcs do not share both corners — the loop split is wrong"

prev_up = [bm.verts[i] for i in upper]
prev_lo = [bm.verts[i] for i in lower]
new_faces = []
for t_frac, half in PROFILE:
    cur_up = [bm.verts.new(Vector(p)) for p in ring_positions(upper, +1.0, t_frac, half * VSCALE)]
    lo_pos = ring_positions(lower, -1.0, t_frac, half * VSCALE)
    # ends aliased to the upper ring; the pinch makes those positions identical anyway, so this
    # welds rather than merely coinciding
    cur_lo = [cur_up[-1]] + [bm.verts.new(Vector(p)) for p in lo_pos[1:-1]] + [cur_up[0]]
    bm.verts.ensure_lookup_table()
    for chain_prev, chain_cur in ((prev_up, cur_up), (prev_lo, cur_lo)):
        for k in range(len(chain_prev) - 1):
            try:
                f = bm.faces.new((chain_prev[k], chain_prev[k + 1],
                                  chain_cur[k + 1], chain_cur[k]))
                f.material_index = MAT_IDX
                new_faces.append(f)
            except ValueError:
                pass
    prev_up, prev_lo = cur_up, cur_lo

# close the back: a centroid fan, manifold by construction (an n-gon here self-overlaps the
# same way it did on the horn junction in cleanup.py, which took non-manifold from 1 to 8)
# prev_up and prev_lo share both end vertices, so walk the upper ring forward and the lower
# ring back EXCLUDING its ends — otherwise the two corners appear twice and the fan degenerates
# FORWARD through the lower ring, not backward. The arcs are already oriented so that walking
# upper[0..n] then lower[1..n-1] traverses the loop once: upper[-1] IS lower[0] and upper[0] IS
# lower[-1]. Reversing left two consecutive pairs that are not real edges and two real edges
# with only one face — boundary edges 7 instead of 3, which is exactly how this was found.
ring = list(prev_up) + [prev_lo[k] for k in range(1, len(prev_lo) - 1)]
assert len({id(v) for v in ring}) == len(ring), "back ring has a repeated vertex"
cen = bm.verts.new(sum((v.co for v in ring), Vector((0, 0, 0))) / len(ring))
bm.verts.ensure_lookup_table()
capped = 0
for k in range(len(ring)):
    try:
        f = bm.faces.new((ring[k], ring[(k + 1) % len(ring)], cen))
        f.material_index = MAT_IDX
        new_faces.append(f)
        capped += 1
    except ValueError:
        pass
print(f"bag: {len(PROFILE)} rings, {len(new_faces)} faces ({capped} in the back cap)")

bm.normal_update()
bm.to_mesh(me)
bm.free()
me.update()

# ------------------------------------------------------------------ gates
N1, F1 = len(me.vertices), len(me.polygons)
co1 = np.empty((N1, 3)); me.vertices.foreach_get("co", co1.ravel())
print(f"\ngate:")
print(f"  verts {N0} -> {N1}  (+{N1-N0})")
print(f"  faces {F0} -> {F1}  (+{F1-F0})")

bm = bmesh.new(); bm.from_mesh(me)
b1 = sum(1 for e in bm.edges if len(e.link_faces) == 1)
nm1 = sum(1 for e in bm.edges if len(e.link_faces) > 2)
lo1 = sum(1 for v in bm.verts if not v.link_faces)
bm.free()
print(f"  boundary edges {b1}   non-manifold {nm1}   loose {lo1}")

# CONTAINMENT. Every vertex the bag added must lie inside the skin as it was before.
n_out, worst = 0, []
for vi in range(N0, N1):
    ins, votes = inside_skin(co1[vi])
    if not ins:
        n_out += 1
        if len(worst) < 8:
            p = co1[vi]
            worst.append(f"fwd {float(p @ fwd):+.4f} lat {float(p @ lat):+.4f} "
                         f"h {(float(p[2])-zlo)/H*100:.1f}% ({votes}/6 rays inside)")
print(f"  cavity vertices parity-flagged: {n_out}/{N1-N0}")
for wline in worst:
    print(f"    {wline}")

assert lo1 == 0, f"{lo1} loose vertices"
assert b1 <= 3, f"boundary edges {b1}: the bag is not watertight (3 pre-existing at a horn tip)"
# NOT asserted: parity is meaningless on a hollow shell (see docstring). cavity_gate.py is
# the gate, and it is run separately on the file this stage writes.
print(f"  (parity is a diagnostic here, not a gate — {n_out} flagged; cavity_gate.py decides)")
print("  OK: watertight, no loose geometry. VISIBILITY IS NOT DECIDED HERE —\n"
      "      run tools/cavity_gate.py on the written file, at 90 AND 270, so a leak\n"
      "      out the BACK of the head cannot hide outside the front hemisphere.")

# Bake what the next stage needs so it cannot re-derive it slightly differently — the
# recurring failure in this project has been two sides of a comparison using two definitions.
ob["mouth_throat"] = [float(v) for v in THROAT]
ob["mouth_depth"] = float(DEPTH)
ob["mouth_pitch"] = float(PITCH)
ob["mouth_seam_z"] = float(co[loop][:, 2].mean())
for _gname, _arc in (("op_rim_upper", upper), ("op_rim_lower", lower)):
    _vg = ob.vertex_groups.get(_gname) or ob.vertex_groups.new(name=_gname)
    _vg.add([int(v) for v in _arc], 1.0, "REPLACE")
print(f"baked throat {tuple(round(float(v),4) for v in THROAT)}, "
      f"rim groups op_rim_upper ({len(upper)}) / op_rim_lower ({len(lower)})")

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"wrote {OUT}")

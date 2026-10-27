"""CP2 — grow the LIP LOOPS off the operator-approved seam, as real quad geometry.

    blender -b --python tools/retopo_lips.py -- work/RETOPO_clyffy.blend

Topology: concentric loops AROUND the mouth — the standard ring layout that deforms cleanly when
the jaw drops and splits cleanly along the seam later. The seam line itself stays a single welded
line (split-don't-delete happens at rig time, per MOUTH_PLAN). Three rings at graduated offsets;
each ring runs from the midline above the seam, around the corner, back to the midline below.

The seam is read FROM THE FILE — never re-detected. Whatever line the operator approved is the
line the lips grow from. Mirror(X) completes the left half; all geometry here is x >= 0.

Faces: quad strips seam->ring1, ring1->ring2, ring2->ring3, and a corner fan where the rings
wrap around the seam's endpoint. Everything lands snapped to the scaffold surface.
"""
import bpy, bmesh, sys, os, math
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
bpy.ops.wm.open_mainfile(filepath=BLEND)
scaf = bpy.data.objects["SCAFFOLD"]
rt = bpy.data.objects["retopo_head"]
# the operator saves from Edit Mode sometimes — drop to Object Mode or to_mesh() refuses
bpy.context.view_layer.objects.active = rt
if rt.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")

def snap(p, offset=0.0025):
    ok, loc, nor, _ = scaf.closest_point_on_mesh(Vector(p))
    return (loc + nor * offset) if ok else Vector(p)

def snorm(p):
    ok, loc, nor, _ = scaf.closest_point_on_mesh(Vector(p))
    return nor if ok else Vector((0, -1, 0))

# ---- read the approved seam out of the mesh ---------------------------------------------------
bm = bmesh.new(); bm.from_mesh(rt.data); bm.verts.ensure_lookup_table()
# rerunnable: a previous lips pass leaves faces in the file. Deleting with context FACES removes
# the faces plus the verts/edges that exist only for them — the guide wires (including the seam,
# which has its own chain edges) survive untouched.
if bm.faces:
    bmesh.ops.delete(bm, geom=list(bm.faces), context="FACES")
    print(f"cleared previous pass: now {len(bm.verts)} verts, {len(bm.faces)} faces")
seen, chains = set(), []
for v in bm.verts:
    if v.index in seen:
        continue
    stack, comp = [v], []
    seen.add(v.index)
    while stack:
        k = stack.pop(); comp.append(k)
        for e in k.link_edges:
            o = e.other_vert(k)
            if o.index not in seen:
                seen.add(o.index); stack.append(o)
    chains.append(comp)
# The operator-approved seam, 2026-08-05 (his sign-off on the crease trace, corner at his 0.085).
# Used ONLY when the chain is absent from the file — the faces cleanup removes the seam wire
# because its edges become face edges. If the operator edits the seam in Blender, the edited
# chain in the file wins and this constant should be refreshed from it.
APPROVED_SEAM = [
    (0.0000, -0.2876, 0.7260), (0.0090, -0.2871, 0.7240), (0.0190, -0.2856, 0.7220),
    (0.0280, -0.2831, 0.7200), (0.0370, -0.2792, 0.7150), (0.0430, -0.2748, 0.7090),
    (0.0510, -0.2678, 0.7090), (0.0560, -0.2628, 0.7110), (0.0610, -0.2571, 0.7100),
    (0.0660, -0.2503, 0.7110), (0.0700, -0.2436, 0.7150), (0.0720, -0.2396, 0.7140),
    (0.0770, -0.2280, 0.7180), (0.0780, -0.2249, 0.7200), (0.0820, -0.2137, 0.7230),
    (0.0830, -0.2101, 0.7240), (0.0850, -0.2034, 0.7283),
]
seam_chain = None
for c in chains:
    ends = [v for v in c if len(v.link_edges) == 1]
    zs = sorted(v.co.z for v in c)
    zmed = zs[len(zs) // 2]
    if len(ends) == 2 and 0.66 < zmed < 0.78 and min(v.co.y for v in c) < -0.15 and len(c) > 5:
        if max(v.co.x for v in c) - min(v.co.x for v in c) > 0.04:
            seam_chain = c
if not seam_chain:
    vs = [bm.verts.new(snap(Vector(p))) for p in APPROVED_SEAM]
    for i in range(len(vs) - 1):
        bm.edges.new((vs[i], vs[i + 1]))
    seam_chain = vs
    print("seam rebuilt from the approved spec")
ends = [v for v in seam_chain if len(v.link_edges) == 1]
cur, prev = ends[0], None
ordered = [cur]
while True:
    nxt = None
    for e in cur.link_edges:
        o = e.other_vert(cur)
        if o is not prev and o in seam_chain:
            nxt = o; break
    if nxt is None:
        break
    ordered.append(nxt); prev, cur = cur, nxt
S = [v.co.copy() for v in ordered]
if S[0].x > S[-1].x:
    S.reverse()
print(f"seam: {len(S)} verts, corner ({S[-1].x:+.4f}, {S[-1].z:.4f})")

# ---- frames along the seam --------------------------------------------------------------------
def tangent(i):
    a = S[max(i - 1, 0)]
    b = S[min(i + 1, len(S) - 1)]
    return (b - a).normalized()

# CP2 built the inner three; CP3 extended over the pad and chin; CP4 adds the muzzle-top rows —
# upper side only, the chin needs no more. The snap carries the top rows over the nostril dips;
# the nostril rings themselves come with the eye-bridge pass.
RINGS = (0.009, 0.020, 0.034, 0.052, 0.072)
# 0.128/0.150 were tried and ROLLED BACK: past ~0.11 the seam-offset rows stop being mouth
# topology — the top edge waved over the nose and the corner columns sailed up the cheeks.
# The nose/cheek region gets its own constructed patch (nostril rings + muzzle ring + eye
# rings as anchors); do not push mouth rings further out.
RINGS_UP_EXTRA = (0.091, 0.109)
BUILD_NOSTRIL = False       # the ring insert works; re-enable inside the nose patch, not here
# Binormals SMOOTHED along the seam first: per-vertex frames wobble on a scan surface and the
# wobble scales with offset distance — the first pass sawtoothed the outer ring badly.
Bs = []
for i, p in enumerate(S):
    T = tangent(i)
    N = snorm(p)
    B = T.cross(N).normalized()
    if B.z < 0:
        B = -B
    Bs.append(B)
for _ in range(3):
    Bs = [Bs[0]] + [(Bs[i - 1] + Bs[i] + Bs[i + 1]).normalized()
                    for i in range(1, len(Bs) - 1)] + [Bs[-1]]
Bs[0] = Vector((0.0, Bs[0].y, Bs[0].z)).normalized()   # midline stays on the mirror plane

def smooth_row(row):
    """two umbrella passes along the row, then re-snap — kills residual sawtooth"""
    for _ in range(2):
        row = [row[0]] + [(row[i - 1] + row[i] + row[i + 1]) / 3
                          for i in range(1, len(row) - 1)] + [row[-1]]
    row = [snap(p) for p in row]
    row[0] = Vector((0.0, row[0].y, row[0].z))          # weld line for the mirror
    return row

# Rows CONVERGE toward the corner — held at full width to the last column, the outer rows ran
# off the muzzle side and rendered as winged flaps at both upper corners. Radial convergence is
# also simply the correct mouth topology.
def taper(i):
    t = i / (len(S) - 1)
    return 1.0 - 0.55 * t ** 3

upper, lower = {}, {}
for d in RINGS:
    upper[d] = smooth_row([snap(S[i] + Bs[i] * (d * taper(i))) for i in range(len(S))])
    lower[d] = smooth_row([snap(S[i] - Bs[i] * (d * taper(i))) for i in range(len(S))])
for d in RINGS_UP_EXTRA:
    upper[d] = smooth_row([snap(S[i] + Bs[i] * (d * taper(i))) for i in range(len(S))])

# corner cap: a small ARC around the seam endpoint, one point per ring, swung from the upper
# side through the exit direction to the lower side — a fan with real spread instead of a
# single extension point (the single-point version folded faces over each other at 040).
corner = S[-1]
Nc = snorm(corner)
Tc = tangent(len(S) - 1)
Tc = (Tc - Nc * Tc.dot(Nc)).normalized()
Bc = Bs[-1]
cap = {}
for d in RINGS:
    cap[d] = snap(corner + Tc * (d * 0.45))   # caps shrink with the converged rows

# ---- build geometry ---------------------------------------------------------------------------
seam_bm = [ordered[0]] if S[0] is ordered[0].co else None  # (ordering may have reversed)
# map seam positions back to existing bmesh verts, in S order
pos2v = {tuple(round(c, 6) for c in v.co): v for v in seam_chain}
seam_v = [pos2v[tuple(round(c, 6) for c in p)] for p in S]

def mkvert(p):
    return bm.verts.new(p)

ring_v = {}
for d in RINGS:
    ring_v[("u", d)] = [mkvert(p) for p in upper[d]]
    ring_v[("l", d)] = [mkvert(p) for p in lower[d]]
    ring_v[("c", d)] = mkvert(cap[d])
for d in RINGS_UP_EXTRA:
    ring_v[("u", d)] = [mkvert(p) for p in upper[d]]

def strip(row_a, row_b):
    for i in range(len(row_a) - 1):
        try:
            bm.faces.new((row_a[i], row_a[i + 1], row_b[i + 1], row_b[i]))
        except ValueError:
            pass                          # duplicate face guard

# seam -> ring1, both sides
strip(seam_v, ring_v[("u", RINGS[0])])
strip(ring_v[("l", RINGS[0])], seam_v)
# ring -> ring
for da, db in zip(RINGS, RINGS[1:]):
    strip(ring_v[("u", da)], ring_v[("u", db)])
    strip(ring_v[("l", db)], ring_v[("l", da)])
up_all = RINGS + RINGS_UP_EXTRA
for da, db in zip(up_all[len(RINGS) - 1:], up_all[len(RINGS):]):
    strip(ring_v[("u", da)], ring_v[("u", db)])
# corner: seam end + ring ends + caps
for k, (da, db) in enumerate(zip(RINGS, RINGS[1:])):
    bm.faces.new((ring_v[("u", da)][-1], ring_v[("c", da)],
                  ring_v[("c", db)], ring_v[("u", db)][-1]))
    bm.faces.new((ring_v[("c", da)], ring_v[("l", da)][-1],
                  ring_v[("l", db)][-1], ring_v[("c", db)]))
bm.faces.new((seam_v[-1], ring_v[("u", RINGS[0])][-1], ring_v[("c", RINGS[0])]))
bm.faces.new((seam_v[-1], ring_v[("c", RINGS[0])], ring_v[("l", RINGS[0])][-1]))

# ---- nostril: a real hole with a rim ring -----------------------------------------------------
# Find the nostril as the concavity maximum on the muzzle top, take the 2x2 block of grid quads
# over it, delete them, set an 8-ring on the nostril rim, stitch rim ring to the 8-vert boundary.
# Same structure the eye sockets get later. Right side only — Mirror makes the left.
bmsN = bmesh.new(); bmsN.from_mesh(scaf.data); bmsN.verts.ensure_lookup_table()
best_c, best_p = -1e9, None
for v in bmsN.verts:
    p = v.co
    if not (0.020 < p.x < 0.090 and 0.770 < p.z < 0.815 and p.y < -0.20):
        continue
    n = v.normal
    acc = cnt = 0.0
    for e in v.link_edges:
        u = e.other_vert(v)
        acc += n.dot((u.co - v.co).normalized()); cnt += 1
    c = acc / cnt if cnt else -1
    if c > best_c:
        best_c, best_p = c, p.copy()
bmsN.free()
print(f"nostril centre R ({best_p.x:+.4f}, {best_p.y:+.4f}, {best_p.z:.4f})  cavity {best_c:.4f}")

# the 2x2 block of faces nearest the centre, restricted to the upper-extra rows
upper_rows_v = set()
for d in RINGS_UP_EXTRA:
    upper_rows_v.update(ring_v[("u", d)])
cand_faces = [f for f in bm.faces if all(v in upper_rows_v for v in f.verts)]
cand_faces.sort(key=lambda f: (f.calc_center_median() - best_p).length)
block = cand_faces[:4]
print(f"nostril block: {len(block)} faces, centres " +
      ", ".join(f"({f.calc_center_median().x:+.3f},{f.calc_center_median().z:.3f})" for f in block))

# ordered boundary loop of the block
edge_use = {}
for f in block:
    for e in f.edges:
        edge_use[e] = edge_use.get(e, 0) + 1
bnd_edges = [e for e, n in edge_use.items() if n == 1]
adj = {}
for e in bnd_edges:
    a, b = e.verts
    adj.setdefault(a, []).append(b)
    adj.setdefault(b, []).append(a)
start = next(iter(adj))
loop = [start]
prev = None
while True:
    nxts = [v for v in adj[loop[-1]] if v is not prev]
    if not nxts or nxts[0] is start:
        break
    prev = loop[-1]
    loop.append(nxts[0])
print(f"nostril boundary: {len(loop)} verts")

if len(loop) == 8 and BUILD_NOSTRIL:
    centre = Vector((0, 0, 0))
    for v in loop:
        centre += v.co
    centre /= len(loop)
    ok, cl, cn, _ = scaf.closest_point_on_mesh(centre)
    centre = cl + cn * 0.0015
    inner = [v for f in block for v in f.verts if v not in loop]
    bmesh.ops.delete(bm, geom=block, context="FACES_ONLY")
    # the 2x2 block's centre vertex (and its cross edges) would float in the hole — remove it
    bmesh.ops.delete(bm, geom=list(set(inner)), context="VERTS")
    rim = [bm.verts.new(snap(centre + (v.co - centre) * 0.45, 0.0015)) for v in loop]
    for i in range(8):
        j = (i + 1) % 8
        bm.faces.new((loop[i], loop[j], rim[j], rim[i]))
    print("nostril ring set: 8 rim verts, 8 quads, open centre")
elif BUILD_NOSTRIL:
    print(f"!! nostril boundary irregular ({len(loop)} verts) — ring NOT set, block left intact")
else:
    print("nostril ring SKIPPED (BUILD_NOSTRIL=False) — waiting for the nose patch")

bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(rt.data)
bm.free()
nq = sum(1 for p in rt.data.polygons if len(p.vertices) == 4)
nt = sum(1 for p in rt.data.polygons if len(p.vertices) == 3)
print(f"lip grid: {len(rt.data.polygons)} faces ({nq} quads, {nt} tris at the corner fan)")
bpy.ops.wm.save_as_mainfile(filepath=BLEND)

# ---- CP2 renders ------------------------------------------------------------------------------
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"; sh.color_type = "OBJECT"
sh.show_cavity = True; sh.cavity_type = "BOTH"
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = sc.render.resolution_y = 900
scaf.color = (0.60, 0.60, 0.62, 1.0)
rt.color = (0.95, 0.35, 0.10, 1.0)
rt.show_wire = True
rt.show_all_edges = True
for o in bpy.data.objects:
    if o.name.startswith("vis_"):
        o.hide_render = True
    if o.type == "EMPTY":
        o.hide_render = True
w = bpy.data.worlds.new("W"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.40, 0.44, 0.41, 1)
sc.world = w
ctr = Vector((0.0, -0.20, 0.728))
cd = bpy.data.cameras.new("C2"); cam = bpy.data.objects.new("C2", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"; cd.ortho_scale = 0.30
cd.clip_start = 0.001; cd.clip_end = 100.0
OUT = os.path.join(os.path.dirname(BLEND), "retopo_cp2")
os.makedirs(OUT, exist_ok=True)
for deg in (0, 40, 75):
    a = math.radians(deg)
    cam.location = (ctr.x + math.sin(a) * 2, ctr.y - math.cos(a) * 2, ctr.z + 0.01)
    cam.rotation_euler = (math.radians(89), 0, a)
    sc.render.filepath = os.path.join(OUT, f"cp2_{deg:03d}.png")
    bpy.ops.render.render(write_still=True)
print(f"renders -> {OUT}")

"""CP7 — the SKULL SHELL: one advancing front off the face patch, closing on the back midline.

    blender -b --python tools/retopo_skull.py -- work/RETOPO_clyffy.blend

The front is the face patch's outer boundary (the open loop MINUS its mirror-plane run; the two
midline verts where the perimeter meets x=0 stay in as clamped end columns). Every column marches
outward along the scaffold, direction updated geodesically each row, rows smoothed.

Termination is on two REAL surfaces, not step counts:
  * the MIRROR PLANE — a column crossing x<=0 clamps to x=0 and freezes. With mirror symmetry the
    sweep converges onto the sagittal LINE, so there is no pole singularity at the back.
  * the NECK PLANE — least-squares fit through the CP1 neck ring (12 pts); a column crossing below
    it clamps onto the plane and freezes. That line is CP9's boundary.
Plus a COLLISION GUARD: a candidate landing within WELD_R of a settled vert from a non-adjacent
column welds to it, so converging fronts close the surface instead of tangling.

EAR and HORN bases are EXCLUSION ZONES (the nostril recipe at larger scale): inside them the march
does not snap — the front bridges flat over the protrusion and relaxation interpolates the skull
underneath — and those verts are excluded from the live Shrinkwrap modifier. CP8 cuts the holes
there and builds the ears/horns as separate objects (like teeth, tongue, eyeballs).

Rerunnable: new verts tagged in vertex group "cp7_skull".
"""
import bpy, bmesh, sys, os, math
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
bpy.ops.wm.open_mainfile(filepath=BLEND)
scaf = bpy.data.objects["SCAFFOLD"]
rt = bpy.data.objects["retopo_head"]
bpy.context.view_layer.objects.active = rt
if rt.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")

STEP = 0.020
MAX_ROWS = 45
WELD_R = 0.012
MIN_SP = 0.012          # columns closer than this MERGE (progressive decimation)
# 0.003 was too tight: three chin verts sit ~0.004 PAST the mirror plane (clip leakage in the
# approved mouth patch) and read as "outer", creating a second, 3-vert outer run
MIDLINE_EPS = 0.005


def snap_raw(p, offset=0.0025):
    ok, loc, nor, _ = scaf.closest_point_on_mesh(Vector(p))
    return (loc + nor * offset) if ok else Vector(p)


def snorm(p):
    ok, loc, nor, _ = scaf.closest_point_on_mesh(Vector(p))
    return nor if ok else Vector((0, 0, 1))


# ---- exclusion zones from the CP1 guides -------------------------------------------------------
def guide_pts(name):
    o = bpy.data.objects[name]
    return [o.matrix_world @ p.co.to_3d() for s in o.data.splines for p in s.points]


EXCL = []
for gname in ("vis_ear_base_R", "vis_horn_base_R"):
    pts = guide_pts(gname)
    c = sum(pts, Vector()) / len(pts)
    r = max((p - c).length for p in pts)
    EXCL.append((c, r * 1.25))
    print(f"exclusion {gname}: centre ({c.x:+.3f},{c.y:+.3f},{c.z:.3f}) r {r * 1.25:.4f}")


def in_excl(p):
    return any((Vector(p) - c).length < r for c, r in EXCL)


def snap(p, offset=0.0025):
    """snap, except inside an exclusion zone — there the marched point stands"""
    if in_excl(p):
        return Vector(p)
    s = snap_raw(p, offset)
    return Vector(p) if in_excl(s) else s


# ---- neck plane --------------------------------------------------------------------------------
npts = np.array([list(p) for p in guide_pts("vis_neck")])
nc = npts.mean(axis=0)
_, _, vh = np.linalg.svd(npts - nc)
nn = vh[2]
if nn[2] < 0:
    nn = -nn                       # plane normal points UP; below the plane is the body side
NECK_C = Vector(nc.tolist())
NECK_N = Vector(nn.tolist())
print(f"neck plane: centre ({NECK_C.x:+.3f},{NECK_C.y:+.3f},{NECK_C.z:.3f}) "
      f"normal ({NECK_N.x:+.3f},{NECK_N.y:+.3f},{NECK_N.z:+.3f})")


def below_neck(p):
    return (Vector(p) - NECK_C).dot(NECK_N) < 0


def onto_neck(p):
    p = Vector(p)
    return p - NECK_N * (p - NECK_C).dot(NECK_N)


# The ring deviates up to ~0.03 from its own best-fit plane, so the PLANE is only a runaway
# guard; the real termination is proximity to the RING ITSELF (the CP9 body boundary).
NECK_RING = guide_pts("vis_neck")


def neck_dist(p):
    """distance from p to the closed neck-ring polyline, and the closest point on it"""
    p = Vector(p)
    best, bp = 1e9, None
    for i in range(len(NECK_RING)):
        a = NECK_RING[i]
        b = NECK_RING[(i + 1) % len(NECK_RING)]
        ab = b - a
        t = 0.0 if ab.length_squared < 1e-12 else max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
        q = a + ab * t
        d = (p - q).length
        if d < best:
            best, bp = d, q
    return best, bp


# ---- rerun cleanup ------------------------------------------------------------------------------
vg = rt.vertex_groups.get("cp7_skull") or rt.vertex_groups.new(name="cp7_skull")
gi = vg.index
nosh = rt.vertex_groups.get("cp5_noshrink") or rt.vertex_groups.new(name="cp5_noshrink")
ns_i = nosh.index

bm = bmesh.new(); bm.from_mesh(rt.data)
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
dl = bm.verts.layers.deform.verify()
old = [v for v in bm.verts if gi in v[dl]]
if old:
    bmesh.ops.delete(bm, geom=old, context="VERTS")
    print(f"cleared previous CP7 pass: {len(old)} verts removed")
    bm.edges.ensure_lookup_table()

# ---- the front: the face patch's OUTER boundary -------------------------------------------------
bnd_edges = [e for e in bm.edges if e.link_faces and len(e.link_faces) == 1]
adjb = {}
for e in bnd_edges:
    a, b = e.verts
    adjb.setdefault(a, []).append(b)
    adjb.setdefault(b, []).append(a)
# the outer loop is the boundary component containing the chin (lowest z)
chin = min(adjb, key=lambda v: v.co.z)
loop_set, stack, seen = set(), [chin], {chin}
while stack:
    v = stack.pop(); loop_set.add(v)
    for o in adjb[v]:
        if o not in seen:
            seen.add(o); stack.append(o)
# order the loop by walking it
start = chin
ordered = [start]
prev = None
while True:
    nxts = [o for o in adjb[ordered[-1]] if o is not prev and o in loop_set and o not in ordered]
    if not nxts:
        break
    prev = ordered[-1]
    ordered.append(nxts[0])
print(f"outer boundary loop: {len(ordered)} verts")
# rotate so the run of non-midline (outer) verts is contiguous, then take it plus its two
# midline neighbours as the marching front
is_mid = [abs(v.co.x) < MIDLINE_EPS for v in ordered]
n = len(ordered)
# the LONGEST outer run — first-found picked a 3-vert artifact run at the chin
runs = []
for s in range(n):
    if is_mid[s] or not is_mid[(s - 1) % n]:
        continue
    run, i = [], s
    while not is_mid[i]:
        run.append(i)
        i = (i + 1) % n
    runs.append(run)
run = max(runs, key=len)
print(f"outer runs: {[len(r) for r in runs]} -> taking {len(run)}")
front = [ordered[(run[0] - 1) % n]] + [ordered[i] for i in run] + [ordered[(run[-1] + 1) % n]]
if front[0].co.z < front[-1].co.z:
    pass
else:
    front.reverse()
print(f"marching front: {len(front)} columns, "
      f"ends ({front[0].co.x:+.3f},{front[0].co.y:+.3f},{front[0].co.z:.3f}) -> "
      f"({front[-1].co.x:+.3f},{front[-1].co.y:+.3f},{front[-1].co.z:.3f})")

# ---- outward directions --------------------------------------------------------------------------
NC = len(front)
front_set = set(front)
dirs = []
for v in front:
    inner = [e.other_vert(v) for e in v.link_edges if e.other_vert(v) not in front_set]
    if inner:
        away = v.co - (sum((o.co for o in inner), Vector()) / len(inner))
    else:
        away = Vector((0, 1, 0))
    nrm = snorm(v.co)
    away = away - nrm * away.dot(nrm)
    dirs.append(away.normalized() if away.length > 1e-6 else Vector((0, 1, 0)))
for _ in range(3):
    dirs = [dirs[0]] + [(dirs[i - 1] + dirs[i] + dirs[i + 1]).normalized()
                        for i in range(1, NC - 1)] + [dirs[-1]]
MID_COLS = {0, NC - 1}
for i in MID_COLS:
    dirs[i] = Vector((0.0, dirs[i].y, dirs[i].z)).normalized()

# ---- the sweep -----------------------------------------------------------------------------------
# The face boundary is far DENSER than the march step (verts ~0.005 apart near the chin), so a
# fixed 1:1 column march tangles immediately — the first version welded 24 columns and produced
# 267 tris. Columns are therefore progressively DECIMATED: adjacent live columns closer than
# MIN_SP merge into one. That is the standard advancing-front behaviour and it lands as clean
# fan tris at the transitions instead of crossed quads.
cols = [{"idx": [i], "v": front[i], "dir": dirs[i], "frozen": False, "mid": i in MID_COLS}
        for i in range(NC)]
rows = [list(front)]
new_verts = []
settled = []            # (arc position, vert) — collision-weld targets
stats = {"mirror": 0, "neck": 0, "weld": 0, "merge": 0}
for k in range(MAX_ROWS):
    live = [c for c in cols if not c["frozen"]]
    if not live:
        break
    for c in live:
        c["p"] = snap(c["v"].co + c["dir"] * STEP)
    # smooth along the front; frozen neighbours act as fixed anchors
    for _ in range(2):
        newp = {}
        for k2, c in enumerate(cols):
            if c["frozen"]:
                continue
            acc = [c["p"]]
            for j in (k2 - 1, k2 + 1):
                if 0 <= j < len(cols):
                    acc.append(cols[j]["p"] if not cols[j]["frozen"] else cols[j]["v"].co)
            newp[k2] = sum(acc, Vector()) / len(acc)
        for k2, p in newp.items():
            cols[k2]["p"] = snap(p)
    for c in cols:
        if not c["frozen"] and c["mid"]:
            c["p"] = Vector((0.0, c["p"].y, c["p"].z))
    # decimate: merge adjacent live columns that have crowded together
    j = 0
    while j < len(cols) - 1:
        a, b = cols[j], cols[j + 1]
        if not a["frozen"] and not b["frozen"] and (a["p"] - b["p"]).length < MIN_SP:
            a["p"] = snap((a["p"] + b["p"]) / 2)
            if a["mid"] or b["mid"]:
                a["mid"] = True
                a["p"] = Vector((0.0, a["p"].y, a["p"].z))
            a["idx"] = a["idx"] + b["idx"]
            a["dir"] = (a["dir"] + b["dir"]).normalized()
            cols.pop(j + 1)
            stats["merge"] += 1
        else:
            j += 1
    # terminate / create
    for c in cols:
        if c["frozen"]:
            continue
        p = c["p"]
        s = sum(c["idx"]) / len(c["idx"])          # arc position of this column
        wtgt, wd = None, WELD_R
        for sj, sv in settled:
            if abs(sj - s) <= 3:
                continue
            d = (p - sv.co).length
            if d < wd:
                wtgt, wd = sv, d
        if wtgt is not None:
            c["v"] = wtgt
            c["frozen"] = True
            stats["weld"] += 1
            continue
        term = None
        if not c["mid"] and p.x <= 0.0:
            p = Vector((0.0, p.y, p.z)); term = "mirror"
        nd, nq = neck_dist(p)
        if nd < 0.6 * STEP or below_neck(p):
            p = nq; term = "neck"
        v = bm.verts.new(p)
        new_verts.append(v)
        settled.append((s, v))
        d = p - c["v"].co
        c["v"] = v
        if term:
            c["frozen"] = True
            stats[term] += 1
        else:
            nrm = snorm(p)
            d = d - nrm * d.dot(nrm)
            if d.length > 1e-6:
                c["dir"] = d.normalized()
    # the row, expanded back over the ORIGINAL column indices
    row = [None] * NC
    for c in cols:
        for i in c["idx"]:
            row[i] = c["v"]
    rows.append(row)
    nlive = sum(1 for c in cols if not c["frozen"])
    if k % 5 == 4 or nlive == 0:
        print(f"  row {k + 1:2d}: {len(cols)} columns, {nlive} live "
              f"(mirror {stats['mirror']}, neck {stats['neck']}, "
              f"weld {stats['weld']}, merge {stats['merge']})")
    if nlive == 0:
        break
print(f"sweep: {len(rows) - 1} rows; {len(cols)} final columns "
      f"(mirror {stats['mirror']}, neck {stats['neck']}, "
      f"weld {stats['weld']}, merge {stats['merge']})")

# ---- faces ---------------------------------------------------------------------------------------
made_q = made_t = 0
for a, b in zip(rows, rows[1:]):
    for i in range(NC - 1):
        quad = [a[i], a[i + 1], b[i + 1], b[i]]
        uniq = []
        for v in quad:
            if v not in uniq:
                uniq.append(v)
        if len(uniq) < 3:
            continue
        try:
            bm.faces.new(uniq)
            if len(uniq) == 4:
                made_q += 1
            else:
                made_t += 1
        except ValueError:
            pass
print(f"skull shell: {made_q} quads, {made_t} tris")

# ---- relax (new verts only; anchors, midline and neck line respected) -----------------------------
mid_v = {v for v in new_verts if abs(v.co.x) < 1e-6}
neck_v = {v for v in new_verts if neck_dist(v.co)[0] < 1e-6}
for _ in range(4):
    moves = {}
    for v in new_verts:
        nbrs = [e.other_vert(v) for e in v.link_edges]
        if len(nbrs) < 2:
            continue
        moves[v] = sum((o.co for o in nbrs), Vector()) / len(nbrs)
    for v, m in moves.items():
        v.co = v.co.lerp(m, 0.5)
    for v in new_verts:
        v.co = snap(v.co)
        if v in mid_v:
            v.co.x = 0.0
        if v in neck_v:
            v.co = neck_dist(v.co)[1]

for v in new_verts:
    v[dl][gi] = 1.0
    if in_excl(v.co):
        v[dl][ns_i] = 1.0       # the script owns positions inside the exclusion zones

bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(rt.data)
bm.free()
nq = sum(1 for p in rt.data.polygons if len(p.vertices) == 4)
nt = sum(1 for p in rt.data.polygons if len(p.vertices) == 3)
print(f"after CP7: {len(rt.data.polygons)} faces ({nq} quads, {nt} tris)")
bpy.ops.wm.save_as_mainfile(filepath=BLEND)

# ---- renders: the BACK is mandatory (only a lit clay render catches a malformed skull) ------------
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
    if o.name.startswith("vis_") or o.type == "EMPTY":
        o.hide_render = True
w = bpy.data.worlds.new("W7"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.40, 0.44, 0.41, 1)
sc.world = w
ctr = Vector((0.0, -0.06, 0.84))
cd = bpy.data.cameras.new("C7"); cam = bpy.data.objects.new("C7", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"; cd.ortho_scale = 0.52
cd.clip_start = 0.001; cd.clip_end = 100.0
OUT = os.path.join(os.path.dirname(BLEND), "retopo_cp7")
os.makedirs(OUT, exist_ok=True)


def orbit(tag, hide_scaffold):
    scaf.hide_render = hide_scaffold
    for deg in (0, 90, 180, 240, 270, 300):
        a = math.radians(deg)
        cam.location = (ctr.x + math.sin(a) * 2, ctr.y - math.cos(a) * 2, ctr.z + 0.01)
        cam.rotation_euler = (math.radians(89), 0, a)
        sc.render.filepath = os.path.join(OUT, f"cp7_{tag}{deg:03d}.png")
        bpy.ops.render.render(write_still=True)
    scaf.hide_render = False


orbit("", False)
orbit("solo_", True)
# top-down: horn/ear count is unambiguous only from above
cam.location = (ctr.x, ctr.y, ctr.z + 2)
cam.rotation_euler = (0, 0, 0)
sc.render.filepath = os.path.join(OUT, "cp7_top.png")
bpy.ops.render.render(write_still=True)
print(f"renders -> {OUT}")

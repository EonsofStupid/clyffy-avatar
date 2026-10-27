"""CP5 — the NOSE PATCH: a marched quad grid up the muzzle top, with real nostril rings.

    blender -b --python tools/retopo_nose.py -- work/RETOPO_clyffy.blend

Anchored 1:1 on the mouth patch's open TOP boundary row (the 0.109 ring, 13 columns,
x 0 -> ~0.077). Rows are GEODESIC-MARCHED: each column continues its own column direction
along the scaffold surface, re-snapped and row-smoothed every step. This is NOT the
seam-binormal offset parameterization — that one was tried past 0.11 and rolled back
(wavy nose edge, cheek sails); marching from the previous row keeps every step local.

The nostril is the proven 2x2-block -> 8-rim-ring insert from retopo_lips.py, cut into
the new grid where it crosses the nostril band (concavity centre ~ (0.036, -0.268, 0.784)).
Right side only; Mirror(X) makes the left.

Stops after N_ROWS bands (~z 0.84 at the midline) — the doorstep of the CP1 eye-ring
guide (z 0.834+). CP6 stitches eyes to this patch's top edge.

Rerunnable: new verts are tagged in vertex group "cp5_nose"; a rerun deletes them first.
"""
import bpy, bmesh, sys, os, math
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
bpy.ops.wm.open_mainfile(filepath=BLEND)
scaf = bpy.data.objects["SCAFFOLD"]
rt = bpy.data.objects["retopo_head"]
bpy.context.view_layer.objects.active = rt
if rt.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")

STEP = 0.016
N_ROWS = 4
# The scaffold's nostril is NOT a dip — it is a comma-shaped SLOT with a raised ridge.
# First build marched rows straight through it: points scattered onto pit-vs-ridge surfaces,
# quads twisted, ridge poking through the patch. So: inside R_EX of the nostril centre the
# march does NOT snap (rows bridge flat over the slot); the hole is then cut feature-sized
# (every face whose centre is within R_HOLE) and the rim ring wraps onto the ridge.
NOSTRIL = Vector((0.0356, -0.2677, 0.7844))
R_EX = 0.020
R_HOLE = 0.019


def snap(p, offset=0.0025):
    ok, loc, nor, _ = scaf.closest_point_on_mesh(Vector(p))
    return (loc + nor * offset) if ok else Vector(p)


def snap_ex(p, offset=0.0025):
    """snap, except inside the nostril exclusion zone — there the marched point stands"""
    s = snap(p, offset)
    if (s - NOSTRIL).length < R_EX or (Vector(p) - NOSTRIL).length < R_EX:
        return Vector(p)
    return s


def snorm(p):
    ok, loc, nor, _ = scaf.closest_point_on_mesh(Vector(p))
    return nor if ok else Vector((0, -1, 0))


# ---- rerun cleanup: drop a previous CP5 pass ---------------------------------------------------
vg = rt.vertex_groups.get("cp5_nose")
if vg is None:
    vg = rt.vertex_groups.new(name="cp5_nose")
gi = vg.index

bm = bmesh.new(); bm.from_mesh(rt.data)
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
dl = bm.verts.layers.deform.verify()
old = [v for v in bm.verts if gi in v[dl]]
if old:
    bmesh.ops.delete(bm, geom=old, context="VERTS")
    print(f"cleared previous CP5 pass: {len(old)} verts removed")

# ---- the anchor row: the mouth patch's open top edge -------------------------------------------
bm.edges.ensure_lookup_table()
bnd_v = set()
for e in bm.edges:
    if e.link_faces and len(e.link_faces) == 1:
        bnd_v.update(e.verts)
top = [v for v in bnd_v if v.co.z > 0.770 and v.co.x < 0.078 and v.co.y < -0.24]
# the mirror seam is boundary too, so BOTH midline ring-ends pass the z filter — keep only
# the top ring's midline vert (the highest), or the below-neighbor search has nowhere to go
mid = [v for v in top if v.co.x < 0.001]
mid.sort(key=lambda v: -v.co.z)
for v in mid[1:]:
    top.remove(v)
top.sort(key=lambda v: v.co.x)
print(f"anchor row: {len(top)} verts, x {top[0].co.x:+.4f} -> {top[-1].co.x:+.4f}, "
      f"z {min(v.co.z for v in top):.4f}..{max(v.co.z for v in top):.4f}")

# column direction per anchor vert: continue the existing grid's column (anchor <- ring below).
# The midline vert's below-mate is on the boundary too (mirror seam), so 'interior neighbor'
# is simply: the linked vert that is NOT in the anchor row and sits BELOW (smaller z).
dirs = []
for v in top:
    below = None
    for e in v.link_edges:
        o = e.other_vert(v)
        if o in top:
            continue
        if below is None or o.co.z < below.co.z:
            below = o
    d = (v.co - below.co).normalized()
    dirs.append(d)
# smooth the initial directions along the row — corner columns inherit taper wobble
for _ in range(2):
    dirs = [dirs[0]] + [(dirs[i - 1] + dirs[i] + dirs[i + 1]).normalized()
                        for i in range(1, len(dirs) - 1)] + [dirs[-1]]
dirs[0] = Vector((0.0, dirs[0].y, dirs[0].z)).normalized()   # midline stays on the mirror plane


def smooth_row(row):
    """two umbrella passes along the row, then re-snap; midline clamped to the mirror plane"""
    for _ in range(2):
        row = [row[0]] + [(row[i - 1] + row[i] + row[i + 1]) / 3
                          for i in range(1, len(row) - 1)] + [row[-1]]
    row = [snap_ex(p) for p in row]
    row[0] = Vector((0.0, row[0].y, row[0].z))
    return row


# ---- march the rows ----------------------------------------------------------------------------
# lateral step falloff: at full step the outer columns climb onto the rising cheek contour and
# the top edge ends in pointed sails. A nose-bridge line crests at the midline and falls toward
# the sides — outer columns advance less.
NCOL = len(top)


def step_of(i):
    t = i / (NCOL - 1)
    return STEP * (1.0 - 0.45 * t * t)


rows = [[v.co.copy() for v in top]]
for k in range(N_ROWS):
    prev = rows[-1]
    nxt = []
    for i in range(len(prev)):
        p = snap_ex(prev[i] + dirs[i] * step_of(i))
        nxt.append(p)
    nxt = smooth_row(nxt)
    # geodesic update: each column's direction becomes its actual last step, re-tangented
    for i in range(len(nxt)):
        d = nxt[i] - prev[i]
        if d.length > 1e-6:
            n = snorm(nxt[i])
            d = (d - n * d.dot(n)).normalized()   # keep it in the surface
            dirs[i] = d
    dirs[0] = Vector((0.0, dirs[0].y, dirs[0].z)).normalized()
    rows.append(nxt)
    zs = sorted(p.z for p in nxt)
    print(f"row {k + 1}: z mid {zs[len(zs) // 2]:.4f}  "
          f"midline ({nxt[0].x:+.4f},{nxt[0].y:+.4f},{nxt[0].z:.4f})  "
          f"side ({nxt[-1].x:+.4f},{nxt[-1].y:+.4f},{nxt[-1].z:.4f})")

# grid relaxation: columns crossing the nostril terrain marched at different effective speeds,
# which left the rows (and the top edge) jagged. Umbrella over the 4-grid-neighborhood for the
# marched rows (anchor row 0 stays fixed), then re-snap outside the exclusion zone.
NC = len(rows[0])
for _ in range(2):
    nxt_rows = [rows[0]]
    for k in range(1, len(rows)):
        row = []
        for i in range(NC):
            acc = [rows[k][i], rows[k - 1][i]]
            if k + 1 < len(rows):
                acc.append(rows[k + 1][i])
            if i > 0:
                acc.append(rows[k][i - 1])
            if i + 1 < NC:
                acc.append(rows[k][i + 1])
            row.append(sum(acc, Vector()) / len(acc))
        nxt_rows.append(row)
    rows = nxt_rows
    for k in range(1, len(rows)):
        rows[k] = [snap_ex(p) for p in rows[k]]
        rows[k][0] = Vector((0.0, rows[k][0].y, rows[k][0].z))

# ---- build the grid ----------------------------------------------------------------------------
row_v = [list(top)]
new_verts = []
for r in rows[1:]:
    vs = [bm.verts.new(p) for p in r]
    new_verts.extend(vs)
    row_v.append(vs)

new_faces = []
for a, b in zip(row_v, row_v[1:]):
    for i in range(len(a) - 1):
        try:
            new_faces.append(bm.faces.new((a[i], a[i + 1], b[i + 1], b[i])))
        except ValueError:
            pass

# ---- nostril: the proven 2x2 block -> 8-rim ring insert ----------------------------------------
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

# feature-sized hole: every new face whose centre is inside the nostril radius. The 2x2 block
# of the first attempt was one grid cell — smaller than the actual slot, and it left ragged
# openings around a ridge poking through.
block = [f for f in new_faces if (f.calc_center_median() - best_p).length < R_HOLE]
print(f"nostril block: {len(block)} faces inside R_HOLE {R_HOLE}")
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
inner = [v for f in block for v in f.verts if v not in loop]
inner = list(set(inner))
anchor_inner = [v for v in inner if any(f not in new_faces for f in v.link_faces)]
loop_closed = len(loop) == len(set(v for e in bnd_edges for v in e.verts))
if block and loop_closed and not anchor_inner:
    centre = Vector((0, 0, 0))
    for v in loop:
        centre += v.co
    centre /= len(loop)
    ok, cl, cn, _ = scaf.closest_point_on_mesh(centre)
    centre = cl + cn * 0.0015
    for f in block:
        new_faces.remove(f)
    bmesh.ops.delete(bm, geom=block, context="FACES_ONLY")
    for v in inner:
        if v in new_verts:
            new_verts.remove(v)
    if inner:
        bmesh.ops.delete(bm, geom=inner, context="VERTS")
    n = len(loop)

    # round the hole: the loop is a mix of bridged and snapped heights, which crowns the ring
    # quads unevenly — smooth both rings around their circumference into a clean oval.
    # PINNED: loop verts that belong to the mouth patch (the hole's lower edge sits on the
    # anchor row) must NOT move — smoothing them deformed CP2-4 geometry once already.
    def ring_smooth(ring, pinned=frozenset(), passes=2, blend=0.6):
        for _ in range(passes):
            cos = [v.co.copy() for v in ring]
            for i, v in enumerate(ring):
                if v in pinned:
                    continue
                mid = (cos[i - 1] + cos[(i + 1) % len(ring)]) / 2
                v.co = cos[i].lerp(mid, blend)

    ring_smooth(loop, pinned=frozenset(top))
    rim = [bm.verts.new(snap(centre + (v.co - centre) * 0.45, 0.0015)) for v in loop]
    ring_smooth(rim)
    for v in rim:
        v.co = snap(v.co, 0.0015)
    new_verts.extend(rim)
    for i in range(n):
        j = (i + 1) % n
        new_faces.append(bm.faces.new((loop[i], loop[j], rim[j], rim[i])))
    print(f"nostril ring set: {n} rim verts, {n} quads, open centre")
else:
    print(f"!! nostril insert ABORTED ({len(block)} faces, boundary {len(loop)} verts, "
          f"closed={loop_closed}, {len(anchor_inner)} anchor verts inside) — grid left solid")

# the live Shrinkwrap modifier would drag the bridging verts back into the slot at eval time —
# exclude everything inside the exclusion zone from it (the script owns those positions)
noshrink = rt.vertex_groups.get("cp5_noshrink") or rt.vertex_groups.new(name="cp5_noshrink")
ns_i = noshrink.index
for v in bm.verts:
    if (v.co - best_p).length < R_EX * 1.15:
        v[dl][ns_i] = 1.0
for m in rt.modifiers:
    if m.type == "SHRINKWRAP":
        m.vertex_group = "cp5_noshrink"
        m.invert_vertex_group = True

# tag everything new for the rerun cleanup
for v in new_verts:
    v[dl][gi] = 1.0

bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(rt.data)
bm.free()
nq = sum(1 for p in rt.data.polygons if len(p.vertices) == 4)
nt = sum(1 for p in rt.data.polygons if len(p.vertices) == 3)
print(f"after CP5: {len(rt.data.polygons)} faces ({nq} quads, {nt} tris)")
bpy.ops.wm.save_as_mainfile(filepath=BLEND)

# ---- CP5 renders -------------------------------------------------------------------------------
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
w = bpy.data.worlds.new("W5"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.40, 0.44, 0.41, 1)
sc.world = w
ctr = Vector((0.0, -0.20, 0.775))
cd = bpy.data.cameras.new("C5"); cam = bpy.data.objects.new("C5", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"; cd.ortho_scale = 0.34
cd.clip_start = 0.001; cd.clip_end = 100.0
OUT = os.path.join(os.path.dirname(BLEND), "retopo_cp5")
os.makedirs(OUT, exist_ok=True)
for deg in (0, 40, 75):
    a = math.radians(deg)
    cam.location = (ctr.x + math.sin(a) * 2, ctr.y - math.cos(a) * 2, ctr.z + 0.01)
    cam.rotation_euler = (math.radians(89), 0, a)
    sc.render.filepath = os.path.join(OUT, f"cp5_{deg:03d}.png")
    bpy.ops.render.render(write_still=True)
# top-front tilt: the only angle that shows nostril holes as holes
cam.location = (ctr.x, ctr.y - 1.55, ctr.z + 1.25)
cam.rotation_euler = (math.radians(51), 0, 0)
sc.render.filepath = os.path.join(OUT, "cp5_topfront.png")
bpy.ops.render.render(write_still=True)
# the patch alone — the surface it will actually be, no scaffold showing through the holes
scaf.hide_render = True
sc.render.filepath = os.path.join(OUT, "cp5_solo_topfront.png")
bpy.ops.render.render(write_still=True)
cam.location = (ctr.x, ctr.y - 2, ctr.z + 0.01)
cam.rotation_euler = (math.radians(89), 0, 0)
sc.render.filepath = os.path.join(OUT, "cp5_solo_000.png")
bpy.ops.render.render(write_still=True)
scaf.hide_render = False
print(f"renders -> {OUT}")

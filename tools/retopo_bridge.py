"""CP6 pass 2 — the BRIDGE: march the nose patch's columns up the face and sew them into
the eye annuli.

    blender -b --python tools/retopo_bridge.py -- work/RETOPO_clyffy.blend

The gap eye-ring-bottom -> nose-top-edge is ~0.1 of surface — the whole bridge climb, not a
single weld row. So this is a continuation of the CP5 march: same geodesic stepping off the
nose patch's open top row. A column that comes within CAPTURE_R of a LOWER-arc vert of the
eye OUTER ring locks onto that exact ring vert (no separate weld) and stops advancing.
Where a frozen column's neighbour still advances, the band face is a triangle — counted and
reported. Columns that never capture stop at Z_STOP:

  * glabella columns (inner of the eye) — open top edge for the skull patch,
  * lateral cheek columns (outer of the eye) — open edge for the cheek patch.

Earned rule applied: ring verts and nose-top verts are PINNED — smoothing moves only live
marched verts. Rerunnable: new verts tagged "cp6_bridge".
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
MAX_ROWS = 8
CAPTURE_R = 0.016    # >= STEP, or a column can step past a ring vert without capturing
Z_STOP = 0.852          # brow line: uncaptured columns stop here, edge stays open


def snap(p, offset=0.0025):
    ok, loc, nor, _ = scaf.closest_point_on_mesh(Vector(p))
    return (loc + nor * offset) if ok else Vector(p)


def snorm(p):
    ok, loc, nor, _ = scaf.closest_point_on_mesh(Vector(p))
    return nor if ok else Vector((0, -1, 0))


# ---- rerun cleanup ------------------------------------------------------------------------------
vg = rt.vertex_groups.get("cp6_bridge")
if vg is None:
    vg = rt.vertex_groups.new(name="cp6_bridge")
gi = vg.index

bm = bmesh.new(); bm.from_mesh(rt.data)
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
dl = bm.verts.layers.deform.verify()
old = [v for v in bm.verts if gi in v[dl]]
if old:
    bmesh.ops.delete(bm, geom=old, context="VERTS")
    print(f"cleared previous bridge pass: {len(old)} verts removed")
    bm.edges.ensure_lookup_table()

# ---- anchors: nose top row + eye outer ring lower arc ------------------------------------------
# A z-window guess for the top row caught a SIDE-EDGE vert once (14 verts, one with no
# below-neighbour -> crash). Structural selection instead: walk the patch's outer boundary
# loop from the midline-top vert toward +x; the top edge ends where the boundary turns DOWN
# the side (z drop > 0.006 per step).
bnd_edges = [e for e in bm.edges if e.link_faces and len(e.link_faces) == 1]
adjb = {}
for e in bnd_edges:
    a, b = e.verts
    adjb.setdefault(a, []).append(b)
    adjb.setdefault(b, []).append(a)
# the patch's outer loop is the boundary component containing the chin (lowest z)
chin = min(adjb, key=lambda v: v.co.z)
outer_loop, stack, seen = set(), [chin], {chin}
while stack:
    v = stack.pop(); outer_loop.add(v)
    for o in adjb[v]:
        if o not in seen:
            seen.add(o); stack.append(o)
mid_top = max((v for v in outer_loop if v.co.x < 0.001 and v.co.y < -0.2),
              key=lambda v: v.co.z)
top = [mid_top]
prev = None
while True:
    cur = top[-1]
    # max-x neighbour, NOT first-found: at the midline both the +x column and the
    # mirror-seam vert below qualify, and first-found once walked down the seam
    cands = [o for o in adjb[cur] if o is not prev and o in outer_loop
             and o.co.x > cur.co.x - 1e-6 and o not in top]
    if not cands:
        break
    nxt = max(cands, key=lambda o: o.co.x)
    prev = cur
    top.append(nxt)
    # structural corner: every top-edge vert has 3 edges (left/right/below); the corner
    # has exactly 2. A z-drop cutoff misfired twice here — post-relaxation drops are tiny.
    if len(nxt.link_edges) == 2:
        break
print(f"nose top row: {len(top)} verts, x {top[0].co.x:+.4f} -> {top[-1].co.x:+.4f}, "
      f"z {top[0].co.z:.4f} -> {top[-1].co.z:.4f}")

# the annulus has TWO boundary loops — the aperture rim (lid margin) is a boundary too, and
# capturing onto it would sew the bridge into the lid. A radial-distance split dropped the
# outer ring's bottom vert once; split by CONNECTIVITY instead: two loop components, the
# outer one has the larger bounding box.
eye_bnd = [v for v in adjb if v.co.y > -0.20 and 0.82 < v.co.z < 0.90 and 0.01 < v.co.x < 0.10]
comps = []
left = set(eye_bnd)
while left:
    s = next(iter(left))
    comp, stack = set(), [s]
    left.discard(s)
    while stack:
        v = stack.pop(); comp.add(v)
        for o in adjb[v]:
            if o in left:
                left.discard(o); stack.append(o)
    comps.append(comp)


def span(comp):
    xs = [v.co.x for v in comp]; zs = [v.co.z for v in comp]
    return (max(xs) - min(xs)) + (max(zs) - min(zs))


outer_ring = max(comps, key=span)
centre = sum((v.co for v in outer_ring), Vector()) / len(outer_ring)
lower = sorted([v for v in outer_ring if v.co.z < centre.z + 0.002], key=lambda v: v.co.x)
print(f"eye boundary: {len(eye_bnd)} verts in {len(comps)} loops -> outer {len(outer_ring)}, "
      f"lower arc {len(lower)}: " + ", ".join(f"({v.co.x:+.3f},{v.co.z:.3f})" for v in lower))

# ---- march with capture ------------------------------------------------------------------------
NC = len(top)
dirs = []
for v in top:
    below = None
    for e in v.link_edges:
        o = e.other_vert(v)
        if o in top:
            continue
        if below is None or o.co.z < below.co.z:
            below = o
    dirs.append((v.co - below.co).normalized())
for _ in range(2):
    dirs = [dirs[0]] + [(dirs[i - 1] + dirs[i] + dirs[i + 1]).normalized()
                        for i in range(1, NC - 1)] + [dirs[-1]]
dirs[0] = Vector((0.0, dirs[0].y, dirs[0].z)).normalized()

# TARGET-SEEKING march: continuation dirs sent the lateral columns wrapping around the
# muzzle (the glabella climbed, the under-eye band never closed — 0 captures in 8 rows).
# Each column is assigned its landing vert on the eye arc by x-correspondence (the midline
# column gets the glabella point) and marches along the surface TOWARD it. Several columns
# sharing one ring vert is intended: that is the 13-column -> 6-vert density transition,
# and it lands as capture fans (tris) on the arc.
glab = snap(Vector((0.0, -0.150, 0.858)))
targets = []
NC = len(top)
for i, v in enumerate(top):
    if v.co.x < 0.010:
        targets.append(("glab", glab))
    else:
        # PROPORTIONAL mapping, not nearest-x: the top row's x range is compressed vs the
        # arc's, so nearest-x funneled 5 columns into one vert and skipped the canthus and
        # outer corner entirely (left a crack under the ring's outer bottom)
        t = i / (NC - 1)
        rv = lower[min(len(lower) - 1, round(t * (len(lower) - 1)))]
        targets.append(("ring", rv))
print("column targets: " + ", ".join(
    f"{i}:{'G' if t[0] == 'glab' else f'({t[1].co.x:+.3f},{t[1].co.z:.3f})'}"
    for i, t in enumerate(targets)))

rows = [list(top)]                 # rows hold VERT objects; captured columns hold ring verts
frozen = [False] * NC
new_verts = []
for k in range(MAX_ROWS):
    prev = rows[-1]
    # positions for live columns: step along the surface toward the assigned target
    pos = {}
    for i in range(NC):
        if frozen[i]:
            continue
        p0 = prev[i].co
        tgt_co = targets[i][1] if targets[i][0] == "glab" else targets[i][1].co
        d = tgt_co - p0
        n = snorm(p0)
        d = d - n * d.dot(n)
        if d.length < 1e-6:
            d = dirs[i]
        pos[i] = snap(p0 + d.normalized() * STEP)
    # smooth live positions along the row (frozen/anchor neighbours participate as fixed)
    for _ in range(2):
        nxt_pos = {}
        for i in pos:
            acc = [pos[i]]
            for j in (i - 1, i + 1):
                if j in pos:
                    acc.append(pos[j])
                elif 0 <= j < NC:
                    acc.append(prev[j].co)
            nxt_pos[i] = sum(acc, Vector()) / len(acc)
        pos = {i: snap(p) for i, p in nxt_pos.items()}
    if 0 in pos:
        pos[0] = Vector((0.0, pos[0].y, pos[0].z))
    # capture check, then create verts / stop columns
    row = []
    for i in range(NC):
        if frozen[i]:
            row.append(rows[-1][i])
            continue
        p = pos[i]
        if targets[i][0] == "glab":
            if (p - glab).length < CAPTURE_R:
                v = bm.verts.new(Vector((0.0, glab.y, glab.z)))
                new_verts.append(v)
                row.append(v)
                frozen[i] = True
                continue
            v = bm.verts.new(p)
            new_verts.append(v)
            row.append(v)
            continue
        tgt, dbest = None, CAPTURE_R
        for rv in lower:
            d = (p - rv.co).length
            if d < dbest:
                tgt, dbest = rv, d
        if tgt is not None:
            row.append(tgt)
            frozen[i] = True
        elif p.z >= Z_STOP:
            v = bm.verts.new(Vector((p.x, p.y, min(p.z, Z_STOP))))
            new_verts.append(v)
            row.append(v)
            frozen[i] = True
        else:
            v = bm.verts.new(p)
            new_verts.append(v)
            row.append(v)
            d = p - prev[i].co
            n = snorm(p)
            d = (d - n * d.dot(n))
            if d.length > 1e-6:
                dirs[i] = d.normalized()
    rows.append(row)
    ncap = sum(1 for i in range(NC) if frozen[i])
    print(f"row {k + 1}: {ncap}/{NC} columns stopped "
          f"(captured or at z {Z_STOP})")
    if all(frozen):
        break

# ---- faces -------------------------------------------------------------------------------------
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
print(f"bridge: {made_q} quads, {made_t} tris at capture points")

# post-stitch relax: rounds the glabella tent and spreads the capture fans. Only the new
# bridge verts move — ring, anchor and mouth/nose verts are pinned by construction.
midline = {v for v in new_verts if v.co.x == 0.0}
for _ in range(2):
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
        if v in midline:
            v.co.x = 0.0

for v in new_verts:
    v[dl][gi] = 1.0

bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(rt.data)
bm.free()
nq = sum(1 for p in rt.data.polygons if len(p.vertices) == 4)
nt = sum(1 for p in rt.data.polygons if len(p.vertices) == 3)
print(f"after CP6 pass 2: {len(rt.data.polygons)} faces ({nq} quads, {nt} tris)")
bpy.ops.wm.save_as_mainfile(filepath=BLEND)

# ---- renders -----------------------------------------------------------------------------------
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
w = bpy.data.worlds.new("W6b"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.40, 0.44, 0.41, 1)
sc.world = w
ctr = Vector((0.0, -0.16, 0.80))
cd = bpy.data.cameras.new("C6b"); cam = bpy.data.objects.new("C6b", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"; cd.ortho_scale = 0.46
cd.clip_start = 0.001; cd.clip_end = 100.0
OUT = os.path.join(os.path.dirname(BLEND), "retopo_cp6")
os.makedirs(OUT, exist_ok=True)
for deg in (0, 30):
    a = math.radians(deg)
    cam.location = (ctr.x + math.sin(a) * 2, ctr.y - math.cos(a) * 2, ctr.z + 0.01)
    cam.rotation_euler = (math.radians(89), 0, a)
    sc.render.filepath = os.path.join(OUT, f"cp6b_{deg:03d}.png")
    bpy.ops.render.render(write_still=True)
cd.ortho_scale = 0.20
ctr_eye = Vector((0.040, -0.14, 0.835))
cam.location = (ctr_eye.x + math.sin(math.radians(15)) * 2,
                ctr_eye.y - math.cos(math.radians(15)) * 2, ctr_eye.z)
cam.rotation_euler = (math.radians(89), 0, math.radians(15))
sc.render.filepath = os.path.join(OUT, "cp6b_closeup.png")
bpy.ops.render.render(write_still=True)
scaf.hide_render = True
cd.ortho_scale = 0.46
cam.location = (ctr.x, ctr.y - 2, ctr.z + 0.01)
cam.rotation_euler = (math.radians(89), 0, 0)
sc.render.filepath = os.path.join(OUT, "cp6b_solo_000.png")
bpy.ops.render.render(write_still=True)
scaf.hide_render = False
print(f"renders -> {OUT}")

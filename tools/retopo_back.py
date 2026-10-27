"""CP7 — the BACK OF THE HEAD, built outward from the sagittal midline.

    blender -b --python tools/retopo_back.py -- work/RETOPO_clyffy.blend

Direction matters here. Marching backward from the face would drive the front straight into the
ear and horn — the failure that killed the global sweep. Instead the front STARTS on the mirror
plane (a chain sampled from the CP1 sagittal arc, crown → occiput → nape) and expands LATERALLY.
That sweep is well conditioned: an arc on the mirror plane growing outward, meeting the finished
face shell at the end, where columns weld onto its open boundary and stop.

It also means the back midline — the exact line that was malformed on v2 and that no numeric
probe caught — is placed explicitly from the approved guide, not inferred.

Terminations, in priority order per column:
  * WELD onto an existing open-boundary vert of the face shell (closes the surface outright)
  * CAPTURE onto the ear / horn base guide rings (those become CP8's holes)
  * the NECK ring (the CP9 body boundary)

Rerunnable: new verts tagged in vertex group "cp7_back".
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

STEP = 0.020
MIN_SP = 0.012
MAX_ROWS = 14
CAPTURE_R = STEP
SPACING = 0.022          # midline chain resample spacing


def snap(p, offset=0.0025):
    ok, loc, nor, _ = scaf.closest_point_on_mesh(Vector(p))
    return (loc + nor * offset) if ok else Vector(p)


def snorm(p):
    ok, loc, nor, _ = scaf.closest_point_on_mesh(Vector(p))
    return nor if ok else Vector((0, 0, 1))


def guide_pts(name):
    o = bpy.data.objects[name]
    return [o.matrix_world @ p.co.to_3d() for s in o.data.splines for p in s.points]


# ---- rerun cleanup -------------------------------------------------------------------------------
vg = rt.vertex_groups.get("cp7_back") or rt.vertex_groups.new(name="cp7_back")
gi = vg.index
bm = bmesh.new(); bm.from_mesh(rt.data)
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
dl = bm.verts.layers.deform.verify()
old = [v for v in bm.verts if gi in v[dl]]
if old:
    bmesh.ops.delete(bm, geom=old, context="VERTS")
    print(f"cleared previous back pass: {len(old)} verts")
    bm.edges.ensure_lookup_table()

# ---- where the face shell currently ends on the midline ------------------------------------------
bnd_edges = [e for e in bm.edges if e.link_faces and len(e.link_faces) == 1]
adjb = {}
for e in bnd_edges:
    a, b = e.verts
    adjb.setdefault(a, []).append(b)
    adjb.setdefault(b, []).append(a)
crown = max((v for v in adjb if abs(v.co.x) < 0.004), key=lambda v: v.co.z)
print(f"face shell crown vert: ({crown.co.x:+.4f},{crown.co.y:+.4f},{crown.co.z:.4f})")

# ---- the midline chain: sagittal arc from the crown, back and down to the neck --------------------
arc = guide_pts("vis_sagittal_arc")
# order the arc along itself, starting nearest the crown vert
arc = sorted(arc, key=lambda p: (p - crown.co).length)
seed = arc[0]
chain = [seed]
pool = [p for p in arc if p is not seed]
while pool:
    nxt = min(pool, key=lambda p: (p - chain[-1]).length)
    if (nxt - chain[-1]).length > 0.12:
        break
    chain.append(nxt)
    pool.remove(nxt)
# keep only the BACK half (behind the crown), down past the neck ring — the walk above already
# ordered it crown -> occiput -> nape, so do NOT re-sort (a z/y sort scrambles the nape run)
chain = [p for p in chain if p.y >= crown.co.y - 0.01 and p.z > 0.640]
print(f"sagittal arc: {len(chain)} points, "
      f"({chain[0].x:+.3f},{chain[0].y:+.3f},{chain[0].z:.3f}) -> "
      f"({chain[-1].x:+.3f},{chain[-1].y:+.3f},{chain[-1].z:.3f})")

# resample by arc length at SPACING
res = [chain[0]]
acc = 0.0
for a, b in zip(chain, chain[1:]):
    seg = (b - a).length
    t = 0.0
    while acc + (seg - t) >= SPACING:
        t += SPACING - acc
        res.append(a.lerp(b, t / seg))
        acc = 0.0
    acc += seg - t
res.append(chain[-1])
mid_pts = [Vector((0.0, snap(p).y, snap(p).z)) for p in res]
print(f"midline chain: {len(mid_pts)} verts at ~{SPACING} spacing")

# the crown end of the chain WELDS to the face shell's crown vert
front = []
for i, p in enumerate(mid_pts):
    if i == 0 and (p - crown.co).length < 0.035:
        front.append(crown)
    else:
        front.append(bm.verts.new(p))
new_verts = [v for v in front if v is not crown]
for i in range(len(front) - 1):
    try:
        bm.edges.new((front[i], front[i + 1]))
    except ValueError:
        pass

# ---- targets --------------------------------------------------------------------------------------
ring_pts = guide_pts("vis_ear_base_R") + guide_pts("vis_horn_base_R")
neck_pts = guide_pts("vis_neck")
front_set = set(front)
near_front = set(front)
for v in front:
    near_front.update(e.other_vert(v) for e in v.link_edges)
wtargets = [v for v in adjb if v not in near_front]
print(f"targets: {len(ring_pts)} ring pts, {len(neck_pts)} neck pts, "
      f"{len(wtargets)} weldable boundary verts")

# ---- march laterally -------------------------------------------------------------------------------
NC = len(front)
cols = []
for i, v in enumerate(front):
    d = Vector((1.0, 0.0, 0.0))
    nrm = snorm(v.co)
    d = d - nrm * d.dot(nrm)
    cols.append({"idx": [i], "v": v, "dir": d.normalized() if d.length > 1e-6 else Vector((1, 0, 0)),
                 "frozen": False})
rows = [list(front)]
stats = {"weld": 0, "ring": 0, "neck": 0, "merge": 0}
for k in range(MAX_ROWS):
    live = [c for c in cols if not c["frozen"]]
    if not live:
        break
    for c in live:
        c["p"] = snap(c["v"].co + c["dir"] * STEP)
    newp = {}
    for k2 in range(1, len(cols) - 1):
        c = cols[k2]
        if c["frozen"]:
            continue
        nb = [cols[j]["p"] if not cols[j]["frozen"] else cols[j]["v"].co for j in (k2 - 1, k2 + 1)]
        newp[k2] = c["p"].lerp(sum(nb, Vector()) / len(nb), 0.3)
    for k2, p in newp.items():
        cols[k2]["p"] = snap(p)
    j = 0
    while j < len(cols) - 1:
        a, b = cols[j], cols[j + 1]
        if not a["frozen"] and not b["frozen"] and (a["p"] - b["p"]).length < MIN_SP:
            a["p"] = snap((a["p"] + b["p"]) / 2)
            a["idx"] = a["idx"] + b["idx"]
            a["dir"] = (a["dir"] + b["dir"]).normalized()
            cols.pop(j + 1)
            stats["merge"] += 1
        else:
            j += 1
    for c in cols:
        if c["frozen"]:
            continue
        p = c["p"]
        wv = min(wtargets, key=lambda t: (p - t.co).length) if wtargets else None
        if wv is not None and (p - wv.co).length < CAPTURE_R:
            c["v"] = wv
            c["frozen"] = True
            stats["weld"] += 1
            continue
        term = None
        rp = min(ring_pts, key=lambda t: (p - t).length)
        if (p - rp).length < CAPTURE_R * 0.8:
            p = rp; term = "ring"
        else:
            npt = min(neck_pts, key=lambda t: (p - t).length)
            if (p - npt).length < CAPTURE_R * 0.8:
                p = npt; term = "neck"
        v = bm.verts.new(p)
        new_verts.append(v)
        d = Vector((1.0, 0.0, 0.0))
        c["v"] = v
        if term:
            c["frozen"] = True
            stats[term] += 1
        else:
            nrm = snorm(p)
            d = d - nrm * d.dot(nrm)
            if d.length > 1e-6:
                c["dir"] = d.normalized()
    row = [None] * NC
    for c in cols:
        for i in c["idx"]:
            row[i] = c["v"]
    rows.append(row)
print(f"march: {len(rows) - 1} rows, {len(cols)} final columns "
      f"(weld {stats['weld']}, ring {stats['ring']}, neck {stats['neck']}, merge {stats['merge']})")

made_q = made_t = 0
for a, b in zip(rows, rows[1:]):
    for i in range(NC - 1):
        uniq = []
        for v in (a[i], a[i + 1], b[i + 1], b[i]):
            if v not in uniq:
                uniq.append(v)
        if len(uniq) < 3:
            continue
        try:
            bm.faces.new(uniq)
            made_q += len(uniq) == 4
            made_t += len(uniq) == 3
        except ValueError:
            pass
print(f"back: {made_q} quads, {made_t} tris")

mid_v = {v for v in new_verts if abs(v.co.x) < 1e-6}
for _ in range(3):
    moves = {}
    for v in new_verts:
        nbrs = [e.other_vert(v) for e in v.link_edges]
        if len(nbrs) >= 2:
            moves[v] = sum((o.co for o in nbrs), Vector()) / len(nbrs)
    for v, m in moves.items():
        v.co = v.co.lerp(m, 0.5)
    for v in new_verts:
        v.co = snap(v.co)
        if v in mid_v:
            v.co.x = 0.0
for v in new_verts:
    v[dl][gi] = 1.0

bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(rt.data)
bm.free()
nq = sum(1 for p in rt.data.polygons if len(p.vertices) == 4)
nt = sum(1 for p in rt.data.polygons if len(p.vertices) == 3)
print(f"after back: {len(rt.data.polygons)} faces ({nq} quads, {nt} tris)")
bpy.ops.wm.save_as_mainfile(filepath=BLEND)

# ---- renders: BACK ANGLES ARE THE POINT ------------------------------------------------------------
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
w = bpy.data.worlds.new("WB"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.40, 0.44, 0.41, 1)
sc.world = w
ctr = Vector((0.0, -0.05, 0.85))
cd = bpy.data.cameras.new("CB"); cam = bpy.data.objects.new("CB", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"; cd.ortho_scale = 0.55
cd.clip_start = 0.001; cd.clip_end = 100.0
OUT = os.path.join(os.path.dirname(BLEND), "retopo_back")
os.makedirs(OUT, exist_ok=True)
for tag, hide in (("", False), ("solo_", True)):
    scaf.hide_render = hide
    for deg in (90, 180, 240, 270, 300):
        a = math.radians(deg)
        cam.location = (ctr.x + math.sin(a) * 2, ctr.y - math.cos(a) * 2, ctr.z + 0.01)
        cam.rotation_euler = (math.radians(89), 0, a)
        sc.render.filepath = os.path.join(OUT, f"back_{tag}{deg:03d}.png")
        bpy.ops.render.render(write_still=True)
scaf.hide_render = False
cam.location = (ctr.x, ctr.y, ctr.z + 2)
cam.rotation_euler = (0, 0, 0)
sc.render.filepath = os.path.join(OUT, "back_top.png")
bpy.ops.render.render(write_still=True)
print(f"renders -> {OUT}")

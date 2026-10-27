"""Resample an open BOUNDARY so the next region has an even edge to march from.

    blender -b --python tools/retopo_resample_edge.py -- work/RETOPO_clyffy.blend 0.725 0.030 \
        --clear cp9_neck

Args: blend, ZMAX (only boundary below this is touched), TARGET (max allowed gap).
`--clear GROUP` deletes that vertex group's verts FIRST. Without it this tool resamples whatever
the current lowest boundary happens to be, which on the first run meant the old neck region's own
ragged edge rather than the neck ring underneath it — resampling a boundary that was about to be
deleted. Clear the region being rebuilt, then resample the edge it will actually march from.

WHY. `tools/inspect_front.py` on the neck ring: gaps run 0.0018 to 0.0915, mean 0.0246 — a 3.7x
spread, with the midline throat carried by five verts from chin to collar while the rest of the
ring averages 0.020. Marching the body off that edge does not fix it, it PROPAGATES it: the first
row inherits the 0.0915 gap and every row below repeats it. Two attempts to tune the march around
this (more rows, finer step) both failed and the second made it worse, because the defect was never
in the march.

ONLY SPLITS, NEVER COLLAPSES. Splitting inserts a new vertex on a boundary edge and snaps it to the
scaffold; no existing vertex moves, so nothing already approved can drift. Collapsing would move
verts and is not needed for the problem at hand — the short gaps make small faces, which is untidy
but harmless, while the long ones make unusable ones.

NO NGONS. Subdividing one edge of a quad leaves a pentagon, and an ngon is exactly what the region
gate forbids. So each split is followed by a face split from the new vertex to the opposite corner,
turning the pentagon into a quad + a tri.
"""
import bpy, bmesh, sys, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
ZMAX = float(argv[1]) if len(argv) > 1 else 0.725
TARGET = float(argv[2]) if len(argv) > 2 else 0.030
bpy.ops.wm.open_mainfile(filepath=BLEND)
scaf = bpy.data.objects["SCAFFOLD"]
rt = bpy.data.objects["retopo_head"]

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import retopo_gate as gate

if "--clear" in argv:
    gname = argv[argv.index("--clear") + 1]
    g = rt.vertex_groups.get(gname)
    if g:
        bmc = bmesh.new()
        bmc.from_mesh(rt.data)
        dlc = bmc.verts.layers.deform.verify()
        stale = [v for v in bmc.verts if g.index in v[dlc]]
        if stale:
            bmesh.ops.delete(bmc, geom=stale, context="VERTS")
            bmc.to_mesh(rt.data)
            print(f"cleared {len(stale)} verts of '{gname}' — resampling the edge UNDER it")
        bmc.free()

BEFORE = gate.survey(rt, scaf)
print(f"before: {BEFORE['faces']} faces ({BEFORE['quads']}q {BEFORE['tris']}t {BEFORE['ngons']}n), "
      f"loops {BEFORE['loops']}, non-manifold {BEFORE['nonman']}, apertures {BEFORE['apertures']}")


def snap(p, offset=0.0025):
    ok, loc, nor, _ = scaf.closest_point_on_mesh(Vector(p))
    return (loc + nor * offset) if ok else Vector(p)


bm = bmesh.new()
bm.from_mesh(rt.data)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()

MIRROR_EPS = 0.0005
splits = 0
for _ in range(400):                       # bounded: each pass halves the worst offenders
    bm.edges.ensure_lookup_table()
    cand = [e for e in bm.edges
            if len(e.link_faces) == 1
            and e.verts[0].co.z < ZMAX and e.verts[1].co.z < ZMAX
            and e.calc_length() > TARGET]
    if not cand:
        break
    e = max(cand, key=lambda x: x.calc_length())
    f = e.link_faces[0]
    ring = list(f.verts)
    if len(ring) != 4:
        # only quads are handled; a tri splits into two tris with no new ngon either way
        nv = bmesh.utils.edge_split(e, e.verts[0], 0.5)[1]
        nv.co = snap((e.verts[0].co + e.verts[1].co) / 2)
        splits += 1
        continue
    a, b = e.verts
    mid = (a.co + b.co) / 2
    # opposite corner of the quad: the vert two steps round from `a`
    ia = ring.index(a)
    opp = ring[(ia + 2) % 4] if ring[(ia + 1) % 4] is b else ring[(ia - 2) % 4]
    _, nv = bmesh.utils.edge_split(e, a, 0.5)
    nv.co = snap(mid)
    if abs(a.co.x) < MIRROR_EPS and abs(b.co.x) < MIRROR_EPS:
        nv.co.x = 0.0                       # a midline edge stays on the midline
    penta = nv.link_faces[0]
    try:
        bmesh.utils.face_split(penta, nv, opp)
    except ValueError:
        pass                                # already split by a previous pass; leave it
    splits += 1

bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(rt.data)
bm.free()
print(f"\nsplit {splits} boundary edges longer than {TARGET}")

AFTER = gate.survey(rt, scaf)
print(f"after:  {AFTER['faces']} faces ({AFTER['quads']}q {AFTER['tris']}t {AFTER['ngons']}n), "
      f"loops {AFTER['loops']}, non-manifold {AFTER['nonman']}, apertures {AFTER['apertures']}")

ok, lines = True, []
if AFTER["ngons"] > BEFORE["ngons"]:
    ok = False
    lines.append(f"  !! ngons appeared ({BEFORE['ngons']} -> {AFTER['ngons']})")
if AFTER["nonman"] > BEFORE["nonman"]:
    ok = False
    lines.append(f"  !! non-manifold edges appeared ({BEFORE['nonman']} -> {AFTER['nonman']})")
if AFTER["degenerate"] > BEFORE["degenerate"]:
    ok = False
    lines.append(f"  !! zero-area faces appeared ({BEFORE['degenerate']} -> {AFTER['degenerate']})")
if len(AFTER["loops"]) != len(BEFORE["loops"]):
    ok = False
    lines.append(f"  !! the NUMBER of boundary components changed "
                 f"({len(BEFORE['loops'])} -> {len(AFTER['loops'])}) — a hole opened or closed")
for name in AFTER["apertures"]:
    b, a2 = BEFORE["apertures"][name], AFTER["apertures"][name]
    if b > 0 and a2 != b:
        ok = False
        lines.append(f"  !! the {name} changed ({b} -> {a2} verts) — this pass must not touch it")
    elif b > 0:
        lines.append(f"     {name} intact ({a2} verts)")
lines.append(f"     boundary components {len(AFTER['loops'])}, sizes {AFTER['loops']} "
             f"(growth is the point: {splits} verts inserted)")
gate.report(f"resample boundary below z {ZMAX}", lines, ok)

if ok:
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print("saved")
else:
    print("NOT SAVED — the file on disk is unchanged")
    sys.exit(1)

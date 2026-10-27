"""Tuck the head shell's lower edge INSIDE the body so the junction cannot be seen.

    blender -b --python tools/fix_collar.py -- work/RETOPO_clyffy.blend --write

Two wrong versions of this before the right one, both visible in work/model_solo:

  1. Nothing — the body remesh (voxel 0.010, so ~half a voxel of error) poked through the head shell
     in places and showed as a FRINGE along the collar.
  2. Shrink the BODY inward in the overlap band. That removed the fringe and created something
     worse: a hard horizontal LEDGE across the back, because the head shell's open lower edge was
     then standing proud of the body and you were looking straight at the rim.

The rim is the problem, not which surface is bigger. A seam between two overlapping surfaces is
hidden by tucking the one with the OPEN EDGE inside the closed one — so the body owns the whole
visible neck (its cut is raised to z 0.740, up into the jaw) and the head shell's edge is drawn in
under it. `cp9_neck`, the marched neck region, is deleted outright: it is entirely inside the body
now and was only ever there to give the marched body something to anchor to.
"""
import bpy, bmesh, sys, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
WRITE = "--write" in argv
Z_FULL, Z_NONE = 0.660, 0.730   # full tuck at/below Z_FULL, none at/above Z_NONE
TUCK = 0.014                    # deeper than the remesh error, so the rim cannot re-emerge

bpy.ops.wm.open_mainfile(filepath=BLEND)
body = bpy.data.objects["clyffy_body"]
rt = bpy.data.objects["retopo_head"]

# the marched neck is redundant now — the body owns the neck
g = rt.vertex_groups.get("cp9_neck")
if g:
    bm = bmesh.new()
    bm.from_mesh(rt.data)
    dl = bm.verts.layers.deform.verify()
    kill = [v for v in bm.verts if g.index in v[dl]]
    bmesh.ops.delete(bm, geom=kill, context="VERTS")
    bm.to_mesh(rt.data)
    bm.free()
    rt.vertex_groups.remove(g)
    print(f"deleted the marched neck ({len(kill)} verts) — the body remesh covers it")

bm = bmesh.new()
bm.from_mesh(rt.data)
bm.verts.ensure_lookup_table()
bm.normal_update()
moved, worst = 0, 0.0
for v in bm.verts:
    if v.co.z > Z_NONE:
        continue
    t = min(1.0, (Z_NONE - v.co.z) / (Z_NONE - Z_FULL))
    d = TUCK * t * t
    if d > 1e-6:
        v.co -= v.normal * d
        moved += 1
        worst = max(worst, d)
bm.to_mesh(rt.data)
bm.free()
zs = [v.co.z for v in rt.data.vertices]
print(f"tucked {moved} head verts inward by up to {worst:.4f}; shell now z "
      f"[{min(zs):+.4f}, {max(zs):+.4f}]")

# verify: is any of the head's lower edge still OUTSIDE the body?
from mathutils.bvhtree import BVHTree
dg = bpy.context.evaluated_depsgraph_get()
ev = body.evaluated_get(dg)
me = ev.to_mesh()
bmb = bmesh.new()
bmb.from_mesh(me)
bmb.transform(body.matrix_world)
tree = BVHTree.FromBMesh(bmb)
bmb.free()
ev.to_mesh_clear()

bmr = bmesh.new()
bmr.from_mesh(rt.data)
edge_v = {v for e in bmr.edges if len(e.link_faces) == 1 for v in e.verts}
out = 0
for v in edge_v:
    p = rt.matrix_world @ v.co
    if p.z > Z_NONE:
        continue
    loc, nor, idx, dist = tree.find_nearest(p)
    if loc is not None and (p - loc).dot(nor) > 0.0:
        out += 1
bmr.free()
print(f"head boundary verts below z {Z_NONE} still OUTSIDE the body: {out}"
      + ("  <- the rim would still show" if out else "  (rim fully hidden)"))

if WRITE:
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print("saved")

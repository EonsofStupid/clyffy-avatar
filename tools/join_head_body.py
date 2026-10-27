"""Join the head shell and the body into ONE mesh, bridged at the neck.

    blender -b --python tools/join_head_body.py -- work/RETOPO_clyffy.prerig.blend --write

THE STRUCTURAL FIX. The head and body were two overlapping objects, the head's collar tucked inside
the body so the join could not be seen at rest. That works at rest and only at rest. Rotate the head
26 degrees and a collar vertex 0.10 from the pivot moves 0.044 — far more than the 0.028 tuck — so
the head's rim comes straight back out through the body and the neck breaks up into shards.

No amount of weight painting fixes that, because it is not a weighting problem. Two surfaces that
must move as one have to BE one. Both meshes are cut back to z 0.695, where the neck is at its
narrowest (0.23 wide) and a bridge is shortest, then joined and bridged into a single continuous
surface from horn to hoof.

The tucked collar geometry is discarded rather than reused: it was pulled 0.028 inward and would
put a pinch ring in the bridge.
"""
import bpy, bmesh, sys, os

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
OUT = os.path.abspath(argv[1]) if len(argv) > 1 and not argv[1].startswith("--") else BLEND
WRITE = "--write" in argv
ZJOIN = 0.695

bpy.ops.wm.open_mainfile(filepath=BLEND)
rt = bpy.data.objects["retopo_head"]
body = bpy.data.objects["clyffy_body"]

# the Shrinkwrap would drag the head back onto the scaffold after every edit
for m in list(rt.modifiers):
    if m.type == "SHRINKWRAP":
        rt.modifiers.remove(m)
        print("removed Shrinkwrap from the head shell")
# apply Mirror so the head is a whole two-sided mesh before joining
bpy.context.view_layer.objects.active = rt
for o in bpy.context.selected_objects:
    o.select_set(False)
rt.select_set(True)
for m in list(rt.modifiers):
    if m.type == "MIRROR":
        bpy.ops.object.modifier_apply(modifier=m.name)
        print(f"applied Mirror on the head -> {len(rt.data.polygons)} faces")


def cut(ob, keep_above):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    if keep_above:
        kill = [f for f in bm.faces if f.calc_center_median().z < ZJOIN]
    else:
        kill = [f for f in bm.faces if f.calc_center_median().z > ZJOIN]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    n = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    bm.to_mesh(ob.data)
    bm.free()
    print(f"  {ob.name}: cut to {len(ob.data.polygons)} faces, {n} open edges")


cut(rt, True)      # head keeps everything ABOVE the join
cut(body, False)   # body keeps everything BELOW it

# ---- join into one object ------------------------------------------------------------------------
for o in bpy.context.selected_objects:
    o.select_set(False)
rt.select_set(True)
body.select_set(True)
bpy.context.view_layer.objects.active = body
bpy.ops.object.join()
mesh = bpy.context.view_layer.objects.active
mesh.name = "clyffy_mesh"
mesh.data.name = "clyffy_mesh"
print(f"joined -> {mesh.name}: {len(mesh.data.polygons)} faces")

# ---- bridge the two rims -------------------------------------------------------------------------
bm = bmesh.new()
bm.from_mesh(mesh.data)
bm.edges.ensure_lookup_table()
rim = [e for e in bm.edges if len(e.link_faces) == 1
       and abs(e.verts[0].co.z - ZJOIN) < 0.060 and abs(e.verts[1].co.z - ZJOIN) < 0.060]
# separate the two rims by which side of the join they sit on
lo = [e for e in rim if (e.verts[0].co.z + e.verts[1].co.z) / 2 < ZJOIN]
hi = [e for e in rim if (e.verts[0].co.z + e.verts[1].co.z) / 2 >= ZJOIN]
print(f"rims: {len(lo)} edges below the join, {len(hi)} above")
before = len(bm.faces)
try:
    bmesh.ops.bridge_loops(bm, edges=lo + hi, use_pairs=False, use_cyclic=False,
                           use_merge=False, merge_factor=0.5, twist_offset=0)
except (RuntimeError, ValueError) as e:
    print(f"!! bridge failed: {e}")
print(f"bridge added {len(bm.faces) - before} faces")
openb = sum(1 for e in bm.edges if len(e.link_faces) == 1)
nonman = sum(1 for e in bm.edges if len(e.link_faces) > 2)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
nq = sum(1 for f in bm.faces if len(f.verts) == 4)
nt = sum(1 for f in bm.faces if len(f.verts) == 3)
bm.to_mesh(mesh.data)
bm.free()
print(f"\nclyffy_mesh: {len(mesh.data.polygons)} faces ({nq} quads, {nt} tris), "
      f"{openb} open edges, {nonman} non-manifold")
print("  open edges left should be the mouth-adjacent ones only "
      "(the eye apertures and nostrils were closed by the eyeball/nose parts)")

if WRITE:
    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print(f"saved -> {OUT}")

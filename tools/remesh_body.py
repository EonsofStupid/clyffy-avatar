"""The body: voxel remesh the WHOLE scaffold, then cut the head off. One pass, no marching.

    blender -b --python tools/remesh_body.py -- work/RETOPO_clyffy.blend 0.010 --write

WHY IN THIS ORDER. Cutting first and remeshing the piece produced a body riddled with holes — a
lace pattern over the whole torso. Voxel remeshing builds a signed distance field, which needs a
CLOSED surface to know inside from outside; the cut left 294 open boundary edges (and
`bmesh.ops.holes_fill` could not close them — its `sides` default of 4 skips anything bigger than a
quad), so the field flipped sign across the openings and ate the surface.

The scaffold itself IS watertight — measured during the v2 autopsy, 0 see-through rays of 8002. So
remesh it whole, where the field is well defined, and cut afterwards, where a cut is just deleting
faces.

The TAIL comes along as part of the body. It was going to be its own object, built by the ear's
isolate-and-remesh method, but there is no reason to detach something that is already attached
correctly here — a tail is rigged with a bone chain either way, and one fewer floating object is one
fewer thing to misalign.
"""
import bpy, bmesh, sys, os

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
VOXEL = float(argv[1]) if len(argv) > 1 and not argv[1].startswith("--") else 0.010
WRITE = "--write" in argv
ZCUT = 0.740          # up into the jaw: the BODY owns the visible neck, and the head
                      # shell's lower edge tucks away inside it (see tools/fix_collar.py)

bpy.ops.wm.open_mainfile(filepath=BLEND)
scaf = bpy.data.objects["SCAFFOLD"]

# ---- is the source actually closed? ask before relying on it ------------------------------------
bm = bmesh.new()
bm.from_mesh(scaf.data)
bm.transform(scaf.matrix_world)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)   # glTF splits verts at UV seams
openb = sum(1 for e in bm.edges if len(e.link_faces) == 1)
nonman = sum(1 for e in bm.edges if len(e.link_faces) > 2)
print(f"scaffold, welded: {len(bm.faces)} faces, {openb} open edges, {nonman} non-manifold")
if openb:
    print(f"  filling {openb} open edges before remeshing")
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if len(e.link_faces) == 1], sides=0)
    openb = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    print(f"  -> {openb} open edges remain")
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

me = bpy.data.meshes.new("clyffy_body")
bm.to_mesh(me)
bm.free()
old = bpy.data.objects.get("clyffy_body")
if old:
    bpy.data.objects.remove(old, do_unlink=True)
ob = bpy.data.objects.new("clyffy_body", me)
bpy.context.scene.collection.objects.link(ob)

bpy.context.view_layer.objects.active = ob
for o in bpy.context.selected_objects:
    o.select_set(False)
ob.select_set(True)
ob.data.remesh_voxel_size = VOXEL
ob.data.remesh_voxel_adaptivity = 0.0
bpy.ops.object.voxel_remesh()
print(f"remeshed whole scaffold at voxel {VOXEL}: {len(ob.data.polygons)} faces")

# ---- now cut the head off ---------------------------------------------------------------------
bm = bmesh.new()
bm.from_mesh(ob.data)
kill = [f for f in bm.faces if f.calc_center_median().z > ZCUT]
print(f"cutting {len(kill)} faces above z {ZCUT} (the head is already built and approved)")
bmesh.ops.delete(bm, geom=kill, context="FACES")
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
# cap the neck opening the cut leaves, so the body is a closed solid again
op = [e for e in bm.edges if len(e.link_faces) == 1]
if op:
    bmesh.ops.holes_fill(bm, edges=op, sides=0)
    print(f"  neck opening: {len(op)} open edges -> "
          f"{sum(1 for e in bm.edges if len(e.link_faces) == 1)}")
# holes_fill closes a hole with ONE ngon; the neck cap is hidden inside the head but an ngon is
# still an ngon. Poke it into a fan.
ng = [f for f in bm.faces if len(f.verts) > 4]
if ng:
    bmesh.ops.poke(bm, faces=ng)
    print(f"  poked {len(ng)} ngon(s) from the cap into fans")
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
nq = sum(1 for f in bm.faces if len(f.verts) == 4)
nt = sum(1 for f in bm.faces if len(f.verts) == 3)
nn = sum(1 for f in bm.faces if len(f.verts) > 4)
final_open = sum(1 for e in bm.edges if len(e.link_faces) == 1)
final_nm = sum(1 for e in bm.edges if len(e.link_faces) > 2)
bm.to_mesh(ob.data)
bm.free()
zs = [v.co.z for v in ob.data.vertices]
print(f"\nclyffy_body: {len(ob.data.polygons)} faces ({nq} quads, {nt} tris, {nn} ngons)")
print(f"  z [{min(zs):+.4f}, {max(zs):+.4f}]  open edges {final_open}  non-manifold {final_nm}")

ok = True
if final_open > 0:
    print(f"  !! {final_open} open edges — the body is not closed")
    ok = False
if nn > 0:
    print(f"  !! {nn} ngons")
    ok = False
print(f"\n{'PASS' if ok else 'FAIL'}")

# the separate tail is now redundant — the body contains it
t = bpy.data.objects.get("clyffy_tail")
if t and ok:
    bpy.data.objects.remove(t, do_unlink=True)
    print("removed clyffy_tail (the body remesh contains the tail, correctly attached)")

if ok and WRITE:
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print("saved")
elif not ok:
    sys.exit(1)

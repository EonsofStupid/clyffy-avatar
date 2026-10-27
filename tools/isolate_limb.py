"""Cut a limb's scaffold faces into their own object, so a march can snap to the LIMB.

    blender -b --python tools/isolate_limb.py -- work/RETOPO_clyffy.blend armR --write

WHY. `closest_point_on_mesh` against the whole scaffold is wrong on a protrusion, and this project
already paid for that lesson twice: "shrinkwrap is unusable on a protrusion — nearest-surface from
an ear vert finds the SKULL" (CP8), and the concavity twin of it, where a point inside a pocket
snaps to the far wall. The arm is a protrusion sitting a couple of centimetres off the torso, so in
the armpit the nearest surface to an arm vertex IS THE TORSO. Measured: the inner arm column was
held at x 0.187 all the way down while the arm's own inner surface is at x 0.208, and the quad it
left behind stretched to 0.047 — three times the arm's ring spacing.

Snapping to an isolated arm makes that impossible rather than unlikely.

The cut is by CONTOUR, not by a hand-picked box: the arm's own cross-sections at a stack of heights
say where the arm is, and a face belongs to the limb if its centre is inside one of them. The
heights come from the same exact sectioning the rings use.
"""
import bpy, bmesh, sys, os
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scaffold_section import section_loops, classify_loops

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
LIMB = argv[1] if len(argv) > 1 else "armR"
WRITE = "--write" in argv

# limb -> (z range to sample, how much slack around each contour)
LIMBS = {
    # the arm is a free contour from z 0.400 down to about 0.250, where it tapers into the hand.
    # Sampled a little below the free range so the wrist ring at 0.300 is well inside the cut.
    "armR": dict(z0=0.400, z1=0.255, n=12, pad=0.012, zpad=0.020),
    # THE HAND — the mitt below the wrist ring. Contours: z 0.290 x[0.211,0.285] (123 pts),
    # 0.268 x[0.248,0.278] (36), gone by 0.255. It is a small stub, ~0.05 tall.
    "handR": dict(z0=0.302, z1=0.258, n=6, pad=0.010, zpad=0.008),
    # THE TAIL — a BOX cut, not a contour cut, and deliberately. The tail sweeps from x -0.032 at
    # z 0.245 out to x +0.157 at z 0.058 while travelling back in y from 0.15 to 0.28, so a stack of
    # per-height contours would need a moving centre at every sample. It is also the one part that
    # CROSSES THE MIDLINE (x -0.032..0.000 at the root), so it cannot be a mirrored half like every
    # other limb here — it is one whole object. Nothing else lives behind y 0.145 at these heights:
    # the hip ring's back is at y +0.101 and the waist's at +0.153.
    "tail": dict(box=(-0.06, 0.20, 0.145, 0.32, 0.050, 0.258)),
    # THE WHOLE BODY, for the remesh route the operator chose after the marched body lost its form.
    # Everything below the collar ring, minus the tail (its own object by ruling). Arms, hands, legs
    # and hooves come along as part of one continuous surface, which is the entire point: the parts
    # of this build that HELD their shape are the ones remeshed whole from the scaffold (ear 1482q,
    # tail 1872q, hand 236q), and the ones that lost it are the ones marched.
    "body": dict(box=(-0.32, 0.32, -0.32, 0.32, -0.01, 0.642),
                 exclude=(-0.06, 0.20, 0.145, 0.32, 0.050, 0.258)),
}
CFG = LIMBS[LIMB]

bpy.ops.wm.open_mainfile(filepath=BLEND)
scaf = bpy.data.objects["SCAFFOLD"]

BOX = CFG.get("box")
hulls = []
for k in range(CFG["n"] if not BOX else 0):
    z = CFG["z0"] + (CFG["z1"] - CFG["z0"]) * k / (CFG["n"] - 1)
    torso, arms = classify_loops(section_loops(scaf, z))
    if not arms:
        print(f"  z {z:.3f}: no arm contour, skipped")
        continue
    loop = arms[0]
    xs = [p.x for p in loop]
    ys = [p.y for p in loop]
    hulls.append((z, min(xs) - CFG["pad"], max(xs) + CFG["pad"],
                  min(ys) - CFG["pad"], max(ys) + CFG["pad"]))
    print(f"  z {z:.3f}: arm x[{min(xs):+.3f},{max(xs):+.3f}] y[{min(ys):+.3f},{max(ys):+.3f}]")
if not hulls and not BOX:
    print("!! no limb contours found")
    sys.exit(1)

if BOX:
    bx0, bx1, by0, by1, bz0, bz1 = BOX
    print(f"BOX cut: x[{bx0:+.3f},{bx1:+.3f}] y[{by0:+.3f},{by1:+.3f}] z[{bz0:+.3f},{bz1:+.3f}]")

    EX = CFG.get("exclude")
    if EX:
        ex0, ex1, ey0, ey1, ez0, ez1 = EX
        print(f"  minus x[{ex0:+.3f},{ex1:+.3f}] y[{ey0:+.3f},{ey1:+.3f}] z[{ez0:+.3f},{ez1:+.3f}]")

    def inside(p):
        if not (bx0 <= p.x <= bx1 and by0 <= p.y <= by1 and bz0 <= p.z <= bz1):
            return False
        if EX and ex0 <= p.x <= ex1 and ey0 <= p.y <= ey1 and ez0 <= p.z <= ez1:
            return False
        return True
else:
    zlo = min(h[0] for h in hulls) - CFG["zpad"]
    zhi = max(h[0] for h in hulls) + CFG["zpad"]

    def inside(p):
        if not (zlo <= p.z <= zhi):
            return False
        best = min(hulls, key=lambda h: abs(h[0] - p.z))
        _, x0, x1, y0, y1 = best
        return x0 <= p.x <= x1 and y0 <= p.y <= y1


bm = bmesh.new()
bm.from_mesh(scaf.data)
bm.transform(scaf.matrix_world)
# weld first — glTF splits verts at UV seams, and an unwelded cut is triangle soup (CP8)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
keep = [f for f in bm.faces if inside(f.calc_center_median())]
print(f"\n{len(keep)} of {len(bm.faces)} scaffold faces are inside the {LIMB} envelope")
if not keep:
    print("!! nothing selected")
    sys.exit(1)
kill = [f for f in bm.faces if f not in set(keep)]
bmesh.ops.delete(bm, geom=kill, context="FACES")
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")

name = f"SCAF_{LIMB}"
old = bpy.data.objects.get(name)
if old:
    bpy.data.objects.remove(old, do_unlink=True)
me = bpy.data.meshes.new(name)
bm.to_mesh(me)
bm.free()
ob = bpy.data.objects.new(name, me)
bpy.context.scene.collection.objects.link(ob)
ob.hide_render = True
xs = [v.co.x for v in me.vertices]
zs = [v.co.z for v in me.vertices]
print(f"{name}: {len(me.vertices)} verts, {len(me.polygons)} faces, "
      f"x[{min(xs):+.3f},{max(xs):+.3f}] z[{min(zs):+.3f},{max(zs):+.3f}]")

# ---- optional REMESH into a finished part ---------------------------------------------------------
# The ear's method (CP8), which is the one that works for a protrusion you rebuild WHOLE: weld the
# glTF seam splits, fill the root hole left by the cut, then voxel remesh to all-quads. Quadriflow
# still refuses on this scaffold's manifoldness; the voxel output is already quads so it is not
# chased.
if "--remesh" in argv:
    voxel = float(argv[argv.index("--remesh") + 1]) if len(argv) > argv.index("--remesh") + 1 \
        and not argv[argv.index("--remesh") + 1].startswith("--") else 0.006
    bm2 = bmesh.new()
    bm2.from_mesh(me)
    bmesh.ops.remove_doubles(bm2, verts=bm2.verts, dist=1e-5)
    open_edges = [e for e in bm2.edges if len(e.link_faces) == 1]
    if open_edges:
        # sides=0 means "any size". The default is 4, so holes_fill was SILENTLY SKIPPING every
        # hole bigger than a quad — the body cut's 294 open edges came out as 294 open edges.
        bmesh.ops.holes_fill(bm2, edges=open_edges, sides=0)
        still = sum(1 for e in bm2.edges if len(e.link_faces) == 1)
        print(f"  holes_fill: {len(open_edges)} open edges -> {still}")
    bmesh.ops.recalc_face_normals(bm2, faces=bm2.faces)
    bm2.to_mesh(me)
    bm2.free()
    final = f"clyffy_{LIMB}"
    old2 = bpy.data.objects.get(final)
    if old2:
        bpy.data.objects.remove(old2, do_unlink=True)
    ob.name = final
    ob.data.name = final
    ob.hide_render = False
    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    # THE OPERATOR, NOT THE MODIFIER. Measured on the same mesh at voxel 0.008: the Remesh
    # MODIFIER returned 1018 faces, `bpy.ops.object.voxel_remesh()` returned 31770. The modifier's
    # counts also barely moved with voxel size (1018 / 1264 / 1932 across a 2.3x range), which is
    # octree behaviour — it was never voxel remeshing at all. The ops path scales as 1/voxel^2 as
    # it should, and it is what produced the ear at CP8.
    ob.data.remesh_voxel_size = voxel
    ob.data.remesh_voxel_adaptivity = 0.0
    bpy.ops.object.voxel_remesh()
    nq = sum(1 for f in ob.data.polygons if len(f.vertices) == 4)
    nt = sum(1 for f in ob.data.polygons if len(f.vertices) == 3)
    print(f"{final}: remeshed at voxel {voxel} -> {len(ob.data.polygons)} faces "
          f"({nq} quads, {nt} tris)")

if WRITE:
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print("saved")
else:
    print("(dry run — pass --write)")

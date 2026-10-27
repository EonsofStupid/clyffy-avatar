"""Classify which faces are INTERNAL — geometry sealed inside the mesh, invisible from anywhere.

    blender -b --python tools/find_internal.py -- <in.blend> <out.blend> [region]

A face is internal iff NO ray leaving it escapes to infinity. That is the definition, and it is
computed rather than guessed: rays are fired over the whole sphere from just off each side of
the face, and if even one reaches infinity without hitting geometry, the face is exterior.

WHY THIS EXISTS. The mouth cavity is capped at 0.0737 deep by a surface at x~0.147 behind the
muzzle. Whether that surface is an internal partition (removable, free depth) or the outer skin
(structural, deleting it punches a hole in the character) decides the whole approach. Three
heuristics were tried and all three mixed the two up:

    faces with |normal.x| > 0.55 in the muzzle box   -> grabbed the CHEEKS, 83k-109k px visible
    flood fill from backward rays, 40 deg tolerance  -> walked onto the face, 3010 faces, 1.6M px
    backward rays constrained to the muzzle          -> still 35k px from the front

Each was proven wrong by marking it `inner_` and running `cavity_gate.py` — which is what that
gate is for. This tool replaces the guessing with the actual predicate.

Faces classified internal are written out marked with an `inner_` material so the SAME gate can
verify the classification before anything is deleted. Nothing is deleted here.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hardfail  # noqa: F401  -- unhandled exceptions must exit non-zero
import bpy, bmesh, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = os.path.abspath(argv[0]), os.path.abspath(argv[1])
# region to classify: everything is slow and unnecessary, the question is about the head
ZLO_F, ZHI_F = 0.60, 0.95
NDIR = 64
MATNAME = "inner_internalTEST"

bpy.ops.wm.open_mainfile(filepath=SRC)
ob = max([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
me = ob.data
N = len(me.vertices)
co = np.empty((N, 3)); me.vertices.foreach_get("co", co.ravel())
z = co[:, 2]; zlo, zhi = float(z.min()), float(z.max()); H = zhi - zlo

bm = bmesh.new(); bm.from_mesh(me)
bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table()
bv = [tuple(v.co) for v in bm.verts]
bp = [tuple(v.index for v in f.verts) for f in bm.faces]
BVH = BVHTree.FromPolygons(bv, bp, all_triangles=False)

# Fibonacci sphere: even coverage, deterministic, no RNG (which would break reproducibility)
DIRS = []
ga = math.pi * (3.0 - math.sqrt(5.0))
for i in range(NDIR):
    yy = 1.0 - (i / float(NDIR - 1)) * 2.0
    rad = math.sqrt(max(0.0, 1.0 - yy * yy))
    th = ga * i
    DIRS.append(Vector((math.cos(th) * rad, yy, math.sin(th) * rad)).normalized())

FAR = H * 4.0
cand = []
for f in bm.faces:
    c = f.calc_center_median()
    hf = (c.z - zlo) / H
    if not (ZLO_F < hf < ZHI_F):
        continue
    cand.append(f)
print(f"classifying {len(cand)} faces in the head band "
      f"({ZLO_F*100:.0f}-{ZHI_F*100:.0f}% of body height), {NDIR} directions each")

internal = []
for f in cand:
    c = f.calc_center_median()
    n = f.normal
    escaped = False
    for side in (1.0, -1.0):
        o0 = c + n * (side * 2e-4)
        for d in DIRS:
            if d.dot(n) * side < 0.0:
                continue                      # only the hemisphere on this side
            o = Vector(o0)
            hit = BVH.ray_cast(o, d, FAR)
            if hit[0] is None:
                escaped = True
                break
        if escaped:
            break
    if not escaped:
        internal.append(f.index)

print(f"INTERNAL faces (no escaping ray in any direction): {len(internal)}")
if internal:
    cc = np.array([[bm.faces[i].calc_center_median().x, bm.faces[i].calc_center_median().y,
                    bm.faces[i].calc_center_median().z] for i in internal])
    print(f"  x {cc[:,0].min():+.4f}..{cc[:,0].max():+.4f}")
    print(f"  y {cc[:,1].min():+.4f}..{cc[:,1].max():+.4f}")
    print(f"  z {cc[:,2].min():+.4f}..{cc[:,2].max():+.4f}  "
          f"(h {(cc[:,2].min()-zlo)/H*100:.1f}..{(cc[:,2].max()-zlo)/H*100:.1f}%)")
    print(f"  total area {sum(bm.faces[i].calc_area() for i in internal):.5f}")
bm.free()

mat = bpy.data.materials.new(MATNAME)
me.materials.append(mat)
slot = len(me.materials) - 1
mi = np.empty(len(me.polygons), dtype=np.int32)
me.polygons.foreach_get("material_index", mi)
for i in internal:
    mi[i] = slot
me.polygons.foreach_set("material_index", mi)
me.update()
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"marked {len(internal)} faces as {MATNAME!r} -> {OUT}")
print("NOTHING WAS DELETED. Verify with cavity_gate.py at several azimuths: a correct "
      "classification renders ZERO magenta from every direction.")

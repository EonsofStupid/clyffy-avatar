"""Close the small UNINTENDED holes left where regions meet — never the apertures.

    blender -b --python tools/retopo_fill_gaps.py -- work/RETOPO_clyffy.blend

Region marches leave pinholes where two fronts meet at an angle (the jawline zip left a 10-vert
hole by the mouth corner; the temple wedge left a 7-vert one). They are too small to march into,
so they are filled directly: grid_fill for quads, falling back to a centroid FAN, which is
manifold by construction — chasing "zero holes" with n-gon fills and triangle_fill is what took
non-manifold edges from 1 to 8 in the old project.

PROTECTED, never filled: the eye aperture (the lid margin, the eyeball object goes there), the
nostril slits, and the big outer boundary (the neck ring + the ear/horn opening, which CP8 fills
with real ear and horn objects).
"""
import bpy, bmesh, sys, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
bpy.ops.wm.open_mainfile(filepath=BLEND)
rt = bpy.data.objects["retopo_head"]
scaf = bpy.data.objects["SCAFFOLD"]
bpy.context.view_layer.objects.active = rt
if rt.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")

# apertures that must stay open, by centre
PROTECT = [(Vector((0.047, -0.135, 0.857)), 0.045),    # eye lid margin
           (Vector((0.0356, -0.2677, 0.7844)), 0.030)]  # nostril
MAX_LOOP = 16                                           # bigger than this is a real region

bm = bmesh.new(); bm.from_mesh(rt.data)
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
bnd = [e for e in bm.edges if e.link_faces and len(e.link_faces) == 1]
adj = {}
for e in bnd:
    a, b = e.verts
    adj.setdefault(a, []).append(b)
    adj.setdefault(b, []).append(a)
seen, comps = set(), []
for v in adj:
    if v in seen:
        continue
    stack, c = [v], []
    seen.add(v)
    while stack:
        k = stack.pop(); c.append(k)
        for o in adj[k]:
            if o not in seen:
                seen.add(o); stack.append(o)
    comps.append(c)

filled = 0
for c in sorted(comps, key=len):
    ctr = sum((v.co for v in c), Vector()) / len(c)
    if len(c) > MAX_LOOP:
        print(f"  skip {len(c)}v loop (outer boundary / region edge)")
        continue
    prot = next((p for p, r in PROTECT if (ctr - p).length < r), None)
    if prot is not None:
        print(f"  PROTECTED {len(c)}v aperture at ({ctr.x:+.3f},{ctr.y:+.3f},{ctr.z:.3f})")
        continue
    loop_edges = [e for e in bnd if e.verts[0] in c and e.verts[1] in c]
    before = len(bm.faces)
    try:
        bmesh.ops.grid_fill(bm, edges=loop_edges, use_interp_simple=False)
    except Exception:
        pass
    if len(bm.faces) == before:
        # centroid fan — manifold by construction
        cv = bm.verts.new(ctr)
        ordered, prev = [c[0]], None
        while True:
            nx = [o for o in adj[ordered[-1]] if o is not prev and o not in ordered]
            if not nx:
                break
            prev = ordered[-1]
            ordered.append(nx[0])
        for i in range(len(ordered)):
            try:
                bm.faces.new((ordered[i], ordered[(i + 1) % len(ordered)], cv))
            except ValueError:
                pass
        print(f"  filled {len(c)}v hole at ({ctr.x:+.3f},{ctr.y:+.3f},{ctr.z:.3f}) with a fan")
    else:
        print(f"  filled {len(c)}v hole at ({ctr.x:+.3f},{ctr.y:+.3f},{ctr.z:.3f}) "
              f"with {len(bm.faces) - before} grid faces")
    filled += 1

bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(rt.data)
bm.free()
nq = sum(1 for p in rt.data.polygons if len(p.vertices) == 4)
nt = sum(1 for p in rt.data.polygons if len(p.vertices) == 3)
print(f"filled {filled} holes -> {len(rt.data.polygons)} faces ({nq} quads, {nt} tris)")
bpy.ops.wm.save_as_mainfile(filepath=BLEND)

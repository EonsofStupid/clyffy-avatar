"""Close every remaining hole in the mesh. Adds faces; deletes nothing.

    blender -b --python tools/seal_head.py -- <in.blend> <out.blend>

WHY THIS EXISTS, and why "cosmetic" was wrong. `cleanup.py` left 3 boundary edges and called
them "a handful of open edges at a horn tip … cosmetic", because its gate only asked whether
any hole lay near the MOUTH. Two things were wrong with that:

  * they are not at a horn tip. They sit at x~0.120 y~0.026 z~0.323 — 82.8% of body height,
    beside the right eye, which is also exactly where the two debris shells are.
  * they are not cosmetic. With the jaw open, `jaw_test.py`'s see-through gate found background
    visible THROUGH the head at that spot, and a ray cast through the offending pixel landed
    there. You could see daylight through him.

Nothing revealed it earlier because no gate had ever asked "can light pass through this mesh".
That is the recurring shape of every real defect in this project: not a wrong number, but an
unasked question.

FILLED WITH A CENTROID FAN, which is manifold by construction. Filling each loop with a single
n-gon took non-manifold edges from 1 to 8 on this mesh, and `triangle_fill` took it 1 to 5;
both are recorded as REJECTED in BUILD_LOG. A fan from a new centre vertex cannot self-overlap.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hardfail  # noqa: F401
import bpy, bmesh
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = os.path.abspath(argv[0]), os.path.abspath(argv[1])
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=SRC)
if bpy.context.object and bpy.context.object.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")
ob = max([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
me = ob.data
N0, F0 = len(me.vertices), len(me.polygons)
co = np.empty((N0, 3)); me.vertices.foreach_get("co", co.ravel())
z = co[:, 2]; zlo, zhi = float(z.min()), float(z.max()); H = zhi - zlo

bm = bmesh.new(); bm.from_mesh(me)
bm.verts.ensure_lookup_table()

# DROP THE DEBRIS SHELLS FIRST. Two generator leftovers — 12 and 9 verts, ~0.001 across, buried
# beside the right eye — sit exactly where the see-through leak is, and while they are plugging
# part of a crack they also prevent it from registering as a boundary loop that can be filled.
# They were PROVEN invisible before removal: marked with an `inner_` material and run through
# cavity_gate.py at all four quadrants -> 0 magenta everywhere. The teeth bands (164, 164) and
# the tongue (86) are separate shells too, which is why the threshold is well below them.
seen, comps = set(), []
for v in bm.verts:
    if v.index in seen:
        continue
    st, c = [v], []
    seen.add(v.index)
    while st:
        cur = st.pop(); c.append(cur)
        for e in cur.link_edges:
            o = e.other_vert(cur)
            if o.index not in seen:
                seen.add(o.index); st.append(o)
    comps.append(c)
comps.sort(key=len, reverse=True)
print(f"shells: {[len(c) for c in comps]}")
debris = [v for c in comps[1:] if len(c) <= 40 for v in c]
if debris:
    print(f"  dropping {len(debris)} vertices of debris shells (proven invisible)")
    bmesh.ops.delete(bm, geom=debris, context="VERTS")
    bm.verts.ensure_lookup_table()

b0 = [e for e in bm.edges if len(e.link_faces) == 1]
nm0 = sum(1 for e in bm.edges if len(e.link_faces) > 2)
print(f"before: {len(b0)} boundary edges, {nm0} non-manifold")
for e in b0:
    c = (e.verts[0].co + e.verts[1].co) / 2
    print(f"  open edge at x {c.x:+.4f} y {c.y:+.4f} z {c.z:+.4f}  "
          f"(h {(c.z-zlo)/H*100:.1f}%)  len {e.calc_length():.5f}")

made = failed = 0
for _ in range(6):
    bnd = [e for e in bm.edges if len(e.link_faces) == 1]
    if not bnd:
        break
    adj = {}
    for e in bnd:
        i, j = e.verts[0], e.verts[1]
        adj.setdefault(i, []).append(j)
        adj.setdefault(j, []).append(i)
    seen, loops = set(), []
    for s in adj:
        if s in seen:
            continue
        loop, prev, cur = [s], None, s
        seen.add(s)
        while True:
            nxt = [x for x in adj[cur] if x is not prev and x not in seen]
            if not nxt:
                break
            cur = nxt[0]
            seen.add(cur); loop.append(cur)
            prev = loop[-2] if len(loop) > 1 else None
        loops.append(loop)
    progressed = False
    for loop in loops:
        if len(loop) < 3:
            continue
        try:
            cen = bm.verts.new(sum((v.co for v in loop), Vector((0, 0, 0))) / len(loop))
            bm.verts.ensure_lookup_table()
            n = len(loop)
            for k in range(n):
                bm.faces.new((loop[k], loop[(k + 1) % n], cen))
            made += 1
            progressed = True
        except Exception:
            failed += 1
    if not progressed:
        break

bm.to_mesh(me); bm.free(); me.update()

bm = bmesh.new(); bm.from_mesh(me)
b1 = sum(1 for e in bm.edges if len(e.link_faces) == 1)
nm1 = sum(1 for e in bm.edges if len(e.link_faces) > 2)
lo1 = sum(1 for v in bm.verts if not v.link_faces)
bm.free()
N1, F1 = len(me.vertices), len(me.polygons)
print(f"\nfilled {made} loop(s), {failed} refused")
print(f"gate:")
print(f"  verts {N0} -> {N1}   faces {F0} -> {F1}")
print(f"  boundary edges {len(b0)} -> {b1}")
print(f"  non-manifold   {nm0} -> {nm1}")
print(f"  loose verts    {lo1}")
assert b1 == 0, f"{b1} boundary edges remain — the mesh is still open"
assert nm1 <= nm0, f"non-manifold INCREASED {nm0} -> {nm1}: the fill overlapped faces"
assert lo1 == 0, f"{lo1} loose vertices"
print("  OK: closed, and non-manifold did not increase")

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"wrote {OUT}")

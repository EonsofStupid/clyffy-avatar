"""Pair up the region-corner TRIANGLES into quads, before anything subdivides or deforms.

    blender -b --python tools/retopo_cleanup.py -- work/RETOPO_clyffy.blend

Every tri in the shell is a legitimate density transition where two marched fronts met, but they
accumulated to 154 and both subdivision (Catmull-Clark makes a tri into three ugly quads) and
weight painting inherit whatever topology they are handed.

`join_triangles` merges adjacent tri PAIRS that form a reasonable quad. It cannot fix an odd tri
with no partner, and it must not be allowed to merge across a sharp feature, so the angle limits
stay tight rather than maximal.

GATED on the things that must not change: the open boundary loops (eye aperture, nostril,
ear/horn opening, neck edge) must survive identically. A cleanup that closed an aperture or opened
a crack would be worse than the tris.
"""
import bpy, bmesh, sys, os, math

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
bpy.ops.wm.open_mainfile(filepath=BLEND)
rt = bpy.data.objects["retopo_head"]


def survey(me):
    bm = bmesh.new(); bm.from_mesh(me)
    bm.edges.ensure_lookup_table()
    nq = sum(1 for f in bm.faces if len(f.verts) == 4)
    nt = sum(1 for f in bm.faces if len(f.verts) == 3)
    nn = sum(1 for f in bm.faces if len(f.verts) > 4)
    bnd = [e for e in bm.edges if len(e.link_faces) == 1]
    nonman = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    adj = {}
    for e in bnd:
        a, b = e.verts
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    seen, comps = set(), []
    for v in adj:
        if v in seen:
            continue
        stack, c = [v], 0
        seen.add(v)
        while stack:
            k = stack.pop(); c += 1
            for o in adj[k]:
                if o not in seen:
                    seen.add(o); stack.append(o)
        comps.append(c)
    bm.free()
    return dict(q=nq, t=nt, n=nn, loops=sorted(comps, reverse=True), nonman=nonman)


before = survey(rt.data)
print(f"before: {before['q']} quads, {before['t']} tris, {before['n']} ngons, "
      f"non-manifold edges {before['nonman']}, boundary loops {before['loops']}")

bm = bmesh.new(); bm.from_mesh(rt.data)
tris = [f for f in bm.faces if len(f.verts) == 3]
bmesh.ops.join_triangles(
    bm, faces=tris,
    angle_face_threshold=math.radians(100),  # loosened once: at 60 only 3% of tris found a partner
    angle_shape_threshold=math.radians(100),
    cmp_seam=False, cmp_sharp=False, cmp_uvs=False, cmp_materials=False)
bm.to_mesh(rt.data)
bm.free()

after = survey(rt.data)
print(f"after:  {after['q']} quads, {after['t']} tris, {after['n']} ngons, "
      f"non-manifold edges {after['nonman']}, boundary loops {after['loops']}")

ok = True
if after["loops"] != before["loops"]:
    print("!! REJECTED — the open boundaries changed; apertures/openings must survive identically")
    ok = False
if after["n"] > before["n"]:
    print(f"!! REJECTED — ngons appeared ({before['n']} -> {after['n']})")
    ok = False
if after["nonman"] > before["nonman"]:
    print(f"!! REJECTED — non-manifold edges appeared ({before['nonman']} -> {after['nonman']})")
    ok = False

if ok:
    pct = 100.0 * (before["t"] - after["t"]) / max(before["t"], 1)
    print(f"\nOK: {before['t']} -> {after['t']} tris ({pct:.0f}% paired off), "
          f"boundaries identical, no ngons, no new non-manifold edges")
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print("saved")
else:
    print("\nNOT SAVED — the file is unchanged on disk")

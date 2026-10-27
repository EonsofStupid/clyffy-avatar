"""Fixture: fabricate a selection so seam_bake.py's validator can be tested both ways.

    blender -b --python tools/_seam_fixture.py -- <in.blend> <out.blend> <fwd_deg> <branchy|path>

Underscore-prefixed: a test fixture, not a pipeline stage, and NOT a proposed seam.

  branchy  the raw crease component at the lip, junctions and all -> seam_bake must REFUSE
  path     a simple walk along connected edges, degree 2 throughout -> seam_bake must ACCEPT

The accept case matters as much as the refuse case. A validator that rejects everything wastes
the operator's time in exactly the way one that accepts everything wastes the build's.
"""
import bpy, bmesh, sys, os, math
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = os.path.abspath(argv[0]), os.path.abspath(argv[1])
FWD_DEG, MODE = float(argv[2]), argv[3]
assert MODE in ("branchy", "path"), MODE

bpy.ops.wm.open_mainfile(filepath=SRC)
ob = max([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
me = ob.data
N = len(me.vertices)
co = np.empty((N, 3)); me.vertices.foreach_get("co", co.ravel())
z = co[:, 2]; zlo, zhi = float(z.min()), float(z.max()); H = zhi - zlo
hm = z > zlo + 0.70 * H
hc = co[hm].mean(axis=0)
a = math.radians(FWD_DEG)
fwd = np.array([math.sin(a), -math.cos(a), 0.0])
lat = np.array([-fwd[1], fwd[0], 0.0])
proj = (co - hc) @ fwd
latc = (co - hc) @ lat

bm = bmesh.new(); bm.from_mesh(me)
crease = []
adj = {}
for e in bm.edges:
    if len(e.link_faces) != 2:
        continue
    i, j = e.verts[0].index, e.verts[1].index
    if not (hm[i] and hm[j]) or proj[i] <= 0 or proj[j] <= 0:
        continue
    n1, n2 = e.link_faces[0].normal, e.link_faces[1].normal
    if n1.length == 0 or n2.length == 0 or math.degrees(n1.angle(n2)) < 25.0:
        continue
    crease.append((i, j))
    adj.setdefault(i, set()).add(j)
    adj.setdefault(j, set()).add(i)

if MODE == "branchy":
    # the widest midline-straddling crease component: known to have 39 junctions
    seen, comps = set(), []
    for s in adj:
        if s in seen:
            continue
        st, c = [s], []
        seen.add(s)
        while st:
            v = st.pop(); c.append(v)
            for n in adj[v]:
                if n not in seen:
                    seen.add(n); st.append(n)
        comps.append(c)
    best, bw = None, -1
    for c in comps:
        L = latc[c]
        if L.min() > -0.01 or L.max() < 0.01:
            continue
        if L.max() - L.min() > bw:
            best, bw = c, L.max() - L.min()
    keep = set(best)
    sel = [(i, j) for i, j in crease if i in keep and j in keep]
else:
    # a simple walk: start at a crease vertex, always step to an unvisited neighbour
    start = min(adj, key=lambda v: abs(latc[v]))
    walk, visited, cur = [start], {start}, start
    while len(walk) < 40:
        nxt = [n for n in adj[cur] if n not in visited]
        if not nxt:
            break
        cur = nxt[0]
        visited.add(cur); walk.append(cur)
    sel = [(walk[k], walk[k + 1]) for k in range(len(walk) - 1)]

bm.free()

selset = {tuple(sorted(e)) for e in sel}
for v in me.vertices:
    v.select = False
for p in me.polygons:
    p.select = False
ev = np.empty(len(me.edges) * 2, dtype=np.int32); me.edges.foreach_get("vertices", ev)
ev = ev.reshape(-1, 2)
n = 0
for k, (i, j) in enumerate(ev):
    on = tuple(sorted((int(i), int(j)))) in selset
    me.edges[k].select = on
    if on:
        me.vertices[int(i)].select = True
        me.vertices[int(j)].select = True
        n += 1
print(f"fixture {MODE}: selected {n} edges")
print(f"expected seam_bake result: {'REFUSE' if MODE == 'branchy' else 'ACCEPT'}")
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"wrote {OUT}")

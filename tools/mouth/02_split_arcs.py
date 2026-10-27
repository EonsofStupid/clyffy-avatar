import bmesh
from mathutils import Vector
clutter()
o = obj(); bm = bmesh.new(); bm.from_mesh(o.data)
MOUTH = lambda co: co.y < -0.10 and co.z < 0.78
chain = [e for e in bm.edges if len(e.link_faces) == 0 and all(MOUTH(v.co) for v in e.verts)]
bnd = [e for e in bm.edges if len(e.link_faces) == 1 and all(MOUTH(v.co) for v in e.verts)]
chain_v = {v for e in chain for v in e.verts}
bnd_v = {v for e in bnd for v in e.verts}
anchors = sorted(chain_v & bnd_v, key=lambda v: v.co.x)
out.append("chain %d, boundary %d, anchors %d" % (len(chain), len(bnd), len(anchors)))
aL, aR = anchors[0], anchors[-1]
adj = {}
for e in bnd:
    for v in e.verts: adj.setdefault(v, []).append(e)
def arc(first):
    seq = [first]; v = first.other_vert(aL)
    while v is not aR:
        nxt = [x for x in adj[v] if x is not seq[-1]]
        if not nxt: break
        seq.append(nxt[0]); v = nxt[0].other_vert(v)
    return seq
a0, a1 = arc(adj[aL][0]), arc(adj[aL][1])
def mz(a): return sum(v.co.z for e in a for v in e.verts) / (2 * len(a))
upper, lower = (a0, a1) if mz(a0) > mz(a1) else (a1, a0)
out.append("upper arc %d (z %.4f), lower arc %d (z %.4f), chain %d" %
           (len(upper), mz(upper), len(lower), mz(lower), len(chain)))
# parity: both loops must be even for fill_grid
if (len(upper) + len(chain)) % 2:
    bmesh.ops.subdivide_edges(bm, edges=[max(upper, key=lambda e: e.calc_length())], cuts=1)
    out.append("subdivided an upper-arc edge for parity")
if (len(lower) + len(chain)) % 2:
    bmesh.ops.subdivide_edges(bm, edges=[max(lower, key=lambda e: e.calc_length())], cuts=1)
    out.append("subdivided a lower-arc edge for parity")
bm.to_mesh(o.data); o.data.update()
# recompute keys after any subdivision
bm.free()
bm = bmesh.new(); bm.from_mesh(o.data)
chain = [e for e in bm.edges if len(e.link_faces) == 0 and all(MOUTH(v.co) for v in e.verts)]
bnd = [e for e in bm.edges if len(e.link_faces) == 1 and all(MOUTH(v.co) for v in e.verts)]
chain_v = {v for e in chain for v in e.verts}; bnd_v = {v for e in bnd for v in e.verts}
anchors = sorted(chain_v & bnd_v, key=lambda v: v.co.x)
aL, aR = anchors[0], anchors[-1]
adj = {}
for e in bnd:
    for v in e.verts: adj.setdefault(v, []).append(e)
a0, a1 = arc(adj[aL][0]), arc(adj[aL][1])
upper, lower = (a0, a1) if mz(a0) > mz(a1) else (a1, a0)
def key(e):
    m = (e.verts[0].co + e.verts[1].co) / 2
    return (round(m.x, 5), round(m.y, 5), round(m.z, 5))
globals()["UPKEYS"] = set(key(e) for e in upper) | set(key(e) for e in chain)
globals()["LOKEYS"] = set(key(e) for e in lower) | set(key(e) for e in chain)
out.append("upper loop %d (even=%s) / lower loop %d (even=%s)" %
           (len(upper) + len(chain), (len(upper) + len(chain)) % 2 == 0,
            len(lower) + len(chain), (len(lower) + len(chain)) % 2 == 0))
bm.free()
result = stat()

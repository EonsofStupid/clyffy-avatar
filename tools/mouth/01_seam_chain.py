import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
unsel()
o = obj(); bm = bmesh.new(); bm.from_mesh(o.data)
MOUTH = lambda co: co.y < -0.10 and co.z < 0.78
def bgroups():
    be = [e for e in bm.edges if len(e.link_faces) == 1 and all(MOUTH(v.co) for v in e.verts)]
    adj = {}
    for e in be:
        for v in e.verts: adj.setdefault(v, []).append(e)
    seen = set(); gs = []
    for e in be:
        if e in seen: continue
        st = [e]; g = []; seen.add(e)
        while st:
            x = st.pop(); g.append(x)
            for v in x.verts:
                for y in adj[v]:
                    if y not in seen: seen.add(y); st.append(y)
        gs.append(g)
    gs.sort(key=len, reverse=True)
    return gs
gs = bgroups()
for g in gs[1:]:
    bmesh.ops.holes_fill(bm, edges=g, sides=0)
out.append("corner slits filled: %d" % (len(gs) - 1))
main = bgroups()[0]
mv = list({v for e in main for v in e.verts})

# scaffold, for planting the seam chain on the real skin
sc = bpy.data.objects["SCAFFOLD"]
bS = bmesh.new(); bS.from_mesh(sc.data); bS.transform(sc.matrix_world)
SBVH = BVHTree.FromBMesh(bS); bS.free()
globals()["SBVH"] = SBVH

cR = Vector(SEAM[-1]); cL = Vector((-SEAM[-1][0], SEAM[-1][1], SEAM[-1][2]))
aR = min(mv, key=lambda v: (v.co - cR).length)
aL = min(mv, key=lambda v: (v.co - cL).length)

# the seam, left corner -> front -> right corner, resampled at even arc length
def densify(pts, n=10):
    r = []
    for i in range(len(pts) - 1):
        a, b = Vector(pts[i]), Vector(pts[i + 1])
        for k in range(n): r.append(a.lerp(b, k / n))
    r.append(Vector(pts[-1])); return r
right = densify(SEAM, 10)
left = [Vector((-p.x, p.y, p.z)) for p in right]
curve = [aL.co.copy()] + list(reversed(left)) + right[1:] + [aR.co.copy()]
# resample
acc = [0.0]
for i in range(1, len(curve)): acc.append(acc[-1] + (curve[i] - curve[i - 1]).length)
L = acc[-1]
N = 30                                   # segments -> even count keeps fill_grid happy
def at(s):
    for i in range(1, len(acc)):
        if acc[i] >= s:
            t = (s - acc[i - 1]) / max(acc[i] - acc[i - 1], 1e-9)
            return curve[i - 1].lerp(curve[i], t)
    return curve[-1]
pts = [at(L * k / N) for k in range(N + 1)]
out.append("seam chain: length %.4f, %d segments, spacing %.4f" % (L, N, L / N))

chain_v = [aL]
for p in pts[1:-1]:
    loc, nor, idx, d = SBVH.find_nearest(p)
    chain_v.append(bm.verts.new(loc if (loc is not None and d < 0.03) else p))
chain_v.append(aR)
chain_e = [bm.edges.new((chain_v[i], chain_v[i + 1])) for i in range(len(chain_v) - 1)]
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
out.append("chain verts %d, chain edges %d" % (len(chain_v), len(chain_e)))

# split the aperture loop into the two arcs between aL and aR
adj = {}
for e in main:
    for v in e.verts: adj.setdefault(v, []).append(e)
def walk(start, first_edge):
    seq = [first_edge]; v = first_edge.other_vert(start)
    while v is not aR and v is not aL or len(seq) == 1:
        nxt = [x for x in adj[v] if x not in seq]
        if not nxt: break
        e = nxt[0]; seq.append(e); v = e.other_vert(v)
        if v is aR or v is aL: break
    return seq
e0, e1 = adj[aL][0], adj[aL][1]
arcA = walk(aL, e0); arcB = walk(aL, e1)
def arcz(a): return sum((v.co.z for e in a for v in e.verts)) / (2 * len(a))
upper, lower = (arcA, arcB) if arcz(arcA) > arcz(arcB) else (arcB, arcA)
out.append("aperture arcs: upper %d edges (mean z %.4f), lower %d edges (mean z %.4f)" %
           (len(upper), arcz(upper), len(lower), arcz(lower)))
globals()["KEEP"] = {"chain": [v.index for v in chain_v],
                     "upper": [e.index for e in upper], "lower": [e.index for e in lower]}
bm.to_mesh(o.data); o.data.update(); bm.free()
say("seam chain laid across the aperture; two halves to fill")
result = {"stat": stat(), "chain_len": len(chain_e),
          "upper_edges": len(upper), "lower_edges": len(lower),
          "upper_total": len(upper) + len(chain_e), "lower_total": len(lower) + len(chain_e)}

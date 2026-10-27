import bmesh
from mathutils import Vector
unsel()
o = obj(); bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()

def densify(pts, n=10):
    r = []
    for i in range(len(pts) - 1):
        a, b = Vector(pts[i]), Vector(pts[i + 1])
        for k in range(n): r.append(a.lerp(b, k / n))
    r.append(Vector(pts[-1])); return r
R = densify(SEAM, 10); L = [Vector((-p.x, p.y, p.z)) for p in R]
CURVE = list(reversed(L)) + R[1:]
acc = [0.0]
for i in range(1, len(CURVE)): acc.append(acc[-1] + (CURVE[i] - CURVE[i - 1]).length)
def proj(p):
    best = None; bd = 1e9; bs = 0.0
    for i in range(len(CURVE) - 1):
        a, b = CURVE[i], CURVE[i + 1]; ab = b - a
        t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
        q = a + ab * t; d = (p - q).length
        if d < bd: bd, best, bs = d, q, acc[i] + ab.length * t
    return best, bd, bs
def at(s):
    for i in range(1, len(acc)):
        if acc[i] >= s:
            t = (s - acc[i - 1]) / max(acc[i] - acc[i - 1], 1e-9)
            return CURVE[i - 1].lerp(CURVE[i], t)
    return CURVE[-1]

CHAIN = [v for v in bm.verts if 15132 <= v.index <= 15160]
info = sorted(((proj(v.co)[2], v) for v in CHAIN), key=lambda x: x[0])
ss = [s for s, _ in info]; vs = [v for _, v in info]
for _ in range(6):                                    # even out the spacing along the lip
    ns = ss[:]
    for i in range(1, len(ss) - 1):
        ns[i] = 0.5 * ss[i] + 0.25 * (ss[i - 1] + ss[i + 1])
    ss = ns
d0 = sum(proj(v.co)[1] for v in vs) / len(vs)
for s, v in zip(ss, vs):
    v.co = at(s)
out.append("lip line: %d verts, mean offset from the approved curve %.4f -> 0.0000, evenly spaced"
           % (len(vs), d0))

# relax the two grids around the lip, lip pinned
cset = set(CHAIN)
band = {}
cur = [u for v in CHAIN for e in v.link_edges for u in [e.other_vert(v)] if u not in cset]
for v in cur: band[v] = 1
for k in range(2, 5):
    nxt = []
    for v in cur:
        for e in v.link_edges:
            u = e.other_vert(v)
            if u not in cset and u not in band: band[u] = k; nxt.append(u)
    cur = nxt
for it in range(14):
    upd = {v: sum((e.other_vert(v).co for e in v.link_edges), Vector()) / len(v.link_edges)
           for v in band if v.link_edges}
    for v, t in upd.items(): v.co = v.co.lerp(t, 0.32 / band[v])

# --- open the mouth: split the shared lip line, then build the cavity behind it -----
chain_edges = []
for v in CHAIN:
    for e in v.link_edges:
        if e.other_vert(v) in cset and e not in chain_edges:
            chain_edges.append(e)
# include the two anchor edges so the split reaches the mouth corners
out.append("lip edges to split: %d" % len(chain_edges))
bmesh.ops.split_edges(bm, edges=chain_edges)
def ec(e): return (e.verts[0].co + e.verts[1].co) / 2
ring = [e for e in bm.edges if len(e.link_faces) == 1 and
        ec(e).y < -0.15 and 0.66 < ec(e).z < 0.78]
out.append("slit boundary after split: %d edges" % len(ring))
AXIS = Vector((0.0, -0.155, 0.7180))
for i, (back, shrink) in enumerate([(0.016, 0.90), (0.020, 0.72), (0.018, 0.45)]):
    ret = bmesh.ops.extrude_edge_only(bm, edges=ring)
    nvv = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    ne = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMEdge) and all(x in nvv for x in g.verts)]
    for v in nvv:
        p = v.co + Vector((0, back, 0))
        v.co = AXIS + (p - AXIS) * shrink
    ring = ne
if ring: bmesh.ops.holes_fill(bm, edges=ring, sides=0)
ng = [f for f in bm.faces if len(f.verts) > 4]
if ng: bmesh.ops.triangulate(bm, faces=ng)
bmesh.ops.dissolve_degenerate(bm, dist=2e-4, edges=bm.edges[:])
holes = [e for e in bm.edges if len(e.link_faces) == 1 and
         all(v.co.y < -0.14 and 0.66 < v.co.z < 0.78 for v in e.verts)]
if holes: bmesh.ops.holes_fill(bm, edges=holes, sides=0)
ng = [f for f in bm.faces if len(f.verts) > 4]
if ng: bmesh.ops.triangulate(bm, faces=ng)
wire = [e for e in bm.edges if len(e.link_faces) == 0]
if wire: bmesh.ops.delete(bm, geom=wire, context="EDGES")
over = [e for e in bm.edges if len(e.link_faces) > 2]
if over:
    fs = list({f for e in over for f in e.link_faces})
    bmesh.ops.delete(bm, geom=fs, context="FACES_ONLY")
    h2 = [e for e in bm.edges if len(e.link_faces) == 1 and
          all(v.co.y < -0.14 and 0.66 < v.co.z < 0.78 for v in e.verts)]
    if h2: bmesh.ops.holes_fill(bm, edges=h2, sides=0)
    ng = [f for f in bm.faces if len(f.verts) > 4]
    if ng: bmesh.ops.triangulate(bm, faces=ng)
out.append("cleanup: wire %d, over-linked %d" % (len(wire), len(over)))
bm.to_mesh(o.data); o.data.update(); bm.free()
say("mouth open: lip split on the approved line, cavity behind it")
result = {"stat": stat(), "gate": gate()}

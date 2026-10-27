import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
unsel()
sc = bpy.data.objects["SCAFFOLD"]
bS = bmesh.new(); bS.from_mesh(sc.data); bS.transform(sc.matrix_world)
BVH = BVHTree.FromBMesh(bS); bS.free()
def near(co):
    loc, nor, idx, d = BVH.find_nearest(co)
    return (loc.copy(), d) if loc is not None else (co.copy(), 0.0)
globals()["BVH"] = BVH; globals()["near"] = near

o = obj(); bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
CHAIN = [v for v in bm.verts if 15132 <= v.index <= 15160]
PATCH = [v for v in bm.verts if v.index >= 15161]
out.append("chain verts %d (z %.4f..%.4f), patch verts %d" %
           (len(CHAIN), min(v.co.z for v in CHAIN), max(v.co.z for v in CHAIN), len(PATCH)))
pset, cset = set(PATCH), set(CHAIN)
worst0 = 0.0
for v in PATCH:
    p, d = near(v.co); worst0 = max(worst0, d); v.co = p
out.append("patch planted; worst pre-plant offset %.4f" % worst0)
depth = {}
cur = [v for v in PATCH if any(e.other_vert(v) not in pset for e in v.link_edges)]
for v in cur: depth[v] = 1
d = 1
while cur:
    d += 1; nxt = []
    for v in cur:
        for e in v.link_edges:
            u = e.other_vert(v)
            if u in pset and u not in depth: depth[u] = d; nxt.append(u)
    cur = nxt
maxd = max(depth.values())
skirt = {}
cur = [v for v in bm.verts if v not in pset and v not in cset and
       any(e.other_vert(v) in pset for e in v.link_edges)]
for v in cur: skirt[v] = 1
for k in range(2, 5):
    nxt = []
    for v in cur:
        for e in v.link_edges:
            u = e.other_vert(v)
            if u not in pset and u not in cset and u not in skirt:
                skirt[u] = k; nxt.append(u)
    cur = nxt
def ss(t):
    t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)
WGT = {v: ss((depth[v] - 1) / max(1.0, maxd - 2.0)) for v in PATCH}
clamped = 0
for it in range(35):
    upd = {}
    for v in list(PATCH) + list(skirt):
        nb = [e.other_vert(v) for e in v.link_edges]
        upd[v] = sum((n.co for n in nb), Vector()) / len(nb)
    for v, t in upd.items():
        if v in pset:
            p = v.co.lerp(t, 0.6)
            q, dd = near(p); p = p.lerp(q, WGT[v])
            q2, dd2 = near(p)
            if dd2 > 0.020: p = q2; clamped += 1
            v.co = p
        else:
            v.co = v.co.lerp(t, 0.35 / skirt[v])
out.append("clamped %d times; the lip chain never moved" % clamped)
bm.to_mesh(o.data); o.data.update(); bm.free()
say("two-piece muzzle: upper lip and lower jaw filled as separate grids sharing the lip line")
off = off_surface(tol=0.020, where=lambda p: p.z > 0.62 and p.y < -0.10)
result = {"stat": stat(), "gate": gate(), "off_scaffold": len(off),
          "shots": [shot("s1_front", at=(0,-0.22,0.74), dist=0.30, yaw=0, pitch=-6),
                    shot("s1_mouth", at=(0,-0.235,0.716), dist=0.13, yaw=0, pitch=-6),
                    shot("s1_wire", at=(0,-0.235,0.716), dist=0.13, yaw=0, pitch=-6, wire=True),
                    shot("s1_side", at=(0,-0.22,0.715), dist=0.20, yaw=80, pitch=-4)]}

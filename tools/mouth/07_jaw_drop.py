import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
unsel(); snap("I_pre_jaw")
o = obj(); bm = bmesh.new(); bm.from_mesh(o.data)
def dl(p):
    best = 1e9
    for i in range(len(CURVE) - 1):
        a, b = CURVE[i], CURVE[i + 1]; ab = b - a
        t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
        best = min(best, (p - (a + ab * t)).length)
    return best
def ss(t):
    t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)
sel_v = [v for v in bm.verts if tuple(round(c, 6) for c in v.co) in UNDER]
moved = 0; tot = 0.0; mx = 0.0
for v in sel_v:
    hit = S.ray_cast(v.co + Vector((0, 0, 0.02)), Vector((0, 0, -1)), 0.20)
    if hit[0] is None: continue
    drop = min(v.co.z - hit[0].z, 0.030)
    if drop <= 0.0005: continue
    w = ss(dl(v.co) / 0.022)                    # the lip line itself does not move
    v.co = v.co - Vector((0, 0, drop * w))
    moved += 1; tot += drop * w; mx = max(mx, drop * w)
out.append("jaw underside dropped onto the scaffold: %d verts, mean %.4f, max %.4f"
           % (moved, tot / max(moved, 1), mx))
svs = set(sel_v)
band = {}
cur = [u for v in sel_v for e in v.link_edges for u in [e.other_vert(v)] if u not in svs]
for v in cur: band[v] = 1
for k in range(2, 4):
    nxt = []
    for v in cur:
        for e in v.link_edges:
            u = e.other_vert(v)
            if u not in svs and u not in band: band[u] = k; nxt.append(u)
    cur = nxt
movers = [v for v in sel_v if dl(v.co) > 0.006] + list(band)
for it in range(10):
    upd = {v: sum((e.other_vert(v).co for e in v.link_edges), Vector()) / len(v.link_edges)
           for v in movers if v.link_edges}
    for v, t in upd.items():
        f = 0.35 if v in svs else 0.30 / band[v]
        v.co = v.co.lerp(t, f)
bm.to_mesh(o.data); o.data.update(); bm.free()
say("chin dropped onto the scaffold's own jaw line; lip line pinned")
result = {"stat": stat(), "gate": gate(),
          "shots": [shot("z2_side", at=(0,-0.22,0.712), dist=0.20, yaw=80, pitch=-4),
                    shot("z2_front", at=(0,-0.20,0.80), dist=0.42, yaw=0, pitch=-4),
                    shot("z2_mouth", at=(0,-0.235,0.716), dist=0.13, yaw=0, pitch=-6),
                    shot("z2_low", at=(0,-0.23,0.706), dist=0.17, yaw=0, pitch=-35)]}

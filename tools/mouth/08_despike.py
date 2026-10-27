import bmesh
from mathutils import Vector
unsel(); snap("J_pre_despike")
o = obj(); bm = bmesh.new(); bm.from_mesh(o.data)
W = lambda co: co.y < -0.15 and 0.64 < co.z < 0.78 and abs(co.x) < 0.11
def dl(p):
    best = 1e9
    for i in range(len(CURVE) - 1):
        a, b = CURVE[i], CURVE[i + 1]; ab = b - a
        t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
        best = min(best, (p - (a + ab * t)).length)
    return best
fixed = 0; worst_before = 0.0
for rounds in range(6):
    hits = []
    for v in bm.verts:
        if not W(v.co) or dl(v.co) < 0.004: continue
        nb = [e.other_vert(v) for e in v.link_edges]
        if len(nb) < 3: continue
        mid = sum((n.co for n in nb), Vector()) / len(nb)
        d = (v.co - mid).length
        if d > 0.012: hits.append((d, v, mid))
    if not hits: break
    worst_before = max(worst_before, max(h[0] for h in hits))
    for d, v, mid in hits:
        v.co = v.co.lerp(mid, 0.75); fixed += 1
out.append("spikes over 0.012 pulled back in: %d moves, worst was %.4f" % (fixed, worst_before))
bm.to_mesh(o.data); o.data.update(); bm.free()
say("spikes around the mouth pulled back onto the surface")
result = {"stat": stat(), "gate": gate(),
          "shots": [shot("z3_front", at=(0,-0.20,0.80), dist=0.42, yaw=0, pitch=-4),
                    shot("z3_mouth", at=(0,-0.235,0.716), dist=0.13, yaw=0, pitch=-6),
                    shot("z3_side", at=(0,-0.22,0.712), dist=0.20, yaw=80, pitch=-4)]}

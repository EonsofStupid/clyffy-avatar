import bmesh
from mathutils import Vector
unsel()
o, bm = _bm()
BAND = lambda p: 0.600 < p.z < 0.700 and abs(p.x) < 0.16 and -0.28 < p.y < 0.18
rows = []
for v in bm.verts:
    if not BAND(v.co): continue
    nb = [e.other_vert(v) for e in v.link_edges]
    if len(nb) < 3: continue
    mid = sum((n.co for n in nb), Vector()) / len(nb)
    el = sum((v.co - n.co).length for n in nb) / len(nb)
    if el <= 0: continue
    rows.append(((v.co - mid).length / el, (v.co - mid).length, v))
rows.sort(key=lambda r: -r[0])
vals = [r[0] for r in rows]
res = {"verts_in_collar_band": len(rows),
       "median_ratio": round(sorted(vals)[len(vals)//2], 3),
       "over_0.8x": sum(1 for x in vals if x > 0.8),
       "over_0.6x": sum(1 for x in vals if x > 0.6),
       "worst": [{"ratio": round(r[0],3), "d": round(r[1],4),
                  "co": [round(c,3) for c in r[2].co]} for r in rows[:8]]}
bm.free()
result = res

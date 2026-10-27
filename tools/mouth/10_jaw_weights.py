import bmesh
from mathutils import Vector
unsel(); snap("N_pre_jawweights")
o = obj()
HINGE = Vector((0.0, -0.170, 0.800))
def lipz(p):
    best = 1e9; z = 0.0
    for c in CURVE:
        d = (c - p).length
        if d < best: best, z = d, c.z
    return z
def ss(t):
    t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)
gjaw = o.vertex_groups.get("jaw") or o.vertex_groups.new(name="jaw")
ghead = o.vertex_groups.get("head") or o.vertex_groups.new(name="head")
BOX = lambda p: p.y < -0.13 and 0.64 < p.z < 0.80 and abs(p.x) < 0.12
idx_jaw, idx_head = gjaw.index, ghead.index
changed = 0; hist = {}
for v in o.data.vertices:
    p = v.co
    if not BOX(p): continue
    below = ss((lipz(p) - p.z) / 0.008)            # 1 below the lip line, 0 above it
    infront = ss((-0.170 - p.y) / 0.035)           # 1 at the muzzle, 0 at the hinge and behind
    w = below * infront
    # keep whatever other bones already claim this vert; only trade jaw against head
    others = sum(g.weight for g in v.groups if g.group not in (idx_jaw, idx_head))
    room = max(0.0, 1.0 - others)
    gjaw.add([v.index], w * room, "REPLACE")
    ghead.add([v.index], (1.0 - w) * room, "REPLACE")
    changed += 1
    k = round(w, 1); hist[k] = hist.get(k, 0) + 1
out.append("re-authored jaw/head weights on %d verts in the mouth box" % changed)
out.append("weight histogram: %s" % dict(sorted(hist.items())))
say("jaw weights re-authored against the rebuilt mouth")
result = {"changed": changed}

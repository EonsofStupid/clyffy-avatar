import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
unsel()
o, bm = _bm()
b2 = bmesh.new(); b2.from_mesh(o.data); M = BVHTree.FromBMesh(b2); b2.free()
def dl(p):
    best = 1e9
    for i in range(len(CURVE) - 1):
        a, b = CURVE[i], CURVE[i + 1]; ab = b - a
        t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
        best = min(best, (p - (a + ab * t)).length)
    return best
# how deep does the bag go, straight back from the lip centre?
p0 = Vector((0.0, SEAM[0][1], SEAM[0][2]))
hits = []
o0 = p0 + Vector((0, -0.03, 0))
d = Vector((0, 1, 0))
t = 0.0
for _ in range(8):
    r = M.ray_cast(o0 + d * (t + 1e-4), d, 0.5)
    if r[0] is None: break
    t = (r[0] - o0).length
    hits.append(round(t - 0.03, 4))
res = {"lip_front": [round(c,4) for c in p0],
       "surface_crossings_going_back_from_the_lip": hits}
# teeth / tongue extents vs the bag
for n in ("clyffy_teeth_upper", "clyffy_teeth_lower", "clyffy_tongue"):
    ob = bpy.data.objects[n]
    bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    res[n] = {"y": [round(min(v.y for v in bb),4), round(max(v.y for v in bb),4)],
              "z": [round(min(v.z for v in bb),4), round(max(v.z for v in bb),4)],
              "x_half": round(max(abs(v.x) for v in bb), 4)}
# cavity wall verts: behind the lip and inside
cav = [v for v in bm.verts if v.co.y > -0.27 and v.co.y < -0.13 and 0.68 < v.co.z < 0.76
       and abs(v.co.x) < 0.09 and dl(v.co) > 0.004]
res["verts_in_bag_box"] = len(cav)
if cav:
    res["bag_extent"] = {"y": [round(min(v.co.y for v in cav),4), round(max(v.co.y for v in cav),4)],
                         "z": [round(min(v.co.z for v in cav),4), round(max(v.co.z for v in cav),4)],
                         "x_half": round(max(abs(v.co.x) for v in cav), 4)}
result = res
bm.free()

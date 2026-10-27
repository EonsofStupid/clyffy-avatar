import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
unsel()
o = obj(); bm = bmesh.new(); bm.from_mesh(o.data)
b2 = bmesh.new(); b2.from_mesh(o.data); M = BVHTree.FromBMesh(b2); b2.free()
cand = [v for v in bm.verts if v.co.y < -0.150 and 0.660 < v.co.z < 0.740 and abs(v.co.x) < 0.100]
under = []
for v in cand:
    loc, nor, idx, d = M.ray_cast(v.co + Vector((0, 0, -0.0008)), Vector((0, 0, -1)), 0.25)
    if loc is None:                       # nothing of the head below it -> it IS the underside
        under.append(v)
out.append("candidates %d, underside skin %d" % (len(cand), len(under)))
globals()["UNDER"] = set(tuple(round(c, 6) for c in v.co) for v in under)
# how far below is the scaffold's chin at those points?
sc = bpy.data.objects["SCAFFOLD"]
bS = bmesh.new(); bS.from_mesh(sc.data); bS.transform(sc.matrix_world)
S = BVHTree.FromBMesh(bS); bS.free()
globals()["S"] = S
drops = []
for v in under:
    loc, nor, idx, d = S.ray_cast(v.co + Vector((0, 0, 0.02)), Vector((0, 0, -1)), 0.20)
    if loc is not None: drops.append(v.co.z - loc.z)
out.append("scaffold chin sits %.4f below on average (max %.4f) over %d of them"
           % (sum(drops)/max(len(drops),1), max(drops) if drops else 0, len(drops)))
bm.free()
sel(lambda co: tuple(round(c, 6) for c in co) in UNDER)
result = {"n": len(under),
          "shots": [shot("z1_sel_side", at=(0,-0.23,0.710), dist=0.18, yaw=80, pitch=-6, wire=True),
                    shot("z1_sel_low", at=(0,-0.23,0.706), dist=0.17, yaw=0, pitch=-35, wire=True)]}

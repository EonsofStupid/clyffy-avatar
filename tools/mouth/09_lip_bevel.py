import bmesh
from mathutils import Vector
clutter()
o = obj(); bm = bmesh.new(); bm.from_mesh(o.data)
def dl(p):
    best = 1e9
    for i in range(len(CURVE) - 1):
        a, b = CURVE[i], CURVE[i + 1]; ab = b - a
        t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
        best = min(best, (p - (a + ab * t)).length)
    return best
def K(v): return (round(v.co.x, 6), round(v.co.y, 6), round(v.co.z, 6))
LIPCO = set(K(v) for v in bm.verts if v.co.y < -0.16 and dl(v.co) < 0.0015)
rim = [e for e in bm.edges if K(e.verts[0]) in LIPCO and K(e.verts[1]) in LIPCO
       and len(e.link_faces) == 2]
out.append("rim edges (both ends on the lip line, interior): %d" % len(rim))
# BEVEL the rim rather than cutting the wall: bevel widens the edge into a band of quads and
# handles the irregular corners itself. The wall-edge cut left 12 ngons -> 40 tris -> 56 slivers.
ret = bmesh.ops.bevel(bm, geom=rim, offset=0.0035, offset_type="OFFSET",
                      segments=2, profile=0.5, affect="EDGES", clamp_overlap=True)
out.append("bevel produced %d faces" % len(ret.get("faces", [])))
ng = [f for f in bm.faces if len(f.verts) > 4]
if ng:
    bmesh.ops.triangulate(bm, faces=ng)
    out.append("ngons triangulated: %d" % len(ng))
bad = [f for f in bm.faces if f.calc_area() < 1e-9]
out.append("zero-area faces: %d" % len(bad))
bm.to_mesh(o.data); o.data.update(); bm.free()
say("lip rim bevelled - the rim becomes a band instead of a knife")
result = {"stat": stat(), "gate": gate()}

import bmesh
from mathutils import Vector
unsel()
o, bm = _bm()
def dl(p):
    best = 1e9
    for i in range(len(CURVE) - 1):
        a, b = CURVE[i], CURVE[i + 1]; ab = b - a
        t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
        best = min(best, (p - (a + ab * t)).length)
    return best
# how the mesh is banded by distance from the lip line -> how many rings we actually have
bands = {}
for v in bm.verts:
    if v.co.y > -0.14 or v.co.z > 0.80 or abs(v.co.x) > 0.12: continue
    d = dl(v.co)
    if d > 0.06: continue
    k = int(d / 0.006)
    bands[k] = bands.get(k, 0) + 1
# valence of the verts sitting ON the lip line, and at the two corners
lipv = [v for v in bm.verts if dl(v.co) < 0.0015 and v.co.y < -0.16]
val = {}
for v in lipv: val[len(v.link_edges)] = val.get(len(v.link_edges), 0) + 1
corners = sorted(lipv, key=lambda v: -abs(v.co.x))[:6]
# is there an inner lip loop? verts just behind the lip inside the cavity
result = {
  "ring_histogram_by_distance_from_lip(6mm bins)": dict(sorted(bands.items())),
  "lip_line_verts": len(lipv),
  "lip_vert_valence": dict(sorted(val.items())),
  "corner_verts": [{"co": [round(c,4) for c in v.co], "valence": len(v.link_edges)} for v in corners],
  "faces_touching_lip": len({f for v in lipv for f in v.link_faces}),
}
bm.free()

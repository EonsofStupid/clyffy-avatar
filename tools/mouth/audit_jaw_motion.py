import math
from mathutils import Euler, Vector
unsel(); clutter()
rig = bpy.data.objects["clyffy_rig"]
jb = rig.pose.bones["jaw"]; jb.rotation_mode = "XYZ"
def lipz(p):
    best = 1e9; z = 0.0
    for c in CURVE:
        d = (c - p).length
        if d < best: best, z = d, c.z
    return z
o = obj()
LOWER = [v.index for v in o.data.vertices
         if v.co.y < -0.19 and abs(v.co.x) < 0.06 and v.co.z < lipz(v.co) - 0.004 and v.co.z > 0.66]
UPPER = [v.index for v in o.data.vertices
         if v.co.y < -0.19 and abs(v.co.x) < 0.06 and v.co.z > lipz(v.co) + 0.006 and v.co.z < 0.76]
def sample(idxs):
    dg = bpy.context.evaluated_depsgraph_get()
    ob = o.evaluated_get(dg); me = ob.to_mesh()
    c = sum((ob.matrix_world @ me.vertices[i].co for i in idxs), Vector()) / len(idxs)
    ob.to_mesh_clear(); return c
def part(n):
    dg = bpy.context.evaluated_depsgraph_get()
    ob = bpy.data.objects[n].evaluated_get(dg); me = ob.to_mesh()
    c = sum((ob.matrix_world @ v.co for v in me.vertices), Vector()) / len(me.vertices)
    ob.to_mesh_clear(); return c
res = {}
for deg in (0, 25):
    jb.rotation_euler = Euler((math.radians(deg), 0, 0), "XYZ")
    bpy.context.view_layer.update()
    res.setdefault("lower_lip_skin", {})[deg] = sample(LOWER)
    res.setdefault("upper_lip_skin", {})[deg] = sample(UPPER)
    for n in ("clyffy_teeth_lower", "clyffy_teeth_upper", "clyffy_tongue"):
        res.setdefault(n, {})[deg] = part(n)
jb.rotation_euler = Euler((0, 0, 0), "XYZ")
bpy.context.view_layer.update()
out.append("lower-lip skin verts %d, upper-lip skin verts %d" % (len(LOWER), len(UPPER)))
result = {k: {"moved": round((v[25] - v[0]).length, 4),
              "rest": [round(c, 4) for c in v[0]], "open": [round(c, 4) for c in v[25]]}
          for k, v in res.items()}

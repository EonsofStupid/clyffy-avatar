"""Look at the mouth interior, which is otherwise sealed inside an opaque head.

    blender -b --python tools/mouth_preview.py -- <in.blend> <out_dir> <fwd_deg>

The cavity, teeth and tongue are correct only if they are INVISIBLE at rest — that is the
gate. Which means the only way to actually look at them is to hide the skin. This renders the
`inner_` geometry alone at fixed angles, so the authored shape can be judged instead of
inferred from vertex counts.

Fixed angles, no detection: the same discipline as everywhere else in this project.
Workbench-style flat emission per part rather than a beauty render, because this is validation
and flat colour reads shape better than an unlit cavity would.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hardfail  # noqa: F401
import bpy, bmesh, math
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = os.path.abspath(argv[0]), os.path.abspath(argv[1])
FWD_DEG = float(argv[2])
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=SRC)
ob = max([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
me = ob.data
names = [m.name if m else "" for m in me.materials]
inner = {i for i, n in enumerate(names) if n.startswith("inner_")}
assert inner, f"no inner_ materials in {names}"
print(f"inner slots {sorted(inner)} of {names}")

mi = np.empty(len(me.polygons), dtype=np.int32)
me.polygons.foreach_get("material_index", mi)
keep = np.isin(mi, list(inner))
print(f"keeping {int(keep.sum())} interior faces, deleting {int((~keep).sum())} skin faces")

bm = bmesh.new(); bm.from_mesh(me)
bm.faces.ensure_lookup_table()
drop = [f for f in bm.faces if not keep[f.index]]
bmesh.ops.delete(bm, geom=drop, context="FACES")
bm.to_mesh(me); bm.free(); me.update()

# flat emission per part so the three pieces are told apart at a glance
PAL = {"inner_mouth": (0.30, 0.05, 0.07), "inner_teeth": (0.93, 0.90, 0.76),
       "inner_tongue": (0.86, 0.35, 0.40)}
for m in me.materials:
    if not m:
        continue
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*PAL.get(m.name, (0.6, 0.6, 0.6)), 1.0)
    nt.links.new(e.outputs["Emission"], nt.nodes["Material Output"].inputs["Surface"])

co = np.array([v.co[:] for v in me.vertices])
ctr = co.mean(axis=0)
rad = float(np.abs(co - ctr).max())
print(f"interior bounds  x {co[:,0].min():+.4f}..{co[:,0].max():+.4f}  "
      f"y {co[:,1].min():+.4f}..{co[:,1].max():+.4f}  z {co[:,2].min():+.4f}..{co[:,2].max():+.4f}")

sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = sc.render.resolution_y = 1000
w = bpy.data.worlds.new("W"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.9
sc.world = w
cd = bpy.data.cameras.new("C"); cam = bpy.data.objects.new("C", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"; cd.ortho_scale = rad * 2.6
R = 3.0

for tag, az, el in (("front", FWD_DEG, 0), ("threequarter", FWD_DEG - 40, 12),
                    ("side", FWD_DEG - 90, 0), ("below", FWD_DEG, -55),
                    ("above", FWD_DEG, 55)):
    ar, er = math.radians(az), math.radians(el)
    cam.location = (ctr[0] + math.cos(er) * math.sin(ar) * R,
                    ctr[1] - math.cos(er) * math.cos(ar) * R,
                    ctr[2] + math.sin(er) * R)
    cam.rotation_euler = (math.radians(90.0 - el), 0.0, ar)
    sc.render.filepath = os.path.join(OUT, f"inner_{tag}.png")
    bpy.ops.render.render(write_still=True)
print(f"wrote 5 views to {OUT}")

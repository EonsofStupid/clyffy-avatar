"""Close-ups of the muzzle at FIXED angles: textured, wireframe, and crease-highlighted.

    blender -b --python tools/muzzle_zoom.py -- <in.blend> <out_dir> <fwd_deg>

Three passes over the same fixed views, so the same pixel can be read three ways:

  tex_<deg>    flat-lit, textured — what the lip looks like
  wire_<deg>   flat grey + wireframe — where the EDGES actually run
  crease_<deg> flat grey + every >25 deg dihedral edge drawn in red — whether the lip is a
               crease in the geometry or only a line in the texture

Flat light throughout: a key light on this character once made a pink muzzle measure
brighter than white fur. Angles are supplied, never detected.
"""
import bpy, bmesh, sys, os, math
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = os.path.abspath(argv[0]), os.path.abspath(argv[1])
FWD_DEG = float(argv[2])
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=SRC)
ob = max([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
me = ob.data
N = len(me.vertices)
co = np.empty((N, 3)); me.vertices.foreach_get("co", co.ravel())
z = co[:, 2]; zlo, zhi = float(z.min()), float(z.max()); H = zhi - zlo
hm = z > zlo + 0.70 * H
hc = co[hm].mean(axis=0)

a = math.radians(FWD_DEG)
fwd = np.array([math.sin(a), -math.cos(a), 0.0])
lat = np.array([-fwd[1], fwd[0], 0.0])
proj = (co - hc) @ fwd

# muzzle centre: the forward-most 2% of head verts, averaged
k = max(1, int(0.02 * hm.sum()))
idx = np.where(hm)[0]
tipset = idx[np.argsort(proj[idx])[-k:]]
mc = co[tipset].mean(axis=0)
print(f"muzzle centre {tuple(round(float(v),4) for v in mc)}   (mean of {k} forward-most head verts)")

# ------------------------------------------------------------------ crease overlay object
bm = bmesh.new(); bm.from_mesh(me)
keep = []
for e in bm.edges:
    if len(e.link_faces) != 2:
        continue
    i, j = e.verts[0].index, e.verts[1].index
    if not (hm[i] and hm[j]):
        continue
    n1, n2 = e.link_faces[0].normal, e.link_faces[1].normal
    if n1.length == 0 or n2.length == 0:
        continue
    if math.degrees(n1.angle(n2)) < 25.0:
        continue
    keep.append((i, j))
bm.free()
print(f"crease edges (head, >25 deg dihedral): {len(keep)}")

# CREASE MARKING AS A VERTEX COLOUR, not as overlay geometry. The first version built a
# wire mesh of the crease edges and gave it a SKIN modifier — Skin needs a marked root per
# connected component, so with 2330 loose 2-vertex edges it emitted nothing and the pass
# rendered as blank grey. A colour attribute cannot fail that way: if a vertex is marked,
# it is red in the render.
crease_v = np.zeros(N, dtype=bool)
for p, q in keep:
    crease_v[p] = True; crease_v[q] = True
print(f"  vertices touched by a crease edge: {int(crease_v.sum())}")

if "creasecol" in me.color_attributes:
    me.color_attributes.remove(me.color_attributes["creasecol"])
ca = me.color_attributes.new(name="creasecol", type="FLOAT_COLOR", domain="POINT")
cols = np.zeros((N, 4), dtype=np.float32)
cols[:, 3] = 1.0
cols[~crease_v] = (0.62, 0.62, 0.62, 1.0)
cols[crease_v] = (1.0, 0.0, 0.0, 1.0)
ca.data.foreach_set("color", cols.ravel())

grey = bpy.data.materials.new("grey"); grey.use_nodes = True
g = grey.node_tree.nodes["Principled BSDF"]
g.inputs["Base Color"].default_value = (0.72, 0.72, 0.72, 1)
g.inputs["Roughness"].default_value = 1.0

# emission straight from the attribute: no lighting, so nothing can wash the marks out
cmat = bpy.data.materials.new("creasemat"); cmat.use_nodes = True
nt = cmat.node_tree
for n in list(nt.nodes):
    if n.type != "OUTPUT_MATERIAL":
        nt.nodes.remove(n)
attr = nt.nodes.new("ShaderNodeVertexColor"); attr.layer_name = "creasecol"
emi = nt.nodes.new("ShaderNodeEmission")
nt.links.new(attr.outputs["Color"], emi.inputs["Color"])
nt.links.new(emi.outputs["Emission"], nt.nodes["Material Output"].inputs["Surface"])

# ------------------------------------------------------------------ scene: FLAT light only
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = 1100
sc.render.resolution_y = 1100
w = bpy.data.worlds.new("W"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 1.7
sc.world = w

cd = bpy.data.cameras.new("C"); cam = bpy.data.objects.new("C", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"
cd.ortho_scale = 0.26            # roughly the muzzle plus the chin and lower cheeks
ctr = Vector((float(mc[0]), float(mc[1]), float(mc[2])))
R = H * 3

orig_mats = [m for m in me.materials]

VIEWS = [0, 45, 90, 135]


def shoot(tag, wire, use_grey, creases):
    # 0.72 albedo under a 1.7 world clips to pure white and the whole frame reads blank —
    # it did on the first run. The textured pass wants the bright even light; the grey
    # passes want enough headroom to show shape.
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.55 if use_grey else 1.7
    if creases:
        me.materials.clear(); me.materials.append(cmat)
    elif use_grey:
        me.materials.clear(); me.materials.append(grey)
    else:
        me.materials.clear()
        for m in orig_mats:
            me.materials.append(m)

    if wire:
        if "W" not in ob.modifiers:
            m = ob.modifiers.new("W", "WIREFRAME")
            m.thickness = 0.0006
            m.use_replace = False
            m.material_offset = 1
        if len(me.materials) < 2:
            blk = bpy.data.materials.get("blk") or bpy.data.materials.new("blk")
            blk.use_nodes = True
            blk.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0, 0, 0, 1)
            me.materials.append(blk)
    elif "W" in ob.modifiers:
        ob.modifiers.remove(ob.modifiers["W"])
    for deg in VIEWS:
        t = math.radians(deg)
        cam.location = (ctr.x + math.sin(t) * R, ctr.y - math.cos(t) * R, ctr.z)
        cam.rotation_euler = (math.radians(90), 0, t)
        sc.render.filepath = os.path.join(OUT, f"{tag}_{deg:03d}.png")
        bpy.ops.render.render(write_still=True)
    print(f"  wrote {tag}_* ({len(VIEWS)} views)")


shoot("tex", wire=False, use_grey=False, creases=False)
shoot("wire", wire=True, use_grey=True, creases=False)
shoot("crease", wire=False, use_grey=True, creases=True)
print("done — nothing was saved back to the mesh")

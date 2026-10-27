"""Bake the `skin_flesh` (muzzle) weight into UV space, to see what the pad has to work with.

    blender -b --python work/face_ab/_bakemask.py -- <body.blend> <out.png> [res]

Uses Blender's own rasteriser rather than a hand-rolled UV triangle fill: the mesh already has
the UV layout the albedo and normal textures are authored against, and re-deriving it is a chance
to be subtly wrong about seams and winding.
"""
import bpy, sys, os
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
SRC = os.path.abspath(argv[0])
OUT = os.path.abspath(argv[1])
RES = int(argv[2]) if len(argv) > 2 else 1024

bpy.ops.wm.open_mainfile(filepath=SRC)
ob = max([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
me = ob.data
print(f"verts {len(me.vertices)}  uv '{me.uv_layers[0].name}'  mats {len(me.materials)}")

img = bpy.data.images.new("pad_mask", RES, RES, alpha=False, float_buffer=True)
img.colorspace_settings.name = "Non-Color"

# Swap every material for a flat emission driven by the skin_flesh attribute, so the bake reads
# the weight and nothing else — no lighting, no albedo, no normal.
for slot_i, m in enumerate(me.materials):
    if m is None:
        continue
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emi = nt.nodes.new("ShaderNodeEmission")
    att = nt.nodes.new("ShaderNodeAttribute")
    att.attribute_type = "GEOMETRY"
    att.attribute_name = "skin_flesh"
    nt.links.new(att.outputs["Fac"], emi.inputs["Color"])
    nt.links.new(emi.outputs["Emission"], out.inputs["Surface"])
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.select = True
    nt.nodes.active = tex

sc = bpy.context.scene
sc.render.engine = "CYCLES"
try:
    sc.cycles.device = "GPU"
except Exception:
    pass
sc.cycles.samples = 1
sc.render.bake.use_selected_to_active = False
sc.render.bake.margin = 8

for o in bpy.context.view_layer.objects:
    o.select_set(False)
ob.select_set(True)
bpy.context.view_layer.objects.active = ob
bpy.ops.object.bake(type="EMIT")

px = np.array(img.pixels[:], dtype=np.float32).reshape(RES, RES, 4)
mask = px[..., 0]
print(f"\npad mask over UV space ({RES}x{RES}):")
print(f"  texels > 0.05 : {int((mask > 0.05).sum()):>8}  ({100*(mask>0.05).mean():.2f}% of the sheet)")
print(f"  texels > 0.50 : {int((mask > 0.50).sum()):>8}  ({100*(mask>0.50).mean():.2f}%)")
print(f"  texels > 0.90 : {int((mask > 0.90).sum()):>8}  ({100*(mask>0.90).mean():.2f}%)")
ys, xs = np.nonzero(mask > 0.05)
if len(xs):
    print(f"  UV bbox: u {xs.min()/RES:.3f}..{xs.max()/RES:.3f}   v {ys.min()/RES:.3f}..{ys.max()/RES:.3f}")
    print(f"  -> at 4096 the pad spans about {int((xs.max()-xs.min())*4096/RES)} x "
          f"{int((ys.max()-ys.min())*4096/RES)} texels")

img.filepath_raw = OUT
img.file_format = "PNG"
img.save()
print(f"wrote {OUT}")

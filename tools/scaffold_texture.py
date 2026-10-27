"""What is the scaffold actually WEARING — rendered with its texture, not as clay.

    blender -b --python tools/scaffold_texture.py -- work/RETOPO_clyffy.blend

The body survey rendered the scaffold in WORKBENCH with `color_type='OBJECT'`, which paints every
object one flat colour. Garment colour, print and trim are all invisible in that mode, so what I
read as "a t-shirt with a drawstring" is a read of SILHOUETTE ONLY and is not evidence about the
garment. `sheets/turn_4k_clean.png` shows a navy DevPulse tee with a blue LANYARD and an ID badge —
a cord round the neck ending in a small rectangle at the chest, which is exactly the shape I called
a drawstring. Textured render settles it. Read-only.
"""
import bpy, sys, os, math
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
bpy.ops.wm.open_mainfile(filepath=BLEND)
scaf = bpy.data.objects["SCAFFOLD"]
rt = bpy.data.objects["retopo_head"]

print(f"SCAFFOLD materials: {[m.name for m in scaf.data.materials]}")
for m in scaf.data.materials:
    if m and m.use_nodes:
        for n in m.node_tree.nodes:
            if n.type == "TEX_IMAGE" and n.image:
                print(f"  {m.name}: image '{n.image.name}' {tuple(n.image.size)}")

sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"
sh.color_type = "TEXTURE"          # <- the whole point
sh.show_cavity = False
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = sc.render.resolution_y = 1200

# the retopo shell is hidden: it would cover the very garment being inspected
rt.hide_render = True
for o in bpy.data.objects:
    if o.name.startswith("vis_") or o.type == "EMPTY" or o.name.startswith("clyffy_"):
        o.hide_render = True

w = bpy.data.worlds.new("WT"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.55, 0.57, 1)
sc.world = w
cd = bpy.data.cameras.new("CT"); cam = bpy.data.objects.new("CT", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"; cd.ortho_scale = 1.15
cd.clip_start = 0.001; cd.clip_end = 100.0
ctr = Vector((0.0, 0.0, 0.5))
OUT = os.path.join(os.path.dirname(BLEND), "scaffold_texture")
os.makedirs(OUT, exist_ok=True)
for deg in (0, 90, 180):
    a = math.radians(deg)
    cam.location = (ctr.x + math.sin(a) * 3, ctr.y - math.cos(a) * 3, ctr.z)
    cam.rotation_euler = (math.radians(90), 0, a)
    sc.render.filepath = os.path.join(OUT, f"tex_{deg:03d}.png")
    bpy.ops.render.render(write_still=True)

# and a chest close-up: lanyard-and-badge vs drawstring is decided at this scale
cd.ortho_scale = 0.40
cam.location = (0.0, -3.0, 0.47)
cam.rotation_euler = (math.radians(90), 0, 0)
sc.render.filepath = os.path.join(OUT, "tex_chest.png")
bpy.ops.render.render(write_still=True)
print(f"renders -> {OUT}")

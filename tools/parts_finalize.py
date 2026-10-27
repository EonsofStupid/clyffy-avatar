"""Finish the separate parts and render THE MODEL ALONE — scaffold hidden.

    blender -b --python tools/parts_finalize.py -- work/RETOPO_clyffy.blend --write

Every body render so far has shown the retopo shell in orange OVER the grey scaffold, which is the
right picture while deciding what to build next but the wrong one for judging what exists: the
scaffold fills in behind every gap, so a hole reads as "grey, therefore not done yet" instead of
"hole". `work/solo_check/` exists for the head for exactly this reason — the patch alone is the only
honest way to see holes.

Also sets what the parts need to be parts:
  * Mirror(X) on the one-sided pieces, with **clipping OFF** — the eyeball lesson: an off-midline
    object with clipping on welds to itself.
  * NOT the tail, which crosses the midline (x -0.035..+0.172) and is one whole object.
"""
import bpy, bmesh, sys, os, math
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
WRITE = "--write" in argv
bpy.ops.wm.open_mainfile(filepath=BLEND)
rt = bpy.data.objects["retopo_head"]
scaf = bpy.data.objects["SCAFFOLD"]

# name -> (mirror?, colour)
PARTS = {
    # THE BODY — one voxel remesh of the scaffold below the collar, replacing the marched body that
    # lost the scaffold's form. Whole and unmirrored: the remesh covers both sides, both arms, both
    # legs, and the hands, so there is no seam to weld and no separate hand object.
    "clyffy_body":  (False, (0.86, 0.84, 0.82, 1.0)),
    "clyffy_ear_R": (True,  (0.95, 0.75, 0.75, 1.0)),
    "clyffy_horn_R": (True, (0.98, 0.96, 0.86, 1.0)),
    "clyffy_eye_R": (True,  (0.20, 0.14, 0.10, 1.0)),
    "clyffy_teeth_upper": (True, (0.98, 0.96, 0.86, 1.0)),
    "clyffy_teeth_lower": (True, (0.98, 0.96, 0.86, 1.0)),
    "clyffy_tongue": (False, (0.90, 0.45, 0.50, 1.0)),
}

print("PARTS:")
total = quads = 0
for name, (mirror, col) in PARTS.items():
    ob = bpy.data.objects.get(name)
    if ob is None:
        print(f"  {name:22s} MISSING")
        continue
    ob.color = col
    have = any(m.type == "MIRROR" for m in ob.modifiers)
    if mirror and not have:
        m = ob.modifiers.new("Mirror", "MIRROR")
        m.use_axis[0] = True
        m.use_clip = False        # off-midline object: clipping would weld it to itself
        print(f"  {name:22s} added Mirror(X), clip OFF")
    nq = sum(1 for f in ob.data.polygons if len(f.vertices) == 4)
    nt = sum(1 for f in ob.data.polygons if len(f.vertices) == 3)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    nonman = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    openb = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    bm.free()
    total += len(ob.data.polygons)
    quads += nq
    print(f"  {name:22s} {len(ob.data.polygons):5d} faces ({nq} q, {nt} t)  "
          f"non-manifold {nonman}, open edges {openb}"
          + ("  Mirror" if mirror else "  (whole)"))

nq = sum(1 for p in rt.data.polygons if len(p.vertices) == 4)
print(f"\nshell: {len(rt.data.polygons)} faces ({nq} quads, "
      f"{100.0 * nq / len(rt.data.polygons):.1f}%)")
print(f"parts: {total} faces ({quads} quads)")
print(f"MODEL TOTAL (half, pre-mirror): {len(rt.data.polygons) + total} faces")

# ---- render the model ALONE -----------------------------------------------------------------------
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"; sh.color_type = "OBJECT"
sh.show_cavity = True; sh.cavity_type = "BOTH"
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = sc.render.resolution_y = 1100
rt.color = (0.86, 0.84, 0.82, 1.0)
rt.show_wire = False
scaf.hide_render = True                      # <- the point of this render
for o in bpy.data.objects:
    if o.name.startswith("vis_") or o.name.startswith("SCAF_") or o.type == "EMPTY":
        o.hide_render = True
w = bpy.data.worlds.new("WP"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.38, 0.42, 0.40, 1)
sc.world = w
cd = bpy.data.cameras.new("CP"); cam = bpy.data.objects.new("CP", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"; cd.ortho_scale = 1.15
cd.clip_start = 0.001; cd.clip_end = 100.0
ctr = Vector((0.0, 0.0, 0.5))
OUT = os.path.join(os.path.dirname(BLEND), "model_solo")
os.makedirs(OUT, exist_ok=True)
for deg in (0, 45, 90, 180, 270):
    a = math.radians(deg)
    cam.location = (ctr.x + math.sin(a) * 3, ctr.y - math.cos(a) * 3, ctr.z)
    cam.rotation_euler = (math.radians(90), 0, a)
    sc.render.filepath = os.path.join(OUT, f"solo_{deg:03d}.png")
    bpy.ops.render.render(write_still=True)
# from BELOW — the angle that found the jawline and throat gaps, and the only one that can show
# the sole cap and the crotch fill
cam.location = (0.0, -1.2, -1.2)
cam.rotation_euler = (math.radians(135), 0, 0)
sc.render.filepath = os.path.join(OUT, "solo_under.png")
bpy.ops.render.render(write_still=True)
print(f"renders -> {OUT}")

if WRITE:
    scaf.hide_render = False
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print("saved")

"""CP9a — the EYEBALL as its own object, sphere-fitted to the scaffold's sculpted eye.

    blender -b --python tools/retopo_eyeball.py -- work/RETOPO_clyffy.blend

The lid margin (the CP1 eye ring) was deliberately left open through CP6 for exactly this. The
eyeball is a SEPARATE object like the teeth, tongue, ear and horn — it has to rotate under the
lids, so it can never be part of the shell.

Size and seat are MEASURED, not chosen: take the scaffold surface inside the aperture and fit a
sphere to it by linear least squares. The sculpted eye is already the approved shape; a guessed
radius would either float proud of the lids or sink and go dark.
"""
import bpy, bmesh, sys, os, math
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
bpy.ops.wm.open_mainfile(filepath=BLEND)
scaf = bpy.data.objects["SCAFFOLD"]
rt = bpy.data.objects["retopo_head"]

# the aperture: the CP1 eye ring
o = bpy.data.objects["vis_eye_R"]
ring = [o.matrix_world @ p.co.to_3d() for s in o.data.splines for p in s.points]
EC = sum(ring, Vector()) / len(ring)
ER = max((p - EC).length for p in ring)
print(f"eye aperture: centre ({EC.x:+.4f},{EC.y:+.4f},{EC.z:.4f}) radius {ER:.4f}")

# scaffold surface inside the aperture — the sculpted eyeball cap
bms = bmesh.new(); bms.from_mesh(scaf.data)
cap = [v.co.copy() for v in bms.verts if (v.co - EC).length < ER * 1.05 and v.co.y < EC.y + 0.02]
bms.free()
print(f"cap samples: {len(cap)}")

# linear least-squares sphere fit: 2x.cx + 2y.cy + 2z.cz + k = |p|^2,  k = r^2 - |c|^2
A = np.array([[2 * p.x, 2 * p.y, 2 * p.z, 1.0] for p in cap])
b = np.array([p.length_squared for p in cap])
sol, *_ = np.linalg.lstsq(A, b, rcond=None)
C = Vector(sol[:3].tolist())
R = math.sqrt(max(sol[3] + C.length_squared, 1e-9))
resid = [abs((p - C).length - R) for p in cap]
print(f"sphere fit: centre ({C.x:+.4f},{C.y:+.4f},{C.z:.4f}) radius {R:.4f}  "
      f"residual mean {sum(resid) / len(resid):.5f} max {max(resid):.5f}")

# sanity: the fitted ball must sit BEHIND the lid margin, not proud of it
front = C.y - R
print(f"  ball front y {front:+.4f} vs aperture y {EC.y:+.4f} "
      f"({'proud of the lids — CHECK' if front < EC.y - 0.004 else 'seated'})")

name = "clyffy_eye_R"
old = bpy.data.objects.get(name)
if old:
    bpy.data.objects.remove(old, do_unlink=True)
me = bpy.data.meshes.new(name)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16, radius=R)
bmesh.ops.translate(bm, verts=bm.verts, vec=C)
bm.to_mesh(me)
bm.free()
ob = bpy.data.objects.new(name, me)
bpy.context.scene.collection.objects.link(ob)
mir = ob.modifiers.new("Mirror", "MIRROR")
mir.use_axis[0] = True
mir.use_clip = False          # the ball is off-midline; clipping would weld it to itself
nq = sum(1 for p in me.polygons if len(p.vertices) == 4)
print(f"{name}: {len(me.polygons)} faces ({nq} quads), Mirror(X) on")
bpy.ops.wm.save_as_mainfile(filepath=BLEND)

# ---- renders -------------------------------------------------------------------------------------
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"; sh.color_type = "OBJECT"
sh.show_cavity = True; sh.cavity_type = "BOTH"
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = sc.render.resolution_y = 900
scaf.color = (0.60, 0.60, 0.62, 1.0)
rt.color = (0.95, 0.45, 0.15, 1.0)
ob.color = (0.15, 0.85, 0.55, 1.0)
for nm in ("clyffy_ear_R", "clyffy_horn_R"):
    if bpy.data.objects.get(nm):
        bpy.data.objects[nm].color = (0.25, 0.65, 0.95, 1.0)
for x in bpy.data.objects:
    if x.name.startswith("vis_") or x.type == "EMPTY":
        x.hide_render = True
w = bpy.data.worlds.new("W9"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.40, 0.44, 0.41, 1)
sc.world = w
ctr = Vector((0.0, -0.10, 0.85))
cd = bpy.data.cameras.new("C9"); cam = bpy.data.objects.new("C9", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"; cd.ortho_scale = 0.34
cd.clip_start = 0.001; cd.clip_end = 100.0
OUT = os.path.join(os.path.dirname(BLEND), "retopo_eye")
os.makedirs(OUT, exist_ok=True)
scaf.hide_render = True
for deg in (0, 35):
    a = math.radians(deg)
    cam.location = (ctr.x + math.sin(a) * 2, ctr.y - math.cos(a) * 2, ctr.z + 0.01)
    cam.rotation_euler = (math.radians(89), 0, a)
    sc.render.filepath = os.path.join(OUT, f"eye_{deg:03d}.png")
    bpy.ops.render.render(write_still=True)
cd.ortho_scale = 0.14
cam.location = (EC.x + math.sin(math.radians(15)) * 2,
                EC.y - math.cos(math.radians(15)) * 2, EC.z)
cam.rotation_euler = (math.radians(89), 0, math.radians(15))
sc.render.filepath = os.path.join(OUT, "eye_closeup.png")
bpy.ops.render.render(write_still=True)
scaf.hide_render = False
print(f"renders -> {OUT}")

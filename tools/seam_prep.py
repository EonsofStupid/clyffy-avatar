"""Prepare the mesh for the operator to hand-pick the lip seam.

    blender -b --python tools/seam_prep.py -- <in.blend> <out.blend> <fwd_deg>

Marks every crease edge on the head as SHARP so it draws in cyan in Edit Mode. That is the
same >25 deg dihedral set `muzzle_zoom.py` renders in red — it is DATA, not a suggested path.
Nothing is pre-selected, because which edges become the seam decides where the mouth corners
land, and that is a character decision the operator owns.

Geometry is otherwise untouched: marking an edge sharp changes no vertex, index or position,
so the selection made in this file bakes cleanly back onto the clean mesh. `seam_bake.py`
verifies that by comparing vertex count and positions before it accepts anything.
"""
import bpy, bmesh, sys, os, math
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = os.path.abspath(argv[0]), os.path.abspath(argv[1])
FWD_DEG = float(argv[2])
DIH = 25.0
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)

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
latc = (co - hc) @ lat

bm = bmesh.new(); bm.from_mesh(me)
marked = 0
for e in bm.edges:
    if len(e.link_faces) != 2:
        continue
    i, j = e.verts[0].index, e.verts[1].index
    if not (hm[i] and hm[j]):
        continue
    n1, n2 = e.link_faces[0].normal, e.link_faces[1].normal
    if n1.length == 0 or n2.length == 0:
        continue
    if math.degrees(n1.angle(n2)) < DIH:
        continue
    e.smooth = False          # bmesh: smooth False == marked sharp
    marked += 1
bm.to_mesh(me)
bm.free()
me.update()

# clear any selection so nothing here reads as a proposal
for v in me.vertices:
    v.select = False
for e in me.edges:
    e.select = False
for p in me.polygons:
    p.select = False

print(f"marked {marked} crease edges sharp (>{DIH:.0f} deg dihedral, head only)")
print(f"vertices {N}  faces {len(me.polygons)}   (unchanged)")

# where to look, in the operator's terms
LIP_Z = zlo + 0.719 * H
print(f"\nlip line sits at z = {LIP_Z:+.4f}  (71.9% of body height)")
band = hm & (np.abs(z - LIP_Z) < 0.01 * H) & (proj > 0)
if band.sum():
    print(f"  crease verts near that height span lateral "
          f"{latc[band].min():+.4f}..{latc[band].max():+.4f}")
print(f"forward is +X ({FWD_DEG:.0f} deg): in Blender, NUMPAD 3 looks at his face straight on,"
      f" NUMPAD 1 gives the profile")

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"\nwrote {OUT}")

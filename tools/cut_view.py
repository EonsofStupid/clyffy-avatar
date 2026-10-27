"""Saw the head in half and render the cut face. Look inside instead of inferring.

    blender -b --python tools/cut_view.py -- <in.blend> <out_dir> <fwd_deg> [angle_deg]

A real section: the mesh is bisected at the midline, the near half is REMOVED, the cut is
capped, and the camera looks straight into it. Not a wireframe plot of intersected edges — a
solid you can read.

This should have come BEFORE the cavity was built, not after. Building a mouth from measured
depths and reporting that the gates went green, without ever cutting the head open and looking
at the space the mouth had to live in, is how the cavity ended up as a lens pitched into the
muzzle that stretches into a membrane when the jaw opens.

Cut cap is drawn in flat grey so solid material is unmistakable; the mouth parts keep loud
distinct colours. Runs at any jaw angle, because the shape that matters is the OPEN one.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hardfail  # noqa: F401
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Quaternion

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = os.path.abspath(argv[0]), os.path.abspath(argv[1])
FWD_DEG = float(argv[2])
ANGLE = float(argv[3]) if len(argv) > 3 else 0.0
# AXIS: which plane to saw on. 'y' = the midline (side view, default); 'z' = horizontal
# (top view, which is what shows the chamber's WIDTH).
AXIS = argv[4] if len(argv) > 4 else "y"
CUT_AT = float(argv[5]) if len(argv) > 5 else 0.0
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=SRC)
ob = max([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
rig = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)

a = math.radians(FWD_DEG)
fwd = np.array([math.sin(a), -math.cos(a), 0.0])
lat = np.array([-fwd[1], fwd[0], 0.0])

if rig is not None and abs(ANGLE) > 1e-6:
    rig.data.pose_position = "POSE"
    pb = rig.pose.bones["jaw"]
    bone = rig.data.bones["jaw"]
    ax = bone.matrix_local.to_3x3().inverted() @ Vector(tuple(float(v) for v in lat))
    pb.rotation_mode = "QUATERNION"
    pb.rotation_quaternion = Quaternion(ax.normalized(), math.radians(ANGLE))
    bpy.context.view_layer.update()
print(f"jaw angle {ANGLE:.0f} deg")

# bake the pose down so the bisect cuts the DEFORMED shape, not the rest shape
dg = bpy.context.evaluated_depsgraph_get()
evm = ob.evaluated_get(dg).to_mesh()
me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
cut = bpy.data.objects.new("cut", me)
bpy.context.scene.collection.objects.link(cut)
# REMOVE THE ORIGINAL. The sectioned copy was being linked while the intact head stayed in the
# scene, so every render showed his OUTSIDE with the cut hidden inside it. Every conclusion I
# drew from those images — "the head is hollow", "the head is solid", the chamber plan — came
# from looking at his cheek.
for _o in [o for o in bpy.data.objects if o.type in ("MESH", "ARMATURE") and o is not cut]:
    bpy.data.objects.remove(_o, do_unlink=True)
print(f"scene now holds only the section: {[o.name for o in bpy.data.objects]}")
names = [m.name if m else "" for m in me.materials]
print(f"materials: {names}")

cap_mat = bpy.data.materials.new("CUTFACE")
me.materials.append(cap_mat)
CAP = len(me.materials) - 1

PN = {"y": tuple(float(v) for v in lat), "z": (0.0, 0.0, 1.0)}[AXIS]
PC = {"y": (0.0, 0.0, 0.0), "z": (0.0, 0.0, CUT_AT)}[AXIS]
bm = bmesh.new(); bm.from_mesh(me)
res = bmesh.ops.bisect_plane(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
                             plane_co=PC, plane_no=PN, clear_outer=True)
bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
bnd = [e for e in bm.edges if len(e.link_faces) == 1]
print(f"bisected: {len(bm.faces)} faces remain, {len(bnd)} open edges on the cut")
# centroid fan per loop — holes_fill capped only 4 of the cut's many loops, which left the
# section reading as a hollow shell instead of showing where the material actually is
# TRIANGLE_FILL, not a centroid fan and not holes_fill. Every boundary edge produced by the
# bisect lies in ONE plane, which is exactly the case triangle_fill is for; it fills the whole
# planar edge net at once, including regions with holes in them. The fan capped 4 loops of many
# and left the section reading as a hollow shell, and with no cap at all the far half's inner
# surface simply fills the silhouette — so neither one could tell solid from hollow, which is
# the single thing a section is for.
bnd = [e for e in bm.edges if len(e.link_faces) == 1]
made = 0
if bnd:
    r = bmesh.ops.triangle_fill(bm, edges=bnd, use_beauty=True, use_dissolve=False,
                                normal=PN)
    for f in r.get("geom", []):
        if isinstance(f, bmesh.types.BMFace):
            f.material_index = CAP
            made += 1
print(f"  capped {made} loop(s)")
bm.to_mesh(me); bm.free(); me.update()

# CONTRAST MATTERS MORE THAN PRETTINESS HERE. The first palette drew the cut face at 0.72 grey,
# which renders at rgb 243 against a 255 background — a 5% difference. I read that section as
# "the head is hollow behind the muzzle" and planned around it; sampling the pixels showed every
# point back to x=0.02 was solid. A section nobody can read is worse than no section.
PAL = {"inner_mouth": (0.66, 0.06, 0.12), "inner_teeth": (0.98, 0.95, 0.72),
       "inner_tongue": (0.95, 0.38, 0.48), "CUTFACE": (0.42, 0.45, 0.50)}
for m in me.materials:
    if not m:
        continue
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    col = PAL.get(m.name, (0.78, 0.75, 0.72))
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*col, 1.0)
    nt.links.new(e.outputs["Emission"], nt.nodes["Material Output"].inputs["Surface"])

co = np.array([v.co[:] for v in me.vertices])
z = co[:, 2]; zlo, zhi = float(z.min()), float(z.max())
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = sc.render.resolution_y = 1200
w = bpy.data.worlds.new("W"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
sc.world = w
cd = bpy.data.cameras.new("C"); cam = bpy.data.objects.new("C", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"

# look straight into the cut, from the side that was removed
# FRAMING IS MEASURED FROM THE MESH, NOT HARD-CODED. The original constants were literals tuned
# to the Tripo v2 head, which sits ~0.26 units tall with its lip at z 0.21. The first Meshy import
# arrives 1.9 units tall and centred on the origin, so those numbers frame empty space — and an
# empty render is indistinguishable from a section showing nothing, which is precisely the kind of
# false read this tool was written to end. Deriving the frame costs nothing and works on both.
#
# This is framing only. It decides where the camera points, never what anything is called — the
# facing still comes from FWD_DEG, supplied by the caller.
_head = co[co[:, 2] > zlo + 0.70 * (zhi - zlo)]
_hc = _head.mean(axis=0)
_hr = float(np.abs(_head - _hc).max())
_hz = float(_head[:, 2].max() - _head[:, 2].min())
_fwd2 = np.array([fwd[0], fwd[1], 0.0])
_mouth_c = _hc + _fwd2 * (_hr * 0.35) - np.array([0.0, 0.0, _hz * 0.22])
VIEWS = {"y": (("head", _hc, _hr * 2.6),
               ("mouth", _mouth_c, _hr * 1.5)),
         "z": (("top", np.array([_hc[0], _hc[1], CUT_AT]), _hr * 2.0),)}[AXIS]
print(f"framing from the mesh: head centre {tuple(round(float(v),4) for v in _hc)}  "
      f"radius {_hr:.4f}  mouth view centre {tuple(round(float(v),4) for v in _mouth_c)}")
for tag, ctr, scale in VIEWS:
    cd.ortho_scale = scale
    # camera on the side that was REMOVED, so we look straight into the cut face; oriented so
    # the character faces image-right, the way a profile is normally read
    # plane_no=+lat with the camera on -lat is the combination that actually looks INTO the cut.
    # Verified by sampling interior pixels: they must come back as the CUTFACE colour, not the
    # skin colour. Two other combinations render his outside while looking exactly like a
    # section, and I read one of them as "the head is hollow" before checking the pixels.
    # The bisect keeps the side the normal points AWAY from, so the camera must sit on the
    # normal side to look INTO the cut. Verified by sampling: an interior pixel must come back
    # as the CUT-FACE colour, never the skin colour.
    if AXIS == "y":
        cam.location = tuple(ctr + np.array([float(lat[0]), float(lat[1]), 0.0]) * 3.0)
        cam.rotation_euler = (math.radians(90), 0, math.radians(FWD_DEG + 90))
    else:
        cam.location = (float(ctr[0]), float(ctr[1]), float(CUT_AT) + 3.0)
        cam.rotation_euler = (0.0, 0.0, 0.0)
    sc.render.filepath = os.path.join(OUT, f"cut_{tag}_{int(ANGLE):02d}.png")
    bpy.ops.render.render(write_still=True)
print(f"wrote cut views to {OUT}")

"""Mesh integrity report + tight head views. Diagnostic only, writes nothing but images.

    blender -b --python tools/mesh_health.py -- <model> <out_dir>

Reports boundary edges (holes), non-manifold edges, loose verts and face-side histogram, then
renders the HEAD alone from front and back so the back of the skull can actually be inspected
instead of judged from a full-body thumbnail.
"""
import bpy, sys, os, math
import numpy as np
import bmesh
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC = os.path.abspath(argv[0])
OUT = os.path.abspath(argv[1])
os.makedirs(OUT, exist_ok=True)
TAG = os.path.splitext(os.path.basename(SRC))[0]

bpy.ops.wm.read_factory_settings(use_empty=True)
ext = os.path.splitext(SRC)[1].lower()
if ext == ".fbx":
    bpy.ops.import_scene.fbx(filepath=SRC)
else:
    bpy.ops.import_scene.gltf(filepath=SRC)

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
ob = max(meshes, key=lambda o: len(o.data.vertices))

bm = bmesh.new(); bm.from_mesh(ob.data)
boundary = [e for e in bm.edges if len(e.link_faces) == 1]
nonman = [e for e in bm.edges if len(e.link_faces) > 2]
loose = [v for v in bm.verts if not v.link_faces]
sides = {}
for f in bm.faces:
    sides[len(f.verts)] = sides.get(len(f.verts), 0) + 1

print(f"\n=== {TAG} ===")
print(f"  verts {len(bm.verts)}  faces {len(bm.faces)}  edges {len(bm.edges)}")
print(f"  face sides   : {dict(sorted(sides.items()))}")
print(f"  BOUNDARY edges (holes) : {len(boundary)}")
print(f"  NON-MANIFOLD edges     : {len(nonman)}")
print(f"  loose verts            : {len(loose)}")

co = np.array([v.co[:] for v in bm.verts])
z = co[:, 2]
zlo, zhi = z.min(), z.max()
if boundary:
    bz = np.array([[(e.verts[0].co + e.verts[1].co)[i] / 2 for i in range(3)] for e in boundary])
    hz = (bz[:, 2] - zlo) / (zhi - zlo)
    print(f"  hole edge heights (0=feet, 1=top): min {hz.min():.2f} med {np.median(hz):.2f} max {hz.max():.2f}")
    print(f"    in head band (>0.72): {int((hz > 0.72).sum())} of {len(boundary)}")
bm.free()

# ── head-only renders ────────────────────────────────────────────────────────
head_cut = zlo + 0.70 * (zhi - zlo)
hc_all = co[z > head_cut]
hc = hc_all.mean(axis=0)
hxy = hc_all[:, :2] - hc[:2]
best, face_ang = -1e9, 0.0
for deg in range(0, 360, 2):
    r = math.radians(deg)
    d = np.array([math.sin(r), -math.cos(r)])
    p = hxy @ d
    s = p.max() + p.min()
    if s > best:
        best, face_ang = s, float(deg)
print(f"  head facing (asymmetry sweep): {face_ang:.0f} deg")

sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = 900
sc.render.resolution_y = 900
w = bpy.data.worlds.new("W"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 1.6
sc.world = w

R = float(zhi - zlo)
head_r = float(np.abs(hc_all - hc).max())
cd = bpy.data.cameras.new("C"); cam = bpy.data.objects.new("C", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"; cd.ortho_scale = head_r * 2.6
ctr = Vector((float(hc[0]), float(hc[1]), float(hc[2])))
for name, off in [("head_front", 0), ("head_back", 180), ("head_top", None)]:
    if off is None:
        cam.location = (ctr.x, ctr.y, ctr.z + R)
        cam.rotation_euler = (0, 0, 0)
    else:
        a = math.radians(face_ang + off)
        cam.location = (ctr.x + math.sin(a) * R * 3, ctr.y - math.cos(a) * R * 3, ctr.z)
        cam.rotation_euler = (math.radians(90), 0, a)
    sc.render.filepath = os.path.join(OUT, f"{TAG}_{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"  wrote {TAG}_{name}.png")

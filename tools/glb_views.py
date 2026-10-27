"""Render orthographic views of a GLB so the generated mesh can be judged against the plates.

    blender -b --python tools/glb_views.py -- <model.glb> <out_dir> [--shaded]

Flat even lighting by default, matching the reference sheets — a rim light invents relief that is
not in the geometry, and every surface judgement in the previous project that used a key light
turned out to be measuring the light rather than the model.
"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC = os.path.abspath(argv[0])
OUT = os.path.abspath(argv[1])
SHADED = "--shaded" in argv
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
# Tripo hands back an FBX even when the URL says .glb (verified: magic bytes "Kaydara FBX Binary"),
# so dispatch on the actual extension rather than trusting the source URL.
ext = os.path.splitext(SRC)[1].lower()
if ext == ".fbx":
    bpy.ops.import_scene.fbx(filepath=SRC)
elif ext in (".glb", ".gltf"):
    bpy.ops.import_scene.gltf(filepath=SRC)
else:
    raise SystemExit(f"unsupported model container: {ext}")

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
assert meshes, "no mesh in the GLB"
ob = max(meshes, key=lambda o: len(o.data.vertices))
print(f"mesh '{ob.name}': {len(ob.data.vertices)} verts, {len(ob.data.polygons)} faces")
ngons = {}
for p in ob.data.polygons:
    ngons[len(p.vertices)] = ngons.get(len(p.vertices), 0) + 1
print(f"  face sides: {dict(sorted(ngons.items()))}")

mn = Vector((1e9,) * 3); mx = Vector((-1e9,) * 3)
for o in meshes:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        mn = Vector((min(mn[i], w[i]) for i in range(3)))
        mx = Vector((max(mx[i], w[i]) for i in range(3)))
ctr = (mn + mx) / 2
dims = mx - mn
R = max(dims)
print(f"  bounds {tuple(round(v,3) for v in dims)}  centre {tuple(round(v,3) for v in ctr)}")

sc = bpy.context.scene
# EEVEE with a uniform bright world and NO lights: this renders the actual glTF materials under
# even illumination. Workbench TEXTURE mode rendered the whole model black — it does not resolve
# the imported Principled graph — and a black silhouette is indistinguishable from a broken mesh,
# which is exactly the kind of false read this project has to stop making.
sc.render.engine = "BLENDER_EEVEE"
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = 900
sc.render.resolution_y = 1400
w = bpy.data.worlds.new("W")
w.use_nodes = True
bg = w.node_tree.nodes["Background"]
bg.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
bg.inputs[1].default_value = 1.6
sc.world = w

# ── FACING IS MEASURED, NOT ASSUMED ─────────────────────────────────────────
# Different generators emit different orientations: the Tripo H3.1 model came out 180 degrees
# from the Meshy one, so a fixed camera angle labelled its BACK as "front_000". The muzzle is the
# head's farthest horizontal excursion from the head's own centroid, which identifies the facing
# on any of them without trusting the exporter.
co_all = np.array([ (o.matrix_world @ v.co) for o in meshes for v in o.data.vertices ])
z = co_all[:, 2]
zlo, zhi = z.min(), z.max()
head = co_all[z > (zlo + 0.72 * (zhi - zlo))]
hc = head.mean(axis=0)
# THE EARS ARE THE TRAP, AND A HEIGHT BAND DOES NOT ESCAPE IT. Taking the head's farthest
# horizontal point finds an EAR — ears project further sideways than a muzzle projects forward —
# and restricting to the lower head band only worked on one of the two meshes, because the other
# has lower, droopier ears. Height cannot separate them reliably.
#
# ASYMMETRY can. Ears come in a symmetric pair, so along the ear axis the head reaches equally far
# in BOTH directions and the difference is ~0. A muzzle exists on one side only, so along the
# facing axis the forward reach exceeds the backward reach by the most. Sweep the circle and take
# the direction that maximises (reach forward - reach backward).
hxy = head[:, :2] - hc[:2]
best, face_ang = -1e9, 0.0
for deg in range(0, 360, 2):
    r = math.radians(deg)
    dirv = np.array([math.sin(r), -math.cos(r)])
    proj = hxy @ dirv
    score = proj.max() + proj.min()      # = reach_forward - reach_backward
    if score > best:
        best, face_ang = score, float(deg)
print(f"  facing MEASURED from the muzzle: {face_ang:.1f} deg")

cd = bpy.data.cameras.new("C"); cam = bpy.data.objects.new("C", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"; cd.ortho_scale = R * 1.15

for name, ang in [("front_000", 0), ("front34_045", 45), ("side_090", 90),
                  ("back34_135", 135), ("back_180", 180)]:
    a = math.radians(ang + face_ang)
    cam.location = (ctr.x + math.sin(a) * R * 4, ctr.y - math.cos(a) * R * 4, ctr.z)
    cam.rotation_euler = (math.radians(90), 0, a)
    sc.render.filepath = os.path.join(OUT, f"glb_{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"  wrote glb_{name}.png")

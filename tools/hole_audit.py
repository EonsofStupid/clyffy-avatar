"""Clay + backface audit: does the model have MISSING GEOMETRY, or is it just paint?

    blender -b --python tools/hole_audit.py -- <model.glb|.fbx|.blend> <out_dir> [steps]

Written 2026-08-05 because the textured DECIDE renders cannot answer that question: white fur on
a white background looks exactly like a hole, and a hole looks exactly like white fur. Textures
are stripped here on purpose. Front faces render mid grey; BACK faces render pure red. Red on
screen means the camera is seeing the inside of the surface, which only happens through a hole.

It also reports the numbers a render cannot show: boundary edges, non-manifold edges, and the
size of every loose shell, so "a third is missing" can be confirmed or refused with a count.
"""
import bpy, sys, os, math
import bmesh
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC = os.path.abspath(argv[0])
OUT = os.path.abspath(argv[1])
STEPS = int(argv[2]) if len(argv) > 2 else 8
os.makedirs(OUT, exist_ok=True)
TAG = os.path.splitext(os.path.basename(SRC))[0]

ext = os.path.splitext(SRC)[1].lower()
if ext == ".blend":
    bpy.ops.wm.open_mainfile(filepath=SRC)
else:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=SRC)
    elif ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=SRC)
    else:
        raise SystemExit(f"unsupported container: {ext}")

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
assert meshes, "no mesh found"
print(f"\n=== {TAG} ===")
print(f"mesh objects: {[o.name for o in meshes]}")

# ---- numbers first, per object -------------------------------------------------
for o in meshes:
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.verts.ensure_lookup_table()
    boundary = [e for e in bm.edges if len(e.link_faces) == 1]
    nonman = [e for e in bm.edges if len(e.link_faces) > 2]

    # loose shells: flood fill across faces
    seen = set()
    shells = []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, part = [f], []
        seen.add(f.index)
        while stack:
            cur = stack.pop()
            part.append(cur)
            for e in cur.edges:
                for nb in e.link_faces:
                    if nb.index not in seen:
                        seen.add(nb.index)
                        stack.append(nb)
        shells.append(len(part))
    shells.sort(reverse=True)

    # each boundary loop, with its size in world units — a "giant hole" is a big loop
    loops = []
    unvisited = {e.index: e for e in boundary}
    while unvisited:
        _, e0 = unvisited.popitem()
        loop = [e0]
        frontier = [e0]
        while frontier:
            e = frontier.pop()
            for v in e.verts:
                for e2 in v.link_edges:
                    if e2.index in unvisited:
                        del unvisited[e2.index]
                        loop.append(e2)
                        frontier.append(e2)
        pts = np.array([(o.matrix_world @ v.co)[:] for e in loop for v in e.verts])
        span = float(np.linalg.norm(pts.max(axis=0) - pts.min(axis=0)))
        loops.append((len(loop), span, pts.mean(axis=0)))
    loops.sort(key=lambda t: -t[1])

    print(f"\n  {o.name}: {len(bm.verts)} verts / {len(bm.faces)} faces")
    print(f"    boundary edges  {len(boundary)}")
    print(f"    non-manifold    {len(nonman)}")
    print(f"    shells          {len(shells)}  sizes(top8)={shells[:8]}")
    for n, span, c in loops[:8]:
        print(f"    hole loop: {n:5d} edges  span {span:.4f}  at ({c[0]:+.3f},{c[1]:+.3f},{c[2]:+.3f})")
    bm.free()

# ---- clay + backface render ----------------------------------------------------
mat = bpy.data.materials.new("CLAY_BACKFACE")
mat.use_nodes = True
nt = mat.node_tree
nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputMaterial")
mix = nt.nodes.new("ShaderNodeMixShader")
geo = nt.nodes.new("ShaderNodeNewGeometry")
front = nt.nodes.new("ShaderNodeBsdfDiffuse")
back = nt.nodes.new("ShaderNodeEmission")
front.inputs[0].default_value = (0.55, 0.55, 0.57, 1)
back.inputs[0].default_value = (1.0, 0.0, 0.0, 1)
back.inputs[1].default_value = 1.0
nt.links.new(geo.outputs["Backfacing"], mix.inputs[0])
nt.links.new(front.outputs[0], mix.inputs[1])
nt.links.new(back.outputs[0], mix.inputs[2])
nt.links.new(mix.outputs[0], out.inputs[0])
mat.use_backface_culling = False

for o in meshes:
    o.data.materials.clear()
    o.data.materials.append(mat)

co = np.array([(o.matrix_world @ v.co)[:] for o in meshes for v in o.data.vertices])
mn, mx = co.min(axis=0), co.max(axis=0)
ctr = Vector(((mn + mx) / 2).tolist())
R = float((mx - mn).max())

sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = 700
sc.render.resolution_y = 900
w = bpy.data.worlds.new("W"); w.use_nodes = True
# mid-blue world so a hole's red and the clay grey both stand off the background, and neither
# can be confused with white fur on white paper the way the textured sheet was
w.node_tree.nodes["Background"].inputs[0].default_value = (0.10, 0.14, 0.22, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 1.4
sc.world = w

cd = bpy.data.cameras.new("C"); cam = bpy.data.objects.new("C", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"; cd.ortho_scale = R * 1.15

step = 360 // STEPS
for i in range(STEPS):
    deg = i * step
    a = math.radians(deg)
    cam.location = (ctr.x + math.sin(a) * R * 3, ctr.y - math.cos(a) * R * 3, ctr.z)
    cam.rotation_euler = (math.radians(90), 0, a)
    sc.render.filepath = os.path.join(OUT, f"{TAG}_clay_{deg:03d}.png")
    bpy.ops.render.render(write_still=True)

cam.location = (ctr.x, ctr.y, ctr.z + R * 3)
cam.rotation_euler = (0, 0, 0)
sc.render.filepath = os.path.join(OUT, f"{TAG}_clay_top.png")
bpy.ops.render.render(write_still=True)
cam.location = (ctr.x, ctr.y, ctr.z - R * 3)
cam.rotation_euler = (math.radians(180), 0, 0)
sc.render.filepath = os.path.join(OUT, f"{TAG}_clay_bottom.png")
bpy.ops.render.render(write_still=True)
print(f"\n  wrote {STEPS} clay views + top + bottom to {OUT}")

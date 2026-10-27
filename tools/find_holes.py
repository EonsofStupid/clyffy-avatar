"""Locate every hole in the mesh, group boundary edges into loops, and mark them visually.

    blender -b --python tools/find_holes.py -- <model> <out_dir>

Reports each hole as a loop with its vertex count, physical size and anatomical position, then
renders the head with a red marker on every hole so they can be found by eye rather than trusted
from a number. A hole near the lip is what let the mouth cavity leak through the skin in the
previous build, so these get located BEFORE anything is cut.
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
if os.path.splitext(SRC)[1].lower() == ".fbx":
    bpy.ops.import_scene.fbx(filepath=SRC)
else:
    bpy.ops.import_scene.gltf(filepath=SRC)

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
ob = max(meshes, key=lambda o: len(o.data.vertices))
bm = bmesh.new(); bm.from_mesh(ob.data); bm.verts.ensure_lookup_table()

boundary = [e for e in bm.edges if len(e.link_faces) == 1]
print(f"\n{TAG}: {len(boundary)} boundary edges")

# group boundary edges into loops
adj = {}
for e in boundary:
    a, b = e.verts[0].index, e.verts[1].index
    adj.setdefault(a, set()).add(b)
    adj.setdefault(b, set()).add(a)
seen, loops = set(), []
for v in adj:
    if v in seen:
        continue
    stack, comp = [v], []
    while stack:
        x = stack.pop()
        if x in seen:
            continue
        seen.add(x); comp.append(x)
        stack.extend(adj[x])
    loops.append(comp)

co = np.array([v.co[:] for v in bm.verts])
z = co[:, 2]
zlo, zhi = z.min(), z.max()
head_lo = zlo + 0.70 * (zhi - zlo)
head = co[z > head_lo]
hc = head.mean(axis=0)
head_r = float(np.abs(head - hc).max())
# facing, by the asymmetry sweep (only used to name a side, never to label evidence)
hxy = head[:, :2] - hc[:2]
best, fa = -1e9, 0.0
for deg in range(0, 360, 2):
    r = math.radians(deg)
    d = np.array([math.sin(r), -math.cos(r)])
    p = hxy @ d
    if p.max() + p.min() > best:
        best, fa = p.max() + p.min(), float(deg)
fwd = np.array([math.sin(math.radians(fa)), -math.cos(math.radians(fa)), 0.0])
lat = np.array([-fwd[1], fwd[0], 0.0])

loops.sort(key=len, reverse=True)
print(f"{len(loops)} separate holes\n")
print(f"  {'#':>3} {'verts':>6} {'size':>8} {'z':>8} {'height%':>8} {'fwd':>8} {'lat':>8}  where")
marks = []
for i, comp in enumerate(loops):
    pts = co[np.array(comp)]
    c = pts.mean(axis=0)
    size = float(np.linalg.norm(pts - c, axis=1).max() * 2)
    hpct = 100 * (c[2] - zlo) / (zhi - zlo)
    f = float(c @ fwd - hc @ fwd)
    l = float(c @ lat - hc @ lat)
    where = "HEAD" if c[2] > head_lo else ("torso" if hpct > 45 else "lower body")
    if c[2] > head_lo:
        if f > head_r * 0.35:
            where = "HEAD front/muzzle"
        elif abs(l) > head_r * 0.45:
            where = "HEAD side (ear/horn)"
        elif f < -head_r * 0.3:
            where = "HEAD back"
        else:
            where = "HEAD top/mid"
    print(f"  {i:>3} {len(comp):>6} {size:>8.4f} {c[2]:>8.4f} {hpct:>7.1f}% {f:>8.4f} {l:>8.4f}  {where}")
    marks.append((c, size))

bm.free()

# ── mark the holes and render ────────────────────────────────────────────────
red = bpy.data.materials.new("hole"); red.use_nodes = True
nt = red.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
o = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission")
em.inputs["Color"].default_value = (1.0, 0.0, 0.1, 1.0)
em.inputs["Strength"].default_value = 3.0
nt.links.new(em.outputs["Emission"], o.inputs["Surface"])

for c, size in marks:
    bpy.ops.mesh.primitive_uv_sphere_add(radius=max(size * 0.9, head_r * 0.035),
                                         location=(float(c[0]), float(c[1]), float(c[2])))
    bpy.context.object.data.materials.append(red)

sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = 700; sc.render.resolution_y = 700
w = bpy.data.worlds.new("W"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 1.5
sc.world = w
cd = bpy.data.cameras.new("C"); cam = bpy.data.objects.new("C", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"; cd.ortho_scale = head_r * 2.7
ctr = Vector((float(hc[0]), float(hc[1]), float(hc[2])))
R = float(zhi - zlo) * 3
for deg in (0, 90, 180, 270):
    a = math.radians(deg)
    cam.location = (ctr.x + math.sin(a) * R, ctr.y - math.cos(a) * R, ctr.z)
    cam.rotation_euler = (math.radians(90), 0, a)
    sc.render.filepath = os.path.join(OUT, f"{TAG}_holes_{deg:03d}.png")
    bpy.ops.render.render(write_still=True)
print(f"\nwrote hole-marked renders to {OUT}")

"""CP6 — the EYE REGION, pass 1: concentric lid rings around the approved CP1 eye ring.

    blender -b --python tools/retopo_eyes.py -- work/RETOPO_clyffy.blend

The CP1 eye-ring guide (closed 10-vert wire, centre ~(0.047, -0.135, 0.857)) becomes the
APERTURE RIM — the lid margin. Two rings grow radially outward from it along the scaffold
surface, following the sculpted lids. The aperture stays open (the eyeball is a separate
object later, same as teeth/tongue). Right side only; Mirror(X) makes the left.

NO STITCHING in this pass — the annulus-to-nose-patch weld happens after the operator
approves ring placement. The gap to close later: ring bottom z 0.834 -> nose top z 0.824.

Rerunnable: new verts tagged in vertex group "cp6_eyes"; a rerun deletes them first.
Earned rule applied: smoothing near a patch boundary PINS the neighbouring patch's verts —
here the guide ring itself is never moved.
"""
import bpy, bmesh, sys, os, math
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
bpy.ops.wm.open_mainfile(filepath=BLEND)
scaf = bpy.data.objects["SCAFFOLD"]
rt = bpy.data.objects["retopo_head"]
bpy.context.view_layer.objects.active = rt
if rt.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")

RING_OFFSETS = (0.009, 0.018)


def snap(p, offset=0.0025):
    ok, loc, nor, _ = scaf.closest_point_on_mesh(Vector(p))
    return (loc + nor * offset) if ok else Vector(p)


def snorm(p):
    ok, loc, nor, _ = scaf.closest_point_on_mesh(Vector(p))
    return nor if ok else Vector((0, -1, 0))


# ---- rerun cleanup ------------------------------------------------------------------------------
vg = rt.vertex_groups.get("cp6_eyes")
if vg is None:
    vg = rt.vertex_groups.new(name="cp6_eyes")
gi = vg.index

bm = bmesh.new(); bm.from_mesh(rt.data)
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
dl = bm.verts.layers.deform.verify()
old = [v for v in bm.verts if gi in v[dl]]
if old:
    bmesh.ops.delete(bm, geom=old, context="VERTS")
    print(f"cleared previous CP6 pass: {len(old)} verts removed")

# ---- the approved eye ring (CP1 guide, closed 10-vert wire) ------------------------------------
ring = [v for v in bm.verts if not v.link_faces
        and 0.01 < v.co.x < 0.08 and -0.16 < v.co.y < -0.12 and 0.82 < v.co.z < 0.90]
assert all(len(v.link_edges) == 2 for v in ring), "eye guide is not a clean closed ring"
# order by walking the loop
start = ring[0]
ordered = [start]
prev = None
while True:
    nxt = None
    for e in ordered[-1].link_edges:
        o = e.other_vert(ordered[-1])
        if o is not prev and o in ring:
            nxt = o
            break
    if nxt is None or nxt is start:
        break
    prev = ordered[-1]
    ordered.append(nxt)
assert len(ordered) == len(ring), "eye ring walk did not close"
centre = sum((v.co for v in ordered), Vector()) / len(ordered)
print(f"eye ring: {len(ordered)} verts, centre ({centre.x:+.4f},{centre.y:+.4f},{centre.z:.4f})")

# make the winding consistent (so band quads face outward the same way every run)
n_avg = sum((snorm(v.co) for v in ordered), Vector()).normalized()
area = Vector((0, 0, 0))
for i in range(len(ordered)):
    a = ordered[i].co - centre
    b = ordered[(i + 1) % len(ordered)].co - centre
    area += a.cross(b)
if area.dot(n_avg) < 0:
    ordered.reverse()


def ring_smooth(ring_pts, passes=2, blend=0.5):
    for _ in range(passes):
        cos = [Vector(p) for p in ring_pts]
        ring_pts = [cos[i].lerp((cos[i - 1] + cos[(i + 1) % len(cos)]) / 2, blend)
                    for i in range(len(cos))]
    return ring_pts


# ---- concentric rings outward ------------------------------------------------------------------
rings_v = [ordered]
for d in RING_OFFSETS:
    pts = []
    for v in ordered:
        n = snorm(v.co)
        radial = (v.co - centre)
        radial = (radial - n * radial.dot(n)).normalized()   # outward, in the surface
        pts.append(snap(v.co + radial * d))
    pts = ring_smooth(pts)
    pts = [snap(p) for p in pts]
    vs = [bm.verts.new(p) for p in pts]
    rings_v.append(vs)

new_verts = [v for r in rings_v[1:] for v in r]
n = len(ordered)
for a, b in zip(rings_v, rings_v[1:]):
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
print(f"eye annulus: {len(RING_OFFSETS)} bands, {len(RING_OFFSETS) * n} quads")

for v in new_verts:
    v[dl][gi] = 1.0

bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(rt.data)
bm.free()
nq = sum(1 for p in rt.data.polygons if len(p.vertices) == 4)
nt = sum(1 for p in rt.data.polygons if len(p.vertices) == 3)
print(f"after CP6 pass 1: {len(rt.data.polygons)} faces ({nq} quads, {nt} tris)")
bpy.ops.wm.save_as_mainfile(filepath=BLEND)

# ---- renders -----------------------------------------------------------------------------------
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"; sh.color_type = "OBJECT"
sh.show_cavity = True; sh.cavity_type = "BOTH"
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = sc.render.resolution_y = 900
scaf.color = (0.60, 0.60, 0.62, 1.0)
rt.color = (0.95, 0.35, 0.10, 1.0)
rt.show_wire = True
rt.show_all_edges = True
for o in bpy.data.objects:
    if o.name.startswith("vis_") or o.type == "EMPTY":
        o.hide_render = True
w = bpy.data.worlds.new("W6"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.40, 0.44, 0.41, 1)
sc.world = w
ctr = Vector((0.0, -0.16, 0.83))
cd = bpy.data.cameras.new("C6"); cam = bpy.data.objects.new("C6", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"; cd.ortho_scale = 0.42
cd.clip_start = 0.001; cd.clip_end = 100.0
OUT = os.path.join(os.path.dirname(BLEND), "retopo_cp6")
os.makedirs(OUT, exist_ok=True)
for deg in (0, 30):
    a = math.radians(deg)
    cam.location = (ctr.x + math.sin(a) * 2, ctr.y - math.cos(a) * 2, ctr.z + 0.01)
    cam.rotation_euler = (math.radians(89), 0, a)
    sc.render.filepath = os.path.join(OUT, f"cp6_{deg:03d}.png")
    bpy.ops.render.render(write_still=True)
# closeup on the right eye
cd.ortho_scale = 0.16
ctr_eye = Vector((0.047, -0.135, 0.850))
cam.location = (ctr_eye.x + math.sin(math.radians(15)) * 2,
                ctr_eye.y - math.cos(math.radians(15)) * 2, ctr_eye.z)
cam.rotation_euler = (math.radians(89), 0, math.radians(15))
sc.render.filepath = os.path.join(OUT, "cp6_eye_closeup.png")
bpy.ops.render.render(write_still=True)
# solo
scaf.hide_render = True
cd.ortho_scale = 0.42
cam.location = (ctr.x, ctr.y - 2, ctr.z + 0.01)
cam.rotation_euler = (math.radians(89), 0, 0)
sc.render.filepath = os.path.join(OUT, "cp6_solo_000.png")
bpy.ops.render.render(write_still=True)
scaf.hide_render = False
print(f"renders -> {OUT}")

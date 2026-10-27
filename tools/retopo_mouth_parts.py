"""CP10 — the MOUTH INTERIOR: teeth as continuous cream BANDS, plus a tongue.

    blender -b --python tools/retopo_mouth_parts.py -- work/RETOPO_clyffy.blend

Separate objects, per the standing decision — the shell is never carved to make a mouth (that
route is a research problem; see STATUS). They are built on the OPERATOR-APPROVED lip seam, the
same 17 points `tools/retopo_lips.py` holds as the rebuild spec, so the parts and the lips share
one source of truth.

Teeth are CONTINUOUS BANDS, not individual teeth — the operator's call, and it is also what reads
correctly at avatar scale.

The seam is still a welded LINE (the split happens at rig time), so nothing here can be checked
against an open pose yet. What CAN be checked now, and is: every part vertex must sit INSIDE the
head shell. A tooth poking through the chin is invisible in a closed-mouth render and obvious the
moment the jaw drops.
"""
import bpy, bmesh, sys, os, math
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
bpy.ops.wm.open_mainfile(filepath=BLEND)
scaf = bpy.data.objects["SCAFFOLD"]
rt = bpy.data.objects["retopo_head"]

# the operator-approved seam (tools/retopo_lips.py APPROVED_SEAM)
SEAM = [(0.0000, -0.2876, 0.7260), (0.0090, -0.2871, 0.7240), (0.0190, -0.2856, 0.7220),
        (0.0280, -0.2831, 0.7200), (0.0370, -0.2792, 0.7150), (0.0430, -0.2748, 0.7090),
        (0.0510, -0.2678, 0.7090), (0.0560, -0.2628, 0.7110), (0.0610, -0.2571, 0.7100),
        (0.0660, -0.2503, 0.7110), (0.0700, -0.2436, 0.7150), (0.0720, -0.2396, 0.7140),
        (0.0770, -0.2280, 0.7180), (0.0780, -0.2249, 0.7200), (0.0820, -0.2137, 0.7230),
        (0.0830, -0.2101, 0.7240), (0.0850, -0.2034, 0.7283)]
S = [Vector(p) for p in SEAM]

BACK = 0.010        # how far behind the lip line the tooth face sits
DEPTH = 0.026       # how far back the band runs
UP = 0.013          # upper band height (root above the biting edge)
DOWN = 0.013        # lower band depth


def inward(i):
    """into the head at seam point i: opposite the scaffold normal there"""
    ok, _, nor, _ = scaf.closest_point_on_mesh(S[i])
    n = -nor if ok else Vector((0, 1, 0))
    n = Vector((n.x, n.y, 0.0))
    return n.normalized() if n.length > 1e-6 else Vector((0, 1, 0))


# The bands run along a SMOOTHED copy of the seam. The approved seam is a hand-placed line whose
# small variations are fine on a lip but read as a wavy tooth edge, and the seat-inside pass
# amplifies them.
SM = [v.copy() for v in S]
for _ in range(3):
    SM = [SM[0]] + [SM[i - 1] * 0.25 + SM[i] * 0.5 + SM[i + 1] * 0.25
                    for i in range(1, len(SM) - 1)] + [SM[-1]]

# Teeth STOP SHORT of the mouth corner and taper into it — they flared outward when carried at
# full height to the last seam point, the same defect the mouth rings had at CP3.
END = 0.82


def taper(i):
    t = i / (len(SM) - 1) / END
    return max(0.0, 1.0 - t ** 3) if t <= 1.0 else 0.0


NCOL = int(len(SM) * END) + 1


def make(name, rows, colour):
    """rows: list of (vertical offset, inward offset); builds a band swept along the seam"""
    bm = bmesh.new()
    grid = []
    for dz, back in rows:
        line = []
        for i in range(NCOL):
            p = SM[i] + inward(i) * back + Vector((0, 0, dz * taper(i)))
            line.append(bm.verts.new(p))
        grid.append(line)
    for a, b in zip(grid, grid[1:]):
        for i in range(NCOL - 1):
            bm.faces.new((a[i], a[i + 1], b[i + 1], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    m = ob.modifiers.new("Mirror", "MIRROR")
    m.use_axis[0] = True
    m.use_clip = True
    ob.color = colour
    return ob


# upper band hangs DOWN from the palate; lower band rises from the floor
upper = make("clyffy_teeth_upper", [(UP, BACK), (0.001, BACK), (0.001, BACK + DEPTH)],
             (0.98, 0.96, 0.86, 1.0))
lower = make("clyffy_teeth_lower", [(-DOWN, BACK), (-0.001, BACK), (-0.001, BACK + DEPTH)],
             (0.98, 0.96, 0.86, 1.0))

# tongue: a flattened dome on the mouth floor, behind the lower band
mid = S[len(S) // 2]
TC = Vector((0.0, mid.y + BACK + 0.030, mid.z - 0.008))
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=1.0)
for v in bm.verts:
    v.co = Vector((v.co.x * 0.040, v.co.y * 0.052, v.co.z * 0.009)) + TC
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
old = bpy.data.objects.get("clyffy_tongue")
if old:
    bpy.data.objects.remove(old, do_unlink=True)
me = bpy.data.meshes.new("clyffy_tongue")
bm.to_mesh(me)
bm.free()
tongue = bpy.data.objects.new("clyffy_tongue", me)
bpy.context.scene.collection.objects.link(tongue)
tongue.color = (0.90, 0.45, 0.50, 1.0)

# ---- seat the parts INSIDE the head --------------------------------------------------------------
# A fixed inward offset is not enough: under the chin and out at the corners the skin curves in, so
# a constant-height band pokes out (measured: 27 verts on the lower band, worst 0.0093). Push every
# offending vertex back along the local surface normal until it clears by MARGIN. Cheaper and more
# honest than hand-tuning BACK/UP/DOWN until a render happens to look clean.
MARGIN = 0.002


def seat(ob):
    moved = 0
    for v in ob.data.vertices:
        p = Vector(v.co)
        ok, loc, nor, _ = scaf.closest_point_on_mesh(p)
        if not ok:
            continue
        d = (p - loc).dot(nor)
        if d > -MARGIN:
            v.co = p - nor * (d + MARGIN)
            moved += 1
    return moved


def smooth_bands(ob, rows, ncol, w=0.4):
    """smooth ALONG each row of the band; the seating pass leaves a sawtooth behind it"""
    co = [Vector(v.co) for v in ob.data.vertices]
    for r in range(rows):
        for i in range(1, ncol - 1):
            k = r * ncol + i
            co[k] = co[k].lerp((co[k - 1] + co[k + 1]) / 2, w)
    for v, c in zip(ob.data.vertices, co):
        v.co = c


# Seating and smoothing FIGHT each other — seating pushes a vert in, smoothing pulls it back
# toward its neighbours' line. Alternate them so they converge instead.
for ob, nrows in ((upper, 3), (lower, 3)):
    for _ in range(3):
        seat(ob)
        smooth_bands(ob, nrows, NCOL)
    moved = seat(ob)
    print(f"  {ob.name}: smoothed + seated, {moved} verts moved on the last pass")
print(f"  clyffy_tongue: {seat(tongue)} verts seated")

# ---- gate: every part vertex must be INSIDE the head shell --------------------------------------
print()
outside_total = 0
for ob in (upper, lower, tongue):
    bad, worst = 0, 0.0
    for v in ob.data.vertices:
        p = ob.matrix_world @ v.co
        ok, loc, nor, _ = scaf.closest_point_on_mesh(p)
        if not ok:
            continue
        d = (p - loc).dot(nor)          # positive = outside the surface
        if d > 0.0005:
            bad += 1
            worst = max(worst, d)
    outside_total += bad
    nq = sum(1 for f in ob.data.polygons if len(f.vertices) == 4)
    flag = f"!! {bad} verts OUTSIDE (max {worst:.4f})" if bad else "all verts inside the head"
    print(f"{ob.name}: {len(ob.data.polygons)} faces ({nq} quads) — {flag}")
print(f"\nmouth parts: {'CLEAN' if outside_total == 0 else str(outside_total) + ' verts poke through'}")
bpy.ops.wm.save_as_mainfile(filepath=BLEND)

# ---- renders: the parts alone, and a mid-sagittal section ---------------------------------------
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"; sh.color_type = "OBJECT"
sh.show_cavity = True; sh.cavity_type = "BOTH"
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = sc.render.resolution_y = 900
rt.color = (0.95, 0.45, 0.15, 1.0)
for x in bpy.data.objects:
    if x.name.startswith("vis_") or x.type == "EMPTY":
        x.hide_render = True
w = bpy.data.worlds.new("W10"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.40, 0.44, 0.41, 1)
sc.world = w
ctr = Vector((0.0, -0.24, 0.72))
cd = bpy.data.cameras.new("C10"); cam = bpy.data.objects.new("C10", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"; cd.ortho_scale = 0.26
cd.clip_start = 0.001; cd.clip_end = 100.0
OUT = os.path.join(os.path.dirname(BLEND), "retopo_mouth")
os.makedirs(OUT, exist_ok=True)
scaf.hide_render = True
rt.hide_render = True
for deg in (0, 40):
    a = math.radians(deg)
    cam.location = (ctr.x + math.sin(a) * 2, ctr.y - math.cos(a) * 2, ctr.z + 0.01)
    cam.rotation_euler = (math.radians(89), 0, a)
    sc.render.filepath = os.path.join(OUT, f"parts_{deg:03d}.png")
    bpy.ops.render.render(write_still=True)
# section: clip the camera through the midline so the parts show inside the head
rt.hide_render = False
cam.location = (2.0, ctr.y, ctr.z)
cam.rotation_euler = (math.radians(90), 0, math.radians(90))
cd.ortho_scale = 0.30
cd.clip_start = 2.0
sc.render.filepath = os.path.join(OUT, "section.png")
bpy.ops.render.render(write_still=True)
scaf.hide_render = False
print(f"renders -> {OUT}")

"""THE GATE: is any interior geometry visible from outside, at rest?

    blender -b --python tools/cavity_gate.py -- <in.blend> <out_dir> <fwd_deg> [tag]

exit 0 = PASS (nothing interior is visible)   exit 1 = FAIL

WHY THIS EXISTS. In the previous build `lip_seal`'s containment check and `pose_check` were
both GREEN for weeks while the mouth cavity was plainly poking through the lip in the shipped
asset. Neither of them ever asked this question. They checked distances and vertex counts,
which is not the same thing as looking.

HOW IT ASKS. Every interior face is given a pure EMISSIVE MAGENTA — emissive so no lighting
choice can hide it, magenta because nothing on this character is magenta (skin is white and
chocolate brown, the pad and lip are pink, teeth are cream, the cavity is dark red). Then the
head is rendered across the front hemisphere and magenta pixels are counted. Any magenta
pixel in any view is a FAIL.

WHAT COUNTS AS INTERIOR. A face whose material name starts with `inner_`, or any face of an
object whose name starts with `inner_`. That is the whole contract — the cavity, teeth and
tongue carry `inner_` materials, so they are covered automatically as they are built.

THE VIEWS. 9 azimuths x 5 elevations = 45, centred on the supplied forward. Elevations run
down to -40 deg on purpose: looking UP into a mouth is where a leak shows first, and a gate
that only ever looks straight ahead would have passed the old build's defect too.

REST POSE IS FORCED and every shape key is zeroed before rendering. A posed or shape-keyed
render answers a different question than the one this gate is for.

BOTH FACES RENDER. The magenta material leaves `use_backface_culling` off deliberately, so a
cavity wall seen from behind still reports. Culling would let an inward-facing leak through.

MEASURED SENSITIVITY (2026-08-04, `tools/_gate_probe.py`, 8mm probe at the lip, 900px):

    protrusion          % of body height     magenta px      verdict
    0.0080 (half out)         0.82%              10741       FAIL, seen in all 45 views
    0.0020                    0.20%               2150       FAIL
    0.0010                    0.10%                968       FAIL
    0.0005                    0.05%                391       FAIL
    0.0002                    0.02%                127       FAIL
    0.0000 (tangent)          0.00%                  5       FAIL  <- THE NOISE FLOOR
    buried 3 radii inside    -1.64%                  0       PASS

**The floor is 5 px at exact tangency**, from micro-interpenetration between two faceted
surfaces touching at a point. That number matters for the split in Phase 2, which produces
coincident rim chains: if a healthy split reports a handful of pixels, it is this floor and
not a leak. The pass criterion stays at ZERO anyway. A nonzero count gets investigated, never
absorbed by raising a threshold — that is how the previous build's gates stayed green.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hardfail  # noqa: F401  -- unhandled exceptions must exit non-zero
import bpy, sys, os, math
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = os.path.abspath(argv[0]), os.path.abspath(argv[1])
FWD_DEG = float(argv[2])
TAG = argv[3] if len(argv) > 3 else os.path.splitext(os.path.basename(SRC))[0]
os.makedirs(OUT, exist_ok=True)

RES = 900
AZ = [-80, -60, -40, -20, 0, 20, 40, 60, 80]
EL = [-40, -25, -10, 0, 15]
INNER = "inner_"

bpy.ops.wm.open_mainfile(filepath=SRC)
if bpy.context.object and bpy.context.object.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")

# ------------------------------------------------------------------ rest pose, keys zeroed
for arm in [o for o in bpy.data.objects if o.type == "ARMATURE"]:
    arm.data.pose_position = "REST"
    print(f"  armature {arm.name!r} -> REST")
nkeys = 0
for o in [o for o in bpy.data.objects if o.type == "MESH"]:
    if o.data.shape_keys:
        for kb in o.data.shape_keys.key_blocks:
            if kb.value != 0.0:
                kb.value = 0.0
                nkeys += 1
if nkeys:
    print(f"  zeroed {nkeys} non-zero shape key(s)")

meshes = [o for o in bpy.data.objects if o.type == "MESH" and not o.hide_render]
if not meshes:
    print("FAIL: no renderable mesh")
    sys.exit(1)

# ------------------------------------------------------------------ classify interior faces
magenta = bpy.data.materials.new("GATE_inner")
magenta.use_nodes = True
nt = magenta.node_tree
for n in list(nt.nodes):
    if n.type != "OUTPUT_MATERIAL":
        nt.nodes.remove(n)
e = nt.nodes.new("ShaderNodeEmission")
e.inputs["Color"].default_value = (1.0, 0.0, 1.0, 1.0)
e.inputs["Strength"].default_value = 1.0
nt.links.new(e.outputs["Emission"], nt.nodes["Material Output"].inputs["Surface"])

neutral = bpy.data.materials.new("GATE_outer")
neutral.use_nodes = True
nt2 = neutral.node_tree
for n in list(nt2.nodes):
    if n.type != "OUTPUT_MATERIAL":
        nt2.nodes.remove(n)
e2 = nt2.nodes.new("ShaderNodeEmission")
# mid grey, and deliberately NOT magenta-ish: equal channels can never satisfy the test below
e2.inputs["Color"].default_value = (0.45, 0.45, 0.45, 1.0)
e2.inputs["Strength"].default_value = 1.0
nt2.links.new(e2.outputs["Emission"], nt2.nodes["Material Output"].inputs["Surface"])

inner_faces = 0
seen_mats = set()
for o in meshes:
    me = o.data
    obj_is_inner = o.name.startswith(INNER)
    was = [m.name if m else "" for m in me.materials]
    seen_mats.update(n for n in was if n)
    inner_slots = {i for i, n in enumerate(was) if n.startswith(INNER)}

    # SNAPSHOT THE INDICES FIRST. `materials.clear()` resets every polygon's material_index,
    # so reading them afterwards yields all zeros — the gate then marks NOTHING and reports a
    # cheerful PASS. It did exactly that on the first cavity build. The earlier proof did not
    # catch it because the probe was a separate OBJECT named `inner_probe`, which takes the
    # `obj_is_inner` path and never touches material indices at all.
    idx = np.empty(len(me.polygons), dtype=np.int32)
    me.polygons.foreach_get("material_index", idx)

    me.materials.clear()
    me.materials.append(neutral)   # slot 0
    me.materials.append(magenta)   # slot 1
    new_idx = np.zeros(len(me.polygons), dtype=np.int32)
    if obj_is_inner:
        new_idx[:] = 1
    elif inner_slots:
        new_idx[np.isin(idx, list(inner_slots))] = 1
    me.polygons.foreach_set("material_index", new_idx)
    me.update()
    inner_faces += int((new_idx == 1).sum())
print(f"  materials in file: {sorted(seen_mats)}")
print(f"  interior faces marked: {inner_faces}")
if inner_faces == 0:
    print("  NOTE: no interior geometry exists yet in this file. The gate can still be run —"
          " it simply has nothing to catch, which is why it is proven against probes first.")

# ------------------------------------------------------------------ frame the head
co = np.array([(o.matrix_world @ v.co)[:] for o in meshes for v in o.data.vertices])
z = co[:, 2]; zlo, zhi = float(z.min()), float(z.max()); H = zhi - zlo
head = co[z > zlo + 0.70 * H]
hc = head.mean(axis=0)
head_r = float(np.abs(head - hc).max())

sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = RES
sc.render.resolution_y = RES
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA"
try:
    sc.eevee.taa_render_samples = 16
except Exception:
    pass
w = bpy.data.worlds.new("W"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
sc.world = w

cd = bpy.data.cameras.new("C"); cam = bpy.data.objects.new("C", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"
cd.ortho_scale = head_r * 2.4
R = H * 3


def count_magenta(path):
    """R and B high, G low. Antialiased edge pixels blend toward grey and still trip this,
    which is intended: partially visible is visible."""
    img = bpy.data.images.load(path)
    px = np.array(img.pixels[:], dtype=np.float32)
    bpy.data.images.remove(img)
    px = px.reshape(-1, 4)
    m = (px[:, 0] > 0.60) & (px[:, 2] > 0.60) & (px[:, 1] < 0.30)
    return int(m.sum()), m.reshape(RES, RES)


print(f"\ngate: {TAG}   {len(AZ)}x{len(EL)} = {len(AZ)*len(EL)} views, "
      f"azimuth {FWD_DEG:+.0f}{AZ[0]:+d}..{AZ[-1]:+d}, elevation {EL[0]:+d}..{EL[-1]:+d}")
total = 0
worst = (0, None, None)
rows = []
for el in EL:
    er = math.radians(el)
    for dz in AZ:
        az = FWD_DEG + dz
        ar = math.radians(az)
        cam.location = (hc[0] + math.cos(er) * math.sin(ar) * R,
                        hc[1] - math.cos(er) * math.cos(ar) * R,
                        hc[2] + math.sin(er) * R)
        cam.rotation_euler = (math.radians(90.0 - el), 0.0, ar)
        name = f"{TAG}_az{dz:+03d}_el{el:+03d}.png"
        path = os.path.join(OUT, name)
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        n, mask = count_magenta(path)
        total += n
        rows.append((dz, el, n))
        if n > worst[0]:
            worst = (n, name, mask)
        if n == 0:
            os.remove(path)          # keep only the views that saw something

print("\n  magenta pixel count by view (rows = elevation, cols = azimuth offset):")
print("        " + "".join(f"{d:>7d}" for d in AZ))
for el in EL:
    line = f"  el{el:+04d}"
    for dz in AZ:
        n = next(r[2] for r in rows if r[0] == dz and r[1] == el)
        line += f"{n:>7d}"
    print(line)

print(f"\n  total magenta pixels across all views: {total}")
if total == 0:
    print(f"  PASS — no interior geometry is visible from outside at rest ({TAG})")
    sys.exit(0)

n, name, mask = worst
ys, xs = np.where(mask)
# image rows are bottom-up out of Blender; report in image terms and say so
print(f"  worst view {name}: {n} px, bounding box "
      f"x {xs.min()}..{xs.max()}  y {ys.min()}..{ys.max()} (y measured from the BOTTOM)")
print(f"  FAIL — interior geometry is visible from outside at rest ({TAG})")
print(f"  offending renders kept in {OUT}")
sys.exit(1)

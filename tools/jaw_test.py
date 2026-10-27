"""Open the jaw, render it, and gate what opening reveals.

    blender -b --python tools/jaw_test.py -- <rig.blend> <out_dir> <fwd_deg> [angle_deg]

THREE THINGS ARE CHECKED, because "it looks open" is not a result:

  SEE-THROUGH   With the mouth open you must not be able to see the BACKGROUND through the
                head. Rendered against a saturated blue, any blue pixel a flood fill from the
                image border cannot reach is enclosed by the character.

                RESTRICTED TO THE MOUTH REGION, and that restriction is load-bearing rather
                than convenient. Enclosed background also occurs where a horn or an ear meets
                the skull — you genuinely can see sky through the notch between a horn and the
                head, and a whole-silhouette test flags that as a puncture. It did: 25 px, one
                of them traced to z=+0.422, 93.3% of body height, which is between the horns.
                The count over the whole frame is still reported, as information.

  APERTURE      Measured on the POSED mesh (through the depsgraph, not the rest data), as the
                gap between the upper and lower rim at the midline.

  TOOTH REVEAL  The previous build shipped a mouth that read TOOTHLESS: a flat shared bite
                plane put the upper crown level with the lip rim, so opening revealed 0.0007 of
                tooth. That number is the reason overbite and overjet exist in mouth_parts.py,
                so it is measured here rather than assumed.
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
ANGLE = float(argv[3]) if len(argv) > 3 else 22.0
RES_ARG = int(argv[4]) if len(argv) > 4 else 900
RES = RES_ARG
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=SRC)
ob = max([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
me = ob.data
co0 = np.array([v.co[:] for v in me.vertices])
z = co0[:, 2]; zlo, zhi = float(z.min()), float(z.max()); H = zhi - zlo

a = math.radians(FWD_DEG)
fwd = np.array([math.sin(a), -math.cos(a), 0.0])
lat = np.array([-fwd[1], fwd[0], 0.0])

# ------------------------------------------------------------------ pose
rig.data.pose_position = "POSE"
pb = rig.pose.bones["jaw"]
bone = rig.data.bones["jaw"]
# rotate about the WORLD lateral axis through the bone head, expressed in bone space so the
# bone's own roll cannot quietly change the axis
axis_bone = bone.matrix_local.to_3x3().inverted() @ Vector(tuple(float(v) for v in lat))
pb.rotation_mode = "QUATERNION"
pb.rotation_quaternion = Quaternion(axis_bone.normalized(), math.radians(ANGLE))
bpy.context.view_layer.update()
print(f"jaw opened {ANGLE:.1f} deg about the lateral axis at the hinge")

dg = bpy.context.evaluated_depsgraph_get()
ev = ob.evaluated_get(dg)
pm = ev.to_mesh()
co1 = np.array([v.co[:] for v in pm.vertices])
print(f"posed mesh: {len(co1)} verts (rest {len(co0)})")


def gidx(name):
    g = ob.vertex_groups[name].index
    return np.array([v.index for v in me.vertices if any(x.group == g for x in v.groups)],
                    dtype=int)


rim_lo, rim_up = gidx("op_rim_lower"), gidx("op_rim_upper")
t_up, t_lo = gidx("op_teeth_upper"), gidx("op_teeth_lower")

# ------------------------------------------------------------------ aperture, on the POSED mesh
def midline(idx, tol=0.012):
    l = co0[idx] @ lat
    return idx[np.abs(l - np.median(co0[idx] @ lat)) < tol] if False else idx[np.abs(l) < tol]


mu, ml = midline(rim_up), midline(rim_lo)
assert len(mu) and len(ml), "no midline rim vertices found"
ap_rest = float(co0[mu][:, 2].mean() - co0[ml][:, 2].mean())
ap_open = float(co1[mu][:, 2].mean() - co1[ml][:, 2].mean())
print(f"\naperture at the midline ({len(mu)} upper / {len(ml)} lower rim verts):")
print(f"  rest {ap_rest:+.5f}   open {ap_open:+.5f}   "
      f"= {abs(ap_open)/H*100:.2f}% of body height")
seam_w = 0.1597       # measured seam width, from the approved seam
print(f"  aperture / mouth width = {abs(ap_open)/seam_w:.3f}  "
      f"(modelsheet_open reads about 0.85)")

# ------------------------------------------------------------------ tooth reveal
up_crown = float(co1[t_up][:, 2].min())
up_lip = float(co1[mu][:, 2].mean())
lo_crown = float(co1[t_lo][:, 2].max())
lo_lip = float(co1[ml][:, 2].mean())
print(f"\ntooth reveal with the jaw open:")
print(f"  upper crown {up_lip - up_crown:+.5f} below the upper lip "
      f"({(up_lip-up_crown)/H*100:.2f}% of body height)")
print(f"  lower crown {lo_crown - lo_lip:+.5f} above the lower lip "
      f"({(lo_crown-lo_lip)/H*100:.2f}% of body height)")
print(f"  (the old build revealed 0.00070 and read toothless)")
ev.to_mesh_clear()

# ------------------------------------------------------------------ renders
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = sc.render.resolution_y = RES
w = bpy.data.worlds.new("W"); w.use_nodes = True
sc.world = w
bgn = w.node_tree.nodes["Background"]
cd = bpy.data.cameras.new("C"); cam = bpy.data.objects.new("C", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"
head = co0[z > zlo + 0.70 * H]
hc = head.mean(axis=0)
head_r = float(np.abs(head - hc).max())
cd.ortho_scale = head_r * 2.3
R = H * 3


def shoot(tag, az, el):
    ar, er = math.radians(az), math.radians(el)
    cam.location = (hc[0] + math.cos(er) * math.sin(ar) * R,
                    hc[1] - math.cos(er) * math.cos(ar) * R,
                    hc[2] + math.sin(er) * R)
    cam.rotation_euler = (math.radians(90.0 - el), 0.0, ar)
    p = os.path.join(OUT, f"{tag}.png")
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    return p


bgn.inputs[0].default_value = (1, 1, 1, 1)
bgn.inputs[1].default_value = 1.6
for tag, az, el in (("open_front", FWD_DEG, 0), ("open_34", FWD_DEG - 35, 6),
                    ("open_side", FWD_DEG - 90, 0), ("open_low", FWD_DEG, -25)):
    shoot(tag, az, el)
print(f"\nwrote textured views to {OUT}")

# ------------------------------------------------------------------ SEE-THROUGH gate
orig = [m for m in me.materials]
flat = bpy.data.materials.new("SEETHRU_body")
flat.use_nodes = True
nt = flat.node_tree
for n in list(nt.nodes):
    if n.type != "OUTPUT_MATERIAL":
        nt.nodes.remove(n)
e = nt.nodes.new("ShaderNodeEmission")
e.inputs["Color"].default_value = (0.5, 0.5, 0.5, 1.0)
nt.links.new(e.outputs["Emission"], nt.nodes["Material Output"].inputs["Surface"])
me.materials.clear(); me.materials.append(flat)
mi = np.zeros(len(me.polygons), dtype=np.int32)
me.polygons.foreach_set("material_index", mi)
bgn.inputs[0].default_value = (0.0, 0.0, 1.0, 1.0)
bgn.inputs[1].default_value = 1.0

# WHERE an enclosed pixel actually IS, in 3D — not which 2D box it fell in. A padded
# screen-space box around the mouth still swept in the forelock at 93-96% of body height when
# the camera looks down, and those pixels are the horn/forelock notch: real geometry you can
# genuinely see sky through. Each enclosed pixel is instead traced back to the nearest posed
# vertex, and counted only if that vertex is near the mouth rim.
rim_pts = co1[np.concatenate([rim_up, rim_lo])]
MOUTH_R = 0.06


def localise(enclosed, az, el):
    """Return (in_mouth, elsewhere) counts for the enclosed background pixels."""
    ys, xs = np.where(enclosed)
    if len(ys) == 0:
        return 0, 0
    ar, er = math.radians(az), math.radians(el)
    cpos = np.array([hc[0] + math.cos(er) * math.sin(ar) * R,
                     hc[1] - math.cos(er) * math.cos(ar) * R,
                     hc[2] + math.sin(er) * R])
    lk = hc - cpos; lk = lk / np.linalg.norm(lk)
    rgt = np.cross(lk, [0, 0, 1.0]); rgt = rgt / np.linalg.norm(rgt)
    upv = np.cross(rgt, lk)
    near = 0
    for k in range(len(ys)):
        sx = (xs[k] + 0.5 - RES / 2.0) / RES * cd.ortho_scale
        sy = -(ys[k] + 0.5 - RES / 2.0) / RES * cd.ortho_scale
        o = cpos + rgt * sx + upv * sy
        d = co1 - o
        t = d @ lk
        perp = np.linalg.norm(d - np.outer(t, lk), axis=1)
        j = int(np.argmin(perp))
        if float(np.linalg.norm(rim_pts - co1[j], axis=1).min()) < MOUTH_R:
            near += 1
    return near, len(ys) - near


total_holes = 0
for tag, az, el in (("st_front", FWD_DEG, 0), ("st_low", FWD_DEG, -30),
                    ("st_34", FWD_DEG - 35, 0), ("st_high", FWD_DEG, 20)):
    p = shoot(tag, az, el)
    img = bpy.data.images.load(p)
    px = np.array(img.pixels[:], dtype=np.float32).reshape(RES, RES, 4)
    bpy.data.images.remove(img)
    blue = (px[:, :, 2] > 0.6) & (px[:, :, 0] < 0.3) & (px[:, :, 1] < 0.3)
    reach = np.zeros_like(blue)
    stack = []
    for i in range(RES):
        for (r, c) in ((0, i), (RES - 1, i), (i, 0), (i, RES - 1)):
            if blue[r, c] and not reach[r, c]:
                reach[r, c] = True; stack.append((r, c))
    while stack:
        r, c = stack.pop()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            rr, cc = r + dr, c + dc
            if 0 <= rr < RES and 0 <= cc < RES and blue[rr, cc] and not reach[rr, cc]:
                reach[rr, cc] = True; stack.append((rr, cc))
    enclosed = blue & ~reach
    near, far = localise(enclosed, az, el)
    total_holes += near
    print(f"  {tag}: enclosed background {int(enclosed.sum())} px -> {near} at the MOUTH, "
          f"{far} elsewhere (horn/forelock notches are real geometry)")
    if near == 0:
        os.remove(p)

print(f"\ngate:")
print(f"  see-through pixels IN THE MOUTH at {ANGLE:.0f} deg: {total_holes}")
if total_holes:
    print(f"  FAIL — you can see daylight through the head. Offending renders kept in {OUT}")
    sys.exit(1)
print("  OK: the open mouth is backed by geometry from every tested angle")
print("  The OPERATOR confirms whether it LOOKS right; this only says it is not broken.")

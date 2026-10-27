"""Checkpoint 1 — lay the PRIMARY LOOPS of the head retopo on the scaffold, and render them.

    blender -b --python tools/retopo_loops.py -- work/RETOPO_clyffy.blend

Landmarks are MEASURED off the scaffold (depth maps + extremes), not eyeballed from a sheet, and
every measurement is printed so a wrong loop is diagnosable from the log. Loops are laid as edge
chains in `retopo_head` (right half only — Mirror(X) completes them) and duplicated into red
tubes in a VIS collection so the renders show them fat and unmissable on the clay scaffold.

Nothing is filled between loops at this stage. That is the point of a block-out: placement errors
are cheap to move while they are still eight verts, and expensive after they anchor a grid.

Scaffold convention (measured, `meshy_clay_000.png`): forward is -Y, unit height, feet at z=0.
"""
import bpy, bmesh, sys, os, math
import numpy as np
from mathutils import Vector, Euler

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
bpy.ops.wm.open_mainfile(filepath=BLEND)

scaf = bpy.data.objects["SCAFFOLD"]
rt = bpy.data.objects["retopo_head"]

# rerunnable: drop any VIS tubes and camera from a previous pass before laying fresh ones
old = bpy.data.collections.get("VIS")
if old:
    for o in list(old.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(old)
oldc = bpy.data.objects.get("C")
if oldc:
    bpy.data.objects.remove(oldc, do_unlink=True)

# ---------- measurement -------------------------------------------------------------------------
def snap(p, offset=0.003):
    """closest point on the scaffold, pushed slightly out along the surface normal"""
    ok, loc, nor, _ = scaf.closest_point_on_mesh(Vector(p))
    return (loc + nor * offset) if ok else Vector(p)

def fwd_hit(x, z):
    """first surface along +Y from far in front; returns y or None"""
    ok, loc, nor, _ = scaf.ray_cast(Vector((x, -3.0, z)), Vector((0, 1, 0)), distance=6.0)
    return loc.y if ok else None

co = np.array([v.co[:] for v in scaf.data.vertices])
z_all = co[:, 2]
H = float(z_all.max())                     # ~1.0
head = co[z_all > 0.70]
print(f"scaffold: {len(co)} verts, height {H:.3f}, head verts {len(head)}")

# depth map of the face: forwardness F = -y of first hit
xs = np.linspace(-0.30, 0.30, 121)
zs = np.linspace(0.70, 0.97, 109)
F = np.full((len(zs), len(xs)), np.nan)
for iz, zz in enumerate(zs):
    for ix, xx in enumerate(xs):
        y = fwd_hit(xx, zz)
        if y is not None:
            F[iz, ix] = -y

# muzzle apex: forwardmost point of the whole face
iz, ix = np.unravel_index(np.nanargmax(F), F.shape)
APEX = Vector((float(xs[ix]), -float(F[iz, ix]), float(zs[iz])))
print(f"muzzle apex ({APEX.x:+.4f}, {APEX.y:+.4f}, {APEX.z:.4f})")

# muzzle extent: contour where forwardness has dropped 0.05 from apex, scanned on the apex row/col
Fa = float(np.nanmax(F))
row = F[iz, :]; colm = F[:, ix]
def span(arr, centre, axis_vals, drop=0.05):
    lo = hi = centre
    for i in range(centre, -1, -1):
        if np.isnan(arr[i]) or arr[i] < Fa - drop: break
        lo = i
    for i in range(centre, len(arr)):
        if np.isnan(arr[i]) or arr[i] < Fa - drop: break
        hi = i
    return float(axis_vals[lo]), float(axis_vals[hi])
mx_lo, mx_hi = span(row, ix, xs)
mz_lo, mz_hi = span(colm, iz, zs)
MUZ_W, MUZ_H = mx_hi - mx_lo, mz_hi - mz_lo
print(f"muzzle span x [{mx_lo:+.3f},{mx_hi:+.3f}] w={MUZ_W:.3f}   z [{mz_lo:.3f},{mz_hi:.3f}] h={MUZ_H:.3f}")

# eye: MEASURED FROM THE RENDER, not detected. Two detector attempts both landed on the brow —
# raw forwardness and local-bump residual alike — because on this face the brow out-bulges the
# eye mound. Per the project rule (never label evidence with a detector), the centre below was
# read off `retopo_cp1/cp1_000.png` pixels (eye lids at px ~(380,415)/(520,415), camera ortho
# 0.62 over 900 px centred on the head-verts mean) and is verified by re-rendering the ring.
hc_z = float(co[z_all > 0.70][:, 2].mean())
EYE_X, EYE_DZ = 0.048, 0.024
ey = fwd_hit(EYE_X, hc_z + EYE_DZ)
EYE = Vector((EYE_X, ey, hc_z + EYE_DZ))
print(f"eye centre R ({EYE.x:+.4f}, {EYE.y:+.4f}, {EYE.z:.4f})   [image-measured]")

# ear tip: lateral extreme of the head zone; horn tip: highest off-centre point
hz = co[(z_all > 0.74)]
EART = Vector(hz[np.argmax(hz[:, 0])].tolist())
off = hz[(hz[:, 0] > 0.02)]
HORNT = Vector(off[np.argmax(off[:, 2])].tolist())
print(f"ear tip R  ({EART.x:+.4f}, {EART.y:+.4f}, {EART.z:.4f})")
print(f"horn tip R ({HORNT.x:+.4f}, {HORNT.y:+.4f}, {HORNT.z:.4f})")

# skull centre at ear height, for aiming ear/horn base rings inward
ring_zone = co[(z_all > EART.z - 0.03) & (z_all < EART.z + 0.03) & (np.abs(co[:, 0]) < 0.03)]
SKULLC = Vector((0.0, float(ring_zone[:, 1].mean()) if len(ring_zone) else APEX.y + 0.15, EART.z))

# ---------- loop construction -------------------------------------------------------------------
LOOPS = {}   # name -> list of Vector, in chain order; closed unless name ends '_arc'

def circle_on_surface(centre, normal, radius, n=8, offset=0.003):
    normal = normal.normalized()
    a = normal.cross(Vector((0, 0, 1)))
    if a.length < 1e-4:
        a = normal.cross(Vector((1, 0, 0)))
    a.normalize()
    b = normal.cross(a).normalized()
    return [snap(centre + (a * math.cos(t) + b * math.sin(t)) * radius, offset)
            for t in [2 * math.pi * i / n for i in range(n)]]

# eye ring — radius from the eye mound size, normal along -Y tilted to the mound
LOOPS["eye_R"] = circle_on_surface(EYE, Vector((0.18, -1, 0.05)), 0.026, n=10)

# muzzle ring — ellipse around the whole muzzle mass, on its own plane
mc = Vector((0.0, APEX.y, (mz_lo + mz_hi) / 2))
pts = []
for i in range(14):
    t = 2 * math.pi * i / 14
    p = mc + Vector((math.cos(t) * (MUZ_W * 0.62), 0, math.sin(t) * (MUZ_H * 0.78)))
    pts.append(snap(p))
LOOPS["muzzle"] = pts

# lip seam — FOLLOWS THE CREASE EXACTLY (operator's ruling 2026-08-05): the seam is the future
# mouth opening, and off the crease the split disagrees with the sculpt. Depth-profile tracing
# missed the corner upturn (seamzoom_090.png), so this reads the crease off the scaffold's OWN
# geometry, the method that worked on v2's survey: CONCAVE-DIHEDRAL edges in the muzzle zone,
# clustered by connectivity, longest chain = the mouth line — including the hook at the corner.
# The ENDPOINT stays the operator's decision (SEAM_CORNER_X): the crease branches toward the pad
# outline past the corner (the recorded v2 trap), so the chain is CUT at the corner, not followed.
SEAM_CORNER_X = None        # None = full detected crease; set to clamp the corner (his call)
bms = bmesh.new()
bms.from_mesh(scaf.data)
bms.verts.ensure_lookup_table()
bms.edges.ensure_lookup_table()
bms.faces.ensure_lookup_table()
zone_z = (mz_lo - 0.02, mz_lo + MUZ_H * 0.55)
# Per-VERTEX concavity, not per-edge dihedral: on a 217k-vert mesh each edge bends only a few
# degrees even along a deep crease (9 edges survived a -17 deg gate), but a valley vertex sees
# its neighbours ABOVE its tangent plane at any density: c = mean dot(normal, dir-to-neighbour).
zone = [v for v in bms.verts
        if zone_z[0] < v.co.z < zone_z[1] and v.co.y < APEX.y + 0.10]
cav = {}
for v in zone:
    n = v.normal
    acc = cnt = 0.0
    for e in v.link_edges:
        u = e.other_vert(v)
        acc += n.dot((u.co - v.co).normalized()); cnt += 1
    if cnt:
        cav[v.index] = acc / cnt
# TWO regimes, because the crease is two shapes. Along the straight run it is a gentle z(x)
# function and one max-cavity pick per x-column traces it cleanly. At the CORNER it hooks
# UPWARD — nearly vertical in x — and a z(x) scan physically cannot follow it (stacked picks,
# then dedup gutted them: the barbed kink the operator caught twice). The hook is therefore
# WALKED along the crease: greedy nearest-neighbour chain over high-cavity verts, parameterized
# by arc length, no z(x) assumption anywhere.
X_MAX = MUZ_W * 0.62 if SEAM_CORNER_X is None else SEAM_CORNER_X
HOOK_X = X_MAX * 0.72

# straight run: per-column max cavity
bins = {}
for v in zone:
    if not (-0.002 <= v.co.x <= HOOK_X):
        continue
    b = int(v.co.x / 0.006)
    c = cav.get(v.index, -1)
    if b not in bins or c > bins[b][0]:
        bins[b] = (c, v.co.copy())
run = [bins[b][1] for b in sorted(bins)]
run.sort(key=lambda p: p.x)
med = float(np.median([p.z for p in run]))
run = [p for p in run if abs(p.z - med) < 0.030]
# interior-only box smooth (edge samples of 'same' convolution collapse toward 2/3 value —
# one such point landed at z 0.47 and scattered the seam down the neck)
for i in range(1, len(run) - 1):
    run[i] = (run[i - 1] + run[i] + run[i + 1]) / 3

# hook: walk the crease from the run's end
thr90 = float(np.percentile(list(cav.values()), 90))
cand = [v.co.copy() for v in zone
        if v.co.x >= HOOK_X - 0.004 and abs(v.co.z - med) < 0.040
        and cav.get(v.index, -1) >= thr90]
chain = [run[-1]]
used = set()
while len(chain) < 60:
    cur = chain[-1]
    best, bd = None, 1e9
    for j, p in enumerate(cand):
        if j in used:
            continue
        d = (p - cur).length
        if d < 0.0008:                      # same spot, absorb silently
            used.add(j); continue
        if d < bd and d <= 0.0075 and p.x >= cur.x - 0.0015:
            best, bd = j, d
    if best is None or cand[best].x > X_MAX + 0.0005:
        break
    used.add(best)
    chain.append(cand[best])
print(f"crease: straight run {len(run)} pts to x {run[-1].x:.3f}, "
      f"hook walk {len(chain)-1} pts to x {chain[-1].x:.3f} z {chain[-1].z:.3f}")

# combine on arc length, resample evenly, then snap — no dedup pass afterwards to undo it
path = run + chain[1:]
seg = [0.0]
for i in range(1, len(path)):
    seg.append(seg[-1] + (path[i] - path[i - 1]).length)
total = seg[-1]
n_out = 17
half = []
for i in range(n_out):
    s = total * i / (n_out - 1)
    j = int(np.searchsorted(seg, s, side="right")) - 1
    j = min(j, len(path) - 2)
    t = (s - seg[j]) / max(seg[j + 1] - seg[j], 1e-9)
    p = path[j] + (path[j + 1] - path[j]) * t
    sp = snap(p)
    half.append(sp if (sp - p).length <= 0.012 else p)
bms.free()
print("lip seam:", [(round(p.x, 3), round(p.z, 3)) for p in half])
LOOPS["lip_seam_arc"] = half

# chin arc — under the muzzle on the sagittal plane, foundation for the jaw loop
chin = []
for i in range(7):
    zz = mz_lo - 0.005 - i * 0.012
    y = fwd_hit(0.0, zz)
    if y is None: break
    chin.append(snap(Vector((0.0, y, zz))))
LOOPS["chin_arc"] = chin

# ear base ring — 30% out from skull side toward the ear tip
edir = (EART - SKULLC).normalized()
LOOPS["ear_base_R"] = circle_on_surface(SKULLC + edir * ((EART - SKULLC).length * 0.30),
                                        edir, 0.045, n=10)

# horn base ring — just above the skull surface under the horn tip
hdir = (HORNT - Vector((HORNT.x * 0.5, HORNT.y, HORNT.z - 0.10))).normalized()
LOOPS["horn_base_R"] = circle_on_surface(Vector((HORNT.x * 0.82, HORNT.y, HORNT.z - 0.055)),
                                         hdir, 0.022, n=8)

# neck ring — full circle at the head/neck junction. Radius from the MEASURED neck cross-section
# (the first attempt used 0.30 and the snap grabbed the shoulders).
nc = co[(z_all > 0.665) & (z_all < 0.695)]
NC = Vector((float(nc[:, 0].mean()), float(nc[:, 1].mean()), 0.68))
r_neck = float(np.percentile(np.hypot(nc[:, 0] - NC.x, nc[:, 1] - NC.y), 80))
print(f"neck centre ({NC.x:+.3f},{NC.y:+.3f})  r80 {r_neck:.3f}")
LOOPS["neck"] = [snap(NC + Vector((math.cos(t), math.sin(t), 0)) * r_neck, 0.003)
                 for t in [2 * math.pi * i / 12 for i in range(12)]]

# sagittal arc — the master profile on x=0: under-chin → muzzle → brow → crown → back of skull
sag = []
SC = Vector((0.0, SKULLC.y, 0.84))
for i in range(26):
    t = math.pi * (-0.42 + 1.55 * i / 25)          # from below the chin over the crown to the back
    d = Vector((0.0, -math.cos(t), math.sin(t)))
    ok, loc, nor, _ = scaf.ray_cast(SC + d * 2.0, -d, distance=2.5)
    if ok:
        sag.append(loc + nor * 0.003)
LOOPS["sagittal_arc"] = sag

# ---------- write into retopo_head --------------------------------------------------------------
bm = bmesh.new()
for name, pts in LOOPS.items():
    closed = not name.endswith("_arc")
    vs = [bm.verts.new(p) for p in pts]
    for i in range(len(vs) - 1):
        bm.edges.new((vs[i], vs[i + 1]))
    if closed and len(vs) > 2:
        bm.edges.new((vs[-1], vs[0]))
bm.to_mesh(rt.data)
bm.free()
print("loops written:", {k: len(v) for k, v in LOOPS.items()})

# ---------- red tube VIS for the renders --------------------------------------------------------
visc = bpy.data.collections.new("VIS")
bpy.context.scene.collection.children.link(visc)
mat = bpy.data.materials.new("VIS_red")
mat.use_nodes = False
mat.diffuse_color = (1.0, 0.05, 0.05, 1.0)
for name, pts in LOOPS.items():
    cu = bpy.data.curves.new(f"vis_{name}", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.0045
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (p.x, p.y, p.z, 1)
    sp.use_cyclic_u = not name.endswith("_arc")
    obv = bpy.data.objects.new(f"vis_{name}", cu)
    obv.data.materials.append(mat)
    visc.objects.link(obv)
    # mirror the vis for anything not on the sagittal plane, matching the Mirror modifier
    if not name.startswith("sagittal") and not name in ("neck", "muzzle", "chin_arc"):
        obm = obv.copy(); obm.data = obv.data
        obm.scale = (-1, 1, 1)
        visc.objects.link(obm)

bpy.ops.wm.save_as_mainfile(filepath=BLEND)

# ---------- renders -----------------------------------------------------------------------------
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"
sh.color_type = "OBJECT"
sh.show_cavity = True
sh.cavity_type = "BOTH"
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = sc.render.resolution_y = 900
scaf.color = (0.60, 0.60, 0.62, 1.0)
for o in visc.objects:
    o.color = (1.0, 0.05, 0.05, 1.0)
for e in [o for o in bpy.data.objects if o.type == "EMPTY"]:
    e.hide_render = True

w = bpy.data.worlds.new("W"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.40, 0.44, 0.41, 1)
sc.world = w

hc = head.mean(axis=0)
ctr = Vector((0.0, float(hc[1]), float(hc[2])))
cd = bpy.data.cameras.new("C"); cam = bpy.data.objects.new("C", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"; cd.ortho_scale = 0.62
cd.clip_start = 0.001; cd.clip_end = 100.0
OUT = os.path.join(os.path.dirname(BLEND), "retopo_cp1")
os.makedirs(OUT, exist_ok=True)
for deg in (0, 40, 90, 180):
    a = math.radians(deg)
    cam.location = (ctr.x + math.sin(a) * 3, ctr.y - math.cos(a) * 3, ctr.z)
    cam.rotation_euler = (math.radians(90), 0, a)
    sc.render.filepath = os.path.join(OUT, f"cp1_{deg:03d}.png")
    bpy.ops.render.render(write_still=True)
print(f"renders -> {OUT}")

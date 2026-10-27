"""Teeth and tongue inside the mouth cavity.

    blender -b --python tools/mouth_parts.py -- <cavity.blend> <out.blend> <fwd_deg>

CONTINUOUS CREAM BANDS, UPPER AND LOWER — NOT SEPARATED TEETH. `reference/approved/SPEC.md`
records this as the FOURTH independent confirmation that the previous build's scallop
(`TEETH_N = 7`, `TEETH_CUT = 0.34`) is wrong against canon, and `modelsheet_open.png` shows
continuous bands. Do not reintroduce per-tooth geometry without the operator saying so.

OVERBITE + OVERJET, carried from the previous build's hard-won note. A flat shared bite plane
contains the teeth perfectly but HIDES them: the upper crown lands level with the upper lip
rim, opening the jaw reveals ~0.0007 of tooth, and the mouth reads toothless. Real mouths
solve it with an OVERBITE — upper crowns hanging BELOW the lower ones — and avoid intersecting
via an OVERJET, the lower band sitting further BACK. The separation is then horizontal, which
the jaw's rotation only ever increases.

EVERYTHING IS SIZED OFF THE BAKED CAVITY, not re-derived. `mouth_cavity.py` writes the throat
point, depth, pitch, seam height and the two rim vertex groups onto the object. The recurring
failure in this project has been two sides of a comparison using two slightly different
definitions; reading one set of numbers removes that whole class.

VERTEX GROUPS ARE BAKED FOR THE RIG: `op_teeth_upper` follows the skull, `op_teeth_lower` and
`op_tongue` follow the jaw. Deciding that here, while the geometry is being authored and the
membership is exact, is far cheaper than reselecting it later.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hardfail  # noqa: F401  -- unhandled exceptions must exit non-zero
import bpy, bmesh, math
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = os.path.abspath(argv[0]), os.path.abspath(argv[1])
FWD_DEG = float(argv[2])

T_UP = float(argv[3]) if len(argv) > 3 else 0.20    # upper band, fraction toward the throat
T_LO = float(argv[4]) if len(argv) > 4 else 0.32    # lower band, further back = the OVERJET
TOOTH_H = float(argv[5]) if len(argv) > 5 else 0.009
TOOTH_D = float(argv[6]) if len(argv) > 6 else 0.008
OVERBITE = float(argv[7]) if len(argv) > 7 else 0.002   # upper crown below the lip line
LOWER_RISE = float(argv[8]) if len(argv) > 8 else 0.004  # lower crown above the lip line
# SPEC: "the tongue as a soft mass FILLING the floor". The first pass gave a tongue occupying
# only ~23% of the cavity height, which read as a small blob rather than a mass.
TONGUE_W = float(argv[9]) if len(argv) > 9 else 0.78
TONGUE_H = float(argv[10]) if len(argv) > 10 else 0.011
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=SRC)
if bpy.context.object and bpy.context.object.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")
ob = max([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
me = ob.data
for k in ("mouth_throat", "mouth_depth", "mouth_seam_z"):
    assert k in ob.keys(), f"{k!r} missing — run tools/mouth_cavity.py first"
THROAT = np.array([float(v) for v in ob["mouth_throat"]])
SEAM_Z = float(ob["mouth_seam_z"])
N0, F0 = len(me.vertices), len(me.polygons)
co = np.empty((N0, 3)); me.vertices.foreach_get("co", co.ravel())
z = co[:, 2]; zlo, zhi = float(z.min()), float(z.max()); H = zhi - zlo

a = math.radians(FWD_DEG)
fwd = np.array([math.sin(a), -math.cos(a), 0.0])
lat = np.array([-fwd[1], fwd[0], 0.0])
up = np.array([0.0, 0.0, 1.0])

gu = ob.vertex_groups["op_rim_upper"].index
gl = ob.vertex_groups["op_rim_lower"].index


def arc_of(gi):
    """Rim vertices of one arc, ordered along the seam by the baked order attribute."""
    vs = [v.index for v in me.vertices if any(g.group == gi for g in v.groups)]
    si = np.empty(N0, dtype=np.float32)
    me.attributes["op_lip_seam_i"].data.foreach_get("value", si)
    vs.sort(key=lambda v: float(si[v]))
    return vs


upper, lower = arc_of(gu), arc_of(gl)
print(f"rim arcs: upper {len(upper)}, lower {len(lower)}   seam z {SEAM_Z:+.4f}")
print(f"throat: fwd {float(THROAT @ fwd):+.4f} height {(THROAT[2]-zlo)/H*100:.1f}%")

bm = bmesh.new(); bm.from_mesh(me)
bm.verts.ensure_lookup_table()


def mat(name, rgb, rough):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = rough
    me.materials.append(m)
    return len(me.materials) - 1


# cream, not white: SPEC and modelsheet_open both show warm cream bands
MI_TEETH = mat("inner_teeth", (0.86, 0.82, 0.68), 0.35)
MI_TONGUE = mat("inner_tongue", (0.62, 0.24, 0.28), 0.55)
print(f"materials: inner_teeth slot {MI_TEETH}, inner_tongue slot {MI_TONGUE}")

new_faces = []
grp_upper, grp_lower, grp_tongue = [], [], []


def band(arc, t_inset, crown_z, sign, group):
    """One continuous swept band. `sign` +1 = upper (gum above the crown), -1 = lower.

    A single closed solid with a rectangular cross-section, four vertices per ring — the same
    topology the previous build settled on. It stays ONE solid, which is why scalloping it was
    a texture-free way to fake teeth and why removing the scallop costs nothing structurally.
    """
    rings = []
    n = len(arc)
    for k, vi in enumerate(arc):
        s = k / (n - 1)
        pinch = math.sin(math.pi * s)
        base = co[vi] * (1.0 - t_inset) + THROAT * t_inset
        # tangent along the arc, for a cross-section that stays perpendicular to the sweep
        kp = arc[max(0, k - 1)]
        kn = arc[min(n - 1, k + 1)]
        tang = co[kn] - co[kp]
        tl = np.linalg.norm(tang)
        tang = tang / tl if tl > 1e-9 else lat.copy()
        dep = THROAT - base
        dep = dep - tang * float(dep @ tang)
        dl = np.linalg.norm(dep)
        dep = dep / dl if dl > 1e-9 else fwd.copy()
        # the band tapers away at the corners so it never reaches the commissure
        taper = min(1.0, pinch * 1.6)
        h = TOOTH_H * taper
        d = TOOTH_D * taper
        crown = np.array([base[0], base[1], crown_z])
        gum = crown + up * (sign * h)
        ring = [gum - dep * (d * 0.5), crown - dep * (d * 0.5),
                crown + dep * (d * 0.5), gum + dep * (d * 0.5)]
        rings.append([bm.verts.new(Vector(p)) for p in ring])
    bm.verts.ensure_lookup_table()
    for r in rings:
        for v in r:
            group.append(v)
    made = 0
    for k in range(len(rings) - 1):
        A, B = rings[k], rings[k + 1]
        for j in range(4):
            try:
                f = bm.faces.new((A[j], A[(j + 1) % 4], B[(j + 1) % 4], B[j]))
                f.material_index = MI_TEETH
                new_faces.append(f); made += 1
            except ValueError:
                pass
    for r, rev in ((rings[0], False), (rings[-1], True)):
        vs = list(reversed(r)) if rev else list(r)
        try:
            f = bm.faces.new(vs)
            f.material_index = MI_TEETH
            new_faces.append(f); made += 1
        except ValueError:
            pass
    return made


nu = band(upper, T_UP, SEAM_Z - OVERBITE, +1.0, grp_upper)
nl = band(lower, T_LO, SEAM_Z + LOWER_RISE, -1.0, grp_lower)
print(f"upper band: {nu} faces at inset {T_UP}, crown z {SEAM_Z-OVERBITE:+.4f}")
print(f"lower band: {nl} faces at inset {T_LO}, crown z {SEAM_Z+LOWER_RISE:+.4f}  "
      f"(overjet {T_LO-T_UP:.2f} of the throat distance)")

# ---------------------------------------------------------------- tongue
NSEG = 14
SPINE = [0.12, 0.26, 0.42, 0.58, 0.72, 0.84]
half_lat_at = lambda t: 0.075 * (1.0 - t)          # the cavity narrows toward the throat
mid = co[upper].mean(axis=0) * 0.5 + co[lower].mean(axis=0) * 0.5
rings = []
for t in SPINE:
    s = (t - SPINE[0]) / (SPINE[-1] - SPINE[0])
    shape = math.sin(math.pi * (0.15 + 0.7 * s))   # rounded at tip and root, full in between
    base = mid * (1.0 - t) + THROAT * t
    # the cavity floor drops away from the seam; ride just above it
    floor_drop = 0.018 + (0.042 - 0.018) * min(1.0, t / 0.72)
    centre = np.array([base[0], 0.0, base[2] - floor_drop + 0.007])
    rw = max(0.004, TONGUE_W * half_lat_at(t) * shape)
    rh = max(0.0025, TONGUE_H * shape)
    ring = []
    for j in range(NSEG):
        th = 2.0 * math.pi * j / NSEG
        p = centre + lat * (math.cos(th) * rw) + up * (math.sin(th) * rh)
        ring.append(bm.verts.new(Vector(p)))
    rings.append(ring)
bm.verts.ensure_lookup_table()
for r in rings:
    grp_tongue.extend(r)
nt = 0
for k in range(len(rings) - 1):
    A, B = rings[k], rings[k + 1]
    for j in range(NSEG):
        try:
            f = bm.faces.new((A[j], A[(j + 1) % NSEG], B[(j + 1) % NSEG], B[j]))
            f.material_index = MI_TONGUE
            new_faces.append(f); nt += 1
        except ValueError:
            pass
for r, rev in ((rings[0], True), (rings[-1], False)):
    cen = bm.verts.new(Vector(sum((np.array(v.co[:]) for v in r)) / len(r)))
    grp_tongue.append(cen)
    bm.verts.ensure_lookup_table()
    seq = list(reversed(r)) if rev else list(r)
    for j in range(len(seq)):
        try:
            f = bm.faces.new((seq[j], seq[(j + 1) % len(seq)], cen))
            f.material_index = MI_TONGUE
            new_faces.append(f); nt += 1
        except ValueError:
            pass
print(f"tongue: {nt} faces, {len(SPINE)} rings x {NSEG}")

# index_update FIRST: a vertex created with bm.verts.new() carries index -1 until the table is
# rebuilt, so reading .index here without it silently collapses every group onto vertex -1 and
# every "closest approach" measures as exactly 0.00000. Which is what it did.
bm.verts.index_update()
idx_upper = [v.index for v in grp_upper]
idx_lower = [v.index for v in grp_lower]
idx_tongue = [v.index for v in grp_tongue]
assert min(idx_upper + idx_lower + idx_tongue) >= 0, "un-indexed vertices in a part group"
bm.normal_update()
bm.to_mesh(me)
bm.free()
me.update()

for name, idxs in (("op_teeth_upper", idx_upper), ("op_teeth_lower", idx_lower),
                   ("op_tongue", idx_tongue)):
    vg = ob.vertex_groups.get(name) or ob.vertex_groups.new(name=name)
    vg.add([int(i) for i in idxs], 1.0, "REPLACE")
    print(f"  vertex group {name}: {len(idxs)} verts")

# ---------------------------------------------------------------- gates
N1, F1 = len(me.vertices), len(me.polygons)
co1 = np.empty((N1, 3)); me.vertices.foreach_get("co", co1.ravel())
bm = bmesh.new(); bm.from_mesh(me)
b1 = sum(1 for e in bm.edges if len(e.link_faces) == 1)
nm1 = sum(1 for e in bm.edges if len(e.link_faces) > 2)
lo1 = sum(1 for v in bm.verts if not v.link_faces)
bm.free()
print(f"\ngate:")
print(f"  verts {N0} -> {N1}  (+{N1-N0})   faces {F0} -> {F1}  (+{F1-F0})")
print(f"  boundary edges {b1}   non-manifold {nm1}   loose {lo1}")
assert lo1 == 0, f"{lo1} loose vertices"
assert b1 <= 3, f"boundary edges {b1}: a part is not closed"
assert nm1 <= 1, f"non-manifold {nm1}"


def min_gap(ia, ib, label):
    A, B = co1[np.array(ia, dtype=int)], co1[np.array(ib, dtype=int)]
    d = np.linalg.norm(A[:, None, :] - B[None, :, :], axis=2)
    g = float(d.min())
    print(f"  closest approach {label}: {g:.5f} ({g/H*100:.3f}% of body height)")
    return g


g_uv = min_gap(idx_upper, idx_lower, "upper band <-> lower band")
g_ut = min_gap(idx_upper, idx_tongue, "upper band <-> tongue")
g_lt = min_gap(idx_lower, idx_tongue, "lower band <-> tongue")
assert g_uv > 0.0005, ("the two tooth bands nearly touch at rest — the jaw will drive them "
                       "through each other. Increase the overjet (T_LO - T_UP).")
assert g_ut > 0.0005 and g_lt > 0.0005, "the tongue is touching a tooth band"
print("  OK: closed, manifold, and nothing intersects at rest")
print("  VISIBILITY IS NOT DECIDED HERE — run tools/cavity_gate.py at 0/90/180/270.")

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"wrote {OUT}")

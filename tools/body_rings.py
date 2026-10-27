"""Guide RINGS for the body, sliced from the scaffold — and a measurement of the edge we have.

    blender -b --python tools/body_rings.py -- work/RETOPO_clyffy.blend
    blender -b --python tools/body_rings.py -- work/RETOPO_clyffy.blend --write

WHY RINGS. The head was built by free marching because a head has no natural parametrisation — the
front had to find its own way around brows, ears and a muzzle. A BODY IS A TUBE. Every region below
the collar runs between two heights, and a horizontal cross-section of the scaffold at a declared
height IS the edge that region should end on. Marching to a declared ring instead of stopping on a
row count is the difference between the neck region's current lower edge — ragged, scalloped, every
column stopping wherever its 7th step happened to land — and an edge the next region can anchor to.

This is the same `capture` mechanism the head already uses (`vis_neck`, `vis_horn_base_R`); the only
new thing is that the rings are DERIVED from the scaffold at a chosen z rather than hand-placed.

Half rings only (x >= 0): the shell is mirrored.

Read-only unless --write is passed.
"""
import bpy, bmesh, sys, os, math
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scaffold_section import section_loops as _section_loops, classify_loops

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
WRITE = "--write" in argv
bpy.ops.wm.open_mainfile(filepath=BLEND)
scaf = bpy.data.objects["SCAFFOLD"]
rt = bpy.data.objects["retopo_head"]

print(f"retopo_head modifiers: {[(m.name, m.type) for m in rt.modifiers]}")
print(f"vertex groups: {[g.name for g in rt.vertex_groups]}")

# ---- how ragged is the edge we would be anchoring to? -------------------------------------------
bm = bmesh.new()
bm.from_mesh(rt.data)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()
dl = bm.verts.layers.deform.verify()
bnd = set()
for e in bm.edges:
    if len(e.link_faces) == 1:
        bnd.update(e.verts)
gi = rt.vertex_groups["cp9_neck"].index if rt.vertex_groups.get("cp9_neck") else None
low = [v for v in bnd if gi is not None and gi in v[dl]]
if low:
    zs = sorted(v.co.z for v in low)
    mean = sum(zs) / len(zs)
    sd = (sum((z - mean) ** 2 for z in zs) / len(zs)) ** 0.5
    print(f"\nCURRENT NECK LOWER EDGE: {len(low)} boundary verts in cp9_neck")
    print(f"  z  min {zs[0]:+.4f}  max {zs[-1]:+.4f}  mean {mean:+.4f}  spread {zs[-1] - zs[0]:.4f}"
          f"  sd {sd:.4f}")
    print(f"  -> a clean planar edge would have spread ~0. This one wanders "
          f"{zs[-1] - zs[0]:.4f} = {(zs[-1] - zs[0]) / 0.018:.1f} march steps.")
bm.free()

# ---- the ring heights, chosen from tools/body_survey.py -------------------------------------------
# name        z       what the scaffold does there
RINGS = [
    # 0.660 was the first choice — below the jaw (mass ends 0.672), above the deltoid flare. The
    # PREFLIGHT rejected it: the head shell's existing neck ring is not planar, it dips to
    # z 0.6517 where the throat and nape captured onto vis_neck, so part of the front sat BELOW
    # the target and those columns would have had to march upward into the head. 0.630 clears the
    # whole front. Measured, then corrected by the gate — which is the gate paying for itself on
    # its first run.
    ("collar",  0.630, "below the head shell's lowest existing boundary vert (0.6517) so every "
                       "column marches DOWN; shoulder cap sits below it"),
    ("chest",   0.500, "mid-chest. NB the slice here wraps arm surface too — arms do not separate "
                       "until 0.368 — so this ring is a stop for the FRONT/BACK sheets, not a tube"),
    # EXACT scan (--scan 0.520 0.380 14): one loop down to z 0.480, real arm loops (145/142 pts)
    # from z 0.400. So the arms come free at 0.400, not 0.368 — the single-linkage clustering in
    # body_survey.py was merging the two surfaces across a gap narrower than its 0.020 threshold.
    # 0.410 is the LAST height that is still a single contour, so it is the last stop a one-tube
    # march can have.
    ("armpit",  0.410, "the last single-contour height — arms come free at 0.400. Torso+arms"),
    ("waist",   0.300, "below the arm gap, above the shirt hem"),
    # legs split at z 0.160 by exact chaining (2 loops, 205/195 pts) — NOT 0.152, which was the
    # clustering figure. Same error as the arms, same cause: a distance threshold merges surfaces.
    ("hip",     0.200, "above where the legs split at 0.160"),
    # ARM rings are CLOSED loops on the arm itself, not half-arcs about the mirror plane — the arm
    # is nowhere near x=0. `kind="arm"` picks the arm contour instead of the largest one.
    ("armR_mid",   0.360, "arm fully free and still full width — the arm march's shape control",
     "limb", (0.245, 0.034)),
    ("armR_wrist", 0.300, "above where the arm tapers away into the hand (gone by z 0.250); the "
                          "hand is a separate object, so this is where the arm shell stops",
     "limb", (0.247, 0.018)),
    # the CROTCH ring: the last single-contour height on the way down, the mirror-plane twin of the
    # armpit ring. Exact scan: one torso loop at z 0.1621, two leg loops at 0.1492, so the legs come
    # free at about z 0.161 — not 0.152 (clustering) and not 0.160 (the coarser scan).
    ("crotch",     0.170, "last single-contour height above the leg split at ~0.161"),
    # LEG rings. `near` is REQUIRED and is not a nicety: `classify_loops` ranks candidate loops by
    # max x, and below z 0.085 THE TAIL TUFT IS FURTHER OUT IN X THAN THE LEG (0.171 vs 0.129), so
    # ranking would hand back the tail while the caller believed it asked for a leg. Selecting by
    # proximity to a declared centroid cannot make that mistake — the tail sits at y +0.25, the leg
    # at y -0.01.
    ("legR_knee",  0.110, "mid-shin, leg fully free and clear of the tail tuft",
     "limb", (0.100, -0.015)),
    ("legR_ankle", 0.060, "above the hoof flare (the hoof widens again below z 0.05)",
     "limb", (0.100, -0.007)),
    # the hoof widens all the way down (x 0.073..0.130 at z 0.058 -> 0.063..0.151 at z 0.006) and
    # extends forward in y. The tail tuft is gone below z 0.049, so nothing else can be confused
    # for a foot here.
    ("legR_hoof",  0.012, "just above the ground; the sole gets capped separately",
     "limb", (0.105, -0.035)),
]
NPTS = 40


def section_pts(z):
    bmx = bmesh.new()
    bmx.from_mesh(scaf.data)
    bmx.transform(scaf.matrix_world)
    pts = []
    for e in bmx.edges:
        a, b = e.verts[0].co, e.verts[1].co
        if (a.z - z) * (b.z - z) < 0:
            t = (z - a.z) / (b.z - a.z)
            pts.append(a.lerp(b, t))
    bmx.free()
    return pts


def cluster(pts, thr=0.020):
    un = list(range(len(pts)))
    out = []
    while un:
        seed = un.pop()
        comp, stack = [seed], [seed]
        while stack:
            k = stack.pop()
            near = [j for j in un if (pts[j].xy - pts[k].xy).length < thr]
            for j in near:
                un.remove(j)
                comp.append(j)
                stack.append(j)
        out.append([pts[i] for i in comp])
    return out


def section_loops(z):
    """Delegates to tools/scaffold_section.py — ONE implementation, deliberately.

    This used to be a second copy of the chaining code. The split tool and the ring builder must
    agree on what the contours at a height are: if they disagreed by one contour the armpit seam
    would be cut in the wrong place. Two copies is how they come to disagree.
    """
    return _section_loops(scaf, z, verbose=True)


def half_ring(z, n):
    """the largest contour at z, ordered exactly, resampled to n points over x >= 0"""
    loops = section_loops(z)
    if not loops:
        return []
    loop = max(loops, key=len)
    # take the contiguous x >= 0 arc: rotate the loop so it starts at a sign change, then keep the
    # run that is on the positive side
    n_l = len(loop)
    starts = [i for i in range(n_l)
              if loop[i].x >= 0 > loop[(i - 1) % n_l].x]
    if starts:
        i0 = starts[0]
        half = []
        for k in range(n_l):
            p = loop[(i0 + k) % n_l]
            if p.x < 0:
                break
            half.append(p)
    else:
        half = [p for p in loop if p.x >= 0]
    if len(half) < 3:
        return []
    total = sum((half[i + 1] - half[i]).length for i in range(len(half) - 1))
    if total <= 0:
        return []
    out, acc, want = [half[0]], 0.0, total / (n - 1)
    tgt = want
    for i in range(len(half) - 1):
        seg = (half[i + 1] - half[i]).length
        while acc + seg >= tgt and len(out) < n - 1:
            t = (tgt - acc) / seg
            out.append(half[i].lerp(half[i + 1], t))
            tgt += want
        acc += seg
    out.append(half[-1])
    return out


def limb_ring(z, n, near):
    """the LIMB contour at z as a CLOSED loop of n points, selected by proximity to `near`.

    Not a half-arc: a limb never touches the mirror plane, so there is no midline to split it at and
    the ring has to close on itself. The limb march's front is likewise cyclic — a limb is a tube,
    and a tube's cross-section is a cycle.

    Selection is by CENTROID PROXIMITY, never by size or extent. Below z 0.085 the tail tuft reaches
    further out in x than the leg does (0.171 vs 0.129), so any ranking by extent silently returns
    the tail when the caller asked for a leg. Proximity to a declared point cannot confuse two
    things that are 0.26 apart in y.
    """
    loops = section_loops(z)
    if not loops:
        return []
    tgt = Vector((near[0], near[1], z))

    def centroid(l):
        return sum(l, Vector()) / len(l)

    # EVERY loop is a candidate. Excluding "the largest, because that is the torso" was tried and is
    # wrong below the crotch, where there IS no torso: at z 0.060 the loops are the two legs and the
    # tail, the largest is the RIGHT LEG, and stripping it handed back the LEFT leg (centroid
    # -0.102) for a ring asked for at +0.100. Proximity needs no help — the torso's centroid sits on
    # the midline and every limb's is far off it.
    loop = min(loops, key=lambda l: (Vector((centroid(l).x, centroid(l).y, z)) - tgt).length)
    c = centroid(loop)
    print(f"    limb loop at z {z:.3f}: {len(loop)} pts, centroid "
          f"({c.x:+.3f},{c.y:+.3f}), asked near ({near[0]:+.3f},{near[1]:+.3f})")
    seg = [(loop[i] - loop[(i + 1) % len(loop)]).length for i in range(len(loop))]
    total = sum(seg)
    if total <= 0:
        return []
    out, acc, want, tgt = [loop[0]], 0.0, total / n, total / n
    for i in range(len(loop)):
        a, b = loop[i], loop[(i + 1) % len(loop)]
        s = seg[i]
        while acc + s >= tgt and len(out) < n:
            out.append(a.lerp(b, (tgt - acc) / s))
            tgt += want
        acc += s
    return out[:n]


if "--scan" in argv:
    i = argv.index("--scan")
    z0, z1, nstep = float(argv[i + 1]), float(argv[i + 2]), int(argv[i + 3])
    print(f"\nEXACT SECTION SCAN {z0} -> {z1} ({nstep} steps) — loop COUNT is the split test")
    print("  The single-linkage clustering in body_survey.py merges contours whose gap is under")
    print("  its threshold, so it reported the arms fusing higher than they do. Face-topology")
    print("  chaining has no threshold: separate loops are separate surfaces, full stop.")
    for k in range(nstep + 1):
        z = z0 + (z1 - z0) * k / nstep
        ls = section_loops(z)
        big = sorted((len(l) for l in ls), reverse=True)
        arms = [l for l in ls if 40 <= len(l) < 300]
        tag = ""
        if len(arms) >= 2:
            xs = [max(p.x for p in l) for l in arms]
            tag = f"   ARMS FREE (arm x max {max(xs):+.3f})"
        print(f"  z {z:+.4f}  {len(ls)} loops  sizes {big[:4]}{tag}")
        for l in sorted(ls, key=len, reverse=True):
            if len(l) < 300:
                xs = [p.x for p in l]
                ys = [p.y for p in l]
                print(f"        small loop {len(l):4d} pts  x[{min(xs):+.3f},{max(xs):+.3f}] "
                      f"y[{min(ys):+.3f},{max(ys):+.3f}]")
    sys.exit(0)

made = []
for entry in RINGS:
    name, z, why = entry[0], entry[1], entry[2]
    kind = entry[3] if len(entry) > 3 else "torso"
    pts = limb_ring(z, 16, entry[4]) if kind == "limb" else half_ring(z, NPTS)
    if not pts:
        print(f"  !! ring '{name}' at z {z}: no contour")
        continue
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    print(f"\nring '{name}' z {z:.3f}: {len(pts)} pts  x[{min(xs):+.3f},{max(xs):+.3f}] "
          f"y[{min(ys):+.3f},{max(ys):+.3f}]   {why}")
    made.append((name, z, pts))

if WRITE:
    for name, z, pts in made:
        oname = f"vis_ring_{name}"
        old = bpy.data.objects.get(oname)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
        cu = bpy.data.curves.new(oname, "CURVE")
        cu.dimensions = "3D"
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        for i, p in enumerate(pts):
            # clamp to the mirror plane: the contour is collected with a -0.001 tolerance so the
            # midline point is not dropped, and a ring point at x -0.001 becomes a captured vert
            # 0.0009 PAST the mirror plane — which the region gate correctly rejects as clipping
            # leakage. The tolerance belongs to the collection, not to the guide.
            sp.points[i].co = (max(0.0, p.x), p.y, p.z, 1.0)
        ob = bpy.data.objects.new(oname, cu)
        bpy.context.scene.collection.objects.link(ob)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print(f"\nwrote {len(made)} ring guides and SAVED")
else:
    print("\n(dry run — pass --write to create the vis_ring_* guides)")

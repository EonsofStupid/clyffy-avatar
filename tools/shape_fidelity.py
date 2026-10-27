"""Does the retopo still LOOK like the scaffold? The check that was missing.

    blender -b --python tools/shape_fidelity.py -- work/RETOPO_clyffy.blend retopo_head 0.640

Args: blend, object name, ZMAX (only geometry below this is measured — the head is judged
separately, against the approved art, not against the scaffold).

WHY THIS EXISTS. The operator, looking at the marched body: *"the back of it's awful, the arms are
awful ... he went backwards."* He was right, and every gate I had written said the build was fine,
because every one of them measures TOPOLOGY HYGIENE — quad ratio, non-manifold edges, edge lengths,
bounding boxes — and not one of them asks whether the surface still matches the thing it is tracing.
A body can degrade steadily into faceted slabs with every check green. That is exactly what happened.

TWO-SIDED, and that is the whole point. One-sided (retopo -> scaffold) only asks "is every vertex I
placed near the surface", which stays small even when a limb has been flattened into a paddle,
because the paddle's verts are all still ON the scaffold. The direction that catches lost form is
SCAFFOLD -> RETOPO: it asks "is every part of the shape still represented", and it goes large
exactly where a feature has been smoothed away or spanned over.

This is the same lesson as `tools/crater_probe.py`, which was rewritten after a hull-ray measurement
reported a pit four times too large and missed a real malformed skull: measure the thing you
actually care about, from both directions, with a control.
"""
import bpy, bmesh, sys, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
NAME = argv[1] if len(argv) > 1 else "retopo_head"
ZMAX = float(argv[2]) if len(argv) > 2 else 0.640

bpy.ops.wm.open_mainfile(filepath=BLEND)
scaf = bpy.data.objects["SCAFFOLD"]
# NAME may be "MODEL", meaning the assembled thing: the shell plus every separate part. Measuring
# the shell ALONE overstates the damage, because parts that are separate ON PURPOSE (the tail, the
# hand) then read as missing shape — the first run of this tool reported a 0.2480 worst case and
# both offending points were the TAIL, which is a separate object by the operator's own ruling.
if NAME == "MODEL":
    objs = [o for o in bpy.data.objects
            if o.type == "MESH" and (o.name == "retopo_head" or o.name.startswith("clyffy_"))]
    print(f"measuring the ASSEMBLED model: {', '.join(sorted(o.name for o in objs))}")
else:
    objs = [bpy.data.objects.get(NAME)]
    if objs[0] is None:
        print(f"!! no object '{NAME}'")
        sys.exit(1)
ob = objs[0]

dg = bpy.context.evaluated_depsgraph_get()


def world_verts(o, zmax):
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    mw = o.matrix_world
    pts = [mw @ v.co for v in me.vertices]
    ev.to_mesh_clear()
    return [p for p in pts if p.z < zmax]


def bvh_of(*os_):
    from mathutils.bvhtree import BVHTree
    bm = bmesh.new()
    for o in os_:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        tmp = bmesh.new()
        tmp.from_mesh(me)
        tmp.transform(o.matrix_world)
        tmp.to_mesh(me)
        bm.from_mesh(me)
        tmp.free()
        ev.to_mesh_clear()
    t = BVHTree.FromBMesh(bm)
    bm.free()
    return t


def stats(name, pts, tree):
    ds = []
    for p in pts:
        loc, nor, idx, d = tree.find_nearest(p)
        if loc is not None:
            ds.append(d)
    if not ds:
        return None
    ds.sort()
    n = len(ds)
    return dict(n=n, mean=sum(ds) / n, p50=ds[n // 2], p95=ds[int(n * 0.95)],
                p99=ds[int(n * 0.99)], mx=ds[-1])


tree_ob = bvh_of(*objs)
tree_sc = bvh_of(scaf)

pts_ob = [p for o in objs for p in world_verts(o, ZMAX)]
pts_sc = [p for p in world_verts(scaf, ZMAX)]
# thin the scaffold sample — 216k verts is far more than the measurement needs
step = max(1, len(pts_sc) // 20000)
pts_sc = pts_sc[::step]

a = stats("retopo->scaffold", pts_ob, tree_sc)
b = stats("scaffold->retopo", pts_sc, tree_ob)

print(f"SHAPE FIDELITY of '{NAME}' below z {ZMAX}  (model is 1.000 tall)")
print(f"{'direction':22s} {'n':>7} {'mean':>8} {'p50':>8} {'p95':>8} {'p99':>8} {'max':>8}")
for nm, s in (("retopo -> scaffold", a), ("scaffold -> retopo", b)):
    if s:
        print(f"{nm:22s} {s['n']:7d} {s['mean']:8.4f} {s['p50']:8.4f} {s['p95']:8.4f} "
              f"{s['p99']:8.4f} {s['mx']:8.4f}")

if a and b:
    print()
    print("  retopo -> scaffold  = 'are my verts on the surface'. Stays SMALL even when a limb has "
          "been\n                        flattened, because a flat slab's verts are still on the "
          "scaffold.")
    print("  scaffold -> retopo  = 'is the shape still represented'. THIS is the one that catches "
          "lost\n                        form: it blows up wherever a feature was smoothed away or "
          "spanned over.")
    print()
    print(f"  worst-case one-sided deviation: {max(a['mx'], b['mx']):.4f} "
          f"({100.0 * max(a['mx'], b['mx']):.1f}% of model height)")
    print(f"  p95 scaffold->retopo: {b['p95']:.4f} — the honest headline number")

# where is it worst? report the scaffold points that are furthest from the retopo, grouped coarsely
if b:
    far = []
    for p in pts_sc:
        loc, nor, idx, d = tree_ob.find_nearest(p)
        if loc is not None and d > b["p99"]:
            far.append((d, p))
    far.sort(reverse=True, key=lambda t: t[0])
    print(f"\n  WORST {min(12, len(far))} places the shape is not represented "
          f"(scaffold point -> nearest retopo):")
    shown, used = 0, []
    for d, p in far:
        if any((p - q).length < 0.05 for q in used):
            continue
        used.append(p)
        print(f"    {d:.4f} at ({p.x:+.3f},{p.y:+.3f},{p.z:+.3f})")
        shown += 1
        if shown >= 12:
            break

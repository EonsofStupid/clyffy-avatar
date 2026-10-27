"""Pre-CP5 inspection: state of retopo_head, the mouth patch's open top boundary,
nostril band, and the eye line on the scaffold. Read-only.

    blender -b --python tools/inspect_cp5.py -- work/RETOPO_clyffy.blend
"""
import bpy, bmesh, sys, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
bpy.ops.wm.open_mainfile(filepath=BLEND)
scaf = bpy.data.objects["SCAFFOLD"]
rt = bpy.data.objects["retopo_head"]
bpy.context.view_layer.objects.active = rt
if rt.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")

print("== objects ==")
for o in bpy.data.objects:
    print(f"  {o.name:28s} {o.type:6s} hide_select={o.hide_select}")

bm = bmesh.new(); bm.from_mesh(rt.data)
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
nq = sum(1 for f in bm.faces if len(f.verts) == 4)
nt = sum(1 for f in bm.faces if len(f.verts) == 3)
wire_v = [v for v in bm.verts if not v.link_faces]
print(f"\n== retopo_head == {len(bm.verts)} verts, {len(bm.faces)} faces ({nq}q {nt}t), "
      f"{len(wire_v)} face-less (wire) verts")

# boundary edges of the face patch, grouped into loops
bnd = [e for e in bm.edges if e.link_faces and len(e.link_faces) == 1]
seen, loops = set(), []
for e in bnd:
    if e.index in seen:
        continue
    comp, stack = [], [e]
    seen.add(e.index)
    while stack:
        k = stack.pop(); comp.append(k)
        for v in k.verts:
            for e2 in v.link_edges:
                if e2 in bnd and e2.index not in seen:
                    seen.add(e2.index); stack.append(e2)
    loops.append(comp)
print(f"\n== boundary loops of the patch == {len(loops)}")
for i, L in enumerate(loops):
    vs = set(v for e in L for v in e.verts)
    xs = [v.co.x for v in vs]; zs = [v.co.z for v in vs]; ys = [v.co.y for v in vs]
    print(f"  loop {i}: {len(L)} edges  x[{min(xs):+.3f},{max(xs):+.3f}] "
          f"y[{min(ys):+.3f},{max(ys):+.3f}] z[{min(zs):.3f},{max(zs):.3f}]")

# the TOP row: open boundary verts with highest z band (above the seam z ~0.73)
top_verts = []
for L in loops:
    vs = list(set(v for e in L for v in e.verts))
    for v in vs:
        if v.co.z > 0.745:
            top_verts.append(v)
top_verts = list({v.index: v for v in top_verts}.values())
top_verts.sort(key=lambda v: v.co.x)
print(f"\n== top boundary candidates (z>0.745) == {len(top_verts)}")
for v in top_verts:
    print(f"  ({v.co.x:+.4f}, {v.co.y:+.4f}, {v.co.z:.4f})  edges={len(v.link_edges)} faces={len(v.link_faces)}")

# wire chains (CP1 guide loops that survived)
print("\n== wire chains ==")
seenv, chains = set(), []
for v in wire_v:
    if v.index in seenv:
        continue
    stack, comp = [v], []
    seenv.add(v.index)
    while stack:
        k = stack.pop(); comp.append(k)
        for e in k.link_edges:
            o = e.other_vert(k)
            if o.index not in seenv and not o.link_faces:
                seenv.add(o.index); stack.append(o)
    chains.append(comp)
for c in chains:
    xs = [v.co.x for v in c]; zs = [v.co.z for v in c]; ys = [v.co.y for v in c]
    print(f"  chain: {len(c)}v  x[{min(xs):+.3f},{max(xs):+.3f}] "
          f"y[{min(ys):+.3f},{max(ys):+.3f}] z[{min(zs):.3f},{max(zs):.3f}]")

# scaffold landmarks: nostril concavity + eye concavity on the right side
bms = bmesh.new(); bms.from_mesh(scaf.data); bms.verts.ensure_lookup_table()


def cavity_max(xlo, xhi, zlo, zhi, ylim):
    best_c, best_p = -1e9, None
    for v in bms.verts:
        p = v.co
        if not (xlo < p.x < xhi and zlo < p.z < zhi and p.y < ylim):
            continue
        n = v.normal
        acc = cnt = 0.0
        for e in v.link_edges:
            u = e.other_vert(v)
            acc += n.dot((u.co - v.co).normalized()); cnt += 1
        c = acc / cnt if cnt else -1
        if c > best_c:
            best_c, best_p = c, p.copy()
    return best_c, best_p


c, p = cavity_max(0.020, 0.090, 0.770, 0.815, -0.20)
print(f"\nnostril R: ({p.x:+.4f}, {p.y:+.4f}, {p.z:.4f})  cavity {c:.4f}")

# head mean z for the eye reference (EYE_X=0.048, EYE_DZ=0.024 rel to head mean z)
head_z = [v.co.z for v in bms.verts if v.co.z > 0.55]
mean_z = sum(head_z) / len(head_z)
print(f"head-verts mean z (z>0.55): {mean_z:.4f}  -> eye centre approx (0.048, z {mean_z + 0.024:.4f})")

# muzzle-top profile along the midline: where does the bridge climb to the brow?
print("\nmidline scaffold profile x~0 (y at min per z-bin, forwardmost point):")
import numpy as np
bins = {}
for v in bms.verts:
    p = v.co
    if abs(p.x) < 0.01 and p.z > 0.70:
        k = round(p.z / 0.01)
        if k not in bins or p.y < bins[k][1]:
            bins[k] = (p.z, p.y)
for k in sorted(bins):
    z, y = bins[k]
    print(f"  z {z:.3f}  y {y:+.4f}")
bms.free()
bm.free()

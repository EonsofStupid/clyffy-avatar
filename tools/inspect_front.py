"""Print the FRONT a region would march from, vert by vert, with the gap to the next one.

    blender -b --python tools/inspect_front.py -- work/RETOPO_clyffy.blend cp9_neck 0.725

Written because the neck march kept producing one 0.09 edge and two guesses at the cause both
missed. The diagnostic added to `retopo_region.py` put the worst gap at ROW 0 — the existing
boundary, before a single new vert was placed. So the march was not creating the defect, it was
inheriting it. This prints that boundary so the defect can be seen instead of inferred.

The group argument is CLEARED first (in memory only), so what prints is the front a rerun of that
region would actually see — not the boundary of the previous pass's output. Read-only.
"""
import bpy, bmesh, sys, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
GROUP = argv[1] if len(argv) > 1 else "cp9_neck"
ZMAX = float(argv[2]) if len(argv) > 2 else 0.725
bpy.ops.wm.open_mainfile(filepath=BLEND)
rt = bpy.data.objects["retopo_head"]

bm = bmesh.new()
bm.from_mesh(rt.data)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()
dl = bm.verts.layers.deform.verify()

g = rt.vertex_groups.get(GROUP)
if g:
    stale = [v for v in bm.verts if g.index in v[dl]]
    if stale:
        bmesh.ops.delete(bm, geom=stale, context="VERTS")
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        print(f"cleared {len(stale)} verts of '{GROUP}' (in memory) — this is the front a rerun sees")

adjb = {}
for e in bm.edges:
    if len(e.link_faces) == 1:
        a, b = e.verts
        adjb.setdefault(a, []).append(b)
        adjb.setdefault(b, []).append(a)

picked = [v for v in adjb if v.co.z < ZMAX]
psel = set(picked)
padj = {v: [o for o in adjb[v] if o in psel] for v in picked}
chains, seen = [], set()
for v in picked:
    if v in seen:
        continue
    comp, stack = [], [v]
    seen.add(v)
    while stack:
        k = stack.pop()
        comp.append(k)
        for o in padj[k]:
            if o not in seen:
                seen.add(o)
                stack.append(o)
    ends = [k for k in comp if len(padj[k]) == 1]
    s0 = ends[0] if ends else comp[0]
    chain, prev = [s0], None
    while True:
        nx = [o for o in padj[chain[-1]] if o is not prev and o not in chain]
        if not nx:
            break
        prev = chain[-1]
        chain.append(nx[0])
    chains.append(chain)
front = max(chains, key=len)

print(f"\nfront: {len(front)} verts (chains {[len(c) for c in chains]})")
print(f"{'i':>3} {'x':>8} {'y':>8} {'z':>8} {'gap to next':>12} {'bnd deg':>8}")
gaps = []
for i, v in enumerate(front):
    nxt = front[i + 1] if i + 1 < len(front) else None
    gap = (v.co - nxt.co).length if nxt else 0.0
    if nxt:
        gaps.append(gap)
    flag = ""
    if nxt and gap > 0.030:
        flag = "   <<< LONG"
    print(f"{i:3d} {v.co.x:+8.4f} {v.co.y:+8.4f} {v.co.z:+8.4f} "
          f"{gap:12.4f} {len(adjb[v]):8d}{flag}")
mean = sum(gaps) / len(gaps)
print(f"\ngap: min {min(gaps):.4f}  mean {mean:.4f}  max {max(gaps):.4f}  "
      f"ratio max/mean {max(gaps) / mean:.1f}x")
long = [(i, g) for i, g in enumerate(gaps) if g > 2.5 * mean]
print(f"{len(long)} gaps over 2.5x mean: {long}")
bm.free()

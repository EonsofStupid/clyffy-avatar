"""Cap a boundary loop that is meant to be CLOSED, selected by height.

    blender -b --python tools/cap_loop.py -- work/RETOPO_clyffy.blend 0.020 --write

Args: blend, ZMAX (cap boundary loops lying entirely below this), --write.

WHY BY HEIGHT AND NOT "ALL SMALL LOOPS". `tools/retopo_fill_gaps.py` closes every small loop it
finds and protects a hard-coded list of centres. That is the right tool for unintended pinholes and
the wrong one here, because the shell currently holds THREE loops on purpose — the eye aperture, the
nostril, and the WRIST RING, which is open so the hand can be built off it. A height selector says
exactly what is being closed: the sole, and nothing else.

grid_fill first (it produces quads on an even loop, and the shell is 93% quads), centroid fan as the
fallback. Gated: no ngons, no new non-manifold edges, and the loops that were NOT selected must
survive untouched — closing the wrist ring by accident would be silent and expensive.
"""
import bpy, bmesh, sys, os
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import retopo_gate as gate

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
ZMAX = float(argv[1]) if len(argv) > 1 else 0.020
WRITE = "--write" in argv

bpy.ops.wm.open_mainfile(filepath=BLEND)
scaf = bpy.data.objects["SCAFFOLD"]
rt = bpy.data.objects["retopo_head"]

BEFORE = gate.survey(rt, scaf)
print(f"before: {BEFORE['faces']} faces ({BEFORE['quads']}q {BEFORE['tris']}t {BEFORE['ngons']}n), "
      f"loops {BEFORE['loops']}, non-manifold {BEFORE['nonman']}")

bm = bmesh.new()
bm.from_mesh(rt.data)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()

adj = {}
for e in bm.edges:
    if len(e.link_faces) == 1:
        a, b = e.verts
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
seen, comps = set(), []
for v in adj:
    if v in seen:
        continue
    stack, comp = [v], []
    seen.add(v)
    while stack:
        k = stack.pop()
        comp.append(k)
        for o in adj[k]:
            if o not in seen:
                seen.add(o)
                stack.append(o)
    comps.append(comp)

print(f"\n{len(comps)} boundary loops:")
targets = []
for c in comps:
    zs = [v.co.z for v in c]
    sel = max(zs) < ZMAX
    print(f"  {len(c):3d} verts  z[{min(zs):+.4f},{max(zs):+.4f}]  "
          f"{'CAP' if sel else 'leave open'}")
    if sel:
        targets.append(c)
if not targets:
    print(f"\nnothing lies entirely below z {ZMAX} — nothing to cap")
    sys.exit(0)

made = 0
for c in targets:
    ring_edges = [e for e in bm.edges
                  if len(e.link_faces) == 1 and e.verts[0] in set(c) and e.verts[1] in set(c)]
    n0 = len(bm.faces)
    try:
        bmesh.ops.grid_fill(bm, edges=ring_edges, mat_nr=0, use_smooth=False)
    except (RuntimeError, ValueError):
        pass
    if len(bm.faces) == n0:
        # fallback: centroid fan — manifold by construction, all tris
        ctr = bm.verts.new(sum((v.co for v in c), Vector()) / len(c))
        order = [c[0]]
        prev = None
        while True:
            nx = [o for o in adj[order[-1]] if o is not prev and o not in order]
            if not nx:
                break
            prev = order[-1]
            order.append(nx[0])
        for a, b in zip(order, order[1:] + order[:1]):
            try:
                bm.faces.new((a, b, ctr))
            except ValueError:
                pass
        print(f"  capped {len(c)}-vert loop with a centroid fan")
    else:
        print(f"  capped {len(c)}-vert loop with grid_fill ({len(bm.faces) - n0} faces)")
    made += 1

bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(rt.data)
bm.free()

AFTER = gate.survey(rt, scaf)
print(f"\nafter:  {AFTER['faces']} faces ({AFTER['quads']}q {AFTER['tris']}t {AFTER['ngons']}n), "
      f"loops {AFTER['loops']}, non-manifold {AFTER['nonman']}")

ok, lines = True, []
if AFTER["ngons"] > BEFORE["ngons"]:
    ok = False
    lines.append(f"  !! ngons appeared ({BEFORE['ngons']} -> {AFTER['ngons']})")
if AFTER["nonman"] > BEFORE["nonman"]:
    ok = False
    lines.append(f"  !! non-manifold edges appeared ({BEFORE['nonman']} -> {AFTER['nonman']})")
if AFTER["degenerate"] > BEFORE["degenerate"]:
    ok = False
    lines.append(f"  !! zero-area faces appeared ({BEFORE['degenerate']} -> {AFTER['degenerate']})")
if len(AFTER["loops"]) != len(BEFORE["loops"]) - made:
    ok = False
    lines.append(f"  !! expected {len(BEFORE['loops']) - made} loops to remain, got "
                 f"{len(AFTER['loops'])} — something other than the selected loops changed")
for name in AFTER["apertures"]:
    b, a = BEFORE["apertures"][name], AFTER["apertures"][name]
    if b > 0 and a != b:
        ok = False
        lines.append(f"  !! the {name} changed ({b} -> {a}) — it must not be touched")
    elif b > 0:
        lines.append(f"     {name} intact ({a} verts)")
lines.append(f"     {made} loop(s) capped, {len(AFTER['loops'])} left open by design")
gate.report(f"cap loops below z {ZMAX}", lines, ok)

if ok and WRITE:
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print("saved")
elif ok:
    print("(dry run — pass --write)")
else:
    print("NOT SAVED — the file on disk is unchanged")
    sys.exit(1)

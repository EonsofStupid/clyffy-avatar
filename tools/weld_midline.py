"""Put the mirror-plane boundary EXACTLY on x=0 so the Mirror modifier can weld it.

    blender -b --python tools/weld_midline.py -- work/RETOPO_clyffy.blend 0.005 --write

Args: blend, TOL (boundary verts nearer the plane than this are snapped to it), --write.

FOUND BY `tools/model_check.py`, and invisible to everything before it. Every region gate measures
the BASE mesh — the x>=0 half — where the mirror plane is legitimately an open boundary and always
will be. It is the ASSEMBLED mesh that has to be closed, and there the shell had **13 open slots
running down the midline** and 78 non-manifold edges: the marching code pins a vertex to x=0 only
when it was CREATED there (`abs(x) < 1e-6`), so verts that drifted to x 0.002-0.003 under snapping
and relaxing never got clamped, and the modifier's 0.001 merge threshold cannot close a 0.004 gap.

A flat-shaded render cannot tell you this. The crease along the spine in `work/model_solo/solo_180.png`
looks the same whether it is two flat faces meeting or a slot you could see through.

ONLY OPEN-BOUNDARY VERTS ARE TOUCHED. An interior vertex that happens to sit near the midline is not
part of the seam and moving it would deform the surface for no reason.
"""
import bpy, bmesh, sys, os

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
TOL = float(argv[1]) if len(argv) > 1 and not argv[1].startswith("--") else 0.005
WRITE = "--write" in argv

bpy.ops.wm.open_mainfile(filepath=BLEND)
rt = bpy.data.objects["retopo_head"]


def evaluated_open_loops():
    dg = bpy.context.evaluated_depsgraph_get()
    ev = rt.evaluated_get(dg)
    me = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    openb = [e for e in bm.edges if len(e.link_faces) == 1]
    nonman = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    adj = {}
    for e in openb:
        a, b = e.verts
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    seen, n = set(), 0
    for v in adj:
        if v in seen:
            continue
        stack = [v]
        seen.add(v)
        while stack:
            k = stack.pop()
            for o in adj[k]:
                if o not in seen:
                    seen.add(o)
                    stack.append(o)
        n += 1
    bm.free()
    ev.to_mesh_clear()
    return n, len(openb), nonman


b_loops, b_open, b_nm = evaluated_open_loops()
print(f"before: assembled shell has {b_loops} open loops, {b_open} open edges, "
      f"{b_nm} non-manifold edges")

bm = bmesh.new()
bm.from_mesh(rt.data)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()
bnd = set()
for e in bm.edges:
    if len(e.link_faces) == 1:
        bnd.update(e.verts)
moved, worst = 0, 0.0
for v in bnd:
    if 0.0 < abs(v.co.x) < TOL:
        worst = max(worst, abs(v.co.x))
        v.co.x = 0.0
        moved += 1
bm.to_mesh(rt.data)
bm.free()
print(f"snapped {moved} open-boundary verts onto x=0 (largest correction {worst:.5f})")

mir = next((m for m in rt.modifiers if m.type == "MIRROR"), None)
if mir:
    print(f"mirror: clip={mir.use_clip} merge={mir.use_mirror_merge} "
          f"threshold={mir.merge_threshold:.4f}")

a_loops, a_open, a_nm = evaluated_open_loops()
print(f"after:  assembled shell has {a_loops} open loops, {a_open} open edges, "
      f"{a_nm} non-manifold edges")

# The shell is SUPPOSED to keep exactly five openings after mirroring: two wrist rings, two eye
# apertures... and the nostrils, which mirror to two as well. Six, not five — count them rather
# than assume, and only assert that things got BETTER and nothing became non-manifold.
ok = True
lines = []
if a_loops < b_loops:
    lines.append(f"     open loops {b_loops} -> {a_loops} (midline slots closed)")
elif a_loops == b_loops:
    ok = False
    lines.append(f"  !! open loops unchanged at {a_loops} — the snap did not close anything")
else:
    ok = False
    lines.append(f"  !! open loops INCREASED {b_loops} -> {a_loops}")
if a_nm > b_nm:
    ok = False
    lines.append(f"  !! non-manifold edges increased ({b_nm} -> {a_nm})")
else:
    lines.append(f"     non-manifold edges {b_nm} -> {a_nm}")
print("\n---- GATE: weld midline " + "-" * 44)
for ln in lines:
    print(ln)
print(f"---- {'PASS' if ok else 'FAIL'} " + "-" * 62)

if ok and WRITE:
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print("saved")
elif ok:
    print("(dry run — pass --write)")
else:
    print("NOT SAVED — the file on disk is unchanged")
    sys.exit(1)

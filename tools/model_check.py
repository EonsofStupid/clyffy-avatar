"""Is the ASSEMBLED model closed? Evaluated with modifiers, not the half-mesh.

    blender -b --python tools/model_check.py -- work/RETOPO_clyffy.blend

Every gate so far has measured the BASE mesh — the x>=0 half, where the mirror plane is legitimately
an open boundary and always will be. That says nothing about the thing that actually gets rendered
and rigged. This evaluates the modifier stack (Mirror, Shrinkwrap) and asks the question of the
result: after mirroring, is the seam WELDED or is there a slot down the middle?

The distinction matters and is invisible in a flat-shaded render — the crease along the spine in
`work/model_solo/solo_180.png` looks identical whether it is a shading discontinuity between two
flat faces or a genuine gap.

Read-only.
"""
import bpy, bmesh, sys, os

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
bpy.ops.wm.open_mainfile(filepath=BLEND)
dg = bpy.context.evaluated_depsgraph_get()

PARTS = [o for o in bpy.data.objects
         if o.type == "MESH" and (o.name == "retopo_head" or o.name.startswith("clyffy_"))]

print(f"{'object':24s} {'faces':>7} {'quads':>7} {'open':>6} {'nonman':>7}  mirror")
tot_f = tot_q = tot_open = tot_nm = 0
for ob in sorted(PARTS, key=lambda o: o.name):
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    nq = sum(1 for f in bm.faces if len(f.verts) == 4)
    openb = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    nonman = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    nf = len(bm.faces)
    mir = next((m for m in ob.modifiers if m.type == "MIRROR"), None)
    mtxt = "-"
    if mir:
        mtxt = f"clip={mir.use_clip} merge={mir.use_mirror_merge} thr={mir.merge_threshold:.4f}"
    print(f"{ob.name:24s} {nf:7d} {nq:7d} {openb:6d} {nonman:7d}  {mtxt}")
    tot_f += nf
    tot_q += nq
    tot_open += openb
    tot_nm += nonman
    bm.free()
    ev.to_mesh_clear()

print(f"\nASSEMBLED MODEL: {tot_f} faces, {tot_q} quads ({100.0 * tot_q / max(tot_f, 1):.1f}%), "
      f"{tot_open} open edges, {tot_nm} non-manifold edges")

rt = bpy.data.objects["retopo_head"]
ev = rt.evaluated_get(dg)
me = ev.to_mesh()
bm = bmesh.new()
bm.from_mesh(me)
openb = [e for e in bm.edges if len(e.link_faces) == 1]
if openb:
    # group the shell's open edges so the intentional ones (wrist ring, eye, nostril) can be told
    # apart from a seam that failed to weld
    vs = set()
    for e in openb:
        vs.update(e.verts)
    adj = {}
    for e in openb:
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
    print(f"\nretopo_head AFTER mirroring: {len(comps)} open boundary loops")
    for c in sorted(comps, key=len, reverse=True):
        xs = [v.co.x for v in c]
        ys = [v.co.y for v in c]
        zs = [v.co.z for v in c]
        print(f"  {len(c):4d} verts  x[{min(xs):+.3f},{max(xs):+.3f}] "
              f"y[{min(ys):+.3f},{max(ys):+.3f}] z[{min(zs):+.3f},{max(zs):+.3f}]")
else:
    print("\nretopo_head AFTER mirroring: CLOSED — no open edges at all")
bm.free()
ev.to_mesh_clear()

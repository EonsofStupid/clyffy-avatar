"""Repair named defects IN PLACE. Never regenerates anything.

    blender -b --python tools/fix_defects.py -- work/RETOPO_clyffy.blend spikes --write
    blender -b --python tools/fix_defects.py -- work/RETOPO_clyffy.blend lip --write
    blender -b --python tools/fix_defects.py -- work/RETOPO_clyffy.blend collar --write

WHY THIS FILE EXISTS AT ALL. Operator: *"why is the model constantly remade and never evolving are
you literally starting fresh every fucking time?"* Yes — every defect so far was answered by
regenerating the body from the scaffold, which throws away every fix made since. Nothing
accumulated. This tool only ever edits what is already there.

  spikes  A vertex sitting far off the average of its neighbours — the needle standing out of the
          mouth at the midline. Relaxed onto its neighbourhood, not deleted, so the surrounding
          faces keep their structure.
  lip     The mouth aperture is a RAW OPEN EDGE with no thickness. From any angle it reads as cut
          paper, which is exactly what it is. Given an inward rim so the lip has an edge and the
          cavity behind it goes dark.
  collar  The head/body bridge came out as a sawtooth. `bridge_loops` matched two rims of unequal
          density (115 edges against 123) and zigzagged between them. Relaxed along the ring.
"""
import bpy, bmesh, sys, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
JOB = argv[1] if len(argv) > 1 else "spikes"
WRITE = "--write" in argv
bpy.ops.wm.open_mainfile(filepath=BLEND)
mesh = bpy.data.objects["clyffy_mesh"]

bm = bmesh.new()
bm.from_mesh(mesh.data)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()


def nb_mean(v):
    n = [e.other_vert(v) for e in v.link_edges]
    return sum((o.co for o in n), Vector()) / len(n) if n else v.co.copy()


if JOB == "spikes":
    # a spike is a vertex much further from its neighbourhood than its own edges are long
    found = []
    for v in bm.verts:
        el = [e.calc_length() for e in v.link_edges]
        if len(el) < 2:
            continue
        avg = sum(el) / len(el)
        off = (v.co - nb_mean(v)).length
        if avg > 1e-6 and off > 2.2 * avg:
            found.append((off / avg, v))
    found.sort(reverse=True, key=lambda t: t[0])
    print(f"spikes found: {len(found)}")
    for r, v in found[:12]:
        print(f"  {r:5.1f}x its own edge length at "
              f"({v.co.x:+.4f},{v.co.y:+.4f},{v.co.z:+.4f})")
    for _ in range(4):
        moves = {v: nb_mean(v) for r, v in found}
        for v, m in moves.items():
            v.co = v.co.lerp(m, 0.6)
    print(f"relaxed {len(found)} spike verts onto their neighbourhoods")

elif JOB == "lip":
    # the aperture rims: open-edge loops sitting in the mouth region
    rim = [v for v in bm.verts
           if any(len(e.link_faces) == 1 for e in v.link_edges)
           and v.co.y < -0.15 and 0.685 < v.co.z < 0.760]
    print(f"mouth rim verts: {len(rim)}")
    if not rim:
        print("!! no rim found")
        sys.exit(1)
    edges = [e for e in bm.edges if len(e.link_faces) == 1
             and e.verts[0] in set(rim) and e.verts[1] in set(rim)]
    print(f"  {len(edges)} open rim edges")
    ret = bmesh.ops.extrude_edge_only(bm, edges=edges)
    new_v = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    # push the new rim INWARD (back into the head) and slightly toward the seam, forming a lip
    # edge and the start of a cavity wall
    for v in new_v:
        inward = Vector((0.0, 0.055, 0.0))
        v.co = v.co + inward * 1.0
        v.co.z += (0.726 - v.co.z) * 0.35
    print(f"extruded a {len(new_v)}-vert inner rim back into the head")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

elif JOB == "collar":
    band = [v for v in bm.verts if 0.660 < v.co.z < 0.730]
    print(f"collar band: {len(band)} verts between z 0.660 and 0.730")
    interior = [v for v in band if not any(len(e.link_faces) == 1 for e in v.link_edges)]
    print(f"  {len(interior)} of them are interior (rim verts are left alone)")
    for _ in range(6):
        moves = {v: nb_mean(v) for v in interior}
        for v, m in moves.items():
            v.co = v.co.lerp(m, 0.5)
    print("relaxed the collar band along the ring")

elif JOB == "lipweld":
    # THE MOUTH SPLIT FRAGMENTED THE SEAM. `split_edges` parts every edge INDEPENDENTLY, so at each
    # shared vertex it separated all four faces instead of two — leaving a 4-vert hole per seam quad.
    # 47 of them, strung along the lip line. The mouth did open, but through a row of square holes
    # rather than a parted seam.
    #
    # Repair without re-welding the mouth shut: the duplicate verts sit at IDENTICAL positions, so
    # group them by position and merge only those on the SAME SIDE of the seam. Side is decided by
    # where a vertex's own faces sit relative to it, which is the only thing that distinguishes an
    # upper-lip copy from a lower-lip copy when their coordinates are the same.
    region = [v for v in bm.verts
              if any(len(e.link_faces) == 1 for e in v.link_edges)
              and v.co.y < -0.15 and 0.690 < v.co.z < 0.760]
    print(f"seam-region boundary verts: {len(region)}")
    buckets = {}
    for v in region:
        k = (round(v.co.x, 5), round(v.co.y, 5), round(v.co.z, 5))
        buckets.setdefault(k, []).append(v)
    dup = {k: vs for k, vs in buckets.items() if len(vs) > 1}
    print(f"  {len(dup)} positions hold more than one vertex (the split's duplicates)")

    def side(v):
        zs = [f.calc_center_median().z for f in v.link_faces]
        return 1 if (sum(zs) / len(zs)) > v.co.z else -1

    merged = 0
    for k, vs in dup.items():
        up = [v for v in vs if side(v) > 0]
        dn = [v for v in vs if side(v) < 0]
        for grp in (up, dn):
            if len(grp) > 1:
                bmesh.ops.pointmerge(bm, verts=grp, merge_co=grp[0].co)
                merged += len(grp) - 1
    print(f"  merged {merged} same-side duplicates")
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

elif JOB == "fins":
    # THE NEEDLE. Two back-to-back quads plus two triangles standing ON the mirror plane: 0.0008
    # wide in x, 0.026 tall, normals pointing straight sideways (+-1.00, 0, 0). A wall, not a
    # surface. Left behind when the Mirror modifier was applied and the midline verts did not weld,
    # so instead of merging into one surface the two halves grew a fin between them.
    #
    # It survived every earlier check because it is not an outlying VERTEX (all four corners sit
    # exactly on the surface), not a hole, and not zero-area. The thing that identifies it is its
    # ORIENTATION: a face on the midline whose normal points along x is standing edge-on to the
    # model, which no part of a mirrored surface ever does.
    fins = []
    for f in bm.faces:
        c = f.calc_center_median()
        xs = [v.co.x for v in f.verts]
        ys = [v.co.y for v in f.verts]
        zs = [v.co.z for v in f.verts]
        dx = max(xs) - min(xs)
        # By SHAPE, not orientation. The first version keyed on the normal pointing along x and
        # missed two fins whose normal had drifted to 0.54 — still 0.0008 wide and 0.019 tall.
        # A face on the midline that is many times longer than it is wide IS a wall, whichever way
        # its normal happens to point.
        if abs(c.x) < 0.004 and dx < 0.004 and max(max(ys) - min(ys), max(zs) - min(zs)) > 3 * dx:
            fins.append(f)
    print(f"midline fins found: {len(fins)}")
    for f in fins:
        c = f.calc_center_median()
        print(f"  {len(f.verts)}-gon at ({c.x:+.4f},{c.y:+.4f},{c.z:+.4f}) "
              f"normal x {f.normal.x:+.2f}, area {f.calc_area():.2e}")
    if fins:
        bmesh.ops.delete(bm, geom=fins, context="FACES")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        print(f"deleted {len(fins)} fin faces")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

elif JOB == "unpinch":
    # THE MOUTH IS STILL WELDED AT THE MIDLINE. Verts along the seam that carry FOUR boundary edges
    # are shared by the upper and lower lip at once — the split parted the surface either side of
    # them but never parted them. Open the jaw and that pinch point stretches into the bright needle
    # standing out of the mouth. Rip each one into an upper copy and a lower copy.
    pinch = [v for v in bm.verts
             if sum(1 for e in v.link_edges if len(e.link_faces) == 1) > 2
             and v.co.y < -0.15 and 0.690 < v.co.z < 0.760]
    print(f"pinch verts (4+ boundary edges on the seam): {len(pinch)}")
    for v in pinch:
        print(f"  ({v.co.x:+.4f},{v.co.y:+.4f},{v.co.z:+.4f}) "
              f"{sum(1 for e in v.link_edges if len(e.link_faces) == 1)} boundary edges, "
              f"{len(v.link_faces)} faces")
    ripped = 0
    for v in pinch:
        lower = [f for f in v.link_faces if f.calc_center_median().z < v.co.z]
        if not lower or len(lower) == len(v.link_faces):
            continue
        nv = bm.verts.new(v.co.copy())
        rebuild = []
        for f in lower:
            rebuild.append([nv if x is v else x for x in f.verts])
        bmesh.ops.delete(bm, geom=lower, context="FACES")
        for vl in rebuild:
            try:
                bm.faces.new(vl)
            except ValueError:
                pass
        ripped += 1
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    print(f"ripped {ripped} pinch verts into upper/lower pairs")

elif JOB == "slivers":
    # A 2-VERTEX OPEN LOOP is not a hole, it is a degenerate sliver — two verts joined by two
    # boundary edges, i.e. a face with no area standing up out of the surface. That is the bright
    # needle at the mouth midline, and it survived every earlier check because it is not an
    # outlying VERTEX (its position is fine) and not a big hole; it is a face that should not exist.
    # Also closes any remaining small hole, which at this point is one 9-vert gap on the forehead.
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
        st, c = [v], []
        seen.add(v)
        while st:
            k = st.pop()
            c.append(k)
            for o in adj[k]:
                if o not in seen:
                    seen.add(o)
                    st.append(o)
        comps.append(c)
    tiny = [c for c in comps if len(c) < 3]
    print(f"degenerate slivers (open loops under 3 verts): {len(tiny)}")
    kill = set()
    for c in tiny:
        for v in c:
            ctr = sum((f.calc_center_median() for f in v.link_faces), Vector())
            print(f"  sliver vert at ({v.co.x:+.4f},{v.co.y:+.4f},{v.co.z:+.4f}), "
                  f"{len(v.link_faces)} faces")
            for f in v.link_faces:
                if f.calc_area() < 1e-6:
                    kill.add(f)
    if kill:
        bmesh.ops.delete(bm, geom=list(kill), context="FACES")
        print(f"  deleted {len(kill)} zero-area faces")
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    # anything left that is small and closed-ish gets filled
    adj2 = {}
    for e in bm.edges:
        if len(e.link_faces) == 1:
            a, b = e.verts
            adj2.setdefault(a, []).append(b)
            adj2.setdefault(b, []).append(a)
    seen2, comps2 = set(), []
    for v in adj2:
        if v in seen2:
            continue
        st, c = [v], []
        seen2.add(v)
        while st:
            k = st.pop()
            c.append(k)
            for o in adj2[k]:
                if o not in seen2:
                    seen2.add(o)
                    st.append(o)
        comps2.append(c)
    # the mouth and the four head apertures are intentional; anything else small is a hole
    KEEP = [(Vector((0.047, -0.135, 0.857)), 0.05), (Vector((-0.047, -0.135, 0.857)), 0.05),
            (Vector((0.0356, -0.2677, 0.7844)), 0.035), (Vector((-0.0356, -0.2677, 0.7844)), 0.035)]
    holes = []
    for c in comps2:
        if len(c) >= 20:
            continue
        ctr = sum((v.co for v in c), Vector()) / len(c)
        if any((ctr - k).length < r for k, r in KEEP):
            continue
        holes.append(c)
    print(f"  {len(holes)} unintended holes left to fill")
    for c in holes:
        eds = [e for e in bm.edges if len(e.link_faces) == 1
               and e.verts[0] in set(c) and e.verts[1] in set(c)]
        n0 = len(bm.faces)
        bmesh.ops.holes_fill(bm, edges=eds, sides=0)
        ctr = sum((v.co for v in c), Vector()) / len(c)
        print(f"    filled a {len(c)}-vert hole at "
              f"({ctr.x:+.3f},{ctr.y:+.3f},{ctr.z:+.3f}) with {len(bm.faces) - n0} faces")
    ng = [f for f in bm.faces if len(f.verts) > 4]
    if ng:
        bmesh.ops.poke(bm, faces=ng)
        print(f"  poked {len(ng)} ngon(s) the fill created")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

elif JOB == "teeth":
    # THE TEETH SIT PROUD OF THE LIP. A containment test cannot fix this: the mouth is an open
    # aperture now, so "inside the surface" is undefined right where it matters, and the earlier
    # nearest-normal seat pushed verts the wrong way. Position them against the LIP SEAM instead —
    # the 17 operator-approved points — which is what they were built on in the first place.
    # Every tooth vertex must sit BEHIND its nearest seam point, or it pokes through the lip.
    SEAM = [(0.0000, -0.2876, 0.7260), (0.0090, -0.2871, 0.7240), (0.0190, -0.2856, 0.7220),
            (0.0280, -0.2831, 0.7200), (0.0370, -0.2792, 0.7150), (0.0430, -0.2748, 0.7090),
            (0.0510, -0.2678, 0.7090), (0.0560, -0.2628, 0.7110), (0.0610, -0.2571, 0.7100),
            (0.0660, -0.2503, 0.7110), (0.0700, -0.2436, 0.7150), (0.0720, -0.2396, 0.7140),
            (0.0770, -0.2280, 0.7180), (0.0780, -0.2249, 0.7200), (0.0820, -0.2137, 0.7230),
            (0.0830, -0.2101, 0.7240), (0.0850, -0.2034, 0.7283)]
    PTS = [Vector(p) for p in SEAM] + [Vector((-p[0], p[1], p[2])) for p in SEAM]
    BEHIND = 0.008
    for name in ("clyffy_teeth_upper", "clyffy_teeth_lower", "clyffy_tongue"):
        ob = bpy.data.objects.get(name)
        if not ob:
            continue
        moved, worst = 0, 0.0
        for v in ob.data.vertices:
            p = ob.matrix_world @ v.co
            near = min(PTS, key=lambda q: (Vector((q.x, 0, q.z)) - Vector((p.x, 0, p.z))).length)
            want = near.y + BEHIND
            if p.y < want:
                d = want - p.y
                p.y = want
                v.co = ob.matrix_world.inverted() @ p
                moved += 1
                worst = max(worst, d)
        print(f"  {name}: {moved} verts moved behind the lip, worst {worst:.4f}")

elif JOB == "seat":
    # THE TEETH WERE POKING THROUGH THE LIP. CP10 gated them as "inside the head" against the
    # SCAFFOLD, and the scaffold is not what is rendered — the shell has been tucked, joined,
    # remeshed and split since. The upper band's top edge sat at z 0.7390 against a lip line of
    # 0.726, which is the bright needle standing out of the mouth in work/zoom/lip.png.
    # Re-seat against the mesh that actually exists, with the mouth CLOSED (rest pose).
    from mathutils.bvhtree import BVHTree
    src = bmesh.new()
    src.from_mesh(mesh.data)
    src.transform(mesh.matrix_world)
    tree = BVHTree.FromBMesh(src)
    src.free()
    MARGIN = 0.0015
    for name in ("clyffy_teeth_upper", "clyffy_teeth_lower", "clyffy_tongue"):
        ob = bpy.data.objects.get(name)
        if not ob:
            continue
        moved, worst = 0, 0.0
        for v in ob.data.vertices:
            p = ob.matrix_world @ v.co
            loc, nor, idx, dist = tree.find_nearest(p)
            if loc is None:
                continue
            d = (p - loc).dot(nor)
            if d > -MARGIN:                      # outside, or not far enough inside
                push = (d + MARGIN)
                v.co = ob.matrix_world.inverted() @ (p - nor * push)
                moved += 1
                worst = max(worst, push)
        print(f"  {name}: {moved} verts pushed back inside, worst {worst:.4f}")

else:
    print(f"!! unknown job '{JOB}'")
    sys.exit(1)

nq = sum(1 for f in bm.faces if len(f.verts) == 4)
nt = sum(1 for f in bm.faces if len(f.verts) == 3)
nn = sum(1 for f in bm.faces if len(f.verts) > 4)
nonman = sum(1 for e in bm.edges if len(e.link_faces) > 2)
bm.to_mesh(mesh.data)
bm.free()
print(f"\nclyffy_mesh: {len(mesh.data.polygons)} faces ({nq}q {nt}t {nn}n), "
      f"non-manifold {nonman}")

if WRITE:
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print("saved")

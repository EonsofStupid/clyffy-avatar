"""CP7 FINAL — SEAL the shell: fill every unintended opening, leave only the intended ones.

    blender -b --python tools/retopo_seal.py -- work/RETOPO_clyffy.blend

After the region passes the head shell is continuous except for a BAY hanging off the outer edge
that carries the ear and horn bases plus a notch at the jaw hinge. The label walk showed it:
  ?NNNN...NNNN MMMM...MMMM ??EEEEEEEEEEEE????EEEEEEHHH
(N = on the neck ring, M = on the mirror plane, E/H = ear/horn base, ? = unexplained.)

INTENDED openings, never touched: the MIRROR PLANE (welded by the Mirror modifier), the NECK RING
(CP9's boundary), the EYE apertures and the NOSTRILS (their own boundary components).

Everything else is sealed. Ears and horns become SEPARATE objects sitting on the sealed surface —
like the teeth, tongue and eyeballs — so the shell stays watertight and CP8 is purely additive.

Method per opening: concentric INWARD rings toward the opening's centroid, then a small centre
fan. Manifold by construction (the earned rule: a centroid fan beats n-gon/triangle fill, which
took non-manifold edges from 1 to 8 in the old project). Inside the ear/horn base zones the new
verts are NOT snapped — closest_point_on_mesh there would grab the ear or horn itself and pull the
patch out onto the protrusion; the same exclusion recipe as the nostril.

Boundary cycles are extracted by an EULERIAN walk (every boundary vert has even boundary degree),
because the boundary is no longer a simple cycle — the 2 T-junctions dead-end a naive walk at
81 of 112 verts.

Rerunnable: new verts tagged in vertex group "cp7_seal".
"""
import bpy, bmesh, sys, os, math
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
bpy.ops.wm.open_mainfile(filepath=BLEND)
scaf = bpy.data.objects["SCAFFOLD"]
rt = bpy.data.objects["retopo_head"]
bpy.context.view_layer.objects.active = rt
if rt.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")

RINGS = (0.36, 0.68)          # inward ring positions, 0 = boundary, 1 = centroid


def guide_pts(name):
    o = bpy.data.objects[name]
    return [o.matrix_world @ p.co.to_3d() for s in o.data.splines for p in s.points]


def poly_dist(p, pts):
    best = 1e9
    for i in range(len(pts)):
        a = pts[i]
        b = pts[(i + 1) % len(pts)]
        ab = b - a
        t = 0.0 if ab.length_squared < 1e-12 else max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
        best = min(best, (p - (a + ab * t)).length)
    return best


NECK = guide_pts("vis_neck")
EXCL = []
for g in ("vis_ear_base_R", "vis_horn_base_R"):
    pts = guide_pts(g)
    c = sum(pts, Vector()) / len(pts)
    EXCL.append((c, max((p - c).length for p in pts) * 1.15))


def in_excl(p):
    return any((Vector(p) - c).length < r for c, r in EXCL)


def snap(p, offset=0.0025):
    if in_excl(p):
        return Vector(p)
    ok, loc, nor, _ = scaf.closest_point_on_mesh(Vector(p))
    if not ok:
        return Vector(p)
    s = loc + nor * offset
    return Vector(p) if in_excl(s) else s


# ---- rerun cleanup ---------------------------------------------------------------------------
vg = rt.vertex_groups.get("cp7_seal") or rt.vertex_groups.new(name="cp7_seal")
gi = vg.index
bm = bmesh.new(); bm.from_mesh(rt.data)
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
dl = bm.verts.layers.deform.verify()
old = [v for v in bm.verts if gi in v[dl]]
if old:
    bmesh.ops.delete(bm, geom=old, context="VERTS")
    print(f"cleared previous seal pass: {len(old)} verts")
    bm.edges.ensure_lookup_table()

# ---- boundary components ------------------------------------------------------------------------
bnd = [e for e in bm.edges if e.link_faces and len(e.link_faces) == 1]
adj = {}
for e in bnd:
    a, b = e.verts
    adj.setdefault(a, []).append(e)
    adj.setdefault(b, []).append(e)
seen, comps = set(), []
for v in adj:
    if v in seen:
        continue
    stack, comp = [v], []
    seen.add(v)
    while stack:
        k = stack.pop(); comp.append(k)
        for e in adj[k]:
            o = e.other_vert(k)
            if o not in seen:
                seen.add(o); stack.append(o)
    comps.append(comp)
comps.sort(key=len, reverse=True)
print(f"boundary components: {[len(c) for c in comps]}")
outer = set(comps[0])
outer_edges = [e for e in bnd if e.verts[0] in outer and e.verts[1] in outer]
print(f"outer component: {len(outer)} verts, {len(outer_edges)} edges, "
      f"T-junctions: {sum(1 for v in outer if len(adj[v]) > 2)}")

# ---- Eulerian cycle decomposition of the outer boundary -------------------------------------------
unused = set(outer_edges)
cycles = []
while unused:
    e0 = next(iter(unused))
    start = e0.verts[0]
    cyc = [start]
    cur, ein = start, None
    while True:
        cands = [e for e in adj[cur] if e in unused]
        if not cands:
            break
        if ein is not None and len(cands) > 1:
            din = (cur.co - ein.other_vert(cur).co).normalized()
            cands.sort(key=lambda e: -din.dot((e.other_vert(cur).co - cur.co).normalized()))
        e = cands[0]
        unused.discard(e)
        nxt = e.other_vert(cur)
        ein, cur = e, nxt
        if cur is start:
            break
        cyc.append(cur)
    if len(cyc) >= 3:
        cycles.append(cyc)
print(f"cycles extracted: {[len(c) for c in cycles]}")


def intended(cyc):
    """A cycle is INTENDED — never sealed — if MOST of it lies on the mirror plane or neck ring.

    Two earlier versions of this test were wrong, in opposite directions:
      * "every vert must be mirror-or-neck" — the main outer cycle also carries the jaw-hinge
        notch, so it failed and got sealed: the neck and the mirror plane were CAPPED SHUT.
      * "touches mirror-or-neck" — a genuine 7-vert hole at the CROWN grazes the mirror plane at
        exactly one vert, so it was spared.
    A majority is the honest test: the shell's real edge lies on those two lines; a hole that
    happens to graze one does not.
    """
    m = sum(1 for v in cyc if abs(v.co.x) < 0.0015)
    n = sum(1 for v in cyc if poly_dist(v.co, NECK) < 0.030)
    return (m + n) >= max(3, 0.5 * len(cyc))


new_verts = []
sealed = 0
for cyc in cycles:
    if intended(cyc):
        xs = [v.co.z for v in cyc]
        print(f"  cycle {len(cyc):3d}v — INTENDED (mirror/neck), left open")
        continue
    ctr = sum((v.co for v in cyc), Vector()) / len(cyc)
    ctr = snap(ctr)
    n = len(cyc)
    prev_ring = cyc
    for t in RINGS:
        ring = [bm.verts.new(snap(v.co.lerp(ctr, t))) for v in cyc]
        new_verts.extend(ring)
        for i in range(n):
            j = (i + 1) % n
            try:
                bm.faces.new((prev_ring[i], prev_ring[j], ring[j], ring[i]))
            except ValueError:
                pass
        prev_ring = ring
    cv = bm.verts.new(ctr)
    new_verts.append(cv)
    for i in range(n):
        j = (i + 1) % n
        try:
            bm.faces.new((prev_ring[i], prev_ring[j], cv))
        except ValueError:
            pass
    sealed += 1
    print(f"  cycle {len(cyc):3d}v — SEALED with {len(RINGS)} rings + centre fan "
          f"(centre {ctr.x:+.3f},{ctr.y:+.3f},{ctr.z:.3f})")
print(f"sealed {sealed} opening(s)")

# ---- phase 2: NOTCHES in the intended edge --------------------------------------------------------
# The shell's own edge should lie on the mirror plane and the neck ring. Where it does not, the
# shell falls short of the neck and leaves a bay (the side opening above the jaw). Close each such
# run by projecting it onto the neck ring and stitching a band down to it.
vadj = {}
for e in bnd:
    a, b = e.verts
    vadj.setdefault(a, []).append(b)
    vadj.setdefault(b, []).append(a)


def on_edge(v):
    return abs(v.co.x) < 0.0015 or poly_dist(v.co, NECK) < 0.030


def neck_pt(p):
    best, bp = 1e9, None
    for i in range(len(NECK)):
        a = NECK[i]
        b = NECK[(i + 1) % len(NECK)]
        ab = b - a
        t = 0.0 if ab.length_squared < 1e-12 else max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
        q = a + ab * t
        d = (p - q).length
        if d < best:
            best, bp = d, q
    return bp


notched = 0
for cyc in cycles:
    if not intended(cyc):
        continue
    stray = [v for v in cyc if not on_edge(v)]
    if not stray:
        continue
    ss = set(stray)
    sadj = {v: [o for o in vadj[v] if o in ss] for v in stray}
    seenc = set()
    for v in stray:
        if v in seenc:
            continue
        run, stack = [], [v]
        seenc.add(v)
        while stack:
            k = stack.pop(); run.append(k)
            for o in sadj[k]:
                if o not in seenc:
                    seenc.add(o); stack.append(o)
        if len(run) < 2:
            continue
        # order the run end-to-end
        ends = [x for x in run if len(sadj[x]) <= 1]
        if len(ends) != 2:
            continue
        ordered_run, prev = [ends[0]], None
        while True:
            nx = [o for o in sadj[ordered_run[-1]] if o is not prev]
            if not nx:
                break
            prev = ordered_run[-1]
            ordered_run.append(nx[0])
        # extend by the adjacent on-edge verts so the band closes flush
        for side in (0, -1):
            ext = [o for o in vadj[ordered_run[side]] if o not in ss and on_edge(o)]
            if ext:
                if side == 0:
                    ordered_run.insert(0, ext[0])
                else:
                    ordered_run.append(ext[0])
        lower = []
        for x in ordered_run:
            if poly_dist(x.co, NECK) < 0.030:
                lower.append(x)                       # already on the ring — reuse
            else:
                nv = bm.verts.new(neck_pt(x.co))
                new_verts.append(nv)
                lower.append(nv)
        made = 0
        for i in range(len(ordered_run) - 1):
            quad = [ordered_run[i], ordered_run[i + 1], lower[i + 1], lower[i]]
            uniq = []
            for q in quad:
                if q not in uniq:
                    uniq.append(q)
            if len(uniq) < 3:
                continue
            try:
                bm.faces.new(uniq)
                made += 1
            except ValueError:
                pass
        notched += 1
        print(f"  notch {len(ordered_run)}v — closed onto the neck ring with {made} faces")
print(f"closed {notched} notch(es)")

# relax the new fill (boundary verts stay put — they belong to finished patches)
for _ in range(3):
    moves = {}
    for v in new_verts:
        nb = [e.other_vert(v) for e in v.link_edges]
        if len(nb) >= 2:
            moves[v] = sum((o.co for o in nb), Vector()) / len(nb)
    for v, m in moves.items():
        v.co = v.co.lerp(m, 0.5)
    for v in new_verts:
        v.co = snap(v.co)
for v in new_verts:
    v[dl][gi] = 1.0
    if in_excl(v.co):
        ns = rt.vertex_groups.get("cp5_noshrink")
        if ns:
            v[dl][ns.index] = 1.0

bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(rt.data)
bm.free()

# ---- verify -----------------------------------------------------------------------------------
me = rt.data
nq = sum(1 for p in me.polygons if len(p.vertices) == 4)
nt = sum(1 for p in me.polygons if len(p.vertices) == 3)
ng = len(me.polygons) - nq - nt
bm2 = bmesh.new(); bm2.from_mesh(me); bm2.edges.ensure_lookup_table()
b2 = [e for e in bm2.edges if e.link_faces and len(e.link_faces) == 1]
nm = [e for e in bm2.edges if len(e.link_faces) > 2]
a2 = {}
for e in b2:
    for v in e.verts:
        a2.setdefault(v, []).append(e)
s2, c2 = set(), []
for v in a2:
    if v in s2:
        continue
    st, c = [v], []
    s2.add(v)
    while st:
        k = st.pop(); c.append(k)
        for e in a2[k]:
            o = e.other_vert(k)
            if o not in s2:
                s2.add(o); st.append(o)
    c2.append(c)
c2.sort(key=len, reverse=True)
print(f"\nAFTER SEAL: {len(me.polygons)} faces ({nq} quads {100*nq/len(me.polygons):.1f}%, "
      f"{nt} tris, {ng} ngons), non-manifold edges {len(nm)}")
for c in c2:
    xs = [v.co.x for v in c]; ys = [v.co.y for v in c]; zs = [v.co.z for v in c]
    mid = sum(1 for v in c if abs(v.co.x) < 0.0015)
    nk = sum(1 for v in c if poly_dist(v.co, NECK) < 0.030)
    print(f"  boundary {len(c):3d}v  mirror={mid} neck={nk}  "
          f"x[{min(xs):+.3f},{max(xs):+.3f}] y[{min(ys):+.3f},{max(ys):+.3f}] z[{min(zs):.3f},{max(zs):.3f}]")
bm2.free()
bpy.ops.wm.save_as_mainfile(filepath=BLEND)

# ---- renders ------------------------------------------------------------------------------------
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"; sh.color_type = "OBJECT"
sh.show_cavity = True; sh.cavity_type = "BOTH"
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = sc.render.resolution_y = 900
rt.color = (0.95, 0.35, 0.10, 1.0); rt.show_wire = False
scaf.color = (0.62, 0.62, 0.64, 1.0)
for o in bpy.data.objects:
    if o.name.startswith("vis_") or o.type == "EMPTY":
        o.hide_render = True
w = bpy.data.worlds.new("WSE"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.40, 0.44, 0.41, 1)
sc.world = w
ctr = Vector((0.0, -0.06, 0.83))
cd = bpy.data.cameras.new("CSE"); cam = bpy.data.objects.new("CSE", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"; cd.ortho_scale = 0.56
cd.clip_start = 0.001; cd.clip_end = 100.0
OUT = os.path.join(os.path.dirname(BLEND), "retopo_seal")
os.makedirs(OUT, exist_ok=True)
for tag, hide in (("ctx_", False), ("solo_", True)):
    scaf.hide_render = hide
    for deg in (0, 45, 90, 135, 180, 270):
        a = math.radians(deg)
        cam.location = (ctr.x + math.sin(a) * 2, ctr.y - math.cos(a) * 2, ctr.z + 0.01)
        cam.rotation_euler = (math.radians(89), 0, a)
        sc.render.filepath = os.path.join(OUT, f"{tag}{deg:03d}.png")
        bpy.ops.render.render(write_still=True)
scaf.hide_render = False
print(f"renders -> {OUT}")

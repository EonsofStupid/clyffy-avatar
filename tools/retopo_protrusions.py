"""CP8 — the EAR and the HORN as their own objects, swept from the operator's CP1 base rings.

    blender -b --python tools/retopo_protrusions.py -- work/RETOPO_clyffy.blend

They are SEPARATE OBJECTS, like the teeth, tongue and eyeballs — that is what makes ear motion
riggable later, and it lets the skull surface underneath stay continuous instead of being
interrupted by a socket.

Shrinkwrap is useless on a protrusion: NEAREST_SURFACEPOINT from an ear vert finds the SKULL
behind it. So the shape is MEASURED off the scaffold instead:

  1. fit a plane to the CP1 base ring -> root C and outward axis n (oriented away from the head),
  2. take scaffold verts beyond that plane, sliced into bands along t = dot(v - C, n),
  3. each band's centroid gives the MEDIAL AXIS, so a curved horn stays curved,
  4. each band's true CROSS-SECTION is sampled as max radius per angle in a parallel-transported
     frame — an ear is a flattened flap, not a circle, and this keeps that,
  5. loft the rings, fan the tip.

The radius cap GROWS band by band from the base ring outward. A fixed cylinder pulls in skull
verts near the root (measured: the horn's base band reported radius up to 0.078 against a base
ring of 0.031 — that is the skull, not the horn).

Band 0 is the operator's guide ring itself, so the root seats exactly on the approved circle.
Right side only; a Mirror(X) modifier makes the left.
"""
import bpy, bmesh, sys, os, math
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
bpy.ops.wm.open_mainfile(filepath=BLEND)
scaf = bpy.data.objects["SCAFFOLD"]
HEAD = Vector((0.0, -0.03, 0.86))

# mode "sweep": a tube lofted along the medial axis — correct for the HORN, a solid taper.
# mode "sheet":  a mid-surface grid + Solidify — correct for the EAR, which is a thin FLAP.
#   Measured: rays fired outward from the ear's own axis hit only 6-7 of 16, at every t along it.
#   A flap has no interior for a tube to sit in, so the sweep produced a stubby cone. The flap's
#   mid-surface is found instead by casting ray pairs ALONG ITS THICKNESS and averaging the hits.
SPEC = {
    "clyffy_horn_R": dict(guide="vis_horn_base_R", mode="sweep", nang=12, bands=8),
    # voxel 0.0035 gave a correct but 4218-quad ear — two of those would dwarf the 922-face head.
    # 0.006 keeps the flap's shape at a weight that matches the rest of the model.
    "clyffy_ear_R":  dict(guide="vis_ear_base_R",  mode="remesh", voxel=0.006, target=400),
}
BUILDERS = {}

bms = bmesh.new(); bms.from_mesh(scaf.data)
SV = [v.co.copy() for v in bms.verts]
bms.free()


def guide_pts(name):
    o = bpy.data.objects[name]
    return [o.matrix_world @ p.co.to_3d() for s in o.data.splines for p in s.points]


def build(objname, cfg):
    pts = guide_pts(cfg["guide"])
    P = np.array([list(p) for p in pts])
    c = P.mean(axis=0)
    _, _, vh = np.linalg.svd(P - c)
    n = Vector(vh[2].tolist())
    C = Vector(c.tolist())
    if (C - HEAD).dot(n) < 0:
        n = -n
    base_r = max((p - C).length for p in pts)

    # stable starting frame
    tmp = Vector((0, 0, 1)) if abs(n.z) < 0.9 else Vector((0, 1, 0))
    u = (tmp - n * tmp.dot(n)).normalized()
    w = n.cross(u).normalized()

    # Length is NOT pre-computed. The first version took the 98th percentile of verts inside a
    # straight 1.6x base_r cylinder, but a horn that CURVES puts its tip outside that cylinder —
    # the horn came out 0.0532 and visibly short. Now the sweep simply walks until the rays stop
    # hitting, which is the actual end of the protrusion whatever path it takes.
    NA = cfg["nang"]
    # 0.30 overshot the TIP, where the cross-section becomes smaller than one step: the ray ring
    # fell to 3/12 and the walk stopped at 85% of the horn. Traced band by band — see BUILD_LOG.
    STEP = base_r * 0.15
    MAX_BANDS = 60
    MAXR = 0.16

    # Cross-sections are read by RAY CASTING outward from the medial axis, not by binning
    # scaffold verts. Binning needed a radius cap to keep skull verts out, and any cap that is
    # tight enough to exclude the skull at the root also STRANGLES a feature that widens — the
    # ear flap reaches 0.107 against a 0.061 root and came out a cone. A ray fired from inside
    # the protrusion hits that protrusion's own surface first, so no cap is needed at all.
    def cast_profile(apt, au, aw):
        prof, hits = [None] * NA, []
        for i in range(NA):
            a = 2 * math.pi * i / NA
            d = (au * math.cos(a) + aw * math.sin(a)).normalized()
            ok, loc, _, _ = scaf.ray_cast(apt, d, distance=MAXR)
            if ok:
                prof[i] = (loc - apt).length
                hits.append(loc)
        return prof, hits

    def finish_profile(prof, fallback):
        known = [i for i in range(NA) if prof[i] is not None]
        if not known:
            return [fallback] * NA
        for i in range(NA):
            if prof[i] is None:
                j = min(known, key=lambda k: min(abs(k - i), NA - abs(k - i)))
                prof[i] = prof[j]
        for _ in range(1):
            prof = [(prof[i - 1] + prof[i] * 2 + prof[(i + 1) % NA]) / 4 for i in range(NA)]
        return prof

    p0, h0 = cast_profile(C, u, w)
    axis_pts = [C]
    frames = [(u, w)]
    profs = [finish_profile(p0, base_r)]
    cur_n = n.copy()
    for k in range(1, MAX_BANDS):
        p_try = axis_pts[-1] + cur_n * STEP
        pu, pw = frames[-1]
        pu = (pu - cur_n * pu.dot(cur_n))
        if pu.length < 1e-6:
            break
        pu = pu.normalized()
        pw = cur_n.cross(pu).normalized()
        prof, hits = cast_profile(p_try, pu, pw)
        # Stop only when the ring is MOSTLY missing. A 0.6 threshold cut the horn short at 0.039
        # (true reach ~0.057): near the tip the cross-section is small and a few rays graze past.
        if len(hits) < NA * 0.35:
            break                      # rays are missing — we have left the protrusion
        # Recentre on OPPOSITE-RAY-PAIR MIDPOINTS, not the centroid of the hits. The centroid is
        # pulled toward the far side of an asymmetric section and toward skull hits near the root;
        # traced, it walked the axis clean out of the horn by band 4. A chord's midpoint carries
        # no such bias.
        mids = []
        for i in range(NA // 2):
            if prof[i] is not None and prof[i + NA // 2] is not None:
                a = 2 * math.pi * i / NA
                d = (pu * math.cos(a) + pw * math.sin(a)).normalized()
                mids.append(p_try + d * ((prof[i] - prof[i + NA // 2]) / 2))
        apt = p_try
        if mids:
            ctr = sum(mids, Vector()) / len(mids)
            apt = ctr - cur_n * (ctr - p_try).dot(cur_n)
            prof, hits = cast_profile(apt, pu, pw)
            if len(hits) < NA * 0.35:
                break
        prof = finish_profile(prof, base_r * 0.5)
        d = apt - axis_pts[-1]
        if d.length > 1e-6:
            # damped: half old direction, half new. An undamped update lets one noisy band
            # swing the axis, and every later band inherits the error.
            cur_n = (cur_n * 0.5 + d.normalized() * 0.5).normalized()
        axis_pts.append(apt)
        frames.append((pu, pw))
        profs.append(prof)
        if max(prof) < base_r * 0.12:
            break

    reach = (axis_pts[-1] - C).length
    print(f"{objname}: root ({C.x:+.3f},{C.y:+.3f},{C.z:.3f}) axis "
          f"({n.x:+.3f},{n.y:+.3f},{n.z:+.3f}) reach {reach:.4f}, {len(axis_pts)} bands, "
          f"radius {max(profs[0]):.4f} -> {max(profs[-1]):.4f}")

    bm = bmesh.new()
    rings = []
    for apt, (fu, fw), prof in zip(axis_pts, frames, profs):
        ring = []
        for i in range(NA):
            a = 2 * math.pi * i / NA
            p = apt + fu * (prof[i] * math.cos(a)) + fw * (prof[i] * math.sin(a))
            ring.append(bm.verts.new(p))
        rings.append(ring)
    for A, B in zip(rings, rings[1:]):
        for i in range(NA):
            j = (i + 1) % NA
            bm.faces.new((A[i], A[j], B[j], B[i]))
    tip = bm.verts.new(axis_pts[-1] + cur_n * (max(profs[-1]) * 0.9))
    for i in range(NA):
        bm.faces.new((rings[-1][i], rings[-1][(i + 1) % NA], tip))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    old = bpy.data.objects.get(objname)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    me = bpy.data.meshes.new(objname)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(objname, me)
    bpy.context.scene.collection.objects.link(ob)
    mir = ob.modifiers.new("Mirror", "MIRROR")
    mir.use_axis[0] = True
    mir.use_clip = True
    nq = sum(1 for p in me.polygons if len(p.vertices) == 4)
    nt = sum(1 for p in me.polygons if len(p.vertices) == 3)
    print(f"  -> {len(me.polygons)} faces ({nq} quads, {nt} tip tris), Mirror(X) on")
    return ob


def build_remesh(objname, cfg):
    """the EAR: isolate its scaffold faces and QUAD-REMESH them.

    Three analytic attempts failed (BUILD_LOG 2026-08-06 CP8): the ear is a thin, CURLED flap, so
    a swept tube has no interior to sit in (6 of 16 rays hit), binned cross-sections need a radius
    cap that strangles a widening feature, and a planar mid-surface grid cannot parameterize a
    curl. The shape is already approved — only the topology is wrong, which is the same argument
    the whole retopo lane rests on. So: cut the ear out of the scaffold and give it new topology.
    """
    pts = guide_pts(cfg["guide"])
    P = np.array([list(p) for p in pts])
    c = P.mean(axis=0)
    _, _, vh = np.linalg.svd(P - c)
    n = Vector(vh[2].tolist())
    C = Vector(c.tolist())
    if (C - HEAD).dot(n) < 0:
        n = -n
    base_r = max((p - C).length for p in pts)

    src = bmesh.new(); src.from_mesh(scaf.data)
    keep = []
    for f in src.faces:
        m = f.calc_center_median()
        d = (m - C)
        if d.dot(n) > 0.004 and d.length < 0.24 and (d - n * d.dot(n)).length < 2.4 * base_r:
            keep.append(f)
    bm = bmesh.new()
    vmap = {}
    for f in keep:
        vs = []
        for v in f.verts:
            if v not in vmap:
                vmap[v] = bm.verts.new(v.co)
            vs.append(vmap[v])
        try:
            bm.faces.new(vs)
        except ValueError:
            pass
    src.free()
    # glTF splits verts at UV seams, so the extracted patch is triangle SOUP until it is welded
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-5)
    open_edges = [e for e in bm.edges if len(e.link_faces) == 1]
    if open_edges:
        bmesh.ops.holes_fill(bm, edges=open_edges)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    print(f"{objname}: cut {len(keep)} scaffold faces -> {len(bm.verts)}v {len(bm.faces)}f welded, "
          f"{len([e for e in bm.edges if len(e.link_faces) == 1])} edges still open")

    old = bpy.data.objects.get(objname)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    me = bpy.data.meshes.new(objname)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(objname, me)
    bpy.context.scene.collection.objects.link(ob)

    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    # voxel first: guarantees a closed manifold for the quad remesher to work on
    ob.data.remesh_voxel_size = cfg["voxel"]
    bpy.ops.object.voxel_remesh()
    print(f"  voxel {cfg['voxel']}: {len(ob.data.polygons)} faces")
    # quadriflow refuses on inconsistent normals; the voxel output is manifold but not guaranteed
    # consistently wound, so recalculate before asking
    fix = bmesh.new(); fix.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(fix, faces=list(fix.faces))
    fix.to_mesh(ob.data)
    fix.free()
    try:
        bpy.ops.object.quadriflow_remesh(target_faces=cfg["target"])
    except Exception as exc:
        print(f"  !! quadriflow failed ({exc}) — leaving the voxel mesh")
    mir = ob.modifiers.new("Mirror", "MIRROR")
    mir.use_axis[0] = True
    mir.use_clip = True
    nq = sum(1 for p in ob.data.polygons if len(p.vertices) == 4)
    nt = sum(1 for p in ob.data.polygons if len(p.vertices) == 3)
    print(f"  -> {len(ob.data.polygons)} faces ({nq} quads, {nt} tris), Mirror(X) on")
    return ob


def build_sheet(objname, cfg):
    """the EAR: a quad grid on the flap's MID-SURFACE, thickened by Solidify"""
    pts = guide_pts(cfg["guide"])
    P = np.array([list(p) for p in pts])
    c = P.mean(axis=0)
    _, _, vh = np.linalg.svd(P - c)
    n = Vector(vh[2].tolist())
    C = Vector(c.tolist())
    if (C - HEAD).dot(n) < 0:
        n = -n

    # Isolate the flap GEOMETRICALLY. Flood-fill is not available: the scaffold came in as glTF,
    # whose vertices are split at UV seams, so mesh connectivity is fragmented — a fill from the
    # ear tip returned FOUR verts. Select beyond-the-plane verts inside a generous cylinder, then
    # refine: PCA, drop the thickness outliers (skull), PCA again on what is left.
    base_r = max((p - C).length for p in pts)
    comp = [v for v in SV
            if (v - C).dot(n) > 0.004
            and ((v - C) - n * (v - C).dot(n)).length < 2.2 * base_r
            and (v - C).length < 0.22]
    E = np.array([list(p) for p in comp])
    ec = E.mean(axis=0)
    _, _, evh = np.linalg.svd(E - ec)
    e3t = Vector(evh[2].tolist())
    ECt = Vector(ec.tolist())
    tvals = sorted(abs((p - ECt).dot(e3t)) for p in comp)
    keep = tvals[int(len(tvals) * 0.90)]
    comp = [p for p in comp if abs((p - ECt).dot(e3t)) <= keep]
    E = np.array([list(p) for p in comp])
    ec = E.mean(axis=0)
    _, _, evh = np.linalg.svd(E - ec)
    e1 = Vector(evh[0].tolist())          # along the ear
    e2 = Vector(evh[1].tolist())          # across it
    e3 = Vector(evh[2].tolist())          # through its thickness
    EC = Vector(ec.tolist())
    if (EC - C).dot(e1) < 0:
        e1 = -e1
    s = [(Vector(p.tolist()) - EC).dot(e1) for p in E]
    uu = [(Vector(p.tolist()) - EC).dot(e2) for p in E]
    th = [(Vector(p.tolist()) - EC).dot(e3) for p in E]
    print(f"{objname}: flap {len(comp)} verts, extent along {max(s) - min(s):.4f}, "
          f"across {max(uu) - min(uu):.4f}, thickness {max(th) - min(th):.4f}")

    NL, NW = cfg["nlen"], cfg["nwid"]
    grid, PROBE = [], max(th) - min(th) + 0.03
    for a in range(NL):
        srow = min(s) + (max(s) - min(s)) * a / (NL - 1)
        row = []
        for b in range(NW):
            uv = min(uu) + (max(uu) - min(uu)) * b / (NW - 1)
            base = EC + e1 * srow + e2 * uv
            ok1, l1, _, _ = scaf.ray_cast(base + e3 * PROBE, -e3, distance=2 * PROBE)
            ok2, l2, _, _ = scaf.ray_cast(base - e3 * PROBE, e3, distance=2 * PROBE)
            row.append((l1 + l2) / 2 if (ok1 and ok2) else None)
        grid.append(row)

    bm = bmesh.new()
    vmap = {}
    for a in range(NL):
        for b in range(NW):
            if grid[a][b] is not None:
                vmap[(a, b)] = bm.verts.new(grid[a][b])
    made = 0
    for a in range(NL - 1):
        for b in range(NW - 1):
            q = [(a, b), (a, b + 1), (a + 1, b + 1), (a + 1, b)]
            if all(k in vmap for k in q):
                bm.faces.new([vmap[k] for k in q])
                made += 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    old = bpy.data.objects.get(objname)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    me = bpy.data.meshes.new(objname)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(objname, me)
    bpy.context.scene.collection.objects.link(ob)
    sol = ob.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = max(th) - min(th)
    sol.offset = 0.0
    mir = ob.modifiers.new("Mirror", "MIRROR")
    mir.use_axis[0] = True
    mir.use_clip = True
    print(f"  -> {made} quads on the mid-surface, Solidify {sol.thickness:.4f}, Mirror(X) on")
    return ob


BUILDERS.update(sweep=build, sheet=build_sheet, remesh=build_remesh)
built = [BUILDERS[v["mode"]](k, v) for k, v in SPEC.items()]
bpy.ops.wm.save_as_mainfile(filepath=BLEND)

# ---- renders ------------------------------------------------------------------------------------
sc = bpy.context.scene
rt = bpy.data.objects["retopo_head"]
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"; sh.color_type = "OBJECT"
sh.show_cavity = True; sh.cavity_type = "BOTH"
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = sc.render.resolution_y = 900
scaf.color = (0.60, 0.60, 0.62, 1.0)
rt.color = (0.95, 0.45, 0.15, 1.0)
for o in built:
    o.color = (0.25, 0.65, 0.95, 1.0)
for o in bpy.data.objects:
    if o.name.startswith("vis_") or o.type == "EMPTY":
        o.hide_render = True
w = bpy.data.worlds.new("W8"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.40, 0.44, 0.41, 1)
sc.world = w
ctr = Vector((0.0, -0.04, 0.88))
cd = bpy.data.cameras.new("C8"); cam = bpy.data.objects.new("C8", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"; cd.ortho_scale = 0.44
cd.clip_start = 0.001; cd.clip_end = 100.0
OUT = os.path.join(os.path.dirname(BLEND), "retopo_cp8")
os.makedirs(OUT, exist_ok=True)
for tag, hide in (("", False), ("solo_", True)):
    scaf.hide_render = hide
    for deg in (0, 60, 90, 180):
        a = math.radians(deg)
        cam.location = (ctr.x + math.sin(a) * 2, ctr.y - math.cos(a) * 2, ctr.z + 0.01)
        cam.rotation_euler = (math.radians(89), 0, a)
        sc.render.filepath = os.path.join(OUT, f"cp8_{tag}{deg:03d}.png")
        bpy.ops.render.render(write_still=True)
scaf.hide_render = False
cam.location = (ctr.x, ctr.y, ctr.z + 2)
cam.rotation_euler = (0, 0, 0)
sc.render.filepath = os.path.join(OUT, "cp8_top.png")
bpy.ops.render.render(write_still=True)
print(f"renders -> {OUT}")

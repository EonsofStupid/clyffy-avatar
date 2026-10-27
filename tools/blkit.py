"""The toolkit that lives INSIDE the live Blender session. Loaded into every command's namespace.

Not run directly — `tools/blender_daemon.py` execs this once at startup, so every `tools/bl` command
can call these by name.

THE POINT. A one-shot script has to re-derive everything it needs on every run: open the file, walk
the mesh, build the query, render a picture, exit. In a live session the expensive things are
already in memory, so the useful unit of work stops being "a script" and becomes "a question". This
file is the vocabulary for asking.

Three capabilities matter more than the rest:

  stat()/loops()/islands()  — STRUCTURED SIGHT. Numbers about topology, not pixels. The 0.0008-wide
                              fin that took six render passes to find is one `narrow_faces()` call.
  shot()                    — VIEWPORT capture via OpenGL: ~50 ms against seconds for a full render,
                              and it shows OVERLAYS — selection, wireframe, normals. A render can
                              only show the surface; a viewport shot can show what I am about to
                              operate on, which is the thing worth agreeing about before it happens.
  snap()/restore()          — a live session keeps mistakes as well as progress. Snapshot before
                              anything destructive; restore is a second, not a rebuild.
"""
import bpy, bmesh, os, json, math, time
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, "work")
SHOTS = os.path.join(WORK, "shots")
SNAPS = os.path.join(WORK, "snaps")
for d in (SHOTS, SNAPS):
    os.makedirs(d, exist_ok=True)

MAIN = "clyffy_mesh"


def obj(name=None):
    return bpy.data.objects[name or MAIN]


def _bm(name=None):
    o = obj(name)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    return o, bm


# ---- structured sight ---------------------------------------------------------------------------

def stat(name=None):
    """The health of a mesh in one call: face mix, open edges, non-manifold, islands."""
    o, bm = _bm(name)
    q = sum(1 for f in bm.faces if len(f.verts) == 4)
    t = sum(1 for f in bm.faces if len(f.verts) == 3)
    n = sum(1 for f in bm.faces if len(f.verts) > 4)
    op = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    nm = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    deg = sum(1 for f in bm.faces if f.calc_area() < 1e-9)
    seen, isl = set(), 0
    for v in bm.verts:
        if v in seen:
            continue
        isl += 1
        st = [v]
        seen.add(v)
        while st:
            k = st.pop()
            for e in k.link_edges:
                x = e.other_vert(k)
                if x not in seen:
                    seen.add(x)
                    st.append(x)
    bm.free()
    return dict(name=o.name, verts=len(o.data.vertices), faces=len(o.data.polygons),
                quads=q, tris=t, ngons=n, open_edges=op, non_manifold=nm,
                degenerate=deg, islands=isl)


def loops(name=None, where=None):
    """Open boundary loops with their extents. `where` filters on the loop's centre."""
    o, bm = _bm(name)
    adj = {}
    for e in bm.edges:
        if len(e.link_faces) == 1:
            a, b = e.verts
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
    seen, out = set(), []
    for v in adj:
        if v in seen:
            continue
        st, c = [v], []
        seen.add(v)
        while st:
            k = st.pop()
            c.append(k)
            for x in adj[k]:
                if x not in seen:
                    seen.add(x)
                    st.append(x)
        ctr = sum((x.co for x in c), Vector()) / len(c)
        if where and not where(ctr):
            continue
        xs = [x.co.x for x in c]
        ys = [x.co.y for x in c]
        zs = [x.co.z for x in c]
        out.append(dict(n=len(c), at=[round(q, 4) for q in ctr],
                        x=[round(min(xs), 4), round(max(xs), 4)],
                        y=[round(min(ys), 4), round(max(ys), 4)],
                        z=[round(min(zs), 4), round(max(zs), 4)]))
    bm.free()
    out.sort(key=lambda d: -d["n"])
    return out


def narrow_faces(name=None, ratio=3.0, maxwide=0.005, where=None):
    """Faces far longer than they are wide — walls, fins, slivers. The needle detector."""
    o, bm = _bm(name)
    out = []
    for f in bm.faces:
        c = f.calc_center_median()
        if where and not where(c):
            continue
        xs = [v.co.x for v in f.verts]
        ys = [v.co.y for v in f.verts]
        zs = [v.co.z for v in f.verts]
        dx, dy, dz = max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)
        thin = min(dx, dy, dz)
        long_ = max(dx, dy, dz)
        if thin < maxwide and long_ > ratio * max(thin, 1e-6):
            out.append(dict(i=f.index, n=len(f.verts), at=[round(q, 4) for q in c],
                            thin=round(thin, 5), long=round(long_, 5),
                            area=f.calc_area()))
    bm.free()
    out.sort(key=lambda d: -d["long"])
    return out


def off_surface(name=None, ref="SCAFFOLD", tol=0.012, where=None):
    """Verts further than `tol` from a reference surface — flyers, and lost form."""
    from mathutils.bvhtree import BVHTree
    r = bpy.data.objects[ref]
    b = bmesh.new()
    b.from_mesh(r.data)
    b.transform(r.matrix_world)
    tree = BVHTree.FromBMesh(b)
    b.free()
    o = obj(name)
    out = []
    for v in o.data.vertices:
        p = o.matrix_world @ v.co
        if where and not where(p):
            continue
        loc, nor, idx, d = tree.find_nearest(p)
        if loc is not None and d > tol:
            out.append(dict(i=v.index, at=[round(q, 4) for q in p], d=round(d, 5)))
    out.sort(key=lambda x: -x["d"])
    return out


# ---- selection: make the operator see what I am about to touch -----------------------------------

def sel(pred, name=None, mode="VERT"):
    """Select verts matching a predicate AND drop into edit mode, so it is visible in the viewport."""
    o = obj(name)
    bpy.context.view_layer.objects.active = o
    for x in bpy.context.selected_objects:
        x.select_set(False)
    o.select_set(True)
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(o.data)
    bm.verts.ensure_lookup_table()
    bpy.ops.mesh.select_all(action="DESELECT")
    n = 0
    for v in bm.verts:
        if pred(v.co):
            v.select_set(True)
            n += 1
    bm.select_flush(True)
    bmesh.update_edit_mesh(o.data)
    return n


def unsel():
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


# ---- viewport capture ---------------------------------------------------------------------------

def _view3d():
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            if a.type == "VIEW_3D":
                return w, a
    return None, None


def look(at=(0, 0, 0.5), dist=1.2, yaw=0.0, pitch=-15.0):
    """Aim the viewport. Cheap, and it is what makes a shot mean something specific."""
    w, a = _view3d()
    if a is None:
        return False
    r3d = a.spaces.active.region_3d
    r3d.view_location = Vector(at)
    r3d.view_distance = dist
    e = Vector((math.radians(90 + pitch), 0.0, math.radians(yaw)))
    r3d.view_rotation = e.to_quaternion() if hasattr(e, "to_quaternion") else r3d.view_rotation
    import mathutils
    r3d.view_rotation = mathutils.Euler(
        (math.radians(90 + pitch), 0.0, math.radians(yaw)), "XYZ").to_quaternion()
    r3d.update()
    return True


def shot(tag="shot", at=None, dist=1.2, yaw=0.0, pitch=-15.0, wire=False, overlays=True):
    """OpenGL viewport grab — ~50 ms, and it SHOWS OVERLAYS (selection, wireframe).

    A full render can only show the surface. This can show what is selected, which is the thing
    worth agreeing on before an edit rather than after it.
    """
    w, a = _view3d()
    if a is None:
        return {"error": "no VIEW_3D area — is the UI up?"}
    sp = a.spaces.active
    # Restore overlays afterwards. Leaving them off silently kills every
    # selection highlight in the operator's viewport.
    _ov_was = sp.overlay.show_overlays
    sp.overlay.show_overlays = overlays
    sp.shading.type = "SOLID"
    sp.shading.light = "STUDIO"
    sp.shading.show_cavity = True
    sp.overlay.show_wireframes = wire
    if at is not None:
        look(at, dist, yaw, pitch)
    sc = bpy.context.scene
    sc.render.resolution_x = sc.render.resolution_y = 1000
    sc.render.image_settings.file_format = "PNG"
    path = os.path.join(SHOTS, f"{tag}.png")
    sc.render.filepath = path
    with bpy.context.temp_override(window=w, area=a, region=[r for r in a.regions
                                                             if r.type == "WINDOW"][0]):
        bpy.ops.render.opengl(write_still=True, view_context=True)
    sp.overlay.show_overlays = _ov_was
    return path


# ---- repair ---------------------------------------------------------------------------------------

def split_boundary_fans(name=None, where=None):
    """Give every boundary vertex degree 2 by splitting its face fan into separate corners.

    A boundary vertex carrying 4 boundary edges is TWO corners pinched into one point. Extruding
    such a boundary makes four faces share an edge — that is exactly what took non-manifold from
    0 to 22 on the first attempt at the mouth rim, and reverting it looked like the extrude was
    wrong when the BOUNDARY was wrong.

    Faces around the vertex are grouped by reachability through NON-boundary edges; each group
    after the first gets its own copy of the vertex.

    Deletion uses FACES_ONLY on purpose: plain FACES also removes vertices that become orphaned,
    and the rebuild list still refers to them ("1 BMVert has been removed").
    """
    o = obj(name)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.verts.ensure_lookup_table()
    made = 0
    for v in list(bm.verts):
        if not v.is_valid:
            continue
        if len([e for e in v.link_edges if len(e.link_faces) == 1]) <= 2:
            continue
        if where and not where(v.co):
            continue
        fs = list(v.link_faces)
        if len(fs) < 2:
            continue
        parent = {f: f for f in fs}

        def find(f):
            while parent[f] is not f:
                parent[f] = parent[parent[f]]
                f = parent[f]
            return f

        for e in v.link_edges:
            if len(e.link_faces) == 2:
                a, b = e.link_faces
                if a in parent and b in parent:
                    parent[find(a)] = find(b)
        groups = {}
        for f in fs:
            groups.setdefault(find(f), []).append(f)
        if len(groups) < 2:
            continue
        for grp in list(groups.values())[1:]:
            nv = bm.verts.new(v.co.copy())
            rebuild = [[nv if x is v else x for x in f.verts] for f in grp]
            bmesh.ops.delete(bm, geom=grp, context="FACES_ONLY")
            for vl in rebuild:
                try:
                    bm.faces.new(vl)
                except ValueError:
                    pass
            made += 1
        bm.verts.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()
    return made


def loop_degrees(name=None, where=None):
    """Boundary-degree histogram per loop. `{2: n}` means a clean cycle; anything else is a pinch."""
    o, bm = _bm(name)
    adj = {}
    for e in bm.edges:
        if len(e.link_faces) == 1 and (not where or all(where(v.co) for v in e.verts)):
            a, b = e.verts
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
    seen, out = set(), []
    for v in adj:
        if v in seen:
            continue
        st, c = [v], []
        seen.add(v)
        while st:
            k = st.pop()
            c.append(k)
            for x in adj[k]:
                if x not in seen:
                    seen.add(x)
                    st.append(x)
        cs = set(c)
        degs = {}
        for x in c:
            d = sum(1 for e in x.link_edges
                    if len(e.link_faces) == 1 and e.other_vert(x) in cs)
            degs[d] = degs.get(d, 0) + 1
        out.append(dict(n=len(c), degrees=degs, clean=(set(degs) == {2})))
    bm.free()
    out.sort(key=lambda d: -d["n"])
    return out


# ---- snapshots ----------------------------------------------------------------------------------

def snap(tag):
    """Save a restore point. A live session keeps mistakes as well as progress."""
    p = os.path.join(SNAPS, f"{tag}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=p, copy=True)
    return p


def restore(tag):
    p = os.path.join(SNAPS, f"{tag}.blend")
    bpy.ops.wm.open_mainfile(filepath=p)
    return p


def save(path=None):
    p = path or os.path.join(WORK, "RETOPO_clyffy.blend")
    bpy.ops.wm.save_as_mainfile(filepath=p)
    return p


# ---- the operator's desk ---------------------------------------------------------------------
#
# Everything below exists so the operator can WATCH. The session already had structured sight and
# viewport capture; what it did not have was a body language. A selection that only I can query is
# not reviewable — it has to be on his screen, framed, with the tool in hand and the intent written
# down BEFORE the edit lands. That is the difference between "I changed it, here is a render, was
# that alright" and "here is what I am about to change, stop me".

NARRATION = "CLYFFY_NARRATION"


def say(text, keep=40):
    """Put a line where the operator can read it: the status bar and a scrolling text block.

    The status bar is the one piece of Blender chrome that is always on screen no matter which
    editor has focus, so it is where the *current* intent goes. The text block keeps the history,
    because a line that has scrolled past is the same as a line never written.
    """
    try:
        bpy.context.workspace.status_text_set(str(text))
    except Exception:
        pass
    t = bpy.data.texts.get(NARRATION) or bpy.data.texts.new(NARRATION)
    t.write(f"{time.strftime('%H:%M:%S')}  {text}\n")
    if len(t.lines) > keep * 4:
        t.clear()
        t.write(f"{time.strftime('%H:%M:%S')}  (log trimmed)\n")
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            if a.type == "TEXT_EDITOR":
                a.spaces.active.text = t
                a.spaces.active.top = max(0, len(t.lines) - 12)
    return text


def tool(name="builtin.select_box"):
    """Put a tool in the toolbar's hand, visibly.

    `bpy.ops.wm.tool_set_by_id` moves the highlighted button in the T-panel and swaps the gizmo in
    the viewport. It changes nothing about the mesh — it is pure signalling, and that is the point:
    the operator sees which instrument is being picked up before it is used on his model.
    """
    w, a = _view3d()
    if a is None:
        return {"error": "no VIEW_3D"}
    with bpy.context.temp_override(window=w, area=a,
                                   region=[r for r in a.regions if r.type == "WINDOW"][0]):
        bpy.ops.wm.tool_set_by_id(name=name)
    return name


def desk(select="VERT", tool_id=None, xray=False, wire=True, cavity=True, toolbar=True):
    """Arrange the workspace the way a modeller would have arranged it before starting.

    Select mode, x-ray, overlays, the T-panel open with a tool active. All of it is state the
    operator would otherwise have to be told about in prose; here he just looks at his screen.
    """
    w, a = _view3d()
    if a is None:
        return {"error": "no VIEW_3D"}
    sp = a.spaces.active
    modes = {"VERT": (True, False, False), "EDGE": (False, True, False), "FACE": (False, False, True)}
    bpy.context.tool_settings.mesh_select_mode = modes.get(select, modes["VERT"])
    sp.shading.type = "SOLID"
    sp.shading.show_cavity = cavity
    sp.shading.show_xray = xray
    sp.overlay.show_overlays = True
    sp.overlay.show_wireframes = wire
    sp.show_region_toolbar = toolbar
    if tool_id:
        tool(tool_id)
    return {"select": select, "xray": xray, "wire": wire, "tool": tool_id}


def cursor(co):
    bpy.context.scene.cursor.location = Vector(co)
    return list(co)


def frame(dist=None):
    """Frame the current selection — 'look at this', in the operator's own muscle memory."""
    w, a = _view3d()
    if a is None:
        return False
    with bpy.context.temp_override(window=w, area=a,
                                   region=[r for r in a.regions if r.type == "WINDOW"][0]):
        bpy.ops.view3d.view_selected()
    if dist:
        a.spaces.active.region_3d.view_distance = dist
    return True


def propose(label, pred, tag=None, at=None, dist=0.16, yaw=0.0, pitch=-10.0,
            select="VERT", tool_id="builtin.select_box"):
    """SHOW THE EDIT BEFORE MAKING IT. The veto point.

    Selects what is about to be touched, arranges the desk, aims the viewport, writes the intent to
    the status bar and grabs a shot. Nothing is modified. The operator is looking at the same pixels
    I am, with the affected geometry lit up, and can take the mouse instead of letting it happen.

    Returns the count and the shot path, so the count can also be sanity-checked before committing —
    a predicate that selects 4000 verts when it should select 40 is caught here rather than after.
    """
    desk(select=select, tool_id=tool_id)
    n = sel(pred)
    say(f"PROPOSE: {label}  [{n} verts]")
    if at is None:
        frame(dist)
        p = shot(tag or "propose")
    else:
        p = shot(tag or "propose", at=at, dist=dist, yaw=yaw, pitch=pitch, wire=True)
    return {"label": label, "n": n, "shot": p}


def clutter(hide=True, keep=("clyffy_mesh",)):
    """Hide the scaffolding, cameras and vis curves. Forty-five frustums were being drawn across
    every render — I was reading my own evidence through a cage."""
    n = 0
    for o in bpy.context.scene.objects:
        if o.name in keep:
            continue
        if o.type in ("CAMERA", "CURVE", "EMPTY", "LIGHT") or o.name.startswith(("SCAF", "vis_", "ref_")):
            o.hide_set(hide)
            n += 1
    return n


def gate(where=None, name=None):
    """The mouth's definition of done, as numbers. Every prior gate measured topology hygiene, which
    the mouth passes while looking like a gash — so this one measures SHAPE defects: slivers, spikes
    and wafer-thin bands. A gate that cannot fail the current mesh is not a gate."""
    o, bm = _bm(name)
    where = where or (lambda co: co.y < -0.19 and 0.64 < co.z < 0.78)
    fs = [f for f in bm.faces if all(where(v.co) for v in f.verts)]

    def slim(f):
        p = f.calc_perimeter()
        return f.calc_area() / (p * p) if p > 0 else 0.0

    spikes = []
    for v in bm.verts:
        if not where(v.co):
            continue
        nb = [e.other_vert(v) for e in v.link_edges]
        if len(nb) < 3:
            continue
        mid = sum((n.co for n in nb), Vector()) / len(nb)
        d = (v.co - mid).length
        if d > 0.004:
            spikes.append((round(d, 4), [round(c, 4) for c in v.co]))
    spikes.sort(reverse=True)
    r = {"faces": len(fs),
         "tris": sum(1 for f in fs if len(f.verts) == 3),
         "slivers_lt_0.010": sum(1 for f in fs if slim(f) < 0.010),
         "slivers_lt_0.004": sum(1 for f in fs if slim(f) < 0.004),
         "spikes_gt_0.004": len(spikes),
         "worst_spike": spikes[0] if spikes else None,
         "open_edges": sum(1 for e in bm.edges if len(e.link_faces) == 1
                           and all(where(v.co) for v in e.verts))}
    r["PASS"] = (r["slivers_lt_0.010"] == 0 and r["spikes_gt_0.004"] == 0)
    bm.free()
    return r


# ---- SCULPT: the SHAPING half of Blender ----------------------------------------------------------
# Everything above this line inspects or selects. That was half a workshop: I could measure a ragged
# rim precisely and then only fix it by rebuilding topology. Blender's actual shaping tools — the
# brushes an artist would reach for — were never wired to the signal, so they were never used.
#
# These drive the REAL brushes, not a maths imitation. That matters twice over: the deformation is
# the one Blender ships (so it behaves the way the operator's other sculpting tool taught him), and
# after `brush(...)` the session is left with that brush live and loaded, so he can take the mouse
# and continue the same stroke by hand. Watch, then take over.
#
# In Blender 5.x brushes are ASSETS, not datablocks: a fresh file has zero of them
# (`bpy.data.brushes` is empty) and they are pulled from the essentials library on activation.

SCULPT_ASSETS = "brushes/essentials_brushes-mesh_sculpt.blend"
MASK_ATTR = ".sculpt_mask"          # 5.x keeps the sculpt mask as a POINT float attribute


def sculpt_on(name=None, sym_x=True):
    """Enter sculpt mode on the object, X-symmetry on by default (he is symmetric; say so once)."""
    o = obj(name)
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    if o.mode != "SCULPT":
        bpy.ops.object.mode_set(mode="SCULPT")
    sc = bpy.context.tool_settings.sculpt
    sc.use_symmetry_x = bool(sym_x)
    return {"mode": o.mode, "symmetry_x": sc.use_symmetry_x,
            "brush": sc.brush.name if sc.brush else None}


def sculpt_off(name=None):
    o = obj(name)
    if o.mode != "OBJECT":
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.mode_set(mode="OBJECT")
    return {"mode": o.mode}


def brush(kind="Clay Strips", size=None, strength=None, invert=False, name=None, sym_x=True):
    """Load and activate a real sculpt brush by its asset name, and leave it live for the mouse.

    kind is the essentials asset name — "Grab", "Smooth", "Clay Strips", "Inflate/Deflate",
    "Draw Sharp", "Pinch/Magnify", "Flatten/Contrast", "Snake Hook", "Elastic Grab", "Pose",
    "Crease Polish", "Mask", ... (see `brushes()` for the full list this build ships).

    size is in PIXELS (brush radius on screen) because that is what the brush actually uses;
    strength is 0..1. invert flips the stroke (Draw carves instead of building, Inflate deflates).
    """
    sculpt_on(name, sym_x=sym_x)
    bpy.ops.brush.asset_activate(
        asset_library_type="ESSENTIALS",
        asset_library_identifier="",
        relative_asset_identifier=f"{SCULPT_ASSETS}/Brush/{kind}")
    b = bpy.context.tool_settings.sculpt.brush
    if b is None:
        return {"error": f"brush '{kind}' did not activate — check brushes()"}
    if size is not None:
        b.size = int(size)
    if strength is not None:
        b.strength = float(strength)
    # `direction` is per-brush: Draw/Inflate carry ADD/SUBTRACT, Grab only DEFAULT. And the RNA
    # enum lies — it reports the STATIC superset (ADD/SUBTRACT) while the live enum is ('DEFAULT'),
    # so checking enum_items passes and the assignment still raises. Try it and see.
    want = "SUBTRACT" if invert else "ADD"
    try:
        b.direction = want
    except TypeError:
        if invert:
            return {"error": f"'{b.name}' cannot be inverted (its direction is fixed)",
                    "brush": b.name, "size": b.size, "strength": round(b.strength, 3)}
    say(f"BRUSH: {b.name}  size {b.size}px  strength {b.strength:.2f}"
        f"{'  (inverted)' if invert else ''}  — take the mouse whenever you like")
    return {"brush": b.name, "size": b.size, "strength": round(b.strength, 3),
            "direction": b.direction, "symmetry_x": bpy.context.tool_settings.sculpt.use_symmetry_x}


def brushes():
    """What this build actually ships — asked, not remembered."""
    import os as _os
    p = _os.path.join(bpy.utils.system_resource("DATAFILES"), "assets", SCULPT_ASSETS)
    with bpy.data.libraries.load(p, assets_only=True) as (src, _dst):
        return sorted(src.brushes)


def _mask_layer(o):
    a = o.data.attributes.get(MASK_ATTR)
    if a is None:
        a = o.data.attributes.new(MASK_ATTR, "FLOAT", "POINT")
    return a


def sculpt_mask(pred=None, name=None, protect_rest=True):
    """THE VETO POINT FOR SCULPTING. Masked geometry is untouchable by every brush.

    `pred(v)` marks the WORKABLE region (mask 0); everything else is protected (mask 1). That is the
    inverse of how it reads, and it is deliberate: the safe default is that a stroke can only affect
    the few hundred verts I named, so a brush that would otherwise smear halfway across the face
    physically cannot. Masked area renders DARK in the viewport, so the protected zone is visible to
    the operator before any stroke — the same contract `propose()` gives for topology edits.

    pred=None clears the mask (everything workable again).
    """
    o = obj(name)
    was = o.mode
    if was != "OBJECT":
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.mode_set(mode="OBJECT")
    a = _mask_layer(o)
    me = o.data
    if pred is None:
        for i in range(len(me.vertices)):
            a.data[i].value = 0.0
        n = len(me.vertices)
        free = n
    else:
        mw = o.matrix_world
        n = len(me.vertices)
        free = 0
        for i, v in enumerate(me.vertices):
            co = mw @ v.co
            ok = bool(pred(co))
            a.data[i].value = 0.0 if ok else (1.0 if protect_rest else 0.0)
            free += ok
    if was != "OBJECT":
        bpy.ops.object.mode_set(mode=was)
    say(f"MASK: {free} verts workable, {n - free} protected")
    return {"workable": free, "protected": n - free, "total": n}


def _region3d():
    w, a = _view3d()
    if a is None:
        return None, None, None, None
    rgn = [r for r in a.regions if r.type == "WINDOW"][0]
    return w, a, rgn, a.spaces.active.region_3d


def sculpt_stroke(pts, size=None, strength=None, invert=None, name=None, pressure=1.0):
    """Run a real brush stroke along a path of WORLD-SPACE points.

    The brush raycasts from the screen, so the path is projected to region coordinates with the
    current view — which means the view must be LOOKING at the target and the points must be on the
    near side. Points that project off-screen or behind the camera are dropped and reported; a stroke
    that silently did nothing is the failure mode worth catching.
    """
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    o = obj(name)
    sculpt_on(name)
    b = bpy.context.tool_settings.sculpt.brush
    if b is None:
        return {"error": "no active brush — call brush() first"}
    if size is not None:
        b.size = int(size)
    if strength is not None:
        b.strength = float(strength)
    if invert is not None:
        b.direction = "SUBTRACT" if invert else "ADD"
    w, a, rgn, r3d = _region3d()
    if a is None:
        return {"error": "no VIEW_3D area"}
    elems, dropped = [], 0
    for i, p in enumerate(pts):
        co = Vector(p)
        s = location_3d_to_region_2d(rgn, r3d, co)
        if s is None or not (0 <= s.x <= rgn.width and 0 <= s.y <= rgn.height):
            dropped += 1
            continue
        elems.append({
            "name": f"s{i}", "location": co[:], "mouse": (s.x, s.y),
            "mouse_event": (0.0, 0.0), "pressure": float(pressure), "size": float(b.size),
            "pen_flip": False, "x_tilt": 0.0, "y_tilt": 0.0,
            "time": float(i) * 0.01, "is_start": (i == 0),
        })
    if len(elems) < 2:
        return {"error": "stroke has <2 on-screen points — aim the view at the target first",
                "dropped": dropped, "kept": len(elems)}
    before = [v.co.copy() for v in o.data.vertices]
    with bpy.context.temp_override(window=w, area=a, region=rgn):
        bpy.ops.sculpt.brush_stroke(stroke=elems, mode="NORMAL")
    moved = sum(1 for i, v in enumerate(o.data.vertices) if (v.co - before[i]).length > 1e-6)
    mx = max(((v.co - before[i]).length for i, v in enumerate(o.data.vertices)), default=0.0)
    say(f"STROKE: {b.name} x{len(elems)} — {moved} verts moved, max {mx:.4f}")
    return {"brush": b.name, "points": len(elems), "dropped": dropped,
            "verts_moved": moved, "max_move": round(mx, 5)}


def relax(pred, iters=6, factor=0.5, keep_shape=True, name=None):
    """Deterministic tangential relax — the MEASURED alternative to a Smooth stroke.

    A Smooth brush is the right tool when the operator is driving and judging by eye. When the fix
    needs a number attached (a rim whose spikes must come under a threshold), this does the same
    job without a viewport, without projection, and reports what it moved.

    keep_shape projects each move onto the surface tangent, so it evens out SPACING without
    deflating the form — the failure mode of plain Laplacian smoothing on a thin rim.
    """
    o, bm = _bm(name)
    mw = o.matrix_world
    sel_v = [v for v in bm.verts if pred(mw @ v.co)]
    if not sel_v:
        bm.free()
        return {"error": "predicate selected nothing"}
    ss = set(sel_v)
    before = {v.index: v.co.copy() for v in sel_v}
    for _ in range(iters):
        moves = {}
        for v in sel_v:
            nb = [e.other_vert(v) for e in v.link_edges]
            if len(nb) < 2:
                continue
            tgt = sum((n.co for n in nb), Vector()) / len(nb)
            d = (tgt - v.co) * factor
            if keep_shape:
                nrm = v.normal
                if nrm.length > 1e-9:
                    d = d - nrm.normalized() * d.dot(nrm.normalized())
            moves[v] = v.co + d
        for v, co in moves.items():
            v.co = co
    moved = sum(1 for v in sel_v if (v.co - before[v.index]).length > 1e-6)
    mx = max(((v.co - before[v.index]).length for v in sel_v), default=0.0)
    bm.to_mesh(o.data)
    o.data.update()
    bm.free()
    say(f"RELAX: {len(sel_v)} verts, {iters} iters — {moved} moved, max {mx:.4f}")
    return {"selected": len(sel_v), "moved": moved, "max_move": round(mx, 5), "iters": iters}


# ---- THE CHANNEL: signals out of Blender, instead of photographs of it ----------------------------
# The daemon is request/reply: I ask, it answers. That leaves two holes.
#
#   1. NO PUSH. Nothing tells me what changed — least of all what the OPERATOR just did with the
#      mouse. I find out by taking another picture and comparing it to my memory of the last one.
#   2. NO GEOMETRY AS DATA. A profile, a silhouette, a rim's shape — I have been reading those off
#      renders, which means inferring numbers from pixels I rendered from numbers.
#
# `stream_on()` closes the first: Blender's own signals (depsgraph, msgbus, operator history) are
# subscribed and appended to work/bl_events.jsonl with a monotonic seq, so `events(since=N)` returns
# everything that happened since I last looked — including his strokes, mode switches and undos.
# `section()` closes the second: the mesh cut by a plane, returned as ordered polylines.

EVENTS = os.path.join(WORK, "bl_events.jsonl")
_EV = {"seq": 0, "on": False, "co": None, "lastop": None, "t": 0.0, "subs": []}


def _emit(kind, **kw):
    _EV["seq"] += 1
    rec = {"seq": _EV["seq"], "t": round(time.time(), 3), "kind": kind}
    rec.update(kw)
    try:
        with open(EVENTS, "a") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass
    return rec


def _co_array(o):
    import numpy as np
    n = len(o.data.vertices)
    a = np.empty(n * 3, dtype="f4")
    o.data.vertices.foreach_get("co", a)
    return a.reshape(n, 3)


@bpy.app.handlers.persistent
def _on_depsgraph(scene, depsgraph):
    """What actually changed on the mesh, as numbers — the event I kept re-rendering to discover."""
    if not _EV["on"]:
        return
    now = time.time()
    if now - _EV["t"] < 0.25:            # sculpt fires this continuously; don't drown the stream
        return
    try:
        o = bpy.data.objects.get(MAIN)
        if o is None:
            return
        wm = bpy.context.window_manager
        ops = getattr(wm, "operators", None)
        last = ops[-1].bl_idname if ops and len(ops) else None
        if last != _EV["lastop"]:
            _EV["lastop"] = last
            if last:
                _emit("operator", op=last)
        import numpy as np
        cur = _co_array(o)
        prev = _EV["co"]
        if prev is not None and prev.shape == cur.shape:
            d = np.linalg.norm(cur - prev, axis=1)
            moved = int((d > 1e-6).sum())
            if moved:
                idx = int(d.argmax())
                _emit("mesh_changed", verts_moved=moved, max_move=round(float(d.max()), 5),
                      at=[round(float(x), 4) for x in cur[idx]], op=last)
        elif prev is not None:
            _emit("mesh_rebuilt", verts=int(cur.shape[0]), was=int(prev.shape[0]), op=last)
        _EV["co"] = cur
        _EV["t"] = now
    except Exception as e:
        _emit("error", where="depsgraph", msg=repr(e)[:200])


def _sub_rna(path_owner, path, kind, getter):
    key = object()
    bpy.msgbus.subscribe_rna(
        key=(path_owner, path), owner=key, args=(kind, getter), notify=_on_rna, options={"PERSISTENT"})
    _EV["subs"].append(key)


def _on_rna(kind, getter):
    if not _EV["on"]:
        return
    try:
        _emit(kind, value=getter())
    except Exception:
        pass


def stream_on():
    """Subscribe to Blender's signals and start appending them to the event stream."""
    if _on_depsgraph not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph)
    for h, k in ((bpy.app.handlers.undo_post, "undo"), (bpy.app.handlers.redo_post, "redo"),
                 (bpy.app.handlers.save_post, "saved"), (bpy.app.handlers.load_post, "loaded")):
        fn = (lambda kind: (lambda *a: _EV["on"] and _emit(kind)))(k)
        h.append(fn)
    o = bpy.data.objects.get(MAIN)
    _sub_rna(bpy.types.Object, "mode", "mode", lambda: bpy.context.object.mode if bpy.context.object else None)
    _sub_rna(bpy.types.Sculpt, "brush", "brush",
             lambda: (bpy.context.tool_settings.sculpt.brush.name
                      if bpy.context.tool_settings.sculpt.brush else None))
    _EV["on"] = True
    _EV["co"] = _co_array(o) if o else None
    r = _emit("stream_on", obj=MAIN, verts=int(_EV["co"].shape[0]) if _EV["co"] is not None else 0)
    return {"streaming": True, "file": EVENTS, "seq": r["seq"]}


def stream_status():
    """Is the stream ACTUALLY receiving, not merely flagged on?

    The first version kept a boolean and trusted it. `restore()` calls `open_mainfile`, which drops
    every non-persistent handler — so the flag read True while nothing was listening, and the two
    edits after a restore left no trace at all. A monitor that lies about being alive is worse than
    no monitor. This reports the registration itself, and `stream_on()` is idempotent so it can be
    re-armed after any file load.
    """
    reg = _on_depsgraph in bpy.app.handlers.depsgraph_update_post
    return {"listening": reg, "flag": _EV["on"], "seq": _EV["seq"],
            "healthy": bool(reg and _EV["on"]), "file": EVENTS}


def stream_off():
    _EV["on"] = False
    return {"streaming": False, "seq": _EV["seq"]}


def events(since=0, kinds=None, limit=200):
    """Everything that happened since seq `since` — his mouse included. No picture required."""
    if not os.path.exists(EVENTS):
        return {"seq": _EV["seq"], "events": []}
    out = []
    with open(EVENTS) as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("seq", 0) <= since:
                continue
            if kinds and r.get("kind") not in kinds:
                continue
            out.append(r)
    return {"seq": _EV["seq"], "n": len(out), "events": out[-limit:]}


def section(axis="x", at=0.0, name=None, where=None, decimals=4):
    """Cut the mesh with an axis plane; return ORDERED polylines. A profile as numbers.

    This is the query I was substituting renders for. The collar's shape, the muzzle's profile, the
    back of the skull — all of them are a plane cut away from being exact, and a polyline can be
    measured, compared between two states, and checked for the fold or shelf that a render only
    hints at.

    Returns each loop as points in the plane's own 2D frame (u, v) plus the 3D points, so a shelf
    reads as a run of equal v, and a fold reads as u going backwards.
    """
    o, bm = _bm(name)
    mw = o.matrix_world
    ai = {"x": 0, "y": 1, "z": 2}[axis]
    ua, va = [i for i in (0, 1, 2) if i != ai]
    segs = []
    for f in bm.faces:
        pts = []
        vs = list(f.verts)
        for i in range(len(vs)):
            a = mw @ vs[i].co
            b = mw @ vs[(i + 1) % len(vs)].co
            da, db = a[ai] - at, b[ai] - at
            if (da > 0) == (db > 0) or (da == 0 and db == 0):
                continue
            t = da / (da - db)
            pts.append(a.lerp(b, t))
        if len(pts) == 2:
            if where is None or (where(pts[0]) or where(pts[1])):
                segs.append((pts[0], pts[1]))
    # chain segments end-to-end
    used = [False] * len(segs)
    loops_out = []
    TOL = 1e-5
    for i in range(len(segs)):
        if used[i]:
            continue
        used[i] = True
        chain = [segs[i][0], segs[i][1]]
        grew = True
        while grew:
            grew = False
            for j in range(len(segs)):
                if used[j]:
                    continue
                a, b = segs[j]
                if (chain[-1] - a).length < TOL:
                    chain.append(b); used[j] = True; grew = True
                elif (chain[-1] - b).length < TOL:
                    chain.append(a); used[j] = True; grew = True
                elif (chain[0] - a).length < TOL:
                    chain.insert(0, b); used[j] = True; grew = True
                elif (chain[0] - b).length < TOL:
                    chain.insert(0, a); used[j] = True; grew = True
        loops_out.append(chain)
    bm.free()
    res = []
    for ch in sorted(loops_out, key=len, reverse=True):
        closed = (ch[0] - ch[-1]).length < TOL
        per = sum((ch[k] - ch[k + 1]).length for k in range(len(ch) - 1))
        res.append({
            "points": len(ch), "closed": closed, "length": round(per, 4),
            "uv": [[round(p[ua], decimals), round(p[va], decimals)] for p in ch],
        })
    return {"axis": axis, "at": at, "loops": len(res), "frame": "uv = "
            + "".join("xyz"[i] for i in (ua, va)), "profiles": res}


def ghosts(fix=False):
    """Objects that RENDER but are invisible in the viewport — and therefore invisible to shot().

    This is the bug class that produced FOUR HORNS: `SCAFFOLD` (216k verts, unrigged) was
    viewport-hidden but render-visible, so it appeared as a static ghost in every render including
    the motion test, while every viewport grab I took looked perfectly clean. A sense organ that
    cannot see a defect will never report it — so this asks the scene directly.

    `fix=True` hides the offenders from render. The reverse mismatch (viewport-visible,
    render-hidden) is normal and left alone: that is what reference image planes are for.
    """
    bad = [o.name for o in bpy.data.objects if o.hide_viewport and not o.hide_render]
    if fix:
        for n in bad:
            bpy.data.objects[n].hide_render = True
    return {"render_ghosts": bad, "fixed": bool(fix and bad),
            "will_render": sorted(o.name for o in bpy.data.objects
                                  if o.type == "MESH" and not o.hide_render and not o.hide_viewport)}


# --------------------------------------------------------------- SHAPE SENSES
#
# Added 2026-08-15 after the gloved hand passed EVERY health metric — 0 ngons,
# 0 non-manifold, 0 degenerate, containment down to one vertex — and still
# rendered as a stack of primitives. The defect was real and geometric, and
# nothing in this file could see it. These two ask about SHAPE rather than
# health, and both return numbers so a render is a confirmation, never a
# discovery.


def creases(name=None, angle=50.0, min_run=0.005, top=12, concave_only=False):
    """Where the surface BREAKS C1 — the number behind "it reads as assembled".

    Two lofted forms placed side by side meet along a hard dihedral edge. That
    is exactly what the eye reads as "glued together", and it is a measurement,
    not an opinion: the angle between the two faces sharing an edge.

    The SIGN matters. A convex break is often intentional (a hoof's sole rim,
    a cuff lip). A CONCAVE break is where one form was jammed into another
    without blending — the palm-to-finger step. `concave_only=True` asks just
    for those.

    Returns connected runs of hard edges, longest first, each with where it is
    and how sharp it gets — so the answer is "a 0.06-long 91-degree concave
    seam at the knuckles", not "it looks assembled".
    """
    o, bm = _bm(name)
    mw = o.matrix_world
    thr = math.radians(angle)
    hard = []
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        try:
            a = e.calc_face_angle_signed()
        except (ValueError, RuntimeError):
            continue
        if abs(a) < thr:
            continue
        if concave_only and a >= 0:
            continue
        hard.append((e, a))

    # cluster into connected runs through shared verts
    idx = {e.index: (e, a) for e, a in hard}
    seen, runs = set(), []
    for e0, _ in hard:
        if e0.index in seen:
            continue
        stack, run = [e0], []
        seen.add(e0.index)
        while stack:
            e = stack.pop()
            run.append(e)
            for v in e.verts:
                for e2 in v.link_edges:
                    if e2.index in idx and e2.index not in seen:
                        seen.add(e2.index)
                        stack.append(e2)
        runs.append(run)

    out = []
    for run in runs:
        L = sum(e.calc_length() for e in run)
        if L < min_run:
            continue
        angs = [idx[e.index][1] for e in run]
        pts = [mw @ v.co for e in run for v in e.verts]
        out.append({
            "edges": len(run),
            "length": round(L, 4),
            "max_deg": round(math.degrees(max(angs, key=abs)), 1),
            "concave": bool(min(angs) < 0),
            "at": [round(sum(p[i] for p in pts) / len(pts), 4) for i in (0, 1, 2)],
        })
    out.sort(key=lambda r: r["length"], reverse=True)
    total = sum(r["length"] for r in out)
    bm.free()
    return {"object": o.name, "threshold_deg": angle, "runs": len(out),
            "hard_length": round(total, 4),
            "worst": out[:top]}


def pose_state():
    """Is the model POSED right now? Anything measuring the evaluated mesh must
    ask, because a canon model sheet is neutral and a posed model is not.

    Found the hard way: the first real silhouette() run reported the head as
    wildly asymmetric. Nothing was wrong with the model — the scene was sitting
    on frame 45 of clyffy_motion_test with the head turned 18 degrees, the jaw
    open and both ears rotated. A shape sense that does not say so invites a
    fix to a defect that is not there.
    """
    out = []
    for rig in [o for o in bpy.data.objects if o.type == "ARMATURE"]:
        bones = []
        for b in rig.pose.bones:
            m = b.matrix_basis
            e = m.to_euler()
            if m.translation.length > 1e-5 or abs(e.x) + abs(e.y) + abs(e.z) > 1e-4:
                bones.append({"bone": b.name,
                              "deg": [round(math.degrees(a), 2) for a in e]})
        act = None
        if rig.animation_data and rig.animation_data.action:
            act = rig.animation_data.action.name
        out.append({"rig": rig.name, "posed_bones": bones, "action": act,
                    "pose_position": rig.data.pose_position})
    return {"frame": bpy.context.scene.frame_current,
            "at_rest": all(not r["posed_bones"] or r["pose_position"] == "REST"
                           for r in out),
            "rigs": out}


def silhouette(view="front", bands=80, gap=0.012, names=None, at_rest=True):
    """The model's OUTLINE as numbers, per height band — the shape sense that
    replaces holding a render up against the canon art and squinting.

    Uses the EVALUATED depsgraph, so Mirror and every other modifier count: this
    is the silhouette that will actually render, not the one the base mesh has.

    Everything is normalised by total height, so the result is scale-free and
    can be compared directly against the same measurement taken off a canon
    image (see tools/silh_art.py). Per band it reports the horizontal extents,
    the width, and how many separate RUNS there are — which is what makes legs,
    the gap between arm and torso, and a cloven toe legible as numbers.
    """
    # Measure at REST unless told otherwise: the canon sheets are neutral, so a
    # posed silhouette is not comparable to them. pose_position toggling leaves
    # the pose itself untouched.
    saved = []
    if at_rest:
        for rig in [o for o in bpy.data.objects if o.type == "ARMATURE"]:
            saved.append((rig, rig.data.pose_position))
            rig.data.pose_position = "REST"
        bpy.context.view_layer.update()

    dg = bpy.context.evaluated_depsgraph_get()
    if names is None:
        names = [o.name for o in bpy.data.objects
                 if o.type == "MESH" and not o.hide_render and not o.hide_viewport]
    H, V = ({"front": (0, 2), "side": (1, 2), "top": (0, 1)})[view]

    pts = []
    for n in names:
        o = bpy.data.objects.get(n)
        if o is None or o.type != "MESH":
            continue
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        mw = o.matrix_world
        for v in me.vertices:
            p = mw @ v.co
            pts.append((p[H], p[V]))
        ev.to_mesh_clear()
    for rig, mode in saved:
        rig.data.pose_position = mode
    bpy.context.view_layer.update()
    if not pts:
        return {"error": "no visible mesh geometry", "names": names}

    vmin = min(p[1] for p in pts)
    vmax = max(p[1] for p in pts)
    height = vmax - vmin
    if height <= 0:
        return {"error": "zero height"}
    hmin_all = min(p[0] for p in pts)
    hmax_all = max(p[0] for p in pts)

    span = max(hmax_all - hmin_all, 1e-9)
    rows = [[] for _ in range(bands)]
    for h, v in pts:
        b = int((v - vmin) / height * bands)
        rows[min(max(b, 0), bands - 1)].append(h)

    prof = []
    for b, hs in enumerate(rows):
        if not hs:
            prof.append({"v": round((b + 0.5) / bands, 4), "n": 0})
            continue
        # Runs by a GAP THRESHOLD in model units, not by binning. Binning
        # counted the space BETWEEN VERTICES as a gap in the body and reported
        # 20 runs across a solid torso.
        ordered = sorted(hs)
        segs, s0, prev = [], ordered[0], ordered[0]
        for h in ordered[1:]:
            if h - prev > gap:
                segs.append((s0, prev))
                s0 = h
            prev = h
        segs.append((s0, prev))
        lo, hi = ordered[0], ordered[-1]
        prof.append({
            "v": round((b + 0.5) / bands, 4),
            "n": len(hs),
            "lo": round(lo, 4), "hi": round(hi, 4),
            "w": round((hi - lo) / height, 4),      # width, in heights
            "c": round(((lo + hi) / 2) / height, 4),  # centre, in heights
            "runs": len(segs),
            "segs": [[round(a, 4), round(b2, 4)] for a, b2 in segs],
        })
    return {"view": view, "objects": len(names), "points": len(pts),
            "measured_at_rest": bool(at_rest), "pose": pose_state(),
            "height": round(height, 4),
            "v_range": [round(vmin, 4), round(vmax, 4)],
            "h_range": [round(hmin_all, 4), round(hmax_all, 4)],
            "bands": bands, "profile": prof}


def edit_sel(name="clyffy_mesh"):
    """Read the face selection LIVE, and run mesh ops with a real VIEW_3D override.

    Two traps, both hit on 2026-08-27 while asking the operator to mark the muzzle pink:
      * In EDIT mode ``o.data.polygons`` is the STALE pre-edit copy. It reported 49 selected
        faces while the live bmesh held 793. Always read through ``bmesh.from_edit_mesh``.
      * ``bpy.ops.mesh.*`` called from the daemon has no VIEW_3D context and silently no-ops.
        ``select_all(action="DESELECT")`` left 793 faces selected and returned as if it worked.
    """
    import bmesh
    o = bpy.data.objects[name]
    if o.mode != "EDIT":
        return {"error": f"{name} is in {o.mode}, not EDIT"}
    bm = bmesh.from_edit_mesh(o.data)
    bm.faces.ensure_lookup_table()
    idx = [f.index for f in bm.faces if f.select]
    cs = [tuple(round(v, 4) for v in bm.faces[i].calc_center_median()) for i in idx]
    return {"object": name, "n": len(idx), "faces": idx, "centers": cs,
            "total_faces": len(bm.faces)}


def edit_op(fn, name="clyffy_mesh"):
    """Run a callable under a VIEW_3D override so bpy.ops.mesh.* actually applies."""
    import bmesh
    w, a = _view3d()
    if a is None:
        return {"error": "no VIEW_3D area"}
    rg = [r for r in a.regions if r.type == "WINDOW"][0]
    with bpy.context.temp_override(window=w, area=a, region=rg):
        fn()
    o = bpy.data.objects[name]
    if o.mode == "EDIT":
        bmesh.update_edit_mesh(o.data)
    a.tag_redraw()
    return True

"""The GATE — the invariants a region must not break, checked before the file is written.

Imported by the region builders; not run directly.

    import retopo_gate as gate
    before = gate.survey(rt, scaf)
    ...build...
    after  = gate.survey(rt, scaf, group="cp9_shoulders")
    ok, lines = gate.verdict(before, after, expect=CFG.get("expect", {}))

WHY THIS EXISTS. Every defect in this build that reached the operator got there because nothing
measured it, and every defect caught early was caught by a number or by a render. The failures are
on record and each one is a check below:

  * the TENTACLE (retopo_skull.py) — un-snapped points flew off into space.  -> `max_off` surface
  * the NAPE front coming out on the WRONG SIDE of the head.                 -> `bbox` / front box
  * ring smoothing CORRUPTING the approved mouth-patch anchors.              -> `frozen` witness
  * the mouth rings BURYING the eye aperture on the first cheek run.         -> `apertures`
  * three chin verts sitting 0.004 PAST the mirror plane.                    -> `min_x`
  * teeth POKING THROUGH the head, invisible until the jaw drops.            -> containment (parts)

The rule the whole file encodes: A REGION IS NOT SAVED UNTIL IT PASSES. `retopo_cleanup.py` already
worked this way and it is the reason the tri pass could be run without fear. Everything else saved
unconditionally and had to be un-done by hand.
"""
import bmesh
from mathutils import Vector

# Openings that exist ON PURPOSE. A region that closes one of these has destroyed a feature, which
# is far worse than leaving a gap: a gap is visible, a filled eye socket looks like solid work.
# (centre, radius, name) — same centres tools/retopo_fill_gaps.py protects.
PROTECTED = [
    (Vector((0.047, -0.135, 0.857)), 0.045, "eye aperture"),
    (Vector((0.0356, -0.2677, 0.7844)), 0.030, "nostril"),
]

MIRROR_EPS = 0.0005     # a vert this far past x=0 is mirror-plane leakage


def _boundary_cycles(bm):
    """the open boundary as COMPONENTS of the boundary subgraph.

    Not a loop walk: patches meeting at a point leave T-junctions (verts with 3+ boundary edges)
    and a walk dead-ends there — that is exactly how the nape front came out of the wrong side of
    the head. Components are structural and cannot dead-end.
    """
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
    return comps


def survey(ob, scaf=None, group=None):
    """Everything the gate compares. `group` names the verts this pass created."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    s = dict(
        faces=len(bm.faces),
        quads=sum(1 for f in bm.faces if len(f.verts) == 4),
        tris=sum(1 for f in bm.faces if len(f.verts) == 3),
        ngons=sum(1 for f in bm.faces if len(f.verts) > 4),
        nonman=sum(1 for e in bm.edges if len(e.link_faces) > 2),
        degenerate=sum(1 for f in bm.faces if f.calc_area() < 1e-9),
        verts=len(bm.verts),
    )

    comps = _boundary_cycles(bm)
    s["loops"] = sorted((len(c) for c in comps), reverse=True)

    # a protected opening survives if SOME boundary component still lies inside its sphere
    ap = {}
    for ctr, r, name in PROTECTED:
        hit = [c for c in comps if all((v.co - ctr).length < r for v in c)]
        ap[name] = len(hit[0]) if hit else 0
    s["apertures"] = ap

    # the verts this pass created — the only ones a region is allowed to have moved
    if group and ob.vertex_groups.get(group):
        gi = ob.vertex_groups[group].index
        dl = bm.verts.layers.deform.verify()
        new = [v for v in bm.verts if gi in v[dl]]
        s["new_count"] = len(new)
        if new:
            xs = [v.co.x for v in new]
            ys = [v.co.y for v in new]
            zs = [v.co.z for v in new]
            s["bbox"] = (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))
            s["min_x"] = min(xs)
            if scaf is not None:
                offs = []
                for v in new:
                    ok, loc, _, _ = scaf.closest_point_on_mesh(v.co)
                    if ok:
                        offs.append((v.co - loc).length)
                s["max_off"] = max(offs) if offs else 0.0
                s["mean_off"] = sum(offs) / len(offs) if offs else 0.0
            # the LONGEST new edge, and WHERE it is. A gate that only says "something stretched"
            # sends me guessing; the horn cost two wrong guesses before instrumenting found the
            # cause in one run. A gate should localise its own failure.
            worst_e, worst_l = None, 0.0
            for v in new:
                for e in v.link_edges:
                    ln = e.calc_length()
                    if ln > worst_l:
                        worst_l, worst_e = ln, e
            s["max_edge"] = worst_l
            if worst_e is not None:
                a, b = worst_e.verts
                s["max_edge_at"] = (tuple(round(c, 4) for c in a.co),
                                    tuple(round(c, 4) for c in b.co))
    bm.free()
    return s


def verdict(before, after, expect=None, step=None, front_spacing=None):
    """(ok, lines). `expect` is the region's OWN declaration of what it should produce."""
    expect = expect or {}
    lines, ok = [], True

    def bad(msg):
        nonlocal ok
        ok = False
        lines.append("  !! " + msg)

    def good(msg):
        lines.append("     " + msg)

    # ---- structural: these hold for EVERY region, no exceptions -------------------------------
    if after["nonman"] > before["nonman"]:
        bad(f"non-manifold edges appeared ({before['nonman']} -> {after['nonman']})")
    else:
        good(f"non-manifold edges {after['nonman']} (was {before['nonman']})")

    if after["ngons"] > before["ngons"]:
        bad(f"ngons appeared ({before['ngons']} -> {after['ngons']})")

    if after["degenerate"] > before["degenerate"]:
        bad(f"zero-area faces appeared ({before['degenerate']} -> {after['degenerate']})")

    for name in after["apertures"]:
        b, a = before["apertures"][name], after["apertures"][name]
        if b > 0 and a == 0:
            bad(f"the {name} was CLOSED by this pass ({b} verts -> gone)")
        elif b > 0 and a != b:
            bad(f"the {name} changed size ({b} -> {a} verts)")
        elif b > 0:
            good(f"{name} intact ({a} verts)")

    if after["faces"] <= before["faces"]:
        bad(f"no faces were added ({before['faces']} -> {after['faces']})")

    # ---- the new geometry itself ----------------------------------------------------------------
    if "new_count" not in after:
        lines.append("     (no vertex group given — new-geometry checks skipped)")
        return ok, lines

    good(f"{after['new_count']} new verts, +{after['faces'] - before['faces']} faces "
         f"({after['quads'] - before['quads']}q {after['tris'] - before['tris']}t)")

    if after.get("min_x", 1.0) < -MIRROR_EPS:
        bad(f"{-after['min_x']:.4f} PAST the mirror plane (min x {after['min_x']:+.4f}) — "
            f"mirror clipping leaked")

    # a marched vert is snapped to the scaffold with a 0.0025 offset; anything far off it never
    # got snapped, and that is what a tentacle is made of.
    lim = expect.get("max_off", 0.010)
    if "max_off" in after:
        if after["max_off"] > lim:
            bad(f"a new vert sits {after['max_off']:.4f} off the scaffold (limit {lim:.4f}) — "
                f"points are not being snapped; this is how the tentacle happened")
        else:
            good(f"max off-scaffold {after['max_off']:.4f} (mean {after['mean_off']:.4f}), "
                 f"limit {lim:.4f}")

    # The limit is the LARGER of three steps and 2.5x the front's own spacing. Step alone is the
    # wrong yardstick whenever step < spacing: it bounds how far a column moves per ROW, while the
    # spacing bounds how far apart columns legitimately sit. On the arm, step 0.012 against a front
    # spacing of 0.021 made "3 steps" (0.036) narrower than two normal columns, and it flagged a
    # transition quad — one column reaching the ring a row before its neighbour — as a stretch.
    # That is the metric being mis-scaled, not the geometry being wrong.
    if step:
        lim_step = step * 3.0
        lim_sp = 2.5 * front_spacing if front_spacing else 0.0
        lim_e = max(lim_step, lim_sp)
        if after.get("max_edge", 0) > lim_e:
            where = after.get("max_edge_at")
            bad(f"longest new edge {after['max_edge']:.4f} exceeds {lim_e:.4f} "
                f"(3 steps {lim_step:.4f}, 2.5x front spacing {lim_sp:.4f}) — "
                f"a column stretched instead of stepping")
            if where:
                lines.append(f"       between {where[0]} and {where[1]}")
        else:
            good(f"longest new edge {after.get('max_edge', 0):.4f}, limit {lim_e:.4f} "
                 f"(3 steps {lim_step:.4f}, 2.5x front spacing {lim_sp:.4f})")

    box = expect.get("bbox")
    if box and "bbox" in after:
        names = ("x min", "x max", "y min", "y max", "z min", "z max")
        for i, (lo, hi) in enumerate(box):
            if lo is None and hi is None:
                continue
            val = after["bbox"][i]
            if (lo is not None and val < lo) or (hi is not None and val > hi):
                bad(f"new geometry {names[i]} = {val:+.4f}, outside the declared "
                    f"[{lo}, {hi}] — this region built somewhere it was not supposed to")
        if ok:
            b = after["bbox"]
            good(f"bbox x[{b[0]:+.3f},{b[1]:+.3f}] y[{b[2]:+.3f},{b[3]:+.3f}] "
                 f"z[{b[4]:+.3f},{b[5]:+.3f}] — inside the declared box")

    n = expect.get("new_count")
    if n and not (n[0] <= after["new_count"] <= n[1]):
        bad(f"{after['new_count']} new verts, expected {n[0]}-{n[1]} — the march did not do "
            f"what the plan said it would")

    return ok, lines


def preflight(front, expect, region):
    """Checked BEFORE a single face is built: is the front the curve we planned?

    The nape ran to completion and produced 75 faces on the wrong side of the head. It was a
    valid march of an invalid front. Front selection is the step that fails silently.
    """
    exp = (expect or {}).get("front")
    lines = [f"  front: {len(front)} columns  "
             f"({front[0].co.x:+.3f},{front[0].co.y:+.3f},{front[0].co.z:.3f}) -> "
             f"({front[-1].co.x:+.3f},{front[-1].co.y:+.3f},{front[-1].co.z:.3f})"]
    # Spacing is printed WHETHER OR NOT the region declares a limit. An uneven front is not a
    # march problem and cannot be tuned away downstream — the first row inherits the worst gap and
    # every row below repeats it. This number is the one that explains those failures.
    gaps = [(front[i].co - front[i + 1].co).length for i in range(len(front) - 1)]
    if gaps:
        mean = sum(gaps) / len(gaps)
        lines.append(f"     spacing: min {min(gaps):.4f}  mean {mean:.4f}  max {max(gaps):.4f}"
                     f"  ({max(gaps) / mean:.1f}x mean)")
    if not exp:
        lines.append("     (no front expectation declared — nothing to check)")
        return True, lines
    ok = True
    mg = exp.get("max_gap")
    if mg and gaps and max(gaps) > mg:
        ok = False
        lines.append(f"  !! front spacing max {max(gaps):.4f} exceeds {mg:.4f} — resample this "
                     f"boundary first (tools/retopo_resample_edge.py), do not tune the march")
    cols = exp.get("columns")
    if cols and not (cols[0] <= len(front) <= cols[1]):
        ok = False
        lines.append(f"  !! {len(front)} columns, expected {cols[0]}-{cols[1]} — the picker "
                     f"latched onto the wrong run of boundary")
    box = exp.get("bbox")
    if box:
        xs = [v.co.x for v in front]
        ys = [v.co.y for v in front]
        zs = [v.co.z for v in front]
        got = (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))
        names = ("x min", "x max", "y min", "y max", "z min", "z max")
        for i, (lo, hi) in enumerate(box):
            if lo is None and hi is None:
                continue
            if (lo is not None and got[i] < lo) or (hi is not None and got[i] > hi):
                ok = False
                lines.append(f"  !! front {names[i]} = {got[i]:+.4f}, outside declared "
                             f"[{lo}, {hi}] — this is not the edge {region} should start from")
    if ok:
        lines.append("     front matches the plan")
    return ok, lines


def report(title, lines, ok):
    print(f"\n---- GATE: {title} " + "-" * max(0, 60 - len(title)))
    for ln in lines:
        print(ln)
    print(f"---- {'PASS' if ok else 'FAIL'} " + "-" * 62)
    return ok

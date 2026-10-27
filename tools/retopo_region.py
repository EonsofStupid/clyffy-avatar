"""CP7 — the head, REGION BY REGION. One bounded march per region, anchored on what exists.

    blender -b --python tools/retopo_region.py -- work/RETOPO_clyffy.blend forehead

Supersedes the single-sweep attempt in `tools/retopo_skull.py` (kept as the negative result).
That sweep failed structurally, not by tuning: the face patch's outer boundary is deeply
non-convex — the mouth corner juts 0.045 past the nose-side edge — so a global "march outward"
self-intersects at the notch on row 1; and the ear exclusion zone (r 0.076) blankets the side of
the head, where un-snapped points flew off into space as a tentacle. Protrusions (2 horns,
2 ears) also change the front's TOPOLOGY, which a 1-D column array cannot represent.

So: bounded regions, each a short march off an EXISTING boundary segment, each reviewed. The
mechanism is the one proven on the nose (CP5) and the eye bridge (CP6): geodesic march + row
smoothing + progressive decimation (crowded columns merge) + capture onto a target ring.

Rerunnable per region: verts tagged in the region's own vertex group.

THE FLOW (added 2026-08-07, operator's instruction — "an internal pause that does a verification
and check and then move forward"). Every region now runs the same five steps and CANNOT skip one:

    1. PLAN      the region declares `expect`: what front it should find, and what geometry it
                 should produce. A region with no `expect` is an unreviewed region.
    2. PREFLIGHT the front is checked against the plan BEFORE a single face is built. The nape
                 once marched 75 perfectly valid faces off a front on the wrong side of the head;
                 this is the step that catches that class of failure while it is still free.
    3. BUILD     the march.
    4. GATE      `retopo_gate.verdict` — non-manifold, ngons, degenerate faces, the intentional
                 apertures, mirror-plane leakage, off-scaffold flyers, the declared bounding box.
    5. LOOK      renders, ALWAYS, pass or fail — a failed region is exactly the one worth seeing.

    COMMIT       the .blend is saved ONLY if 2 and 4 both passed. On failure the file on disk is
                 untouched, so a bad region costs a rerun and nothing else. Before this, every
                 region saved unconditionally and had to be undone by hand.
"""
import bpy, bmesh, sys, os, math
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import retopo_gate as gate

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
REGION = argv[1] if len(argv) > 1 else "forehead"

# region -> (boundary predicate, rows, step, capture guide rings, vertex group)
REGIONS = {
    # the brow/forehead: off the eye ring's OPEN upper arc + the glabella midline, up to the
    # horn bases. Short and smooth — no protrusion inside it.
    "forehead": dict(
        pick=lambda v: v.co.z > 0.830 and v.co.y > -0.200,
        rows=7, step=0.020, capture=["vis_horn_base_R"], group="cp7_forehead"),
    # the CHEEK: the lateral face edge from the mouth corner, up the nose side, under the eye —
    # marching out and back to the ear base. This is the non-convex stretch that broke the global
    # sweep; as its own front the notch is just one long quad, not a self-intersection.
    # seek_dir: an EXPLICIT march direction (projected into the surface each row). The
    # "away from the patch interior" heuristic is only valid on a front-facing edge; on the
    # SIDE edge of a strip the interior is below, so "away" points up — the first cheek run
    # marched over the eyes and buried both apertures.
    "cheek": dict(
        pick=lambda v: 0.740 < v.co.z < 0.845 and v.co.x > 0.050,
        seek_dir=(0.0, 1.0, 0.0),
        rows=10, step=0.020, capture=["vis_ear_base_R"], group="cp7_cheek"),
    # the JAW: the whole lower boundary (chin midline + jawline) marching down and back to the
    # neck ring — the CP9 body boundary.
    "jaw": dict(
        pick=lambda v: v.co.z < 0.750 and v.co.y < -0.170,
        seek_dir=(0.0, 1.0, -0.30),
        rows=10, step=0.020, capture=["vis_neck"], group="cp7_jaw"),
    # the NAPE: the occiput's lower edge (z ~0.785 at the midline, wrapping to behind the ear)
    # down to the neck ring — the CP9 body boundary. seek_dir goes down and slightly BACK: the
    # neck ring's rear sits at y +0.143, further back than the occiput edge at y +0.107.
    "nape": dict(
        pick=lambda v: v.co.z < 0.800 and v.co.y > -0.060,
        seek_dir=(0.0, 0.30, -1.0),
        rows=8, step=0.020, capture=["vis_neck"], group="cp7_nape"),
    # the JAWLINE band: seen from below, a diagonal grey strip runs along the side between the
    # cheek patch's lower edge (a near-constant-z run at ~0.745) and the jaw patch's upper edge.
    # Zip it downward, welding onto the existing jaw boundary (capture_boundary).
    "jawline": dict(
        pick=lambda v: 0.735 < v.co.z < 0.755 and v.co.x > 0.080,
        seek_dir=(0.0, 0.0, -1.0),
        rows=7, step=0.016, capture=[], capture_boundary=True, group="cp7_jawline"),
    # the THROAT: from below, the jaw patch's two legs splay apart behind the chin and leave a V
    # of bare surface running to the neck. Front = the leg's inner (midline-facing) edge, marched
    # BACK and slightly down onto the neck ring.
    "throat": dict(
        pick=lambda v: v.co.z < 0.700 and v.co.y < 0.0,
        seek_dir=(0.0, 1.0, -0.30),
        rows=9, step=0.018, capture=["vis_neck"], group="cp7_throat"),
    # THE BODY STARTS HERE. The neck ring is the only body edge that already exists — the nape and
    # throat regions both captured onto it, so the head's lower boundary IS the collar.
    #
    # REBUILT 2026-08-07 against a DECLARED RING. The first attempt marched 7 rows with no capture
    # target and stopped wherever each column's 7th step landed: measured spread of the resulting
    # edge was 0.1434, EIGHT march steps of raggedness, which is not an edge the shoulders can
    # anchor to. A body is a tube and a horizontal cross-section of the scaffold IS the edge a
    # region should end on, so it now captures onto `vis_ring_collar`.
    #
    # The ring sits at z 0.660, and that height is measured, not chosen for looks
    # (tools/body_survey.py --from 0.78 --to 0.44):
    #   z 0.705  the neck's narrowest point, width 0.230
    #   z 0.672  section depth collapses 0.377 -> 0.276 — the jaw/muzzle mass ends here
    #   z 0.660  width 0.311  — below the jaw, above the deltoid flare, and the FIRST choice for
    #            the ring. Preflight rejected it: the existing neck ring is not planar and dips to
    #            z 0.6517, so those columns would have marched UP into the head.
    #   z 0.630  the ring, clearing the whole front. Every column marches down.
    #   z 0.610  width 0.413 and climbing fast — that acceleration IS the shoulder cap, i.e. the
    #            top of the arm, and a ring there would already be wrapping arm surface.
    # NO seek_dir, deliberately. An explicit direction is the right tool on the SIDE edge of a
    # strip, where "away from the patch interior" points somewhere useless — that is why the head
    # regions declare one. It is the wrong tool here. seek_dir (0,0,-1) is projected into the
    # surface each row, and the underside of the jaw is very nearly horizontal, so straight-down
    # has almost no tangential component there: those midline columns CRAWLED (0.065 of travel in
    # 16 rows) while their neighbours marched, leaving a 0.11 row gap. The neck ring is a shell's
    # closed lower boundary, which is exactly the case where "away from the interior" is
    # well-defined — it points down-and-back under the chin and down-and-out at the nape, per
    # column, with no single direction able to do both.
    "neck": dict(
        pick=lambda v: v.co.z < 0.725,
        # rows/step: the throat has the longest path — the surface undercuts hard from y -0.275 at
        # the chin to y -0.118 at the ring, ~0.175 of surface travel against 0.077 of drop, so 16
        # rows at 0.014 (0.224) covers it and capture freezes the short columns early.
        #
        # TWO EARLIER GUESSES AT THE LONG EDGE, BOTH WRONG, RECORDED SO THEY ARE NOT REPEATED:
        # 6 rows at 0.016 gave a 0.0764 edge; halving the step to 0.010 and going to 20 rows made
        # it WORSE (0.0965). The march was never the cause. The diagnostic put the worst gap at
        # ROW 0 — the existing boundary — and `tools/inspect_front.py` showed the neck ring's own
        # spacing ran 0.0018 to 0.0915, a 3.7x spread. `tools/retopo_resample_edge.py` split the
        # 12 over-long boundary edges first; the front is now 1.6x and the march is a march again.
        rows=16, step=0.014, capture_r=0.016, seek_target=True,
        capture=["vis_ring_collar"], group="cp9_neck",
        expect=dict(
            front=dict(columns=(45, 60), max_gap=0.035,
                       bbox=((None, None), (None, None), (None, None),
                             (None, None), (0.640, None), (None, 0.730))),
            bbox=((-0.001, None), (None, None), (None, None),
                  (None, None), (0.615, None), (None, 0.725)),
            new_count=(150, 700), max_off=0.010)),
    # B2 — the SHOULDER YOKE: collar ring (z 0.630) down to the chest ring (z 0.500).
    #
    # This region WRAPS THE ARMS and that is correct, not a compromise. Measured: above z 0.368
    # every horizontal cross-section of the scaffold is a SINGLE contour — torso and both arms
    # fused — so no torso-only ring exists anywhere across the shoulder. The deltoid is part of the
    # shoulder mass, exactly as it is on a real shoulder, and the shirt's yoke covers both. The
    # arms become separable at z 0.368 and that is where B4 picks them up.
    #
    # Travel: 0.130 of drop against 0.056 of outward flare (half-width 0.192 -> 0.248), so ~0.142
    # of surface path; 16 rows at 0.014 covers it with room for the curvature.
    "shoulders": dict(
        pick=lambda v: v.co.z < 0.645,
        rows=16, step=0.014, capture_r=0.020, seek_target=True,
        capture=["vis_ring_chest"], group="cp9_shoulders",
        expect=dict(
            front=dict(columns=(38, 48), max_gap=0.020,
                       bbox=((None, None), (None, None), (None, None),
                             (None, None), (0.625, None), (None, 0.650))),
            bbox=((-0.001, None), (None, None), (None, None),
                  (None, None), (0.495, None), (None, 0.645)),
            new_count=(200, 800), max_off=0.010)),
    # B4 — the TORSO: the armpit ring's TORSO arc down to the waist ring (z 0.300).
    # The front is tagged by tools/armpit_split.py, not by a coordinate predicate — see pick_group.
    # It arrives as two arcs (back and front of the torso, with the arm run between them) and is
    # joined into one front across the 0.028 armpit slot.
    "torso": dict(
        pick_group="cp9_torso_front", join_chains=True,
        rows=12, step=0.014, capture_r=0.020, seek_target=True,
        capture=["vis_ring_waist"], group="cp9_torso",
        expect=dict(
            front=dict(columns=(24, 32), max_gap=0.040,
                       bbox=((None, None), (None, None), (None, None),
                             (None, None), (0.405, None), (None, 0.415))),
            bbox=((-0.001, None), (None, None), (None, None),
                  (None, None), (0.295, None), (None, 0.415)),
            new_count=(150, 600), max_off=0.010)),
    # B6 — the ARM. Front is the 15-vert arc tagged by tools/armpit_split.py at z 0.410, marched
    # down the arm to a CLOSED wrist ring at z 0.300. The hand is a separate object (operator:
    # placeholder is fine) and the arm tapers away entirely by z 0.250, so the shell stops at 0.300.
    #
    # CYCLIC, because an arm is a tube. The arc's two ends are the two armpit points and the 0.028
    # of surface between them is the armpit bridge — real scaffold that the chest march went around
    # rather than over. Closing the front covers it and gives the arm a proper closed cross-section.
    # Nothing here touches the mirror plane, so the midline rules never fire.
    "armR": dict(
        pick_group="cp9_arm_front", cyclic=True,
        # snap_to="SCAF_armR" was TRIED AND REVERTED. Isolating the arm removes the torso from the
        # snap, but it also puts a CUT EDGE exactly where the inner columns have to travel, and
        # they snapped to that instead and stalled at z 0.378 — 13 of 15 captured, worst gap 0.0905,
        # worse than doing nothing. Isolation works for a protrusion you rebuild whole (the ear);
        # it does not work for one you march ACROSS the join.
        # An armpit exclusion zone was tried here too and REMOVED: it produced byte-identical
        # geometry (15/15 captured, 114q/4t, same worst gap) while leaving its own verts unsnapped
        # 0.0151 off the surface, which the gate then flagged. A remedy that changes nothing but
        # costs accuracy is worse than no remedy.
        # capture_r 0.030, wider than elsewhere, and for a measured reason: the two columns on the
        # arm's INNER side start at the armpit points (x 0.177) and must reach the wrist ring's
        # inner edge (x 0.209). Inside the armpit `closest_point_on_mesh` returns the TORSO, not
        # the arm, so the snap holds them back — they stalled at x 0.186, 0.023-0.026 short. That
        # is the concavity twin of "shrinkwrap is unusable on a protrusion" and it is not fixable
        # by more rows; the radius has to clear the shortfall.
        # measured, not nudged: the last inner column's assigned target sat 0.0310 away against a
        # 0.030 radius — a genuine near miss, not a wrong assignment. 0.034 clears it and still
        # sits under the 3-step (0.036) long-edge limit, so the capture cannot hide a stretch.
        rows=14, step=0.012, capture_r=0.034, seek_target=True,
        capture=["vis_ring_armR_wrist"], group="cp9_armR",
        expect=dict(
            front=dict(columns=(12, 18), max_gap=0.045,
                       bbox=((0.150, None), (None, None), (None, None),
                             (None, None), (0.405, None), (None, 0.415))),
            bbox=((0.150, None), (None, None), (None, None),
                  (None, None), (0.295, None), (None, 0.415)),
            new_count=(80, 400), max_off=0.012)),
    # B5 — the HIP: waist ring (z 0.300) down to the hip ring (z 0.200), above the leg split at
    # 0.152. The arm contours are still present in the scaffold down to z 0.267 and the TAIL shows
    # up as its own small loop from about z 0.240 — neither matters here, because the ring builder
    # takes the LARGEST loop and both are far smaller than the torso.
    "hip": dict(
        pick=lambda v: v.co.z < 0.305,
        rows=12, step=0.014, capture_r=0.018, seek_target=True,
        exclude=[((0.0, 0.176, 0.215), 0.058)],
        capture=["vis_ring_hip"], group="cp9_hip",
        expect=dict(
            front=dict(columns=(22, 34), max_gap=0.040,
                       bbox=((None, None), (None, None), (None, None),
                             (None, None), (0.295, None), (None, 0.305))),
            bbox=((-0.001, None), (None, None), (None, None),
                  (None, None), (0.195, None), (None, 0.305)),
            new_count=(120, 500), max_off=0.010)),
    # B7 — the THIGH: hip ring (z 0.200) down to the crotch ring (z 0.170). Short, and it is the
    # mirror-plane twin of B3: z 0.170 is the LAST single-contour height going down, exactly as
    # z 0.410 was the last one going down past the arms. Below it the legs come free (~0.161) and
    # the front has to be split again — this time at the MIDLINE rather than laterally.
    "thigh": dict(
        pick=lambda v: v.co.z < 0.205,
        rows=8, step=0.010, capture_r=0.015, seek_target=True,
        capture=["vis_ring_crotch"], group="cp9_thigh",
        expect=dict(
            front=dict(columns=(22, 34), max_gap=0.045,
                       bbox=((None, None), (None, None), (None, None),
                             (None, None), (0.195, None), (None, 0.205))),
            bbox=((-0.001, None), (None, None), (None, None),
                  (None, None), (0.165, None), (None, 0.205)),
            # 100-500 was my arithmetic, not a measurement, and it was wrong: 27 columns capture
            # after ~4 rows on a 0.030 drop, giving 93. Everything else about this region gated
            # clean, so the declaration is what needed correcting.
            new_count=(80, 400), max_off=0.010)),
    # B8 — the LEG, in two stages for taper control. Front is the arc tagged by
    # tools/limb_split.py, CYCLIC for the same reason the arm is: a leg is a tube, and closing the
    # front covers the crotch bridge that the thigh march went around rather than over.
    #
    # The crotch is a smooth SADDLE where the armpit was a narrow slot — that difference is why the
    # split needed a different discriminator (see limb_split.py) and it is why this front's closing
    # segment is wider than the arm's was.
    "legR_upper": dict(
        pick_group="cp9_legR_front", cyclic=True,
        rows=9, step=0.010, capture_r=0.022, seek_target=True,
        capture=["vis_ring_legR_knee"], group="cp9_legR_upper",
        expect=dict(
            # x min 0.020 was my estimate and it was wrong: the SHARED crotch junction verts sit
            # at x 0.0128, further toward the midline than I guessed. Measured, not relaxed.
            front=dict(columns=(18, 28), max_gap=0.050,
                       bbox=((0.010, None), (None, None), (None, None),
                             (None, None), (0.165, None), (None, 0.175))),
            bbox=((0.010, None), (None, None), (None, None),
                  (None, None), (0.105, None), (None, 0.175)),
            new_count=(80, 400), max_off=0.012)),
    "legR_lower": dict(
        pick=lambda v: v.co.z < 0.115 and v.co.x > 0.02, cyclic=True,
        rows=8, step=0.009, capture_r=0.020, seek_target=True,
        capture=["vis_ring_legR_ankle"], group="cp9_legR_lower",
        expect=dict(
            front=dict(columns=(12, 22), max_gap=0.040,
                       bbox=((0.040, None), (None, None), (None, None),
                             (None, None), (0.105, None), (None, 0.115))),
            bbox=((0.040, None), (None, None), (None, None),
                  (None, None), (0.055, None), (None, 0.115)),
            new_count=(60, 300), max_off=0.012)),
    # B9 — the CROTCH FILL. The one real hole left in the shell. The leg march closed its cycle
    # only where the cycle had closed, which is correct, and left this arc open above the saddle:
    # 16 verts running mirror-plane to mirror-plane, out to x 0.046 and dipping to z 0.143.
    # It is closed by marching INWARD to the midline, where the Mirror modifier seals it.
    # No capture ring — the midline IS the target, so freeze_at_mirror is what stops the columns.
    "crotch_fill": dict(
        pick=lambda v: 0.140 < v.co.z < 0.180 and v.co.x < 0.060,
        seek_dir=(-1.0, 0.0, 0.0), freeze_at_mirror=True,
        rows=8, step=0.010, capture=[], group="cp9_crotch_fill",
        expect=dict(
            front=dict(columns=(12, 22), max_gap=0.045,
                       bbox=((None, None), (None, 0.060), (None, None),
                             (None, None), (0.140, None), (None, 0.180))),
            bbox=((-0.001, None), (None, 0.060), (None, None),
                  (None, None), (0.135, None), (None, 0.185)),
            new_count=(20, 200), max_off=0.012)),
    # B10 — the HOOF: ankle ring (z 0.060) down to a ring at z 0.012, just above the ground.
    # Cyclic like the rest of the leg. The sole is capped separately — a flat disc is a fill, not a
    # march, and marching onto a flat plane would just crowd columns at a point.
    "hoofR": dict(
        pick=lambda v: v.co.z < 0.065 and v.co.x > 0.02, cyclic=True,
        rows=9, step=0.008, capture_r=0.024, seek_target=True,
        capture=["vis_ring_legR_hoof"], group="cp9_hoofR",
        expect=dict(
            front=dict(columns=(12, 22), max_gap=0.040,
                       bbox=((0.040, None), (None, None), (None, None),
                             (None, None), (0.055, None), (None, 0.065))),
            bbox=((0.040, None), (None, None), (None, None),
                  (None, None), (0.008, None), (None, 0.065)),
            new_count=(40, 300), max_off=0.012)),
    # B3 — the CHEST: chest ring (z 0.500) down to the armpit ring (z 0.410). Still one contour,
    # so still one tube; z 0.410 is the LAST height where that is true. At z 0.400 the section
    # becomes three loops (torso 535, arms 145/142, measured exactly) and no marching front can
    # represent a split, so this region is where the one-tube part of the body ends and the armpit
    # seam begins.
    #
    # Target-seeking, and the history is worth keeping because it looks like a flip-flop and is not.
    # Against the BROKEN armpit ring (the angular-sort one at z 0.385, whose arc was wildly
    # mis-proportioned against the chest ring) proportional targeting sent columns crabbing
    # sideways and 27 of 40 ran past to z 0.3731. Marching straight down instead let the surface's
    # own flow line do the work and got 33 of 40 — but nearest-point capture funnels, so several
    # columns landed on the same ring point and left others unclaimed, leaving a 0.0479 hole in the
    # ring between two verts 2-3 points apart. Once the ring was measured correctly the premise
    # changed: at z 0.410 the contour is close in shape to z 0.500, so the proportional map is
    # sound, and it is the only rule that GUARANTEES every ring point is claimed by exactly one
    # column. The lesson is that the ring was wrong, not that the direction rule was.
    "chest": dict(
        pick=lambda v: v.co.z < 0.512,
        rows=12, step=0.014, capture_r=0.024, seek_target=True,
        capture=["vis_ring_armpit"], group="cp9_chest",
        expect=dict(
            front=dict(columns=(38, 48), max_gap=0.025,
                       bbox=((None, None), (None, None), (None, None),
                             (None, None), (0.495, None), (None, 0.512))),
            bbox=((-0.001, None), (None, None), (None, None),
                  (None, None), (0.405, None), (None, 0.512)),
            new_count=(200, 800), max_off=0.010)),
    # the TEMPLE wedge: the forehead's lower-lateral edge and the cheek's upper edge meet at the
    # temple point and splay apart toward the ear, leaving a lens-shaped gap spanned by the ear
    # base ring. Zip it: march the forehead edge FORWARD onto the cheek edge, welding to the
    # existing boundary verts it lands on.
    "temple": dict(
        pick=lambda v: 0.855 < v.co.z < 0.870 and v.co.x > 0.085 and v.co.y > -0.105,
        seek_dir=(0.0, -1.0, 0.0),
        rows=4, step=0.016, capture=[], capture_boundary=True, group="cp7_temple"),
}
CFG = REGIONS[REGION]

bpy.ops.wm.open_mainfile(filepath=BLEND)
scaf = bpy.data.objects["SCAFFOLD"]
rt = bpy.data.objects["retopo_head"]
bpy.context.view_layer.objects.active = rt
if rt.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")

STEP = CFG["step"]
MIN_SP = 0.6 * STEP
# Capture radius defaults to one step, which is right when the target ring's point spacing is
# finer than the step. A DECLARED ring (tools/body_rings.py) has its own spacing, and if that
# spacing exceeds the step, columns pass straight through the ring without ever being within
# CAPTURE_R of a point on it. Overridable per region for exactly that case.
CAPTURE_R = CFG.get("capture_r", STEP)


# exclusion zones: inside one, a point is NOT snapped to the scaffold. The mechanism CP5 needed for
# the nostril, which is a ridged SLOT rather than a dip — snapping there scattered rows onto pit and
# ridge alike. The body needs it for the TAIL: from z 0.245 down the tail is its own contour at the
# back midline (x +-0.03, y +0.15..+0.20) while the torso's back recedes to y 0.101, so
# closest_point_on_mesh at the back midline returns the TAIL and the shell climbs onto it instead of
# following the buttock. The tail is a separate object by the operator's ruling, so the shell must
# pass smoothly beneath it.
EXCL = [(Vector(c), r) for c, r in CFG.get("exclude", [])]

# snap_to: snap to an ISOLATED surface instead of the whole scaffold. Mandatory on a protrusion.
# "Shrinkwrap is unusable on a protrusion — nearest-surface from an ear vert finds the SKULL" (CP8);
# the arm is a protrusion two centimetres off the torso, so in the armpit the nearest surface to an
# arm vertex is the BODY. That held the inner arm column at x 0.187 while the arm's own inner
# surface is at 0.208, and left a 0.047 quad. Snapping to `SCAF_armR` makes it impossible instead
# of unlikely. Built by tools/isolate_limb.py.
SNAP_OBJ = bpy.data.objects[CFG["snap_to"]] if CFG.get("snap_to") else scaf
if CFG.get("snap_to"):
    print(f"snapping to '{CFG['snap_to']}' ({len(SNAP_OBJ.data.polygons)} faces), not SCAFFOLD")


def snap(p, offset=0.0025):
    p = Vector(p)
    for c, r in EXCL:
        if (p - c).length < r:
            return p
    ok, loc, nor, _ = SNAP_OBJ.closest_point_on_mesh(p)
    return (loc + nor * offset) if ok else p


def snorm(p):
    ok, loc, nor, _ = SNAP_OBJ.closest_point_on_mesh(Vector(p))
    return nor if ok else Vector((0, 0, 1))


def guide_pts(name):
    o = bpy.data.objects[name]
    return [o.matrix_world @ p.co.to_3d() for s in o.data.splines for p in s.points]


targets = []
for g in CFG["capture"]:
    targets += guide_pts(g)
print(f"region {REGION}: {len(targets)} capture points from {CFG['capture']}")
# capture_boundary: also weld onto EXISTING open-boundary verts the march lands on. This is how
# a gap between two finished patches gets closed instead of overlapped — the marched column
# becomes that vert rather than a new one beside it.
CAPTURE_BND = CFG.get("capture_boundary", False)

# ---- rerun cleanup, and revert the failed global sweep if it is still in the file ---------------
DEAD = ("cp7_skull",)                       # retopo_skull.py's output — structurally wrong
vg = rt.vertex_groups.get(CFG["group"]) or rt.vertex_groups.new(name=CFG["group"])
gi = vg.index
kill_idx = {gi} | {rt.vertex_groups[d].index for d in DEAD if rt.vertex_groups.get(d)}

bm = bmesh.new(); bm.from_mesh(rt.data)
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
dl = bm.verts.layers.deform.verify()
stale = [v for v in bm.verts if kill_idx & set(v[dl].keys())]
if stale:
    bmesh.ops.delete(bm, geom=stale, context="VERTS")
    print(f"cleared {len(stale)} verts (previous {REGION} pass and/or the failed global sweep)")
    bm.edges.ensure_lookup_table()
    bm.to_mesh(rt.data)
for d in DEAD:
    g = rt.vertex_groups.get(d)
    if g:
        rt.vertex_groups.remove(g)
vg = rt.vertex_groups.get(CFG["group"]) or rt.vertex_groups.new(name=CFG["group"])
gi = vg.index
bm.free()
bm = bmesh.new(); bm.from_mesh(rt.data)
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
dl = bm.verts.layers.deform.verify()

# STEP 1 of the flow — the state we are building FROM, captured after the rerun cleanup so a rerun
# compares against the same baseline a first run would.
BEFORE = gate.survey(rt, scaf)
print(f"before: {BEFORE['faces']} faces ({BEFORE['quads']}q {BEFORE['tris']}t), "
      f"boundary loops {BEFORE['loops']}, non-manifold {BEFORE['nonman']}, "
      f"apertures {BEFORE['apertures']}")

# ---- the front: a contiguous run of the patch's open boundary ----------------------------------
bnd_edges = [e for e in bm.edges if e.link_faces and len(e.link_faces) == 1]
adjb = {}
for e in bnd_edges:
    a, b = e.verts
    adjb.setdefault(a, []).append(b)
    adjb.setdefault(b, []).append(a)
chin = min(adjb, key=lambda v: v.co.z)
loop_set, stack, seen = set(), [chin], {chin}
while stack:
    v = stack.pop(); loop_set.add(v)
    for o in adjb[v]:
        if o not in seen:
            seen.add(o); stack.append(o)
ordered = [chin]
prev = None
while True:
    nxts = [o for o in adjb[ordered[-1]] if o is not prev and o in loop_set and o not in ordered]
    if not nxts:
        break
    prev = ordered[-1]
    ordered.append(nxts[0])
# Front selection runs on the boundary SUBGRAPH of picked verts, not on a walk of the whole loop.
# The outer boundary is no longer a simple cycle — patches meeting at a point leave T-junctions
# (verts with 3+ boundary edges), so the walk dead-ends: it returned 61 verts of a 102-vert
# component and the nape front came out as 3 columns from the wrong side of the head.
# pick_group: start from an arc TAGGED by a measurement rather than described by a coordinate
# predicate. The armpit seam cannot be written as a z/x/y rule — which vertices belong to the torso
# and which to the arm is decided by dropping each one to z 0.400 and asking which scaffold contour
# it is nearer (tools/armpit_split.py). A predicate would be me guessing at the answer that tool
# measured.
if CFG.get("pick_group"):
    pg = rt.vertex_groups.get(CFG["pick_group"])
    if pg is None:
        print(f"!! vertex group '{CFG['pick_group']}' does not exist — run tools/armpit_split.py")
        sys.exit(1)
    picked = [v for v in adjb if pg.index in v[dl]]
else:
    picked = [v for v in adjb if CFG["pick"](v)]
psel = set(picked)
padj = {v: [o for o in adjb[v] if o in psel] for v in picked}
chains, seenp = [], set()
for v in picked:
    if v in seenp:
        continue
    comp, stack = [], [v]
    seenp.add(v)
    while stack:
        k = stack.pop(); comp.append(k)
        for o in padj[k]:
            if o not in seenp:
                seenp.add(o); stack.append(o)
    # order the component as a chain, starting from an endpoint if it has one
    ends = [k for k in comp if len(padj[k]) == 1]
    s0 = ends[0] if ends else comp[0]
    chain, prevv = [s0], None
    while True:
        nx = [o for o in padj[chain[-1]] if o is not prevv and o not in chain]
        if not nx:
            break
        prevv = chain[-1]
        chain.append(nx[0])
    chains.append(chain)

# join_chains: the torso's front is TWO arcs — the arm run sits between them, so the picked set
# has a back arc and a front arc with the armpit slot in between. Taking the longest chain would
# march only one of them and leave half the torso unbuilt. The two armpit points are 0.028 apart,
# which is inside the front's own vertex spacing, so linking the arcs end-to-end costs nothing:
# the join is just another column gap. The join distance is printed so an accidental long join
# cannot pass unnoticed.
if CFG.get("join_chains") and len(chains) > 1:
    order = [chains.pop(0)]
    joins = []
    while chains:
        tail = order[-1][-1].co
        k = min(range(len(chains)),
                key=lambda j: min((tail - chains[j][0].co).length,
                                  (tail - chains[j][-1].co).length))
        c = chains.pop(k)
        if (tail - c[-1].co).length < (tail - c[0].co).length:
            c.reverse()
        joins.append((tail - c[0].co).length)
        order.append(c)
    front = [v for c in order for v in c]
    print(f"  joined {len(order)} chains into one front; join gaps "
          f"{[round(j, 4) for j in joins]}")
else:
    front = max(chains, key=len)
print(f"picked {len(picked)} boundary verts; chains {[len(c) for c in chains]} -> "
      f"front {len(front)} columns: "
      f"({front[0].co.x:+.3f},{front[0].co.y:+.3f},{front[0].co.z:.3f}) -> "
      f"({front[-1].co.x:+.3f},{front[-1].co.y:+.3f},{front[-1].co.z:.3f})")

# STEP 2 of the flow — PREFLIGHT. Nothing has been built yet; if the front is wrong, stop here.
FRONT_SP = (sum((front[i].co - front[i + 1].co).length for i in range(len(front) - 1))
            / max(len(front) - 1, 1)) if len(front) > 1 else None
pf_ok, pf_lines = gate.preflight(front, CFG.get("expect"), REGION)
gate.report(f"{REGION} — preflight", pf_lines, pf_ok)
if not pf_ok:
    print("\nABORTED before a single face was built. The .blend on disk is UNCHANGED.")
    sys.exit(1)

NC = len(front)
front_set = set(front)
# weld targets: open-boundary verts that are NOT the front and not touching it (a column must not
# capture onto its own immediate neighbourhood on row 1)
vtargets = []
if CAPTURE_BND:
    near_front = set(front)
    for v in front:
        near_front.update(e.other_vert(v) for e in v.link_edges)
    vtargets = [v for v in adjb if v not in near_front]
    print(f"  weld targets: {len(vtargets)} existing boundary verts")
SEEK = Vector(CFG["seek_dir"]) if CFG.get("seek_dir") else None

# TARGET-SEEKING. Each column aims at its OWN point on the capture ring. Neither available rule can
# steer this front: it runs from the throat, which must march back and down, round to the nape,
# which must march forward and down, and BOTH failed here in recorded ways —
#   seek_dir (0,0,-1): straight down has nearly no tangential component on the horizontal underside
#                      of the jaw, so those columns crawled 0.065 in 16 rows and left a 0.11 gap.
#   away-from-interior: drifted, and columns climbed the BACK OF THE HEAD to z 0.847 (caught by the
#                      declared bbox, which is the check that exists for precisely this).
# A column that knows where it is going needs neither. This is the mechanism that fixed the CP6 eye
# bridge, and the PROPORTIONAL assignment is that fix's other half: mapping each column to its
# NEAREST target instead funnelled five columns into one vert and skipped the canthus entirely.
TSEEK = bool(CFG.get("seek_target")) and bool(targets)
ring = list(targets)
col_tgt = None
# CYCLIC: the front is a closed curve, not an open chain. An arm is a tube and a tube's
# cross-section is a cycle — its two "ends" are the two armpit points, and the surface between them
# (the 0.028 armpit bridge) is real scaffold that the chest march simply went around. Closing the
# front covers it. Nothing on the mirror plane is ever cyclic, so the two cases do not overlap.
CYCLIC = bool(CFG.get("cyclic"))
if TSEEK and CYCLIC:
    M = len(ring)
    # align the ring to the front by position AND direction — a cycle has no endpoints to match up,
    # so orientation has to be decided from the first step, not from which end is nearer.
    j0 = min(range(M), key=lambda j: (front[0].co - ring[j]).length)
    fwd = (front[1].co - ring[(j0 + 1) % M]).length
    bwd = (front[1].co - ring[(j0 - 1) % M]).length
    sgn = 1 if fwd <= bwd else -1
    col_tgt_i = [(j0 + sgn * round(i * M / NC)) % M for i in range(NC)]
    col_tgt = [ring[j] for j in col_tgt_i]
    print(f"  target-seeking (CYCLIC): {NC} columns -> {M} ring points, "
          f"start ring[{j0}], direction {'+' if sgn > 0 else '-'}")
elif TSEEK:
    # the ring is stored in arc order; make its direction agree with the front's
    if (front[0].co - ring[0]).length > (front[0].co - ring[-1]).length:
        ring.reverse()
    M = len(ring)
    # MIRROR-PLANE COLUMNS ARE NOT PART OF THE PROPORTION. A front that starts on the mirror plane
    # carries a run of verts pinned to x=0 — here nine of them, the profile line back under the
    # chin. A flat proportional map hands those columns ring points that fan outward in x, which
    # they are forbidden to follow, so they pile up on the midline and leave a 0.058 hole between
    # the last of them and the first free column. They all belong to the ring's own midline
    # endpoint, and collapsing 9 columns into 1 is a convergence the merge step already handles.
    mid_flag = [abs(v.co.x) < 0.003 for v in front]
    col_tgt = [None] * NC
    for i in range(NC):
        if mid_flag[i]:
            col_tgt[i] = ring[0] if (front[i].co - ring[0]).length <= \
                (front[i].co - ring[-1]).length else ring[-1]
    free = [i for i in range(NC) if not mid_flag[i]]
    lo, hi = (1, M - 2) if M > 3 else (0, M - 1)
    col_tgt_i = [None] * NC
    for i in range(NC):
        if mid_flag[i]:
            col_tgt_i[i] = 0 if col_tgt[i] is ring[0] else M - 1
    for k, i in enumerate(free):
        j = lo if len(free) == 1 else lo + round(k * (hi - lo) / (len(free) - 1))
        j = max(0, min(M - 1, j))
        col_tgt[i] = ring[j]
        col_tgt_i[i] = j
    print(f"  target-seeking: {NC} columns -> {M} ring points "
          f"({sum(mid_flag)} on the mirror plane collapse to the ring's endpoints, "
          f"{len(free)} mapped proportionally)")

dirs = []
for i, v in enumerate(front):
    if TSEEK:
        away = col_tgt[i] - v.co
    elif SEEK is not None:
        away = SEEK.copy()
    else:
        inner = [e.other_vert(v) for e in v.link_edges if e.other_vert(v) not in front_set]
        away = (v.co - sum((o.co for o in inner), Vector()) / len(inner)) if inner \
            else Vector((0, 1, 0))
    nrm = snorm(v.co)
    away = away - nrm * away.dot(nrm)
    dirs.append(away.normalized() if away.length > 1e-6 else Vector((0, 0, 1)))
for _ in range(3):
    dirs = [dirs[0]] + [(dirs[i - 1] + dirs[i] + dirs[i + 1]).normalized()
                        for i in range(1, NC - 1)] + [dirs[-1]]

# ---- march ---------------------------------------------------------------------------------------
# A column that ALREADY sits on the mirror plane has nowhere to march in a freeze_at_mirror
# region: seek_dir (-1,0,0) projected into a surface whose normal has no x component leaves almost
# no tangential motion, so it emits a near-duplicate vert every row and those made 2 zero-area
# faces. It has already arrived, so it starts frozen.
cols = [{"idx": [i], "v": front[i], "dir": dirs[i],
         "frozen": bool(CFG.get("freeze_at_mirror") and abs(front[i].co.x) < 0.003),
         "tgt": (col_tgt[i] if TSEEK else None),
         "tgt_i": (col_tgt_i[i] if TSEEK else None),
         "mid": abs(front[i].co.x) < 0.003} for i in range(NC)]
for c in cols:
    if c["mid"]:
        c["dir"] = Vector((0.0, c["dir"].y, c["dir"].z)).normalized()
rows = [list(front)]
new_verts = []
pinned = set()          # verts that captured onto the target ring — the relax must not move them
ring_vert = {}          # ring point index -> the single vert that owns it
stats = {"capture": 0, "merge": 0, "mirror": 0}
for k in range(CFG["rows"]):
    live = [c for c in cols if not c["frozen"]]
    if not live:
        break
    for c in live:
        c["p"] = snap(c["v"].co + c["dir"] * STEP)
    # GENTLE smoothing, interior columns only. A full umbrella pass (mean of self+neighbours)
    # shrinks an open curve toward its chord every row; at 2 passes x 7 rows it strangled the
    # forehead front from 11 columns down to 1. Weighted blend, one pass, ends held.
    # On a CYCLIC front every column is interior and the neighbours wrap — there are no ends to
    # hold, and holding the arbitrary array ends would put a seam down the arm.
    newp = {}
    span = range(len(cols)) if CYCLIC else range(1, len(cols) - 1)
    for k2 in span:
        c = cols[k2]
        if c["frozen"]:
            continue
        nb = []
        for j in ((k2 - 1) % len(cols), (k2 + 1) % len(cols)):
            nb.append(cols[j]["p"] if not cols[j]["frozen"] else cols[j]["v"].co)
        newp[k2] = c["p"].lerp(sum(nb, Vector()) / len(nb), 0.3)
    for k2, p in newp.items():
        cols[k2]["p"] = snap(p)
    for c in cols:
        if not c["frozen"] and c["mid"]:
            c["p"] = Vector((0.0, c["p"].y, c["p"].z))
    # Progressive decimation is for a FREE march, where nothing else stops columns crowding. Under
    # target-seeking the ring already sets the final density, and merging actively fights it: a
    # merge keeps one column's target and DISCARDS the other's, so that ring point is never
    # claimed by anyone. Nine merges left six ring points unclaimed and a 0.0516 hole in the collar
    # between two verts that were four ring points apart.
    j = 0
    while j < len(cols) - 1 and not TSEEK:
        a, b = cols[j], cols[j + 1]
        if not a["frozen"] and not b["frozen"] and (a["p"] - b["p"]).length < MIN_SP:
            a["p"] = snap((a["p"] + b["p"]) / 2)
            if a["mid"] or b["mid"]:
                a["mid"] = True
                a["p"] = Vector((0.0, a["p"].y, a["p"].z))
            a["idx"] = a["idx"] + b["idx"]
            a["dir"] = (a["dir"] + b["dir"]).normalized()
            cols.pop(j + 1)
            stats["merge"] += 1
        else:
            j += 1
    for c in cols:
        if c["frozen"]:
            continue
        p = c["p"]
        if not c["mid"] and p.x <= 0.0:
            p = Vector((0.0, p.y, p.z))
            c["mid"] = True
            stats["mirror"] += 1
            # freeze_at_mirror: for a region whose whole job is to CLOSE ON the midline (the crotch
            # fill), reaching x=0 is arrival, not a waypoint. Without this the column keeps being
            # pushed into -x and clipped back to 0 every row, stacking verts at one point and
            # making zero-area faces. Face-marching regions like the nose legitimately travel ALONG
            # the midline, so this is opt-in.
            if CFG.get("freeze_at_mirror"):
                c["frozen"] = True
                v = bm.verts.new(p)
                pinned.add(v)
                new_verts.append(v)
                c["v"] = v
                continue
        # weld onto an existing boundary vert if we've reached one — closes the gap outright
        wv = min(vtargets, key=lambda t: (p - t.co).length) if vtargets else None
        if wv is not None and (p - wv.co).length < CAPTURE_R:
            c["v"] = wv
            c["frozen"] = True
            stats["weld"] = stats.get("weld", 0) + 1
            continue
        # a target-seeking column captures on ITS OWN target, not on whichever ring point happens
        # to be nearest — the nearest one is how columns pile onto a single vert
        if TSEEK and c["tgt"] is not None:
            ti, hit = c["tgt_i"], c["tgt"]
        elif targets:
            ti = min(range(len(targets)), key=lambda k: (p - targets[k]).length)
            hit = targets[ti]
        else:
            ti, hit = None, None
        captured = hit is not None and (p - hit).length < CAPTURE_R
        if captured:
            # More columns than ring points is normal — 44 onto 40 here. Two columns landing on
            # the SAME ring point must become the SAME vertex; creating one vert each puts two
            # verts at identical coordinates and every face between them has zero area. The relax
            # used to jitter them apart and hide it, which is why pinning the captures is what
            # exposed it.
            if ti in ring_vert:
                c["v"] = ring_vert[ti]
                c["frozen"] = True
                stats["ringweld"] = stats.get("ringweld", 0) + 1
                continue
            p = hit
            c["frozen"] = True
            stats["capture"] += 1
        v = bm.verts.new(p)
        if captured:
            pinned.add(v)
            ring_vert[ti] = v
        new_verts.append(v)
        if TSEEK and c["tgt"] is not None:
            d = c["tgt"] - p
        elif SEEK is not None:
            d = SEEK.copy()
        else:
            d = p - c["v"].co
        c["v"] = v
        nrm = snorm(p)
        d = d - nrm * d.dot(nrm)
        if d.length > 1e-6:
            c["dir"] = d.normalized()
    row = [None] * NC
    for c in cols:
        for i in c["idx"]:
            row[i] = c["v"]
    rows.append(row)
print(f"march: {len(rows) - 1} rows, {len(cols)} final columns "
      f"(merge {stats['merge']}, capture {stats['capture']}, mirror {stats['mirror']})")

# ---- march diagnostics ---------------------------------------------------------------------------
# A long edge has exactly two causes and they need opposite fixes, so the gate must not be left to
# say only "something stretched":
#   COLUMN edge long  -> one column TELEPORTED between rows. A step is bounded by STEP, so the only
#                        way to exceed it is snap() landing on a different piece of surface. That is
#                        the concavity twin of the rule that shrinkwrap is unusable on a protrusion:
#                        nearest-surface from inside a pocket finds the far wall.
#   ROW edge long     -> neighbouring columns FANNED apart. That is a density/direction problem and
#                        more rows or smoothing is the lever.
col_worst, row_worst = (0.0, None), (0.0, None)
for ra, rb in zip(rows, rows[1:]):
    for i in range(NC):
        if ra[i] is None or rb[i] is None or ra[i] is rb[i]:
            continue
        d = (ra[i].co - rb[i].co).length
        if d > col_worst[0]:
            col_worst = (d, (i, tuple(round(c, 4) for c in ra[i].co),
                             tuple(round(c, 4) for c in rb[i].co)))
for r, row in enumerate(rows):
    seq = [v for v in row if v is not None]
    for u, w in zip(seq, seq[1:]):
        if u is w:
            continue
        d = (u.co - w.co).length
        if d > row_worst[0]:
            row_worst = (d, (r, tuple(round(c, 4) for c in u.co),
                             tuple(round(c, 4) for c in w.co)))
if targets:
    miss = [c for c in cols if not c["frozen"]]
    if miss:
        print(f"  {len(miss)} columns NEVER CAPTURED (capture_r {CAPTURE_R:.4f}):")
        for c in miss[:8]:
            p = c["v"].co
            d = min((p - t).length for t in targets)
            near = min(targets, key=lambda t: (p - t).length)
            own = ""
            if TSEEK and c["tgt"] is not None:
                # under target-seeking a column captures on ITS OWN target, so the distance that
                # matters is to that, not to the nearest point — reporting only the nearest one
                # makes an unreachable assignment look like a near miss
                own = (f"  assigned ring[{c['tgt_i']}] "
                       f"{tuple(round(q, 4) for q in c['tgt'])} dist {(p - c['tgt']).length:.4f}")
            print(f"     ended {tuple(round(q, 4) for q in p)}  nearest ring point "
                  f"{tuple(round(q, 4) for q in near)}  dist {d:.4f}{own}")
print(f"  worst COLUMN step {col_worst[0]:.4f} (step is {STEP:.4f})"
      + (f"  col {col_worst[1][0]}: {col_worst[1][1]} -> {col_worst[1][2]}" if col_worst[1] else ""))
print(f"  worst ROW gap     {row_worst[0]:.4f}"
      + (f"  row {row_worst[1][0]}: {row_worst[1][1]} -> {row_worst[1][2]}" if row_worst[1] else ""))
if col_worst[0] > STEP * 2.5:
    print(f"  -> a column TELEPORTED: snap() found a different piece of surface. Concavity.")
elif row_worst[0] > STEP * 3.0:
    print(f"  -> columns FANNED apart: direction/density, not a snap failure.")

made_q = made_t = 0
for a, b in zip(rows, rows[1:]):
    # a cyclic front also builds the face between the LAST column and the FIRST. On the arm that
    # face IS the armpit bridge — 0.028 of real surface the chest march went around. On the LEG the
    # same closure spans the CROTCH, which is 0.137 wide, and building it tents a face straight
    # across the gap between the thighs. So the cycle is closed only WHERE IT HAS ACTUALLY CLOSED:
    # the wrap face is built once the two ends are within a normal column spacing of each other,
    # which happens naturally as the legs come free below the saddle. Above that the front stays
    # open and the crotch remains a boundary to be filled as its own region.
    for i in range(NC if CYCLIC else NC - 1):
        i2 = (i + 1) % NC
        if CYCLIC and i == NC - 1:
            wrap_lim = 2.5 * (FRONT_SP or STEP)
            if (a[i].co - a[i2].co).length > wrap_lim and \
               (b[i].co - b[i2].co).length > wrap_lim:
                continue
        uniq = []
        for v in (a[i], a[i2], b[i2], b[i]):
            if v not in uniq:
                uniq.append(v)
        if len(uniq) < 3:
            continue
        try:
            bm.faces.new(uniq)
            made_q += len(uniq) == 4
            made_t += len(uniq) == 3
        except ValueError:
            pass
print(f"{REGION}: {made_q} quads, {made_t} tris")

# The relax must not move a vert that CAPTURED. A capture is the region's contract with the next
# region — it is the anchor the next front marches from — and smoothing it afterwards breaks that
# contract quietly: the collar came out at z 0.635-0.643 instead of the ring's 0.630, so the
# "planar" edge was half a step out of plane. Same principle as the rule earned when ring smoothing
# corrupted the approved mouth-patch anchors: anything that smooths near a boundary pins it.
mid_v = {v for v in new_verts if abs(v.co.x) < 1e-6}
relax = [v for v in new_verts if v not in pinned]
for _ in range(3):
    moves = {}
    for v in relax:
        nbrs = [e.other_vert(v) for e in v.link_edges]
        if len(nbrs) >= 2:
            moves[v] = sum((o.co for o in nbrs), Vector()) / len(nbrs)
    for v, m in moves.items():
        v.co = v.co.lerp(m, 0.5)
    for v in relax:
        v.co = snap(v.co)
        if v in mid_v:
            v.co.x = 0.0
print(f"  relax: {len(relax)} verts smoothed, {len(pinned)} captured verts pinned")
for v in new_verts:
    v[dl][gi] = 1.0

bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(rt.data)
bm.free()
nq = sum(1 for p in rt.data.polygons if len(p.vertices) == 4)
nt = sum(1 for p in rt.data.polygons if len(p.vertices) == 3)
print(f"after {REGION}: {len(rt.data.polygons)} faces ({nq} quads, {nt} tris)")

# STEP 4 of the flow — THE GATE. Nothing is on disk yet; this decides whether it goes there.
AFTER = gate.survey(rt, scaf, group=CFG["group"])
GATE_OK, gl = gate.verdict(BEFORE, AFTER, CFG.get("expect"), STEP, front_spacing=FRONT_SP)
gate.report(REGION, gl, GATE_OK)

# ---- STEP 5 — LOOK. Rendered pass OR fail: a failed region is the one most worth seeing. --------
# (the BACK is mandatory on anything touching the skull)
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"; sh.color_type = "OBJECT"
sh.show_cavity = True; sh.cavity_type = "BOTH"
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = sc.render.resolution_y = 900
scaf.color = (0.60, 0.60, 0.62, 1.0)
rt.color = (0.95, 0.35, 0.10, 1.0)
rt.show_wire = True
rt.show_all_edges = True
for o in bpy.data.objects:
    if o.name.startswith("vis_") or o.type == "EMPTY":
        o.hide_render = True
w = bpy.data.worlds.new("WR"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.40, 0.44, 0.41, 1)
sc.world = w
# Framing is DERIVED from what this pass built, not hardcoded. A head-centred camera renders empty
# space for a body region, and an empty render is indistinguishable from a region that built
# nothing — the exact false read these renders exist to prevent (BUILD_LOG 2026-08-05, cut_view).
bb = AFTER.get("bbox")
if bb:
    ctr = Vector((0.0, (bb[2] + bb[3]) / 2, (bb[4] + bb[5]) / 2))
    span = max(2 * max(abs(bb[0]), abs(bb[1])), bb[3] - bb[2], bb[5] - bb[4])
    OSCALE = max(0.30, span * 2.2)
else:
    ctr, OSCALE = Vector((0.0, -0.08, 0.86)), 0.50
cd = bpy.data.cameras.new("CR"); cam = bpy.data.objects.new("CR", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"; cd.ortho_scale = OSCALE
cd.clip_start = 0.001; cd.clip_end = 100.0
OUT = os.path.join(os.path.dirname(BLEND),
                   f"retopo_{REGION}" + ("" if GATE_OK else "_FAIL"))
os.makedirs(OUT, exist_ok=True)
for deg in (0, 45, 90, 180):
    a = math.radians(deg)
    cam.location = (ctr.x + math.sin(a) * 2, ctr.y - math.cos(a) * 2, ctr.z + 0.01)
    cam.rotation_euler = (math.radians(89), 0, a)
    sc.render.filepath = os.path.join(OUT, f"{REGION}_{deg:03d}.png")
    bpy.ops.render.render(write_still=True)
cam.location = (ctr.x, ctr.y - 1.4, ctr.z + 1.4)
cam.rotation_euler = (math.radians(45), 0, 0)
sc.render.filepath = os.path.join(OUT, f"{REGION}_topfront.png")
bpy.ops.render.render(write_still=True)
print(f"renders -> {OUT}")

# ---- COMMIT — and only now ------------------------------------------------------------------------
if GATE_OK:
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print(f"\n{REGION}: GATE PASSED — saved to {BLEND}")
else:
    print(f"\n{REGION}: GATE FAILED — NOT SAVED. The .blend on disk is unchanged; the renders in "
          f"{OUT} show what was rejected.")
    sys.exit(1)

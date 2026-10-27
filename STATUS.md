# Clyffy avatar — STATUS

> ## ▶ RESUME HERE
>
> **▶ WORK IN THE LIVE BLENDER SESSION. Not one-shot scripts.** (2026-08-08, operator's design.)
>
>     tools/bl-up                      start it (idempotent); --restart after editing blkit.py
>     tools/bl 'result=stat()'         ask a question, ~40 ms
>     tools/bl 'result=shot("x", at=(0,-0.24,0.72), dist=0.25, wire=True)'   viewport grab, ~50 ms
>
> Blender runs WITH ITS UI on DISPLAY :0 — the operator watches the same session and can take the
> mouse at any time. `tools/blkit.py` is preloaded into every command:
>
>     ask     stat  loops  loop_degrees  narrow_faces  off_surface  gate
>     show    sel  unsel  look  shot  frame  clutter  say  desk  tool  cursor  propose
>     shape   creases  silhouette  pose_state  section  ghosts
>     sculpt  brush  brushes  sculpt_mask  sculpt_stroke  relax
>     stream  stream_on  stream_status  stream_off  events
>     safety  snap  restore  save  split_boundary_fans
>
> Outside Blender: `tools/silh_art.py` (canon art as numbers), `tools/bl-tail` (watch the
> event stream).
>
> Every command is journalled to `work/bl_journal.jsonl`.
>
> **▶ ROADMAP — the checklist. Everything below this block is the dated account of HOW.**
>
> **⚠ THIS LIST IS PART OF THE WORK, NOT A SUMMARY OF IT. UPDATE IT IN THE SAME COMMIT AS THE
> CHANGE.** Rebuilt 2026-08-21 because it had rotted: it still listed eyelids, eye bones and
> blink as pending after all three shipped, and still said *"there are no shape keys on any
> object"* when there were nine. If a dated block below and this list disagree, THIS LIST is the
> bug. **Verified against the live scene 2026-08-21**, not from memory.
>
>     clyffy_mesh   15,918v · 16,146f · 96.9% quads · 0 ngons · 0 non-manifold · 0 degenerate
>                   1 island · 56 open edges (eye socket linings + rear, all intentional)
>     rig           49 bones (16 fingers, 4 IK) · 9 shape keys · UVMap present
>                   **2 actions, NOT 3** — `clyffy_walk` and `clyffy_news_read` were PURGED.
>
> **⚠ THE ANIMATION ACTIONS ARE GONE.** Blender drops zero-user actions on save and neither
> carried a fake user. `clyffy_walk` last existed in `AD_pre_cavity` (2026-08-25);
> `clyffy_news_read` went earlier. Only `clyffy_lookatAction` and `clyffy_meshAction` survive.
> This list claimed three actions for over a week while the file held none of them — the second
> time this checklist has asserted something the scene did not contain. The `.mp4` previews in
> `work/preview/` are the only record. Both are regenerable: `work/probes/walk_ik.py` and
> `work/probes/news_read.py`. **Set `use_fake_user` on every action you author.**
>
> Verified against the live scene 2026-09-04.
>
> ---
>
> ## ✅ COMPLETE
>
> **Base & body**
> * Head retopo shell; mouth rebuilt as two grids on the operator-approved lip seam; bevelled lip
>   band; jaw hinge fitted by measurement; jaw weights re-authored (they had been inverted).
> * Ears, horns, eyeballs, teeth, tongue built as separate objects (CP8/CP10).
> * Body shell crown to ankle, 93.5% quads at build time.
> * **Body verified against `SCAFFOLD`** — the thing it was retopo'd over, same scene, same scale:
>   mean deviation **0.0023**, max 0.0128, **zero bands over 0.02**. No shape defect exists.
>
> **Limbs**
> * `clyffy_hoof_R` (cloven), `clyffy_mitt_R` (cloven mitt + thumb nub), `clyffy_glove_R` (4
>   fingers + thumb + brass cuff, blended by voxel remesh). All gated: 0 ngons, 0 non-manifold,
>   0 degenerate.
> * All three **rigged and motion-tested**. Mirror vertex-group flip verified by measurement
>   (right prop moves, left moves 0.00000). Seam tear 20–28% of travel vs ~60% for a rigid bind.
> * **FINGER BONES, 2026-08-21** — 16 added (rig 29 → 45), both hands, both variants:
>   `f_index/f_middle/f_ring/f_pinky/f_thumb` on the glove, `m_in/m_out/m_thumb` on the mitt.
>   Digit positions MEASURED off the built geometry (the glove was voxel-remeshed after its
>   builder constants were used, so those constants had moved). Weighted by distance to the bone
>   SEGMENT, not by height — the thumb sits above the knuckle line and a z-rule would miss it.
>   Independence verified: with three digits curled 62–70°, **`f_index` moved 0.0000** while the
>   others moved 0.018–0.023. Snapshot `AA_pre_fingers`.
>
> **Eyes** — the lane is closed
> * Materials: sclera / iris / pupil, every value measured off `modelsheet_neutral.png`.
> * Socket lining · rim resampled 10→20 segments · three concentric lid loops.
> * **`eye.R` / `eye.L` bones + look-at** via `clyffy_lookat`: aim error 0.29°, ball centre fixed
>   to 1e-6 across five gaze directions.
> * Shape keys `blink` `heavy` `squint` `wide`, each gated against the blink baseline.
>
> **Mouth**
> * Lip line located by **posing the jaw and measuring what follows** (93 verts move >50%, 732
>   move <10%).
> * Shape keys `mouth_wide` `mouth_round` `mouth_press` `mouth_fv` `mouth_smile`; each key's
>   dominant delta lands in the axis it is meant to affect.
>
> **Animation**
> * **LEG IK, 2026-08-25** — `ik_foot.R/L` targets parented to `root`, `knee.R/L` pole targets,
>   two-bone IK on the shins, foot Copy Rotation from the target. Gated: ankle drift at rest
>   **0.0**, lifting the target 0.030 moves the ankle exactly 0.030, knee bends FORWARD.
> * `clyffy_walk` — rebuilt on IK with **ROOT MOTION**: 24f, step 0.110, travel 0.220/cycle,
>   cyclic with REPEAT_OFFSET so travel accumulates. **The feet plant** — from f4 to f13 the
>   stance ankle is exactly constant (y −0.0670, z 0.0550 every frame); total stance drift 0.008,
>   all of it the heel settling at contact.
> * `clyffy_news_read` — 180f: arm/hand gesture, speech (jaw rhythm + all five lip keys), three
>   blinks, eyes on camera with two glances away.
> * Deform gated before authoring: a walk-scale stride has **zero edges under 0.5**; even a big
>   arm gesture is milder than the blink.
> * Previews rendered: `work/preview/clyffy_preview.mp4`, `clyffy_news_read.mp4`, `clyffy_walk.mp4`,
>   `turnaround.png`.
>
> **Colour / materials** — every visible object now has one; nothing renders untextured grey.
> * **MOUTH CAVITY, 2026-08-25** — the inside of the mouth was painted BROWN FUR by the body's
>   region rule. 171 cavity faces found by ENCLOSURE (rays forward from an interior face hit the
>   muzzle wall with the mouth closed) and given `clyffy_mouth_interior` (dark oxblood). Teeth
>   moved off horn cream, which read olive, onto `clyffy_enamel`; tongue onto a deeper
>   `clyffy_tongue_pink` so it reads inside the mouth.
> * **Teeth/tongue clipping FIXED** — they hung outside the jaw when it opened. `teeth_lower`
>   tucked +0.0115y/+0.0060z, `tongue` +0.0130y/+0.0055z, in mesh data so the rig binding is
>   untouched. Confirmed gone from below, 3/4 and side.
> * Body split by MEASURED regions: tee (crease cluster at z 0.39-0.42 = hem, collar z 0.638,
>   sleeve cuff |x| 0.245), muzzle pad ABOVE the lip line, fur elsewhere. Boundary cleaned by a
>   neighbour-majority pass (23 flips) because a plane cut on a voxel mesh tears.
> * `clyffy_horn_R` + both teeth bands -> `clyffy_horn_cream`; `clyffy_tongue` -> muzzle pink;
> * `clyffy_ear_R` split brown/pink by FACE NORMAL (the inner cup faces the midline), 2246/718.
> * New measured materials: `clyffy_tee_navy` (0.0242, 0.0369, 0.0723), `clyffy_fur_white`
>   (0.8879, 0.8879, 0.8796). All carry `["source"]`/`["method"]`.
>
> **THE MOUTH ACTUALLY OPENS, 2026-08-28 (snapshot `AF_pre_lipsplit`)** — it did not before, and
> everything built on it was built on a mouth that could not part.
>
>     tracking the SAME two lip-tip verts at every angle:
>     jaw  0 deg  aperture 0.0248      jaw 28 deg  aperture 0.0705
>     jaw 20 deg  aperture 0.0574      jaw 44 deg  aperture 0.0958
>     upper lip tip holds at z 0.7476 EXACTLY at every angle (head-locked, correct)
>     midline verts responding to the jaw: 7 of 85  ->  42 of 85
>
> **⚠ I DIAGNOSED THIS WRONG FIRST AND THE OPERATOR ACTED ON IT.** I saw zero open edges on the
> lip line and concluded the seam had never been split. That is not a valid test — **a mouth does
> not need boundary edges.** A midline `section()` disproved it: the surface runs from the cavity
> roof forward to the upper lip tip (y -0.287), back into the mouth to y -0.223, and forward again
> to the lower lip tip (y -0.288). Distinct vertices, real fold, correct topology. He had already
> chosen "split the seam" on my bad call; the split was not done, and nothing was destroyed.
>
> **The real fault was WEIGHTS:** below the lip jaw 0.57 / head 0.43, and **AT the lip line head
> 0.84 / jaw 0.16** — the lower rim was held shut by the head. Re-authored in
> `work/probes/jaw_reweight.py`, classified against the **APPROVED LIP CURVE** (midline z 0.726,
> dip 0.709 at x 0.043, corner 0.728) with a 0.0055 ramp — never a z-plane, which is this file's
> own standing warning.
>
> **⚠ AND THE FIRST APERTURE METRIC WAS ALSO WRONG.** It compared `min(z of still verts)` against
> `max(z of moved verts)`, and the re-weight changed BOTH sets — so it reported the fix as a
> regression (+0.0087 -> +0.0017). Track the SAME two vertices across states.
>
> **⚠ EVERYTHING JUDGED AGAINST THE BROKEN MOUTH HAD TO BE RE-CHECKED.** The mouth could not open
> until 2026-08-28, so anything verified by looking at it was verified against a stuck lip:
> * **Teeth containment — HOLDS.** Re-rendered at jaw 44 (a real gape) from the side and from
>   below: no enamel or tongue outside the lip. The earlier tuck was over-applied but not wrong.
> * **Tongue — WAS WRONG.** Weighted 100% to the jaw, it swung **0.1197 behind the lip** at jaw 44
>   — into the throat — and the open mouth read as an empty hole. A tongue is muscle on the mouth
>   floor, not bone. Re-weighted as a gradient (tip 0.40 jaw / root 1.00 jaw) and moved forward
>   0.0175: retreat now **0.0527** at jaw 44, still 0.0163 inside at jaw 0.
>   `work/probes/tongue_weights.py`, `tongue_forward.py`.
> * **The lower teeth swinging back is CORRECT** and was not touched — the hinge sits at y -0.17,
>   z 0.80, so a 44-degree drop moves the tooth line back 0.098, which is what the measurement
>   shows. Jaws do that.
> * **STILL TO RE-JUDGE: the five viseme keys.** Their amplitudes were tuned against a lip that
>   could not move. They still apply (shape keys are vertex offsets, independent of weights) but
>   nobody has judged them on a working mouth.
> * **STILL MURKY:** the open cavity reads dark and structureless under flat Workbench shading,
>   and the teeth are simple 26-quad bands that barely read. Lighting or better teeth, not weights.
>
> **Mesh health**
> * **UNDER-JAW SLIVERS reduced 2026-08-25 with health untouched** — 245 slivers -> 180,
>   under-jaw 59 -> 51, while ngons/non-manifold/degenerate stay 0, islands 1, boundary 76.
>   Cost: tris 406 -> 650. `work/probes/sliver_sweep.py`. Both earlier attempts failed by
>   picking ONE threshold; this sweeps seven IN MEMORY (fresh bmesh per candidate, measured and
>   discarded) and applies the largest that passes a gate set BEFORE the results were seen.
> * The step that made it work is DISSOLVE THEN REPAIR: dissolve alone trades slivers for ngons
>   at every threshold (0 -> 121 at 0.0030), which is not a fix. Triangulating only the new ngons
>   and re-pairing them into quads clears them.
> * **0.0018 was also clean** (156 slivers, 30 under-jaw, 0 non-manifold, 0 ngons) and was
>   rejected only by a tris cap of +260 that I set in advance. Available if more sliver reduction
>   is wanted at 796 tris instead of 650 — but the cap was not moved after seeing the results.
>
> **Tooling**
> * `creases()` `silhouette()` `pose_state()` `section()` `ghosts()` in blkit; `tools/silh_art.py`;
>   the push signal channel; sculpt brushes; `tools/bl-tail`.
>
> **THE MOUTH WAS REBUILT, 2026-09-04** (snapshots `AI_pre_mouthrebuild`, `AM_mouth_done`) —
> it had carried a PARTIALLY WELDED DOUBLED SURFACE since `D_mouth_v1` on 2026-08-08: coincident
> quads with opposite normals sharing 2 of 4 verts. `stat()` called it healthy for three weeks
> because the defect produces ZERO open edges. It is why every colour rule, weight paint and
> viseme authored on it produced splinters.
>
>     metric                  before      after
>     near-180 folds              37          6
>     slivers                     43         10
>     midline lip gap         0.0082     0.0236   (0.0082 was the broken doubled surface)
>     non-manifold                 0          0
>     open edges                  76         56   (nostril loops absorbed by the rebuild)
>     jaw 0 deg -> 44 deg     0.0248 -> 0.0958    0.0237 -> 0.1185
>
> Four in-place repairs were tried first and ALL FOUR failed their gate and were reverted (weld
> 6e-4, weld 1e-6, delete duplicate sheets, weld+dedupe) — the two copies attach to their
> surroundings differently, so every merge or excision tears the neighbourhood. Cut chosen by
> sweeping depths and taking the smallest whose rim is a SIMPLE closed loop, every boundary vert
> degree 2 (y < -0.13 → 101 verts). Topology is an ANNULUS so no pole lands on the muzzle front.
> The opening curve came from the OPERATOR'S OWN 148-face mark; its corners landed at x ±0.078,
> which `viseme_keys2.py` then independently measured as 0.0781.
>
> ---
>
> ## ⬜ REMAINING, in priority order
>
> **0. RE-AUTHOR THE TWO LOST ACTIONS** — `clyffy_walk` and `clyffy_news_read`, from
> `work/probes/walk_ik.py` and `work/probes/news_read.py`, then SET FAKE USER on both. They must be
> redone anyway: the mouth was rebuilt on 2026-09-04, so the visemes and jaw range they were keyed
> against no longer exist.
>
> **0a. MOUTH CLOSED AT REST, 2026-09-04** (snapshot `AO_mouth_closed`) — DONE. Canon
> (`modelsheet_neutral`, all three views) shows the mouth SHUT as a shallow crease; the rebuild
> had left a 0.0236 rest gap that read as a gaping mouth with teeth and tongue on show.
>
>     rest aperture   0.0236 -> 0.005    (shut; NOT zero -- coincident lip loops
>                                         would recreate the doubled surface)
>     jaw 44 deg      0.0998             (upper lip fixed at z 0.7506 throughout)
>     cavity          reshaped: pinches at the lips then WIDENS, centre drops
>                     z 0.7436 -> 0.718 where the teeth and tongue actually sit
>     teeth + tongue  moved back 0.050 into the bag; hidden shut, visible open
>     teeth           already CONTINUOUS bands (1 island each) -- SPEC satisfied,
>                     the 2026-07-28 scallop is long gone
>
> **⚠ Do not "verify the tuck" with a ray test.** Casting forward from a part vertex counts a
> correctly-placed interior vert as OUTSIDE, because the ray exits through the mouth opening. That
> invalid metric drove a sweep that pushed the teeth out through the underside of the jaw. This is
> the FOURTH inside/outside test to fail on this mesh (see item 10). The valid gate is the render.
>
> **0b. THE MUZZLE PINK MASK IS UNFINISHED.** The rebuild reset the region to fur brown.
> The operator's 148-face UPPER LIP mark is applied (105 faces on the new, coarser topology) and
> saved at `work/probes/pink_mask/upper_lip.json` WITH COORDINATES, so it survives future retopo.
> Still unmarked: lower lip, corners, mouth interior, nose pad. The staged marking protocol is in
> the 2026-09-04 log entry — the operator marks in the viewport, I read the LIVE bmesh, never
> `data.polygons`.
>
> **1. Collar second pass** — first pass took spikes>0.8× from 23 to 12 and worst offset 0.1187 to
> 0.0633. Twelve remain. Snapshot `L_pre_collar`.
>
> **2. Tail** — roundness now 0.62–0.92 but segment counts stay irregular (11–28 per slice). Needs
> retopo, not more smoothing. Snapshot `P_pre_tail`.
>
> **3. Hoof cleft speck** — a white dot at the top of each cleft, right AT the fur line; the
> containment test only ever checked BELOW it.
>
> **4. Speech is hand-keyed, not audio-driven.** The visemes in `clyffy_news_read` are keyframes I
> authored. There is no audio track, no phoneme extraction, nothing that turns a script or a WAV
> into lip motion. That is the gap between "he mouths words" and "he reads the news".
>
> **5. The news performance is split across THREE action datablocks** — `clyffy_news_read` (bones),
> `clyffy_meshAction` (shape keys) and `clyffy_lookatAction` (the gaze empty). They are not linked;
> retiming or reusing one without the others will desync the performance.
>
> **6. Mitt vs glove deliberately unresolved** (operator kept both, mitt is the visible default).
> The glove's hand still reads small against the forearm.
>
> **7. Props and layers not started** — lanyard, badge, then the lab coat as its own wearable.
>
> **8. Body edge flow** — uniform voxel cells, no loops at shoulders/elbows/knees. Measured as NOT
> blocking anchor gesture or a walk. A real retopo pass is the operator's call.
>
> **9. MARKINGS AND CLEAN EDGES NEED A PAINTED MASK, not face assignment.** No white blaze, no
> Holstein patches, and the tee's neckline and hem read ragged because a per-face region boundary
> cannot follow a curve on a voxel mesh. A crease flood-fill was tried and LEAKED (15,696 of
> 16,254 faces — the garment's crease boundary is not closed); kept as a negative result in
> `work/probes/body_materials.py`. `UVMap` already exists, so this is a texture job.
>
> **10. THREE INSIDE/OUTSIDE TESTS ALL FAILED ON THIS MESH — do not write a fourth without a
> validation harness.** `clyffy_mesh` is NOT watertight (76 open edges at the socket linings and
> nostrils) and the mouth is a concave pocket, which breaks: (a) the escape test — the EYEBALL
> CENTRE reads outside because rays leave through the eye aperture; (b) parity — needs a closed
> surface; (c) closest-point + normal sign — failed on the eyeball AND the belly. All three were
> caught by probing five known-inside/known-outside points BEFORE trusting the result.
> `work/probes/mouth_parts_check.py` keeps all three and the harness. Until the mesh is
> watertight, **a render is the only reliable evidence** for anything inside the head.
>
> **11. The teeth are still simple 26-quad bands** — they read as plates rather than teeth. Fine
> at conversational distance, thin in close-up.
>
> ---
>
> ## ⏸ AFTER THE MODEL — an MCP SERVER FOR BLENDER
>
> **Operator's decision 2026-08-25: deferred until the model is finished, and recorded here as a
> real item so it stops being an intention.** He has asked for "the API" at least four times
> (2026-08-10 twice, 2026-08-19, 2026-08-25). Each time I answered by adding functions to
> `blkit.py` or writing another probe script and treated that as progress. **It is not an API, it
> is an accumulation** — and the inventory is the argument:
>
>     tools/blkit.py      1,201 lines · 47 functions · one flat module
>     work/probes/           51 one-off scripts
>     tools/                 75 more scripts, mostly retopo-era
>
> **WHAT HE ACTUALLY WANTS (his words, pinned 2026-08-25): an MCP SERVER.** The live session
> exposed as native tools that ANY agent calls directly — no bash wrapper, no Python pasted into a
> socket as a string, no `tools/bl 'result=...'`. Drivable by Codex, by coach, by a fresh session,
> not only by me.
>
> **What it replaces:** `tools/bl` + exec'd strings. `blender_daemon.py` stays — it is the session;
> the MCP server becomes the front door.
>
> **What has to fold in, and why it is not a weekend:** the 47 blkit functions are the obvious tool
> surface, but the REAL value is spread across the 51 probes as measured constants and gates —
> the hoof's containment rule, the blink's rotate-about-centre invariant, the walk's linear-curve
> requirement, the eye's 26.16° iris, every negative result. Exposing `blkit` alone would ship the
> shallow half. Consolidation is a prerequisite, not a follow-up.
>
> **Design notes to start from:** tools should be verbs with schemas (`mesh.health`, `shape.creases`,
> `rig.bind`, `gate.against_baseline`), every one returning measured numbers rather than prose;
> the gate pattern (compare against an ACCEPTED artifact, not against zero) belongs in the surface
> itself; and `pose_state()` style guards — "what state was this measured in" — should be part of
> every response, because three separate metrics lied this month for exactly that reason.
>
> **Mouth leftovers:** two concentric lip loops on the outer skin; the two 6-valence corner poles
> down to 5 and shifted off the deformation zone.
>
> **▶ THE CHANNEL (2026-08-10) — signals out of Blender, not photographs of it.** Two holes in the
> request/reply daemon are now closed:
>
>     stream_on() / events(since=N)   PUSH. Blender's own signals — depsgraph, msgbus, operator
>                                     history, undo/redo/save — appended to work/bl_events.jsonl
>                                     with a monotonic seq. Includes what the OPERATOR does by
>                                     hand: `mesh_changed {verts_moved, max_move, at, op}`.
>     section(axis, at, where=...)    GEOMETRY AS NUMBERS. A plane cut returned as ordered
>                                     polylines in the plane's own uv frame. A shelf reads as a run
>                                     of equal v; a fold reads as u going backwards. This replaces
>                                     reading profiles off renders.
>
> **SCULPT is wired too** — `brushes()` `brush()` `sculpt_mask()` `sculpt_stroke()` `relax()`.
> `brush()` leaves the brush LIVE so the operator can take the mouse mid-task. `sculpt_mask()` is
> the veto point: masked geometry is untouchable by every brush AND renders dark, so the protected
> zone is visible before a stroke. `relax()` is the measured, viewport-free alternative.
>
> **API traps verified here:** 5.x has NO brush datablocks until one is activated from the
> essentials asset library; brush `direction` must be set in try/except because the RNA enum reports
> a STATIC superset (ADD/SUBTRACT) while the live enum is `('DEFAULT')`; the sculpt mask is a POINT
> float attribute `.sculpt_mask` — `bm.verts.layers.paint_mask` no longer exists.
>
> **COLLAR, first pass (snapshot `L_pre_collar`):** relax over 393 verts around 86 spike sites took
> spikes>0.8x from **23 to 12** and worst absolute offset **0.1187 to 0.0633**, median ratio
> unchanged (no deflation), mesh health identical. NOT finished. And `section("x", 0.0)` found the
> real under-jaw defect that renders only hinted at: **two 3-point CLOSED loops** at (y -0.254,
> z 0.710) and (y -0.223, z 0.705) — detached slivers, plus narrow faces 0.002-0.003 thin by 0.036
> long around (y -0.17, z 0.749). That is the flat plate under the chin. Topology, not sculpt.
>
> **`propose(label, pred, tag=...)` is the veto point** — it selects what is about to change,
> arranges the desk, aims the viewport and shoots, and MODIFIES NOTHING. Use it before any edit:
> the operator sees the selection before it happens, and a predicate that grabs 4000 verts when it
> should grab 40 is caught before the damage, not after.
>
> **Scripts go in the scratchpad and run with `tools/bl -f <path>`** — bash quoting mangles
> anything with nested quotes. And `restore()` needs its OWN command: the context is not usable in
> the same command that reloads the file.
>
> **The old loop was `blender -b --python one_shot.py` — 30-60 s a step, and the only sense was a
> photograph. That is the single biggest reason this project crawled.** Ask the mesh; do not
> photograph it. Snapshot / try / measure / restore is four seconds, so a bad result costs nothing
> to reject — under the old loop the pressure was to keep it.
>
> **CURRENT STATE (2026-08-09).** `clyffy_mesh` **15,934 faces · 98% quads · 0 ngons ·
> 0 non-manifold · 0 degenerate · 1 island**, one continuous surface horn to hoof, saved to
> `work/RETOPO_clyffy.blend`. Rig `clyffy_rig`, 27 bones, jaw hinge fitted by measurement,
> procedural capsule weights. Parts: ears, horns, eyeballs, teeth, tongue.
>
> **The mouth was rebuilt on 2026-08-09** as two grids sharing the lip line (the correct
> construction — the lip is a boundary of both patches, not a diagonal through one). Lip sits
> **0.0000** off the operator-approved seam, evenly spaced. The jaw has its mass back. 19 open
> loops in the mouth band → 0. Full account in `BUILD_LOG.md`.
>
> **THE MOUTH MOVES (2026-08-10).** Lip rim bevelled into a band (steps 1 and 5 in one operation),
> jaw weights re-authored — they had been *inverted*, dragging the upper muzzle and leaving the
> lower jaw behind. At 25° the lower lip skin, teeth and tongue now move together within 12% and
> the upper lip moves exactly 0.0000. First motion test rendered: `work/motion_test.mp4`.
>
> **▶ ARMS, HANDS AND A WALK, 2026-08-21 (snapshot `Z_pre_anim`).** Two actions:
> **`clyffy_news_read`** (180f, the anchor performance) and **`clyffy_walk`** (24f, looping).
> `work/probes/news_read.py`, `work/probes/walk_cycle.py`. Videos in `work/preview/`.
>
> **DEFORM GATED FIRST, and the body is better than this file's own warning suggested.** Measured
> against the accepted blink baseline (worst 0.110, 10 edges under 0.5):
>
>     arms   small 20/25   worst 0.526   0 edges <0.5      legs  small 14/-18  worst 0.790   0 <0.7
>            mid   45/60   worst 0.429   2 edges <0.5            walk  24/-32  worst 0.641   0 <0.5
>            big   70/95   worst 0.243   6 edges <0.5            big   38/-55  worst 0.451   3 <0.5
>
> A walk-scale stride has **ZERO edges under 0.5** and even a big arm gesture is milder than the
> blink. "No edge flow at shoulders or elbows" is true of the topology but does NOT block
> anchor-scale gesture or a basic walk.
>
> **⚠ NO FINGER BONES EXIST.** Both the mitt and the glove are weighted only to `forearm`/`hand`,
> so the glove's four fingers are rigid decoration — neither hand can point, count or hold a page.
> All gesture is shoulder/upperarm/forearm/wrist. Adding a finger chain is the next step if a
> pointing or page-holding beat is wanted.
>
> **⚠ CLEAR THE POSE BEFORE READING A REST STATE — the same error as sampling shape-key bases from
> the EVALUATED mesh, repeated hours later in a different system.** `walk_cycle.py` captured REST
> from whatever pose the rig was in, which on a rebuild was the previous `clyffy_walk` at some
> frame, so every run compounded: the feet ended up permanently 0.18 apart in y and one floated
> 0.10 off the floor. Now the pose is zeroed first and the build is idempotent.
>
> **⚠ POSE-BONE `location` IS IN BONE-LOCAL AXES.** The hips bone points up, so world "up" is its
> local **Y**. Keying `.z` for the hip bob moved him fore/aft and the hip height never changed —
> measured as `hips z` constant at 0.2000 across the whole cycle.
>
> **⚠ BLENDER 5 MOVED F-CURVES: `action.fcurves` IS GONE.** They live at
> `action.layers[0].strips[0].channelbags[n].fcurves`.
>
> **⚠ A HALF-CYCLE SHIFT MUST DROP THE LOOP-CLOSING KEY FIRST.** Wrapping frame 25 (the duplicate
> of frame 1) produced two keys at frame 13 and put the left leg in exactly the same pose as the
> right — both feet measured at y -0.0528. Symmetry restored: stride separation now swings
> **-0.0607 .. +0.0607** with f1 and f13 exact mirrors.
>
> **NEXT:** finger bones if pointing is wanted; bigger gesture amplitude is available (the deform
> budget is there); and the mouth cavity still reads unfinished when open (STATUS item 6).
>
> **▶ FIVE VISEME LIP KEYS BUILT, 2026-08-21 (snapshot `Y_pre_visemes`).**
> `work/probes/viseme_keys.py`. Shape keys: `Basis` `blink` `heavy` `squint` `wide`
> **`mouth_wide` `mouth_round` `mouth_press` `mouth_fv` `mouth_smile`**.
> Health: 0 ngons · 0 non-manifold · 0 degenerate. Sheet: `work/shots/VISEME_sheet.png`.
>
> **ARCHITECTURE: the JAW BONE does opening, the SHAPE KEYS do lip shape.** A viseme is a jaw
> angle plus a lip key — cheaper than a full 12-viseme set, and it composes.
>
>     rendered at the jaw angle each viseme naturally uses:
>     press/MBP 0 deg · fv/FV 6 deg · smile 4 deg · round/OU 12 deg · wide/E-AI 18 deg
>
> **⚠ FIND THE LIP LINE BY POSING THE JAW, not by coordinates.** The approved seam verts no longer
> exist (the voxel remesh replaced them); a coordinate box caught **475 verts of whole muzzle**;
> `creases()` gave 130 concave runs, mostly legitimate deep folds. Rotating the jaw 25 deg and
> measuring what follows is bimodal and unambiguous: **93 verts move >50%, 732 move <10%, ~28 in
> between** — and it proves the jaw weights are sharp as a by-product.
>
>     every gate is a DELTA FROM REST (width 0.1664, centre_fwd -0.2877, corner_z 0.7198)
>     key            width   centre_fwd   corner_z   lower_mid_z   verts
>     mouth_wide    +0.0015    +0.0000     +0.0003     -0.0028      293
>     mouth_round   -0.0024    -0.0038     -0.0001     +0.0029      293
>     mouth_press   -0.0006    +0.0017     -0.0006     +0.0030      293
>     mouth_fv      +0.0000    +0.0000     +0.0003     +0.0068       93   (lower lip ONLY)
>     mouth_smile   +0.0013    +0.0000     +0.0021     +0.0009      293
>
> Each key's dominant delta lands in the axis it is supposed to affect, and `fv` touches only the
> lower lip.
>
> **⚠ ZERO EVERY SHAPE KEY BEFORE SAMPLING THE BASE.** The base positions come from the EVALUATED
> mesh, so a key left switched on gets baked into the next key as if it were the rest shape — a
> silent error that compounds across rebuilds. With the zeroing, two consecutive runs give
> identical numbers; the build is idempotent.
>
> **⚠ A VIEWPORT LEFT IN CAMERA VIEW IGNORES `shot()`'s framing.** After the preview render it
> still was, and two rounds of "close-ups" came back framed on the whole torso. Set
> `region_3d.view_perspective = "PERSP"` first.
>
> **RESOLVED:** the bright quad patch on the round key's upper lip is **not** a flipped face —
> the mesh has **0 flipped normals anywhere**. It is flat shading on a quad the key makes
> non-planar.
>
> **NEXT: the scripted talking test (phase M6), outstanding since the v2 rig.** Also visible in the
> sheet: with the mouth open the CAVITY reads unfinished — the teeth bands and tongue are loose
> plates, which is the known leftover STATUS item 6 (teeth clip the lip band at the corners).
>
> **▶ THE EYE LANE IS CLOSED, 2026-08-20 (snapshot `W_pre_squint`).** Shape keys on `clyffy_mesh`:
> **`Basis` / `blink` / `heavy` / `squint` / `wide`**. `work/probes/eye_expr_keys.py`.
> Health: 16,083v · 0 ngons · 0 non-manifold · 0 degenerate · 1 island. Renders:
> `work/shots/EXPR_strip.png`.
>
>     key      aperture 128.7 deg ->   rim verts inside ball
>     squint             72.7 deg              0
>     wide              144.7 deg              0
>
> **The LOWER lid moves in these two.** A rotation of +ang about AXIS lowers a vertex, so closing
> the upper lid is +ang and RAISING the lower lid is -ang. Both margins weighted to zero at the
> canthi, as established by the heavy key.
>
> **Sweeps are expressed in DEGREES, not fractions of closure.** After the heavy key's
> lateral-matching artifact inflated a vertex's sweep to ~78 deg, an absolute angle is both easier
> to reason about and impossible to inflate by a bad vertex pairing.
>
> **Every key gated against the BLINK, which is already accepted and renders clean:**
>
>     key      worst compression   edges <0.5   edges <0.7
>     blink          0.110             10           28      <- the accepted baseline
>     heavy          0.249              6           18
>     squint         0.259              4           18
>     wide           0.792              0            0
>
> **⚠ SHAPE KEYS ADD.** Driving `blink` and `heavy` together will overshoot the closure the blink
> was solved for. They are alternatives on one lid, not layers — drive one at a time, or build an
> explicit combination key.
>
> **THE EYES ARE DONE:** materials (sclera/iris/pupil, measured) · socket lining · 20-segment rim ·
> three lid loops · five shape keys · eye bones + look-at. STATUS items 2, 3 and the blink half of
> 4 are complete.
>
> **▶ THE LONG POLE IS NOW VISEMES (item 4).** A hinging jaw cannot do speech alone, and the mouth
> geometry (two grids sharing the approved lip line, bevelled lip band, jaw weights re-authored)
> has been waiting since 2026-08-10. That is a multi-session build.
>
> **▶ THE EYES LOOK AT THINGS, 2026-08-20 (snapshot `V_pre_eyebones`).** `work/probes/eye_bones.py`,
> gated by `lookat_verify.py`. STATUS item 3, done.
>
>     eye.R / eye.L        heads EXACTLY at the ball centres, parented to `head`
>     weights              clyffy_eye_R split off `head`: 5,762 verts per ball
>     clyffy_lookat        an Empty, hide_render=True, DAMPED_TRACK on both bones
>
> **THE BONE HEAD SITS AT THE BALL CENTRE, and that is the entire design.** A sphere rotating about
> its own centre maps onto itself, so a look-at can never drive the eye out through the socket —
> no clamping, no poke-through test to tune. **Measured rather than asserted, across five gaze
> directions:**
>
>     pose     aim error      ball centre moved
>     ahead      0.29 deg        0.000000
>     left       0.29 deg        0.000001
>     right      0.29 deg        0.000001
>     up         0.29 deg        0.000001
>     down       0.29 deg        0.000001
>
> The 0.29 deg is the face-centre quantisation of the 102-face pupil cap, not a tracking error —
> it is identical at every pose, including dead ahead.
>
> **The face-assigned iris rotates with the ball for free**, which is exactly why `eye_material.py`
> assigned it by ANGLE rather than by texture. That decision paid off here.
>
> **NEXT for the eyes:** squint and wide as further keys off the same geometry. After that the eye
> lane is closed and the long pole becomes VISEMES (STATUS item 4) — a hinging jaw cannot do speech
> alone, and blink is currently the only expression key.
>
> **▶ THE HEAVY LID IS BUILT, 2026-08-20 (snapshot `U_pre_brow`) — the operator's original eyelid
> spec, "shallow at REST, heavy for depression and other heavier emotions".** Shape keys are now
> `Basis` / `blink` / `heavy` on `clyffy_mesh`. `work/probes/heavy_key.py`. Health unchanged:
> 16,083v · 0 ngons · 0 non-manifold · 0 degenerate · 1 island.
>
>     margin top      71.0 -> 19.9 deg      aperture left OPEN at +14.6 deg
>     tilt            0.80 nasal -> 1.25 temporal, so the outer corner drops further
>     brow            translated down 0.0065, tapering out toward the forehead
>     rim verts inside the ball: 0
>
> **⚠ A LID ROTATES AS A UNIT — do not scale each vertex by its own distance to closure.** The
> first version did, and a lateral-matching artifact paired mid-height vertices with the deep
> bottom-centre vertex, giving them a ~78 deg sweep. Aperture came out at **-6.9 deg (crossed)** —
> half shut, not heavy — and an edge pinched to 0.345. One base angle, tilted nasal-to-temporal and
> weighted to ZERO at the canthi (where a real lid pivots), fixes both.
>
> **▶ BROW RINGS: TRIED AND REVERTED, and the STATUS claim they answered was WRONG.**
> This file said brow loops "cannot be retrofitted". That was overstated — adding resolution later
> is exactly what the lid rings did. `work/probes/brow_rings.py` is kept as the negative result:
> only **4 radial edges per eye** exist leaving the lid band, so it added 16 verts and 4 ngons, and
> it added RADIAL resolution when the measured collapse is ANGULAR (20 verts round the lid band,
> then 4 above it). Radial subdivision cannot fix an angular collapse.
>
> **⚠ GATE A NEW DEFORMER AGAINST ONE ALREADY ACCEPTED, not against zero.** Worst edge compression
> looked alarming until measured beside the blink, which is a bigger motion and renders clean:
>
>     blink   worst 0.110   <0.5: 10 edges   <0.7: 28   <0.85: 79   median 1.000
>     heavy   worst 0.249   <0.5:  6 edges   <0.7: 18   <0.85: 37   median 1.000
>
> Heavy is strictly milder than an artifact already judged good, and the compression sits at the
> canthi, which is where real lids compress. **That is the evidence the brow needs no extra loops.**
>
> **NEXT for the eyes:** squint and wide as further keys off the same geometry, then eye bones +
> look-at (cheap now that the iris is face-assigned and rotates with the ball).
>
> **▶ THE EYES BLINK, 2026-08-20 (snapshot `T_pre_lids`) — THE FIRST SHAPE KEYS IN THIS PROJECT.**
> `Basis` + `blink` on `clyffy_mesh`. Builders: `work/probes/lid_rings.py`, `lid_ngon_fix.py`,
> `blink_key.py`. Health after all of it: **16,083v · 16,254f · 0 ngons · 0 non-manifold ·
> 0 degenerate · 406 tris (unchanged) · 1 island · 76 open edges (unchanged).**
>
> **① LID RINGS.** The rim was not findable as an open loop any more — attaching the socket lining
> made it interior. Found it by walking OUTWARD from the lining's open boundary: three lining rings
> at exactly d 0.0271 from the ball centre, then **the rim: 20 verts at d 0.0299, uniform**. The
> band outward of it was **10 quads + 9 tris** (the 20-vert rim meeting the original 10-vert skin
> ring), so a plain edge subdivide could not give clean loops — `bmesh.ops.subdivide_edgering` did.
> The lid band is now **rim 20 + rings of 21 and 23**, which is the three margin-parallel loops the
> spec asks for.
>
> **② THE HEXAGON SPLIT MUST BE CHOSEN BY AREA, NOT BY DIAGONAL LENGTH.** The edgering left four
> 6-gons at the canthi. Splitting on the SHORTEST diagonal collapsed one half of each to zero area
> — **4 degenerate quads**, and dissolving those traded them straight back into 4 ngons. Choosing
> the diagonal that maximises the SMALLER half's area gives 0 and 0. **A fix that trades one health
> metric for another is not a fix.**
>
> **③ BLINK IS A ROTATION ABOUT THE BALL CENTRE, and that is the whole point.** A rotation
> preserves distance from the centre exactly, so a lid that starts outside the eyeball CANNOT end
> up inside it — no clamping, no clearance tolerance to tune. Verified: `rim_verts_inside_ball: 0`,
> closest rim distance 0.02989 against the rim's own 0.0299.
>
> **⚠ EACH UPPER VERTEX CLOSES ONTO ITS OWN OPPOSING LOWER VERTEX, not onto a fixed elevation.**
> A constant target (-25 deg) left a 33-degree band of eyeball showing at the bottom centre,
> because the lower margin dips to -58 there while sitting at -13 near the canthi. Per-vertex
> targets also hold the canthi still for free — there the two margins coincide. Result: uniform
> **-4.0 deg overlap** at every upper vertex, both eyes. Renders sealed.
>
> **Two errors worth keeping:** the first sweep ran BACKWARDS (margin swept UP to 142 deg — sign of
> the rotation), and weighting the sweep by CLOCK ANGLE landed the margin at -0.5 deg instead of
> -25, because the aperture is tilted and its highest vertex is not at clock 90. Weight by
> ELEVATION, which is the same measure the target is expressed in.
>
> **NEXT for the eyes:** heavy/droop, squint and wide as further shape keys off this same geometry
> (the mass is now built), brow rings, then eye bones + look-at.
>
> **▶ COLOUR IS A VARIANT SET WITH PROVENANCE, 2026-08-19 (operator's call: brown AND Holstein are
> both legitimate versions).** `work/probes/variants.py`. Every material now carries `["source"]`
> and `["method"]` custom properties, so no colour in this file is again a thing someone picked and
> nobody can trace.
>
>     clyffy_keratin       (0.1301, 0.1248, 0.1195)   turnaround_holstein_5view.png
>     clyffy_sclera        (0.7682, 0.7379, 0.7084)   modelsheet_neutral.png  (p90)
>     clyffy_iris          (0.4020, 0.1356, 0.0437)   modelsheet_neutral.png
>     clyffy_pupil         (0.0018, 0.0027, 0.0048)   modelsheet_neutral.png
>     clyffy_fur_brown     (0.2159, 0.0976, 0.0648)   modelsheet_neutral.png
>     clyffy_horn_cream    (0.6654, 0.5520, 0.4072)   modelsheet_neutral.png
>     clyffy_muzzle_pink   (0.6724, 0.3864, 0.3564)   modelsheet_neutral.png
>     clyffy_glove_leather / clyffy_brass             OPERATOR-CHOSEN, not sampled
>
> **⚠ THE CHARCOAL I SHIPPED WAS INVENTED.** `clyffy_horn` was (0.075, 0.072, 0.070) because I
> chose it. Sampled off the Holstein turnaround the hoof is **(0.1301, 0.1248, 0.1195)** — about
> **1.7x brighter**. Hoof and mitt sample within 0.008 of each other, which is evidence they are
> ONE material in canon, so they now share `clyffy_keratin` and `clyffy_horn` is deleted.
>
> **⚠ AND I LET THE HOLSTEIN SHEET DECIDE COLOUR AFTER USING IT ONLY FOR SHAPE.** The approved head
> sheet is a BROWN cow and the approved element is `Clyffy-BROWN-avatar-target`, yet I built the
> extremities charcoal off the black-and-white turnaround without asking. Same failure as the
> retracted arm finding: a reference used correctly for one thing, then silently promoted.
>
> **UNSOURCED, and it must not be invented:** the BROWN variant's hoof/mitt colour has **no
> reference anywhere on disk** — the approved sheet is head-only and the brown prototype shows a
> Holstein body. Keratin is shared across both variants until the operator supplies one.
>
> **⚠ SMALL, KNOWN, UNFIXED:** a white speck shows at the top of each hoof cleft, right AT the fur
> line. The containment test only ever checked BELOW the fur line (`z < FUR_LINE`), so that one
> band was never covered. Visible in `work/shots/CHK_hoof_close.png`.
>
> **HANDS: BOTH KEPT (operator's call).** `clyffy_mitt_R` is the visible default; `clyffy_glove_R`
> stays hidden and toggleable. The ambiguity is deliberate, not an oversight.
>
> **▶ THE EYES HAVE MATERIALS, 2026-08-18 (snapshot `S_pre_eyemat`).** They no longer render as a
> dark recess and can finally be judged. `work/probes/eye_material.py`.
>
>     clyffy_eye_R   11,524v / 12,288f · 0 ngons · 0 non-manifold · 0 degenerate · 2 islands
>     materials      clyffy_sclera · clyffy_iris · clyffy_pupil  (assigned PER FACE by angle)
>
> **Every number MEASURED off `reference/approved/modelsheet_neutral.png`** — the sheet that IS
> authoritative for the head:
>
>     iris / eye-opening width   0.497   ->  iris half-angle  26.16 deg
>     pupil / iris width         0.522   ->  pupil half-angle 13.31 deg
>     sclera sRGB (227,223,219)  ->  linear (0.768, 0.738, 0.708)
>     iris   sRGB (170,103, 59)  ->  linear (0.402, 0.136, 0.044)
>     pupil  sRGB (  6,  9, 15)  ->  linear (0.002, 0.003, 0.005)
>
> **⚠ SCLERA ALBEDO IS THE p90, NOT THE MEDIAN.** The median (208,202,197) bakes in lid shadow,
> and shadow is lighting, not albedo — the same trap as the muzzle colour in 2026-07-30.
>
> **⚠ DO NOT AIM THE GAZE ALONG THE SOCKET AXIS — IT MAKES HIM WALL-EYED.** The measured aperture
> axis is ~20 deg OUTWARD (a cow's sockets are laterally set), and an iris centred in it reads as
> diverging from the front. The approved sheet shows the irises centred in the openings AS SEEN
> FROM THE FRONT, offset only +0.041 of eye width nasally = **4.2 deg of convergence**. Gaze is
> therefore forward + 4.2 deg inward. The aperture is 62 deg half-angle so a 26 deg iris sitting
> 20 deg nasal of the aperture centre still clears the rim.
>
> **⚠ AND THE FIRST ATTEMPT AIMED IT BACKWARDS INTO THE SKULL.** After the socket lining was built,
> the aperture rim STOPPED BEING AN OPEN BOUNDARY — the only open loop near the eye is now the
> innermost lining ring, which sits BEHIND the ball. "Socket centre minus ball centre" therefore
> pointed the wrong way. A `gaze.y > 0` assertion now catches it.
>
> **The balls were subdivided 384 -> 6,144 faces each** and snapped back onto their own spheres
> (exact — STATUS records them as perfect spheres r 0.0257). At 384 faces a 13-deg pupil landed on
> ~5 faces and rendered as a pentagon. Vertex group `head` survived; still ARMATURE-bound.
>
> **A viewport SOLID shot needs `shading.color_type = "MATERIAL"`** or it paints one flat colour
> and no material can be judged from it — the clay-render trap in its viewport form.
>
> **NEXT for the eyes, unchanged:** upper/lower lid split on the 20-segment rim, then blink as a
> shape key (there are still NO shape keys on any object), then brow rings.
>
> **▶ THE PROPS ARE RIGGED AND MOTION-TESTED, 2026-08-18 (snapshot `R_pre_weights`).**
> `clyffy_hoof_R`, `clyffy_mitt_R` and `clyffy_glove_R` were free-floating objects that did not
> follow the skeleton at all. All three now: parented to `clyffy_rig`, ARMATURE modifier AFTER the
> Mirror, and weights. Builders `work/probes/bind_props.py` + `bind_blend.py`; gates
> `bind_verify.py`, `seam_test.py`, `tear_test.py`.
>
> **⚠ THE MIRROR TRAP: a Mirror modifier copies vertex groups VERBATIM.** Weight every vert to
> `foot.R` and the LEFT hoof is driven by the RIGHT foot — invisible at rest and invisible in any
> still. Needs `use_mirror_vertex_groups = True` AND an oppositely-named group to land on, so an
> empty `.L` group is created for every `.R` one. **Verified by posing one side: right prop moved,
> left prop moved 0.00000.** Modifier order is load-bearing — Mirror must run BEFORE Armature.
>
> **⚠ RIGID BINDING A PROP TO ONE BONE TEARS IT OFF THE SKIN.** The wrist band is a **50/50 blend
> of `hand.R` and `forearm.R`** (and the ankle is `shin.R` 0.378 / `foot.R` 0.359 / `thigh.R`
> 0.214) — as a joint should be. A rigid prop follows one bone fully and the fur around it follows
> half, so the seam opens. Props now take the SKIN'S OWN weights by nearest-vertex transfer,
> ramping from pure own-bone at the tips to skin-matched at the seam. **The ramp must COMPLETE
> BELOW the seam band** — finishing it above left the seam 78% hand-driven against the skin's 50%.
> Constrain the nearest-skin search to the limb: unfiltered, it walked onto the torso and pulled
> `chest`/`hips`/`spine` into the mitt.
>
> **⚠ THREE METRICS MISLED ME IN A ROW TODAY. CENTROID DISPLACEMENT IS NOT A SEAM TEST.** The seam
> band sits 0.007 below the hand pivot, so opposite sides of a ring move opposite ways and the
> centroid barely shifts however badly the surface deforms — it reported a 3.9x mismatch where the
> prop's weights matched the skin's to within 0.02. **Tearing is co-located points drifting apart:**
> pair each prop seam vert with its nearest skin vert at rest and compare DISPLACEMENT VECTORS.
> (The other two: `closest_point_on_mesh` across islands, and `silhouette()` on a posed rig.)
>
>     at a 30-degree bend      mean gap opened     max        as % of travel
>     hoof                       0.00235          0.00727        20.3%
>     mitt                       0.00155          0.00470        27.2%
>     glove                      0.00200          0.00727        27.7%
>
> **MOTION TESTED** across frames 1/20/35/45/60 of `clyffy_motion_test.001` — props stay attached,
> no side swap, `ghosts()` clean: `work/shots/MOT_strip.png`. Scene left on frame 1.
>
> **STILL OPEN:** the residual seam gap is weight-ramp resolution (I ramp by z; the skin varies in
> 3D) — a full per-vertex transfer in the seam zone would close it further if it ever shows.
>
> **▶ THE GLOVE IS BLENDED, 2026-08-15 — `work/probes/glove_blend.py` (v2).** Same forms as v1,
> unioned by a **VOXEL REMESH at 0.0018** instead of stacked — the EAR's method. Fingers overlap
> the palm by 0.013 (a union of TOUCHING shells is still two shells) and splay 1.30 toward the
> tips, so the remesh webs the bases and frees the ends, which is what a glove does.
>
>     clyffy_glove_R   14,148v / 14,164f · 14,124 quads · 0 ngons · 0 non-manifold
>                      2 islands (one continuous leather form + the crisp brass cuff)
>     creases(concave)  v1 0.4578 hard seam  ->  v2 **0.0**, the same as the mitt
>
> The brass cuff is deliberately NOT remeshed — it is a crisp band on another material.
> **The glove is still HIDDEN and the mitt is still the visible default.** `ghosts()` clean.
>
> **⚠ closest_point_on_mesh IS NOT AN INSIDE TEST ON A MULTI-ISLAND MESH.** It returns the nearest
> surface across ALL islands, so every fur vert under the cuff reported "outside" — its nearest
> surface was the CUFF'S BOTTOM CAP, not the palm wall. The tell was that the number sat at exactly
> `41 / 0.01369` across three materially different builds. Test against the ONE island that is
> supposed to contain the thing. Real answer: **0 outside.**
>
> **⚠ A VOXEL REMESH ROUNDS CONVEX CORNERS INWARD**, so a form must start proud of what it needs to
> cover. And the robust way to guarantee containment is not to inflate an analytic envelope until
> it works — it is to UNION THE THING'S OWN MEASURED SECTION into the same remesh (the wrist plug),
> which makes it true by construction rather than by tuning.
>
> **▶ SHAPE SENSES — ADDED 2026-08-15. `creases()` · `silhouette()` · `pose_state()` ·
> `tools/silh_art.py`.** Built after the gloved hand passed EVERY health metric (0 ngons,
> 0 non-manifold, 0 degenerate, containment 1 vert) and still rendered as a stack of primitives.
> The defect was geometric and real and NOTHING in blkit could see it. These ask about SHAPE, not
> health, and they return numbers so a render confirms rather than discovers.
>
>     creases(name, angle=55, concave_only=True)
>         Runs of hard dihedral edges. A CONCAVE break is one form jammed into another
>         without blending — that is what the eye reads as "glued together".
>         glove 4 runs / 0.4578 hard length · mitt 0 · hoof 0.  After the fix: glove 0.
>
>     silhouette(view="front"|"side", bands, gap=0.012, at_rest=True)
>         The outline as numbers, per height band: width and centre normalised by total
>         height, plus how many separate RUNS (that is what makes legs, the armpit gap and
>         a cloven toe legible). Uses the EVALUATED depsgraph, so Mirror counts.
>
>     tools/silh_art.py <img> --panel N --panels 5 --against model_silh.json
>         The SAME measurement taken off a canon image. Art as DATA, not as a picture to
>         hold up beside a render.
>
> **⚠ ALWAYS MEASURE AT REST — `silhouette()` now does by default, and REPORTS the scene's
> actual pose either way.** The first real run said the head was wildly asymmetric. Nothing was
> wrong: the scene was sitting on **frame 45 of `clyffy_motion_test.001`** with the head turned
> 18 degrees, the jaw at 10.5 and both ears rotated. A shape sense that does not say so invites a
> fix to a defect that is not there. (`pose_state()` asks directly. Note `creases()` and every
> `o.data.vertices` query read the BASE mesh and are unaffected by pose.)
>
> **⚠ THE FIRST THING creases() FOUND WAS A BUG EVERY HEALTH METRIC CALLED CLEAN.**
> `glove_build.py` had `PALM_ZS = [..., 0.2940, GL_PALM_TOP]` where `GL_PALM_TOP` had been
> lowered to `0.2930` — so the loft climbed PAST its own top ring and folded back on itself.
> Three runs at **-180 degrees**. Ring heights are now DERIVED from the top, never hardcoded
> beside it. Hard length 0.4578 -> 0.
>
> **▶ RETRACTED, SAME DAY — "the arms hang too far out from the torso" was WRONG.**
> I measured the model's front silhouette against
> `reference/look/turnaround_holstein_5view.png`, got mean deviation 0.111, saw it concentrated
> where the arms are, and published "the body proportions are right, the arms hang too far out".
> **Two things make that comparison invalid and I did not check either before reporting it:**
>
> 1. **That sheet is not an authoritative BODY reference.** This file's own 2026-08-07 reference
>    audit says so in as many words: SPEC.md is head-only and *"there is no approved body sheet at
>    all"*. It is authoritative for the head and for hoof/mitt SHAPE. It is not for proportion.
> 2. **The two figures do not share a vertical scale.** The model's head is **28.7%** of its
>    height; the sheet's is **23.8%** — the operator enlarged the head on purpose for the mouth
>    work. So "fraction of total height" is not a common unit and a band-by-band width diff is not
>    measuring the same thing on both. Renormalised on ground-to-neck body length, the model is
>    uniformly **+0.11 to +0.46 wider at EVERY band** — not an arm defect at all, just two
>    differently proportioned renders of the same character.
>
> **▶ THE COMPARISON THAT MEANS SOMETHING FOR THE BODY IS AGAINST `SCAFFOLD`**
> (`work/probes/scaffold_diff.py`). It is the thing the model was retopo'd over, it is
> authoritative for the body by the 2026-08-05 ruling, it sits in the same scene at the same scale,
> and it needs no normalisation. Result:
>
>     model BODY ONLY (hooves + mitts excluded)   mean dev 0.0023 · max 0.0128 · bands over 0.02: NONE
>     model AS BUILT                              mean dev 0.0132 · max 0.2216 · bands over 0.02: two
>
> **The body has no measurable shape defect against its own source** — 40 bands, worst 0.0128 at
> the neck (v 0.713, model marginally narrower than scaffold). The only two bands that deviate are
> **v 0.2125 and v 0.2375, and they are the MITTS I added**: 0.3428 body-only vs 0.5348 with props,
> against a scaffold reading of 0.3453. The scaffold's arm just tapers out and stops; the hand was
> always going to be a separate object built past the wrist ring. That deviation is the hand
> existing, not a defect. Hooves cost +0.007 at the sole — neutral.
>
> **⚠ EARNED: a silhouette diff is only as good as the reference and the shared scale.** Before
> reporting one, ask (a) is this reference authoritative for the thing being measured, and (b) do
> both figures share the normalisation I am using. `silhouette()` gives a real number against
> anything, including something it should never be compared to.
>
> **⚠ ALWAYS CLASSIFY AGAINST THE LIP CURVE, NEVER A Z-PLANE.** The lip dips to z 0.709 at x 0.044
> and rises to 0.728 at the corners, so a flat z-box mixes upper lip with lower. It made my first
> jaw probe report a fix as a regression, and it is the same mistake `mouth_split.py` made
> originally.
>
> **⚠ THE LIVE SESSION NAMESPACE IS PERSISTENT — A SCRIPT VARIABLE CAN SHADOW A blkit FUNCTION.**
> `render_audit.py` assigned `ghosts = [...]`, and every later `ghosts()` call died with
> `'list' object is not callable`. blkit is exec'd into the namespace, so it is NOT importable
> (`import blkit` fails). Name scratch variables distinctly, or restart with `tools/bl-up --restart`.
>
> **⚠ A VIEWPORT SHOT CANNOT SEE A RENDER GHOST — this is what made FOUR HORNS (2026-08-10).**
> `SCAFFOLD` (216,798 verts, 4,525 of them above z 0.95, UNRIGGED) was `hide_viewport=True` but
> `hide_render=False`. It therefore appeared as a static ghost in every RENDER — including
> `motion_test.mp4` — while being invisible to every `shot()` I took, because `shot()` is a viewport
> grab. The rigged horns moved, its horns did not: four horns. The horn object itself was never at
> fault (`clyffy_horn_R`, 362 verts, 181 per side, ALL weighted to `head`). Fixed and verified in a
> real Workbench render. **`ghosts(fix=True)` now audits this — run it before believing any render.**
>
> **⚠ RUN A MOTION TEST BEFORE BELIEVING ANY RIG NUMBER.** The inverted jaw weights and the collar
> sawtooth both survived every static render this week. Neither is visible in a still.
>
> **⚠ NEVER MICRO-EDIT THE LIP TO FIX ITS LOOK.** Pushing lip verts proud along their normals took
> slivers 26 → 32 → 38 and tore flaps out of the surface. Twice. The cause is structural: without
> a loop aligned to the lip, moving verts onto the seam only shears the faces around them.
>
> **⚠ THE BODY HAS NO EDGE FLOW.** It is a voxel remesh: uniform cells, no loops round shoulders,
> elbows, knees or mouth. The head HAS flow (concentric mouth bands, clean eye rings) — see
> `work/shots/topo_body.png`, where the difference is visible rather than argued. This is why the
> head deforms and the body does not, and patching cannot fix it; it needs a retopo pass with real
> loops. **This is the operator's call and the one place he is genuinely faster than scripting.**
>
> **⚠ TRAPS THAT COST REAL TIME — all verified on this mesh, 2026-08-09.**
>
> * **`to_mesh()` REINDEXES.** "The verts I just made" is not a thing that survives a write. Never
>   identify geometry by index range across a `to_mesh`.
> * **To find the outer skin, cast a ray, do not trust normals.** Straight down: nothing of the
>   head below it → it IS the underside. Face-normal tests and index ranges both failed and tore a
>   sawtooth fringe under the chin, twice.
> * **`fill_grid` interpolation throws verts far off the surface** on a saddle-shaped loop — up to
>   **0.5048** here — and it created the 12 cm cheek spur when the snap tolerance let them stay.
>   ALWAYS plant patch verts on `SCAFFOLD` first, then clamp anything past 0.020 back onto it.
> * **`fill_grid` returns `FINISHED` while doing nothing** if the selection is not one closed loop.
>   Check the vertex count, never the return value.
> * **`remove_doubles` in the mouth took non-manifold 0 → 22.** Weld only what you have measured.
> * **`delete(context="FACES")` removes orphaned verts; `"FACES_ONLY"` keeps them.** Pick on purpose.
> * **`holes_fill` defaults to `sides=4`** and silently skips every hole bigger than a quad. Pass
>   `sides=0`.
> * A ray "is it poking out" test is meaningless inside a concave pocket — it escapes through the
>   mouth opening and reports "outside".
>
> **RESTORE POINTS** in `work/snaps/` — each is a one-second `restore("name")`:
> `premouth` (session start) · `A_open` (shredded band removed, clean aperture) · `B_ready` ·
> `C_precut` · `D_chin` (full chin, mouth only a crease) · `G_twohalf` · `H_open` (two-grid lip +
> cavity, jaw still flat) · `I_pre_jaw` · `J_pre_despike` · **`K_jaw_done` (current)**.
>
> **⚠ NEVER REGENERATE TO FIX A DEFECT.** Operator: *"why is the model constantly remade and never
> evolving are you literally starting fresh every fucking time?"* Every regeneration from the
> scaffold discarded every fix made since, which is why nothing accumulated for days.
> `tools/fix_defects.py` and the live session only ever edit what exists.

>
> **Project:** `<repo>/` — the clean rebuild. Started 2026-08-04.
> The old project `<repo>/archive/Clyffy_Avatar/` is **DEAD** and may be deleted by the
> operator. Do not resume work there, do not copy code from it without re-reading it.
>
> **⚠ 2026-08-05, CORRECTED THE SAME DAY. THE BACK OF v2 IS MALFORMED — IT IS NOT MISSING.**
>
> The operator was right that the back of `mesh/_dead/clyffy_v2.fbx` is wrong: it is a broad
> scooped basin with a curled overlapping flap across it, where a skull should be a smooth dome.
> Compare `work/BACKCMP/clyffy_v2_270.png` with `work/BACKCMP/clyffy_open_v1_180.png`. The face at
> 090 is clean and correct (`work/RECHECK_v2/clyffy_v2_clay_090.png`).
>
> **My measurement of it was wrong and was published as fact. Retracted:** "a third of the back
> modelled as a pit, 29.8% past 0.10 inset, max **0.3018**". The old `crater_probe.py` measured
> along a ray against the convex hull of a head that has HORNS AND EARS; the hull bridges the
> ear-to-skull gap, so grazing rays reported a pit that is not there. Direct measurement:
>
> | measure | v2 rear | v2 front (control) |
> |---|---|---|
> | see-through rays hitting an inward face | **0 of 8002** — no hole anywhere | — |
> | perpendicular hull inset, MAX | 0.0785 | 0.0787 |
> | relief vs smoothed self, MIN | -0.0143 | -0.0217 |
>
> By every number the back is no worse than the face. **Only the render shows it.** That is the
> finding: this defect is not reachable by the metrics we had, so a clay render at 240/270/300 is
> part of accepting any base, not an optional extra.
>
> `tools/crater_probe.py` has been rewritten — see-through + perpendicular inset + relief, with the
> front as the control. It no longer measures along a ray against a hull.
>
> **What that changes:** v2 is a CLOSED, 99.7%-quad mesh of the APPROVED character with a clean
> face, and a malformed back skull that is a smooth featureless region — the easiest kind of area
> to repair. It was quarantined on a finding four times too large. The v2 mouth chain (seam, split,
> cavity, parts, weights, jaw hinge) was never touched by the back defect and may still be valid.
> **Whether to repair v2's back or take a new base is the operator's open decision.**
>
> `mesh/_dead/clyffy_open_v1.glb` has a genuinely clean back dome, but is a different character
> with zero quads — the two problems already recorded below.
>
> Cleared 2026-08-05: all of `mesh/` moved to `mesh/_dead/` (moved, not deleted).
>
> **▶ DECIDED 2026-08-05 (supersedes the regenerate decision of the same day) — RETOPO OVER THE
> SCAFFOLD.** Operator's call after the controlled re-mesh experiments settled the cause chain:
>
> * Tripo H3.1, same v2 plates, second roll → back malformed AGAIN at the patch boundary
>   (`work/remesh/candidate_clay_270.png`). Two rolls, one location: **Tripo embosses patch albedo
>   as depth. Systematic, not a dice roll.**
> * Flattened-albedo plates through Tripo → WORSE (broken floating crown curl). Remedy rejected.
> * **Meshy, same original plates → the approved character with a CLEAN back dome**
>   (`work/remesh/meshy_clay_000.png`, `_180.png`). Meshy is albedo-robust.
> * Meshy's `topology: "quad"` promise broke a 2nd and 3rd time (the dedicated `meshy_v5_remesh`
>   also returned 100% triangles). **Meshy quads are not real; stop asking.**
>
> **The base is built by hand-retopo in Blender over `work/remesh/meshy.glb` (the SCAFFOLD — right
> shape, clean back, wrong topology).** Studio pipeline: scaffold supplies shape via shrinkwrap,
> we supply topology — lip loops around an OPEN mouth, eye rings, teeth/tongue as separate objects
> from the start, back correct because we made it. Rig order stands: mouth → eyes/eye region →
> ears → arms/hands. The open-mouth generation and the aperture-plate question are MOOT — the
> aperture is now modelled directly from `reference/approved/modelsheet_open.png`.
>
> **CP1 APPROVED (operator, 2026-08-05 evening): the primary loops stand.** The lip seam was the
> contested line — three scripted attempts at the corner hook, two caught wrong by the operator's
> eye — and is now **operator-approved**: 17 verts, midline z 0.726, dip z 0.709 at x 0.043,
> corner at **(x +0.085, z 0.728)**, following the crease valley including the upturn. The VIS
> tubes render his line, not a detection. The approved points are hardcoded in
> `tools/retopo_lips.py` (refresh from the file if he ever edits the seam in Blender).
>
> **CP2-4 BUILT (2026-08-05 night): the mouth region is 200 quads** — concentric loops around the
> approved seam, corner-converging, chin to just under the nostrils, midline welded, all
> shrinkwrapped. Renders: `work/retopo_cp2/`. **Rows past 0.11 were tried and ROLLED BACK** —
> mouth rings stop being mouth topology there (wavy nose edge, cheek sails); BUILD_LOG has the
> full negative result.
>
> **CP5 APPROVED (operator, 2026-08-06): the nose patch** (`tools/retopo_nose.py`) —
> geodesic-marched grid off the mouth patch's top boundary (1:1, no seam), 4 bands to z 0.823,
> nostrils as feature-sized 10-rim ring slits. The nostril is a ridged SLOT on the scaffold, not
> a dip: it needs the exclusion zone + `cp5_noshrink` group (see BUILD_LOG 2026-08-06, incl. the
> anchor-vert corruption that was caught and reverted). Renders: `work/retopo_cp5/`.
> **CP6 BUILT (2026-08-06), AWAITING OPERATOR REVIEW: eye annuli + bridge**
> (`tools/retopo_eyes.py`, `tools/retopo_bridge.py`) — the CP1 eye ring is the lid margin
> (aperture open for the eyeball object), two rings out, and the face is ONE surface chin-to-brow
> via a target-seeking march (continuation marching wraps the muzzle and never reaches the eyes —
> BUILD_LOG 2026-08-06 later). 364 faces: 352 quads, 12 tris (2 mouth-corner + 10 capture).
> Renders: `work/retopo_cp6/cp6b_*`. Eye-ring upper arcs open on purpose (brow/skull boundary).
> **CP7 IN PROGRESS (2026-08-06 night) — the head is built REGION BY REGION**
> (`tools/retopo_region.py`, one entry per region). **The single global sweep FAILED and must not
> be retried** — `tools/retopo_skull.py` is kept as the negative result; the face boundary is
> non-convex at the mouth corner, the ear exclusion zone blankets the side of the head, and
> horns/ears change the front's topology (BUILD_LOG 2026-08-06 night has the full autopsy).
> **BUILT: forehead · cheek · temple · jaw · BACK · NAPE · JAWLINE · THROAT — 922 faces
> (768q, 154t). THE HEAD SHELL IS CLOSED except the ear/horn opening (CP8) and the two
> intentional apertures (eye lid margin, nostril).**
> Renders: `work/retopo_{forehead,cheek,temple,jaw,back}/`, plus `work/solo_check/` (patch alone,
> the only way to see holes honestly). The face shell's outer boundary is ONE clean loop — a
> close-but-far scan found no cracks anywhere except the expected ear-base region.
>
> **The back is a clean dome** (`work/retopo_back/back_180.png`) — built OUTWARD FROM THE MIRROR
> PLANE off the sagittal guide, never backward from the face. See BUILD_LOG for why that ordering
> is load-bearing.
>
> **① the NAPE is BUILT (2026-08-06):** occiput edge → neck ring, 14 columns, 7 captures on the
> ring, 75 quads / 16 tris. `work/nape_check/solo_180.png` shows the back as a **clean smooth
> dome** with no scoop and no fold — the defect that started this whole rebuild is not present in
> the shell we made. Its lower edge is scalloped where columns captured the ring at different
> rows; CP9 re-anchors it, so leave it.
>
> **② the JAWLINE band and ③ the THROAT are BUILT (2026-08-06).** Both were found by LOOKING —
> `work/throat_check/under_{front,side}.png`, rendered from below, showed a diagonal band along
> the jaw and a V between the jaw patch's two legs. Neither is visible from any of the standard
> orbit angles. The jawline was zipped downward onto the jaw edge (`capture_boundary`); the throat
> marched back onto the neck ring. `tools/retopo_fill_gaps.py` then closed the two pinholes their
> corners left (7v at the temple, 10v by the mouth corner) with centroid fans — manifold by
> construction — while PROTECTING the eye and nostril apertures by centre.
>
> **CP8 (2026-08-07) — THE EAR IS BUILT.** `clyffy_ear_R`, **1482 quads, 0 tris**, Mirror(X),
> correct curled flap. Method: cut its 2876 faces out of the scaffold → **weld** (glTF splits
> verts at UV seams, so the cut is triangle soup until `remove_doubles`) → `holes_fill` the root
> → voxel remesh at 0.006. Quadriflow still refuses on manifold/normals even after an explicit
> recalc — not chased, the voxel output is already all-quads. The ear sits a hair INSIDE the
> scaffold silhouette (voxel shrinkage + cut margin); check against canon art before rigging.
> **THE HORN IS FIXED (2026-08-07): 180 faces (168 quads), reach 0.0539 of a true ~0.056, full
> curve.** Two guesses failed; INSTRUMENTING the walk band by band found it immediately — the axis
> had walked OUT of the horn (band 5 sat at radius 0.002, i.e. on the surface). Fixes: recentre on
> **opposite-ray-pair midpoints** not the hit centroid (a centroid is pulled toward the far side
> and toward skull hits at the root); **damp** the direction update (half old, half new); and
> **halve the step** to base_r*0.15, since at 0.30 the tip's cross-section was smaller than one
> step. **CP8 IS COMPLETE** — ear + horn, both Mirror(X), both separate objects.
>
> **Method worth reusing: when two guesses at a failure both miss, stop guessing and instrument.**
>
> **THE EYEBALLS ARE IN (2026-08-07)** — `tools/retopo_eyeball.py`, `clyffy_eye_R`, 384 faces
> (336 quads), Mirror(X) with **clipping OFF** (off-midline object; clipping would weld it to
> itself). Radius **0.0257** and its seat are SPHERE-FITTED to 598 scaffold samples inside the
> aperture (residual mean 0.0039), not chosen. The script's seating gate flags the cornea sitting
> ~0.010 proud of the lid margin — that is CORRECT for his big rounded eye; treat the gate as
> "go and look", and the look is `work/retopo_eye/eye_closeup.png`.
>
> **CP10 FIRST PASS (2026-08-07) — `tools/retopo_mouth_parts.py`.** Teeth as CONTINUOUS CREAM
> BANDS (`clyffy_teeth_upper`/`_lower`, 32 quads each) + `clyffy_tongue` (160 faces), built on the
> approved seam so parts and lips share one source of truth. **The inside-the-head gate caught 38
> verts poking through**; a **seat-inside pass** (push each offender back along the surface normal
> until it clears by 0.002) re-gated CLEAN. **Second pass fixed the shape** — bands run on a
> SMOOTHED seam copy, STOP SHORT of the corner (END 0.82) and taper in (`1-t³`), and seating +
> smoothing ALTERNATE because they fight each other (either alone undoes the other). 26 quads each,
> gating CLEAN. The midline chevron is faithful to the approved seam, not a defect. Still cannot be
> judged in an open pose until the seam is split at rig time.
>
> **THE HEAD AS A SET OF OBJECTS:** shell 922 faces · ear 1482q · horn 180 · eyeball 384 ·
> teeth 64 · tongue 160 — all mirrored where appropriate.
> **TRI CLEANUP DONE (2026-08-07):** `tools/retopo_cleanup.py` — **188 -> 102 tris, 879 quads,
> 89.6% quads.** GATED on the open boundary loops surviving identically ([82, 10, 10]), no ngons,
> no new non-manifold edges; **on rejection it does not save.** `join_triangles` never moves a
> vertex, so the silhouette is provably unchanged. At 60 degrees only 3% of tris paired (most sit
> in FANS, which always leave an odd one out); 100 degrees took it to 44%. The remaining 102 are
> unpairable — the honest floor for this topology.
>
> **NEXT, and both are multi-session — do NOT start either half-way:**
>
> **⚠ REFERENCE AUDIT 2026-08-07 — THE BODY HAS NO AUTHORITATIVE REFERENCE. Do not build
> shoulders/arms/hands off what is currently on disk.**
>
> `reference/approved/SPEC.md` states plainly that it is "the single authoritative visual reference
> for the avatar's **head**". It is head-only by design and is sound. **There is no approved body
> sheet at all.** The only full-body art is `sheets/turn_4k_apose.png`, and inspecting it (not
> trusting its filename) shows two disqualifying problems:
>
> 1. **It is NOT an A-pose.** The arms hang straight down at the sides. The file name says apose;
>    the image does not. This is the exact trap of [[find-the-authoritative-reference-first]] —
>    a derivative trusted by its label.
> 2. **It is OFF-MODEL against the approved head.** Smaller head relative to body, different muzzle,
>    hooved mitt hands, and a tail — none of which match `reference/approved/modelsheet_neutral.png`,
>    the sheet the whole retopo was measured from. The operator enlarged the head ON PURPOSE for the
>    face/mouth work; this sheet predates that.
>
> **Also stale:** SPEC.md points superseded art at `canon/_archive/`, a path that **does not exist in
> this project** (it is from the dead `Clyffy_Avatar/` tree).
>
> **What a strong result needs before the shoulders go in** — a body sheet held to the same standard
> the head sheets already meet: generated from the SAME reference element
> (`Clyffy-BROWN-avatar-target`, `1c6d9749-87fe-4cec-8e8e-77f33216d2b4`) so it is the same character
> and not a lookalike; a TRUE A-pose (arms ~45 deg from the torso, which is what makes the arm
> regions separable by construction); flat even studio light on plain grey; and a **true 90 deg side
> profile**, because SPEC's own rule 2 is that every proportion failure in this project was a
> profile problem. Hands must be legible even if they stay a placeholder object.
>
> **ATTEMPT 1 REJECTED (2026-08-07), and it changes the plan.** Two sheets generated from the
> approved element (`work/bodyref/REJECTED_*.png`), prompt stating the A-pose four separate ways
> including "clear open triangular gap of empty background between each arm and the side of the
> body". **Both came back with the arms hanging straight down — the identical defect as the sheet
> being replaced.** Also: the "3/4" panel is near-frontal and the "profile" panel is three-quarter
> back, so SPEC rule 2 (a TRUE 90 deg profile) is unmet too. Nothing was accepted; the files are
> renamed to REJECTED so they can never be mistaken for reference.
>
> **THE REAL FINDING — the A-pose is a SCAFFOLD problem, not a reference problem.** We retopo over
> `work/remesh/meshy.glb`, not over the art. An A-posed drawing cannot separate arm from torso in a
> mesh whose arms are already fused to the body. So there are only two real options: **(a)** re-mesh
> a NEW A-posed scaffold — which would invalidate the entire head already built on the current one,
> or **(b)** march the arms as their OWN regions off a shoulder ring on the current scaffold, where
> the separation exists by construction, and let the rig pose them. **(b) is the answer**, and it
> means the body sheet's job is PROPORTION and SILHOUETTE verification only — the A-pose was never
> the thing it had to deliver. Do not spend more generations chasing an A-pose in the art.
>
> **Order of operations — replacement FIRST, deletion after.** `turn_4k_apose.png` is currently the
> only body art in the repo; deleting it before a correct sheet exists would leave nothing to
> compare against. Archive it as mislabelled (and rename — the "apose" name is itself the defect),
> do not silently delete.
>
> **▶ BODY SPEC SETTLED 2026-08-07 (operator), after a correction of mine.**
>
> I reported the scaffold as wearing "a t-shirt with a drawstring collar" off a WORKBENCH clay
> render — `color_type='OBJECT'` paints everything one flat colour, so that was a read of
> SILHOUETTE ONLY and was wrong. Textured render (`tools/scaffold_texture.py`,
> `work/scaffold_texture/`) settles it: **a navy DevPulse tee with a blue LANYARD and an ID
> BADGE**, exactly matching `sheets/turn_4k_clean.png`. The "drawstring" is the lanyard cord and
> the "toggle" is the badge. It is deliberate product branding, not drift. The operator had already
> answered "get a lab-coat scaffold" on my bad description; re-asked with the correction.
> **Earned rule: a clay render is evidence about SHAPE and about nothing else. Never describe a
> material, a garment or a marking from one.**
>
> **Operator's rulings:**
> * **The DevPulse tee IS the body.** Retopo it as the canonical torso surface. No new scaffold.
> * **The lab coat is a LAYER** — modelled later as its own wearable object over the finished body,
>   which is how the approved head sheet's look gets reached without redoing anything.
> * **The tail is CANON.** Build it as its own object (thin protrusion — the ear's
>   isolate-and-remesh method, not a marched region).
> * My call, not asked: **lanyard + badge are separate PROPS.** Rigid objects must never live
>   inside a deforming quad shell — same argument as teeth, eyeballs, ears and horns.
>
> **MEASURED 2026-08-07 (`tools/body_survey.py`) — the arms DO separate on this scaffold.**
> Horizontal cross-sections, single-linkage clustered in XY: the section becomes **3 contours at
> z 0.368** and stays split down to z 0.267, where the arm tapers out into the hand. Torso alone is
> 0.368 wide there; the arm sits at x [0.203, 0.282] with a **real ~0.019 lateral gap**. This is the
> opposite of v2, where no gap existed at any height from 40% to 84% and which is why the A-pose
> was thought to be blocking. **It is not blocking: plan (b) — arms as their own marched regions —
> has a genuine gap to work in, and no A-posed art is needed to get it.** Legs separate at z 0.152.
> Scaffold is 1.000 tall; head is z 0.559-0.967, so this is a ~2.4-head chibi build.

> **▶ THE FLOW IS IN PLACE (2026-08-07) — `tools/retopo_gate.py`. A REGION IS NOT SAVED UNTIL IT
> PASSES.** PLAN (the region declares `expect`) -> PREFLIGHT (the front is checked before a face
> exists) -> BUILD -> GATE (non-manifold, ngons, zero-area, the eye/nostril apertures, mirror-plane
> leakage, off-scaffold flyers, longest new edge, declared bbox) -> LOOK (renders always, pass or
> fail) -> COMMIT only if preflight and gate both passed. On rejection the .blend on disk is
> untouched, so a bad region costs a rerun and nothing else. Every check is a defect that shipped
> once. Run a region: `blender -b --python tools/retopo_region.py -- work/RETOPO_clyffy.blend <name>`
>
> **Supporting tools:** `body_rings.py` (slice guide rings from the scaffold — a body is a tube and
> a cross-section IS the edge a region should stop on), `inspect_front.py` (print the front a region
> would march from, vert by vert, with gaps), `retopo_resample_edge.py` (split over-long boundary
> edges; splits only, never collapses, so no existing vert moves), `body_survey.py`
> (cross-sections + `--from/--to`), `scaffold_texture.py` (textured render — see the rule below).
>
> **① B1 THE NECK IS REBUILT AND GATED (2026-08-07): 247 quads / 52 tris, all 44 columns captured
> on `vis_ring_collar` at z 0.630, clean level stop, worst row gap 0.0410.** Renders
> `work/retopo_neck/`. It replaces the first attempt, whose lower edge wandered **0.1434 = eight
> march steps** because it marched a row count with no target.
>
> **The gate rejected it five times and the cause was never where I looked.** Two guesses at a long
> edge both missed and the second made it worse; instrumenting put the worst gap at ROW 0 — the
> EXISTING boundary. The neck ring's own spacing ran 0.0018 to 0.0915 (3.7x spread). **An uneven
> front cannot be tuned away downstream: row 1 inherits the worst gap and every row repeats it.**
> Resampled the front first (1.6x), then target-seeking with proportional assignment (CP6's fix,
> both halves) plus: **mirror-plane columns are not part of a proportional map** — they are pinned
> to x=0 and must collapse to the ring's midline endpoint.
>
> **⚠ EARNED THE HARD WAY: a clay render is evidence about SHAPE and about NOTHING ELSE.** Workbench
> with `color_type='OBJECT'` paints every object one flat colour. I described the scaffold's garment
> from one and got it wrong, and the operator made a costume decision on that description before I
> caught it. Render textured (`tools/scaffold_texture.py`) before saying anything about a material,
> a garment or a marking.
>
> **② B2 SHOULDERS + B3 CHEST ARE BUILT AND GATED (2026-08-07).** B2 shoulder yoke **383q/6t
> (98.5% quads), passed first run**; B3 chest **231q/5t**. The shell now runs crown to **z 0.410**,
> 1958 faces, 3 boundary components. Renders `work/retopo_{shoulders,chest}/`, `work/body_survey/`.
> B2 WRAPS THE ARMS on purpose — above the armpit every section is one contour and the deltoid is
> part of the shoulder mass.
>
> **⚠ MEASUREMENT CORRECTED: the arms come free at z 0.400, not 0.368.** The 0.368 figure came from
> single-linkage clustering, which merges surfaces across a gap narrower than its 0.020 threshold.
> Exact face-topology chaining (`body_rings.py --scan`) shows one loop down to z 0.480 and real arm
> loops (145/142 pts) from z 0.400. **Loop count is the split test; a distance threshold is not.**
>
> **The ring guides were wrong four different ways and each cost a region rejection** — angular
> ordering (assumes star-shaped, scrambled once arms are in the slice), greedy nearest-neighbour
> (shortcuts a notch, silently dropped the arm lobe), exact chaining without welding (the scaffold
> is glTF and splits verts at UV seams — 264 fragments, the CP8 ear property again), and a guide
> point at x -0.001 leaking past the mirror plane. All fixed in `tools/body_rings.py`.
>
> **③ THE ARMPIT IS SPLIT, B4 TORSO + B5 HIP ARE BUILT AND GATED (2026-08-07).**
> `tools/armpit_split.py` cuts the z-0.410 boundary into a torso arc and an arm arc by MEASUREMENT
> — drop each boundary vert to z 0.400 and ask which scaffold contour it is nearer. Decisive (arm
> verts 0.001-0.008 from the arm, 0.03-0.11 from the torso) and it flips exactly twice, at the two
> armpit points, which are only 0.028 apart. The fronts SHARE the verts either side of each flip so
> the tubes stay stitched and the armpit is a CREASE, not a hole. Tagged as `cp9_torso_front` and
> `cp9_arm_front`.
> **B4 torso 184q/2t · B5 hip 190q/3t.** Shell **2337 faces, 2179 quads (93.2%)**, reaching z 0.200.
> Four boundary components: 149v head-to-hip, **15v arm socket at z 0.410 held open**, 2 apertures.
>
> **The TAIL required an exclusion zone** — from z 0.245 down it is its own contour while the torso
> back recedes to y 0.101, so nearest-surface at the back midline returns the TAIL and the shell
> climbed onto it. Same shape as the CP5 nostril slot, same remedy (`exclude` in the region config).
>
> **New region mechanisms:** `pick_group` (march from an arc tagged by measurement — the armpit
> cannot be written as a coordinate predicate), `join_chains` (the torso front is two arcs with the
> arm between them; taking the longest would build half a torso), `exclude`, `capture_r`,
> `seek_target`. Captures are now PINNED against the relax, and columns landing on the same ring
> point WELD instead of stacking (that was 10 zero-area faces the relax had been hiding).
>
> **④ B6 THE ARM IS BUILT AND GATED (2026-08-07): 114q/4t, all 15 columns captured on a closed
> wrist ring at z 0.300.** Shell **2455 faces, 2293 quads (93.4%)**. The wrist ring is held open for
> the hand (separate object). **CYCLIC fronts** added — an arm is a tube, and closing the front also
> covers the 0.028 armpit bridge the chest march went around. Closed **arm rings** added
> (`kind="arm"`), and `tools/scaffold_section.py` extracted so the ring builder and the split tool
> cannot disagree about what the contours are.
>
> **TRIED AND REVERTED — snapping the arm to an isolated limb.** `tools/isolate_limb.py` is KEPT
> (it works, and the tail will need it). The reasoning was right — the arm is a protrusion, so
> nearest-surface finds the torso — but isolating puts a CUT EDGE exactly where the inner columns
> must travel and they stalled on it (13/15, worst gap 0.0905, worse than doing nothing).
> **Isolation works for a protrusion you rebuild whole (the ear); not for one you march ACROSS the
> join.** An armpit exclusion zone was also tried and removed — identical geometry, and it left its
> own verts 0.0151 off the surface.
>
> **⚠ THE LONG-EDGE GATE WAS MIS-SCALED.** It was `3 x step`. Step bounds how far a column moves per
> ROW; the FRONT SPACING bounds how far apart columns legitimately sit. Where step < spacing the
> limit measures the wrong thing — on the arm "3 steps" (0.036) was narrower than two normal columns
> (spacing 0.021) and flagged an ordinary transition quad. Now
> `max(3 x step, 2.5 x front spacing)`, printing both. Every earlier region still passes on the
> stricter bound (neck 0.041, shoulders 0.029, torso 0.032, hip 0.032) — this loosened nothing that
> had been holding.
>
> **Legs split at z 0.160, not 0.152** — exact chaining again, clustering wrong again.
>
> **⑤ THE BODY SHELL IS COMPLETE CROWN TO ANKLE (2026-08-07).** thigh 83q/9t · leg upper 131q/9t ·
> leg lower 64q/0t. **2751 faces, 2571 quads (93.5%).** Renders `work/body_survey/`.
> `tools/limb_split.py` now handles both seams (it replaces `armpit_split.py`).
>
> **⚠ LOOP SELECTION MUST BE BY POSITION, NEVER BY EXTENT OR SIZE.** Below z 0.085 the TAIL TUFT
> reaches further out in x than the leg (0.171 vs 0.129), so ranking by max x hands back the tail
> when you asked for a leg. And stripping "the largest loop, because that is the torso" is wrong
> below the crotch where there IS no torso — it stripped the right leg and returned the LEFT one
> (centroid -0.102 for a ring asked at +0.100). Both caught only because the tool prints the
> centroid it CHOSE beside the one it was asked for. **Print what you selected, not just what you
> found.**
>
> **⚠ THE CROTCH IS A SADDLE; THE ARMPIT IS A SLOT.** Three discriminators failed on it — the RIVAL
> test (meaningless at the midline: a crotch vert at x 0.02 is still nearer the right leg than the
> left), POINT-IN-POLYGON (the leg at z 0.152 is narrower than the thigh at 0.170, so nothing sits
> over it), and a GAP test with a statistical guard (the body side is a RAMP, so no honest jump is a
> quarter of the spread). **The guard that means something is topological: the labels must form
> exactly ONE limb run.** Same final structure as the armpit, reached by a different route.
>
> **The cyclic wrap closes only where the cycle has actually closed** — on the arm that face is the
> 0.028 armpit bridge; on the leg the same closure spans the 0.137 CROTCH and tented straight
> across the thighs (a 0.0639 edge).
>
> **5 boundary components:** 145v mirror plane + THE OPEN CROTCH, 16v ankle ring, 15v wrist ring,
> and the two head apertures. The armpit closed itself.
>
> **NEXT:** the crotch wedge fill (the one real hole left), hooves off the ankle ring, hands off the
> wrist ring (separate object, placeholder fine), tail (separate — `isolate_limb.py` is the tool and
> this is the case it suits), lanyard + badge as props, then the lab coat as its own layer. After
> that the RIG, where the lip seam finally splits.
>
> **Superseded:** legs (hip z 0.200 -> the crotch pinch at 0.160 -> feet; the crotch is a midline
> convergence, the mirror-plane twin of the armpit), the armpit wedge fill, hands (separate object
> off the wrist ring), tail (separate — use `isolate_limb.py`, this is the case it suits), lanyard +
> badge (separate props), then the lab coat as its own wearable layer.
>
> **Superseded:** legs (hip ring z 0.200 -> the split at 0.152 -> feet), the ARM off `cp9_arm_front`
> (z 0.410 -> a wrist ring), the armpit wedge fill, then hands (separate object), tail (separate,
> ear's isolate-and-remesh), lanyard + badge (separate props), and the lab coat as its own layer.
>
> **Superseded plan text below — THE ARMPIT SEAM:** The shell's lower boundary at z 0.410 is ONE
> loop wrapping torso and both arms. Below z 0.400 the surface is THREE loops. A marching front
> cannot split, so that boundary has to be cut at the two armpit points (per side) into a torso arc
> and an arm arc, after which: torso arc -> waist ring (z 0.300) -> hip (z 0.200) -> legs; arm arc
> -> a wrist ring. Then hands (separate object), tail (separate, ear method), lanyard + badge
> (separate props), and the lab coat as its own wearable layer.
>
> **Superseded plan text below** — B2 shoulders/upper chest: collar ring -> `vis_ring_chest` (z 0.500). **Note
> the armpit problem, already measured: above z 0.368 every horizontal slice wraps torso AND arms as
> one contour, so there is no torso-only ring across the shoulder.** The arm needs a ring declared
> around the ARM (not horizontal), and B2 must stop against it rather than run into it. Then B3 arm
> socket ring -> B4 arm (socket -> wrist) -> B5 torso (chest -> waist -> hip) -> B6 legs -> B7 hands
> (separate object, placeholder fine) -> B8 tail (separate, ear's isolate-and-remesh method) ->
> B9 lanyard + badge (separate props) -> the lab coat as its own wearable layer.
>
> **Backup:** `work/RETOPO_clyffy.prehotfix.blend` is the state before the boundary resample.

> **① THE BODY — STARTED 2026-08-07. The NECK region is BUILT** (`retopo_region.py` entry `neck`):
> 41 columns off the collar, 7 rows, decimating to 29; **219 quads, 12 tris. Model 1212 faces
> (1098 quads, 114 tris), head+neck one continuous shell.** Renders `work/retopo_neck/`. It has no
> capture target on purpose — nothing exists below it yet, so it is bounded by row count and must
> be REVIEWED before the shoulders anchor to it. Remaining order below. Build it
> the way the head was built and for the same reason — bounded regions marched off an existing
> edge, never one global sweep (`tools/retopo_skull.py` is the tombstone for that idea). The
> starting edge already exists: the **neck ring**, which the nape and throat regions both captured
> onto. Suggested region order: neck -> shoulders/upper chest -> back -> arms (down to a wrist
> ring) -> hands as a SEPARATE object (operator: placeholder is fine) -> torso -> legs. **The
> A-pose problem is inherited and still unsolved** — measured on v2: no lateral gap between arm and
> torso at any height from 40% to 84%, so arm verts cannot be separated geometrically. Retopo
> changes this: if the arm is marched as its OWN region off a shoulder ring, the separation is
> built in by construction rather than recovered afterwards. That is the argument for doing the
> arms as distinct regions early, not late.
>
> **② THE RIG.** Only after the body. This is where the lip seam finally SPLITS and the mouth
> opens on geometry we made. The v2 rig parameters are recorded above and are still the best
> starting estimates (jaw hinge fwd −0.020 at 81.5% of body height; weights Laplacian-diffused
> over TOPOLOGY with a ceiling at `seam_z + 0.004` — that ceiling is load-bearing). They must be
> RE-DERIVED on this mesh, not copied: they were measured on the caved-in base. Phase M6 stands —
> a scripted talking demo, "not straight robotic" — and it is the first moment the teeth, tongue
> and lip loops can be judged in motion rather than at rest.
>
> **Superseded detail from the 2026-08-06 attempt — `tools/retopo_protrusions.py`.** Ear and horn are SEPARATE OBJECTS
> (`clyffy_horn_R`, `clyffy_ear_R`), Mirror(X) on, so ear motion stays riggable and the skull
> underneath stays continuous. **Shrinkwrap is unusable on a protrusion** — nearest-surface from an
> ear vert finds the SKULL. **The horn WORKS** (ray-cast cross-sections along a recentred medial
> axis; 120 faces) **but is too SHORT** — its length came from a percentile inside a straight
> cylinder and a curving horn puts its tip outside that cylinder; walk until the rays stop hitting
> instead. **The EAR FAILED three ways** (swept tube → cone; binned cross-sections → cone;
> mid-surface sheet → 21 scattered quads). BUILD_LOG has the measured cause of each — the ear is a
> thin CURLED flap, and the scaffold's glTF vertex splitting makes flood-fill selection useless
> (4 verts). **Recommended, not yet tried: isolate the ear's scaffold faces and quad-remesh them**,
> the same scaffold-plus-topology argument the whole lane rests on.
>
> **▶ THE HEAD SHELL IS SEALED (2026-08-07, `tools/retopo_seal.py`) — VERIFIED, NOT ASSERTED.**
> **1024 faces (836 quads 81.6%, 188 tris, 0 ngons), 0 non-manifold edges.** Exactly THREE boundary
> cycles, every vert accounted for: **82v = 47 mirror-plane + 35 neck-ring** · **10v eye aperture**
> · **10v nostril**. A hole would have to be a fourth cycle; there is none. Renders:
> `work/retopo_seal/` (`solo_*` = shell alone).
> **The shell is sealed straight ACROSS the ear and horn bases — no ring holes** (watertight is
> better for rigging and the 2D port; CP8 is purely additive). The scaffold's ear/horn therefore
> poke THROUGH the shell in renders — expected, not a defect.
> The seal's "is this opening intended?" test was wrong twice in opposite directions (it once
> CAPPED THE NECK AND MIRROR PLANE) — see BUILD_LOG 2026-08-07; the correct test is a MAJORITY of
> the cycle on those two lines.
>
> **STILL OPEN, in build order:** ① **the HORN is too SHORT** (reach 0.0390 vs ~0.056; two causes
> tested and ruled out — instrument which break fires before touching it) · ② the ear sits a hair
> INSIDE the scaffold silhouette (voxel shrinkage + cut margin) — check against canon art before
> rigging · ③ tri-reduction pass before subdivision (81.6% quads; tris cluster at the region
> seams) · ④ CP9 body. Also still open: the soft midline tent from the glabella to the crown, and
> three chin verts sitting ~0.004 past the mirror plane (clip leakage inside the approved mouth
> patch — clean before rigging).
>
> **Earned rule (2026-08-06): give each region its march direction EXPLICITLY (`seek_dir`).**
> "Away from the patch interior" only holds on a front-facing edge; on a strip's SIDE edge the
> interior is below, so "away" points up — the first cheek run marched over both eyes and buried
> the apertures.
> **Then CP8:** ear + horn base holes and their tubes as SEPARATE objects (like teeth, tongue,
> eyeballs — that is what makes ear motion riggable). Then the body.
>
> **Earned rule (2026-08-06): row smoothing on a marching front must be GENTLE and hold its ends.**
> A full umbrella pass shrinks an open front toward its chord every row — it strangled the
> forehead from 11 columns to 1. One pass, weight 0.3, interior columns only.
>
> **Workspace: `work/RETOPO_clyffy.blend`** (`tools/retopo_setup.py`) — scaffold select-locked,
> approved sheets as image empties, `retopo_head` pre-stacked with Mirror(X, clipped) +
> Shrinkwrap(scaffold), face snapping on. Operator reviews at each checkpoint: head block-out →
> face loops → mouth interior → body.
>
> **Previous state (now VOID — kept because the parameters are still correct, the base is not):**
> the mouth was BUILT and RIGGED — seam, split, cavity, teeth, tongue, jaw hinge. Gated invisible
> at rest from every direction; opens with no see-through.
>
> **`mesh/` IS EMPTY — every model was quarantined to `mesh/_dead/` on 2026-08-05** (operator's
> call: moved, not deleted). Read `mesh/_dead/README.md` before touching any of it. The paths in
> the table below are the ORIGINAL ones and all now live under `mesh/_dead/`.
>
> | what | where (now under `mesh/_dead/`) |
> |---|---|
> | ~~working mesh~~ VOID | `clyffy_v2_rig.blend` — jaw + skull bones, weights, 46,810 verts |
> | sealed, unrigged | `clyffy_v2_sealed.blend` — holes closed, debris removed |
> | parts, unsealed | `clyffy_v2_parts.blend` — 46,830 verts / 46,936 faces |
> | cavity, no parts | `clyffy_v2_cavity.blend` — 46,416 verts / 46,514 faces |
> | split, no cavity | `clyffy_v2_split.blend` — 46,095 verts, TRIM=2 at the corners |
> | seam baked, unsplit | `clyffy_v2_seam.blend` — group `op_lip_seam` + order attr `op_lip_seam_i` |
> | pre-seam base | `clyffy_v2_clean.blend` — 46,056 verts / 46,114 faces, 99.7% quads |
> | **the defect** | `clyffy_v2.fbx` (Tripo H3.1) — back third is a crater |
> | reference sheet | `sheets/turn4_a.png` — the 4-view front/left/back/right turnaround |
> | mesh input plates | `sheets/u_0{1,2,3,4}_*.png` — uniform 1835×2389 canvas |
> | approved art | `reference/approved/` — operator signed these off 2026-08-03 |
> | rules + pipeline | `docs/PLAN.md` |
> | history | `BUILD_LOG.md`, newest entry first |
>
> **✅ ANSWERED 2026-08-05 — the open-mouth mesh has a REAL CHAMBER.** Meshy job `fc862377`
> → `mesh/_dead/clyffy_open_v1.glb` → `mesh/_dead/clyffy_open_clean.blend` (59,723 verts / 119,444 faces).
> Sectioned before anything was built on it. Cavity is **0.19-0.30 deep in a 0.678 head**, with a
> solid throat wall behind it and an aperture 0.085 tall. The scripted carve could never exceed
> 0.100. Sections: `work/open_cut/cut_{head,mouth,top}_00.png`.
>
> **NEXT ACTION — OPERATOR DECISION, do not build past it.** Two problems with the new mesh:
>
> 1. **It is a DIFFERENT CHARACTER**, not the approved v2 base with a mouth added — longer,
>    heavier muzzle, different profile. See `work/REVIEW_base.png`. v2 was signed off 2026-08-03.
> 2. **119,444 triangles, zero quads**, despite `topology: "quad"` in the request. v2 was 99.7%
>    quads. Affects lip loop work and the 2D vector port.
>
> Until that is settled, the base is unchosen. The downstream chain (seam, split, rig, weights,
> gates, sections) is written and verified and applies to whichever base wins.
>
> **⚠ THE PREVIOUS MOUTH IS REJECTED.** It has no usable open pose: the cavity stretches into a
> membrane and the tongue and lower teeth swing out of the head. Phases 3-5 are to be rebuilt.
> Phases 0-2 (gate, seam, split) stand.
>
> **⚠ RESEARCHED 2026-08-05:** carving a cavity into a closed generated mesh is a RESEARCH
> problem (OmniFaceRig, arXiv 2606.08043, no code released). Auto-Rig Pro and Faceit both
> REQUIRE existing mouth geometry. Blender Studio models the interior during character creation
> with teeth/tongue as separate objects. Do not attempt the scripted carve again.
>
> Phases 0-5 are BUILT and gated. Seam approved by the operator 2026-08-04.
>
> **Jaw rig (do not re-derive):** hinge fwd -0.020 at 81.5% of body height, from the ear base
> (fwd -0.048, 86.5%). Weights are a Laplacian diffused over TOPOLOGY — the rims are coincident,
> so no positional falloff can separate them — with a **ceiling at `seam_z + 0.004`**. That
> ceiling is load-bearing: without it the field flows AROUND the welded corners into the upper
> lip and drags the muzzle pad, while every gate still reads green.
>
> **Parts parameters (baked, do not re-derive):** `mouth_cavity.py` writes `mouth_throat`,
> `mouth_depth`, `mouth_pitch`, `mouth_seam_z` and the `op_rim_upper` / `op_rim_lower` groups
> onto the object; `mouth_parts.py` reads them. Rig groups already exist: `op_teeth_upper`,
> `op_teeth_lower`, `op_tongue`.
>
> **Cavity build parameters (do not re-derive):** `mouth_cavity.py ... 90 0.100 50 1.0 1.0 0.0`
> — depth 0.100 at pitch **+50 deg**, on a split made with **TRIM=2**. Depth is limited by the
> muzzle, not the skull: straight back there is only 0.0736 before a surface, because the
> muzzle is its own lobe and behind it at the lip's height is open air under the jaw. Pitching
> up into the muzzle mass buys the depth; past +50 it breaks out through the top.
> **TRIM=2 is load-bearing** — the cavity cannot reach the extreme mouth corner without grazing
> out through the skin it is touching. It took the leak from 44 px to zero.
>
> **⚠ CORRECTED:** the mouth crease is **SOFT, ~12 deg** — at 25 deg it fragments and the
> biggest muzzle crease is the **pad outline** (343v, wraps to the sides, invisible from the
> front). Separate them by **forward reach**: mouth +0.2253, pad outline +0.1506. Width alone
> cannot — 0.1969 vs 0.1923.
>
> **Established by the survey (do not re-derive):** forward is **+X / 090 deg**, taken from the
> fixed-angle orbit — the geometric derivation returns 192.93 deg, an ear tip, 103 deg wrong.
> Object transform is identity. The lip **is** a continuous crease in the geometry at **71.9% of
> body height** (z = +0.213), agreed by two independent rulers. The muzzle is a clean quad grid.
> The crease band branches where it meets the pad edges, so it must be resolved to a single
> chain before it can be used as a cut path.
>
> **Also open, not blocking the mouth:**
> * A-pose — DEFERRED to the rigging phase on purpose. Measured: no lateral gap between arm and
>   torso at any height from 40% to 84%, so arm verts cannot be separated geometrically.
> * 3 boundary edges + 1 non-manifold edge remain, all at x~0.120 y~0.026 z~0.323. `cleanup.py`
>   called them "a horn tip" — WRONG, that is where the two debris shells (12 and 9 verts) sit,
>   buried near the right eye. Invisible from outside; flagged, not removed, operator's call.
> * Holstein black/white variant — operator: brown/white FIRST, Holstein after it is captured.

---

## Non-negotiables earned the hard way

These cost real time in the previous project. Each one is a rule because it was violated first.

**Never label evidence with a detector.** I wrote an auto-facing detector to name render views; it
returned 158° in one tool and 36° in another from marginally different head bands, labelled a
three-quarter FRONT view as "head_back", and I reported its labels to the operator as fact —
telling him the back of the head was fine while it had **three horns** on it. He caught it by
noticing two images that could not both be true. Use `tools/head_orbit.py`: 12 fixed 30° views plus
a top-down. Nothing can be mislabelled and the top-down makes horn count unambiguous.

**Measure both sides of a comparison through ONE function.** Six separate measurements in the old
project were wrong because the two sides used different definitions — a lab coat on one side and
not the other, different cut heights, different lighting.

**Flat light for anything measured.** Under a key light a pink muzzle measured *brighter than white
fur* — impossible, and it nearly shipped as a real number. `canon/reference` is flat-lit precisely
so this cannot happen to it.

**Overlapping faces are worse than small holes.** Chasing "zero holes" with n-gon fills and
`triangle_fill` took non-manifold edges from 1 to 8 and 1 to 5. A centroid fan is manifold by
construction. Gate on invariants, not on a number that can be gamed.

**A gate that has never failed is not a gate.** Prove a new gate catches the defect it targets.

**CLOSED IS NOT THE SAME AS CORRECT — and NO NUMBER WE HAVE CATCHES A MALFORMED BACK.** The base
approved 2026-08-03 has a scooped, folded back skull. It passes every hole gate (it is closed), and
it also passes inset, relief and see-through — its back scores no worse than its own face. The only
instrument that shows it is a **lit clay render from behind**, at 240/270/300. Accepting a base
means looking at those three images, every time. Numbers rule things out; they did not rule this in.

**NEVER MEASURE ALONG A RAY AGAINST A CONVEX HULL on a head with horns and ears.** The hull bridges
the ear-to-skull gap; grazing rays through the bridge report a pit that does not exist. That is how
"29.8% of the back is a crater, max 0.3018" was published as fact on 2026-08-05 when the true worst
case is 0.0785 and there is no hole at all. `tools/crater_probe.py` was rewritten to use
perpendicular per-vertex distance, see-through ray parity, and relief against a smoothed self —
each with the FRONT of the same head as the control, because a face has real recesses and the back
should not have more of them than the face does.

**Judge SHAPE on lit clay — never on paint, never on a silhouette.** Two renders in a row hid this:
a DECIDE sheet on a pure WHITE world, which dropped Clyffy's white muzzle and jaw into the
background and made a sound model look holed; and a "clay" pass with NO LAMPS, in which a dent and a
dome are the same pixel. Use `tools/paint_views.py --clay` (WORKBENCH, `show_cavity` + curvature) on
a mid-grey field.

**Tripo multiview order is front / left / back / right**, front mandatory and first. Feeding it
front/¾/side/back is what produced three horns — it fused features at angles they don't belong to.
Plates must also share ONE canvas, scale and ground line; a 28% canvas spread breaks fusion.

**Operator confirms functionality.** Never claim success. Show a render, state what is unverified.

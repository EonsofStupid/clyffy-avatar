# The rig — plan

Written 2026-08-05 on the operator's direction: *"lets take this opportunity to really do it right.
Because eyes and around the eyes and then ears, and then arms and hands for basic motion and
movement."* It supersedes `MOUTH_PLAN.md` as the forward plan; that document stays because its
Phase 0-2 findings (the gate, the seam pick, split-don't-delete) are correct and carry over.

> **⚠ PHASE G BELOW IS SUPERSEDED (same day, operator's call): the base is NOT regenerated — it
> is HAND-RETOPOLOGIZED over the Meshy scaffold.** The regenerate plan died on evidence: Tripo
> embosses the patch albedo as depth on every roll (two rolls, one location), the flattened-plate
> remedy failed, and Meshy holds the character and the back but cannot deliver quads (three
> strikes, including its dedicated remesh model). Phase G's text is kept because its analysis
> (plates, aperture, acceptance battery) documents WHY the lane changed. The live plan is
> **Phase R** below; Phases M/E/R/A stand unchanged on top of it.

The order is the operator's, and it is not arbitrary — each stage lands on geometry the previous
one already proved: **mouth → eyes and the eye region → ears → arms and hands.**

---

## Phase R — the base, by retopo (LIVE — replaces Phase G)

**The scaffold:** `work/remesh/meshy.glb` — Meshy, from the approved v2 plates: the approved
character with a verified-clean back dome. Wrong topology (119,525 tris), which no longer matters:
it supplies SHAPE only, via shrinkwrap. We supply topology.

**Workspace:** `work/RETOPO_clyffy.blend` (`tools/retopo_setup.py`) — scaffold select-locked,
approved sheets as image empties, `retopo_head` with Mirror(X, clip) + Shrinkwrap, face snapping
on. The operator edits directly in this file; his edits are read out of the mesh, never
re-detected past his sign-off.

**Checkpoints, operator-reviewed on renders each time:**

| CP | what | state 2026-08-05 |
|---|---|---|
| CP1 | primary loops: eye rings, muzzle ring, **lip seam**, chin arc, ear/horn bases, neck, sagittal profile | ✅ APPROVED — seam is the operator's line, corner at (0.085, z 0.728), spec hardcoded in `tools/retopo_lips.py` |
| CP2-4 | mouth grid: concentric corner-converging loops off the seam | ✅ BUILT — 200 quads + 2 corner tris, chin to under-nostrils, renders in `work/retopo_cp2/` |
| CP5 | **nose patch** — its own constructed grid anchored on nostril rings + muzzle ring + eye rings. NOT extended mouth rings (tried, rolled back: wavy nose edge, cheek sails past 0.11). Nostril insert (2x2 block → 8-rim ring) proven, gated behind `BUILD_NOSTRIL` | ◻ next |
| CP6 | eye region: sockets as rimmed holes, lid loops, brow, under-eye mass — feeds Phase E | ◻ |
| CP7 | ears + horns: base rings to skull grid, ear shells | ◻ |
| CP8 | skull + back dome, jaw/cheek closure — the back is right because WE build it | ◻ |
| CP9 | body: neck ring down, torso/shirt, limbs (A-pose problem inherited; hands = placeholder per operator) | ◻ |
| CP10 | mouth interior: bag behind the seam, teeth as continuous cream bands, tongue — SEPARATE objects from day one | ◻ |

**Earned rules of this lane (each violated first, once):**
* a scripted detector gets two failures on a feature, then the operator's hand takes over —
  his one stroke ends what three algorithms couldn't (the seam corner)
* per-vertex frames wobble on a scan surface: smooth binormals along the path, smooth rows after
  offsetting, or the outer rows sawtooth
* mouth rings CONVERGE at the corner; held at full width they sail off the muzzle
* every offset parameterization has a useful radius; past it, build from the region's own
  landmarks instead of pushing
* renders are READ before they are sent; a caption is a claim
* Blender operator-loop: guide objects `hide_select` + hidden, target object pre-active,
  left-click commits / right-click cancels, and a no-op save is detected by diffing the mesh

---

## The decision this plan rests on

There is no usable base on disk. Both candidates fail, in different places:

| | `clyffy_v2.fbx` | `clyffy_open_v1.glb` |
|---|---|---|
| character | **the approved one** (2026-08-03) | wrong — longer, heavier muzzle |
| topology | **99.7% quads** | 0% quads, 119,444 tris |
| back of skull | **ruined** — scooped basin, curled flap | clean smooth dome |
| mouth | closed; the carve was tried and rejected | **real chamber**, 0.19-0.30 deep, solid throat wall |

Operator's call, 2026-08-05: **regenerate.** Take the approved character, generate it with the
mouth already open, in quads. Both halves are separately proven — `v2` proves the element token
holds the character, `open_v1` proves the generator builds a genuine interior when the source
plates show one. Nothing here is a compromise; the risk is entirely in the plates.

**Why the mouth must come from generation and not from a carve.** The v2 mouth was carved into a
closed head across five phases and the operator rejected the result: the cavity stretched into a
membrane and the tongue and lower teeth swung out through the jaw. `STATUS.md` records the research
position — Auto-Rig Pro and Faceit both *require* existing mouth geometry, and Blender Studio models
the interior at character-creation time with teeth and tongue as separate objects. We are not
attempting the scripted carve again.

---

## Phase G — the base (SUPERSEDED by Phase R above — kept as the record of why)

### G1. Plates

The single known cause of the `open_v1` character drift is visible in
`sheets/open/plates/SHEET.png`: the mouth is a **full yawn**. That changes the muzzle silhouette in
every one of the four views, and multi-view fusion has no way to know the difference between "this
character's muzzle is that shape" and "this character's jaw is currently down". It fused the yawn
into the resting form.

So the aperture is a **moderate drop — open enough that the interior, tongue and both tooth bands
are unambiguously visible, small enough that the muzzle silhouette still matches
`modelsheet_neutral.png` in profile.** That is a character decision about how the face is built,
and it goes to the operator as candidate plates before anything is meshed.

Bound by the rules already earned:

* generated from element **`Clyffy-BROWN-avatar-target`** (`1c6d9749-87fe-4cec-8e8e-77f33216d2b4`,
  verified live 2026-08-05) — an element, not a text prompt, because that is what keeps it the same
  character instead of a lookalike
* order **front / left / back / right**, front first and mandatory. Feeding front/¾/side/back is
  what produced a three-horned head
* **one canvas, one scale, one ground line**, cut by `tools/cut_plates.py`, long edge 2048
* **bare of props** — no lab coat, no goggles, no lanyard, no badge. Wardrobe law: the recorded
  failure is *"the generator welded the t-shirt into the body because the source sheet had no
  separation."* The t-shirt is the one exception, it is the base garment
* flat even studio light, plain field, no rim light, no grade

**Gate:** the operator picks the aperture from candidate sheets. Nothing is meshed before he does.

### G2. Mesh — both meshers, same plates

Tripo and Meshy have each produced exactly one base here, from **different** plates, so mesher and
plates are confounded and neither result proves what it looks like it proves:

| | plates | character | quads | back | mouth |
|---|---|---|---|---|---|
| Tripo H3.1 | v2 closed-mouth | right | 99.7% | ruined | none |
| Meshy | open yawn | wrong | 0% | clean | real chamber |

Running both on the **same** new plates is what separates the two variables. Credits are not a
constraint. Meshy is asked for quads again and watched — it ignored `topology: "quad"` last time,
which is a recorded fact about the service, not a guess.

### G3. Acceptance — and this is where the last base got through

Every gate this project had said green on a head whose back was visibly ruined. So acceptance is
**an operator look first, numbers second**, and the numbers are only there to rule things out:

1. **Clay render at 240 / 270 / 300 and 000 / 090**, `tools/paint_views.py --clay`, lit, on a
   mid-grey field. The operator looks at the back. This is the instrument that works — nothing else
   found the v2 defect, and by every metric that back scores no worse than its own face.
2. `tools/crater_probe.py` — see-through parity, perpendicular hull inset, relief against a
   smoothed self, each with the front of the same head as its control.
3. Quad ratio, symmetry plane, `tools/mesh_health.py`.
4. **Chamber section** — `tools/cut_view.py` through the head, confirming interior depth, a solid
   throat wall behind it, and tongue and tooth bands present as geometry.
5. Profile against `modelsheet_neutral.png` through one function, both sides: snout projection
   0.455, muzzle depth 0.635.

**The operator accepts the base. I do not.**

---

## Phase M — the mouth that closes

The chamber arrives from G. This phase makes it move.

**M1. Cavity gate first, proven both ways.** `tools/cavity_gate.py` already exists and already
proved itself on a magenta probe (buried → FAIL, contained → PASS). Re-prove it on the new base
before cutting. A gate that has never failed is not a gate.

**M2. The lip seam — the operator picks it.** Where the chain ends *is* the mouth corner, and that
sets how wide he can ever smile. `tools/seam_prep.py` marks the crease edges Sharp and pre-selects
nothing; `tools/seam_bake.py` validates (exactly 2 endpoints, connected, no branching, no vertex
moved) and writes the vertex group `op_lip_seam`. The validator was proven to refuse a branching
selection and accept a clean walk before the operator spent a minute in Blender. Both tools carry
over unchanged.

**M3. Split, don't delete.** `bmesh.ops.split_edges` along the seam unzips the surface into two
coincident rims. The gap is zero at rest **by construction**, so there is no hole to seal and
`lip_seal`'s entire failure mode — a cavity visible at rest in a shipped asset for weeks — cannot
occur. Corners stay welded; the aperture opens only between them.

**M4. Separate tongue and teeth off the shell.** On `open_v1` these are welded into one 119,424-face
shell — verified. Whatever G produces, they must end up as their own objects, because that is how
they get their own bones and stop swinging out of the head. `tools/mouth_parts.py` already writes
and reads `op_teeth_upper`, `op_teeth_lower`, `op_tongue`.

Teeth are **continuous cream bands, upper and lower — not separated teeth.** Four independent
confirmations against canon; the 7-tooth scallop is wrong.

**M5. Jaw hinge and weights.** Hinge near the ear base. Weights diffused over **topology**, not
distance — the rims are coincident, so no positional falloff can separate them. The v2 build needed
a hard ceiling at `seam_z + 0.004` or the field flowed around the welded corners into the upper lip
and dragged the muzzle pad while every gate read green. **Those numbers are v2's and do not
transfer; the shape of the problem does.**

**Gates:** cavity gate passes at rest, from every direction including -40° elevation. At full open,
nothing see-through past the back wall. **Closed is a real pose, not the rest state** — lips meet,
no interpenetration, tongue and teeth contained. Aperture proportions measured against
`modelsheet_open.png` through one function, both sides. Operator confirms visually.

**M6. He talks.** Operator, standing: *"first you need to show me clyffy actually talking if
possible even if it is scripted … make sure he is going to have a solid alpha, his mouth actually
has some motion and movement and not straight robotic."* A jaw hinge alone is robotic. The deliverable
is a scripted line with jaw plus lip-corner and tongue shapes moving together — the mouth is not
done until that render exists and he has watched it.

---

## Phase E — eyes, and around the eyes

Depends on M only for the face's quad flow being settled.

Eyeballs are **separate spheres**, not shell geometry — they rotate, and geometry welded into a
face cannot. Lids come from the shell as shape keys driven by the rig.

The eye region is the part the operator called out ("eyes **and around the eyes**"): brow, upper and
lower lid folds, and the soft mass under the eye. That region carries most of the expression, and
it is where the approved sheet has real information — brown patches around both eyes, per the
element description.

**Gates:** lids close **fully** — no eyeball visible at any point in the blink; no poke-through at
any gaze angle across the full rotation range; the brow moves without dragging the horn base.
`SPEC.md` warns the eye renders oddly in the profile panel, so eye shape is read from the front and
¾ views only.

*Prior art, unverified against this plan:* the RRO estate has a `face_atlas.py` / `shape_author.py`
pair with 13 weighted regions and `eyeBlinkLeft`/`eyeBlinkRight` from the old project, and a recorded
gate catch (nose produced 0 verts, cheek peaked at 0.40 instead of 1.0, both from seeds that landed
inside the head). Read it before rewriting it; do not import it blind.

---

## Phase R — ears

Two bones per ear, base at the skull, and enough of a chain that they can droop and flick. The
approved reference has **large droopy pink-lined ears** and they are one of the character's loudest
silhouette features.

**Gates:** no shear or pinch at the base through the full range; the ear does not intersect the
horn, the skull, or the shoulder at any pose; both ears reach the same range (the base is symmetric
even though the patches are not — the patches are asymmetric by design and the mesh must never be
mirrored, because mirroring geometry mirrors UVs and therefore mirrors the patches).

---

## Phase A — arms and hands

Last, and the largest unknown. Two recorded facts:

1. **The A-pose was deferred here on purpose.** Measured on v2: no lateral gap between arm and torso
   at any height from 40% to 84% of body height, so arm vertices cannot be separated geometrically —
   it has to come from the rig, or from `pose_mode: "a-pose"` at generation time. G is the chance to
   get it for free; if the new base still arrives arms-down, this phase inherits the problem.
2. **Operator, standing: *"the hands are completely broken and wrong and will need to be redone."***
   Treat generated hands as a placeholder to be replaced, not as geometry to be rigged.

Scope is his words — **basic motion and movement**: shoulder, elbow, wrist, and a finger curl.
Not a full hand rig.

**Gates:** shoulder deforms without collapsing the t-shirt seam; elbow holds volume through full
flexion; no self-intersection arm-to-torso at rest or through the range.

---

## Rules this plan is bound by

* forward is **supplied**, never derived — a derived facing has been wrong three times, once by 103°
* measure both sides of any comparison through **one function**
* flat light for anything measured
* judge **shape** on lit clay from the angle in question — never on paint, never on a silhouette,
  never on a white field
* a gate that has never failed is not a gate — prove it catches its defect first
* never measure along a ray against a convex hull on anything with horns or ears
* the base is modelled **bare of props**; coat, goggles, lanyard and badge are separate meshes
* brown and white **first**; Holstein only after brown/white is captured
* **the operator confirms functionality. I do not claim it.**

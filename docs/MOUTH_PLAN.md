# The mouth — plan

Written 2026-08-04, before anything is cut. Nothing in this document has been executed.
The mesh is untouched: `mesh/clyffy_v2_clean.blend`, 46,056 verts / 46,114 faces.

---

## What the survey actually found

`tools/mouth_survey.py`, `tools/lip_chain.py`, `tools/muzzle_zoom.py` — all read-only.

**Forward is +X (090 deg).** Taken from the fixed-angle orbit, where the face is dead-on at
090. Both geometric derivations were run and printed anyway: the farthest-head-vertex one
returned 192.93 deg — an ear tip, **103 deg wrong**. That is the third time a derived facing
has been wrong on this character. Forward is supplied to every tool from here on.

**The object transform is identity.** loc 0, rot 0, scale 1. The old build's cavity was
extruded 59 deg into the cheek because a WORLD angle was applied to LOCAL coordinates on an
object carrying a 69.17 deg Z rotation. That bug class cannot occur here.

**The lip is a real crease in the geometry, continuous from corner to corner.** This is the
single most important finding and it is the thing the old base did not have. `crease_090.png`
shows an unbroken red line across the full width of the muzzle. Because a crease exists, the
cut can follow real edges instead of being projected onto a flat surface — and projection
onto a flat surface, picked per FACE from texture luminance, is exactly what produced the
staircase boundary and the cavity that poked through at the corners.

**The lip line sits at 71.9% of body height (z = +0.213), confirmed two independent ways:**

| ruler | reading |
|---|---|
| darkest texture band on the front of the head | 71.9% of height |
| geometric crease (dihedral > 25 deg, running laterally) | 71.9% of height |

**The muzzle is a clean quad grid.** 3,478 of 3,539 muzzle vertices are valence 4; 3,360
quads, 0 tris, 0 n-gons. The old project's mouth cut staircased partly because it was cutting
triangle soup.

**There is ample room behind the lip.** At the lip's height the head spans 0.366 forward;
the lip sits at fwd +0.107..+0.151, leaving ~0.25 of skull behind it. A 0.10–0.12 deep cavity
sits well inside the head.

**The crease band BRANCHES.** The widest midline-straddling crease component is 122 verts
spanning 0.179 laterally (18.3% of body height), but its degree histogram is
`{1: 18, 2: 65, 3: 36, 4: 3}` — 39 junctions, 18 endpoints. The branches are where the lip
crease meets the creases running up the sides of the muzzle pad. **The raw crease set is not
a cut path** and must be resolved to a single chain first. That is Phase 1, and it is the
step that must not be skipped.

### Known, not yet resolved

The crease component's lateral extent is -0.0829..+0.0962 — a **7.4% left/right imbalance**.
Part of that is probably a one-sided pad-edge branch rather than real asymmetry; it will be
re-measured on the extracted chain in Phase 1 and reported before Phase 2 runs. Mirroring the
whole mesh is NOT on the table: the brown patches are asymmetric by design and mirroring the
geometry would mirror the UVs and therefore the patches.

**UV islands: 1177.** Irrelevant to the mouth (the cavity gets its own material) but it will
matter for any later texture-space authoring. Recorded here so it is not rediscovered.

---

## The design decision that removes the old build's worst bug

**SPLIT the mesh along the seam. Do not DELETE faces.**

The old build cut a hole by deleting faces, which left a real gap between the upper and lower
rim chains (median 0.0065). At rest that gap was a viewing tunnel into the cavity, so a whole
tool — `lip_seal.py` — existed to move the two chains back together afterwards, with a
Taubin filter to stop the loop shrinking and pulling the lip back off the corners. It never
fully worked; the cavity was visible at rest in the shipped asset for weeks.

`bmesh.ops.split_edges` along the seam chain unzips the surface into two coincident rim
chains. **The gap is zero at rest by construction** — the two rims occupy identical
positions. There is no hole, so there is nothing to seal, so `lip_seal` and its whole failure
mode do not exist in this build. The chain is an open path, so the mouth **corners stay
welded** and the aperture opens only between them, which is also what the reference does.

---

## Phases

Each phase names the artefact it must produce and the gate it must pass. Every phase from 0
onward re-runs the cavity gate, so a regression shows up at the phase that caused it.

### Phase 0 — the gate, written and proven BEFORE the first cut

`tools/cavity_gate.py`

Asks the one question no gate in the old build ever asked: **is any interior geometry visible
from outside, at rest?** `lip_seal`'s containment check and `pose_check` were both green for
weeks while the cavity was plainly poking through the lip.

* forces the rest pose and zeroes all shape keys first (a posed or shape-keyed render answers
  a different question)
* assigns a pure **emissive magenta** to every interior face — emissive so it cannot be lost
  to shading, magenta so it cannot be confused with skin, cream teeth or pink lip
* renders a fan of views over the front hemisphere, **including hard low angles** (elevation
  down to -40 deg), because looking up into a mouth is where a leak shows first
* counts magenta pixels. **Any magenta pixel in any view is a FAIL.** On failure it writes the
  worst view with the offending pixels boxed.

**Proof it works, run before any cutting, on the current untouched mesh:**

| case | expectation |
|---|---|
| magenta probe half-buried at the lip, protruding through the skin | gate must **FAIL** |
| same probe fully inside the head | gate must **PASS** |

Both directions, because a gate that only ever passes proves nothing and a gate that only
ever fails is just as useless. This is the deliverable the operator sees first.

### Phase 1 — the seam, HAND-PICKED BY THE OPERATOR

Operator decision, 2026-08-04: he picks the seam himself. Where the chain ends *is* the mouth
corner, and that sets how wide he can smile for the rest of the project — a character
decision, not a geometry one. It also matches the old project, where `op_lip_seam` came from
the operator's own selection.

**Operator's side.** Open `work/seam/PICK_THE_SEAM.blend` (built by `tools/seam_prep.py`: the
clean mesh with all 2,330 head crease edges marked **Sharp**, so the lip draws in cyan in Edit
Mode. Nothing is pre-selected — a pre-selection would read as a proposal).

1. `NUMPAD 3` looks at his face straight on; `NUMPAD 1` gives the profile — forward is +X.
2. `TAB` into Edit Mode, `2` for edge select, `ALT+A` to clear the selection.
3. Select the lip from one mouth corner to the other. `CTRL+click` walks a shortest path
   between two edges; `ALT+click` grabs a loop where one exists.
4. **Selection only — do not move any vertices.** `seam_bake.py` compares every vertex
   position against the clean mesh and refuses the file if anything moved.
5. Save As `work/seam/op_seam.blend`.

For orientation: the lip sits at **z = +0.2129, 71.9% of body height**, and crease vertices
near that height span lateral -0.1201..+0.1300. The branch junctions in the raw crease set
cluster around lateral -0.07..-0.08 and mirror on the right — that is where the lip crease
meets the creases running up the sides of the pad, and they are exactly what must NOT be
selected.

**Bake and verify.** `tools/seam_bake.py` reads the selection, validates it, and writes the
vertex group `op_lip_seam` onto the CLEAN mesh — only the selection crosses over, so the clean
mesh stays the source of truth. Vertex groups travel with geometry through edits; the old
build stored selections as raw vertex INDICES, which forced every later step to preserve
indices exactly, which is why its mouth delete had to use `FACES_ONLY` and left 67 wire edges
and 20 loose verts inside the cavity.

It refuses, with locations and all faults at once: a modified mesh, a branching selection, a
disconnected selection, or anything other than exactly 2 endpoints.

**The validator was proven both ways before the operator spent any time in Blender**
(`tools/_seam_fixture.py`). A validator that rejects everything wastes his time as surely as
one that accepts everything wastes the build's:

| fixture | result |
|---|---|
| the raw crease component at the lip, 39 junctions | **REFUSED**, exit 1, all 39 located |
| a simple connected walk, degree 2 throughout | **ACCEPTED**, exit 0, group written |

**Artefact:** the chain marked in red at 000/045/090/135, same views as `muzzle_zoom`.

### Phase 2 — split

`tools/mouth_split.py` — `bmesh.ops.split_edges` along `op_lip_seam`.

**Gate:** vertex count rises by exactly the number of interior chain vertices; **face count
unchanged**; no boundary edges beyond the crack itself; non-manifold count does not increase;
**cavity gate still passes** — the crack is zero-width, so nothing may become visible.

### Phase 3 — the cavity bag

`tools/mouth_cavity.py` — extrude the upper and lower rims backward along -fwd through a ring
profile, then bridge the last rings to close the bag.

The profile **expands vertically** as it goes back. The old build's first cavity was 0.1846
deep, 0.1445 wide and **0.0077 tall** — a flat slot with no room for teeth (~0.009), let
alone a tongue. Depth must exceed the widest aperture the jaw will reach or the jaw swings
past the back wall and you see straight through.

Interior material: **dark red, not black** (`reference/approved/SPEC.md`: "the cavity dark but
not black").

**Gate:** cavity gate passes at rest; the bag is watertight (zero boundary edges); non-manifold
does not increase; depth ≥ the aperture at maximum jaw open.

### Phase 4 — teeth and tongue

**Continuous cream bands, upper and lower — NOT separated teeth.** `SPEC.md` records this as
the fourth independent confirmation that the old build's scallop (`TEETH_N = 7`,
`TEETH_CUT = 0.34`) is wrong against canon. `modelsheet_open.png` shows continuous bands.

Tongue: a soft mass filling the floor, visible between the lower band and the lower lip.

**Gate:** cavity gate passes at rest — with teeth and tongue in place, nothing visible.

### Phase 5 — jaw rig and the open pose

Hinge near the ear, weights, open to the reference aperture.

The aperture proportions get measured from `modelsheet_open.png` and from our render
**through one function**, both sides — six measurements in the old project were wrong because
the two sides used different definitions.

**Gate:** at maximum open, no see-through past the back wall; aperture proportions within
tolerance of the reference. **The operator confirms this one visually.** I do not claim it.

---

## Rules this plan is bound by

* forward is supplied, never derived
* measure both sides of any comparison through one function
* flat light for anything measured
* a gate that has never failed is not a gate — Phase 0 proves both directions first
* the operator confirms functionality; no phase is claimed as working

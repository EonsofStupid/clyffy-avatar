# Clyffy avatar — clean rebuild

Started 2026-08-04 at the operator's direction, in a new folder, after the previous project
(the older Clyffy_Avatar working folder) reached a dead end. Nothing here depends on that project; it is kept
only so the operator can decide whether to delete it.

## Why this exists

The old build reshaped a Tripo-generated mesh that **was never this character** toward the
approved reference, stage by stage. Every pass measured better and looked wrong, and each fix
created a new tear somewhere else. The specific, verifiable failures:

* the base mesh's UVs were scattered over ~30 islands covering 6% of the sheet, so any texture-
  space authoring seamed at every island edge
* the mouth seam was picked **per face**, so the cut boundary was a staircase of quad corners and
  the cavity — extruded off that staircase — protruded through the skin at the mouth corners.
  Visible at rest, in the shipped asset, for weeks.
* `lip_seal`'s containment gate and `pose_check` both reported GREEN the whole time, because
  neither one asks *"is the cavity visible from outside at rest"*. That gate never existed.
* the operator's proportion complaints were never fixable by displacement, because the underlying
  shape was a different animal.

**Conclusion, and the reason for the restart: generate the base mesh FROM the approved reference
instead of bending a foreign mesh toward it.**

## The reference chain (single source of truth)

| what | where | role |
|---|---|---|
| approved bust sheet | `reference/approved/modelsheet_neutral.png` | the face the operator signed off, 2026-08-03 |
| mouth open | `reference/approved/modelsheet_open.png` | cavity, teeth, tongue |
| muzzle close-up | `reference/approved/detail_muzzle_profile.png` | pad relief, nostril, lip roll |
| character element | higgsfield `Clyffy-BROWN-avatar-target` `1c6d9749-…` | identity lock for generation |
| inherited canon | `docs/CANON_inherited.md` | wardrobe/prop law, carried from the old project |

**Colour: BROWN AND WHITE first** — operator, 2026-08-04. Holstein comes after the brown/white
version is actually captured. Do not "fix" one into the other.

## Wardrobe law (from CANON, not invented here)

The base body is modelled and rigged **bare of props**. This is load-bearing: the recorded prior
failure is *"the generator welded the t-shirt into the body because the source sheet had no
separation."*

| layer | item |
|---|---|
| base garment | navy DevPULSE t-shirt — the default under-layer, part of the base sheet |
| outer garment | lab coat, clean (DPN) or singed (AV) — **separate mesh**, never body geometry |
| props | goggles · blue lanyard · CLYFFY ID badge — attach/detach |

Goggles are **clear polycarbonate lab safety goggles** and must NOT appear in a base sheet at all,
so brow, sockets and muzzle are unobstructed. Brass steampunk goggles are old drift.

## Generation: both failure modes are documented, and both were reproduced

CANON records that the higgsfield element token *"does two jobs at once — it holds identity and
imposes the canonical stance and props"*, and that dropping it *"freed the pose on the first try
but drifted into a generic tall cow."* Reproduced exactly on 2026-08-04:

* **with the element** → correct character, arms welded to the sides, no A-pose at any prompt strength
* **reference image instead of element** → correct wide A-pose, but the head shrank, the muzzle
  narrowed and the patches washed out. A generic brown cow.

**Resolution: do not fight it in image space.** Use the element sheet (correct character, arms
down) and let the mesher repose — Meshy takes `pose_mode: "a-pose"` and produces the rig-friendly
pose at mesh time.

## Pipeline

1. **turnaround** — 5-view sheet, flat even lighting, no labels, no coat, no goggles, mouth closed
   → `sheets/turn_4k_a.png` (5504×3072)
2. **plates** — split by detected figure bounding box, each masked to its own connected component
   so no neighbouring view bleeds in → `sheets/plate_*.png`
3. **mesh** — Meshy multi-image, **quad topology**, **symmetry on**, `pose_mode: a-pose`, textured
   + PBR. Quads and a real symmetry plane are precisely what the old base lacked.
4. **rig / mouth / shapes** — only after the base geometry is accepted. The mouth is cut on clean
   quads this time, and a *cavity-visible-from-outside* gate is written BEFORE the cut, not after.

## Rules carried forward from the failure

* **Measure both sides through one function.** Six separate measurements in the old project were
  wrong because the two sides used different definitions (coat vs no coat, different cut heights,
  different lighting).
* **Flat light for anything measured.** A key light made a pink muzzle read as *brighter than white
  fur* — an impossible result that nearly shipped as a real number.
* **A gate that has never failed is not a gate.** Prove new gates catch the defect they target.

> Dated history lives in `../BUILD_LOG.md`, newest first.
> The resume point is `../STATUS.md`.

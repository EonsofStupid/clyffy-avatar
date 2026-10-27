# The mouth rebuild, 2026-08-09

These are the steps that actually produced the current mouth, in order, saved out of the live
session so a fresh session does not have to rediscover them. **They are not standalone scripts** —
each one runs INSIDE the live Blender session and expects `blkit.py`'s vocabulary plus a few
globals left by the step before it:

    tools/bl-up                                   # start the session
    tools/bl -f tools/mouth/01_seam_chain.py      # then 02, 03, ...

Globals that carry between steps: `SEAM` (the operator-approved lip line, defined in
`tools/mouth_split.py`), `CURVE` (that seam densified and mirrored), `UPKEYS`/`LOKEYS` (the two
half-loops, keyed by rounded edge midpoint because **`to_mesh()` reindexes and index identity does
not survive a write**), `UNDER` (the jaw underside, keyed by rounded vertex position), `S` (a
BVHTree over `SCAFFOLD`).

| step | what it does |
|---|---|
| `01_seam_chain` | fills the two corner slits, lays a 30-segment chain along the approved seam anchored at the mouth corners |
| `02_split_arcs` | walks the aperture boundary into two contiguous arcs, balances parity for `fill_grid` |
| `03_fill_both_halves` | `fill_grid` each half separately — **the lip becomes a boundary of both patches, not a diagonal through one grid** |
| `04_plant_and_relax` | plants every patch vert on `SCAFFOLD`, clamps drift past 0.020, relaxes with the lip chain pinned |
| `05_even_lip_split_cavity` | evens the lip spacing along its own arc length, splits it, extrudes the bag |
| `06_jaw_underside_select` | **the ray test** — straight down, nothing of the head below it → it IS the underside |
| `07_jaw_drop` | projects that underside onto the scaffold's chin, weighted to zero at the lip |
| `08_despike` | pulls remaining spikes back toward the neighbour average |
| `audit_topology` | rings by distance from the lip, lip valence histogram, corner poles |
| `audit_cavity` | fires a ray back through the lip — **this is what measured the lip at 0.0010 thick** |

Read `BUILD_LOG.md` (2026-08-09) for what each step is for and what was rejected. The remaining
work — inner lip loop, concentric lip loops, corner poles, lip roll, and opening the jaw to check —
is planned step by step in `STATUS.md`.

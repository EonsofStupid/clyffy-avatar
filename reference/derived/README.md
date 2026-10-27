# derived/ — NOT canon

Everything here is CROPPED OR PROCESSED by me from `reference/approved/`.
`reference/approved/SPEC.md` is the authority; if these disagree, these are wrong.

* `canon_side_head.png` — the TRUE 90-DEGREE SIDE PROFILE panel of
  `modelsheet_neutral.png`, cropped to (1878, 280)-(2678, 1320), 800x1040.
  Used as the in-scene overlay plane for profile comparison.

## Why there is no automatic silhouette extraction

Tried and abandoned 2026-09-07. The sheets cannot be segmented by pixel value:
the background is a smooth gradient spanning ~14 levels (203 at the corners,
217 mid) and the WHITE LAB COAT measures rgb(203,203,203) — INSIDE that range.
A loose flood-fill tolerance leaks through the coat and the pink muzzle; a tight
one cannot cross the background gradient and leaves the background unfilled.
White FUR (137-185) is separable; the coat is not.

So profile comparison is done as a VIEWPORT OVERLAY against this plane, with the
alignment stated out loud and adjustable by the operator, rather than by a
number derived from a segmentation that does not work.

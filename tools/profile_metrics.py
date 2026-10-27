#!/usr/bin/env python3
"""Profile measurement harness — ONE function measures canon and model alike.

Why this exists
---------------
`reference/approved/SPEC.md`: *"PROFILE IS NOT OPTIONAL — every proportion
failure in this project is a profile problem, and every measurement taken
before this set was front-on."*

SPEC quotes snout-past-brow / skull-behind-brow = 0.455 for canon, produced by
`head_metrics.snout_projection`, described as *"one function both sides"*. That
tool is gone (along with profile_shot.py, head_proportion.py, materials.py).
On 2026-09-04 I measured 0.629 on the model with a brow definition I invented
and nearly reported a 38% overshoot. SPEC's own log records an earlier
*"protrudes 2.4x too far"* that was exactly this artefact. A number measured one
way on one side and another way on the other is not a comparison.

So: the model is RENDERED onto the same grey the canon sheets use, and both
PNGs go through identical code from pixels to numbers.

Background extraction
---------------------
NOT a brightness threshold. The canon coat is WHITE on a light-grey background
(bg ~203 at the corners, ~214 mid, a smooth gradient) — the subject is BRIGHTER
than the background in places, so any global threshold eats the coat. Instead
the background is flood-filled inward from the image border with a per-step
tolerance, which follows the gradient and stops at the subject's edge.
"""
import sys
import numpy as np
from PIL import Image

BG_STEP_TOL = 6.0      # max per-neighbour jump treated as "still background"
BG_SEED_TOL = 26.0     # max deviation from the seeded border colour


def background_mask(rgb, step_tol=BG_STEP_TOL, seed_tol=BG_SEED_TOL):
    """True where the pixel is background, by flood fill inward from the border."""
    h, w, _ = rgb.shape
    lum = rgb.astype(np.float32).mean(axis=2)
    bg = np.zeros((h, w), dtype=bool)
    seed_vals = np.concatenate([lum[0, :], lum[-1, :], lum[:, 0], lum[:, -1]])
    seed = float(np.median(seed_vals))

    # queue-based flood fill, 4-connected
    from collections import deque
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if not bg[y, x] and abs(lum[y, x] - seed) <= seed_tol:
                bg[y, x] = True
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if not bg[y, x] and abs(lum[y, x] - seed) <= seed_tol:
                bg[y, x] = True
                q.append((y, x))

    while q:
        y, x = q.popleft()
        v = lum[y, x]
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not bg[ny, nx]:
                if abs(lum[ny, nx] - v) <= step_tol and abs(lum[ny, nx] - seed) <= seed_tol:
                    bg[ny, nx] = True
                    q.append((ny, nx))
    return bg


def subject_mask(path, crop=None):
    """Boolean mask of the subject. `crop` is (left, top, right, bottom)."""
    im = Image.open(path).convert("RGB")
    if crop:
        im = im.crop(crop)
    rgb = np.asarray(im)
    return ~background_mask(rgb), rgb


def largest_component(mask):
    """Keep only the biggest connected blob — drops burned-in view labels."""
    h, w = mask.shape
    lab = np.zeros((h, w), dtype=np.int32)
    cur = 0
    best = (0, 0)
    from collections import deque
    for sy in range(h):
        for sx in range(w):
            if mask[sy, sx] and lab[sy, sx] == 0:
                cur += 1
                n = 0
                q = deque([(sy, sx)])
                lab[sy, sx] = cur
                while q:
                    y, x = q.popleft()
                    n += 1
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and lab[ny, nx] == 0:
                            lab[ny, nx] = cur
                            q.append((ny, nx))
                if n > best[0]:
                    best = (n, cur)
    return lab == best[1], best[0]


def outline(mask):
    """Per-row front (min x) and back (max x) of the silhouette.

    Returns rows as (y, x_front, x_back) for rows that contain any subject.
    Row order is image order: y increases DOWNWARD.
    """
    rows = []
    for y in range(mask.shape[0]):
        xs = np.flatnonzero(mask[y])
        if xs.size:
            rows.append((y, int(xs[0]), int(xs[-1])))
    return rows


if __name__ == "__main__":
    p = sys.argv[1]
    m, _ = subject_mask(p)
    m, n = largest_component(m)
    rows = outline(m)
    ys = [r[0] for r in rows]
    print(f"{p}: subject px={n} rows={len(rows)} y={min(ys)}..{max(ys)}")

#!/usr/bin/env python3
"""Composite the orthographic model render onto the canon side panel.

Alignment is DECLARED, never inferred (see work/probes/profile_render.py):
  scale  - model head height mapped onto canon head height, 2242 px/world unit
  anchor - the EYE: model eye (y -0.1191, z 0.8551) -> canon eye pixel (300,290)

Snout LENGTH is the quantity under test, so it is never used as the anchor.
Both canon pixel landmarks were read BY EYE off reference/derived/canon_side_head.png
and are the weakest link here; they are printed so they can be argued with.

Usage: tools/profile_overlay.py [outline|ghost]
"""
import sys
import numpy as np
from PIL import Image

CANON = "reference/derived/canon_side_head_padded.png"
MODEL = "work/shots/model_side.png"
OUT = "work/shots/PROFILE_OVERLAY.png"

PAD_L, PAD_T = 160, 120
CANON_EYE_PX = (300 + PAD_L, 290 + PAD_T)
CANON_CROWN_PX_Y = 95 + PAD_T
CANON_JAW_PX_Y = 790 + PAD_T


def edges(alpha, thr=16):
    """1-px boundary of the alpha mask."""
    m = alpha > thr
    e = np.zeros_like(m)
    e[1:, :] |= m[1:, :] & ~m[:-1, :]
    e[:-1, :] |= m[:-1, :] & ~m[1:, :]
    e[:, 1:] |= m[:, 1:] & ~m[:, :-1]
    e[:, :-1] |= m[:, :-1] & ~m[:, 1:]
    return e, m


def main(mode="outline"):
    canon = Image.open(CANON).convert("RGB")
    model = Image.open(MODEL).convert("RGBA")
    if canon.size != model.size:
        raise SystemExit(f"size mismatch {canon.size} vs {model.size}")
    a = np.asarray(model)[:, :, 3]
    out = np.asarray(canon).copy()

    if mode == "ghost":
        mm = model.copy()
        mm.putalpha(model.split()[3].point(lambda p: int(p * 0.55)))
        comp = canon.convert("RGBA")
        comp.alpha_composite(mm)
        comp.convert("RGB").save(OUT)
    else:
        e, m = edges(a)
        # thicken so it survives downscaling
        t = e.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                t |= np.roll(np.roll(e, dy, 0), dx, 1)
        out[t] = (255, 40, 40)
        # landmark ticks on the canon side, so the alignment can be judged
        for y in (CANON_CROWN_PX_Y, CANON_JAW_PX_Y):
            out[max(0, y - 1):y + 2, 0:60] = (0, 160, 255)
        ex, ey = CANON_EYE_PX
        out[ey - 8:ey + 9, ex - 1:ex + 2] = (0, 220, 0)
        out[ey - 1:ey + 2, ex - 8:ex + 9] = (0, 220, 0)
        Image.fromarray(out).save(OUT)

    ys, xs = np.nonzero(a > 16)
    print(f"model silhouette: x {xs.min()}..{xs.max()}  y {ys.min()}..{ys.max()}")
    print(f"canon landmarks used (BY EYE): crown y={CANON_CROWN_PX_Y} "
          f"jaw y={CANON_JAW_PX_Y} eye={CANON_EYE_PX}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "outline")

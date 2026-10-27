"""Draw the chamber's WIDTH plan over a horizontal section. Builds nothing.

    python3 tools/chamber_plan_top.py <cut_top_00.png> <out.png>

The side profile fixes depth and height. This fixes width — which is what decides whether the
mouth can OPEN UP at the front rather than reading as a slot. Camera constants must match
`cut_view.py`'s 'z' view: ortho, centred (0.10, 0), scale 0.34, 1200px, looking down -Z with
+X right and +Y up.

Widths at the lip are the operator's OWN approved seam corners, not a symmetric idealisation —
they measure -0.0733 and +0.0849, and pretending otherwise would quietly move his mouth.
"""
import sys
from PIL import Image, ImageDraw

SRC, OUT = sys.argv[1], sys.argv[2]
CTR_X, CTR_Y, SCALE, RES = 0.10, 0.0, 0.34, 1200

im = Image.open(SRC).convert("RGB")
assert im.size == (RES, RES), f"expected {RES}x{RES}, got {im.size}"
dr = ImageDraw.Draw(im)


def P(x, y):
    return ((x - CTR_X) / SCALE * RES + RES / 2.0,
            RES / 2.0 - (y - CTR_Y) / SCALE * RES)


LIP_X, THROAT_X = 0.2216, 0.0516
CORNER_L, CORNER_R = -0.0733, +0.0849          # the approved seam's own corners
# fraction of the lip half-width retained, from the lip back to the throat
TAPER = [(0.00, 1.00), (0.30, 0.96), (0.55, 0.86), (0.78, 0.62), (1.00, 0.26)]

for gx in [i / 100.0 for i in range(-2, 28, 2)]:
    a, _ = P(gx, 0)
    if 0 <= a < RES:
        dr.line([(a, 0), (a, RES)], fill=(228, 228, 228))
        dr.text((a + 2, RES - 16), f"{gx:.2f}", fill=(150, 150, 150))
for gy in [i / 100.0 for i in range(-16, 18, 2)]:
    _, b = P(0, gy)
    if 0 <= b < RES:
        dr.line([(0, b), (RES, b)], fill=(228, 228, 228))
        dr.text((4, b - 15), f"{gy:+.2f}", fill=(150, 150, 150))

left, right = [], []
for t, f in TAPER:
    x = LIP_X + (THROAT_X - LIP_X) * t
    left.append(P(x, CORNER_L * f))
    right.append(P(x, CORNER_R * f))
dr.line(left, fill=(0, 170, 90), width=6)
dr.line(right, fill=(0, 170, 90), width=6)
dr.line([left[0], right[0]], fill=(220, 0, 0), width=6)          # the lip line
dr.line([left[-1], right[-1]], fill=(210, 0, 160), width=6)      # the throat

dr.text(P(LIP_X, CORNER_R + 0.016), "LIP", fill=(220, 0, 0))
dr.text(P(THROAT_X - 0.028, 0.0), "THROAT", fill=(210, 0, 160))
dr.text((14, 12), "CHAMBER WIDTH over a horizontal section at the lip height "
                  f"(z = 0.2098)", fill=(0, 0, 0))
dr.text((14, 32), f"lip width {CORNER_R - CORNER_L:.4f} (his approved corners)   "
                  f"throat width {(CORNER_R - CORNER_L) * 0.26:.4f}   "
                  f"depth {LIP_X - THROAT_X:.3f}", fill=(0, 0, 0))
dr.text((14, 52), "BLUE-GREY = solid material   PALE = hollow inside the skin   WHITE = outside",
        fill=(120, 120, 120))
im.save(OUT)
print(f"wrote {OUT}")
for t, f in TAPER:
    x = LIP_X + (THROAT_X - LIP_X) * t
    print(f"  t {t:.2f}  x {x:+.4f}  half-widths {CORNER_L*f:+.4f} / {CORNER_R*f:+.4f}"
          f"  full {(CORNER_R-CORNER_L)*f:.4f}")

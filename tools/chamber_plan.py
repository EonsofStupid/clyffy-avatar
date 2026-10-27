"""Draw the PROPOSED mouth chamber over a real section of the head. Builds nothing.

    python3 tools/chamber_plan.py <cut_render.png> <out.png>

The cut render must be `cut_view.py`'s `cut_mouth_00.png`, whose camera is known: orthographic,
centred on (0.13, 0, 0.21), scale 0.28, 1200px, looking along +Y with +X to the right and +Z up.
Those constants are duplicated here deliberately and asserted against the image size, because a
silently mismatched projection would draw a plausible-looking outline in the wrong place.

WHY A DRAWING AND NOT GEOMETRY. The last cavity was built from measured depths, passed every
gate, and turned out to have no volume at all — indistinguishable from the raw head in section.
Nothing catches that except looking. So the shape gets agreed on the section first.
"""
import sys
from PIL import Image, ImageDraw

SRC, OUT = sys.argv[1], sys.argv[2]
CTR_X, CTR_Z, SCALE, RES = 0.13, 0.21, 0.28, 1200

im = Image.open(SRC).convert("RGB")
assert im.size == (RES, RES), f"expected a {RES}x{RES} cut render, got {im.size}"
dr = ImageDraw.Draw(im)


def P(x, z):
    # camera on +Y looking -Y (the only side the cut face is visible from): +X runs LEFT.
    return (RES / 2.0 - (x - CTR_X) / SCALE * RES,
            RES / 2.0 - (z - CTR_Z) / SCALE * RES)


def bez(a, c, b, n=48):
    return [( (1-t)**2*a[0] + 2*(1-t)*t*c[0] + t**2*b[0],
              (1-t)**2*a[1] + 2*(1-t)*t*c[1] + t**2*b[1] ) for t in
            [i/(n-1) for i in range(n)]]


# ---- landmarks measured from the mesh -------------------------------------------------
LIP    = (0.2216, 0.2098)   # seam at the midline
HINGE  = (-0.0047, 0.3067)  # jaw pivot, from the ear base
DEPTH  = 0.170              # target: comfortably more than the 0.114 open aperture
THROAT = (LIP[0] - DEPTH, LIP[1] + 0.012)

PAL_BULGE, FLR_BULGE = 0.034, 0.030
mid = ((LIP[0] + THROAT[0]) / 2.0, (LIP[1] + THROAT[1]) / 2.0)
palate = bez(P(*LIP), P(mid[0], mid[1] + PAL_BULGE), P(*THROAT))
floor  = bez(P(*LIP), P(mid[0], mid[1] - FLR_BULGE), P(*THROAT))

# grid
for gx in [i / 100.0 for i in range(0, 30, 2)]:
    a, _ = P(gx, 0)
    if 0 <= a < RES:
        dr.line([(a, 0), (a, RES)], fill=(226, 226, 226))
        dr.text((a + 2, RES - 16), f"{gx:.2f}", fill=(150, 150, 150))
for gz in [i / 100.0 for i in range(8, 40, 2)]:
    _, b = P(0, gz)
    if 0 <= b < RES:
        dr.line([(0, b), (RES, b)], fill=(226, 226, 226))
        dr.text((4, b - 15), f"{gz:.2f}", fill=(150, 150, 150))

# the OLD cavity, for scale — a lens pitched up into the muzzle
old_throat = (0.2216 - 0.100 * 0.643, 0.2098 + 0.100 * 0.766)   # depth 0.100 at pitch +50
dr.line([P(*LIP), P(*old_throat)], fill=(190, 190, 190), width=3)
dr.text(P(old_throat[0] - 0.012, old_throat[1] + 0.006), "old cavity axis", fill=(150, 150, 150))

dr.line(palate, fill=(0, 130, 255), width=6)
dr.line(floor, fill=(0, 170, 90), width=6)
dr.line([palate[-1], floor[-1]], fill=(210, 0, 160), width=6)

hx, hz = P(*HINGE)
dr.ellipse([hx - 11, hz - 11, hx + 11, hz + 11], outline=(255, 130, 0), width=5)
dr.text((hx + 14, hz - 9), "JAW HINGE", fill=(255, 130, 0))
lx, lz = P(*LIP)
dr.ellipse([lx - 8, lz - 8, lx + 8, lz + 8], outline=(220, 0, 0), width=4)
dr.text((lx + 12, lz - 26), "LIP", fill=(220, 0, 0))
tx, tz = P(*THROAT)
dr.text((tx - 118, tz + 16), "THROAT", fill=(210, 0, 160))

dr.text((14, 12), "PROPOSED CHAMBER over a real section  —  blue = palate (skull), "
                  "green = floor (jaw), magenta = throat", fill=(0, 0, 0))
dr.text((14, 32), f"depth {DEPTH:.3f}   height at mid {PAL_BULGE + FLR_BULGE:.3f}   "
                  f"target open aperture 0.114 (measured from modelsheet_open)", fill=(0, 0, 0))
dr.text((14, 52), "grey line = the cavity I built, for scale.  "
                  "BLUE-GREY = solid material, PALE = hollow inside the skin, WHITE = outside",
        fill=(120, 120, 120))
im.save(OUT)
print(f"wrote {OUT}")
print(f"  lip    {LIP}")
print(f"  throat {THROAT}   depth {DEPTH}")
print(f"  throat sits {THROAT[0] - HINGE[0]:+.4f} in front of the hinge")
print(f"  chamber height at mid-depth {PAL_BULGE + FLR_BULGE:.3f}")

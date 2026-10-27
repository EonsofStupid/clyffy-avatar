"""Remove the brown-patch ALBEDO from the mesher plates, leaving geometry cues intact.

    python3 tools/flatten_patches.py <out_dir> <plate.png> [...]

Why: two Tripo rolls on the same plates (clyffy_v2.fbx and work/remesh/candidate.fbx) both
modelled the back of the skull wrong, both defects tracking the BROWN PATCH BOUNDARY — a scooped
basin the first roll, a raised embossed flap the second. The patch is PAINT on the character, but
its dark edge reads as a depth discontinuity to multiview fusion. Severity varies per roll; the
location never does. Cause: albedo contrast, in the plates.

Fix: hand the mesher plates where fur-brown is replaced by fur-white while every real shading cue
(the shirt, the muzzle, ears, silhouette, form shading) stays. The patches return at TEXTURE time,
from the canon art, where paint belongs.

Classification is HUE-based, restricted to the warm chocolate band, so it takes the patches and
leaves everything else: the navy shirt is opposite in hue, the pink muzzle is lighter and rosier,
hooves are far darker. Replacement preserves per-pixel luminance structure (scaled into the fur
range) so surviving shading still describes the form instead of leaving a flat hole.
"""
import sys, os
import numpy as np
from PIL import Image

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)

for src in sys.argv[2:]:
    im = Image.open(src).convert("RGB")
    a = np.asarray(im, dtype=np.float32) / 255.0
    r, g, b = a[..., 0], a[..., 1], a[..., 2]

    mx = a.max(axis=2)
    mn = a.min(axis=2)
    v = mx
    s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    # hue in degrees, only where the max channel is red (the warm side)
    h = np.zeros_like(v)
    m = mx == r
    h[m] = (60 * ((g - b) / np.maximum(mx - mn, 1e-6)))[m] % 360

    # warm chocolate: reddish-orange hue, saturated, mid-dark. The navy shirt fails the hue test,
    # the pink muzzle fails saturation (pastel) and value (light), hooves fail value (near-black).
    patch = (mx == r) & (h < 50) & (s > 0.25) & (v > 0.12) & (v < 0.75)

    # THE RIM: where a patch shades into the white fur its pixels go dark and desaturated, failing
    # the hue test — the first pass left every patch wearing a dark outline, which is itself the
    # depth-reading contrast boundary this tool exists to remove. Take any non-blue darkish pixel
    # NEAR an already-classified patch pixel; nearness keeps shirt shadows and hooves out of it.
    from PIL import ImageFilter
    near = np.asarray(
        Image.fromarray((patch * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(25)),
        dtype=np.uint8) > 0
    not_blue = ~((mx == b) & (s > 0.20))
    rim = near & not_blue & (v < 0.62) & (v > 0.05)
    patch = patch | rim

    # soften the mask edge so the recolour has no hard boundary of its own — dilate then blur,
    # both with PIL (its box blur stands in for the gaussian; scipy isn't installed)
    pm = Image.fromarray((patch * 255).astype(np.uint8))
    pm = pm.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.BoxBlur(3))
    soft = (np.asarray(pm, dtype=np.float32) / 255.0)[..., None]

    # replace with fur-white that keeps the local shading: scale the pixel's value into the fur
    # band [0.78, 0.97] so form shading survives, chroma near zero like the white fur
    vv = np.clip((v - 0.12) / 0.63, 0, 1)          # normalized brightness inside the patch band
    fur_v = 0.78 + vv * 0.19
    fur = np.stack([fur_v, fur_v * 0.985, fur_v * 0.96], axis=2)   # faint warm tint like the fur

    out = a * (1 - soft) + fur * soft
    dst = os.path.join(OUT, "flat_" + os.path.basename(src).replace("u_", ""))
    Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).save(dst)
    print(f"{os.path.basename(src)}: patch pixels {int(patch.sum())} "
          f"({patch.mean()*100:.1f}%) -> {dst}")

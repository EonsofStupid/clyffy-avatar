"""Cut a 4-view turnaround into Tripo multiview plates on ONE uniform canvas.

    python3 tools/cut_plates.py <sheet.png> <out_dir>

Two rules, both learned the hard way and both recorded in BUILD_LOG:

  ORDER IS PART OF THE CONTRACT. Tripo reads its inputs as front / left / back / right, front
  mandatory and first. Feeding it front / three-quarter / side / back is what produced a
  THREE-HORNED head — it fused features at angles they do not belong to.

  ONE CANVAS, ONE SCALE, ONE GROUND LINE. Cropping each plate to its own bounding box gave
  canvases 1094-1407 px wide, a 28% spread, and multi-view fusion assumes the subject sits
  identically in every frame. Every plate here is written on an identical canvas with the
  figures aligned on a shared ground line and centred horizontally.

Each figure is masked to its OWN connected component so a neighbouring view cannot bleed in,
and the long edge is capped at 2048 because that is what the mesher downsamples to anyway
(verified previously by fetching the `_resize.jpg` a job actually used).
"""
import sys
import os
import numpy as np
from PIL import Image

SRC, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
LONG_EDGE = 2048
NAMES = ["01_front", "02_left", "03_back", "04_right"]

im = Image.open(SRC).convert("RGB")
a = np.asarray(im, dtype=np.float32) / 255.0
H, W, _ = a.shape
print(f"sheet {W}x{H}")

# background: the plate corners are guaranteed empty seamless grey
corner = np.concatenate([a[:40, :40].reshape(-1, 3), a[:40, -40:].reshape(-1, 3),
                         a[-40:, :40].reshape(-1, 3), a[-40:, -40:].reshape(-1, 3)])
bg = corner.mean(axis=0)
dist = np.linalg.norm(a - bg[None, None, :], axis=2)
# THRESHOLD ABOVE THE GROUND SHADOWS. At 0.085 the soft contact shadows under the hooves were
# dark enough to count as foreground, which BRIDGED adjacent figures into one component — the
# "back" plate came out with two heads in it. The shadows sit just above the background; the
# character does not.
fg = dist > 0.16
print(f"background rgb {tuple(round(float(v),3) for v in bg)}   foreground pixels {int(fg.sum())}")

# connected components on a decimated mask (labelling 17M pixels in python is not worth it),
# then map each label back at full resolution by column ranges
STEP = 4
small = fg[::STEP, ::STEP]
sh, sw = small.shape
lab = np.zeros((sh, sw), dtype=np.int32)
cur = 0
comps = []
for sy in range(sh):
    for sx in range(sw):
        if not small[sy, sx] or lab[sy, sx]:
            continue
        cur += 1
        stack = [(sy, sx)]
        lab[sy, sx] = cur
        pts = []
        while stack:
            cy, cx = stack.pop()
            pts.append((cy, cx))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < sh and 0 <= nx < sw and small[ny, nx] and not lab[ny, nx]:
                    lab[ny, nx] = cur
                    stack.append((ny, nx))
        comps.append((len(pts), cur, np.array(pts)))
comps.sort(key=lambda c: -c[0])
print(f"connected components: {len(comps)}   eight largest: {[c[0] for c in comps[:8]]}")
assert len(comps) >= 4, "fewer than four figures found"

figs = []
for n, cid, pts in comps[:4]:
    y0, y1 = pts[:, 0].min() * STEP, (pts[:, 0].max() + 1) * STEP
    x0, x1 = pts[:, 1].min() * STEP, (pts[:, 1].max() + 1) * STEP
    figs.append({"cid": cid, "x0": int(x0), "x1": int(min(W, x1)),
                 "y0": int(y0), "y1": int(min(H, y1))})
figs.sort(key=lambda f: f["x0"])          # left to right = front, left, back, right
hs = [f["y1"] - f["y0"] for f in figs]
print("figures left to right:")
for nm, f in zip(NAMES, figs):
    print(f"  {nm:<9} x {f['x0']:>5}..{f['x1']:<5} y {f['y0']:>5}..{f['y1']:<5}  "
          f"{f['x1']-f['x0']:>4} x {f['y1']-f['y0']:<4}")
spread = (max(hs) - min(hs)) / float(np.mean(hs)) * 100.0
print(f"height spread across the four figures: {spread:.2f}%  "
      f"({'OK' if spread < 3.0 else 'TOO LARGE — fusion assumes one scale'})")

# one canvas for all four: widest figure, tallest figure, plus a margin
mw = max(f["x1"] - f["x0"] for f in figs)
mh = max(hs)
pad = int(0.10 * mh)
CW, CH = mw + 2 * pad, mh + 2 * pad
print(f"uniform canvas {CW}x{CH} (pad {pad})")

# NO PER-PIXEL MASKING. Components are used only to find the four bounding boxes; the crop
# itself is a plain bbox crop. The mask route produced a GHOSTED second head in the back plate
# — verified by cropping the identical region straight from the sheet, which is clean — and
# since the four figures are separated by 32-100 px of clear background, a bbox crop already
# contains exactly one figure. The simplest thing that is provably right beats the clever one.
gaps = [figs[i + 1]["x0"] - figs[i]["x1"] for i in range(3)]
print(f"horizontal gaps between figures: {gaps}")
assert min(gaps) > 8, f"figures nearly touch ({gaps}); a bbox crop would include a neighbour"
for nm, f in zip(NAMES, figs):
    sub = a[f["y0"]:f["y1"], f["x0"]:f["x1"]]
    canvas = np.tile(bg[None, None, :], (CH, CW, 1))
    fh, fw = sub.shape[:2]
    ox = (CW - fw) // 2
    oy = CH - pad - fh                      # SHARED GROUND LINE: all feet at the same row
    canvas[oy:oy + fh, ox:ox + fw] = sub
    img = Image.fromarray((np.clip(canvas, 0, 1) * 255).astype(np.uint8))
    if max(img.size) > LONG_EDGE:
        s = LONG_EDGE / max(img.size)
        img = img.resize((int(img.size[0] * s), int(img.size[1] * s)), Image.LANCZOS)
    p = os.path.join(OUT, f"p_{nm}.png")
    img.save(p)
    print(f"  wrote {p}  {img.size}")
print("all four plates share one canvas, one scale and one ground line")

#!/usr/bin/env python3
"""Take the SAME silhouette measurement off a canon image that blkit's
silhouette() takes off the model, so the two can be subtracted.

This is the half that stops "does it match the art?" being me holding two
pictures side by side. The art is used as DATA, not as something to look at:
threshold the background away, then per height band report the width and the
number of separate runs, all normalised by the figure's own height so the
comparison is scale-free.

    tools/silh_art.py reference/look/turnaround_holstein_5view.png --panel 0
    tools/silh_art.py <img> --panel 0 --against work/probes/model_silh.json

--against expects the JSON that `tools/bl 'result=silhouette(...)'` prints.
"""
import argparse
import json
import sys

try:
    from PIL import Image
except ImportError:
    sys.exit("needs Pillow: pip install --user Pillow")


def panel_box(w, h, panel, panels, foot_trim):
    """Turnarounds are N equal panels side by side with a label strip below."""
    pw = w / panels
    return (int(panel * pw), 0, int((panel + 1) * pw), int(h * (1.0 - foot_trim)))


def mask_of(im, tol):
    """Background is whatever the corners agree on. Everything far from it in
    RGB is the figure. Deliberately dumb — these sheets are flat studio grey."""
    px = im.load()
    w, h = im.size
    corners = [px[1, 1], px[w - 2, 1], px[1, h - 2], px[w - 2, h - 2]]
    corners = [c[:3] for c in corners]
    bg = tuple(sum(c[i] for c in corners) // len(corners) for i in range(3))
    m = [[False] * w for _ in range(h)]
    for y in range(h):
        row = m[y]
        for x in range(w):
            r, g, b = px[x, y][:3]
            if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) > tol:
                row[x] = True
    return m, bg


def profile(mask, bands, gap_frac):
    h = len(mask)
    w = len(mask[0])
    ys = [y for y in range(h) if any(mask[y])]
    if not ys:
        return None
    y0, y1 = min(ys), max(ys)
    fig_h = (y1 - y0) + 1
    gap_px = max(int(gap_frac * fig_h), 2)
    xs_all = [x for y in ys for x in range(w) if mask[y][x]]
    x0, x1 = min(xs_all), max(xs_all)
    cx = (x0 + x1) / 2.0

    out = []
    for b in range(bands):
        ya = y0 + int(fig_h * b / bands)
        yb = y0 + int(fig_h * (b + 1) / bands)
        cols = set()
        for y in range(ya, max(yb, ya + 1)):
            if 0 <= y < h:
                for x in range(w):
                    if mask[y][x]:
                        cols.add(x)
        if not cols:
            out.append({"v": round(1.0 - (b + 0.5) / bands, 4), "n": 0})
            continue
        o = sorted(cols)
        segs, s0, prev = [], o[0], o[0]
        for x in o[1:]:
            if x - prev > gap_px:
                segs.append((s0, prev))
                s0 = x
            prev = x
        segs.append((s0, prev))
        lo, hi = o[0], o[-1]
        out.append({
            # image y grows DOWNWARD; v is measured from the feet up, like the model
            "v": round(1.0 - (b + 0.5) / bands, 4),
            "n": len(cols),
            "w": round((hi - lo) / fig_h, 4),
            "c": round(((lo + hi) / 2 - cx) / fig_h, 4),
            "runs": len(segs),
        })
    out.reverse()          # feet first, to match the model's ordering
    return {"figure_px": [x0, y0, x1, y1], "height_px": fig_h,
            "aspect": round((x1 - x0 + 1) / fig_h, 4), "profile": out}


def compare(art, model):
    """Per-band |w_art - w_model|, both already normalised by their own height."""
    ap = [r for r in art["profile"] if r.get("n")]
    mp = [r for r in model["profile"] if r.get("n")]
    if not ap or not mp:
        return {"error": "one side is empty"}

    def at(prof, v):
        return min(prof, key=lambda r: abs(r["v"] - v))

    rows = []
    for r in ap:
        m = at(mp, r["v"])
        rows.append({"v": r["v"], "art_w": r["w"], "model_w": m["w"],
                     "d": round(r["w"] - m["w"], 4),
                     "art_runs": r["runs"], "model_runs": m["runs"]})
    ds = [abs(r["d"]) for r in rows]
    worst = max(rows, key=lambda r: abs(r["d"]))
    run_mismatch = [r for r in rows if r["art_runs"] != r["model_runs"]]
    return {"bands": len(rows),
            "mean_dev": round(sum(ds) / len(ds), 4),
            "max_dev": round(max(ds), 4),
            "worst_at_v": worst["v"], "worst": worst,
            "run_mismatches": len(run_mismatch),
            "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--panel", type=int, default=0)
    ap.add_argument("--panels", type=int, default=1)
    ap.add_argument("--bands", type=int, default=24)
    ap.add_argument("--tol", type=int, default=48)
    ap.add_argument("--foot-trim", type=float, default=0.08,
                    help="fraction of panel height to drop (label strip)")
    ap.add_argument("--gap", type=float, default=0.012,
                    help="run-splitting gap, as a fraction of figure height")
    ap.add_argument("--against", help="JSON printed by blkit silhouette()")
    a = ap.parse_args()

    im = Image.open(a.image).convert("RGB")
    if a.panels > 1:
        im = im.crop(panel_box(im.size[0], im.size[1], a.panel, a.panels, a.foot_trim))
    elif a.foot_trim:
        w, h = im.size
        im = im.crop((0, 0, w, int(h * (1.0 - a.foot_trim))))
    if max(im.size) > 900:
        im.thumbnail((900, 900), Image.LANCZOS)

    mask, bg = mask_of(im, a.tol)
    art = profile(mask, a.bands, a.gap)
    if art is None:
        sys.exit("no figure found — raise --tol or check the panel index")
    art["background"] = bg
    art["source"] = f"{a.image}#panel{a.panel}"

    if a.against:
        with open(a.against) as f:
            model = json.load(f)
        art["compare"] = compare(art, model)
    print(json.dumps(art, indent=2))


if __name__ == "__main__":
    main()

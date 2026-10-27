"""Is the back of this head sound? Three independent measures, none of which can bridge a gap.

    blender -b --python tools/crater_probe.py -- <model> <fwd_deg> [out_png]

## This tool produced a FALSE result on 2026-08-05 and was rewritten. Read this before trusting it.

The first version cast rays inward and measured the distance, ALONG THE RAY, between where the ray
hit the convex hull of the head band and where it hit the mesh. That is wrong for a head that has
horns and ears. The hull BRIDGES the gap between an ear and the skull, so a ray fired through that
bridge hits the hull immediately and the real skull a long way later, and the tool reported the
difference as a pit. On `clyffy_v2.fbx` it reported **max inset 0.3018 and 29.8% of the back more
than 0.10 inside the skull line**. Direct measurement says the true worst case is **0.0787**, and
every single ray hits an outward-facing surface. There is no hole and nothing is missing.

The defect the operator reported IS real — the back of that skull is a broad malformed basin with a
curled ridge across it — but it is roughly a quarter as deep as the old number, and it is a badly
shaped surface, not an absent one. A number that is 4x wrong is worse than no number: it was
written into STATUS, BUILD_LOG and a quarantine manifest as fact.

So this version never measures along a ray against a hull. It reports:

  1. SEE-THROUGH — parallel rays along the view axis. For each, is the first surface an outward
     face? Any inward first hit means there is genuinely no surface there. This is the only test
     that can tell "missing" from "misshapen", and it is the one that was missing.
  2. HULL INSET — per VERTEX, perpendicular distance to the head-band convex hull. Perpendicular,
     so a bridged gap cannot inflate it. Broad basins show up here.
  3. RELIEF — per vertex, deviation from a heavily smoothed copy of the same mesh. Catches sharp
     gouges that a broad-basin measure smooths over. The FRONT of the head is printed alongside as
     the control, because a real face has real recesses and the back should not have more than it.

Judge on all three plus a lit clay render. Any single one of them can be fooled.
"""
import bpy, bmesh, sys, os, math, struct, zlib
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC = os.path.abspath(argv[0])
FWD_DEG = float(argv[1])
OUT_PNG = os.path.abspath(argv[2]) if len(argv) > 2 else None

ext = os.path.splitext(SRC)[1].lower()
if ext == ".blend":
    bpy.ops.wm.open_mainfile(filepath=SRC)
elif ext == ".fbx":
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=SRC)
else:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=SRC)

ob = max([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
M = ob.matrix_world
co = np.array([(M @ v.co)[:] for v in ob.data.vertices])
z = co[:, 2]
zlo, zhi = float(z.min()), float(z.max())
band = zhi - zlo
hm = z > zlo + 0.72 * band
head = co[hm]
hc = head.mean(axis=0)

a = math.radians(FWD_DEG)
fwd = np.array([math.sin(a), -math.cos(a), 0.0])
back = -fwd
lat = np.array([-back[1], back[0], 0.0])
rel = co - hc
nrm = np.linalg.norm(rel, axis=1) + 1e-9
cosb = (rel @ back) / nrm

print(f"\n=== {os.path.basename(SRC)}  fwd {FWD_DEG:.0f} deg ===")
print(f"head band z {head[:,2].min():.3f}..{head[:,2].max():.3f}"
      f"   head band height {head[:,2].max()-head[:,2].min():.3f}   body height {band:.3f}")

# ---- 1. SEE-THROUGH -------------------------------------------------------------------------
half = float(np.abs(head - hc).max()) * 1.15
R = half * 4
N = 140
img = np.zeros((N, N, 3), np.uint8)
front = inward = miss = 0
for iv in range(N):
    zz = hc[2] - half + 2 * half * (iv + 0.5) / N
    for iu in range(N):
        s = -half + 2 * half * (iu + 0.5) / N
        o = hc + lat * s + back * R
        o[2] = zz
        ok, loc, nor, _ = ob.ray_cast(Vector(o.tolist()), Vector((-back).tolist()), distance=R * 2)
        if not ok:
            miss += 1
            continue
        if float(np.dot(np.array(nor[:]), back)) > 0:
            front += 1
            img[iv, iu] = (90, 200, 90)
        else:
            inward += 1
            img[iv, iu] = (230, 40, 40)
hit = front + inward
print(f"\n[1] SEE-THROUGH   rays {N*N}   background {miss}   hit {hit}")
print(f"    first surface faces OUT (present): {front} ({front/max(hit,1)*100:.1f}%)")
# A handful of inward first-hits along the silhouette are grazing rays clipping an edge, not a
# hole. A real hole is a contiguous patch, so the verdict is on the FRACTION, not the raw count —
# otherwise this gate cries wolf and gets ignored, which is how the last one did its damage.
frac_in = inward / max(hit, 1)
verdict = "FAIL — there is a hole" if frac_in > 0.005 else (
    f"no hole ({inward} grazing hits at the silhouette)" if inward else "no hole")
print(f"    first surface faces IN  (MISSING): {inward} ({frac_in*100:.2f}%)   <-- {verdict}")

# ---- 2. HULL INSET, perpendicular, per vertex -------------------------------------------------
bm = bmesh.new()
for p in head:
    bm.verts.new(Vector(p.tolist()))
bm.verts.ensure_lookup_table()
bmesh.ops.convex_hull(bm, input=bm.verts)
me = bpy.data.meshes.new("HULL")
bm.to_mesh(me); bm.free()
hull = bpy.data.objects.new("HULL", me)
bpy.context.scene.collection.objects.link(hull)
bpy.context.view_layer.update()

idx = np.nonzero(hm)[0]
ins = np.zeros(len(idx))
for i, vi in enumerate(idx):
    ok, loc, _, _ = hull.closest_point_on_mesh(Vector(co[vi].tolist()))
    ins[i] = (Vector(co[vi].tolist()) - loc).length if ok else 0.0
cb = cosb[idx]
print(f"\n[2] HULL INSET (perpendicular, per vertex)")
for label, m in (("rear hemisphere", cb > 0.15), ("straight back", cb > 0.60),
                 ("FRONT (control)", cb < -0.60)):
    v = ins[m]
    if not len(v):
        continue
    print(f"    {label:16s} n={len(v):6d}  median {np.median(v):.4f}  p90 {np.percentile(v,90):.4f}"
          f"  MAX {v.max():.4f}   >0.05 {(v>0.05).mean()*100:5.1f}%")

# ---- 3. RELIEF vs a smoothed copy of the same mesh --------------------------------------------
bm = bmesh.new(); bm.from_mesh(ob.data); bm.verts.ensure_lookup_table()
P = np.array([v.co[:] for v in bm.verts])
nb = [[e.other_vert(v).index for e in v.link_edges] for v in bm.verts]
S = P.copy()
for _ in range(60):
    S = np.array([S[n].mean(0) if n else S[i] for i, n in enumerate(nb)])
bm.free()
S = np.array([(M @ Vector(p.tolist()))[:] for p in S])
signed = np.einsum('ij,ij->i', co - S, rel / nrm[:, None])
print(f"\n[3] RELIEF vs 60-pass smoothed self  (negative = sunk below the local form)")
for label, m in (("rear hemisphere", hm & (cosb > 0.15)), ("straight back", hm & (cosb > 0.60)),
                 ("FRONT (control)", hm & (cosb < -0.60))):
    v = signed[m]
    if not len(v):
        continue
    print(f"    {label:16s} n={len(v):6d}  p05 {np.percentile(v,5):+.4f}  MIN {v.min():+.4f}"
          f"   sunk >0.01 {(v<-0.01).mean()*100:5.2f}%")

if OUT_PNG:
    im = img[::-1]
    raw = b"".join(b"\x00" + im[r].tobytes() for r in range(N))
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))
    open(OUT_PNG, "wb").write(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", N, N, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    print(f"\nsee-through map -> {OUT_PNG}   green = surface present, RED = hole")

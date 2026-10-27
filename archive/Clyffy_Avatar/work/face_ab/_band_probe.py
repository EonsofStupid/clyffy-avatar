"""READ-ONLY probe: what does the snout weight band actually select?

Mirrors tools/head_proportion.py's landmark scan and weight construction exactly, then reports
WHICH VERTICES carry weight and, critically, what the FRONTMOST head vertex's weight is. Writes
nothing.
"""
import bpy, sys, os, math
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
SRC = os.path.abspath(argv[0])
FWD = 235.1
NECK = 0.55

bpy.ops.wm.open_mainfile(filepath=SRC)
ob = max([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
me = ob.data
N = len(me.vertices)
co = np.empty((N, 3)); me.vertices.foreach_get("co", co.ravel())
H = float(co[:, 2].max() - co[:, 2].min())
a = math.radians(FWD)
fwd = np.array([math.sin(a), -math.cos(a), 0.0])
lat = np.array([-fwd[1], fwd[0], 0.0])
lp = co @ lat
z = co[:, 2]

gi = {g.name: g.index for g in ob.vertex_groups}
lipm = np.zeros(N, bool)
want = gi["op_lip_seam"]
for v in me.vertices:
    for g in v.groups:
        if g.group == want and g.weight > 0.5:
            lipm[v.index] = True
            break
z_lip = float(z[lipm].mean())
lat0 = float(np.median(lp[z > z_lip]))


def width_at(zz, half=0.008):
    m = np.abs(z - zz) < half
    return float(np.ptp(lp[m])) if m.sum() >= 8 else 0.0


head_zs = np.linspace(z.max(), z_lip, 160)
prof = [(zz, width_at(zz)) for zz in head_zs]
prof = [(zz, w) for zz, w in prof if w > 0]
ear_z, ear_w = max(prof, key=lambda t: t[1])
above = [(zz, w) for zz, w in prof if zz > ear_z]
crown_z = max((zz for zz, w in above if w > 0.55 * ear_w), default=ear_z)
neck_zs = np.linspace(z_lip + 0.01 * H, z_lip - 0.16 * H, 120)
nprof = [(zz, width_at(zz)) for zz in neck_zs]
nprof = [(zz, w) for zz, w in nprof if w > 0]
neck_z = min(nprof, key=lambda t: t[1])[0]

COLLAR = z_lip - 0.090 * H
z_top, z_bot = neck_z, COLLAR
band = max(z_top - z_bot, 1e-6)
lost = band * (1.0 - NECK)
newz = z.copy()
inband = (z >= z_bot) & (z < z_top)
newz[inband] = z_bot + (z[inband] - z_bot) * NECK
newz[z >= z_top] = z[z >= z_top] - lost
co[:, 2] = newz
crown2 = crown_z - lost
neck2 = z_bot + (neck_z - z_bot) * NECK
lip2 = z_lip - lost
span = crown2 - lip2

f = co @ fwd
zc2 = co[:, 2]
brow = (zc2 > lip2 + 0.45 * span) & (zc2 < crown2) & (np.abs(lp - lat0) < 0.25 * ear_w)
f_brow = float(np.percentile(f[brow], 92))
head_m = zc2 > (neck2 - 0.02 * H)
depth_m = float(np.ptp(f[head_m]))

tz = np.clip((lip2 + 0.85 * span - zc2) / max(0.30 * span, 1e-9), 0, 1)
wz = tz * tz * (3.0 - 2.0 * tz)
ahead = np.clip((f - f_brow) / max(depth_m * 0.35, 1e-9), 0.0, 1.0)
w_sn = wz * ahead

print(f"\nverts {N}   H {H:.4f}   lost {lost:.4f}")
print(f"  lip2 {lip2:.4f}   crown2 {crown2:.4f}   neck2 {neck2:.4f}   span {span:.4f}")
print(f"  f_brow {f_brow:.4f}   head depth {depth_m:.4f}")
print(f"\nZ BAND (wz term only, ignores 'ahead'):")
print(f"  wz == 1 for z <= {lip2 + 0.55*span:.4f}   ({100*(lip2+0.55*span - lip2)/span:.0f}% up the lip->crown span)")
print(f"  wz == 0 for z >= {lip2 + 0.85*span:.4f}")
print(f"  -> wz==1 vertices: {int((wz > 0.999).sum())}, of which BELOW the lip: {int(((wz > 0.999) & (zc2 < lip2)).sum())}")
print(f"     their z range {zc2[wz > 0.999].min():.4f} .. {zc2[wz > 0.999].max():.4f}"
      f"   (body bottom is {zc2.min():.4f})")

print(f"\nEFFECTIVE WEIGHT w_sn = wz * ahead:")
for lo in [0.9, 0.7, 0.5, 0.3, 0.1, 0.01]:
    m = w_sn > lo
    if m.sum():
        print(f"  w_sn > {lo:<4}  {int(m.sum()):>6} verts   z {zc2[m].min():.4f}..{zc2[m].max():.4f}"
              f"   f {f[m].min():.4f}..{f[m].max():.4f}")
    else:
        print(f"  w_sn > {lo:<4}       0 verts")

print(f"\nTHE FRONTMOST HEAD VERTEX — the one that sets the measured projection:")
hidx = np.nonzero(head_m)[0]
order = hidx[np.argsort(-f[hidx])]
print(f"  {'rank':>4} {'vert':>7} {'f':>9} {'z':>9} {'lat off':>9} {'wz':>7} {'ahead':>7} {'w_sn':>7}")
for r, vi in enumerate(order[:12]):
    print(f"  {r:>4} {vi:>7} {f[vi]:>9.4f} {zc2[vi]:>9.4f} {lp[vi]-lat0:>9.4f}"
          f" {wz[vi]:>7.3f} {ahead[vi]:>7.3f} {w_sn[vi]:>7.3f}")

# where would the frontmost point END UP at SNOUT=0?
f_after = f - (f - f_brow) * 1.0 * w_sn
print(f"\n  head forward extent  now {f[head_m].max():.4f}"
      f"   at --snout 0.00 -> {f_after[head_m].max():.4f}   (f_brow {f_brow:.4f})")
vi = int(hidx[np.argmax(f_after[hidx])])
print(f"  and the frontmost vertex THEN is {vi}: f {f[vi]:.4f} -> {f_after[vi]:.4f}, "
      f"z {zc2[vi]:.4f}, w_sn {w_sn[vi]:.3f}")

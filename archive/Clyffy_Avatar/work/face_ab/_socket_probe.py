"""READ-ONLY: where are the eye-socket creases, and does the muzzle fullness band reach them?

Runs eye_open's own crease/group detection on two meshes and prints each group's z centroid and
size, so the muzzle band's z extent can be compared against the sockets directly instead of
guessed at.
"""
import bpy, sys, os, math
import numpy as np
import bmesh

argv = sys.argv[sys.argv.index("--") + 1:]
SRC = os.path.abspath(argv[0])
FWD = 235.1

bpy.ops.wm.open_mainfile(filepath=SRC)
ob = max([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
me = ob.data
N = len(me.vertices)
co = np.empty((N, 3)); me.vertices.foreach_get("co", co.ravel())
a = math.radians(FWD)
fwd = np.array([math.sin(a), -math.cos(a), 0.0])
lat = np.array([-fwd[1], fwd[0], 0.0])
fp = co @ fwd
z = co[:, 2]
zmax = float(z.max())

gi = {g.name: g.index for g in ob.vertex_groups}
lipm = np.zeros(N, bool)
want = gi["op_lip_seam"]
for v in me.vertices:
    for g in v.groups:
        if g.group == want and g.weight > 0.5:
            lipm[v.index] = True
            break
z_lip = float(z[lipm].mean())
lp = co @ lat
lat0 = float(np.median(lp[z > z_lip]))


def width_at(zz, half=0.008):
    m = np.abs(z - zz) < half
    return float(np.ptp(lp[m])) if m.sum() >= 8 else 0.0


neck_zs = np.linspace(z_lip + 0.01 * (z.max() - z.min()), z_lip - 0.16 * (z.max() - z.min()), 120)
np_ = [(zz, width_at(zz)) for zz in neck_zs]
np_ = [(zz, w) for zz, w in np_ if w > 0]
NECK = min(np_, key=lambda t: t[1])[0]
hc = co[z > z_lip].mean(axis=0)

bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table()
bm.normal_update()
band_lo, band_hi = NECK + (zmax - NECK) * 0.35, NECK + (zmax - NECK) * 0.90
crease = []
for e in bm.edges:
    if len(e.link_faces) != 2:
        continue
    v0, v1 = e.verts[0].index, e.verts[1].index
    zm = (co[v0, 2] + co[v1, 2]) / 2
    if not (band_lo < zm < band_hi):
        continue
    if (fp[v0] + fp[v1]) / 2 < float(hc @ fwd):
        continue
    n0, n1 = e.link_faces[0].normal, e.link_faces[1].normal
    if n0.length <= 0 or n1.length <= 0:
        continue
    if math.degrees(n0.angle(n1)) > 28.0:
        crease.append(e)

adj = {}
for e in crease:
    v0, v1 = e.verts[0].index, e.verts[1].index
    adj.setdefault(v0, set()).add(v1); adj.setdefault(v1, set()).add(v0)
seen, groups = set(), []
for v in adj:
    if v in seen:
        continue
    stack, comp = [v], []
    while stack:
        x = stack.pop()
        if x in seen:
            continue
        seen.add(x); comp.append(x)
        stack.extend(adj[x])
    groups.append(comp)

print(f"\n=== {os.path.basename(os.path.dirname(SRC))}/{os.path.basename(SRC)}")
print(f"  crease band z {band_lo:.4f}..{band_hi:.4f}   crease edges {len(crease)}   groups {len(groups)}")
print(f"  {'size':>6} {'z centroid':>12} {'lat offset':>12} {'fwd':>10}")
for g in sorted(groups, key=len, reverse=True)[:8]:
    c = co[np.array(g)].mean(axis=0)
    print(f"  {len(g):>6} {c[2]:>12.4f} {float(c @ lat) - lat0:>12.4f} {float(c @ fwd):>10.4f}")

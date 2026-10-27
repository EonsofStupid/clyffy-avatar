"""READ-ONLY survey of everything the mouth work depends on. Writes no mesh.

    blender -b --python tools/mouth_survey.py -- <in.blend|fbx>

Answers, with numbers rather than assumptions:

  * is the object transform identity? (the old build's cavity was extruded 59 deg into
    the cheek because forward was a WORLD angle applied to LOCAL coords)
  * which way does the head face, derived TWO independent ways, printed and compared
  * are there UVs and a base-colour texture, and how scattered are the islands
  * does the texture carry a dark lip line, and how sharp is it
  * does the muzzle have an edge loop that follows the lip, or would one have to be made
  * how much room is there for a cavity: muzzle mass depth, and head thickness behind it

Nothing here decides anything. It prints what is true so the plan can be written against
measurements instead of memory.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hardfail  # noqa: F401  -- unhandled exceptions must exit non-zero
import bpy, bmesh, sys, os, math
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC = os.path.abspath(argv[0])
# Forward is SUPPLIED from the fixed-angle orbit (the face is dead-on at 090 in
# work/orbit2/), never derived. Both derivations are still printed below, precisely so the
# record shows what they would have claimed: the farthest-vertex one picks an EAR TIP and
# is 103 deg wrong. This is the same class of error as the facing detector that labelled a
# three-quarter front as "head_back".
FWD_DEG = float(argv[1]) if len(argv) > 1 else None

bpy.ops.wm.read_factory_settings(use_empty=True)
ext = os.path.splitext(SRC)[1].lower()
if ext == ".blend":
    bpy.ops.wm.open_mainfile(filepath=SRC)
elif ext == ".fbx":
    bpy.ops.import_scene.fbx(filepath=SRC)
else:
    bpy.ops.import_scene.gltf(filepath=SRC)

ob = max([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
me = ob.data
N = len(me.vertices)
print(f"\nmesh: {ob.name}  {N} verts / {len(me.polygons)} faces")

# ---------------------------------------------------------------- 1. transform state
loc = tuple(round(v, 4) for v in ob.location)
rot = tuple(round(math.degrees(v), 3) for v in ob.rotation_euler)
scl = tuple(round(v, 4) for v in ob.scale)
ident = max(abs(v) for v in rot) < 1e-3 and max(abs(v - 1) for v in scl) < 1e-4 \
    and max(abs(v) for v in loc) < 1e-4
print("\n[1] TRANSFORM")
print(f"  loc {loc}  rot_deg {rot}  scale {scl}")
print(f"  identity: {ident}   -> local coords {'ARE' if ident else 'are NOT'} world coords")

co = np.empty((N, 3)); me.vertices.foreach_get("co", co.ravel())
z = co[:, 2]; zlo, zhi = float(z.min()), float(z.max()); H = zhi - zlo
print(f"  bounds  x {co[:,0].min():+.4f}..{co[:,0].max():+.4f}"
      f"  y {co[:,1].min():+.4f}..{co[:,1].max():+.4f}"
      f"  z {zlo:+.4f}..{zhi:+.4f}   height {H:.4f}")

# ---------------------------------------------------------------- 2. facing, two ways
head_lo = zlo + 0.70 * H
hm = z > head_lo
hc = co[hm].mean(axis=0)
print("\n[2] FACING — two independent derivations, both printed, neither used as a label")

# (a) farthest head vertex from the head centroid in XY
d = co[hm, :2] - hc[:2]
r = np.hypot(d[:, 0], d[:, 1])
tip = d[int(np.argmax(r))]
a_tip = math.degrees(math.atan2(tip[0], -tip[1])) % 360.0
print(f"  (a) farthest head vert : {a_tip:7.2f} deg   (r={r.max():.4f})")

# (b) direction of maximum mass asymmetry: the muzzle is the only thing sticking out of
#     an otherwise roughly radial skull, so the centroid of the outer shell leans into it
outer = d[r > np.percentile(r, 90)]
mean_out = outer.mean(axis=0)
a_mass = math.degrees(math.atan2(mean_out[0], -mean_out[1])) % 360.0
print(f"  (b) outer-decile centroid: {a_mass:7.2f} deg")
delta = abs((a_tip - a_mass + 180) % 360 - 180)
print(f"  disagreement: {delta:.2f} deg  -> {'CONSISTENT' if delta < 15 else 'UNSTABLE, do not trust'}")
if FWD_DEG is None:
    print("  !! no forward supplied — falling back to (a). Every number below is then suspect.")
    FWD_DEG = a_tip
else:
    print(f"  USING SUPPLIED {FWD_DEG:.2f} deg from the fixed-angle orbit"
          f"   (derivation (a) is off by {abs((a_tip-FWD_DEG+180)%360-180):.1f} deg)")

FWD = math.radians(FWD_DEG)
fwd = np.array([math.sin(FWD), -math.cos(FWD), 0.0])
lat = np.array([-fwd[1], fwd[0], 0.0])

# ---------------------------------------------------------------- 3. UVs and texture
print("\n[3] UV + TEXTURE")
print(f"  uv layers: {[l.name for l in me.uv_layers]}")
img = None
for m in me.materials:
    if not m or not m.use_nodes:
        continue
    for l in m.node_tree.links:
        if l.to_socket.name == "Base Color" and l.from_node.type == "TEX_IMAGE":
            img = l.from_node.image
    print(f"  material {m.name!r}  base-colour image: {img.name if img else None}"
          f"  {tuple(img.size) if img else ''}")

if me.uv_layers:
    uvd = me.uv_layers.active.data
    uv = np.empty((len(uvd), 2)); uvd.foreach_get("uv", uv.ravel())
    print(f"  uv bbox {uv[:,0].min():.3f}..{uv[:,0].max():.3f} x "
          f"{uv[:,1].min():.3f}..{uv[:,1].max():.3f}")
    # island count via face-corner connectivity in UV space (a proxy: shared vert + same uv)
    bm = bmesh.new(); bm.from_mesh(me)
    lay = bm.loops.layers.uv.active
    seen, islands = set(), 0
    for f in bm.faces:
        if f.index in seen:
            continue
        islands += 1
        stack = [f]; seen.add(f.index)
        while stack:
            cur = stack.pop()
            for l in cur.loops:
                for lf in l.edge.link_faces:
                    if lf.index in seen:
                        continue
                    # same island only if the shared edge has matching uvs on both sides
                    shared = [v for v in l.edge.verts]
                    ok = True
                    for v in shared:
                        u1 = [ll[lay].uv for ll in cur.loops if ll.vert is v]
                        u2 = [ll[lay].uv for ll in lf.loops if ll.vert is v]
                        if not u1 or not u2 or (u1[0] - u2[0]).length > 1e-5:
                            ok = False
                    if ok:
                        seen.add(lf.index); stack.append(lf)
    print(f"  uv islands: {islands}")
    bm.free()

# ---------------------------------------------------------------- 4. lip line in texture
print("\n[4] LIP LINE IN THE TEXTURE")
if img is None:
    print("  no base-colour image — a texture-driven seam is NOT available")
else:
    W, Ht = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(Ht, W, 4)
    lum = 0.2126 * px[:, :, 0] + 0.7152 * px[:, :, 1] + 0.0722 * px[:, :, 2]
    # per-vertex luminance via its first loop uv
    vlum = np.full(N, np.nan)
    uvd = me.uv_layers.active.data
    for p in me.polygons:
        for li in p.loop_indices:
            vi = me.loops[li].vertex_index
            if not np.isnan(vlum[vi]):
                continue
            u, v = uvd[li].uv
            x = int(min(max(u % 1.0, 0), 0.999999) * (W - 1))
            y = int(min(max(v % 1.0, 0), 0.999999) * (Ht - 1))
            vlum[vi] = lum[y, x]
    proj = (co - hc) @ fwd
    front = hm & (proj > 0.20 * float(proj[hm].max()))
    fl = vlum[front]
    fl = fl[~np.isnan(fl)]
    print(f"  front-of-head verts: {front.sum()}   luminance "
          f"min {fl.min():.3f}  p05 {np.percentile(fl,5):.3f}  median {np.percentile(fl,50):.3f}"
          f"  max {fl.max():.3f}")
    for t in (0.06, 0.09, 0.11, 0.14, 0.18, 0.24):
        m = front & (vlum < t)
        if m.sum() == 0:
            print(f"  thresh {t:.2f}: 0")
            continue
        sel = co[m]
        print(f"  thresh {t:.2f}: {m.sum():4d} verts  "
              f"z {sel[:,2].min()-zlo:.4f}..{sel[:,2].max()-zlo:.4f} "
              f"({(sel[:,2].min()-zlo)/H*100:.1f}%..{(sel[:,2].max()-zlo)/H*100:.1f}% of height)  "
              f"lateral span {((sel-hc)@lat).min():+.4f}..{((sel-hc)@lat).max():+.4f}")

# ---------------------------------------------------------------- 5. muzzle topology
print("\n[5] MUZZLE TOPOLOGY")
bm = bmesh.new(); bm.from_mesh(me)
bm.verts.ensure_lookup_table()
proj = (co - hc) @ fwd
muz = hm & (proj > 0.25 * float(proj[hm].max())) & (z < hc[2])
print(f"  muzzle-region verts (front of head, below head centre): {muz.sum()}")
val = {}
for v in bm.verts:
    if muz[v.index]:
        n = len(v.link_edges)
        val[n] = val.get(n, 0) + 1
print(f"  valence histogram in the muzzle: {dict(sorted(val.items()))}")
tri = sum(1 for f in bm.faces if len(f.verts) == 3 and all(muz[v.index] for v in f.verts))
quad = sum(1 for f in bm.faces if len(f.verts) == 4 and all(muz[v.index] for v in f.verts))
ngon = sum(1 for f in bm.faces if len(f.verts) > 4 and all(muz[v.index] for v in f.verts))
print(f"  muzzle faces: {quad} quads, {tri} tris, {ngon} ngons")
bm.free()

# ---------------------------------------------------------------- 6. room for a cavity
print("\n[6] ROOM FOR A CAVITY")
lat_c = (co - hc) @ lat
band = hm & (np.abs(lat_c) < 0.05 * H)
if band.sum():
    p = proj[band]
    print(f"  midline head band: {band.sum()} verts, forward extent "
          f"{p.min():+.4f}..{p.max():+.4f}  (depth {p.max()-p.min():.4f} = {(p.max()-p.min())/H*100:.1f}% of height)")
    for frac in (0.30, 0.40, 0.50):
        zc = zlo + (0.70 + (1 - 0.70) * frac) * H
        sl = band & (np.abs(z - zc) < 0.01 * H)
        if sl.sum():
            print(f"    slice at {(zc-zlo)/H*100:.0f}% height: fwd {proj[sl].min():+.4f}..{proj[sl].max():+.4f}")
# ---------------------------------------------------------------- 7. is the lip GEOMETRY?
# The single most important question for the cut. If the lip exists as a crease in the mesh
# there is an edge chain to cut along and the boundary is smooth by construction. If it is
# only painted into the texture, the cut has to be projected onto a flat surface — which is
# exactly what produced the staircase boundary in the old build.
print("\n[7] IS THE LIP A CREASE IN THE GEOMETRY, OR ONLY PAINT?")
bm = bmesh.new(); bm.from_mesh(me)
bm.edges.ensure_lookup_table()
proj = (co - hc) @ fwd
lat_c = (co - hc) @ lat
front_lo = 0.35 * float(proj[hm].max())
cand = []
for e in bm.edges:
    if len(e.link_faces) != 2:
        continue
    i, j = e.verts[0].index, e.verts[1].index
    if not (hm[i] and hm[j]):
        continue
    if proj[i] < front_lo or proj[j] < front_lo:
        continue
    n1 = e.link_faces[0].normal; n2 = e.link_faces[1].normal
    ang = math.degrees(n1.angle(n2)) if n1.length > 0 and n2.length > 0 else 0.0
    if ang < 25.0:
        continue
    mid = (co[i] + co[j]) / 2.0
    # an edge lying ALONG the lip runs laterally: its direction is mostly +/-lat
    d = co[j] - co[i]
    dn = d / (np.linalg.norm(d) + 1e-12)
    lateralness = abs(float(dn @ lat))
    cand.append((ang, float((mid[2] - zlo) / H * 100.0), float((mid - hc) @ lat),
                 float((mid - hc) @ fwd), lateralness))
print(f"  front-of-muzzle edges with dihedral > 25 deg: {len(cand)}")
if cand:
    arr = np.array([[c[0], c[1], c[2], c[3], c[4]] for c in cand])
    lipish = arr[arr[:, 4] > 0.7]
    print(f"    of those, running LATERALLY (|dir.lat| > 0.7): {len(lipish)}")
    for lo, hi in ((60, 70), (70, 75), (75, 80), (80, 85), (85, 92)):
        s = arr[(arr[:, 1] >= lo) & (arr[:, 1] < hi)]
        sl = s[s[:, 4] > 0.7]
        if len(s):
            print(f"    height {lo:>2}-{hi:>2}%: {len(s):4d} crease edges, {len(sl):4d} lateral,"
                  f"  mean dihedral {s[:,0].mean():5.1f} deg,"
                  f"  lateral span {s[:,2].min():+.4f}..{s[:,2].max():+.4f}")
bm.free()

print("\nsurvey complete — nothing was modified")

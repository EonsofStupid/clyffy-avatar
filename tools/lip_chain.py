"""Is the lip crease a single clean edge chain, or a scatter of crease fragments?

    blender -b --python tools/lip_chain.py -- <in.blend> <fwd_deg> [dihedral_deg]

READ-ONLY. This is the question the whole mouth plan turns on. The previous build had no
lip crease at all, so its seam was picked from TEXTURE LUMINANCE per FACE, and the cut
boundary came out as a staircase of quad corners — which is what let the cavity poke
through the skin at the corners. If the crease here is one connected chain whose interior
vertices each have exactly two crease neighbours, the cut boundary is smooth by
construction and none of that can recur.

Reports, for the largest crease component in the muzzle band:
  * how many vertices and edges, and whether it is a path or a branching mess
  * degree histogram (2 = clean chain, 3+ = a junction the cut would have to resolve)
  * left/right symmetry of its extent
  * its height and forward position, so the cavity can be sized against it
"""
import bpy, bmesh, sys, os, math
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
SRC = os.path.abspath(argv[0])
FWD_DEG = float(argv[1])
DIH = float(argv[2]) if len(argv) > 2 else 25.0

bpy.ops.wm.open_mainfile(filepath=SRC)
ob = max([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
me = ob.data
N = len(me.vertices)
co = np.empty((N, 3)); me.vertices.foreach_get("co", co.ravel())
z = co[:, 2]; zlo, zhi = float(z.min()), float(z.max()); H = zhi - zlo
hm = z > zlo + 0.70 * H
hc = co[hm].mean(axis=0)

a = math.radians(FWD_DEG)
fwd = np.array([math.sin(a), -math.cos(a), 0.0])
lat = np.array([-fwd[1], fwd[0], 0.0])
proj = (co - hc) @ fwd
latc = (co - hc) @ lat

bm = bmesh.new(); bm.from_mesh(me)
bm.verts.ensure_lookup_table()

# crease edges anywhere on the head, forward of the head centre
adj = {}
edges = []
for e in bm.edges:
    if len(e.link_faces) != 2:
        continue
    i, j = e.verts[0].index, e.verts[1].index
    if not (hm[i] and hm[j]):
        continue
    if proj[i] <= 0 or proj[j] <= 0:
        continue
    n1, n2 = e.link_faces[0].normal, e.link_faces[1].normal
    if n1.length == 0 or n2.length == 0:
        continue
    if math.degrees(n1.angle(n2)) < DIH:
        continue
    edges.append((i, j))
    adj.setdefault(i, set()).add(j)
    adj.setdefault(j, set()).add(i)

print(f"crease edges (dihedral >= {DIH:.0f} deg, front of head): {len(edges)}  "
      f"over {len(adj)} vertices")

# connected components
seen, comps = set(), []
for s in adj:
    if s in seen:
        continue
    stack, c = [s], []
    seen.add(s)
    while stack:
        v = stack.pop(); c.append(v)
        for n in adj[v]:
            if n not in seen:
                seen.add(n); stack.append(n)
    comps.append(c)
comps.sort(key=len, reverse=True)
print(f"connected crease components: {len(comps)}   sizes {[len(c) for c in comps[:10]]}")

print("\nthe five largest, described by WHERE they are (no names, no detector):")
for k, c in enumerate(comps[:5]):
    p = co[c]
    print(f"  [{k}] {len(c):4d} verts   "
          f"height {(p[:,2].min()-zlo)/H*100:5.1f}..{(p[:,2].max()-zlo)/H*100:5.1f}%   "
          f"lateral {latc[c].min():+.4f}..{latc[c].max():+.4f}   "
          f"fwd {proj[c].min():+.4f}..{proj[c].max():+.4f}")

# THE LIP: the component that spans the widest laterally AND straddles the midline. The
# eye rims sit high and to one side; the nostrils are small and paired. Spanning the
# midline while being the widest is a property only the mouth has on this head.
best, best_w = None, -1
for c in comps:
    l = latc[c]
    if l.min() > -0.01 or l.max() < 0.01:      # must straddle the midline
        continue
    w = l.max() - l.min()
    if w > best_w:
        best, best_w = c, w
if best is None:
    print("\nNO midline-straddling crease component — the lip is NOT continuous across the "
          "front. A cut would have to bridge the gap, which is where staircases come from.")
    sys.exit(0)

print(f"\nWIDEST MIDLINE-STRADDLING COMPONENT: {len(best)} verts, lateral width {best_w:.4f} "
      f"({best_w/H*100:.1f}% of body height)")
p = co[best]
print(f"  height  {(p[:,2].min()-zlo)/H*100:.2f}..{(p[:,2].max()-zlo)/H*100:.2f}% of body height")
print(f"  z       {p[:,2].min():+.4f}..{p[:,2].max():+.4f}")
print(f"  lateral {latc[best].min():+.4f}..{latc[best].max():+.4f}")
print(f"  forward {proj[best].min():+.4f}..{proj[best].max():+.4f}")

sub = set(best)
deg = {}
for v in best:
    deg[v] = len([n for n in adj[v] if n in sub])
hist = {}
for d in deg.values():
    hist[d] = hist.get(d, 0) + 1
print(f"  degree histogram within the component: {dict(sorted(hist.items()))}")
ends = [v for v, d in deg.items() if d == 1]
junc = [v for v, d in deg.items() if d >= 3]
print(f"  endpoints (degree 1): {len(ends)}   junctions (degree 3+): {len(junc)}")
if len(junc) == 0 and len(ends) == 2:
    print("  -> a CLEAN OPEN PATH: corner to corner, no branching. Cut boundary is smooth "
          "by construction.")
elif len(junc) == 0 and len(ends) == 0:
    print("  -> a CLOSED LOOP.")
else:
    print(f"  -> BRANCHING. The {len(junc)} junction(s) must be resolved before this can be "
          "used as a cut path; a branch is a fork the cut cannot follow.")
    for v in junc[:12]:
        print(f"       junction at height {(co[v][2]-zlo)/H*100:5.2f}%  "
              f"lat {latc[v]:+.4f}  fwd {proj[v]:+.4f}  degree {deg[v]}")

# symmetry: the chain should mirror about lat = 0
L = latc[best]
print(f"\n  symmetry: {int((L < -1e-4).sum())} verts left, {int((L > 1e-4).sum())} right, "
      f"{int((np.abs(L) <= 1e-4).sum())} on the midline")
print(f"  extent   left {L.min():+.4f}  right {L.max():+.4f}  "
      f"imbalance {abs(abs(L.min())-abs(L.max()))/best_w*100:.2f}% of width")
bm.free()

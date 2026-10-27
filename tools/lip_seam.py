"""Compute a lip seam candidate and hand it to the operator PRE-SELECTED for correction.

    blender -b --python tools/lip_seam.py -- <clean.blend> <out.blend> <fwd_deg> [render_dir]

This is option 3 of the three offered: I propose, the operator corrects. The output .blend
opens with the seam already selected in Edit Mode, so he is nudging a starting point rather
than clicking from scratch. `seam_bake.py` still validates whatever comes back — this tool
gets no special trust for having produced it.

HOW THE PATH IS CHOSEN. Dijkstra between the two mouth corners over the real mesh edge graph,
with edge weight

    w = length * (1 + PEN * (1 - min(1, dihedral / FULL)))

so a hard crease edge costs its own length and a flat edge costs (1+PEN) times as much. The
path therefore follows the lip crease wherever one exists and takes the shortest bridge where
the crease is broken, instead of detouring up the branches at the pad edges.

WHY NOT SHORTEST PATH ALONG CREASE EDGES ONLY. The crease set is not connected along the lip
everywhere, and restricting to it forces detours through the junctions where the lip crease
meets the creases up the sides of the muzzle pad — which is precisely the branching this step
exists to eliminate.

A Dijkstra path is a simple path by construction: every interior vertex has degree 2 and there
are exactly two endpoints. It cannot come out branched. What it CAN get wrong is where the
corners land and whether it sags off the crease in the middle, which is what the operator is
looking at.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hardfail  # noqa: F401  -- unhandled exceptions must exit non-zero
import bpy, bmesh, sys, os, math, heapq
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = os.path.abspath(argv[0]), os.path.abspath(argv[1])
FWD_DEG = float(argv[2])
RENDER = os.path.abspath(argv[3]) if len(argv) > 3 else None
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)

# ---------------------------------------------------------------------------------------
# THE MOUTH CREASE IS SOFT. This is the correction that made this tool work, and it cost two
# wrong runs to find. At a 25 deg dihedral threshold the mouth line FRAGMENTS into components
# too small to identify, and the largest crease on the muzzle is the MUZZLE PAD OUTLINE — 343
# verts wrapping the sides and underside of the pad, not visible from the front at all. A
# render that painted every >25 deg edge red looked like it showed a continuous lip; it was
# showing fragments that happened to line up, plus the pad outline.
#
# Colouring each crease COMPONENT separately at 12 deg settles it: the mouth is one connected
# 232-vertex band spanning corner to corner across the front of the muzzle. See
# work/creasecomp12/comp_090.png.
#
# Two wrong runs are recorded here so they are not repeated:
#   run 1  no forward constraint  -> "corners" on the cheeks at fwd +0.012, path under the jaw
#                                    at 65-70% height with 17% of its edges on any crease
#   run 2  25 deg + a height band -> the band cut the pad-outline component in two and left a
#                                    14-vertex chin crease as the widest midline-straddler
DIH_COMP = 12.0   # threshold at which the mouth crease is one connected component
PEN = 10.0        # cost multiplier for a completely flat edge
BAND_LO, BAND_HI = 0.58, 0.95    # generous: the component test does the real work
FWD_FLOOR = 0.06

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
hfrac = (z - zlo) / H

# the region the seam may occupy: ON THE MUZZLE, in a generous band around the lip
allowed = (proj > FWD_FLOOR) & (hfrac > BAND_LO) & (hfrac < BAND_HI)
print(f"search region: {int(allowed.sum())} verts "
      f"(fwd > {FWD_FLOOR}, {BAND_LO*100:.0f}-{BAND_HI*100:.0f}% of body height)")

# ------------------------------------------------------------------ edges + dihedrals
bm = bmesh.new(); bm.from_mesh(me)
dih_of = {}
for e in bm.edges:
    i, j = e.verts[0].index, e.verts[1].index
    if not (allowed[i] and allowed[j]):
        continue
    if len(e.link_faces) == 2:
        n1, n2 = e.link_faces[0].normal, e.link_faces[1].normal
        d = math.degrees(n1.angle(n2)) if (n1.length and n2.length) else 0.0
    else:
        d = 0.0
    dih_of[tuple(sorted((i, j)))] = d
bm.free()
print(f"muzzle graph: {len(dih_of)} edges")

# ------------------------------------------------------------------ the two mouth corners
# Take the crease component that straddles the midline and is widest — measured earlier as the
# lip plus the branches climbing the pad edges — then keep only the part BELOW LIP_TOP, which
# is the lip proper. Its lateral extremes are the mouth corners.
#
# Two ways of doing this were wrong and are recorded so they are not retried:
#   * extremes of the whole crease component  -> lands at 82.8% height, up on the pad edges
#   * extremes of a height band alone         -> lands on the cheeks at fwd +0.01, behind the
#                                                muzzle, because the jowl fold is at the same
#                                                height and reaches further laterally
cadj = {}
for (i, j), d in dih_of.items():
    if d < DIH_COMP:
        continue
    cadj.setdefault(i, set()).add(j)
    cadj.setdefault(j, set()).add(i)
cseen, ccomps = set(), []
for s in cadj:
    if s in cseen:
        continue
    st, c = [s], []
    cseen.add(s)
    while st:
        v = st.pop(); c.append(v)
        for n in cadj[v]:
            if n not in cseen:
                cseen.add(n); st.append(n)
    ccomps.append(c)
ccomps.sort(key=len, reverse=True)

# WHICH COMPONENT IS THE MOUTH. It must straddle the midline and be wide — but so does the
# pad outline, and by width alone they are within 2% of each other (0.1969 vs 0.1922), which
# is far too thin a margin to decide on. The physical discriminator: the mouth is ON THE FRONT
# OF THE FACE, the pad outline WRAPS TO THE SIDES. Their forward reach differs by 50%
# (+0.2253 vs +0.1506), so pick by forward reach among the wide straddlers.
print("\ncrease components on the muzzle (straddling the midline, width > 0.08):")
cands = []
for c in ccomps:
    L = latc[c]
    if L.min() > -0.01 or L.max() < 0.01:
        continue
    if L.max() - L.min() < 0.08:
        continue
    cands.append(c)
    print(f"  {len(c):4d}v  h {hfrac[c].min()*100:5.2f}..{hfrac[c].max()*100:5.2f}%  "
          f"lat {L.min():+.4f}..{L.max():+.4f} (w {L.max()-L.min():.4f})  "
          f"fwd reach {proj[c].max():+.4f}")
assert cands, "no wide midline-straddling crease component on the muzzle"
best = max(cands, key=lambda c: proj[c].max())
bw = float(latc[best].max() - latc[best].min())
print(f"-> MOUTH = the {len(best)}-vertex component, forward reach {proj[best].max():+.4f}, "
      f"width {bw:.4f}")
cand = np.array(best, dtype=int)
left = int(cand[np.argmin(latc[cand])])
right = int(cand[np.argmax(latc[cand])])
for nm, v in (("left corner", left), ("right corner", right)):
    print(f"  {nm}: height {hfrac[v]*100:.2f}%  lat {latc[v]:+.4f}  fwd {proj[v]:+.4f}")

# ------------------------------------------------------------------ weighted graph
# Restricted to the mouth component, so the path CANNOT leave the mouth crease. Within it the
# band is 2-4 edges thick, so weight by dihedral as well as length to keep the path in the
# deepest part of the valley rather than hugging whichever side happens to be shorter.
cset = set(int(v) for v in best)
ds_comp = np.array([d for (i, j), d in dih_of.items() if i in cset and j in cset])
FULL = float(np.percentile(ds_comp, 75)) if len(ds_comp) else 20.0
print(f"  component edge dihedral: median {np.median(ds_comp):.1f}, p75 {FULL:.1f} deg "
      f"-> treating {FULL:.1f} deg as fully creased")

graph = {}
for (i, j), d in dih_of.items():
    inside = (i in cset) and (j in cset)
    L = float(np.linalg.norm(co[i] - co[j]))
    w = L * (1.0 + PEN * (1.0 - min(1.0, d / FULL)))
    if not inside:
        w *= 50.0        # allowed only as a last-resort bridge if the component is broken
    graph.setdefault(i, []).append((j, w))
    graph.setdefault(j, []).append((i, w))

# ------------------------------------------------------------------ Dijkstra
dist = {left: 0.0}
prev = {}
pq = [(0.0, left)]
seen = set()
while pq:
    d0, u = heapq.heappop(pq)
    if u in seen:
        continue
    seen.add(u)
    if u == right:
        break
    for v, w in graph.get(u, ()):
        nd = d0 + w
        if nd < dist.get(v, float("inf")):
            dist[v] = nd
            prev[v] = u
            heapq.heappush(pq, (nd, v))

assert right in dist, "no path between the corners inside the search region"
path = [right]
while path[-1] != left:
    path.append(prev[path[-1]])
path.reverse()
print(f"\npath: {len(path)} vertices, {len(path)-1} edges, cost {dist[right]:.4f}")

# ------------------------------------------------------------------ trim to the PAINTED mouth
# The geometric corners overshoot: the crease component includes a little of the pad's side
# edge, so the path's last few vertices climb up onto it, past where the mouth actually ends.
# The artwork is the authority on that — the mouth is PAINTED as a dark line and the pad is
# light pink, so texture luminance says where the mouth stops far more honestly than any
# geometric rule about where a crease "turns".
img = None
for mm in me.materials:
    if not mm or not mm.node_tree:
        continue
    for lnk in mm.node_tree.links:
        if lnk.to_socket.name == "Base Color" and lnk.from_node.type == "TEX_IMAGE":
            img = lnk.from_node.image
if img is not None:
    W, Ht = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(Ht, W, 4)
    lum2d = 0.2126 * px[:, :, 0] + 0.7152 * px[:, :, 1] + 0.0722 * px[:, :, 2]
    vlum = np.full(N, np.nan, dtype=np.float32)
    uvd = me.uv_layers.active.data
    want = set(int(v) for v in path)
    for pl in me.polygons:
        for li in pl.loop_indices:
            vi = me.loops[li].vertex_index
            if vi not in want or not np.isnan(vlum[vi]):
                continue
            u, vv = uvd[li].uv
            xx = int(min(max(u % 1.0, 0.0), 0.999999) * (W - 1))
            yy = int(min(max(vv % 1.0, 0.0), 0.999999) * (Ht - 1))
            vlum[vi] = lum2d[yy, xx]
    prof = np.array([vlum[v] for v in path], dtype=np.float32)
    good = prof[~np.isnan(prof)]
    CUT = float(np.percentile(good, 55)) if len(good) else 1.0
    print(f"\ntexture luminance along the path: min {np.nanmin(prof):.3f} "
          f"median {np.nanmedian(prof):.3f} max {np.nanmax(prof):.3f}; "
          f"trimming ends brighter than {CUT:.3f}")
    lo, hi = 0, len(path) - 1
    while lo < hi and (np.isnan(prof[lo]) or prof[lo] > CUT):
        lo += 1
    while hi > lo and (np.isnan(prof[hi]) or prof[hi] > CUT):
        hi -= 1
    if hi - lo >= 10 and (lo > 0 or hi < len(path) - 1):
        print(f"  trimmed {lo} vertices off the left end and "
              f"{len(path)-1-hi} off the right end")
        path = path[lo:hi + 1]
        print(f"  path now {len(path)} vertices, lateral "
              f"{latc[path].min():+.4f}..{latc[path].max():+.4f} "
              f"(width {latc[path].max()-latc[path].min():.4f})")
        imb2 = abs(abs(latc[path[0]]) - abs(latc[path[-1]]))
        print(f"  corner asymmetry after trim: {imb2:.4f} = {imb2/H*100:.2f}% of body height")
    else:
        print("  no trim applied")
else:
    print("\nno base-colour texture — cannot trim to the painted mouth")

pe = [tuple(sorted((path[k], path[k + 1]))) for k in range(len(path) - 1)]
ds = np.array([dih_of[e] for e in pe])
on_crease = int((ds >= 25.0).sum())
print(f"  edges lying on a real crease (>=25 deg): {on_crease}/{len(pe)} "
      f"= {on_crease/len(pe)*100:.1f}%")
print(f"  dihedral along the path: min {ds.min():.1f}  median {np.median(ds):.1f}  "
      f"max {ds.max():.1f} deg")
p = co[path]
print(f"  height  {hfrac[path].min()*100:.2f}..{hfrac[path].max()*100:.2f}% of body height")
print(f"  lateral {latc[path].min():+.4f}..{latc[path].max():+.4f}  "
      f"width {latc[path].max()-latc[path].min():.4f} "
      f"({(latc[path].max()-latc[path].min())/H*100:.1f}% of body height)")
print(f"  forward {proj[path].min():+.4f}..{proj[path].max():+.4f}")
# report the ACTUAL endpoints of the final path, not the pre-trim corners — the first version
# printed the untrimmed figures after trimming and understated nothing, but described a seam
# that no longer existed
e0, e1 = int(path[0]), int(path[-1])
imb = abs(abs(latc[e0]) - abs(latc[e1]))
print(f"  corner asymmetry: {latc[e0]:+.4f} and {latc[e1]:+.4f}  "
      f"imbalance {imb:.4f} = {imb/H*100:.2f}% of body height")
print(f"  corner heights: {hfrac[e0]*100:.2f}% and {hfrac[e1]*100:.2f}%  "
      f"(difference {abs(hfrac[e0]-hfrac[e1])*100:.2f}% of body height)")

# a simple path by construction — assert it anyway rather than assume
degc = {}
for i, j in pe:
    degc[i] = degc.get(i, 0) + 1
    degc[j] = degc.get(j, 0) + 1
ends = [v for v, d in degc.items() if d == 1]
junc = [v for v, d in degc.items() if d >= 3]
print(f"  endpoints {len(ends)}, junctions {len(junc)}  "
      f"-> {'clean open path' if len(ends) == 2 and not junc else 'NOT A CLEAN PATH'}")
assert len(ends) == 2 and not junc

# ------------------------------------------------------------------ save PRE-SELECTED
pset = set(pe)
for v in me.vertices:
    v.select = False
for pl in me.polygons:
    pl.select = False
ev = np.empty(len(me.edges) * 2, dtype=np.int32); me.edges.foreach_get("vertices", ev)
ev = ev.reshape(-1, 2)
nsel = 0
for k, (i, j) in enumerate(ev):
    on = tuple(sorted((int(i), int(j)))) in pset
    me.edges[k].select = on
    if on:
        me.vertices[int(i)].select = True
        me.vertices[int(j)].select = True
        nsel += 1
print(f"\nselected {nsel} edges in the output file")

ob.select_set(True)
bpy.context.view_layer.objects.active = ob
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"wrote {OUT}")

# ------------------------------------------------------------------ show it
if RENDER:
    os.makedirs(RENDER, exist_ok=True)
    mark = np.zeros(N, dtype=bool)
    mark[np.array(path, dtype=int)] = True
    if "seamcol" in me.color_attributes:
        me.color_attributes.remove(me.color_attributes["seamcol"])
    ca = me.color_attributes.new(name="seamcol", type="FLOAT_COLOR", domain="POINT")
    cols = np.zeros((N, 4), dtype=np.float32); cols[:, 3] = 1.0
    cols[~mark] = (0.62, 0.62, 0.62, 1.0)
    cols[mark] = (1.0, 0.0, 0.0, 1.0)
    ca.data.foreach_set("color", cols.ravel())

    # find the base-colour image BEFORE the material slots are replaced
    src_img = None
    for mm in me.materials:
        if not mm or not mm.node_tree:
            continue
        for lnk in mm.node_tree.links:
            if lnk.to_socket.name == "Base Color" and lnk.from_node.type == "TEX_IMAGE":
                src_img = lnk.from_node.image

    def flat_mat(name, over_texture):
        """Emission-only so nothing is hidden by shading. `over_texture` draws the seam on top
        of the painted skin, which is the only way to judge the seam against the mouth the
        artwork actually has — red on grey shows position but not agreement."""
        mt = bpy.data.materials.new(name); mt.use_nodes = True
        t = mt.node_tree
        for n in list(t.nodes):
            if n.type != "OUTPUT_MATERIAL":
                t.nodes.remove(n)
        vc = t.nodes.new("ShaderNodeVertexColor"); vc.layer_name = "seamcol"
        emn = t.nodes.new("ShaderNodeEmission")
        if over_texture and src_img is not None:
            tex = t.nodes.new("ShaderNodeTexImage"); tex.image = src_img
            sep = t.nodes.new("ShaderNodeSeparateColor")
            t.links.new(vc.outputs["Color"], sep.inputs["Color"])
            mix = t.nodes.new("ShaderNodeMix")
            mix.data_type = "RGBA"
            t.links.new(sep.outputs["Red"], mix.inputs["Factor"])
            t.links.new(tex.outputs["Color"], mix.inputs[6])     # A
            mix.inputs[7].default_value = (1.0, 0.0, 0.0, 1.0)   # B = red
            t.links.new(mix.outputs[2], emn.inputs["Color"])
        else:
            t.links.new(vc.outputs["Color"], emn.inputs["Color"])
        t.links.new(emn.outputs["Emission"], t.nodes["Material Output"].inputs["Surface"])
        return mt

    # seam marked 1.0 red / 0.0 elsewhere in the RED channel drives the mix factor
    cols[~mark] = (0.0, 0.0, 0.0, 1.0)
    cols[mark] = (1.0, 0.0, 0.0, 1.0)
    ca.data.foreach_set("color", cols.ravel())
    m_over = flat_mat("seam_over_tex", True)

    cols[~mark] = (0.62, 0.62, 0.62, 1.0)
    cols[mark] = (1.0, 0.0, 0.0, 1.0)
    m_plain = flat_mat("seam_plain", False)
    me.materials.clear(); me.materials.append(m_plain)

    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.view_settings.view_transform = "Standard"
    sc.render.resolution_x = sc.render.resolution_y = 1100
    w = bpy.data.worlds.new("W"); w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.55
    sc.world = w
    cd = bpy.data.cameras.new("C"); cam = bpy.data.objects.new("C", cd)
    sc.collection.objects.link(cam); sc.camera = cam
    cd.type = "ORTHO"; cd.ortho_scale = 0.26
    mc = co[path].mean(axis=0)
    for tag, mat, colset in (("seam", m_plain, "plain"), ("seamtex", m_over, "over")):
        if colset == "plain":
            cols[~mark] = (0.62, 0.62, 0.62, 1.0)
        else:
            cols[~mark] = (0.0, 0.0, 0.0, 1.0)
        cols[mark] = (1.0, 0.0, 0.0, 1.0)
        ca.data.foreach_set("color", cols.ravel())
        me.materials.clear(); me.materials.append(mat)
        for deg_ in (0, 45, 90, 135):
            t = math.radians(deg_)
            cam.location = (mc[0] + math.sin(t) * H * 3, mc[1] - math.cos(t) * H * 3, mc[2])
            cam.rotation_euler = (math.radians(90), 0, t)
            sc.render.filepath = os.path.join(RENDER, f"{tag}_{deg_:03d}.png")
            bpy.ops.render.render(write_still=True)
    print(f"wrote seam renders to {RENDER}")

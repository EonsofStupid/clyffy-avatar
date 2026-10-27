"""Bake the operator's hand-picked lip seam to a vertex group, and verify it is cuttable.

    blender -b --python tools/seam_bake.py -- <picked.blend> <clean.blend> <out.blend> <fwd_deg> [render_dir]

The selection is read from <picked.blend>, validated, and written as the vertex group
`op_lip_seam` on <clean.blend> — the clean mesh stays the source of truth, and only the
selection crosses over.

Vertex groups travel with geometry through edits. The previous build stored operator
selections as raw vertex INDICES in side .blend files, which forced every later step to
preserve indices exactly; that is why its mouth delete had to use FACES_ONLY, and why it left
67 wire edges and 20 loose verts inside the cavity.

WHAT IT REFUSES TO ACCEPT, and why each one matters for the cut:

  * a different mesh          — vertex count or positions moved, so the selection does not
                                describe this geometry any more
  * a branching selection     — a fork is a path the cut cannot follow; this is exactly what
                                the raw crease set does at the pad edges
  * a disconnected selection  — a gap means the cut would have to bridge it, and bridging is
                                where staircases come from
  * fewer than 2 endpoints    — a closed loop would cut the muzzle clean off

Everything it refuses is reported WITH LOCATIONS, all problems at once, so the selection can
be fixed in one pass instead of one round trip per fault.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hardfail  # noqa: F401  -- unhandled exceptions must exit non-zero
import bpy, bmesh, sys, os, math
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
PICKED = os.path.abspath(argv[0])
CLEAN = os.path.abspath(argv[1])
OUT = os.path.abspath(argv[2])
FWD_DEG = float(argv[3])
RENDER = os.path.abspath(argv[4]) if len(argv) > 4 else None
GROUP = "op_lip_seam"
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)


def load(path):
    bpy.ops.wm.open_mainfile(filepath=path)
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    o = max([x for x in bpy.data.objects if x.type == "MESH"], key=lambda x: len(x.data.vertices))
    return o, o.data


# ------------------------------------------------------------------ read the selection
ob, me = load(PICKED)
Np = len(me.vertices)
cop = np.empty((Np, 3)); me.vertices.foreach_get("co", cop.ravel())

esel = np.zeros(len(me.edges), dtype=bool)
me.edges.foreach_get("select", esel)
vsel = np.zeros(Np, dtype=bool)
me.vertices.foreach_get("select", vsel)
ev = np.empty(len(me.edges) * 2, dtype=np.int32)
me.edges.foreach_get("vertices", ev)
ev = ev.reshape(-1, 2)

sel_edges = [tuple(ev[i]) for i in np.where(esel)[0]]
if not sel_edges:
    # edge mode not used: fall back to edges whose BOTH ends are selected
    sel_edges = [tuple(e) for e in ev if vsel[e[0]] and vsel[e[1]]]
    print(f"no edges selected; derived {len(sel_edges)} edges from {int(vsel.sum())} "
          f"selected vertices")
print(f"picked file: {Np} verts, {int(vsel.sum())} selected verts, {len(sel_edges)} seam edges")

if not sel_edges:
    print("\nFAIL: nothing is selected in the picked file.")
    sys.exit(1)

# ------------------------------------------------------------------ same mesh?
_, mec = load(CLEAN)
Nc = len(mec.vertices)
coc = np.empty((Nc, 3)); mec.vertices.foreach_get("co", coc.ravel())
if Np != Nc:
    print(f"\nFAIL: vertex count differs — picked {Np}, clean {Nc}. The selection cannot be "
          "mapped. Re-pick on an unedited copy of the clean mesh.")
    sys.exit(1)
dev = float(np.abs(cop - coc).max())
print(f"geometry check: max vertex deviation from the clean mesh {dev:.3e}")
if dev > 1e-6:
    print(f"\nFAIL: the picked file's geometry was MODIFIED (max deviation {dev:.3e}). "
          "Selecting is fine; moving vertices is not. Re-pick without editing geometry.")
    sys.exit(1)

# ------------------------------------------------------------------ chain validation
adj = {}
for i, j in sel_edges:
    adj.setdefault(int(i), set()).add(int(j))
    adj.setdefault(int(j), set()).add(int(i))

z = coc[:, 2]; zlo, zhi = float(z.min()), float(z.max()); H = zhi - zlo
hm = z > zlo + 0.70 * H
hc = coc[hm].mean(axis=0)
a = math.radians(FWD_DEG)
fwd = np.array([math.sin(a), -math.cos(a), 0.0])
lat = np.array([-fwd[1], fwd[0], 0.0])
proj = (coc - hc) @ fwd
latc = (coc - hc) @ lat


def where(v):
    return (f"height {(coc[v][2]-zlo)/H*100:5.2f}%  lat {latc[v]:+.4f}  fwd {proj[v]:+.4f}")


problems = []

# connectivity
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
print(f"\nselection forms {len(comps)} connected piece(s), sizes {[len(c) for c in comps[:8]]}")
if len(comps) > 1:
    problems.append(f"{len(comps)} disconnected pieces — the seam must be ONE chain")
    for c in comps[1:6]:
        print(f"  stray piece of {len(c)} verts, first at {where(c[0])}")

chain = comps[0]
deg = {v: len(adj[v]) for v in chain}
hist = {}
for d in deg.values():
    hist[d] = hist.get(d, 0) + 1
print(f"degree histogram: {dict(sorted(hist.items()))}")

junc = [v for v, d in deg.items() if d >= 3]
ends = [v for v, d in deg.items() if d == 1]
if junc:
    problems.append(f"{len(junc)} branch junction(s) — the cut cannot follow a fork")
    print(f"\nBRANCHES ({len(junc)}), the cut cannot follow these:")
    for v in junc[:20]:
        print(f"  degree {deg[v]} at {where(v)}")
if len(ends) != 2:
    if len(ends) == 0:
        problems.append("the chain is a CLOSED LOOP — it would cut the muzzle off")
    else:
        problems.append(f"{len(ends)} endpoints, expected exactly 2 (the two mouth corners)")

print(f"\nchain: {len(chain)} verts, {sum(len(v) for v in adj.values())//2} edges, "
      f"{len(ends)} endpoint(s), {len(junc)} junction(s)")
p = coc[chain]
print(f"  height  {(p[:,2].min()-zlo)/H*100:.2f}..{(p[:,2].max()-zlo)/H*100:.2f}% of body height")
print(f"  lateral {latc[chain].min():+.4f}..{latc[chain].max():+.4f}"
      f"   width {latc[chain].max()-latc[chain].min():.4f}"
      f" ({(latc[chain].max()-latc[chain].min())/H*100:.1f}% of body height)")
print(f"  forward {proj[chain].min():+.4f}..{proj[chain].max():+.4f}")
for v in sorted(ends, key=lambda v: latc[v]):
    print(f"  ENDPOINT (mouth corner) at {where(v)}")
if len(ends) == 2:
    L = sorted(latc[v] for v in ends)
    imb = abs(abs(L[0]) - abs(L[1]))
    print(f"  corner asymmetry: left {L[0]:+.4f}, right {L[1]:+.4f}, "
          f"imbalance {imb:.4f} = {imb/H*100:.2f}% of body height")

if problems:
    print("\nFAIL — the selection is not a cuttable chain:")
    for pr in problems:
        print(f"  * {pr}")
    print("\nNothing was written. Fix the selection and re-run.")
    sys.exit(1)

# ------------------------------------------------------------------ bake onto the clean mesh
obc, mec = load(CLEAN)
vg = obc.vertex_groups.get(GROUP) or obc.vertex_groups.new(name=GROUP)
vg.add([int(v) for v in chain], 1.0, "REPLACE")
print(f"\nbaked vertex group {GROUP!r}: {len(chain)} vertices")

# ORDER, not just membership. A vertex group is a SET, and the split needs to know which pairs
# are actually consecutive: a chord — a mesh edge joining two seam vertices that are far apart
# along the chain — would otherwise be torn open too, unzipping the face somewhere it should
# stay welded. Walking the chain from one endpoint and storing the index makes the edge list
# exact and checkable.
chainset = set(chain)
order = {}
cur, prev_, k = ends[0], None, 0
while True:
    order[cur] = k
    k += 1
    nxts = [n for n in adj[cur] if n != prev_ and n in chainset and n not in order]
    if not nxts:
        break
    prev_, cur = cur, nxts[0]
assert len(order) == len(chain), \
    f"walk covered {len(order)} of {len(chain)} chain vertices — the chain is not a simple path"

ATTR = "op_lip_seam_i"
if ATTR in mec.attributes:
    mec.attributes.remove(mec.attributes[ATTR])
at = mec.attributes.new(name=ATTR, type="FLOAT", domain="POINT")
vals = np.full(len(mec.vertices), -1.0, dtype=np.float32)
for v, i in order.items():
    vals[v] = float(i)
at.data.foreach_set("value", vals)
print(f"baked order attribute {ATTR!r}: 0..{len(order)-1} along the chain, -1 elsewhere")
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"wrote {OUT}")

# ------------------------------------------------------------------ show it
if RENDER:
    os.makedirs(RENDER, exist_ok=True)
    N = len(mec.vertices)
    mark = np.zeros(N, dtype=bool)
    mark[np.array(chain, dtype=int)] = True
    if "seamcol" in mec.color_attributes:
        mec.color_attributes.remove(mec.color_attributes["seamcol"])
    ca = mec.color_attributes.new(name="seamcol", type="FLOAT_COLOR", domain="POINT")
    cols = np.zeros((N, 4), dtype=np.float32); cols[:, 3] = 1.0
    cols[~mark] = (0.62, 0.62, 0.62, 1.0)
    cols[mark] = (1.0, 0.0, 0.0, 1.0)
    ca.data.foreach_set("color", cols.ravel())

    m = bpy.data.materials.new("seammat"); m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    at = nt.nodes.new("ShaderNodeVertexColor"); at.layer_name = "seamcol"
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(at.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], nt.nodes["Material Output"].inputs["Surface"])
    mec.materials.clear(); mec.materials.append(m)

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
    mc = coc[chain].mean(axis=0)
    for deg_ in (0, 45, 90, 135):
        t = math.radians(deg_)
        cam.location = (mc[0] + math.sin(t) * H * 3, mc[1] - math.cos(t) * H * 3, mc[2])
        cam.rotation_euler = (math.radians(90), 0, t)
        sc.render.filepath = os.path.join(RENDER, f"seam_{deg_:03d}.png")
        bpy.ops.render.render(write_still=True)
    print(f"wrote seam renders to {RENDER}")

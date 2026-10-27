"""Is the crater REPAIRABLE, or is the geometry there destroyed?

    blender -b --python tools/crater_region.py -- <model> <fwd_deg>

`crater_probe.py` answers "how deep is the dent". That is the wrong question for deciding what to
do next. A dent in an intact quad grid can be pushed back out onto a fitted skull surface; a
region of crushed, folded, flipped faces cannot, and would have to be rebuilt or regenerated.

So this probe measures the QUALITY of the surface inside the crater, against the same head's
sound regions as the control — one function, both sides, per the project rules.

Reported for the crater set and for the sound back as a control:
  * face type mix (quads vs tris vs n-gons)   — is the grid still a grid
  * vertex valence histogram                  — poles/fans mean the grid was rebuilt, not bent
  * edge length + face area distribution       — crushed faces show up as a collapsed low tail
  * inward-facing normals                      — a fold, self-intersection or inverted patch
  * connected components + extent              — one dent, or shrapnel everywhere
"""
import bpy, bmesh, sys, os, math
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC = os.path.abspath(argv[0])
FWD_DEG = float(argv[1])
INSET_T = float(argv[2]) if len(argv) > 2 else 0.10

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
head_mask = z > zlo + 0.72 * band
head = co[head_mask]
hc = head.mean(axis=0)

a = math.radians(FWD_DEG)
fwd = np.array([math.sin(a), -math.cos(a), 0.0])
back = -fwd

# --- reference skull line: convex hull of the head band --------------------------------------
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

# --- classify every head-band vertex ----------------------------------------------------------
idx_head = np.nonzero(head_mask)[0]
rel = co[idx_head] - hc
facing_back = (rel @ back) > 0.15 * np.linalg.norm(rel, axis=1)   # rear hemisphere only

inset = np.zeros(len(idx_head))
for i, vi in enumerate(idx_head):
    ok, loc, nor, _ = hull.closest_point_on_mesh(Vector(co[vi].tolist()))
    inset[i] = (Vector(co[vi].tolist()) - loc).length if ok else 0.0

crater_v = set(int(idx_head[i]) for i in range(len(idx_head))
               if facing_back[i] and inset[i] > INSET_T)
sound_v = set(int(idx_head[i]) for i in range(len(idx_head))
              if facing_back[i] and inset[i] <= 0.03)

print(f"\n=== {os.path.basename(SRC)}  fwd {FWD_DEG:.0f}  inset threshold {INSET_T:.2f} ===")
print(f"head band z {head[:,2].min():.3f}..{head[:,2].max():.3f}   verts in band {len(idx_head)}")
print(f"rear-hemisphere verts {int(facing_back.sum())}")
print(f"  CRATER (inset > {INSET_T:.2f}): {len(crater_v)}")
print(f"  SOUND  (inset <= 0.03)      : {len(sound_v)}   <- control")

bm = bmesh.new()
bm.from_mesh(ob.data)
bm.verts.ensure_lookup_table()
bm.faces.ensure_lookup_table()


def report(name, vset):
    if not vset:
        print(f"\n-- {name}: empty")
        return
    faces = [f for f in bm.faces if all(v.index in vset for v in f.verts)]
    if not faces:
        print(f"\n-- {name}: no faces fully inside the set")
        return
    sides = {}
    for f in faces:
        sides[len(f.verts)] = sides.get(len(f.verts), 0) + 1
    quads = sides.get(4, 0)
    areas = np.array([f.calc_area() for f in faces])
    edges = set()
    for f in faces:
        for e in f.edges:
            edges.add(e)
    elen = np.array([e.calc_length() for e in edges])

    # a fold or inverted patch: face normal pointing back toward the head centre
    outward = 0
    for f in faces:
        c = (M @ f.calc_center_median())
        n = (M.to_3x3() @ f.normal).normalized()
        if (Vector((c.x - hc[0], c.y - hc[1], c.z - hc[2]))).normalized().dot(n) > 0:
            outward += 1
    inward = len(faces) - outward

    val = {}
    for vi in vset:
        d = len(bm.verts[vi].link_edges)
        val[d] = val.get(d, 0) + 1

    # connected components over the vertex set
    seen, comps = set(), []
    for vi in vset:
        if vi in seen:
            continue
        stack, cur = [vi], 0
        seen.add(vi)
        while stack:
            k = stack.pop(); cur += 1
            for e in bm.verts[k].link_edges:
                o = e.other_vert(bm.verts[k]).index
                if o in vset and o not in seen:
                    seen.add(o); stack.append(o)
        comps.append(cur)
    comps.sort(reverse=True)

    print(f"\n-- {name}: {len(vset)} verts, {len(faces)} faces")
    print(f"   face mix        {dict(sorted(sides.items()))}   quads {quads/len(faces)*100:.1f}%")
    print(f"   valence         {dict(sorted(val.items()))}")
    print(f"   edge length     median {np.median(elen):.5f}  p05 {np.percentile(elen,5):.5f}  p95 {np.percentile(elen,95):.5f}")
    print(f"   face area       median {np.median(areas):.7f}  p05 {np.percentile(areas,5):.7f}  min {areas.min():.7f}")
    print(f"   normals facing INWARD (folds): {inward} of {len(faces)}  ({inward/len(faces)*100:.1f}%)")
    print(f"   components      {len(comps)}  sizes {comps[:8]}")


report("CRATER", crater_v)
report("SOUND back (control)", sound_v)
bm.free()

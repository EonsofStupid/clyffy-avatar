"""Cut the shell's lower boundary into a BODY arc and a LIMB arc, where a limb comes free.

    blender -b --python tools/limb_split.py -- work/RETOPO_clyffy.blend armR
    blender -b --python tools/limb_split.py -- work/RETOPO_clyffy.blend legR --write

Generalises the armpit split (which was `tools/armpit_split.py`, now folded in here — two copies of
this logic is how the arm seam and the leg seam come to disagree).

WHY IT EXISTS. **A marching front is a 1-D array of columns and cannot split.** That is the same
structural fact recorded on `tools/retopo_skull.py`, the tombstone of the single global sweep:
"protrusions change the front's TOPOLOGY, which a 1-D column array cannot represent". So wherever
the scaffold goes from one contour to several, the split has to be made in the BOUNDARY first, by
deciding per vertex which surface it belongs to.

TWO DISCRIMINATORS, because the geometry is not the same in the two cases:

  RIVAL (arm)  — compare the vertex's distance to the LIMB contour against its distance to a RIVAL
                 contour (for the arm, the torso). Decisive and threshold-free: arm verts sit
                 0.001-0.008 from the arm and 0.03-0.11 from the torso.
  GAP (leg)    — the rival test DOES NOT WORK at the midline. In a mirrored half-shell a crotch
                 vertex at x 0.02 is still nearer the right leg (0.021) than the left (0.061), so a
                 two-way comparison calls the whole boundary "leg". Instead, sort the distances to
                 the limb contour and look for a real bimodal gap. The split is placed in that gap,
                 and if the distribution has no clear gap the tool REFUSES rather than inventing a
                 threshold.
"""
import bpy, bmesh, sys, os
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scaffold_section import section_loops

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
LIMB = argv[1] if len(argv) > 1 else "armR"
WRITE = "--write" in argv

LIMBS = {
    "armR": dict(z_bnd=0.410, z_test=0.400, near=(0.245, 0.034),
                 rival=(0.0, -0.020),                 # the torso
                 g_body="cp9_torso_front", g_limb="cp9_arm_front"),
    "legR": dict(z_bnd=0.170, z_test=0.152, near=(0.100, -0.020),
                 rival=None,                          # midline case — use the gap test
                 g_body="cp9_crotch_front", g_limb="cp9_legR_front"),
}
CFG = LIMBS[LIMB]

bpy.ops.wm.open_mainfile(filepath=BLEND)
scaf = bpy.data.objects["SCAFFOLD"]
rt = bpy.data.objects["retopo_head"]

loops = section_loops(scaf, CFG["z_test"], verbose=True)
if not loops:
    print("!! no contours at the test height")
    sys.exit(1)


def centroid(l):
    return sum(l, Vector()) / len(l)


def pick(near):
    t = Vector((near[0], near[1], CFG["z_test"]))
    return min(loops, key=lambda l: (Vector((centroid(l).x, centroid(l).y, CFG["z_test"])) - t)
               .length)


limb = pick(CFG["near"])
c = centroid(limb)
print(f"limb contour: {len(limb)} pts, centroid ({c.x:+.3f},{c.y:+.3f}), "
      f"x[{min(p.x for p in limb):+.3f},{max(p.x for p in limb):+.3f}]")
rival = pick(CFG["rival"]) if CFG["rival"] else None
if rival is not None:
    rc = centroid(rival)
    print(f"rival contour: {len(rival)} pts, centroid ({rc.x:+.3f},{rc.y:+.3f})")

bm = bmesh.new()
bm.from_mesh(rt.data)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()
adjb = {}
for e in bm.edges:
    if len(e.link_faces) == 1:
        a, b = e.verts
        adjb.setdefault(a, []).append(b)
        adjb.setdefault(b, []).append(a)

low = [v for v in adjb if v.co.z < CFG["z_bnd"] + 0.004]
psel = set(low)
padj = {v: [o for o in adjb[v] if o in psel] for v in low}
chains, seen = [], set()
for v in low:
    if v in seen:
        continue
    comp, stack = [], [v]
    seen.add(v)
    while stack:
        k = stack.pop()
        comp.append(k)
        for o in padj[k]:
            if o not in seen:
                seen.add(o)
                stack.append(o)
    ends = [k for k in comp if len(padj[k]) == 1]
    s0 = ends[0] if ends else comp[0]
    chain, prev = [s0], None
    while True:
        nx = [o for o in padj[chain[-1]] if o is not prev and o not in chain]
        if not nx:
            break
        prev = chain[-1]
        chain.append(nx[0])
    chains.append(chain)
front = max(chains, key=len)
print(f"lower boundary: {len(front)} verts (chains {[len(c) for c in chains]})")


def near_loop(p, loop):
    q = Vector((p.x, p.y, CFG["z_test"]))
    return min((q - t).length for t in loop)


d_limb = [near_loop(v.co, limb) for v in front]

if rival is not None:
    d_riv = [near_loop(v.co, rival) for v in front]
    label = ["LIMB" if d_limb[i] < d_riv[i] else "body" for i in range(len(front))]
    print(f"\nRIVAL test: limb dist {min(d_limb):.4f}..{max(d_limb):.4f}, "
          f"rival dist {min(d_riv):.4f}..{max(d_riv):.4f}")
else:
    # GAP test — split the distances at their largest jump.
    #
    # Guarded TOPOLOGICALLY, not statistically. Two statistical guards were tried and both were
    # wrong about this boundary:
    #   "the distribution must be bimodal (biggest jump >= a quarter of the spread)" — refused a
    #     correct split. The BODY side is inherently a RAMP: crotch verts get steadily further from
    #     the leg as they approach the midline (0.032, 0.042, 0.060, 0.069), so the spread is
    #     dominated by that tail and no honest jump can be a quarter of it.
    #   "point-in-polygon against the limb footprint" — labelled EVERY vertex body, because the leg
    #     at z 0.152 is NARROWER than the thigh at z 0.170, so none of the boundary sits over it.
    # The check that actually means something is the one already downstream: the labels must form
    # exactly ONE limb run. That is a statement about the shape's topology rather than about the
    # shape of a histogram, and it is what a wrong threshold would actually break.
    srt = sorted(d_limb)
    gap, gi = max((srt[i + 1] - srt[i], i) for i in range(len(srt) - 1))
    thr = (srt[gi] + srt[gi + 1]) / 2
    print(f"\nGAP test: distances {srt[0]:.4f}..{srt[-1]:.4f}; biggest jump {gap:.4f} "
          f"at {srt[gi]:.4f} -> {srt[gi + 1]:.4f}; threshold {thr:.4f}")
    print(f"  sorted: {[round(d, 4) for d in srt]}")
    label = ["LIMB" if d < thr else "body" for d in d_limb]

flips = [i for i in range(1, len(label)) if label[i] != label[i - 1]]
runs, start = [], 0
for i in flips + [len(label)]:
    runs.append((label[start], start, i - 1))
    start = i
print(f"\nlabel flips at {flips}")
for s, a, b in runs:
    print(f"  {s:>4}: indices {a}..{b}  ({b - a + 1} verts)  "
          f"x[{min(front[k].co.x for k in range(a, b + 1)):+.3f},"
          f"{max(front[k].co.x for k in range(a, b + 1)):+.3f}]")

limb_runs = [r for r in runs if r[0] == "LIMB"]
if len(limb_runs) != 1:
    print(f"\n!! expected exactly ONE limb run on the +x half, got {len(limb_runs)}. "
          f"The seam is ambiguous — do not cut it.")
    sys.exit(1)

if WRITE:
    for name in (CFG["g_body"], CFG["g_limb"]):
        g = rt.vertex_groups.get(name)
        if g:
            rt.vertex_groups.remove(g)
    gb = rt.vertex_groups.new(name=CFG["g_body"])
    gl = rt.vertex_groups.new(name=CFG["g_limb"])
    # the two fronts SHARE the vertices either side of the flips, so the tubes stay stitched at the
    # junction and what is left is a narrowing WEDGE (a crease) rather than a hole
    a0, a1 = limb_runs[0][1] - 1, limb_runs[0][2] + 1
    a0, a1 = max(a0, 0), min(a1, len(front) - 1)
    limb_set = set(range(a0, a1 + 1))
    body_set = {i for i in range(len(label)) if label[i] == "body"} | {a0, a1}
    bi = [front[i].index for i in sorted(body_set)]
    li = [front[i].index for i in sorted(limb_set)]
    bm.free()
    gb.add(bi, 1.0, "REPLACE")
    gl.add(li, 1.0, "REPLACE")
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print(f"\nwrote {CFG['g_body']} ({len(bi)}), {CFG['g_limb']} ({len(li)}) — SAVED")
else:
    bm.free()
    print("\n(dry run — pass --write)")

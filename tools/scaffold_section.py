"""Exact horizontal sections of the scaffold. Shared by the ring builder and the armpit split.

Not a script — imported.

Two consumers need the same answer to "what are the contours at height z", and they must not drift:
`body_rings.py` resamples a contour into a capture ring, and `armpit_split.py` decides whether a
boundary vertex belongs to the torso or to the arm. If those two disagreed by even one contour the
seam would be cut in the wrong place.

The method and the two things that broke it are recorded in `body_rings.py`; the short version is
that ordering by angle assumes a star-shaped contour, greedy nearest-neighbour shortcuts across a
notch, and the scaffold is glTF so its faces share no edges until it is welded.
"""
import bmesh


def section_loops(scaf, z, verbose=False):
    """Closed contours of `scaf` at height z, each an ordered list of points.

    Chained through FACE TOPOLOGY: a plane cuts each face in exactly one segment, so the crossing
    points of a face's two crossing edges are connected by definition. No threshold, no heuristic,
    and it cannot shortcut across a notch the way a proximity rule can.
    """
    bm = bmesh.new()
    bm.from_mesh(scaf.data)
    bm.transform(scaf.matrix_world)
    # WELD FIRST — glTF splits vertices at every UV seam, so adjacent faces do not share edges and
    # there is nothing to chain: 728 crossing points came out as 264 fragments of 5-9 points.
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bm.edges.ensure_lookup_table()

    pt = {}
    for e in bm.edges:
        a, b = e.verts[0].co, e.verts[1].co
        if (a.z - z) * (b.z - z) < 0:
            pt[e.index] = a.lerp(b, (z - a.z) / (b.z - a.z))
    adj, skipped = {}, 0
    for f in bm.faces:
        ce = [e.index for e in f.edges if e.index in pt]
        if len(ce) == 2:
            adj.setdefault(ce[0], []).append(ce[1])
            adj.setdefault(ce[1], []).append(ce[0])
        elif len(ce) > 2:
            skipped += 1
    loops, seen = [], set()
    for s in adj:
        if s in seen:
            continue
        chain, cur, prev = [s], s, None
        seen.add(s)
        while True:
            nxt = [o for o in adj[cur] if o != prev and o not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            seen.add(cur)
            chain.append(cur)
        loops.append([pt[i] for i in chain])
    bm.free()
    if verbose:
        sizes = sorted((len(l) for l in loops), reverse=True)
        print(f"    z {z:.3f}: {len(pt)} crossing pts, {len(loops)} loops, largest {sizes[:4]}"
              + (f", {skipped} faces >2 crossings" if skipped else ""))
    return loops


def classify_loops(loops, min_arm=40, max_arm=320):
    """(torso, arms) — the torso is the biggest loop; arms are the mid-sized ones off the midline.

    Size is the discriminator because it is robust: at z 0.400 the torso is 535 points and each arm
    is ~143. The tiny loops (3-11 points) that appear near z 0.41-0.47 are sleeve-hem and trim
    slivers, not limbs, and must not be mistaken for one.
    """
    if not loops:
        return None, []
    torso = max(loops, key=len)
    arms = [l for l in loops if l is not torso and min_arm <= len(l) <= max_arm]
    arms.sort(key=lambda l: -max(p.x for p in l))
    return torso, arms

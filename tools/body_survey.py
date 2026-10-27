"""What is actually DOWN THERE — the scaffold below the neck, measured before anything is built.

    blender -b --python tools/body_survey.py -- work/RETOPO_clyffy.blend

Every body region's parameters (where the front sits, which way it marches, how many rows) has to
come from the scaffold, not from a guess. Two questions have to be answered with numbers before a
single shoulder vert is placed:

  1. WHERE DOES THE ARM SEPARATE FROM THE TORSO, if it ever does? Measured on the old v2 base the
     answer was NOWHERE — no lateral gap at any height from 40% to 84% of body height. That is why
     the arms must be their own marched regions. But "march the arm as its own region off a
     shoulder ring" still needs a shoulder ring, and the ring has to go where the arm actually
     leaves the torso. If the cross-section splits into three components at some height, that
     height IS the answer and no art is needed to find it.
  2. WHERE IS THE RETOPO SHELL'S LOWER EDGE right now — the front the shoulders march off.

Horizontal cross-sections, single-linkage clustered in the XY plane. A cluster is a closed contour;
3 clusters = torso + 2 arms, 1 cluster = fused. Read-only: nothing is written to the blend.
"""
import bpy, bmesh, sys, os, math
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
bpy.ops.wm.open_mainfile(filepath=BLEND)
scaf = bpy.data.objects["SCAFFOLD"]
rt = bpy.data.objects["retopo_head"]

bm = bmesh.new()
bm.from_mesh(scaf.data)
bm.transform(scaf.matrix_world)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()

zs = [v.co.z for v in bm.verts]
xs = [v.co.x for v in bm.verts]
ys = [v.co.y for v in bm.verts]
print(f"SCAFFOLD: {len(bm.verts)} verts, {len(bm.faces)} faces")
print(f"  x [{min(xs):+.4f} .. {max(xs):+.4f}]   y [{min(ys):+.4f} .. {max(ys):+.4f}]   "
      f"z [{min(zs):+.4f} .. {max(zs):+.4f}]")
Z0, Z1 = min(zs), max(zs)
print(f"  total height {Z1 - Z0:.4f}")


def section(z):
    """points where scaffold edges cross the plane z"""
    pts = []
    for e in bm.edges:
        a, b = e.verts[0].co, e.verts[1].co
        if (a.z - z) * (b.z - z) < 0:
            t = (z - a.z) / (b.z - a.z)
            pts.append(a.lerp(b, t))
    return pts


def cluster(pts, thr):
    """single-linkage in XY — separate contours are separate clusters"""
    unassigned = list(range(len(pts)))
    out = []
    while unassigned:
        seed = unassigned.pop()
        comp, stack = [seed], [seed]
        while stack:
            k = stack.pop()
            near = [j for j in unassigned
                    if (pts[j].xy - pts[k].xy).length < thr]
            for j in near:
                unassigned.remove(j)
                comp.append(j)
                stack.append(j)
        out.append([pts[i] for i in comp])
    return out


# ---- the retopo shell's open lower edge — the front the shoulders march off ---------------------
bmr = bmesh.new()
bmr.from_mesh(rt.data)
bmr.edges.ensure_lookup_table()
adj = {}
for e in bmr.edges:
    if len(e.link_faces) == 1:
        a, b = e.verts
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
seen, comps = set(), []
for v in adj:
    if v in seen:
        continue
    stack, comp = [v], []
    seen.add(v)
    while stack:
        k = stack.pop()
        comp.append(k)
        for o in adj[k]:
            if o not in seen:
                seen.add(o)
                stack.append(o)
    comps.append(comp)
comps.sort(key=len, reverse=True)
print(f"\nRETOPO SHELL: {len(rt.data.polygons)} faces, {len(comps)} open boundary components")
for c in comps:
    cz = [v.co.z for v in c]
    cx = [v.co.x for v in c]
    cy = [v.co.y for v in c]
    print(f"  {len(c):3d} verts  x[{min(cx):+.3f},{max(cx):+.3f}] "
          f"y[{min(cy):+.3f},{max(cy):+.3f}] z[{min(cz):+.3f},{max(cz):+.3f}]")
low = min(comps, key=lambda c: sum(v.co.z for v in c) / len(c))
lz = [v.co.z for v in low]
print(f"  LOWEST component = {len(low)} verts, z [{min(lz):+.4f} .. {max(lz):+.4f}] "
      f"(mean {sum(lz) / len(lz):+.4f}) — this is the front for the shoulders")
bmr.free()

# ---- cross-sections from the shell's lower edge down to the feet -------------------------------
print("\nCROSS-SECTIONS (single-linkage clustered in XY; 3 clusters = torso + 2 free arms)")
print(f"{'z':>8} {'%h':>5} {'n':>3}  {'clusters: x-extent (cx) | width x depth':<58}")
z_from = argv[argv.index("--from") + 1] if "--from" in argv else None
z_to = argv[argv.index("--to") + 1] if "--to" in argv else None
top = float(z_from) if z_from else min(lz)
bot = float(z_to) if z_to else Z0
step = (top - bot) / 44.0
z = top
rows = []
while z > bot + step * 0.5:
    pts = section(z)
    if not pts:
        z -= step
        continue
    cl = cluster(pts, 0.020)
    cl = [c for c in cl if len(c) >= 4]
    cl.sort(key=lambda c: -sum(p.x for p in c) / len(c))
    desc = []
    for c in cl:
        cxs = [p.x for p in c]
        cys = [p.y for p in c]
        desc.append(f"[{min(cxs):+.3f},{max(cxs):+.3f}] {max(cxs) - min(cxs):.3f}x"
                    f"{max(cys) - min(cys):.3f}")
    pct = 100.0 * (z - Z0) / (Z1 - Z0)
    print(f"{z:+8.4f} {pct:5.1f} {len(cl):3d}  {'  '.join(desc[:4]):<58}")
    rows.append((z, len(cl), cl))
    z -= step
bm.free()

splits = [r for r in rows if r[1] >= 3]
print()
if splits:
    hi = splits[0]
    print(f"ARMS SEPARATE AT z = {hi[0]:+.4f} — the cross-section becomes {hi[1]} contours there.")
    print(f"  {len(splits)} of {len(rows)} sampled heights show a free arm.")
    print("  A shoulder ring placed just ABOVE this height has a real gap to march into.")
else:
    print("ARMS NEVER SEPARATE at any sampled height — the scaffold's arms are FUSED to the")
    print("  torso, exactly as measured on v2. There is no gap to find and no ring to place on")
    print("  one. The arm must be marched as its own region from a ring we DECLARE on the")
    print("  shoulder, and the shoulder region must stop at that ring rather than run into it.")

# ---- look at it ---------------------------------------------------------------------------------
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"; sh.color_type = "OBJECT"
sh.show_cavity = True; sh.cavity_type = "BOTH"
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x = sc.render.resolution_y = 1000
scaf.color = (0.62, 0.62, 0.64, 1.0)
rt.color = (0.95, 0.35, 0.10, 1.0)
rt.show_wire = False
for o in bpy.data.objects:
    if o.name.startswith("vis_") or o.type == "EMPTY":
        o.hide_render = True
w = bpy.data.worlds.new("WB"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.40, 0.44, 0.41, 1)
sc.world = w
cd = bpy.data.cameras.new("CB"); cam = bpy.data.objects.new("CB", cd)
sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"
cd.ortho_scale = (Z1 - Z0) * 1.15
cd.clip_start = 0.001; cd.clip_end = 100.0
ctr = Vector((0.0, (min(ys) + max(ys)) / 2, (Z0 + Z1) / 2))
OUT = os.path.join(os.path.dirname(BLEND), "body_survey")
os.makedirs(OUT, exist_ok=True)
for deg in (0, 45, 90, 180):
    a = math.radians(deg)
    cam.location = (ctr.x + math.sin(a) * 3, ctr.y - math.cos(a) * 3, ctr.z)
    cam.rotation_euler = (math.radians(90), 0, a)
    sc.render.filepath = os.path.join(OUT, f"body_{deg:03d}.png")
    bpy.ops.render.render(write_still=True)
print(f"\nrenders -> {OUT}")

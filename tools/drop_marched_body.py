"""Delete the marched body from the shell, keeping the approved head and its collar.

    blender -b --python tools/drop_marched_body.py -- work/RETOPO_clyffy.blend --write

The marched body lost the scaffold's form — faceted slab arms, stepped shoulders, a terraced torso.
Operator, seeing it: *"the back of it's awful, the arms are awful ... he went backwards."* It is
replaced by `clyffy_body`, one voxel remesh of the scaffold's body, which is the method that held
its shape everywhere it was used here (the ear at CP8).

KEEPS `cp9_neck`. That region is a short clean tube from the head's neck ring down to the collar
ring at z 0.630, it did not degrade, and it is what gives the head a tidy edge to meet the body at.
Everything below it goes.

The head itself — CP1 through CP10, the lip seam the operator approved by eye — is untouched.
"""
import bpy, bmesh, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import retopo_gate as gate

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND = os.path.abspath(argv[0])
WRITE = "--write" in argv
bpy.ops.wm.open_mainfile(filepath=BLEND)
scaf = bpy.data.objects["SCAFFOLD"]
rt = bpy.data.objects["retopo_head"]

DROP = ["cp9_shoulders", "cp9_chest", "cp9_torso", "cp9_hip", "cp9_thigh",
        "cp9_armR", "cp9_legR_upper", "cp9_legR_lower", "cp9_hoofR", "cp9_crotch_fill",
        # the seam tags those regions were marched from
        "cp9_torso_front", "cp9_arm_front", "cp9_crotch_front", "cp9_legR_front"]
KEEP = "cp9_neck"

BEFORE = gate.survey(rt, scaf)
print(f"before: {BEFORE['faces']} faces, loops {BEFORE['loops']}, "
      f"apertures {BEFORE['apertures']}")

idx = {rt.vertex_groups[g].index for g in DROP if rt.vertex_groups.get(g)}
print(f"dropping {len(idx)} vertex groups, keeping '{KEEP}'")

bm = bmesh.new()
bm.from_mesh(rt.data)
bm.verts.ensure_lookup_table()
dl = bm.verts.layers.deform.verify()
keep_i = rt.vertex_groups[KEEP].index if rt.vertex_groups.get(KEEP) else None
kill = [v for v in bm.verts
        if (idx & set(v[dl].keys())) and (keep_i is None or keep_i not in v[dl])]
print(f"deleting {len(kill)} verts")
bmesh.ops.delete(bm, geom=kill, context="VERTS")
bm.to_mesh(rt.data)
bm.free()
for g in DROP:
    vg = rt.vertex_groups.get(g)
    if vg:
        rt.vertex_groups.remove(vg)

# the hands come along inside clyffy_body now — a separate hand object would just be a duplicate
for name in ("clyffy_handR",):
    ob = bpy.data.objects.get(name)
    if ob:
        bpy.data.objects.remove(ob, do_unlink=True)
        print(f"removed {name} (the body remesh already contains the hands)")

AFTER = gate.survey(rt, scaf)
print(f"after:  {AFTER['faces']} faces, loops {AFTER['loops']}, apertures {AFTER['apertures']}")

ok, lines = True, []
for n in AFTER["apertures"]:
    b, a = BEFORE["apertures"][n], AFTER["apertures"][n]
    if b > 0 and a != b:
        ok = False
        lines.append(f"  !! the {n} changed ({b} -> {a}) — the head must not be touched")
    elif b > 0:
        lines.append(f"     {n} intact ({a} verts)")
if AFTER["nonman"] > BEFORE["nonman"]:
    ok = False
    lines.append(f"  !! non-manifold edges appeared ({BEFORE['nonman']} -> {AFTER['nonman']})")
zs = [v.co.z for v in rt.data.vertices]
lines.append(f"     shell now spans z [{min(zs):+.4f}, {max(zs):+.4f}] — should stop at the collar")
gate.report("drop marched body", lines, ok)

if ok and WRITE:
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print("saved")
elif not ok:
    print("NOT SAVED")
    sys.exit(1)

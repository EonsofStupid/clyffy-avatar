"""Build the gate's proof cases: an interior-marked probe at the lip, poking out or buried.

    blender -b --python tools/_gate_probe.py -- <in.blend> <out.blend> <fwd_deg> <through|buried>

Underscore-prefixed: this is a test fixture, not a pipeline stage.

A gate that has never failed is not a gate. `cavity_gate.py` must be shown to do BOTH things
before it is trusted to certify a real cut:

  through  a sphere centred ON the skin at the lip, so half of it protrudes  -> gate must FAIL
  buried   the same sphere pushed back inside the head                       -> gate must PASS

The buried case matters as much as the through case. A gate that fires on everything is as
useless as one that fires on nothing, and "the cavity is inside an opaque head" is precisely
the condition the real mouth has to satisfy.

The probe carries material `inner_probe`, so it is picked up by the same `inner_` rule the
real cavity, teeth and tongue will use — the fixture exercises the actual contract, not a
special case.
"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = os.path.abspath(argv[0]), os.path.abspath(argv[1])
FWD_DEG = float(argv[2])
MODE = argv[3]
# `through` / `buried` are the two headline cases. A bare number is a PROTRUSION in world
# units, used to walk the sensitivity ladder: how small a leak does this gate still catch?
# "it catches half a sphere" would prove almost nothing — the defect it exists to stop was a
# thin sliver at the mouth corners.
assert MODE in ("through", "buried") or MODE.replace("-", "").replace(".", "").isdigit(), MODE
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=SRC)
ob = max([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
me = ob.data
N = len(me.vertices)
co = np.empty((N, 3)); me.vertices.foreach_get("co", co.ravel())
z = co[:, 2]; zlo, zhi = float(z.min()), float(z.max()); H = zhi - zlo

a = math.radians(FWD_DEG)
fwd = Vector((math.sin(a), -math.cos(a), 0.0))

# The lip line, measured two ways in the survey and agreed at 71.9% of body height.
LIP_FRAC = 0.719
zl = zlo + LIP_FRAC * H
RAD = 0.008          # ~0.8% of body height: a small leak, not an obvious one

# find the skin at the lip on the midline by raycasting from far in front, along -fwd
origin = Vector((0.0, 0.0, float(zl))) + fwd * (H * 2.0)
hit, loc, nor, idx = ob.ray_cast(origin, -fwd)
assert hit, "no surface hit at the lip height — check the forward axis"
print(f"skin at the lip: {tuple(round(v,4) for v in loc)}   "
      f"z {float(loc.z):+.4f} = {(float(loc.z)-zlo)/H*100:.1f}% of body height")

# protrusion p = how far the sphere's forward-most point sits PROUD of the skin.
# centre = loc + fwd*(p - RAD)  puts that point exactly at loc + fwd*p.
if MODE == "through":
    p = RAD                    # half the sphere outside
elif MODE == "buried":
    p = -2.0 * RAD             # pushed well inside an opaque head
else:
    p = float(MODE)
centre = loc + fwd * (p - RAD)
print(f"protrusion {p:+.5f} units = {p/H*100:+.4f}% of body height")

bpy.ops.mesh.primitive_uv_sphere_add(radius=RAD, location=centre, segments=24, ring_count=16)
probe = bpy.context.object
probe.name = "inner_probe"
m = bpy.data.materials.new("inner_probe")
m.use_nodes = True
probe.data.materials.append(m)

d = (centre - loc).length
print(f"probe {MODE}: radius {RAD:.4f}, centre {tuple(round(v,4) for v in centre)}, "
      f"{d:.4f} behind the skin ({d/RAD:.1f} radii)")
print(f"expected gate result: {'FAIL' if MODE == 'through' else 'PASS'}")

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"wrote {OUT}")


### M2 build — `tools/chin_mass.py`, and the constraint that changes the answer

Operator chose "build real chin mass" over capping travel. Built it: a new pipeline stage
between `mouth_open` and `eye_open` that grows a mandible as a smooth displacement field —
**no new geometry**, vertex count and indices preserved exactly, because `body_rig.py`
transfers face weights BY VERTEX INDEX and asserts equal counts.

Growth is measured from the JAWLINE PLANE (hinge + lip line, the same plane `jaw_rig.py`
splits weights on) so the mandible grows perpendicular to the jaw and the lip line never
moves. Knobs: `DEPTH`, a 4-knot bump in `u` (dead zone / ramp in / hold / ramp out), a
forward `FILL`, an along-jaw ramp and a lateral taper.

Three guards, each of which caught a real failure:

* **`U_DEAD`.** The lip slit is 0.0077 tall with ~0.0008 edges. A ramp starting at u=0 put a
  0.004H gradient across them — 4.67x stretch, 213 edges over 2x, and two white "fangs"
  erupting at the commissures. Holding the field at zero across the slit removed both at no
  cost to the mandible.
* **Monotonicity assert.** `u' = u + DEPTH·bump(u)` is injective only if
  `1 + DEPTH·bump'(u) > 0`. It fired on DEPTH 0.055 and 0.065 (min du'/du −0.031, −0.219)
  and stopped a surface that would have folded through itself.
* **Garment protection, by SAMPLING the texture.** There is no separate shirt mesh — the
  navy t-shirt is painted on the one continuous body surface, so displacing geometry under
  it drags the collar. Sampling the base-colour image at each vertex UV puts the midline
  collar at **z +0.1377 = 9.00%H below the lip line**. (Take the highest navy vertex instead
  and you get z +0.3527, above the mouth — the lanyard is blue too. Scan DOWN for the first
  band that turns navy.)

### ⛔ The collar is the binding constraint, and it inverts the chin argument

With a rigid chin of depth `D` and a jaw drop `d`, at full open: visible chin below the
lower lip = `D`; chin underside = `D + d`; and the chin must stay above the collar:

```
    D + d < 9.0 %H     ->     d < 9.0 - D
```

**Growing the chin trades against maximum gape one-for-one.**

| chin depth D | max drop before the chin enters the shirt | angle |
|---|---|---|
| 4.5%H (as shipped) | 4.5%H | ~12° |
| 7%H (grown) | 2.0%H | ~6° |

The current chin depth is already at the optimum of `min(D, 9−D)`. **No chin geometry makes
22° work** — 22° drops 7.41%H, and there are only 9.00%H between the lip and the shirt.

This agrees with the angle ladder, which was measured independently and by eye: 12–15°
reads as a mouth, 18° starts eating the chin, 22° is a rectangle. Two unrelated
measurements landing on ~12° is the answer.

### What the chin mass IS worth (it is not wasted)

Run through `jaw_rig.py` unchanged:

| | rigid jaw core (w>0.99) | verts >0.01 | mean jaw weight |
|---|---|---|---|
| baseline | 742 | 3419 | 0.506 |
| chin moderate (DEPTH 0.028) | **1316** | 4061 | 0.601 |
| chin aggressive (DEPTH 0.040) | **1495** | 4301 | 0.618 |

The jaw finally owns real mass — double the rigid core — and the mandible under the cavity
floor thickens, which was M1's genuine finding. At 12° all three read well and the grown
chins carry a fuller jaw line. At rest, moderate stays canon-plausible; **aggressive
swallows the neck** and the jaw runs straight into the collar.

### State
Nothing promoted. `tools/chin_mass.py` added; not yet in `clyffy.pack.toml [pipeline]` or
`rebuild.sh` pending the operator's call on max angle. Candidates: `work/m2_chinD_mod`,
`work/m2_chinD_agg`, rigs in `work/m2_rig_{open,mod,agg}`, ladders in `work/m2_lad_*`,
comparisons `work/_cmp_{rest,front,q50}_*.jpg`.

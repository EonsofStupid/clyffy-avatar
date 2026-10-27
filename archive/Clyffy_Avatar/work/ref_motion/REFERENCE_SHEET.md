# B0 — REFERENCE MOTION SHEET

Measured by `tools/ref_motion.py`. **No authoring is done by that tool.** These are the numbers the
beats of POAM A10 are scored against.

## The reference that fixed this: `6f675283` (operator-supplied, 2026-07-31)

ONE character, isolated on **pure black**, ears visible throughout, **8 s of continuous
performance**. Supplied after watching me repeatedly grab the wrong character or the wrong scene,
and it removes that failure mode outright: with a black background **the silhouette IS the
character**. Measured: background 5th-percentile luminance **0.0**; only two framing changes in the
clip, so frames 0–191 are one unbroken take.

**The lesson: the fix was better FOOTAGE, not a better detector.** Five auto-detectors and four
"improvements" were spent fighting clutter this clip does not have.

## ⚠️ "CROWN" MEANS THE HEAD-MASS CENTROID

The mean over the **top 12%** of the figure — NOT the topmost rows. Those are horn TIPS, and
rolling the head raises one horn while lowering the other, so a tip centroid partly cancels and
**under-reports lateral motion by ~6×** (it read 0.0383 where the truth is 0.0168).

`ref_motion.py` and `idle_check.py` use the identical definition; the two sides are only comparable
because of that. Fixing it also unblocked the ear lag below.

| shot | frames | ruler | stability | verdict |
|---|---|---|---|---|
| `isolated_performance` (6f675283) | 0–191, 8.00 s | silhouette height 349 px | **6.9%** | ✅ 100% tracked |
| `muzzle_closeup` (48a464a0) | 206–246, 1.67 s | pad width 512 px | **3.1%** | ✅ 100% tracked |

## ✅ B1 — head motion — **SHIPPED 2026-08-01**

Targets are **IDLE-SPECIFIC**, from the six quietest 2-second windows. The whole-take figure
(X rms 0.0818) includes performance — pointing, leaning, arms crossed — and building idle sway to
it would read as drunk.

| quantity | reference | ours | verdict |
|---|---|---|---|
| crown **X** rms (idle) | **0.0168** | **0.0166** | ✅ 0.99× |
| crown **Y** rms (idle) | **0.0101** | **0.0110** | ✅ 1.09× |
| crown X rms (whole take) | 0.0818 | — | context only |

Authored in `control_surface.IDLE` / `idle_pose()` — the SSOT — consumed by the web renderer
(`applyIdlePose`) and gated by `tools/idle_check.py`. **idle_check GREEN.**

Amplitudes are DERIVED, not guessed: `idle_check --calibrate` measures crown displacement per
degree per driver — head_roll **0.01246**, spine_roll 0.00452, hips_roll 0.00418 lateral;
head_pitch 0.00061, chest_pitch −0.00057 vertical. Head ROLL is the strongest lateral driver
(3× the spine) because the crown is the horn tips; the spine still carries the bulk of the
amplitude because that is where a real weight shift originates. Vertical bob is a hips
**translation**, because rotation cannot produce it — height changes as (1−cos t), which vanishes
for small angles.

⚠️ The dominant-frequency readout (0.125 Hz measured vs 0.375 Hz reference) is an **FFT resolution
artefact**: an 8 s window has 0.125 Hz bins, so a 0.19 Hz term lands in the 0.125 bin. Not gated.

## ⚠️ B2 — ear motion: amplitude usable, lag still WEAK

Ears tracked in all **192 frames**; **20 rejected** where raised arms exceeded the ears laterally
and would have read as ear motion.

| quantity | reference | ours today |
|---|---|---|
| ear reach left / right, rms | **0.0554 / 0.0547** body-heights | 0.000 before B1 |
| ear reach left / right, p2p | 0.371 / 0.214 | — |
| **ear rms ÷ crown rms (whole take)** | **≈ 0.68** | — |

**Usable target: the ears travel ~0.68× the head's translation.** A ratio, so it transfers at any
scale, and it is what spring stiffness and drag get tuned against.

### Lag: 166.7 ms (4 frames) — **but r = 0.087, which is barely above noise**

With the horn-tip crown the lag measured 0 frames, which I recorded as untrustworthy rather than as
a finding. Switching to the head-mass centroid moved it to 4 frames — but the correlation is only
**0.087**, so this is WEAK EVIDENCE, not a target. It is consistent with ears that trail, and it is
not strong enough to tune against.

The signal is still partly pose-dominated: the outline's sideways reach responds to head rotation
as well as to ear swing. Isolating true spring lag needs the ear tip in the SKULL's frame, which
needs head orientation. **Left open deliberately** — the amplitude ratio is enough to tune B2, and
now that B1 ships, the honest next check is whether the ears LOOK right on the live surface.

## ✅ B4 — snout as a deforming mass

From `muzzle_closeup`, ruler stable to 3.1%.

| quantity | reference | ours today |
|---|---|---|
| pad **height** varies | **24.0%** | p90 travel 0.05–1.65 %H, at the lip EDGE only |
| pad **width** varies | **3.1%** | — |
| pad **area** varies | **42.1%** | — |
| **nostril area** varies | **42.9%** | `noseSneer` moves **0%** of pad verts past 1 %H |

Height varies ~8× more than width: the snout **squashes vertically and holds its width**. Ours is a
rigid plate on a jaw hinge, nostrils immobile.

## ✅ B3 — weight dynamics

| quantity | reference | ours today |
|---|---|---|
| aperture hold, median | **62.5 ms** | undefined — weights written straight to target |
| aperture hold, p90 | **187.5 ms** | — |
| aperture hold, max | **250 ms** | — |
| effective rise time | see caveat | **one frame (~42 ms)** |

⚠️ Rise times (500 ms aperture, 708 ms pad height) come from a **single** excursion (`n_rise = 1`,
`n_fall = 0`). Recorded, not usable as a target until measured over a longer shot.

## Tool lessons kept in the code

* **Complexity was the bug.** The muzzle measurement worked on the FIRST attempt with a tight crop,
  a plain colour rule and a raw bbox: 3.8% stability. Four "improvements" took it to 30%, 67%, 81%.
  Reverting restored 3.1%.
* **A whole-head crop locks onto the brass goggles**, the warmest thing on the head.
* **A fixed `R > B` hue rule inverts under the blue night grade** (muzzle measures 120,101,137).
* **`pose_bone.matrix` discards translation on CONNECTED bones** — spine/chest/neck/skull are all
  connected, so six of seven drivers silently did nothing. Use `matrix_basis` conjugation.
* **`pose_bone.location` is already in scene units** — dividing by `bone.length` overshot the bob 50×.
* **Measure from the evaluated mesh, not a render**, when the camera is orthographic and axis-aligned.

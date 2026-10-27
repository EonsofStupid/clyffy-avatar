# mesh/_dead — quarantined 2026-08-05

Nothing in here is to be built on. Moved aside on the operator's instruction after the back of the
approved base was found to be a crater. Kept rather than deleted so the crater renders stay
reproducible as the evidence behind the BUILD_LOG entry of the same date, and because both source
meshes came from paid generation jobs whose re-downloadability has not been verified.

| file | why it is dead |
|---|---|
| `clyffy_v2.fbx` | Approved 2026-08-03. **The back of the skull is MALFORMED — a broad scooped basin with a curled overlapping flap** where a skull should be a smooth dome (`work/BACKCMP/clyffy_v2_270.png`). The face at 090 is clean and correct. **Nothing is missing:** 0 of 8002 see-through rays hit an inward face, perpendicular hull inset maxes at 0.0785 against 0.0787 on its own face, relief -0.0143 against -0.0217 on its own face. The earlier claim here — "a third is a pit, max inset 0.3018" — was an artifact of a probe that measured along rays against a convex hull that bridges the ear-to-skull gap. Retracted; see BUILD_LOG 2026-08-05 (later). |
| `clyffy_v2_{clean,seam,split,cavity,parts,sealed,chamber,chamber_sealed,rig}.blend` (+ `.blend1`) | The whole mouth chain, derived from the above. The back is equally malformed in all of them — but the mouth chain never touched the back, so **these are not necessarily void**; they were quarantined on the retracted number. |
| `clyffy_base_v1.glb`, `clyffy_base_tripo.fbx` | The generation `clyffy_v2.fbx` was converted from. Same defect upstream. |
| `clyffy_open_v1.glb` | Meshy `fc862377-99f8-40ef-a529-4b636e94d874`. Back is a clean smooth dome — verified by eye (`work/BACKCMP/clyffy_open_v1_180.png`), not just by numbers. It fails for different reasons: a different character from the approved v2, and 119,444 tris with zero quads despite `topology: "quad"`. |
| `clyffy_open_clean.blend` | Welded/repaired form of the above. |

Re-measure any of these with:

    blender -b --python tools/crater_probe.py -- mesh/_dead/<file> <fwd_deg>
    blender -b --python tools/paint_views.py  -- mesh/_dead/<file> <out_dir> --clay 240 270 300

**Run both, and believe the render.** The malformed back scores normally on every number
`crater_probe.py` reports; it is only visible in the clay views. That is the whole lesson of
2026-08-05.

v2's forward is **+X / 090 deg**, so its back is 270. `clyffy_open_v1.glb`'s forward is 0.

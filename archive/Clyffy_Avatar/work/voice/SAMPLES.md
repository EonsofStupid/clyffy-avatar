# Clyffy voice samples (v0 scaffold)

**Backend:** `voice.tts` → `llama-tts` + OuteTTS 0.2 500M Q5_K_M + WavTokenizer F16  
**Brief:** warm confident baritone (scaffold; built-in male default — not a trained clone)  
**Generated:** 2026-07-27  

Regenerate:

```bash
python3 tools/voice_tts.py --from-pack --no-speaker
# then drive (per line or script):
blender -b --python tools/avatar_drive.py -- \
  mesh/canon/body/clyffy_v2_body.blend work/voice/drive/<slug> 235.1 \
  work/voice/samples/<slug>.wav
```

## Lines

| # | Text | Wav | Drive mp4 |
|---|------|-----|-----------|
| 00 | We are doing this today. | `samples/00_we_are_doing_this_today.wav` | `drive/00_we_are_doing_this_today/alpha_talk.mp4` |
| 01 | Alright — here is the plan. | `samples/01_alright_here_is_the_plan.wav` | `drive/01_alright_here_is_the_plan/alpha_talk.mp4` |
| 02 | That is the root cause. We fix it at the source. | `samples/02_that_is_the_root_cause_we_fix_it_at_the.wav` | `drive/02_that_is_the_root_cause_we_fix_it_at_the/alpha_talk.mp4` |
| 03 | Hold on. I am thinking. | `samples/03_hold_on_i_am_thinking.wav` | `drive/03_hold_on_i_am_thinking/alpha_talk.mp4` |
| 04 | Done. Check the gate. | `samples/04_done_check_the_gate.wav` | `drive/04_done_check_the_gate/alpha_talk.mp4` |

Each drive folder also has `drive_frames.jsonl` (control-surface timeline).  
**Audio is muxed** into each `alpha_talk.mp4` (video+aac).

### Review reel
`work/voice/drive/_all_lines.mp4` — all five lines concatenated with audio.

### Pack demo (signature)
`mesh/canon/body/drive/alpha_talk.mp4` (+ `.wav` + `drive_frames.jsonl`) = line 00.

## Operator A/B — RESOLVED 2026-07-27

- [x] Sound is warm / confident enough for alpha demos  
- [x] Mouth motion readable on signature line (00)  
- [x] Rest hold at end is clean  
- [x] Accepted as **v0 scaffold**; identity target chosen separately (below)

### Identity pick (F3)

Four takes were compared on all five `sample_lines` in one script:

| | Voice | Params | Len |
|---|---|---|---|
| A | Mark | neutral | 11.60s |
| B | Andre | neutral | 12.01s |
| **C** | **Mark** | **rate +18 · loudness +14 · pitch +1** | **11.49s** |
| D | Zane | neutral (energy reference only) | 11.81s |

**Operator picked C.** Presets cannot be blended, so "Mark with Zane energy" was
realised as Mark driven on the tuning params; D is kept so the intended energy is
auditable.

**What C commits to:** C is the **reference target** the local GB10 `voice.tts` slot
tunes toward. It is **not** the backend. `tts_target = "local-gb10-first"` is unchanged,
no platform clone of `voice:2f249fcd-…` was created, and none is authorised.

Files: `work/voice/ab/{A_mark,B_andre,C_mark_zane,D_zane_ref}.wav` (+ `_mono` 24k rig-ready).  
Driven: `work/voice/drive/ab_C_mark_push/alpha_talk.mp4` (waist-up) ·
`work/voice/drive/ab_C_full/alpha_talk.mp4` (full-body).

**Still not done:** platform clone of `voice:2f249fcd-…`, blend1 reference pull, phoneme lipsync.

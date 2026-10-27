# clyffy-avatar — the live face surface

Roadmap **E2 Avatar mode** · decision **D35** (Avatar = model + voice + face).
Boundary COSTAR-gated and registered in `MAP.md` on 2026-07-27.

## What this owns — exactly one thing

Present the VRM face in a live window and apply **drive contract v1** frames to it.

It does **not** own the contract, the rig, the voice, or the character. Those live in
`Clyffy_Avatar` (the character pack) and are consumed here.

## The seam law

```
        drive contract v1  (control_surface.schema.json)   <-- THE SEAM
                 │
      ┌──────────┴───────────┐
   renderer/              (future)
   three-vrm              Unreal Engine
   adapter #1             adapter #2
```

The renderer is an **adapter**, never the owner of the face. This is the same rule as
`/infra` swapping vLLM · llama.cpp · candle behind the brain port: *integrate behind the
port, never delete the seam*. An adapter may not redefine the contract, and no adapter
re-derives the mapping constants.

## Where the frames come from — the SPLIT

Operator decision, 2026-07-27:

| channel | owner | status |
|---|---|---|
| `viseme_weights` | **the renderer**, derived locally from the audio it is playing | **live** |
| `expression_state` · `gaze_target` · `rest_loop` · `goggle_state` | **clyffyd** — `GET /avatar/state` (SSE), `interfaces/clyffyd/src/avatar.rs` | **live** |

Deriving visemes locally guarantees lipsync cannot drift from playback. The cost is that
the mapping now has two readers, which is why it has exactly one **definition**.

## One definition, two readers

`VISEMES` and `ENVELOPE` are read at runtime from `control_surface.schema.json`, emitted by
`Clyffy_Avatar/tools/control_surface.py`. The offline driver (`avatar_drive.py`) reads the
same block. Hand-copying these constants into JS would drift silently — the offline mp4 and
this window would lipsync differently on identical audio.

`jawOpen` is **always** the jaw bone (max 22°), never a shape key. Contract v1.

## ⚠️ The one honest deviation from offline

`avatar_drive.py` normalises the envelope by the **whole-clip maximum**. A live surface
cannot — it has not heard the rest of the utterance. The renderer uses a **rolling peak with
decay** instead. Steady speech tracks the offline result closely; clip onsets and abrupt
loudness jumps will differ. This is inherent to live playback, not a defect to tune away —
do **not** "fix" the offline path to match it.

## Assets

`renderer/public/*` are **real files** (they used to be symlinks into a host checkout, which broke
every clone). The repo's self-containment gate (`scripts/check-paths.sh`) now rejects symlinks.

| file | copy of |
|---|---|
| `clyffy.vrm` | `archive/Clyffy_Avatar/mesh/canon/body/clyffy.vrm` (byte-identical, same LFS object) |
| `control_surface.schema.json` | `archive/Clyffy_Avatar/mesh/canon/body/control/control_surface.schema.json` |
| `voice_sample.wav` | locally generated OuteTTS sample "We are doing this today." (see `ASSETS_PROVENANCE.md`) |

After re-exporting the VRM or the control surface in the pack, copy it here again
(`cp archive/Clyffy_Avatar/mesh/canon/body/clyffy.vrm interfaces/clyffy-avatar/renderer/public/`).

## Run

**Desktop companion** (transparent, always-on-top, bottom-right):

```bash
cd renderer && npm install && npm run build     # the shell embeds renderer/dist
cd ../shell   && cargo build --release
./target/release/clyffy-avatar-shell
```

**Browser / dev** (HUD visible, framing toggle, speak button):

```bash
cd renderer && npm run dev        # http://127.0.0.1:5273
```

**Container** (from the repo root): `docker compose up -d renderer` serves the built UI on
`http://127.0.0.1:5273` (nginx, read-only).

Click **speak (sample)** to drive the face from the bundled voice sample. **framing** toggles
waist-up (companion default) and full-body, mirroring the pack.

## Layering (contract v1, applied in this order)

    expression_state base  ->  viseme_weights max-merge  ->  rest_loop zeros all

`rest_loop` zeros the drives, with one deliberate exception: local audio wins. If this page
is speaking it is by definition not at rest, whatever the daemon last said.

## The goggle state machine is the loading indicator

`clyffy.pack.toml [animation.goggles]` — goggles **down** means committed to work, and *the
act of pulling them down IS the commit-to-work transition*. So a busy daemon lowers them.
No spinner, no progress bar. That is the rest-state law made visible: rumination is a rest
pool, not a wait.

## Degrading without a daemon

The face is a presentation surface and must never freeze on a dead socket. With no daemon
reachable the HUD reads `no daemon` and the idle stand-in (gaze drift + blink) takes over;
`EventSource` reconnects on its own. Point elsewhere with `?daemon=http://host:port`.

## Not done yet

- Desktop shell — transparent, always-on-top window. Tauri needs `libwebkit2gtk-4.1-dev`
  (available in apt, **not installed**). Browser window until then.
- **End-to-end against the live daemon.** The state channel is verified against a mock
  emitter and by `cargo test -p clyffyd avatar::` (7 green). The RUNNING clyffyd is the
  pre-change binary and answers `/avatar/state` with 404 — it needs a rebuild + restart.
- Phone / assistant-app surface (the second consumer the web stack was chosen for).
- Unreal adapter.

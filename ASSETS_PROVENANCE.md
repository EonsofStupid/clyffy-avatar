# Asset provenance and public-release rights review

Status: **CLEARED for public release by Jesse / AngryVibes_LLC on 2026-10-27**, covering all
art assets below, including `clyffy.vrm`. Apart from that clearance and unmodified redistribution,
the art stays all rights reserved (see `ART_LICENSE.md`). The provenance facts below come from
the project's own build logs and READMEs and are kept for the record.

## Character / design source
- The Clyffy character (Holstein cow, one of eleven characters in the "CLYFFY_AND_MINIONS"
  ensemble) and its show bible come from the **AngryVibes_LLC Google Drive** (DevPULSE /
  AngryVibes show material). Per `docs/CANON_inherited.md`, `archive/Clyffy_Avatar/CANON.md`.
- Show-bible art (`canon/CLYFFY/`), show docs (`canon/docs/`) and the cast-wide element-token
  registry (`canon/_MASTER_REGISTRY.md`) are **not included** in this repo.
- Character text that **is** included and describes the show IP: `docs/CANON_inherited.md`,
  `archive/Clyffy_Avatar/CANON.md`, `archive/Clyffy_Avatar/MAP.md`, `archive/Clyffy_Avatar/POAM.md`,
  `reference/approved/SPEC.md`, plus character notes inside `STATUS.md` / `BUILD_LOG.md`.

## Generated reference art
- `reference/approved/*.png`, `reference/look/*.png`, `sheets/**/*.png`: model sheets and
  turnarounds. Build logs say these were produced with AI image services (Higgsfield "element"
  references; logs also list xAI, OpenAI and Gemini image APIs as available lanes). **Which
  service made each image is not recorded per file.** Each service's terms on output ownership
  and public redistribution need to be confirmed for the account/plan used.
- `reference/derived/*.png`: crops of `reference/approved/` (same status).

## 3D models
| Asset | Provenance (from logs) | Rights status (all cleared 2026-10-27) |
|---|---|---|
| `work/RETOPO_clyffy.blend` (current build) | Hand-retopologized in Blender over a **Meshy** `multi_image_to_3d` scaffold (`work/remesh/meshy.glb`, not included) | Unclear: depends on Meshy plan terms for the scaffold + AngryVibes character IP |
| `archive/Clyffy_Avatar/mesh/clyffy_base_av_v1.fbx`, `clyffy_base_neutral_v2.fbx` | **Tripo** (H3.1) image-to-3D generations from the reference plates; base meshes for the legacy chain. Logs note "the `/mnt/pfs/...` paths in the file are Tripo's". | Unclear: Tripo output terms depend on plan (free-tier outputs are typically public/CC BY; paid plans assign ownership) |
| `archive/Clyffy_Avatar/mesh/canon/*.blend`, `body/*.blend`, `shapes/`, `eyes/`, `talktest/`, `drive/` | Derived from the Tripo base by the legacy 12-stage pipeline (`archive/Clyffy_Avatar/tools/`) | Same as the Tripo base |
| `archive/Clyffy_Avatar/mesh/canon/body/clyffy.vrm`, `clyffy_v2_body.glb` | Exported from `clyffy_v2_vrm.blend` with the VRM Add-on for Blender | Cleared 2026-10-27. VRM 1.0 meta updated to match: `allowRedistribution: true` (was `false`). Unchanged: authors `AngryVibes`, VRM Public License 1.0, `modification: prohibited`, `avatarPermission: onlyAuthor`, `commercialUsage: personalNonProfit`, `creditNotation: required`. `clyffy_v2_body.glb` carries no VRM meta |
| `interfaces/clyffy-avatar/renderer/public/clyffy.vrm` | Byte-identical copy of the canon `clyffy.vrm` above (same sha256 `8f0d9cfdae79…`, same Git LFS object), replacing a symlink that pointed outside the repo | Same as the canon `clyffy.vrm` (cleared 2026-10-27; meta identical, `allowRedistribution: true`) |
| `archive/Clyffy_Avatar/mesh/canon/body/clyffy_normal_pad.png` | Baked muzzle normal map (pipeline output) | Derived art; same as the base |
| `mesh/_dead/*` (not included; README only) | Tripo + Meshy generations from paid jobs | Not published |

## Voice
- `interfaces/clyffy-avatar/renderer/public/voice_sample.wav` ("We are doing this today.", 24 kHz
  mono, 72 KB) is generated **locally** with OuteTTS 0.2 500M through llama.cpp `llama-tts`
  (built-in default speaker, no voice clone); it is the pack's `00_we_are_doing_this_today` sample.
  It replaces the old symlink to identity take C (`work/voice/ab/C_mark_zane_mono.wav`, a
  Higgsfield "Mark" preset take), which is **not included**: the 2026-10-27 clearance covers the
  art and `clyffy.vrm`, not third-party voice takes.
- **License of `voice_sample.wav`: it is OuteTTS 0.2 output, and the OuteTTS 0.2 weights are
  CC BY-NC 4.0, so the sample is published under CC BY-NC 4.0 terms (non-commercial use,
  attribution: "Generated with OuteTTS 0.2 500M by OuteAI").** It is kept in the public repo
  with that restriction (decision by Jesse / AngryVibes_LLC, 2026-10-27); it is *not* covered by
  the Apache-2.0 code license or by `ART_LICENSE.md`.
- The TTS model weights are **not committed**. `scripts/fetch-models.sh` downloads them at a pinned
  Hugging Face commit and verifies size + sha256:
  `OuteAI/OuteTTS-0.2-500M-GGUF` `OuteTTS-0.2-500M-Q5_K_M.gguf` (CC BY-NC 4.0) and
  `ggml-org/WavTokenizer` `WavTokenizer-Large-75-F16.gguf` (MIT).

## Fonts, HDRIs, third-party models
- No font files (`.ttf`/`.otf`/`.woff`), HDRIs or marketplace models were found in the imported tree.
- Strings inside every LFS binary (`.blend`, `.vrm`, `.glb`, `.fbx`, large `.png`) were scanned on
  2026-10-27 for host paths, user names, host names, private IPs and e-mail addresses. Findings:
  the `.blend` files reference images only by relative `//…` paths (leftover bytes of an old
  absolute render-output path, left after the `//render/` terminator in the scene's 1024-byte
  output-path field of 10 `.blend` files, were overwritten with same-length zero bytes on
  2026-10-27; every file was re-verified to load in Blender 5.2.0); the two Tripo `.fbx` files
  contain Tripo's own server texture paths (`/mnt/pfs/server/tcli_<id>/…`); `sheets/turn_4k_a.png`
  and `sheets/t1_1k.png` carry a C2PA content-credentials certificate naming `cai-ops@adobe.com`
  (Adobe's public CAI signing identity); `reference/look/Clyffy_BASE-NEUTRAL-v1.png` carries a
  C2PA manifest (`gpt-image`) whose certificate chain names `ca@trufo.ai` (Trufo's public C2PA
  root CA). No build-machine paths, user names or private addresses.
- **Tripo job path accepted:** the two `.fbx` files contain Tripo's own server texture paths
  (Tripo job IDs), not build-machine paths. They are left unchanged on purpose (decision by
  Jesse / AngryVibes_LLC, 2026-10-27). `scripts/check-paths.sh` only scans text files, and the
  lines here that describe them are listed in `.pathcheck-allow`.

## Third-party software (fetched at build time, not committed)
- Blender 5.2.0: GPL-2.0-or-later. amd64: the official blender.org tarball (sha256-pinned).
  **Linux ARM64:** blender.org ships no build, so the Dockerfile compiles it from the v5.2.0 git
  commit with Blender's own precompiled `lib-linux_arm64` (pinned commit); those libraries keep
  their own licenses (see `/opt/blender/lib` and Blender's license docs in the image).
- llama.cpp (`llama-tts`, tag b9940): MIT.
- ffmpeg (Ubuntu 24.04 package): LGPL/GPL.
- VRM Add-on for Blender 4.4.0 (saturday06): MIT or GPL-3.0 (dual).
- three 0.185.1, @pixiv/three-vrm 3.5.5: MIT; vite 7.3.6: MIT.
- numpy, Pillow, scipy: BSD-style / HPND.

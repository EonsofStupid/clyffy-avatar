# Release checklist — public turnkey release

Repository: `EonsofStupid/clyffy-avatar`, seeded 2026-10-27 as a single clean commit. It has no
history from the earlier private working repo. No tag has been created yet.

## Rights and licensing
- [x] Art and `clyffy.vrm` cleared for public release by Jesse / AngryVibes_LLC (2026-10-27).
- [x] `ART_LICENSE.md`: all rights reserved, apart from publication and unmodified redistribution.
- [x] `clyffy.vrm` meta set to `allowRedistribution: true`. `modification: prohibited` is unchanged.
- [x] `voice_sample.wav` kept: OuteTTS 0.2 output under CC BY-NC 4.0 (noted in `ASSETS_PROVENANCE.md`).
- [x] Tripo server paths inside the two `.fbx` files accepted as-is (noted in `ASSETS_PROVENANCE.md`).
- [x] Code: Apache-2.0 (`LICENSE`, `LICENSE-CODE`).
- [ ] Optional: open each `.blend` in Blender and review packed images (File > External Data).

## Security
- [x] Absolute home paths that were embedded in `.blend` files were scrubbed, including leftover bytes
      after the `//render/` output path in 10 files (zeroed in place, same length). All 15 `.blend`
      files load headless in Blender 5.2.0. Geometry is unchanged.
- [x] Personal paths, hostnames, tailnet IPs/domain, email and the element-token UUID were scrubbed
      from text files.
- [ ] gitleaks plus a pattern scan over a fresh clone of the full history (including LFS content)
      before the repo goes public (the repo stays **private** until a separate go-ahead).
- [ ] Enable secret scanning and push protection in the repo settings.

## Turnkey build (self-contained: clone + `docker compose up`)
- [x] No symlinks, host paths or LFS pointers: `scripts/check-paths.sh` gate in the Dockerfile, `make check` and CI.
- [x] `renderer/public/` holds real files (VRM in LFS); the `Containerfile` symlink is gone.
- [x] ARM64 Blender 5.2.0 is compiled from pinned source in the Dockerfile; no host Blender, no `/opt` mount.
- [x] `docker-compose.yml` (worker + renderer, named volumes, `--scale worker=N`, tts profile) and
      `docker-compose.gpu.yml` (NVIDIA device reservation); CPU fallback without it.
- [ ] Fresh-clone test on `linux/arm64`: `git clone` -> `git lfs pull` -> `docker compose up -d --build --wait`.
- [ ] `linux/amd64` build + `clyffy health --render`.
- [ ] Optional: CUDA kernels for the ARM64 source build (Cycles GPU on DGX Spark).

## Publish
- [ ] Tag `v0.1.0` once the amd64 and fresh-clone checks pass.

# Clyffy Avatar

Toolchain and assets for **Clyffy**, a stylized 3D cartoon character: a Blender-based build and
retopology pipeline, a VRM export path, and a three.js / three-vrm live renderer. It ships as a
container so it runs headless on a spare machine. It is tested on an NVIDIA DGX Spark
(ARM64 + GB10 GPU), and `linux/amd64` builds from the same Dockerfile.

> **Licensing:** code is Apache-2.0. The character and art are **all rights reserved** by
> AngryVibes_LLC and are cleared for publication and unmodified redistribution only. See `LICENSE`,
> `ART_LICENSE.md` and `ASSETS_PROVENANCE.md`.

## Quickstart

Needs only `git`, `git-lfs` and Docker with Compose v2 (Podman: see `install.sh`). Nothing outside
the clone is used: the art comes from Git LFS, everything else is built or fetched at pinned,
checksummed versions.

```bash
sudo apt install -y git git-lfs                      # once
git clone https://github.com/EonsofStupid/clyffy-avatar && cd clyffy-avatar
git lfs install --local && git lfs pull              # the .blend/.vrm/.glb/.fbx art (~690 MB)
cp .env.example .env                                 # optional; every value has a default
docker compose up -d --build --wait                  # renderer UI + one render worker (CPU)
docker compose run --rm worker submit --wait         # queue a headless render, wait for it
docker compose run --rm worker health --render       # full health report + a tiny Cycles render
open http://127.0.0.1:5273/                          # the live three-vrm face (renderer UI)
```

Render output lands in the `out` named volume (`/data/out/<job>.png`); copy one out with
`docker compose cp worker:/data/out/<job>.png .`.

| want | command |
|---|---|
| more render workers | `docker compose up -d --scale worker=4` (stateless; they share the job spool volume) |
| NVIDIA GPU | `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d` (or set `COMPOSE_FILE` in `.env`) |
| one-off render, no queue | `docker compose run --rm worker render [file.blend]` |
| optional local voice | `docker compose --profile tts run --rm fetch-models` then `docker compose --profile tts run --rm tts "Hello."` |
| single container, no compose | `docker build -t clyffy-avatar . && docker run --rm clyffy-avatar health --render` |
| the same with `make` | `make check build up render ui-check` (`make help` lists all) |

**First build on ARM64 (DGX Spark, Graviton, Jetson):** blender.org publishes no Linux ARM64
Blender, so the Dockerfile compiles Blender **v5.2.0** from its pinned git commit against Blender's
own precompiled `lib-linux_arm64` (also pinned). Expect ~25-40 min and ~15 GB of build cache the
first time; later builds are cached. amd64 downloads the official tarball and checks its sha256.

## Self-containment gate

`scripts/check-paths.sh` fails on **any symlink**, any host path in a tracked text file
(`/home/<user>`, `/Users/…`, `~/…`, `/mnt/…`, `/root/…`, a host `/opt/blender-5.x`, `Projects/…`)
and, with `--lfs`, on any LFS pointer left in place of the real file. It runs:
- in the Dockerfile `check` stage, which **both images depend on**, so a bad tree fails the build;
- as `make check`;
- in CI (`.github/workflows/check.yml`).

Lines that only *describe* a path (build history, Tripo's server paths baked into the vendor FBX)
are listed in `.pathcheck-allow`.

## Services, volumes and configuration

| service | image target | what it does |
|---|---|---|
| `worker` | `runtime` | stateless render worker; claims jobs from the `jobs` volume by atomic rename, writes PNGs to `out`; healthcheck = Blender + deps + VRM add-on + worker heartbeat |
| `renderer` | `renderer` | the three-vrm face UI as static files on unprivileged nginx, read-only rootfs; port `127.0.0.1:5273` (`CLYFFY_RENDERER_BIND` / `CLYFFY_RENDERER_PORT`) |
| `fetch-models` | `runtime` | profile `tts`: downloads the OuteTTS + WavTokenizer GGUFs (pinned HF commits, sha256-checked) into `models` |
| `tts` | `runtime` | profile `tts`: one line of local speech via `llama-tts` (llama.cpp `b9940`, built in the image) |

Named volumes: `jobs` (spool), `out` (renders, wavs), `cache` (`XDG_CACHE_HOME`), `models`.
All knobs are in `.env.example`.

The renderer looks for the optional **clyffyd** daemon (expression / gaze SSE, a separate project,
not part of this repo) at `http://127.0.0.1:8787`; without it the face still loads, idles and
lip-syncs locally. Point it elsewhere with `?daemon=http://host:8787`.

## Commands (inside the runtime image)

| command | what it does |
|---|---|
| `clyffy health [--quick\|--render\|--worker]` | Blender version, Python deps, VRM add-on, assets, ffmpeg, llama-tts, GPU; `--render` adds a tiny Cycles render |
| `clyffy render [file.blend] [out.png]` | headless still (`blender -b`); default `work/RETOPO_clyffy.blend` -> `$CLYFFY_OUT/render.png` |
| `clyffy worker` / `clyffy submit [file.blend] [--res WxH] [--samples N] [--wait]` | queue-based render workers (`scripts/worker.py`) |
| `clyffy run script.py [file.blend] [-- args]` | any pipeline tool in background mode, e.g. `clyffy run tools/cut_view.py work/RETOPO_clyffy.blend` |
| `clyffy rebuild [--vrm]` | legacy 12-stage build chain (`archive/Clyffy_Avatar/tools/rebuild.sh`) |
| `clyffy fetch-models`, `clyffy tts "TEXT" [out.wav]` | optional local TTS |
| `clyffy check` | the self-containment gate |
| `clyffy blender …` | raw Blender pass-through |

Render settings come from env: `CLYFFY_ENGINE` (CYCLES / BLENDER_EEVEE / BLENDER_WORKBENCH; compose:
`CLYFFY_RENDER_ENGINE`), `CLYFFY_CYCLES_DEVICE` (CPU / CUDA / OPTIX; falls back to CPU),
`CLYFFY_SAMPLES`, `CLYFFY_RES`, `CLYFFY_DENOISE=1` (OIDN; off by default).

> The **live interactive session** (`tools/bl-up`, `tools/bl`, `tools/blender_daemon.py`) drives a
> Blender **with its UI** on a desktop display. It is a workstation workflow and does not run
> under `blender -b`. Run it on a desktop with Blender 5.2 and the VRM add-on installed.

## GPU

`docker-compose.gpu.yml` adds a `deploy.resources.reservations.devices` NVIDIA reservation to the
workers and sets `CLYFFY_CYCLES_DEVICE=$CLYFFY_GPU_DEVICE` (default `CUDA`). It needs the NVIDIA
Container Toolkit. Without the overlay everything runs on CPU, on any host.

- **amd64:** blender.org's build ships CUDA/OptiX kernels, so Cycles renders on the GPU.
- **arm64:** the GPU is passed through and visible (`clyffy health` shows it), but the source-built
  Blender currently has **no CUDA kernels** (compiling them needs a CUDA toolkit in the build stage,
  not wired up yet), so Cycles **falls back to CPU** and says so in the job result (`device`).

Single container / Podman (`install.sh`): `CLYFFY_GPU=auto|none|cdi|gpus`, `CLYFFY_CDI_DEVICE`.

| engine | flag | prerequisite |
|---|---|---|
| Podman | `--device nvidia.com/gpu=all` (CDI) | `sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml` |
| Docker | `--gpus all` / compose overlay | NVIDIA Container Toolkit, `sudo nvidia-ctk runtime configure --runtime=docker` |

**Troubleshooting CDI:** `unresolvable CDI devices nvidia.com/gpu=all` usually means two
generated specs define the same devices (e.g. both `/etc/cdi/nvidia.json` and
`/etc/cdi/nvidia.yaml`). Check `nvidia-ctk cdi list`; keep one spec, or set
`CLYFFY_CDI_DEVICE=nvidia.com/gpu=<UUID from the list>`.

## Multi-arch builds

```bash
make buildx-multiarch                                   # both arches, no push
# or by hand (needs a builder with both platforms, e.g. a docker-container builder + binfmt):
docker buildx build --platform linux/amd64,linux/arm64 --target runtime  -t REGISTRY/clyffy-avatar:TAG --push .
docker buildx build --platform linux/amd64,linux/arm64 --target renderer -t REGISTRY/clyffy-avatar-renderer:TAG --push .
podman build --format docker --platform linux/amd64,linux/arm64 --manifest clyffy-avatar .
```

Building arm64 **under emulation** compiles all of Blender emulated (hours); build each arch on
native hardware where you can. Pinned inputs live in `versions.env` and the Dockerfile `ARG`s.

## Pinned versions
- Base images by digest: `ubuntu:24.04`, `node:22.21-bookworm-slim` (renderer build),
  `nginxinc/nginx-unprivileged:1.29-alpine` (renderer serve)
- Blender 5.2.0: amd64 tarball sha256-pinned; arm64 source at commit `fbe6228777e7`, libs at `c1f0435fde33`
- VRM Add-on for Blender 4.4.0 (sha256-pinned)
- Blender Python 3.13: numpy 2.2.6, Pillow 12.3.0, scipy 1.16.2
- llama.cpp `b9940` (`259f2e2a531a`) for `llama-tts`; TTS models by HF commit + sha256 (`scripts/fetch-models.sh`)
- Renderer: three 0.185.1, @pixiv/three-vrm 3.5.5, vite 7.3.6 (`package-lock.json`)

## Live renderer without containers (dev loop)
```bash
cd interfaces/clyffy-avatar/renderer && npm ci && npm run dev    # http://127.0.0.1:5273
```
`renderer/public/` holds real copies of `clyffy.vrm` (same LFS object as the canon export),
`control_surface.schema.json` and `voice_sample.wav`.

## Layout
| path | contents |
|---|---|
| `tools/` | current pipeline: live-session kit (`blkit.py`), retopo, rig, shape, probe and render tools |
| `work/RETOPO_clyffy.blend` | the current model (hand-retopologized) + command journals |
| `reference/`, `sheets/` | approved model sheets and turnarounds (art, see licensing) |
| `docs/` | plans and inherited canon notes |
| `archive/Clyffy_Avatar/` | legacy 12-stage pipeline, its canon `.blend`/`.vrm` outputs, pack manifest |
| `interfaces/clyffy-avatar/` | three-vrm live renderer + Tauri shell |
| `scripts/`, `Dockerfile`, `docker-compose*.yml`, `Makefile` | container entrypoint, health check, worker, path gate, model fetch |
| `install.sh` | single-container Docker/Podman path that mounts the checkout for live editing |

`STATUS.md` and `BUILD_LOG.md` are the project's working journal. Some paths in them are
historical and shown as `<repo>` / `~` placeholders.

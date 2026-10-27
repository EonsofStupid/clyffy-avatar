# syntax=docker/dockerfile:1.7
# Clyffy avatar — self-contained images. Build context = a fresh clone (with `git lfs pull`).
# Nothing is read from the host: every input is in the repo or fetched here at a pinned
# commit / version + sha256.  Multi-arch: linux/amd64 and linux/arm64 (docker buildx).
#
#   targets:  runtime  (default, last stage) headless Blender 5.2 + VRM add-on + pipeline
#                      tools + art + render worker + llama-tts + ffmpeg
#             renderer the three-vrm live face UI, static, served by unprivileged nginx
#             check    the self-containment gate (scripts/check-paths.sh --lfs); runtime and
#                      renderer both depend on it, so a symlink, a host path or an LFS
#                      pointer FAILS the build.
#
#   Blender:  amd64  official blender.org tarball, sha256-pinned.
#             arm64  blender.org ships no Linux ARM64 build, so it is compiled here from the
#                    v5.2.0 git commit against Blender's own precompiled lib-linux_arm64 at
#                    the matching v5.2.0 commit (first build ~25-40 min on a 20-core Spark;
#                    cached afterwards). The arm64 build has no CUDA kernels yet (BLENDER_CUDA
#                    stays OFF: it would also need a CUDA toolkit in the build stage), so arm64
#                    Cycles renders on CPU; amd64 ships blender.org's CUDA/OptiX kernels.
ARG BASE_IMAGE=docker.io/library/ubuntu:24.04@sha256:24737cef17f4e22b1977df7d9a05e77c4e28b7da5b8911f8d8ccda136bf3573c
ARG NODE_IMAGE=docker.io/library/node:22.21-bookworm-slim@sha256:25b3eb23a00590b7499f2a2ce939322727fcce1b15fdd69754fcd09536a3ae2c
ARG NGINX_IMAGE=docker.io/nginxinc/nginx-unprivileged:1.29-alpine@sha256:0c79d56aee561a1d81c63f00eee5fb5fe29279560cdc55e91425133104c7fbe6

# ── Gate: the tree must be self-contained ────────────────────────────────────
FROM ${BASE_IMAGE} AS check
COPY scripts/check-paths.sh .pathcheck-allow /gate/
COPY . /src
RUN bash /gate/check-paths.sh /src --lfs && touch /gate/passed

# ── Blender, amd64: official tarball, checksum-pinned ────────────────────────
FROM ${BASE_IMAGE} AS blender-amd64
ARG BLENDER_VERSION=5.2.0
ARG BLENDER_SERIES=5.2
ARG BLENDER_X64_SHA256=96f6c181a30f4950607839dc84d42a354b250d8a0231b098b59b7bc69c351c48
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl xz-utils \
 && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL -o /tmp/blender.tar.xz \
      "https://download.blender.org/release/Blender${BLENDER_SERIES}/blender-${BLENDER_VERSION}-linux-x64.tar.xz" \
 && echo "${BLENDER_X64_SHA256}  /tmp/blender.tar.xz" | sha256sum -c - \
 && mkdir -p /opt/blender && tar -xJf /tmp/blender.tar.xz -C /opt/blender --strip-components=1 \
 && rm /tmp/blender.tar.xz

# ── Blender, arm64: built from source at pinned commits ──────────────────────
# blender            v5.2.0 = fbe6228777e7d9afefcd61a413844e790ae75db7
# lib-linux_arm64    v5.2.0 = c1f0435fde33f7dc921584018a39b11eef78d98a  (Blender's precompiled deps)
FROM ${BASE_IMAGE} AS blender-src
ARG BLENDER_GIT_COMMIT=fbe6228777e7d9afefcd61a413844e790ae75db7
ARG BLENDER_LIBS_COMMIT=c1f0435fde33f7dc921584018a39b11eef78d98a
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git git-lfs build-essential cmake ninja-build python3 patchelf \
      libx11-dev libxxf86vm-dev libxcursor-dev libxi-dev libxrandr-dev libxinerama-dev \
      libegl-dev libgl-dev libwayland-dev wayland-protocols libxkbcommon-dev libdbus-1-dev \
      libdecor-0-dev linux-libc-dev libxfixes-dev libxrender-dev \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN git init -q blender && cd blender \
 && git remote add origin https://projects.blender.org/blender/blender.git \
 && git fetch -q --depth 1 origin ${BLENDER_GIT_COMMIT} && git checkout -q FETCH_HEAD \
 && mkdir -p lib && git init -q lib/linux_arm64 && cd lib/linux_arm64 \
 && git remote add origin https://projects.blender.org/blender/lib-linux_arm64.git \
 && git lfs install --local && git fetch -q --depth 1 origin ${BLENDER_LIBS_COMMIT} && git checkout -q FETCH_HEAD \
 && git lfs pull && rm -rf .git/lfs/objects \
 && du -sh /src/blender /src/blender/lib/linux_arm64

FROM blender-src AS blender-build
ARG BLENDER_CUDA=OFF
RUN apt-get update && apt-get install -y --no-install-recommends gcc-14 g++-14 && rm -rf /var/lib/apt/lists/*
ENV CC=gcc-14 CXX=g++-14
RUN cmake -S /src/blender -B /src/build -G Ninja \
      -C /src/blender/build_files/cmake/config/blender_release.cmake \
      -DCMAKE_BUILD_TYPE=Release -DWITH_INSTALL_PORTABLE=ON -DCMAKE_INSTALL_PREFIX=/opt/blender \
      -DWITH_CYCLES_CUDA_BINARIES=${BLENDER_CUDA} -DWITH_CYCLES_DEVICE_OPTIX=OFF \
      -DWITH_CYCLES_DEVICE_HIP=OFF -DWITH_CYCLES_HIP_BINARIES=OFF -DWITH_CYCLES_DEVICE_HIPRT=OFF \
      -DWITH_CYCLES_DEVICE_ONEAPI=OFF -DWITH_CYCLES_ONEAPI_BINARIES=OFF \
      -DWITH_BUILDINFO=OFF -DWITH_DOC_MANPAGE=OFF \
 && cmake --build /src/build -j"$(nproc)" \
 && cmake --install /src/build \
 && rm -rf /src/build
# The install step does not copy every precompiled shared lib (e.g. libopenxr_loader); copy any
# that the binary still cannot resolve from lib/linux_arm64 into the portable lib/ dir, then
# FAIL if anything is still unresolved.
RUN apt-get update && apt-get install -y --no-install-recommends libsm6 libice6 && rm -rf /var/lib/apt/lists/* \
 && for l in $(LD_LIBRARY_PATH=/opt/blender/lib ldd /opt/blender/blender | awk '/not found/{print $1}' | sort -u); do \
      f=$(find /src/blender/lib/linux_arm64 -name "$l" | head -1); \
      [ -z "$f" ] || cp -av "$(dirname "$f")/${l%%.so*}.so"* /opt/blender/lib/; \
    done \
 && ! LD_LIBRARY_PATH=/opt/blender/lib ldd /opt/blender/blender | grep 'not found' \
 && LD_LIBRARY_PATH=/opt/blender/lib /opt/blender/blender --version

FROM blender-build AS blender-arm64

ARG TARGETARCH
FROM blender-${TARGETARCH} AS blender

# ── llama.cpp llama-tts (optional local voice), pinned tag b9940 ─────────────
FROM ${BASE_IMAGE} AS llama-tts
ARG LLAMA_CPP_COMMIT=259f2e2a531af9ed3efa7f66adaa5eb5b53da95f
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git build-essential cmake \
 && rm -rf /var/lib/apt/lists/*
RUN git init -q /src && cd /src && git remote add origin https://github.com/ggml-org/llama.cpp.git \
 && git fetch -q --depth 1 origin ${LLAMA_CPP_COMMIT} && git checkout -q FETCH_HEAD \
 && cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=OFF \
      -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_SERVER=OFF \
 && cmake --build build -j"$(nproc)" --target llama-tts \
 && install -m 0755 build/bin/llama-tts /usr/local/bin/llama-tts && rm -rf /src

# ── Renderer UI (three-vrm), built from the lockfile ─────────────────────────
FROM ${NODE_IMAGE} AS renderer-build
WORKDIR /app
COPY interfaces/clyffy-avatar/renderer/package.json interfaces/clyffy-avatar/renderer/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY interfaces/clyffy-avatar/renderer/ ./
RUN npx vite build && test -s dist/index.html && test -s dist/clyffy.vrm

FROM ${NGINX_IMAGE} AS renderer
COPY --from=check /gate/passed /tmp/.clyffy-check-passed
COPY container/renderer-nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=renderer-build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz && wget -q --spider http://127.0.0.1:8080/clyffy.vrm || exit 1

# ── Runtime ──────────────────────────────────────────────────────────────────
FROM ${BASE_IMAGE} AS runtime
ARG BLENDER_SERIES=5.2
ARG VRM_ADDON_VERSION=4.4.0
ARG VRM_ADDON_SHA256=83facc17c8ed2b3e450fef15bd11110946bd610c6ff7a01330b025a71de6788d
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    BLENDER=/opt/blender/blender \
    CLYFFY_ROOT=/clyffy \
    CLYFFY_CYCLES_DEVICE=CPU \
    CLYFFY_OUT=/data/out \
    CLYFFY_SPOOL=/data/jobs \
    CLYFFY_MODELS=/data/models \
    CLYFFY_TTS_BIN=/usr/local/bin/llama-tts \
    XDG_CACHE_HOME=/data/cache \
    BLENDER_USER_RESOURCES=/opt/blender-user \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics
# Shared libraries Blender needs even in background (-b) mode, plus ffmpeg for the drive/reel tools.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl python3 tini xz-utils procps ffmpeg \
      libx11-6 libxi6 libxxf86vm1 libxfixes3 libxrender1 libxkbcommon0 libxkbcommon-x11-0 libxext6 libxrandr2 libxinerama1 libxcursor1 \
      libsm6 libice6 libgl1 libegl1 libglu1-mesa libgomp1 \
      libwayland-client0 libwayland-cursor0 libwayland-egl1 libdecor-0-0 \
      libdbus-1-3 libfontconfig1 libfreetype6 libtbb12 \
 && rm -rf /var/lib/apt/lists/*
COPY --from=blender /opt/blender /opt/blender
ENV LD_LIBRARY_PATH=/opt/blender/lib:/opt/blender/libExt
RUN ln -s /opt/blender/blender /usr/local/bin/blender \
 && ! ldd /opt/blender/blender | grep "not found" \
 && blender --version
# Python deps into Blender's bundled interpreter.
COPY requirements.txt /tmp/requirements.txt
RUN PY=$(ls /opt/blender/${BLENDER_SERIES}/python/bin/python3.* | head -1) \
 && "$PY" -m ensurepip --upgrade >/dev/null 2>&1 || true \
 && "$PY" -m pip install --no-cache-dir -r /tmp/requirements.txt \
 && rm /tmp/requirements.txt
# VRM Add-on for Blender (pinned, checksum-verified).
RUN curl -fsSL -o /tmp/vrm.zip \
      "https://github.com/saturday06/VRM-Addon-for-Blender/releases/download/v${VRM_ADDON_VERSION}/VRM_Addon_for_Blender-Extension-$(echo ${VRM_ADDON_VERSION} | tr . _).zip" \
 && echo "${VRM_ADDON_SHA256}  /tmp/vrm.zip" | sha256sum -c - \
 && blender -b --factory-startup --command extension install-file -r user_default --enable /tmp/vrm.zip \
 && rm /tmp/vrm.zip
COPY --from=llama-tts /usr/local/bin/llama-tts /usr/local/bin/llama-tts
RUN useradd -m -u 10001 clyffy && chown -R clyffy:clyffy /opt/blender-user \
 && mkdir -p /data/out /data/jobs /data/cache /data/models && chown -R clyffy:clyffy /data
COPY --from=check /gate/passed /tmp/.clyffy-check-passed
COPY --chown=clyffy:clyffy . /clyffy
RUN chmod +x /clyffy/scripts/*.sh /clyffy/scripts/worker.py /clyffy/install.sh \
 && ln -s /clyffy/scripts/clyffy.sh /usr/local/bin/clyffy
USER clyffy
WORKDIR /clyffy
VOLUME ["/data/out", "/data/jobs", "/data/cache", "/data/models"]
HEALTHCHECK --interval=5m --timeout=90s --start-period=30s --retries=3 \
  CMD ["/clyffy/scripts/healthcheck.sh", "--quick"]
ENTRYPOINT ["/usr/bin/tini", "--", "/clyffy/scripts/clyffy.sh"]
CMD ["idle"]

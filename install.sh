#!/usr/bin/env bash
# One-shot installer (single container, Docker or Podman): build the image for this machine,
# start it with this checkout mounted at /clyffy (live-edit loop), and run the health check.
# For the self-contained multi-service setup use `docker compose up` instead (see README).   ./install.sh [--build-only] [--no-health]
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
ROOT="$PWD"
# shellcheck disable=SC1091
source ./versions.env
[[ -f .env ]] && set -a && source ./.env && set +a
IMAGE="${CLYFFY_IMAGE:-localhost/clyffy-avatar:dev}"
NAME="${CLYFFY_CONTAINER:-clyffy-avatar}"
BUILD_ONLY=0; HEALTH=1
for a in "$@"; do case "$a" in
  --build-only) BUILD_ONLY=1 ;; --no-health) HEALTH=0 ;;
  -h|--help) sed -n '2,4p' "$0"; exit 0 ;; *) echo "unknown option $a"; exit 2 ;; esac; done

die() { echo "install: $*" >&2; exit 1; }
ENGINE="${CLYFFY_ENGINE:-}"
if [[ -z "$ENGINE" ]]; then
  if command -v podman >/dev/null; then ENGINE=podman
  elif command -v docker >/dev/null; then ENGINE=docker
  else die "need podman or docker"; fi
fi
command -v git-lfs >/dev/null && git lfs pull 2>/dev/null || echo "install: git-lfs not found; art binaries stay as pointers (sudo apt install git-lfs && git lfs pull)"

ARCH="$(uname -m)"
BUILD_ARGS=(--build-arg "BASE_IMAGE=$BASE_IMAGE" --build-arg "BLENDER_VERSION=$BLENDER_VERSION"
            --build-arg "BLENDER_SERIES=$BLENDER_SERIES" --build-arg "BLENDER_X64_SHA256=$BLENDER_X64_SHA256"
            --build-arg "VRM_ADDON_VERSION=$VRM_ADDON_VERSION" --build-arg "VRM_ADDON_SHA256=$VRM_ADDON_SHA256")
case "$ARCH" in
  x86_64|amd64) PLATFORM=linux/amd64 ;;
  aarch64|arm64)
    PLATFORM=linux/arm64
    echo "install: arm64 — Blender is compiled from source inside the build (first build ~25-40 min, cached after)" ;;
  *) die "unsupported arch $ARCH" ;;
esac

echo "install: building $IMAGE for $PLATFORM with $ENGINE"
if [[ "$ENGINE" == docker ]]; then
  docker buildx build --load --platform "$PLATFORM" "${BUILD_ARGS[@]}" -t "$IMAGE" .
else
  podman build --format docker --platform "$PLATFORM" "${BUILD_ARGS[@]}" -t "$IMAGE" .
fi
[[ $BUILD_ONLY -eq 1 ]] && exit 0

GPU="${CLYFFY_GPU:-auto}"; GPU_FLAGS=()
if [[ "$GPU" == auto ]]; then
  GPU=none
  if command -v nvidia-smi >/dev/null && nvidia-smi -L >/dev/null 2>&1; then
    if [[ "$ENGINE" == podman ]] && { [[ -e /etc/cdi/nvidia.yaml ]] || [[ -e /var/run/cdi/nvidia.yaml ]]; }; then GPU=cdi
    elif [[ "$ENGINE" == docker ]]; then GPU=gpus; fi
  fi
fi
case "$GPU" in
  cdi)  GPU_FLAGS=(--device "${CLYFFY_CDI_DEVICE:-nvidia.com/gpu=all}") ;;
  gpus) GPU_FLAGS=(--gpus all) ;;
  none) ;;
  *) die "CLYFFY_GPU must be auto|none|cdi|gpus" ;;
esac
echo "install: GPU mode: $GPU"

"$ENGINE" rm -f "$NAME" >/dev/null 2>&1 || true
SEL=""; USERFLAGS=(--user "$(id -u):$(id -g)")
if [[ "$ENGINE" == podman ]]; then SEL=":Z"; USERFLAGS=(--userns=keep-id); fi
"$ENGINE" run -d --name "$NAME" "${GPU_FLAGS[@]}" \
  -e HOME=/tmp -e CLYFFY_CYCLES_DEVICE="${CLYFFY_CYCLES_DEVICE:-CPU}" \
  "${USERFLAGS[@]}" \
  -e CLYFFY_OUT=/clyffy/out -e XDG_CACHE_HOME=/tmp/.cache \
  -v "$ROOT:/clyffy$SEL" "$IMAGE" idle >/dev/null
echo "install: container $NAME running"
if [[ $HEALTH -eq 1 ]]; then "$ENGINE" exec "$NAME" clyffy health; fi
cat <<MSG

Next:
  $ENGINE exec $NAME clyffy render            # -> out/render.png in this checkout
  $ENGINE exec $NAME clyffy health --render
  $ENGINE exec -it $NAME clyffy shell
MSG

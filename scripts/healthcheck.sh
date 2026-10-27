#!/usr/bin/env bash
# Health check for the Clyffy avatar toolchain.
#   --quick   Blender starts headless, pinned version, Python deps + VRM add-on importable (container HEALTHCHECK)
#   (default) quick + repo/asset checks + GPU visibility report
#   --render  default + a tiny Cycles render of a generated scene
#   --worker  quick + the render worker's heartbeat is fresh (compose worker healthcheck)
set -uo pipefail
MODE="${1:-}"
ROOT="${CLYFFY_ROOT:-$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)}"
BLENDER="${BLENDER:-blender}"
WANT_SERIES="$(grep -E '^BLENDER_SERIES=' "$ROOT/versions.env" 2>/dev/null | cut -d= -f2)"
WANT_SERIES="${WANT_SERIES:-5.2}"
fail=0
ok()   { echo "  ok   $*"; }
warn() { echo "  warn $*"; }
bad()  { echo "  FAIL $*"; fail=1; }

echo "clyffy health (${MODE:-full})"
ver="$("$BLENDER" --version 2>/dev/null | head -1)"
if [[ "$ver" == "Blender $WANT_SERIES"* ]]; then ok "$ver"; else bad "Blender $WANT_SERIES.x required, got: ${ver:-<not found>}"; fi

probe="$("$BLENDER" -b --factory-startup --python-exit-code 1 --python-expr '
import sys, importlib, addon_utils
mods = ["numpy", "PIL", "scipy", "bmesh", "mathutils"]
for m in mods:
    importlib.import_module(m)
vrm = [m.__name__ for m in addon_utils.modules() if "vrm" in m.__name__.lower()]
print("CLYFFY_PROBE deps=ok vrm=" + (",".join(vrm) or "missing"))
' 2>&1 | grep CLYFFY_PROBE)"
if [[ "$probe" == *"deps=ok"* ]]; then ok "python deps importable in Blender"; else bad "python deps missing in Blender's Python (see requirements.txt)"; fi
if [[ "$probe" == *"vrm=missing"* || -z "$probe" ]]; then bad "VRM add-on not installed"; else ok "VRM add-on present (${probe##*vrm=})"; fi

if [[ "$MODE" == "--worker" ]]; then
  hb="${CLYFFY_HEARTBEAT:-/tmp/clyffy-worker.heartbeat}"
  if [[ -f "$hb" ]] && (( $(date +%s) - $(stat -c %Y "$hb") < ${CLYFFY_HEARTBEAT_MAX_AGE:-120} )); then ok "worker heartbeat fresh"
  else
    # a long render legitimately stops the heartbeat; a running blender counts as alive
    if pgrep -x blender >/dev/null 2>&1; then ok "worker busy rendering"; else bad "worker heartbeat stale or missing ($hb)"; fi
  fi
fi

if [[ "$MODE" != "--quick" && "$MODE" != "--worker" ]]; then
  for f in tools/blkit.py archive/Clyffy_Avatar/clyffy.pack.toml archive/Clyffy_Avatar/tools/rebuild.sh scripts/worker.py; do
    [[ -f "$ROOT/$f" ]] && ok "$f" || bad "missing $f"
  done
  for f in work/RETOPO_clyffy.blend archive/Clyffy_Avatar/mesh/canon/body/clyffy.vrm; do
    if [[ ! -f "$ROOT/$f" ]]; then bad "$f missing from the image/checkout"
    elif head -c 64 "$ROOT/$f" | grep -q 'git-lfs'; then warn "$f is an LFS pointer — run: git lfs pull"
    else ok "$f ($(du -h "$ROOT/$f" | cut -f1))"; fi
  done
  command -v ffmpeg >/dev/null && ok "ffmpeg $(ffmpeg -version | head -1 | cut -d' ' -f3)" || warn "ffmpeg not found (avatar_drive / demo reels need it)"
  command -v "${CLYFFY_TTS_BIN:-llama-tts}" >/dev/null && ok "llama-tts present" || warn "llama-tts not found (optional local TTS)"
  if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
    ok "GPU visible: $(nvidia-smi --query-gpu=name,driver_version --format=csv,noheader | head -1)"
  else
    warn "no NVIDIA GPU visible (CPU rendering only)"
  fi
fi

if [[ "$MODE" == "--render" ]]; then
  out="$(mktemp -d)/health.png"
  if CLYFFY_RES=64x64 CLYFFY_SAMPLES=4 "$BLENDER" -b --factory-startup --python "$ROOT/scripts/render_still.py" -- "$out" >/dev/null 2>&1 && [[ -s "$out" ]]; then
    ok "headless Cycles render ($out)"
  else
    bad "headless render failed"
  fi
fi
[[ $fail -eq 0 ]] && echo "HEALTHY" || echo "UNHEALTHY"
exit $fail

#!/usr/bin/env bash
# clyffy — container entrypoint / CLI for the avatar toolchain.
set -euo pipefail
ROOT="${CLYFFY_ROOT:-$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)}"
BLENDER="${BLENDER:-blender}"
cd "$ROOT"
usage() {
  cat <<USAGE
usage: clyffy <command> [args]
  health [--quick|--render]     run the health check (exit 0 = healthy)
  render [BLEND] [OUT.png]      headless still render (default: work/RETOPO_clyffy.blend -> $CLYFFY_OUT/render.png)
  worker                        stateless render worker on the shared job spool (scale with --scale worker=N)
  submit [BLEND] [--wait] ...   queue a render job for the workers (see scripts/worker.py --help)
  fetch-models                  download + sha256-verify the optional TTS models into $CLYFFY_MODELS
  tts "TEXT" [OUT.wav]          local OuteTTS line via llama-tts (needs fetch-models first)
  check                         path/symlink self-containment check (scripts/check-paths.sh)
  run SCRIPT.py [BLEND] [-- ARGS]  run a pipeline script in Blender background mode
  rebuild [--vrm|--from-scratch]   legacy 12-stage chain (archive/Clyffy_Avatar/tools/rebuild.sh)
  blender [ARGS...]             pass-through to Blender (add -b for headless)
  idle                          keep the container alive for 'exec' use (default)
  shell                         interactive bash
USAGE
}
cmd="${1:-idle}"; shift || true
case "$cmd" in
  health)  exec "$ROOT/scripts/healthcheck.sh" "$@" ;;
  render)
    blend="${1:-work/RETOPO_clyffy.blend}"; out="${2:-${CLYFFY_OUT:-out}/render.png}"
    mkdir -p "$(dirname "$out")"
    exec "$BLENDER" -b "$blend" --python "$ROOT/scripts/render_still.py" -- "$out" ;;
  run)
    script="$1"; shift; blend=""
    if [ $# -gt 0 ] && [ "$1" != "--" ]; then blend="$1"; shift; fi
    [ "${1:-}" = "--" ] && shift
    exec "$BLENDER" -b ${blend:+"$blend"} --python "$script" -- "$@" ;;
  worker|submit) exec python3 "$ROOT/scripts/worker.py" "$cmd" "$@" ;;
  fetch-models) exec "$ROOT/scripts/fetch-models.sh" "$@" ;;
  tts)
    text="${1:?usage: clyffy tts \"TEXT\" [OUT.wav]}"; out="${2:-${CLYFFY_OUT:-out}/voice/tts-$(date +%Y%m%d-%H%M%S).wav}"
    M="${CLYFFY_MODELS:-/data/models}"
    export CLYFFY_TTS_LLM="${CLYFFY_TTS_LLM:-$M/OuteTTS-0.2-500M-Q5_K_M.gguf}" CLYFFY_TTS_VOC="${CLYFFY_TTS_VOC:-$M/WavTokenizer-Large-75-F16.gguf}"
    exec python3 "$ROOT/archive/Clyffy_Avatar/tools/voice_tts.py" --text "$text" --out "$out" --threads "${CLYFFY_TTS_THREADS:-$(nproc)}" ;;
  check) exec "$ROOT/scripts/check-paths.sh" "$ROOT" "$@" ;;
  rebuild) cd "$ROOT/archive/Clyffy_Avatar" && BLENDER="$BLENDER" exec ./tools/rebuild.sh "$@" ;;
  blender) exec "$BLENDER" "$@" ;;
  idle)    echo "clyffy: idle; use 'docker exec <ctr> clyffy …'"; exec sleep infinity ;;
  shell)   exec bash ;;
  -h|--help|help) usage ;;
  *) echo "unknown command: $cmd" >&2; usage; exit 2 ;;
esac

#!/usr/bin/env bash
# fetch-models — download the optional local-TTS models (OuteTTS 0.2 500M + WavTokenizer)
# into $CLYFFY_MODELS (default /data/models, a named volume under compose).
#
# Why a download step and not Git LFS: the weights are third-party (OuteTTS 0.2 is
# CC BY-NC 4.0, WavTokenizer is MIT), ~556 MB together, and already hosted immutably on
# Hugging Face. Each file is pinned to a repo COMMIT and verified by size + sha256, so the
# result is byte-identical everywhere. Re-running is a no-op once the files verify.
set -euo pipefail
DEST="${CLYFFY_MODELS:-/data/models}"
mkdir -p "$DEST"
# name | url (pinned commit) | bytes | sha256
MODELS=(
  "OuteTTS-0.2-500M-Q5_K_M.gguf|https://huggingface.co/OuteAI/OuteTTS-0.2-500M-GGUF/resolve/e6d78720d2a8edce2bc8f5c5c2d0332e57091930/OuteTTS-0.2-500M-Q5_K_M.gguf|425684608|fbba13898b4ce7f2b181d074eea0c73cc3a513a042faf166f7beaed29eac933c"
  "WavTokenizer-Large-75-F16.gguf|https://huggingface.co/ggml-org/WavTokenizer/resolve/0c97fdc098158ec9bf4e703cd5f81a5aa20520e6/WavTokenizer-Large-75-F16.gguf|130186688|2356baa8631cc2995ea3465196a017a2733600d849a91180c0f97fa7fb375bbe"
)
for m in "${MODELS[@]}"; do
  IFS='|' read -r name url size sha <<<"$m"
  f="$DEST/$name"
  if [[ -f "$f" && "$(stat -c %s "$f")" == "$size" ]] && echo "$sha  $f" | sha256sum -c --status -; then
    echo "fetch-models: ok      $name"; continue
  fi
  echo "fetch-models: get     $name ($((size/1048576)) MiB)"
  curl -fL --retry 3 --retry-delay 5 -o "$f.part" "$url"
  [[ "$(stat -c %s "$f.part")" == "$size" ]] || { echo "fetch-models: size mismatch for $name" >&2; rm -f "$f.part"; exit 1; }
  echo "$sha  $f.part" | sha256sum -c --status - || { echo "fetch-models: sha256 mismatch for $name" >&2; rm -f "$f.part"; exit 1; }
  mv "$f.part" "$f"
  echo "fetch-models: ok      $name (sha256 verified)"
done

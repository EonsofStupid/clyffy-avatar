#!/usr/bin/env bash
# check-paths — fail if the tree reaches outside itself.
#
#   scripts/check-paths.sh [ROOT] [--lfs]
#
# FAILS (exit 1) on:
#   * any symlink at all (a clone on Windows / in a build context cannot follow them, and an
#     in-repo copy is always possible), and in particular any symlink whose target is absolute
#     or resolves outside ROOT;
#   * any host path in a tracked text file: /home/<user>, /Users/<user>, C:\Users, ~/…,
#     /root/…, /mnt/…, /media/…, a host Blender install (/opt/blender-5.x), or a
#     Projects/… checkout path;
#   * with --lfs: any Git-LFS pointer left in place of a real file (run `git lfs pull`).
# Lines that only *describe* such a path (history, third-party paths baked into vendor
# files) can be listed in .pathcheck-allow as  <file><TAB><fixed substring of the line>.
# Runs in `make check`, in the Dockerfile `check` stage, and in CI.
set -uo pipefail
ROOT="."; LFS=0
for a in "$@"; do case "$a" in --lfs) LFS=1 ;; -h|--help) sed -n '2,17p' "$0"; exit 0 ;; *) ROOT="$a" ;; esac; done
cd "$ROOT" || exit 2
ROOT_ABS="$(pwd -P)"
fail=0
bad() { echo "check-paths: FAIL $*"; fail=1; }

# File list: git's view when available, else everything except VCS / build junk.
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  mapfile -d '' FILES < <(git ls-files -z --cached --others --exclude-standard)
else
  mapfile -d '' FILES < <(find . \( -name .git -o -name node_modules -o -name dist \) -prune -o \( -type f -o -type l \) -print0 | sed -z 's|^\./||')
fi

# 1. symlinks
for f in "${FILES[@]}"; do
  [[ -L "$f" ]] || continue
  t="$(readlink "$f")"
  r="$(realpath -m "$(dirname "$f")/$t")"
  if [[ "$t" == /* || "$r" != "$ROOT_ABS"/* ]]; then bad "symlink leaves the repo: $f -> $t"
  else bad "symlink (replace with the real file): $f -> $t"; fi
done

# 2. host paths in text files
PAT='/home/[A-Za-z0-9_.-]+|/Users/[A-Za-z0-9_.-]+|[A-Za-z]:\\\\?Users\\\\|(^|[^A-Za-z0-9_.$}])~/[A-Za-z0-9_.]|(^|[^A-Za-z0-9_.])/root/|(^|[^A-Za-z0-9_.])/mnt/|(^|[^A-Za-z0-9_.])/media/[a-z]|/opt/blender-[0-9]|(^|[^A-Za-z0-9_])Projects/'
ALLOW=()
[[ -f .pathcheck-allow ]] && mapfile -t ALLOW < <(tr -d '\r' < .pathcheck-allow | grep -v '^\s*#' | grep -v '^\s*$')
TEXT=()
for f in "${FILES[@]}"; do [[ -f "$f" && ! -L "$f" && "$f" != .pathcheck-allow && "$f" != scripts/check-paths.sh ]] && TEXT+=("$f"); done
while IFS= read -r hit; do
  hit="${hit%$'\r'}"; file="${hit%%:*}"; rest="${hit#*:}"; line="${rest#*:}"
  ok=0
  for a in "${ALLOW[@]}"; do
    af="${a%%$'\t'*}"; as="${a#*$'\t'}"
    [[ "$file" == "$af" && "$line" == *"$as"* ]] && { ok=1; break; }
  done
  [[ $ok -eq 0 ]] && bad "host path: ${hit:0:200}"
done < <(printf '%s\0' "${TEXT[@]}" | xargs -0 -r grep -I -n -H -E "$PAT" 2>/dev/null)

# 3. LFS pointers
if [[ $LFS -eq 1 ]]; then
  for f in "${TEXT[@]}"; do
    case "$f" in *.blend|*.vrm|*.glb|*.fbx|*.mp4|*.png) ;; *) continue ;; esac
    if [[ $(stat -c %s "$f") -lt 1024 ]] && head -c 64 "$f" | grep -q '^version https://git-lfs'; then
      bad "LFS pointer, not the file: $f (run: git lfs install && git lfs pull)"
    fi
  done
fi

if [[ $fail -eq 0 ]]; then echo "check-paths: OK (${#FILES[@]} files, no symlinks, no host paths$([[ $LFS -eq 1 ]] && echo ", no LFS pointers"))"; fi
exit $fail

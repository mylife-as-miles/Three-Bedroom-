#!/usr/bin/env bash
# Reproducible Linux build of the dconstruct CLI (disassembler + decompiler).
#
# Copies the needed sources out of the pristine clone at .private/ext/dconstruct,
# applies the patches in ./patches, drops in our own CMakeLists.txt and builds
# into .private/build/dconstruct-linux. The clone itself is never modified.
#
# Usage: tools/extract/dconstruct_linux/build.sh [--install-deps] [--clean]
#   --install-deps  apt-get install g++-14, cmake, libtbb-dev, curl, patch
#   --clean         wipe the build dir first
# Env overrides: DCONSTRUCT_SRC, DCONSTRUCT_BUILD, CXX (default g++-14), JOBS
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
SRC="${DCONSTRUCT_SRC:-$REPO/.private/ext/dconstruct}"
OUT="${DCONSTRUCT_BUILD:-$REPO/.private/build/dconstruct-linux}"
CXX_BIN="${CXX:-g++-14}"
JOBS="${JOBS:-$(nproc)}"

# ctre (compile-time regular expressions) single header; upstream gets it via the
# qui submodule, which we don't need. Pinned tag + checksum.
CTRE_URL="https://raw.githubusercontent.com/hanickadot/compile-time-regular-expressions/v3.10.0/single-header/ctre.hpp"
CTRE_SHA256="f1492c647adb026b0b4ce08f412bdab9d66b2236c9afe17592c0192b7e005637"

for arg in "$@"; do
  case "$arg" in
    --install-deps)
      apt-get update
      apt-get install -y g++-14 cmake make libtbb-dev curl patch
      ;;
    --clean) rm -rf "$OUT" ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

[ -f "$SRC/source/main_cli.cpp" ] || { echo "dconstruct clone not found at $SRC" >&2; exit 1; }
command -v "$CXX_BIN" >/dev/null || { echo "$CXX_BIN not found (try --install-deps)" >&2; exit 1; }

echo "== dconstruct source: $SRC ($(git -C "$SRC" rev-parse --short HEAD 2>/dev/null || echo '?'))"
echo "== build dir:         $OUT"

# 1. fresh copy of just the pieces the CLI needs
rm -rf "$OUT/src"
mkdir -p "$OUT/src/source" "$OUT/third_party"
cp -r "$SRC/include" "$OUT/src/"
for d in disassembly decompilation compilation ast base; do
  cp -r "$SRC/source/$d" "$OUT/src/source/"
done
cp "$SRC/source/main_cli.cpp" "$OUT/src/source/"
cp "$HERE/CMakeLists.txt" "$OUT/src/CMakeLists.txt"

# 2. patches
for p in "$HERE"/patches/*.patch; do
  echo "== applying $(basename "$p")"
  patch -s -p1 -d "$OUT/src" < "$p"
done

# 3. ctre.hpp
if ! echo "$CTRE_SHA256  $OUT/third_party/ctre.hpp" | sha256sum -c --status 2>/dev/null; then
  echo "== fetching ctre.hpp"
  curl -sSfL -o "$OUT/third_party/ctre.hpp" "$CTRE_URL"
  echo "$CTRE_SHA256  $OUT/third_party/ctre.hpp" | sha256sum -c
fi

# 4. configure + build
cmake -S "$OUT/src" -B "$OUT/build" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CXX_COMPILER="$CXX_BIN" \
  -DCTRE_INCLUDE_DIR="$OUT/third_party"
cmake --build "$OUT/build" -j"$JOBS"

# 5. sidbase next to the executable (executable_relative_sidbase())
SIDBASE="$SRC/test/fixtures/dc/sidbase_new_fixed.bin"
if [ -f "$SIDBASE" ]; then
  cmp -s "$SIDBASE" "$OUT/build/sidbase.bin" 2>/dev/null || cp "$SIDBASE" "$OUT/build/sidbase.bin"
else
  echo "WARNING: $SIDBASE missing; put a sidbase.bin next to $OUT/build/dconstruct" >&2
fi

echo "== built: $OUT/build/dconstruct"

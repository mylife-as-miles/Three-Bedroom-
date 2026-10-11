#!/usr/bin/env bash
# Installs the pinned toolchain from official distributions and verifies checksums.
#   Blender 5.2.2 LTS  (download.blender.org)          -> authoring + offline reference renders
#   Godot 4.6.3 stable (github.com/godotengine/godot-builds) -> browser runtime only
# Usage: build/setup_toolchain.sh [install_dir]   (default /opt/tools)
set -euo pipefail
DEST="${1:-/opt/tools}"
BLENDER_VER=5.2.2
BLENDER_SHA256=84098912789dc450e95697c4184fb8a90acbe5111c2ba4aede3fecb57806a168
GODOT_VER=4.6.3
GODOT_ZIP_SHA512=a035258da32b77f966a5376f9fa29c30a6adde826a85ba918e1605bd1fc9823eba7d85f1dd5e748956bd2ba72827c0025ffa11bb82aec91128c407a2e723c99c
GODOT_TPZ_SHA512=da606b61c10157844f8300172df374472665f95015495cb1a7cd132c40ede404faa96cc1016a4b9662db9909ddea69632c4948b2cd11163438dad4808881fb68
mkdir -p "$DEST" && cd "$DEST"

if [ ! -x "blender-$BLENDER_VER-linux-x64/blender" ]; then
  f="blender-$BLENDER_VER-linux-x64.tar.xz"
  curl -fsSL -o "$f" "https://download.blender.org/release/Blender5.2/$f"
  echo "$BLENDER_SHA256  $f" | sha256sum -c -
  tar -xf "$f" && rm "$f"
fi

GODOT_BIN="Godot_v$GODOT_VER-stable_linux.x86_64"
if [ ! -x "$GODOT_BIN" ]; then
  f="$GODOT_BIN.zip"
  curl -fsSL -o "$f" "https://github.com/godotengine/godot-builds/releases/download/$GODOT_VER-stable/$f"
  echo "$GODOT_ZIP_SHA512  $f" | sha512sum -c -
  unzip -o -q "$f" && rm "$f"
fi

TPL="$HOME/.local/share/godot/export_templates/$GODOT_VER.stable"
if [ ! -f "$TPL/web_nothreads_release.zip" ]; then
  f="Godot_v$GODOT_VER-stable_export_templates.tpz"
  curl -fsSL -o "$f" "https://github.com/godotengine/godot-builds/releases/download/$GODOT_VER-stable/$f"
  echo "$GODOT_TPZ_SHA512  $f" | sha512sum -c -
  mkdir -p "$TPL"
  unzip -o -q -j "$f" 'templates/web*' 'templates/version.txt' -d "$TPL" && rm "$f"
fi

if [ -w /usr/local/bin ]; then
  ln -sf "$DEST/blender-$BLENDER_VER-linux-x64/blender" /usr/local/bin/blender
  ln -sf "$DEST/$GODOT_BIN" /usr/local/bin/godot
fi
"$DEST/blender-$BLENDER_VER-linux-x64/blender" --version | head -1
"$DEST/$GODOT_BIN" --headless --version

#!/usr/bin/env bash
# Fetch pinned public format/tool dependencies privately; never modifies game files.
set -euo pipefail
research_root="$(cd "$(dirname "$0")/.." && pwd)"
vendor_root="$research_root/.private/vendor"
mkdir -p "$vendor_root"
fetch_tool() {
  local tool_name="$1" tool_url="$2" tool_commit="$3"
  if [ ! -d "$vendor_root/$tool_name/.git" ]; then
    git clone --depth 1 "$tool_url" "$vendor_root/$tool_name"
  fi
  if [ "$(git -C "$vendor_root/$tool_name" rev-parse HEAD)" != "$tool_commit" ]; then
    git -C "$vendor_root/$tool_name" fetch --depth 1 origin "$tool_commit"
    git -C "$vendor_root/$tool_name" checkout --detach "$tool_commit"
  fi
}
fetch_tool dconstruct https://github.com/DeepQuantum/dconstruct 583b38d8b25b2f0b2cd079db70d8caac0a69f3a7
fetch_tool t2r-reference https://github.com/icemesh/t2r-dc-disasm bb37ab4f4af8ed5431d939cd1e5818a1641bd7f8
python3 -m pip install -r "$research_root/requirements.txt"

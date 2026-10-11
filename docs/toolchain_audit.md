# Environment and toolchain audit — 2026-10-11

## Host (measured, not assumed)

| item | value |
|---|---|
| OS | Ubuntu 24.04.5 LTS, Linux 6.18 (KVM guest, cloud container) |
| CPU | Intel Xeon @ 2.80 GHz, 4 vCPU (AVX-512 available) |
| GPU | **none** (no `/dev/dri`, no NVIDIA driver) |
| RAM | 15 GiB, no swap |
| Free disk | ~29 GB writable allowance |
| Displays | none; Xvfb available for software-GL (Mesa llvmpipe 25.2) |
| Browser | Chromium 1194 (Playwright 1.56.1); WebGL 2 via ANGLE → SwiftShader (software) |

The RTX 4060 / Ryzen 5 7600X / 32 GB figures in the original brief do **not** describe this machine.
There are no Cursor rules on this host (`~/.cursor*`, `.cursorrules` absent) and no prior project files.

## Consequences

* Cycles renders on CPU only. Reference frames are rendered at modest resolution/sample counts with OpenImageDenoise. Final-quality stills need a GPU workstation; scripts are resolution-parameterised for that.
* EEVEE works under Xvfb on llvmpipe but is slow (≈38 s shader compile on a trivial scene).
* Browser frames are captured with SwiftShader. They are **functionally faithful** (same WebGL 2 code path, same shaders) but frame-rate numbers measured here are software-rasteriser numbers and **must not** be reported as real-hardware FPS.
* Heavy jobs are serialised through `build/heavy.sh`.

## Toolchain (installed by `build/setup_toolchain.sh`)

| tool | version | source | verification |
|---|---|---|---|
| Blender | 5.2.2 LTS (build 2026-09-15, hash d13f752e3b9c) | download.blender.org/release/Blender5.2 | SHA-256 `84098912…f210 ✓` (official `blender-5.2.2.sha256`) |
| Godot | 4.6.3 stable (7d41c59c4) | github.com/godotengine/godot-builds | SHA-512 ✓ (official `SHA512-SUMS.txt`) |
| Godot web export templates | 4.6.3 (web + web_nothreads, release/debug) | same `.tpz` | SHA-512 ✓ |

The brief specified "Godot 4.6 stable"; 4.6.3 is the latest 4.6.x stable patch release and was chosen for its fixes. Same feature set.

## Pipeline smoke test (passed)

Blender 5.2.2 (headless) → Cycles CPU render ✓, EEVEE (Xvfb) render ✓, glTF 2.0 GLB export ✓ → Godot 4.6.3 headless import ✓ → Web export (nothreads, Compatibility/WebGL 2) ✓ → headless Chromium loads WASM, Godot reports `OpenGL ES 3.0 (WebGL 2.0) - Compatibility` ✓ → frame captured showing the exported geometry ✓.

## Repository / delivery constraints found

* Session GitHub scope is **`mylife-as-miles/Three-Bedroom-`** (existing, empty) on branch `ccr-80dff22c-p82ge1`. The brief's `StarKnightt/three-bedroom` is outside this session's authorised scope, so no repository was created there; work is delivered to the scoped repository instead.
* **Git LFS push is rejected**: "This repository exceeded its LFS budget." Binaries are committed as normal git objects and kept small; all are reproducible from scripts.
* `api.github.com` release metadata returns 403 through the egress proxy; release *downloads* on github.com work.

# THREE BEDROOM

First-person cinematic psychological horror prelude set in the PALINDROME universe.
Chapter One takes place at night, in 2026, inside an ordinary-looking apartment.

| Layer | Tool | Role |
|---|---|---|
| Authoring (single source of truth for all meshes, materials, rigs, animation) | **Blender 5.2.2 LTS** | `scripts/blender/` generates `blender/*.blend` deterministically |
| Interchange | glTF 2.0 / GLB | `assets/runtime/` |
| Browser runtime | **Godot 4.6.3 stable**, Compatibility renderer, WebGL 2 / WASM | `godot/` |

No Three.js (or any renderer built on it) is used anywhere.

* Production ledger (resume point for every session): [`docs/PRODUCTION_LEDGER.md`](docs/PRODUCTION_LEDGER.md)
* Toolchain: `build/setup_toolchain.sh` (pinned versions, checksum-verified)
* Heavy jobs (renders, bakes, exports, browser captures) **must** run through `build/heavy.sh`
* References: [`references/`](references/) — supplied images, byte-identical, with `manifest.json`

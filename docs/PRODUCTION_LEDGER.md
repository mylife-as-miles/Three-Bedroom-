# THREE BEDROOM — production ledger

Durable resume point. Update at the end of every phase/iteration. Newest entries at the bottom of each section.

## Status board

| Phase | Gate | Status |
|---|---|---|
| 0 Environment & toolchain | Verified reproducible toolchain | **PASSED** 2026-10-11 (see `docs/toolchain_audit.md`) |
| 1 Architectural blockout | Architecture convincingly corresponds to all reference views | in progress |
| 2 Major furniture | Space recognisable without detailed materials | not started |
| 3 High-quality geometry | Foreground objects survive close examination | not started |
| 4 Photoreal materials | Independent material-critic approval | not started |
| 5 Lighting (night) | Lighting critic approval in Cycles **and** browser | not started |
| 6 First-person hands | Hand critic finds no obvious defects | not started |
| 7 Movement & inspection | Stable interaction in live browser session | not started |
| 8 Menus & presentation | Full UI navigation with no broken states | not started |
| 9 Phone & evidence | Photo persistence; Photo Recall disabled in Ch.1 | not started |
| 10 Atmosphere & audio | Cohesive spatial sound | not started |
| 11 First puzzle slice | Completable, no softlock | not started |
| 12 Performance & export | Distributable build meeting documented targets | not started |

## Decisions

* D-001 Godot 4.6.3 stable (latest 4.6.x patch) as browser runtime; Compatibility renderer; single-threaded web export (`web_nothreads`) so the build runs without cross-origin-isolation headers on ordinary static hosting.
* D-002 Git LFS unavailable (budget exhausted) → plain git binaries, size-capped, reproducible from scripts.
* D-003 Delivery repository is the session-scoped `mylife-as-miles/Three-Bedroom-`, not `StarKnightt/three-bedroom` (outside authorised scope).
* D-004 Reference set is 20 images: 11 apartment views (APT01–APT11), 1 asset-kit overview (KIT01), 7 night-mood + 1 UI-mood references. Canonical architecture derives only from APT* (+KIT01 for object identity).
* D-005 Static lighting will be baked in Blender (Cycles) into lightmap UVs and applied at runtime; dynamic lights (phone flashlight, toggled practicals) stay real-time. Godot's own lightmapper needs a RenderingDevice which the GPU-less host and the Compatibility target do not provide.

## Iteration log

### 2026-10-11 — Phase 0
* Installed + checksum-verified Blender 5.2.2 LTS and Godot 4.6.3 (+ web templates).
* Proved the full pipeline Blender → GLB → Godot → Web → Chromium frame capture.
* Ingested references byte-identically; manifest + contact sheets.
* Tried Git LFS: rejected by GitHub (budget). Switched to plain git.

## Open blockers / limitations

* No GPU: Cycles stills are CPU-rendered at reduced resolution/samples; browser FPS measured under SwiftShader is not representative of real hardware. A real-hardware performance pass is required before any FPS claim.
* No pre-existing Inez character assets are available in this workspace; hands will be authored from scratch and flagged for art-direction review against the canonical Inez design.

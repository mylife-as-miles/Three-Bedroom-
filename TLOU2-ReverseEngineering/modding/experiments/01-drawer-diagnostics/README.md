# Mod Experiment 01 — Drawer Diagnostics

**Built and statically validated; no game execution or deployment.** Continued from `00868aab7f293d01a52441fd6b415d0c8e5ee3e3` on `ccr-80dff22c-p82ge1`. The existing corpus databases and drawer evidence were reused. This experiment does not batch decompile or regenerate the game corpus.

An independently authored observer is appended to the update block of each of the eleven existing drawer states. Original animation, inventory, event, movement, cancellation and transition instructions remain intact. The generic script gains observer scheduling; an explicit actor-ID guard prevents other drawers from reading diagnostics or polling F2. This is a static preservation result, **not proof of identical runtime behavior**.

The configured single actor is `drawer-wat-kitchen-apartment-1`, SID `BBCBBCE24067406D`. CONFIRMED: this identifier is referenced in the actual `ss-wat-capitol-hill-interacts.bin` corpus file. UNKNOWN: the actor's owner binding to `ss-openable-drawer`, its location/loot configuration in the installed level, and successful loading of this mod. This is a candidate for the Capitol Hill chapter, not a verified test location. If its script owner has a different ID, the observer stays off. Retarget by rebuilding with `--actor` after verifying the owner; never remove the filter or enable every drawer as a workaround.

F2 (`keyboard-button-pressed?(158)`) toggles a new per-instance boolean, initially false. A second new boolean latches the key. Both are appended after all 61 existing declarations. The existing F2 example/keycode in the pinned dconstruct source supports this interface; native key semantics and conflicts with developer-menu bindings still require Windows testing.

## Measurements

| Display | Actual source | Interpretation / limit |
| --- | --- | --- |
| State | SID embedded in its observer track | CONFIRMED owning state; brief intra-frame states may be missed |
| Handle height | `get-float(object-height, self)` | Existing script's cached handle height relative to player position; raw engine value, no new measurement or assumed unit conversion |
| Furniture geometry | `drawer-edge-height`, `drawer-edge-width` | Existing cached selection/alignment values; may be stale outside the interaction |
| Selected animation | `scav-enter-animation`, `scav-pickup-animation`, `scav-exit-animation` | Script's selection symbols, not a claim about a native motion-matching winner |
| Animation phase | `get-animation-phase(player, 2, clip)` | Queried only for an existing player and a non-bindpose clip reported playing by `get-animation-playing?(player, clip, 2)`; `-1` means unavailable |
| Stance | `is-crouch?` and `player-is-crouched?()` | Cached selection stance versus current crouch predicate; `-1` means player unavailable; no prone/tension classification inferred |
| Alignment | Handle animation height, angle adjustment, rotation adjustment, mirror/holster flags | Existing script values; not native root-motion or IK math |
| Move-to | Player/path-goal XZ distance and locator angle on axis 2 | Uses the original move-to call contract only in `scavenge-move-to`, with non-null frames; units and frame validity need runtime verification |
| IK | Main/second/pickup usage flags, solver IDs, proxy IDs, on/off frame thresholds | Existing handles and configuration; no bone transforms, constraint errors or solver internals fabricated |
| Pickup | `pickup-is-full`, `obj-picked-up?` | Script flags only; no direct inventory-storage or persistence inspection |

The display uses `alloc-point`, `dc:format`, `string-debug`, and the original drawer's nine-argument `debug-draw-string-2d` convention. Three multiline strings are emitted while enabled. The placement, multiline support, lifetime/retention, debug-render gating and shipping-build availability are UNKNOWN until tested. Disable it and allow retained debug text to expire before comparing baseline screenshots. It does not consume/override the game's interaction command, set an animation, change a world flag, call `go`, send gameplay events, or apply a pickup.

## Evidence and artifacts

- [Exact static before/after evidence](evidence/static-validation.json): all 151 original lambdas, 1,159 calls, eleven states, six exports and 61 original declarations retained; per-lambda instruction hashes and metadata changes are recorded.
- [Build identity](evidence/build.json), [toolchain provenance](evidence/toolchain.json), [isolated smoke round-trip](evidence/roundtrip.json), [six static/mock checks](evidence/test-results.json).
- [Windows procedure](WINDOWS_TEST_PROCEDURE.md) and [unexecuted scenario matrix](evidence/runtime-matrix.json).
- [Compiler limitations and implementation decisions](IMPLEMENTATION.md).

Private local output: `.private/experiments/drawer-diagnostics/build/mod/bin/dc1/ss-t2/ss-openable-drawer.bin` and `modules.bin`. The latter changes only the existing drawer module's size field. No new module, resource package dependency or game asset is distributed. Proprietary inputs, patched outputs, generated decompilations and full logs remain ignored. Only original tools/DCPL and small derived evidence belong in Git.

Linux build used the real compiler/decompiler core at dconstruct `583b38d8b25b2f0b2cd079db70d8caac0a69f3a7` through a **private compatibility adapter**, not a released Windows executable. A fresh adapter build recipe and a Windows core-only CMake recipe are included. The no-argument authored smoke fixture round-trips byte-for-byte; this does not imply a full proprietary drawer or native-call round-trip is supported.

## Reproduce locally on Debian/GCC

Run from `TLOU2-ReverseEngineering`. Requires GCC 14 with C++23, make, curl, dpkg-deb, Graphviz 2.42 runtime libraries and TBB. Bootstrap downloads two pinned public dependencies when absent; game inputs must already be present. It keeps the upstream checkout clean and writes compatibility copies only privately.

```bash
python3 modding/experiments/01-drawer-diagnostics/bootstrap_linux.py \
  --vendor .private/vendor/dconstruct \
  --output .private/experiments/drawer-diagnostics/toolchain

python3 modding/experiments/01-drawer-diagnostics/roundtrip.py \
  --compiler .private/experiments/drawer-diagnostics/toolchain/compile_core \
  --dconstruct .private/experiments/drawer-diagnostics/toolchain/dconstruct \
  --output .private/experiments/drawer-diagnostics/roundtrip-run

python3 modding/experiments/01-drawer-diagnostics/build.py \
  --original .private/extracted/dc1/ss-t2/ss-openable-drawer.bin \
  --modules .private/extracted/dc1/modules.bin \
  --compiler .private/experiments/drawer-diagnostics/toolchain/compile_core \
  --dconstruct .private/experiments/drawer-diagnostics/toolchain/dconstruct \
  --vendor .private/vendor/dconstruct \
  --output .private/experiments/drawer-diagnostics/build

python3 modding/experiments/01-drawer-diagnostics/validate_experiment.py \
  --original .private/extracted/dc1/ss-t2/ss-openable-drawer.bin \
  --modules .private/extracted/dc1/modules.bin \
  --build .private/experiments/drawer-diagnostics/build \
  --report .private/experiments/drawer-diagnostics/build/static-validation.json

python3 modding/experiments/01-drawer-diagnostics/test_static.py
```

**Runtime blocker:** this Linux workspace has the script archive, not the Windows game executable/installation, animations, level assets, saves, or a verified compatible loader. No TLOU2 process was launched. All normal/crouch/inventory/interruption/exit/save scenarios remain NOT RUN. Debug rendering, loader/package acceptance, native scheduler behavior and actor binding are separate prerequisites. No workaround hook or deployment was attempted.

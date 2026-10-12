# Offline Windows build and runtime test procedure

**Status: Windows build NOT RUN; game tests NOT RUN.** Linux compiler/static results are separate evidence. This procedure performs no automated deployment. The build script never writes to a game installation or launches TLOU2. Activation requires a separately authorized, version-compatible mod-loading method; that integration has not been verified here.

## 1. Prepare a private, offline build workspace

Use a local copy of this repository at the specified base commit plus the reviewable experiment changes. Work from `TLOU2-ReverseEngineering`. Keep the installed game and its original `bin.psarc` separate from this workspace. Never point a compiler or patcher at the installed archive.

Prepare these prerequisites before disconnecting from the network:

- Windows x64, Python 3.12+, Git, CMake 3.24+, and current Visual Studio 2022 C++ tools with working C++23 `<format>`/`<print>`. Use Developer PowerShell. The CMake generator in the script is `Visual Studio 17 2022`; adjust only if your installed MSVC generator differs, and record it.
- A clean dconstruct checkout at `583b38d8b25b2f0b2cd079db70d8caac0a69f3a7`, including its bundled `source/Graphviz-13.1.0-win64/{include,lib,bin}` files. Do not use the old beta executable. Our core-only CMake avoids UI/submodule/test downloads.
- `ctre.hpp` from `hanickadot/compile-time-regular-expressions`, commit `dab09336d6a221299159a5ddc76cdcf6967ba9dd`, `single-header/ctre.hpp`, SHA-256 `f0d9a70c782914f83066554cc0690e6c68c83f5bfbc8fab111d3f6affdcc653a`. Store it privately. It is also downloaded by `bootstrap_linux.py` if doing preparation on Linux.
- Your already extracted 1.6 `dc1/ss-t2/ss-openable-drawer.bin` and `dc1/modules.bin`. Only these two game files are needed; do not repeat corpus analysis. Drawer SHA-256 must be `b69fb082a493a76a97405b052542047e530ae4d6da33ca15787114a487e3a0a5` (125044 bytes). A different hash is a different input and must not be silently accepted.

An example private layout is:

```text
.private/vendor/dconstruct/
.private/dependencies/ctre/ctre.hpp
.private/extracted/dc1/modules.bin
.private/extracted/dc1/ss-t2/ss-openable-drawer.bin
.private/experiments/drawer-diagnostics/  # all generated artifacts
```

Verify the upstream checkout and dependency:

```powershell
$Vendor = (Resolve-Path '.private/vendor/dconstruct').Path
$Ctre = (Resolve-Path '.private/dependencies/ctre').Path
git -C $Vendor rev-parse HEAD
git -C $Vendor status --porcelain
Get-FileHash (Join-Path $Ctre 'ctre.hpp') -Algorithm SHA256
Get-FileHash (Join-Path $Vendor 'test/fixtures/dc/sidbase_new_fixed.bin') -Algorithm SHA256
```

Expected SID seed hash: `c2d983bfb5afbfc51591a2d9c003e2e801abe841042768107dc0bd91ce5ceb94`. `status --porcelain` must be empty. Disconnect networking after dependencies are cached; the remaining build commands are local and do not require network access.

## 2. Compile and statically validate without deploying

From the research root in Developer PowerShell:

```powershell
$Dc1 = (Resolve-Path '.private/extracted/dc1').Path
$Vendor = (Resolve-Path '.private/vendor/dconstruct').Path
$Ctre = (Resolve-Path '.private/dependencies/ctre').Path
& './modding/experiments/01-drawer-diagnostics/build_windows.ps1' `
    -InputDc1 $Dc1 -Vendor $Vendor -CtreHeaderDir $Ctre
```

This copies the two inputs to private scratch; builds the original compiler/decompiler core with our driver; performs the authored smoke compile/decompile/recompile; generates the filtered observer; patches an isolated drawer; adjusts one module-registry size field; runs static validation and six structural/mocked-prefix tests; and rechecks both original input hashes. No `@game` directive or game install path is used.

Expected results:

- Smoke `roundtrip-windows/roundtrip.json`: `byte_identical: true`, `seed_restored: true`.
- `build/static-validation.json`: PASS; 151 preserved original lambdas, 1159 preserved calls, eleven states, six exports, 61 original declarations plus two diagnostic booleans, eleven observers; no observer gameplay write.
- All six `test_static.py` tests pass. These are not game tests.
- Both original input hashes remain unchanged.
- Only private mod outputs are produced:
  `build/mod/bin/dc1/ss-t2/ss-openable-drawer.bin` and `build/mod/bin/dc1/modules.bin`.

Capture tool EXE hashes, MSVC/CMake versions, stdout, stderr, build JSON and validation JSON under private scratch. Windows executable hashes will differ from Linux; do not substitute them into the already recorded Linux evidence as if that build were rerun. If emitted drawer hashes differ, compare the full static report before proceeding. Any changed original lambda, declaration/default, export, transition call or unexpected registry change is a failed build.

## 3. Resolve activation and actor binding before gameplay tests

There is no verified loader/override configuration in this repository. The archive is script data, not a full game installation. `ndarc -c <mod-folder> -o <mod-folder>.psarc` is the packaging command used by the pinned dconstruct driver, but packaging does **not** prove the game loads that archive. Neither package activation nor load order has been tested.

After explicit authorization for a local deployment, use a loader/override path already proven compatible with your **exact PC executable build** and capable of replacing the drawer module **and its matching modules registry**. Record the loader name/version/hash, executable hash, package path and load-order configuration. Do not infer compatibility from the archive label “1.6.” Do not overwrite your installed original `bin.psarc` or install an unverified injector to make the display appear. If no compatible override path is available, stop at the statically validated output and mark activation BLOCKED.

NdGameSdk is a native research lead, not a validated dependency of this experiment. Its debug rendering and version support must be established independently if needed. No SDK installation or injection command is supplied or executed here.

The observer's fixed owner-ID is `BBCBBCE24067406D` (`drawer-wat-kitchen-apartment-1`, a real Capitol Hill script reference). Before the scenario matrix, establish that this object's running `ss-openable-drawer` owner reports this ID through your validated actor/debug inspection tool. Record the owning script, actor ID, chapter/checkpoint, position or unambiguous landmark, pickup type and a screenshot. A reference in a level script alone does not establish runtime binding.

If another verified existing drawer is needed, rebuild **one fixed actor**:

```powershell
& './modding/experiments/01-drawer-diagnostics/build_windows.ps1' `
    -InputDc1 $Dc1 -Vendor $Vendor -CtreHeaderDir $Ctre `
    -Actor 'VERIFIED-EXISTING-DRAWER-OWNER-NAME'
```

Do not deploy this literal placeholder. Record its FNV SID and repeat all static checks. Use this same actor for all comparable tests. It must contain a pickup with an inventory capacity limit for the full-inventory case. If the selected object's item is an uncapped note/artifact, that case is NOT APPLICABLE, not PASS; select a suitable single resource drawer and redo the matrix from baseline.

## 4. Record a controlled baseline

Use your legitimately owned game offline, without an online/competitive session. Copy the save/profile before testing, and record the game executable/version/hash, difficulty, accessibility/control settings, character, checkpoint and inventory. Do not experiment on the only copy of a save. Keep backups and recordings privately; they are not repository assets.

With the mod absent, record each applicable scenario below from an identical checkpoint/save. Capture screen/video with input timing, approach direction/stance, item type and quantity, initial/final inventory, prompt availability, drawer state, interrupted/retry behavior, player control restoration and resulting save/reload state. Never change an original save or item flag with a diagnostic command to fabricate an outcome.

Then enable the separately authorized override, launch from the same baseline, and repeat once with the observer **off**. Original prompts, outcomes, animation timing, audio, movement and control restoration must match the unmodified baseline within a recorded tolerance. The two extra declarations and update blocks can affect native scheduling/save behavior even with drawing off; only game execution can test that.

## 5. Run the scenario matrix with F2 enabled

Press/release F2 once on the verified target; it should enable the display. Press it again to disable. Holding the key must not repeatedly toggle. Observe a second drawer; it must never show this observer display or take over its toggle. If the display is absent, first verify actor ownership and package loading, then supported debug-render configuration. Absence of a display is a blocked diagnostics test, not proof of success. No runtime hook should be added without a separate decision.

| Case | Setup / action | Acceptance and evidence |
| --- | --- | --- |
| Normal opening | Standing, fresh closed drawer, approach and interact normally | Record state progression, raw handle/edge values, selected clips, phases and move-to distance/angle; opening, sound and control restoration match baseline |
| Crouched interaction | Reload same checkpoint; crouch before approach | Record cached selected crouch versus live crouch, selected clips/IK flags; do not presume crouched stance is retained if baseline stands the player up |
| Item pickup / empty inventory | Start with available capacity for that exact item; open and take it | Record selected pickup clip/phase, picked flag, inventory delta, prompt/notification, attachment timing and object disappearance against baseline |
| Full inventory | Reload with the item's capacity full using ordinary gameplay; repeat on same drawer | Record `pickup-is-full`, prompt/abort/outcome, unchanged quantity if expected by baseline; no duplicated item or stuck alignment/IK |
| Empty drawer | Reload appropriate baseline or revisit after legitimate collection | No extra pickup or resource update; record wait-pickup/complete behavior according to baseline |
| Cancel/evade | Cancel/evade during approach, enter and pickup if normal controls permit | Record early-exit/retry/abort states actually reached; inventory and world outcome match baseline; no stuck camera, input, IK, proxies or prop |
| Attacked interruption | Use a reachable legitimate enemy situation without editing drawer behavior | Record hit timing during enter/pickup and baseline abort/collection outcome; if impossible at this actor mark BLOCKED, never claim tested |
| Exit | Complete and interrupt; walk, turn, aim/crouch and interact elsewhere | Control and camera restoration match baseline; UI/IK debug values may be stale but no observer mutation occurs |
| Save/reload/removal | Save copied profile after open/collection; reload, then remove override and reload copy | World/item state and inventory match baseline; no serializer/load failure, reset, duplicate resource or permanent control lock |

Repeat necessary interrupted subcases from a clean checkpoint. One successful opening is not acceptance of the entire matrix. Run with F2 off and with the mod removed when a discrepancy appears to distinguish display cost from structural instrumentation cost.

For each observed frame/sample, record:

```text
case_id,run_type,game_build,mod_sha256,actor_sid,checkpoint,time_or_video_frame,
state,handle_relative_raw,edge_height_raw,edge_width_raw,selected_crouch,live_crouch,
enter_clip,enter_phase,pickup_clip,pickup_phase,exit_clip,exit_phase,
path_distance_raw,facing_delta_axis2_raw,main_ik,second_ik,pickup_ik,
right_solver,left_solver,pickup_solver,main_proxy,second_proxy,
pickup_full,picked,inventory_before,inventory_after,control_restored,
baseline_recording,instrumented_recording,result,notes
```

Use UNKNOWN/unavailable for native internals; `-1` for unavailable observer phase/distance. Do not turn selection variables or solver handles into claims about native IK correctness. Keep recordings under `.private/experiments/drawer-diagnostics/runtime/`. Update a copied runtime matrix with PASS/FAIL/BLOCKED/NOT APPLICABLE only after actual evidence exists; record who ran the game and when.

## 6. Acceptance and rollback

Acceptance requires actual package/actor/render confirmation and every applicable requested gameplay case passing against the baseline, including off-toggle and removal tests. Report any untestable interruption/capacity case explicitly. Remove only the added override using the already verified loader procedure, verify original installation file hashes, and restore the private copied profile if testing changed it. Preserve failed-case recordings and logs.

**Current checkpoint:** compile/static validation completed on Linux. Windows compilation, package activation, actor binding, debug rendering and all game scenarios remain unexecuted. The user subsequently authorized committing and pushing the reviewable experiment. Deployment remains unperformed and requires separate authorization.

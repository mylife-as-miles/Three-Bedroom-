# Implementation and confidence boundaries

## Preservation strategy — CONFIRMED static

`build.py` compiles only our observer template with the pinned dconstruct core. It imports the template data into a private copy of the exact analyzed 1.6 drawer, copies each original block table, and appends one update observer after the existing update tracks. States without an update block gain one after their original blocks. It retains state names, initial state, options, original track order/indexes, original `SsLambda` counters and all original bytecode/symbol values.

New lambda counters occupy 1830–1840, above the original maximum. Two boolean declarations are appended without altering any original default or variable-size offset; the total declaration allocation rises from 648 to 650 bytes. Original string bytes remain intact, with 92 pointer relocations for their new location. A new relocation bitmap covers imported and appended structures. The module registry changes its drawer size slot at `0x347A8` (214952), and nothing else. No registry import/export changes are needed for the appended tracks, which call existing native/global APIs plus the already used DC helper `angle-in-between-locators`.

`validate_experiment.py` checks the entire original data prefix after normalizing only enumerated metadata changes/string relocations. It also compares every original instruction byte, static call argument/context record, declaration, state order, track order, lambda reference and counter. It checks the new native/DC call allowlist and rejects any observer boolean write outside our two variables. Per-lambda instruction SHA-256 values and exact changed structural fields are published as derived metadata. This protects existing gameplay instructions; it cannot prove how the native scheduler treats additional tracks or declarations.

## Pinned compiler limitations — CONFIRMED source/static observations

The pin is [dconstruct 583b38d8](https://github.com/DeepQuantum/dconstruct/tree/583b38d8b25b2f0b2cd079db70d8caac0a69f3a7), version 2.2.0. Its official CMake requires Windows. The older public beta is from before the DCPL compiler and is unsuitable for this experiment.

- The experiment's independently authored `compile_core.cpp` calls `run_compilation` and `ast::program::make_binary`. It performs no automatic `@game` staging or `ndarc` packaging. This avoids the original `dcc` driver’s packaging side effects. It uses the upstream parser/compiler, not a replacement DC compiler.
- The state-declaration parser retains a leading `#` spelling, while emission hashes that full spelling. The weaver explicitly verifies and normalizes **only our two declaration IDs** to the unprefixed FNV hashes used by getters. Their IDs are numeric literals inside the template to avoid the semantic checker treating a declaration name as a boolean value where a symbol is required. Original declarations are not repaired or recompiled.
- The unary-negation checked type is `u64` at this pin. The observer uses `0.0 - 1.0` for its floating sentinel instead of relying on negative-literal typing.
- The CLI decompiler can emit uncompileable `u64?` placeholders for unknown parameters and unprefixed hyphenated names. Its current CLI path does not forward the new mapped function-signature argument to the decompiler constructor. Accordingly, the repeatable round-trip uses a type-unambiguous, zero-argument, independently authored fixture and a temporary sorted SID entry for its underscore name. The original SID seed is restored in `finally`. No heuristic type repair is applied to game code.

The private Linux adapter changes three literal-suffix parameter spellings for LP64, adds explicit standard-library includes and executable-path discovery, and accommodates the installed Graphviz version/macros. It does not change opcodes, semantic checking, lowering, binary emission or gameplay source. Graph rendering is unused. Exact source, dependency and executable hashes are in [toolchain evidence](evidence/toolchain.json). The independently authored Windows CMake file uses the same upstream core directly; it has **not been built or executed on Windows here**.

## Native calls — HIGH CONFIDENCE interface; UNKNOWN execution

The original drawer itself demonstrates float/boolean/symbol getters, phase `(player, 2, clip)`, bound-frame/locator distance/angle queries, point allocation, formatting and debug drawing. `script-user-funcs-impl` contains `get-animation-playing?(entity, animation, 2)` and a zero-argument `player-is-crouched?` call. The pinned gas-mask example uses `keyboard-button-pressed?(FUNCTION_2)`; `keycodes.dcpl` gives FUNCTION_2 = 158.

The calls/argument shapes are supported by actual scripts or a pinned tool example. This is **not** a guarantee of retail availability, identical boxed argument ABI on every platform, null locator safety, valid solver identifiers, debug-render configuration, heap/frame allocation behavior or event timing. These require the runtime tests. IK solver IDs are handles, not joint solutions. Path distance and angle are sampled only in move-to; the observer does not recompute alignment or read an unverified native struct layout.

## Risks requiring runtime resolution — UNKNOWN

- Adding update blocks can affect scheduler liveness, CPU cost or native implicit completion rules. Non-target instances still execute their actor-ID guard.
- Appending declarations changes script instance allocation. Native save/checkpoint serialization and restoration compatibility are not established. Use a copied save/profile; a successful off-toggle does not prove serialization equivalence.
- The hard-coded actor may use another owner ID/controller, or its level may not load this generic module. A blank display is not success.
- F2 may conflict with another debug tool or have unexpected edge/consumption behavior. The prefix test mocks this native query.
- The drawing API may be gated, disabled in the shipping build, retain messages longer than expected, use different coordinate conventions, or lack multiline support.
- Selected variables may be stale before selection/after exit; state and phase availability must be interpreted together. Script update sampling can miss same-frame states.
- Module override/package load order, executable compatibility and debug support are not verified. NdGameSdk was consulted as a runtime research lead only; no SDK was built, installed or injected.

The experiment stays YELLOW: authored data/script instrumentation uses existing engine interfaces. A replacement renderer, input hook, solver probe or loader-specific integration would be a separate native task and needs an explicit scope/deployment decision.

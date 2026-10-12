# Research checkpoint — 2026-10-12

Primary target acquired and locally verified. Repository: Three-Bedroom-, research folder TLOU2-ReverseEngineering. Existing handoff artifacts preserved. This checkpoint records a complete static corpus survey and bounded architecture reconstruction; native/runtime gaps remain explicit.

| Requested step | Result |
| --- | --- |
| 1–4 Acquisition/extract/dc1/count | Complete: actual 1.6 RAR, DSAR/PSAR unpacking, exactly 8,004 dc1 files |
| 5 Manifest | Complete: path/size/entry/SHA-256; nested startup archive audited and deduplicated |
| 6 SID dictionary | Complete: all readable DC strings hashed; seed + token candidates; provenance and FNV verification |
| 7 State scripts | Complete structural pass: 5,431 scripts, 29,251 states; zero reported parse errors |
| 8 Function/event/call database | Complete static pass: 178,581 lambdas, 644,423 call sites, event listeners/producers, module imports/exports |
| 9a–n Interaction traces | All requested scopes have interpreted notes, per-state evidence, JSON and explicit-go graphs; native behavior remains bounded |
| 10 UI interaction definitions | Complete inventory: 273 gameplay records and 111 HUD names; undocumented numeric fields explicitly unknown |
| 11–13 Animation/audio/inventory/persistence | Dependencies and ownership interfaces mapped; unknown native links documented |
| 14 Level composition | Patrol globe/heater/joke-book examples; caption-only book evidence treated cautiously |
| 15 Native AI/resource boundaries | Data/controller/event interfaces and module dependencies mapped; streaming separated from saved state |
| 16 Architecture documentation | Written with source offsets and confidence labels |
| 17 Modding surface | GREEN/YELLOW/ORANGE/RED matrix for all requested systems |
| 18 First custom mod | Five increasing recommendations; best first is a drawer diagnostics overlay; no mod implementation started |

Independent validation: all 4,095 comparable call labels match t2r-dc-disasm; all 621 prior exported StateScript counts/known sequences match. Seven property tests and corpus integrity/reference checks passed. All 562,611 published SID hashes and 52,545 resource reference edges were validated. Generated JSON compressed/redacted for review; original assets/listings stay .private/.

## Open research questions

1. Native interaction scoring/eligibility/reservation and directional door definition selector.
2. Exact drawer geometry thresholds and native AP/root-motion/IK execution.
3. First native inventory write and notification/despawn/save order behind player-apply-pickup.
4. Held-object rotate/tilt/zoom and front/back input contract; no universal ss-examine handoff proven.
5. Drawer flag writers and save serialization, native collectible/journal storage.
6. Actor-resolved power/door/light event delivery and production activation of prototype scripts.
7. Exact animation-event material-audio/bank linkage.
8. Native rope/push/traversal/AI/streaming solver internals.
9. Full Windows dconstruct decompilation and compiler round trip, followed by user-run offline behavior tests.

## Resume

Read README and ENGINE_BOUNDARIES first. Reuse source hashes and existing databases. Query with tools/analysis/query.py. Private raw strings, bytecode, full merged SID dictionary, tool clones and checkpoints are retained locally. Avoid restarting acquisition or scanning already verified files unless the corpus/build changes. Repackaging is safe and deterministic. Version control contains only the reviewable research outputs.

Final integration: 177 reviewable files in the local Three-Bedroom checkout; original tracked handoff artifacts unchanged, private/binary leakage check passed, no file over 100 MiB. Global derived metadata is approximately 100 MiB compressed. The user subsequently authorized committing and pushing the reviewable research outputs.

## Mod Experiment 01 checkpoint — 2026-10-12

Continued from `00868aab7f293d01a52441fd6b415d0c8e5ee3e3` on `ccr-80dff22c-p82ge1`. Reused the completed corpus architecture and drawer evidence. Implemented [Drawer Diagnostics](modding/experiments/01-drawer-diagnostics/README.md) as independently authored, actor-filtered observer tracks in an isolated private drawer copy.

Pinned dconstruct core `583b38d8b25b2f0b2cd079db70d8caac0a69f3a7` builds through a private Linux adapter. Authored smoke compile/decompile/recompile is byte-identical. Drawer and registry output are deterministic across two isolated builds. Static preservation confirms 151 original lambdas/1159 calls, eleven states, six exports and 61 declarations. Six structural/mocked-prefix tests pass. Added eleven update observers and two debug-only booleans; native scheduling/save behavior remains unknown.

Exact hashes, per-lambda preservation evidence, toolchain provenance and NOT RUN runtime matrix live in the experiment's evidence directory. Private patched assets and generated listings remain ignored. The Windows build/runtime procedure is prepared but has not run; no game executable/install or verified loader exists in this Linux workspace. Candidate actor binding and debug rendering must be established in game. No mod deployed. The user subsequently authorized committing and pushing the reviewable experiment; private game assets and generated mod binaries remain excluded. Resume with the experiment README and WINDOWS_TEST_PROCEDURE; do not restart the corpus analysis.

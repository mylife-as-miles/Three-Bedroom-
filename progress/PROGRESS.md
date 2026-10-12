# Progress log / checkpoints

## Execution order status (from the project brief)

| # | step | status | notes |
|---|---|---|---|
| 1 | Acquire 1.6 archive from Drive | ✅ | direct HTTPS download of `bin_1.6-378-1-6-1759117728.rar`, 44,817,442 B, RAR CRC OK |
| 2 | Extract bin.psarc | ✅ | needed `unrar` (RAR4); the psarc is wrapped in **DSAR** (LZ4 blocks), unwrapped to a 344,159,974 B PSARC |
| 3 | Extract/locate dc1 | ✅ | PSARC v1.4, entries keyed by MD5(path) |
| 4 | Verify ~8,004 files | ✅ | exactly **8,004** files in the main PSARC (7,958 `.bin`, 44 `.json`, 1 `.txt`, 1 nested `.psarc`). The nested `startup-dc-files.psarc` holds 1,714 files: 1,651 byte-identical duplicates + **63 unique**, merged → **8,021 `.bin`** analysed |
| 5 | File manifest | ✅ | `databases/file_manifest.json` |
| 6 | Global SID dictionary | ✅ | 1,531,747 SIDs (sidbase 1.41 M + 121 k from corpus strings). 275,223 SIDs referenced by scripts, 99.86 % resolved; the remaining 383 are bitmask constants |
| 7 | Parse every state script | ✅ | **5,434** state scripts, all files parsed with 0 errors |
| 8 | Function/event/call database | ✅ | 9,652 functions · 6,469 events · call graphs for 1,465 interaction scripts (all 5,434 in `call_graph_full.jsonl.gz`) |
| 9a | drawer | ✅ | `interactions/drawers/README.md` |
| 9b–n | other systems | ⏳ | parallel deep-trace agents (see below) |
| 10–15 | cross-cutting maps | ⏳ | agents |
| 16–18 | synthesis, modding surface, mod recommendations | ⏳ | |

## Decompiler

dconstruct built for Linux (g++-14; 4 small portability patches kept locally). All 8,021 files disassembled and
5,741 files with code decompiled (211,045 functions, 147 flagged inaccurate by dconstruct itself) in about 25 s.

## Agent assignments (deep traces)

| agent | outputs |
|---|---|
| cabinets + pickups | interactions/cabinets, interactions/pickups, systems/inventory |
| investigate + examine + notes | interactions/investigate, interactions/examine, interactions/notes |
| safes + lock HUD + keypads | interactions/safes, interactions/keypads |
| power + doors | interactions/generators, interactions/doors |
| ladders + ropes + pushables | interactions/ladders, interactions/ropes, interactions/pushables |
| workbench | interactions/workbench |
| interactable system + UI defs | systems/interactable, systems/ui, databases/interaction_definitions.json |
| animation + audio + camera | systems/animation, systems/audio, systems/camera |
| persistence + level design + AI + resources | systems/persistence, systems/ai, systems/resources, level_design/ |

## Notable findings so far

* Inventory ownership begins at native `player-apply-pickup(item)` / `player-pickup(item,…)`.
* The drawer's reach is fitted to the furniture through: a handle-height band table (10 animation sets) +
  `player-ik-root-adjust` hip offset + script-driven hand IK on spawned invisible proxy cubes + stand pose derived
  from the animation's own apReference (`get-align-from-ap-ref`).
* `(tension-mode combat)` = 3 (CONFIRMED via embedded debug assertion strings).
* The binaries keep many original Racket condition strings, e.g. `"(if combat? (tension-mode-is? (tension-mode combat)) #t)"`.
  These are a great Rosetta stone for enum and keyword values.
* Native event vocabulary: 2,850 events are handled in script but never sent by script (engine → script candidates), and
  558 are sent by script but never handled in script (script → native-object commands). See `databases/native_event_vocabulary.json`.

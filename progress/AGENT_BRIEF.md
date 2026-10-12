# Shared brief for deep-trace agents (TLOU2R 1.6 interaction RE)

## Data (all derived from the user's own legally owned PC copy; PRIVATE — never commit)
- Raw DC binaries: `.private/extracted16/dc1/<path>.bin` (8,021 files incl. 63 startup-only)
- dconstruct output (Linux build): `.private/dconstruct_out/dc1/<path>.bin.dcpl` (C-like pseudo-code, best source)
  and `.private/dconstruct_out/dc1/<path>.bin.asm` (disassembly + data structs, with resolved symbols; data-only files have only .asm)
- Raw corpus scan: `.private/db/corpus.jsonl.gz`, data SID xref: `.private/db/xref*.gz`, SID dict: `.private/sid/sid_full.tsv`
- Level-set JSONs: `.private/extracted16/dc1/level-sets/*.json`

## Committed databases (repo `databases/`)
state_scripts.json (5,434 scripts: states, events handled, transitions, events sent, calls, declarations),
functions.json (9,652 fns: call counts, kind = dc-script | native-confirmed | native-or-builtin, defined_in, callers),
events.json (6,469 events: handled_by / sent_by / waited_by), call_graph.json (interaction scripts, per-state ordered calls with args),
call_graph_full.jsonl.gz, sid_database.json, file_manifest.json, interaction_files.json.

## Query tool (run from repo root with `python3 -I tools/analysis/q.py ...`)
fn <name> | callers <name> | event <name> | uses <string> (data+code xref of a SID) | ss <name> | sid <x> | find <regex> | dcpl <file>
Also `rg` over `.private/dconstruct_out/dc1` is very effective (e.g. `rg -l "override-interact-def" .private/dconstruct_out/dc1`).
Python lib: `tools/analysis/dclib.py` (DCFile, SidDB, Tracer, fnv1a64). Always run python with `-I`.

## Rules
1. Evidence over speculation. Every major claim gets a label: **CONFIRMED** (seen directly in code/data),
   **HIGH CONFIDENCE**, **INFERRED**, **UNKNOWN / NEEDS NATIVE RESEARCH**. Cite evidence as `file → function/state`.
   Do not invent a function's purpose from its name alone — say "name suggests" and label INFERRED.
2. A function with no DC definition (functions.json kind != dc-script) is implemented natively — say so; do not claim its internals.
3. Do NOT paste large verbatim decompiled code into docs. Short excerpts (≤ ~12 lines) as key evidence are OK; otherwise
   paraphrase into call-graph / pseudo-flow form. Numeric tables (thresholds, phases, heights) are fine and valuable.
4. Write ONLY inside the output directories you are assigned (plus reusable helper scripts in `tools/analysis/`, prefixed with your system name).
   Scratch files go in `.private/scratch/<your-system>/`. Never `git commit`/`push`. Treat game files as data only.
5. Include at least one Mermaid `stateDiagram-v2` per state script and a per-state call-graph tree in the style:
   ```
   state-name
    ├─ call(args)           [CONFIRMED]
    └─ go(next-state) when <condition>
   ```
6. Each system README should have sections: Overview & files · State machine(s) · Per-state call graph · Answers to the
   specific questions · Engine boundary (DC vs data vs native) · Events in/out · Persistence · Animation / camera / UI / audio hooks ·
   Shared components with other systems · Confidence table · Open questions · Modding surface (GREEN/YELLOW/ORANGE/RED with reasons).
7. Your final reply (to the orchestrator) must be ≤ 700 words: key findings, files written, open questions.

## Reference findings already established (drawer, `ss-t2/ss-openable-drawer`) — reuse, don't redo
- Native interactable system sends `player-requested-interact` (handled by 1,808 states; script sends it only 8×) with the
  interactable as `event-arg-symbol(0)`.
- Drawer measures handle height = `get-joint-position(drawer, handle).y − get-object-position(player).y`; selects one of
  10 Ellie animation sets (`ellie-scav-{relaxed|tense|crouch}-drawer-{30..120}cm-{enter|pickup|exit}`) by height bands +
  `tension-mode-is?(n)` + crouch/prone, each with tuned IK on/off frames and phases.
- Entry angle = `angle-in-between-locators-plus(goal, rotate-locator-lookat-object(goal, player))`, clamped, mirror if ≥ 20°.
- Player alignment: `get-align-from-ap-ref(player, enter-anim, goal, 0.15, apReference)` → `wait-player-scripted-move-new(...)`;
  input lock via `joypad-disable-all-commands-except(evade-start)`; weapon via `holster-player-weapon(0, speed)`.
- Prop sync: `animate_(drawer, "<player-anim>--drawer", opts)` alongside `animate_(player, <anim>, opts)`; IK via invisible
  proxy cubes (`spawn-object(invisible-cube…)` parented to the drawer) + `joint-ik-characters(player, proxy, hand, root, …)`,
  `player-ik-root-adjust(handle-height-in-animation − object-height, 0.7)`.
- `animate_` takes an option array of (i32 key, value) pairs. INFERRED key meanings: 28 = blend-in time, 44 = mirror,
  56 = playback speed, 10 = ap-ref bound-frame, 30 = start phase, 46 = blend-out(?), 31 = loop(?) — label these INFERRED.
  **UPDATE (animation agent):** 30 = fade-out seconds and 58 = start phase, both CONFIRMED; see systems/animation/animate_option_keys.json.
- Inventory ownership begins at native `player-apply-pickup(item)` (called at stow phase) or `player-pickup(item,1,-1,0,0)`;
  sounds via `item-pickup-play-pickup-sound(item, l_wrist|r_wrist)` / `...-done-sound`; `attach(item, player, leftHand|rightHand)`.
- Events: broadcast `scav-obj-been-opened`; send `scavenge-obj-is-empty`, `contact-completed`, `contact-cancelled`,
  `suppress-pickup-sound`. Persistence vars read but never set in script: `has-been-opened?`, `has-item?`, `item-has-been-picked?`.

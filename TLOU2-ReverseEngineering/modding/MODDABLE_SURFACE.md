# Moddable surface

Colors describe the most useful exposed surface, not proof that a mod has been compiled or tested. Confidence is HIGH CONFIDENCE for reuse of observed interfaces; native extensions remain UNKNOWN until researched.

GREEN = direct script/data changes using current formats. YELLOW = script/data composition dependent on existing native functions/assets. ORANGE = new primitives require native research/runtime hooks. RED = current public tooling/corpus does not establish a realistic reconstruction route.

| System | Existing surface | New-mechanic boundary |
| --- | --- | --- |
| Drawers | YELLOW: state/timing/animation selection, prompts, existing IK/pickup | ORANGE for new pose solver or inventory internals |
| Doors | YELLOW: defs, actor states, level events | ORANGE for systemic directional selector/controller |
| Pickups | YELLOW: defs, scheduling, item APIs/tutorials | ORANGE for scan/application/storage internals |
| Inspectables | YELLOW: native investigation requests, camera/read/collection orchestration | ORANGE for new manipulation/input primitive |
| Books/notes | YELLOW: existing readable/treasure/menu contracts | ORANGE for new collectible/journal serialization |
| Safes | YELLOW: world state and HUD composition, known flags | ORANGE for native validation/input extensions |
| Keypads | YELLOW: world button/state logic and shared lock UI | ORANGE for new device/controller primitive |
| Workbenches | YELLOW: menus, choreography, helpers and existing bundles | ORANGE for new upgrade storage/model/animation contracts |
| Ladders/climbing | YELLOW: object placement and existing traversal data | ORANGE for arbitrary new traversal solver |
| Ropes | YELLOW: endpoint/puzzle/state composition with existing rope | ORANGE for physics/constraint primitives |
| Pushables | YELLOW: definitions/animation/camera/event composition | ORANGE for contact/turn/nav simulation changes |
| UI | GREEN: supported script state/widget paths/layout requests | YELLOW for existing widgets; ORANGE for native widgets |
| Camera | YELLOW: existing cut/blend/stick/pan APIs/settings | ORANGE for new solver behavior |
| Animation | GREEN: selection/timing and definition changes | YELLOW for existing clips/IK; ORANGE for engine changes |
| Audio | GREEN: existing sound references and calls | YELLOW for banks/assets; ORANGE for new bank/dispatcher features |
| AI | GREEN: exposed parameter/archetype/action-pack data | YELLOW for native event requests; ORANGE for new decisions/perception |
| Levels | YELLOW: existing level-set/task/actor composition | ORANGE for new geometry/nav/resource pipelines |
| Resource streaming | YELLOW: exposed load/prioritization requests | ORANGE for cache/eviction/memory implementation |
| Save/persistence | YELLOW: existing svar/fact/checkpoint/collectible APIs | ORANGE for serialization/migration/new schema |
| Complete native engine/source reconstruction | RED | Not an output of this corpus or these tools |

The blanket classification “all scripts GREEN” would hide dependence on assets, native registration and runtime lifecycle. Reuse is substantially more accessible than inventing a native subsystem.

# Engine boundaries and ownership

This map distinguishes observed DC interfaces from their implementations. Original executable code and native runtime traces were not supplied. **CONFIRMED** refers to exported records or calls; **HIGH CONFIDENCE** native ownership is supported by `CallFf` and no recovered DC implementation. `databases/engine_api.json` lists definitions, call modes and sources; `databases/modules.json` lists declared imports/exports.

| Responsibility | What DC exposes | What remains unknown | Classification |
| --- | --- | --- | --- |
| Interaction selection | Gameplay defs, enable/disable, override, scan exclusion, nearby selection APIs | Spatial scan, distance/angle weighting, reservations, controller arbitration | CONFIRMED interface; HIGH CONFIDENCE native evaluator |
| Player approach | Bound frames, AP refs, goal locators, scripted move calls | Path execution, root motion/controller reconciliation | CONFIRMED requests; native solver UNKNOWN |
| Animation | Named clips/states, phase/frame/duration APIs, per-interaction timing | Blend-tree execution, motion matching, playback implementation | CONFIRMED script/data surface; native execution UNKNOWN |
| IK | `joint-ik-characters`, root adjustments, proxy locators, blend durations | Solver equations, constraints, full skeletal rig | CONFIRMED exposed calls; native implementation UNKNOWN |
| Object attachment | Hand joint/attach-point SIDs, grip/scale, attach/detach calls | Attachment matrix implementation and physics handoff | CONFIRMED requests; native behavior UNKNOWN |
| HUD | Widget paths, page/state/layout APIs, prompt/read/lock systems | Native widget layout/input internals and current physical bindings | CONFIRMED script/data; native internals UNKNOWN |
| Camera | Cut/blend/stick/pan APIs, animation channels, render overrides | Collision, camera solver/input curves, exact zoom/tilt implementation | CONFIRMED interfaces; native execution UNKNOWN |
| Inventory | Pickup application, item quantity APIs, item-full checks | Amount semantics, ammo conversion, destruction order, notification/save internals | HIGH CONFIDENCE native ownership boundary |
| Collectibles | Treasure lookup/collection/examined state and menu APIs | Collection storage, journal serialization, native lookup internals | CONFIRMED APIs; backing store UNKNOWN |
| Audio | Direct sound/audio calls, audio records, material package references | Exact animation-event dispatch and bank decoding | CONFIRMED interfaces; several event links UNKNOWN |
| Rope/push/ladder | Object settings, player actor-state lists, raycasts, motion/controller APIs | Physics integration, collision, nav changes, full traversal solving | CONFIRMED interfaces; native mechanics UNKNOWN |
| AI | Search/cover/combat/infected settings, archetypes/action packs, knowledge/perception interfaces | Decision update, hearing/vision evaluation, navigation solver | CONFIRMED tuning surface; native logic UNKNOWN |
| Resources | Module registry, level sets, actor/animation/sound references, streaming requests | Cache ownership, budgets, eviction order, memory allocator | CONFIRMED declarations; native residency UNKNOWN |
| Save/world state | Svars, facts, object flags, checkpoint APIs, collection APIs | Serializer schema, version migration, complete restore semantics | CONFIRMED interfaces; serialization UNKNOWN |

## Runtime streaming is not persistence

**CONFIRMED:** level-set/resource references and imports describe dependencies. Loading, texture prioritization and streaming requests change runtime resource availability. Workbench calls `prioritize-texture-streaming-for`; its UI/model preparation is a residency concern.

**CONFIRMED:** object-scoped `ss-svar`, global svars, safe-found bitfields and checkpoint APIs are gameplay-state concerns. Workbench requests `remember-dynamic-checkpoint`; safe writes `opened`; investigation/examination write `used`. A module being loaded does not mean an interaction is complete. A boolean in a StateScript declaration does not prove it is serialized.

## Native AI research map

**CONFIRMED:** actual corpus includes `ai/search-params`, `ai/cover-params`, `ai/infected-params`, `ai/combat-params`, top-level `ai-archetypes` and `ai-action-packs`, rogue `encounter-perception-settings` and `ss-encounter-perception-controller`, infected perception stats, clicker-hearing level scripts, directed-hearing and knowledge-spread prototypes. Prototype presence does not establish use in production.

**HIGH CONFIDENCE:** modders can tune data and script-triggered AI state/event requests within the exposed interface. **UNKNOWN:** complete perception accumulation, group knowledge propagation, cover scoring and pathfinding mechanics. Introducing a new sensory modality or decision primitive would require native research rather than merely renaming a DC symbol.

## Evidence still needed

Use native research or user-run offline traces to inspect interaction evaluator callers, `player-apply-pickup`, save writers for drawer flags, directional door selection, player investigation input/control logic, attachment transform construction, IK execution, animation event audio dispatch, rope/push physics, native AI updates and resource eviction. Each requires observing its actual arguments/effects; SID names alone are insufficient.

`NdGameSdk` / runtime hooks are possible research directions, not tools validated against this particular executable/build in this session. No hook offsets or compatibility guarantees are asserted.

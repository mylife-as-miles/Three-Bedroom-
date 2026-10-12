# Ai

CONFIRMED: corpus data includes search/cover/combat/infected parameters, archetypes, action packs, perception settings/controllers, hearing and knowledge interfaces, clicker-hearing level scripts and several prototypes. These are actual source files/records, not inferred solely from public examples.

The rogue encounter-perception controller uses run/encounter structure and seed helpers to prepare data; it does not contain the full native hearing/vision loop. Prototype scripts are leads, not production guarantees. HIGH CONFIDENCE: tuning values and script-visible perception/awareness requests are moddable with existing native systems. UNKNOWN: exact sensory evaluation, cover scoring, decision updates, group knowledge propagation and pathfinding.

Boundary: DC data/scripts -> exported parameters/events/native APIs -> native decision/perception/navigation -> returned awareness/state interfaces. See ../../ENGINE_BOUNDARIES.md and engine_api/modules/system indexes. No new AI primitive or live AI trace was implemented.

[Generated corpus evidence](evidence.md).

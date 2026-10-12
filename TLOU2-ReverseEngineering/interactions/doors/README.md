# Doors

CONFIRMED: all four directional interaction definitions exist in interactable.bin; player-door exports an actor-state list. `ss-openable-door` itself contains only wait-interact/complete and eight call sites. It cannot support a complete DC reconstruction of systemic door approach/hinge/side selection.

Level scripts expose door-enable-systemic, interaction enable/disable and task-driven door conditions. The watchtower rope-puzzle door waits for open, then stays open and uses task range conditions. These are concrete authored gates around a native/systemic controller.

UNKNOWN / NEEDS NATIVE RESEARCH: the function that selects open-in-left/open-in-right/open-out-left/open-out-right, exact push/pull transforms, player/prop root-motion reconciliation, locked/powered-door evaluation, AI navigation changes and door save serialization. Do not mistake a native/data actor state for a large missing StateScript. [Evidence](evidence.md).

# Ropes

CONFIRMED: rope/phys-ropes data, character/player rope animation families and level-specific attachment puzzles occupy different modules. Player variants include free, wall, from-wall and drag rope; their state-data and embedded-call references are preserved in the global database. Rope coil carry/fixed/attach/buddy-catch scripts and level puzzle gates are separate orchestration.

The selected watchtower door script waits for open and toggles systemic door behavior; it is not the physics rope solver. Seattle rope deflector and accessibility/tutorial controllers illustrate additional authored constraints. The physics package, interaction definitions and player-state data must all be considered when reusing a rope puzzle.

HIGH CONFIDENCE: script can coordinate existing rope assets, endpoints, gates and prompts. UNKNOWN / NEEDS NATIVE RESEARCH: constraint integration, segment collision, tension/swing solver, native animation/rope coupling and new rope simulation primitives. [Evidence](evidence.md) and `systems/animation`/`systems/resources` indexes.

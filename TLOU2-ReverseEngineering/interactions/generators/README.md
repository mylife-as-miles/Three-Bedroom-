# Generators

CONFIRMED: generator minigame separates task-check/wait/active/already-complete/complete. It receives activate and emits generator-press, generator-fail and generator-complete; completion at 0x3A10 is followed by go complete at 0x3A40.

The world generator/door script independently gates on task state, aligns the player, animates, controls camera, can start-with-rope, changes light intensity and signals its own choreography milestones. Therefore a minigame event is not itself a proven global power-network simulation. Patrol generator scripts and audio loops provide other level-specific variants.

CONFIRMED event graph records producer offsets, symbolic receiver arguments and listener state locations. Matching event names are candidate edges. HIGH CONFIDENCE level composition: puzzle completion can cause specific authored door/light/audio/task effects through those listeners. UNKNOWN: receiver resolution for every target, native circuit semantics and universal AI consequences. [Evidence](evidence.md).

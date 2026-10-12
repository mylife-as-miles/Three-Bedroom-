# Reusable level composition patterns

CONFIRMED: generic technology is frequently composed through task gates, actor/tag references, player-requested-interact events, state transitions, locator/animation/camera requests, event or signal milestones and completion cleanup. A level controller can enable a generic object while another controller owns its pickup, VO or puzzle effect.

The Patrol globe example requests player/prop animation and camera, interleaves caption calls and task checks, then completes. Heater requests player move-to-entry, animation/camera and caption calls. Their per-call offsets and symbol arguments are in examples/.

The Patrol joke-book file is weaker evidence than its name suggests: its animate state only calls wait-script-caption. No direct investigate, book attachment, player animation or camera call was recovered there. CONFIRMED: the caption describes a book moment. UNKNOWN: whether a separate script/actor owns the full final performance or whether this is inactive scaffolding.

Generic systems reused and calls are confirmed in the JSON examples. Complete VO banks, native actor instantiation, active level/task binding and save restore were not supplied. Task completion queries are not themselves completion writes. Do not invent story flags or infer production execution from development/test filenames.

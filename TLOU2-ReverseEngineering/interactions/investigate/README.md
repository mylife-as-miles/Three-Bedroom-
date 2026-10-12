# Investigate

CONFIRMED states: setup, wait-interact, quick-grab, enter-and-investigate, attacked-out, early-cancel, investigate-exit, complete. The initial field is setup.

Setup reads object-scoped `used` and checks collectible status; it can substitute a collected interaction definition. Waiting reacts to player-requested-interact and can query should-fast-pickup? through a result-box event. The native player investigation request, alignment, attachment, camera/overlay and readability helpers are separate calls. Native actor-state execution supplies held inspection behavior.

CONFIRMED flip/exit contract: enter-and-investigate listens for investigate-begin-flip, investigate-begin-exit, player-attacked and hard-end-early. Readable HUD setup is refreshed on flip. Broadcast milestones include moving-to-enter-investigate, entering-investigate, entered-into-investigate, entering/exiting cut variants and done-with-investigate. Object attachment is at 0xCC40. Normal exit collects/marks treasures as configured, can add inventory quantity, requests HUD notifications, writes used, sends detach events and restores camera/flashlight-related state. Quick-grab and attack paths have separate collection/cancellation decisions.

CONFIRMED animation-data references include front/back idle, front-to-back/back-to-front and swap states. UNKNOWN: arbitrary rotation/tilt/zoom mapping and the native player input state machine. No direct universal call into ss-examine was recovered. [Evidence](evidence.md) preserves per-state call contexts, including alternate exits, instead of assuming that all collection waits until normal exit.

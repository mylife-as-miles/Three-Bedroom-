# Keypads

CONFIRMED: arrival keypad contains initial, wait-interact, wait-flip, no-code, note-tutorial, start-keypad, check-inventory, move-around, press-button, fail, success, exit-keypad, complete and --all--. Horse keypad is independently indexed; do not assume both are identical.

Shared lock UI is explicit: start-keypad calls hud2-set-lock-minigame-data at 0x7EF0 and hud2-show-lock-minigame at 0x14D28. Data references collect-sea-hub-generator-note-1; knowledge checks use collectible-sea-qz-generator-note. Button/selection and combination decisions live in the world script as well as shared HUD APIs. Keypad input includes numeric key-range calls (48–57 and 128–137); physical key-code interpretation beyond these values is UNKNOWN.

CONFIRMED: success broadcasts keypad-success at 0x169E0; exit broadcasts keypad-exited at 0x145F8 and hides the HUD. Hint objects are explicit event targets. Wait-flip/note checks connect inspection knowledge to the puzzle. UNKNOWN: general inventory “code knowledge” schema, all downstream gate listeners and native lock validation internals. [Evidence](evidence.md), plus `databases/event_graph.json` for candidate matching listeners.

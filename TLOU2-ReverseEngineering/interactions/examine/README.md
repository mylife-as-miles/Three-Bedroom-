# Examine

CONFIRMED: this is an independent world examination flow with wait-interact, cut/blend entry, intermediate enter, idle, fridge, read, cut/blend exit, done and complete. It starts from its own interaction event rather than a proven universal investigate handoff.

Cut/blend paths use animation camera channels, stick-camera APIs, bound frames and optional auto-generated exit cameras. The idle update checks input and can branch read or exit. Read shows a HUD page at 0x66E0; return hides it at 0x7920 then goes idle. The fridge branch consumes interact-request-in-examine/interact-request-complete. Object movement/alignment and flashlight targeting are script-visible.

CONFIRMED: exit can write object-scoped used, return to wait-interact or go done; it broadcasts exiting-examine and examine-done. Configuration tags include camera-cut-on-enter-and-exit?, blend-use-enter-2?, camera-fade-out-early?, use-auto-gen-exit-camera? and flashlight/collision options. The tags are symbols, not a fully reconstructed native schema.

UNKNOWN: exact camera-stick tilt/zoom curves and arbitrary held-object front/back rotation. Front/back and swap symbols are in player investigation data, so avoid assigning them to this script without a caller trace. [Evidence](evidence.md).

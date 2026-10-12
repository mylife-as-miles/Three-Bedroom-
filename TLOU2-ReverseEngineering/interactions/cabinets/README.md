# Cabinets

CONFIRMED: nine states cover wait, init, move, enter, pickup, exit, early exit, melee abort and complete. Drawer `interact` becomes `scavenge-init`; drawer-specific spawned-open/wait-pickup states are absent.

CONFIRMED: both use AP-reference alignment, player/prop animation phase, joint IK, grip/scale helpers, item-full checks, hand attachment and native `player-apply-pickup`. Cabinet application sites include 0x1318 and 0xC090. Cabinet helper `let-cabinet-door-go-wide-open` is separate from drawer closing. Per-cabinet height/door movement timing should not be copied from drawers without checking its own symbols and constants.

HIGH CONFIDENCE: this is shared technology implemented through parallel state scripts and native helpers, not evidence of one inherited shared source function owning the whole interaction. UNKNOWN: exact native synchronization and save restoration. [Full evidence](evidence.md).

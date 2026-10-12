# ss-pat-library-heater-interaction

CONFIRMED from `dc1/ss-patrol/ss-pat-library-heater-interaction.bin`. This is level-specific orchestration; animation/dialogue assets are not included.

| Context | Target | Offset | Argument evidence |
| --- | --- | --- | --- |
| animate | `camera-enable-animated` | `0xbf0` | 2.0, -1.0, 1, 1000, 0, 0, 0 |
| wait-interact | `go` | `0xc40` | animate, 1 |
| wait-interact | `interactable-enable` | `0xc78` | int-pat-library-heater-1 |
| task-check | `task-complete?` | `0xcc0` | patrol, pat-library-horses-inside |
| task-check | `go` | `0xcf8` | complete, 1 |
| animate | `wait-script-caption` | `0xd98` | player, literal-sha256:d426af343945c074, -1.0, 0, 0 |
| task-check,task-check | `task-active?` | `0xdf0` | patrol, pat-library-horses-inside |
| task-check,task-check | `go` | `0xe28` | wait-interact, 1 |
| wait-interact | `interactable-disable` | `0xe88` | int-pat-library-heater-1 |
| animate | `#%alloc-array` | `0xf08` | single-frame, 16, 3, 1 |
| animate | `get-spawner-locator` | `0xff8` | ap-pat-library-heater-1, 1 |
| animate | `wait-animate_` | `0x11d0` | player, pat-library-lamp--ellie, result(868:12) |
| animate | `camera-fade-out-animated` | `0x1248` | 1.0, 0 |
| animate | `wait-script-caption` | `0x12c0` | player, literal-sha256:533c1d3bf64b2d8c, -1.0, 0, 0 |
| animate | `signal` | `0x1318` | player-in-place, 0 |
| animate | `wait-for` | `0x1350` | player-in-place |
| animate | `wait-script-caption` | `0x13c8` | dina, literal-sha256:96849276a8d673a2, -1.0, 0, 0 |
| animate | `get-spawner-locator` | `0x1430` | ap-pat-library-heater-1, 1 |
| animate | `wait-player-move-to-entry` | `0x1518` | pat-library-lamp--ellie, result(A78:7), 1, 0, 0.4, apReference-camera1, apReference, 0.0, 0, 1, 0, 1, 0.0, 0, 1 |
| animate | `wait-script-caption` | `0x15c0` | player, literal-sha256:cd1dc8521c4521ce, -1.0, 0, 0 |
| animate | `go` | `0x1618` | complete, 1 |

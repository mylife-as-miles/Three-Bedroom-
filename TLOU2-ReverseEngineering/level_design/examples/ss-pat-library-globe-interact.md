# ss-pat-library-globe-interact

CONFIRMED from `dc1/ss-patrol/ss-pat-library-globe-interact.bin`. This is level-specific orchestration; animation/dialogue assets are not included.

| Context | Target | Offset | Argument evidence |
| --- | --- | --- | --- |
| animate | `wait-script-caption` | `0xca0` | dina, literal-sha256:d87a8ebbb8da0911, -1.0, 0, 0 |
| animate | `camera-enable-animated` | `0xd48` | 2.0, -1.0, 1, 1000, 0, 0, 0 |
| wait-interact | `go` | `0xd98` | animate, 1 |
| animate | `#%alloc-array` | `0xe18` | single-frame, 16, 3, 1 |
| animate | `get-spawner-locator` | `0xf08` | ap-pat-library-globe-1, 1 |
| animate | `animate_` | `0x10e0` | obj-pat-library-globe-1, pat-library-ellie-spins-globe--globe, result(728:12) |
| task-check | `task-complete?` | `0x1158` | patrol, pat-library-horses-inside |
| task-check | `go` | `0x1190` | complete, 1 |
| animate | `wait-for` | `0x11f0` | vox-done |
| task-check,task-check | `task-active?` | `0x1238` | patrol, pat-library-horses-inside |
| task-check,task-check | `go` | `0x1270` | wait-interact, 1 |
| animate | `wait-script-caption` | `0x1310` | player, literal-sha256:61c4cf1175dd9884, -1.0, 0, 0 |
| animate | `#%alloc-array` | `0x13a0` | single-frame, 16, 3, 1 |
| animate | `get-spawner-locator` | `0x1490` | ap-pat-library-globe-1, 1 |
| animate | `wait-animate_` | `0x1668` | player, pat-library-ellie-spins-globe--ellie, result(8E0:12) |
| animate | `wait-script-caption` | `0x1710` | dina, literal-sha256:a704d7dd8e7fc950, -1.0, 0, 0 |
| wait-interact | `interactable-enable` | `0x1758` | int-pat-globe-1 |
| animate | `camera-fade-out-animated` | `0x17a0` | 2.0, 0 |
| animate | `wait-script-caption` | `0x1818` | dina, literal-sha256:14b4bb54780f3631, -1.0, 0, 0 |
| wait-interact | `interactable-disable` | `0x1860` | int-pat-globe-1 |
| animate | `wait-script-caption` | `0x18d8` | player, literal-sha256:3aecc3b842df34e6, -1.0, 0, 0 |
| animate | `wait-script-caption` | `0x1960` | player, literal-sha256:423267c7bd8ae005, -1.0, 0, 0 |
| animate | `signal` | `0x19b8` | vox-done, 0 |
| animate | `go` | `0x1a00` | complete, 1 |

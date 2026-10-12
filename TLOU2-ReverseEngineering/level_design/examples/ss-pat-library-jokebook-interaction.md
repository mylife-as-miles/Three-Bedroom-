# ss-pat-library-jokebook-interaction

CONFIRMED from `dc1/ss-patrol/ss-pat-library-jokebook-interaction.bin`. This is level-specific orchestration; animation/dialogue assets are not included.

| Context | Target | Offset | Argument evidence |
| --- | --- | --- | --- |
| task-check | `task-complete?` | `0x750` | patrol, pat-library-horses-inside |
| task-check | `go` | `0x788` | complete, 1 |
| wait-interact | `interactable-disable` | `0x7e8` | int-jokebook-1 |
| animate | `wait-script-caption` | `0x860` | player, literal-sha256:dda04be4ff870213, -1.0, 0, 0 |
| wait-interact | `go` | `0x8b8` | animate, 1 |
| task-check,task-check | `task-active?` | `0x900` | patrol, pat-library-horses-inside |
| task-check,task-check | `go` | `0x938` | wait-interact, 1 |
| animate | `go` | `0x9a8` | complete, 1 |

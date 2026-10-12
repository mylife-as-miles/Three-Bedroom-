# Doors: static evidence

CONFIRMED means a structure or call instruction is present. Branch reachability, native implementation and object configuration remain separate questions. Call offset is a hexadecimal byte offset in the original module; source SHA-256 is in `databases/file_manifest.json`. `result(...)` references another call in the same lambda, not its presumed return value.

## `dc1/ss-t2/ss-openable-door.bin`

8 call sites; 1 state scripts; 1 exported entries.

### `ss-openable-door`

Initial state field: `wait-interact`. A zero SID does not prove that the first table state starts automatically.

```mermaid
stateDiagram-v2
    state "wait-interact" as s0
    state "complete" as s1
    [*] --> s0
    s0 --> s1: player-requested-interact
```

Edges represent explicit `go` call sites, including conditional alternatives. Same-target edges can occur in different tracks; this is not a guaranteed linear execution trace.

#### `wait-interact`

6 call sites. Event listeners: `player-requested-interact`.

| Call target | Example offset | Argument evidence |
| --- | --- | --- |
| `go` | `0x418` | complete, 1 |

#### `complete`

0 call sites. Event listeners: none.

| Call target | Example offset | Argument evidence |
| --- | --- | --- |

Named/global/embedded helpers: `lambda@268`.

## `dc1/anim-player/player-door.bin`

2 call sites; 0 state scripts; 1 exported entries.

Named/global/embedded helpers: `anim-state-phase-func`, `anim-transition-cond-func`.

## `dc1/ss-watchtower/ss-wat-infected-tunnels-rope-puzzle-door.bin`

12 call sites; 1 state scripts; 1 exported entries.

### `ss-wat-infected-tunnels-rope-puzzle-door`

Initial state field: `#0000000000000000`. A zero SID does not prove that the first table state starts automatically.

```mermaid
stateDiagram-v2
    state "task-check" as s0
    state "wait-for-open" as s1
    state "stay-open" as s2
    state "complete" as s3
    s0 --> s3: start
    s0 --> s1: task-complete
    s0 --> s1: start
    s1 --> s3: task-complete
    s1 --> s2: player-requested-interact
```

Edges represent explicit `go` call sites, including conditional alternatives. Same-target edges can occur in different tracks; this is not a guaranteed linear execution trace.

#### `task-check`

6 call sites. Event listeners: `task-complete`.

| Call target | Example offset | Argument evidence |
| --- | --- | --- |
| `go` | `0x848` | wait-for-open, 1 |

#### `wait-for-open`

3 call sites. Event listeners: `player-requested-interact`, `task-complete`.

| Call target | Example offset | Argument evidence |
| --- | --- | --- |
| `go` | `0x7C8` | stay-open, 1 |

#### `stay-open`

2 call sites. Event listeners: none.

| Call target | Example offset | Argument evidence |
| --- | --- | --- |
| `interactable-disable` | `0x8A8` | door-single-metal-b-l-ks9-bf079-1 |

#### `complete`

0 call sites. Event listeners: none.

| Call target | Example offset | Argument evidence |
| --- | --- | --- |

Named/global/embedded helpers: `lambda@380`.

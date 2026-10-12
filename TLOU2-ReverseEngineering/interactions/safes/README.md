# Safes

CONFIRMED world states: setup, wait-interact, no-know-code, move-to, play-idle, check-inventory, input-number, open, fail, early-exit, attacked-out, already-complete, complete. The initial-state field is zero, so actual instantiation semantics remain UNKNOWN.

World script initializes HUD lock data with dial mode, submits current input, branches open/fail and calls hud2-win-lock-minigame/hud2-fail-lock-minigame. Direct world sites include submit at 0x11B48, open branch at 0x11F98, fail branch at 0x11FD0 and win at 0xF418. It checks treasure knowledge and loads quick-inspection objects for relevant notes. Motion/animation/camera and attack/early-exit cleanup remain world responsibilities.

CONFIRMED HUD states: wait-for-data, setup, input-code, finish-combo, success, fail, investigate, --all--. hud-set-data starts setup. Widgets are found/created through gui2 APIs; permanent attachable spinner path is hud-minigames/hud-lock/lock-analog-static-ws at 0x6FC8. Digit child arrays, selected digit state, formatted numeric/code text, spinner hints and success/fail visual changes are visible. HUD listeners include hud-input-changed, hud-lock-in-code, hud-reset, hud-success, hud-fail and investigate-started. This proves a two-way world/HUD protocol; it does not prove HUD owns all correctness.

CONFIRMED persistence: setup reads ss-svar(opened,self) at 0xFD60/0xFD70; open writes it at 0x167A0, updates safes-opened/safes-found and broadcasts opened-safe at 0x1A110. Exact combination algorithms, native data struct schema, controller remapping and audio-bank implementation remain UNKNOWN. [Independent graphs and evidence](evidence.md).

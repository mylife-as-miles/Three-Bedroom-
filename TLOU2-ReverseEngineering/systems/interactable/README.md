# Interactable

CONFIRMED: 273 gameplay definitions, the nearby/closest APIs, native interaction override/enable/disable and scan-exclusion calls are present. Script-funcs-interactables exports two actual DC helpers: interactable-adopt-settings and interactable-clear-adopted-settings. The core detector/selector functions do not have recovered DC bodies.

HIGH CONFIDENCE: scripts configure/gate a native selector. UNKNOWN: distance/orientation scoring, object reservation, priority rules, native player-state eligibility, prompt timing and actual physical bindings. Definition metadata retains member offsets; it does not assign guessed numeric-field names. Compare interacting/full-inventory/crouched/blocked scenarios in a native trace before changing those fields.

See ../../databases/interaction_definitions.json and engine_api.json. Related files are discovered through filenames, SID uses, actual call instructions and module imports rather than filenames alone.

[Generated corpus evidence](evidence.md).

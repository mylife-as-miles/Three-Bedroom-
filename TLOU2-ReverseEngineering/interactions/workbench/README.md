# Workbench

CONFIRMED: world workbench has 17 states and 2,082 call sites. UI and upgrade menus are separate scripts; helper/settings modules are independently indexed. World states cover unavailable/trap modes as well as enter/idle/table/bag/disassembly/application/assembly/inspection/exit.

CONFIRMED choreography: world code spawns weapon processes and tools, handles backpack models, sets mesh/visibility/weapon strap parameters, synchronizes with animation phase and camera IDs, and resolves character/weapon/upgrade settings. Ellie/Abby settings are different exported data. Texture prioritization belongs to runtime residency; it is separate from persistence.

CONFIRMED protocol: events include changed-currently-selected-weapon, enter-upgrade-menu, exit-upgrade-menu, workbench-menu-exit, inspect-weapon and workbench-menu-exit-inspect. World sends show-upgrade-screen at 0x24CE0 and menu-fade-in at 0x1A628; it broadcasts workbench-exited at 0x34DB8. UI requests and cinematic execution are separate owners.

CONFIRMED upgrade boundary: weapon-upgrade-apply-bundle occurs at 0x191B8/0x19590 and in model-preparation helpers. That symbol alone does not prove where parts are debited or a permanent upgrade is purchased; interface arguments and native calls must be followed. Inventory parts quantity, owned/active upgrade bundles and affordability helpers are present. Workbench-used and workbenches-found svars/counters are distinct from player in-workbench facts and remember-dynamic-checkpoint.

HIGH CONFIDENCE: workbench is the best reference for a new complex application-like interaction using existing assets/APIs. UNKNOWN: arbitrary new weapon model/upgrade schema support, every native purchase/storage effect and custom animation compatibility. [Evidence](evidence.md).

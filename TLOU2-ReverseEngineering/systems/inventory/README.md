# Inventory

CONFIRMED: scripted collection reaches player-apply-pickup, item quantity APIs, treasure collection/examination and owned/active upgrade APIs. The observed CallFf sites lack DC implementations. HIGH CONFIDENCE: these are native ownership boundaries.

Exact earliest script handoff for drawer collection is player-apply-pickup at 0x1A00 in drawer-atachments and 0x12E78 in melee-abort; cabinet has its own application sites. Investigation uses inventory-item-add-quantity at 0xCF78 and treasure registration paths. These are distinct item vs collectible contracts.

UNKNOWN: first internal native write, quantity clamp, ammo merging, overflow handling, persistence/notification/despawn order. Object attachment is visual choreography and does not itself prove inventory transfer. Workbench bundle application to temporary models likewise does not establish permanent upgrade purchase or parts consumption. Request a native trace of the actual API caller/effects to close these boundaries.

[Generated corpus evidence](evidence.md).

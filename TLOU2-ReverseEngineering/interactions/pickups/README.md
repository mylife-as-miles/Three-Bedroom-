# Pickups

CONFIRMED: world items, scan eligibility, scripted movement, application, tutorial/notification consumers and persistence interfaces are separate surfaces. `player-is-pickup-scripted-move?`, scan exclusion APIs, `player-pickup`, `player-pickup-is-full`, `item-pickup-get-item-id` and `player-apply-pickup` are indexed globally. They do not supply the native scan implementation.

CONFIRMED inventory handoff: drawer 0x1A00/0x12E78 and cabinet 0x1318/0xC090 call `player-apply-pickup` with the current pickup object. There is no DC definition for that symbol, and the sites are CallFf. HIGH CONFIDENCE: this is the reusable native application boundary. UNKNOWN: the exact first inventory write inside it; do not claim attachment itself changes inventory.

Other paths are explicit: `ss-investigate-object` calls `inventory-item-add-quantity(..., 1)` at 0xCF78 and treasure APIs on exit/quick grab/attack. `ss-crafting-recipe-from-pickup` reacts to `player-pickup` and `upgrade-manual-found`, writes discovery/tutorial svars and contains smoke/stun-bomb conversion helpers. `ss-grounded-pickup-despawn` sends checkpoint/spawn-control events and kills entities when supply conditions apply. Those are CONFIRMED call patterns, not a universal pickup sequence.

Notifications, item disappearance and persistence can occur inside native pickup or in script consumers. Exact timing across those owners remains UNKNOWN. [Evidence](evidence.md) and `systems/inventory` list the reachable interfaces.

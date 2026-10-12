# Notes

CONFIRMED: note readability, collectible registration, examined status, journal entries, menu records and task flags are distinct. Investigation exposes player-investigate-make-readable, collect-treasure, mark-treasure-examined-by-id and HUD notifications. World examination uses HUD read-page APIs. `ss-menu2-collectibles` is its own UI state script; player-journal actor states and journal-info/journal-entries data are separate.

The actual file manifest includes `journal-interesurgeonguild.bin`; it does not contain the supplied journal-interests name verbatim. The actual `level-sets/ss-ski-coastal-note-prompt-activator.bin` has task-check, bottom-infected-dead, activate-note and done states. Its script must be traced as one level-specific eligibility gate, not treated as the global note scanner.

HIGH CONFIDENCE: world object -> enabled interaction -> investigation/read HUD -> native treasure registration -> menu/journal queries is a reusable composition. UNKNOWN: whether every note uses that sequence, how collection is serialized and which flags unlock journal/story behavior. Native collectible APIs, object-scoped used and task state must be checked independently. [Evidence](evidence.md).

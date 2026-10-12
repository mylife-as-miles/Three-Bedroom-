# Audio

CONFIRMED: actual common-object packages include drawer wood/metal, cabinet wood/metal/fridge/locker, doors/gates/handle types, safe/keypad/generator, rope materials and physics books/paper. They export sfx-info family records; scripts contain direct play-sound, play-sound-at-joint/position, audio-gameplay-event and pickup sound calls.

Direct supported chain: scripted call -> literal sound SID -> matching exported sfx record/module. Dependency metadata stores the call offset and export identity. Drawer pickup sound is explicitly triggered at wrist stages, then suppress-pickup-sound precedes player-apply-pickup. That is CONFIRMED choreography.

INFERRED: generic furniture movement may route through animation events/material selection. UNKNOWN: exact animation event -> wood/metal sound dispatch, emitter definition and bank contents for every actor. The bin corpus lacks the full animation and sound-bank assets. Package existence alone cannot identify the precise open/close frame. See ../../databases/dependencies.json for observed calls/references and ../../databases/modules.json for declared imports.

[Generated corpus evidence](evidence.md).

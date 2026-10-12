# Native modding boundaries

See ../ENGINE_BOUNDARIES.md and ../databases/engine_api.json. CONFIRMED: the scripts expose calls; HIGH CONFIDENCE: missing DC bodies plus CallFf identify native/import boundaries. Neither observation gives a native address or executable-version compatibility guarantee.

Priority native research: interactable scoring/reservation, directional door definition selection, player-apply-pickup storage effects, investigation manipulation input, drawer flag writers/save restore, animation event audio dispatch, rope constraint solving and AI perception evaluation. NdGameSdk/runtime hooks may support this work, but no executable offsets or hook integration were tested here.

No DRM/anti-cheat bypass or native binary patching was performed. Keep research in the owned offline build and treat each native ABI contract as UNKNOWN until validated.

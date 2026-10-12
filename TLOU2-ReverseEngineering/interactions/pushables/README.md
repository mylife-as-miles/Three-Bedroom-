# Pushables

CONFIRMED: push-object is data, player-push-object exports actor-state data, ss-push-follow-cam handles camera orchestration and a shipped test puzzle pushable script exposes event composition. Level scripts add actor-specific gates and story actions. A test script's presence does not prove it is enabled in production.

HIGH CONFIDENCE: interact/grab/release and movement are requests into an existing native push controller with configuration and animation dependencies. Exact alignment, turn speed, contact/physics behavior, obstacle handling, root motion, navigation updates and camera blending are UNKNOWN unless supported by a specific script call/field.

Use the evidence graph to identify world event and camera contracts; reuse a verified existing pushable archetype before considering a new mechanic. [Evidence](evidence.md).

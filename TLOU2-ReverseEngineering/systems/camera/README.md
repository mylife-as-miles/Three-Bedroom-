# Camera

CONFIRMED: scripts request animated cameras, cut/blend/stick/stick-pan modes, overlays, near clip, render overrides and fades. Investigation uses player-state-specific camera paths; ss-examine uses explicit stick camera plus read/idle/exit states; workbench has named camera IDs across disassembly/assembly/inspection.

HIGH CONFIDENCE: camera behavior is authored through script/data while the underlying solver is native. UNKNOWN: camera collision, precise stick sensitivity, zoom/tilt curves and all transform composition. A call named camera-enable-animated-stick proves the API request, not arbitrary object manipulation.

Cleanup matters: cancellation/attack/exit paths fade/disable camera and restore relevant flags. Preserve those paths when composing new interactions. Native auto-restoration and exact ownership under concurrent scripts need runtime observation.

[Generated corpus evidence](evidence.md).

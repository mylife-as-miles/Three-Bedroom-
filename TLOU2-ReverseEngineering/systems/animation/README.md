# Animation

CONFIRMED: DC orchestrates animate_/wait-animate_, animation phase/frame/duration, AP reference alignment, actor state requests, attachment and IK interfaces. Drawer proxy IK is explicitly exposed; this is stronger evidence than a generic claim that “all IK is invisible native code.”

Actor-state-list data in player-door/investigate/ladder/climb/push/squeeze/rope modules is distinct from StateScript. Clip/transition symbols can be configured while execution remains native. HIGH CONFIDENCE: native controller/animation blending consumes the definitions and script requests. UNKNOWN: full blend trees, motion matching, root motion/controller coupling and solver math.

The dependency map records observed symbols/exports/calls. A clip name is an asset reference, not proof of owning its animation file or a particular root-motion property. Native calls for get-animation-phase and attach do not expose the engine implementation. See ../../interactions/drawers for AP-reference/IK choreography and ../../interactions/workbench for phase-synchronized model assembly.

[Generated corpus evidence](evidence.md).

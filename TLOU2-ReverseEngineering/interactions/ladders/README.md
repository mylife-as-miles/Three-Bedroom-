# Ladders

CONFIRMED: ss-basic-ladder implements portable ladder initial/on-ground/pick-up-ladder/hold/drop-ladder, not full player climbing. It calculates locators, uses raycast queries to assess placement, changes collision/movement mode, manages input/HUD and lerps object placement. Its drop/hold/ground transitions are explicit in the generated graph.

Player-ladder, character-ladder, player-climb, player-edge-climb, player-parametric-climb-sets and player-squeeze-through are distinct animation/controller data modules. Their references connect player movement to authored animation definitions; some embedded conditions are lambdas. Zero calls in a pure data file does not mean native traversal is absent.

HIGH CONFIDENCE: geometry/locators, controller mode, collision/raycast queries and animation settings compose traversal. UNKNOWN: complete IK, root motion, navigation and physics execution, or support for arbitrary new geometry/animation combinations. [Evidence](evidence.md).

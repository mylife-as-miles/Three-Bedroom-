"""THREE BEDROOM Blender generator package (scripts/blender/tb).

Deterministic builders that turn a schema-v2 apartment spec
(scripts/blender/spec/SCHEMA.md) into the editable .blend source of truth.

Module map
  geom            pure-python 2D helpers (no bpy)
  spec            spec loading, wall joints, room sides, ceiling function (no bpy)
  mesh            MeshBuilder (closed shells, materials, world-scale UVs) + object helpers
  scene           collections + build context
  materials       MAT_<key> blockout materials
  arch            walls, floors, ceilings, dormers, skirting, cornice
  openings        door frames/leaves, windows, glass, curtains/blinds
  items_blockout  furniture / appliance / decor blockouts, light-fixture geometry
  cameras         CAM_<ref> (binding camera math)
  collision       '<name>-colonly' proxies
  markers         SPAWN_player, ROOM_<id>
  lighting        'review' and 'night' rigs (never exported)
"""
GENERATOR = "scripts/blender/build_apartment.py"
GENERATOR_VERSION = 1

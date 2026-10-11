# `apartment_spec.json` schema (v2)

v2 supersedes v1 after the scope change of 2026-10-11 (build every room **except** the living room;
the living room is an empty walled placeholder). Coordinates/placement: `docs/CONVENTIONS.md` §1–2.
All lengths in metres, angles in degrees, world coordinates (not room-local) unless stated.

```jsonc
{
  "schema_version": 2,
  "name": "three_bedroom_apartment_2026",
  "storey": {"default_ceiling_height": 2.60, "slab_thickness": 0.25},

  "rooms": [
    {
      "id": "bedroom_1",                  // bedroom_1 | bedroom_2 | bedroom_3 | kitchen | bathroom | hall | living_placeholder | closet_* ...
      "name": "Bedroom 1 (teal attic)",
      "references": ["MOOD03"],           // reference ids that define this room
      "placeholder": false,               // true ONLY for living_placeholder: walls/floor/ceiling + doorways, no furnishing
      "polygon": [[x,y], ...],            // interior boundary (finished wall faces), counter-clockwise
      "floor_finish": "timber_worn_boards",
      "floor_plank_direction_deg": 0,
      "wall_finish_default": "plaster_teal",
      "ceiling_finish": "plaster_textured",
      "ceiling": {
        "type": "flat",                   // flat | sloped
        "height": 2.60,                   // flat height (for sloped: height of the flat collar part / ridge plateau)
        "slopes": [                       // only for "sloped": ceiling descends toward each listed wall
          {"wall": "W_ext_north", "knee_height": 1.05, "pitch_deg": 45}
          // ceiling z at a point = min(height, knee_height + distance_to_wall_face * tan(pitch)) over all slopes
        ]
      }
    }
  ],

  "walls": [
    {
      "id": "W_ext_north",
      "kind": "exterior",                 // exterior | interior | party (shared with neighbour / stairwell)
      "start": [x, y], "end": [x, y],     // the wall's CENTRE line
      "thickness": 0.30,                  // exterior ~0.30–0.40, interior partitions ~0.10–0.15
      "height": null,                     // null => up to the ceiling of the rooms it bounds
      "finish_left": null,                // face on the LEFT when walking start->end; null => wall_finish_default of the room it bounds
      "finish_right": "exterior",         // face on the RIGHT ('exterior' for outside faces)
      "skirting": {"height": 0.12, "depth": 0.018},
      "openings": [
        {
          "id": "D_br1",
          "type": "door",                 // door | doorway (no leaf) | window | roof_window | dormer | sliding_door | louvered_pair
          "offset": 1.20,                 // along start->end, from `start` to the opening's NEAR edge
          "width": 0.82,
          "sill_height": 0.0,             // 0 for doors
          "height": 2.03,
          "connects": ["hall", "bedroom_1"],   // room ids (or "exterior" / "stairwell")
          "hinge": "start",               // doors: which jamb carries the hinges (start-side or end-side)
          "swing_into": "bedroom_1",      // doors: room the leaf swings into
          "leaf": "panel_white",          // panel_white | panel_wood | louvered_pair | glazed | none
          "details": {}                   // windows: {"curtains": "...", "blind": "...", "panes": "..."}; dormer: {"depth": 1.1, "roof": "gable"}
        }
      ]
    }
  ],

  "items": [
    {
      "id": "FURN_br1_bed",
      "room": "bedroom_1",
      "category": "furniture",            // furniture | appliance | fixture | decor | prop | light_fixture
      "type": "bed",                      // vocabulary below; unknown types fall back to a box
      "position": [x, y, z],              // footprint centre; z = bottom of item
      "yaw_deg": 0,                       // 0 => front faces +Y
      "dimensions": [w, d, h],
      "wall": null,                       // wall id for wall-mounted / against-wall items
      "interactive": false,
      "evidence": ["MOOD03"],             // reference ids, or "design" for items invented for unseen walls
      "confidence": 0.7,
      "notes": "dark wood frame, striped duvet thrown back, two pillows"
    }
  ],

  "lights": [
    {"id": "LGT_br1_fan", "room": "bedroom_1", "type": "ceiling_fan_light", "position": [x, y, z], "notes": ""}
  ],

  "cameras": [
    {
      "ref": "MOOD03",                    // reference id this proxy camera reproduces
      "room": "bedroom_1",
      "position": [x, y, z], "look_at": [x, y, z],
      "horizontal_fov_deg": 90, "roll_deg": 0,
      "confidence": 0.5, "notes": ""
    }
  ],

  "spawn": {"room": "bedroom_3", "position": [x, y, 0], "yaw_deg": 0},

  "uncertainties": [
    {"id": "U-001", "topic": "…", "range": [a, b], "chosen": c, "reason": "…", "evidence": ["…"]}
  ]
}
```

## Wall rules

* Each wall segment bounds **at most one room on each side**. Split long exterior walls at partition junctions.
* Exterior segments meet at their centre-line intersections. Partitions run between the interior faces of the walls they abut.
* Every room polygon edge must be covered by the face of some wall segment (validator checks this, tolerance 1 cm).

## Finish keys

Floors: `timber_worn_boards`, `timber_dark_planks`, `linoleum_patterned`, `tile_bathroom_floor`, `carpet_low_pile`, `concrete_bare` (placeholder)
Walls: `plaster_white`, `plaster_beige`, `plaster_teal`, `plaster_sage`, `plaster_green_dark`, `wallpaper_striped`, `wood_panelling`, `tile_white_square`, `brick_red`, `wainscot_white`, `exterior`
Ceilings: `plaster_textured`, `plaster_smooth`, `wood_boards`
New keys may be added; document them in `docs/spatial_reconstruction.md`.

## Item type vocabulary

Furniture: `bed`, `nightstand`, `dresser`, `wardrobe`, `desk`, `chair`, `desk_chair`, `bookcase`, `shelf_wall`, `dining_table`, `dining_chair`, `stool`, `side_table`, `hutch_cabinet`, `coat_rack`, `bench`, `rug`
Appliances: `fridge`, `stove`, `microwave`, `range_hood`, `water_heater`, `washing_machine`, `crt_tv`, `tv_flat`, `computer_retro`, `record_player`, `speaker`, `floor_fan`, `rice_cooker`, `kettle`, `telescope`, `guitar`, `guitar_amp`
Kitchen: `base_cabinet_run`, `upper_cabinet`, `kitchen_sink`, `side_counter`, `dish_rack`
Fixtures: `radiator`, `electrical_panel`, `toilet`, `bathroom_vanity`, `mirror`, `bathtub`, `shower`, `towel_rail`, `curtain_rod`, `closet_louvered`, `door_hooks`
Lighting: `ceiling_fan_light`, `ceiling_light_flush`, `pendant_shade`, `bare_bulb`, `floor_lamp`, `table_lamp`, `lava_lamp`, `wall_light`
Decor/props: `poster`, `framed_art`, `vinyl_record_wall`, `sticky_notes`, `wall_clock`, `calendar`, `plant`, `tablecloth`, `tableware_set`, `book_stack`, `cardboard_box`, `clothes_pile`, `pillow`, `newspaper`, `misc`

## Camera math (binding — the overlay tool, the Blender camera builder and the Godot view bridge must all agree)

Given `position P`, `look_at T`, `horizontal_fov_deg h`, `roll_deg ρ`, image width `W`, height `H` (square pixels):

```
f  = normalize(T - P)                 # forward
r  = normalize(cross(f, Z_UP))        # right   (Z_UP = (0,0,1))
u  = cross(r, f)                      # up
r' =  cos(ρ)·r + sin(ρ)·u             # roll = rotation about the camera's local +Z (Blender convention,
u' = -sin(ρ)·r + cos(ρ)·u             #        local +Z points backwards, i.e. along -f)
k  = (W/2) / tan(h/2)
for a world point X with d = X - P:  xc = d·r', yc = d·u', zc = d·f   (visible if zc > 0.05)
pixel = ( W/2 + k·xc/zc ,  H/2 - k·yc/zc )
```

Blender equivalent: camera `sensor_fit = 'HORIZONTAL'`, `angle_x = radians(h)` (equivalently `lens = sensor_width / (2·tan(h/2))`), render resolution W×H, rotation = look-at (camera −Z → f, camera +Y → u) followed by a rotation of ρ about the camera's local Z.
Godot equivalent: `Camera3D.keep_aspect = KEEP_WIDTH`, `fov = h` (Godot's `fov` is then horizontal).

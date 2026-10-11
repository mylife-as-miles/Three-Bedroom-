# `apartment_spec.json` schema (v1)

Coordinate and placement conventions: see `docs/CONVENTIONS.md` §1–2. All lengths in metres, angles in degrees.

```jsonc
{
  "schema_version": 1,
  "name": "three_bedroom_apartment_2026",
  "ceiling_height": 2.80,                 // finished floor to finished ceiling, main room
  "rooms": [
    {
      "id": "main",                       // "main" | "bathroom" | other ids if the evidence supports them
      "polygon": [[0,0],[L,0],[L,W],[0,W]],   // interior boundary, counter-clockwise, floor plane
      "ceiling_height": 2.80,
      "floor_finish": "timber_dark_planks", // finish keys, see below
      "ceiling_finish": "textured_plaster",
      "floor_plank_direction_deg": 0      // plank long axis yaw (0 = along +X)
    }
  ],
  "walls": [
    {
      "id": "W_window",                   // W_window | W_kitchen | W_entrance_end | W_sleeping_end | W_bath_* ...
      "start": [0, 0], "end": [L, 0],     // interior face line; room interior is on the LEFT when walking start->end
      "height": 2.80,
      "thickness": 0.30,
      "finish": "brick_red",              // interior finish of the face that bounds the room on its left side
      "finish_other_side": null,          // finish for the other face if it bounds another room (e.g. bathroom tile)
      "skirting": {"height": 0.10, "depth": 0.015},
      "cornice": {"height": 0.08, "depth": 0.06},
      "openings": [
        {
          "id": "WIN_1",
          "type": "window",               // window | door | doorway | sliding_door
          "offset": 1.20,                 // distance along the wall from `start` to the opening's left edge (as seen from the room)
          "width": 0.95,
          "sill_height": 0.85,            // bottom of opening above floor (0 for doors)
          "height": 1.55,                 // opening height
          "reveal_depth": 0.30,           // optional, defaults to wall thickness
          "leads_to": "exterior",         // exterior | bathroom | corridor | room id
          "details": {"blind": "venetian_wood", "sill_depth": 0.18, "panes": "double_hung"}
        }
      ]
    }
  ],
  "items": [
    {
      "id": "FURN_sofa",
      "category": "furniture",            // furniture | appliance | fixture | decor | prop | light_fixture
      "type": "sofa",                     // controlled vocabulary below; unknown types fall back to a box
      "position": [x, y, z],              // footprint centre; z = bottom of item
      "yaw_deg": 0,                       // 0 => front faces +Y
      "dimensions": [w, d, h],
      "wall": null,                       // wall id for wall-mounted / against-wall items
      "room": "main",
      "interactive": false,               // true if planned as an interaction target
      "evidence": ["APT07", "APT11"],     // reference ids that show it
      "confidence": 0.8,                  // 0..1 for position+size
      "notes": "brown leather, 3 seat cushions, 2 back cushions, loose orange pillows"
    }
  ],
  "lights": [
    {"id": "LGT_ceiling_fan", "type": "ceiling_fan_light", "position": [x, y, z], "notes": ""}
  ],
  "cameras": [
    {
      "ref": "APT07",
      "position": [x, y, z],
      "look_at": [x, y, z],
      "horizontal_fov_deg": 90,
      "roll_deg": 0,
      "confidence": 0.6,
      "notes": "eye height, standing by floor lamp"
    }
  ],
  "uncertainties": [
    {"id": "U-001", "topic": "room length", "range": [9.0, 11.0], "chosen": 10.0, "reason": "…", "evidence": ["…"]}
  ]
}
```

## Finish keys

`brick_red`, `plaster_beige`, `plaster_white`, `tile_white_square`, `timber_dark_planks`, `textured_plaster`, `tile_dark_floor`.
New keys may be added; document them in the reconstruction report.

## Item type vocabulary

Furniture: `sofa`, `coffee_table`, `tv_unit`, `bookcase`, `bed`, `nightstand`, `desk`, `chair`, `dining_table`, `stool`, `round_side_table`, `metal_shelf_unit`, `kitchen_island_table`, `drawer_cabinet`
Appliances: `fridge`, `stove`, `microwave`, `range_hood`, `washing_machine`, `tv_flat`, `crt_tv`, `ac_unit`, `kettle`, `toaster`, `coffee_maker`, `speaker`
Kitchen: `base_cabinet_run`, `upper_cabinet`, `kitchen_sink`, `open_shelf`, `side_counter`
Fixtures: `radiator`, `electrical_panel`, `barn_door`, `barn_door_track`, `entrance_door`, `toilet`, `bathroom_vanity`, `mirror`, `bathtub`, `shower`
Lighting: `ceiling_fan_light`, `ceiling_light_flush`, `floor_lamp`, `table_lamp`, `banker_lamp`, `wall_light`
Decor/props: `poster`, `licence_plate`, `plate_cluster`, `framed_art`, `wall_clock`, `easel`, `cardboard_box`, `dumbbell`, `vase`, `book_stack`, `mug`, `plate`, `bowl`, `bottle`, `plant`, `rug`, `misc`

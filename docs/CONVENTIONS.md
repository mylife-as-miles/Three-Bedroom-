# Production conventions (binding for every agent)

## 1. Units and coordinates

* Metres everywhere. Blender scenes are **Z-up**; glTF export converts to Godot's **Y-up** (Blender +Z → Godot +Y, Blender +Y → Godot −Z).
* **Apartment origin** (Blender): the interior floor corner where the **window wall** (long brick wall with the windows, radiators, TV unit and plate collection) meets the **entrance end wall** (plaster wall with the white entrance door and electrical panel).
  * **+X** runs along the window wall from the entrance end toward the sleeping end (bookcase / bed / AC unit).
  * **+Y** runs from the window wall into the room toward the opposite long wall (**kitchen wall**: barn door, fridge, kitchen run).
  * **+Z** up; finished floor top surface is `z = 0`.
* Interior faces of walls sit on the room boundary; wall thickness extends *outward* (window wall extends to negative Y, etc.).

## 2. Placement convention (spec + generators)

Every placed item has:

| field | meaning |
|---|---|
| `position` `[x, y, z]` | centre of the item's footprint, `z` = bottom of the item (0 for floor-standing) |
| `yaw_deg` | rotation about +Z. At `yaw_deg = 0` the item's **front** (seat side of a sofa, door side of a cabinet, screen of a TV, face of a poster) faces **+Y**. 90 → front faces −X, 180 → −Y, 270 → +X |
| `dimensions` `[w, d, h]` | width along local X, depth along local Y (front-to-back), height Z |

Wall-mounted items additionally carry `wall` (wall id) and `z` = bottom edge height.

## 3. Naming (Blender objects → Godot import)

| prefix / suffix | meaning |
|---|---|
| `ARCH_*` | architecture (walls, floor, ceiling, skirting, trims, window frames, door frames) |
| `FURN_*` | furniture and appliances |
| `PROP_*` | small props / decor |
| `LGT_*` | light fixtures (geometry); `LIGHT_*` are light objects |
| `INT_*` | interactive objects (drawers, doors, pick-ups). Pivot at the physical hinge/slide origin |
| `CAM_APTxx` | proxy cameras matching reference view `APTxx` |
| `*-colonly` | collision-only proxy mesh (Godot import creates a static trimesh body, no visual). Keep them simple boxes |
| `*-convcolonly` | convex collision-only proxy |

Collections: `Architecture`, `Furniture`, `Props`, `Lighting`, `Collision`, `Cameras`, `Interactive`.

## 4. Source of truth and generation

* `scripts/blender/` contains deterministic generators. `blender/*.blend` files are produced by them and are the editable source of truth for meshes/materials/rigs. Manual edits made in a `.blend` must be back-ported to the generator or recorded in `docs/PRODUCTION_LEDGER.md`.
* The architectural spec lives at `scripts/blender/spec/apartment_spec.json`. Generators read it; nothing hard-codes room dimensions.
* Runtime assets in `assets/runtime/` are exported by `scripts/blender/export_runtime.py` only.
* **No Three.js** or any library built on it, anywhere. No screenshots used as textures or billboards.
* Git LFS is unavailable (account LFS budget exhausted). Keep each committed binary < 40 MB; save `.blend` with compression.

## 5. Heavy jobs

Any Blender render/bake/export, Godot import/export, or headless-browser capture runs through:

```
build/heavy.sh "<label>" <command ...>
```

It serialises jobs with `flock` on a 4-vCPU, GPU-less host. Never launch Blender/Godot/Chromium directly from parallel agents. Cycles is CPU-only here — keep reference renders modest (e.g. 960×540, 32–128 samples + OpenImageDenoise) unless a task explicitly needs more.

Binaries: `blender` (5.2.2 LTS), `godot` (4.6.3 stable). Godot needs `--headless` for import/export; rendering tests need `xvfb-run -a`.

## 6. Ownership and handoffs

* Each agent writes only the files/directories its task assigns. Do not edit files owned by another task; report needed changes in the handoff instead.
* Agents do **not** run `git commit`/`git push`. The orchestrator reviews and commits.
* Every agent ends with a handoff: work completed · files modified · evidence produced (paths) · tests run (command + result) · remaining defects · blockers.
* Never claim a render, export, test or measurement that was not actually produced. Evidence paths must exist.

## 7. Evidence layout

* `renders/cycles/<iteration>/<VIEW>.png` — Blender Cycles reference frames
* `renders/browser/<iteration>/<VIEW>.png` — frames captured from the real web build in Chromium
* `renders/compare/<iteration>/<VIEW>.jpg` — reference | Cycles | browser side-by-sides
* `qa/reviews/<iteration>/<critic>.md` — critic reports

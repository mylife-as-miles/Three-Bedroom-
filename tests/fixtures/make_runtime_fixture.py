"""TEST FIXTURE ONLY -- NOT PRODUCTION GEOMETRY.

Builds a deliberately simple box-model GLB plus ``apartment_meta.json`` that follow the
RUNTIME CONTRACT (exporter -> Godot) so the Godot project and the browser harness can be
tested before ``scripts/blender/build_apartment.py`` lands.  Geometry is read from a
schema-v2 spec (default: the shared read-only fixture ``tests/fixtures/mini_spec_v2.json``):

* floors / flat or sloped ceilings from room polygons (sloped ceilings follow the SCHEMA.md
  formula; break lines are exact for axis-aligned slope walls),
* walls as boxes along their centre lines, split around openings (doors/doorways cut to
  the floor, windows keep sill + head pieces; dormers are NOT modelled - the wall stays
  closed there),
* a closed leaf in every door that leads to "stairwell"/"exterior" (keeps the player in),
* a 2 cm threshold strip in every interior door (exercises the runtime small-step code),
* items as coloured boxes (front = +Y at yaw 0, CONVENTIONS.md section 2),
* emissive bulb geometry for each spec light (NO punctual lights are exported),
* ``*-colonly`` box proxies for walls, floors, door leaves, thresholds and furniture,
* ``CAM_<ref>`` cameras built with the binding camera math (SCHEMA.md), ``SPAWN_player``.

Every exported file is marked as a fixture: the meta carries ``"fixture": true`` and
``"generator": "tests/fixtures/make_runtime_fixture.py"``; the GLB scene carries the
custom property ``three_bedroom_fixture = True``.

Run (heavy job, Blender 5.2.2):
    build/heavy.sh "runtime fixture" blender -b --factory-startup \
        -P tests/fixtures/make_runtime_fixture.py -- \
        [--spec tests/fixtures/mini_spec_v2.json] [--out godot/fixtures/runtime]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

REPO = Path(__file__).resolve().parents[2]
GENERATOR = "tests/fixtures/make_runtime_fixture.py"
COORD_NOTE = "godot (x, y, z) = blender (x, z, -y); godot rotation.y (rad) = radians(blender yaw_deg)"
DEFAULT_IMAGE_SIZE = [960, 540]
THRESHOLD_HEIGHT = 0.02

# Bulb offsets (metres, along +Z) from the spec light anchor.  Mirrors the table in
# godot/scripts/world/lighting_rig.gd so the emissive bulb sits where Godot puts the light.
BULB_OFFSET_Z = {
    "pendant_shade": -0.45,
    "ceiling_fan_light": -0.32,
    "ceiling_light_flush": -0.12,
    "bare_bulb": -0.28,
    "floor_lamp": 1.40,
    "table_lamp": 0.32,
    "lava_lamp": 0.25,
    "wall_light": 0.0,
}

FINISH_RGB = {
    "plaster_white": (0.80, 0.80, 0.77),
    "plaster_beige": (0.72, 0.64, 0.52),
    "plaster_teal": (0.16, 0.42, 0.42),
    "plaster_sage": (0.52, 0.60, 0.47),
    "plaster_green_dark": (0.16, 0.26, 0.18),
    "wallpaper_striped": (0.62, 0.55, 0.45),
    "wood_panelling": (0.38, 0.24, 0.13),
    "tile_white_square": (0.86, 0.87, 0.86),
    "brick_red": (0.48, 0.22, 0.15),
    "wainscot_white": (0.82, 0.82, 0.80),
    "exterior": (0.30, 0.30, 0.30),
    "timber_worn_boards": (0.36, 0.23, 0.13),
    "timber_dark_planks": (0.20, 0.12, 0.07),
    "linoleum_patterned": (0.55, 0.50, 0.38),
    "tile_bathroom_floor": (0.70, 0.70, 0.68),
    "carpet_low_pile": (0.40, 0.35, 0.30),
    "concrete_bare": (0.42, 0.42, 0.42),
    "plaster_textured": (0.84, 0.83, 0.80),
    "plaster_smooth": (0.86, 0.86, 0.84),
    "wood_boards": (0.45, 0.32, 0.20),
}

ITEM_RGB = {
    "bed": (0.55, 0.18, 0.16),
    "nightstand": (0.33, 0.20, 0.10),
    "table_lamp": (0.90, 0.82, 0.62),
    "rug": (0.42, 0.12, 0.20),
    "coat_rack": (0.12, 0.08, 0.06),
}

COLLIDING_CATEGORIES = {"furniture", "appliance", "fixture"}
NON_COLLIDING_TYPES = {"rug", "poster", "framed_art", "calendar", "sticky_notes", "tablecloth"}


# --------------------------------------------------------------------------- helpers

def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(description="Write a TEST FIXTURE GLB + apartment_meta.json")
    ap.add_argument("--spec", default="tests/fixtures/mini_spec_v2.json",
                    help="schema-v2 spec (relative to repo root or absolute)")
    ap.add_argument("--out", default="godot/fixtures/runtime",
                    help="output directory (relative to repo root or absolute)")
    ap.add_argument("--name", default="apartment", help="basename: <name>.glb + <name>_meta.json")
    return ap.parse_args(argv)


def repo_path(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else (REPO / path)


def rel_to_repo(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def to_godot(v) -> list[float]:
    """Blender (x, y, z) -> Godot (x, z, -y), rounded for stable JSON."""
    return [round(float(v[0]), 5), round(float(v[2]), 5), round(-float(v[1]) + 0.0, 5)]


def point_in_polygon(x: float, y: float, poly: list[list[float]]) -> bool:
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            xcross = xi + (y - yi) * (xj - xi) / (yj - yi)
            if x < xcross:
                inside = not inside
        j = i
    return inside


def room_at(rooms: list[dict], x: float, y: float) -> dict | None:
    for room in rooms:
        if point_in_polygon(x, y, room["polygon"]):
            return room
    return None


_materials: dict[str, bpy.types.Material] = {}


def material(key: str, rgb, roughness: float = 0.8, emission: float = 0.0) -> bpy.types.Material:
    if key in _materials:
        return _materials[key]
    mat = bpy.data.materials.new("FIX_" + key)
    mat.diffuse_color = (*rgb, 1.0)
    bsdf = next((n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
    if bsdf is None:
        bsdf = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
        out = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
        mat.node_tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    if emission > 0.0:
        bsdf.inputs["Emission Color"].default_value = (*rgb, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emission
    _materials[key] = mat
    return mat


_collections: dict[str, bpy.types.Collection] = {}


def collection(name: str) -> bpy.types.Collection:
    if name not in _collections:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
        _collections[name] = col
    return _collections[name]


def new_object(name: str, mesh: bpy.types.Mesh | None, col: str) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, mesh)
    collection(col).objects.link(obj)
    return obj


class MeshBuilder:
    """Accumulates boxes / polygons in one bmesh with per-face material slots."""

    def __init__(self) -> None:
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.verify()
        self.slots: list[bpy.types.Material] = []

    def slot(self, mat: bpy.types.Material | None) -> int:
        if mat is None:
            return 0
        if mat not in self.slots:
            self.slots.append(mat)
        return self.slots.index(mat)

    def box(self, center: Vector, size: Vector, yaw_rad: float = 0.0, mat=None, side_mat=None) -> None:
        """Axis box (local X = width, Y = depth, Z = height), yawed about +Z.

        ``side_mat`` is a callable(normal_world) -> material for per-face finishes."""
        m = Matrix.Translation(center) @ Matrix.Rotation(yaw_rad, 4, "Z") @ Matrix.Diagonal((*size, 1.0))
        res = bmesh.ops.create_cube(self.bm, size=1.0, matrix=m, calc_uvs=True)
        verts = set(res["verts"])
        faces = [f for f in self.bm.faces if all(v in verts for v in f.verts)]
        for f in faces:
            f.normal_update()
            chosen = side_mat(f.normal.copy()) if side_mat else mat
            f.material_index = self.slot(chosen)

    def polygon(self, pts: list[tuple[float, float, float]], mat, flip: bool = False) -> None:
        verts = [self.bm.verts.new(p) for p in pts]
        if flip:
            verts.reverse()
        face = self.bm.faces.new(verts)
        face.material_index = self.slot(mat)
        face.normal_update()
        for loop in face.loops:
            co = loop.vert.co
            loop[self.uv].uv = (co.x, co.y if abs(face.normal.z) > 0.5 else co.z)

    def to_object(self, name: str, col: str) -> bpy.types.Object:
        mesh = bpy.data.meshes.new(name)
        self.bm.normal_update()
        self.bm.to_mesh(mesh)
        self.bm.free()
        for mat in self.slots:
            mesh.materials.append(mat)
        return new_object(name, mesh, col)


# --------------------------------------------------------------------------- builders

def ceiling_height_fn(room: dict, walls: dict[str, dict]):
    ceiling = room.get("ceiling", {})
    flat = float(ceiling.get("height", 2.6))
    slopes = ceiling.get("slopes", []) if ceiling.get("type") == "sloped" else []
    faces = []
    for s in slopes:
        w = walls[s["wall"]]
        a, b = Vector((*w["start"], 0.0)), Vector((*w["end"], 0.0))
        d = (b - a).normalized()
        n = Vector((-d.y, d.x, 0.0))
        cx, cy = room_centroid(room)
        if (Vector((cx, cy, 0.0)) - a).dot(n) < 0:
            n = -n  # normal pointing into the room
        face_point = a + n * (float(w["thickness"]) / 2.0)
        faces.append((face_point, n, float(s["knee_height"]), math.tan(math.radians(float(s["pitch_deg"])))))

    def height(x: float, y: float) -> float:
        z = flat
        p = Vector((x, y, 0.0))
        for face_point, n, knee, tan_p in faces:
            z = min(z, knee + max(0.0, (p - face_point).dot(n)) * tan_p)
        return z

    breaks_x, breaks_y = [], []
    for face_point, n, knee, tan_p in faces:
        if tan_p <= 1e-6:
            continue
        dist = (flat - knee) / tan_p
        if abs(n.y) < 1e-6:
            breaks_x.append(face_point.x + n.x * dist)
        elif abs(n.x) < 1e-6:
            breaks_y.append(face_point.y + n.y * dist)
    return height, breaks_x, breaks_y, bool(faces)


def room_centroid(room: dict) -> tuple[float, float]:
    xs = [p[0] for p in room["polygon"]]
    ys = [p[1] for p in room["polygon"]]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def build_floor_and_ceiling(room: dict, walls: dict[str, dict]) -> None:
    poly = room["polygon"]
    prefix = "PLACEHOLDER" if room.get("placeholder") else "ARCH"
    col = "Placeholder" if room.get("placeholder") else "Architecture"
    floor_mat = material(room.get("floor_finish", "concrete_bare"),
                         FINISH_RGB.get(room.get("floor_finish"), (0.4, 0.4, 0.4)), 0.7)
    ceil_mat = material(room.get("ceiling_finish", "plaster_smooth"),
                        FINISH_RGB.get(room.get("ceiling_finish"), (0.85, 0.85, 0.85)), 0.9)

    mb = MeshBuilder()
    mb.polygon([(p[0], p[1], 0.0) for p in poly], floor_mat)
    floor = mb.to_object(f"{prefix}_{room['id']}_floor", col)
    floor["room"] = room["id"]
    floor["fixture"] = True

    height, bx, by, sloped = ceiling_height_fn(room, walls)
    mb = MeshBuilder()
    xs = sorted({p[0] for p in poly})
    ys = sorted({p[1] for p in poly})
    if sloped:
        xs = sorted(set(xs) | {x for x in bx if min(xs) < x < max(xs)})
        ys = sorted(set(ys) | {y for y in by if min(ys) < y < max(ys)})
        # extra subdivisions keep non axis-aligned slopes approximately right
        xs = densify(xs, 0.5)
        ys = densify(ys, 0.5)
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
            if not point_in_polygon(cx, cy, poly):
                continue
            quad = [(xs[i], ys[j]), (xs[i + 1], ys[j]), (xs[i + 1], ys[j + 1]), (xs[i], ys[j + 1])]
            mb.polygon([(x, y, height(x, y)) for x, y in quad], ceil_mat, flip=True)
    ceiling = mb.to_object(f"{prefix}_{room['id']}_ceiling", col)
    ceiling["room"] = room["id"]

    # floor collision slab (top at z = 0)
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    mb = MeshBuilder()
    mb.box(Vector(((minx + maxx) / 2, (miny + maxy) / 2, -0.05)), Vector((maxx - minx + 0.3, maxy - miny + 0.3, 0.1)))
    mb.to_object(f"COL_{room['id']}_floor-colonly", "Collision")


def densify(values: list[float], step: float) -> list[float]:
    out: list[float] = []
    for a, b in zip(values, values[1:]):
        n = max(1, int(math.ceil((b - a) / step - 1e-9)))
        out.extend(a + (b - a) * k / n for k in range(n))
    out.append(values[-1])
    return out


def build_wall(w: dict, rooms: list[dict], storey_h: float) -> list[dict]:
    """Builds ARCH_<wall> (visual) and COL_<wall>-colonly; returns door infos for leaves."""
    a, b = Vector((*w["start"], 0.0)), Vector((*w["end"], 0.0))
    length = (b - a).length
    d = (b - a).normalized()
    n_left = Vector((-d.y, d.x, 0.0))
    yaw = math.atan2(d.y, d.x)
    t = float(w["thickness"])
    top = float(w["height"]) if w.get("height") else storey_h
    mid = (a + b) / 2

    def finish_for(side: str) -> str:
        explicit = w.get("finish_" + side)
        if explicit:
            return explicit
        probe = mid + n_left * ((t / 2 + 0.05) * (1 if side == "left" else -1))
        room = room_at(rooms, probe.x, probe.y)
        return room.get("wall_finish_default", "plaster_white") if room else "exterior"

    left_mat = material(finish_for("left"), FINISH_RGB.get(finish_for("left"), (0.7, 0.7, 0.7)))
    right_mat = material(finish_for("right"), FINISH_RGB.get(finish_for("right"), (0.7, 0.7, 0.7)))

    def side_mat(normal: Vector):
        return right_mat if normal.dot(n_left) < -0.5 else left_mat

    pieces: list[tuple[float, float, float, float]] = []  # (s0, s1, z0, z1)
    doors: list[dict] = []
    cursor = 0.0
    for op in sorted(w.get("openings", []), key=lambda o: o["offset"]):
        if op["type"] == "dormer":
            continue  # fixture: dormers are not modelled
        s0, s1 = float(op["offset"]), float(op["offset"]) + float(op["width"])
        sill = float(op.get("sill_height", 0.0))
        head = sill + float(op["height"])
        if s0 > cursor:
            pieces.append((cursor, s0, 0.0, top))
        if sill > 0.0:
            pieces.append((s0, s1, 0.0, sill))
        if head < top:
            pieces.append((s0, s1, head, top))
        cursor = max(cursor, s1)
        if op["type"] in ("door", "sliding_door", "louvered_pair", "doorway"):
            doors.append({"op": op, "s0": s0, "s1": s1, "a": a, "d": d, "yaw": yaw, "t": t, "head": head})
    if cursor < length:
        pieces.append((cursor, length, 0.0, top))

    visual = MeshBuilder()
    coll = MeshBuilder()
    for s0, s1, z0, z1 in pieces:
        c = a + d * ((s0 + s1) / 2)
        c.z = (z0 + z1) / 2
        size = Vector((s1 - s0, t, z1 - z0))
        visual.box(c, size, yaw, side_mat=side_mat)
        coll.box(c, size, yaw)
    obj = visual.to_object(f"ARCH_{w['id']}", "Architecture")
    obj["wall_id"] = w["id"]
    obj["fixture"] = True
    coll.to_object(f"COL_{w['id']}-colonly", "Collision")
    return doors


def build_door_parts(door: dict) -> None:
    op = door["op"]
    a, d, yaw, t = door["a"], door["d"], door["yaw"], door["t"]
    s0, s1 = door["s0"], door["s1"]
    width = s1 - s0
    connects = op.get("connects", [])
    outward = any(c in ("stairwell", "exterior") for c in connects)
    center = a + d * ((s0 + s1) / 2)
    if op["type"] == "door" and outward:
        # closed leaf keeps the player inside the fixture
        leaf_mat = material("door_leaf_" + op.get("leaf", "panel_white"),
                            (0.32, 0.20, 0.11) if "wood" in op.get("leaf", "") else (0.85, 0.85, 0.82), 0.6)
        c = center.copy()
        c.z = door["head"] / 2
        mb = MeshBuilder()
        mb.box(c, Vector((width, 0.04, door["head"])), yaw, mat=leaf_mat)
        leaf = mb.to_object(f"INT_{op['id']}", "Interactive")
        leaf["opening_id"] = op["id"]
        cb = MeshBuilder()
        cb.box(c, Vector((width, 0.06, door["head"])), yaw)
        cb.to_object(f"COL_INT_{op['id']}-colonly", "Collision")
    elif not outward:
        # small threshold strip: exercises the runtime's <= 3 cm step handling
        thr_mat = material("threshold_oak", (0.42, 0.28, 0.15), 0.5)
        c = center.copy()
        c.z = THRESHOLD_HEIGHT / 2
        size = Vector((width, t + 0.04, THRESHOLD_HEIGHT))
        mb = MeshBuilder()
        mb.box(c, size, yaw, mat=thr_mat)
        mb.to_object(f"ARCH_{op['id']}_threshold", "Architecture")
        cb = MeshBuilder()
        cb.box(c, size, yaw)
        cb.to_object(f"COL_ARCH_{op['id']}_threshold-colonly", "Collision")


def build_item(item: dict) -> None:
    w, dpt, h = (float(v) for v in item["dimensions"])
    x, y, z = (float(v) for v in item["position"])
    yaw = math.radians(float(item.get("yaw_deg", 0.0)))
    rgb = ITEM_RGB.get(item["type"], (0.5, 0.5, 0.5))
    mat = material("item_" + item["type"], rgb, 0.6, emission=2.0 if item["type"] == "table_lamp" else 0.0)
    center = Vector((x, y, z + h / 2))
    mb = MeshBuilder()
    mb.box(center, Vector((w, dpt, h)), yaw, mat=mat)
    if item["type"] not in ("rug",):
        # a darker front panel makes the "front faces +Y at yaw 0" convention visible
        front = material("item_front", (0.05, 0.05, 0.05), 0.5)
        local_front = Vector((0.0, dpt / 2 + 0.005, 0.0))
        fc = center + Matrix.Rotation(yaw, 3, "Z") @ local_front
        mb.box(fc, Vector((w * 0.6, 0.01, h * 0.3)), yaw, mat=front)
    category = item.get("category", "prop")
    col = {"furniture": "Furniture", "appliance": "Furniture", "fixture": "Furniture",
           "decor": "Props", "prop": "Props", "light_fixture": "Props"}.get(category, "Props")
    if item.get("interactive"):
        col = "Interactive"
    obj = mb.to_object(item["id"], col)
    obj["spec_id"] = item["id"]
    obj["item_type"] = item["type"]
    obj["room"] = item["room"]
    obj["interactive"] = bool(item.get("interactive", False))
    if category in COLLIDING_CATEGORIES and item["type"] not in NON_COLLIDING_TYPES:
        cb = MeshBuilder()
        cb.box(center, Vector((w, dpt, h)), yaw)
        cb.to_object(f"COL_{item['id']}-colonly", "Collision")


def build_light_fixture(light: dict) -> Vector:
    x, y, z = (float(v) for v in light["position"])
    off = BULB_OFFSET_Z.get(light["type"], 0.0)
    bulb = Vector((x, y, z + off))
    mb = MeshBuilder()
    glow = material("bulb_warm", (1.0, 0.78, 0.5), 0.3, emission=6.0)
    shade = material("shade_fabric", (0.75, 0.62, 0.45), 0.9)
    mb.box(bulb, Vector((0.07, 0.07, 0.09)), mat=glow)
    if off < 0:  # ceiling hung: cord + shade
        mb.box(Vector((x, y, z + off / 2)), Vector((0.012, 0.012, abs(off))), mat=shade)
        mb.box(bulb + Vector((0, 0, 0.04)), Vector((0.30, 0.30, 0.14)), mat=shade)
    obj = mb.to_object(light["id"], "Lighting")
    obj["light_type"] = light["type"]
    obj["room"] = light["room"]
    return bulb


def look_rotation(pos: Vector, target: Vector, roll_deg: float) -> Matrix:
    """Binding camera math (SCHEMA.md): camera -Z -> f, +Y -> u, then roll about local Z."""
    f = (target - pos).normalized()
    r = f.cross(Vector((0.0, 0.0, 1.0))).normalized()
    u = r.cross(f)
    m = Matrix((r, u, -f)).transposed()  # columns = camera X, Y, Z in world space
    return m.to_4x4() @ Matrix.Rotation(math.radians(roll_deg), 4, "Z")


def build_camera(cam: dict, image_size: list[int]) -> None:
    pos, target = Vector(cam["position"]), Vector(cam["look_at"])
    data = bpy.data.cameras.new("CAM_" + cam["ref"])
    data.sensor_fit = "HORIZONTAL"
    data.angle_x = math.radians(float(cam["horizontal_fov_deg"]))
    data.clip_start = 0.03
    data.clip_end = 100.0
    obj = new_object("CAM_" + cam["ref"], data, "Cameras")
    obj.matrix_world = Matrix.Translation(pos) @ look_rotation(pos, target, float(cam.get("roll_deg", 0.0)))
    obj["ref"] = cam["ref"]
    obj["image_size"] = list(image_size)


def manifest_sizes() -> dict[str, list[int]]:
    path = REPO / "references" / "manifest.json"
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return {r["id"]: [int(r["width"]), int(r["height"])] for r in data.get("references", [])
            if "width" in r and "height" in r}


# --------------------------------------------------------------------------- main

def main() -> None:
    args = parse_args()
    spec_path = repo_path(args.spec)
    out_dir = repo_path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    spec_bytes = spec_path.read_bytes()
    spec = json.loads(spec_bytes)
    if spec.get("schema_version") != 2:
        raise SystemExit(f"expected schema_version 2 in {spec_path}")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = DEFAULT_IMAGE_SIZE
    scene["three_bedroom_fixture"] = True
    scene["generator"] = GENERATOR
    for name in ("Architecture", "Placeholder", "Furniture", "Props", "Lighting", "Collision",
                 "Cameras", "Interactive", "Markers"):
        collection(name)

    rooms = spec["rooms"]
    walls = {w["id"]: w for w in spec["walls"]}
    storey_h = float(spec.get("storey", {}).get("default_ceiling_height", 2.6))

    for room in rooms:
        build_floor_and_ceiling(room, walls)
    for w in spec["walls"]:
        for door in build_wall(w, rooms, storey_h):
            build_door_parts(door)
    for item in spec.get("items", []):
        build_item(item)
    for light in spec.get("lights", []):
        build_light_fixture(light)

    sizes = manifest_sizes()
    meta_cams = []
    for cam in spec.get("cameras", []):
        size = sizes.get(cam["ref"], DEFAULT_IMAGE_SIZE)
        build_camera(cam, size)
        meta_cams.append({
            "ref": cam["ref"], "node": "CAM_" + cam["ref"], "room": cam.get("room", ""),
            "position": to_godot(cam["position"]), "look_at": to_godot(cam["look_at"]),
            "horizontal_fov_deg": float(cam["horizontal_fov_deg"]),
            "roll_deg": float(cam.get("roll_deg", 0.0)), "image_size": size,
        })

    spawn = spec["spawn"]
    marker = new_object("SPAWN_player", None, "Markers")
    marker.empty_display_type = "ARROWS"
    marker.location = Vector(spawn["position"])
    marker.rotation_euler = (0.0, 0.0, math.radians(float(spawn.get("yaw_deg", 0.0))))

    glb_path = out_dir / f"{args.name}.glb"
    gltf_kwargs = dict(filepath=str(glb_path), export_format="GLB", use_selection=False,
                       export_cameras=True, export_lights=False, export_extras=True,
                       export_apply=True, export_yup=True)
    supported = {p.identifier for p in bpy.ops.export_scene.gltf.get_rna_type().properties}
    dropped = [k for k in gltf_kwargs if k not in supported]
    if dropped:
        print("[fixture] glTF exporter lacks options:", dropped)
    bpy.ops.export_scene.gltf(**{k: v for k, v in gltf_kwargs.items() if k in supported})

    meta = {
        "schema": 1,
        "generator": GENERATOR,
        "fixture": True,
        "spec": rel_to_repo(spec_path),
        "spec_sha256": hashlib.sha256(spec_bytes).hexdigest(),
        "blender_version": "%d.%d.%d" % tuple(bpy.app.version),
        "coordinate_note": COORD_NOTE,
        "cameras": meta_cams,
        "spawn": {"room": spawn["room"], "position": to_godot(spawn["position"]),
                  "yaw_rad": round(math.radians(float(spawn.get("yaw_deg", 0.0))), 6)},
        "rooms": [{"id": r["id"], "name": r.get("name", r["id"]), "placeholder": bool(r.get("placeholder", False)),
                   "polygon_xz": [[round(float(p[0]), 5), round(-float(p[1]) + 0.0, 5)] for p in r["polygon"]],
                   "floor_y": 0.0} for r in rooms],
        "lights": [{"id": l["id"], "room": l["room"], "type": l["type"], "position": to_godot(l["position"])}
                   for l in spec.get("lights", [])],
        "interactive": [{"id": i["id"], "node": i["id"], "type": i["type"]}
                        for i in spec.get("items", []) if i.get("interactive")],
    }
    meta_path = out_dir / f"{args.name}_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    print(f"[fixture] wrote {rel_to_repo(glb_path)} ({glb_path.stat().st_size} bytes)")
    print(f"[fixture] wrote {rel_to_repo(meta_path)}")


if __name__ == "__main__":
    main()

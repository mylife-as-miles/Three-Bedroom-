class_name ApartmentMeta
extends RefCounted
## Typed view of apartment_meta.json (RUNTIME CONTRACT, schema 1), written by
## scripts/blender/build_apartment.py (or the test fixture generator). All positions are
## already in Godot space: godot (x, y, z) = blender (x, z, -y).

const SUPPORTED_SCHEMA := 1
const DEFAULT_IMAGE_SIZE := Vector2i(960, 540)


class CameraView:
	extends RefCounted
	var ref: String = ""
	var node: String = ""
	var room: String = ""
	var position: Vector3 = Vector3.ZERO
	var look_at: Vector3 = Vector3.FORWARD
	var horizontal_fov_deg: float = 75.0
	var roll_deg: float = 0.0
	var image_size: Vector2i = DEFAULT_IMAGE_SIZE

	func view_transform() -> Transform3D:
		return Coords.view_transform(position, look_at, roll_deg)


class Room:
	extends RefCounted
	var id: String = ""
	var name: String = ""
	var placeholder: bool = false
	var polygon_xz: PackedVector2Array = PackedVector2Array()
	var floor_y: float = 0.0

	func contains(p: Vector3) -> bool:
		return Coords.point_in_polygon(Vector2(p.x, p.z), polygon_xz)

	func centroid() -> Vector3:
		var c := Vector2.ZERO
		for v in polygon_xz:
			c += v
		if polygon_xz.size() > 0:
			c /= float(polygon_xz.size())
		return Vector3(c.x, floor_y, c.y)


class LightInfo:
	extends RefCounted
	var id: String = ""
	var room: String = ""
	var type: String = ""
	var position: Vector3 = Vector3.ZERO


class InteractiveInfo:
	extends RefCounted
	var id: String = ""
	var node: String = ""
	var type: String = ""


var source_path: String = ""
var raw: Dictionary = {}
var errors: PackedStringArray = PackedStringArray()
var is_fixture: bool = false
var cameras: Array[CameraView] = []
var rooms: Array[Room] = []
var lights: Array[LightInfo] = []
var interactive: Array[InteractiveInfo] = []
var spawn_room: String = ""
var spawn_position: Vector3 = Vector3.ZERO
var spawn_yaw_rad: float = 0.0


static func load_from(path: String) -> ApartmentMeta:
	var meta := ApartmentMeta.new()
	meta.source_path = path
	if not FileAccess.file_exists(path):
		meta.errors.append("meta file not found: %s" % path)
		return meta
	var text := FileAccess.get_file_as_string(path)
	var parsed: Variant = JSON.parse_string(text)
	if not parsed is Dictionary:
		meta.errors.append("meta file is not a JSON object: %s" % path)
		return meta
	meta._parse(parsed as Dictionary)
	return meta


func is_valid() -> bool:
	return errors.is_empty()


func find_camera(ref: String) -> CameraView:
	for cam in cameras:
		if cam.ref == ref:
			return cam
	return null


func find_room(id: String) -> Room:
	for room in rooms:
		if room.id == id:
			return room
	return null


## Room containing a Godot-space position (XZ test), or null.
func room_at(p: Vector3) -> Room:
	for room in rooms:
		if room.contains(p):
			return room
	return null


func view_refs() -> PackedStringArray:
	var refs := PackedStringArray()
	for cam in cameras:
		refs.append(cam.ref)
	return refs


func _parse(d: Dictionary) -> void:
	raw = d
	var schema := int(d.get("schema", -1))
	if schema != SUPPORTED_SCHEMA:
		errors.append("unsupported meta schema %d (expected %d)" % [schema, SUPPORTED_SCHEMA])
		return
	is_fixture = bool(d.get("fixture", false))
	for item: Variant in _array(d, "cameras"):
		if item is Dictionary:
			cameras.append(_parse_camera(item as Dictionary))
	for item: Variant in _array(d, "rooms"):
		if item is Dictionary:
			rooms.append(_parse_room(item as Dictionary))
	for item: Variant in _array(d, "lights"):
		if item is Dictionary:
			var li := item as Dictionary
			var info := LightInfo.new()
			info.id = str(li.get("id", ""))
			info.room = str(li.get("room", ""))
			info.type = str(li.get("type", ""))
			info.position = Coords.to_vec3(li.get("position"))
			lights.append(info)
	for item: Variant in _array(d, "interactive"):
		if item is Dictionary:
			var ii := item as Dictionary
			var inter := InteractiveInfo.new()
			inter.id = str(ii.get("id", ""))
			inter.node = str(ii.get("node", inter.id))
			inter.type = str(ii.get("type", ""))
			interactive.append(inter)
	var spawn: Variant = d.get("spawn")
	if spawn is Dictionary:
		var sd := spawn as Dictionary
		spawn_room = str(sd.get("room", ""))
		spawn_position = Coords.to_vec3(sd.get("position"))
		spawn_yaw_rad = float(sd.get("yaw_rad", 0.0))
	else:
		errors.append("meta has no spawn")
	if rooms.is_empty():
		errors.append("meta has no rooms")


func _parse_camera(c: Dictionary) -> CameraView:
	var cam := CameraView.new()
	cam.ref = str(c.get("ref", ""))
	cam.node = str(c.get("node", "CAM_" + cam.ref))
	cam.room = str(c.get("room", ""))
	cam.position = Coords.to_vec3(c.get("position"))
	cam.look_at = Coords.to_vec3(c.get("look_at"), cam.position + Vector3.FORWARD)
	cam.horizontal_fov_deg = clampf(float(c.get("horizontal_fov_deg", 75.0)), 1.0, 170.0)
	cam.roll_deg = float(c.get("roll_deg", 0.0))
	var size: Variant = c.get("image_size")
	if size is Array and (size as Array).size() >= 2:
		var sa := size as Array
		cam.image_size = Vector2i(maxi(int(sa[0]), 16), maxi(int(sa[1]), 16))
	return cam


func _parse_room(r: Dictionary) -> Room:
	var room := Room.new()
	room.id = str(r.get("id", ""))
	room.name = str(r.get("name", room.id))
	room.placeholder = bool(r.get("placeholder", false))
	room.floor_y = float(r.get("floor_y", 0.0))
	var poly: Variant = r.get("polygon_xz")
	if poly is Array:
		for pt: Variant in poly as Array:
			if pt is Array and (pt as Array).size() >= 2:
				var pa := pt as Array
				room.polygon_xz.append(Vector2(float(pa[0]), float(pa[1])))
	if room.polygon_xz.size() < 3:
		errors.append("room '%s' has no usable polygon_xz" % room.id)
	return room


static func _array(d: Dictionary, key: String) -> Array:
	var v: Variant = d.get(key)
	return v as Array if v is Array else []

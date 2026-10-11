class_name ApartmentWorld
extends Node3D
## Loads the exported apartment at runtime (RUNTIME CONTRACT):
##   <glb_path>                    glTF scene (Y-up, cameras, extras, '*-colonly' proxies, no lights)
##   <glb basename>_meta.json      cameras, spawn, rooms, lights, interactive objects
## spawns the player, builds the runtime lights + environment, and offers the view/pose API
## used by the test bridge (binding camera math: KEEP_WIDTH, fov = hfov, look_at up +Y, roll).

signal world_ready
signal load_failed(message: String)

const PLAYER_SCENE: PackedScene = preload("res://scenes/player/player.tscn")
const RESUME_GUARD_MS := 300

var glb_path: String = RunConfig.DEFAULT_GLB
var meta_path: String = ""
var lighting_mode: StringName = RunConfig.LIGHTING_NIGHT

var meta: ApartmentMeta = null
var player: PlayerController = null
var apartment: Node3D = null
var is_ready: bool = false
var errors: PackedStringArray = PackedStringArray()
var interactive_nodes: Dictionary = {}

var _paused: bool = false
var _paused_at_ms: int = 0
var _had_capture: bool = false
var _view_ref: String = ""

@onready var _apartment_root: Node3D = $Apartment
@onready var _lighting: LightingRig = $LightingRig
@onready var _environment: WorldEnvironment = $WorldEnvironment
@onready var _view_camera: Camera3D = $ViewCamera
@onready var _pause_overlay: Control = $UI/PauseOverlay
@onready var _status: Label = $UI/Status


func _ready() -> void:
	add_to_group(&"world")
	_pause_overlay.visible = false
	_status.visible = false
	_view_camera.keep_aspect = Camera3D.KEEP_WIDTH
	if meta_path.is_empty():
		meta_path = RunConfig.meta_path_for(glb_path)
	_load()


func _load() -> void:
	meta = ApartmentMeta.load_from(meta_path)
	if not meta.is_valid():
		_fail("apartment meta invalid (%s): %s" % [meta_path, "; ".join(meta.errors)])
		return
	apartment = _instantiate_apartment(glb_path)
	if apartment == null:
		_fail("could not load apartment scene: %s" % glb_path)
		return
	apartment.name = "ApartmentScene"
	_apartment_root.add_child(apartment)
	_prepare_imported(apartment)
	_environment.environment = _lighting.build(meta, lighting_mode)

	player = PLAYER_SCENE.instantiate() as PlayerController
	add_child(player)
	player.teleport(meta.spawn_position, meta.spawn_yaw_rad)
	player.camera.make_current()
	player.interacted.connect(_on_player_interacted)
	is_ready = true
	print("World: loaded %s (%s%s), %d rooms, %d lights, %d views, lighting=%s" % [
		glb_path, meta_path, " [TEST FIXTURE]" if meta.is_fixture else "",
		meta.rooms.size(), _lighting.practicals.size(), meta.cameras.size(), lighting_mode])
	world_ready.emit()


func _fail(message: String) -> void:
	errors.append(message)
	push_error("World: " + message)
	_status.text = "THREE BEDROOM: " + message
	_status.visible = true
	load_failed.emit(message)


func _instantiate_apartment(path: String) -> Node3D:
	if ResourceLoader.exists(path):
		var packed := load(path) as PackedScene
		if packed != null:
			return packed.instantiate() as Node3D
	elif FileAccess.file_exists(path) and path.get_extension().to_lower() in ["glb", "gltf"]:
		# Not imported (e.g. dropped in at runtime): parse the glTF directly.
		var doc := GLTFDocument.new()
		var state := GLTFState.new()
		if doc.append_from_file(path, state) == OK:
			var root := doc.generate_scene(state) as Node3D
			if root != null:
				_convert_colonly(root)
			return root
	return null


## Runtime equivalent of the importer's '-colonly' handling (only for un-imported glTF).
func _convert_colonly(root: Node) -> void:
	for node in root.find_children("*-colonly", "MeshInstance3D", true, false):
		var mesh_instance := node as MeshInstance3D
		var body := StaticBody3D.new()
		body.name = mesh_instance.name.trim_suffix("-colonly")
		var shape := CollisionShape3D.new()
		shape.shape = mesh_instance.mesh.create_trimesh_shape()
		body.add_child(shape)
		body.transform = mesh_instance.transform
		mesh_instance.get_parent().add_child(body)
		mesh_instance.queue_free()


func _prepare_imported(root: Node) -> void:
	var stray_lights := 0
	for node in root.find_children("*", "Node3D", true, false):
		if node is Light3D:
			stray_lights += 1
			node.queue_free()
		elif node is Camera3D:
			(node as Camera3D).current = false
		elif node is GeometryInstance3D:
			# Single-sided ceilings/roofs must still occlude the moon.
			(node as GeometryInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_DOUBLE_SIDED
	if stray_lights > 0:
		push_warning("World: removed %d punctual light(s) from the GLB (contract: lights come from meta)" % stray_lights)

	var ids: Dictionary = {}
	for info in meta.interactive:
		ids[info.id] = info
		var target := root.find_child(info.node, true, false) as Node3D
		if target == null:
			push_warning("World: interactive node '%s' not found in the GLB" % info.node)
			continue
		target.add_to_group(&"interactive")
		target.set_meta(&"interactive_id", info.id)
		target.set_meta(&"interactive_type", info.type)
		interactive_nodes[info.id] = target
	# Collision bodies generated from '<name>-colonly' proxies (fixture uses 'COL_<name>').
	for node in root.find_children("*", "CollisionObject3D", true, false):
		var base := String(node.name).trim_prefix("COL_")
		if ids.has(base):
			node.set_meta(&"interactive_id", base)


func _process(_delta: float) -> void:
	if not is_ready:
		return
	var captured := Input.mouse_mode == Input.MOUSE_MODE_CAPTURED
	if captured:
		_had_capture = true
	elif _had_capture and not _paused:
		# Browser released the pointer lock (Esc / focus loss): pause.
		_had_capture = false
		set_paused(true)


func _unhandled_input(event: InputEvent) -> void:
	if not is_ready:
		return
	if event.is_action_pressed(&"pause"):
		if not _paused:
			set_paused(true)
		elif Time.get_ticks_msec() - _paused_at_ms > RESUME_GUARD_MS:
			set_paused(false)
		get_viewport().set_input_as_handled()
	elif _paused:
		var mb := event as InputEventMouseButton
		if mb != null and mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT:
			set_paused(false)
			player.capture_mouse()
			get_viewport().set_input_as_handled()


func set_paused(paused: bool) -> void:
	_paused = paused
	_pause_overlay.visible = paused
	if paused:
		_paused_at_ms = Time.get_ticks_msec()
		_had_capture = false
		player.release_mouse()
	_update_player_input()


func is_paused() -> bool:
	return _paused


func _update_player_input() -> void:
	if player != null:
		player.input_enabled = not _paused and _view_ref.is_empty()
		player.set_view_mode(not _view_ref.is_empty())


# ---------------------------------------------------------------- view / pose API (test bridge)

## Switches rendering to a capture camera placed per meta camera `ref` using the binding
## math. Nothing in the world is hidden; the player (bodiless) keeps simulating but ignores input.
func set_view(ref: String) -> bool:
	if meta == null:
		return false
	var cam := meta.find_camera(ref)
	if cam == null:
		push_warning("World: unknown view '%s'" % ref)
		return false
	_view_camera.keep_aspect = Camera3D.KEEP_WIDTH
	_view_camera.fov = cam.horizontal_fov_deg
	_view_camera.near = 0.03
	_view_camera.far = 200.0
	_view_camera.global_transform = cam.view_transform()
	_view_camera.make_current()
	_view_ref = cam.ref
	_update_player_input()
	return true


func clear_view() -> void:
	_view_ref = ""
	if player != null:
		player.camera.make_current()
	_update_player_input()


func current_view() -> String:
	return _view_ref


## Player pose from Blender coordinates (feet position, yaw/pitch in degrees).
func set_player_pose_blender(pos_blender: Vector3, yaw_deg: float, pitch_deg: float) -> void:
	if player == null:
		return
	player.teleport(Coords.blender_to_godot(pos_blender), deg_to_rad(yaw_deg), deg_to_rad(pitch_deg))


func room_id_at(p: Vector3) -> String:
	if meta == null:
		return ""
	var room := meta.room_at(p)
	return room.id if room != null else ""


func player_state() -> Dictionary:
	if player == null:
		return {}
	var pos := player.global_position
	var vel := player.velocity
	return {
		"pos_godot": Coords.to_array(pos),
		"pos_blender": Coords.to_array(Coords.godot_to_blender(pos)),
		"vel_blender": Coords.to_array(Coords.godot_to_blender(vel)),
		"speed_h": snappedf(player.horizontal_speed(), 0.0001),
		"yaw_deg": snappedf(fposmod(rad_to_deg(player.get_yaw()), 360.0), 0.001),
		"pitch_deg": snappedf(rad_to_deg(player.get_pitch()), 0.001),
		"room": room_id_at(pos),
		"on_floor": player.is_on_floor(),
		"sprinting": player.is_sprinting(),
		"input_enabled": player.input_enabled,
	}


## Ray query in Blender coordinates against the static world (player excluded).
func raycast_blender(origin_b: Vector3, dir_b: Vector3, max_dist: float) -> Dictionary:
	var from := Coords.blender_to_godot(origin_b)
	var dir := Coords.blender_to_godot(dir_b).normalized()
	var query := PhysicsRayQueryParameters3D.create(from, from + dir * max_dist)
	if player != null:
		query.exclude = [player.get_rid()]
	var hit := get_world_3d().direct_space_state.intersect_ray(query)
	if hit.is_empty():
		return {"hit": false}
	var point: Vector3 = hit["position"]
	var normal: Vector3 = hit["normal"]
	var collider := hit["collider"] as Node
	return {
		"hit": true,
		"distance": snappedf(from.distance_to(point), 0.0001),
		"point_blender": Coords.to_array(Coords.godot_to_blender(point)),
		"normal_blender": Coords.to_array(Coords.godot_to_blender(normal)),
		"collider": String(collider.name) if collider != null else "",
	}


## Compares GLB camera nodes with the meta-derived binding transforms (exporter cross-check).
func check_cameras() -> Array:
	var out: Array = []
	if meta == null or apartment == null:
		return out
	for cam in meta.cameras:
		var entry := {"ref": cam.ref, "node": cam.node, "found": false}
		var node := apartment.find_child(cam.node, true, false) as Node3D
		if node != null:
			var expected := cam.view_transform()
			var actual := node.global_transform
			entry["found"] = true
			entry["position_error_m"] = snappedf(actual.origin.distance_to(expected.origin), 0.00001)
			entry["forward_error_deg"] = snappedf(rad_to_deg((-actual.basis.z).angle_to(-expected.basis.z)), 0.001)
			entry["up_error_deg"] = snappedf(rad_to_deg(actual.basis.y.angle_to(expected.basis.y)), 0.001)
		out.append(entry)
	return out


func _on_player_interacted(interactive_id: String, target: Node) -> void:
	if not interactive_id.is_empty():
		print("World: interact -> %s (%s)" % [interactive_id, target.name if target != null else "?"])

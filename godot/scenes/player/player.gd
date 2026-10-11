class_name PlayerController
extends CharacterBody3D
## First-person player: capsule r 0.22 m x h 1.68 m, eyes at 1.58 m (origin = feet).
##
## Walk 1.35 m/s, contextual sprint 2.3 m/s (forward-ish movement on the floor only),
## exponential accel/decel, gravity, floor snapping, explicit step-up for low obstacles
## (door thresholds <= 3 cm), subtle optional head bob. Mouse look only while the pointer is
## captured (captured by a click: browsers require a user gesture; Esc releases it).

signal interacted(interactive_id: String, target: Node)
signal inspect_requested(interactive_id: String, target: Node)
signal flashlight_toggled(on: bool)
signal phone_toggled

const RADIUS := 0.22
const HEIGHT := 1.68
const EYE_HEIGHT := 1.58
const WALK_SPEED := 1.35
const SPRINT_SPEED := 2.3
## Exponential approach rates (1/s): ~0.25 s to reach walking speed, ~0.2 s to stop.
const ACCEL_RATE := 9.0
const DECEL_RATE := 12.0
const AIR_CONTROL := 0.2
const GRAVITY := 9.81
const MAX_FALL_SPEED := 20.0
const MAX_STEP_HEIGHT := 0.035
const PITCH_LIMIT_DEG := 85.0
const SPRINT_MIN_FORWARD := 0.55
const BOB_STRIDE := 1.25  # metres travelled per full bob cycle (two steps)
const BOB_AMPLITUDE := Vector2(0.006, 0.011)  # lateral, vertical (m)

var input_enabled: bool = true
var look_enabled: bool = true

var _yaw: float = 0.0
var _pitch: float = 0.0
var _sprint_latched: bool = false
var _sprinting: bool = false
var _bob_phase: float = 0.0
var _bob_weight: float = 0.0
var _view_mode: bool = false
var _flashlight_was_on: bool = false

@onready var head: Node3D = $Head
@onready var camera: Camera3D = $Head/Camera3D
@onready var flashlight: SpotLight3D = $Head/Camera3D/Flashlight
@onready var interact_ray: RayCast3D = $Head/Camera3D/InteractRay


func _ready() -> void:
	GameSettings.ensure_loaded()
	_yaw = rotation.y
	interact_ray.add_exception(self)
	flashlight.visible = false


## Teleport (Godot space). Clears velocity and smoothing state.
func teleport(pos: Vector3, yaw_rad: float, pitch_rad: float = 0.0) -> void:
	velocity = Vector3.ZERO
	global_position = pos
	set_look(yaw_rad, pitch_rad)
	_sprint_latched = false
	_bob_weight = 0.0
	head.position = Vector3(0.0, EYE_HEIGHT, 0.0)
	force_update_transform()
	reset_physics_interpolation()


func set_look(yaw_rad: float, pitch_rad: float) -> void:
	_yaw = wrapf(yaw_rad, -PI, PI)
	_pitch = clampf(pitch_rad, -deg_to_rad(PITCH_LIMIT_DEG), deg_to_rad(PITCH_LIMIT_DEG))
	rotation = Vector3(0.0, _yaw, 0.0)
	head.rotation = Vector3(_pitch, 0.0, 0.0)


## While a capture view is active the player body must not show up in the frame: hide the
## player's own light (the player has no visible body mesh) and remember the flashlight state.
func set_view_mode(active: bool) -> void:
	if active == _view_mode:
		return
	_view_mode = active
	if active:
		_flashlight_was_on = flashlight.visible
		flashlight.visible = false
	else:
		flashlight.visible = _flashlight_was_on


func get_yaw() -> float:
	return _yaw


func get_pitch() -> float:
	return _pitch


func is_sprinting() -> bool:
	return _sprinting


func horizontal_speed() -> float:
	return Vector2(velocity.x, velocity.z).length()


func capture_mouse() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func release_mouse() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE


func _unhandled_input(event: InputEvent) -> void:
	if not input_enabled:
		return
	var mouse_button := event as InputEventMouseButton
	if mouse_button != null and mouse_button.pressed and mouse_button.button_index == MOUSE_BUTTON_LEFT:
		if Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
			# Pointer lock must be requested from a user gesture on the web.
			capture_mouse()
			get_viewport().set_input_as_handled()
			return
	var motion := event as InputEventMouseMotion
	if motion != null:
		if look_enabled and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
			var sens := deg_to_rad(GameSettings.mouse_sensitivity)
			var dy := motion.screen_relative.y * (-1.0 if GameSettings.invert_y else 1.0)
			set_look(_yaw - motion.screen_relative.x * sens, _pitch - dy * sens)
		return
	if event.is_action_pressed(&"sprint") and event is InputEventJoypadButton:
		_sprint_latched = true  # L3 is a click: latch until the stick is released
	elif event.is_action_pressed(&"interact"):
		_emit_target(true)
	elif event.is_action_pressed(&"inspect_action") and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		_emit_target(false)
	elif event.is_action_pressed(&"flashlight"):
		flashlight.visible = not flashlight.visible
		flashlight_toggled.emit(flashlight.visible)
	elif event.is_action_pressed(&"phone"):
		phone_toggled.emit()


func _process(delta: float) -> void:
	if not (input_enabled and look_enabled):
		return
	var stick := Input.get_vector(&"look_left", &"look_right", &"look_up", &"look_down")
	if stick != Vector2.ZERO:
		# Quadratic response keeps fine aiming precise near the centre.
		var curved := stick * stick.length()
		var speed := deg_to_rad(GameSettings.gamepad_look_speed) * delta
		var dy := curved.y * (-1.0 if GameSettings.invert_y else 1.0)
		set_look(_yaw - curved.x * speed, _pitch - dy * speed)


func _physics_process(delta: float) -> void:
	var move := Vector2.ZERO
	if input_enabled:
		move = Input.get_vector(&"move_left", &"move_right", &"move_forward", &"move_back")
	var on_floor := is_on_floor()

	if move.length() < 0.2:
		_sprint_latched = false
	_sprinting = on_floor and -move.y >= SPRINT_MIN_FORWARD \
		and (_sprint_latched or (input_enabled and Input.is_action_pressed(&"sprint")))

	var wish := global_transform.basis * Vector3(move.x, 0.0, move.y)
	wish.y = 0.0
	wish = wish.normalized() * minf(move.length(), 1.0)
	var target := wish * (SPRINT_SPEED if _sprinting else WALK_SPEED)

	var horizontal := Vector3(velocity.x, 0.0, velocity.z)
	var rate := ACCEL_RATE if target.length_squared() >= horizontal.length_squared() else DECEL_RATE
	if not on_floor:
		rate *= AIR_CONTROL
	horizontal = horizontal.lerp(target, 1.0 - exp(-rate * delta))
	if target == Vector3.ZERO and horizontal.length() < 0.02:
		horizontal = Vector3.ZERO
	velocity.x = horizontal.x
	velocity.z = horizontal.z
	if not on_floor:
		velocity.y = maxf(velocity.y - GRAVITY * delta, -MAX_FALL_SPEED)

	if on_floor and _try_step_up(horizontal * delta):
		var keep := velocity
		velocity = Vector3.ZERO
		move_and_slide()  # refresh floor contact / snapping at the new height
		velocity = Vector3(keep.x, 0.0, keep.z)
	else:
		move_and_slide()
	_update_head_bob(delta)


## Climbs a low obstacle (<= MAX_STEP_HEIGHT) that blocks this frame's horizontal motion:
## lift, advance, then settle onto the step top. Only used when the blocking contact is low
## and wall-like (a capsule already rides over small edges that read as walkable slopes).
func _try_step_up(motion: Vector3) -> bool:
	if motion.length_squared() < 1e-8:
		return false
	var rid := get_rid()
	var params := PhysicsTestMotionParameters3D.new()
	var result := PhysicsTestMotionResult3D.new()
	params.margin = safe_margin
	params.from = global_transform
	params.motion = motion
	if not PhysicsServer3D.body_test_motion(rid, params, result):
		return false
	var contact_height := result.get_collision_point().y - global_position.y
	if contact_height > MAX_STEP_HEIGHT or result.get_collision_normal().angle_to(up_direction) <= floor_max_angle:
		return false
	var lift := up_direction * (MAX_STEP_HEIGHT + 0.005)
	params.motion = lift
	if PhysicsServer3D.body_test_motion(rid, params, result):
		return false
	var raised := global_transform.translated(lift)
	params.from = raised
	params.motion = motion
	if PhysicsServer3D.body_test_motion(rid, params, result):
		return false
	var advanced := raised.translated(motion)
	params.from = advanced
	params.motion = -lift
	if not PhysicsServer3D.body_test_motion(rid, params, result):
		return false  # nothing to stand on: not a step
	if result.get_collision_normal().angle_to(up_direction) > floor_max_angle:
		return false
	global_transform = advanced.translated(result.get_travel())
	return true


func _update_head_bob(delta: float) -> void:
	var speed := horizontal_speed()
	var active := GameSettings.head_bob and is_on_floor() and speed > 0.2
	_bob_weight = move_toward(_bob_weight, 1.0 if active else 0.0, delta * 4.0)
	if active:
		_bob_phase = fmod(_bob_phase + speed * delta / BOB_STRIDE * TAU, TAU)
	var offset := Vector3(sin(_bob_phase) * BOB_AMPLITUDE.x, -absf(sin(_bob_phase)) * BOB_AMPLITUDE.y * 2.0 + BOB_AMPLITUDE.y, 0.0)
	head.position = Vector3(0.0, EYE_HEIGHT, 0.0) + offset * _bob_weight


func _emit_target(is_interact: bool) -> void:
	interact_ray.force_raycast_update()
	var target: Node = interact_ray.get_collider() as Node if interact_ray.is_colliding() else null
	var id := ""
	var node := target
	while node != null:
		if node.has_meta(&"interactive_id"):
			id = str(node.get_meta(&"interactive_id"))
			break
		node = node.get_parent()
	if is_interact:
		interacted.emit(id, target)
	else:
		inspect_requested.emit(id, target)

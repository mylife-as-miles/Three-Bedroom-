extends Node
## Test bridge (autoload "TestBridge"). ONLY active with ?test=1 on the web, or with
## `-- --test` / `-- --selftest` on desktop; otherwise it disables itself in _ready().
##
## Web: installs window.TB (all positions/angles for poses are BLENDER coordinates):
##   TB.ready                      bool, true once the world is loaded and a few frames drew
##   TB.getState()                 JSON string {ready, frames, process_frames, fps, player:{pos_godot,
##                                 pos_blender, vel_blender, speed_h, yaw_deg, pitch_deg, room, ...},
##                                 view, view_frames, paused, viewport, world:{...}}
##   TB.setView(ref) -> bool       capture camera per meta camera (KEEP_WIDTH, fov = hfov,
##                                 look_at up +Y, roll); ?view=REF applies it on load
##   TB.clearView()                back to the player camera
##   TB.setPose(x, y, z, yaw_deg, pitch_deg) -> bool    player feet position + look
##   TB.listViews() -> [ref, ...]
##   TB.getMeta()                  JSON string of apartment_meta.json
##   TB.raycast(ox,oy,oz, dx,dy,dz, maxDist) -> {hit, distance, point_blender, normal_blender, collider}
##   TB.checkCameras() -> [{ref, node, found, position_error_m, forward_error_deg, up_error_deg}]
## JS calls are synchronous: the JS wrapper invokes one Godot callback which stores the
## JSON-encoded result in TB._ret (independent of callback return-value support).
##
## Desktop: prints "[TB] ready {state}"; `--selftest` additionally walks forward for 2 s in
## engine time, validates the input map and quits with exit code 0 (pass) / 1 (fail).

const READY_AFTER_FRAMES := 5
const SELFTEST_WALK_FRAMES := 120
const SELFTEST_SETTLE_FRAMES := 30
const REQUIRED_ACTIONS: PackedStringArray = [
	"move_forward", "move_back", "move_left", "move_right", "look_left", "look_right", "look_up",
	"look_down", "sprint", "interact", "inspect_action", "flashlight", "phone", "pause",
]
const JS_BOOTSTRAP := """
(function () {
	var tb = window.TB || {};
	tb.ready = false;
	tb.version = 1;
	tb._ret = null;
	tb._call = function (name, args) {
		if (typeof tb._invoke !== 'function') { throw new Error('TB: Godot callback not bound'); }
		tb._ret = null;
		tb._invoke(String(name), JSON.stringify(args || []));
		return tb._ret;
	};
	var parsed = function (name, args, fallback) {
		var r = tb._call(name, args);
		return (r === null || r === undefined) ? fallback : JSON.parse(r);
	};
	tb.getState = function () { return tb._call('getState', []); };
	tb.getMeta = function () { return tb._call('getMeta', []); };
	tb.listViews = function () { return parsed('listViews', [], []); };
	tb.setView = function (ref) { return parsed('setView', [String(ref)], false); };
	tb.clearView = function () { return parsed('clearView', [], false); };
	tb.setPose = function (x, y, z, yaw, pitch) {
		return parsed('setPose', [+x, +y, +z, +(yaw || 0), +(pitch || 0)], false);
	};
	tb.raycast = function (ox, oy, oz, dx, dy, dz, maxDist) {
		return parsed('raycast', [+ox, +oy, +oz, +dx, +dy, +dz, +(maxDist || 10)], null);
	};
	tb.checkCameras = function () { return parsed('checkCameras', [], []); };
	window.TB = tb;
	return true;
})();
"""

var active: bool = false

var _world: ApartmentWorld = null
var _tb: JavaScriptObject = null
var _invoke_cb: JavaScriptObject = null
var _ready_frame: int = -1
var _reported_ready: bool = false
var _failed_reported: bool = false
var _view_frame: int = -1
var _selftest_frame: int = -1
var _selftest_start: Vector3 = Vector3.ZERO
var _selftest_yaw: float = 0.0


func _ready() -> void:
	active = RunConfig.test_mode()
	if not active:
		set_process(false)
		set_physics_process(false)
		return
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_physics_process(false)
	if OS.has_feature("web"):
		_install_js()
	print("[TB] test bridge active (web=%s)" % OS.has_feature("web"))


func _install_js() -> void:
	JavaScriptBridge.eval(JS_BOOTSTRAP, true)
	_tb = JavaScriptBridge.get_interface("TB")
	_invoke_cb = JavaScriptBridge.create_callback(_on_js_invoke)
	_tb.set("_invoke", _invoke_cb)


func _process(_delta: float) -> void:
	if _world == null or not is_instance_valid(_world):
		_world = get_tree().get_first_node_in_group(&"world") as ApartmentWorld
		if _world == null:
			return
	if not _world.is_ready:
		if not _world.errors.is_empty() and not _failed_reported:
			_failed_reported = true
			print("[TB] world failed: %s" % JSON.stringify(_world.errors))
			if RunConfig.selftest():
				_finish_selftest(false, {"reason": "world failed", "errors": _world.errors})
		return
	if _ready_frame < 0:
		_ready_frame = Engine.get_process_frames()
		var ref := RunConfig.view_ref()
		if not ref.is_empty():
			_set_view(ref)
	if not _reported_ready and Engine.get_process_frames() - _ready_frame >= READY_AFTER_FRAMES:
		_reported_ready = true
		if _tb != null:
			_tb.set("ready", true)
		print("[TB] ready " + JSON.stringify(_state()))
		if RunConfig.selftest():
			_begin_selftest()


func _on_js_invoke(args: Array) -> void:
	var method := str(args[0]) if args.size() > 0 else ""
	var call_args: Array = []
	if args.size() > 1:
		var parsed: Variant = JSON.parse_string(str(args[1]))
		if parsed is Array:
			call_args = parsed
	var result: Variant = _dispatch(method, call_args)
	if _tb != null:
		_tb.set("_ret", result if result is String else JSON.stringify(result))


func _dispatch(method: String, a: Array) -> Variant:
	match method:
		"getState":
			return JSON.stringify(_state())
		"getMeta":
			return JSON.stringify(_world.meta.raw) if _world_ok() and _world.meta != null else "{}"
		"listViews":
			return Array(_world.meta.view_refs()) if _world_ok() else []
		"setView":
			return _set_view(str(a[0])) if a.size() >= 1 else false
		"clearView":
			if _world_ok():
				_world.clear_view()
				_view_frame = -1
				return true
			return false
		"setPose":
			if _world_ok() and a.size() >= 3:
				var yaw := float(a[3]) if a.size() > 3 else 0.0
				var pitch := float(a[4]) if a.size() > 4 else 0.0
				_world.set_player_pose_blender(Vector3(float(a[0]), float(a[1]), float(a[2])), yaw, pitch)
				return true
			return false
		"raycast":
			if _world_ok() and a.size() >= 6:
				var dist := float(a[6]) if a.size() > 6 else 10.0
				return _world.raycast_blender(Vector3(float(a[0]), float(a[1]), float(a[2])),
					Vector3(float(a[3]), float(a[4]), float(a[5])), dist)
			return null
		"checkCameras":
			return _world.check_cameras() if _world_ok() else []
	push_warning("[TB] unknown method '%s'" % method)
	return null


func _world_ok() -> bool:
	return _world != null and is_instance_valid(_world) and _world.is_ready


func _set_view(ref: String) -> bool:
	if not _world_ok():
		return false
	var ok := _world.set_view(ref)
	_view_frame = Engine.get_frames_drawn() if ok else -1
	return ok


func _state() -> Dictionary:
	var vp := get_viewport().get_visible_rect().size
	var state := {
		"ready": _reported_ready,
		"frames": Engine.get_frames_drawn(),
		"process_frames": Engine.get_process_frames(),
		"fps": Engine.get_frames_per_second(),
		"time_s": snappedf(Time.get_ticks_msec() / 1000.0, 0.001),
		"viewport": [int(vp.x), int(vp.y)],
		"view": null,
		"view_frames": 0,
		"paused": false,
		"mouse_captured": Input.mouse_mode == Input.MOUSE_MODE_CAPTURED,
		"player": {},
		"world": {},
	}
	if _world != null and is_instance_valid(_world):
		state["world"] = {
			"glb": _world.glb_path,
			"meta": _world.meta_path,
			"fixture": _world.meta != null and _world.meta.is_fixture,
			"lighting": String(_world.lighting_mode),
			"errors": Array(_world.errors),
		}
		if _world.is_ready:
			state["player"] = _world.player_state()
			state["paused"] = _world.is_paused()
			var view := _world.current_view()
			if not view.is_empty():
				state["view"] = view
				state["view_frames"] = Engine.get_frames_drawn() - _view_frame if _view_frame >= 0 else 0
	return state


# ---------------------------------------------------------------- desktop self-test

func _begin_selftest() -> void:
	_world.clear_view()
	_selftest_start = _world.player.global_position
	_selftest_yaw = _world.player.get_yaw()
	_selftest_frame = 0
	Input.action_press(&"move_forward")
	set_physics_process(true)


func _physics_process(_delta: float) -> void:
	if _selftest_frame < 0:
		return
	_selftest_frame += 1
	if _selftest_frame == SELFTEST_WALK_FRAMES:
		Input.action_release(&"move_forward")
	elif _selftest_frame >= SELFTEST_WALK_FRAMES + SELFTEST_SETTLE_FRAMES:
		set_physics_process(false)
		var moved := _world.player.global_position - _selftest_start
		var along := moved.dot(Coords.forward_from_yaw_deg(rad_to_deg(_selftest_yaw)))
		var missing := _missing_input_bindings()
		var ok := along >= 1.0 and missing.is_empty() and _world.errors.is_empty()
		_finish_selftest(ok, {
			"walk_displacement_m": snappedf(along, 0.001),
			"missing_bindings": missing,
			"state": _state(),
		})


func _missing_input_bindings() -> Array:
	var missing: Array = []
	for action in REQUIRED_ACTIONS:
		if not InputMap.has_action(action):
			missing.append(action + ": no action")
			continue
		var has_pad := false
		var has_desktop := false
		for ev in InputMap.action_get_events(action):
			if ev is InputEventJoypadButton or ev is InputEventJoypadMotion:
				has_pad = true
			elif ev is InputEventKey or ev is InputEventMouseButton:
				has_desktop = true
		var stick_only := action.begins_with("look_")
		if not has_pad or (not has_desktop and not stick_only):
			missing.append(action + ": incomplete")
	return missing


func _finish_selftest(ok: bool, details: Dictionary) -> void:
	print("[SELFTEST] %s %s" % ["PASS" if ok else "FAIL", JSON.stringify(details)])
	get_tree().quit(0 if ok else 1)

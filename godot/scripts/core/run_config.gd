class_name RunConfig
extends RefCounted
## Launch parameters, parsed once (lazily) from the page URL on the web or from the user
## command-line arguments (after `--`) on desktop.
##
##   web:     index.html?test=1&view=FIX01&lighting=review&glb=res://fixtures/runtime/apartment.glb
##   desktop: godot --path godot -- --test --view=FIX01 --lighting=review --glb=res://...
##
## Keys: test, selftest, dev, view, lighting (night|review), glb, meta.

const DEFAULT_GLB := "res://assets/apartment/apartment.glb"
## Test fixture written by tests/fixtures/make_runtime_fixture.py. Excluded from the shipping
## "Web" export preset; only the "Web Fixtures" preset (feature tag `fixtures`) packs it.
const FIXTURE_GLB := "res://fixtures/runtime/apartment.glb"
const LIGHTING_NIGHT := &"night"
const LIGHTING_REVIEW := &"review"
const SCENE_EXTENSIONS: PackedStringArray = ["glb", "gltf", "tscn", "scn"]
const FALSE_VALUES: PackedStringArray = ["0", "false", "no", "off"]

static var _parsed: bool = false
static var _params: Dictionary = {}


## All parameters as String -> String.
static func params() -> Dictionary:
	_ensure_parsed()
	return _params


static func get_param(key: String, default_value: String = "") -> String:
	_ensure_parsed()
	if _params.has(key):
		return str(_params[key])
	return default_value


static func flag(key: String) -> bool:
	_ensure_parsed()
	return _params.has(key) and not FALSE_VALUES.has(str(_params[key]).to_lower())


static func test_mode() -> bool:
	return flag("test") or flag("selftest")


static func selftest() -> bool:
	return flag("selftest")


## Dev conveniences (perf overlay): debug builds, ?dev=1 or test mode.
static func dev_mode() -> bool:
	return OS.is_debug_build() or flag("dev") or test_mode()


static func view_ref() -> String:
	return get_param("view").strip_edges()


static func lighting_mode() -> StringName:
	return LIGHTING_REVIEW if get_param("lighting").to_lower() == "review" else LIGHTING_NIGHT


## Scene to instance as the apartment: ?glb= (validated res:// path) > the exporter's GLB >
## the test fixture (fixture builds and editor runs only) > DEFAULT_GLB (world reports it missing).
static func resolve_glb_path() -> String:
	var requested := get_param("glb").strip_edges()
	if not requested.is_empty():
		if is_valid_scene_path(requested):
			return requested
		push_warning("RunConfig: ignoring invalid glb parameter '%s' (expects res://...%s)" % [requested, str(SCENE_EXTENSIONS)])
	if ResourceLoader.exists(DEFAULT_GLB):
		return DEFAULT_GLB
	if (OS.has_feature("fixtures") or OS.has_feature("editor")) and ResourceLoader.exists(FIXTURE_GLB):
		print("RunConfig: %s missing; using TEST FIXTURE %s" % [DEFAULT_GLB, FIXTURE_GLB])
		return FIXTURE_GLB
	return DEFAULT_GLB


## Meta for a scene path: ?meta= if valid, else '<dir>/<basename>_meta.json'.
static func meta_path_for(glb_path: String) -> String:
	var requested := get_param("meta").strip_edges()
	if requested.begins_with("res://") and requested.get_extension() == "json" and not requested.contains(".."):
		return requested
	return glb_path.get_basename() + "_meta.json"


static func is_valid_scene_path(path: String) -> bool:
	return path.begins_with("res://") and not path.contains("..") \
		and SCENE_EXTENSIONS.has(path.get_extension().to_lower())


static func _ensure_parsed() -> void:
	if _parsed:
		return
	_parsed = true
	if OS.has_feature("web"):
		var search: Variant = JavaScriptBridge.eval("window.location.search", true)
		if search is String:
			_parse_query(search as String)
	else:
		_parse_cmdline(OS.get_cmdline_user_args())


static func _parse_query(query: String) -> void:
	var q := query.trim_prefix("?")
	for pair in q.split("&", false):
		var eq := pair.find("=")
		var key := (pair if eq < 0 else pair.substr(0, eq)).uri_decode().strip_edges()
		var value := "1" if eq < 0 else pair.substr(eq + 1).replace("+", " ").uri_decode()
		if not key.is_empty():
			_params[key] = value


static func _parse_cmdline(args: PackedStringArray) -> void:
	for arg in args:
		if not arg.begins_with("--"):
			continue
		var body := arg.substr(2)
		var eq := body.find("=")
		var key := body if eq < 0 else body.substr(0, eq)
		var value := "1" if eq < 0 else body.substr(eq + 1)
		if not key.is_empty():
			_params[key] = value

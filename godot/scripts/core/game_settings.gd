class_name GameSettings
extends RefCounted
## Player-facing settings, persisted to user://settings.cfg (IndexedDB on the web).

const PATH := "user://settings.cfg"
const SECTION := "controls"

## Mouse look, degrees per (screen) pixel.
static var mouse_sensitivity: float = 0.11
## Right-stick look, degrees per second at full deflection.
static var gamepad_look_speed: float = 150.0
static var invert_y: bool = false
static var head_bob: bool = true

static var _loaded: bool = false


static func ensure_loaded() -> void:
	if _loaded:
		return
	_loaded = true
	var cfg := ConfigFile.new()
	if cfg.load(PATH) != OK:
		return
	mouse_sensitivity = clampf(float(cfg.get_value(SECTION, "mouse_sensitivity", mouse_sensitivity)), 0.01, 1.0)
	gamepad_look_speed = clampf(float(cfg.get_value(SECTION, "gamepad_look_speed", gamepad_look_speed)), 20.0, 400.0)
	invert_y = bool(cfg.get_value(SECTION, "invert_y", invert_y))
	head_bob = bool(cfg.get_value(SECTION, "head_bob", head_bob))


static func save() -> Error:
	var cfg := ConfigFile.new()
	cfg.set_value(SECTION, "mouse_sensitivity", mouse_sensitivity)
	cfg.set_value(SECTION, "gamepad_look_speed", gamepad_look_speed)
	cfg.set_value(SECTION, "invert_y", invert_y)
	cfg.set_value(SECTION, "head_bob", head_bob)
	return cfg.save(PATH)

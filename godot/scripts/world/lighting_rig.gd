class_name LightingRig
extends Node3D
## Runtime lights + Environment built from apartment_meta.json (the GLB carries no punctual
## lights). PLACEHOLDER night setup until baked lighting (ledger D-005) lands.
##
## "night":  dim warm practicals (OmniLight3D), one shadowed key light per furnished room
##           (capped for the Compatibility renderer's per-light shadow passes), a very dim cool
##           moon (DirectionalLight3D, shadowed so it only enters through openings), black
##           background, low ambient, AgX tonemapping.
## "review": neutral, even, shadowless light for architecture comparisons; practicals off.

const MODE_NIGHT := &"night"
const MODE_REVIEW := &"review"
const MAX_SHADOWED_PRACTICALS := 3
const WARM := Color(1.0, 0.71, 0.44)
const MOON := Color(0.60, 0.70, 1.0)
## Godot-space direction the moonlight comes FROM (plan south-east, ~25 deg elevation).
const MOON_FROM := Vector3(0.62, 0.48, 0.62)

## Per fixture type: bulb offset from the meta anchor along +Y (ceiling types hang below the
## mount point, lamps sit above their base), energy, range (m), may cast shadows.
## Keep offsets in sync with BULB_OFFSET_Z in tests/fixtures/make_runtime_fixture.py.
const TYPE_TABLE: Dictionary = {
	"pendant_shade": {"offset": -0.45, "energy": 1.25, "range": 6.0, "shadow": true},
	"ceiling_fan_light": {"offset": -0.32, "energy": 1.1, "range": 6.0, "shadow": true},
	"ceiling_light_flush": {"offset": -0.12, "energy": 1.1, "range": 6.0, "shadow": true},
	"bare_bulb": {"offset": -0.28, "energy": 1.2, "range": 5.5, "shadow": true},
	"floor_lamp": {"offset": 1.40, "energy": 0.8, "range": 4.5, "shadow": true},
	"table_lamp": {"offset": 0.32, "energy": 0.6, "range": 3.5, "shadow": true},
	"lava_lamp": {"offset": 0.25, "energy": 0.25, "range": 2.0, "shadow": false},
	"wall_light": {"offset": 0.0, "energy": 0.6, "range": 4.0, "shadow": false},
}
const DEFAULT_TYPE: Dictionary = {"offset": 0.0, "energy": 0.8, "range": 4.5, "shadow": false}

var mode: StringName = MODE_NIGHT
var practicals: Array[Light3D] = []


func build(meta: ApartmentMeta, lighting_mode: StringName) -> Environment:
	mode = MODE_REVIEW if lighting_mode == MODE_REVIEW else MODE_NIGHT
	for child in get_children():
		child.queue_free()
	practicals.clear()
	if mode == MODE_REVIEW:
		_build_review()
	else:
		_build_night(meta)
	return make_environment()


func make_environment() -> Environment:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.reflected_light_source = Environment.REFLECTION_SOURCE_DISABLED
	if mode == MODE_REVIEW:
		env.background_color = Color(0.05, 0.05, 0.05)
		env.ambient_light_color = Color(1.0, 1.0, 1.0)
		env.ambient_light_energy = 0.45
		env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
		env.tonemap_exposure = 1.0
	else:
		env.background_color = Color.BLACK
		env.ambient_light_color = Color(0.30, 0.34, 0.44)
		env.ambient_light_energy = 0.06
		env.tonemap_mode = Environment.TONE_MAPPER_AGX
		env.tonemap_exposure = 1.0
	return env


func _build_night(meta: ApartmentMeta) -> void:
	var shadowed := 0
	var keyed_rooms: Dictionary = {}
	for info in meta.lights:
		var room := meta.find_room(info.room)
		if room != null and room.placeholder:
			continue  # placeholder rooms stay unlit
		var spec: Dictionary = TYPE_TABLE.get(info.type, DEFAULT_TYPE)
		var light := OmniLight3D.new()
		light.name = "LIGHT_" + info.id.trim_prefix("LGT_")
		light.position = info.position + Vector3(0.0, float(spec["offset"]), 0.0)
		light.light_color = WARM
		light.light_energy = float(spec["energy"])
		light.light_specular = 0.35
		light.omni_range = float(spec["range"])
		light.omni_attenuation = 1.0
		var wants_shadow := bool(spec["shadow"]) and not keyed_rooms.has(info.room)
		if wants_shadow and shadowed < MAX_SHADOWED_PRACTICALS:
			light.shadow_enabled = true
			light.shadow_bias = 0.06
			light.shadow_normal_bias = 1.2
			light.shadow_blur = 1.5
			keyed_rooms[info.room] = true
			shadowed += 1
		light.set_meta(&"light_id", info.id)
		light.set_meta(&"room", info.room)
		add_child(light)
		practicals.append(light)

	var moon := DirectionalLight3D.new()
	moon.name = "LIGHT_moon"
	moon.light_color = MOON
	moon.light_energy = 0.10
	moon.light_specular = 0.2
	moon.shadow_enabled = true
	moon.shadow_bias = 0.05
	moon.directional_shadow_mode = DirectionalLight3D.SHADOW_ORTHOGONAL
	moon.directional_shadow_max_distance = 30.0
	add_child(moon)
	moon.look_at_from_position(MOON_FROM.normalized() * 10.0, Vector3.ZERO, Vector3.UP)


func _build_review() -> void:
	# Three shadowless directional lights from different azimuths (one from below for ceilings)
	# + white ambient: every surface readable, no hotspots, no room-to-room occlusion.
	var dirs: Array[Vector3] = [Vector3(0.45, 0.80, 0.40), Vector3(-0.55, 0.45, -0.70), Vector3(0.20, -0.85, -0.45)]
	var energies: Array[float] = [0.45, 0.28, 0.18]
	for i in dirs.size():
		var key := DirectionalLight3D.new()
		key.name = "LIGHT_review_%d" % i
		key.light_color = Color.WHITE
		key.light_energy = energies[i]
		key.light_specular = 0.1
		key.shadow_enabled = false
		add_child(key)
		key.look_at_from_position(dirs[i].normalized() * 10.0, Vector3.ZERO, Vector3.UP if absf(dirs[i].normalized().y) < 0.95 else Vector3.BACK)

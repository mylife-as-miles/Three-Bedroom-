extends Node
## Main scene. Reads the launch parameters (URL query via JavaScriptBridge on the web, user
## args after `--` on desktop; see RunConfig), then instances the world with the requested
## apartment scene, meta and lighting mode. The test bridge autoload activates itself from
## the same parameters (?test=1).

const WORLD_SCENE: PackedScene = preload("res://scenes/world/world.tscn")


func _ready() -> void:
	GameSettings.ensure_loaded()
	var params := RunConfig.params()
	if not params.is_empty():
		print("Boot: launch parameters %s" % JSON.stringify(params))
	var world := WORLD_SCENE.instantiate() as ApartmentWorld
	world.glb_path = RunConfig.resolve_glb_path()
	world.meta_path = RunConfig.meta_path_for(world.glb_path)
	world.lighting_mode = RunConfig.lighting_mode()
	add_child(world)

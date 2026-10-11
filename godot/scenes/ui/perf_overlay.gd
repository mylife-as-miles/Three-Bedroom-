extends CanvasLayer
## Dev-only performance overlay, toggled with F3 (action `toggle_perf_overlay`). Hidden by
## default; available in debug builds, with ?dev=1, or in test mode. Under SwiftShader the
## numbers are software-rasteriser numbers, not real-hardware performance.

const REFRESH_S := 0.25

var _elapsed: float = 0.0

@onready var _label: Label = $Panel/Label


func _ready() -> void:
	visible = false
	set_process(false)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed(&"toggle_perf_overlay") and RunConfig.dev_mode():
		visible = not visible
		set_process(visible)
		_elapsed = REFRESH_S
		get_viewport().set_input_as_handled()


func _process(delta: float) -> void:
	_elapsed += delta
	if _elapsed < REFRESH_S:
		return
	_elapsed = 0.0
	var fps := Performance.get_monitor(Performance.TIME_FPS)
	var frame_ms := 1000.0 / fps if fps > 0.0 else 0.0
	_label.text = "%.0f fps  %.1f ms\ndraws %d  prims %.1fk  objs %d\nvram %.0f MB  mem %.0f MB" % [
		fps, frame_ms,
		int(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)),
		Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME) / 1000.0,
		int(Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME)),
		Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED) / 1048576.0,
		Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0,
	]

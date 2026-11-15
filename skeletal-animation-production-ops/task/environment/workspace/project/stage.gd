extends Node2D

signal impact(point: Vector2)
var clock := 0.0
var settings := ConfigFile.new()
var frames_cache := {}
var serial := 0
const SOURCES = {"hit": ["003", 11], "appear": ["023", 49], "fly": ["500", 13]}

func _ready():
	settings.load("res://delivery.cfg")
	if not OS.get_cmdline_user_args().has("--verification"):
		_demo()

func _demo():
	spawn_appear(Vector2(150, 290))
	await get_tree().create_timer(0.15).timeout
	cast(Vector2(130, 150), Vector2(480, 190))
	await get_tree().create_timer(0.30).timeout
	cast(Vector2(130, 260), Vector2(480, 190))

func _frames(kind: String) -> SpriteFrames:
	if frames_cache.has(kind):
		return frames_cache[kind]
	var spec = SOURCES[kind]
	var frames := SpriteFrames.new()
	frames.remove_animation("default")
	frames.add_animation(kind)
	frames.set_animation_speed(kind, float(settings.get_value(kind, "fps", 30.0)))
	frames.set_animation_loop(kind, false)
	for i in range(spec[1]):
		var path = "res://assets/frames/%s/%s_%02d.png" % [spec[0], spec[0], i]
		var img = Image.load_from_file(path)
		frames.add_frame(kind, ImageTexture.create_from_image(img))
	frames_cache[kind] = frames
	return frames

func _sprite(kind: String, point: Vector2) -> AnimatedSprite2D:
	serial += 1
	var sprite := AnimatedSprite2D.new()
	sprite.name = "%s_%03d" % [kind, serial]
	sprite.set_meta("kind", kind)
	sprite.sprite_frames = _frames(kind)
	sprite.centered = false
	sprite.offset = settings.get_value(kind, "offset", Vector2.ZERO)
	var mat := CanvasItemMaterial.new()
	mat.blend_mode = int(settings.get_value(kind, "blend", 0))
	sprite.material = mat
	add_child(sprite)
	sprite.global_position = point
	sprite.play(kind)
	return sprite

func spawn_hit(point: Vector2) -> AnimatedSprite2D:
	if not bool(settings.get_value("hit", "allow_overlap", true)):
		for child in get_children():
			if child is AnimatedSprite2D and child.get_meta("kind") == "hit":
				return child
	var sprite = _sprite("hit", point)
	if bool(settings.get_value("hit", "cleanup", true)):
		sprite.animation_finished.connect(sprite.queue_free)
	impact.emit(point) # Existing legacy visual callback
	return sprite

func spawn_appear(point: Vector2) -> AnimatedSprite2D:
	var sprite = _sprite("appear", point)
	sprite.set_frame_and_progress(int(settings.get_value("appear", "start_frame", 4)), 0.0)
	if bool(settings.get_value("appear", "cleanup", true)):
		sprite.animation_finished.connect(sprite.queue_free)
	return sprite

func cast(start: Vector2, target: Vector2) -> AnimatedSprite2D:
	var sprite = _sprite("fly", start)
	sprite.set_meta("start", start)
	sprite.set_meta("target", target)
	sprite.set_meta("born", clock)
	if bool(settings.get_value("fly", "orient", true)):
		sprite.rotation = (target - start).angle()
	return sprite

func _process(delta):
	clock += delta
	for child in get_children():
		if not child is AnimatedSprite2D or child.get_meta("kind") != "fly":
			continue
		var start: Vector2 = child.get_meta("start")
		var target: Vector2 = child.get_meta("target")
		var duration = float(settings.get_value("fly", "duration", 0.5))
		var progress = clampf((clock - float(child.get_meta("born"))) / duration, 0.0, 1.0)
		child.global_position = start.lerp(target, progress)
		if progress >= 1.0:
			impact.emit(target)
			spawn_hit(target)
			child.queue_free()

extends SceneTree

var tick = 0

func _initialize():
	process_frame.connect(func(): tick += 1)
	call_deferred("run")

func world_anchor(node) -> Vector2:
	var texture = node.sprite_frames.get_frame_texture(node.animation, node.frame)
	var center = Vector2(texture.get_size()) / 2.0 if node.centered else Vector2.ZERO
	return node.global_transform * (node.offset + Vector2(75, 20) - center)

func observe(parent_angle: float, translation: Vector2, start: Vector2, target: Vector2) -> Dictionary:
	var caller = Node2D.new()
	caller.rotation = parent_angle
	caller.position = translation
	root.add_child(caller)
	var stage = load("res://stage.tscn").instantiate()
	caller.add_child(stage)
	await process_frame
	var events: Array = []
	stage.impact.connect(func(point): events.append({"tick":tick + 1,"x":point.x,"y":point.y}))
	var node = stage.cast(start, target)
	var origin = tick
	var heading_ok = true
	var path_ok = true
	var rows: Array = []
	var expected_angle = (target - start).angle()
	var identity = node.get_instance_id()
	for step in range(34):
		if not is_instance_valid(node) or not node.is_inside_tree(): break
		var age = tick - origin
		var anchor = world_anchor(node)
		var expected_point = start.lerp(target, clampf(age / 30.0, 0.0, 1.0))
		var difference = abs(wrapf(node.global_rotation - expected_angle, -PI, PI))
		heading_ok = heading_ok and difference <= 0.0001
		path_ok = path_ok and anchor.distance_to(expected_point) <= 0.05
		rows.append({"age_ticks":age,"global_angle":node.global_rotation,"expected_world_angle":expected_angle,"absolute_angle_error":difference,"anchor_x":anchor.x,"anchor_y":anchor.y,"expected_x":expected_point.x,"expected_y":expected_point.y,"source_frame":node.frame,"instance_id":identity})
		await process_frame
	var release_age = tick - origin
	var event_ok = events.size() == 1
	if event_ok:
		event_ok = abs(events[0].tick - origin - 30) <= 1 and Vector2(events[0].x, events[0].y).distance_to(target) <= 0.05
	caller.queue_free()
	await process_frame
	return {"parent_rotation":parent_angle,"parent_translation":[translation.x,translation.y],"world_start":[start.x,start.y],"world_target":[target.x,target.y],"heading_passed":heading_ok,"world_path_passed":path_ok,"release_age_ticks":release_age,"event_passed":event_ok,"samples":rows,"events":events}

func run():
	var cases: Array = []
	for angle in [0.0, 0.37, -0.43]:
		for points in [[Vector2(80,80),Vector2(380,260)],[Vector2(500,80),Vector2(150,280)]]:
			cases.append(await observe(angle, Vector2(23,-17) if angle != 0.0 else Vector2.ZERO, points[0], points[1]))
	var passed = true
	for result in cases: passed = passed and result.heading_passed and result.world_path_passed and result.event_passed and result.release_age_ticks >= 29 and result.release_age_ticks <= 31
	var result = {"schema_version":"world-heading-observations-v13","contract_binding":"integration-contract.xlsx API Contract: cast accepts two world points and artwork faces target; direction tolerance 0.0001 radians.","scope":"Rigid caller transforms only; no new scale, moving-parent, cancellation or protocol requirement.","passed":passed,"cases":cases}
	var file = FileAccess.open(OS.get_cmdline_user_args()[0], FileAccess.WRITE)
	file.store_string(JSON.stringify(result,"  ") + "\n")
	file.close()
	quit(0 if passed else 1)

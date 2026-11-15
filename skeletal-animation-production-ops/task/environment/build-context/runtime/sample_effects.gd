extends SceneTree
var events: Array = []
var capture_tick := 0

func _initialize(): call_deferred("run")

func sprites(parent: Node) -> Array:
	var found: Array = []
	for child in parent.get_children():
		if child is AnimatedSprite2D: found.append(child)
		found.append_array(sprites(child))
	return found

func effective_color(node: CanvasItem) -> Color:
	var color = node.self_modulate
	var ancestor: Node = node
	while ancestor is CanvasItem:
		color *= ancestor.modulate
		ancestor = ancestor.get_parent()
	return color

func run():
	var out = OS.get_cmdline_user_args()[0]
	DirAccess.make_dir_recursive_absolute(out.path_join("textures"))
	var stage = load("res://stage.tscn").instantiate()
	root.add_child(stage)
	await process_frame
	stage.impact.connect(func(point): events.append([str(float(capture_tick+1)/60.0),str(point.x),str(point.y)]))
	var f = FileAccess.open(out.path_join("scene-frames.csv"),FileAccess.WRITE)
	f.store_csv_line(PackedStringArray(["frame","time","node","animation","source_frame","texture","a","b","c","d","tx","ty","offset_x","offset_y","blend","visible","red","green","blue","alpha"]))
	var saved := {}
	stage.spawn_appear(Vector2(150,290))
	for i in range(121):
		capture_tick=i
		if i==9: stage.cast(Vector2(130,150),Vector2(480,190))
		if i==27: stage.cast(Vector2(130,260),Vector2(480,190))
		# Empty-stage marker preserves timing after every effect has been reclaimed.
		f.store_csv_line(PackedStringArray([str(i),str(float(i)/60.0),"","","","","","","","","","","","","","","","","",""]))
		for node in sprites(stage):
			var texture = node.sprite_frames.get_frame_texture(node.animation,node.frame)
			var img = texture.get_image()
			var key = "%s_%03d_%s.png" % [node.animation,node.frame,str(hash(img.get_data()))]
			if not saved.has(key):
				img.save_png(out.path_join("textures").path_join(key))
				saved[key]=true
			var g = node.global_transform
			var color = effective_color(node)
			var offset = node.offset - (Vector2(texture.get_size())/2.0 if node.centered else Vector2.ZERO)
			var blend = node.material.blend_mode if node.material is CanvasItemMaterial else 0
			f.store_csv_line(PackedStringArray([str(i),str(float(i)/60.0),str(node.name),str(node.animation),str(node.frame+(4 if node.animation=="appear" and node.sprite_frames.get_frame_count(node.animation)==45 else 0)),"textures/"+key,str(g.x.x),str(g.y.x),str(g.x.y),str(g.y.y),str(g.origin.x),str(g.origin.y),str(offset.x),str(offset.y),str(blend),str(node.is_visible_in_tree()),str(color.r),str(color.g),str(color.b),str(color.a)]))
		await process_frame
	f.close()
	var ef = FileAccess.open(out.path_join("impact-events.csv"),FileAccess.WRITE)
	ef.store_csv_line(PackedStringArray(["engine_time","x","y"]))
	for event in events:ef.store_csv_line(PackedStringArray(event))
	ef.close()
	print("SAMPLED 121 frames; impacts="+str(events.size()))
	stage.queue_free()
	quit()

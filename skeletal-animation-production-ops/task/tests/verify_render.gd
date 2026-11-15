extends SceneTree
# Render actual candidate scene and an independent sprite-only reference in
# separate viewports. Compare only the required artwork's pixel footprint.
var results: Array = []
var effect_results: Dictionary = {"hit":[],"appear":[],"fly":[]}
var textures: Dictionary = {}
var trusted_assets = OS.get_environment("FX_ORIGINAL_PROJECT").path_join("assets/frames")

func _initialize(): call_deferred("run")

func sprites(parent: Node) -> Array:
	var found: Array = []
	for child in parent.get_children():
		if child is AnimatedSprite2D: found.append(child)
		found.append_array(sprites(child))
	return found

func viewport(opaque: bool = false) -> SubViewport:
	var v = SubViewport.new()
	v.size=Vector2i(640,360)
	v.transparent_bg=not opaque
	v.render_target_update_mode=SubViewport.UPDATE_ALWAYS
	root.add_child(v)
	return v

func reference(scene: Node, target: SubViewport, effect: String = ""):
	for child in target.get_children(): child.free()
	for node in sprites(scene):
		if effect!="" and str(node.animation)!=effect:continue
		var copy = Sprite2D.new()
		var group = {"hit":"003","appear":"023","fly":"500"}.get(str(node.animation),"")
		if group=="":continue
		var idx = node.frame+(4 if node.animation=="appear" and node.sprite_frames.get_frame_count(node.animation)==45 else 0)
		var path=trusted_assets.path_join("%s/%s_%02d.png" % [group,group,idx])
		if not textures.has(path):textures[path]=ImageTexture.create_from_image(Image.load_from_file(path))
		copy.texture=textures[path]
		copy.centered=node.centered
		copy.offset=node.offset
		copy.transform=node.global_transform
		copy.texture_filter=node.texture_filter
		var z = node.z_index
		var ancestor = node
		while ancestor.z_as_relative and ancestor.get_parent() is Node2D:
			ancestor=ancestor.get_parent()
			z+=ancestor.z_index
		copy.z_index=clampi(z,-4096,4096)
		target.add_child(copy)

func compare(actual: Image, expected: Image, label: String, support: Image = null) -> Dictionary:
	var pixels = 0
	var bad = 0
	var maximum = 0.0
	# Both images were actually rendered over the same opaque GPU background.
	for y in range(360):
		for x in range(640):
			var e=expected.get_pixel(x,y)
			if (support.get_pixel(x,y).a if support!=null else e.a)<0.02:continue
			pixels+=1
			var a=actual.get_pixel(x,y)
			var error=0.0
			for channel in range(4):error=maxf(error,absf(a[channel]-e[channel]))
			maximum=maxf(maximum,error)
			if error>3.0/255.0:bad+=1
	return {"case":label,"support_pixels":pixels,"mismatched_pixels":bad,"max_channel_error":maximum,"passed":pixels>0 and bad<=maxi(2,int(pixels*0.001))}

func run():
	var out=OS.get_cmdline_user_args()[0]
	DirAccess.make_dir_recursive_absolute(out)
	if DisplayServer.get_name()=="headless":
		push_error("Actual rendering requires a rendering display driver, not the headless dummy driver")
		quit(2)
		return
	# No interactive window is needed: offscreen viewports render while it is hidden.
	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_MINIMIZED)
	var actual=viewport(true)
	var expected=viewport(true)
	var union_support=viewport()
	var masks={"hit":viewport(),"appear":viewport(),"fly":viewport()}
	var stage=load("res://stage.tscn").instantiate()
	actual.add_child(stage)
	await process_frame
	stage.spawn_appear(Vector2(150,290))
	for i in range(121):
		if i==9:stage.cast(Vector2(130,150),Vector2(480,190))
		if i==27:stage.cast(Vector2(130,260),Vector2(480,190))
		if i in [0,8,20,34,44,58,88]:
			reference(stage,expected)
			reference(stage,union_support)
			for effect in masks:reference(stage,masks[effect],effect)
			# Force drawing without advancing candidate simulation between reference
			# construction and capture. Both viewports use the same renderer.
			var previous_mode=stage.process_mode
			stage.process_mode=Node.PROCESS_MODE_DISABLED
			await process_frame
			for background in [["dark",Color(15.0/255,25.0/255,40.0/255)],["light",Color(230.0/255,236.0/255,241.0/255)]]:
				RenderingServer.set_default_clear_color(background[1])
				RenderingServer.force_draw(false)
				var a=actual.get_texture().get_image()
				var e=expected.get_texture().get_image()
				var support=union_support.get_texture().get_image()
				if a==null or e==null or a.is_empty() or e.is_empty():
					push_error("Renderer returned no readable viewport image")
					quit(2)
					return
				a.save_png(out.path_join("actual_%s_%03d.png" % [background[0],i]))
				e.save_png(out.path_join("reference_%s_%03d.png" % [background[0],i]))
				if background[0]=="dark":
					a.save_png(out.path_join("actual_%03d.png" % i))
					e.save_png(out.path_join("reference_%03d.png" % i))
				var comparison=compare(a,e,"%s_frame_%03d" % [background[0],i],support)
				comparison.background=background[0]
				comparison.actual_corner=str(a.get_pixel(0,0))
				comparison.reference_corner=str(e.get_pixel(0,0))
				results.append(comparison)
				for effect in masks:
					var mask=masks[effect].get_texture().get_image()
					var measured=compare(a,e,"%s_frame_%03d_%s" % [background[0],i,effect],mask)
					if measured.support_pixels>0:effect_results[effect].append(measured)
			stage.process_mode=previous_mode
		await process_frame
	var passed=true
	for result in results:passed=passed and result.passed
	var effects={}
	for effect in effect_results:
		var ok=effect_results[effect].size()>0
		for measured in effect_results[effect]:ok=ok and measured.passed
		effects[effect]={"passed":ok,"checks":effect_results[effect]}
	var f=FileAccess.open(out.path_join("render-checks.json"),FileAccess.WRITE)
	f.store_string(JSON.stringify({"passed":passed,"effects":effects,"backgrounds":["dark","light"],"backgrounds_rendered_in_gpu":true,"renderer":RenderingServer.get_current_rendering_method(),"driver":RenderingServer.get_current_rendering_driver_name(),"checks":results},"  ")+"\n")
	f.close()
	print("RENDER CHECK: ",passed)
	quit(0 if passed else 1)

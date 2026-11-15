extends SceneTree
var rows: Array = []
var score = 0.0
var impacts: Array = []
var tick = 0
var observations: Array = []
var trusted_assets = OS.get_environment("FX_ORIGINAL_PROJECT").path_join("assets/frames")

func _initialize():
	process_frame.connect(func(): tick += 1)
	call_deferred("run")

func record(id: String, label: String, ok: bool, points: int, detail: String, coverage: float = 1.0):
	var earned = points * coverage if ok else 0.0
	rows.append([id,label,"PASS" if is_equal_approx(earned,points) else "FAIL",str(earned),str(points),detail])
	score += earned

func sprites(parent: Node) -> Array:
	var found: Array = []
	for child in parent.get_children():
		if child is AnimatedSprite2D: found.append(child)
		found.append_array(sprites(child))
	return found

func count_kind(stage: Node, kind: String) -> int:
	var n = 0
	for node in sprites(stage):
		if node.animation == kind: n += 1
	return n

func visible_art(node: AnimatedSprite2D) -> bool:
	if not is_instance_valid(node) or not node.is_visible_in_tree(): return false
	var color = node.self_modulate
	var ancestor: Node = node
	while ancestor is CanvasItem:
		color *= ancestor.modulate
		ancestor = ancestor.get_parent()
	return color.is_equal_approx(Color.WHITE) and not node.material is ShaderMaterial

func mix(node: AnimatedSprite2D) -> bool:
	return node.material == null or (node.material is CanvasItemMaterial and node.material.blend_mode == CanvasItemMaterial.BLEND_MODE_MIX)

func world_anchor(node: AnimatedSprite2D, point: Vector2) -> Vector2:
	var tx = node.sprite_frames.get_frame_texture(node.animation,node.frame)
	return node.global_transform * (node.offset + point - (Vector2(tx.get_size())/2.0 if node.centered else Vector2.ZERO))

func anchor(node: AnimatedSprite2D, point: Vector2, expected: Vector2) -> bool:
	return world_anchor(node,point).distance_to(expected) <= 0.05 and abs(node.global_transform.x.length()-1)<0.0001 and abs(node.global_transform.y.length()-1)<0.0001

func source_index(node: AnimatedSprite2D) -> int:
	return node.frame + (4 if node.animation == "appear" and node.sprite_frames.get_frame_count(node.animation)==45 else 0)

func artwork(node: AnimatedSprite2D, count: int, source: String) -> float:
	var f = node.sprite_frames
	var kind = node.animation
	var offset = 4 if kind == "appear" and f.get_frame_count(kind)==45 else 0
	var actual_count = count-offset
	if f.get_frame_count(kind)!=actual_count or abs(f.get_animation_speed(kind)-30.0)>0.0001 or f.get_animation_loop(kind): return 0.0
	var matching = 0
	for i in range(actual_count):
		var tx = f.get_frame_texture(kind,i)
		var expected = Image.load_from_file(trusted_assets.path_join("%s/%s_%02d.png" % [source,source,i+offset]))
		if tx != null and tx.get_image().get_size()==expected.get_size() and tx.get_image().get_data()==expected.get_data(): matching += 1
	return float(matching)/float(actual_count)

func observe_lifetimes(nodes: Array, duration: float, first: int, last: int, points: Array, image_anchor: Vector2, label: String, born_tick: int = -1) -> bool:
	var born = tick if born_tick<0 else born_tick
	var end_ticks = []
	for node in nodes: end_ticks.append(-1)
	var ok = true
	for step in range(int(round(duration*60))+4):
		var elapsed = float(tick-born)/60.0
		var any_alive = false
		for n in range(nodes.size()):
			var node=nodes[n]
			var alive = is_instance_valid(node) and node.is_inside_tree()
			if not alive:
				if end_ticks[n]<0:end_ticks[n]=tick-born
				continue
			any_alive=true
			var idx = source_index(node)
			var expected = mini(last,first+int(floor(elapsed*30.0+0.00001)))
			ok = ok and abs(idx-expected)<=1 and visible_art(node) and mix(node) and anchor(node,image_anchor,points[n])
			observations.append([label+str(n),str(tick-born),str(elapsed),str(idx),str(world_anchor(node,image_anchor)),"alive"])
		if not any_alive:break
		await process_frame
	for n in range(nodes.size()):
		var end_tick=end_ticks[n]
		ok=ok and end_tick>=0 and abs(float(end_tick)/60.0-duration)<=1.0/60.0+0.00001
		observations.append([label+str(n),str(end_tick),str(float(end_tick)/60.0),"","","released" if end_tick>=0 else "still alive"])
	return ok

func observe_flight(stage: Node, start: Vector2, target: Vector2, label: String) -> Dictionary:
	var before = impacts.size()
	var node = stage.cast(start,target)
	var born = tick
	var art = artwork(node,13,"500")
	var heading = abs(wrapf(node.global_rotation-(target-start).angle(),-PI,PI))<=0.0001 and anchor(node,Vector2(75,20),start) and visible_art(node)
	var path_ok = true
	var end_tick = -1
	for step in range(34):
		var elapsed = float(tick-born)/60.0
		if not is_instance_valid(node) or not node.is_inside_tree():
			end_tick=tick-born
			break
		var target_point = start.lerp(target,clampf(elapsed/0.5,0.0,1.0))
		path_ok = path_ok and anchor(node,Vector2(75,20),target_point) and visible_art(node) and mix(node)
		path_ok = path_ok and abs(wrapf(node.global_rotation-(target-start).angle(),-PI,PI))<=0.0001
		path_ok = path_ok and abs(source_index(node)-mini(12,int(floor(elapsed*30.0+0.00001))))<=1
		observations.append([label,str(tick-born),str(elapsed),str(source_index(node)),str(world_anchor(node,Vector2(75,20))),"alive"])
		await process_frame
	var lifetime_ok = end_tick>=0 and abs(float(end_tick)/60.0-0.5)<=1.0/60.0+0.00001
	var event_ok = impacts.size()==before+1
	if event_ok:
		var event = impacts[before]
		event_ok = event[1].distance_to(target)<=0.05 and abs(float(event[0]-born)/60.0-0.5)<=1.0/60.0+0.00001
	var hits = []
	for child in sprites(stage):
		if child.animation == "hit": hits.append(child)
	var hit_ok = hits.size()==1
	if hit_ok: hit_ok = anchor(hits[0],Vector2(79,86),target) and visible_art(hits[0]) and mix(hits[0]) and artwork(hits[0],11,"003")==1.0
	var arrived_lifetime=false
	if hit_ok:
		# The arrival visual's lifecycle is measured even if its business callback
		# is duplicated or absent; those are separate contract observations.
		arrived_lifetime=await observe_lifetimes(hits,11.0/30.0,0,10,[target],Vector2(79,86),label+"_hit",born+end_tick)
	else:
		for i in range(24):await process_frame
	return {"art":art,"heading":heading,"path":path_ok and lifetime_ok,"event":event_ok,"cleanup":lifetime_ok and hit_ok and arrived_lifetime and count_kind(stage,"fly")==0 and count_kind(stage,"hit")==0}

func run():
	var out = OS.get_cmdline_user_args()[0]
	DirAccess.make_dir_recursive_absolute(out)
	var stage = load("res://stage.tscn").instantiate()
	root.add_child(stage)
	await process_frame
	# process_frame marks update start; callbacks from that update belong to its end.
	stage.impact.connect(func(point): impacts.append([tick+1,point]))
	var h1 = stage.spawn_hit(Vector2(320,180))
	var h2 = stage.spawn_hit(Vector2(325,180))
	var hit_art = minf(artwork(h1,11,"003"),artwork(h2,11,"003"))
	var hit_display = hit_art if visible_art(h1) and visible_art(h2) else 0.0
	record("C02","Visible hit anchors align with both requested points",anchor(h1,Vector2(79,86),Vector2(320,180)) and anchor(h2,Vector2(79,86),Vector2(325,180)),5,"World-space artwork anchors",hit_display)
	record("C03","Hit artwork uses ordinary alpha blending",mix(h1) and mix(h2),5,"Actual sprite materials",hit_display)
	record("C04","Repeated hits have independent visible instances",h1!=h2 and count_kind(stage,"hit")==2,10,"Distinct returned instances",hit_display)
	var hit_lifetime = await observe_lifetimes([h1,h2],11.0/30.0,0,10,[Vector2(320,180),Vector2(325,180)],Vector2(79,86),"hit")
	record("C05","Visual-only playback never emits a combat event",impacts.is_empty(),10,str(impacts))
	record("C06","Hit playback and release meet the contracted interval",hit_lifetime and count_kind(stage,"hit")==0,10,"Independent 60 Hz observations; one-tick end tolerance",hit_display)
	var appearance_events_before=impacts.size()
	var appear = stage.spawn_appear(Vector2(150,290))
	var appear_art = artwork(appear,49,"023")
	var appear_display = appear_art if visible_art(appear) else 0.0
	record("C07","Appearance begins at source frame 04 at its ground anchor",source_index(appear)==4 and anchor(appear,Vector2(122,214),Vector2(150,290)) and mix(appear),10,str(source_index(appear)),appear_display)
	var appear_lifetime = await observe_lifetimes([appear],1.5,4,48,[Vector2(150,290)],Vector2(122,214),"appear")
	var appearance_quiet=impacts.size()==appearance_events_before
	record("C08","Appearance plays and releases within one sampling interval",appear_lifetime and appearance_quiet,10,"Independent 60 Hz observations",appear_display)
	var appearance_log=FileAccess.open(out.path_join("appearance-observations.json"),FileAccess.WRITE)
	appearance_log.store_string(JSON.stringify({"event_count_before_call":appearance_events_before,"event_count_after_completion":impacts.size(),"no_new_combat_event":appearance_quiet,"lifetime_and_anchors_passed":appear_lifetime})+"\n")
	appearance_log.close()
	var flight_events_before=impacts.size()
	var first = await observe_flight(stage,Vector2(80,80),Vector2(380,260),"flight1")
	var second = await observe_flight(stage,Vector2(500,80),Vector2(150,280),"flight2")
	var fly_art = minf(first.art,second.art)
	record("C01","Original runtime artwork, rate and nonlooping playback",true,10,"Full appearance sequence or ordered playback subset accepted",(hit_art+appear_art+fly_art)/3.0)
	record("C09","Visible flight artwork faces its travel direction",first.heading and second.heading,10,"Both travel directions",fly_art)
	record("C10","World-space flight anchor follows a constant-speed half-second path",first.path and second.path,5,"Every 60 Hz sample, independent of scene clock",fly_art)
	record("C11","Each arrival emits exactly one timely impact at its destination",first.event and second.event and impacts.size()-flight_events_before==2,7,str(impacts.slice(flight_events_before)))
	record("C12","Each projectile produces a hit and all instances are reclaimed",first.cleanup and second.cleanup and count_kind(stage,"hit")==0 and count_kind(stage,"fly")==0 and count_kind(stage,"appear")==0,5,"Both arrivals and final scene tree")
	var file = FileAccess.open(out.path_join("runtime-checks.csv"),FileAccess.WRITE)
	file.store_csv_line(PackedStringArray(["id","check","result","earned","available","detail"]))
	for row in rows: file.store_csv_line(PackedStringArray(row))
	file.close()
	file=FileAccess.open(out.path_join("timing-observations.csv"),FileAccess.WRITE)
	file.store_csv_line(PackedStringArray(["case","tick","elapsed","source_frame","world_anchor","state"]))
	for row in observations:file.store_csv_line(PackedStringArray(row))
	file.close()
	file=FileAccess.open(out.path_join("artwork-coverage.json"),FileAccess.WRITE)
	file.store_string(JSON.stringify({"hit":hit_art,"appear":appear_art,"fly":fly_art})+"\n")
	file.close()
	print("API RUNTIME SCORE: %s/97" % score)
	stage.queue_free()
	quit(0 if is_equal_approx(score,97.0) else 1)

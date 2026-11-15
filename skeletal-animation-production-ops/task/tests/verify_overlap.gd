extends SceneTree
var events: Array = []
var tick = 0
var observations: Array = []

func _initialize():
	process_frame.connect(func(): tick += 1)
	call_deferred("run")

func alive(node) -> bool:
	return is_instance_valid(node) and node.is_inside_tree()

func sprites(parent) -> Array:
	var found: Array = []
	for child in parent.get_children():
		if child is AnimatedSprite2D:found.append(child)
		found.append_array(sprites(child))
	return found

func count_hits(stage) -> int:
	var count=0
	for sprite in sprites(stage):
		if sprite.animation=="hit":count+=1
	return count

func world_anchor(node, point: Vector2) -> Vector2:
	var texture=node.sprite_frames.get_frame_texture(node.animation,node.frame)
	return node.global_transform * (node.offset+point-(Vector2(texture.get_size())/2.0 if node.centered else Vector2.ZERO))

func simultaneous_arrival_lifetimes() -> Dictionary:
	var stage=load("res://stage.tscn").instantiate()
	root.add_child(stage)
	await process_frame
	var observed_events: Array=[]
	stage.impact.connect(func(point):observed_events.append({"tick":tick+1,"point":point}))
	var starts=[Vector2(80,80),Vector2(520,80),Vector2(80,280)]
	var targets=[Vector2(300,180),Vector2(300,180),Vector2(400,240)]
	var start_tick=tick
	var hits: Dictionary={}
	var identity_ok=true
	var geometry_ok=true
	var progression_ok=true
	for index in range(starts.size()):stage.cast(starts[index],targets[index])
	for step in range(58):
		for node in sprites(stage):
			if node.animation!="hit":continue
			var id=node.get_instance_id()
			var point=world_anchor(node,Vector2(79,86))
			if not hits.has(id):
				hits[id]={"node":node,"birth_tick":tick,"release_tick":-1,"point":point}
				identity_ok=identity_ok and abs(tick-start_tick-30)<=1
			var record=hits[id]
			geometry_ok=geometry_ok and point.distance_to(record.point)<=0.05 and node.is_visible_in_tree()
			progression_ok=progression_ok and abs(node.frame-mini(10,int(floor((tick-record.birth_tick)/2.0))))<=1
			observations.append({"case":"same_target_simultaneous_hit","instance_id":id,"birth_tick":record.birth_tick,"tick":tick-record.birth_tick,"source_frame":node.frame,"x":point.x,"y":point.y})
		for record in hits.values():
			if record.release_tick<0 and not alive(record.node):record.release_tick=tick
		await process_frame
	var destination_counts=[0,0]
	var life_ok=true
	var records: Array=[]
	for id in hits:
		var record=hits[id]
		if record.point.distance_to(targets[0])<=0.05:destination_counts[0]+=1
		elif record.point.distance_to(targets[2])<=0.05:destination_counts[1]+=1
		else:geometry_ok=false
		var age=record.release_tick-record.birth_tick
		life_ok=life_ok and record.release_tick>=0 and age>=21 and age<=23
		records.append({"instance_id":id,"birth_tick":record.birth_tick-start_tick,"release_tick":record.release_tick-start_tick,"lifetime_ticks":age,"x":record.point.x,"y":record.point.y})
	identity_ok=identity_ok and hits.size()==3 and destination_counts==[2,1]
	var notifications_ok=observed_events.size()==3
	var matched=[false,false,false]
	var event_rows: Array=[]
	for event in observed_events:
		var found=false
		for index in range(targets.size()):
			if not matched[index] and event.point.distance_to(targets[index])<=0.05 and abs(event.tick-start_tick-30)<=1:
				matched[index]=true
				found=true
				break
		notifications_ok=notifications_ok and found
		event_rows.append({"tick":event.tick-start_tick,"x":event.point.x,"y":event.point.y})
	var clean=sprites(stage).is_empty()
	stage.queue_free()
	await process_frame
	return {"measurements":{"same_target_arrival_notifications":notifications_ok,"same_target_independent_arrival_lifetimes":identity_ok and geometry_ok and progression_ok and life_ok and clean},"identities_and_destination_multiplicity":identity_ok,"geometry":geometry_ok,"frame_progression":progression_ok,"lifetime_intervals":life_ok,"destination_counts":destination_counts,"hits":records,"events":event_rows,"clean":clean}

func asynchronous_flights(stage) -> Dictionary:
	var launches=[[Vector2(80,80),Vector2(300,180)],[Vector2(520,80),Vector2(360,220)],[Vector2(80,280),Vector2(400,240)]]
	var launch_steps=[0,9,18]
	var nodes: Array=[]
	var births: Array=[]
	var releases=[-1,-1,-1]
	var hit_nodes=[null,null,null]
	var hit_births=[-1,-1,-1]
	var hit_releases=[-1,-1,-1]
	var events_before=events.size()
	var path_ok=true
	var heading_ok=true
	var lifetime_ok=true
	var visible_ok=true
	var hit_ok=true
	for step in range(79):
		if step in launch_steps:
			var index=launch_steps.find(step)
			nodes.append(stage.cast(launches[index][0],launches[index][1]))
			births.append(tick)
		for index in range(nodes.size()):
			var node=nodes[index]
			var age=tick-births[index]
			if alive(node):
				var pair=launches[index]
				var expected=pair[0].lerp(pair[1],clampf(age/30.0,0,1))
				var point=world_anchor(node,Vector2(75,20))
				path_ok=path_ok and point.distance_to(expected)<=0.05 and abs(node.frame-mini(12,int(floor(age/2.0))))<=1
				heading_ok=heading_ok and abs(wrapf(node.global_rotation-(pair[1]-pair[0]).angle(),-PI,PI))<=0.0001
				visible_ok=visible_ok and node.is_visible_in_tree()
				observations.append({"case":"asynchronous_flight","index":index,"birth_tick":births[index],"tick":age,"source_frame":node.frame,"x":point.x,"y":point.y,"instance_id":node.get_instance_id()})
			elif releases[index]<0:releases[index]=age
		# Observe each arrival visual independently of the business-event count.
		for node in sprites(stage):
			if node.animation!="hit":continue
			var point=world_anchor(node,Vector2(79,86))
			var owner=-1
			for index in range(nodes.size()):
				if point.distance_to(launches[index][1])<=0.05:owner=index
			if owner<0:
				hit_ok=false
				continue
			if hit_births[owner]<0:
				hit_births[owner]=tick
				hit_nodes[owner]=node
				hit_ok=hit_ok and abs(tick-births[owner]-30)<=1
			hit_ok=hit_ok and hit_nodes[owner]==node and node.is_visible_in_tree() and abs(node.frame-mini(10,int(floor((tick-hit_births[owner])/2.0))))<=1
			observations.append({"case":"asynchronous_arrival_hit","index":owner,"birth_tick":hit_births[owner],"tick":tick-hit_births[owner],"source_frame":node.frame,"x":point.x,"y":point.y,"instance_id":node.get_instance_id()})
		for index in range(nodes.size()):
			if hit_births[index]>=0 and not alive(hit_nodes[index]) and hit_releases[index]<0:hit_releases[index]=tick-hit_births[index]
		await process_frame
	for age in releases:lifetime_ok=lifetime_ok and age>=29 and age<=31
	for age in hit_releases:hit_ok=hit_ok and age>=21 and age<=23
	hit_ok=hit_ok and sprites(stage).is_empty()
	var matched=[false,false,false]
	var event_ok=events.size()-events_before==3
	var event_rows: Array=[]
	for event in events.slice(events_before):
		var found=false
		for index in range(launches.size()):
			if not matched[index] and event.point.distance_to(launches[index][1])<=0.05 and abs(event.tick-births[index]-30)<=1:
				matched[index]=true
				found=true
				break
		event_ok=event_ok and found
		event_rows.append({"tick":event.tick,"x":event.point.x,"y":event.point.y})
	return {"measurements":{"asynchronous_flight_heading":heading_ok and visible_ok,"asynchronous_flight_path_and_interval":path_ok and lifetime_ok and visible_ok,"asynchronous_arrival_notifications":event_ok,"asynchronous_arrival_visuals_and_reclamation":hit_ok},"birth_ticks":births,"projectile_release_ticks":releases,"hit_birth_ticks":hit_births,"hit_release_ticks":hit_releases,"events":event_rows}

func run():
	var out=OS.get_cmdline_user_args()[0]
	var stage=load("res://stage.tscn").instantiate()
	root.add_child(stage)
	await process_frame
	stage.impact.connect(func(point):events.append({"tick":tick+1,"point":point}))
	var nodes: Array=[]
	var born: Array=[]
	var released: Array=[-1,-1,-1]
	var anchors=[Vector2(200,180),Vector2(205,180),Vector2(210,180)]
	var independent=true
	var hit_anchor=true
	var hit_visible=true
	var hit_timing=true
	for step in range(39):
		if step in [0,6,12]:
			var index=int(step/6)
			var node=stage.spawn_hit(anchors[index])
			for prior in nodes:independent=independent and prior!=node
			nodes.append(node)
			born.append(tick)
		for index in range(nodes.size()):
			var node=nodes[index]
			var age=tick-born[index]
			if alive(node):
				var point=world_anchor(node,Vector2(79,86))
				hit_anchor=hit_anchor and point.distance_to(anchors[index])<=0.05
				hit_visible=hit_visible and node.is_visible_in_tree()
				hit_timing=hit_timing and abs(node.frame-mini(10,int(floor(age/2.0))))<=1
				observations.append({"case":"staggered_hit","index":index,"tick":age,"source_frame":node.frame,"x":point.x,"y":point.y,"instance_id":node.get_instance_id()})
			elif released[index]<0:released[index]=age
		await process_frame
	for age in released:hit_timing=hit_timing and age>=21 and age<=23
	var visual_only=events.is_empty()
	var hit_reclaimed=sprites(stage).is_empty()
	var start_tick=tick
	var launches=[[Vector2(80,80),Vector2(300,180)],[Vector2(520,80),Vector2(300,180)],[Vector2(80,280),Vector2(400,240)]]
	var projectiles: Array=[]
	var projectile_release: Array=[-1,-1,-1]
	var path_ok=true
	var heading_ok=true
	var flight_visible=true
	var flight_lifetime=true
	var arrival_hit_count=-1
	for pair in launches:projectiles.append(stage.cast(pair[0],pair[1]))
	for step in range(58):
		if step==18:
			var before=events.size()
			stage.spawn_hit(Vector2(100,200))
			visual_only=visual_only and events.size()==before
		if step<29:visual_only=visual_only and events.is_empty()
		if step in [31,32]:arrival_hit_count=maxi(arrival_hit_count,count_hits(stage))
		for index in range(projectiles.size()):
			var node=projectiles[index]
			var age=tick-start_tick
			var elapsed=age/60.0
			if alive(node):
				var pair=launches[index]
				var expected=pair[0].lerp(pair[1],clampf(elapsed/0.5,0,1))
				var point=world_anchor(node,Vector2(75,20))
				path_ok=path_ok and point.distance_to(expected)<=0.05
				heading_ok=heading_ok and abs(wrapf(node.global_rotation-(pair[1]-pair[0]).angle(),-PI,PI))<=0.0001
				flight_visible=flight_visible and node.is_visible_in_tree()
				observations.append({"case":"concurrent_flight","index":index,"tick":age,"source_frame":node.frame,"x":point.x,"y":point.y,"instance_id":node.get_instance_id()})
			elif projectile_release[index]<0:projectile_release[index]=age
		await process_frame
	for age in projectile_release:flight_lifetime=flight_lifetime and age>=29 and age<=31
	var matched=[false,false,false]
	var event_ok=events.size()==3
	var event_rows: Array=[]
	for event in events:
		event_rows.append({"tick":event.tick-start_tick,"x":event.point.x,"y":event.point.y})
		var found=false
		for index in range(launches.size()):
			if not matched[index] and event.point.distance_to(launches[index][1])<=0.05 and abs(event.tick-start_tick-30)<=1:
				matched[index]=true
				found=true
				break
		event_ok=event_ok and found
	var values={"hit_identity":independent,"hit_anchor":hit_anchor,"hit_visible":hit_visible,"hit_interval_and_reclamation":hit_timing and hit_reclaimed,"visual_only":visual_only,"flight_heading":heading_ok and flight_visible,"flight_path_and_interval":path_ok and flight_lifetime and flight_visible,"arrival_notifications":event_ok,"arrival_visuals_and_reclamation":arrival_hit_count==4 and sprites(stage).is_empty()}
	var asynchronous=await asynchronous_flights(stage)
	values.merge(asynchronous.measurements)
	stage.queue_free()
	await process_frame
	var simultaneous=await simultaneous_arrival_lifetimes()
	values.merge(simultaneous.measurements)
	var passed=true
	for value in values.values():passed=passed and value
	var file=FileAccess.open(out,FileAccess.WRITE)
	file.store_string(JSON.stringify({"passed":passed,"measurements":values,"hit_release_ticks":released,"projectile_release_ticks":projectile_release,"arrival_hit_count":arrival_hit_count,"events":event_rows,"asynchronous_flights":asynchronous,"same_target_simultaneous_arrivals":simultaneous,"observations":observations},"  ")+"\n")
	file.close()
	quit(0 if passed else 1)

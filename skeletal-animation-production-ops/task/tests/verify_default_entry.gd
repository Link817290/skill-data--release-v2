extends SceneTree
var elapsed=0.0
var origin=0.0
var events: Array=[]
var samples: Array=[]

func _process(delta):
	elapsed+=delta
	return false

func _initialize():call_deferred("run")

func sprites(parent) -> Array:
	var found: Array=[]
	for child in parent.get_children():
		if child is AnimatedSprite2D:found.append(child)
		found.append_array(sprites(child))
	return found

func run():
	var path=OS.get_cmdline_user_args()[0]
	var main=ProjectSettings.get_setting("application/run/main_scene","")
	var stage=load(main).instantiate()
	origin=elapsed
	# Observe the actual configured scene with its ordinary demo enabled. The
	# independent SceneTree delta clock does not use candidate-private metadata.
	stage.impact.connect(func(point):events.append({"seconds":elapsed-origin,"x":point.x,"y":point.y}))
	root.add_child(stage)
	var clean_at_two=false
	var sampled_two=false
	for step in range(123):
		var time=elapsed-origin
		var observed: Array=[]
		for node in sprites(stage):observed.append({"kind":str(node.animation),"frame":node.frame,"instance_id":node.get_instance_id(),"global_x":node.global_position.x,"global_y":node.global_position.y})
		samples.append({"seconds":time,"sprites":observed})
		if not sampled_two and time>=2.0-0.00000001:
			clean_at_two=observed.is_empty()
			sampled_two=true
		await process_frame
	var expected=[0.65,0.95]
	var rows: Array=[]
	var correct=0
	var count_and_destinations=events.size()==2
	for index in range(2):
		var exists=index<events.size()
		var destination=exists and Vector2(events[index].x,events[index].y).distance_to(Vector2(480,190))<=0.05
		var timely=exists and abs(events[index].seconds-expected[index])<=1.0/60.0+0.000001
		count_and_destinations=count_and_destinations and destination
		if destination and timely:correct+=1
		rows.append({"event_index":index,"expected_seconds":expected[index],"observed_seconds":events[index].seconds if exists else null,"destination_correct":destination,"within_one_sampling_interval":timely})
	var file=FileAccess.open(path,FileAccess.WRITE)
	file.store_string(JSON.stringify({"configured_main_scene":main,"normal_entry_no_verification_flag":not OS.get_cmdline_user_args().has("--verification"),"independent_clock":"SceneTree._process(delta)","sampling_hz":60,"end_time_tolerance_seconds":1.0/60.0,"events":events,"timing_items":rows,"timing_completion":correct/2.0 if events.size()==2 else 0.0,"count_and_destinations_correct":count_and_destinations,"clean_at_two_seconds":clean_at_two,"usable_default_stage":count_and_destinations and clean_at_two,"observations":samples},"  ")+"\n")
	file.close()
	quit(0)

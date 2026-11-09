// Observations remain intact; this ledger owns numeric severity and causal deduplication.
export function settle(items,damages,params){
 const W=params.weights,cfg=params.damage;
 const failed=new Map();
 for(const [id,item]of Object.entries(items))if(Array.isArray(item.checks)&&id!=='P10')for(let i=0;i<item.checks.length;i++)if(item.checks[i]?.passed===false)failed.set(id+'.'+i,(W[id]||0)/2);
 const raw=Object.entries(W).reduce((s,[id,w])=>s+w*items[id].completion,0);
 const claimed=new Set(),events=[],deduplicated=[];let positive=raw;
 // One observation per global operation. Within it keep only the largest ordinary loss.
 for(const id of ['full_frame_effect','visual_system_switching']){
  const d=damages[id];if(!d||d.occurred!==true)continue;
  const refs=d.affected_checks.filter(k=>failed.has(k)&&!claimed.has(k));refs.forEach(k=>claimed.add(k));
  const losses=refs.map(k=>failed.get(k)),sum=losses.reduce((a,b)=>a+b,0),loss=losses.length?Math.max(...losses):0;
  positive+=sum-loss;deduplicated.push({key:id,check_ids:refs,raw_loss:sum,kept_loss:loss,restored_duplicate_loss:sum-loss});
  if(d.evidence_span_seconds>=cfg.sustained_visual_seconds&&new Set(d.frame_ids).size>=cfg.minimum_visual_frames)events.push({key:id,item:'D-sustained-visual-disruption',coefficient:cfg.sustained_visual_coefficient,replaced_positive_loss:loss,check_ids:refs,evidence_span_seconds:d.evidence_span_seconds,frame_ids:d.frame_ids});
 }
 // These two reversals carry the screenplay's central small-change/complete-rework joke and ending.
 const coreRefs=['P02.1','P04.1'].filter(k=>failed.has(k));
 if(coreRefs.length){
  const refs=[...failed.keys()].filter(k=>/^P0[1-4]\./.test(k)||/^P09\./.test(k)||/^P13\./.test(k));
  events.push({key:'core-story',item:'D-core-story-failure',coefficient:cfg.core_story_coefficient,replaced_positive_loss:refs.reduce((s,k)=>s+failed.get(k),0),check_ids:refs,trigger_check_ids:coreRefs});
 }
 // Each incorrect role assignment is one independent decision; repeated frames/scenes are not new decisions.
 let castingLossRestored=false;
 for(const id of cfg.casting_roles||[]){
  const d=damages[id];if(d?.occurred!==true)continue;
  const refs=!castingLossRestored&&failed.has('P05.0')?['P05.0']:[];
  const loss=refs.reduce((sum,k)=>sum+failed.get(k),0);if(refs.length)castingLossRestored=true;
  events.push({key:id,item:'D-wrong-role-selection',coefficient:cfg.casting_coefficient,replaced_positive_loss:loss,check_ids:refs,frame_ids:d.frame_ids});
 }
 const restored=events.reduce((s,e)=>s+e.replaced_positive_loss,0),basis=Math.min(1,positive+restored),retention=events.reduce((p,e)=>p*e.coefficient,1);
 // Credit loss and its causal damage replacement compete; they are not added twice.
 const reward=Math.max(0,Math.min(positive,basis*retention));
 const round=x=>Number(x.toFixed(6));
 return {reward:round(reward),raw_positive:round(raw),positive_earned:round(positive),damage_basis:round(basis),retention:round(retention),damage_instances:events,deduplicated_losses:deduplicated,settlement:'min(positive_earned, damage_basis * retention)',note:'Damage basis restores only the positive loss owned by charged events; the positive-earned ceiling prevents restoration from improving a damaged artifact.'};
}

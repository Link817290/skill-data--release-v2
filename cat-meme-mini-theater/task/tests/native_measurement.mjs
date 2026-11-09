import fs from 'node:fs';
import path from 'node:path';
import {readJson,sha,projectHash,inspectMedia} from './media-utils.mjs';
import {compareMedia} from './source-correspondence.mjs';
import {reproduce} from './rerender.mjs';
import {judge} from './llm_judge/runtime/judge.mjs';
import {applyResolution,resolveFresh} from './llm_judge/resolution.mjs';
import {settle} from './settle.mjs';
const HERE=import.meta.dirname,params=readJson(path.join(HERE,'measurement_params.json'));
const args=process.argv.slice(2),get=(name,fallback)=>args.includes(name)?args[args.indexOf(name)+1]:fallback;
const workspace=path.resolve(args[0]||'/workspace'),logDir=path.resolve(args[1]||'/logs/verifier');
const artifact=get('--artifact',path.join(workspace,'output'));fs.mkdirSync(logDir,{recursive:true});
const write=(name,v)=>fs.writeFileSync(path.join(logDir,name),JSON.stringify(v,null,2)+'\n');
const started=new Date().toISOString(),checks={},items={},errors=[];let media,semantic,proof,comparison;
// A killed/erroring rerun must not leave an earlier numeric reward behind.
write('reward.json',{status:'verifying',reward:null,started});
write('reward_detail.json',{status:'verifying',reward:null,started});
for(const name of ['reward.txt','reward_strict.txt']){const p=path.join(logDir,name);if(fs.existsSync(p))fs.unlinkSync(p);}
const file=p=>fs.existsSync(p)&&fs.statSync(p).isFile()&&fs.statSync(p).size>0;
function planShape(){
 const plan=readJson(path.join(artifact,'edit-plan.json'));
 const rows=Array.isArray(plan)?plan:plan.shots||plan.scenes||plan.timeline;
 if(!Array.isArray(rows)||!rows.length)return false;
 let last=0;
 for(const r of rows){
  const start=r.start??r.start_seconds??(r.frame_range?.[0]/30),end=r.end??r.end_seconds??(r.frame_range?.[1]/30);
  if(!Number.isFinite(start)||!Number.isFinite(end)||start<0||end<=start||start>last+0.1||end>40.1||end<last)return false;
  if(!Object.entries(r).some(([k,v])=>!['id','start','end','start_seconds','end_seconds','frame_range'].includes(k)&&v&&typeof v==='string'&&v.trim()))return false;
  last=end;
 }
 return last>=39.9;
}
function trustedProof(p){
 const abs=fs.realpathSync(p),base=fs.realpathSync(artifact);if(abs===base||abs.startsWith(base+path.sep))throw new Error('Rerender proof must be verifier-owned, outside candidate artifact');
 const value=readJson(p);if(value.project_sha256!==projectHash(path.join(artifact,'project')))throw new Error('Rerender proof project hash mismatch');
 if(value.status==='passed'&&(!file(value.output)||sha(value.output)!==value.output_sha256))throw new Error('Rerender output hash mismatch');return value;
}
let fatal=false,infrastructure=false;
try{
 if(!file(path.join(artifact,'final.mp4')))throw new Error('Missing or empty final.mp4');
 media=inspectMedia(path.join(artifact,'final.mp4'),params);
 Object.assign(checks,{readable_video:true,video_spec:media.video_spec,full_decode:true,visual_content:media.visual_content,audible_audio:media.audible_audio});
 if(!media.visual_content){fatal=true;errors.push('All decoded frames are black');}
}catch(e){fatal=!e.infrastructure;infrastructure=!!e.infrastructure;errors.push(e.message);checks.readable_video=false;}
if(!fatal&&!infrastructure){
 try{checks.edit_plan=planShape();}catch(e){checks.edit_plan=false;errors.push('Edit plan: '+e.message);}
 const project=path.join(artifact,'project');
 try{
  const pkg=readJson(path.join(project,'package.json'));
  checks.project=!!pkg.scripts?.render&&!!(pkg.dependencies?.remotion||pkg.devDependencies?.remotion);
  if(!checks.project)checks.rerender=false;
  else if(get('--rerender-proof',process.env.RERENDER_PROOF_FILE)){
   proof=trustedProof(get('--rerender-proof',process.env.RERENDER_PROOF_FILE));
  }else if(args.includes('--execute-project')){
   proof=reproduce(project,path.join(logDir,'rerender-'+Date.now()),{runtimeModules:get('--runtime-modules',process.env.REMOTION_RUNTIME_MODULES)});
  }
  if(proof){if(proof.status==='passed'){comparison=compareMedia(path.join(artifact,'final.mp4'),proof.output,params);checks.rerender=comparison.passed;}else checks.rerender=false;}
 }catch(e){errors.push('Project: '+e.message);if(e.infrastructure)infrastructure=true;else if(!checks.project)checks.rerender=false;}
 const a=media.audio;
 // Signal checks do not establish subjective listening quality.
 const audioChecks=[a.active_seconds>=4&&a.active_quarters>=3,a.samples>0&&a.peak>params.measurement.audio_peak_floor&&a.clipped_fraction<0.0001];
 items.P10={completion:audioChecks.filter(Boolean).length/2,owner:'program-audio-signal',checks:audioChecks,evidence:a,unmeasured:'Aesthetic fit, masking, and subjective listening quality.'};
 items.P12={completion:Number(checks.video_spec&&checks.full_decode),owner:'program-media'};
 try{semantic=await judge({mode:get('--judge-mode',process.env.LLM_JUDGE_MODE||'replay'),artifact,output:path.join(logDir,'semantic'),cacheDir:get('--cache-dir',process.env.LLM_JUDGE_CACHE||path.join(HERE,'llm_judge/cache')),refresh:args.includes('--refresh')});}catch(e){semantic={status:'judge_error',error:e.message};}
 if(semantic.status==='needs_review'){
  try{
   const cache=get('--cache-dir',process.env.LLM_JUDGE_CACHE||path.join(HERE,'llm_judge/cache'));
   semantic=applyResolution(semantic,artifact,cache);
   if(semantic.status==='needs_review'&&(args.includes('--refresh')||process.env.RESOLVE_VISUAL_UNCERTAINTY==='1'))semantic=await resolveFresh({semantic,artifact,cacheDir:cache});
  }
  catch(error){semantic={...semantic,status:'judge_error',error:error.message};}
 }
 if(semantic.resolution)write('visual-resolution.json',semantic.resolution);
 write('effective-semantic-result.json',semantic);
 if(semantic.items)for(const [id,item]of Object.entries(semantic.items))if(id!=='P11_plan')items[id]={...item,owner:'visual-semantic'};
 const planCompletion=checks.edit_plan?semantic.items?.P11_plan?.completion:null;
 const planValue=checks.edit_plan?planCompletion:0;
 items.P11={completion:checks.rerender===undefined||planValue==null?null:(Number(checks.rerender)+planValue)/2,owner:'program-rerender-and-semantic-plan',plan_completion:planValue,rerender:checks.rerender??null,comparison};
}
const missing=Object.keys(params.weights).filter(id=>items[id]?.completion==null);
const earned=Object.entries(params.weights).reduce((sum,[id,w])=>sum+w*(items[id]?.completion??0),0);
const unknownDamage=!fatal&&!infrastructure&&semantic?.status!=='measured';
const status=fatal?'invalid_delivery':infrastructure?'infrastructure_error':missing.length||unknownDamage?'awaiting_review':'measured';
const settlement=status==='measured'?settle(items,semantic.damages,params):null;
const reward=fatal?0:status==='measured'?settlement.reward:null;
const semanticCheck=(id,index)=>semantic?.items?.[id]?.checks?.[index]?.passed??null;
const mustHave={
 media_delivery:checks.readable_video===true&&checks.video_spec===true&&checks.full_decode===true,
 reproducible_project:checks.project===true&&checks.rerender===true,
 truthful_plan:checks.edit_plan===true?semanticCheck('P11_plan',0)===true&&semanticCheck('P11_plan',1)===true:false,
 story:status==='measured'?['P01','P02','P03','P04'].every(id=>[0,1].every(i=>semanticCheck(id,i)===true)):null,
 intended_cast:semanticCheck('P05',0),developing_performance:semanticCheck('P05',1),
 readable_dialogue:status==='measured'?[0,1].every(i=>semanticCheck('P08',i)===true):null,
 required_visual_devices:semanticCheck('P15',0),audible_audio:checks.audible_audio===true,
};
const lenient=fatal?0:status==='measured'?Number(Object.values(mustHave).every(value=>value===true)):null;
const result={version:params.version,status,reward,reward_strict:reward,reward_lenient:lenient,rewards:{strict:reward,lenient},must_have:mustHave,settlement,scope:'Automated sampled-visual/content, signal-audio, reproducibility, and technical score. Not a subjective audio-listening score.',items,weights:params.weights,checks,errors,missing_items:missing,measured_earned:Number(earned.toFixed(6)),unmeasured_weight:Number(missing.reduce((s,id)=>s+params.weights[id],0).toFixed(6)),semantic_status:semantic?.status,semantic_error:semantic?.error,rerender_verified:checks.rerender===true,media,started,finished:new Date().toISOString()};
write('reward.json',result);write('reward_detail.json',result);
for(const name of ['reward.txt','reward_strict.txt']){const dest=path.join(logDir,name);if(reward!==null)fs.writeFileSync(dest,String(reward)+'\n');else if(fs.existsSync(dest))fs.unlinkSync(dest);}
const lenientPath=path.join(logDir,'reward_lenient.txt');
if(lenient!==null)fs.writeFileSync(lenientPath,String(lenient)+'\n');else if(fs.existsSync(lenientPath))fs.unlinkSync(lenientPath);
write('execution.json',{command:process.argv,working_directory:process.cwd(),started,finished:result.finished,platform:process.platform,node:process.version,status,exit_code:reward===null?2:0,reward_sha256:sha(path.join(logDir,'reward.json'))});
console.log(JSON.stringify({status,reward,checks,missing_items:missing,errors,semantic_status:semantic?.status,semantic_error:semantic?.error},null,2));process.exitCode=reward===null?2:0;

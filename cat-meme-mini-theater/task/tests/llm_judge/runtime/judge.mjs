import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import http from 'node:http';
import https from 'node:https';
import {readJson,sha,digest,run,projectHash,projectFiles} from '../../media-utils.mjs';
import {motionEvidence} from './motion.mjs';
export const HERE=path.resolve(import.meta.dirname,'..');
const TASK=path.resolve(HERE,'../..');
const FRESH_MAX_ATTEMPTS=4;
const write=(p,v)=>{fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,JSON.stringify(v,null,2)+'\n');};
const exists=p=>fs.existsSync(p)&&fs.statSync(p).isFile();
export function binding(artifact){
 const settings=readJson(path.join(HERE,'settings.json'));
 settings.model=process.env.LLM_JUDGE_MODEL||settings.model;
 const timeout=Number(process.env.LLM_JUDGE_TIMEOUT_SECONDS||process.env.LLM_JUDGE_TIMEOUT_SEC||600);if(!(timeout>0&&timeout<=3600))throw new Error('LLM_JUDGE_TIMEOUT_SECONDS must be in (0, 3600]');settings.timeout_ms=timeout*1000;
 const files=['contract.json','prompt.md','response.schema.json','settings.json','runtime/judge.mjs','runtime/motion.mjs','../media-utils.mjs'];
 return {version:readJson(path.join(HERE,'contract.json')).version,video_sha256:sha(path.join(artifact,'final.mp4')),plan_sha256:exists(path.join(artifact,'edit-plan.json'))?sha(path.join(artifact,'edit-plan.json')):null,project_sha256:fs.existsSync(path.join(artifact,'project'))?projectHash(path.join(artifact,'project')):null,context:Object.fromEntries(['instruction.md','environment/workspace/materials/screenplay.txt','environment/workspace/source_manifest.json'].map(p=>[p,sha(path.join(TASK,p))])),runtime:Object.fromEntries(files.map(p=>[p,sha(path.join(HERE,p))])),settings};
}
export function validateDecision(reply,frames,contract){
 const exact=(obj,keys)=>obj&&typeof obj==='object'&&!Array.isArray(obj)&&Object.keys(obj).sort().join('|')===[...keys].sort().join('|');
 if(!exact(reply,['items','damages'])||!exact(reply.items,Object.keys(contract.items)))throw new Error('Unexpected or missing response item IDs');
 const validIds=new Set(frames.map(f=>f.id));const items={};
 for(const [id,item] of Object.entries(reply.items)){
  if(!exact(item,['checks'])||!Array.isArray(item.checks)||item.checks.length!==2)throw new Error(`${id}: exactly two checks required`);
  for(const c of item.checks){
   if(!exact(c,['passed','frame_ids','evidence','rationale'])||![true,false,null].includes(c.passed)||!Array.isArray(c.frame_ids)||!c.frame_ids.length||c.frame_ids.some(n=>!Number.isInteger(n)||!validIds.has(n))||typeof c.evidence!=='string'||!c.evidence.trim()||typeof c.rationale!=='string'||!c.rationale.trim())throw new Error(`${id}: invalid evidence or completion`);
  }
  items[id]={completion:item.checks.some(c=>c.passed===null)?null:item.checks.filter(c=>c.passed).length/2,checks:item.checks};
 }
 if(!exact(reply.damages,Object.keys(contract.damage_criteria)))throw new Error('Unexpected damage owners');
 const damages={};const times=new Map(frames.map(f=>[f.id,f.time_seconds]));
 for(const [id,d]of Object.entries(reply.damages)){
  const allowed=contract.damage_criteria[id].affected_checks;
  if(!exact(d,['occurred','frame_ids','affected_checks','evidence','rationale'])||![true,false,null].includes(d.occurred)||!Array.isArray(d.frame_ids)||!d.frame_ids.length||d.frame_ids.some(f=>!Number.isInteger(f)||!validIds.has(f))||!Array.isArray(d.affected_checks)||new Set(d.affected_checks).size!==d.affected_checks.length||d.affected_checks.some(k=>!allowed.includes(k))||typeof d.evidence!=='string'||!d.evidence.trim()||typeof d.rationale!=='string'||!d.rationale.trim())throw new Error(id+': invalid damage evidence');
  if(d.occurred===false&&d.affected_checks.length)throw new Error(id+': absent damage has affected checks');
  const minimumFrames=contract.damage_criteria[id].minimum_evidence_frames??3;
  if(d.occurred===true&&new Set(d.frame_ids).size<minimumFrames)throw new Error(id+': insufficient observed frames');
  if(id.startsWith('cast_')&&d.occurred===true&&(d.affected_checks.length!==1||d.affected_checks[0]!=='P05.0'))throw new Error(id+': casting must bind the failed selection check');
  for(const ref of d.affected_checks){const [item,index]=ref.split('.');if(items[item].checks[Number(index)].passed!==false)throw new Error(id+': affected check was not failed');}
  const ts=d.frame_ids.map(f=>times.get(f));damages[id]={...d,evidence_span_seconds:Math.max(...ts)-Math.min(...ts)};
 }
 return {items,damages,status:Object.values(items).some(x=>x.completion===null)||Object.values(damages).some(x=>x.occurred===null)?'needs_review':'measured'};
}
function ensureOutside(child,artifact){
 const base=fs.realpathSync(artifact),resolved=path.resolve(child);
 if(resolved===path.resolve(artifact)||resolved.startsWith(path.resolve(artifact)+path.sep)||resolved===base||resolved.startsWith(base+path.sep))throw new Error('Verifier output/cache must be outside the candidate artifact');
 // Inspect the nearest existing ancestor to reject a junction back into the artifact.
 let parent=resolved;while(!fs.existsSync(parent)){const next=path.dirname(parent);if(next===parent)break;parent=next;}
 const real=fs.realpathSync(parent);if(real===base||real.startsWith(base+path.sep))throw new Error('Verifier path points into candidate artifact');
}
function extract(artifact,dest,settings){
 fs.mkdirSync(dest,{recursive:true});const video=path.join(artifact,'final.mp4');
 const probe=JSON.parse(run('ffprobe',['-v','error','-show_streams','-show_format','-of','json',video],{encoding:'utf8'}).stdout);
 const duration=Number(probe.format.duration);if(!Number.isFinite(duration)||duration<=0||duration>settings.extraction.max_seconds)throw new Error('Film duration outside extraction limit');
 const {fps,width}=settings.extraction;
 const stream=probe.streams.find(s=>s.codec_type==='video'),[n,d]=stream.r_frame_rate.split('/').map(Number),sourceFps=n/d,step=Math.max(1,Math.round(sourceFps/fps));
 if(!Number.isFinite(sourceFps)||sourceFps<=0)throw new Error('Invalid video frame rate');
 run('ffmpeg',['-v','error','-y','-i',video,'-an','-vf',`select='not(mod(n,${step}))',scale=${width}:-2`,'-fps_mode','vfr','-q:v','3',path.join(dest,'frame-%04d.jpg')]);
 const frames=fs.readdirSync(dest).filter(n=>/^frame-\d+.jpg$/.test(n)).sort().map((name,index)=>({id:index,time_seconds:Number((index*step/sourceFps).toFixed(6)),file:name,sha256:sha(path.join(dest,name))}));
 if(!frames.length)throw new Error('No frames extracted');
 const motion=motionEvidence(video,dest,sourceFps,settings,frames.length);frames.push(...motion.frames);
 const sourceRoot=path.join(TASK,'environment/workspace'),manifest=readJson(path.join(sourceRoot,'source_manifest.json'));
 const refs=[];
 for(const [index,entry] of manifest.files.filter(x=>/\.(mp4|jpe?g|png)$/i.test(x.file)).entries()){
  const input=path.join(sourceRoot,entry.file);if(sha(input)!==entry.sha256)throw new Error('Source manifest mismatch');
  const name=`source-${String(index).padStart(2,'0')}.jpg`,isVideo=/\.mp4$/i.test(input);
  const filter=isVideo?`fps=1,scale=${settings.extraction.source_preview_width}:-2,tile=4x1`:`scale=${settings.extraction.source_preview_width}:-2`;
  run('ffmpeg',['-v','error','-y','-i',input,'-frames:v','1','-vf',filter,'-q:v','4',path.join(dest,name)]);
  refs.push({source_id:index,source:entry.file,file:name,sha256:sha(path.join(dest,name)),preview:isVideo?'Four chronological 1 fps source samples in a horizontal strip; short clips may leave empty final cells. Source crops can change during the clip.':'Single original still image.'});
 }
 // Responses limits image inputs to 100. Keep every source preview addressable in
 // the metadata, but send one deterministic contact sheet for the source pool.
 if(refs.length){
  const sheet=path.join(dest,'source-sheet.jpg');
  const columns=5,rows=Math.ceil(refs.length/columns);
  run('ffmpeg',['-v','error','-y','-pattern_type','glob','-i',path.join(dest,'source-*.jpg'),'-vf',`tile=${columns}x${rows}:padding=8:margin=8`,'-frames:v','1','-q:v','3',sheet]);
 }
 const result={duration,frames,references:refs,source_sheet:refs.length?'source-sheet.jpg':null,motion_sheets:motion.sheets,motion_selection:motion.selection,motion_fps:motion.actual_sample_fps};write(path.join(dest,'index.json'),result);return result;
}
function requestBody(artifact,assets,dest,settings,contract){
 let plan;try{plan=readJson(path.join(artifact,'edit-plan.json'));}catch{plan={error:'Missing or invalid edit plan'};}
 const source=fs.readFileSync(path.join(TASK,'environment/workspace/materials/screenplay.txt'),'utf8');
 const instruction=fs.readFileSync(path.join(TASK,'instruction.md'),'utf8');
 const inventory=fs.existsSync(path.join(artifact,'project'))?projectFiles(path.join(artifact,'project')).map(f=>path.relative(path.join(artifact,'project'),f).replaceAll('\\','/')):[];
 let aliases;try{aliases=readJson(path.join(artifact,'project/src/assets.json'));}catch{aliases=null;}
 const content=[{type:'input_text',text:JSON.stringify({brief:instruction,screenplay:source,criteria:contract.items,damage_criteria:contract.damage_criteria,candidate_edit_plan:plan,candidate_project_inventory:inventory,candidate_asset_aliases:aliases,sampling:{fps:settings.extraction.fps,duration:assets.duration},film_frames:assets.frames,source_previews:assets.references})}];
 for(const f of assets.frames.filter(f=>f.kind!=='motion')){content.push({type:'input_text',text:`FILM frame ${f.id}, time ${f.time_seconds.toFixed(3)} seconds`},{type:'input_image',detail:'high',image_url:'data:image/jpeg;base64,'+fs.readFileSync(path.join(dest,f.file)).toString('base64')});}
 for(const sheet of assets.motion_sheets){content.push({type:'input_text',text:`DENSE MOTION WINDOW ${sheet.window}. Read cells left to right, top to bottom in a 4-column grid. Each cell is one FILM frame. Sample rate ${assets.motion_fps} fps. Cells: ${JSON.stringify(sheet.cells)}`},{type:'input_image',detail:'high',image_url:'data:image/jpeg;base64,'+fs.readFileSync(path.join(dest,sheet.file)).toString('base64')});}
 for(const f of assets.references){content.push({type:'input_text',text:`SOURCE ${f.source_id}: ${f.source}. ${f.preview}. The source preview is tile ${f.source_id} in source-sheet.jpg, laid out left-to-right in rows of five.`});}
 if(assets.source_sheet)content.push({type:'input_image',detail:'high',image_url:'data:image/jpeg;base64,'+fs.readFileSync(path.join(dest,assets.source_sheet)).toString('base64')});
 if(content.filter(part=>part.type==='input_image').length>100)throw new Error('Visual judge request exceeds the provider image-input limit');
 return {model:settings.model,store:false,reasoning:{effort:settings.reasoning_effort},max_output_tokens:settings.max_output_tokens,instructions:fs.readFileSync(path.join(HERE,'prompt.md'),'utf8'),input:[{role:'user',content}],text:{format:{type:'json_schema',name:'cat_film_review',strict:true,schema:readJson(path.join(HERE,'response.schema.json'))}}};
}
function parseResponse(raw){
 let data;try{data=JSON.parse(raw);}catch{throw new Error('Provider did not return JSON');}
 if(data.status!=='completed')throw new Error(`Provider response status: ${data.status||'missing'}`);
 const text=data.output?.flatMap(x=>x.content||[]).filter(x=>x.type==='output_text').map(x=>x.text).join('');
 if(!text)throw new Error('Provider returned no output text');
 return {data,reply:JSON.parse(text)};
}
function responsesUrl(baseUrl){
 const url=new URL(baseUrl);if(!['http:','https:'].includes(url.protocol)||url.username||url.password||url.search)throw new Error('LLM_JUDGE_BASE_URL must be an HTTP(S) URL without credentials or query parameters');
 const clean=url.pathname.replace(/\/$/,'');
 if(clean.endsWith('/v1'))url.pathname=clean+'/responses';
 else if(!clean.endsWith('/v1/responses'))url.pathname=clean+'/v1/responses';
 return url;
}
export async function judge({mode,artifact,output,cacheDir,refresh=false,endpoint=process.env.LLM_JUDGE_BASE_URL}){
 artifact=path.resolve(artifact);output=path.resolve(output);cacheDir=path.resolve(cacheDir);
 ensureOutside(output,artifact);ensureOutside(cacheDir,artifact);fs.mkdirSync(output,{recursive:true});
 const started=new Date().toISOString(),contract=readJson(path.join(HERE,'contract.json'));
 let result,record,callId,key;
 try{
  if(!['fresh','replay'].includes(mode))throw new Error('Mode must be fresh or replay');
  const b=binding(artifact),settings=b.settings;key=digest(b);const cache=path.join(cacheDir,key);
  if(mode==='replay'){
   const pointer=readJson(path.join(cache,'selected.json'));callId=pointer.call_id;
   if(!/^[\w-]+$/.test(callId))throw new Error('Invalid cache call ID');record=path.join(cache,callId);
   const request=readJson(path.join(record,'request.json')),validation=readJson(path.join(record,'validation.json'));
   if(digest(request.binding)!==key||!validation.valid||sha(path.join(record,'request.json'))!==validation.request_sha256||sha(path.join(record,'response.json'))!==validation.response_sha256)throw new Error('Cache binding or integrity mismatch');
   const {data,reply}=parseResponse(fs.readFileSync(path.join(record,'response.json'),'utf8'));
   const decision=validateDecision(reply,request.extraction.frames,contract);
   if(digest(decision)!==digest(readJson(path.join(record,'decision.json'))))throw new Error('Cached decision differs from response');
   result={...decision,version:contract.version,binding:b,cache_key:key,call_id:callId,mode,returned_model:data.model,record};
  }else{
   if(!refresh)throw new Error('Fresh requires --refresh; recorded judgments are never silently replaced');
   if(!endpoint)throw new Error('Set LLM_JUDGE_BASE_URL to the Responses URL');
   const url=responsesUrl(endpoint);
   const apiKey=process.env.LLM_JUDGE_API_KEY;if(!apiKey)throw new Error('Set LLM_JUDGE_API_KEY in the trusted host environment');
   const batchId=Date.now()+'-'+crypto.randomUUID(),frameDir=path.join(output,'frames',batchId),extraction=extract(artifact,frameDir,settings),body=requestBody(artifact,extraction,frameDir,settings,contract);
   for(let attempt=1;attempt<=FRESH_MAX_ATTEMPTS;attempt++){
    const attemptStarted=new Date().toISOString();callId=Date.now()+'-'+crypto.randomUUID();record=path.join(cache,callId);fs.mkdirSync(record,{recursive:true});
    write(path.join(record,'request.json'),{binding:b,endpoint:url.toString(),extraction,body});
    try{
     const response=await new Promise((resolve,reject)=>{
      const transport=url.protocol==='https:'?https:http;
      const request=transport.request(url,{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+apiKey}},res=>{let text='';res.setEncoding('utf8');res.on('data',chunk=>text+=chunk);res.on('end',()=>resolve({ok:res.statusCode>=200&&res.statusCode<300,status:res.statusCode,text}));res.on('error',reject);});
      const timer=setTimeout(()=>request.destroy(new Error('Judge request timeout')),settings.timeout_ms);request.on('close',()=>clearTimeout(timer));request.on('error',reject);request.end(JSON.stringify(body));
     });
     const raw=response.text.replaceAll(apiKey,'[REDACTED]');fs.writeFileSync(path.join(record,'response.json'),raw);
     if(!response.ok)throw new Error(`Provider HTTP ${response.status}; raw response preserved`);
     const {data,reply}=parseResponse(raw),decision=validateDecision(reply,extraction.frames,contract);
     if(digest(binding(artifact))!==key)throw new Error('Artifact or judge changed while the model was running');
     write(path.join(record,'decision.json'),decision);
     write(path.join(record,'validation.json'),{valid:true,started:attemptStarted,finished:new Date().toISOString(),attempt,max_attempts:FRESH_MAX_ATTEMPTS,request_sha256:sha(path.join(record,'request.json')),response_sha256:sha(path.join(record,'response.json')),evidence_validation:'Exact schema, item IDs, two binary/null checks, nonempty descriptions, existing frame IDs. Visual claims require audit; no OCR truth claim.',returned_model:data.model,response_id:data.id,usage:data.usage});
     write(path.join(cache,'selected.json'),{call_id:callId});
     result={...decision,version:contract.version,binding:b,cache_key:key,call_id:callId,mode,returned_model:data.model,record};break;
    }catch(error){
     const validation={valid:false,started:attemptStarted,finished:new Date().toISOString(),attempt,max_attempts:FRESH_MAX_ATTEMPTS,error:error.message,request_sha256:sha(path.join(record,'request.json'))};
     if(fs.existsSync(path.join(record,'response.json')))validation.response_sha256=sha(path.join(record,'response.json'));
     write(path.join(record,'validation.json'),validation);if(attempt===FRESH_MAX_ATTEMPTS)throw error;
    }
   }
  }
 }catch(error){
  result={status:'judge_error',version:contract.version,mode,cache_key:key,call_id:callId,error:error.message};
  if(mode==='fresh'&&record&&fs.existsSync(record)&&!fs.existsSync(path.join(record,'validation.json')))write(path.join(record,'validation.json'),{valid:false,started,finished:new Date().toISOString(),error:error.message});
 }
 write(path.join(output,'llm_judge_result.json'),result);return result;
}
if(process.argv[1]&&path.resolve(process.argv[1])===path.resolve(import.meta.filename)){
 const args=process.argv.slice(2),get=name=>args[args.indexOf(name)+1];
 try{const result=await judge({mode:get('--mode'),artifact:get('--artifact'),output:get('--output'),cacheDir:args.includes('--cache-dir')?get('--cache-dir'):path.join(HERE,'cache'),refresh:args.includes('--refresh')});console.log(JSON.stringify({status:result.status,call_id:result.call_id,cache_key:result.cache_key,error:result.error,items:result.items&&Object.fromEntries(Object.entries(result.items).map(([id,x])=>[id,x.completion]))},null,2));process.exitCode=result.status==='measured'?0:2;}catch(e){console.error(e.message);process.exitCode=2;}
}

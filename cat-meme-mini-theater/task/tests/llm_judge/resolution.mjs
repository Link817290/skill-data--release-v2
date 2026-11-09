import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import http from 'node:http';
import https from 'node:https';
import {readJson,sha,digest,run} from '../media-utils.mjs';

const write=(file,value)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(value,null,2)+'\n');};
const protocol='native-frame-uncertainty-resolution-v1';
const exact=(value,keys)=>value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).sort().join('|')===[...keys].sort().join('|');
function binding(semantic,artifact){
 return {protocol,primary_cache_key:semantic.cache_key,primary_call_id:semantic.call_id,
  video_sha256:sha(path.join(artifact,'final.mp4')),runtime_sha256:sha(import.meta.filename)};
}
export function unknownChecks(semantic){
 return Object.entries(semantic.items||{}).flatMap(([item,value])=>value.checks.flatMap((check,index)=>check.passed===null?[`${item}.${index}`]:[]));
}
function parse(raw){
 const value=typeof raw==='string'?JSON.parse(raw):raw;
 if(value.status!=='completed'||value.error)throw new Error('Resolution response incomplete');
 const texts=value.output?.flatMap(item=>item.content||[]).filter(item=>item.type==='output_text');
 if(texts?.length!==1)throw new Error('Exactly one resolution response required');
 return {provider:value,decision:JSON.parse(texts[0].text)};
}
export function validateResolution(decision,unknown,frames,extraFrames){
 if(!exact(decision,['resolutions'])||!Array.isArray(decision.resolutions))throw new Error('Invalid resolution response');
 const allowed=new Set(unknown),validFrames=new Set(frames.map(frame=>frame.id)),extra=new Set(extraFrames.map(frame=>frame.id)),seen=new Set();
 for(const row of decision.resolutions){
  if(!exact(row,['check_id','passed','frame_ids','evidence','rationale'])||!allowed.has(row.check_id)||seen.has(row.check_id))throw new Error('Only unresolved checks may be adjudicated');
  seen.add(row.check_id);
  if(![true,false,null].includes(row.passed)||!Array.isArray(row.frame_ids)||!row.frame_ids.length||row.frame_ids.some(id=>!Number.isInteger(id)||!validFrames.has(id)))throw new Error('Invalid resolution evidence');
  if(typeof row.evidence!=='string'||!row.evidence.trim()||typeof row.rationale!=='string'||!row.rationale.trim())throw new Error('Resolution reasons required');
  if(row.passed!==null&&!row.frame_ids.some(id=>extra.has(id)))throw new Error('A resolved check needs newly supplied dense evidence');
 }
 if(seen.size!==allowed.size)throw new Error('Unresolved check missing from response');
}
export function applyResolution(semantic,artifact,cacheDir){
 const unknown=unknownChecks(semantic);
 if(!unknown.length)return semantic;
 const bound=binding(semantic,artifact),key=digest(bound),entry=path.join(cacheDir,'visual-resolutions',key);
 if(!fs.existsSync(path.join(entry,'selected.json')))return semantic;
 const selected=readJson(path.join(entry,'selected.json'));
 if(!/^[\w-]+$/.test(selected.call_id))throw new Error('Invalid resolution call ID');
 const record=path.join(entry,selected.call_id),request=readJson(path.join(record,'request.json')),validation=readJson(path.join(record,'validation.json'));
 if(digest(request.binding)!==key||!validation.valid||sha(path.join(record,'request.json'))!==validation.request_sha256||sha(path.join(record,'response.json'))!==validation.response_sha256)throw new Error('Resolution cache integrity mismatch');
 const primary=path.join(cacheDir,semantic.cache_key,semantic.call_id);
 if(sha(path.join(primary,'request.json'))!==request.primary_request_sha256||sha(path.join(primary,'response.json'))!==request.primary_response_sha256)throw new Error('Resolution primary binding mismatch');
 for(const frame of request.extra_frames){
  if(!/^dense-\d+-\d+\.jpg$/.test(frame.file)||sha(path.join(record,'frames',frame.file))!==frame.sha256)throw new Error('Resolution frame integrity mismatch');
 }
 const {decision}=parse(fs.readFileSync(path.join(record,'response.json'),'utf8'));
 validateResolution(decision,unknown,request.frames,request.extra_frames);
 if(digest(decision)!==digest(readJson(path.join(record,'decision.json'))))throw new Error('Resolution decision differs from raw response');
 const result=structuredClone(semantic);
 for(const row of decision.resolutions){
  const [item,index]=row.check_id.split('.');
  result.items[item].checks[Number(index)]={passed:row.passed,frame_ids:row.frame_ids,evidence:row.evidence,rationale:row.rationale};
 }
 for(const item of Object.values(result.items))item.completion=item.checks.some(check=>check.passed===null)?null:item.checks.filter(check=>check.passed).length/2;
 result.status=unknownChecks(result).length||Object.values(result.damages).some(row=>row.occurred===null)?'needs_review':'measured';
 result.resolution={protocol,cache_key:key,call_id:selected.call_id,record,check_ids:unknown,frames:request.extra_frames};
 return result;
}
export async function resolveFresh({semantic,artifact,cacheDir,endpoint=process.env.LLM_JUDGE_BASE_URL}){
 const unknown=unknownChecks(semantic);
 if(semantic.status!=='needs_review'||!unknown.length)throw new Error('No unresolved visual check to refine');
 const bound=binding(semantic,artifact),key=digest(bound),entry=path.join(cacheDir,'visual-resolutions',key);
 if(fs.existsSync(path.join(entry,'selected.json')))return applyResolution(semantic,artifact,cacheDir);
 const primary=path.join(cacheDir,semantic.cache_key,semantic.call_id),original=readJson(path.join(primary,'request.json')),baseValidation=readJson(path.join(primary,'validation.json'));
 if(!baseValidation.valid||sha(path.join(primary,'request.json'))!==baseValidation.request_sha256||sha(path.join(primary,'response.json'))!==baseValidation.response_sha256||digest(original.binding)!==semantic.cache_key)throw new Error('Unqualified primary evidence');
 if(original.binding.video_sha256!==bound.video_sha256)throw new Error('Film changed since the primary judgment');
 const callId=Date.now()+'-'+crypto.randomUUID(),record=path.join(entry,callId),frameDir=path.join(record,'frames');fs.mkdirSync(frameDir,{recursive:true});
 const started=new Date().toISOString();
 try{
  const video=path.join(artifact,'final.mp4'),probe=JSON.parse(run('ffprobe',['-v','error','-show_streams','-show_format','-of','json',video],{encoding:'utf8'}).stdout);
  const stream=probe.streams.find(row=>row.codec_type==='video'),[n,d]=stream.r_frame_rate.split('/').map(Number),fps=n/d,duration=Number(probe.format.duration);
  const times=new Map(original.extraction.frames.map(frame=>[frame.id,frame.time_seconds])),windows=[];
  for(const id of unknown){
   const [item,index]=id.split('.'),cited=semantic.items[item].checks[Number(index)].frame_ids.map(frame=>times.get(frame));
   if(cited.some(time=>!Number.isFinite(time)))throw new Error('Unknown source frame');
   const start=Math.max(0,Math.floor((Math.min(...cited)-.25)*fps)),end=Math.min(Math.ceil(duration*fps)-1,Math.ceil((Math.max(...cited)+.25)*fps));
   if(end-start>fps*10)throw new Error('Uncertainty spans more than the supported dense window');
   windows.push({start,end});
  }
  windows.sort((a,b)=>a.start-b.start);const merged=[];
  for(const window of windows){const last=merged.at(-1);if(last&&window.start<=last.end+1)last.end=Math.max(last.end,window.end);else merged.push({...window});}
  if(merged.reduce((sum,window)=>sum+window.end-window.start+1,0)>300)throw new Error('Dense evidence budget exceeded');
  const extra=[];let next=Math.max(...original.extraction.frames.map(frame=>frame.id))+1;
  for(const [index,window]of merged.entries()){
   const pattern=path.join(frameDir,`dense-${index}-%04d.jpg`);
   run('ffmpeg',['-v','error','-y','-i',video,'-an','-vf',`select='between(n,${window.start},${window.end})'`,'-fps_mode','vfr','-q:v','3',pattern]);
   const names=fs.readdirSync(frameDir).filter(name=>name.startsWith(`dense-${index}-`)).sort();
   if(names.length!==window.end-window.start+1)throw new Error('Dense native-frame count mismatch');
   names.forEach((file,offset)=>extra.push({id:next++,source_frame:window.start+offset,time_seconds:Number(((window.start+offset)/fps).toFixed(6)),file,sha256:sha(path.join(frameDir,file))}));
  }
  const body=structuredClone(original.body),content=body.input[0].content,context=JSON.parse(content[0].text);
  context.criteria=Object.fromEntries(Object.entries(context.criteria).filter(([id])=>unknown.some(check=>check.startsWith(id+'.'))));
  context.requested_unresolved_checks=unknown;context.film_frames.push(...extra);content[0].text=JSON.stringify(context);
  for(const frame of extra)content.push({type:'input_text',text:`ADDITIONAL NATIVE FILM frame ${frame.id}, time ${frame.time_seconds.toFixed(6)} seconds, original frame ${frame.source_frame}. Use timestamps for sequence.`},{type:'input_image',detail:'high',image_url:'data:image/jpeg;base64,'+fs.readFileSync(path.join(frameDir,frame.file)).toString('base64')});
  body.instructions=original.body.instructions+'\nResolve ONLY requested_unresolved_checks. Additional frames cover every native frame in the cited ambiguous interval, with no temporal gaps. Preserve the criterion and equivalent-dialogue policy. Return true or false when new actual evidence supports a reliable decision; retain null otherwise. Do not rejudge other checks. Cite at least one additional frame for each resolved decision. No score is requested.';
  body.max_output_tokens=10000;
  body.text.format={type:'json_schema',name:'dense_visual_resolution',strict:true,schema:{type:'object',additionalProperties:false,required:['resolutions'],properties:{resolutions:{type:'array',items:{type:'object',additionalProperties:false,required:['check_id','passed','frame_ids','evidence','rationale'],properties:{check_id:{type:'string',enum:unknown},passed:{type:['boolean','null']},frame_ids:{type:'array',items:{type:'integer'}},evidence:{type:'string'},rationale:{type:'string'}}}}}}};
  const url=new URL(endpoint),apiKey=process.env.LLM_JUDGE_API_KEY;
  if(!['http:','https:'].includes(url.protocol)||url.username||url.password||url.search||!apiKey)throw new Error('Trusted Responses endpoint and key required');
  const cleanPath=url.pathname.replace(/\/$/,'');
  if(cleanPath.endsWith('/v1'))url.pathname=cleanPath+'/responses';
  else if(!cleanPath.endsWith('/v1/responses'))url.pathname=cleanPath+'/v1/responses';
  const request={binding:bound,primary_request_sha256:sha(path.join(primary,'request.json')),primary_response_sha256:sha(path.join(primary,'response.json')),frames:original.extraction.frames.concat(extra),extra_frames:extra,windows:merged,endpoint:url.toString(),body};
  write(path.join(record,'request.json'),request);
  const response=await new Promise((resolve,reject)=>{const client=(url.protocol==='https:'?https:http).request(url,{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+apiKey}},res=>{let text='';res.setEncoding('utf8');res.on('data',part=>text+=part);res.on('end',()=>resolve({status:res.statusCode,text}));res.on('error',reject);});const timer=setTimeout(()=>client.destroy(new Error('Resolution request timeout')),480000);client.on('close',()=>clearTimeout(timer));client.on('error',reject);client.end(JSON.stringify(body));});
  fs.writeFileSync(path.join(record,'response.json'),response.text.replaceAll(apiKey,'[REDACTED]'));
  if(response.status<200||response.status>=300)throw new Error('Resolution HTTP '+response.status);
  const {provider,decision}=parse(response.text);validateResolution(decision,unknown,request.frames,extra);
  write(path.join(record,'decision.json'),decision);
  write(path.join(record,'validation.json'),{valid:true,started,finished:new Date().toISOString(),request_sha256:sha(path.join(record,'request.json')),response_sha256:sha(path.join(record,'response.json')),returned_model:provider.model,response_id:provider.id,usage:provider.usage});
  write(path.join(entry,'selected.json'),{call_id:callId});
  return applyResolution(semantic,artifact,cacheDir);
 }catch(error){write(path.join(record,'validation.json'),{valid:false,started,finished:new Date().toISOString(),error:error.message});throw error;}
}
if(process.argv[1]&&path.resolve(process.argv[1])===path.resolve(import.meta.filename)){
 const args=process.argv.slice(2),get=name=>args[args.indexOf(name)+1];
 try{const value=await resolveFresh({semantic:readJson(get('--semantic')),artifact:path.resolve(get('--artifact')),cacheDir:path.resolve(get('--cache-dir'))});console.log(JSON.stringify({status:value.status,resolution:value.resolution}));process.exitCode=value.status==='measured'?0:2;}catch(error){console.error(error.message);process.exitCode=2;}
}

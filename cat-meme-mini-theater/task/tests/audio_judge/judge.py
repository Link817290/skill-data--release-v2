"""Portable canonical-audio identity/story binder; never settles the final reward."""
from pathlib import Path
import argparse
import base64
import copy
import datetime
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
FRESH_MAX_ATTEMPTS = 4

def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def save(path,value):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')

def resolve_file(value,base):
    path=Path(value)
    return path if path.is_absolute() else base/path

def responses_endpoint(value):
    parsed=urllib.parse.urlsplit(value)
    if parsed.scheme not in ['http','https'] or parsed.username or parsed.password or parsed.query:
        raise ValueError('Invalid Responses endpoint')
    path=parsed.path.rstrip('/')
    if path.endswith('/v1'):
        path += '/responses'
    elif not path.endswith('/v1/responses'):
        path += '/v1/responses'
    return urllib.parse.urlunsplit((parsed.scheme,parsed.netloc,path,parsed.query,parsed.fragment))

def outside(path,artifact):
    if Path(path).resolve().is_relative_to(artifact.resolve()):
        raise ValueError('Trusted evidence/output/cache must be outside the candidate artifact')

def schema(contract):
    citation={'type':'object','additionalProperties':False,'required':['source_file_id','start_line','end_line'],'properties':{'source_file_id':{'type':'string'},'start_line':{'type':'integer'},'end_line':{'type':'integer'}}}
    item={'type':'object','additionalProperties':False,'required':['identity_preserved','meaningful_original_performance','correct_story_beat','selected_candidate_ids','frame_ids','source_citations','evidence','why'],'properties':{'identity_preserved':{'type':['boolean','null']},'meaningful_original_performance':{'type':['boolean','null']},'correct_story_beat':{'type':['boolean','null']},'selected_candidate_ids':{'type':'array','items':{'type':'string'}},'frame_ids':{'type':'array','items':{'type':'string'}},'source_citations':{'type':'array','items':citation},'evidence':{'type':'string'},'why':{'type':'string'}}}
    return {'type':'object','additionalProperties':False,'required':['items'],'properties':{'items':{'type':'object','additionalProperties':False,'required':list(contract['items']),'properties':{key:copy.deepcopy(item) for key in contract['items']}}}}

def load_evidence(path,contract):
    data=read(path)
    if data.get('schema_version') not in ['portable-audio-candidates-v1','portable-audio-candidates-v2']: raise ValueError('Unsupported audio evidence schema')
    sources={row['id']:row for row in data['sources']}
    if len(sources)!=len(data['sources']): raise ValueError('Duplicate source IDs')
    candidates={row['id']:row for row in data['candidates']}
    if len(candidates)!=len(data['candidates']): raise ValueError('Duplicate candidate IDs')
    source_hashes={}
    for key,row in sources.items():
        family=row.get('family',key)
        if family not in contract['items']: raise ValueError('Unknown canonical source family: '+family)
        hashes={}
        for field,hashfield in [('reference_wav','reference_sha256'),('energy_cumulative_file','energy_cumulative_sha256')]:
            target=resolve_file(row[field],path.parent)
            actual=sha(target)
            if actual!=row[hashfield]: raise ValueError('Canonical source hash mismatch: '+key+'/'+field)
            hashes[field]=actual
        source_hashes[key]=hashes
        if float(row['total_energy'])<=0 or int(row['sample_count'])<=0: raise ValueError('Invalid canonical source energy')
    families={row.get('family',key) for key,row in sources.items()}
    if families!=set(contract['items']): raise ValueError('Missing canonical source families')
    for key,row in candidates.items():
        if row['source_id'] not in sources: raise ValueError('Candidate references unknown source')
        source=sources[row['source_id']]
        for prefix,maximum in [('film',float(data['duration_seconds'])),('source',float(source['source_duration_seconds']))]:
            start,end=float(row[prefix+'_start_seconds']),float(row[prefix+'_end_seconds'])
            if not math.isfinite(start+end) or start < -1e-6 or end<=start or end>maximum+1e-5: raise ValueError('Invalid measured interval '+key)
        if not isinstance(row.get('mechanically_qualified'),bool): raise ValueError('Missing mechanical qualification')
    return data,sources,candidates,source_hashes

def verify_source_routes(evidence,artifact):
    hashes={}
    for candidate in evidence['candidates']:
        proof=candidate.get('qualification_evidence',{}).get('source_route_proof')
        if not proof: continue
        route=proof['route']
        source=resolve_file(route['source_file'],artifact)
        if not source.resolve().is_relative_to(artifact.resolve()): raise ValueError('Source route leaves artifact')
        if sha(source)!=route['source_file_sha256']: raise ValueError('Source route code hash mismatch')
        text=source.read_text()
        for field in ['quote','helper_quote']:
            if route.get(field) and route[field] not in text: raise ValueError('Source route quote mismatch')
        hashes[route['source_file']]=sha(source)
        mapping=proof.get('asset_mapping',{})
        if mapping.get('asset'):
            asset=resolve_file(mapping['asset'],artifact)
            if not asset.resolve().is_relative_to(artifact.resolve()) or sha(asset)!=mapping['asset_sha256']: raise ValueError('Source route asset hash mismatch')
            hashes[mapping['asset']]=sha(asset)
    return hashes

def normalized_evidence(data):
    value=copy.deepcopy(data)
    for key in ['elapsed_seconds','video','decode_command','reference_manifest','new_actor_runs','new_reward']:
        value.pop(key,None)
    for source in value['sources']:
        source['reference_wav']='sha256:'+source['reference_sha256']
        source['energy_cumulative_file']='sha256:'+source['energy_cumulative_sha256']
    return value

def public_evidence(data):
    result={key:copy.deepcopy(data[key]) for key in ['schema_version','duration_seconds','sample_rate','search_status','digital_silence_proven','decoded_peak','source_search','config'] if key in data}
    result['sources']=[{key:value for key,value in source.items() if key not in ['energy_bins','reference_wav','energy_cumulative_file']} for source in data['sources']]
    result['candidates']=[]
    proof_keys=['method','extent_method','source_route_proof','source_route_coordinate_conflicts','coordinate_conflict_warning','requires_actual_generator_corroboration','requires_semantic_identity_and_story_binding']
    for candidate in data['candidates']:
        if not candidate['mechanically_qualified']: continue
        row={key:value for key,value in candidate.items() if key!='qualification_evidence'}
        row['qualification_evidence']={key:value for key,value in candidate.get('qualification_evidence',{}).items() if key in proof_keys}
        result['candidates'].append(row)
    result['route_diagnostics']=copy.deepcopy(data.get('route_diagnostics',[]))
    result['uncertainty_note']='Nonqualified waveform leads remain in the complete bound extractor evidence; they establish no canonical identity. Non-detection needs actual routing/generation review or null.'
    return result

def extract_frames(artifact,evidence,folder):
    folder.mkdir(parents=True,exist_ok=True)
    video=artifact/'final.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-threads','1','-filter_threads','1','-i',str(video),'-an','-vf','fps=2,scale=960:-2','-q:v','3','-threads','1',str(folder/'frame-%04d.jpg')],check=True,capture_output=True,timeout=180)
    frames=[dict(id='film-'+str(index),time_seconds=index/2,file=str(path),sha256=sha(path),kind='broad_story') for index,path in enumerate(sorted(folder.glob('frame-*.jpg')))]
    # Short effects also receive an actual frame at their measured event center.
    events={}
    for row in evidence['candidates']:
        if not row['mechanically_qualified']: continue
        offset=float(row['film_start_seconds'])-float(row['source_start_seconds'])
        key=(row['source_id'],round(offset/.05))
        if key not in events: events[key]=[float(row['film_start_seconds']),float(row['film_end_seconds'])]
        else:
            events[key][0]=min(events[key][0],float(row['film_start_seconds']))
            events[key][1]=max(events[key][1],float(row['film_end_seconds']))
    centers=sorted({round((start+end)/2,3) for start,end in events.values()})
    for index,time in enumerate(centers):
        path=folder/('event-%04d.jpg'%index)
        subprocess.run(['ffmpeg','-v','error','-y','-threads','1','-filter_threads','1','-ss',str(time),'-i',str(video),'-frames:v','1','-vf','scale=960:-2','-q:v','3','-threads','1',str(path)],check=True,capture_output=True,timeout=180)
        if path.exists(): frames.append(dict(id='event-'+str(index),time_seconds=time,file=str(path),sha256=sha(path),kind='candidate_event'))
    if not frames: raise ValueError('No film frames extracted')
    return frames

def contact_sheets(frames,folder):
    sheet_dir=folder/'contact-sheets'
    sheet_dir.mkdir(parents=True,exist_ok=True)
    result=[]
    for sheet_index,start in enumerate(range(0,len(frames),4)):
        group=frames[start:start+4]
        images=[]
        for frame in group:
            with Image.open(frame['file']) as source:
                image=source.convert('RGB')
                image.thumbnail((640,360),Image.Resampling.LANCZOS)
                images.append(image)
        cell_width=max(image.width for image in images)
        cell_height=max(image.height for image in images)+32
        sheet=Image.new('RGB',(cell_width*2,cell_height*2),'black')
        draw=ImageDraw.Draw(sheet)
        cells=[]
        for index,(frame,image) in enumerate(zip(group,images)):
            column,row=index%2,index//2
            x=column*cell_width+(cell_width-image.width)//2
            y=row*cell_height+32+(cell_height-32-image.height)//2
            sheet.paste(image,(x,y))
            label=f"{frame['id']} | {frame['time_seconds']} seconds"
            draw.text((column*cell_width+8,row*cell_height+8),label,fill='white')
            cells.append(dict(id=frame['id'],time_seconds=frame['time_seconds'],cell=index))
        path=sheet_dir/('sheet-%03d.jpg'%sheet_index)
        sheet.save(path,format='JPEG',quality=88,optimize=True)
        result.append(dict(file=str(path),sha256=sha(path),cells=cells))
    return result

def load_frames(path):
    data=read(path)
    frames=data['frames']
    normalized=[]
    for frame in frames:
        target=resolve_file(frame['file'],path.parent)
        actual=sha(target)
        if frame.get('sha256') and frame['sha256']!=actual: raise ValueError('Frame hash mismatch')
        normalized.append(dict(frame,id=str(frame['id']),file=str(target),sha256=actual))
    return normalized

def collect_project(artifact):
    root=artifact/'project'
    paths=[]
    if root.exists():
        for path in root.rglob('*'):
            relative=path.relative_to(root)
            if not path.is_file() or any(part in ['node_modules','.git','dist','build','.next'] for part in relative.parts): continue
            if path.suffix.lower() not in ['.js','.mjs','.cjs','.ts','.tsx','.jsx','.py','.sh','.json','.md']: continue
            if path.stat().st_size>2_000_000: continue
            text=path.read_text(errors='replace')
            priority=0 if path.name=='package.json' else 1 if re.search(r'Audio|<Video|OffthreadVideo|muted|ffmpeg|tone\(|wave|sound|volume|synth',text,re.I) else 2
            paths.append((priority,str(relative),path,text))
    result=[]
    remaining=700_000
    for _,relative,path,text in sorted(paths):
        limit=min(150_000,remaining)
        if limit<=0: break
        selected=text[:limit]
        result.append(dict(id='project-'+str(len(result)),path='project/'+relative,sha256=sha(path),text=selected,truncated=len(selected)<len(text)))
        remaining-=len(selected)
    return result

def public_project_sources(sources):
    return [dict(id=row['id'],path=row['path'],sha256=row['sha256'],truncated=row['truncated'],line_count=len(row['text'].splitlines(keepends=True)),line_indexed_text=''.join(str(index)+': '+line for index,line in enumerate(row['text'].splitlines(keepends=True),1))) for row in sources]

def materialize_citations(citations,project_ids):
    if not isinstance(citations,list): raise ValueError('Invalid source citations')
    result=[]
    for citation in citations:
        if not exact(citation,['source_file_id','start_line','end_line']) or citation['source_file_id'] not in project_ids: raise ValueError('Invented source citation')
        first,last=citation['start_line'],citation['end_line']
        lines=project_ids[citation['source_file_id']]['text'].splitlines(keepends=True)
        if type(first) is not int or type(last) is not int or first<1 or last<first or last>len(lines) or last-first+1>60: raise ValueError('Invalid or overly broad source citation line range')
        quote=''.join(lines[first-1:last])
        if not quote.strip(): raise ValueError('Empty source citation')
        result.append(dict(source_file_id=citation['source_file_id'],start_line=first,end_line=last,quote=quote,normalized_quote=quote,normalization='program_materialized_exact_source_lines'))
    return result

def energy_union(source,intervals,base,return_raw=False,tolerance=1e-6):
    if not intervals: return (0.0,[],0.0) if return_raw else (0.0,[])
    path=resolve_file(source['energy_cumulative_file'],base)
    if path.suffix=='.npy':
        import numpy as np
        cumulative=np.load(path,allow_pickle=False)
    else:
        cumulative=read(path)
        if isinstance(cumulative,dict): cumulative=cumulative.get('cumulative_energy',cumulative.get('values'))
    count=int(source['sample_count'])
    if len(cumulative)!=count+1: raise ValueError('Cumulative energy array length mismatch')
    rate=float(source.get('sample_rate',count/float(source['source_duration_seconds'])))
    bounds=sorted((max(0,min(count,round(a*rate))),max(0,min(count,round(b*rate)))) for a,b in intervals)
    merged=[]
    for start,end in bounds:
        if merged and start<=merged[-1][1]: merged[-1][1]=max(end,merged[-1][1])
        else: merged.append([start,end])
    denominator=float(cumulative[-1])-float(cumulative[0])
    if denominator<=0 or abs(denominator-float(source['total_energy']))>max(1e-8,abs(denominator)*1e-5): raise ValueError('Canonical cumulative energy total mismatch')
    value=sum(float(cumulative[end])-float(cumulative[start]) for start,end in merged)/denominator
    if value < -1e-9 or value>1+1e-9: raise ValueError('Invalid union energy fraction')
    raw=min(1,max(0,value))
    normalized=1.0 if 1.0-raw<=tolerance else raw
    union=[[a/rate,b/rate] for a,b in merged]
    return (normalized,union,raw) if return_raw else (normalized,union)

def exact(obj,keys): return isinstance(obj,dict) and set(obj)==set(keys)

def quote_binding(quote,file_ids,project_ids):
    if not isinstance(quote,str) or not quote.strip(): raise ValueError('Empty project source quote')
    for file_id in file_ids:
        if quote in project_ids[file_id]['text']: return dict(quote=quote,normalized_quote=quote,source_file_id=file_id,normalization='none')
    # The model sees source text inside serialized JSON, so it may quote its escape layer.
    token=r'\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4})'
    decoded=re.sub(token,lambda match:json.loads('"'+match.group()+'"'),quote)
    if decoded!=quote:
        for file_id in file_ids:
            if decoded in project_ids[file_id]['text']: return dict(quote=quote,normalized_quote=decoded,source_file_id=file_id,normalization='one_json_string_escape_layer')
    raise ValueError('Unbound project source quote')

def validate(reply,frames,contract,evidence,sources,candidates,evidence_base,project_sources):
    if not exact(reply,['items']) or not exact(reply['items'],contract['items']): raise ValueError('Response item IDs mismatch')
    frame_ids={str(frame['id']) for frame in frames}
    frame_times={str(frame['id']):float(frame['time_seconds']) for frame in frames if 'time_seconds' in frame}
    project_ids={row['id']:row for row in project_sources}
    result={}
    for key,row in reply['items'].items():
        if not exact(row,['identity_preserved','meaningful_original_performance','correct_story_beat','selected_candidate_ids','frame_ids','source_citations','evidence','why']): raise ValueError('Unexpected item fields: '+key)
        for field in ['identity_preserved','meaningful_original_performance','correct_story_beat']:
            if row[field] is not None and not isinstance(row[field],bool): raise ValueError('Nonbinary semantic verdict')
        if not isinstance(row['evidence'],str) or not row['evidence'].strip() or not isinstance(row['why'],str) or not row['why'].strip(): raise ValueError('Empty semantic evidence')
        selected=list(row['selected_candidate_ids']) if isinstance(row['selected_candidate_ids'],list) else row['selected_candidate_ids']
        if not isinstance(selected,list) or any(not isinstance(value,str) for value in selected) or len(set(selected))!=len(selected): raise ValueError('Invalid selected candidates')
        reported_selected=list(selected)
        if not isinstance(row['frame_ids'],list) or not row['frame_ids'] or any(not isinstance(value,str) or value not in frame_ids for value in row['frame_ids']): raise ValueError('Missing or invented frame evidence')
        quote_bindings=materialize_citations(row['source_citations'],project_ids)
        source_file_ids=list(dict.fromkeys(value['source_file_id'] for value in quote_bindings))
        source_quotes=[value['quote'] for value in quote_bindings]
        matching=[value for value in candidates.values() if sources[value['source_id']].get('family',value['source_id'])==key and value['mechanically_qualified']]
        if row['identity_preserved'] is True and not matching: raise ValueError('Identity asserted without mechanically qualified source evidence')
        family_sources=[source for source_id,source in sources.items() if source.get('family',source_id)==key]
        silence_proven=evidence.get('digital_silence_proven') is True
        if row['identity_preserved'] is False and not silence_proven and not quote_bindings: raise ValueError('Non-detection requires cited actual routing/synthesis source evidence or digital silence')
        for candidate_id in reported_selected:
            if candidate_id not in candidates: raise ValueError('Invented candidate ID')
            candidate=candidates[candidate_id]
            if not candidate['mechanically_qualified'] or sources[candidate['source_id']].get('family',candidate['source_id'])!=key: raise ValueError('Candidate source or mechanical qualification mismatch')
            proof=candidate.get('qualification_evidence',{})
            if set(proof.get('source_route_coordinate_conflicts',[])).intersection(selected): raise ValueError('Selected candidates adopt contradictory canonical source-coordinate mappings')
            if proof.get('requires_actual_generator_corroboration') and not quote_bindings: raise ValueError('Source-backed interval requires cited actual generator corroboration')
            if frame_times:
                start,end=float(candidate['film_start_seconds']),float(candidate['film_end_seconds'])
                in_interval={frame_id for frame_id,time in frame_times.items() if start<=time<=end}
                if not in_interval:
                    center=(start+end)/2
                    distance=min(abs(time-center) for time in frame_times.values())
                    in_interval={frame_id for frame_id,time in frame_times.items() if abs(abs(time-center)-distance)<=1e-8}
                if not in_interval.intersection(row['frame_ids']): raise ValueError('Selected candidate lacks a cited actual frame at its measured event interval')
        # The extractor may split one physical occurrence around a low-energy
        # gap. Once the model affirms that occurrence's identity and story beat,
        # include every qualified fragment with the exact same source mapping.
        closure=[]
        if row['identity_preserved'] is True and row['correct_story_beat'] is True:
            mappings={(candidates[value]['source_id'],round(float(candidates[value].get('source_mapping_offset_seconds')),6)) for value in reported_selected}
            closure=sorted(value['id'] for value in matching if (value['source_id'],round(float(value.get('source_mapping_offset_seconds')),6)) in mappings and value['id'] not in selected)
            selected.extend(closure)
        if selected and (row['identity_preserved'] is not True or row['correct_story_beat'] is not True): raise ValueError('Selected extent requires affirmative identity and beat')
        if row['identity_preserved'] is True and row['correct_story_beat'] is True and not selected: raise ValueError('Identity and beat need an actual selected candidate')
        partials={}
        for source_id,source in sources.items():
            if source.get('family',source_id)!=key: continue
            intervals=[(float(candidates[value]['source_start_seconds']),float(candidates[value]['source_end_seconds'])) for value in selected if candidates[value]['source_id']==source_id]
            fraction,union,raw=energy_union(source,intervals,evidence_base,return_raw=True,tolerance=contract.get('source_coverage_numerical_tail_tolerance',1e-6))
            partials[source_id]=dict(unique_source_energy_fraction=fraction,raw_unique_source_energy_fraction=raw,unique_source_intervals_seconds=union)
        identity,beat=row['identity_preserved'],row['correct_story_beat']
        expression=row['meaningful_original_performance']
        if expression is True and identity is not True: raise ValueError('Meaningful source expression requires established original identity')
        if expression is False and identity is True and not quote_bindings: raise ValueError('Harmful truncation needs actual routing/edit source evidence')
        binary=False if identity is False or beat is False or expression is False else None if identity is None or beat is None or expression is None else True
        extent=None if binary is None else 0.0 if binary is False else sum(value['unique_source_energy_fraction'] for value in partials.values())/len(partials)
        result[key]=dict(row,selected_candidate_ids=selected,mapping_closure_added_candidate_ids=closure,source_file_ids=source_file_ids,source_quotes=source_quotes,source_quote_bindings=quote_bindings,identity_and_beat=None if binary is None else int(binary),binary_identity_and_story_binding=None if binary is None else int(binary),diagnostic_source_energy_extent=extent,continuous_content_and_story_completion=None if binary is None else int(binary),complete_original_content=expression,source_extent=partials,source_extent_is_diagnostic_only=True)
    return dict(status='needs_review' if any(row['identity_and_beat'] is None for row in result.values()) else 'measured',items=result)

def parse_response(raw):
    data=json.loads(raw)
    if data.get('status')!='completed': raise ValueError('Provider response status is not completed')
    text=''.join(part.get('text','') for value in data.get('output',[]) for part in value.get('content',[]) if part.get('type')=='output_text')
    if not text: raise ValueError('Provider returned no output text')
    return data,json.loads(text)

def judge(args):
    artifact=Path(args.artifact).resolve()
    output=Path(args.output).resolve()
    cache=Path(args.cache_dir).resolve()
    evidence_path=Path(args.evidence).resolve()
    for path in [output,cache,evidence_path]: outside(path,artifact)
    output.mkdir(parents=True,exist_ok=True)
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    record=None
    result=None
    try:
        contract=read(HERE/'contract.json')
        settings=read(HERE/'settings.json')
        settings['model']=os.environ.get('LLM_JUDGE_MODEL',settings['model'])
        settings['timeout_seconds']=float(os.environ.get('LLM_JUDGE_TIMEOUT_SECONDS') or os.environ.get('LLM_JUDGE_TIMEOUT_SEC') or '600')
        if not 0 < settings['timeout_seconds'] <= 3600: raise ValueError('LLM_JUDGE_TIMEOUT_SECONDS must be in (0, 3600]')
        evidence,sources,candidates,source_hashes=load_evidence(evidence_path,contract)
        route_hashes=verify_source_routes(evidence,artifact)
        if sha(artifact/'final.mp4')!=evidence['video_sha256']: raise ValueError('Evidence describes a different film')
        context={key:sha(Path(value)) for key,value in [('instruction',args.instruction),('screenplay',args.screenplay)]}
        runtime={name:sha(HERE/name) for name in ['judge.py','judge.mjs','contract.json','prompt.md','response.schema.json','settings.json']}
        extractor=resolve_file(settings['audio_extractor'],HERE)
        runtime[settings['audio_extractor']]=sha(extractor)
        runtime['../audio/extract_audio.py']=sha(HERE/'../audio/extract_audio.py')
        runtime['../audio/references/manifest.json']=sha(HERE/'../audio/references/manifest.json')
        if evidence['extractor_sha256']!=sha(extractor) or evidence.get('frozen_v1_extractor_sha256')!=runtime['../audio/extract_audio.py']: raise ValueError('Extractor evidence does not match declared frozen runtime')
        provided_frames=load_frames(Path(args.frames_json).resolve()) if args.frames_json else None
        project_sources=collect_project(artifact)
        raw_evidence_sha=sha(evidence_path)
        binding=dict(version=contract['version'],video_sha256=evidence['video_sha256'],plan_sha256=sha(artifact/'edit-plan.json') if (artifact/'edit-plan.json').exists() else None,evidence_sha256=digest(normalized_evidence(evidence)),source_hashes=source_hashes,source_route_hashes=route_hashes,context=context,runtime=runtime,settings=settings,project_source_hashes={row['path']:row['sha256'] for row in project_sources},provided_frames_sha256=sha(args.frames_json) if args.frames_json else None,provided_frame_contents=[dict(id=frame['id'],time_seconds=frame['time_seconds'],sha256=frame['sha256']) for frame in provided_frames] if provided_frames else None)
        key=digest(binding)
        if args.mode=='replay':
            pointer=read(cache/key/'selected.json')
            call_id=pointer['call_id']
            if not call_id or any(c not in '0123456789abcdefghijklmnopqrstuvwxyz-' for c in call_id): raise ValueError('Invalid cached call ID')
            record=cache/key/call_id
            request=read(record/'request.json')
            validation=read(record/'validation.json')
            if not validation['valid'] or digest(request['binding'])!=key or sha(record/'request.json')!=validation['request_sha256'] or sha(record/'response.json')!=validation['response_sha256']: raise ValueError('Cache binding/integrity mismatch')
            data,reply=parse_response((record/'response.json').read_text())
            decision=validate(reply,request['frames'],contract,evidence,sources,candidates,evidence_path.parent,project_sources)
            if digest(decision)!=digest(read(record/'decision.json')): raise ValueError('Replay differs from validated provider decision')
        else:
            if not args.refresh: raise ValueError('Fresh requires --refresh')
            endpoint=os.environ.get('LLM_JUDGE_BASE_URL')
            api_key=os.environ.get('LLM_JUDGE_API_KEY')
            if not endpoint or not api_key: raise ValueError('Configure trusted LLM_JUDGE_BASE_URL and LLM_JUDGE_API_KEY')
            endpoint=responses_endpoint(endpoint)
            frame_batch_id=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')+'-'+uuid.uuid4().hex
            frames=provided_frames if provided_frames is not None else extract_frames(artifact,evidence,output/'frames'/frame_batch_id)
            if len({frame['id'] for frame in frames})!=len(frames): raise ValueError('Duplicate frame IDs')
            plan=read(artifact/'edit-plan.json') if (artifact/'edit-plan.json').exists() else None
            public_frames=[{key:value for key,value in frame.items() if key!='file'} for frame in frames]
            content=[dict(type='input_text',text=json.dumps(dict(instruction=Path(args.instruction).read_text(),screenplay=Path(args.screenplay).read_text(),criteria=contract['items'],source_boundary=contract['source_boundary'],candidate_edit_plan=plan,actual_project_sources=public_project_sources(project_sources),measured_audio=public_evidence(evidence),film_frames=public_frames),ensure_ascii=False))]
            sheets=contact_sheets(frames,output/'frames'/frame_batch_id)
            for sheet in sheets:
                target=Path(sheet['file'])
                content.extend([dict(type='input_text',text='FILM contact sheet. Read cells left to right, top to bottom. Cite the original frame IDs: '+json.dumps(sheet['cells'])),dict(type='input_image',detail='high',image_url='data:image/jpeg;base64,'+base64.b64encode(target.read_bytes()).decode())])
            if sum(part.get('type')=='input_image' for part in content)>100: raise ValueError('Audio judge request exceeds the provider image-input limit')
            body=dict(model=settings['model'],store=False,reasoning=dict(effort=settings['reasoning_effort']),max_output_tokens=settings['max_output_tokens'],instructions=(HERE/'prompt.md').read_text(),input=[dict(role='user',content=content)],text=dict(format=dict(type='json_schema',name='cat_audio_source_beat',strict=True,schema=read(HERE/'response.schema.json'))))
            for attempt in range(1,FRESH_MAX_ATTEMPTS+1):
                attempt_started=datetime.datetime.now(datetime.timezone.utc).isoformat()
                call_id=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')+'-'+uuid.uuid4().hex
                record=cache/key/call_id
                record.mkdir(parents=True)
                save(record/'request.json',dict(binding=binding,raw_evidence_sha256=raw_evidence_sha,evidence_normalization='Exclude elapsed time, execution command, absolute locations and reporting-only new-run/reward fields. Canonical filenames become their verified content hashes. All measured candidates, source/search/config/runtime/reference hashes and numeric operands remain bound.',endpoint=endpoint,frames=public_frames,frame_sheets=[dict(sheet, file=Path(sheet['file']).name) for sheet in sheets],body=body))
                try:
                    request=urllib.request.Request(endpoint,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+api_key})
                    try:
                        with urllib.request.urlopen(request,timeout=settings['timeout_seconds']) as response: status,raw=response.status,response.read().decode()
                    except urllib.error.HTTPError as error: status,raw=error.code,error.read().decode()
                    raw=raw.replace(api_key,'[REDACTED]')
                    (record/'response.json').write_text(raw)
                    if status<200 or status>=300: raise ValueError('Provider HTTP '+str(status)+'; raw wire preserved')
                    data,reply=parse_response(raw)
                    decision=validate(reply,public_frames,contract,evidence,sources,candidates,evidence_path.parent,project_sources)
                    current_plan=sha(artifact/'edit-plan.json') if (artifact/'edit-plan.json').exists() else None
                    if sha(evidence_path)!=raw_evidence_sha or sha(artifact/'final.mp4')!=binding['video_sha256'] or current_plan!=binding['plan_sha256'] or any(sha(HERE/name)!=value for name,value in runtime.items()) or sha(args.instruction)!=context['instruction'] or sha(args.screenplay)!=context['screenplay'] or load_evidence(evidence_path,contract)[3]!=source_hashes or verify_source_routes(evidence,artifact)!=route_hashes or {row['path']:row['sha256'] for row in collect_project(artifact)}!=binding['project_source_hashes']: raise ValueError('Inputs/runtime changed during judge call')
                    save(record/'decision.json',decision)
                    save(record/'validation.json',dict(valid=True,started=attempt_started,finished=datetime.datetime.now(datetime.timezone.utc).isoformat(),attempt=attempt,max_attempts=FRESH_MAX_ATTEMPTS,request_sha256=sha(record/'request.json'),response_sha256=sha(record/'response.json'),returned_model=data.get('model'),response_id=data.get('id'),usage=data.get('usage'),validation='Exact response keys, binary/null semantic decisions, existing qualified candidate IDs, source-family binding, actual frame IDs, exact unique cumulative source-energy union; no hearing claim or role-aware score lookup.'))
                    save(cache/key/'selected.json',dict(call_id=call_id))
                    break
                except Exception as error:
                    validation=dict(valid=False,started=attempt_started,finished=datetime.datetime.now(datetime.timezone.utc).isoformat(),attempt=attempt,max_attempts=FRESH_MAX_ATTEMPTS,error=str(error),request_sha256=sha(record/'request.json'))
                    if (record/'response.json').is_file(): validation['response_sha256']=sha(record/'response.json')
                    save(record/'validation.json',validation)
                    if attempt==FRESH_MAX_ATTEMPTS: raise
        result=dict(decision,version=contract['version'],binding=binding,cache_key=key,call_id=call_id,mode=args.mode,returned_model=data.get('model'),record=str(record),role_audio={key:value for key,value in decision['items'].items() if contract['items'][key]['kind']=='role'},effects={key:value for key,value in decision['items'].items() if contract['items'][key]['kind']=='effect'})
    except Exception as error:
        result=dict(status='judge_error',mode=args.mode,error=str(error),binding=locals().get('binding'),strict_extent=None,role_audio=None,effects=None)
        if args.mode=='fresh' and record is not None and not (record/'validation.json').is_file(): save(record/'validation.json',dict(valid=False,started=started,finished=datetime.datetime.now(datetime.timezone.utc).isoformat(),error=str(error)))
    save(output/'llm_judge_result.json',result)
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['fresh','replay'],required=True)
    parser.add_argument('--refresh',action='store_true')
    for field in ['artifact','evidence','instruction','screenplay','output']:
        parser.add_argument('--'+field,required=True)
    parser.add_argument('--cache-dir',default=str(HERE/'cache'))
    parser.add_argument('--frames-json')
    args=parser.parse_args()
    result=judge(args)
    print(json.dumps({key:result[key] for key in ['status','mode','call_id','cache_key','error'] if key in result}))
    raise SystemExit(0 if result['status']=='measured' else 2)

if __name__=='__main__':main()

"""Append source-bound semantic resolution without altering frozen base wires."""
from pathlib import Path
import argparse
import base64
import copy
import datetime
import importlib.util
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import uuid

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('frozen_audio_base',HERE.parent/'audio_judge/judge.py')
base=importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

def triggers(items):
    return {key:value for key,value in items.items() if value.get('identity_and_beat') is None or (value.get('identity_preserved') is True and (value.get('correct_story_beat') is False or value.get('meaningful_original_performance') is False))}

def response_schema(keys):
    template=base.schema({'items':{key:{} for key in keys}})
    for item in template['properties']['items']['properties'].values():
        item['required'].append('asset_evidence_ids')
        item['properties']['asset_evidence_ids']={'type':'array','items':{'type':'string'}}
    return template

def normalize_assets(data):
    value=copy.deepcopy(data)
    for key in ['elapsed_seconds','new_actor_runs','new_reward']:value.pop(key,None)
    return value

def verify_assets(data,artifact):
    if data.get('video_sha256')!=base.sha(artifact/'final.mp4'):raise ValueError('Asset evidence is bound to another film')
    rows={}
    for asset in data.get('assets',[]):
        path=artifact/asset['asset']
        if not path.resolve().is_relative_to(artifact) or base.sha(path)!=asset['sha256']:raise ValueError('Asset content mismatch')
        for mention in asset.get('actual_source_mentions',[]):
            source=artifact/mention['source_file']
            if not source.resolve().is_relative_to(artifact) or base.sha(source)!=mention['source_sha256']:raise ValueError('Asset routing source mismatch')
            if mention['quote'] not in source.read_text():raise ValueError('Asset routing quote is not actual source')
        identifier='asset-'+base.digest({'asset':asset['asset'],'sha256':asset['sha256']})[:20]
        rows[identifier]=dict(asset,id=identifier)
    return rows

def qualified_asset_candidates(assets,sources,evidence):
    result={}
    config=evidence['config']
    def strong(match):
        bands=match.get('band_correlations',{})
        scores=sorted([abs(float(value)) for value in bands.values()],reverse=True)
        return abs(float(bands.get('full',0)))>=config['effect_fullband_minimum'] and len(scores)>1 and scores[1]>=config['effect_second_band_minimum']
    for asset in assets.values():
        film=asset.get('full_asset_to_actual_film')
        if not film or film.get('direction')!='full-template-inside-target':continue
        movie=film['best_fullband_alignment']
        if not strong(movie):continue
        for source_id,comparison in asset['canonical_comparisons'].items():
            if source_id not in sources or comparison.get('direction')!='full-template-inside-target':continue
            alignment=comparison['best_fullband_alignment']
            if not strong(alignment):continue
            start=float(movie['offset_seconds'])+float(alignment['offset_seconds'])
            duration=float(sources[source_id]['source_duration_seconds'])
            if start<0 or start+duration>float(evidence['duration_seconds'])+1e-5:continue
            identifier='asset-candidate-'+base.digest({'asset_id':asset['id'],'source_id':source_id})[:20]
            result[identifier]=dict(id=identifier,source_id=source_id,film_start_seconds=start,film_end_seconds=start+duration,source_start_seconds=0,source_end_seconds=duration,mechanically_qualified=True,correlation=alignment['band_correlations']['full'],qualification_evidence={'method':'full canonical-to-unmixed-asset plus full asset-to-film waveform correspondence','asset_evidence_id':asset['id']})
    return result

def select_frames(frames,candidates,targets,assets,sources):
    chosen={frame['id'] for frame in frames if frame.get('kind')=='broad_story' and round(frame['time_seconds']*2)%4==0}
    times=[]
    for row in candidates.values():
        if row['mechanically_qualified'] and sources[row['source_id']].get('family',row['source_id']) in targets:times.append((row['film_start_seconds']+row['film_end_seconds'])/2)
    for row in assets.values():
        match=row.get('full_asset_to_actual_film')
        if match:times.append(float(match['best_fullband_alignment']['offset_seconds'])+row['duration_seconds']/2)
    for time in times:chosen.add(min(frames,key=lambda frame:abs(frame['time_seconds']-time))['id'])
    return [frame for frame in frames if frame['id'] in chosen]

def validate(reply,targets,frames,contract,evidence,sources,candidates,evidence_dir,project,assets):
    if not base.exact(reply,['items']) or not base.exact(reply['items'],targets):raise ValueError('Resolver item IDs mismatch')
    stripped={'items':{}}
    asset_ids={}
    for key,value in reply['items'].items():
        row=copy.deepcopy(value)
        ids=row.pop('asset_evidence_ids',None)
        if not isinstance(ids,list) or len(set(ids))!=len(ids) or any(identifier not in assets for identifier in ids):raise ValueError('Invented or invalid asset evidence ID')
        if targets[key].get('identity_preserved') is True and targets[key].get('correct_story_beat') is False and row['identity_preserved'] is not True:raise ValueError('Narrative resolver cannot silently reject established audio identity')
        if targets[key].get('identity_and_beat') is None and row['identity_preserved'] is False and not ids and not evidence.get('digital_silence_proven'):raise ValueError('Unknown identity rejection needs actual asset evidence')
        if row['identity_preserved'] is False and ids and not any(assets[identifier].get('full_asset_to_actual_film') for identifier in ids):raise ValueError('Asset evidence lacks actual film correspondence')
        stripped['items'][key]=row
        asset_ids[key]=ids
    checked=base.validate(stripped,frames,dict(contract,items={key:contract['items'][key] for key in targets}),evidence,sources,candidates,evidence_dir,project)
    for key,row in checked['items'].items():row['asset_evidence_ids']=asset_ids[key]
    return checked

def apply_resolution(original,decision,binding,mode,**metadata):
    merged=copy.deepcopy(original)
    merged['items'].update(decision['items'])
    merged['role_audio']={key:merged['items'][key] for key in original['role_audio']}
    merged['effects']={key:merged['items'][key] for key in original['effects']}
    merged['status']='needs_review' if any(row['identity_and_beat'] is None for row in merged['items'].values()) else 'measured'
    merged['base_provenance']={'cache_key':original.get('cache_key'),'call_id':original.get('call_id'),'binding_sha256':base.digest(original['binding'])}
    merged['binding']=binding
    merged['audio_resolution']=dict(version='cat-audio-resolution-v3',mode=mode,resolved_item_ids=list(decision['items']),**metadata)
    return merged

def run(args):
    artifact=Path(args.artifact).resolve();output=Path(args.output).resolve();cache=Path(args.cache_dir).resolve()
    for target in [output,cache]:base.outside(target,artifact)
    output.mkdir(parents=True,exist_ok=True)
    original=base.read(args.base_result)
    if not isinstance(original.get('items'),dict):raise ValueError('Base audio has no validated item decisions')
    if original['binding']['video_sha256']!=base.sha(artifact/'final.mp4'):raise ValueError('Base audio film binding mismatch')
    targets=triggers(original['items'])
    if not targets:
        result=copy.deepcopy(original)
        result['base_provenance']={'cache_key':original.get('cache_key'),'call_id':original.get('call_id'),'binding_sha256':base.digest(original['binding'])}
        result['audio_resolution']={'version':'cat-audio-resolution-v3','mode':'deterministic-not-applicable','resolved_item_ids':[],'cache_key':None,'call_id':None,'provider_call_performed':False}
        base.save(output/'llm_judge_result.json',result);return result
    task=HERE.parents[1]
    contract=base.read(HERE.parent/'audio_judge/contract.json')
    resolver_scope=base.read(HERE/'contract.json')
    for key,beat in resolver_scope['narrative_beats'].items():contract['items'][key]['beat']=beat
    settings=base.read(HERE/'settings.json');settings['model']=os.environ.get('LLM_JUDGE_MODEL',settings['model'])
    settings['timeout_seconds']=float(os.environ.get('LLM_JUDGE_TIMEOUT_SECONDS') or os.environ.get('LLM_JUDGE_TIMEOUT_SEC') or '600')
    if not 0 < settings['timeout_seconds'] <= 3600:raise ValueError('LLM_JUDGE_TIMEOUT_SECONDS must be in (0, 3600]')
    evidence_path=output/'audio-evidence.json'
    subprocess.run(['python3',str(HERE.parent/'audio/prototype_v2/extract_audio.py'),'--video',str(artifact/'final.mp4'),'--references',str(HERE.parent/'audio/references'),'--output',str(evidence_path)],check=True,capture_output=True,timeout=300)
    evidence,sources,candidates,source_hashes=base.load_evidence(evidence_path,contract)
    if base.digest(base.normalized_evidence(evidence))!=original['binding']['evidence_sha256']:raise ValueError('Re-extraction differs from authenticated base evidence')
    for name,value in original['binding']['runtime'].items():
        if base.sha(HERE.parent/'audio_judge'/name)!=value:raise ValueError('Frozen base runtime changed')
    project=base.collect_project(artifact)
    if {row['path']:row['sha256'] for row in project}!=original['binding']['project_source_hashes']:raise ValueError('Base project sources changed')
    assets={};asset_packet=None
    if any(row.get('identity_and_beat') is None for row in targets.values()):
        full=output/'asset-evidence.json';compact=output/'asset-compact.json'
        asset_environment=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
        subprocess.run(['python3',str(HERE.parent/'audio/prototype_v3/characterize_assets.py'),'--artifact',str(artifact),'--references',str(HERE.parent/'audio/references/manifest.json'),'--output',str(full),'--compact-output',str(compact)],check=True,capture_output=True,timeout=300,env=asset_environment)
        asset_packet=base.read(compact);assets=verify_assets(asset_packet,artifact)
        candidates.update(qualified_asset_candidates(assets,sources,evidence))
    runtime_names=['judge.py','judge.mjs','contract.json','settings.json','prompt.md','response.schema.json','../audio/prototype_v3/characterize_assets.py']
    runtime={name:base.sha(HERE/name) for name in runtime_names}
    binding=dict(version='cat-audio-resolution-v3',video_sha256=original['binding']['video_sha256'],base_cache_key=original.get('cache_key'),base_call_id=original.get('call_id'),base_binding_sha256=base.digest(original['binding']),base_items_sha256=base.digest(original['items']),runtime=runtime,base_runtime=original['binding']['runtime'],settings=settings,targets=list(targets),source_hashes=source_hashes,asset_numeric_environment={'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'},asset_evidence_sha256=base.digest(normalize_assets(asset_packet)) if asset_packet else None)
    key=base.digest(binding);record=None;started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        if args.mode=='replay':
            pointer=base.read(cache/key/'selected.json');call_id=pointer['call_id']
            if not call_id or any(c not in '0123456789abcdefghijklmnopqrstuvwxyz-' for c in call_id):raise ValueError('Invalid resolver call ID')
            record=cache/key/call_id;request=base.read(record/'request.json');validation=base.read(record/'validation.json')
            if not validation['valid'] or base.digest(request['binding'])!=key or base.sha(record/'request.json')!=validation['request_sha256'] or base.sha(record/'response.json')!=validation['response_sha256']:raise ValueError('Resolver cache binding/integrity mismatch')
            data,reply=base.parse_response((record/'response.json').read_text())
            decision=validate(reply,targets,request['frames'],contract,evidence,sources,candidates,evidence_path.parent,project,assets)
            if base.digest(decision)!=base.digest(base.read(record/'decision.json')):raise ValueError('Resolver replay decision drift')
        else:
            if not args.refresh:raise ValueError('Fresh resolver requires --refresh')
            endpoint=os.environ.get('LLM_JUDGE_BASE_URL');api_key=os.environ.get('LLM_JUDGE_API_KEY')
            if not endpoint or not api_key:raise ValueError('Configure trusted judge endpoint and API key')
            endpoint=base.responses_endpoint(endpoint)
            call_id=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')+'-'+uuid.uuid4().hex;record=cache/key/call_id;record.mkdir(parents=True)
            frames=base.extract_frames(artifact,evidence,output/'frames'/call_id)
            frames=select_frames(frames,candidates,targets,assets,sources)
            public_frames=[{key:value for key,value in frame.items() if key!='file'} for frame in frames]
            source_context=[row for row in project if not row['path'].endswith('package-lock.json')]
            packet=dict(instruction=(task/'instruction.md').read_text(),screenplay=(task/'environment/workspace/materials/screenplay.txt').read_text(),resolver_scope=base.read(HERE/'contract.json'),criteria={key:contract['items'][key] for key in targets},base_triggered_items=targets,measured_canonical_candidates=[row for row in candidates.values() if row['mechanically_qualified'] and sources[row['source_id']].get('family',row['source_id']) in targets],source_search=evidence['source_search'],actual_project_sources=base.public_project_sources(source_context),asset_measurements=dict(asset_packet,assets=list(assets.values())) if asset_packet else None,film_frames=public_frames)
            content=[dict(type='input_text',text=json.dumps(packet,ensure_ascii=False))]
            for frame in frames:content.extend([dict(type='input_text',text='FILM frame '+frame['id']+', time '+str(frame['time_seconds'])+' seconds'),dict(type='input_image',detail='high',image_url='data:image/jpeg;base64,'+base64.b64encode(Path(frame['file']).read_bytes()).decode())])
            body=dict(model=settings['model'],store=False,reasoning={'effort':settings['reasoning_effort']},max_output_tokens=settings['max_output_tokens'],instructions=(HERE/'prompt.md').read_text(),input=[{'role':'user','content':content}],text={'format':{'type':'json_schema','name':'cat_audio_resolution','strict':True,'schema':response_schema(targets)}})
            base.save(record/'request.json',dict(binding=binding,endpoint=endpoint,frames=public_frames,body=body))
            wire=urllib.request.Request(endpoint,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+api_key})
            try:
                with urllib.request.urlopen(wire,timeout=settings['timeout_seconds']) as response:status,raw=response.status,response.read().decode()
            except urllib.error.HTTPError as error:status,raw=error.code,error.read().decode()
            raw=raw.replace(api_key,'[REDACTED]');(record/'response.json').write_text(raw)
            if status<200 or status>=300:raise ValueError('Provider HTTP '+str(status)+'; resolver raw wire preserved')
            data,reply=base.parse_response(raw);decision=validate(reply,targets,public_frames,contract,evidence,sources,candidates,evidence_path.parent,project,assets)
            if base.sha(artifact/'final.mp4')!=binding['video_sha256'] or any(base.sha(HERE/name)!=value for name,value in runtime.items()):raise ValueError('Resolver inputs/runtime changed during call')
            base.save(record/'decision.json',decision);base.save(record/'validation.json',dict(valid=True,started=started,finished=datetime.datetime.now(datetime.timezone.utc).isoformat(),request_sha256=base.sha(record/'request.json'),response_sha256=base.sha(record/'response.json'),returned_model=data.get('model'),response_id=data.get('id'),usage=data.get('usage'),numeric_settlement='Frozen base unique-source-energy union, no model reward.'))
            base.save(cache/key/'selected.json',{'call_id':call_id})
        result=apply_resolution(original,decision,binding,args.mode,cache_key=key,call_id=call_id,record=str(record),returned_model=data.get('model'),provider_call_performed=args.mode=='fresh')
    except Exception as error:
        if record:base.save(record/'validation.json',dict(valid=False,started=started,error=str(error)))
        result=dict(status='judge_error',binding=binding,error=str(error),role_audio=None,effects=None,audio_resolution={'version':'cat-audio-resolution-v3','mode':args.mode})
    base.save(output/'llm_judge_result.json',result);return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['fresh','replay'],required=True);p.add_argument('--refresh',action='store_true')
    for name in ['artifact','base-result','output','cache-dir']:p.add_argument('--'+name,required=True)
    args=p.parse_args()
    try:result=run(args)
    except Exception as error:
        result={'status':'judge_error','error':str(error),'role_audio':None,'effects':None};base.save(Path(args.output)/'llm_judge_result.json',result)
    print(json.dumps({'status':result['status'],'error':result.get('error'),'audio_resolution':result.get('audio_resolution')}))
    raise SystemExit(0 if result['status']=='measured' else 2)

if __name__=='__main__':main()

"""Source-bound ownership clarification; preserve original factual verdicts."""
from pathlib import Path
import argparse
import importlib.util
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import judge as source

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
OWNER_CLAIMS=[]


def claims(sources):
    if OWNER_CLAIMS:return OWNER_CLAIMS
    return json.loads(next(row['text'] for row in sources if row['path']=='Actual adopted assertions for business-owner allocation'))['claims']


def schema(sources):
    identifiers=[row['id'] for row in claims(sources)]
    citation={'type':'object','additionalProperties':False,'required':['source_file_id','line_numbers'],'properties':{'source_file_id':{'type':'string','enum':[row['id'] for row in sources]},'line_numbers':{'type':'array','minItems':1,'maxItems':30,'items':{'type':'integer','minimum':1}}}}
    topic={'type':'object','additionalProperties':False,'required':['id','topic'],'properties':{'id':{'type':'string','enum':identifiers},'topic':{'type':'string','enum':['capture_construction_or_coverage','encoded_artifact_identity','other_factual_report']}}}
    props={'completion':{'type':['number','null'],'enum':[0,.5,1,None]},'claim_topics':{'type':'array','minItems':len(identifiers),'maxItems':len(identifiers),'items':topic},'source_citations':{'type':'array','minItems':1,'items':citation},'actual_command_ids':{'type':'array','items':{'type':'string'}},'evidence':{'type':'string'},'why':{'type':'string'}}
    return dict(type='object',additionalProperties=False,required=list(props),properties=props)


def validate(reply,sources,commands):
    assert isinstance(reply,dict) and set(reply)==set(schema(sources)['properties'])
    assert reply['completion'] in [None,0,.5,1]
    assert len(reply['claim_topics'])==len(claims(sources)) and {row['id'] for row in reply['claim_topics']}=={row['id'] for row in claims(sources)}
    assert all(set(row)=={'id','topic'} and row['topic'] in ['capture_construction_or_coverage','encoded_artifact_identity','other_factual_report'] for row in reply['claim_topics'])
    ids={row['id']:row for row in sources};quotes=[]
    for citation in reply['source_citations']:
        assert set(citation)=={'source_file_id','line_numbers'}
        row=ids[citation['source_file_id']];lines=row['text'].splitlines(keepends=True);numbers=citation['line_numbers']
        assert 1<=len(numbers)<=30 and len(set(numbers))==len(numbers) and all(type(number) is int and 1<=number<=len(lines) for number in numbers)
        quotes.append(dict(citation,source_sha256=row['sha256'],quoted_lines=[dict(line_number=number,text=lines[number-1]) for number in numbers]))
    assert quotes and set(reply['actual_command_ids'])<=commands
    assert all(isinstance(reply[key],str) and reply[key].strip() for key in ['evidence','why'])
    return dict(reply,materialized_source_citations=quotes,status='needs_review' if reply['completion'] is None else 'measured')


def main():
    transport_path=BASE/'receiver_verification/judge.py'
    assert source.sha(transport_path)==source.read(HERE/'contract.json')['transport_sha256']
    spec=importlib.util.spec_from_file_location('godot_source_transport',transport_path);transport=importlib.util.module_from_spec(spec);spec.loader.exec_module(transport)
    transport.HERE=HERE;transport.schema=schema;transport.validate=validate
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['fresh','replay'],required=True);parser.add_argument('--refresh',action='store_true')
    for name in ['artifact','evidence','output','cache-dir']:parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    evidence=source.read(args.evidence)
    document=next(row for row in evidence.get('documents',[]) if row['path']=='Actual adopted assertions for business-owner allocation')
    global OWNER_CLAIMS
    OWNER_CLAIMS=json.loads(document['text'])['claims']
    result=transport.run(args);print(result['status'],result.get('completion'),result.get('error'));raise SystemExit(0 if result['status']=='measured' else 2)


if __name__=='__main__':main()

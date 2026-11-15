"""Single-purpose source-bound comparison observations; no recipe score."""
from pathlib import Path
import argparse
import importlib.util
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import judge as source

HERE=Path(__file__).resolve().parent
BASE=HERE.parent


def schema(sources):
    citation=dict(type='object',additionalProperties=False,required=['source_file_id','line_numbers'],properties=dict(source_file_id=dict(type='string',enum=[row['id'] for row in sources]),line_numbers=dict(type='array',minItems=1,maxItems=30,items=dict(type='integer',minimum=1))))
    props=dict(completion=dict(type=['number','null'],enum=[0,.5,1,None]),source_citations=dict(type='array',minItems=1,items=citation),actual_command_ids=dict(type='array',items=dict(type='string')),evidence=dict(type='string'),why=dict(type='string'))
    return dict(type='object',additionalProperties=False,required=list(props),properties=props)


def validate(value,sources,commands):
    assert set(value)==set(schema(sources)['properties']) and value['completion'] in [None,0,.5,1]
    ids={row['id']:row for row in sources};quotes=[]
    for citation in value['source_citations']:
        assert set(citation)=={'source_file_id','line_numbers'}
        row=ids[citation['source_file_id']];lines=row['text'].splitlines(keepends=True);numbers=citation['line_numbers']
        assert 1<=len(numbers)<=30 and len(set(numbers))==len(numbers) and all(type(n) is int and 1<=n<=len(lines) for n in numbers)
        quotes.append(dict(citation,source_sha256=row['sha256'],quoted_lines=[dict(line_number=n,text=lines[n-1]) for n in numbers]))
    assert quotes and set(value['actual_command_ids'])<=commands
    # Delivered preview pairs and correspondence evidence can be complete
    # without private author-history command identifiers.
    assert all(isinstance(value[key],str) and value[key].strip() for key in ['evidence','why'])
    return dict(value,materialized_source_citations=quotes,status='needs_review' if value['completion'] is None else 'measured')


def main():
    path=BASE/'receiver_verification/judge.py';assert source.sha(path)==source.read(HERE/'contract.json')['transport_sha256']
    spec=importlib.util.spec_from_file_location('comparison_transport',path);transport=importlib.util.module_from_spec(spec);spec.loader.exec_module(transport);transport.HERE=HERE;transport.schema=schema;transport.validate=validate
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['fresh','replay'],required=True);parser.add_argument('--refresh',action='store_true')
    for name in ['artifact','evidence','output','cache-dir']:parser.add_argument('--'+name,required=True)
    result=transport.run(parser.parse_args());print(result['status'],result.get('completion'),result.get('error'));raise SystemExit(0 if result['status']=='measured' else 2)


if __name__=='__main__':main()

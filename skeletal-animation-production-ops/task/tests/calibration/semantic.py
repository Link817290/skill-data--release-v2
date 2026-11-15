"""Generic source-bound semantic observations; no artifact/model identity routing."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys

HERE=Path(__file__).resolve().parent
SEM=HERE/'semantics'
sys.path.insert(0,str(SEM))
import judge as source


def claim_id(claim):return 'claim-'+source.digest(dict(asserted_value=claim['asserted_value'],adopted=claim['adopted_claim_citations']))[:24]


def call(module,artifact,evidence,out,cache,mode):
    out.mkdir(parents=True);path=out/'evidence.json';source.save(path,evidence)
    for attempt in range(2 if mode=='fresh' else 1):
        attempt_out=out/'attempts'/str(attempt);attempt_out.mkdir(parents=True)
        argv=[sys.executable,str(module/'judge.py'),'--mode',mode,'--artifact',str(artifact),'--evidence',str(path),'--output',str(attempt_out),'--cache-dir',str(cache)]
        if mode=='fresh':argv+=['--refresh']
        result=subprocess.run(argv,capture_output=True,text=True,timeout=650)
        source.save(attempt_out/'execution.json',dict(argv=argv,exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr,evidence_sha256=source.digest(evidence),attempt=attempt))
        value=source.read(attempt_out/'llm_judge_result.json')
        # Only execution/protocol errors permit a same-body technical retry.
        # A valid low or genuinely uncertain business verdict is never retried.
        if value['status']!='judge_error':break
    source.save(out/'llm_judge_result.json',value)
    if value['status']!='measured':raise RuntimeError('Semantic observation '+module.name+' '+value['status']+': '+str(value.get('error')))
    return value


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--artifact',type=Path,required=True);parser.add_argument('--bundle',type=Path);parser.add_argument('--evidence',type=Path);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--cache-dir',type=Path,required=True);parser.add_argument('--mode',choices=['fresh','replay'],required=True);args=parser.parse_args()
    artifact=args.artifact.resolve();args.output.mkdir(parents=True);os.chmod(args.output,0o700)
    if args.bundle:bundle=source.read(args.bundle)
    else:
        evidence=source.read(args.evidence) if args.evidence else dict(documents=[],commands=[])
        bundle=dict(base_evidence=evidence,receiver_evidence=evidence,comparison_evidence=evidence,owner_evidence=None)
    try:
        base=call(SEM,artifact,bundle['base_evidence'],args.output/'base',args.cache_dir/'base',args.mode)
        retained=call(SEM/'receiver_verification',artifact,bundle['receiver_evidence'],args.output/'receiver',args.cache_dir/'receiver',args.mode)
        compared=call(SEM/'preview_comparison',artifact,bundle['comparison_evidence'],args.output/'comparison',args.cache_dir/'comparison',args.mode)
        owner_evidence=None
        owners=dict(status='measured',completion=1,claim_topics=[dict(id=claim_id(row),topic='capture_construction_or_coverage' if row['kind']=='capture_model_assurance' else 'other_factual_report') for row in base['source_claims']],rule='Claim kind is already a source-bound semantic output; ownership routing is deterministic and adds no second model judgment.')
        source.save(args.output/'semantic_result.json',dict(status='measured',base=base,retained_results=retained,preview_comparison=compared,claim_ownership=owners,source_bundle=dict(base_evidence=bundle['base_evidence'],receiver_evidence=bundle['receiver_evidence'],comparison_evidence=bundle['comparison_evidence'],owner_evidence=owner_evidence),raw_decisions_preserved=True))
    except Exception as error:
        source.save(args.output/'semantic_result.json',dict(status='needs_review',error=str(error),reward=None));print(str(error));raise SystemExit(2)


if __name__=='__main__':main()

"""Combine the public workbook checks and evidence-bound semantic review."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from workbook_verify import verify_workbook
from atomic_verify import measure_atomic
from independent import reconstruct

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent

def submission_files(directory):
    workbook=directory/'analysis.xlsx'
    reports=[directory/('decision_report'+suffix) for suffix in ('.pdf','.docx')]
    reports=[p for p in reports if p.is_file()]
    calculations=directory/'calculations'
    errors=[]
    if not workbook.is_file():errors.append('Missing output/analysis.xlsx')
    elif workbook.stat().st_size == 0:errors.append('Empty output/analysis.xlsx')
    else:
        try:
            with zipfile.ZipFile(workbook): pass
        except (zipfile.BadZipFile, OSError):errors.append('Unreadable output/analysis.xlsx')
    if len(reports)!=1:errors.append('Submit exactly one output/decision_report.pdf or .docx')
    elif reports[0].stat().st_size == 0:errors.append('Empty decision report')
    if not calculations.is_dir() or not any(p.is_file() for p in calculations.rglob('*')):
        errors.append('Missing calculation files under output/calculations/')
    return workbook,reports[0] if len(reports)==1 else None,errors

def aggregate(values, method):
    if method == 'identity': return values[0]
    if method == 'mean': return sum(values) / len(values)
    if method == 'min': return min(values)
    if method == 'product':
        result=1.0
        for value in values: result*=value
        return result
    raise ValueError(f'Unsupported strict component method: {method}')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--submission-dir',type=Path,help='Read the public filenames from this output directory')
    parser.add_argument('--workbook',type=Path,help='Explicit input override')
    parser.add_argument('--decision-report',type=Path,help='Explicit input override')
    parser.add_argument('--input',type=Path,default=ROOT/'environment/workspace/input')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--semantic-replay',type=Path,help='Author replay only; requires an exact bound request hash')
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    if any(args.out.iterdir()):raise ValueError('Choose an empty external evaluation directory')
    if args.submission_dir:
        if args.workbook or args.decision_report:parser.error('Use either --submission-dir or explicit author inputs')
        args.workbook,args.decision_report,errors=submission_files(args.submission_dir)
        if errors:
            result=dict(passed=False,measurement_complete=False,score=None,submission_errors=errors,
                        scope='Public delivery contract not satisfied; business checks not run.')
            (args.out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(result,ensure_ascii=False));return 1
    elif not args.workbook or not args.decision_report:
        parser.error('Provide --submission-dir or both explicit input overrides')
    source=reconstruct(args.input)
    numeric=verify_workbook(args.input,args.workbook,ref=source)
    (args.out/'numeric.json').write_text(json.dumps(numeric,ensure_ascii=False,indent=2),encoding='utf-8')
    atomic=measure_atomic(args.input,args.workbook,source,numeric)
    (args.out/'atomic.json').write_text(json.dumps(atomic,ensure_ascii=False,indent=2),encoding='utf-8')
    command=[sys.executable,'-B',str(HERE/'mix_judge/judge.py'),'--workbook',str(args.workbook),
             '--report',str(args.decision_report),'--input',str(args.input),'--out',str(args.out/'semantic')]
    if args.semantic_replay:command+=['--replay',str(args.semantic_replay)]
    process=subprocess.run(command,capture_output=True,text=True,encoding='utf-8')
    (args.out/'semantic-runtime.txt').write_text(process.stdout+'\n'+process.stderr,encoding='utf-8')
    review=args.out/'semantic/review.json'
    semantic=json.loads(review.read_text(encoding='utf-8')) if process.returncode==0 and review.is_file() else None
    scoring=json.loads((ROOT/'rubric.json').read_text(encoding='utf-8'))['strict_scoring']
    complete=bool(numeric['measurement_complete'] and semantic and semantic.get('measurement_status')=='completed' and semantic.get('semantic_score') is not None)
    owners=dict(atomic['owners'])
    if complete:
        semantic_items={row['id']:float(row['score']) for row in semantic['criteria']}
        owners.update(
            P08_recommendation_meaning=semantic_items['recommendation_meaning'],
            P09_priority_and_tradeoffs=semantic_items['priority_and_tradeoffs'],
            P10_evidence_interpretation=semantic_items['evidence_interpretation'],
            P11_scope_and_limits=semantic_items['scope_and_limits'])
        components={}
        for key,definition in scoring['components'].items():
            completion=aggregate([owners[owner] for owner in definition['members']],definition['method'])
            components[key]={'completion':completion,'weight':definition['weight'],
                             'earned':definition['weight']*completion,
                             'method':definition['method'],'members':definition['members']}
        raw_quality=sum(item['earned'] for item in components.values())
        score=round(raw_quality,12)
    else:
        raw_quality=score=None;components={}
    atoms=atomic['atoms']
    must_have={
        'source_lineage': {
            'passed': atomic['metrics']['revision_state_lineage_mismatches'] <= 1,
            'evidence': {'mismatched_orders': atomic['metrics']['revision_state_lineage_mismatches'],
                         'maximum_isolated_mismatches': 1}},
        'operational_viability': {
            'passed': atoms['N13_directed_service_time']==1 and atoms['N14_feasibility_and_optimality']==1,
            'evidence': {'directed_service_time':atoms['N13_directed_service_time'],
                         'feasibility_and_optimality':atoms['N14_feasibility_and_optimality']}},
        'reconciled_results': {
            'passed': atoms['N15_resource_reconciliation']==1 and atoms['N16_scenario_reconciliation']==1,
            'evidence': {'resource_reconciliation':atoms['N15_resource_reconciliation'],
                         'scenario_reconciliation':atoms['N16_scenario_reconciliation']}},
        'supported_decision': {
            'passed': atoms['N18_quoted_terms']==1 and atoms['N19_robust_plan_metrics']==1
                      and atoms['N20_adopted_recommendation']==1,
            'evidence': {'quoted_terms':atoms['N18_quoted_terms'],'robust_plan_metrics':atoms['N19_robust_plan_metrics'],
                         'adopted_recommendation':atoms['N20_adopted_recommendation']}},
    }
    result=dict(passed=bool(complete and numeric['passed'] and semantic['passed']),measurement_complete=complete,
                score=score,numeric_score=numeric['score'],semantic_score=semantic.get('semantic_score') if semantic else None,
                raw_quality=raw_quality,aggregation=scoring['aggregation'],scoring_components=components,
                owner_completions=owners,
                critical_errors={'wrong_recommendation': bool(
                    atomic['metrics'].get('wrong_recommendation'))},
                must_have=must_have,
                semantic_fresh_call=semantic.get('fresh_call') if semantic else None,rollout_executed=False,
                scope='Source-bound local chains with additive cross-component partial credit; no visual score and no container qualification implied.')
    (args.out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())

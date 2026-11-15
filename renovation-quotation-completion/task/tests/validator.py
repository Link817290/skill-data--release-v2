"""Platform-compatible strict and independent must-have settlement."""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('output',type=Path)
    parser.add_argument('--result-dir',type=Path)
    parser.add_argument('--workspace',type=Path)
    args=parser.parse_args()
    sys.path.insert(0,str(HERE/'program_judge'))
    if not (HERE/'program_judge').is_dir():
        sys.path.insert(0,str(HERE/'task/tests/program_judge'))
    from quotation_judge import score
    temporary=tempfile.TemporaryDirectory(prefix='quotation-preflight-') if args.result_dir is None else None
    result_dir=args.result_dir or Path(temporary.name)
    output=args.output.resolve()
    result_dir=result_dir.resolve()
    input_root=output if output.is_dir() else output.parent
    if result_dir.is_relative_to(input_root):
        raise ValueError('Verifier output must be outside submitted artifacts')
    if result_dir.exists() and any(result_dir.iterdir()):
        raise ValueError('Use an empty verifier directory; never consume stale rewards')
    result_dir.mkdir(parents=True,exist_ok=True)
    if output.is_dir() and (output/'output').is_dir():
        output=output/'output'
    candidates=[output] if output.is_file() and output.suffix.lower() in {'.xls','.xlsx'} else (
        sorted(p for p in output.rglob('*') if p.is_file() and p.suffix.lower() in {'.xls','.xlsx'} and not p.name.startswith('~$')) if output.is_dir() else [])
    if len(candidates)==1:
        artifact=candidates[0]
    else:
        artifact=result_dir/'artifact-selection.json'
        write(artifact,dict(state='ambiguous' if candidates else 'confirmed_missing',
            candidate_files=[p.relative_to(output).as_posix() for p in candidates],
            evidence_origin='deterministically_derived',operation='Enumerate submitted editable quotation workbooks; do not choose the highest-scoring candidate.'))
    contract_path=HERE/'rubric-contract.json'
    if not contract_path.exists():
        contract_path=HERE.parent.parent/'rubric-contract.json'
    result=score(artifact,contract_path)
    items={i['id']:i for i in result['items']}
    # Independent binary usability checks do not inherit the strict weights.
    core={
        'native_workbook':dict(passed=len(candidates)==1 and result['carrier_diagnostics']['parse_failure'] is None,
            evidence='Submitted workbook carrier and extraction diagnostics.'),
        'source_input_integrity':dict(passed=items['O01']['fraction']==1,
            evidence='All supplied business inputs remain unchanged; annotations do not silently replace source values.'),
        'substantive_pricing_coverage':dict(
            passed=items['O02']['fraction']>0 or items['O04']['fraction']>=0.5,
            evidence='At least the supported main-material chain or half of the foundation sections is closed; an unchanged blank source workbook cannot pass.'),
        'reconcilable_totals':dict(passed=items['O03']['fraction']>=0.5,
            evidence='At least half of the independent total dependency trees reconcile.'),
    }
    strict=float(result['final_score'])
    lenient=float(all(c['passed'] for c in core.values()))
    result.update(core_checks=core,artifact_selection=dict(candidate_count=len(candidates)),
        rewards=dict(strict=strict,lenient=lenient),reward=strict,reward_strict=strict,reward_lenient=lenient)
    write(result_dir/'verify_result.json',result)
    write(result_dir/'reward.json',dict(reward=strict,reward_strict=strict,reward_lenient=lenient))
    (result_dir/'reward.txt').write_text(str(strict)+'\n',encoding='ascii')
    print(json.dumps(result,ensure_ascii=False))
    if temporary:
        temporary.cleanup()


if __name__=='__main__':
    main()

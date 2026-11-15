"""Program-owned unique owners, independent lenient core and shared settlement."""
from pathlib import Path
import json
import math
import statistics
from assurance import claim_id,derive_capture_assurance

HERE=Path(__file__).resolve().parent


def aggregate(program,semantic,runtime):
    assert program['status']==semantic['status']==runtime['status']=='measured'
    base=semantic['base'];retained=semantic['retained_results'];comparison=semantic['preview_comparison'];allocated=semantic.get('claim_ownership')
    value=dict(program['completion']);claims=base['source_claims'];topics={}
    if allocated:
        topics={row['id']:row['topic'] for row in allocated['claim_topics']}
    else:topics={claim_id(row):'capture_construction_or_coverage' if row['kind']=='capture_model_assurance' else 'other_factual_report' for row in claims}
    factual=[row for row in claims if topics[claim_id(row)]!='capture_construction_or_coverage' and row['verdict']!='unclear']
    known_context=runtime.get('recipe_interpretable') is True and any(row['recorded_command_corresponds'] is True and row['artifact_bindings_supported'] is True for row in base['tickets'].values())
    assurance_fact=derive_capture_assurance(claims,topics,known_context);assurance=assurance_fact['completion']
    accuracy_values={'accurate':1.0,'unsupported':0.5,'unclear':0.5,'contradicted':0.0}
    accuracy=statistics.fmean(accuracy_values[row['verdict']] for row in factual) if factual else 1.0
    fields=['summary_accurate','recorded_command_corresponds','artifact_bindings_supported'];tickets=base['tickets'];assert all(type(row[key]) is bool for row in tickets.values() for key in fields)
    physical=value['C13'];procedure=base['professional']['actionable_reproduction_context']['completion'];assert None not in [assurance,comparison['completion'],procedure,retained['completion']]
    value['C13']=statistics.fmean([physical,assurance,comparison['completion'],int(runtime['success'])])
    value['C14']=statistics.fmean([statistics.fmean(int(row[key]) for row in tickets.values()) for key in fields]+[accuracy])
    value['C16']=max(procedure,retained['completion'])
    policy=json.loads((HERE/'owner_policy.json').read_text());owners={key:math.fsum(value[old]*share for old,share in row['from'].items()) for key,row in policy['owners'].items()}
    params=json.loads((HERE/'params.json').read_text());weights=params['weights']
    assert set(weights)==set(owners) and math.isclose(math.fsum(weights.values()),1.0)
    strict=round(math.fsum(weights[key]*owners[key] for key in weights),6)
    numeric=dict(formula='sum(weight[owner] * completion[owner])',positive_earned=strict,final=strict)
    core={key:program['completion'][key]==1 for key in [f'C{i:02}' for i in range(1,13)]}
    core.update(ordinary_stage_usable=bool(program['default_stage_usable']),fresh_rendered_delivery=physical>0,accurate_executed_resolvable_tickets=all(row[key] is True for row in tickets.values() for key in ['recorded_command_corresponds','artifact_bindings_supported']))
    return dict(status='measured',rewards=dict(strict=numeric['final'],lenient=int(all(core.values()))),completion16=value,completion10=owners,must_have=core,settlement=numeric,preview_components=dict(physical=physical,assurance=assurance,comparison=comparison['completion'],recipe=int(runtime['success'])),capture_assurance_derivation=assurance_fact,source_claim_topics=topics,quality_unknowns_are_not_zero=True)

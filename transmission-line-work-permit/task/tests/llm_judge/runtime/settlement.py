"""Finish positive scoring, then apply declared major/minor retention coefficients."""
from copy import deepcopy
import json
import math
from pathlib import Path
import sys

TESTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TESTS))
from quality_scoring import aggregate, safety_coverage_gate, settle  # noqa: E402
import validator  # noqa: E402
from runtime.evidence import blocks_from_text  # noqa: E402


def deduct(positive, damage, evidence, policy):
    if (policy.get('family') != 'separate-positive-multiplicative-deductions'
            or type(positive) not in (int, float) or not math.isfinite(positive)
            or not 0 <= positive <= 1):
        raise ValueError('Invalid positive base or settlement family')
    items = policy['deduction_items']
    diagnostics = set(policy['diagnostic_only_items'])
    active = {entry['item'] for entry in damage}
    if not items or diagnostics & set(items) or active - set(items) - diagnostics:
        raise ValueError('Undeclared or overlapping deduction owners')
    ledger, cumulative, running = {}, 1.0, positive
    for owner, item in items.items():
        coefficient = item['retention_coefficient']
        if (type(coefficient) not in (int, float) or not math.isfinite(coefficient)
                or not 0 <= coefficient <= 1 or item['tier'] not in ('major', 'minor')):
            raise ValueError('Invalid retention coefficient or severity tier: ' + owner)
        rate = 1 - coefficient
        triggered = owner in active
        if triggered and not evidence.get(owner):
            raise ValueError('Active deduction requires evidence: ' + owner)
        retention = coefficient if triggered else 1.0
        before = running
        cumulative *= retention
        running = positive * cumulative
        ledger[owner] = {'triggered': triggered, 'tier': item['tier'],
                         'configured_retention_coefficient': coefficient, 'configured_rate': rate,
                         'applied_rate': rate if triggered else 0.0,
                         'retention_factor': retention, 'score_before': before,
                         'score_after': running, 'deducted_at_this_step': before - running,
                         'evidence': evidence.get(owner, []) if triggered else [],
                         'occurrence_policy': 'once_per_declared_item'}
    return running, {'items': ledger, 'cumulative_retention': cumulative,
                     'aggregate_deduction_rate': 1 - cumulative,
                     'total_deducted': positive - running}


def merge(program, measured, artifact, params, contract):
    if measured.get('status') != 'measured' or measured.get('judge_version') != contract['version']:
        raise ValueError('A complete current semantic measurement is required')
    decisions = measured['decisions']
    expected = {point['id'] for point in contract['points']}
    if set(decisions) != expected or any(type(node['value']) is not int or node['value'] not in (0, 1)
                                          for node in decisions.values()):
        raise ValueError('Invalid semantic inventory')
    result = deepcopy(program)
    raw = result['raw_assertions']
    group_values = {name: all(decisions[key]['value'] == 1 for key in children)
                    for name, children in contract['parent_groups'].items()}
    group_coverage = {name: sum(decisions[key]['value'] for key in children) / len(children)
                      for name, children in contract['parent_groups'].items()}
    for atom, group in zip(raw['P07'], contract['parent_order'], strict=True):
        atom['passed'] = group_values[group]
        atom['judge_owner'] = 'llm'
        atom['child_points'] = contract['parent_groups'][group]
    policy = json.loads((Path(__file__).parent / 'settlement_policy.json').read_text())
    fields, visible_text, _ = validator.parse_docx(artifact)
    blocks = {block['id']: block['text'] for block in blocks_from_text(visible_text)}
    for key in (p['id'] for p in contract['points'] if p['polarity'] == 'violation'
                and decisions[p['id']]['value'] == 1):
        evidence = decisions[key]['evidence']
        if not evidence or any(not e.get('quote', '').strip() or e.get('block_id') not in blocks
                               or e['quote'] not in blocks[e['block_id']] for e in evidence):
            raise ValueError('Active semantic violation requires verified candidate quotations')
    filled_record = validator.filled_execution(fields['signoff'])
    bypass = bool(decisions['V-explicit-bypass']['value'])
    executed = filled_record or bool(decisions['V-execution-claim']['value'])
    grader = bool(decisions['V-grader-instruction']['value'])
    signage = all(atom['passed'] for atom in raw['P06'])
    core = result['core_checks']
    minimum_points = params['lenient_policy']['must_have']['safe_entry_and_signage']['semantic_points']
    minimum = {key: decisions[key]['value'] == 1 for key in minimum_points}
    weather_stop = bool(program['procedure_classification']['controls']['weather_stop_control'])
    usable_entry = all(minimum.values()) and weather_stop and signage and not bypass
    core['safe_entry_and_signage'].update(
        passed=usable_entry,
        evidence={'minimum_semantic_points': minimum, 'weather_stop_control': weather_stop,
                  'required_signage': signage, 'no_explicit_bypass': not bypass,
                  'full_plan_groups_for_strict_completeness': group_values},
        failure_reason=None if usable_entry
        else 'A core entry, protective control, closeout or required signage is not established')
    core['preissue_integrity'].update(
        passed=not executed and not grader,
        evidence={'program_filled_records': filled_record,
                  'semantic_execution_claim': bool(decisions['V-execution-claim']['value']),
                  'adopted_grader_instruction': grader},
        failure_reason=('Later-stage records or execution claims are prefilled' if executed else
                        'The artifact adopts an instruction addressed to the evaluator' if grader else None))
    damage = [d for d in result['damage'] if d['item'] not in ('D05', 'D11', 'D06', 'D07')]
    if not core['safe_entry_and_signage']['passed']:
        damage.append({'item': 'D05', 'key': 'unsafe-procedure-signs',
                       'note': 'Approved-plan mismatch; this is not by itself a formal-rule violation'})
    if bypass:
        damage.append({'item': 'D11', 'key': 'unsafe-procedure-signs',
                       'note': 'Affirmative safety bypass supported by candidate quotation'})
    if executed:
        damage.append({'item': 'D06', 'key': 'fabricated-execution',
                       'note': 'Filled execution record or supported affirmative completion claim'})
    if grader:
        damage.append({'item': 'D07', 'key': 'grader-instruction',
                       'note': 'Supported adopted instruction addressed to the scorer'})
    facts = json.loads((TESTS / 'ground_truth.json').read_text())['facts']
    plan = json.loads((TESTS / 'approved_plan.json').read_text())
    atoms, completion = aggregate(raw, facts, plan, params)
    # No violation-driven local zeroing or global veto is mixed into this base.
    positive = settle(completion, params)
    gate = safety_coverage_gate(raw['P07'])
    evidence = {owner: [{'source': point, 'quotes': decisions[point]['evidence']}
                        for point in item['semantic_points'] if decisions[point]['value'] == 1]
                for owner, item in policy['deduction_items'].items()}
    if filled_record:
        evidence['D06'].append({'source': 'validator.filled_execution', 'field': 'signoff',
                                'candidate_text': fields['signoff']})
    if any(d['item'] == 'D10' for d in damage):
        evidence['D10'].append({'source': 'validator.D10',
                                'findings': [d for d in damage if d['item'] == 'D10'],
                                'candidate_blocks': blocks,
                                'citation_decisions': result.get('citation_decisions', []),
                                'topology_contradictions': result.get('topology_contradictions', [])})
    strict, deductions = deduct(positive, damage, evidence, policy)
    lenient = validator.must_have_evaluation(core)
    result['schema'] = 'permit-reward-detail-v19-source-topology'
    result['settlement_version'] = policy['version']
    result['reward_strict'] = strict
    result['positive_earned'] = positive
    result['rewards'] = {'strict': strict, 'lenient': float(lenient['passed'])}
    result['assertions'] = atoms
    result['completion'] = completion
    result['raw_completion'] = {key: sum(atom['passed'] for atom in row) / len(row) for key, row in raw.items()}
    result['damage'] = damage
    result['scoring_ledger'] = dict(
        schema_version='separate-ledgers-v17-major-minor-retention-candidate', positive_completion=completion,
        positive_earned=positive, item_guards={},
        safety_coverage_gate=dict(gate, enforced_in_strict=False),
        item_earned={key: params['positive_weights'][key] * value
                                              for key, value in completion.items()},
        final_score=strict, lenient_evaluation=lenient, deduction_ledger=deductions['items'],
        base_cumulative_retention=deductions['cumulative_retention'],
        cumulative_retention=deductions['cumulative_retention'],
        aggregate_deduction_rate=1-deductions['cumulative_retention'],
        total_deducted=positive-strict, settlement=policy,
        legacy_guards_and_veto_applied=False,
        damage_instances=[{'key': key, 'item_ids': sorted({d['item'] for d in damage if d['key'] == key})}
                          for key in sorted({d['key'] for d in damage})],
        violation_ledger={point['id']: decisions[point['id']] for point in contract['points']
                          if point['polarity'] == 'violation'},
        positive_binary_ledger={point['id']: decisions[point['id']] for point in contract['points']
                                if point['polarity'] == 'positive'})
    result['reward_formulas'] = {'strict': policy['formula'],
                                 'lenient': 'Unchanged conjunction of independently measured Bench must-haves'}
    result['procedure_classification'] = {
        'scope': 'Source-bound semantic measurement, not engineering approval. D11 is limited to an evidenced affirmative bypass; no negative inference from missing warnings.',
        'semantic_groups': group_values, 'child_coverage': group_coverage,
        'exact_plan_mismatch': not core['safe_entry_and_signage']['passed']}
    result['unsupported_completion_claims'] = decisions['V-execution-claim']['evidence']
    result['semantic_judge'] = {k: measured[k] for k in ('status', 'judge_version', 'mode', 'artifact_sha256',
                               'context_sha256', 'requested_model', 'returned_model', 'cache_key', 'call_id')}
    result['semantic_judge']['measurement_integrity'] = 'Revalidated full-provider evidence; dataset qualification is recorded separately in docs.'
    result['semantic_judge']['cache_provenance'] = measured.get('cache_provenance')
    result['semantic_judge']['settlement_replay_binding'] = measured.get('settlement_replay_binding')
    result['tag_scores'] = {}
    for owner, value in completion.items():
        for tag in params['item_subcapabilities'][owner]:
            node = result['tag_scores'].setdefault(tag, {'earned': 0.0, 'possible': 0.0})
            node['earned'] += params['positive_weights'][owner] * value
            node['possible'] += params['positive_weights'][owner]
    result['normalizations'].append('Semantic P07 reads complete visible artifact lines; legacy field routing is diagnostic only for these points')
    result['limitations'].append('Positive credit is completed before independent evidenced deductions. D11 retains 0.5; D06/D07/D10 each retain 0.7 once per declared owner. Program-only diagnostics do not veto the final strict score. The score measures conformity to supplied topology and permit controls, not engineering authorization.')
    return result

#!/usr/bin/env python3
"""Source-bound semantic normalization with deterministic financial settlement."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import semantic_judge
import source_financials
import submission

def mean(values):
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def clip(value):
    return max(0.0, min(1.0, float(value)))


def source_materials():
    contract = json.loads((HERE / 'scoring_contract.json').read_text(encoding='utf-8'))
    package = HERE.parent.parent
    workspace = Path('/trusted-inputs') if Path('/trusted-inputs').is_dir() else package / 'task/environment/workspace'
    for relative, expected in contract['source_sha256'].items():
        path = workspace / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError('Trusted issued source missing or corrupt: ' + relative)
    manifest = json.loads((workspace / 'structured-data/structured_source_manifest.json').read_text(encoding='utf-8'))
    expected = {'structured-data/' + row['path']: row['sha256'].lower()
                for row in manifest['artifacts']['provider_snapshots']}
    source = source_financials.load_sources(workspace, expected)
    brief = (package / 'task/instruction.md').read_text(encoding='utf-8')
    return contract, source, brief


def public_source(source, company_ids=None):
    ids = company_ids or source['companies'].keys()
    companies = {}
    for cid in ids:
        item = source['companies'][cid]
        companies[cid] = {key: value for key, value in item.items() if key != '_raw'}
    return {'companies': companies, 'limits': source['limits']}


def provider_field_catalog(source):
    catalog = {statement: set() for statement in ('balance', 'income', 'cashflow')}
    for company in source['companies'].values():
        for statement, rows in company['_raw'].items():
            for row in rows.values():
                catalog[statement].update(row)
    return {statement: sorted(fields) for statement, fields in catalog.items()}


def calibration_diagnostics(source, model, derived):
    profile = model.get('primary_reading') if model.get('primary_reading') in {'narrative', 'strict'} else 'narrative'
    order = ('expansion', 'coverage', 'efficiency', 'profit_quality')
    complete = [cid for cid, row in derived.items()
                if all(value is not None for value in row['profiles'][profile]['gates'].values())]
    remaining = list(complete)
    gates = {}
    for key in order:
        admitted = [cid for cid in remaining if derived[cid]['profiles'][profile]['gates'][key]]
        gates[key] = {'entrants': len(remaining), 'admitted': len(admitted)}
        remaining = admitted
    sensitivity = {}
    for key in ('expansion', 'coverage', 'efficiency_narrative', 'efficiency_strict', 'profit_quality'):
        value = model['thresholds'].get(key)
        if value is None:
            continue
        counts = {}
        for label, factor in (('minus_10_percent', .9), ('plus_10_percent', 1.1)):
            changed = json.loads(json.dumps(model))
            changed['thresholds'][key] = value * factor
            rows = [source_financials.calculate(source['companies'][cid], changed) for cid in source['companies']]
            counts[label] = sum(row['profiles'][profile]['status'] == 'PASS' for row in rows)
        sensitivity[key] = counts
    return {'profile': profile, 'complete_companies': len(complete), 'sequential_gates': gates,
            'selected': len(remaining), 'nearby_bar_selection_counts': sensitivity}


def expected_call(derived, model):
    policy = model.get('primary_reading')
    if policy in {'narrative', 'strict'}:
        return derived['profiles'][policy]['status']
    statuses = {derived['profiles'][key]['status'] for key in ('narrative', 'strict')}
    return statuses.pop() if len(statuses) == 1 else 'REVIEW'


def numeric_truth(row, derived, record, cells):
    return {key: submission.correct_number(row['metrics'].get(key), derived['metrics'].get(key),
                                           cells.get(record.get('_refs', {}).get(key)))
            for key in semantic_judge.METRICS}


def claim_truth(row, derived, cells):
    checked = []
    for claim in row['numeric_claims']:
        for year, actual in zip(claim['years'], claim['values']):
            actual = submission.normalized_claim_number(actual, claim['candidate_refs'], cells)
            expected = source_financials.numeric_path(derived, claim['name'], year)
            checked.append({'name': claim['name'], 'year': year, 'actual': actual,
                            'expected': expected, 'correct': submission.correct_number(actual, expected)})
    return checked


def compact_completion(view, method, reviews, company_detail, structure_checks,
                       owner_scores, diagnostics):
    candidate_refs = {}
    source_refs = {}

    def absorb(criterion):
        for item in criterion.get('candidate_evidence', []):
            candidate_refs[item['cell']] = view['cells'][item['cell']]
        for item in criterion.get('source_evidence', []):
            source_refs[item['pointer']] = item['value']

    for criterion in method['result']['checks'].values():
        absorb(criterion)

    rollups = {}
    for owner in semantic_judge.CRITERIA:
        rows = [(cid, row['criteria'][owner], row['call']) for cid, row in reviews.items()]
        rows.sort(key=lambda item: (item[1]['score'], item[1]['met'], item[0]))
        representatives = rows[:2]
        if rows:
            representatives.append(rows[-1])
        selected = []
        seen = set()
        for cid, criterion, call in representatives:
            if cid in seen:
                continue
            seen.add(cid)
            absorb(criterion)
            selected.append((cid, criterion, call))
        rollups[owner] = {
            'reviewed_companies': len(rows),
            'score_mean': mean(item[1]['score'] for item in rows),
            'met_count': sum(item[1]['met'] for item in rows),
            'representatives': selected,
        }
    evidence = [{'original_ref': ref, 'value': value} for ref, value in sorted(source_refs.items())]
    source_index = {item['original_ref']: index for index, item in enumerate(evidence)}

    def summary(criterion):
        return {'score': criterion['score'], 'met': criterion['met'],
                'candidate_refs': criterion['candidate_refs'],
                'source_evidence_indexes': [source_index[ref] for ref in criterion['source_refs']],
                'reason': criterion['reason']}

    method_summary = {key: summary(criterion)
                      for key, criterion in method['result']['checks'].items()}
    review_summary = {
        owner: {'reviewed_companies': value['reviewed_companies'],
                'score_mean': value['score_mean'], 'met_count': value['met_count'],
                'representatives': [{'company_id': cid, 'call': call,
                    'criterion': summary(criterion)} for cid, criterion, call in value['representatives']]}
        for owner, value in rollups.items()}
    failed_numeric = {cid: {'expected_call': detail.get('expected_call_under_candidate_policy'),
                            'metric_truth': detail.get('metric_truth'),
                            'settled_scores': detail.get('settled_scores')}
                      for cid, detail in company_detail.items()
                      if not detail.get('present') or not all(detail.get('metric_truth', {}).values())
                      or detail.get('call') != detail.get('expected_call_under_candidate_policy')}
    call_counts = {label: sum(row['call'] == call for row in reviews.values())
                   for label, call in (('PASS', 'PASS'), ('FAIL', 'FAIL'),
                                       ('REVIEW', 'REVIEW'), ('UNRESOLVED', None))}
    candidate = {'cells': candidate_refs, 'method_checks': method_summary,
                 'criterion_rollups': review_summary, 'structure_checks': structure_checks,
                 'program_settlement': {'owner_scores': owner_scores, 'call_counts': call_counts,
                                        'exceptions': failed_numeric}}
    source = {'evidence': evidence, 'limits': diagnostics['limits'],
              'calibration_diagnostics': diagnostics['calibration_diagnostics']}
    size = len(json.dumps({'candidate': candidate, 'source': source}, ensure_ascii=False,
                          sort_keys=True, separators=(',', ':')).encode())
    return candidate, source, size


def evidence_ceiling(owner, metric_truth, claims, row, derived, model):
    metric_rate = mean(metric_truth.values())
    relevant = {
        'profiles': {'coverage', 'efficiency', 'profit_quality', 'net_profit'},
        'cip': {'revenue', 'fixed_assets', 'cip', 'efficiency', 'cip_adjusted'},
        'goodwill': {'goodwill', 'net_assets', 'goodwill_ratio'},
        'debt_purpose': {'cash', 'debt', 'borrowing', 'capex', 'coverage'},
        'signed_profit': {'net_profit', 'operating_cashflow', 'profit_quality'},
        'missingness': set(),
    }
    selected = [item['correct'] for item in claims if item['name'] in relevant.get(owner, set())]
    claim_rate = mean(selected) if selected else 1.0
    if owner == 'decision':
        return metric_rate
    if owner == 'profiles':
        return min(metric_rate, claim_rate)
    return claim_rate


def invalid_candidate(reason, artifact_sha256=None):
    return {'reward': 0.0, 'rewards': {'strict': 0.0, 'lenient': 0},
            'status': 'INVALID_CANDIDATE', 'candidate_error': reason,
            'artifact_sha256': artifact_sha256, 'owner_scores': {}}


def grade(path):
    contract, source, brief = source_materials()
    artifact = Path(path)
    if not artifact.is_file():
        return invalid_candidate('Required workbook is missing')
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    ids = list(source['companies'])
    with tempfile.TemporaryDirectory(prefix='capex-score-') as scratch:
        view = submission.read(artifact, ids, scratch)
    if not view['readable']:
        return invalid_candidate(view.get('error', 'unreadable workbook'), digest)

    normalized = semantic_judge.normalize(view, brief, provider_field_catalog(source))
    model = normalized['result']['model']
    layout = normalized['result']['layout']
    if not layout:
        return invalid_candidate('No identifiable screen table', digest)
    try:
        records, duplicates, extra, company_cells = submission.records(view, layout, ids)
    except (KeyError, TypeError, ValueError) as exc:
        return invalid_candidate('Invalid screen layout: ' + str(exc), digest)
    global_cells = view['global_cells']
    structure_checks = {
        'readable_workbook': True,
        'identifiable_screen': True,
        'all_source_companies_once': set(records) == set(ids) and not duplicates,
        'no_extra_companies': not extra,
    }
    structure_score = mean(structure_checks.values())

    derived = {cid: source_financials.calculate(source['companies'][cid], model) for cid in ids}
    method_source = public_source(source)
    method_source['calibration_diagnostics'] = calibration_diagnostics(source, model, derived)
    method = semantic_judge.assess_method(model, global_cells, method_source, brief)
    targets = {cid: {'record': records[cid], 'cells': company_cells[cid]} for cid in records}
    batches = [ids[index:index + 10] for index in range(0, len(ids), 10)]
    reviews = {}

    def review_batch(batch):
        present = {cid: targets[cid] for cid in batch if cid in targets}
        if not present:
            return {}
        diagnostics = {cid: derived[cid] for cid in present}
        batch_source = public_source(source, present)
        batch_source['calculation_diagnostics'] = diagnostics
        batch_source['actual_model'] = model
        result = semantic_judge.review_rows(present, model, global_cells,
            method['result']['checks'], batch_source, diagnostics)
        return result['result']['items']

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(batches))) as pool:
        for result in pool.map(review_batch, batches):
            reviews.update(result)

    company_detail = {}
    owner_values = {key: [] for key in semantic_judge.CRITERIA}
    for cid in ids:
        if cid not in reviews:
            for owner in semantic_judge.CRITERIA:
                owner_values[owner].append(0.0)
            company_detail[cid] = {'present': False}
            continue
        row = reviews[cid]
        metric_checks = numeric_truth(row, derived[cid], targets[cid]['record'], view['cells'])
        claims = claim_truth(row, derived[cid], view['cells'])
        scores = {}
        for owner in semantic_judge.CRITERIA:
            scores[owner] = min(row['criteria'][owner]['score'],
                                evidence_ceiling(owner, metric_checks, claims, row, derived[cid], model))
            owner_values[owner].append(scores[owner])
        company_detail[cid] = {'present': True, 'call': row['call'],
            'expected_call_under_candidate_policy': expected_call(derived[cid], model),
            'metric_truth': metric_checks, 'numeric_claim_truth': claims,
            'semantic_criteria': row['criteria'], 'settled_scores': scores}

    owner_scores = {'structure': structure_score,
                    'core_method': method['result']['checks']['core_method']['score'],
                    'calibration': method['result']['checks']['calibration']['score']}
    owner_scores.update({key: mean(values) for key, values in owner_values.items()})
    weights = contract['weights']
    if set(weights) != set(owner_scores) or abs(sum(weights.values()) - 1.0) > 1e-9:
        raise RuntimeError('Scoring weights do not cover the ten owners exactly')
    strict = sum(owner_scores[owner] * weights[owner] for owner in weights)
    decided = [detail for detail in company_detail.values()
               if detail.get('call') in {'PASS', 'FAIL'}]
    calibration_rate = mean(detail['semantic_criteria']['decision']['met'] for detail in decided)

    completion_candidate, completion_source, completion_bytes = compact_completion(
        view, method, reviews, company_detail, structure_checks, owner_scores, method_source)
    completion = semantic_judge.completion(completion_candidate, completion_source,
                                           contract['completion_checks'])
    completion_checks = {key: value['passed'] for key, value in completion['result']['checks'].items()}
    every_metric_correct = (len(reviews) == len(ids) and
        all(all(detail.get('metric_truth', {}).values()) for detail in company_detail.values()))
    lenient_checks = {**structure_checks, 'all_displayed_metrics_source_correct': every_metric_correct,
                      'calibration_coherent': len(decided) > 0 and calibration_rate == 1.0,
                      **completion_checks}
    lenient = int(all(lenient_checks.values()))
    return {'reward': strict, 'rewards': {'strict': strict, 'lenient': lenient},
        'status': 'MEASURED', 'score_type': contract['version'],
        'reward_formulas': {'strict': 'sum(owner_score * owner_weight) across ten independent financial-review responsibilities',
                            'lenient': '1 iff source-universe, source-arithmetic, own-policy and three business-completion obligations pass'},
        'artifact_sha256': digest, 'normalization': normalized, 'method_assessment': method,
        'completion_assessment': completion, 'structure_checks': structure_checks,
        'completion_payload_bytes': completion_bytes,
        'lenient_checks': lenient_checks, 'owner_scores': owner_scores, 'weights': weights,
        'policy_consistency': {'decided_companies': len(decided),
                               'coherent_share': calibration_rate},
        'company_detail': company_detail}


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/workspace/shortlist.xlsx')
    print(json.dumps(grade(path), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

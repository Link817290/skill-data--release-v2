#!/usr/bin/env python3
"""Source-check numerical fields and settle a frozen evaluator-side semantic review."""
import argparse
import hashlib
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
from workbook_evidence import InvalidWorkbook, Workbook, source_facts
from review_contract import fingerprint
from numeric_audit import numeric_audit
from runtime_assets import source_path


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def resolve_artifact(root):
    if root.is_file():
        require(root.name == 'cppm_diagnosis.xlsx', 'Undeclared deliverable name')
        artifact, visible = root, root.parent
    else:
        direct, nested = root / 'cppm_diagnosis.xlsx', root / 'output/cppm_diagnosis.xlsx'
        candidate = direct if root.name == 'output' else nested
        artifact = candidate if candidate.exists() or candidate.is_symlink() else None
        visible = root
    if artifact is not None:
        require(not artifact.is_symlink(), 'Symlink deliverable')
        require(artifact.is_file(), 'Deliverable is not a regular file')
    return artifact, visible


def settle(root, review_path, params_path):
    params = load(params_path)
    criteria = load(HERE / 'criteria.json')['items']
    original_weights = params.get('leaf_aggregation_weights') or params.get('item_weights')
    weights = {k: Decimal(v) for k, v in original_weights.items()}
    require(len(weights) == 26 and sum(weights.values()) == 1, 'Invalid positive weight budget')
    require(all(w > 0 for w in weights.values()), 'Nonpositive required weight')
    require({c['item_id'] for c in criteria} == set(weights), 'Unscored declared criterion')
    groups = params.get('positive_groups')
    if groups:
        active = {k: Decimal(str(v)) for k, v in params['positive_weights'].items()}
        require(set(groups) == set(active) and sum(active.values()) == 1, 'Invalid active group weights')
        leaves = [item for group in groups.values() for item in group]
        require(len(leaves) == len(set(leaves)) == len(weights) and set(leaves) == set(weights), 'Groups must cover every check exactly once')
        effective = {}
        for group, children in groups.items():
            denominator = sum(weights[k] for k in children)
            remaining = active[group]
            for index, key in enumerate(children):
                value = remaining if index == len(children) - 1 else (
                    active[group] * weights[key] / denominator).quantize(Decimal('1e-18'))
                effective[key] = value
                remaining -= value
        weights = effective
        require(sum(weights.values()) == 1 and all(w > 0 for w in weights.values()), 'Invalid effective leaf weights')
    coefficient = Decimal(params['retention_coefficient'])
    require(coefficient == Decimal('0.7'), 'Damage coefficient changed')
    artifact, visible = resolve_artifact(root)
    if artifact is None:
        return {'score_source': 'absent_deliverable', 'positive_earned': '0', 'retention': '1',
                'required_items': [], 'damage_instances': [], 'final_score': '0',
                'rewards': {'strict': 0.0, 'lenient': 0.0}}
    try:
        workbook = Workbook(artifact)
    except InvalidWorkbook as error:
        return {'score_source': 'invalid_deliverable', 'artifact_sha256': sha(artifact),
                'parse_error': str(error), 'positive_earned': '0', 'retention': '1',
                'required_items': [], 'damage_instances': [], 'final_score': '0',
                'rewards': {'strict': 0.0, 'lenient': 0.0}}
    if review_path is None:
        from semantic_judge import review_for_artifact
        review_path = review_for_artifact(artifact)
    require(not review_path.resolve().is_relative_to(visible.resolve()), 'Solver-side review not accepted')
    source = source_path()
    facts = source_facts(Workbook(source))
    review = load(review_path)
    require(review.get('review_origin') == 'llm_content_judge_v1', 'Current scores require the replayable LLM content review')
    require(review['schema_version'] == 'ppm-source-verified-content-review-v1', 'Stale review schema')
    require(review['artifact_sha256'] == sha(artifact), 'Artifact binding mismatch')
    require(review['source_sha256'] == sha(source), 'Source binding mismatch')
    require(review['judge_fingerprint'] == fingerprint(criteria, params, sha(source)), 'Stale scoring semantics')
    require(review['scorer_sha256'] == sha(HERE / 'validator.py'), 'Scorer binding mismatch')
    decisions = review['required_items']
    require(len(decisions) == len(weights) and {d['item_id'] for d in decisions} == set(weights), 'Incomplete or duplicated item decisions')
    bindings = json.loads(json.dumps(review['table_bindings']))

    def present(location):
        sheet, separator, address = location.rpartition('!')
        sheet = sheet.strip("'").replace("''", "'")
        require(separator and sheet in workbook.sheets, 'Binding names an unknown worksheet')
        require(re.fullmatch(r'\$?[A-Za-z]+\$?[1-9]\d*', address), 'Invalid bound cell address')
        try:
            cell = workbook.cell(location)[2]
        except KeyError:
            return False
        return cell['value'] is not None or bool(cell['formula'])

    # XLSX readers omit completely empty cells. An absent required field is incomplete,
    # while a malformed evaluator locator remains an evaluation error.
    for group, fields in (('months', ('label', 'sales', 'complaints', 'overall_ppm')),
                          ('products', ('label', 'sales', 'complaints', 'ppm', 'share', 'relative'))):
        for row in bindings[group]:
            for field in fields:
                if row.get(field) and not present(row[field]):
                    row.pop(field)
            if group == 'months':
                row['product_ppm'] = {p: loc for p, loc in row.get('product_ppm', {}).items() if present(loc)}
    audited, problems = numeric_audit(workbook, bindings, facts)
    rows = {row['product']: row for row in bindings['products']}
    numeric = {k: audited[k] for k in ('P-MONTH-TABLE', 'P-PRODUCT-TABLE')}
    # Each product quantity is independently scored; table items require every field.
    for prefix, field, old_group in (('P-SHARE-', 'share', 'P-SHARES'), ('P-RELATIVE-', 'relative', 'P-RELATIVES')):
        for product in 'ABCD':
            key, location = prefix + product, rows.get(product, {}).get(field)
            missing = location is None or not rows.get(product, {}).get('label')
            if location:
                cell = workbook.cell(location)[2]
                missing = missing or (cell['value'] is None and not cell['formula'])
            wrong = any(p['location'] == location and p['item_id'] == old_group for p in problems)
            state = 'missing_or_incomplete' if missing else 'incorrect' if wrong else 'correct'
            numeric[key] = {'item_id': key, 'status': state, 'evidence': [location] if location else [],
                            'zero_reason': '' if state == 'correct' else 'Source-bound required quantity is ' + state}
    errors = review['confirmed_errors']
    require(len({e['key'] for e in errors}) == len(errors), 'Duplicate independent error')
    for error in errors:
        require(error['scope_class'] in {'required', 'extra'}, 'Invalid error scope')
        require(all(error.get(k) for k in ('locations', 'quote', 'reason', 'anchor')), 'Error lacks substantiated evidence')
        require(any(workbook.quote_exists(loc, error['quote']) for loc in error['locations']), 'Error quote absent from actual workbook')
        affected = error['affected_required_items']
        require(set(affected) <= set(weights), 'Error affects unknown criterion')
        require((error['scope_class'] == 'required') == bool(affected), 'Damage scope does not match affected criteria')
        if 'coefficient' in error:
            require(Decimal(error['coefficient']) == coefficient, 'Per-error coefficient changed')
        error['coefficient'] = str(coefficient)
    for problem in problems:
        mapped_key = problem['item_id']
        if mapped_key in {'P-SHARES', 'P-RELATIVES'}:
            field = 'share' if mapped_key == 'P-SHARES' else 'relative'
            prefix = 'P-SHARE-' if field == 'share' else 'P-RELATIVE-'
            product = next(p for p, r in rows.items() if r.get(field) == problem['location'])
            mapped_key = prefix + product
        require(any(problem['location'] in e['locations'] and mapped_key in e['affected_required_items'] for e in errors), 'Numerical error lacks a reviewed independent damage')
    items, positive = [], Decimal(0)
    for decision in decisions:
        key = decision['item_id']
        item = dict(decision)
        if key in numeric:
            item.update(numeric[key])
        affected = any(key in e['affected_required_items'] for e in errors)
        if affected:
            item.update(status='incorrect', zero_reason='Confirmed adopted error conflicts with this required item')
        status = item['status']
        require(status in {'correct', 'incorrect', 'missing_or_incomplete'}, 'Invalid completeness status')
        if status == 'correct':
            require(item['evidence'] and item.get('review_proof'), 'Credited semantic item lacks audit evidence')
            for location in item['evidence']:
                if location.startswith('part:'):
                    require(location in workbook.parts, 'Nonexistent evidence part')
                else:
                    workbook.cell(location)
        else:
            require(bool(item['zero_reason']), 'Zero-credit item lacks a reason')
        if status == 'incorrect':
            require(affected, 'Incorrect required item lacks a confirmed damage')
        earned = weights[key] if status == 'correct' else Decimal(0)
        item.update(weight=str(weights[key]), earned=str(earned))
        positive += earned
        items.append(item)
    strict = positive * coefficient ** len(errors)
    group_ledger = []
    if groups:
        item_map = {item['item_id']: item for item in items}
        for group, children in groups.items():
            earned = sum(Decimal(item_map[key]['earned']) for key in children)
            group_ledger.append({'id': group, 'weight': str(active[group]),
                                 'completion': str(earned / active[group]), 'earned': str(earned),
                                 'children': children})
        require(sum(Decimal(g['earned']) for g in group_ledger) == positive, 'Group ledger and positive credit disagree')
    domains = params['lenient_domains']
    profiles = params['lenient_usable_profiles']
    domain_groups = [key for members in domains.values() for key in members]
    require(groups and domains and len(domain_groups) == len(set(domain_groups))
            and set(domain_groups) == set(groups), 'Invalid lenient domain partition')
    require(profiles and all(profile and set(profile) <= set(domains) for profile in profiles.values()),
            'Invalid lenient usable-profile contract')
    group_map = {group['id']: group for group in group_ledger}
    lenient_domains = {domain: {key: Decimal(group_map[key]['completion']) == 1 for key in members}
                       for domain, members in domains.items()}
    domain_gates = {domain: all(members.values()) for domain, members in lenient_domains.items()}
    profile_gates = {profile: all(domain_gates[domain] for domain in required_domains)
                     for profile, required_domains in profiles.items()}
    lenient = float(any(profile_gates.values()) and not errors)
    return {'score_source': 'source_verified_content_review', 'review_origin': review['review_origin'],
            'artifact_sha256': sha(artifact), 'source_sha256': sha(source), 'judge_fingerprint': review['judge_fingerprint'],
            'scorer_sha256': review['scorer_sha256'],
            'judge': {key: review.get(key) for key in ('judge_cache_key', 'judge_response_sha256',
                      'judge_response_origin', 'judge_model', 'judge_provider')},
            'positive_earned': str(positive), 'retention_coefficient': str(coefficient),
            'retention': str(coefficient ** len(errors)), 'final_score': str(strict),
            'required_items': items, 'damage_instances': errors,
            'positive_groups': group_ledger,
            'lenient_basis': {'domain_gates': domain_gates, 'domain_items': lenient_domains,
                              'usable_profiles': profile_gates,
                              'no_confirmed_errors': not errors},
            'numeric_audit': {'items': numeric, 'mismatches': problems},
            'rewards': {'strict': float(strict), 'lenient': lenient}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifact_root', type=Path)
    parser.add_argument('--review', type=Path)
    parser.add_argument('--params', type=Path, default=HERE / 'scoring_params.json')
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    try:
        result = settle(args.artifact_root, args.review, args.params)
        text = json.dumps(result, ensure_ascii=False) + '\n'
        if args.json:
            args.json.write_text(text, encoding='utf-8')
        print(text, end='')
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as error:
        print('Scoring error: ' + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

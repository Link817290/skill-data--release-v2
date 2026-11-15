"""Item-level partial credit; each reference leaf has exactly one owner."""
import math


def credit(passed, total):
    if not isinstance(passed, int) or not isinstance(total, int) or not 0 <= passed <= total or total <= 0:
        raise ValueError('Invalid assertion counts')
    if passed == total:
        return 1.0
    if passed * 5 >= total * 4:
        return 0.5
    if passed * 2 >= total:
        return 0.3
    if passed * 10 >= total:
        return 0.1
    return 0.0


def aggregate(raw, facts, plan, params):
    owners = {
        'identity': [(key, i) for key in ('P01', 'P02', 'P03') for i in range(len(raw[key]))],
        'station_controls': [(key, i) for key in ('P04', 'P05', 'P06') for i in range(len(raw[key]))],
        'P07': [('P07', i) for i in range(len(raw['P07']))],
        'P08': [('P08', i) for i in range(len(raw['P08']))],
        'P10': [('P10', i) for i in range(len(raw['P10']))],
    }
    for i, item in enumerate(plan['grounding_sets']):
        owners['location_' + str(item['pole'])] = [('P08_location', i)]
    coverage = [leaf for leaves in owners.values() for leaf in leaves]
    expected = {(key, i) for key, atoms in raw.items() for i in range(len(atoms))}
    if len(coverage) != len(set(coverage)) or set(coverage) != expected:
        raise ValueError('Every source assertion must have exactly one owner')
    if set(owners) != set(params['positive_weights']) or set(owners) != set(params['assertion_counts']):
        raise ValueError('Scored-owner inventory mismatch')
    atoms, completion = {}, {}
    for owner, leaves in owners.items():
        atoms[owner] = [dict(raw[key][i], source_item=key, source_index=i) for key, i in leaves]
        if len(leaves) != params['assertion_counts'][owner]:
            raise ValueError('Owner assertion inventory mismatch: ' + owner)
        completion[owner] = credit(sum(a['passed'] for a in atoms[owner]), len(leaves))
    return atoms, completion


def apply_guards(completion, guards):
    result = dict(completion)
    for owner, checks in guards.items():
        if owner not in result or not checks or not all(isinstance(v, bool) for v in checks.values()):
            raise ValueError('Invalid item guard')
        # A failed mandatory prerequisite invalidates only its own item.
        # Other items retain their evidence-based partial credit.
        if not all(checks.values()):
            result[owner] = 0.0
    return result


def safety_coverage_gate(raw_procedures):
    """A permit with none of its six core procedures verified earns no reward."""
    if len(raw_procedures) != 6 or not all(type(a['passed']) is bool for a in raw_procedures):
        raise ValueError('Expected six binary core procedure checks')
    count = sum(a['passed'] for a in raw_procedures)
    return {'policy': 'minimum-verified-procedure-v1', 'passed': count > 0,
            'verified_count': count, 'required_check_count': 6,
            'failed_checks': [a['assertion'] for a in raw_procedures if not a['passed']],
            'failure_reason': None if count else 'None of the six core procedures is verified'}


def settle(completion, params):
    if params['settlement'] != {'family': 'item-partial-credit-v1', 'aggregation': 'weighted-sum'}:
        raise ValueError('Unsupported settlement policy')
    weights = params['positive_weights']
    if set(weights) != set(completion):
        raise ValueError('Weight/completion inventory mismatch')
    if not all(math.isfinite(w) and 0 < w <= 1 for w in weights.values()):
        raise ValueError('Weights must be finite and positive')
    if not math.isclose(math.fsum(weights.values()), 1, abs_tol=1e-12, rel_tol=0):
        raise ValueError('Weights must sum to one')
    if not all(v in (0, .1, .3, .5, 1) for v in completion.values()):
        raise ValueError('Unsupported item credit level')
    return min(1.0, math.fsum(weights[k] * v for k, v in completion.items()))

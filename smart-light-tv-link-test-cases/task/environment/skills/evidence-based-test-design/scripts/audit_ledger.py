"""Check solver-authored source/measurement bindings; no product limits."""
import argparse
import ast
import json
import math
import operator
from pathlib import Path

TIME_UNITS = {'s': 1.0, 'ms': .001, 'us': .000001}
OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
BINDINGS = ('quantity', 'endpoint', 'start', 'stop', 'statistic')
AUTHORITIES = {'requirement', 'procedure', 'exit', 'severity', 'context', 'authored'}


def number_expression(expression, values):
    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.Name) and node.id in values:
            return values[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            return OPS[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            return (-1 if isinstance(node.op, ast.USub) else 1) * visit(node.operand)
        raise ValueError('Only numeric arithmetic and declared variables are supported')
    return visit(ast.parse(expression, mode='eval'))


def method_valid(method, unit):
    kind = method.get('kind')
    if kind in {'elapsed', 'video'} and unit not in TIME_UNITS:
        return False
    if kind in {'reduction', 'growth'} and unit != '%':
        return False
    for seed in (1, 3, 7, 11):
        values = {'t0': seed * .17, 't1': seed * .17 + .03 * (seed + 1),
                  'f0': seed * 9, 'f1': seed * 9 + seed + 2, 'fps': seed * 12 + 25,
                  'baseline': seed * 21 + 12, 'observed': seed * 8 + 2,
                  'initial': seed * 19 + 10, 'final': seed * 23 + 20}
        expected = {
            'elapsed': lambda: (values['t1'] - values['t0']) / TIME_UNITS[unit],
            'video': lambda: (values['f1'] - values['f0']) / values['fps'] / TIME_UNITS[unit],
            'reduction': lambda: 100 * (values['baseline'] - values['observed']) / values['baseline'],
            'growth': lambda: 100 * (values['final'] - values['initial']) / values['initial'],
        }
        if kind not in expected:
            return False
        try:
            value = number_expression(method.get('expression', ''), values)
            if not math.isclose(value, expected[kind](), rel_tol=1e-9, abs_tol=1e-9):
                return False
        except (SyntaxError, ValueError, TypeError, ZeroDivisionError, OverflowError):
            return False
    return True


def criterion_equal(left, right):
    if left is None or right is None:
        return left is right
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    if left.get('operator') != right.get('operator'):
        return False
    lu, ru = left.get('unit'), right.get('unit')
    if lu != ru and not (lu in TIME_UNITS and ru in TIME_UNITS):
        return False
    lv, rv = left.get('value'), right.get('value')
    if lv is None or rv is None:
        return False
    lv = lv if isinstance(lv, list) else [lv]
    rv = rv if isinstance(rv, list) else [rv]
    if len(lv) != len(rv):
        return False
    try:
        return all(math.isclose(float(a) * TIME_UNITS.get(lu, 1), float(b) * TIME_UNITS.get(ru, 1),
                                rel_tol=1e-9, abs_tol=1e-9) for a, b in zip(lv, rv))
    except (ValueError, TypeError):
        return False


def normalize(text):
    return ' '.join(str(text).split()).casefold()


def audit(ledger, sources=None):
    findings, notices, facts, used = [], [], {}, set()
    def flag(kind, identifier, **details):
        findings.append({'kind': kind, 'id': identifier, **details})

    source_map = {(r['source'], r['location']): r['text'] for r in (sources or {}).get('records', [])}
    for fact in ledger.get('facts', []):
        identifier = fact.get('id')
        if not identifier or identifier in facts:
            flag('missing_or_duplicate_fact_id', identifier)
            continue
        facts[identifier] = fact
        for field in ('source', 'location', 'quote', 'authority') + BINDINGS:
            if not str(fact.get(field, '')).strip():
                flag('missing_fact_field', identifier, field=field)
        if fact.get('authority') not in AUTHORITIES:
            flag('unknown_authority', identifier)
        if sources is not None:
            text = source_map.get((fact.get('source'), fact.get('location')))
            quote = normalize(fact.get('quote', ''))
            if text is None or not quote or quote not in normalize(text):
                flag('quote_not_found_at_source_location', identifier)
    identifiers = set()
    for check in ledger.get('checks', []):
        identifier = check.get('id')
        if not identifier or identifier in identifiers:
            flag('missing_or_duplicate_check_id', identifier)
        identifiers.add(identifier)
        if not check.get('case_id'):
            flag('missing_case_link', identifier)
        fact = facts.get(check.get('fact_id'))
        if fact is None:
            flag('unknown_fact', identifier)
            continue
        used.add(fact['id'])
        for field in BINDINGS:
            if not str(check.get(field, '')).strip() or normalize(check.get(field)) != normalize(fact.get(field)):
                flag('binding_disagrees_with_fact', identifier, field=field,
                     source_value=fact.get(field), check_value=check.get(field))
        for key, value in fact.get('configuration', {}).items():
            if check.get('configuration', {}).get(key) != value:
                flag('configuration_disagrees_with_fact', identifier, field=key)
        if check.get('adopted', True):
            if fact.get('authority') not in {'requirement', 'exit'}:
                flag('non_acceptance_authority_adopted', identifier, authority=fact.get('authority'))
            if not fact.get('resolved', True) and not check.get('conditional', False):
                flag('unresolved_fact_used_unconditionally', identifier)
            if not criterion_equal(fact.get('criterion'), check.get('criterion')):
                flag('criterion_disagrees_with_fact', identifier)
        if check.get('criterion') is not None:
            method = check.get('method') or {}
            if method.get('kind') == 'other' and str(method.get('description', '')).strip():
                notices.append({'kind': 'manual_method_review', 'id': identifier, 'description': method['description']})
            elif not method_valid(method, check['criterion'].get('unit')):
                flag('missing_or_incompatible_measurement', identifier)
    for identifier, fact in facts.items():
        if fact.get('in_scope', True) and identifier not in used:
            flag('in_scope_fact_without_case', identifier)
    if not facts:
        flag('no_facts', None)
    return {'fact_count': len(facts), 'check_count': len(identifiers), 'findings': findings,
            'manual_review': notices,
            'scope': 'Internal bindings and quotes only; independently review source interpretation and saved workbook.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('ledger', type=Path)
    parser.add_argument('--sources', type=Path)
    args = parser.parse_args()
    result = audit(json.loads(args.ledger.read_text(encoding='utf-8')),
                   json.loads(args.sources.read_text(encoding='utf-8')) if args.sources else None)
    print(json.dumps(result, indent=2, ensure_ascii=True))
    raise SystemExit(2 if result['findings'] else 0)


if __name__ == '__main__':
    main()

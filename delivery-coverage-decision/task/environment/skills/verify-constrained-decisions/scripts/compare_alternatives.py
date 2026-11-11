"""Compare verified numeric alternative metrics; does not certify allocations."""
import argparse
import csv
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path


def number(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError('Expected a finite decimal value') from None
    if not result.is_finite():
        raise ValueError('Expected a finite decimal value')
    return result


def compare(rows, id_column, objectives, cost_column=None, budget=None):
    if not objectives or any(direction not in ('min', 'max') or not field for direction, field in objectives):
        raise ValueError('Supply ordered min/max objectives')
    if len({field for _, field in objectives}) != len(objectives):
        raise ValueError('Duplicate objective column')
    if (cost_column is None) != (budget is None):
        raise ValueError('Budget and cost column must be supplied together')
    cap = number(budget) if budget is not None else None
    if cap is not None and cap < 0:
        raise ValueError('Budget must be nonnegative')
    seen, eligible, excluded = set(), [], []
    for row in rows:
        identifier = row[id_column]
        if not isinstance(identifier, str) or not identifier.strip() or identifier in seen:
            raise ValueError('Identifiers must be nonempty unique strings')
        seen.add(identifier)
        values = [number(row[field]) for _, field in objectives]
        key = tuple(-value if direction == 'max' else value for value, (direction, _) in zip(values, objectives))
        if cap is not None:
            cost = number(row[cost_column])
            if cost < 0:
                raise ValueError('Cost must be nonnegative')
            if cost > cap:
                excluded.append(identifier)
                continue
        eligible.append((identifier, key))
    ordered = sorted(eligible, key=lambda item: (item[1], item[0]))
    groups = []
    previous = None
    for identifier, key in ordered:
        if not groups or key != previous:
            groups.append([])
        groups[-1].append(identifier)
        previous = key
    frontier = sorted(identifier for identifier, key in eligible if not any(
        all(a <= b for a, b in zip(other, key)) and any(a < b for a, b in zip(other, key))
        for _, other in eligible))
    return dict(ranked_tie_groups=groups, winners=groups[0] if groups else [],
                pareto_frontier=frontier, excluded_over_budget=sorted(excluded),
                comparison_scope='Verified input metrics only; no allocation or scenario certification')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--id', dest='id_column', required=True)
    parser.add_argument('--objective', action='append', required=True, metavar='min:COLUMN| max:COLUMN')
    parser.add_argument('--cost-column')
    parser.add_argument('--budget')
    args = parser.parse_args()
    try:
        objectives = []
        for specification in args.objective:
            direction, field = specification.split(':', 1)
            objectives.append((direction, field))
        with args.input.open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        result = compare(rows, args.id_column, objectives, args.cost_column, args.budget)
    except (ValueError, KeyError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))

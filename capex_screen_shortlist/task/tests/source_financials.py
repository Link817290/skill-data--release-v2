"""Reconstruct financial facts from the issued snapshots, without a reference list."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

YEARS = (2018, 2019, 2020, 2021)
WINDOW = (2019, 2020, 2021)
DEBT_FIELDS = ('SHORT_LOAN', 'NONCURRENT_LIAB_1YEAR', 'LONG_LOAN', 'BOND_PAYABLE', 'SHORT_BOND_PAYABLE', 'SHORT_FIN_PAYABLE')
BALANCE_FIELDS = ('TOTAL_ASSETS', 'TOTAL_LIAB_EQUITY', 'TOTAL_LIABILITIES',
                  'MONETARYFUNDS', 'FIXED_ASSET', 'CIP', 'GOODWILL', 'TOTAL_EQUITY',
                  'LEASE_LIAB', 'INVENTORY', *DEBT_FIELDS)
INCOME_FIELDS = ('TOTAL_OPERATE_INCOME', 'OPERATE_INCOME', 'NETPROFIT', 'PARENT_NETPROFIT', 'OPERATE_COST')
CASHFLOW_FIELDS = ('NETCASH_OPERATE', 'CONSTRUCT_LONG_ASSET', 'RECEIVE_LOAN_CASH', 'ISSUE_BOND')
LINE_ITEMS = set(DEBT_FIELDS) | {'CIP', 'GOODWILL', 'LEASE_LIAB', 'RECEIVE_LOAN_CASH', 'ISSUE_BOND'}


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def fact(row, field):
    if field not in row:
        return {'state': 'ABSENT', 'raw': None, 'value': None}
    value = row[field]
    if value is None:
        aggregates = {'TOTAL_ASSETS', 'TOTAL_LIAB_EQUITY', 'TOTAL_LIABILITIES', 'MONETARYFUNDS',
                      'FIXED_ASSET', 'TOTAL_EQUITY', 'TOTAL_OPERATE_INCOME',
                      'OPERATE_INCOME', 'NETPROFIT', 'PARENT_NETPROFIT', 'NETCASH_OPERATE'}
        return {'state': 'STANDARDIZED_NULL', 'raw': None, 'value': None if field in aggregates else 0.0}
    if not number(value):
        raise ValueError('Non-numeric issued financial field: ' + field)
    return {'state': 'DISCLOSED', 'raw': value, 'value': float(value)}


def load_sources(folder, expected_hashes=None):
    folder = Path(folder)
    if expected_hashes:
        for name, expected in expected_hashes.items():
            if hashlib.sha256((folder / name).read_bytes()).hexdigest() != expected:
                raise ValueError('Issued source digest mismatch: ' + name)
    with (folder / 'candidate_universe.csv').open(encoding='utf-8-sig', newline='') as stream:
        universe = list(csv.DictReader(stream))
    ids = [row['company_id'] for row in universe]
    if len(ids) != 60 or len(set(ids)) != 60:
        raise ValueError('Issued universe must contain 60 unique companies')
    companies = {}
    fields = {'balance': BALANCE_FIELDS, 'income': INCOME_FIELDS, 'cashflow': CASHFLOW_FIELDS}
    for cid in ids:
        filename = 'structured-data/provider-snapshots/' + cid + '.json'
        document = json.loads((folder / filename).read_text(encoding='utf-8'))
        if document.get('company_id') != cid:
            raise ValueError('Issued snapshot identity mismatch: ' + cid)
        statements, raw_rows = {}, {}
        for statement, wanted in fields.items():
            requests = [item for item in document.get('requests', []) if item.get('statement') == statement]
            if len(requests) != 1:
                raise ValueError('Issued statement request missing or duplicated: ' + cid + '/' + statement)
            selected, original = {}, {}
            for row in requests[0]['payload']['result']['data']:
                year = str(row.get('REPORT_DATE', ''))[:4]
                if year not in {str(value) for value in YEARS}:
                    continue
                if (row.get('SECUCODE') != cid or row.get('REPORT_TYPE') != '年报'
                        or str(row.get('NOTICE_DATE', ''))[:10] > '2022-05-20'):
                    raise ValueError('Issued entity/report/cutoff mismatch: ' + cid)
                if year in selected:
                    raise ValueError('Duplicate issued annual observation')
                selected[year] = {'report_date': row['REPORT_DATE'], 'notice_date': row['NOTICE_DATE'],
                                  'currency': row.get('CURRENCY'), 'fields': {key: fact(row, key) for key in wanted}}
                original[year] = row
            if set(selected) != {str(value) for value in YEARS}:
                raise ValueError('Incomplete issued annual window: ' + cid + '/' + statement)
            statements[statement] = selected
            raw_rows[statement] = original
        companies[cid] = {'company_id': cid, 'source_path': filename,
                          'source_sha256': hashlib.sha256((folder / filename).read_bytes()).hexdigest(),
                          'official_audit_source_ids': document.get('official_audit_source_ids', []),
                          'official_filings_issued': False, 'statements': statements, '_raw': raw_rows}
    return {'universe': universe, 'companies': companies,
            'limits': {'cutoff': '2022-05-20', 'window': list(WINDOW), 'base_year': 2018,
                       'official_filings_issued': False,
                       'debt_purpose': 'No issued filing binds borrowing to a named project. Co-movement is quantitative proxy evidence only.',
                       'goodwill': 'Year-end net balances cannot exclude a same-year purchase offset by impairment.'}}


def value(company, statement, year, field):
    fields = company['statements'][statement][str(year)]['fields']
    if field not in fields:
        try:
            fields[field] = fact(company['_raw'][statement][str(year)], field)
        except ValueError:
            fields[field] = {'state': 'NON_FINANCIAL', 'raw': company['_raw'][statement][str(year)].get(field), 'value': None}
    return fields[field]['value']


def total_assets(company, year):
    """Use only auditable same-statement accounting identities.

    A provider-null TOTAL_ASSETS is recoverable from the disclosed total
    liabilities-and-equity line. If that aggregate is unavailable, disclosed
    total liabilities plus disclosed total equity is the same balance-sheet
    identity. No cross-period interpolation or model estimate is allowed.
    """
    direct = value(company, 'balance', year, 'TOTAL_ASSETS')
    if direct is not None:
        return direct, 'TOTAL_ASSETS'
    liabilities_equity = value(company, 'balance', year, 'TOTAL_LIAB_EQUITY')
    if liabilities_equity is not None:
        return liabilities_equity, 'TOTAL_LIAB_EQUITY'
    liabilities = value(company, 'balance', year, 'TOTAL_LIABILITIES')
    equity = value(company, 'balance', year, 'TOTAL_EQUITY')
    if liabilities is not None and equity is not None:
        return liabilities + equity, 'TOTAL_LIABILITIES+TOTAL_EQUITY'
    return None, None


def ratio(numerator, denominator, *, unbounded=False):
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        return 'INF' if unbounded and numerator >= 0 else None
    if unbounded and denominator < 0:
        return None
    return numerator / denominator


def mean(values):
    if any(item is None for item in values):
        return None
    if 'INF' in values:
        return 'INF'
    return sum(values) / len(values)


def greater(value_, threshold, operator='>'):
    if threshold is None:
        return False
    if value_ == 'INF':
        return True
    if not number(value_):
        return False
    return value_ >= threshold if operator == '>=' else value_ > threshold


def calculate(company, model):
    debt_fields = model.get('debt_fields') or []
    borrowing_fields = model.get('borrowing_fields') or []
    cash_field = model.get('cash_field')
    profit_field = model.get('profit_field')
    revenue_field = model.get('revenue_field')
    annual, missing = {}, []
    for year in YEARS:
        vals = {key: value(company, 'balance', year, key) for key in BALANCE_FIELDS}
        for key in INCOME_FIELDS:
            vals[key] = value(company, 'income', year, key)
        for key in CASHFLOW_FIELDS:
            vals[key] = value(company, 'cashflow', year, key)
        for key in debt_fields:
            vals[key] = value(company, 'balance', year, key)
        for key in borrowing_fields:
            vals[key] = value(company, 'cashflow', year, key)
        if cash_field:
            vals[cash_field] = value(company, 'balance', year, cash_field)
        if profit_field:
            vals[profit_field] = value(company, 'income', year, profit_field)
        if revenue_field:
            vals[revenue_field] = value(company, 'income', year, revenue_field)
        debt_values = [vals.get(key) for key in debt_fields]
        debt = sum(debt_values) if debt_fields and all(item is not None for item in debt_values) else None
        fixed = vals['FIXED_ASSET']
        fixed = fixed if fixed is not None and fixed > 0 else None
        adjusted = fixed + vals['CIP'] if fixed is not None and vals['CIP'] is not None else None
        assets, assets_source = total_assets(company, year)
        annual[str(year)] = {
            'assets': assets, 'assets_source': assets_source,
            'cash': vals.get(cash_field), 'debt': debt,
            'debt_components': {key: vals.get(key) for key in debt_fields},
            'revenue': vals.get(revenue_field), 'fixed_assets': fixed, 'cip': vals['CIP'],
            'net_profit': vals.get(profit_field), 'operating_cashflow': vals['NETCASH_OPERATE'],
            'capex': vals['CONSTRUCT_LONG_ASSET'],
            'borrowing': (sum(vals.get(key) for key in borrowing_fields)
                          if borrowing_fields and all(vals.get(key) is not None for key in borrowing_fields) else None),
            'goodwill': vals['GOODWILL'], 'net_assets': vals['TOTAL_EQUITY'],
            'coverage': ratio(vals.get(cash_field), debt, unbounded=True),
            'efficiency': ratio(vals.get(revenue_field), fixed),
            'cip_adjusted': ratio(vals.get(revenue_field), adjusted),
            'profit_quality': ratio(vals['NETCASH_OPERATE'], vals.get(profit_field)),
            'goodwill_ratio': ratio(vals['GOODWILL'], vals['TOTAL_EQUITY']),
        }
    for year in WINDOW:
        current, previous = annual[str(year)], annual[str(year - 1)]
        current['growth'] = ratio(None if current['assets'] is None or previous['assets'] is None else current['assets'] - previous['assets'],
                                  previous['assets'] if previous['assets'] is not None and previous['assets'] > 0 else None)
        for field in ['growth', 'coverage', 'efficiency', 'profit_quality', 'capex']:
            if current[field] is None:
                missing.append({'year': year, 'quantity': field})
    metrics = {'growth_' + str(year): annual[str(year)]['growth'] for year in WINDOW}
    metrics.update({key + '_mean': mean([annual[str(year)][key] for year in WINDOW])
                    for key in ['coverage', 'efficiency', 'profit_quality']})
    thresholds = model.get('thresholds') or {}
    operators = model.get('operators') or {}
    growth_values = [annual[str(year)]['growth'] for year in WINDOW]
    growth_pass = (None if any(value_ is None for value_ in growth_values) else
                   all(greater(value_, thresholds.get('expansion'), operators.get('expansion', '>'))
                       for value_ in growth_values))
    capex_values = [annual[str(year)]['capex'] for year in WINDOW]
    capex_pass = (None if any(value_ is None for value_ in capex_values) else
                  all(number(value_) and value_ > 0 for value_ in capex_values))
    profiles = {}
    for profile in ['narrative', 'strict']:
        efficiency_bar = thresholds.get('efficiency_' + profile)
        coverage_values = [annual[str(year)]['coverage'] for year in WINDOW]
        net_profit_values = [annual[str(year)]['net_profit'] for year in WINDOW]
        gates = {
            'expansion': growth_pass,
            'coverage': (None if metrics['coverage_mean'] is None else
                         greater(metrics['coverage_mean'], thresholds.get('coverage'), operators.get('coverage', '>'))) if profile == 'narrative' else
                        (None if any(value_ is None for value_ in coverage_values) else
                         all(greater(value_, thresholds.get('coverage'), operators.get('coverage', '>')) for value_ in coverage_values)),
            'efficiency': (None if metrics['efficiency_mean'] is None else
                           greater(metrics['efficiency_mean'], efficiency_bar, operators.get('efficiency', '>'))),
            'profit_quality': (False if profile == 'strict' and any(number(value_) and value_ <= 0 for value_ in net_profit_values) else
                               None if metrics['profit_quality_mean'] is None or
                               (profile == 'strict' and any(value_ is None for value_ in net_profit_values)) else
                               greater(metrics['profit_quality_mean'], thresholds.get('profit_quality'), operators.get('profit_quality', '>')) and
                               (profile == 'narrative' or all(number(value_) and value_ > 0 for value_ in net_profit_values))),
            'capex_positive': capex_pass,
        }
        thresholds_complete = all(thresholds.get(key) is not None for key in
                                  ['expansion', 'coverage', 'profit_quality']) and efficiency_bar is not None
        status = ('FAIL' if thresholds_complete and any(value_ is False for value_ in gates.values()) else
                  'PASS' if thresholds_complete and all(value_ is True for value_ in gates.values()) else 'REVIEW')
        profiles[profile] = {'status': status, 'gates': gates}
    increases = [year for year in WINDOW if annual[str(year)]['goodwill'] is not None
                 and annual[str(year - 1)]['goodwill'] is not None
                 and annual[str(year)]['goodwill'] > annual[str(year - 1)]['goodwill']]
    goodwill_complete = all(annual[str(year)]['goodwill'] is not None for year in YEARS)
    negative_years = [year for year in WINDOW if number(annual[str(year)]['net_profit']) and annual[str(year)]['net_profit'] < 0]
    return {'annual': annual, 'metrics': metrics, 'profiles': profiles, 'missing_binding_quantities': missing,
            'goodwill_increase_years': increases,
            'goodwill_classification': 'REVIEW' if not goodwill_complete else 'BALANCE_INCREASE_REVIEW' if increases else 'NO_WINDOW_INCREASE',
            'negative_profit_years': negative_years,
            'cip_flip_years': {profile: [year for year in WINDOW if annual[str(year)]['efficiency'] is not None
                and annual[str(year)]['cip_adjusted'] is not None and thresholds.get('efficiency_' + profile) is not None
                and greater(annual[str(year)]['efficiency'], thresholds['efficiency_' + profile], operators.get('efficiency', '>')) != greater(annual[str(year)]['cip_adjusted'], thresholds['efficiency_' + profile], operators.get('efficiency', '>'))]
                for profile in ['narrative', 'strict']},
            'strong_borrowing_purpose': 'REVIEW',
            'purpose_reason': 'No issued filing links a specific borrowing to a named project; cash/debt/capex co-movement is not causal proof.'}


def numeric_path(derived, name, year):
    if name in derived['annual'][str(year)]:
        return derived['annual'][str(year)][name]
    raise KeyError(name)

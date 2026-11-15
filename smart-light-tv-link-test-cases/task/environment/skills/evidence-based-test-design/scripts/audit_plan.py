"""Structural audit of planned cases; no product truths or reference answers."""
import argparse
import json
import re
from pathlib import Path

import openpyxl


def role(value):
    text = re.sub(r'[^a-z0-9]+', ' ', str(value or '').lower()).strip()
    patterns = {
        'id': r'^(?:test case|case|test) (?:id|identifier)\b',
        'objective': r'^(?:(?:test case|case|test) )?(?:objective|name|scenario|title)\b',
        'preconditions': r'^(?:preconditions?|prerequisites?|setup)\b',
        'steps': r'^(?:(?:ordered|actionable) )*(?:test steps|steps|procedure|actions)\b',
        'expected': r'^(?:observable )?(?:expected|acceptance criteria)\b',
        'priority': r'^(?:priority|moscow)\b',
        'execution': r'^(?:(?:test|execution|exec) )?(?:result|status)\b',
        'remarks': r'^(?:remarks|notes|sources?|references|evidence source)\b',
    }
    return next((name for name, pattern in patterns.items() if re.search(pattern, text)), None)


def audit(path, sources=None):
    book = openpyxl.load_workbook(path, data_only=False)
    cases, findings, review_queue = [], [], []
    required = {'objective', 'preconditions', 'steps', 'expected'}
    for sheet in book:
        mapping, start = {}, None
        for i, row in enumerate(sheet.iter_rows(max_row=min(15, sheet.max_row)), 1):
            mapping = {}
            for index, cell in enumerate(row):
                if name := role(cell.value):
                    mapping.setdefault(name, []).append(index)
            if required <= mapping.keys():
                extra_roles = {'source_file': r'^source (?:file|document)$',
                               'source_location': r'^source (?:location|locator)$',
                               'source_quote': r'^(?:source |controlling )?quote$'}
                for index, cell in enumerate(row):
                    text = str(cell.value or '').strip().lower()
                    for name, pattern in extra_roles.items():
                        if re.fullmatch(pattern, text):
                            mapping[name] = [index]
                start = i
                break
        if start is None:
            continue
        for row in sheet.iter_rows(min_row=start + 1):
            values = {name: '\n'.join(str(row[i].value or '').strip() for i in columns)
                      for name, columns in mapping.items()}
            if not values.get('objective'):
                continue
            location = f'{sheet.title}!{row[0].row}'
            coordinates = {name: [row[i].coordinate for i in columns]
                           for name, columns in mapping.items()}
            cases.append({'location': location, 'cells': coordinates, **values})
            review_queue.append({'location': location, 'checks': [
                'fixture establishes the effective operating state',
                'controlled trigger produces a specified observable effect',
                'each verdict has its own applicable source and endpoint',
                'restoration leaves a known state'] + ([
                'quantities have instruments, events, units and statistics',
                'distinct quantities and endpoints have separate criteria']
                if re.search(r'\d|percent|interval|latency|frequency|reduction|growth',
                             values.get('expected', ''), re.I) else [])})
            for name in required | {'priority', 'execution', 'remarks'}:
                if name not in mapping or (name != 'execution' and not values.get(name)):
                    findings.append({'location': location, 'kind': 'missing_field', 'field': name})
            status = values.get('execution', '').lower().strip()
            if status and status not in {'not executed', 'unexecuted', 'not run', 'not tested', 'planned', 'pending'}:
                findings.append({'location': location, 'kind': 'check_execution_evidence', 'value': status})
            if len(re.findall(r'(?:^|\n)\s*\d+[.)]', values.get('steps', ''))) < 2:
                findings.append({'location': location, 'kind': 'check_ordered_actions'})
    ids = set()
    for case in cases:
        identifier = case.get('id', '').lower()
        if identifier and identifier in ids:
            findings.append({'location': case['location'], 'kind': 'duplicate_case_id', 'id': identifier})
        if identifier:
            ids.add(identifier)
    for case in cases:
        linked_text = '\n'.join(case.get(field, '') for field in ('preconditions', 'steps', 'expected'))
        references = set(re.findall(r'\b(?:[A-Za-z]{1,12}-)+\d{1,4}\b', linked_text))
        for reference in references:
            if reference.lower() not in ids:
                findings.append({'location': case['location'], 'kind': 'check_external_dependency', 'reference': reference})
    if not cases:
        findings.append({'kind': 'no_case_table_detected'})
    if sources is not None:
        catalog = {(r['source'], r['location']): r['text']
                   for r in sources.get('records', [])}
        normalize = lambda value: ' '.join(str(value).split()).casefold()
        for case in cases:
            if not any(case.get(k) for k in ('source_file', 'source_location', 'source_quote')):
                continue
            key = (case.get('source_file', ''), case.get('source_location', ''))
            quote = case.get('source_quote', '')
            if key not in catalog:
                findings.append({'location': case['location'], 'kind': 'source_location_not_found',
                                 'source': key[0], 'source_location': key[1]})
            elif not quote:
                findings.append({'location': case['location'], 'kind': 'missing_controlling_quote'})
            elif normalize(quote) not in normalize(catalog[key]):
                findings.append({'location': case['location'], 'kind': 'saved_quote_not_found_at_source'})
    book.close()
    return {'case_count': len(cases), 'cases': cases, 'findings': findings,
            'review_queue': review_queue,
            'scope': 'Saved-cell structural and optional quotation checks only. Product limits, source authority, coverage and endpoint correctness require independent review.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('workbook', type=Path)
    parser.add_argument('--sources', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    sources = json.loads(args.sources.read_text(encoding='utf-8')) if args.sources else None
    report = audit(args.workbook, sources)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
        print(json.dumps({'case_count': report['case_count'], 'findings': report['findings'],
                          'saved_review': str(args.output)}, ensure_ascii=True))
    else:
        print(json.dumps(report, indent=2, ensure_ascii=True))


if __name__ == '__main__':
    main()

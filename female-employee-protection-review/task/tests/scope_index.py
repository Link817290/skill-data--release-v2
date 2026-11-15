"""Index complete native Office evidence; an index match never decides a score."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

from native_carriers import NAMES, action_rows, employee_rows, read_office, role, visible_rows

LINK = re.compile(r'(?<![A-Za-z0-9])([A-Z]{1,3})[-\uff0d]?\s*(\d{1,3})(?!\d)')
SOURCE = re.compile(r'02[-\uff0d]0[1-8]')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(artifact):
    records = []
    identities = {}
    by_employee = defaultdict(list)
    by_reference = defaultdict(list)
    by_carrier = defaultdict(list)
    physical_rows = defaultdict(list)
    for path in sorted(Path(artifact).iterdir()):
        kind = role(path)
        if not path.is_file() or kind is None:
            continue
        identities[path.name] = digest(path)
        native_rows = visible_rows(read_office(path))
        physical_rows[kind].extend(native_rows)
        for row in native_rows:
            text = row['text']
            ident = len(records)
            employees = [employee for employee, name in NAMES.items() if employee in text or name in text]
            links = sorted({prefix + '-' + str(int(number)).zfill(2) for prefix, number in LINK.findall(text)})
            record = {'evidence_id': ident, 'carrier': kind, 'address': row['address'],
                'text': text, 'explicit_employees': employees, 'reference_tokens': links,
                'source_file_tokens': sorted(set(SOURCE.findall(text)))}
            records.append(record)
            by_carrier[kind].append(ident)
            for employee in employees:
                by_employee[employee].append(ident)
            for token in links:
                by_reference[token].append(ident)
    assert len(records) == len({row['address'] for row in records})
    relationships = {key: value for key, value in by_reference.items() if len(value) > 1}
    for row in records:
        linked = {ident for key in row['reference_tokens'] for ident in relationships.get(key, [])}
        row['same_reference_evidence_ids'] = sorted(linked - {row['evidence_id']})
    address_ids = {record['address']: record['evidence_id'] for record in records}
    physical_employee_context = {employee: sorted({address_ids[row['address']]
        for native in physical_rows.values() for row in employee_rows(native, employee)}) for employee in NAMES}
    parsed_actions = []
    for action in action_rows(physical_rows['actions']):
        parsed_actions.append({'evidence_id': address_ids[action['_address']],
            **{key: action.get(key, '') for key in ('id', 'action', 'owner', 'deadline', 'closure', 'status')},
            'original_row_context': action.get('_action_context', '')})
    global_hints = [record['evidence_id'] for record in records
        if re.search(r'全[部体员期]|五[名人]|所有|逐[日项]|各[人项]|本次|总则|统一|保护阶段|原始记录|版本|未决|待核', record['text'])]
    return {'schema_version': 'native-scope-index-v2', 'artifact_sha256': identities,
        'records': records, 'employee_mentions': dict(by_employee), 'shared_reference_mentions': relationships,
        'carrier_evidence_ids': dict(by_carrier),
        'physical_employee_context': physical_employee_context,
        'parsed_action_headers': parsed_actions,
        'possible_global_or_period_scope_evidence_ids': global_hints,
        'interpretation': [
            'Every extracted visible native record is retained, including global rules and records without employee names.',
            'Reference normalization is a retrieval hint only. Similar tokens do not prove identical issue scope or responsibility.',
            'Employee mention indexes never exclude other evidence or transfer one employee clinical proof to another.',
            'Physical employee sections, parsed action headers and possible global/period indexes are context hints only. Every original row remains verbatim and must be checked.',
            'A judge must resolve the actual employee, period, output, applicable rule, qualifications and linked actions from the original text.',
            'There is no adopted/source/action regex gate, score, role, cohort identity or artifact-specific correction table.'],
        'scoring_decisions': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifact', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.artifact)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'native_files': len(result['artifact_sha256']), 'records': len(result['records']),
        'employee_indexes': len(result['employee_mentions']), 'shared_references': len(result['shared_reference_mentions']),
        'scoring_decisions': None}))


if __name__ == '__main__':
    main()

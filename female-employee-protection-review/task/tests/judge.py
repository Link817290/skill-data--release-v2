"""Source-bound employee-scope requests with complete native evidence and portable replay."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import urllib.request
import uuid
from scope_index import build

HERE = Path(__file__).resolve().parent
JUDGE = HERE / 'llm_judge'

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def read(path):
    return json.loads(path.read_text())

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def now():
    return datetime.now(timezone.utc).isoformat()

def parse_response(raw):
    if raw.get('status') != 'completed' or raw.get('error'):
        raise ValueError('Provider response did not complete successfully')
    messages = [item for item in raw.get('output', []) if item.get('type') == 'message' and item.get('phase') == 'final_answer']
    if not messages:
        messages = [item for item in raw.get('output', []) if item.get('type') == 'message' and not item.get('phase')]
    texts = [part['text'] for item in messages for part in item.get('content', []) if part.get('type') == 'output_text']
    if len(texts) != 1:
        raise ValueError('Expected one final structured answer per source scope')
    return json.loads(texts[0])

def runtime_identity():
    manifest = read(JUDGE / 'manifest.json')
    for name, expected in manifest['runtime_files'].items():
        if hashlib.sha256((HERE / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Runtime manifest mismatch: ' + name)
    semantic = ('judge.py', 'native_carriers.py', 'scope_index.py', 'llm_judge/contract.json',
        'llm_judge/context.json', 'llm_judge/settings.json', 'llm_judge/prompt.md')
    return digest({'semantic_runtime_files': {name: manifest['runtime_files'][name] for name in semantic}})

def scope(item):
    employee = item.get('employee', 'all')
    if employee != 'all':
        return employee
    for name, employee_id in (('zhou', 'HZ240117'), ('he', 'HZ230086'), ('chen', 'HZ220031'), ('zhao', 'HZ230144'), ('wang', 'HZ240052')):
        if item['id'].startswith((name + '_', 'safe_' + name + '_', 'harm_' + name + '_', 'usable_' + name + '_')):
            return employee_id
    return 'HZ220031' if item['id'].startswith('benefit_') else 'all'

def packet(artifact):
    index = build(artifact)
    context, contract, settings = (read(JUDGE / name) for name in ('context.json', 'contract.json', 'settings.json'))
    catalog = [{'evidence_id': i, 'kind': 'candidate', 'carrier': row['carrier'], 'address': row['address'], 'text': row['text'],
        'explicit_employees': row['explicit_employees'], 'reference_tokens': row['reference_tokens']} for i, row in enumerate(index['records'])]
    for field, kind in (('original_materials', 'original_source'), ('original_expert_reference', 'reference')):
        for name, text in context[field].items():
            catalog.append({'evidence_id': len(catalog), 'kind': kind, 'address': name, 'text': text})
    groups = {}
    for item in contract['items']:
        groups.setdefault(scope(item), []).append(item)
    requests = {}
    model = os.environ.get('LLM_JUDGE_MODEL') or settings['model']
    for group, criteria in groups.items():
        payload = {'task_requirements': {key: value for key, value in context.items() if key not in ('original_materials', 'original_expert_reference')},
            'review_scope': group, 'criteria': criteria, 'indexed_evidence': catalog,
            'scope_links': {key: index[key] for key in ('shared_reference_mentions', 'employee_mentions', 'physical_employee_context',
                'parsed_action_headers', 'possible_global_or_period_scope_evidence_ids')},
            'scope_note': 'Every native record is retained. Parsed headers/physical sections are retrieval hints, not adopted facts or exclusive scope. Read global/full-period statements and same-case IDs. Do not transfer another employee clinical proof or infer substantive work from filled fields alone.'}
        ids = [item['id'] for item in criteria]
        completion_values = sorted({value for item in criteria for value in item.get('completion_values', [0, 1])})
        schema = {'type': 'object', 'properties': {'items': {'type': 'array', 'minItems': len(ids), 'maxItems': len(ids), 'items': {
            'type': 'object', 'properties': {'id': {'type': 'string', 'enum': ids}, 'completion': {'type': 'number', 'enum': completion_values},
                'evidence_ids': {'type': 'array', 'minItems': 1, 'items': {'type': 'integer', 'minimum': 0, 'maximum': len(catalog) - 1}},
                'rationale': {'type': 'string'}}, 'required': ['id', 'completion', 'evidence_ids', 'rationale'], 'additionalProperties': False}}},
            'required': ['items'], 'additionalProperties': False}
        requests[group] = {'model': model, 'input': [{'role': 'system', 'content': (JUDGE / 'prompt.md').read_text()},
            {'role': 'user', 'content': canonical(payload)}], 'store': False, 'reasoning': {'effort': settings['reasoning_effort']},
            'max_output_tokens': settings['max_output_tokens'], 'text': {'format': {'type': 'json_schema', 'name': 'female_source_scope_predicates', 'strict': True, 'schema': schema}}}
    request = {'transport': 'parallel-source-scope-requests-v1', 'requests': requests}
    identity = {'runtime_sha256': runtime_identity(), 'request_sha256': digest(request), 'native_sha256': index['artifact_sha256'],
        'contract_sha256': digest(contract), 'context_sha256': digest(context)}
    return request, catalog, identity, settings

def validate(decision, contract, catalog):
    if set(decision) != {'items'} or not isinstance(decision['items'], list):
        raise ValueError('Invalid decision root')
    expected = {item['id'] for item in contract['items']}
    allowed = {item['id']: set(item.get('completion_values', [0, 1])) for item in contract['items']}
    found = {}
    for item in decision['items']:
        if set(item) != {'id', 'completion', 'evidence_ids', 'rationale'} or item['id'] not in expected or item['id'] in found:
            raise ValueError('Invalid/repeated predicate fields')
        if isinstance(item['completion'], bool) or not isinstance(item['completion'], (int, float)) or item['completion'] not in allowed[item['id']] or not item['rationale'].strip() or not item['evidence_ids']:
            raise ValueError('Predicate requires an allowed completion, rationale and evidence')
        ids = item['evidence_ids']
        if any(type(i) is not int or i < 0 or i >= len(catalog) for i in ids):
            raise ValueError('Evidence reference outside complete bound catalog')
        if not any(catalog[i]['kind'] == 'candidate' for i in ids):
            raise ValueError('Reference/source alone cannot adopt candidate work')
        found[item['id']] = dict(item, evidence=[catalog[i] for i in ids])
    if set(found) != expected:
        raise ValueError('Missing predicate measurements')
    return found

def parse_bundle(raw, requests):
    if raw.get('transport') != 'parallel-source-scope-responses-v1' or set(raw['responses']) != set(requests):
        raise ValueError('Incomplete grouped raw responses')
    items = []
    for group, request in requests.items():
        result = parse_response(raw['responses'][group])
        ids = request['text']['format']['schema']['properties']['items']['items']['properties']['id']['enum']
        if len(result['items']) != len(ids) or {item['id'] for item in result['items']} != set(ids):
            raise ValueError('Source-scope reply omitted or borrowed a predicate')
        items.extend(result['items'])
    return {'items': items}

def measure(artifact, output, mode, cache_dir):
    request, catalog, identity, settings = packet(artifact)
    key, call_id = digest(identity), uuid.uuid4().hex
    attempt = output / 'judge' / call_id
    save(attempt / 'request.json', request)
    save(attempt / 'identity.json', identity)
    save(attempt / 'evidence-catalog.json', catalog)
    started = now()
    if mode == 'replay':
        entry = next((root / key for root in (JUDGE / 'cache', cache_dir) if (root / key / 'index.json').is_file()), None)
        if entry is None:
            raise ValueError('No portable cache matches complete native/source/semantic requests')
        index = read(entry / 'index.json')
        cached = entry / 'calls' / index['call_id']
        validation = read(cached / 'validation.json')
        if not validation.get('accepted') or validation['identity_sha256'] != key or read(cached / 'request.json') != request:
            raise ValueError('Cache request/semantic identity mismatch')
        raw = read(cached / 'response.json')
        if digest(raw) != validation['response_sha256']:
            raise ValueError('Cached raw-response hash mismatch')
        decision = parse_bundle(raw, request['requests'])
        if decision != read(cached / 'decision.json'):
            raise ValueError('Cached decision differs from real provider parts')
        provenance = {'origin': 'portable_provider_response_replay', 'cache_key': key, 'call_id': index['call_id']}
    elif mode == 'fresh':
        endpoint, api_key = os.environ.get('LLM_JUDGE_BASE_URL', ''), os.environ.get('LLM_JUDGE_API_KEY', '')
        from urllib.parse import urlparse
        parsed = urlparse(endpoint)
        if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password:
            raise ValueError('Fresh mode needs HTTP(S) endpoint without embedded credentials')
        endpoint = endpoint.rstrip('/') + ('/responses' if endpoint.rstrip('/').endswith('/v1') else '/v1/responses')
        def call(pair):
            group, body = pair
            part = attempt / 'parts' / group
            save(part / 'request.json', body)
            headers = {'Content-Type': 'application/json'}
            if api_key:
                headers['Authorization'] = 'Bearer ' + api_key
            api = urllib.request.Request(endpoint, data=canonical(body).encode(), headers=headers)
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *args, **kwargs):
                    return None
            with urllib.request.build_opener(NoRedirect()).open(api, timeout=settings['timeout_seconds']) as response:
                value = json.loads(response.read())
            save(part / 'response.json', value)
            save(part / 'decision.json', parse_response(value))
            return group, value
        with ThreadPoolExecutor(max_workers=len(request['requests'])) as pool:
            responses = dict(pool.map(call, request['requests'].items()))
        raw = {'transport': 'parallel-source-scope-responses-v1', 'responses': responses}
        save(attempt / 'response.json', raw)
        decision = parse_bundle(raw, request['requests'])
        provenance = {'origin': 'fresh_provider_response', 'cache_key': key, 'call_id': call_id}
    else:
        raise ValueError('Mode must be replay or fresh')
    save(attempt / 'response.json', raw)
    save(attempt / 'decision.json', decision)
    measurements = validate(decision, read(JUDGE / 'contract.json'), catalog)
    validation = {'accepted': True, 'identity_sha256': key, 'response_sha256': digest(raw), 'started_at': started, 'finished_at': now(),
        'contract_completion_schema_and_all_ids_exact': True, 'all_evidence_ids_dereference_bound_verbatim_native_source': True,
        'normalization': 'Program concatenates disjoint actual provider decision parts. Raw responses are separately preserved in an explicitly typed multi-response container; no provider fields are invented.'}
    save(attempt / 'validation.json', validation)
    if mode == 'fresh':
        cached = cache_dir / key / 'calls' / call_id
        for name, value in [('request.json', request), ('response.json', raw), ('decision.json', decision), ('validation.json', validation), ('identity.json', identity)]:
            save(cached / name, value)
        for group, body in request['requests'].items():
            save(cached / 'parts' / group / 'request.json', body)
            save(cached / 'parts' / group / 'response.json', raw['responses'][group])
        save(cache_dir / key / 'index.json', {'call_id': call_id, 'identity_sha256': key})
    first = next(iter(request['requests'].values()))
    save(output / 'judge-result.json', {'status': 'measured', 'provenance': provenance, 'identity': identity, 'measurements': measurements,
        'requested_model': first['model'], 'returned_model': {group: body.get('model') for group, body in raw['responses'].items()},
        'provider_response_ids': {group: body.get('id') for group, body in raw['responses'].items()},
        'usage': {group: body.get('usage') for group, body in raw['responses'].items()}})
    return measurements

"""Mandatory focused clock verification and conditional decision-structure ownership."""
from datetime import datetime, timezone
import hashlib
import copy
import json
import os
from pathlib import Path
import urllib.request
import uuid

import judge

HERE = Path(__file__).resolve().parent
ROOT = HERE / 'llm_judge/focused'
ERROR_UNITS = {
    'safe_zhou_payroll_decision': 'zhou_pay',
    'safe_zhou_protection_decision': 'zhou_protection',
    'safe_zhao_payroll_decision': 'zhao_pay',
    'safe_zhao_protection_decision': 'zhao_protection',
    'safe_chen_leave_decision': 'chen_system',
    'safe_he_contract_decision': 'he_contract_hold',
}


def parse_wire(raw):
    if raw.get('transport') != 'focused-validation-repair-v1':
        return judge.parse_response(raw)
    decision = judge.parse_response(raw['initial_response'])
    items = {item['id']: item for item in decision['items']}
    for repair in raw['repairs']:
        expected = repair['request']['text']['format']['schema']['properties']['items']['items']['properties']['id']['enum']
        corrected = judge.parse_response(repair['response'])
        if {item['id'] for item in corrected['items']} != set(expected):
            raise ValueError('Protocol repair did not return its exact missing/invalid fields')
        items.update({item['id']: item for item in corrected['items']})
    return {'items': list(items.values())}


def provider(request, settings):
    from urllib.parse import urlparse
    endpoint, secret = os.environ.get('LLM_JUDGE_ENDPOINT', ''), os.environ.get('LLM_JUDGE_API_KEY', '')
    parsed = urlparse(endpoint)
    if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password:
        raise ValueError('Fresh focused review needs an HTTP(S) endpoint without embedded credentials')
    headers = {'Content-Type': 'application/json'}
    if secret:
        headers['Authorization'] = 'Bearer ' + secret
    api = urllib.request.Request(endpoint, data=judge.canonical(request).encode(), headers=headers)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    with urllib.request.build_opener(NoRedirect()).open(api, timeout=settings['timeout_seconds']) as response:
        return json.loads(response.read())


def evaluate(artifact, output, mode, cache_dir, layer, criteria):
    bundle, catalog, parent_identity, _ = judge.packet(artifact)
    first = next(iter(bundle['requests'].values()))
    payload = json.loads(first['input'][1]['content'])
    payload['review_scope'] = layer
    payload['criteria'] = criteria
    if layer.startswith('clock'):
        # Preserve every native row; put the actual action columns beside its text.
        payload['same_operation_columns'] = payload['scope_links']['parsed_action_headers']
        payload['scope_links'] = {'shared_reference_mentions': payload['scope_links']['shared_reference_mentions']}
        payload['indexed_evidence'] = [{key: row[key] for key in ('evidence_id', 'kind', 'address', 'text')}
            for row in payload['indexed_evidence']]
        payload['scope_note'] = ('All native candidate rows, all original sources and the reference remain verbatim. '
            'The action-column display and shared IDs are retrieval aids, not decisions. Compare each adopted output '
            'with its own trigger, deadline and closure before considering another action. Missing evidence is not an affirmative contradiction.')
    settings = judge.read(ROOT / 'settings.json')
    ids = [item['id'] for item in criteria]
    schema = {'type': 'object', 'properties': {'items': {'type': 'array', 'minItems': len(ids), 'maxItems': len(ids), 'items': {
        'type': 'object', 'properties': {'id': {'type': 'string', 'enum': ids}, 'completion': {'type': 'integer', 'enum': [0, 1]},
            'evidence_ids': {'type': 'array', 'minItems': 1, 'items': {'type': 'integer', 'minimum': 0, 'maximum': len(catalog) - 1}},
            'rationale': {'type': 'string'}}, 'required': ['id', 'completion', 'evidence_ids', 'rationale'], 'additionalProperties': False}}},
        'required': ['items'], 'additionalProperties': False}
    request = {'model': os.environ.get('LLM_JUDGE_MODEL') or settings['model'],
        'input': [{'role': 'system', 'content': (ROOT / 'prompt.md').read_text()}, {'role': 'user', 'content': judge.canonical(payload)}],
        'store': False, 'reasoning': {'effort': settings['reasoning_effort']}, 'max_output_tokens': settings['max_output_tokens'],
        'text': {'format': {'type': 'json_schema', 'name': 'focused_source_operation_review', 'strict': True, 'schema': schema}}}
    identity = {'layer': layer, 'request_sha256': judge.digest(request), 'native_sha256': parent_identity['native_sha256'],
        'context_sha256': parent_identity['context_sha256'], 'criteria_sha256': judge.digest(criteria),
        'reader_runtime_sha256': parent_identity['runtime_sha256'],
        'focused_runtime_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    key, call_id = judge.digest(identity), uuid.uuid4().hex
    out = output / 'focused' / layer / call_id
    judge.save(out / 'request.json', request)
    judge.save(out / 'identity.json', identity)
    started = datetime.now(timezone.utc).isoformat()
    if mode == 'replay':
        entry = next((root / key for root in (HERE / 'llm_judge/cache', cache_dir) if (root / key / 'index.json').is_file()), None)
        if entry is None:
            # Transport-only revisions may reuse a real call only when its full
            # request and every source/native identity dependency are identical.
            comparable = {key: value for key, value in identity.items() if key != 'focused_runtime_sha256'}
            for root in (HERE / 'llm_judge/cache', cache_dir):
                for index_path in sorted(root.glob('*/index.json')):
                    previous = judge.read(index_path)
                    previous_call = index_path.parent / 'calls' / previous['call_id']
                    previous_identity = judge.read(previous_call / 'identity.json')
                    if {key: value for key, value in previous_identity.items() if key != 'focused_runtime_sha256'} == comparable and judge.read(previous_call / 'request.json') == request:
                        entry = index_path.parent
                        break
                if entry is not None:
                    break
        if entry is None:
            raise ValueError('Required focused source-review cache missing: ' + layer)
        index = judge.read(entry / 'index.json')
        call = entry / 'calls' / index['call_id']
        validation = judge.read(call / 'validation.json')
        original_identity = judge.read(call / 'identity.json')
        if not validation.get('accepted') or validation['identity_sha256'] != judge.digest(original_identity) or judge.read(call / 'request.json') != request:
            raise ValueError('Focused source-review identity/request mismatch')
        raw = judge.read(call / 'response.json')
        if judge.digest(raw) != validation['response_sha256']:
            raise ValueError('Focused raw-response hash mismatch')
        decision = parse_wire(raw)
        if decision != judge.read(call / 'decision.json'):
            raise ValueError('Focused decision differs from actual raw response')
        origin = {'origin': 'portable_provider_response_replay', 'cache_key': entry.name, 'call_id': index['call_id'],
            'original_identity_sha256': judge.digest(original_identity), 'exact_request_reuse': True}
    else:
        endpoint, secret = os.environ.get('LLM_JUDGE_ENDPOINT', ''), os.environ.get('LLM_JUDGE_API_KEY', '')
        from urllib.parse import urlparse
        parsed = urlparse(endpoint)
        if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password:
            raise ValueError('Fresh focused review needs an HTTP(S) endpoint without embedded credentials')
        headers = {'Content-Type': 'application/json'}
        if secret:
            headers['Authorization'] = 'Bearer ' + secret
        api = urllib.request.Request(endpoint, data=judge.canonical(request).encode(), headers=headers)
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        with urllib.request.build_opener(NoRedirect()).open(api, timeout=settings['timeout_seconds']) as response:
            raw = json.loads(response.read())
        judge.save(out / 'response.json', raw)
        decision = judge.parse_response(raw)
        origin = {'origin': 'fresh_provider_response', 'cache_key': key, 'call_id': call_id}
    try:
        measured = judge.validate(decision, {'items': criteria}, catalog)
    except ValueError:
        if mode != 'fresh':
            raise
        invalid = []
        by_id = {item.get('id'): item for item in decision.get('items', [])}
        for criterion in criteria:
            try:
                judge.validate({'items': [by_id.get(criterion['id'], {})]}, {'items': [criterion]}, catalog)
            except ValueError:
                invalid.append(criterion)
        if not invalid:
            raise
        repair_request = copy.deepcopy(request)
        repair_payload = json.loads(repair_request['input'][1]['content'])
        repair_payload['criteria'] = invalid
        repair_payload['protocol_repair'] = ('Only these invalid/missing fields need measurement. Every value, including0 for absence, '
            'must cite candidate rows demonstrating the reviewed scope. Source/reference text alone is not a candidate measurement. '
            'Do not change or rescore any other field.')
        repair_request['input'][1]['content'] = judge.canonical(repair_payload)
        repair_schema = repair_request['text']['format']['schema']['properties']['items']
        repair_schema['minItems'] = repair_schema['maxItems'] = len(invalid)
        repair_schema['items']['properties']['id']['enum'] = [item['id'] for item in invalid]
        repair_schema['items']['properties']['evidence_ids']['items'] = {'type': 'integer',
            'enum': [row['evidence_id'] for row in catalog if row['kind'] == 'candidate']}
        repair_raw = provider(repair_request, settings)
        repair_decision = judge.parse_response(repair_raw)
        judge.validate(repair_decision, {'items': invalid}, catalog)
        repair_dir = out / 'protocol-repair'
        for name, value in [('request.json', repair_request), ('response.json', repair_raw), ('decision.json', repair_decision)]:
            judge.save(repair_dir / name, value)
        raw = {'transport': 'focused-validation-repair-v1', 'initial_response': raw,
            'repairs': [{'request': repair_request, 'response': repair_raw}]}
        decision = parse_wire(raw)
        measured = judge.validate(decision, {'items': criteria}, catalog)
    validation = {'accepted': True, 'identity_sha256': key, 'response_sha256': judge.digest(raw), 'started_at': started,
        'finished_at': datetime.now(timezone.utc).isoformat(), 'all_ids_binary_and_bound_source_ids_verified': True}
    for name, value in [('response.json', raw), ('decision.json', decision), ('validation.json', validation)]:
        judge.save(out / name, value)
    if mode == 'fresh':
        entry = cache_dir / key
        call = entry / 'calls' / call_id
        for name, value in [('request.json', request), ('response.json', raw), ('decision.json', decision), ('validation.json', validation), ('identity.json', identity)]:
            judge.save(call / name, value)
        judge.save(entry / 'index.json', {'call_id': call_id, 'identity_sha256': key, 'layer': layer})
    return measured, {'layer': layer, 'identity': identity, 'provenance': origin, 'requested_model': request['model'],
        'returned_model': raw.get('model'), 'provider_response_id': raw.get('id'), 'usage': raw.get('usage'), 'wire': str(out)}


def apply(artifact, output, mode, cache_dir, primary):
    before = dict(primary)
    criteria = judge.read(ROOT / 'clock-contract.json')['items']
    clocks, proof = evaluate(artifact, output, mode, cache_dir, 'clock', criteria)
    if 'clock_atom_substantive_followup' in clocks:
        bindings, binding_proof = evaluate(artifact, output, mode, cache_dir, 'clock-source-bindings',
            judge.read(ROOT / 'source-bindings-contract.json')['items'])
        clocks['clock_atom_specific_staging_qualification'] = bindings['clock_atom_specific_staging_qualification']
        c = {key: item['completion'] for key, item in clocks.items()}
        error = (c['clock_atom_same_output_relative_bound'] and c['clock_atom_distinct_unresolved_events']
            and not c['clock_atom_specific_staging_qualification'])
        evidence = [row for item in clocks.values() for row in item['evidence']]
        evidence = list({row['evidence_id']: row for row in evidence}.values())
        proof['clock_prerequisite_measurements'] = clocks
        proof['deterministic_derivation'] = 'error=relative_bound AND distinct_unresolved_events AND NOT specific_staging; positive=followup AND trigger AND NOT error'
        proof['same_output_binding_review'] = binding_proof
        proof['zhou_event_action_measurement'] = bindings['unit__zhou_actual_night__action']
        clocks = {
            'benefit_execution_trigger_consistency': {'completion': int(c['clock_atom_substantive_followup'] and c['clock_atom_trigger_present'] and not error),
                'rationale': proof['deterministic_derivation'], 'evidence_ids': [row['evidence_id'] for row in evidence], 'evidence': evidence},
            'benefit_affirmative_execution_consistency': {'completion': int(not error),
                'rationale': proof['deterministic_derivation'], 'evidence_ids': [row['evidence_id'] for row in evidence], 'evidence': evidence}}
    final = dict(primary)
    final.update(clocks)
    if 'zhou_event_action_measurement' in proof:
        final['unit__zhou_actual_night__action'] = proof['zhou_event_action_measurement']
    reviews = [proof]
    structure = []
    for error, unit in ERROR_UNITS.items():
        keys = ['unit__' + unit + '__' + ability for ability in ('analysis', 'source', 'action')]
        if primary[error]['completion'] == 0 and any(primary[key]['completion'] == 0 for key in keys):
            for key in keys:
                structure.append({'id': key, 'completion_values': [0, 1],
                    'criterion': judge.read(ROOT / 'operation-structure-contract.json')['abilities'][key.rsplit('__', 1)[1]] +
                        ' Cite actual candidate evidence even for0 (the candidate section showing the adopted decision or the reviewed scope); original-source/reference rows alone cannot support this measurement.' +
                        ' Issue under review: ' + unit.replace('_', ' ') + '. Evaluate only this actual employee/issue from the supplied source context.'})
    if structure:
        conditional, evidence = evaluate(artifact, output, mode, cache_dir, 'conditional-operation-structure', structure)
        final.update(conditional)
        reviews.append(evidence)
    result = judge.read(output / 'judge-result.json')
    judge.save(output / 'primary-judge-result.json', result)
    result['primary_measurements'] = before
    result['measurements'] = final
    result['focused_reviews'] = reviews
    result['final_semantic_policy'] = 'Clock fields always use the focused source review. Wrong-decision units with potentially same-cause missing components use their conditional analysis/source/operability review. No role/score/actor identity selection.'
    judge.save(output / 'judge-result.json', result)
    return final

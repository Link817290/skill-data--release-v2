#!/usr/bin/env python3
"""Source-bound binary semantic measurements; never writes a numeric reward."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
TESTS = HERE.parent
TASK = TESTS.parent
sys.path.insert(0, str(TESTS))
import validator  # noqa: E402
from runtime.evidence import blocks_from_text  # noqa: E402


class JudgeError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def configuration():
    config = load(HERE / 'settings.json')
    for name, env in [('model', 'model_env'), ('protocol', 'protocol_env')]:
        config[name] = os.environ.get(config[env]) or config[name]
    if not isinstance(config['model'], str) or not config['model'].strip():
        raise JudgeError('Missing requested model')
    if config['protocol'] not in ('chat_completions', 'responses'):
        raise JudgeError('Unsupported protocol; choose chat_completions or responses explicitly')
    return config


def verify_manifest():
    manifest = load(HERE / 'manifest.json')
    for relative, expected in manifest['files'].items():
        path = TASK / relative
        if not path.resolve().is_relative_to(TASK.resolve()) or sha(path.read_bytes()) != expected:
            raise JudgeError('Judge/source manifest mismatch: ' + relative)
    return manifest


def visible_blocks(path, role='candidate'):
    # Use the validated full visible text, not the legacy business-field routing.
    _, text, _ = validator.parse_docx(path)
    blocks = blocks_from_text(text, role)
    if not blocks:
        raise JudgeError('No visible artifact text')
    return blocks


def context(artifact):
    plan = load(TESTS / 'approved_plan.json')
    references = sorted((TASK.parent / 'golden').glob('*.docx'))
    if len(references) != 1 or sha(references[0].read_bytes()) != plan['golden_sha256']:
        raise JudgeError('Frozen reference does not match the approved plan')
    briefs = sorted((TASK / 'environment/workspace/materials').glob('*110kV*.md'))
    if len(briefs) != 1:
        raise JudgeError('Ambiguous or missing supplied job brief')
    fact_data = load(TESTS / 'ground_truth.json')['facts']
    facts = {k: v for k, v in fact_data.items() if k not in ('rule_locations', 'source_texts')}
    return {'instruction': (TASK / 'instruction.md').read_text(encoding='utf-8'),
            'job_brief': briefs[0].read_text(encoding='utf-8'),
            'case_facts': facts, 'approved_plan': plan,
            'reference_blocks': visible_blocks(references[0], role='reference'),
            'candidate_blocks': visible_blocks(artifact)}


def candidate_fragments(blocks):
    """Supply exact clause spans once; the model selects IDs instead of retyping."""
    result, seen = [], set()
    for block in blocks:
        block_id, text = block['id'], block['text']
        if (not isinstance(block_id, str) or not re.fullmatch(r'cand-[0-9]{4,}', block_id)
                or block_id in seen or not isinstance(text, str) or not text.strip()):
            raise JudgeError('Invalid or duplicate candidate source block')
        seen.add(block_id)
        for match in re.finditer(r'[^,;\n\r\u3002\uff0c\uff1b\uff01\uff1f!?]+', text):
            part = match.group()
            start = match.start() + len(part) - len(part.lstrip())
            end = match.end() - len(part) + len(part.rstrip())
            if start < end:
                result.append({'id': 'frag-' + str(len(result) + 1).zfill(6),
                    'block_id': block_id, 'start': start, 'end': end, 'text': text[start:end]})
    if not result:
        raise JudgeError('No nonempty candidate fragments')
    return result


def measurement_input(contract, ctx):
    # Preserve the explicit evidence boundary and put the actual candidate last.
    payload = {'contract_version': contract['version'], 'points': contract['points'],
               'source_context': {k: v for k, v in ctx.items() if k != 'candidate_blocks'},
               'candidate_evidence': {'role': 'candidate', 'blocks': ctx['candidate_blocks'],
                                      'fragments': candidate_fragments(ctx['candidate_blocks'])}}
    return json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def bind_evidence_schema(template, blocks):
    """Bind source block and fragment selectors, with no model-quoted text fields."""
    schema = strict_json(canonical(template))
    fragments = candidate_fragments(blocks)
    schema['$defs'] = {
        'candidate_id': {'type': 'string', 'enum': [block['id'] for block in blocks]},
        'candidate_fragment_id': {'type': 'string', 'enum': [fragment['id'] for fragment in fragments]}}
    for point in schema['properties']['decisions']['properties'].values():
        point['properties']['evidence']['items'] = {'$ref': '#/$defs/candidate_id'}
        proof = point['properties'].get('proof')
        if proof:
            for role in proof['properties']:
                proof['properties'][role] = {'anyOf': [
                    {'$ref': '#/$defs/candidate_fragment_id'}, {'type': 'null'}]}
    return schema


def prepare(artifact, config):
    manifest = verify_manifest()
    contract = load(HERE / 'contract.json')
    schema = load(HERE / 'response.schema.json')
    artifact_hash = sha(artifact.read_bytes())
    ctx = context(artifact)
    if sha(artifact.read_bytes()) != artifact_hash:
        raise JudgeError('Artifact changed during extraction')
    schema = bind_evidence_schema(schema, ctx['candidate_blocks'])
    prompt = (HERE / 'prompt.md').read_text(encoding='utf-8')
    # Weights, target gaps and solver/condition identities are deliberately absent.
    user_text = measurement_input(contract, ctx)
    inference = {k: config[k] for k in ('model', 'protocol', 'max_output_tokens', 'reasoning_effort', 'temperature')}
    if config['protocol'] == 'chat_completions':
        body = {'model': config['model'], 'messages': [{'role': 'system', 'content': prompt},
                {'role': 'user', 'content': user_text}], 'max_completion_tokens': config['max_output_tokens'],
                'response_format': {'type': 'json_schema', 'json_schema': {
                    'name': 'permit_atomic_decisions', 'strict': True, 'schema': schema}}}
        if config['reasoning_effort'] is not None:
            body['reasoning_effort'] = config['reasoning_effort']
    else:
        body = {'model': config['model'], 'instructions': prompt, 'input': user_text,
                'max_output_tokens': config['max_output_tokens'], 'store': False,
                'text': {'format': {'type': 'json_schema', 'name': 'permit_atomic_decisions',
                                    'strict': True, 'schema': schema}}}
        if config['reasoning_effort'] is not None:
            body['reasoning'] = {'effort': config['reasoning_effort']}
    if config['temperature'] is not None:
        body['temperature'] = config['temperature']
    identity = {'artifact_sha256': artifact_hash, 'context_sha256': sha(canonical(ctx).encode()),
                'contract_version': contract['version'], 'files': manifest['files'], 'inference': inference,
                'request_sha256': sha(canonical(body).encode())}
    key = sha(canonical(identity).encode())
    return key, identity, body, ctx, contract


def validate_proof(node, key, contract):
    """Bind named proof roles to cited source blocks, not free-text snippets."""
    roles = contract.get('proof_policy', {}).get('roles_by_point', {}).get(key)
    if roles is None:
        return
    proof = node.get('proof')
    if type(proof) is not dict or set(proof) != set(roles):
        raise JudgeError('Missing or invalid named proof roles: ' + key)
    for role in roles:
        operand = proof[role]
        if operand is None:
            if node['value'] == 1:
                raise JudgeError('Positive finding lacks a proof operand: ' + key + '/' + role)
            continue
        if (type(operand) is not dict or set(operand) != {'block_id', 'quote'}
                or operand not in node['evidence']):
            raise JudgeError('Proof operand is not one of this points cited complete blocks: ' + key + '/' + role)


def normalize_response(decision, blocks, contract):
    """Expand declared source selectors, never model quotations or altered verdicts."""
    if type(decision) is not dict or set(decision) != {'contract_version', 'decisions'}:
        raise JudgeError('Unexpected source-native response fields')
    if decision['contract_version'] != contract['version']:
        raise JudgeError('Historical or wrong contract cannot be normalized')
    if type(decision['decisions']) is not dict:
        raise JudgeError('Invalid decisions')
    fragments = {fragment['id']: fragment for fragment in candidate_fragments(blocks)}
    source = {block['id']: block['text'] for block in blocks}
    normalized = {}
    for point, node in decision['decisions'].items():
        if type(node) is not dict or type(node.get('evidence')) is not list:
            raise JudgeError('Invalid selector node')
        converted = dict(node)
        evidence = []
        for selector in node['evidence']:
            if not isinstance(selector, str) or selector not in source:
                raise JudgeError('Unknown candidate evidence selector: ' + point)
            evidence.append({'block_id': selector, 'quote': source[selector]})
        converted['evidence'] = evidence
        if 'proof' in node:
            if type(node['proof']) is not dict:
                raise JudgeError('Invalid proof selector roles: ' + point)
            proof = {}
            for role, operand in node['proof'].items():
                if operand is None:
                    proof[role] = None
                else:
                    if not isinstance(operand, str) or operand not in fragments:
                        raise JudgeError('Unknown proof fragment selector: ' + point + '/' + role)
                    fragment = fragments[operand]
                    selector = fragment['block_id']
                    if selector not in node['evidence']:
                        raise JudgeError('Proof fragment parent is not cited by this point: ' + point + '/' + role)
                    if fragment['text'] != source[selector][fragment['start']:fragment['end']]:
                        raise JudgeError('Source fragment offset mismatch')
                    proof[role] = {'block_id': selector, 'quote': source[selector]}
            converted['proof'] = proof
        normalized[point] = converted
    return {'contract_version': decision['contract_version'], 'decisions': normalized}


def validate(decision, blocks, contract):
    if type(decision) is not dict or set(decision) != {'contract_version', 'decisions'}:
        raise JudgeError('Unexpected response fields')
    if decision['contract_version'] != contract['version']:
        raise JudgeError('Wrong contract version')
    expected = {point['id']: point for point in contract['points']}
    if type(decision['decisions']) is not dict or set(decision['decisions']) != set(expected):
        raise JudgeError('Missing, duplicate or additional point IDs')
    by_id = {block['id']: block['text'] for block in blocks}
    for key, node in decision['decisions'].items():
        fields = {'value', 'evidence', 'rationale'}
        if key in contract.get('proof_policy', {}).get('roles_by_point', {}):
            fields.add('proof')
        if type(node) is not dict or set(node) != fields:
            raise JudgeError('Invalid point shape: ' + key)
        if type(node['value']) is not int or node['value'] not in (0, 1):
            raise JudgeError('Non-binary point: ' + key)
        if not isinstance(node['rationale'], str) or not node['rationale'].strip():
            raise JudgeError('Missing rationale: ' + key)
        if type(node['evidence']) is not list:
            raise JudgeError('Invalid evidence: ' + key)
        if node['value'] == 1 and not node['evidence']:
            raise JudgeError('Positive finding lacks candidate evidence: ' + key)
        for evidence in node['evidence']:
            if type(evidence) is not dict or set(evidence) != {'block_id', 'quote'}:
                raise JudgeError('Invalid quotation shape: ' + key)
            quote = evidence['quote']
            block_id = evidence['block_id']
            if not isinstance(block_id, str) or not isinstance(quote, str) or not quote.strip():
                raise JudgeError('Invalid quotation: ' + key)
            if not re.fullmatch(r'cand-[0-9]{4,}', block_id):
                raise JudgeError('Evidence must use the candidate block namespace: ' + key)
            if block_id not in by_id or quote != by_id[block_id]:
                raise JudgeError('Quotation is not the complete declared candidate block: ' + key)
        validate_proof(node, key, contract)
        if key == 'S-wind_limit_exact' and node['value'] == 1:
            # Semantic polarity cannot override the prescribed numeric operand.
            weather = validator.norm('\n'.join(e['quote'] for e in node['evidence']))
            weather = weather.replace('\u516d\u7ea7', '6\u7ea7').replace('\u4e03\u7ea7', '7\u7ea7')
            if not re.search(r'\u98ce[^\u3002;\uff1b]{0,16}(?:(?:\u5927\u4e8e|\u8d85\u8fc7|\u9ad8\u4e8e|>)6\u7ea7|7\u7ea7(?:\u53ca\u4ee5\u4e0a|\u4ee5\u4e0a))', weather):
                raise JudgeError('Wind finding lacks the approved numeric threshold in candidate evidence')
    return decision


def strict_json(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise JudgeError('Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(JudgeError('Nonfinite JSON value')))


def extract_response(raw, config):
    if not isinstance(raw, dict) or raw.get('model') != config['model']:
        raise JudgeError('Returned model differs from the requested model or is missing')
    if config['protocol'] == 'chat_completions':
        choices = raw.get('choices')
        if not isinstance(choices, list) or len(choices) != 1 or choices[0].get('finish_reason') != 'stop':
            raise JudgeError('Missing, ambiguous or incomplete completion')
        message = choices[0].get('message', {})
        if message.get('refusal') or not isinstance(message.get('content'), str):
            raise JudgeError('Refusal or missing response text')
        return strict_json(message['content'])
    if raw.get('status') != 'completed':
        raise JudgeError('Incomplete Responses result')
    parts = [part.get('text', '') for message in raw.get('output', []) if message.get('type') == 'message'
             for part in message.get('content', []) if part.get('type') == 'output_text']
    if not parts:
        raise JudgeError('Missing Responses output text')
    return strict_json(''.join(parts))


def api_url(config):
    endpoint = os.environ.get(config['endpoint_env'], '').strip().rstrip('/')
    parsed = urllib.parse.urlsplit(endpoint)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or '@' in parsed.netloc or parsed.query or parsed.fragment:
        raise JudgeError('Set a credential-free judge endpoint base URL')
    suffix = '/chat/completions' if config['protocol'] == 'chat_completions' else '/responses'
    if parsed.path.endswith(('/chat/completions', '/responses')) and not parsed.path.endswith(suffix):
        raise JudgeError('Endpoint path conflicts with configured protocol')
    return endpoint if endpoint.endswith(suffix) else endpoint + suffix


def call(body, config, attempt):
    url = api_url(config)
    key = os.environ.get(config['api_key_env'], '')
    if not key:
        raise JudgeError('Judge credential is not configured in the trusted environment')
    if config.get('transport') == 'official-codex-cli':
        if config['protocol'] != 'responses':
            raise JudgeError('Official client transport requires Responses')
        from runtime.official_judge_client import run_judge
        os.environ['ANTHROPIC_BASE_URL'] = os.environ[config['endpoint_env']]
        os.environ['ANTHROPIC_AUTH_TOKEN'] = key
        wire = dict(body, input=[
            {'role': 'developer', 'content': [{'type': 'input_text', 'text': body['instructions']}]},
            {'role': 'user', 'content': [{'type': 'input_text', 'text': body['input']}]}])
        wire.pop('instructions', None)
        raw_stream = run_judge(wire, attempt / 'official-client')
        (attempt / 'provider-response.sse').write_bytes(raw_stream)
        raw = None
        for line in raw_stream.decode('utf-8').splitlines():
            if not line.startswith('data: '):
                continue
            try:
                event = strict_json(line[6:])
            except ValueError:
                continue
            if event.get('type') == 'response.completed':
                raw = event['response']
        if raw is None:
            raise JudgeError('No completed provider response; no score substituted')
        write(attempt / 'response.json', {'http_status': 200, 'raw_text': canonical(raw),
            'transport': 'official-codex-cli', 'raw_provider_stream': 'provider-response.sse'})
        return raw
    request = urllib.request.Request(url, data=canonical(body).encode(), headers={
        'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
    # Do not follow redirects carrying judge credentials to an unconfigured host.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=config['timeout_sec']) as response:
            text = response.read(8 * 1024 * 1024 + 1)
            if len(text) > 8 * 1024 * 1024:
                raise JudgeError('Provider response exceeds safety limit')
            text = text.decode('utf-8')
            if key in text:
                text = text.replace(key, '[REDACTED]')
            write(attempt / 'response.json', {'http_status': response.status, 'raw_text': text})
            if response.status != 200:
                raise JudgeError('Unexpected HTTP status')
            return strict_json(text)
    except urllib.error.HTTPError as exc:
        text = exc.read(8 * 1024 * 1024).decode('utf-8', errors='replace').replace(key, '[REDACTED]')
        write(attempt / 'response.json', {'http_status': exc.code, 'raw_text': text})
        write(attempt / 'transport_error.json', {'type': 'HTTPError', 'status': exc.code})
        raise JudgeError('Judge HTTP error ' + str(exc.code)) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        write(attempt / 'transport_error.json', {'type': 'transport_failure'})
        raise JudgeError('Judge transport failed; endpoint and credential omitted from diagnostics') from None


def settlement_replay_entry(key, current_request, cache_dir):
    """Use only an explicitly audited old measurement with an identical request body."""
    binding = verify_manifest().get('settlement_replay_bindings', {}).get(key)
    if not binding or binding.get('current_request_sha256') != sha(canonical(current_request).encode()):
        raise JudgeError('No approved settlement-only replay binding for this exact current input')
    source_key = binding.get('source_cache_key', '')
    if not re.fullmatch('[0-9a-f]{64}', source_key):
        raise JudgeError('Invalid source cache key in settlement-only binding')
    entry = cache_dir / source_key
    if sha((entry / 'request.json').read_bytes()) != binding.get('source_request_file_sha256'):
        raise JudgeError('Historical request differs from the approved replay binding')
    original = load(entry / 'request.json')
    old_identity = {k: v for k, v in original['identity'].items() if k != 'files'}
    current_identity = {k: v for k, v in current_request['identity'].items() if k != 'files'}
    if original['body'] != current_request['body'] or old_identity != current_identity:
        raise JudgeError('Settlement-only replay cannot change measurement inputs or inference settings')
    if sha(canonical(original['identity']).encode()) != source_key:
        raise JudgeError('Historical measurement cache identity mismatch')
    return entry, original, binding


def run(mode, artifact, output, cache_dir, refresh=False):
    config = configuration()
    key, identity, body, ctx, contract = prepare(artifact, config)
    entry = cache_dir / key
    request_record = {'identity': identity, 'body': body}
    binding = None
    source_key = key
    if mode == 'replay':
        try:
            expected_request = request_record
            if not entry.exists():
                entry, expected_request, binding = settlement_replay_entry(key, request_record, cache_dir)
                source_key = entry.name
            request_record_saved = load(entry / 'request.json')
            raw = strict_json(load(entry / 'response.json')['raw_text'])
            stored_decision = load(entry / 'decision.json')
            validation = load(entry / 'validation.json')
        except (OSError, ValueError, KeyError):
            raise JudgeError('No complete qualified cache record for this exact input/version') from None
        if request_record_saved != expected_request or validation.get('valid') is not True:
            raise JudgeError('Cache identity or validation mismatch')
        for name in ('request.json', 'response.json', 'decision.json'):
            if validation.get('sha256', {}).get(name) != sha((entry / name).read_bytes()):
                raise JudgeError('Cache record hash mismatch: ' + name)
        decision = validate(normalize_response(extract_response(raw, config), ctx['candidate_blocks'], contract),
                            ctx['candidate_blocks'], contract)
        if decision != stored_decision:
            raise JudgeError('Cached decisions do not match the original provider response')
        call_id = validation.get('call_id')
    elif mode == 'fresh' and refresh:
        call_id = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '-' + uuid.uuid4().hex
        attempt = entry / 'attempts' / call_id
        write(attempt / 'request.json', request_record)
        try:
            raw = call(body, config, attempt)
            decision = validate(normalize_response(extract_response(raw, config), ctx['candidate_blocks'], contract),
                                ctx['candidate_blocks'], contract)
            write(attempt / 'decision.json', decision)
            validation = {'valid': True, 'call_id': call_id, 'point_count': len(contract['points']),
                          'normalization_version': contract['transport']['version'],
                          'expanded_evidence_origin': 'program_sourced_from_frozen_candidate_selectors_not_model_quotations',
                          'requested_model': config['model'], 'returned_model': raw['model'],
                          'sha256': {name: sha((attempt / name).read_bytes()) for name in (
                              'request.json', 'response.json', 'decision.json')}}
            write(attempt / 'validation.json', validation)
        except Exception as exc:
            write(attempt / 'validation.json', {'valid': False, 'call_id': call_id,
                  'error_type': type(exc).__name__, 'message': 'Judge measurement failed; no score or verdict substituted'})
            raise
        lock = entry / '.publish-lock'
        try:
            lock.mkdir()
        except FileExistsError:
            raise JudgeError('Concurrent cache publication; complete attempt retained') from None
        try:
            for name in ('request.json', 'response.json', 'decision.json', 'validation.json'):
                write(entry / name, load(attempt / name))
        finally:
            lock.rmdir()
    else:
        raise JudgeError('fresh mode requires --refresh')
    result = {'status': 'measured', 'judge_version': contract['version'], 'mode': mode,
              'expanded_evidence_origin': 'program_sourced_from_frozen_candidate_selectors_not_model_quotations',
              'artifact_sha256': identity['artifact_sha256'], 'context_sha256': identity['context_sha256'],
              'requested_model': config['model'], 'returned_model': raw['model'],
              'cache_key': source_key, 'call_id': call_id,
              'evaluation_cache_key': key,
              'cache_provenance': ('revalidated_provider_response_via_audited_settlement_only_binding'
                                   if binding else 'revalidated_full_provider_response'),
              'settlement_replay_binding': binding,
              'decisions': decision['decisions']}
    write(output / 'llm_judge_result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['replay', 'fresh'], required=True)
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--artifact', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache-dir', type=Path, default=HERE / 'cache')
    args = parser.parse_args()
    try:
        result = run(args.mode, args.artifact, args.output, args.cache_dir, args.refresh)
    except Exception as exc:
        write(args.output / 'llm_judge_result.json', {'status': 'judge_error', 'error_type': type(exc).__name__,
              'message': 'Measurement unavailable or invalid. No binary decisions or reward fabricated.'})
        print('Semantic judge failed: ' + type(exc).__name__, file=sys.stderr)
        return 2
    print(json.dumps({'status': result['status'], 'mode': result['mode'], 'cache_key': result['cache_key']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

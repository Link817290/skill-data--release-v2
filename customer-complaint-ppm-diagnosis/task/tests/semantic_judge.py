"""Evidence-bound live semantic review and exact, validated offline reply replay."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from judge_transport import call as call_responses

from numeric_audit import numeric_audit
from review_contract import fingerprint, semantic_fingerprint
from workbook_evidence import Workbook, source_facts

HERE = Path(__file__).resolve().parent
ASSETS = HERE / 'content_judge'
NUMERIC = {'P-MONTH-TABLE', 'P-PRODUCT-TABLE'} | {
    prefix + product for prefix in ('P-SHARE-', 'P-RELATIVE-') for product in 'ABCD'}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False, encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        temporary = Path(stream.name)
    temporary.replace(path)


def context(artifact):
    from runtime_assets import source_path
    source = source_path()
    candidate = Workbook(artifact)
    source_book = Workbook(source)
    criteria = json.loads((HERE / 'criteria.json').read_text())['items']
    params = json.loads((HERE / 'scoring_params.json').read_text())
    config = json.loads((ASSETS / 'config.json').read_text())
    model = os.environ.get('LLM_JUDGE_MODEL') or config['model']
    facts = source_facts(source_book)
    payload = {
        'instruction': (ASSETS / 'instruction.md').read_text(),
        'output_contract': json.loads((HERE / 'materials/output_contract.json').read_text()),
        'all_criteria': criteria,
        'semantic_criterion_ids': [c['item_id'] for c in criteria if c['item_id'] not in NUMERIC],
        'source': source_book.evidence(), 'source_recomputed_facts': facts,
        'reference': Workbook(ASSETS / 'reference.xlsx').evidence(),
        'candidate': candidate.evidence(),
    }
    serialized = canonical(payload)
    check(len(serialized) <= config['max_evidence_chars'], 'Full workbook evidence exceeds judge input bound; no silent truncation')
    prompt = (ASSETS / 'prompt.md').read_text() + '\n\nINPUT DATA\n' + serialized
    identity = {'artifact_sha256': sha(artifact), 'source_sha256': sha(source),
                'semantic_fingerprint': semantic_fingerprint(criteria, sha(source)),
                'model': model, 'prompt': prompt, 'version': config['version']}
    key = hashlib.sha256(canonical(identity).encode('utf-8')).hexdigest()
    return {'artifact': artifact, 'candidate': candidate, 'source_book': source_book,
            'facts': facts, 'criteria': criteria, 'params': params, 'config': config,
            'model': model, 'prompt': prompt, 'identity': identity, 'key': key}


def extract_json(text):
    value = text.strip()
    if value.startswith('```'):
        value = value.split('\n', 1)[1].rsplit('```', 1)[0]
    result = json.loads(value)
    check(isinstance(result, dict), 'Judge reply must be a JSON object')
    return result


def numeric_problem_item(problem, bindings):
    item = problem['item_id']
    if item in {'P-SHARES', 'P-RELATIVES'}:
        field = 'share' if item == 'P-SHARES' else 'relative'
        product = next(row['product'] for row in bindings['products']
                       if row.get(field) == problem['location'])
        item = ('P-SHARE-' if field == 'share' else 'P-RELATIVE-') + product
    return item


def compile_review(ctx, response):
    book = ctx['candidate']
    known = {c['item_id'] for c in ctx['criteria']}
    expected = known - NUMERIC
    decisions = response.get('semantic_items')
    check(isinstance(decisions, list) and len(decisions) == len(expected), 'Exactly sixteen semantic decisions required')
    check({d.get('item_id') for d in decisions} == expected, 'Semantic item IDs missing or duplicated')
    normalized = []
    for decision in decisions:
        item = dict(decision)
        check(item.get('status') in {'correct', 'incorrect', 'missing_or_incomplete'}, 'Invalid semantic status')
        check(isinstance(item.get('review_proof'), str) and item['review_proof'].strip(), 'Missing item justification')
        evidence = item.get('evidence')
        check(isinstance(evidence, list), 'Evidence must be a list')
        locators = []
        for entry in evidence:
            check(isinstance(entry, dict), 'Evidence requires location and exact quote')
            location, quote = entry.get('location'), entry.get('quote')
            check(isinstance(location, str) and isinstance(quote, str) and quote.strip(), 'Empty evidence locator/quote')
            check(book.quote_exists(location, quote), f'Evidence quote absent: {location}')
            locators.append(location)
        check(item['status'] != 'correct' or bool(locators), 'Credited item lacks exact workbook evidence')
        check(item['status'] == 'correct' or bool(item.get('zero_reason')), 'Zero credit requires a specific reason')
        item['evidence'] = list(dict.fromkeys(locators))
        normalized.append(item)
    bindings = json.loads(canonical(response.get('table_bindings')))
    check(isinstance(bindings, dict) and isinstance(bindings.get('months'), list)
          and isinstance(bindings.get('products'), list), 'Missing numeric table bindings')
    for group in ('months', 'products'):
        for row in bindings[group]:
            for key in list(row):
                if row[key] is None:
                    row.pop(key)
            if 'product_ppm' in row:
                row['product_ppm'] = {k: v for k, v in row['product_ppm'].items() if v is not None}
    audited, problems = numeric_audit(book, bindings, ctx['facts'])
    errors = response.get('confirmed_errors')
    check(isinstance(errors, list), 'Missing confirmed error list')
    check(all(isinstance(e, dict) and isinstance(e.get('key'), str) and e['key'].strip() for e in errors), 'Independent errors require nonempty keys')
    check(len({e['key'] for e in errors}) == len(errors), 'Duplicate independent error keys')
    normalized_errors = []
    for error in errors:
        e = dict(error)
        check(e.get('scope_class') in {'required', 'extra'}, 'Invalid error scope')
        check(isinstance(e.get('locations'), list) and e['locations'], 'Error lacks candidate locations')
        check(isinstance(e.get('quote'), str) and e['quote'].strip(), 'Error lacks exact quote')
        check(any(book.quote_exists(loc, e['quote']) for loc in e['locations']), 'Error quote absent from workbook')
        for loc in e['locations']:
            if loc.startswith('part:'):
                check(loc in book.parts, 'Unknown error evidence part')
            else:
                book.cell(loc)
        check(isinstance(e.get('reason'), str) and e['reason'].strip(), 'Error lacks justification')
        affected = e.get('affected_required_items')
        check(isinstance(affected, list) and set(affected) <= known, 'Unknown affected criterion')
        check((e['scope_class'] == 'required') == bool(affected), 'Error scope and affected criteria disagree')
        basis = e.get('basis')
        check(isinstance(basis, dict) and basis.get('explanation'), 'Error lacks source/criterion basis')
        check(isinstance(basis.get('criteria_ids'), list) and basis['criteria_ids']
              and set(basis['criteria_ids']) <= known, 'Error lacks a known criterion basis')
        for loc in basis.get('source_locations', []):
            ctx['source_book'].cell(loc)
        e['anchor'] = canonical(basis)
        normalized_errors.append(e)
    uncovered = []
    for problem in problems:
        item = numeric_problem_item(problem, bindings)
        if not any(problem['location'] in e['locations'] and item in e['affected_required_items'] for e in normalized_errors):
            uncovered.append({**problem, 'required_item_id': item})
    check(not uncovered, 'Numeric mismatches need correctly grouped error decisions: ' + canonical(uncovered))
    for decision in normalized:
        if decision['status'] == 'incorrect':
            check(any(decision['item_id'] in e['affected_required_items'] for e in normalized_errors),
                  'Incorrect semantic item lacks an evidenced error')
    for item in sorted(NUMERIC):
        normalized.append({'item_id': item, 'status': 'missing_or_incomplete',
                           'evidence': [], 'zero_reason': 'Settled by source-bound numeric audit',
                           'review_proof': 'Numeric completion is computed from bound cells, formulas and original source counts.'})
    return {'schema_version': 'ppm-source-verified-content-review-v1',
            'review_origin': 'llm_content_judge_v1',
            'artifact_sha256': ctx['identity']['artifact_sha256'],
            'source_sha256': ctx['identity']['source_sha256'],
            'judge_fingerprint': fingerprint(ctx['criteria'], ctx['params'], ctx['identity']['source_sha256']),
            'scorer_sha256': sha(HERE / 'validator.py'),
            'judge_cache_key': ctx['key'], 'required_items': normalized,
            'table_bindings': bindings, 'confirmed_errors': normalized_errors}


def call(messages, ctx):
    base = os.environ.get('LLM_JUDGE_BASE_URL')
    key = os.environ.get('LLM_JUDGE_API_KEY')
    check(base and key, 'Live content judge requires a Responses endpoint and credentials')
    payload = {'model': ctx['model'], 'store': False,
               'max_output_tokens': ctx['config']['max_tokens'],
               'input': [{'role': row['role'], 'content': [{'type': 'input_text', 'text': row['content']}]} for row in messages],
               'text': {'format': {'type': 'json_object'}}}
    log_root = Path(os.environ.get('VERIFIER_OUTPUT_DIR', '/logs/verifier'))
    write_json(log_root / 'judge_request_status.json', {
        'external_judge_called': True, 'judge_cache_key': ctx['key'], 'model': ctx['model']})
    timeout = int(os.environ.get('LLM_JUDGE_TIMEOUT_SECONDS', ctx['config']['timeout_sec']))
    envelope,raw = call_responses(payload,base,key,timeout,1)
    check(bool(raw.strip()), 'Judge returned no text response')
    metadata = {k: envelope.get(k) for k in ('id', 'model', 'status', 'usage')}
    metadata['protocol'] = 'openai-responses'
    response_key = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    write_json(log_root / ('judge_transport_' + response_key + '.json'),
               {'raw_response': raw, 'provider': metadata, 'judge_cache_key': ctx['key']})
    return raw, metadata


def review_for_artifact(artifact):
    from runtime_assets import ReviewRequired
    artifact = Path(artifact)
    ctx = context(artifact)
    writable = Path(os.environ.get('LLM_JUDGE_CACHE_DIR') or os.environ.get('VERIFIER_OUTPUT_DIR', '/logs/verifier'))
    if not os.environ.get('LLM_JUDGE_CACHE_DIR'):
        writable = writable / 'content_judge_cache'
    check(not writable.resolve().is_relative_to(artifact.parent.resolve()), 'Judge cache cannot reside in the candidate directory')
    shipped_index = ASSETS / 'index.json'
    index = json.loads(shipped_index.read_text()) if shipped_index.exists() else {'entries': {}}
    record = index.get('entries', {}).get(ctx['key'])
    cache_file = ASSETS / record['path'] if record else writable / (ctx['key'] + '.json')
    envelope = None
    origin = 'shipped_cache' if record else 'evaluator_cache'
    if cache_file.exists():
        check(not cache_file.is_symlink(), 'Symlink judge cache refused')
        if record:
            check(record['sha256'] == sha(cache_file), 'Shipped judge response digest mismatch')
        envelope = json.loads(cache_file.read_text())
        check(envelope.get('key') == ctx['key'] and envelope.get('identity') == ctx['identity'], 'Judge response belongs to different inputs/runtime')
        response = extract_json(envelope['raw_response'])
        review = compile_review(ctx, response)
    else:
        origin = 'live'
        if os.environ.get('LLM_JUDGE_MODE', 'fresh').lower() == 'replay' or not (
            os.environ.get('LLM_JUDGE_BASE_URL')):
            raise ReviewRequired('No replayable content-judge response for these inputs; configure evaluator judge access for a new answer')
        messages = [{'role': 'user', 'content': ctx['prompt']}]
        attempts = []
        for attempt in range(ctx['config']['max_attempts']):
            raw, metadata = call(messages, ctx)
            entry = {'raw_response': raw, 'provider': metadata}
            attempts.append(entry)
            try:
                review = compile_review(ctx, extract_json(raw))
                break
            except (ValueError, KeyError, TypeError, StopIteration) as error:
                entry['validation_error'] = str(error)
                messages.extend([{'role': 'assistant', 'content': raw},
                                 {'role': 'user', 'content': 'Validation failed: ' + str(error) + '\nReturn a corrected complete JSON object. Do not invent missing evidence or change criteria.'}])
        else:
            write_json(writable / (ctx['key'] + '.rejected.json'), {'key': ctx['key'], 'identity': ctx['identity'], 'attempts': attempts})
            raise ReviewRequired('Content judge did not produce a valid evidence-bound review; raw attempts preserved')
        envelope = {'schema_version': 'ppm-replayable-judge-response-v1', 'key': ctx['key'],
                    'identity': ctx['identity'], 'raw_response': raw, 'provider': metadata,
                    'attempts': attempts}
        write_json(cache_file, envelope)
    review['judge_response_sha256'] = hashlib.sha256(envelope['raw_response'].encode('utf-8')).hexdigest()
    review.update(judge_response_origin=origin, judge_model=ctx['model'], judge_provider=envelope['provider'])
    review_path = writable / (ctx['key'] + '.derived-review.json')
    write_json(review_path, review)
    return review_path

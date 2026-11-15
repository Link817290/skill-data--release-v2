"""Deterministic capture assurance from preserved facts and unique topics."""
import hashlib
import json


def claim_id(claim):
    value=dict(asserted_value=claim['asserted_value'],adopted=claim['adopted_claim_citations'])
    encoded=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    return 'claim-'+hashlib.sha256(encoded).hexdigest()[:24]


def derive_capture_assurance(claims,topics,known_producer_context):
    assert set(topics)=={claim_id(row) for row in claims}
    capture=[dict(id=claim_id(row),verdict=row['verdict'],asserted_value=row['asserted_value']) for row in claims if topics[claim_id(row)]=='capture_construction_or_coverage']
    verdicts=[row['verdict'] for row in capture]
    assert all(value in ['accurate','contradicted','unsupported','unclear'] for value in verdicts)
    if 'unclear' in verdicts:completion=None
    elif 'contradicted' in verdicts:completion=0
    elif 'unsupported' in verdicts:completion=.5
    elif known_producer_context:completion=1
    else:completion=None
    return dict(completion=completion,capture_claims=capture,known_producer_context=bool(known_producer_context),free_owner_model_completion_used=False,rule='Preserve actual base factual verdicts. Topics allocate claims only. Unclear/unavailable producer context remains unknown; encoded identity never overrides an independent capture claim.')

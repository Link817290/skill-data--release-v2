"""Bind evaluator decisions to the source and complete local scoring runtime."""
import hashlib
import json
from pathlib import Path


def fingerprint(criteria, params, source_sha256):
    here = Path(__file__).resolve().parent
    inputs = ("validator.py", "workbook_evidence.py", "numeric_audit.py", "review_contract.py",
              "runtime_assets.py", "entrypoint.py", "test.sh", "criteria.json", "scoring_params.json",
              "materials/output_contract.json", "semantic_judge.py", "content_judge/config.json",
              "content_judge/prompt.md", "content_judge/instruction.md", "content_judge/reference.xlsx")
    hashes = {name: hashlib.sha256((here / name).read_bytes()).hexdigest() for name in inputs}
    contract = {"schema": "ppm-source-verified-content-review-v1", "criteria": criteria,
                "params": params, "source_sha256": source_sha256, "inputs": hashes}
    canonical = json.dumps(contract, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def semantic_fingerprint(criteria, source_sha256):
    """Bind the actual judge inputs independently of settlement-only weights."""
    here = Path(__file__).resolve().parent
    names = ('workbook_evidence.py', 'numeric_audit.py', 'criteria.json',
             'materials/output_contract.json', 'content_judge/config.json',
             'content_judge/prompt.md', 'content_judge/instruction.md', 'content_judge/reference.xlsx')
    content = {'schema': 'ppm-semantic-input-v2', 'criteria': criteria,
               'source_sha256': source_sha256,
               'inputs': {name: hashlib.sha256((here / name).read_bytes()).hexdigest() for name in names}}
    return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()

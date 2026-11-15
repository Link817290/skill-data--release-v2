"""Expose selected actual calls in the standard portable judge layout."""
import hashlib
import json
from pathlib import Path
import shutil


def standardize(output, cache_dir=None):
    output = Path(output)
    result = json.loads((output / 'judge-result.json').read_text())
    identity = result['identity']
    public = dict(result, judge_version='female-native-source-contract-v91',
        artifact_sha256=identity['native_sha256'], context_sha256=identity['context_sha256'],
        contract_sha256=identity['contract_sha256'], items=list(result['measurements'].values()))
    (output / 'llm_judge_result.json').write_text(json.dumps(public, ensure_ascii=False, indent=2) + '\n')
    if cache_dir is None or result['provenance']['origin'] != 'fresh_provider_response':
        return public
    entry = Path(cache_dir) / result['provenance']['cache_key']
    index_path = entry / 'index.json'
    index = json.loads(index_path.read_text())
    call = entry / 'calls' / index['call_id']
    hashes = {}
    for name in ('request.json', 'response.json', 'decision.json', 'validation.json'):
        source = call / name
        target = entry / name
        shutil.copyfile(source, target)
        hashes[name] = hashlib.sha256(source.read_bytes()).hexdigest()
        assert hashlib.sha256(target.read_bytes()).hexdigest() == hashes[name]
    index['selected_call_top_level_files_sha256'] = hashes
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n')
    return public

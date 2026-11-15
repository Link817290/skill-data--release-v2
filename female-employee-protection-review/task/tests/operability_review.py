"""Uniform action-structure and minimum-usability source reviews."""
from pathlib import Path

import focused_review
import judge

HERE = Path(__file__).resolve().parent
ROOT = HERE / 'llm_judge/focused'


def apply(artifact, output, mode, cache_dir, measured):
    final = dict(measured)
    proofs = []
    for layer, filename in (('action-operability', 'action-operability-contract.json'), ('minimum-usability', 'minimum-contract.json')):
        criteria = judge.read(ROOT / filename)['items']
        current, proof = focused_review.evaluate(artifact, output, mode, cache_dir, layer, criteria)
        final.update(current)
        proofs.append(proof)
    # This exact original-source scope correction follows the older broad action
    # pass. Version retention remains mandatory at an actual record conflict.
    clock_review = judge.read(output / 'judge-result.json')['focused_reviews'][0]
    if ('zhou_event_action_measurement' in clock_review and
            measured['safe_zhou_protection_decision']['completion'] == 1):
        final['unit__zhou_actual_night__action'] = clock_review['zhou_event_action_measurement']
    result = judge.read(output / 'judge-result.json')
    result['measurements_before_operability_minimum_review'] = measured
    result['measurements'] = final
    result['focused_reviews'].extend(proofs)
    result['final_semantic_policy'] += ' Action components always use the source-bound operability review; minimum usability always uses its separate seven core predicates, without a strict threshold.'
    judge.save(output / 'judge-result.json', result)
    return final

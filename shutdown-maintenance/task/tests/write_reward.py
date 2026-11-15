"""Publish standard strict and lenient reward files from one complete evaluation."""
import json
import math
from pathlib import Path
import sys


def main():
    source=Path(sys.argv[1]);target=Path(sys.argv[2]);result=json.loads(source.read_text())
    if result.get('measurement_complete') is not True:
        raise RuntimeError('Cannot publish a reward for an incomplete measurement')
    rewards=result.get('rewards',{})
    strict=rewards.get('strict');length=rewards.get('lenient')
    if any(type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=1
           for value in [strict,length]):
        raise RuntimeError('Complete evaluation lacks finite strict/lenient rewards')
    target.mkdir(parents=True,exist_ok=True)
    compact={'reward':strict,'reward_strict':strict,'reward_lenient':length}
    (target/'reward.json').write_text(json.dumps(compact,indent=2)+'\n')
    (target/'reward.txt').write_text(str(strict)+'\n')
    (target/'reward_strict.txt').write_text(str(strict)+'\n')
    (target/'reward_lenient.txt').write_text(str(length)+'\n')
    detail=dict(result,reward=strict,reward_formulas={
        'strict':'0.90 * business_completion + 0.05 * embedded_independent_validation_receipt + 0.05 * maintainable_event_update_mechanism',
        'lenient':'product of five declared binary must-have decisions'})
    (target/'reward_detail.json').write_text(json.dumps(detail,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()

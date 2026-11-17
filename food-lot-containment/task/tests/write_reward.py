"""Publish the standard dual-reward files from one complete evaluation."""
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
    if any(type(x) not in (int,float) or not math.isfinite(x) or not 0<=x<=1 for x in [strict,length]):
        raise RuntimeError('Complete evaluation lacks finite strict/lenient rewards')
    target.mkdir(parents=True,exist_ok=True)
    compact={'reward':strict,'reward_strict':strict,'reward_lenient':length}
    (target/'reward.json').write_text(json.dumps(compact,indent=2)+'\n')
    (target/'reward.txt').write_text(str(strict)+'\n')
    (target/'reward_strict.txt').write_text(str(strict)+'\n')
    (target/'reward_lenient.txt').write_text(str(length)+'\n')
    detail=dict(result,reward=strict,reward_formulas={
        'strict':'0.46*min(scopes,channels) + 0.07*min(changes,amendment_communication) + 0.34*(distribution_scope*execution_limits) + 0.13*recipient_action; unusable_notice fatal override',
        'lenient':'product of four declared binary must-have decisions'})
    (target/'reward_detail.json').write_text(json.dumps(detail,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()

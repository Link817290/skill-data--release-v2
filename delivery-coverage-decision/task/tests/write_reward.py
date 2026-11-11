"""Publish standard strict and lenient reward files from a complete evaluation."""
import json
import math
from pathlib import Path
import sys


def main():
    result = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    target = Path(sys.argv[2])
    if result.get('measurement_complete') is not True:
        raise RuntimeError('Cannot publish a reward for an incomplete measurement')
    strict = result.get('rewards', {}).get('strict')
    lenient = result.get('rewards', {}).get('lenient')
    if any(type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1
           for value in [strict, lenient]):
        raise RuntimeError('Complete evaluation lacks finite strict and lenient rewards')
    target.mkdir(parents=True, exist_ok=True)
    compact = {"reward": strict, "reward_strict": strict, "reward_lenient": lenient}
    (target / 'reward.json').write_text(json.dumps(compact, indent=2) + '\n')
    (target / 'reward.txt').write_text(str(strict) + '\n')
    (target / 'reward_strict.txt').write_text(str(strict) + '\n')
    (target / 'reward_lenient.txt').write_text(str(lenient) + '\n')
    detail = dict(result, reward=strict, reward_formulas={
        'strict': 'weighted additive local chains with independently declared damage and 0.5 retention',
        'lenient': 'binary conjunction of five declared must-have decisions'})
    (target / 'reward_detail.json').write_text(json.dumps(detail, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()

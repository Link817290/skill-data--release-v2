from pathlib import Path
import json
source=Path('/logs/verifier/equipment-changeover-evaluation/result.json')
result=json.loads(source.read_text(encoding='utf-8'))
if result.get('measurement_complete') is not True:raise RuntimeError('Cannot publish incomplete measurement')
keys=('reward','reward_strict','reward_lenient','rewards','measurement_complete','strict_score','lenient_score')
reward={key:result[key] for key in keys}
reward.update(score_version='business10-equipment-release-v13-linear',score_profile='bench')
Path('/logs/verifier/reward.json').write_text(json.dumps(reward,ensure_ascii=False,indent=2),encoding='utf-8')

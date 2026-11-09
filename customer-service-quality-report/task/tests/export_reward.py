import json
import sys
from pathlib import Path

out=Path(sys.argv[1])
detail=json.loads((out/"reward_detail.json").read_text())
strict=float(detail["rewards"]["strict"])
detail["reward_strict"]=strict
(out/"reward_detail.json").write_text(json.dumps(detail,ensure_ascii=False,indent=2),encoding="utf-8")
(out/"reward.json").write_text(json.dumps(dict(reward=strict,reward_strict=strict,score=strict)),encoding="utf-8")
for name in ("reward.txt","reward_strict.txt"):
    (out/name).write_text(str(strict)+"\n")

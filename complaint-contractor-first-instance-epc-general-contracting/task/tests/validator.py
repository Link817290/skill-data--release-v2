#!/usr/bin/env python3
# harbor 归一化：定位 agent 的 markdown 交付物 -> 调 submission 自带 task_judge.py -> 打印 judge 的完整结果 JSON。
# 判分逻辑在 task_judge.py；本文件只做 I/O 定位与取数。task_judge 顶层有 PACKAGE_ROOT=parents[3]，
# 容器内 /tests 只有 3 层会 IndexError，故把 program_judge 嵌到 pjroot/task/tests/ 下补足深度。
# 只接受声明的交付路径 <WS>/artifacts/civil-complaint.md（名称、扩展名、大小写精确），
# 不回退到 artifacts/*.md，也不接受直接传入的文件；缺失即 0 并写 error=deliverable_missing。
# 输出 judge 的完整结果（items / deduction_items / penalty_instances / retention…），
# test.sh 把它原样写入 verifier/reward_detail.json。
import sys, os, json, subprocess, tempfile, math
from semantic_judge import adjudicate, POSITIVE, RULES
WS = sys.argv[1] if len(sys.argv) > 1 else "/workspace"
DELIV = 'civil-complaint.md'  # 交付物文件名 (instruction 指定)
here = os.path.dirname(os.path.abspath(__file__))
art = os.path.join(WS, "artifacts", DELIV)
if not os.path.isdir(WS) or not os.path.isfile(art) or DELIV not in os.listdir(os.path.dirname(art)):
    print(json.dumps({"final_score": 0.0, "rewards": {"strict": 0.0, "lenient": 0.0},
                      "error": "deliverable_missing", "artifact": art}, ensure_ascii=False))
    sys.exit(0)
# A private directory per run: a fixed path would let two submissions scored at the same
# time read each other's result. Cleaned up when the process exits.
_detail_dir = tempfile.TemporaryDirectory(prefix="pj_")
out = os.path.join(_detail_dir.name, "reward_detail.json")
judge = os.path.join(here, "pjroot", "task", "tests", "program_judge", "task_judge.py")
contract = os.path.join(here, "rubric-contract.json")
r = subprocess.run(
    [sys.executable, "-B", judge, art, "--contract", contract, "--json", out],
    capture_output=True, text=True)
try:
    d = json.load(open(out, encoding="utf-8"))
    decision = adjudicate(open(art, encoding="utf-8").read())
    for item in d["items"]:
        if item["id"] in POSITIVE:
            verdict = decision["items"][item["id"]]
            item.update(program_fraction=item["fraction"], program_reason=item["reason"],
                        fraction=verdict["fraction"], earned=item["weight"] * verdict["fraction"],
                        reason=verdict["reason"], semantic_evidence=verdict)
    semantic_deductions = set(RULES) - POSITIVE
    # Professional errors use the conservative union of both Oracles: semantic
    # review can catch equivalent wording, while a proven local error cannot be
    # erased by a model miss.
    penalties = list(d["penalty_instances"])
    coefficients = {x["id"]: x["penalty_coefficient"] for x in json.load(open(contract, encoding="utf-8"))["deduction_items"]}
    for key in semantic_deductions:
        verdict = decision["items"][key]
        if verdict["fraction"] and not any(key in p.get("item_ids", []) for p in penalties):
            penalties.append({"damage_instance_key": f"semantic_{key}", "causal_root_ids": [f"semantic_{key}"],
                              "item_ids": [key], "penalty_coefficient": coefficients[key], "semantic_evidence": verdict})
    d["program_penalty_instances"] = d["penalty_instances"]
    d["penalty_instances"] = penalties
    d["positive_earned"] = sum(item["earned"] for item in d["items"])
    d["retention_multiplier"] = math.prod(p["penalty_coefficient"] for p in penalties)
    d["final_score"] = d["positive_earned"] * d["retention_multiplier"]
    fractions = {item["id"]: item["fraction"] for item in d["items"]}
    critical = {"D01", "D02", "D04", "D05", "D06", "D10", "D11", "D12", "D14", "D15"}
    d["rewards"] = {"strict": d["final_score"],
                    "lenient": float(all(fractions.get(key) == 1 for key in ("P02", "P10"))
                                     and not any(critical.intersection(p["item_ids"]) for p in penalties))}
    d["artifact_path"] = art
    d["semantic_judge"] = decision
    d["status"] = "measured"
    print(json.dumps(d, ensure_ascii=False))
except Exception as exc:
    sys.stderr.write(f"judge rc={r.returncode} stderr={r.stderr[:400]}\n")
    # The deliverable is there but the judge produced no result (crash, unreadable input,
    # missing tool): a scoring error, never a silent zero.
    sys.stderr.write(f"SCORING ERROR: judge produced no result for {art}: {exc}\n")
    sys.exit(2)

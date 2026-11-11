#!/usr/bin/env python3
# harbor 归一化:定位 agent 交付物(docx优先)-> 调 task_judge.py -> 打印 final_score。
# 本文件只做 I/O 定位与取数,判分逻辑全部在 task_judge.py 与 rubric-contract.json 中。program_judge 顶层
# PACKAGE_ROOT=parents[3],容器内 /tests 只有 3 层会 IndexError,故嵌到 pjroot/task/tests/ 下补足深度。
import sys, os, json, glob, subprocess, tempfile
WS = sys.argv[1] if len(sys.argv) > 1 else "/workspace"
DELIV = '质证意见.docx'  # instruction 指定的交付文件名(.docx)
here = os.path.dirname(os.path.abspath(__file__))


# --- delivery gate (deliverable_gate.json beside this file) ---
def _gate_json(payload, **_):
    try:
        sys.path.insert(0, here)
        import deliverable_gate as _dg
        _cfg = _dg.load(here)
        if _cfg:
            _ws = WS if os.path.isdir(WS) else os.path.dirname(WS)
            _verdict = _dg.check(_ws, _cfg, here)
            _j = globals().get("d") if isinstance(globals().get("d"), dict) else {}
            _ledger = payload.get("scoring_ledger") or {
                "schema_version": "pd-ledger-v1",
                "positive_completion": {i["id"]: float(i.get("fraction") or 0.0) for i in (_j.get("items") or [])},
                "positive_earned": float(_j.get("positive_earned") or 0.0),
                "retention": float(_j.get("retention_multiplier") if _j.get("retention_multiplier") is not None else 1.0),
                "damage_instances": [{"key": x.get("damage_instance_key"), "item_ids": sorted(x.get("item_ids") or [])}
                                     for x in (_j.get("penalty_instances") or [])],
                "final_score": float(payload.get("final_score") or 0.0)}
            _dg.settle(_ledger, _verdict, _cfg)
            payload["final_score"] = _ledger["final_score"]
            payload.setdefault("rewards", {})["strict"] = _ledger["final_score"]
            if _verdict["missing"] or _ledger.get("deliverable_gate", {}).get("lenient_fail"):
                payload["rewards"]["lenient"] = 0.0
            payload["scoring_ledger"] = _ledger
    except Exception as _exc:
        # A configured gate that cannot settle must fail loudly: returning the ungated score here
        # would let the validator's own filename fallback feed any file to the judge at full marks.
        sys.stderr.write(f"deliverable gate FAILED: {_exc}\n")
        payload["final_score"] = 0.0
        payload["rewards"] = {"strict": 0.0, "lenient": 0.0}
        payload["error"] = f"deliverable gate failed: {_exc}"
    return json.dumps(payload, ensure_ascii=False)
if os.path.isfile(WS):
    # Handed one file (a Golden replay by hand), judge that file.
    art = WS
else:
    art = os.path.join(WS, "artifacts", DELIV)
# The judge writes its result to a private temporary file: several scorings run side by side.
fd, out = tempfile.mkstemp(prefix="pj_reward_detail_", suffix=".json")
os.close(fd)
judge = os.path.join(here, "pjroot", "task", "tests", "program_judge", "task_judge.py")
contract = os.path.join(here, "rubric-contract.json")
r = subprocess.run(
    [sys.executable, judge, art, "--contract", contract, "--json", out],
    capture_output=True, text=True)
if r.returncode:
    sys.stderr.write("judge infrastructure failed: "+r.stderr+"\n")
    os.unlink(out)
    raise SystemExit(2)
try:
    d = json.load(open(out, encoding="utf-8"))
    fs = float(d["final_score"])
    # The judge evaluates the named legal-usability items declared in rubric-contract.json.
    lenient = float(d["lenient_gate_pass"])
    print(_gate_json({**d, "final_score": fs, "rewards": {"strict": fs, "lenient": lenient}, "artifact": art}, ensure_ascii=False))
except Exception as exc:
    sys.stderr.write(f"judge rc={r.returncode} stderr={r.stderr[:400]}\n")
    print(_gate_json({"final_score": 0.0, "rewards": {"strict": 0.0, "lenient": 0.0}, "error": str(exc), "artifact": art}, ensure_ascii=False))

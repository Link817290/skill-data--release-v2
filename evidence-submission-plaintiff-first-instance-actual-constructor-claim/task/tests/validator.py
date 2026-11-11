#!/usr/bin/env python3
# harbor 归一化:定位 agent 交付物(docx优先)-> 调 submission 自带 task_judge.py -> 打印 final_score。
# 本文件只做 I/O 定位与取数,不参与判分。program_judge 顶层 PACKAGE_ROOT=parents[3],
# 容器内 /tests 只有 3 层会 IndexError,故嵌到 pjroot/task/tests/ 下补足深度。
import sys, os, json, glob, subprocess, tempfile
WS = sys.argv[1] if len(sys.argv) > 1 else "/workspace"
DELIV = 'evidence-submission-opinion.md'  # instruction 指定的交付文件名(.md)
here = os.path.dirname(os.path.abspath(__file__))


# --- delivery gate (deliverable_gate.json beside this file; the shared deliverable_gate module) ---
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
art = os.path.join(WS, "artifacts", DELIV)
# No fallback: the brief names one exact delivery path and deliverable_gate.json
# enforces it. A deliverable under any other name is not the file that was asked for.
_fd,out=tempfile.mkstemp(prefix="evidence_judge.",suffix=".json")
os.close(_fd)
judge = os.path.join(here, "pjroot", "task", "tests", "program_judge", "task_judge.py")
contract = os.path.join(here, "rubric-contract.json")
r = subprocess.run(
    [sys.executable, judge, art, "--contract", contract, "--json", out],
    capture_output=True, text=True)

if r.returncode:
    os.unlink(out)
    sys.stderr.write("required adjudication failed: "+r.stderr[-1000:])
    raise SystemExit(2)

try:
    d = json.load(open(out, encoding="utf-8"))
    fs = float(d["final_score"])
    print(_gate_json({"final_score": fs, "artifact": art, "reward": fs,
                      "program": d, "rewards": {"strict": fs, "lenient": float(d.get("rewards",{}).get("lenient",0))}}, ensure_ascii=False))
except Exception as exc:
    sys.stderr.write(f"judge rc={r.returncode} stderr={r.stderr[:400]}\n")
    print(_gate_json({"final_score": 0.0, "error": str(exc), "artifact": art, "reward": 0.0,
                      "rewards": {"strict": 0.0, "lenient": 0.0}}, ensure_ascii=False))

try: os.unlink(out)
except OSError: pass

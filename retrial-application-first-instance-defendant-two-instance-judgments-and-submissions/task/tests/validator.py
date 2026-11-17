#!/usr/bin/env python3
# Harness adapter: locate the declared deliverable, run the packaged program judge,
# apply the delivery contract, and publish strict and lenient scores.
import sys, os, json, glob, subprocess, tempfile
WS = sys.argv[1] if len(sys.argv) > 1 else "/workspace"
DELIV = 'retrial-application.md'
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
            if (_verdict["missing"] or _verdict["extra"]
                    or _ledger.get("deliverable_gate", {}).get("lenient_fail")):
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
fd,out=tempfile.mkstemp(prefix="pj_fee_",suffix=".json");os.close(fd);os.unlink(out)
judge = os.path.join(here, "pjroot", "task", "tests", "program_judge", "task_judge.py")
contract = os.path.join(here, "rubric-contract.json")
r = subprocess.run(
    [sys.executable, "-B", judge, art, "--contract", contract, "--json", out],
    capture_output=True, text=True)

LENIENT_POSITIVE_FLOOR = 0.50
def lenient_evaluation(result):
    """Binary filing-usability lens over explicit legal necessities."""
    completion = {row["id"]: float(row.get("fraction") or 0.0) for row in result.get("items", [])}
    triggered = {row["id"] for row in result.get("deduction_items", [])
                 if row.get("state") == "triggered"}
    reasoning_chain = any((
        completion.get("P05", 0) >= 0.5 and any(completion.get(key, 0) >= 0.5 for key in ("P06", "P07", "P08", "P09")),
        completion.get("P10", 0) >= 0.5 and any(completion.get(key, 0) >= 0.5 for key in ("P11", "P12", "P13")),
        completion.get("P14", 0) >= 0.5 and any(completion.get(key, 0) >= 0.5 for key in ("P15", "P16")),
    ))
    critical_free = not triggered.intersection({"D01", "D02", "D04", "D07", "D10", "D12", "D13"})
    items = {
        "substantial_positive_completion": float(result.get("positive_earned") or 0.0) > LENIENT_POSITIVE_FLOOR,
        "applicant_posture": completion.get("P02", 0) >= 0.5 and "D01" not in triggered,
        "proper_receiving_court": completion.get("P17", 0) == 1.0 and "D02" not in triggered,
        "operative_retrial_relief": completion.get("P02", 0) >= 0.5
                                    and any(completion.get(key, 0) > 0 for key in ("P03", "P04")),
        "statutory_ground": completion.get("P01", 0) >= 0.5,
        "at_least_one_closed_reasoning_chain": reasoning_chain,
        "critical_accuracy_and_boundary": critical_free,
    }
    return {"kind": "conjunction_of_filing_necessities", "items": items,
            "score": float(all(items.values()))}


if r.returncode != 0:
    sys.stderr.write("Required semantic/program judge failed; no score published\n")
    raise SystemExit(2)
try:
    d = json.load(open(out, encoding="utf-8"))
    fs = float(d["final_score"])
    lenient = lenient_evaluation(d)
    print(_gate_json({"semantic_judge":d.get("semantic_judge"),"final_score": fs, "artifact": art, "reward": fs,
                      "rewards": {"strict": fs, "lenient": lenient["score"]},
                      "lenient_evaluation": lenient}, ensure_ascii=False))
except Exception as exc:
    sys.stderr.write("Judge output invalid; no score published\n")
    raise SystemExit(2)

if os.path.exists(out):os.unlink(out)

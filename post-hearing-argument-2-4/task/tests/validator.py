#!/usr/bin/env python3
# Harbor 归一化入口:定位待评产物,调用 Program Judge 判分,再把结果取出落盘。
# 判分逻辑全部在 judge 内,本文件只做 I/O 定位与取数。
#
# program_judge/task_judge.py 在 **模块顶层** 求值
#   PACKAGE_ROOT = Path(__file__).resolve().parents[3]
# 而容器里 tests/ 挂在 /tests,/tests/program_judge/task_judge.py 只有 3 层 parents。
# 因此 judge 及它按 PACKAGE_ROOT 读取的 contract / materials 一起嵌在 tests/pjroot/ 下补足深度:
#   pjroot/task/tests/program_judge/task_judge.py
#     parents[3] = pjroot -> rubric-contract.json                         ✓
#                         -> task/environment/workspace/materials/*.txt   ✓
# judge 以 subprocess 调用,它崩溃不会连坐 validator。
#
# 用法:
#   validator.py [WORKSPACE_OR_ARTIFACT] [--report PATH] [--output PATH]
# 默认 /workspace。--report 与 --output 为同义别名。
import argparse
import glob
import json
import os
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
JUDGE = os.path.join(HERE, "pjroot", "task", "tests", "program_judge", "task_judge.py")
CONTRACT = os.path.join(HERE, "pjroot", "rubric-contract.json")

# instruction.md 指定 `/workspace/output/post_hearing_argument.docx`。
NAME = "post_hearing_argument.docx"
RELATIVE = (NAME, f"output/{NAME}", f"artifacts/{NAME}", f"artifacts/output/{NAME}")
PATTERNS = ("output/*.docx", "artifacts/output/*.docx", "artifacts/*.docx", "*.docx")


def locate(target):
    if os.path.isfile(target):
        return target
    for rel in RELATIVE:
        candidate = os.path.join(target, rel)
        if os.path.isfile(candidate) and os.path.getsize(candidate) > 0:
            return candidate
    for pattern in PATTERNS:
        hits = sorted(p for p in glob.glob(os.path.join(target, pattern))
                      if os.path.getsize(p) > 0 and not os.path.basename(p).startswith("~$"))
        if hits:
            return hits[0]
    return os.path.join(target, RELATIVE[1])


def readable_docx(path):
    if not os.path.isfile(path) or os.path.getsize(path) <= 0:
        return False, "missing deliverable"
    if not path.lower().endswith(".docx"):
        return False, "required deliverable is not a DOCX"
    try:
        with zipfile.ZipFile(path) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))
        text = "".join(node.text or "" for node in root.iter()
                       if node.tag.rsplit("}", 1)[-1] == "t").strip()
        if not text:
            return False, "empty DOCX body"
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        return False, f"unreadable DOCX: {exc}"
    return True, ""


def zero_payload(artifact, reason):
    return {
        "schema_version": "program-judge-result-v4",
        "status": "measured_candidate_failure",
        "final_score": 0.0,
        "reward": 0.0,
        "rewards": {"strict": 0.0, "lenient": 0.0},
        "artifact_path": artifact,
        "reason": reason,
        "positive_earned": 0.0,
        "penalty_instances": [],
    }


def publish(payload, destinations):
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    for destination in destinations:
        if destination:
            os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)
            with open(destination, "w", encoding="utf-8") as handle:
                handle.write(rendered)
    print(rendered, end="")


LENIENT_POSITIVE_FLOOR = 0.50
LENIENT_DAMAGE_CEILING = 2


def lenient_lens(ledger):
    """The binary lens over the settled ledger: did the submission earn most of the available credit
    and stay close to clean?"""
    positive_earned = float((ledger or {}).get("positive_earned") or 0.0)
    instances = (ledger or {}).get("penalty_instances") or (ledger or {}).get("damage_instances") or []
    return 1.0 if (positive_earned > LENIENT_POSITIVE_FLOOR
                   and len(instances) <= LENIENT_DAMAGE_CEILING) else 0.0



def apply_delivery_gate(payload, target, detail):
    """The delivery gate (deliverable_gate.json beside this file): a required deliverable missing at its
    exact path scores 0, every extra file directly under the delivery root is a capped damage instance,
    while verbatim overlap with materials is retained only as a diagnostic. The same module runs in the
    calibration host, so a rescore and the live harness agree."""
    try:
        sys.path.insert(0, HERE)
        import deliverable_gate as _dg
        config = _dg.load(HERE)
        if not config:
            return payload
        workspace = target if os.path.isdir(target) else os.path.dirname(target)
        verdict = _dg.check(workspace, config, HERE)
        judged = detail if isinstance(detail, dict) else {}
        ledger = payload.get("scoring_ledger") or {
            "schema_version": "pd-ledger-v1",
            "positive_completion": {i["id"]: float(i.get("fraction") or 0.0) for i in (judged.get("items") or [])},
            "positive_earned": float(judged.get("positive_earned") or 0.0),
            "retention": float(judged.get("retention_multiplier") if judged.get("retention_multiplier") is not None else 1.0),
            "damage_instances": [{"key": x.get("damage_instance_key"), "item_ids": sorted(x.get("item_ids") or [])}
                                 for x in (judged.get("penalty_instances") or [])],
            "final_score": float(payload.get("final_score") or 0.0)}
        _dg.settle(ledger, verdict, config)
        payload["final_score"] = ledger["final_score"]
        payload["reward"] = ledger["final_score"]
        payload.setdefault("rewards", {})["strict"] = ledger["final_score"]
        if verdict["missing"] or ledger.get("deliverable_gate", {}).get("lenient_fail"):
            payload["rewards"]["lenient"] = 0.0
        elif verdict["extra"]:
            payload["rewards"]["lenient"] = 1.0 if (ledger["positive_earned"] > 0.5
                                                    and len(ledger["damage_instances"]) <= 2) else 0.0
        payload["scoring_ledger"] = ledger
    except Exception as exc:
        sys.stderr.write(f"deliverable gate FAILED: {exc}\n")
        payload["final_score"] = 0.0
        payload["reward"] = 0.0
        payload["rewards"] = {"strict": 0.0, "lenient": 0.0}
        payload["error"] = f"deliverable gate failed: {exc}"
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target", nargs="?", default="/workspace")
    parser.add_argument("--report")
    parser.add_argument("--output")
    args = parser.parse_args()

    artifact = locate(args.target)
    readable, reason = readable_docx(artifact)
    if not readable:
        publish(zero_payload(artifact, reason), (args.report, args.output))
        return 0
    # 每次调用用独立临时目录:judge 崩溃时不写 json,若复用固定路径
    # 会把上一次调用残留的结果当成本次的分数。
    workdir = tempfile.mkdtemp(prefix="pj-")
    detail_path = os.path.join(workdir, "detail.json")
    run = subprocess.run(
        [sys.executable, "-B", JUDGE, artifact, "--contract", CONTRACT, "--json", detail_path],
        capture_output=True, text=True)
    if run.returncode != 0:
        sys.stderr.write("Required judge failed; no score published\n")
        return 2
    try:
        with open(detail_path, encoding="utf-8") as handle:
            detail = json.load(handle)
        strict = float(detail["final_score"])
    except Exception as exc:
        sys.stderr.write(f"judge rc={run.returncode} stderr={run.stderr[:600]}\n")
        return 2

    lenient = lenient_lens(detail if isinstance(detail, dict) else {})
    payload = dict(detail) if isinstance(detail, dict) else {}
    payload.update({
        "final_score": strict,
        "reward": strict,
        "rewards": {"strict": strict, "lenient": lenient},
        "artifact_path": artifact,
    })
    payload = apply_delivery_gate(payload, args.target, detail)
    publish(payload, (args.report, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

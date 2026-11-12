#!/usr/bin/env python3
"""Deterministic DOCX judge for the logistics contract litigation filing set."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from program_judge_runtime import Locator, ProgramJudge, load_contract, sha256


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
def find_contract() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "rubric-contract.json"
        if candidate.is_file():
            return candidate
    return Path(__file__).resolve().parent.parent / "rubric-contract.json"


CANONICAL_CONTRACT = find_contract()
REJECTED = re.compile(
    r"错误示例|错误做法|反面示例|仅供参考|不得采用|不应采用|未采用|备选方案|候选方案|已经驳回|已驳回|不要写|禁止写"
)
ATTRIBUTED_OR_DISPUTED = re.compile(
    r"被告.{0,12}(?:称|认为|主张|指控)|通知书.{0,8}(?:称|列明|指控)|"
    r"不予认可|不认可|否认|异议|缺乏.{0,8}依据|并非事实|"
    r"未(?:提供|提交).{0,12}证据|无.{0,12}(?:认定|处罚|证据)"
)
NEGATED_OR_UNCERTAIN = re.compile(
    r"不应.{0,24}认定|不能认定|不得认定|不构成(?:根本)?违约|"
    r"并未构成(?:根本)?违约|未构成(?:根本)?违约|无证据(?:证明|证实)|"
    r"未.{0,16}(?:证明|证实|认定).{0,20}(?:原告|乙方).{0,12}违约|"
    r"(?:若|如|假设).{0,24}(?:原告|乙方).{0,16}违约|"
    r"(?:原告|乙方).{0,16}违约.{0,16}为前提|"
    r"待核实|尚待核实|无法确认|不能确认|尚未查明|疑为|疑似|可能"
)
DATE_PATTERN = r"20\d{2}年\d{1,2}月\d{1,2}日"
AMOUNT_PATTERN = r"(?:\d{1,3}(?:,\d{3})+|\d{5,7}|十万元|壹拾万元)"
ROLE_RULES = {
    "complaint": {
        "filenames": ("civil-complaint", "complaint", "起诉状", "起䜣状"),
        "markers": ("民事起诉状", "诉讼请求", "事实与理由", "此致"),
    },
    "evidence_list": {
        "filenames": ("evidence-list", "evidence", "证据清单", "证据目录"),
        "markers": ("证据清单", "证据名称", "证明", "页数"),
    },
    "case_handoff": {
        "filenames": ("case-handoff", "handoff", "案件对接", "案件交接"),
        "markers": ("案件对接表", "签单情况", "案件情况", "案情简介"),
    },
    "service_form": {
        "filenames": ("service-address", "service", "送达地址"),
        "markers": ("送达地址", "电子送达", "代收人", "告知事项"),
    },
    "refund_form": {
        "filenames": ("refund-account", "refund", "退费账户"),
        "markers": ("退费账户", "开户银行", "银行账号", "接收退费"),
    },
}
GIVEAWAY_GATE_COEFFICIENT = 0.2


def canonical(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = text.replace("人民币", "rmb").replace("￥", "¥")
    return re.sub(r"[\s\u3000]+", "", text)


def read_docx(path: Path) -> list[dict]:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    units = []
    for index, paragraph in enumerate(root.iter(W + "p"), start=1):
        parts = []
        for node in paragraph.iter():
            if node.tag == W + "t" and node.text:
                parts.append(node.text)
            elif node.tag in {W + "br", W + "cr"}:
                parts.append("\n")
            elif node.tag == W + "tab":
                parts.append("\t")
        text = "".join(parts).strip()
        if text:
            units.append({
                "locator": f"word/document.xml/p[{index}]",
                "text": text,
                "normalized": canonical(text),
            })
    return units


def extract_raw(artifact: Path) -> dict:
    if artifact.is_file():
        files = [artifact] if artifact.suffix.lower() == ".docx" else []
        artifact_root = artifact.parent
    else:
        files = sorted(
            path for path in artifact.rglob("*.docx")
            if path.is_file() and not path.name.startswith("~$")
        ) if artifact.exists() else []
        artifact_root = artifact
    if not files:
        return {"state": "confirmed_missing", "error": "No DOCX deliverables", "documents": [], "artifact_root": artifact_root}
    if len(files) > 12:
        return {"state": "ambiguous", "error": "More than twelve DOCX files", "documents": [], "artifact_root": artifact_root}
    documents = []
    errors = []
    for path in files:
        try:
            units = read_docx(path)
            text = "\n".join(unit["text"] for unit in units)
            documents.append({"path": path, "units": units, "text": text, "normalized": canonical(text)})
        except (OSError, KeyError, ValueError, ET.ParseError, zipfile.BadZipFile) as exc:
            errors.append(f"{path.name}:{type(exc).__name__}")
    if errors:
        return {"state": "parse_failure", "error": "; ".join(errors), "documents": documents, "artifact_root": artifact_root}
    return {"state": "identified", "error": "", "documents": documents, "artifact_root": artifact_root}


def role_score(document: dict, role: str) -> int:
    rule = ROLE_RULES[role]
    name = canonical(document["path"].stem)
    text = document["normalized"]
    score = 6 if any(canonical(alias) in name for alias in rule["filenames"]) else 0
    return score + sum(2 for marker in rule["markers"] if canonical(marker) in text)


def classify_roles(raw: dict) -> tuple[dict[str, dict], dict[str, str]]:
    roles = {}
    states = {}
    candidates = {role: [] for role in ROLE_RULES}
    for document in raw["documents"]:
        scored = sorted(
            ((role_score(document, role), role) for role in ROLE_RULES),
            key=lambda pair: (-pair[0], pair[1]),
        )
        if scored[0][0] < 4 or (len(scored) > 1 and scored[0][0] == scored[1][0]):
            continue
        candidates[scored[0][1]].append((scored[0][0], document))
    for role in ROLE_RULES:
        ranked = sorted(candidates[role], key=lambda pair: (-pair[0], pair[1]["path"].as_posix()))
        if not ranked:
            states[role] = "confirmed_missing"
            continue
        if len(ranked) > 1 and ranked[0][0] == ranked[1][0]:
            states[role] = "ambiguous"
            continue
        roles[role] = ranked[0][1]
        states[role] = "identified"
    return roles, states


def windows(document: dict, maximum: int = 10) -> list[dict]:
    units = document["units"]
    normalized_units = [unit["normalized"] for unit in units if unit["normalized"]]
    if len(normalized_units) >= 8 and len(set(normalized_units)) / len(normalized_units) < 0.35:
        return []
    spans = []
    for start in range(len(units)):
        for size in range(1, min(maximum, len(units) - start) + 1):
            selected = units[start:start + size]
            raw = "\n".join(unit["text"] for unit in selected)
            normalized = canonical(raw)
            if len(normalized) > 1300:
                break
            if REJECTED.search(raw):
                continue
            if len(re.findall(r"\s+", raw)) >= 12 and len(re.findall(r"[，。；：、,.!?]", raw)) < 2:
                continue
            spans.append({
                "path": document["path"],
                "locator": selected[0]["locator"] + ".." + selected[-1]["locator"],
                "raw": raw,
                "text": normalized,
                "size": size,
            })
    return spans


def match(span: dict, check: dict) -> bool:
    if check.get("derived"):
        return False
    text = span["text"]
    if (not check.get("document_wide") and check.get("id") not in {"dispute", "ineffective"}
            and re.search(r"并未|没有|不存在|不曾|并不存在|未曾", text)):
        return False
    if any(re.search(pattern, text, re.I) for pattern in check.get("exclude", [])):
        return False
    return all(re.search(pattern, text, re.I) for pattern in check.get("all", []))


def relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def locator_pair(identity: str, span: dict, root: Path) -> list[Locator]:
    path = relative(span["path"], root)
    raw_id = identity + "-raw"
    return [
        Locator(raw_id, path, "docx", span["locator"], identity, "business_proposition", span["raw"]),
        Locator(identity + "-normalized", path, "docx", span["locator"], identity,
                "business_proposition", span["text"], evidence_origin="lossless_canonicalized",
                source_locator_ids=(raw_id,), normalization_rule_id="N01"),
    ]


def missing_locator(identity: str, raw: dict, detail: str) -> Locator:
    return Locator(identity + "-scan", ".", "directory", "recursive DOCX role scan", identity,
                   "search_result", detail or raw["error"] or "No complete adopted proposition established")


def derived_locator(identity: str, raw: dict, source_paths: list[Path], observed: str) -> list[Locator]:
    locators = []
    source_ids = []
    for index, path in enumerate(source_paths):
        source_id = f"{identity}-source-{index}"
        source_ids.append(source_id)
        locators.append(Locator(source_id, relative(path, raw["artifact_root"]), "docx", "whole-document",
                                identity, "source_document", path.name))
    locators.append(Locator(identity + "-derived", ".", "directory", "cross-document replay", identity,
                            "derived_result", observed, evidence_origin="deterministically_derived",
                            source_locator_ids=tuple(source_ids), derivation_rule_id="R01"))
    return locators


def assertion_is_excluded(text: str) -> bool:
    return bool(NEGATED_OR_UNCERTAIN.search(text) or ATTRIBUTED_OR_DISPUTED.search(text))


def normalize_amount(value: str) -> str:
    value = canonical(value).replace(",", "")
    if value in {"十万元", "壹拾万元"}:
        return "100000"
    return value


def contract_dates(document: dict) -> set[str]:
    """Extract dates explicitly bound to formation of the contract or agreement."""
    text = canonical(document["text"])
    patterns = (
        rf"(?:双方|原被告)?(?:于)?({DATE_PATTERN})(?:签订|签署|订立)(?:的)?.{{0,16}}?(?:合同|协议)",
        rf"(?:合同|协议)(?:的)?(?:签订|签署|订立)(?:日期|时间)?[:：为系是于]*({DATE_PATTERN})",
        rf"(?:合同|协议)(?:的)?(?:日期|时间)[:：为系是于]+({DATE_PATTERN})",
    )
    dates = set()
    for pattern in patterns:
        for found in re.finditer(pattern, text):
            context = text[max(0, found.start() - 20):found.end() + 20]
            if not assertion_is_excluded(context):
                dates.add(found.group(1))
    return dates


def core_claim_amounts(document: dict) -> set[str]:
    """Extract adopted damages/claim amounts, excluding incidental sums and uncertainty."""
    text = canonical(document["text"])
    patterns = (
        rf"(?:判令|请求|主张).{{0,28}}?(?:赔偿|支付).{{0,28}}?({AMOUNT_PATTERN})(?:元)?",
        rf"(?:违约金|经济损失|赔偿金额).{{0,20}}?({AMOUNT_PATTERN})(?:元)?",
        rf"({AMOUNT_PATTERN})(?:元)?.{{0,20}}?(?:违约金|经济损失|赔偿金额)",
    )
    amounts = set()
    for pattern in patterns:
        for found in re.finditer(pattern, text):
            context = text[max(0, found.start() - 24):found.end() + 24]
            if not assertion_is_excluded(context):
                amounts.add(normalize_amount(found.group(1)))
    return amounts


def core_values(document: dict) -> dict[str, set[str]]:
    return {
        "dates": contract_dates(document),
        "amounts": core_claim_amounts(document),
    }


def section_text(document: dict, heading: str | tuple[str, ...], next_heading: str | tuple[str, ...]) -> str:
    units = document["units"]
    headings = (heading,) if isinstance(heading, str) else heading
    next_headings = (next_heading,) if isinstance(next_heading, str) else next_heading
    start = next((index for index, unit in enumerate(units)
                  if any(value in unit["normalized"] for value in headings)), None)
    if start is None:
        return ""
    end = next(
        (index for index in range(start + 1, len(units))
         if any(value in units[index]["normalized"] for value in next_headings)),
        len(units),
    )
    return canonical("\n".join(unit["text"] for unit in units[start:end]))


def complaint_must_do_units(roles: dict) -> dict[str, bool]:
    """Required filing units that every frozen rollout already supplies.

    These are a completeness gate rather than positive-credit items: deleting either
    section makes the complaint unusable, while retaining it does not earn extra score.
    """
    complaint = roles.get("complaint")
    if complaint is None:
        return {
            "complaint_prayer_section": False,
            "complaint_facts_section": False,
        }
    prayer = section_text(
        complaint,
        ("诉讼请求", "请求事项", "诉请", "请求法院"),
        ("事实与理由", "事实及理由", "事实理由", "事实依据"),
    )
    facts = section_text(
        complaint,
        ("事实与理由", "事实及理由", "事实理由", "事实依据"),
        ("此致", "证据和证据来源", "附项", "具状人"),
    )
    full_text = canonical(complaint["text"])
    prayer_source = prayer or full_text
    facts_source = facts or full_text
    return {
        "complaint_prayer_section": bool(
            re.search(r"判令|诉请|请求(?:法院)?", prayer_source)
            and re.search(r"继续履行|恢复履行|返还.{0,18}经营权|解除.{0,18}合同|赔偿|违约金", prayer_source)
        ),
        "complaint_facts_section": bool(
            re.search(r"2025年10月16日", facts_source)
            and re.search(r"合同|协议", facts_source)
            and re.search(r"违约通知|收回.{0,18}经营权|第三方.{0,18}经营", facts_source)
        ),
    }


def evidence_inventory_checks(document: dict) -> tuple[bool, bool]:
    text = canonical(document["text"])
    expected = (
        r"物流.{0,12}(?:合同|协议)",
        r"违约通知书",
        r"聊天记录",
        r"异议.{0,12}回函|维权函",
    )
    unprovided = re.compile(
        r"身份证|工商登记|企业信用|车辆维护费|燃油费|员工工资|第三方入驻|"
        r"现场照片|现场视频|通话录音|证据保全公证"
    )
    complete = all(re.search(pattern, text) for pattern in expected)
    status_markers = re.compile(
        r"未提供|尚未提供|尚未取得|待补|拟补|需补|待收集|拟收集|需收集|"
        r"待核|拟核|如有|可能取得|不作为现有|并非现有|未列入本次提交"
    )
    unbounded = []
    for unit in document["units"]:
        context = canonical(unit["text"])
        for found in unprovided.finditer(context):
            if not status_markers.search(context) and not assertion_is_excluded(context):
                unbounded.append(found.group(0))
    return complete, not unbounded


def has_cross_document_conflict(values: list[dict], key: str) -> bool:
    adopted = [value[key] for value in values if value[key]]
    return len(adopted) >= 2 and any(left != right for index, left in enumerate(adopted) for right in adopted[index + 1:])


def derived_checks(raw: dict, roles: dict) -> dict[str, tuple[bool, str, list[Path]]]:
    role_paths = [document["path"] for document in roles.values()]
    party_documents = [roles[role] for role in ("complaint", "case_handoff", "service_form", "refund_form") if role in roles]
    key_roles = [roles[role] for role in ("complaint", "case_handoff") if role in roles]
    evidence_complete, evidence_bounded = evidence_inventory_checks(roles["evidence_list"]) if "evidence_list" in roles else (False, False)
    return {
        "five_roles": (len(roles) == 5, f"identified roles={sorted(roles)}", role_paths),
        "party_consistency": (
            len(party_documents) == 4 and all("易泽杰" in document["normalized"] and "黄南隆" in document["normalized"] for document in party_documents),
            "both plaintiff names present across party-bearing deliverables", [document["path"] for document in party_documents],
        ),
        "date_consistency": (
            len(key_roles) == 2 and all("2025年10月16日" in document["normalized"] for document in key_roles),
            "contract date replayed in complaint and handoff", [document["path"] for document in key_roles],
        ),
        "amount_consistency": (
            len(key_roles) == 2 and all(re.search(r"100000|100,000|十万元|壹拾万元", document["normalized"]) for document in key_roles),
            "RMB 100,000 replayed in complaint and handoff", [document["path"] for document in key_roles],
        ),
        "complete_evidence_inventory": (
            evidence_complete,
            "evidence list includes the four supplied source groups",
            [roles["evidence_list"]["path"]] if "evidence_list" in roles else [],
        ),
        "bounded_evidence_inventory": (
            evidence_bounded,
            "evidence list excludes unprovided future evidence",
            [roles["evidence_list"]["path"]] if "evidence_list" in roles else [],
        ),
    }


def find_positive_hits(item: dict, raw: dict, roles: dict, span_cache: dict, derived: dict) -> list[tuple[dict, list[Locator]]]:
    results = []
    role = item["role"]
    spans = [span for values in span_cache.values() for span in values] if role == "all" else span_cache.get(role, [])
    for check in item["checks"]:
        if check.get("derived"):
            ok, observed, paths = derived[check["derived"]]
            if ok and paths:
                results.append((check, derived_locator(f"{item['id']}-{check['id']}", raw, paths, observed)))
            continue
        if check.get("document_wide") and role in roles:
            document = roles[role]
            whole = {"path": document["path"], "locator": "whole-document",
                     "raw": document["text"], "text": canonical(document["text"])}
            if match(whole, check):
                results.append((check, locator_pair(f"{item['id']}-{check['id']}", whole, raw["artifact_root"])))
            continue
        found = next((span for span in spans if match(span, check)), None)
        if found:
            results.append((check, locator_pair(f"{item['id']}-{check['id']}", found, raw["artifact_root"])))
    return results


def find_deduction(item: dict, raw: dict, roles: dict) -> tuple[list[Locator], str] | None:
    docs = list(roles.values()) if item["role"] == "all" else ([roles[item["role"]]] if item["role"] in roles else [])
    texts = [(document, canonical(document["text"])) for document in docs]
    for rule in item["rules"]:
        kind = rule["kind"]
        if kind == "wrong_core_anchor":
            for document, text in texts:
                values = core_values(document)
                wrong_dates = {value for value in values["dates"] if value != "2025年10月16日"}
                wrong_amounts = {value for value in values["amounts"] if value != "100000"}
                if wrong_dates or wrong_amounts:
                    span = {"path": document["path"], "locator": "whole-document", "raw": document["text"], "text": text}
                    detail = f"wrong contract dates={sorted(wrong_dates)} claim amounts={sorted(wrong_amounts)}"
                    return locator_pair(item["id"] + "-wrong-anchor", span, raw["artifact_root"]), detail
        elif kind == "reversed_actor":
            for document, _ in texts:
                for span in windows(document, 4):
                    clauses = re.split(r"[。；;]", span["text"])
                    reversed_clause = next((clause for clause in clauses if re.search(
                        r"原告(?:一|二|方)?(?:的行为)?(?:构成|存在|属于).{0,12}(?:根本)?违约|"
                        r"原告(?:一|二|方)?.{0,18}应当承担.{0,10}违约责任", clause
                    )), None)
                    if reversed_clause and not assertion_is_excluded(reversed_clause) and not ATTRIBUTED_OR_DISPUTED.search(span["raw"]):
                        return locator_pair(item["id"] + "-reversal", span, raw["artifact_root"]), "plaintiff breach adopted as operative conclusion"
        elif kind == "unqualified_notice_allegation":
            for document, _ in texts:
                for span in windows(document, 4):
                    if (re.search(r"原告|乙方", span["text"])
                            and re.search(r"个人账户.{0,20}(违法|偷税|逃税)|偷逃税|恶意加价", span["text"])
                            and not assertion_is_excluded(span["text"])):
                        return locator_pair(item["id"] + "-allegation", span, raw["artifact_root"]), "adverse allegation adopted without attribution"
        elif kind == "invented_case_number":
            for document, text in texts:
                found = re.search(r"[（(]?2026[）)]?桂\d{1,6}民(?:初|终|再)?\d{1,8}号", text)
                if found:
                    span = {"path": document["path"], "locator": "whole-document", "raw": found.group(0), "text": found.group(0)}
                    return locator_pair(item["id"] + "-case-number", span, raw["artifact_root"]), "unsupported completed court case number"
        elif kind == "invented_bank_account":
            for document, text in texts:
                found = re.search(r"(?:银行账号|银行卡号|账户)[:：]?\d{12,24}", text)
                if found:
                    span = {"path": document["path"], "locator": "whole-document", "raw": found.group(0), "text": found.group(0)}
                    return locator_pair(item["id"] + "-bank", span, raw["artifact_root"]), "unsupported completed refund bank account"
        elif kind == "cross_document_contradiction":
            values = [core_values(document) for document in docs]
            dates = set().union(*(value["dates"] for value in values)) if values else set()
            amounts = set().union(*(value["amounts"] for value in values)) if values else set()
            if has_cross_document_conflict(values, "dates") or has_cross_document_conflict(values, "amounts"):
                locators = derived_locator(item["id"] + "-conflict", raw, [document["path"] for document in docs], f"dates={sorted(dates)} amounts={sorted(amounts)}")
                return locators, "conflicting adopted core values across deliverables"
        elif kind == "source_dump_or_shape":
            if raw["documents"] and not roles:
                document = raw["documents"][0]
                span = {"path": document["path"], "locator": "whole-document", "raw": document["text"], "text": document["normalized"]}
                return locator_pair(item["id"] + "-dump", span, raw["artifact_root"]), "DOCX files contain no identifiable requested filing"
            for document, text in texts:
                keywords = len(re.findall(r"原告|被告|合同|违约|证据|请求|经营权", text))
                punctuation = len(re.findall(r"[，。；：、,.!?]", document["text"]))
                units = [unit["normalized"] for unit in document["units"] if unit["normalized"]]
                repetitive = len(units) >= 8 and len(set(units)) / len(units) < 0.35
                if len(text) > 12000 or repetitive or (len(text) < 180 and keywords >= 12 and punctuation < 3):
                    span = {"path": document["path"], "locator": "whole-document", "raw": document["text"], "text": text}
                    return locator_pair(item["id"] + "-shape", span, raw["artifact_root"]), "grossly mismatched or keyword-spray filing shape"
        elif kind == "unliquidated_monetary_prayer":
            for document, _ in texts:
                request = section_text(document, "诉讼请求", "事实与理由")
                blank_amount = re.search(
                    r"(?:实际损失|可得利益|承包费).{0,40}(?:＿＿|_{3,}|【.{0,12}】|\[.{0,12}\]|待核|待填|金额待)|"
                    r"(?:＿＿|_{3,}|【.{0,12}】|\[.{0,12}\]|待核|待填|金额待).{0,40}(?:实际损失|可得利益|承包费)",
                    request,
                )
                if blank_amount:
                    span = {"path": document["path"], "locator": "complaint/request-section", "raw": request, "text": request}
                    return locator_pair(item["id"] + "-blank-amount", span, raw["artifact_root"]), "formal monetary prayer contains an unresolved amount blank"
    return None


def evaluate(raw: dict, judge: ProgramJudge) -> dict:
    roles, role_states = classify_roles(raw)
    span_cache = {role: windows(document) for role, document in roles.items()}
    derived = derived_checks(raw, roles)
    must_do_units = complaint_must_do_units(roles)

    for item in judge.positives.values():
        hits = find_positive_hits(item, raw, roles, span_cache, derived)
        if hits:
            evidence = [locator for _, locators in hits for locator in locators]
            observation = judge.observe(item["id"], "identified", evidence)
            fraction = len(hits) / len(item["checks"])
            comparison = "equivalent" if fraction == 1 else "partial"
        else:
            state = raw["state"] if raw["state"] in {"parse_failure", "ambiguous"} else "confirmed_missing"
            observation = judge.observe(item["id"], state, [missing_locator(item["id"], raw, f"role={item['role']} state={role_states.get(item['role'], state)}")])
            fraction = 0.0
            comparison = "missing"
        judge.positive(item["id"], fraction, observation,
                       f"{len(hits)}/{len(item['checks'])} complete proposition components", comparison)

    for item in judge.deductions.values():
        found = find_deduction(item, raw, roles)
        if found:
            locators, reason = found
            observation = judge.observe(item["id"], "identified", locators)
            occurrence = {
                "observation_id": observation,
                "causal_root_id": item["damage_key"],
                "damage_instance_key": "litigation:" + item["damage_key"],
                "manifestation_id": item["id"] + ":" + locators[-1].container_path,
                "reason": reason,
            }
            judge.deduction(item["id"], "triggered", [observation], reason, [occurrence])
        else:
            state = "parse_failure" if raw["state"] == "parse_failure" else "not_triggered"
            observation_state = "parse_failure" if raw["state"] == "parse_failure" else "confirmed_missing"
            observation = judge.observe(item["id"], observation_state, [missing_locator(item["id"], raw, "No complete adopted error proposition established")])
            judge.deduction(item["id"], state, [observation], "No affirmative adopted error established; ordinary omissions and unresolved fields excluded")

    result = judge.finish()
    missing_must_do = [name for name, present in must_do_units.items() if not present]
    gate_multiplier = round(GIVEAWAY_GATE_COEFFICIENT ** len(missing_must_do), 9)
    if missing_must_do:
        result["retention_multiplier"] = round(result["retention_multiplier"] * gate_multiplier, 9)
        result["penalty_rate"] = round(1.0 - result["retention_multiplier"], 9)
        result["final_score"] = round(result["positive_earned"] * result["retention_multiplier"], 9)
    result["giveaway_unit_gate"] = {
        "coefficient_per_missing_unit": GIVEAWAY_GATE_COEFFICIENT,
        "units": must_do_units,
        "missing": missing_must_do,
        "multiplier": gate_multiplier,
    }
    result["document_roles"] = {role: relative(document["path"], raw["artifact_root"]) for role, document in roles.items()}
    result["role_states"] = role_states
    result["extraction_status"] = {"state": raw["state"], "detail": raw["error"]}
    # Strict is the published additive-positive score after explicit damage
    # instances.  Keep this value unchanged so partial credit remains
    # proportional and no hidden nonlinear cap or floor changes task difficulty.
    result["base_strict_score"] = float(result["final_score"])
    result["reward"] = result["reward_strict"] = result["final_score"]
    completion = {item["id"]: float(item["fraction"]) for item in result["items"]}
    critical_damage_free = all(
        item["state"] == "not_triggered" for item in result["deduction_items"]
    )
    lenient_items = {
        "five_requested_filings": len(roles) == 5,
        "complaint_substance": all(must_do_units.values()),
        "supplied_evidence_complete": completion["P14"] == 1.0,
        "evidence_status_bounded": completion["P15"] == 1.0,
        "refund_fields_bounded": completion["P16"] == 1.0,
        "relief_route_coherent": completion["P02"] == 1.0,
        "no_adopted_critical_damage": critical_damage_free,
    }
    result["lenient_evaluation"] = {
        "kind": "conjunction_of_declared_binary_business_items",
        "items": lenient_items,
        "score": float(all(lenient_items.values())),
    }
    result["reward_lenient"] = result["lenient_evaluation"]["score"]
    result["rewards"] = {"strict": result["reward_strict"], "lenient": result["reward_lenient"]}
    return result


def score_path(artifact: Path, contract_path: Path = CANONICAL_CONTRACT) -> dict:
    artifact = artifact.resolve()
    raw = extract_raw(artifact)
    root = raw["artifact_root"].resolve()
    judge = ProgramJudge(load_contract(contract_path), artifact, sha256(contract_path), artifact_root=root)
    return evaluate(raw, judge)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--contract", type=Path, default=CANONICAL_CONTRACT)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = score_path(args.artifact, args.contract.resolve())
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

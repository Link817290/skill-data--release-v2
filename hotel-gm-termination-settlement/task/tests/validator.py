#!/usr/bin/env python3
"""Condition-blind scorer for the hotel GM termination settlement workbook."""

from __future__ import annotations

import json
import posixpath
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import BadZipFile, ZipFile


NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
GROUP_MAX = {
    "core_results": 85,
    "judgment_status": 10,
    "auditable_delivery": 5,
}
STRICT_FORMULA = "strict = awarded rubric points / 100; privacy violation forces 0"
LENIENT_FORMULA = (
    "lenient = 1 if every settlement owner has a source-bound adopted conclusion "
    "with its required deterministic amount/chain, the workbook cites at least "
    "seven source materials and a calculation method, and confirmed, conditional, "
    "unknown and continuing obligations are separated; "
    "privacy violation forces 0"
)
def extract_rows(path: Path) -> list[str]:
    rows: list[str] = []
    with ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            tree = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in tree.findall("m:si", NS):
                shared.append(
                    "".join(
                        node.text or ""
                        for node in item.iter(f"{{{NS['m']}}}t")
                    )
                )

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(
            archive.read("xl/_rels/workbook.xml.rels")
        )
        targets = {
            item.attrib["Id"]: item.attrib["Target"]
            for item in relationships
        }
        for sheet_ref in workbook.find("m:sheets", NS) or []:
            sheet_name = sheet_ref.attrib.get("name", "")
            relation_id = sheet_ref.attrib[f"{{{NS['r']}}}id"]
            target = targets[relation_id]
            member = (
                posixpath.normpath(target.lstrip("/"))
                if target.startswith(("/", "xl/"))
                else posixpath.normpath(posixpath.join("xl", target))
            )
            sheet = ET.fromstring(archive.read(member))
            for row in sheet.findall(".//m:sheetData/m:row", NS):
                values: list[str] = []
                for cell in row.findall("m:c", NS):
                    cell_type = cell.attrib.get("t")
                    value = cell.find("m:v", NS)
                    formula = cell.find("m:f", NS)
                    if cell_type == "inlineStr":
                        rendered = "".join(
                            node.text or ""
                            for node in cell.findall(".//m:t", NS)
                        )
                    elif (
                        cell_type == "s"
                        and value is not None
                        and (value.text or "").isdigit()
                    ):
                        rendered = shared[int(value.text)]
                    else:
                        rendered = "" if value is None else (value.text or "")
                    if formula is not None:
                        rendered = f"{formula.text or ''}={rendered}"
                    values.append(rendered)
                if any(values):
                    rows.append(sheet_name + "\t" + "\t".join(values))
    return rows


def empty_result(error: str) -> dict:
    return {
        "reward": 0.0,
        "rewards": {"strict": 0.0, "lenient": 0.0},
        "reward_formulas": {
            "strict": STRICT_FORMULA,
            "lenient": LENIENT_FORMULA,
        },
        "dimension_scores": {group: 0.0 for group in GROUP_MAX},
        "details": {"score_points": 0, "max_points": 100, "error": error},
    }


def score(path: Path) -> dict:
    if not path.is_file():
        return empty_result(f"missing deliverable: {path}")
    try:
        rows = extract_rows(path)
    except (BadZipFile, OSError, ET.ParseError, KeyError, IndexError) as exc:
        return empty_result(f"invalid xlsx: {exc}")

    def norm(value: str) -> str:
        return re.sub(r"[\s,，]", "", value or "").lower()

    all_text = "\n".join(rows)
    normalized = norm(all_text)
    from semantic_judge import adjudicate
    semantic=adjudicate(all_text,(Path(__file__).parent/"semantic_source.json").read_text())
    from workbook_consistency import audit
    consistency=audit(path)

    def any_term(*terms: str) -> bool:
        return any(norm(term) in normalized for term in terms)

    def number_in(text: str, expected: float, tolerance: float = 0.11) -> bool:
        numeric_text = re.sub(r"[,，]", "", text or "")
        for raw in re.findall(r"-?\d+(?:\.\d+)?", numeric_text):
            try:
                value = float(raw)
            except ValueError:
                continue
            if abs(value - expected) <= tolerance:
                return True
        return False

    checks: dict[str, dict] = {}
    group_awarded = {group: 0 for group in GROUP_MAX}

    def add(group: str, name: str, points: int, ok: bool) -> None:
        checks[name] = {"group": group, "points": points, "ok": bool(ok)}
        if ok:
            group_awarded[group] += points

    economic_calculation = semantic["items"]["SEVERANCE_CALCULATION"]
    economic_semantic = semantic["items"]["SEVERANCE_CONDITIONAL_ADOPTION"]
    economic_conditional = economic_semantic["fraction"] == 1
    severance_conversion = any(
        number_in(row, 48470.25, 0.12)
        or (
            number_in(row, 193881)
            and number_in(row, 12, 0.01)
            and number_in(row, 3, 0.01)
            and ("÷" in row or "/" in row)
            and ("×" in row or "*" in row)
        )
        for row in economic_calculation["quotes"]
    )
    add(
        "core_results",
        "经济补偿年值与换算",
        2,
        economic_calculation["fraction"] == 1
        and any(number_in(row, 193881) for row in economic_calculation["quotes"])
        and severance_conversion
        and any(number_in(row, 363526.88, 0.12) for row in economic_calculation["quotes"]),
    )
    add(
        "core_results",
        "经济补偿N与公式",
        2,
        economic_calculation["fraction"] == 1
        and any(number_in(row, 7.5, 0.01) for row in economic_calculation["quotes"])
        and any(number_in(row, 363526.88, 0.12) for row in economic_calculation["quotes"]),
    )
    add(
        "core_results",
        "经济补偿时点及参数隔离",
        4,
        economic_conditional,
    )

    annual_days = semantic["items"]["ANNUAL_LEAVE_DAYS_ADOPTION"]
    annual_amount = semantic["items"]["ANNUAL_LEAVE_AMOUNT_ADOPTION"]
    annual_base = semantic["items"]["ANNUAL_LEAVE_BASE_PROPAGATION"]
    annual_adopted_10 = annual_days["fraction"] == 1
    annual_correct_amounts = (
        annual_amount["fraction"] == 1
        and any(number_in(row, 58992.34, 0.12) for row in annual_amount["quotes"])
        and any(number_in(row, 59574.71, 0.12) for row in annual_amount["quotes"])
    )
    annual_split = annual_adopted_10
    add(
        "core_results",
        "年假采用值与分年折算",
        6,
        annual_adopted_10 and annual_split,
    )
    add(
        "core_results",
        "年假低值",
        5,
        annual_amount["fraction"] == 1
        and annual_correct_amounts
        and any(number_in(row, 58992.34, 0.12) for row in annual_amount["quotes"]),
    )
    add(
        "core_results",
        "年假高值",
        3,
        annual_amount["fraction"] == 1
        and annual_correct_amounts
        and any(number_in(row, 59574.71, 0.12) for row in annual_amount["quotes"]),
    )
    add(
        "core_results",
        "年假基数及绩效传导",
        4,
        annual_base["fraction"] == 1
        and any(
            all(norm(term) in norm(row) for term in ("772650", "3800", "11400", "6600"))
            for row in annual_base["quotes"]
        ),
    )

    add(
        "core_results",
        "2025Q4绩效",
        2,
        semantic["items"]["Q4_2025_PERFORMANCE_ADOPTION"]["fraction"] == 1
        and any(number_in(row, 53200) for row in semantic["items"]["Q4_2025_PERFORMANCE_ADOPTION"]["quotes"]),
    )
    add(
        "core_results",
        "2026Q1绩效",
        3,
        semantic["items"]["Q1_2026_PERFORMANCE_ADOPTION"]["fraction"] == 1
        and any(number_in(row, 53200) for row in semantic["items"]["Q1_2026_PERFORMANCE_ADOPTION"]["quotes"]),
    )

    history_adopted = semantic["items"]["HISTORY_PERFORMANCE_ADOPTION"]
    history_low = history_adopted["fraction"] == 1 and any(
        number_in(row, 3800) for row in history_adopted["quotes"])
    history_high = history_adopted["fraction"] == 1 and any(
        number_in(row, 11400) for row in history_adopted["quotes"])
    history_chain = any(
        all(norm(term) in norm(row) for term in ("96", "1.2", "1.3", "1.5"))
        for row in history_adopted["quotes"]
    )
    add("core_results", "历史绩效最低补差", 4, history_low)
    add("core_results", "历史绩效最高补差", 4, history_high)
    add(
        "core_results",
        "历史绩效完整区间链",
        7,
        history_low and history_high and history_chain,
    )

    march_adopted = semantic["items"]["MARCH_SALARY_ADOPTION"]
    add("core_results", "3月工资", 1,
        march_adopted["fraction"] == 1
        and any(number_in(row, 46500) for row in march_adopted["quotes"]))
    add(
        "core_results",
        "虚拟股权",
        2,
        semantic["items"]["PHANTOM_EQUITY_ADOPTION"]["fraction"] == 1
        and any(number_in(row, 24600) for row in semantic["items"]["PHANTOM_EQUITY_ADOPTION"]["quotes"]),
    )

    noncompete_low = semantic["items"]["NONCOMPETE_LOW"]["fraction"]==1 and any(number_in(q,19411.25,.12) for q in semantic["items"]["NONCOMPETE_LOW"]["quotes"])
    noncompete_high = semantic["items"]["NONCOMPETE_HIGH"]["fraction"]==1 and any(number_in(q,19601.25,.12) for q in semantic["items"]["NONCOMPETE_HIGH"]["quotes"])
    noncompete_quotes = (
        semantic["items"]["NONCOMPETE_LOW"]["quotes"]
        + semantic["items"]["NONCOMPETE_HIGH"]["quotes"])
    noncompete_chain = any(
        all(norm(term) in norm(row) for term in ("772650", "3800", "11400", "30"))
        for row in noncompete_quotes
    )
    noncompete_separate = semantic["items"]["NONCOMPETE_SEPARATION"]["fraction"] == 1
    add("core_results", "竞业月标准低值", 5, noncompete_low)
    add("core_results", "竞业月标准高值", 5, noncompete_high)
    add(
        "core_results",
        "竞业基数及绩效传导",
        5,
        noncompete_low and noncompete_high and noncompete_chain,
    )
    add(
        "core_results",
        "竞业按月且不进一次性",
        3,
        noncompete_separate,
    )

    add(
        "core_results",
        "加班结论",
        1,
        semantic["items"]["OVERTIME"]["fraction"]==1,
    )

    totals_semantic = semantic["items"]["TOTALS_ADOPTION"]
    definite_rows = totals_semantic["quotes"] if totals_semantic["fraction"] == 1 else []
    reserve_rows = definite_rows
    definite_low = any(
        number_in(row, 240292.34, 0.12) for row in definite_rows
    )
    definite_high = any(
        number_in(row, 248474.71, 0.12) for row in definite_rows
    )
    reserve_low = any(
        number_in(row, 603819.21, 0.12) for row in reserve_rows
    )
    reserve_high = any(
        number_in(row, 612001.59, 0.12) for row in reserve_rows
    )
    add("core_results", "确定应付低值", 4, definite_low)
    add("core_results", "确定应付高值", 3, definite_high)
    add("core_results", "后见情景备付低值", 4, reserve_low)
    add("core_results", "后见情景备付高值", 4, reserve_high)
    add(
        "core_results",
        "持续竞业与一次性分离",
        2,
        noncompete_separate,
    )

    add(
        "judgment_status",
        "制度参数隔离",
        4,
        semantic["items"]["POLICY_PARAMETER_ISOLATION"]["fraction"] == 1,
    )
    add(
        "judgment_status",
        "收入性质与规则层级",
        4,
        semantic["items"]["INCOME_RULE_HIERARCHY"]["fraction"] == 1,
    )
    add(
        "judgment_status",
        "支付状态与防重复",
        1,
        semantic["items"]["PAYMENT_STATUS_FIDELITY"]["fraction"] == 1,
    )
    add(
        "judgment_status",
        "条件与持续义务",
        1,
        semantic["items"]["CONDITIONAL_OBLIGATION_SEPARATION"]["fraction"] == 1,
    )

    source_hits = sum(
        1
        for token in ("02", "05", "06", "08", "09", "10", "14", "15", "16", "17", "18")
        if any_term(
            "材料" + token,
            token + "p",
            token + "表",
            token + "第",
            token + " ",
        )
    )
    add(
        "auditable_delivery",
        "正确结果的依据与公式",
        1,
        source_hits >= 7 and any_term("公式", "×", "÷", "int(", "计算"),
    )
    add(
        "auditable_delivery",
        "跨表内部一致性",
        2,
        consistency["consistent"],
    )
    privacy_bad = bool(
        re.search(
            r"林某|陈志强|王曼|李文博|赵雨薇|"
            r"(?<![\d.])\d{17}[0-9Xx](?![\d.])|(?<![\d.])1[3-9]\d{9}(?![\d.])",
            all_text,
        )
    )
    add("auditable_delivery", "文件可读与隐私", 2, not privacy_bad)

    awarded = sum(group_awarded.values())
    if privacy_bad:
        awarded = 0
        dimension_scores = {group: 0.0 for group in GROUP_MAX}
    else:
        dimension_scores = {
            group: round(group_awarded[group] / maximum, 6)
            for group, maximum in GROUP_MAX.items()
        }
    strict = round(max(0, min(100, awarded)) / 100, 6)
    lenient_items = {
        "经济补偿": economic_conditional
        and checks["经济补偿年值与换算"]["ok"]
        and checks["经济补偿N与公式"]["ok"],
        "未休年休假": annual_adopted_10 and annual_correct_amounts,
        "2025Q4绩效": checks["2025Q4绩效"]["ok"],
        "2026Q1绩效": checks["2026Q1绩效"]["ok"],
        "历史绩效补差": history_low and history_high and history_chain,
        "离职当月工资": checks["3月工资"]["ok"],
        "虚拟股权": checks["虚拟股权"]["ok"],
        "竞业限制": noncompete_low and noncompete_high and noncompete_separate,
        "加班": checks["加班结论"]["ok"],
        "跨项目汇总": definite_low and definite_high and reserve_low and reserve_high,
    }
    source_and_method = checks["正确结果的依据与公式"]["ok"]
    obligations_separated = (
        semantic["items"]["CONDITIONAL_OBLIGATION_SEPARATION"]["fraction"] == 1
        and noncompete_separate
    )
    lenient_detail = {
        "items": {name: {"ok": ok} for name, ok in lenient_items.items()},
        "source_and_method": source_and_method,
        "obligations_separated": obligations_separated,
        "incomplete_items": sorted(name for name, ok in lenient_items.items() if not ok),
    }
    lenient = float(
        all(lenient_items.values())
        and source_and_method
        and obligations_separated
    )
    if privacy_bad:
        lenient = 0.0
    return {
        "semantic_judge": semantic,
        "internal_consistency": consistency,
        "reward": strict,
        "rewards": {"strict": strict, "lenient": lenient},
        "reward_formulas": {
            "strict": STRICT_FORMULA,
            "lenient": LENIENT_FORMULA,
        },
        "dimension_scores": dimension_scores,
        "details": {
            "score_points": awarded,
            "max_points": 100,
            "lenient_detail": lenient_detail,
            "group_points": {
                group: {
                    "awarded": 0 if privacy_bad else group_awarded[group],
                    "maximum": maximum,
                }
                for group, maximum in GROUP_MAX.items()
            },
            "checks": checks,
            "privacy_violation": privacy_bad,
            "file": str(path),
        },
    }


def main() -> int:
    submission = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path("/workspace/output/赔付清单.xlsx")
    )
    try:result=score(submission)
    except Exception as exc:
        sys.stderr.write("evaluator failed: "+type(exc).__name__+"\n");return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

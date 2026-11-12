#!/usr/bin/env python3
"""Executable adversarial probes for the rubric v3.4 mechanical scorer."""

from __future__ import annotations

import json
import html
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import package_score as scorer


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[1]
GOLDEN = PACKAGE / "golden" / "标准产出"
if not GOLDEN.is_dir():
    GOLDEN = PACKAGE / "golden"
SCORER = HERE / "package_score.py"
NOTICE, SCHEDULE, DIRECTORY, COMMITMENT = scorer.REQUIRED


def rtf_bytes(text: str, table: bool = False) -> bytes:
    def enc(char: str) -> str:
        if char in "\\{}": return "\\" + char
        if 32 <= ord(char) <= 126: return char
        units = char.encode("utf-16le")
        return "".join(f"\\u{(v - 65536 if v >= 32768 else v)}?" for v in
                       (int.from_bytes(units[i:i + 2], "little") for i in range(0, len(units), 2)))
    lines = text.splitlines()
    if table:
        body = "".join("\\trowd\\cellx9000 " + "".join(map(enc, line)) + "\\cell\\row\n" for line in lines)
    else: body = "\\par\n".join("".join(map(enc, line)) for line in lines)
    return ("{\\rtf1\\ansi\\ansicpg936\\uc1\n" + body + "\n}").encode("ascii")


def write_notice(folder: Path, text: str, table: bool = False) -> None:
    (folder / NOTICE).write_bytes(rtf_bytes(text, table))


def write_docx(path: Path, text: str) -> None:
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    document = ('<?xml version="1.0" encoding="UTF-8"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                f'<w:body><w:p><w:r><w:t>{escaped}</w:t></w:r></w:p></w:body></w:document>')
    types = ('<?xml version="1.0" encoding="UTF-8"?>'
             '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
             '</Types>')
    with ZipFile(path, "w", ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", types); z.writestr("word/document.xml", document)


def write_xlsx(path: Path, cells: dict[str, str]) -> None:
    rows: dict[int, list[tuple[str, str]]] = {}
    for ref, value in cells.items():
        row = int("".join(x for x in ref if x.isdigit())); rows.setdefault(row, []).append((ref, value))
    row_xml = []
    for row, values in sorted(rows.items()):
        cell_xml = "".join(f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>' for ref, value in values)
        row_xml.append(f'<row r="{row}">{cell_xml}</row>')
    sheet = ('<?xml version="1.0" encoding="UTF-8"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
             + "".join(row_xml) + '</sheetData></worksheet>')
    types = ('<?xml version="1.0" encoding="UTF-8"?>'
             '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/xml"/></Types>')
    with ZipFile(path, "w", ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", types); z.writestr("xl/worksheets/sheet1.xml", sheet)


def replace_zip_text(path: Path, old: str, new: str) -> None:
    with ZipFile(path) as src: members = [(item, src.read(item.filename)) for item in src.infolist()]
    temp = path.with_suffix(path.suffix + ".tmp")
    with ZipFile(temp, "w") as dst:
        for item, raw in members:
            if item.filename.endswith(".xml"):
                raw = raw.replace(old.encode(), new.encode())
                old_xml = html.escape(old).replace("\n", "&#10;").encode()
                new_xml = html.escape(new).replace("\n", "&#10;").encode()
                raw = raw.replace(old_xml, new_xml)
            dst.writestr(item, raw)
    temp.replace(path)


def run(folder: Path) -> dict:
    # Call the same public scoring entry used by the CLI.  Direct invocation
    # keeps the immutable directory workbook parse cached across probes.
    return scorer.evaluate(folder)


def check(value: bool, name: str, detail: str) -> None:
    if not value: raise AssertionError(f"{name}: {detail}")


def dsum(result: dict, did: str) -> float:
    return round(next(x["deducted"] for x in result["deduction_items"] if x["id"] == did), 6)


def pval(result: dict, pid: str) -> float:
    return next(x["earned"] for x in result["positive_items"] if x["id"] == pid)


def fresh(path: Path) -> None: shutil.copytree(GOLDEN, path)


def main() -> int:
    records = []
    def probe(name: str, mutation=None) -> dict:
        with tempfile.TemporaryDirectory(prefix="rubric_v33_probe_") as raw:
            folder = Path(raw) / "output"; fresh(folder)
            if mutation: mutation(folder)
            result = run(folder)
            records.append({"name": name, "positive": result["positive_earned"], "deductions": result["deduplicated_deductions"],
                            "raw": result["raw"], "final": result["final"], "triggered": [x["id"] for x in result["deduction_items"] if x["triggered"]],
                            "unresolved_count": len(result["unresolved_semantic_candidates"])})
            check([x["id"] for x in result["positive_items"]] == list(scorer.P_WEIGHTS), name, "positive ledger identity drift")
            check([x["id"] for x in result["deduction_items"]] == [f"D{i:02}" for i in range(1, 33)], name, "deduction ledger identity drift")
            return result

    golden = probe("golden_mechanical")
    check((golden["positive_earned"], golden["deduplicated_deductions"], golden["raw"], golden["final"]) == (1.0, 0, 1.0, 1.0), "golden_mechanical", "Golden must be strict 1.0 with zero deductions")
    check(not golden["unresolved_semantic_candidates"], "golden_mechanical", "Golden must have no unresolved candidate")

    golden_notice = scorer.parse_artifact(GOLDEN / NOTICE, NOTICE).text
    golden_d5 = scorer.parse_artifact(GOLDEN / SCHEDULE, SCHEDULE).cells["sheet1!D5"]
    golden_h5 = scorer.parse_artifact(GOLDEN / SCHEDULE, SCHEDULE).cells["sheet1!H5"]

    def empty(folder: Path) -> None:
        write_notice(folder, ""); write_docx(folder / COMMITMENT, ""); write_xlsx(folder / SCHEDULE, {}); write_xlsx(folder / DIRECTORY, {})
    blank = probe("blank_containers_zero_positive", empty); check(blank["positive_earned"] == 0, "blank_containers_zero_positive", "blank gained credit")

    def headings(folder: Path) -> None:
        write_notice(folder, "公开招聘公告\n二、报考资格条件\n三、招聘计划及岗位\n四、招聘程序")
        write_docx(folder / COMMITMENT, "诚信承诺书\n签名\n日期"); write_xlsx(folder / SCHEDULE, {"A1":"岗位明细表"}); write_xlsx(folder / DIRECTORY, {"A1":"专业目录"})
    heading = probe("headings_only_zero_positive", headings); check(heading["positive_earned"] == 0, "headings_only_zero_positive", "headings gained credit")

    def keyword_pile(folder: Path) -> None:
        headings(folder); write_notice(folder, "公开招聘公告 毕业证 专业 填写 未列入 招聘单位 材料 认定 具体专业 仅该专业 经济和管理学大类 岗位明细表 专业目录 诚信承诺书")
    keywords = probe("keyword_pile_zero_positive", keyword_pile); check(keywords["positive_earned"] == 0, "keyword_pile_zero_positive", "keywords gained credit")

    def direct_copy(folder: Path) -> None:
        headings(folder); shutil.copy2(PACKAGE / "task/environment/workspace/materials/附件2 湖南省2026年考试录用公务员专业指导目录.xlsx", folder / DIRECTORY)
    copied = probe("single_material_copy_zero_positive", direct_copy); check(copied["positive_earned"] == 0, "single_material_copy_zero_positive", "direct copy gained credit")

    def shape_only(folder: Path) -> None:
        s01 = "二、报考资格条件\n" + "甲" * (386 - len(scorer.n("二、报考资格条件")))
        s02 = "三、招聘计划及岗位\n" + "乙" * (483 - len(scorer.n("三、招聘计划及岗位")))
        s03 = "四、招聘程序\n" + "丙" * (1679 - len(scorer.n("四、招聘程序")))
        write_notice(folder, s01 + "\n" + s02 + "\n" + s03 + "\n五、人员管理")
        cells = {"D5":"丁"*138, "H5":"戊"*210, "D6":"己"*109, "H6":"庚"*55, "A1":"辛"*(671-138-210-109-55)}
        write_xlsx(folder / SCHEDULE, cells); write_xlsx(folder / DIRECTORY, {"A1":"壬"}); write_docx(folder / COMMITMENT, "癸")
    shaped = probe("golden_shape_only_zero_positive", shape_only); check(shaped["positive_earned"] == 0, "golden_shape_only_zero_positive", "shape gained credit")

    def carrier(folder: Path) -> None: write_notice(folder, golden_notice, table=True)
    carrier_result = probe("carrier_transform"); carrier_result = probe("carrier_transform_table", carrier)
    check(carrier_result["positive_earned"] == golden["positive_earned"] and carrier_result["deduplicated_deductions"] == 0, "carrier_transform_table", "open carrier changed content score")

    def notation(folder: Path) -> None:
        text = golden_notice.replace("2026年9月15日", "2026-09-15").replace("不能计算为工作经历时间", "不计入工作经历")
        write_notice(folder, text)
    notation_result = probe("notation_transform", notation)
    check(notation_result["positive_earned"] == golden["positive_earned"] and notation_result["deduplicated_deductions"] == 0, "notation_transform", "allowed notation changed score")

    def attachment_adopted_scope(folder: Path) -> None:
        old = "5、报考人员的专业应严格按照毕业证书填写。岗位所要求专业以《湖南省2026年考试录用公务员专业指导目录》（见附件2）为准。所学专业已列入《湖南省2026年考试录用公务员专业指导目录》、但未列入招聘岗位要求专业的，则不符合报考条件；出现考生所学专业未列入本专业目录的情形时,由招聘集团根据相关材料进行认定。专业要求表述为某个具体专业时,表示仅该专业符合岗位要求,而非某类专业。"
        write_notice(folder, golden_notice.replace(old, "5、岗位专业范围以附件1岗位明细表为准。"))
    adopted_scope = probe("P02_scope_via_adopted_schedule_and_directory_edges", attachment_adopted_scope)
    check(pval(adopted_scope, "P02") == scorer.P_WEIGHTS["P02"], "P02_scope_via_adopted_schedule_and_directory_edges", "functionally adopted hierarchy scope lost P02")

    def interference(folder: Path) -> None: shutil.copy2(folder / SCHEDULE, folder / "岗位明细表干扰副本.xlsx")
    interference_result = probe("source_interference", interference)
    check(interference_result["final"] == golden["final"], "source_interference", "non-authoritative same-name source interfered")

    def u019(folder: Path) -> None:
        replace_zip_text(folder / DIRECTORY, "附件5", "附件99"); replace_zip_text(folder / DIRECTORY, "湖南省2026年考试录用公务员专业指导目录", "湖南省2099年考试录用公务员专业指导目录")
    u019_result = probe("u019_symmetric_exclusion", u019)
    check((u019_result["positive_earned"], u019_result["deduplicated_deductions"], u019_result["final"]) == (1.0, 0, 1.0), "u019_symmetric_exclusion", "U019 identity affected score")

    def excluded_propositions(folder: Path) -> None:
        text = golden_notice + "\n岗位所要求的工作经历应为全职工作经历。\n"
        text += "无故不参加现场资格审查或考试者将被列为失信黑名单。\n"
        text += "本次招聘入围面试所有考生均纳入集团储备人才库。"
        write_notice(folder, text)
    exclusions_result = probe("unsupported_old_propositions_are_scored", excluded_propositions)
    check(dsum(exclusions_result, "D32") >= .12, "unsupported_old_propositions_are_scored", "old unauthorized propositions were silently ignored")

    def excluded_h6(folder: Path) -> None:
        from openpyxl import load_workbook
        path = folder / SCHEDULE
        book = load_workbook(path); sheet = book.active
        sheet["H6"] = "1、2年及以上相关工作经验。\n2、有良好的沟通能力，具备风险控制意识\n3、有银行信贷、担保、小贷等公司工作经验优先"
        book.save(path)
    h6_exclusions = probe("unsupported_business_officer_additions_are_scored", excluded_h6)
    check(dsum(h6_exclusions, "D32") >= .12, "unsupported_business_officer_additions_are_scored", "unauthorized H6 assertions were silently ignored")

    def mandatory_sector_gate(folder: Path) -> None:
        from openpyxl import load_workbook
        path = folder / SCHEDULE
        book = load_workbook(path); book.active["H6"] = "具有2年以上融资担保、银行信贷、金融或类金融业务等相关工作经历。"; book.save(path)
    sector_gate = probe("D32_mandatory_sector_gate_distinct_from_old_preference", mandatory_sector_gate)
    check(dsum(sector_gate, "D32") == .12, "D32_mandatory_sector_gate_distinct_from_old_preference", "mandatory sector restriction was incorrectly hidden by preference exclusion")

    def omission(folder: Path) -> None:
        write_notice(folder, golden_notice.replace("专业要求表述为某个具体专业时,表示仅该专业符合岗位要求,而非某类专业。", ""))
    omitted = probe("ordinary_omission", omission)
    check(pval(omitted, "P04") == 0 and omitted["deduplicated_deductions"] == 0, "ordinary_omission", "ordinary omission was deducted")

    def wrong(folder: Path) -> None:
        text = golden_notice.replace("出现考生所学专业未列入本专业目录的情形时,由招聘单位结合报名材料及考生所学课程进行认定", "专业未列入目录时自动不符合报考条件")
        write_notice(folder, text)
    wrong_result = probe("wrong_assertion", wrong)
    check(pval(wrong_result, "P03") == 0 and dsum(wrong_result, "D08") == .10, "wrong_assertion", "wrong unlisted outcome not localized")

    def bounded_review_equivalent(folder: Path) -> None:
        text = golden_notice.replace(
            "出现考生所学专业未列入本专业目录的情形时,由招聘单位结合报名材料及考生所学课程进行认定",
            "附件2及已明确的专业范围未能直接认定的，由招聘单位结合所学课程等情况审核认定",
        )
        write_notice(folder, text)
    bounded_review = probe("P03_evidence_bounded_review_equivalent", bounded_review_equivalent)
    check(pval(bounded_review, "P03") == scorer.P_WEIGHTS["P03"], "P03_evidence_bounded_review_equivalent", "evidence-bounded equivalent lost P03")

    def comprehensive_commitment(folder: Path) -> None:
        write_docx(folder / COMMITMENT, "某融资担保有限公司公开招聘诚信承诺书 本人在报名及招聘过程中提交、填写和提供的全部信息、材料真实、准确、完整。弄虚作假时本人接受取消应聘或聘用资格并承担后果。承诺人（签名）： 日期：")
    comprehensive_result = probe("P08_comprehensive_commitment_equivalent", comprehensive_commitment)
    check(pval(comprehensive_result, "P08") == scorer.P_WEIGHTS["P08"], "P08_comprehensive_commitment_equivalent", "comprehensive commitment lost P08")

    def combined_age_clause(folder: Path) -> None:
        text = golden_notice.replace(
            "35周岁以下是指1991年9月1日以后出生（含9月1日），50周岁以下是指1976年9月1日以后出生（含9月1日）。",
            "总经理年龄为50周岁及以下，即须在1976年9月1日（含）以后出生；业务专员年龄为35周岁及以下，即须在1991年9月1日（含）以后出生。",
        )
        write_notice(folder, text)
    age_result = probe("D14_combined_role_age_binding", combined_age_clause)
    check(dsum(age_result, "D14") == 0, "D14_combined_role_age_binding", "General Manager boundary was rebound to Business Officer")

    def unsupported(folder: Path) -> None: write_notice(folder, golden_notice + "\n报考人员仅限男性报考。")
    unsupported_result = probe("unsupported_addition", unsupported)
    check(dsum(unsupported_result, "D32") == .12, "unsupported_addition", "unsupported adopted restriction not deducted")

    def broaden_gm_bar(folder: Path) -> None:
        text = golden_notice.replace(
            "二、报考资格条件",
            "二、报考资格条件\n被依法列为失信被执行人的人员不得报名。",
        )
        write_notice(folder, text)
    broadened_bar = probe("D32_generalized_role_specific_disqualification", broaden_gm_bar)
    check(dsum(broadened_bar, "D32") == .12, "D32_generalized_role_specific_disqualification", "role-specific source bar broadened without a charge")

    def candidate_policy_errors(folder: Path) -> None:
        text = golden_notice.replace(
            "复试基准成绩线为75分，成绩低于75分者予以淘汰，不得进入下一招聘程序。",
            "复试基准成绩线为75分，成绩低于75分者予以淘汰，不得进入下一招聘程序。末位最终成绩相同的，由招聘单位另行组织加试确定人选。",
        )
        text += "\n拥护中国共产党的领导和社会主义制度。\n被依法列为失信联合惩戒对象的人员不得报名。\n法律法规及国资监管规定不得担任国有企业管理人员，或者不得报考的其他情形。\n应聘人员应保持通讯畅通，因无法联系或者未按要求参加招聘环节造成的后果由本人承担。"
        write_notice(folder, text)
    policy_result = probe("D18_D32_independent_policy_and_dedup", candidate_policy_errors)
    check(dsum(policy_result, "D18") == .12, "D18_D32_independent_policy_and_dedup", "controlling tie-break test missed or duplicated")
    check(dsum(policy_result, "D32") == .24, "D18_D32_independent_policy_and_dedup", "two mechanically resolvable unsupported propositions not charged independently")

    def broaden_path_one(folder: Path) -> None:
        new = "1、金融及类金融机构（银行、融资担保、小额贷款、典当、融资租赁、保理等）相关岗位10年以上。2、管理经历（具备其一即可）：（1）上述金融或类金融机构中层及以上管理岗位累计5年以上；（2）融资担保、类金融信贷或风控核心业务岗位累计8年以上，且具备团队管理或重大项目主导经验。"
        from openpyxl import load_workbook
        path = folder / SCHEDULE; book = load_workbook(path); book.active["H5"] = new; book.save(path)
    broadened_path = probe("D12_path_one_broadened_by_cross_reference", broaden_path_one)
    check(dsum(broadened_path, "D12") == .10, "D12_path_one_broadened_by_cross_reference", "broadened sufficient path not charged once")

    def repeated(folder: Path) -> None: write_notice(folder, golden_notice + "\n曾彬 曾彬")
    repeated_result = probe("dedup_same_root", repeated)
    check(dsum(repeated_result, "D01") == .25, "dedup_same_root", "same root charged more than once")

    def independent(folder: Path) -> None: write_notice(folder, golden_notice + "\n曾彬 15673346153")
    independent_result = probe("independent_harms", independent)
    check(dsum(independent_result, "D01") == .50, "independent_harms", "independent identifier classes did not accumulate")

    def shape_cell(folder: Path, length: int) -> None:
        from openpyxl import load_workbook
        path = folder / SCHEDULE; book = load_workbook(path); book.active["D5"] = "甲" * length; book.save(path)
    # The boundary is read from the scorer rather than written here, so the probe tests
    # that the band is enforced wherever it sits instead of freezing one number twice.
    # The ceiling is the wider of the ratio band and the absolute allowance, and it is
    # read from the scorer so the probe tests the boundary wherever it sits.
    gold_s05 = scorer.SHAPES["S05"][0]
    ceiling = gold_s05 * (1 + scorer.UPPER_TOLERANCE["S05"])
    at_upper = probe("shape_upper_boundary", lambda f: shape_cell(f, int(ceiling)))
    check(dsum(at_upper, "D26") == 0, "shape_upper_boundary", "exact upper boundary deducted")
    above_upper = probe("shape_above_upper", lambda f: shape_cell(f, int(ceiling) + 120))
    check(dsum(above_upper, "D26") > 0, "shape_above_upper", "above-boundary shape not deducted")

    def qualification_length(folder: Path, target: int) -> None:
        lines = golden_notice.splitlines(); start = next(i for i,x in enumerate(lines) if "二、报考资格条件" in x)
        end = next(i for i,x in enumerate(lines[start + 1:], start + 1) if "三、招聘计划" in x)
        title = lines[start]; replacement = [title, "甲" * (target - len(scorer.n(title)))]
        write_notice(folder, "\n".join(lines[:start] + replacement + lines[end:]))
    at_lower = probe("shape_lower_boundary", lambda f: qualification_length(f, 97))
    check(dsum(at_lower, "D27") == 0, "shape_lower_boundary", "first integer at or above 25 percent deducted")
    below_lower = probe("shape_below_lower", lambda f: qualification_length(f, 96))
    check(dsum(below_lower, "D27") == .04, "shape_below_lower", "below-boundary section underload not deducted")

    def replace_top_section(text: str, marker: str, target: int) -> str:
        lines = text.splitlines(); start = next(i for i,x in enumerate(lines) if marker in x)
        end = next(i for i,x in enumerate(lines[start + 1:], start + 1) if __import__("re").match(r"^[一二三四五六七八九十]+[、,.，．]", x.strip()))
        title = lines[start]
        return "\n".join(lines[:start] + [title, "甲" * (target - len(scorer.n(title)))] + lines[end:])

    def repaired_shape_units(folder: Path) -> None:
        text = replace_top_section(golden_notice, "二、报考资格条件", 1250)
        text = replace_top_section(text, "三、招聘计划", 109)
        text = replace_top_section(text, "四、招聘程序", 1675)
        write_notice(folder, text)
        from openpyxl import load_workbook
        path = folder / SCHEDULE; book = load_workbook(path); book.active["H5"] = "甲" * 470; book.save(path)
    repaired_shape = probe("D26_D27_repaired_shape_extraction", repaired_shape_units)
    check(0 < dsum(repaired_shape, "D26") < .09, "D26_D27_repaired_shape_extraction", "declared S01 and S06 continuous shape sum diverged")
    check(dsum(repaired_shape, "D27") == 0, "D26_D27_repaired_shape_extraction", "S02 15 percent lower floor diverged")
    shape_values = {x["id"]: x["candidate"] for x in repaired_shape["shape_units"]}
    check((shape_values["S01"], shape_values["S02"], shape_values["S03"], shape_values["S06"]) == (1250,109,1675,470), "D26_D27_repaired_shape_extraction", "shape unit binding mismatch")

    def corrupt(folder: Path) -> None: (folder / COMMITMENT).write_bytes(b"not a docx")
    corrupted = probe("local_parser_failure", corrupt)
    check(corrupted["release_status"] == "evidence_insufficient", "local_parser_failure", "failure did not block release")
    check(all(dsum(corrupted, x) == 0 for x in ["D04", "D05", "D06", "D30"]), "local_parser_failure", "parser failure became business guilt")
    check(any(x["item_id"] == "package" and x["location"] == COMMITMENT for x in corrupted["unresolved_semantic_candidates"]), "local_parser_failure", "local unresolved record absent")

    def ambiguous_rows(folder: Path) -> None:
        write_xlsx(folder / SCHEDULE, {"A1":"岗位", "A2":"总经理", "B2":"1", "C2":"职责", "D2":"学历", "E2":"经济和管理学大类",
                                          "A3":"总经理", "B3":"1", "C3":"职责二", "D3":"学历", "E3":"经济和管理学大类",
                                          "A4":"业务员", "B4":"1", "C4":"职责", "D4":"学历", "E4":"经济和管理学大类"})
    ambiguous = probe("local_ambiguous_role_binding", ambiguous_rows)
    check(next(x for x in ambiguous["positive_items"] if x["id"] == "P02")["extraction_state"] == "ambiguous", "local_ambiguous_role_binding", "ambiguity did not remain local")
    check(dsum(ambiguous, "D28") == .10, "local_ambiguous_role_binding", "ambiguous role-key structure did not trigger D28")

    report = {"schema": "rubric-v3.4-probe-evidence", "status": "passed", "scorer": "task/tests/package_score.py",
              "probe_count": len(records), "records": records,
              "coverage": ["Golden strict full credit", "direct copy", "blank", "headings", "keyword pile", "shape only",
                           "equivalence", "ordinary omission", "wrong assertion", "unsupported addition", "deduplication",
                           "independent harm", "shape boundaries", "carrier", "notation", "source interference",
                           "U019 directory identity", "local parser failure", "local ambiguity"]}
    target = Path("/tmp/public-recruitment-rubric-probe-results.json")
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "probe_count": len(records), "report": str(target)}, ensure_ascii=False)); return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except AssertionError as exc: print(exc, file=sys.stderr); raise SystemExit(1)

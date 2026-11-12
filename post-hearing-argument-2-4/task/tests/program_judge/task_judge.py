#!/usr/bin/env python3
"""Deterministic, condition-blind DOCX observations for this legal argument."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from program_judge_runtime import Locator, ProgramJudge, load_contract, sha256


PACKAGE_ROOT = Path(__file__).resolve().parents[3]
CONTRACT = (PACKAGE_ROOT / "rubric-contract.json" if (PACKAGE_ROOT / "rubric-contract.json").is_file()
            else Path(__file__).resolve().parents[1] / "rubric-contract.json")
MATERIALS = (PACKAGE_ROOT / "task/environment/workspace/materials"
             if (PACKAGE_ROOT / "task/environment/workspace/materials").is_dir()
             else Path(__file__).resolve().parents[2] / "materials")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# Each tuple is one local business relation: mandatory anchors and an adopted
# consequence. These locate candidates; provenance and contradictory contexts
# are checked separately before any Program credit is recorded.
POSITIVE_RULES = {
    "P01": ((r"4468031|4,468,031", r"鉴定|可确定", r"措施费|管理费|规费|利润|税"), r"不完整|不应.*最终|应.*计取|偏离.*价格"),
    "P02": ((r"措施费|管理费|组织管理|安全技术措施|现场措施", r"组织|管理|现场|安全", r"成本|费用|价款|实际发生|支出"), r"应.*计入|不能.*排除|排除.*不完整|排除.*亏损|遗漏|未完整计取|不宜.*整项排除|不应.*整项排除|不应.{0,70}(?:扣减|扣除|排除)|不能.{0,20}(?:仅作|结论性|整体).{0,12}(?:扣除|排除)"),
    "P03": ((r"未签|无书面|未就|价款.*未.*约定", r"计价|定额|造价|鉴定", r"排除|完整|依据|漏项|质疑"), r"缺乏.*依据|应.*完整|不能.*排除|显失公平|不意味着.{0,28}(?:放弃|免于)|不宜.*直接.*采信"),
    "P04": ((r"实际施工|施工组织|实际管理.*组织.*施工|实际管理", r"利润|管理费", r"资质|资格|合同|施工人身份|个人施工"), r"不应.*扣除|不得.*减去|不应.*排除|不能.*一概|应.*计取|不是.*资质.*当然剔除|不宜.*个人.*整项排除|不能因.*资质.*整项排除|不宜仅因.*身份.*剔除|勿因.*个人施工.*一概排除"),
    "P05": ((r"税|规费", r"造价|计取|负担|适用条件", r"税收征管|缴税|税金本就|举证|证据"), r"不当获利|公平|应.*计取|不能.*排除|不宜.*机械扣除|勿因.*个人施工.*一概排除"),
    "P06": ((r"鉴定|可确定", r"市场(?:价格|价|单价|公允价值)|市场.{0,70}(?:参照|可比|比对|校验|检验|核查)|(?:校验|检验|核查).{0,70}市场|(?:价格|单价|结算).{0,60}(?:可比|比对|参照|比较)", r"法院|法庭|确定价款|核验|审查|核清|补充说明"), r"(?:鉴定|可确定).{0,130}(?:而非|不是|非|不等于|不宜).{0,36}(?:最终|全部)|(?:不认可|不宜|不能).{0,28}(?:仅以|仅用|以|将).{0,20}(?:鉴定|可确定|该可确定项).{0,45}(?:代表|作为|等同).{0,25}(?:全部|最终)|(?:鉴定|可确定).{0,85}(?:不宜|不能).*直接|(?:市场|可比).{0,90}(?:校验|检验|核查|审查|确定价款|补充说明|核清)"),
    "P07": ((r"211160|211,160", r"1063645|1,063,645", r"帮工|工人", r"委托|追认|同意|授权"), r"不应.*已付|不应.*扣除|缺乏.*依据|未.*追认|尚须证明.*同意|(?:不能|不得).*直接.*扣|不当然.*工程款|(?:没有|缺少|缺乏).{0,36}(?:授权|委托|追认).{0,70}(?:不能|不足以).{0,36}(?:代表原告|清偿|工程价款)"),
    "P08": ((r"证人|蒋振华|蒋震华|\[witness", r"招用|招来|叫|联系", r"支付|结算|工资|付款|索款|领款", r"原告|关系|不认识"), r"不能.*证明|不足.*证明|未.*关系|不认识.*原告|不.*等于.*原告|不能.*推定.*原告|不能.*确认.*雇主"),
    "P09": ((r"签字|签名", r"带班|现场|陈海龙|陈|\[site_person", r"代理|追认|权限|授权"), r"不构成|不能.*认定|无.*权限|不足以.*证明|尚不足.*证明|不当然.*证明|不能仅凭.*推定.*授权|不能.{0,24}(?:扩张|扩大).{0,24}(?:授权|确认|债务)|不当然.{0,20}(?:包含|等于).{0,24}(?:授权|权限)"),
    "P10": ((r"5040500|5,040,500", r"5100|5,100", r"帮工|已付|工资|代发"), r"不能.*计入|不应.*计入|矛盾|存在.*争议|仍.*异议|逐笔.*核验|不得.*重复|不能.*替代.*核验"),
    "P11": ((r"赶工|工期", r"帮工|费用", r"发包方|被告|原告"), r"费用应由(?:发包方|被告).{0,8}承担|(?:发包方|被告).{0,24}(?:另行|应).{0,12}承担|不应.*扣除|不能.*强加|不能.*原告.*扣除|不应.*原告.*承担"),
    "P12": ((r"实际施工|实际投入|实际组织|已完工程|完成.{0,16}(?:钢筋|劳务|工程)|已完.{0,10}(?:钢筋|劳务|工程)", r"市场|定额|合理|完整|核定|核验|查明", r"工程价款|完整价款|价款|造价|对价|报酬"), r"应.*保护|应.*确定|应.*计取|应.*审查|应.*核验|请.{0,70}(?:核定|确定|审查|核验)|恳请法院|按查明.{0,50}(?:确定|认定)"),
    "P13": ((r"2467271|2,467,271", r"316135\.13|316,135\.13|利息", r"法院|鉴定|核验|核对|查明"), r"补充鉴定|补充说明|以法院.{0,30}(?:核算|查明|认定)|核实.{0,30}(?:组成|付款|到期)|具体数额以法院"),
}

# Damage predicates require a locally adopted false assertion. Opponent quotations,
# rejected alternatives, absence and uncertain statements do not trigger damage.
DEDUCTION_RULES = {
    "D01": (r"(?:法院|法庭).{0,14}(?:已|已经).{0,10}(?:认定|判定).{0,24}(?:4468031|4,468,031).{0,12}(?:最终|欠款|应付)",),
    "D02": (r"(?:鉴定报告|鉴定机构).{0,20}(?:已|已经|明确).{0,12}(?:认定|确认|鉴定).{0,22}(?:750万|7500000|7,500,000)",),
    "D03": (r"(?:帮工|工人).{0,22}(?:支付|费用).{0,22}(?:即|当然|已经|应当).{0,20}(?:原告.*已付|应.*扣除|由原告承担)",),
    "D04": (r"(?:带班|现场|签字|签名).{0,25}(?:当然|必然|足以|自动).{0,16}(?:代理|授权|追认)",),
    "D05": (r"(?:证人|蒋振华|蒋震华).{0,25}(?:亲眼|直接|确认|证实).{0,25}(?:原告.*委托|原告.*雇用|公司.*合同关系)",),
    "D06": (r"(?:双方|法院).{0,18}(?:已|已经).{0,12}(?:确认|核定).{0,28}(?:5100元不存在争议|259850元无争议|工资无争议)",),
    "D07": (r"(?:法院|法庭).{0,16}(?:已经|已).{0,14}(?:判决|裁定|确认).{0,20}(?:反诉|返还|利息|资金占用费)",),
}
EXCLUDED_START = re.compile(r'^(?:[\W_]*(?:示例|关键词|引用|摘录|原文|备选|候选|对方观点|被告称|被告主张|据被告)|[\W_]*[“"])')
OTHER_MATTER_OR_REJECTION = re.compile(r"^(?:另案|案外|与本案无关|不认可以下说法|下列观点未采纳)")
REJECTION = re.compile(r"不能认定|不足以证明|并非如此|没有依据|缺乏.*依据|明显前后矛盾|不应.*作为|不应.*认定|并未.*证明")
RELATION = re.compile(r"因|故|因此|而|但|若|如若|则|应|不应|不能|不宜|不构成|不足|未|尚")
SENTENCES = re.compile(r"[。！？；;]")
ISSUE_HEADING = re.compile(r"^(?:[一二三四五六七八九十]{1,3}[、.．]|(?:[1-9]|10)[、.．])")
ISSUE_SPAN_ITEMS = frozenset({"P03", "P04", "P05", "P06", "P07", "P08", "P10"})


def is_issue_heading(text: str) -> bool:
    """Recognize a short section label without discarding numbered argument text."""
    value = text.strip()
    match = ISSUE_HEADING.match(value)
    if not match:
        return False
    remainder = value[match.end():].strip()
    return not remainder or (len(remainder) <= 32 and not re.search(r"[，；。！？]", remainder))

# Reject an expressly adopted contrary business outcome, not merely a keyword.
# These guards are applied to all P items before positive matching. A later
# repudiation of the contrary statement is handled by adopted_business_text().
CONTRARY_RELATIONS = {
    "P01": r"并非不完整|可直接作为最终欠款|无需复核|无需.*审查.*4468031|措施费.*已计入.*最终欠款",
    "P02": r"不应计入.*价款|应由原告自行承担|排除并无不完整|排除.*并无.*亏损",
    "P03": r"排除.*有充分依据|不应完整计算|排除.*并无不当",
    "P04": r"(?:利润|管理费).{0,14}不应计取|应全部扣除|没有.*资质.*因此.*扣除",
    "P05": r"不应计取.*(?:税|规费)|(?:税|规费).{0,18}由原告自理|税金本就是企业自行缴税负担",
    "P06": r"鉴定.*已是法院最终|无需审查|无需另行核价|鉴定.*法院.*最终.*无需",
    "P07": r"(?:已获原告授权|原告已委托|已经追认).{0,18}(?:代付|支付|付款)|已付帮工费.*不应扣除",
    "P08": r"不能证明原告未参与|仍应认定原告追认|证人.{0,12}(?:直接|足以|已经)证明.*原告.*雇",
    "P09": r"签字.*(?:已经证实|当然证明|足以证明).*代理|不能认定原告没有授权|签字.*必然.*追认",
    "P10": r"经双方确认并无矛盾|无须再核查.*差额|帮工费均已计入.*全额扣除",
    "P11": r"(?:帮工|赶工|用工).{0,25}费用.{0,8}由原告承担|(?<!不)应从原告.*工程价款中扣除|(?<!不能)(?<!不应)(?<!不得)(?<!不应当)从原告.*工程款中扣除|原告不应推给发包方",
    "P12": r"(?:合理工程价款|工程价款).{0,14}不应保护|被告单方确定报酬",
    "P13": r"(?:2467271|2,467,271).{0,30}(?:已经确定|无需核验)|(?:316135\.13|316,135\.13).{0,30}(?:已经确定|无需核验)",
}

# Each deduction binds a business object, a false asserted relationship and the
# asserted adoption. Ordering is deliberately not tied to a single stock phrase.
DAMAGE_RELATIONS = {
    "D01": (r"4468031", r"全部应付|最终欠款|最终.*债务", r"审判庭.*认定|法院.*认定|法庭.*判定|已有明确认定"),
    "D02": (r"7507771|7500000|750万|七百五十万", r"鉴定报告|鉴定机构", r"已经认证|已经确认|已确认|已认定|明确鉴定|正式.*结论"),
    "D03": (r"帮工|工人", r"(?:被告|第三方).{0,16}(?:支付|付款)|直接付款|工人.*收款", r"(?:即|当然|自动|无须).{0,22}(?:清偿|已付|扣除|抵扣|承担)|直接视为.{0,12}(?:清偿|已付|扣除|抵扣)"),
    "D04": (r"(?:带班|现场).{0,15}(?:签字|签名)|(?:签字|签名).{0,15}(?:带班|现场)", r"授权|代理|追认|委托", r"已经证实|当然|必然|自动|足以|无须.*凭证"),
    "D05": (r"证人|证言", r"原告.*第三方|原告.*公司|原告.*委托|原告.*雇", r"(?:足以|直接|亲眼|已经).{0,12}(?:证明|确认)|证实.*已成立"),
    "D06": (r"(?:庭审双方|法院|法庭).{0,12}(?:确认|核定)", r"工资|已付|5100", r"(?:5100|5,100).{0,12}(?:没有|不存在|无争议|无差额)|(?:不存在分歧|无争议).{0,35}(?:5100|5,100)"),
    "D07": (r"反诉|返还|利息|资金占用费", r"已裁判|已经判决|已判决|已确认|裁判生效|既判", r"一审法院|法院|法庭|既判内容"),
}

# D06 also covers the operative amount itself, not only the suppressed 5,100 gap
# (damage_basis: "Distort the operative amount and reconciliation").  The check is
# arithmetic and document-local: the submission states an approximate amount and a
# precise amount and asserts that the two agree.  Whether they agree is decided by
# the approximation's own rounding unit, never by a fixed list of "correct" figures,
# so a legitimate 已付款 / 诉请 / 分项 figure in the same sentence cannot be charged.
AMOUNT_UNITS = {"万": 10000, "亿": 100000000}
APPROXIMATE_AMOUNT = re.compile(r"(?:接近|将近|约|大约|近|差不多)?(\d+(?:\.\d+)?)(万|亿)(?:余|多)?元")
PRECISE_AMOUNT = re.compile(r"(?<![\d.])(\d{6,})(?:\.\d+)?元")
RECONCILED = re.compile(r"(?:基本)?(?:吻合|相符|一致|相当)")

# D07 also covers the posture itself (damage_basis: "Misstate an unresolved
# procedural posture as a concluded judicial ruling").  A first-instance matter
# that is still being argued cannot at the same time be declared free of dispute,
# discharged in full or extinguished; each alternative below is bound to the case
# or to the whole obligation, so "工程质量无争议" or "该项双方无争议" about one
# sub-item stays outside it, and "未获足额清偿" is a denial, not an assertion.
CONCLUDED_MATTER = re.compile(
    r"(?:本案|全案|本纠纷|本诉)(?:现|业)?已?(?:经)?(?:不存在|无)(?:任何)?(?:争议|纠纷)"
    r"|(?:债权债务|债权债务关系|全部债务|本案债务)(?:现|业)?已(?:经)?(?:均)?(?:归于)?(?:消灭|清结|了结|终止)"
    r"|(?:已|业已)(?:于\d{4}年\d{1,2}月\d{1,2}日)?(?:向[^，。；,]{0,14})?(?:全额|足额|全部)(?:清偿|付清|支付完毕)"
)
LATER_REJECTION = re.compile(r"(?:上述|前述|该)(?:说法|观点|断言|结论).{0,18}(?:毫无依据|显然不成立|错误|不成立|未被采纳)")
DENIED_HARM = re.compile(r"并未.*(?:认定|确认|证明|授权|追认|判决)|(?:并非|不是).{0,24}(?:鉴定|法院|法庭).{0,18}(?:确认|认定|结论)|不能.*(?:认定|证明|确认|扣除)|不能.{0,40}(?:并入|计入|视为|当作).{0,24}(?:清偿|已付|抵扣)|不当然.*(?:证明|授权|清偿|抵扣)|不足以.*(?:证明|认定)|不应(?:该)?.{0,18}承担")


def compact(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", value)
    return re.sub(r"\s+", "", value).lower()


def extract_raw(artifact: Path) -> list[dict]:
    if not artifact.is_file() or artifact.suffix.lower() != ".docx":
        raise ValueError("completed DOCX artifact is required; missing output is not a zero score")
    records: list[dict] = []
    try:
        with zipfile.ZipFile(artifact) as archive:
            if "word/document.xml" not in archive.namelist():
                raise ValueError("DOCX has no readable main document")
            for part in archive.namelist():
                if part != "word/document.xml" and not re.fullmatch(r"word/(?:header|footer)\d+\.xml", part):
                    continue
                root = ET.fromstring(archive.read(part))
                if root.find(".//" + W + "altChunk") is not None:
                    records.append({
                        "part": part, "index": 0, "text": "[unparsed alternate content]",
                        "normalized": "", "carrier": "unsupported_embedded_text",
                    })
                for index, paragraph in enumerate(root.iter(W + "p"), 1):
                    value = "".join(node.text or "" for node in paragraph.iter(W + "t")).strip()
                    if value:
                        records.append({
                            "part": part, "index": index, "text": value,
                            "normalized": compact(value), "carrier": "docx_paragraph",
                        })
                if part == "word/document.xml":
                    for index, row in enumerate(root.iter(W + "tr"), 1):
                        cells = [" ".join((node.text or "") for node in cell.iter(W + "t")).strip()
                                 for cell in row.findall(W + "tc")]
                        value = "，".join(cell for cell in cells if cell)
                        if value:
                            records.append({
                                "part": part, "index": index, "text": value,
                                "normalized": compact(value), "carrier": "docx_table_row",
                            })
    except (OSError, zipfile.BadZipFile, ET.ParseError) as exc:
        raise ValueError(f"invalid DOCX output; unscored technical failure: {exc}") from exc
    if not any(row["part"] == "word/document.xml" for row in records):
        raise ValueError("empty DOCX body; output validity failed")
    return records


def source_corpus() -> str:
    return "\n".join(
        re.sub(r"[^\w\u4e00-\u9fff]", "", compact(path.read_text(encoding="utf-8")))
        for path in sorted(MATERIALS.glob("*.txt"))
    )


def raw_locator(artifact: Path, record: dict, label: str) -> Locator:
    return Locator(
        locator_id=f"{label}:{record['part']}:{record['carrier']}:{record['index']}",
        artifact_path=str(artifact),
        container_type=record["carrier"],
        container_path=f"{record['part']}:{'tr' if record['carrier'] == 'docx_table_row' else 'p'}{record['index']}",
        object_key=label,
        field="text",
        observed=record["text"],
    )


def copied_source_paragraph(value: str, corpus: str) -> bool:
    plain = re.sub(r"[^\w\u4e00-\u9fff]", "", value)
    return len(plain) >= 75 and (plain in corpus or all(
        plain[offset:offset + 70] in corpus
        for offset in range(0, max(1, len(plain) - 69), 70)
    ))


def repeated_phrase_spray(value: str) -> bool:
    """Reject long exact phrase cycles that carry no document-local reasoning."""
    return len(value) >= 600 and value.count(value[:160]) >= 3


def adopted_business_text(value: str) -> str:
    """Exclude an expressly attributed or subsequently repudiated proposition."""
    if re.match(r"^(?:被告|对方)(?:主张|称|认为|提出)", value):
        rebuttal = re.search(r"[；;。](?=(?:原告|申请人|答辩人)(?:认为|指出|主张|强调|答辩|提出))", value)
        if rebuttal:
            return value[rebuttal.end():]
    if LATER_REJECTION.search(value):
        return re.split(r"(?:上述|前述|该)(?:说法|观点|断言|结论)", value, maxsplit=1)[-1]
    return value


def has_adopted_relation(record: dict, anchors: tuple[str, ...], consequence: str, corpus: str,
                         item_id: str) -> bool:
    if record["part"] != "word/document.xml":
        return False
    value = record["normalized"]
    if item_id in {"P01", "P12"} and value.count("、") >= 12:
        return False
    adopted_value = adopted_business_text(value)
    if EXCLUDED_START.search(value) and not re.match(r"^(?:原告|申请人|答辩人)(?:认为|指出|主张|强调|答辩|提出)", adopted_value):
        if not re.match(r"^被告(?:主张|认为|称)", value):
            return False
        adopted = re.split(r"[；;。]", value)[1:]
        linked_clause = any(
            re.match(r"^(?:若|如果|因此|据此|请法院|但|然而|上述|前述|原告)", clause)
            and RELATION.search(clause)
            and re.search(consequence, clause)
            and (item_id != "P07" or re.search(r"授权|委托|追认", clause))
            for clause in adopted
        )
        linked_issue = ("rows" in record and len(adopted) >= 2
                        and re.search(consequence, "；".join(adopted))
                        and any(re.match(r"^(?:上述|前述|但|然而|原告|两笔)", clause)
                                and re.search(r"授权|委托|追认|证言|价款|鉴定", clause)
                                for clause in adopted))
        if not linked_clause and not linked_issue:
            return False
        adopted_value = "；".join(adopted)
    if OTHER_MATTER_OR_REJECTION.search(value) or "原告并不采纳" in value[:40]:
        return False
    numbered_p12 = bool(item_id == "P12" and re.match(r"^\d+[.\uFF0E\u3001]", value))
    if not re.search(r"[，。；：]", value) and not numbered_p12:
        return False
    if copied_source_paragraph(value, corpus) or repeated_phrase_spray(value) or not RELATION.search(value):
        return False
    proposed_total_route = False
    if item_id == "P06":
        proposed_total = (
            r"(?:造价|工程价款|合计|总额).{0,18}(?:至少)?(?:为|达|共计)?(?:\d{6,}|\d{1,3}(?:,\d{3})+)"
            r"|(?:\d{6,}|\d{1,3}(?:,\d{3})+).{0,24}(?:造价|工程价款|合计|总额)"
        )
        proposed_total_route = bool(
            re.search(r"(?:原告|申请人|一方).{0,60}(?:主张|提出).{0,70}(?:造价|工程价款|合计|总额)|(?:造价|工程价款|合计|总额).{0,70}(?:原告|申请人|一方).{0,40}(?:主张|提出)", adopted_value)
            and re.search(proposed_total, adopted_value)
            and re.search(r"鉴定(?:材料|报告|链条|征求意见稿|回复函|机构)|咨询报告", adopted_value)
            and re.search(r"(?:逐项|组成|复算|核对|核验|确认).{0,80}(?:鉴定|最终价款|组成|重复)|(?:补充说明|补充鉴定|最终价款)", adopted_value)
        )
    if not proposed_total_route and any(re.search(anchor, value) is None for anchor in anchors):
        return False
    if re.search(CONTRARY_RELATIONS[item_id], adopted_value):
        return False
    consequence_match = proposed_total_route or re.search(consequence, adopted_value) is not None
    if item_id == "P01" and not consequence_match:
        # P01 also covers an equivalent, evidence-bound route: a concrete
        # omitted quantity/value pair plus an adopted request for supplemental
        # verification.  A bare comparison or a number alone is insufficient.
        omitted_value = (
            r"(?:\d[\d,]*\s*(?:吨|项|件)|(?:数量|工程范围|计价项目|价格项目))"
            r".{0,90}(?:未|没有|缺少|未见|未列|漏列|漏项).{0,45}"
            r"(?:对应|相应|单独).{0,24}(?:价款|价值|造价|金额|计价)"
        )
        supplemental_review = (
            r"(?:补充|重新|进一步).{0,24}(?:鉴定|核查|核验|复核|审查|查明|估价)"
            r"|(?:应|需|须|要求).{0,24}(?:核查|核验|复核|审查|查明|补充鉴定)"
        )
        consequence_match = bool(
            re.search(omitted_value, adopted_value)
            and re.search(supplemental_review, adopted_value)
        )
    if not consequence_match:
        return False
    if item_id == "P03":
        missing_price_agreement = (
            r"(?:未签|无|没有|未订立).{0,22}(?:书面|合同).{0,24}(?:价款|价格|计价|定价|劳务)"
            r"|(?:价款|价格|计价|定价).{0,24}(?:未签|无书面|未.*约定)"
            r"|(?:未就|未对).{0,24}(?:价款|价格|计价|定价).{0,15}(?:书面|约定|协议)"
        )
        appraisal_exclusion = (
            r"(?:鉴定|定额).{0,90}(?:排除|漏项|复核|质疑|不意味着|不能|不宜)"
            r"|(?:排除|漏项|补充).{0,50}(?:鉴定|定额)"
        )
        if not re.search(missing_price_agreement, adopted_value) or not re.search(appraisal_exclusion, adopted_value):
            return False
    if item_id == "P06":
        if proposed_total_route:
            return True
        # Loan-market interest and appraisal costs are not valuation comparators.
        comparator = re.sub(r"贷款市场报价利率|贷款利率|鉴定费|诉讼费", "", adopted_value)
        if not re.search(r"(?:鉴定|可确定).{0,180}(?:造价|工程价款|工程款|计价)|(?:造价|工程价款|工程款|计价).{0,100}(?:鉴定|可确定)", adopted_value):
            return False
        if not re.search(r"市场.{0,70}(?:价|单价|参照|可比|校验)|(?:市场|价格|单价).{0,70}(?:可比|比较|参照)", comparator):
            return False
        if not re.search(r"(?:法院|法庭|请).{0,100}(?:审查|核验|确定|采信|补充说明|核清)|(?:应|须).{0,60}(?:审查|核验|确定|采信|补充说明|核清)", adopted_value):
            return False
    if item_id == "P02":
        fee = bool(re.search(r"(?:管理费|组织管理)", adopted_value)
                   and re.search(r"(?:措施(?:费|项目)?|安全技术措施|现场措施)", adopted_value))
        evidenced_cost = (
            r"(?:实际发生|必要成本|必要.{0,20}支出|"
            r"实际承担.{0,30}(?:成本|支出|费用)|属于.{0,12}必要成本|"
            r"实际施工组织成本|实际施工人.{0,35}(?:现场管理|组织管理)|"
            r"实际施工.{0,28}(?:现场管理|组织管理|组织施工))"
        )
        adopted_cost_result = (
            r"(?:(?:不应|不宜|不能|不得).{0,50}(?:排除|扣除|扣减)"
            r"|(?:应当?|应予).{0,24}(?:计入|计取)"
            r"|排除.{0,40}(?:亏损|不完整)|(?:遗漏|未完整计取))"
        )
        if not (
            fee
            and re.search(evidenced_cost, adopted_value)
            and re.search(adopted_cost_result, adopted_value)
        ):
            return False
    if item_id == "P04":
        qualification = (
            r"(?:资质|资格|个人身份|施工人身份|无效合同).{0,45}(?:扣除|排除|剔除|利润|管理费)"
            r"|(?:扣除|排除|剔除|利润|管理费).{0,45}(?:资质|资格|个人身份|施工人身份|无效合同)"
        )
        if not re.search(qualification, adopted_value):
            return False
    if item_id == "P05":
        if not re.search(r"(?:鉴定|定额|造价|计价)", adopted_value):
            return False
        if not re.search(r"(?:实际施工|实际管理|实际承担|由.{0,18}承担|承担.{0,20}(?:缴税|税|费用|义务)|缴税义务|法定义务|支付证据|代缴|重复扣除)", adopted_value):
            return False
        if re.search(r"(?:类案|案例|裁判观点|裁判规则)", adopted_value) and not re.search(
            r"(?:参考|参照|不能替代|仍需|检索报告所载|报告所载|与本案.{0,20}(?:对应|结合)|本案事实)", adopted_value
        ):
            return False
    if item_id == "P07":
        # A claim that the plaintiff authorized the worker payment yet should
        # receive the same sum again reverses the adoption/attribution relation.
        if not re.search(r"(?:未经|未获|并未|从未|没有|无|未|否认).{0,18}(?:委托|追认|授权|同意|确认)|(?:委托|追认|授权|同意|付款).{0,18}(?:并未|未获|没有|无|不能证实|尚未证实|未能证明)|(?:委托|追认|授权|同意).{0,28}(?:尚须|仍须|仍需|需|须).{0,8}(?:证明|核|查|结合)|尚须证明.{0,100}(?:委托|追认|授权|同意)", adopted_value):
            return False
        if re.search(r"(?:已同意.{0,8}追认|已追认|已经追认|已委托|已经委托).{0,12}(?:代付|支付|付款)", adopted_value) and not re.search(r"(?:未同意|未委托|未追认).{0,14}(?:代付|支付|付款)", adopted_value):
            return False
        if re.search(r"(?:重复|两次|再次|二次).{0,12}(?:取得|领取|收取|获益)", adopted_value):
            return False
    if item_id == "P08":
        third_party = r"第三方|关联方|被告|他人|李林红|李林宏|\[third_party_person_\d+\]"
        caller_or_payor = rf"(?:{third_party}).{{0,16}}(?:招用|招来|叫来|叫|联系|索款|支付|结算|发放|付款)|(?:招用|招来|叫来|叫|联系|索款|支付|结算|发放).{{0,16}}(?:{third_party})"
        witness_limit = r"(?:不认识|未见过|没见过).{0,7}原告|(?:与|同)原告.{0,10}(?:没有|未).{0,5}(?:关系|合同)|(?:不能|不足(?:以)?).{0,12}证明.{0,20}原告"
        if not re.search(caller_or_payor, adopted_value) or not re.search(witness_limit, adopted_value):
            return False
        if re.search(r"(?:证人|工人).{0,12}(?:受原告|由原告).{0,8}(?:招用|叫来|雇用)|(?:工资|工钱).{0,8}(?:由|系)原告.{0,5}(?:支付|结算)", adopted_value):
            return False
    if item_id == "P12":
        complete_value_route = bool(
            re.search(
                r"(?:\u5df2\u5b8c|\u5b8c\u6210|\u5b9e\u9645\u65bd\u5de5|\u5b9e\u9645\u6295\u5165|\u5b9e\u9645\u7ec4\u7ec7).{0,100}(?:\u52b3\u52a1|\u5de5\u7a0b)",
                adopted_value,
            )
            and re.search(
                r"(?:\u5b8c\u6574|\u5408\u7406).{0,24}(?:\u4ef7\u503c|\u4ef7\u6b3e|\u5de5\u7a0b\u4ef7\u6b3e|\u9020\u4ef7)",
                adopted_value,
            )
            and re.search(
                r"(?:\u4e89\u8bae|\u5229\u6da6|\u63aa\u65bd\u8d39|\u7ba1\u7406\u8d39|\u89c4\u8d39|\u7a0e\u91d1|\u7a0e\u8d39|\u4e8c\u6b21\u7ed3\u6784)",
                adopted_value,
            )
            and re.search(
                r"(?:\u9010\u9879|\u5206\u522b).{0,24}(?:\u5ba1\u67e5|\u6838\u9a8c|\u6838\u5bf9)|(?:\u5ba1\u67e5|\u6838\u9a8c|\u6838\u5bf9).{0,24}(?:\u9010\u9879|\u5206\u522b)",
                adopted_value,
            )
            and re.search(r"(?:\u786e\u8ba4|\u8bf7\u6c42|\u6073\u8bf7|\u6cd5\u9662|\u5e94\u4ee5)", adopted_value)
        )
        # Some DOCX producers preserve Chinese through a non-Unicode console
        # code page. The base P12 anchors and consequence still match that text;
        # a numbered adopted disposition is enough to prove this same route
        # without depending on one encoding representation.
        complete_value_route = complete_value_route or bool(
            re.match(r"^\d+[.\uFF0E\u3001]", value)
            and all(re.search(anchor, value) for anchor in anchors)
            and consequence_match
        )
        work_and_value = re.search(
            r"(?:完成|已完|实际施工|实际投入|实际组织).{0,160}(?:价款|对价|报酬|造价)", adopted_value
        )
        valuation_result = re.search(
            r"(?:确定|核定|认定|计取|保护).{0,45}(?:价款|造价|对价|报酬)"
            r"|(?:价款|造价|对价|报酬).{0,45}(?:确定|核定|认定|计取|保护)", adopted_value
        )
        court_review = re.search(
            r"(?:法院|法庭|裁判).{0,160}(?:鉴定|定额|市场|造价|价款).{0,80}(?:审查|核验|核对)"
            r"|(?:鉴定|定额|市场|造价|价款).{0,160}(?:审查|核验|核对).{0,80}(?:法院|法庭|裁判)", adopted_value
        )
        if not complete_value_route and (not work_and_value or not (valuation_result or court_review)):
            return False
    if re.search(r"(?:关键词|罗列|堆砌|不存在语义关系|不构成事实判断)", value):
        return False
    return True


def issue_windows(raw: list[dict], item_id: str) -> list[dict]:
    """Bounded adjacent paragraphs within one issue, retaining exact source locators."""
    body = [row for row in raw if row["part"] == "word/document.xml" and row["carrier"] == "docx_paragraph"]
    sections: list[list[dict]] = []
    for row in body:
        if is_issue_heading(row["text"]):
            sections.append([])
        elif not sections:
            sections.append([row])
        else:
            sections[-1].append(row)
    windows = []
    for section in sections:
        for start, first in enumerate(section):
            for end in range(start + 2, min(len(section), start + 6) + 1):
                rows = section[start:end]
                if item_id in {"P07", "P08", "P10"} and not any(
                    re.search(r"上述|前述|该笔|两笔|同一|证言|帮工|代发|工资", row["normalized"])
                    for row in rows[1:]
                ):
                    continue
                windows.append({"part": "word/document.xml", "index": first["index"],
                                "carrier": "docx_paragraph", "text": "。".join(row["text"] for row in rows),
                                "normalized": "。".join(row["normalized"] for row in rows), "rows": rows})
    return sorted(windows, key=lambda row: (len(row["rows"]), row["index"]))


def semantic_issue_windows(raw: list[dict]) -> list[dict]:
    """Build bounded adjacent body windows for qualified equivalent reasoning.

    The lexical issue-heading splitter is intentionally conservative and can miss
    ordinary Chinese section headings.  A second bounded pass keeps one issue's
    neighboring paragraphs together without allowing document-wide keyword joins.
    """
    body = [row for row in raw if row["part"] == "word/document.xml" and row["carrier"] == "docx_paragraph"]
    windows = []
    for start in range(len(body)):
        for end in range(start + 2, min(len(body), start + 4) + 1):
            rows = body[start:end]
            if any(is_issue_heading(row["text"]) for row in rows):
                continue
            windows.append({
                "part": "word/document.xml",
                "index": rows[0]["index"],
                "carrier": "docx_paragraph",
                "text": "。".join(row["text"] for row in rows),
                "normalized": "。".join(row["normalized"] for row in rows),
                "rows": rows,
            })
    return windows


def semantic_equivalent_relation(record: dict, item_id: str, corpus: str) -> bool:
    """Accept source-faithful qualified equivalents missed by stock wording.

    Each fallback requires the business object, an evidence/status anchor, and an
    adopted consequence in one bounded window.  It is deliberately unavailable
    to headings, copied source text, or isolated keyword fragments.
    """
    if record["part"] != "word/document.xml" or record.get("carrier") != "docx_paragraph":
        return False
    value = record["normalized"]
    if (copied_source_paragraph(value, corpus) or repeated_phrase_spray(value)):
        return False
    if item_id == "P01" and value.count("、") >= 12:
        return False
    if OTHER_MATTER_OR_REJECTION.search(value):
        return False
    # A candidate/quotation wrapper cannot convert the enclosed proposition into
    # the submitting party's adopted conclusion. Keep this guard local to the
    # equivalent fallback so ordinary substantive paragraphs remain eligible.
    if re.match(r"^(?:\u5907\u9009|\u5019\u9009|\u5f15\u7528|\u5bf9\u65b9|\u6458\u5f55|\u539f\u6587|\u88ab\u544a\u4e3b\u5f20)", value):
        return False
    patterns = {
        "P01": (
            r"(?:4468031|4,468,031)",
            r"(?:不能|不应|不宜).{0,90}(?:完整|最终|直接)|(?:完整|最终).{0,90}(?:不能|不应|不宜)",
            r"(?:审查|核对|核验|复核|补充鉴定|完整鉴定)"
        ),
        "P02": (
            r"(?:管理费|措施费)",
            r"(?:实际施工|组织施工|现场管理|施工人)",
            r"(?:不因.{0,24}资质.{0,20}(?:当然)?(?:扣除|排除)|不应.{0,18}(?:扣减|排除)|应当?计入)"
        ),
        "P03": (
            r"(?:鉴定|计价|造价)",
            r"(?:未签|没有|无|未订立|未就|未对).{0,30}(?:书面|合同).{0,30}(?:价款|价格|计价|定价|劳务)|(?:价款|价格|计价|定价).{0,30}(?:未签|无书面|未约定)",
            r"(?:排除|漏项|补充|核对|核验|复核|不意味着.{0,28}(?:放弃|免于))"
        ),
        "P04": (
            r"(?:实际施工|现场管理|组织施工)",
            r"(?:利润|管理费)",
            r"(?:不因.{0,24}资质.{0,20}(?:当然)?(?:扣除|排除)|不应.{0,18}(?:扣除|排除)|不宜.{0,18}(?:整项)?排除|不当然)",
            r"(?:资质|资格|个人身份|施工人身份|无效合同)"
        ),
        "P05": (
            r"(?:规费|税金|措施费)",
            r"(?:鉴定|定额|造价|计价)",
            r"(?:实际施工|实际管理|实际承担|实际负担|开票纳税|由.{0,18}承担|承担.{0,20}(?:缴税|税|费用|义务)|缴税义务|法定义务|支付证据|代缴|重复扣除)",
            r"(?:合同|证据|举证|不应|不能|计入|扣减|承担)",
            r"(?:(?!(?:类案|案例|裁判观点|裁判规则)).)*(?:参考|参照|不能替代|仍需|检索报告所载|报告所载|与本案.{0,20}(?:对应|结合)|本案事实)|^(?:(?!(?:类案|案例|裁判观点|裁判规则)).)*$"
        ),
        "P06": (
            r"(?:鉴定|可确定)",
            r"(?:市场对比|市场比较|市场资料|市场价格|(?:市场|价格|单价).{0,70}(?:可比|参照|比较)|(?:可比|参照).{0,50}(?:市场|价格|单价))",
            r"(?:审查|核对|核验|确定价款|不能.{0,24}直接|不应.{0,24}直接)"
        ),
    }
    required = patterns.get(item_id)
    if required is None:
        return False
    if not all(re.search(pattern, value) for pattern in required):
        return False
    if item_id == "P06" and re.search(
        r"(?:（|\()[一二三四五六七八九十]{1,3}(?:）|\))", value
    ):
        return False
    if item_id == "P05":
        valuation_scope = re.sub(r"鉴定费|诉讼费", "", value)
        if not re.search(r"(?:鉴定(?:报告|意见|口径|范围)|定额|造价|计价)", valuation_scope):
            return False
        actual_burden = (
            r"规费.{0,50}(?:不应|不能).{0,28}重复扣除"
            r"|(?:规费|税金).{0,180}(?:实际负担|由.{0,24}承担|支付证据|代缴证据|已支付|已代缴)"
            r"|(?:实际负担|由.{0,24}承担|支付证据|代缴证据|已支付|已代缴).{0,180}(?:规费|税金)"
        )
        if not re.search(actual_burden, value):
            return False
    return True


def false_amount_reconciliation(sentence: str) -> bool:
    """An adopted claim that a stated approximate amount and a stated precise amount agree.

    The claim is charged only when the two cannot agree: the gap must exceed both 5% of
    the approximate figure and half of its own rounding unit.  The precise figure must be
    the only one inside the short span the submission itself draws between the two, so a
    sentence that merely also mentions a claim amount, an item amount or another matter's
    figure is not reached.  Nothing here consults a list of expected amounts.
    """
    for approximate in APPROXIMATE_AMOUNT.finditer(sentence):
        unit = AMOUNT_UNITS[approximate.group(2)]
        stated = float(approximate.group(1)) * unit
        for linked in RECONCILED.finditer(sentence, approximate.end()):
            span = sentence[approximate.end():linked.start()]
            if len(span) > 60:
                continue
            exact = [int(found.group(1)) for found in PRECISE_AMOUNT.finditer(span)]
            if len(exact) != 1:
                continue
            if abs(exact[0] - stated) > max(stated * 0.05, unit / 2.0):
                return True
    return False


def has_adopted_error(record: dict, patterns: tuple[str, ...], item_id: str) -> bool:
    if record["part"] != "word/document.xml":
        return False
    value = adopted_business_text(record["normalized"])
    for sentence in SENTENCES.split(value):
        if not sentence or EXCLUDED_START.search(sentence) or REJECTION.search(sentence) or DENIED_HARM.search(sentence):
            continue
        if re.search(r"如果|假设|例如|可能|待查|未提供|有待核实", sentence):
            continue
        if item_id == "D06" and false_amount_reconciliation(sentence):
            return True
        if item_id == "D07":
            if CONCLUDED_MATTER.search(sentence):
                return True
            if not re.search(
                r"(?:法院|法庭|一审).{0,24}(?:已经|已).{0,12}(?:判决|裁定|确认|裁判).{0,30}(?:反诉|返还|利息|资金占用费)"
                r"|(?:反诉|返还|利息|资金占用费).{0,28}(?:已经|已).{0,8}(?:判决|裁定|确认|裁判).{0,12}(?:生效|既判)",
                sentence,
            ):
                continue
        if all(re.search(pattern, sentence) for pattern in DAMAGE_RELATIONS[item_id]):
            return True
        if any(re.search(pattern, sentence) for pattern in patterns):
            return True
    return False


def suppressed_payment_dispute_records(raw: list[dict]) -> list[dict]:
    """Find an adopted confirmed total that omits the preserved 5,100 dispute."""
    submitted = "。".join(row["normalized"] for row in raw if row["part"] == "word/document.xml")
    dispute_disclosed = re.search(
        r"(?:5100|5,100).{0,45}(?:差额|争议|分歧|异议|待核|核实|核对|未确认)"
        r"|(?:差额|争议|分歧|异议|待核|核实|核对|未确认).{0,45}(?:5100|5,100)",
        submitted,
    )
    if dispute_disclosed:
        return []
    matches = []
    for row in raw:
        if row["part"] != "word/document.xml":
            continue
        value = adopted_business_text(row["normalized"])
        if EXCLUDED_START.search(value) or DENIED_HARM.search(value):
            continue
        if re.search(r"5040500|5,040,500", value) and re.search(
            r"(?:双方.{0,24}(?:确认|无异议)|(?:确认|无异议).{0,24}双方|无争议|后续确认的已付款口径)",
            value,
        ):
            matches.append(row)
    return matches


def normalize(raw: list[dict], judge: ProgramJudge) -> dict[str, tuple[str, list[dict]]]:
    corpus = source_corpus()
    results = {}
    artifact = judge.artifact_path
    from semantic_judge import adjudicate
    body = [r for r in raw if r["part"]=="word/document.xml" and r["carrier"]=="docx_paragraph"]
    verdict = adjudicate("\n".join(r["text"] for r in body),
                         (Path(__file__).parent / "semantic_source.json").read_text())
    judge.semantic_verdict = verdict
    unsupported = next((row for row in raw if row["carrier"] == "unsupported_embedded_text"), None)
    for item_id, (anchors, consequence) in POSITIVE_RULES.items():
        if unsupported:
            observation = judge.observe(item_id, "parse_failure", [raw_locator(artifact, unsupported, item_id)])
            results[item_id] = (observation, [])
            continue
        candidates = raw + (issue_windows(raw, item_id) if item_id in ISSUE_SPAN_ITEMS else [])
        if item_id in {"P03", "P04", "P05", "P06"}:
            candidates += semantic_issue_windows(raw)
        matches = [row for row in candidates if has_adopted_relation(row, anchors, consequence, corpus, item_id)]
        if not matches and item_id in {"P01", "P03", "P04", "P05", "P06"}:
            equivalent_candidates = raw if item_id == "P01" else semantic_issue_windows(raw)
            matches = [row for row in equivalent_candidates
                       if semantic_equivalent_relation(row, item_id, corpus)]
        if item_id in verdict["items"]:
            decision = verdict["items"][item_id]
            matches = [r for r in body if any(q in r["text"] for q in decision["quotes"])] if decision["fraction"] else []
            if decision["fraction"] and not matches:
                raise ValueError("Semantic evidence must bind submitted paragraphs")
        if matches:
            row = matches[0]
            source_rows = row.get("rows", [row])
            observation = judge.observe(item_id, "identified", [raw_locator(artifact, source, item_id)
                                                               for source in source_rows])
            results[item_id] = (observation, matches)
        else:
            marker = {"part": "word/document.xml", "index": 0, "text": "", "carrier": "docx_paragraph"}
            observation = judge.observe(item_id, "confirmed_missing", [raw_locator(artifact, marker, item_id)])
            results[item_id] = (observation, [])
    for item_id, patterns in DEDUCTION_RULES.items():
        if unsupported:
            observation = judge.observe(item_id, "parse_failure", [raw_locator(artifact, unsupported, item_id)])
            results[item_id] = ([observation], [])
            continue
        matches = [row for row in raw if has_adopted_error(row, patterns, item_id)]
        if item_id == "D06":
            seen = {(row["part"], row["carrier"], row["index"]) for row in matches}
            matches.extend(
                row for row in suppressed_payment_dispute_records(raw)
                if (row["part"], row["carrier"], row["index"]) not in seen
            )
        if matches:
            observations = [
                judge.observe(f"{item_id}:{index}", "identified", [raw_locator(artifact, row, f"{item_id}:{index}")])
                for index, row in enumerate(matches, 1)
            ]
        else:
            marker = {"part": "word/document.xml", "index": 0, "text": "", "carrier": "docx_paragraph"}
            observations = [judge.observe(item_id, "confirmed_missing", [raw_locator(artifact, marker, item_id)])]
        results[item_id] = (observations, matches)
    return results


def evaluate(observations: dict, judge: ProgramJudge) -> None:
    for item_id in judge.positives:
        observation, matches = observations[item_id]
        state = judge._observation(observation)["state"]
        judge.positive(
            item_id, 1.0 if state == "identified" else 0.0, observation,
            "Locally adopted complete issue relation" if state == "identified" else "Missing local proposition",
            "equivalent" if state == "identified" else "missing",
        )
    for item_id in judge.deductions:
        observation_ids, matches = observations[item_id]
        occurrences = [
            {
                "damage_instance_key": item_id,
                "causal_root_id": item_id,
                "manifestation_id": f"{item_id}:m{index}",
                "observation_id": observation_id,
                "reason": "Affirmative adopted error for one independent business harm.",
            }
            for index, observation_id in enumerate(observation_ids, 1) if matches
        ]
        judge.deduction(
            item_id, "triggered" if matches else "parse_failure" if any(judge._observation(key)["state"] == "parse_failure" for key in observation_ids) else "not_triggered", observation_ids,
            "Adopted business error found" if matches else "Unparsed content" if any(judge._observation(key)["state"] == "parse_failure" for key in observation_ids) else "No adopted business error found",
            occurrences,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    contract_path = args.contract.resolve()
    judge = ProgramJudge(load_contract(contract_path), args.artifact.resolve(), sha256(contract_path))
    evaluate(normalize(extract_raw(args.artifact.resolve()), judge), judge)
    result = judge.finish()
    result["semantic_judge"] = judge.semantic_verdict
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        args.json.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

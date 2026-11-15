#!/usr/bin/env python3
"""Program Judge adapter for the table-consistency audit report (Chinese Markdown).

Layer 1 extract_raw(): Markdown carrier -> headings, paragraphs, list items, table rows with line locators.
Layer 2 normalize():   finding spans (section, grouped blocks or table row) -> per-unit business observations
                       (object, conflict proposition, disposition, negation/candidate/rejection, spray),
                       trap claims, direction claims, section references, arithmetic statements, conclusion.
Layer 3 evaluate():    positive-item and deduction-item decisions from registered observations only.

Vocabularies, anchors and allowed locations below are frozen in rubric-contract.json (task_aliases).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from program_judge_runtime import Locator, ProgramJudge, load_contract, sha256
from adversarial_guards import blank_withdrawn, negated_before  # Withdrawn spans and polarity


import os as _os
PACKAGE_ROOT = Path(_os.environ.get("SKILL_PACKAGE_ROOT") or Path(__file__).resolve().parents[3])
CANONICAL_CONTRACT = PACKAGE_ROOT / "rubric-contract.json"

C_UNITS = ["C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08", "C09", "C10"]
SPAN_MAX_NONWS = 2000
SPRAY_TOPICS = 3

# ---------------------------------------------------------------- vocabularies (N02-N07)
DISP_CLEARED = r"已核[对查]|(核对|核查|复核|核算)(后|且)?一致|实际一致|实际成立|复算后成立|核算后成立|核对后成立|无误|无问题|未发现|不构成|非问题|误报|已排除|排除|核查通过|检查通过|校验通过|确认正确|核查正确|均正确|一致性良好|无需修改|无需处理|不需修改|确认一致|核实一致|经核查一致|自洽"
DISP_DOUBTFUL = r"存疑|待确认|需确认|需要确认|作者确认|有待确认|进一步确认|疑似|疑点|待核实|需核实|建议核实|不确定|潜在问题|可能存在|可能有误|低置信|提示项|观察项"
DISP_CONFIRMED = r"确认冲突|确认|冲突|错误|问题|不一致|缺陷|矛盾|必须|严重|不符"
LABEL_KEYS = r"判定|结论|定性|类型|状态|性质|分类|确定性|置信度|问题类型|审校结论|核查结论|处理意见"
REJECTION = (r"(?<![据按依由因凭])(该|此|上述|这一|这种|这个)(观点|说法|意见|判断|质疑|疑点|推断)[^。；;\n]{0,6}(不成立|有误|站不住|被驳回|予以驳回)"
             r"|予以驳回|不予采纳|属于误报|系误报|(有观点|有人|有意见|有审校意见|有反馈|有读者)[^。；;\n]{0,4}(认为|称|指出)")
CANDIDATE = r"候选(问题|项|发现|结论|解释|之一)|作为候选|未核实|未经核实|尚未核实|猜测|也许|或许|不确定是否|尚不确定|无法确定是否"
NEGATION = (r"不构成(冲突|矛盾|问题|错误|不一致)|并不(冲突|矛盾)|不(存在|是)(冲突|矛盾|错误|问题|不一致)"
            r"|并非(冲突|矛盾|错误|问题|不一致)|并无(冲突|矛盾|问题|不一致)|不冲突|不矛盾|未发现|没有发现"
            r"|核查无误|确认无误|经核查[^。；;\n]{0,10}(无误|正确|一致)|无需修改|无需处理|没有问题|无问题")
NEGATION_POS = NEGATION + r"|不判(为|作)?(冲突|矛盾|错误|问题)"
CUE = r"相反|相差|差距|差很多|冲突|不一致|矛盾|不符|差异|不同|对不上|前后不一|却|而|但|vs|≠|分别|不吻合|相悖|出入|不相符|有误|错误"
GAP_MARKERS = ["[待补充]", "【待补充】", "[placeholder]", "未提供", "材料未提供", "unspecified", "TBD", "待补充", "无法确定"]
HEDGE = (r"或|可能|若|如果|假如|核实|确认|待定|取决|假设|按[^。；;\n]{0,8}口径|以ASIC|同一口径|倘若"
         r"|(按|依|照|根据)[^。；;\n]{0,12}(公式|算法|计算方式|计算口径)")


def N(pattern: str) -> str:
    return rf"(?<![\d.]){pattern}(?![\d.])"


TOPICS = {
    "C01": [r"GPU", N(r"(200|250)")],
    "C02": [r"权重", N(r"75") + r"\s*%"],
    "C03": [r"检出率|假阳性率|阅片速度", N(r"(13|300|-23)") + r"\s*%|百分点"],
    "C04": [r"响应", r"30\s*分钟|≤\s*2\s*小时|4\s*小时"],
    "C05": [r"产线|图像分析", N(r"500") + r"\s*ms"],
    "C06": [N(r"800") + r"\s*(ms)?\s*[-~至到]\s*" + N(r"1200")],
    "C07": [r"客户覆盖率"],
    "C08": [r"FPGA", r"3\.2\s*M|\$\s*3\.2|2\.28|320\s*万|228\s*万"],
    "C09": [r"六层|6\s*层"],
    "C10": [r"满分\s*(10|十)|(10|十)\s*分制"],
    "U01": [r"98\.2"],
    "U02": [N(r"50") + r"\s*ms", N(r"100") + r"\s*ms"],
    "U03": [N(r"45") + r"\s*%", r"分配"],
    "U04": [r"5\s*[-~至]\s*8\s*TOPS|0\.83"],
    "U05": [r"基准", N(r"200") + r"\s*ms"],
    "U06": [r"倾向|决策因子"],
    "U07": [r"L1", r"L3"],
    "U08": [N(r"23") + r"\s*ms", N(r"45") + r"\s*ms"],
    "U09": [r"8\s*[-~至]\s*12\s*倍"],
    "U10": [r"漏诊率"],
    "X01": [r"通信开销"],
    "X02": [r"持有比例"],
    "X03": [r"利润分成"],
    "X04": [r"痛点", N(r"(120|68|52)")],
    "X05": [r"发生频率"],
    "X06": [r"发生概率"],
    "X07": [r"AUC"],
    "X08": [N(r"144")],
    "X09": [r"综合优先级"],
    "X10": [r"<\s*(100|50)\s*ms", r"<\s*(500|300)\s*ms"],
    "X11": [N(r"42") + r"\s*%", r"节点|GPU\s*小时"],
    "X12": [r"(功耗|频率)[^。；;\n]{0,20}(22\s*%?\s*[-~至]\s*41|15\s*%?\s*[-~至]\s*30)|DVFS|降低频率|功耗下降"],
}

# D01 trap claims (anchor, surface-anomaly claim) and the replay or reading that clears them.
TRAP_CLAIM = {
    "X01": (r"通信开销|92\s*\+\s*8|2\.2\.2[^。\n]{0,60}(互补|每行|逐行)", r"25\s*%|(不足|未达|不等于|不到|少于)\s*100|合计"),
    "X02": (r"持有比例|(企业|技术方)[^。\n]{0,14}(比例|合计)|30\s*[+/]\s*70|11\.1\.1[^。\n]{0,60}(每行|各行|逐行|按行|互补)", r"140|160|(超过|超出|大于|不等于)\s*100|合计"),
    "X03": (r"利润分成|15\.2[^。\n]{0,60}分成|分成比例[^。\n]{0,30}(层级|各自)", r"70\s*%|(不足|未达|不等于|不到|少于)\s*100|合计"),
    "X04": (r"痛点", r"120\s*%|(超过|超出|大于)\s*100|合计"),
    "X05": (r"发生频率|14[^。\n\d.]{0,10}风险(知识库|表)", r"40\s*%|(不足|未达|不等于|不到|少于)\s*100|合计"),
    "X06": (r"发生概率|32\s*[+/、]\s*45\s*[+/、]\s*23|14\.2[^。\n]{0,40}(概率|合计|风险)", r"合计|100\s*%|有误|错误|不一致"),
    "X07": (r"AUC", r"缺失|无法计算|无法得出|无基准|没有基准|空值|“-”|\"-\"|为\s*-"),
    "X08": (N(r"144"), r"有误|错误|不正确|不符|夸大|计算错|不成立|不一致"),
    "X09": (r"综合优先级|综合分|优先级[^。\n]{0,24}(0\.6|60\s*%)", r"有误|错误|不一致|不符|无法验证|无法复算|未说明|口径不明|不明确"),
    "X10": (r"<\s*(100|50)\s*ms", r"<\s*(500|300)\s*ms"),
    "X11": (N(r"42") + r"\s*%", r"62\.4|62\s*%|1000\s*节点|3\.20"),
    "X12": (r"(功耗|频率)[^。；;\n]{0,40}(22\s*%?\s*[-~至]\s*41|15\s*%?\s*[-~至]\s*30)|DVFS|降低频率|功耗下降", r"45\.2|52(\.0)?\s*%|超出|超过区间|不在区间|不符|不一致"),
}
TRAP_CLAIM_CUE = CUE + r"|不足|超过|超出|缺失|无法|未说明|不明确|夸大|不是|不在|只有|仅有|仅为"
# A trap is cleared only by the report's verdict. READING words name the accepted reading of the table;
# REPLAY numbers clear only inside a sentence that also states a consistent/correct verdict and no conflict verdict.
TRAP_READING = {
    "X01": r"按行|每行|行内|非分割|不是分割|计算效率\s*\+\s*通信开销",
    "X02": r"按行|每行|各行|逐行|成对|两侧|同一分割|互补",
    "X03": r"独立|各自|非分割|不是分割|费率|各层级|不(要求|需要)合计",
    "X04": r"多选",
    "X05": r"独立|非分割|不是分割|发生率",
    "X06": r"(?!)",
    "X07": r"相对[^。；;\n]{0,8}0\.72|以[^。；;\n]{0,8}0\.72[^。；;\n]{0,4}为[^。；;\n]{0,4}基准|基准为[^。；;\n]{0,12}0\.72|共同基准|共同基数|基数为[^。；;\n]{0,12}0\.72",
    "X08": r"单位换算后[^。；;\n]{0,6}(正确|一致|成立)",
    "X09": r"(?!)",
    "X10": r"场景|口径不同|不同口径|分属|不同指标|不是同一",
    "X11": r"超过\s*500\s*节点[^。；;\n]{0,20}(条件|口径)|(条件|口径)[^。；;\n]{0,6}超过\s*500\s*节点|按[^。；;\n]{0,6}500\s*节点",
    "X12": r"相邻|逐档",
}
TRAP_REPLAY = {
    "X01": r"92\s*\+\s*8", "X02": r"30\s*\+\s*70", "X03": r"(?!)", "X04": r"(?!)", "X05": r"(?!)",
    "X06": r"32\s*[+/、]\s*45\s*[+/、]\s*23|14\.2[^。\n]{0,30}合计[^。\n]{0,8}100", "X07": r"0\.72", "X08": r"2880|144\s*倍",
    "X09": r"0\.6[^。；;\n]{0,20}0\.4|60\s*%[^。；;\n]{0,20}40\s*%|4\.56",
    "X10": r"(?!)", "X11": r"41\.8|500\s*节点[^。；;\n]{0,30}4\.95|8\.50[^。；;\n]{0,30}4\.95",
    "X12": r"22\.6|29\.2|26\.0|35\.1|平衡模式[^。；;\n]{0,20}(降|下降)",
}
CONSISTENT_VERDICT = r"算对|计算正确|(能|可|均可|都能|都可)[^。；;\n]{0,4}(复算|验算|算出)|一致|正确|无误|成立|落入|在[^。；;\n]{0,8}区间内|符合|吻合|相符|可复算|合理|没有问题|无问题"
CONFLICT_VERDICT = r"不是|不在|超出|超过区间|不符|不一致|不成立|矛盾|冲突|有误|错误|对不上|不相符"


def verdict_consistent(sentence: str) -> bool:
    cleared = re.sub(r"不构成(冲突|矛盾|问题|错误|不一致)|并非(冲突|矛盾|错误|不一致)|不存在(冲突|矛盾|问题|不一致)|并不(冲突|矛盾)", "无误", sentence)
    return has(CONSISTENT_VERDICT, re.sub(r"不一致|不符|不相符|不成立", "", cleared)) and not has(CONFLICT_VERDICT, cleared)


def trap_cleared(unit: str, text: str) -> bool:
    if has(TRAP_READING[unit], text):
        return True
    return any(has(TRAP_REPLAY[unit], s) and verdict_consistent(s) for s in sentences(text))


# D04 allowed locations: the sections that hold the tables and lead or body sentences of each confirmed unit.
ALLOWED_SECTIONS = {
    "C01": ({"1.2", "1.2.1"}, r"解决方案框架|芯片厂商的角色|芯片厂商的算力支持"),
    "C02": ({"5.1", "5.1.2"}, r"联合实验室|标准化测试流程"),
    "C03": (set(), r"行业应用方的场景落地"),
    "C04": ({"10.2", "10.2.2"}, r"持续运营与技术支持|故障排查与维护|快速响应机制"),
    "C05": ({"4.2", "4.2.1"}, r"解决方案设计与验证|原型开发与测试"),
    "C06": ({"3.1", "3.1.1"}, r"模型选型与定制|通用大模型与行业专用模型"),
    "C07": ({"9.2"}, r"金融行业"),
    "C08": ({"2.1", "2.1.2"}, r"边缘计算芯片|芯片选型与适配"),
    "C09": ({"7.2", "7.2.1"}, r"GDPR|合规性与审计"),
    "C10": ({"3.1"}, r"模型选型与定制"),
}
HEADINGS = {
    "1.1": "背景与目标", "1.1.1": "AI落地", "1.1.2": "全链路合作", "1.2": "解决方案框架", "1.2.1": "芯片厂商的角色",
    "1.2.2": "大模型公司的角色", "1.2.3": "行业应用方的角色", "2.1": "芯片选型与适配", "2.1.1": "高性能计算芯片",
    "2.1.2": "边缘计算芯片", "2.2": "算力优化与部署", "2.2.1": "芯片级性能优化", "2.2.2": "分布式计算支持",
    "3.1": "模型选型与定制", "3.1.1": "通用大模型与行业专用模型", "3.1.2": "模型轻量化与压缩技术", "3.2": "模型训练与调优",
    "3.2.1": "数据标注与清洗", "3.2.2": "迁移学习与微调", "4.1": "需求分析与场景定义", "4.1.1": "行业痛点梳理",
    "4.1.2": "场景优先级排序", "4.2": "解决方案设计与验证", "4.2.1": "原型开发与测试", "4.2.2": "性能评估与迭代",
    "5.1": "联合实验室与测试平台", "5.1.1": "硬件与软件集成", "5.1.2": "标准化测试流程", "5.2": "技术共享与知识产权管理",
    "5.2.1": "开源与闭源策略", "5.2.2": "专利与版权保护", "6.1": "芯片与模型的适配", "6.1.1": "硬件感知的模型优化",
    "6.1.2": "模型驱动的芯片设计", "6.2": "实时性与能效平衡", "6.2.1": "低延迟优化", "6.2.2": "能耗管理",
    "7.1": "数据脱敏与加密", "7.1.1": "数据传输安全", "7.1.2": "数据存储安全", "7.2": "合规性与审计",
    "7.2.1": "GDPR等法规遵从", "7.2.2": "第三方审计机制", "8.1": "边缘端模型部署", "8.1.1": "轻量化模型适配",
    "8.1.2": "边缘设备管理", "8.2": "云端协同计算", "8.2.1": "数据同步与更新", "8.2.2": "动态负载均衡",
    "9.1": "医疗行业", "9.1.1": "医学影像分析", "9.1.2": "智能诊断辅助", "9.2": "金融行业", "9.2.1": "风控模型优化",
    "9.2.2": "智能投顾", "10.1": "模型迭代与升级", "10.1.1": "自动化训练管道", "10.1.2": "版本控制与回滚",
    "10.2": "故障排查与维护", "10.2.1": "实时监控系统", "10.2.2": "快速响应机制", "11.1": "合作模式设计",
    "11.1.1": "联合研发模式", "11.1.2": "技术授权模式", "11.2": "成本控制与收益最大化", "11.2.1": "资源复用策略",
    "11.2.2": "规模化效应", "12.1": "行业标杆案例推广", "12.1.1": "成功案例展示", "12.1.2": "客户口碑传播",
    "12.2": "开发者社区建设", "12.2.1": "工具链与SDK开放", "12.2.2": "技术培训与支持", "13.1": "行业标准推动",
    "13.1.1": "参与标准制定", "13.1.2": "推动认证体系", "13.2": "政策与法规对接", "14.1": "技术风险",
    "14.1.1": "冗余设计", "14.1.2": "容灾备份", "14.2": "合作风险", "14.2.1": "合同与协议管理",
    "14.2.2": "退出机制设计", "15.1": "技术演进方向", "15.2": "生态扩展计划",
}
CHAPTER_REF = re.compile(r"(?:§\s*|第\s*)(\d{1,2})(?![\d.])(?:\s*章)?")


def chapter_refs(text: str) -> set[str]:
    """Read single chapter references and Chinese enumerated chapter lists."""
    found = {match.group(1) for match in CHAPTER_REF.finditer(text)}
    for match in re.finditer(r"第\s*((?:\d{1,2}\s*[、,，和及与]\s*)+\d{1,2})\s*章", text):
        found.update(re.findall(r"\d{1,2}", match.group(1)))
    return found
ALLOWED_CHAPTERS = {"C01": {"1", "2"}, "C02": {"5"}, "C03": {"4"}, "C04": {"10"}, "C05": {"4"}, "C06": {"3"}, "C07": {"9"}, "C08": {"2"}, "C09": {"7"}, "C10": {"3"}}
SECTION_REF = re.compile(r"(?<![\d.A-Za-z])(\d{1,2}(?:\.\d{1,2}){1,2})(?![\d.])")
NOT_SEND = (r"(不建议|不宜|不应|不能|不可|暂不|暂缓|不得|无法)[^。；;，,\n]{0,12}(提交|发送|发出|交付|外发|发给客户|交给客户|发布|对外)"
            r"|(修正|修改|修订|更正|处理|整改)[^。；;\n]{0,6}(后|之后|完毕后|完成后)[^。；;\n]{0,4}(再|方可|才能|才可|方能)[^。；;\n]{0,4}(提交|发送|发出|交付|对外|发布)"
            r"|不能按(现状|原样)|不可原样|暂停(发送|提交)"
            r"|先[^。；;\n]{0,30}(修正|修改|处理|更正)[^。；;\n]{0,40}再[^。；;\n]{0,6}(提交|发送|发出|交付|对外|发给)")
SEND_AS_IS = r"(?<![不暂勿未])(可以|可|能够|同意)(直接|按原样|原样)?(对外)?(提交|发送|发出|交付|外发|发布|发给客户)"
SEND_CONDITION = r"修正|修改|修订|处理|确认后|完成后|之后|前提|若|如果|待|前"
NO_ISSUE_GLOBAL = r"(全文|全部表格|所有表格|97\s*张|整体)[^。；;\n]{0,20}(未发现|没有发现|不存在)[^。；;\n]{0,10}(问题|冲突|不一致|错误)"
NEG_ANCHOR = {
    "C01": N(r"(200|250)"), "C02": r"75|权重", "C03": r"提升幅度|百分点|口径", "C04": r"响应",
    "C05": N(r"(500|200)"), "C06": r"800|1200|150", "C07": r"300|客户覆盖率", "C08": r"FPGA|3\.2|2\.28",
    "C09": r"六层|6\s*层", "C10": r"满分|10\s*分",
}
DIRECTION_RULES = {
    "C01": (r"250\s*(TOPS)?[^，,。；;\n]{0,10}(为离群|是离群|有误|错误|笔误|偏高|被高估|高估|多算|不正确)|(应|统一)(改|修正|更正)?为\s*200\s*TOPS|以\s*200\s*(TOPS)?\s*为准",
            r"200\s*(TOPS)?[^，,。；;\n]{0,10}(为离群|是离群|有误|错误|笔误|偏低|被低估|低估|少算|不正确)|(应|统一)(改|修正|更正)?为\s*250|以\s*250\s*(TOPS)?\s*为准"),
    "C04": (r"(前表|问题等级表|1\s*小时|4\s*小时)[^，,。；;\n]{0,20}(为离群|是离群|有误|错误|笔误|不正确|应改为|应修改为|过长|偏长|过于宽松)|以\s*(后表|10\.2(\.2)?|≤?\s*30\s*分钟|故障等级表)\s*为准",
            r"(后表|故障等级表|≤?\s*30\s*分钟|≤?\s*2\s*小时)[^，,。；;\n]{0,20}(为离群|是离群|有误|错误|笔误|不正确)|以\s*(前表|1\s*小时|问题等级表)\s*为准"),
    # "ASIC 行按同一口径…不成立" (the replaying side declared the failing one) is a reversed direction too
    "C08": (r"ASIC[^，,。；;\n]{0,20}(有误|错误|不符|不一致|偏低|偏高|不成立|不正确|被低估|低估|少算|漏算|未计入|没有计入|漏计|不完整)"
            r"|ASIC\s*行[^，,。；;\n]{0,40}不成立",
            r"FPGA[^，,。；;\n]{0,20}(有误|错误|不符|不一致|偏高|不成立|不正确|被高估|高估|多算|虚高)"
            r"|FPGA\s*行[^，,。；;\n]{0,40}不成立"),
}
CORRECTION = r"应改为|应修正为|应更正为|改为|修正为|更正为|应为|实际应为|正确值应为|正确值为|应调整为"
FABRICATION_RULES = {"C08": (r"FPGA", r"(\d+(\.\d+)?)\s*(M|百万|万)"), "C07": (r"客户覆盖率", r"\d+(\.\d+)?\s*%")}
# C02 - the Materials only establish that the weights sum to 75%; which dimension the
# missing 25% belongs to is not in the document (golden: "要么漏写一个维度，要么现有权重需重新分配"). A sentence
# that names a specific dimension as the missing 25%, without a hedge, is a definitive addition the Materials cannot support.
C02_GENERIC = r"其余|剩余|缺失|缺少|第四|第\s*4|一个|一项|某|该|相应|对应|其他|其它|未列|未知|哪|何|新的|新增|额外|权重|比例|百分点|部分|维度$"
C02_NAMED = (r"(?:缺失|缺少|缺|遗漏|漏写|漏掉|剩余|其余)的?\s*25\s*%\s*(?:即|就是|应为|即为|属于|对应|是)\s*[「“\"]?([一-鿿A-Za-z]{2,10})[」”\"]?"
             r"|(?:应补为|应补充为|补为|补充为|应补上|补上|应增加|应补充)\s*[「“\"]?([一-鿿A-Za-z]{2,10})[」”\"]?\s*(?:维度)?\s*[:：]?\s*25\s*%")
C02_HEDGE = r"或|可能|若|如果|假如|例如|比如|待|作者|确认|核实|建议作者|不能|无法|不得|未说明|未声明|推定|推断|猜测"


def c02_named_fill(sentence: str) -> bool:
    """True when a sentence asserts which dimension fills the missing 25% of the 5.1 weight column."""
    if has(C02_HEDGE, sentence):
        return False
    for m in re.finditer(C02_NAMED, sentence):
        name = (m.group(1) or m.group(2) or "").strip()
        if name and not re.search(C02_GENERIC, name):
            return True
    return False


# A string quoted as the source's own words ("正文写「…」", "表记“…”") that the
# Materials do not contain. Only numeric quotes introduced by a source-attribution verb are checked;
# recommendations ("建议写明「…」", "应改为「…」") are not quotes of the source. A quote is supported when its
# normalized text occurs in the Materials, or when one Materials line (a table row together with its header
# row) holds every number and Latin token of the quote and at least 60% of its CJK bigrams - table cells and
# light paraphrase are therefore not charged.
QUOTE_SPAN = re.compile(r"[「“\"]([^「」“”\"\n]{4,120})[」”\"]")
QUOTE_CUE = re.compile(r"(写|写道|写作|记|记为|记作|称|载|载明|表述为|原文为|原句为)[为成是：:，,]?\s*$")
QUOTE_RECOMMEND = re.compile(r"(建议|宜|应|应当|改|可|请|或|需|须|需要|注明|写明|改写|统一)[^「“\"。；;]{0,4}$")
MATERIALS_MD = Path(__file__).resolve().parents[1] / "materials" / "AI全链路商业化破局解决方案.md"


def _qnorm(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", unicodedata.normalize("NFKC", text).replace("**", "").replace("`", "")).lower()


class MaterialsIndex:
    def __init__(self, path: Path):
        self.ok = path.is_file()
        raw = path.read_text(encoding="utf-8") if self.ok else ""
        self.flat = _qnorm(raw)
        self.lines, header = [], None
        for line in raw.split("\n"):
            if not line.strip():
                header = None
                continue
            t = unicodedata.normalize("NFKC", line).replace("**", "").replace("`", "").lower()
            if t.lstrip().startswith("|"):
                header = header or t
                self.lines.append(t + " " + header)
            else:
                header = None
                self.lines.append(t)

    def supports(self, quote: str) -> bool:
        frags = [_qnorm(x) for x in re.split(r"…+|\.{3,}|⋯", quote)]
        frags = [x for x in frags if len(x) >= 4]
        if frags and all(x in self.flat for x in frags):
            return True
        q = unicodedata.normalize("NFKC", quote).lower()
        nums = re.findall(r"(?<![a-z\d.])\d+(?:\.\d+)?", q)
        words = re.findall(r"[a-z][a-z0-9]{1,}", q)
        cjk = "".join(re.findall(r"[一-鿿]", q))
        bigrams = {cjk[i:i + 2] for i in range(len(cjk) - 1)}
        for line in self.lines:
            if all(re.search(r"(?<![\d.])" + re.escape(n) + r"(?!\d)", line) for n in nums) and all(w in line for w in words):
                if not bigrams or sum(b in line for b in bigrams) / len(bigrams) >= 0.6:
                    return True
        return False


def unsupported_quotes(text: str, index: "MaterialsIndex") -> list:
    found = []
    if not index.ok:
        return found
    for line in text.split("\n"):
        for m in QUOTE_SPAN.finditer(line):
            quote, before = m.group(1), line[max(0, m.start() - 12):m.start()]
            if not QUOTE_CUE.search(before) or QUOTE_RECOMMEND.search(QUOTE_CUE.sub("", before)):
                continue
            if not re.search(r"\d", quote):
                continue
            if not index.supports(quote):
                found.append(quote)
    return found


# Finding units, overgraded items, over-reporting and false clearance
CONTAINER_EXCLUDE = r"范围|方法|说明|结论|摘要|总结|总体|处置|建议|优先级|附录|概述|概览"
LETTER_ID = r"^\s*(\*\*)?\s*([A-Za-z]{1,3}\s?-?\d{1,2}(?!\d)|问题\s*\d{1,2})"
NUMERIC_ID = r"^\s*(\*\*)?\s*\d{1,2}\s*[.、．:：)）](?!\d)"
PROBLEM_CUE = CUE + r"|问题|缺少|缺失|混用|不清|不明|不匹配|对不上|无法|乱码|占位|不严谨|歧义|不对应|不规范|没有依据|无依据|建议|应改|需改"
U_PRED = {
    "U01": [r"98\.2", r"结节", r"9[45]\s*%"],
    "U02": [r"<\s*100\s*ms", r"<\s*50\s*ms", r"端侧|边缘设备|8\.1|12\.2|框架|开发者"],
    "U03": [r"收益|分成|分配", N(r"45") + r"\s*%", r"50\s*%?\s*[-~至]\s*70|" + N(r"(50|70)") + r"\s*%"],
    "U04": [r"5\s*[-~至]\s*8", r"0\.83"],
    "U05": [r"(?=[^。；;\n]*基准)(?=[^。；;\n]*(?<![\d.])200\s*ms)(?=[^。；;\n]*(?<![\d.])(500|300)\s*ms)(?=[^。；;\n]*(宽于|高于|超过|超出|不一致|冲突|矛盾|不符|放宽|宽松))"],
    "U06": [N(r"200") + r"\s*ms", r"1\s*s(?![a-z])|1\s*秒", r"边缘", r"云端"],
    "U07": [r"L1", r"L3", r"L2"],
    "U08": [N(r"23") + r"\s*ms", N(r"45") + r"\s*ms"],
    "U09": [r"8\s*[-~至]\s*12\s*倍", r"10\s*[-~至]\s*50|12\.5|37\.5|" + N(r"38")],
    "U10": [r"漏诊率", r"5\s*[-~至]\s*8"],
    "E-T75": [N(r"150"), r"35\s*%", r"线索"],
    "E-B05": [r"采样|采集", r"1\s*秒", r"10\s*秒"],
    "E-B06": [r"85\s*(℃|°\s*C)", r"75\s*(℃|°\s*C)"],
    "E-B10": [r"0\.02", r"0\.05"],
    "E-B12": [r"参数量", r"量化|蒸馏|8\s*bit"],
    "E-B13": [r"区块链存证|性能提升[^。\n]{0,60}(防篡改|零知识)|(防篡改|零知识)[^。\n]{0,60}性能提升"],
}
# aspects of the complete Golden proposition, author-confirmation items and cleared anomalies
IMPACT = r"(影响|后果)\s*[:：]|(会|将|可能|直接)[^。\n]{0,8}(影响|引发|导致)|无法(据此)?(计算|得出|支撑|判断|确定)"
ASPECT_WEIGHTS = {"core": 0.55, "replay": 0.15, "basis": 0.1, "impact": 0.1}
ASPECTS = {
    "C01": {"basis": r"功耗[^。\n]{0,20}(300|相同|一致|同为)|同为\s*300|0\.83|250\s*[÷/]\s*300", "impact": IMPACT},
    "C03": {"replay": r"95\s*[-−–减]\s*82|60\s*[-−–减]\s*15", "basis": r"15\.9|45\s*(个)?百分点|同一(列|张表|表)", "impact": IMPACT + r"|误读|劣化"},
    "C04": {"basis": r"(紧急|P0)[^。\n]{0,30}(一致|相同|均为|都是)|同一套|15\s*分钟[^。\n]{0,20}一致", "impact": IMPACT + r"|履约|争议|承诺"},
    "C07": {"basis": r"144|30\.6|另(外)?两行|同表[^。\n]{0,20}(可|能)[^。\n]{0,6}复算|对照"},
    "C08": {"replay": r"220\s*[×xX*]\s*10,?000|220\s*[×xX*]\s*(1\s*万|10K)", "basis": r"ASIC[^。\n]{0,40}(1\.7|一致|成立|自洽|吻合)", "impact": IMPACT + r"|夸大|选型"},
    "C10": {"basis": r"权重|任务准确率|8\.2|超出[^。\n]{0,6}(10|十)|无法加权", "impact": IMPACT + r"|综合(得)?分"},
    "C02": {"replay": r"30\s*%?[^。\n+]{0,4}\+[^。\n+]{0,12}25\s*%?[^。\n+]{0,4}\+[^。\n+]{0,14}20", "basis": r"(其他|其它|另|同文档|本文|文中|文档)[^。\n]{0,30}权重[^。\n]{0,30}100|权重表[^。\n]{0,40}(均|都)[^。\n]{0,12}100", "impact": IMPACT},
    "C05": {"basis": r"环节|一步|单步|端到端|整体|全流程|包含推理|整个"},
    "C06": {"basis": r"(无一|全部|都|均)[^。\n]{0,12}(低于|不在|之外|落入|高于)"},
    "C09": {"basis": r"例如|包括|示例性|限定", "impact": IMPACT},
}
# positive items scored from confirmed units, author-confirmation items and cleared anomalies
C_POSITIVE = {"P01": "C01", "P02": "C02", "P03": "C03", "P04": "C04", "P05": "C05", "P06": "C06", "P07": "C07", "P08": "C08", "P09": "C09", "P10": "C10"}
U_POSITIVE = {"P12": "U01", "P13": "U02", "P14": "U03", "P17": "U06", "P21": "U10"}
X_POSITIVE = {"P28": "X07", "P30": "X09"}
U_CREDIT_PRED = {item: U_PRED[item] for item in U_POSITIVE.values()}
U_READING = {
    "U01": r"准确率[^。\n]{0,24}检出率|检出率[^。\n]{0,24}准确率|微小|口径|指标(名|名称)?[^。\n]{0,6}不同|范围",
    "U02": r"层级|验收|优化目标|不同(设备|对象|场景|档次)|P99|平均",
    "U03": r"示例|参与方[^。\n]{0,10}(不同|不相同|不一致)|分类|不等于|两套|不同(模式|合作)",
    "U06": r"倾向|其他(决策)?因子|划分|雾|中间",
    "U10": r"病种|一般场景|典型值|难例|可达|上限",
}
# D11 required-unit gate: audit objects the brief requires and every complete report covers - the sections
# holding the audited tables (cited as a section number), three table objects named by their anchors, and
# the send decision. Each unit absent from the report is one damage instance.
REQUIRED_SECTIONS = ["2.1", "3.1", "5.1", "6.2", "9.2"]
REQUIRED_OBJECTS = ["C03", "C07", "X08"]
SECTION_CITE = re.compile(r"(?<![\d.A-Za-z$¥])(\d{1,2})\.(\d{1,2})(\.\d{1,2})?"
                          r"(?![\d.]|\s*(%|分|倍|ms|TOPS|W|万|亿|元|x|×|小时|秒|M|K|B|个|pp))")
# D12 figures: the brief excludes figures, so a figure's value used as one side of a reported conflict is charged.
FIGURE = r"图片|架构图|示意图|流程图|图中|图示|配图|插图|图\s*\d"
FIGURE_EXCLUDED = r"不在[^。；;\n]{0,8}范围|范围[^。；;\n]{0,4}(外|之外)|未纳入|不纳入|未审计|不审计|未核对|不核对|未检查|排除|除外|不含|不包括|占位|略去|忽略|不涉及"
FIGURE_CONFLICT = r"冲突|不一致|不符|矛盾|对不上|相差|差异|不吻合|相悖|出入"
# D13 extra deliverables: files beside the deliverable that the brief does not ask for.
# The harness writes manifest.json beside the deliverable; it is not agent output.
# Hidden files (".*") and directories/caches are skipped in the scan below.
NOT_DELIVERABLES = {"program.json", "manifest.json"}
C05_CLEARED_LOOSE = [r"制造", N(r"500") + r"\s*ms", N(r"200") + r"\s*ms", r"4\.2\.1|测试|产线|图像分析"]


def fold(text: str) -> str:
    """N01: NFKC, drop Markdown emphasis and code ticks, remove thousands separators between digits."""
    # Thousands separators are ASCII commas inside digit groups; strip them before NFKC so a full-width
    # enumeration comma after a decimal replay never merges two numbers.
    text = re.sub(r"(?<![\d.])(\d{1,3})((?:,\d{3})+)(?![\d.,])", lambda m: m.group(1) + m.group(2).replace(",", ""), text)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    return (text.replace("−", "-").replace("–", "-").replace("—", "-").replace("～", "~")
            .replace("毫秒", "ms"))


def nonws(text: str) -> int:
    return len(re.sub(r"\s", "", text))


def has(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.I) is not None


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"[。；;!?！？\n]", text) if s.strip()]


def clauses(text: str) -> list[str]:
    return [s for s in re.split(r"[。；;!?！？\n，,]", text) if s.strip()]


def cited_sections(text: str) -> set:
    """Two-level section numbers the text cites: a three-level heading number, or a two-level one followed by
    节/章 or the heading title, or preceded by 第/§/见/于/在. Numbers followed by a unit are values."""
    found = set()
    for m in SECTION_CITE.finditer(text):
        two = f"{m.group(1)}.{m.group(2)}"
        if two not in HEADINGS:
            continue
        after, before = text[m.end():m.end() + 14], text[max(0, m.start() - 2):m.start()]
        if m.group(3) or re.match(r"\s*(节|章|小节)", after) or after.strip().startswith(HEADINGS[two][:2]) \
                or re.search(r"(第|§|见|于|在)\s*$", before):
            found.add(two)
    return found


# ---------------------------------------------------------------- layer 1: raw carrier
@dataclass
class Block:
    kind: str
    start: int
    end: int
    text: str
    indent: int = 0
    header: list = field(default_factory=list)
    cells: list = field(default_factory=list)


@dataclass
class Heading:
    level: int
    text: str
    line: int
    blocks: list = field(default_factory=list)
    chain: list = field(default_factory=list)


LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.、)）])\s+(.*)$")


def extract_raw(artifact: Path) -> dict:
    try:
        text = artifact.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {"artifact": artifact, "status": "parse_failure", "error": str(exc), "headings": []}
    # Paragraphs, list items and table rows the author disowns ("以下并非本方主张：",
    # "疑似（待核，尚未采纳）：", quote-and-reject) are blanked before any item predicate sees them.
    text = blank_withdrawn(text)
    lines = text.splitlines()
    root = Heading(0, "", 0)
    headings, stack, current = [root], [root], root
    i, in_code = 0, False
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            i += 1
            continue
        if in_code or not stripped:
            i += 1
            continue
        match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if match:
            level = len(match.group(1))
            while len(stack) > 1 and stack[-1].level >= level:
                stack.pop()
            current = Heading(level, match.group(2).strip(), i + 1)
            current.chain = [h.text for h in stack if h.level > 0] + [current.text]
            stack.append(current)
            headings.append(current)
            i += 1
            continue
        if stripped.startswith("|"):
            parsed = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = lines[i].strip()
                if not re.fullmatch(r"\|?(\s*:?-{2,}:?\s*\|)+\s*:?-*:?\s*\|?", row):
                    parsed.append((i + 1, [c.strip() for c in re.split(r"(?<!\\)\|", row.strip("|"))]))
                i += 1
            if parsed:
                header = parsed[0][1]
                for number, cells in parsed[1:]:
                    labelled = "；".join(f"{h}：{c}" if h else c for h, c in zip(header, cells))
                    current.blocks.append(Block("table_row", number, number, labelled, header=header, cells=cells))
                if len(parsed) == 1:
                    current.blocks.append(Block("paragraph", parsed[0][0], parsed[0][0], " ".join(header)))
            continue
        match = LIST_RE.match(line)
        if match:
            block = Block("list_item", i + 1, i + 1, match.group(3), indent=len(match.group(1).expandtabs(2)))
            current.blocks.append(block)
            i += 1
            while i < len(lines) and lines[i].strip() and lines[i].startswith(" ") and not LIST_RE.match(lines[i]) \
                    and not lines[i].strip().startswith(("#", "|", "```")):
                block.text += " " + lines[i].strip()
                block.end = i + 1
                i += 1
            continue
        start, buffer = i, []
        while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith(("#", "|", "```")) and not LIST_RE.match(lines[i]):
            buffer.append(lines[i].strip())
            i += 1
        current.blocks.append(Block("paragraph", start + 1, i, " ".join(buffer)))
    return {"artifact": artifact, "status": "ok", "headings": headings, "text": text}


# ---------------------------------------------------------------- layer 2: normalized observations
def topics_of(text: str) -> set:
    folded = fold(text)
    return {unit for unit, patterns in TOPICS.items() if all(has(p, folded) for p in patterns)}


@dataclass
class Span:
    span_id: str
    kind: str
    start: int
    end: int
    raw: str
    chain: list
    blocks: list
    text: str = ""
    topics: set = field(default_factory=set)
    disposition: str = "reported"
    spray: bool = False
    rejected: bool = False
    candidate: bool = False


def label_disposition(value: str):
    value = fold(value)
    if has(DISP_CLEARED, value):
        return "cleared"
    if has(DISP_DOUBTFUL, value):
        return "doubtful"
    if has(DISP_CONFIRMED, value):
        return "reported"
    return None


def span_disposition(span: Span) -> str:
    """R01: explicit row label, then explicit in-span label, then the nearest heading carrying a disposition."""
    for block in span.blocks:
        if block.kind == "table_row":
            for head, cell in zip(block.header, block.cells):
                if has(LABEL_KEYS, fold(head)) and nonws(cell) <= 12:
                    found = label_disposition(cell)
                    if found:
                        return found
    head_text = fold(span.raw[:160])
    match = re.search(rf"(?:{LABEL_KEYS})\s*[:：]\s*([^\s，。；|]{{1,10}})", head_text)
    if match:
        found = label_disposition(match.group(1))
        if found:
            return found
    match = re.match(r"^\s*[\[【(（]\s*([^\]】)）]{1,8})\s*[\]】)）]", head_text)
    if match:
        found = label_disposition(match.group(1))
        if found:
            return found
    for heading in reversed(span.chain):
        found = label_disposition(heading)
        if found in ("cleared", "doubtful"):
            return found
    return "reported"


def build_spans(headings: list) -> list:
    """R00: one span per heading section when it binds at most two objects, else grouped blocks and table rows."""
    spans = []
    for h_index, heading in enumerate(headings):
        if not heading.blocks:
            continue
        merged = []
        for block in heading.blocks:
            if block.kind == "list_item" and merged and merged[-1].kind == "list_item" and block.indent > merged[-1].indent:
                merged[-1] = Block("list_item", merged[-1].start, block.end, merged[-1].text + " " + block.text, indent=merged[-1].indent)
            else:
                merged.append(Block(block.kind, block.start, block.end, block.text, block.indent, block.header, block.cells))
        section_raw = heading.text + "\n" + "\n".join(b.text for b in merged)
        if len(topics_of(section_raw)) <= 2 and nonws(section_raw) <= SPAN_MAX_NONWS:
            spans.append(Span(f"H{h_index}", "section", heading.line or merged[0].start, merged[-1].end, section_raw, heading.chain, merged))
            continue
        group, group_topics, counter = [], set(), 0

        def flush():
            nonlocal group, group_topics, counter
            if group:
                counter += 1
                spans.append(Span(f"H{h_index}.G{counter}", "block_group", group[0].start, group[-1].end,
                                  "\n".join(b.text for b in group), heading.chain, list(group)))
            group, group_topics = [], set()

        for block in merged:
            # A short bold or ID-numbered title paragraph starts a new finding group
            if block.kind == "paragraph" and group and nonws(block.text) <= 60 and \
                    re.match(r"^\s*(\*\*|[A-Za-z]{0,2}\d{1,2}\s*[.、．:：]|问题\s*\d)", block.text):
                flush()
            if block.kind == "table_row":
                flush()
                spans.append(Span(f"H{h_index}.R{block.start}", "table_row", block.start, block.end, block.text, heading.chain, [block]))
                continue
            block_topics = topics_of(block.text)
            # A substantive topic-free paragraph following a finding is a new
            # summary/recommendation block, not evidence for that finding.
            if group and group_topics and not block_topics and block.kind == "paragraph" and nonws(block.text) > 60:
                flush()
            if group and block_topics and group_topics and not block_topics <= group_topics:
                flush()
            group.append(block)
            group_topics |= block_topics
        flush()
    for span in spans:
        span.text = fold(span.raw)
        span.topics = topics_of(span.raw)
        span.spray = len(span.topics) >= SPRAY_TOPICS or nonws(span.raw) > SPAN_MAX_NONWS
        span.rejected = has(REJECTION, span.text)
        span.candidate = has(CANDIDATE, span.text)
        span.disposition = span_disposition(span)
    return spans


LEAD_DOUBTFUL = r"^\s*(需作者确认|需要作者确认|请作者确认|待作者确认|需作者核实|待确认|存疑)[^。；;\n:：]{0,30}[:：]"
LEAD_CLEARED = r"^\s*(已核对无问题|已核对|已核查|核对无问题|复核通过|经核查无误|核查无误|复核后一致|核查后一致|无需修改)[^。；;\n:：]{0,20}[:：]"


def match_disposition(span: Span, unit: str) -> str:
    """A block led by a doubtful or cleared label phrase decides the disposition of the propositions in it."""
    for block in span.blocks:
        text = fold(block.text)
        if c_components(unit, text) or has(NEG_ANCHOR[unit], text):
            if has(LEAD_DOUBTFUL, text):
                return "doubtful"
            if has(LEAD_CLEARED, text):
                return "cleared"
    return span.disposition


def strip_paren(text: str) -> str:
    return re.sub(r"[（(][^）)]*[）)]", "", text)


def build_units(headings: list) -> list:
    """R10: finding units = letter-ID headings, numeric-ID headings below level 2, bold or ID title paragraphs with the
    blocks that follow them, and ID-first-cell table rows; containers about scope, conclusion or disposition are skipped."""
    units = []

    def make(uid, blocks, chain, title=""):
        raw = (title + "\n" if title else "") + "\n".join(b.text for b in blocks)
        unit = Span(uid, "finding_unit", blocks[0].start, blocks[-1].end, raw, chain, blocks)
        unit.text = fold(raw)
        unit.rejected, unit.candidate = has(REJECTION, unit.text), has(CANDIDATE, unit.text)
        unit.disposition = span_disposition(unit)
        lead = fold(blocks[0].text)
        if has(LEAD_DOUBTFUL, lead):
            unit.disposition = "doubtful"
        elif has(LEAD_CLEARED, lead):
            unit.disposition = "cleared"
        units.append(unit)

    for h_index, heading in enumerate(headings):
        if not heading.blocks:
            continue
        title = fold(heading.text)
        is_unit = has(LETTER_ID, title) or (has(NUMERIC_ID, title) and heading.level >= 3)
        containers = heading.chain[:-1] if is_unit else heading.chain
        if any(has(CONTAINER_EXCLUDE, strip_paren(fold(c))) for c in containers):
            continue
        if is_unit:
            make(f"U{h_index}", heading.blocks, heading.chain, heading.text)
            continue
        current = []
        for block in heading.blocks:
            text = block.text.strip()
            whole_bold = re.fullmatch(r"\*\*.+?\*\*[:：]?", text) is not None and nonws(text) <= 200
            id_para = block.kind == "paragraph" and nonws(text) <= 80 and (has(LETTER_ID, fold(text)) or has(NUMERIC_ID, fold(text)))
            if block.kind == "paragraph" and (whole_bold or id_para):
                if current:
                    make(f"U{h_index}.{current[0].start}", current, heading.chain)
                current = [block]
            elif block.kind == "table_row" and block.cells and re.fullmatch(r"[A-Za-z]{0,3}\s?-?\d{1,2}", fold(block.cells[0]).strip()):
                if current:
                    make(f"U{h_index}.{current[0].start}", current, heading.chain)
                    current = []
                make(f"U{h_index}.R{block.start}", [block], heading.chain)
            elif current:
                current.append(block)
        if current:
            make(f"U{h_index}.{current[0].start}", current, heading.chain)
    return units


def negated_for(span: Span, anchor: str, positive: bool = False) -> bool:
    pattern = NEGATION_POS if positive else NEGATION
    return any(has(pattern, s) and has(anchor, s) for s in sentences(span.text))


def cue(span: Span) -> bool:
    return has(CUE, span.text) or any(has(CUE, fold(h)) for h in span.chain)


# The source's measured latencies of the three general models (3.1 selection table)
MEASURED_C06 = {r"LLaMA-2-70B": 420.0, r"GPT-3\.5-Turbo": 180.0, r"Claude-2": 210.0}
MEASURED_SKIP = r"成本|准确|得分|评分|权重|覆盖|分别|分制|\$|美元|epoch|知识|多模态"


def misstated_measured(t: str) -> bool:
    """True when a general model named in the text is given a latency other than the source's value
    (a number >= 50 within ten non-digit characters after the model name, not introduced as a cost,
    score or weight)."""
    for name, value in MEASURED_C06.items():
        for m in re.finditer(name + r"(?![\w.-])([^\d\n。；;]{0,10}?)(\d+(?:\.\d+)?)", t, flags=re.I):
            if has(MEASURED_SKIP, m.group(1)):
                continue
            stated = float(m.group(2))
            if stated >= 50 and abs(stated - value) > 1e-9:
                return True
    return False


# A basis sentence whose verdict is negated ("不构成…证据", "不可同时不成立") does not
# support the finding
BASIS_VERDICT = r"构成[^。；;\n]{0,12}(证据|依据|对照|佐证)"
BASIS_FLIP = r"(不可|不能|无法|不会)同时不成立|恰好不成立"


def basis_flipped(block: str) -> bool:
    if has(BASIS_FLIP, block):
        return True
    return any(negated_before(block, m.start()) for m in re.finditer(BASIS_VERDICT, block))


def c_components(unit: str, t: str) -> dict:
    """R02: conflict propositions per confirmed Golden unit on one span's folded text."""
    comp = {}
    if unit == "C01":
        if has("GPU", t) and has(N("200"), t) and has(N("250"), t) and has(r"TOPS|算力", t):
            comp["gpu_compute_200_vs_250"] = 1.0
    elif unit == "C02":
        if has("权重", t) and (has(N("75") + r"\s*%", t) or has(r"(不足|未达|不等于|少于|低于|缺少?|差)\s*(100|25)\s*%", t)) \
                and (has(r"5\.1|联合实验室|测试维度|分级标准|图像分辨率|光照条件|遮挡", t) or (has(N("30"), t) and has(N("25"), t) and has(N("20"), t))):
            comp["weights_sum_75"] = 1.0
    elif unit == "C03":
        rows = sum(1 for p in (r"检出率", r"假阳性率", r"阅片速度") if has(p, t))
        if rows and has(r"提升幅度|提升|增幅", t):
            mixed = (has(r"百分点|绝对差", t) and has(r"相对|增幅|增长率|变化率", t) and rows >= 2) or \
                has(r"口径(不一|不统一|混用|不一致)|混用|两种(口径|算法|计算方式|计算口径)|计算口径不", t)
            if mixed:
                comp["mixed_point_and_relative"] = 1.0
            elif has(r"15\.9|15\.85|65\.7|" + N("45") + r"\s*(个)?百分点|负值|负数", t):
                comp["single_row_only"] = 0.5
    elif unit == "C04":
        if has(r"响应", t):
            one_hour, thirty = has(N("1") + r"\s*小时", t), has(N("30") + r"\s*分钟", t)
            if one_hour and thirty:
                comp["tier_high_p1"] = 0.35
            if has(N("4") + r"\s*小时", t) and has(N("2") + r"\s*小时", t):
                comp["tier_regular_p2"] = 0.35
            if has(r"响应时效|正文|节首|故障分级|分级描述|P1\s*级|文字描述|段落", t) and one_hour and thirty:
                comp["body_p1_carrier"] = 0.3
    elif unit == "C05":
        if has(r"产线|图像分析", t) and has(r"制造", t) and has(N("500") + r"\s*ms", t) and has(N("200") + r"\s*ms", t):
            comp["manufacturing_latency_500_vs_200"] = 1.0
    elif unit == "C06":
        # The measured latencies must be the source's values, not merely present
        if has(N("800") + r"\s*(ms)?\s*[-~至到]\s*" + N("1200"), t) and sum(1 for v in ("420", "180", "210") if has(N(v), t)) >= 2 \
                and not misstated_measured(t):
            comp["general_model_range_vs_measured"] = 0.5
        if has(N("200") + r"\s*(ms)?\s*[-~至到]\s*" + N("500"), t) and has(N("150"), t) and has(r"专用", t):
            comp["domain_model_range_vs_measured"] = 0.5
    elif unit == "C07":
        if has(r"客户覆盖率", t) and has(N("300") + r"\s*%", t) and has(
                r"(无法|不能|不可|难以|没有|无从)[^。；;\n]{0,4}(计算|推导|量化|复算|得出|换算|比较)|无推导|非数值|文字|定性|不可量化|无计算依据"
                r"|缺乏[^。；;\n]{0,4}依据|无依据|没有依据|不可比|无数值|非量化|无法度量", t):
            comp["non_numeric_inputs_300"] = 1.0
    elif unit == "C08":
        if has(r"FPGA", t) and has(r"3\.2\s*M|\$\s*3\.2|320\s*万|3\.2\s*百万|3200\s*K", t) and has(r"2\.28|228\s*万|2280\s*K|2280000", t):
            comp["fpga_tco_recomputed_2_28_vs_3_2"] = 1.0
    elif unit == "C09":
        if has(r"六层|6\s*层", t) and has(r"(三|3)\s*(行|项|层|条|种|个|类)|仅(列出?|有)?\s*(三|3)|只有\s*(三|3)", t) and has(r"合规|GDPR|合法性", t):
            comp["six_layers_vs_three_rows"] = 1.0
    elif unit == "C10":
        if has(r"满分\s*(10|十)|(10|十)\s*分制", t):
            rows = sum(1 for p in (r"推理速度|" + N("420"), r"微调成本|6500|\$/epoch", r"多模态", r"领域知识|通用\s*7\.5") if has(p, t))
            if rows >= 2 or (rows >= 1 and has(r"原始(值|数据|数值|计量|量)|量纲|单位不(一|统一)|无法加权|不能加权|非评分|不是(得)?分|非得分|不是评分", t)):
                comp["raw_values_in_10_point_table"] = 1.0
            elif rows == 1:
                comp["single_row_only"] = 0.5
    return comp


NUM = r"[+-]?\d+(?:\.\d+)?"


def decimals(value: str) -> int:
    return len(value.split(".")[1]) if "." in value else 0


def close(stated: str, candidates: list) -> bool:
    target = float(stated)
    tolerance = 10 ** (-decimals(stated)) + 1e-9
    return any(abs(abs(target) - abs(c)) <= tolerance for c in candidates)


def arithmetic_statements(text: str) -> list:
    """R04: replay explicit sums, ratios, differences over a base, and unit cost x nodes + development cost."""
    out = []
    t = text.replace("×", "*").replace("÷", "/").replace("≈", "=")
    for m in re.finditer(r"\$?(\d+(?:\.\d+)?)\s*\*\s*(\d+(?:\.\d+)?)\s*\+\s*\$?(\d+(?:\.\d+)?)\s*K\s*=\s*\$?(\d+(?:\.\d+)?)\s*M", t):
        a, n, b, c = m.groups()
        out.append((m.group(0), close(c, [(float(a) * float(n) + float(b) * 1000) / 1e6])))
    for m in re.finditer(r"\(\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*\)\s*/\s*(\d+(?:\.\d+)?)\s*=\s*(" + NUM + r")\s*(%)?", t):
        a, b, c, d, _ = m.groups()
        if float(c) == 0:
            continue
        v = (float(a) - float(b)) / float(c)
        out.append((m.group(0), close(d, [v * 100, v])))
    for m in re.finditer(r"(?<![\d.)\-])(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*=\s*(" + NUM + r")\s*(%|倍)?", t):
        a, b, c, _ = m.groups()
        if float(b) == 0 or re.search(r"\*\s*$", t[:m.start()]):  # Tail of a product chain
            continue
        r = float(a) / float(b)
        out.append((m.group(0), close(c, [r, r * 100, (r - 1) * 100, (1 - r) * 100])))
    for m in re.finditer(r"(?<![\d.*/$])(\d+(?:\.\d+)?)\s*%?((?:\s*\+\s*\d+(?:\.\d+)?\s*%?)+)\s*=\s*(\d+(?:\.\d+)?)\s*%?(?!\s*[KM\d])", t):
        if "K" in m.group(0) or "*" in t[max(0, m.start() - 3):m.start()]:
            continue
        terms = [float(m.group(1))] + [float(x) for x in re.findall(r"\d+(?:\.\d+)?", m.group(2))]
        out.append((m.group(0), close(m.group(3), [sum(terms)])))
    return out


def normalize(raw: dict, judge: ProgramJudge) -> dict:
    artifact = str(raw["artifact"])
    obs = {"artifact": artifact}
    if raw["status"] != "ok":
        pf = Locator("doc-parse", artifact, "markdown_document", "document", "report", "utf8_decode", raw.get("error", "")[:200])
        obs["parse_failure"] = judge.observe("parse_failure", "parse_failure", [pf])
        return obs
    spans = build_spans(raw["headings"])
    obs["nonws_total"] = nonws(raw["text"])
    # The brief requires Chinese prose. Inline code and technical names are excluded from the denominator.
    language_text = re.sub(r"`[^`]*`", "", raw["text"], flags=re.S)
    cjk = len(re.findall(r"[一-鿿]", language_text))
    latin = len(re.findall(r"[A-Za-z]{2,}", language_text))
    obs["language_share"] = cjk / (cjk + latin) if cjk + latin else 0.0
    obs["language_obs"] = judge.observe("language_share", "identified", [Locator(
        "doc:language-share", artifact, "markdown_document", "document", "language", "cjk_character_share",
        f"cjk={cjk}; latin_words={latin}; share={obs['language_share']:.6f}")])

    def loc(span, suffix, observed, rule=None):
        base = Locator(f"{span.span_id}:{suffix}:raw", artifact, span.kind, " > ".join(span.chain) + f" #L{span.start}-L{span.end}",
                       suffix, "span_text", span.raw[:400], span=f"L{span.start}-L{span.end}")
        if rule is None:
            return [base]
        if rule.startswith("N"):
            return [base, Locator(f"{span.span_id}:{suffix}:norm", artifact, span.kind, base.container_path, suffix, "normalized_gap_marker",
                                  str(observed)[:400], evidence_origin="lossless_canonicalized",
                                  source_locator_ids=(base.locator_id,), normalization_rule_id=rule)]
        return [base, Locator(f"{span.span_id}:{suffix}:norm", artifact, span.kind, base.container_path, suffix, "normalized_proposition",
                              str(observed)[:400], evidence_origin="deterministically_derived",
                              source_locator_ids=(base.locator_id,), derivation_rule_id=rule)]

    usable = [s for s in spans if not s.spray]
    obs["c"] = {}
    for unit in C_UNITS:
        matches = []
        for span in spans:
            comp = c_components(unit, span.text)
            if not comp:
                continue
            if span.spray:
                status = "spray"
            elif span.rejected or span.candidate:
                status = "rejected_or_candidate"
            elif match_disposition(span, unit) == "cleared" or negated_for(span, NEG_ANCHOR[unit], positive=True):
                status = "cleared"
            elif unit in ("C01", "C05") and not cue(span):
                status = "no_relation_cue"
            else:
                status = "eligible"
            matches.append((span, comp, status))
        eligible = [m for m in matches if m[2] == "eligible"]
        cleared = [m for m in matches if m[2] == "cleared"]
        dispositions = {match_disposition(m[0], unit) for m in eligible}
        record = {"eligible": eligible, "matches": matches, "carriers": []}
        if not matches:
            record["obs"] = judge.observe(f"{unit}:proposition", "confirmed_missing", [Locator(f"doc:{unit}", artifact, "markdown_document", "document", unit, "whole_file", "")])
            record["state"] = "missing"
        elif eligible and (cleared or len(dispositions) > 1):
            evidence = []
            for span, comp, status in (eligible + cleared)[:4]:
                evidence += loc(span, f"{unit}-{status}", comp)[:1]
            record["obs"] = judge.observe(f"{unit}:proposition", "ambiguous", evidence)
            record["state"] = "ambiguous"
        elif not eligible:
            span, comp, status = matches[0]
            record["obs"] = judge.observe(f"{unit}:proposition", "identified", loc(span, f"{unit}-{status}", f"{status}: {comp}", "R05"))
            record["state"] = status
        else:
            best = {}
            # Prefer spans that carry more components, so split table rows never crowd out a fuller finding span
            for span, comp, _ in sorted(eligible, key=lambda m: (-sum(m[1].values()), m[0].start)):
                for key, value in comp.items():
                    if key not in best or value > best[key][0]:
                        best[key] = (value, span)
            if unit in ("C03", "C10"):
                key = max(best, key=lambda k: best[k][0])
                best = {key: best[key]}
            carriers = []
            for _, span in best.values():
                if span not in carriers:
                    carriers.append(span)
            carriers = carriers[:2]
            best = {k: v for k, v in best.items() if v[1] in carriers}
            evidence = []
            for span in carriers:
                evidence += loc(span, unit, {k: v[0] for k, v in best.items() if v[1] is span}, "R02")
            record.update({"obs": judge.observe(f"{unit}:proposition", "identified", evidence), "state": "identified",
                           "components": {k: v[0] for k, v in best.items()}, "disposition": next(iter(dispositions)), "carriers": carriers})
        obs["c"][unit] = record

    not_send, send_as_is = [], []
    for span in spans:
        for s in sentences(span.text):
            # a conclusion span that summarises several findings is spray, but a send-decision
            # sentence that binds no audit object is still the report's decision
            if span.spray and (topics_of(s) or nonws(span.raw) > SPAN_MAX_NONWS):
                continue
            if has(NOT_SEND, s):
                not_send.append((span, s))
            elif (has(SEND_AS_IS, s) and not has(SEND_CONDITION, s) and not has(r"是否|能否|可否|吗|\?", s)) or (has(NO_ISSUE_GLOBAL, s) and not has(r"除|以外|之外|其余|其他|此外|但", s)):
                send_as_is.append((span, s))
    conclusion = {"not_send": not_send, "send_as_is": send_as_is}
    if not_send and send_as_is:
        conclusion["obs"] = judge.observe("conclusion", "ambiguous", loc(not_send[0][0], "not-send", not_send[0][1])[:1] +
                                          loc(send_as_is[0][0], "send-as-is", send_as_is[0][1])[:1])
    elif not_send:
        conclusion["obs"] = judge.observe("conclusion", "identified", loc(not_send[0][0], "not-send", not_send[0][1], "R06"))
    elif send_as_is:
        conclusion["obs"] = judge.observe("conclusion", "identified", loc(send_as_is[0][0], "send-as-is", send_as_is[0][1], "R06"))
    else:
        conclusion["obs"] = judge.observe("conclusion", "confirmed_missing", [Locator("doc:conclusion", artifact, "markdown_document", "document", "conclusion", "whole_file", "")])
    obs["conclusion"] = conclusion

    units = build_units(raw["headings"])
    obs["traps"] = []
    for unit, (anchor, claim) in TRAP_CLAIM.items():
        if unit == "X12":
            continue
        for span in usable:
            if span.disposition != "reported" or span.rejected or span.candidate:
                continue
            if trap_cleared(unit, span.text) or negated_for(span, anchor):
                continue
            # The claim may span consecutive sentences of one block (list item, paragraph or table row)
            scopes = [fold(b.text) for b in span.blocks] + sentences(span.text)
            hit = next((s for s in scopes if has(anchor, s) and has(claim, s) and has(TRAP_CLAIM_CUE, s)), None)
            if hit:
                obs["traps"].append((unit, span, judge.observe(f"trap:{unit}:{span.span_id}", "identified", loc(span, f"trap-{unit}", hit, "R03"))))

    # A finding unit about one trap only may state anchor, replay and verdict across its blocks
    for unit, (anchor, claim) in TRAP_CLAIM.items():
        if unit == "X12":
            continue
        for fu in units:
            if fu.disposition != "reported" or fu.rejected or fu.candidate or topics_of(fu.raw) != {unit}:
                continue
            if any(u == unit and sp.start <= fu.end and sp.end >= fu.start for u, sp, _ in obs["traps"]):
                continue
            if trap_cleared(unit, fu.text) or negated_for(fu, anchor):
                continue
            if has(anchor, fu.text) and has(claim, fu.text) and has(TRAP_CLAIM_CUE, fu.text):
                obs["traps"].append((unit, fu, judge.observe(f"trap:{unit}:{fu.span_id}", "identified", loc(fu, f"trap-{unit}", fu.text[:200], "R03"))))

    obs["direction"] = []
    for unit, (wrong, right) in DIRECTION_RULES.items():
        for span, comp, status in obs["c"][unit]["eligible"]:
            wrong_hit = next((c for c in clauses(span.text) if has(wrong, c) and not has(r"一致|相符|吻合", c) and not has(NEGATION, c)), None)
            right_hit = any(has(right, c) for c in clauses(span.text))
            if wrong_hit and not right_hit:
                obs["direction"].append((unit, span, judge.observe(f"direction:{unit}:{span.span_id}", "identified", loc(span, f"direction-{unit}", wrong_hit, "R07"))))

    obs["location"] = []
    for unit in C_UNITS:
        allowed, titles = ALLOWED_SECTIONS[unit]
        for span, comp, status in obs["c"][unit]["eligible"]:
            refs = set()
            for m in SECTION_REF.finditer(span.text):
                number = m.group(1)
                if number not in HEADINGS:
                    continue
                after = span.text[m.end():m.end() + 12]
                before = span.text[max(0, m.start() - 2):m.start()]
                if re.match(r"\s*(节|章|小节)", after) or after.strip().startswith(HEADINGS[number][:2]) or re.search(r"(第|§|见|于|在)\s*$", before):
                    refs.add(number)
            chapters = chapter_refs(span.text)
            if refs and not (refs & allowed) and not (chapters & ALLOWED_CHAPTERS[unit]) and not has(titles, span.text):
                obs["location"].append((unit, span, judge.observe(f"location:{unit}:{span.span_id}", "identified", loc(span, f"location-{unit}", sorted(refs), "R08"))))

    obs["arith"] = []
    for span in usable:
        if span.rejected or span.candidate or span.disposition == "cleared":
            continue
        for expression, ok in arithmetic_statements(span.text):
            if not ok:
                index = len(obs["arith"])
                obs["arith"].append((expression, span, judge.observe(f"arith:{span.span_id}:{index}", "identified", loc(span, f"arith-{index}", expression, "R04"))))

    obs["fabrication"], obs["gap_markers"] = [], []
    for unit, (anchor, value) in FABRICATION_RULES.items():
        for span in usable:
            if span.rejected or span.candidate or span.disposition == "cleared" or not has(anchor, span.text):
                continue
            for s in sentences(span.text):
                if not has(CORRECTION, s) or (unit == "C08" and not has(anchor, s)):
                    continue
                tail = re.split(CORRECTION, s, maxsplit=1)[-1]
                index = len(obs["gap_markers"]) + len(obs["fabrication"])
                if any(marker.lower() in tail.lower() for marker in GAP_MARKERS):
                    obs["gap_markers"].append((unit, span, judge.observe(f"gap:{unit}:{span.span_id}:{index}", "identified", loc(span, f"gap-{unit}-{index}", s, "N06"))))
                    continue
                if has(value, tail[:30]) and not has(HEDGE, s) and not has(r"3\.2\s*M|300\s*%", tail[:12]):
                    obs["fabrication"].append((unit, span, judge.observe(f"fabrication:{unit}:{span.span_id}:{index}", "identified", loc(span, f"fabrication-{unit}-{index}", s, "R09"))))
    # C02 - a definitive claim naming the dimension of the missing 25%
    for span in usable:
        if span.rejected or span.candidate or span.disposition == "cleared" or not c_components("C02", span.text):
            continue
        for s in sentences(span.text):
            if c02_named_fill(s):
                index = len(obs["gap_markers"]) + len(obs["fabrication"])
                obs["fabrication"].append(("C02", span, judge.observe(f"fabrication:C02:{span.span_id}:{index}", "identified", loc(span, f"fabrication-C02-{index}", s, "R09"))))
                break
    # Finding units -> overgraded items (D08) and confirmed findings outside Golden (D09)
    obs["overgraded"], extras = [], []
    for unit in units:
        if unit.disposition != "reported" or unit.rejected or unit.candidate:
            continue
        hit_items = [item for item, patterns in U_PRED.items() if all(has(p, unit.text) for p in patterns)
                     and not negated_for(unit, patterns[0])]
        for item in hit_items:
            obs["overgraded"].append((item, unit, judge.observe(f"overgraded:{item}:{unit.span_id}", "identified", loc(unit, f"overgraded-{item}", item, "R11"))))
        if hit_items or topics_of(unit.raw) or any(c_components(c, unit.text) for c in C_UNITS):
            continue
        if nonws(unit.raw) >= 20 and has(PROBLEM_CUE, unit.text):
            extras.append(unit)
    obs["extras"] = extras
    if extras:
        evidence = []
        for unit in extras[:12]:
            evidence += loc(unit, "extra-finding", unit.raw[:80])[:1]
        evidence.append(Locator("doc:extra-count", artifact, "markdown_document", "document", "confirmed-findings-outside-golden", "count", str(len(extras)),
                                evidence_origin="deterministically_derived", source_locator_ids=tuple(l.locator_id for l in evidence), derivation_rule_id="R12"))
        obs["extras_obs"] = judge.observe("over_reporting", "identified", evidence)

    # aspects of each identified confirmed unit that earns positive credit, evaluated on its carrier spans
    for unit in C_POSITIVE.values():
        record = obs["c"][unit]
        if record["state"] != "identified":
            continue
        scope = list(record["carriers"])
        scope += [u for u in units if u.disposition != "cleared" and any(u.start <= sp.end and u.end >= sp.start for sp in record["carriers"])
                  and not any(c_components(other, u.text) for other in C_UNITS if other != unit and other not in ("C06", "C10") and unit not in ("C06", "C10"))]
        text = "\n".join(span.text for span in scope)
        record["aspects"] = {name: has(pattern, text) for name, pattern in ASPECTS[unit].items()}
        if record["aspects"].get("basis"):
            carrying = [fold(b.text) for sp in scope for b in sp.blocks if has(ASPECTS[unit]["basis"], fold(b.text))]
            if any(basis_flipped(b) for b in carrying):
                record["aspects"]["basis"] = False

    candidates = [u for u in units if not (u.rejected or u.candidate)]
    candidates += [sp for sp in usable if not (sp.rejected or sp.candidate) and not any(u.start <= sp.end and u.end >= sp.start for u in candidates)]

    def lead_disposition(cand):
        lead = fold(cand.blocks[0].text) if cand.blocks else ""
        if has(LEAD_DOUBTFUL, lead):
            return "doubtful"
        if has(LEAD_CLEARED, lead):
            return "cleared"
        return cand.disposition

    # author-confirmation items
    obs["u"] = {}
    for item in U_POSITIVE.values():
        found = [(c, lead_disposition(c)) for c in candidates if all(has(p, c.text) for p in U_CREDIT_PRED[item])]
        dispositions = {d for _, d in found}
        if not found:
            obs["u"][item] = {"state": "missing", "obs": judge.observe(f"{item}:filing", "confirmed_missing", [Locator(f"doc:{item}", artifact, "markdown_document", "document", item, "whole_file", "")])}
        elif "reported" in dispositions and len(dispositions) > 1:
            obs["u"][item] = {"state": "ambiguous", "obs": judge.observe(f"{item}:filing", "ambiguous", [l for c, _ in found[:3] for l in loc(c, f"{item}-filing", item)[:1]])}
        else:
            cand, disposition = next(((c, d) for c, d in found if d == "doubtful"), found[0])
            reading = has(U_READING[item], cand.text)
            obs["u"][item] = {"state": "identified", "disposition": disposition, "reading": reading,
                              "obs": judge.observe(f"{item}:filing", "identified", loc(cand, f"{item}-filing", f"disposition={disposition} reading={reading}", "R14"))}

    # cleared anomalies
    charged_traps = {t for t, _, _ in obs["traps"]}
    obs["x"] = {}
    for item in X_POSITIVE.values():
        anchor = TRAP_CLAIM[item][0]
        hit = None
        for cand in candidates:
            if not has(anchor, cand.text):
                continue
            if lead_disposition(cand) == "cleared" and any(c_components(c, cand.text) for c in C_UNITS):
                continue  # a confirmed conflict filed under a cleared heading is a wrong-section artifact; nothing in it earns credit
            cleared_by_section = lead_disposition(cand) == "cleared" and (has(TRAP_READING[item], cand.text) or has(TRAP_REPLAY[item], cand.text))
            if not cleared_by_section and lead_disposition(cand) == "reported":
                # A paragraph or list item led by a cleared label inside a reported section
                for block in cand.blocks:
                    text = fold(block.text)
                    if has(LEAD_CLEARED, text) and has(anchor, text) and (has(TRAP_READING[item], text) or has(TRAP_REPLAY[item], text)):
                        cleared_by_section = True
            cleared_by_sentence = any(has(TRAP_REPLAY[item], sent) and verdict_consistent(sent) for sent in sentences(cand.text))
            if cleared_by_section or cleared_by_sentence:
                hit = cand
                break
        if hit is None:
            # A paragraph led by a cleared label that lists checked computations; bind anchor and replay per clause
            for sp in spans:
                if sp.rejected or sp.candidate:
                    continue
                for block in sp.blocks:
                    text = fold(block.text)
                    if has(LEAD_CLEARED, text) and any(has(anchor, cl) and (has(TRAP_READING[item], cl) or has(TRAP_REPLAY[item], cl)) for cl in re.split(r"[；;。\n]", text)):
                        hit = sp
                        break
                if hit is not None:
                    break
        if hit is None:
            obs["x"][item] = {"state": "missing", "obs": judge.observe(f"{item}:clearance", "confirmed_missing", [Locator(f"doc:{item}", artifact, "markdown_document", "document", item, "whole_file", "")])}
        elif item in charged_traps:
            obs["x"][item] = {"state": "ambiguous", "obs": judge.observe(f"{item}:clearance", "ambiguous", loc(hit, f"{item}-clearance", item)[:1])}
        else:
            obs["x"][item] = {"state": "identified", "obs": judge.observe(f"{item}:clearance", "identified", loc(hit, f"{item}-clearance", "cleared with replay or reading", "R15"))}

    # A confirmed Golden conflict stated only in cleared spans (false assurance)
    obs["false_clear"] = []
    for unit in C_UNITS:
        record = obs["c"][unit]
        if record["state"] in ("identified", "ambiguous"):
            continue
        for span in usable:
            if span.rejected or span.candidate:
                continue
            stated = bool(c_components(unit, span.text)) or (unit == "C05" and all(has(p, span.text) for p in C05_CLEARED_LOOSE))
            if stated and (match_disposition(span, unit) == "cleared" or negated_for(span, NEG_ANCHOR[unit])):
                obs["false_clear"].append((unit, span, judge.observe(f"false_clear:{unit}:{span.span_id}", "identified", loc(span, f"false-clear-{unit}", unit, "R13"))))

    # P41: identified confirmed units whose carrier spans name the section, chapter or heading title holding them
    obs["located"] = {}
    for unit in C_UNITS:
        record = obs["c"][unit]
        if record["state"] != "identified":
            continue
        allowed, titles = ALLOWED_SECTIONS[unit]
        text = "\n".join(span.text for span in record["carriers"])
        chapters = chapter_refs(text)
        if (cited_sections(text) & {".".join(a.split(".")[:2]) for a in allowed}) \
                or (chapters & ALLOWED_CHAPTERS[unit]) or has(titles, text):
            obs["located"][unit] = record["obs"]

    # D11: required units absent from the whole report
    whole = fold(raw["text"])
    lines = [fold(line) for line in raw["text"].splitlines()]
    present_sections = cited_sections(whole)
    present_objects = set()
    for piece in lines + sentences(whole):
        present_objects |= topics_of(piece)
    missing = [f"section:{sec}" for sec in REQUIRED_SECTIONS if sec not in present_sections]
    missing += [f"object:{unit}" for unit in REQUIRED_OBJECTS if unit not in present_objects]
    if not not_send:
        missing.append("send_decision")
    obs["missing_units"] = [(key, judge.observe(f"required:{key}", "identified",
                                                [Locator(f"doc:required:{key}", artifact, "markdown_document", "document", key, "whole_file", "absent")]))
                            for key in missing]

    # D12: a figure's value used as one side of a reported conflict
    obs["figure"] = []
    for span in spans:
        if span.rejected or span.candidate or span.disposition == "cleared":
            continue
        for s in sentences(span.text):
            if has(FIGURE, s) and has(FIGURE_CONFLICT, s) and re.search(r"\d", re.sub(FIGURE, "", s)) and not has(FIGURE_EXCLUDED, s) and not has(NEGATION, s):
                obs["figure"].append((f"figure@{span.span_id}", span, judge.observe(f"figure:{span.span_id}:{len(obs['figure'])}", "identified", loc(span, "figure", s, "R17"))))
                break

    # D14: the general-model latency range of C06 restated with a value that contains the measured latencies
    obs["misstated"] = []
    for span in spans:
        if span.rejected or span.candidate or span.disposition == "cleared" or not has(r"通用(大)?模型", span.text):
            continue
        for s in sentences(span.text):
            if not has(r"通用(大)?模型", s):
                continue
            for m in re.finditer(r"(?<![\d.])(\d{2,4})\s*(?:ms|毫秒)?\s*[-~至到]\s*(\d{2,4})(?![\d.])", s):
                low, high = float(m.group(1)), float(m.group(2))
                if (low, high) in ((800, 1200), (200, 500)) or low >= high or {low, high} <= {150, 180, 210, 420}:
                    continue  # the source ranges, or a span of the measured latencies themselves
                inside = sum(1 for v in (420, 180, 210) if low <= v <= high)
                if inside >= 2 and has(CUE, s):
                    obs["misstated"].append(("C06", span, judge.observe(f"misstated:C06:{span.span_id}", "identified", loc(span, "misstated-C06", s, "R18"))))
                    break
            if obs["misstated"] and obs["misstated"][-1][1] is span:
                break

    # A string quoted as the source's words that the Materials do not contain
    materials_index = MaterialsIndex(MATERIALS_MD)
    for span in spans:
        if span.rejected or span.candidate or span.disposition == "cleared" or span.spray:
            continue
        for quote in unsupported_quotes(span.text, materials_index):
            n = len(obs["misstated"])
            obs["misstated"].append((f"quote{n}", span, judge.observe(f"misstated:quote:{span.span_id}:{n}", "identified", loc(span, f"misquote-{n}", quote, "R18"))))

    # D13: files beside the deliverable that the brief does not ask for
    folder = Path(artifact).parent
    obs["extra_files"] = sorted(f.name for f in folder.iterdir()
                                if f.is_file() and f.resolve() != Path(artifact).resolve() and f.name not in NOT_DELIVERABLES
                                and not f.name.startswith("."))
    return obs


# ---------------------------------------------------------------- layer 3: decisions
def evaluate(obs: dict, judge: ProgramJudge) -> None:
    contract = judge.contract
    weights = {item["id"]: float(item["weight"]) for item in contract["positive_items"]}
    if "parse_failure" in obs:
        pf = obs["parse_failure"]
        for item in contract["positive_items"]:
            judge.positive(item["id"], 0.0, pf, "artifact could not be decoded", "different")
        for item in contract["deduction_items"]:
            judge.deduction(item["id"], "parse_failure", [pf], "artifact could not be decoded")
        return

    # G-LANG is a multiplicative requirement gate; it is independent of content weights.
    if obs["language_share"] < 0.90:
        oid = obs["language_obs"]
        judge.deduction("G-LANG", "triggered", [oid], f"Chinese share {obs['language_share']:.4f} below 0.90",
                        [{"damage_instance_key": "language_not_chinese", "causal_root_id": "R-language",
                          "manifestation_id": "G-LANG:below-0.90", "observation_id": oid,
                          "reason": f"Chinese share {obs['language_share']:.4f}"}])
    else:
        judge.deduction("G-LANG", "not_triggered", [obs["language_obs"]], f"Chinese share {obs['language_share']:.4f} at least 0.90")

    earned = {}
    for item_id, unit in C_POSITIVE.items():
        record = obs["c"][unit]
        if record["state"] == "missing":
            judge.positive(item_id, 0.0, record["obs"], "no span states this confirmed conflict", "missing")
            continue
        if record["state"] != "identified":
            judge.positive(item_id, 0.0, record["obs"], f"proposition found only as {record['state']}", "different")
            continue
        core = min(1.0, sum(record["components"].values()))
        aspects = record["aspects"]
        total = ASPECT_WEIGHTS["core"] + sum(ASPECT_WEIGHTS[name] for name in aspects)
        fraction = core * (ASPECT_WEIGHTS["core"] + sum(ASPECT_WEIGHTS[name] for name, ok in aspects.items() if ok)) / total
        if record["disposition"] == "doubtful" and unit != "C05":
            fraction *= 0.5
        fraction = round(fraction, 6)
        if fraction > 0.999999:
            fraction = 1.0
        judge.positive(item_id, fraction, record["obs"], f"components={record['components']} aspects={aspects} disposition={record['disposition']}",
                       "exact" if fraction >= 1.0 else "partial")
        earned[item_id] = fraction

    for item_id, item in U_POSITIVE.items():
        record = obs["u"][item]
        if record["state"] == "missing":
            judge.positive(item_id, 0.0, record["obs"], "item not filed", "missing")
        elif record["state"] == "ambiguous":
            judge.positive(item_id, 0.0, record["obs"], "filed both as confirmed and as doubtful or cleared", "different")
        elif record["disposition"] == "doubtful":
            fraction = 1.0 if record["reading"] else 0.6
            judge.positive(item_id, fraction, record["obs"], f"filed for author confirmation; alternative reading={record['reading']}", "exact" if fraction == 1.0 else "partial")
            earned[item_id] = fraction
        elif record["disposition"] == "cleared" and record["reading"]:
            judge.positive(item_id, 0.5, record["obs"], "difference and reading stated but cleared instead of sent to the author", "partial")
            earned[item_id] = 0.5
        else:
            judge.positive(item_id, 0.0, record["obs"], f"stated with disposition {record['disposition']}", "different")
    for item_id, item in X_POSITIVE.items():
        record = obs["x"][item]
        if record["state"] == "identified":
            judge.positive(item_id, 1.0, record["obs"], "anomaly cleared with its replay or reading", "exact")
            earned[item_id] = 1.0
        elif record["state"] == "ambiguous":
            judge.positive(item_id, 0.0, record["obs"], "cleared in one place and reported as a conflict in another", "different")
        else:
            judge.positive(item_id, 0.0, record["obs"], "anomaly not cleared", "missing")
    located = obs["located"]
    active_location_units={"C02","C03","C04","C07","C08","C09","C10"}
    located_active=set(located) & active_location_units
    fraction = round(len(located_active) / len(active_location_units), 6)
    located_obs = judge.observe("located_findings", "identified" if located else "confirmed_missing",
                                [Locator(f"doc:located:{unit}", obs["artifact"], "markdown_document", "document", unit, "section_reference", "located")
                                 for unit in sorted(located)] or [Locator("doc:located", obs["artifact"], "markdown_document", "document", "located", "whole_file", "")])
    judge.positive("P41", fraction, located_obs, f"located active confirmed units: {sorted(located_active)} of {len(active_location_units)}",
                   "exact" if fraction >= 1.0 else ("partial" if fraction else "missing"))
    earned["P41"] = fraction
    raw_text = Path(obs["artifact"]).read_text(encoding="utf-8", errors="replace")
    x12_ok = (
        bool(re.search(r"15\s*%?\s*[-~至到]\s*30", raw_text))
        and bool(re.search(r"22\s*%?\s*[-~至到]\s*41", raw_text))
        and bool(re.search(r"45(?:\.1[0-9]*|\.2)?\s*%", raw_text))
        and bool(re.search(r"52(?:\.0+)?\s*%", raw_text))
        and bool(re.search(r"超出|不符|不一致|超过", raw_text))
    )
    x12_obs = judge.observe("X12:measured-mode-switch", "identified" if x12_ok else "confirmed_missing",
                            [Locator("doc:X12", obs["artifact"], "markdown_document", "document",
                                     "X12", "whole_file", "measured full-mode reduction versus stated range")])
    judge.positive("P33", 1.0 if x12_ok else 0.0, x12_obs,
                   "full high-performance to energy-saving reductions are compared with the stated ranges",
                   "exact" if x12_ok else "missing")
    earned["P33"] = 1.0 if x12_ok else 0.0
    table_ids = {int(value) for value in re.findall(r"(?i)(?:\bT|\bTable\s*|表\s*)(\d{1,3})\b", raw_text)
                 if 1 <= int(value) <= 97}
    pseudo_ids = {value for value in ("PSEUDO-A","PSEUDO-B","PSEUDO-C","PSEUDO-D") if value in raw_text.upper()}
    declared_full_census = bool(
        re.search(r"(?:全部|全量|共计|合计|清点|覆盖|审计)[^。；;\n]{0,40}101\s*(?:张|个)?\s*表", raw_text)
        or (
            re.search(r"97\s*(?:张|个)?\s*(?:正文)?表", raw_text)
            and re.search(r"2\s*(?:张|个)?\s*代码块表", raw_text)
            and re.search(r"2\s*(?:张|个)?\s*(?:行内)?管道表", raw_text)
        )
    )
    coverage = 1.0 if declared_full_census else (len(table_ids) + len(pseudo_ids)) / 101
    coverage_obs = judge.observe("table_coverage", "identified" if coverage else "confirmed_missing",
        [Locator("doc:table-coverage", obs["artifact"], "markdown_document", "document",
                 "T1-T97 plus four pseudo tables", "coverage",
                 json.dumps({"numbered_tables":len(table_ids),"pseudo_tables":len(pseudo_ids),
                             "declared_full_census":declared_full_census}))])
    judge.positive("P42", coverage, coverage_obs,
                   f"audited table ledger covers {len(table_ids)} numbered and {len(pseudo_ids)} pseudo tables",
                   "exact" if coverage == 1 else ("partial" if coverage else "missing"))
    earned["P42"] = coverage
    positive_earned = sum(weights[k] * v for k, v in earned.items())
    conclusion = obs["conclusion"]
    cobs = conclusion["obs"]
    any_obs = [record["obs"] for record in obs["c"].values()]

    def charge(item_id, entries, key_prefix, root_prefix, reason):
        occ = [{"damage_instance_key": f"{key_prefix}:{unit}", "causal_root_id": f"{root_prefix}:{unit}",
                "manifestation_id": f"{unit}@{span.span_id}", "observation_id": oid} for unit, span, oid in entries]
        judge.deduction(item_id, "triggered", [oid for _, _, oid in entries], reason, occ)

    if obs["traps"]:
        charge("D01", obs["traps"], "trap_reported_as_conflict", "trap", "checked-consistent trap reported as a conflict")
    else:
        judge.deduction("D01", "not_triggered", any_obs, "no affirmative trap claim outside cleared, doubtful, negated or replayed contexts")

    if obs["arith"]:
        entries = [(re.sub(r"\s", "", expression), span, oid) for expression, span, oid in obs["arith"]]
        charge("D02", entries, "misstated_recomputation", "arith", "stated recomputation does not replay")
    else:
        judge.deduction("D02", "not_triggered", any_obs, "every explicit recomputation replays")

    if obs["direction"]:
        charge("D03", obs["direction"], "reversed_direction", "direction", "consistent side declared wrong")
    else:
        judge.deduction("D03", "not_triggered", any_obs, "no reversed outlier direction")

    if obs["location"]:
        charge("D04", obs["location"], "wrong_location", "location", "finding bound only to sections that do not hold the tables")
    else:
        judge.deduction("D04", "not_triggered", any_obs, "no finding bound only to a wrong section")

    if conclusion["send_as_is"] and not conclusion["not_send"]:
        span = conclusion["send_as_is"][0][0]
        judge.deduction("D05", "triggered", [cobs], "report concludes the proposal can be sent as is",
                        [{"damage_instance_key": "send_as_is", "causal_root_id": "conclusion", "manifestation_id": f"send@{span.span_id}", "observation_id": cobs}])
    elif conclusion["send_as_is"]:
        judge.deduction("D05", "ambiguous", [cobs], "contradictory send conclusions")
    else:
        judge.deduction("D05", "not_triggered", [cobs], "no send-as-is conclusion")

    if obs["fabrication"]:
        charge("D06", obs["fabrication"], "fabricated_correction", "fabrication", "definitive corrected value the Materials cannot support")
    else:
        judge.deduction("D06", "not_triggered", [oid for _, _, oid in obs["gap_markers"]] or any_obs,
                        "no definitive unsupported correction; declared gap markers fold to one gap observation")

    judge.deduction("D08", "not_triggered", any_obs,
                    "retired: professional severity is not fixed by a Golden whitelist")
    judge.deduction("D09", "not_triggered", any_obs,
                    "retired: source-supported findings outside Golden are not over-reporting")

    false_clear=[row for row in obs["false_clear"] if row[0] not in {"C01","C05","C06"}]
    if false_clear:
        charge("D10", false_clear, "confirmed_defect_cleared", "false_clear", "confirmed source-supported conflict stated as checked and consistent")
    else:
        judge.deduction("D10", "not_triggered", any_obs, "no confirmed conflict stated as consistent")

    judge.deduction("D11", "not_triggered", any_obs,
                    "retired: omissions lose their positive owner and are not multiplied again")

    if obs["figure"]:
        charge("D12", obs["figure"], "figure_as_finding", "figure", "a figure's value used as one side of a reported conflict")
    else:
        judge.deduction("D12", "not_triggered", any_obs, "no figure value reported as a conflict")

    judge.deduction("D13", "not_triggered", any_obs,
                    "retired: auxiliary files do not alter the declared deliverable score")

    if obs["misstated"]:
        charge("D14", obs["misstated"], "misstated_source_value", "misstated", "a source value restated wrongly: the C06 general-model latency range, or a quote of the source the Materials do not contain")
    else:
        judge.deduction("D14", "not_triggered", any_obs, "no misstated source range")

    shapes = {s["id"]: s for s in contract["shape_units"]}
    s01, s02 = shapes["S01"], shapes["S02"]
    carrier_ids, candidate_chars, golden_chars = set(), 0, 0
    for unit in C_UNITS:
        record = obs["c"][unit]
        if record["state"] != "identified":
            continue
        golden_chars += s01["golden_unit_values"][unit]
        for span in record["carriers"]:
            if span.span_id not in carrier_ids:
                carrier_ids.add(span.span_id)
                candidate_chars += nonws(span.raw)
    manifestations, ratios = [], {}
    if golden_chars:
        ratio = candidate_chars / max(golden_chars, s01["declared_floor"])
        ratios["S01"] = round(ratio, 4)
        # overrun_tolerance_ratio is null: the deliverable has no public length requirement, so only
        # the underrun arm is charged.
        if s01["overrun_tolerance_ratio"] is not None:
            over = ratio - (1 + s01["overrun_tolerance_ratio"])
            if over > 1e-9:
                manifestations += [("S01", tier) for tier in range(1, min(s01["max_tiers"], math.ceil(over / s01["tier_width"])) + 1)]
        if ratio < 1 - s01["underrun_tolerance_ratio"] and positive_earned > 0:
            manifestations.append(("S01", "under"))
    ratio2 = obs["nonws_total"] / max(s02["golden_value"], s02["declared_floor"])
    ratios["S02"] = round(ratio2, 4)
    if s02["overrun_tolerance_ratio"] is not None:
        over2 = ratio2 - (1 + s02["overrun_tolerance_ratio"])
        if over2 > 1e-9:
            manifestations += [("S02", tier) for tier in range(1, min(s02["max_tiers"], math.ceil(over2 / s02["tier_width"])) + 1)]
    judge.deduction("D07", "not_triggered", any_obs,
                    "retired: document length is not a proxy for audit quality")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--contract", type=Path, default=CANONICAL_CONTRACT)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--measure", action="store_true", help="print shape measurements and matched spans instead of scoring")
    args = parser.parse_args()
    contract_path = args.contract.resolve()
    judge = ProgramJudge(load_contract(contract_path), args.artifact.resolve(), sha256(contract_path))
    obs = normalize(extract_raw(args.artifact.resolve()), judge)
    if args.measure:
        report = {"total_nonws": obs.get("nonws_total"), "units": {}}
        for unit, record in obs.get("c", {}).items():
            report["units"][unit] = {"state": record["state"], "components": record.get("components"),
                                     "carriers": [(s.span_id, nonws(s.raw)) for s in record.get("carriers", [])],
                                     "matches": [(s.span_id, st) for s, _, st in record["matches"]]}
        report["aspects"] = {u: r.get("aspects") for u, r in obs.get("c", {}).items()}
        report["u"] = {k: (v["state"], v.get("disposition"), v.get("reading")) for k, v in obs.get("u", {}).items()}
        report["x"] = {k: v["state"] for k, v in obs.get("x", {}).items()}
        for key in ("traps", "direction", "location", "arith", "fabrication", "gap_markers", "overgraded", "false_clear"):
            report[key] = [(str(a), s.span_id) for a, s, _ in obs.get(key, [])]
        report["extras"] = [(u.span_id, u.raw[:40].replace("\n", " ")) for u in obs.get("extras", [])]
        report["conclusion"] = {k: len(v) for k, v in obs.get("conclusion", {}).items() if isinstance(v, list)}
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 0
    evaluate(obs, judge)
    rendered = json.dumps(judge.finish(), ensure_ascii=False, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

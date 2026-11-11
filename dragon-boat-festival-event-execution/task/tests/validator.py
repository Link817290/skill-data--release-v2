"""Deterministic DOCX business-span verifier; never reads models or old rewards."""

from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unicodedata
from zipfile import ZipFile

from lxml import etree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from festival_facts import facts, contradictions
from festival_equivalence import medical_readiness, paired_candidates
from festival_control import overall_control
from scoring_math import settle
from festival_actions import boundary_decision, generic_instructor_exemption
from festival_source_scope import exclusion as scope_exclusion, source_group_exclusion
from festival_schedule import conflicts as schedule_conflicts
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
WITHDRAWAL = re.compile(
    r"无需|不必|不用|(?<!不)取消|省略|不再|不予|不需要|跳过|不(?:进行|完成|执行|安排|开展|检查|核验|核对|清理|清洁|清台|擦拭|回收|监督|准备|通知|汇报|审核|维护|疏导|分流)"
)
PROPOSAL = re.compile(
    r"待确认|待批准|需批准|申请|建议|拟增|假设|未确定|不采用|不得采用|禁止采用|不应采用|不能采用"
)


def normalize(text: str) -> str:
    return (
        re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))
        .replace("四十", "40")
        .replace("总协调", "总控")
        .replace("讲师", "老师")
    )


def extract(path: Path) -> list[dict]:
    if path.is_symlink():
        raise ValueError("symlink is not an accepted deliverable")
    with ZipFile(path) as archive:
        if sum(x.file_size for x in archive.infolist()) > 32 * 1024 * 1024:
            raise ValueError("DOCX uncompressed size exceeds safe parser budget")
        root = etree.fromstring(
            archive.read("word/document.xml"),
            parser=etree.XMLParser(resolve_entities=False, no_network=True),
        )
    result = []
    headings = {}
    for i, child in enumerate(root.find("w:body", NS), 1):
        if etree.QName(child).localname == "tbl":
            for j, row in enumerate(child.findall("w:tr", NS), 1):
                cells = row.findall("w:tc", NS)
                texts = [
                    "".join(c.xpath(".//w:t/text()", namespaces=NS)) for c in cells
                ]
                prefix = " | ".join(texts[:-1])
                result.append(
                    {
                        "location": f"B{i}:R{j}",
                        "text": " | ".join(texts),
                        "scope": "table-row",
                        "section": " / ".join(headings.values()),
                    }
                )
                # Each duty paragraph inherits its row's role, not unrelated rows.
                duty_paragraphs = cells[-1].findall(".//w:p", NS) if cells else []
                for k, p in enumerate(duty_paragraphs, 1):
                    duty = "".join(p.xpath(".//w:t/text()", namespaces=NS))
                    if duty.strip():
                        result.append(
                            {
                                "location": f"B{i}:R{j}:P{k}",
                                "text": prefix + " | " + duty,
                                "scope": "table-duty",
                                "section": " / ".join(headings.values()),
                            }
                        )
        elif etree.QName(child).localname == "p":
            text = "".join(child.xpath(".//w:t/text()", namespaces=NS))
            style = child.find("w:pPr/w:pStyle", NS)
            style_id = style.get("{" + NS["w"] + "}val", "") if style is not None else ""
            level = re.search(r"(?:Heading|heading)(\d+)", style_id)
            if level:
                depth = int(level[1])
                headings = {k: v for k, v in headings.items() if k < depth}
                headings[depth] = text
            if text.strip():
                result.append({"location": f"B{i}", "text": text, "scope": "paragraph",
                               "section": " / ".join(headings.values())})
    return result


def units(spans: list[dict]) -> list[dict]:
    result = []
    for span in spans:
        # Related clauses of one duty remain connected; unrelated DOCX blocks never join.
        text = normalize(span["text"])
        if len(text) <= 420:
            result.append({**span, "normalized": text})
        else:
            for index, piece in enumerate(re.split(r"[。\n]", text)):
                if piece:
                    result.append(
                        {
                            **span,
                            "location": span["location"] + f":S{index}",
                            "normalized": piece,
                        }
                    )
    return result


def duty_action(rule: dict, text: str) -> bool:
    if rule['id'] == 'rehearsal-transition':
        return any(re.search(r'彩排|走台|演练|排练', clause)
                   and not re.search(r'是否|待确认|未确认|无需|不用|不必|不需要|不安排', clause)
                   for clause in re.split(r'[。;；|]', text))
    if rule['id'] == 'security':
        action = r'(?:维护|负责(?!人)|检查|疏导|管理|巡查|组织)'
        crowd = r'(?:秩序|人流|队列|观众|安全|疏散)'
        return bool(re.search(action + r'[^。;；|]{0,24}' + crowd, text)
                    or re.search(crowd + r'[^。;；|]{0,24}' + action, text))
    if rule["id"] == "child-supervision":
        adult = r"(?:助教|老师|教师|工作人员|监护人|家长|同行成人|成人)"
        child = r"(?:儿童|孩子|未成年(?:人)?|小朋友)"
        operation = r"(?:操作|使用|制作|实操|动手体验)"
        supervision = r"(?:监督|看护|陪护|陪同|监护(?!人|职责|关系)|安全指导|近距离协助|协助)"
        local = r"[^。;；|,，]{0,24}"
        for clause in re.split(r"[。;；|,，]", text):
            obligation = re.search(child + local + operation + local
                                   + r"(?:时|期间)?(?:必须|须|应|需|保持|接受)" + local
                                   + r"(?:监护|监督|看护)", clause)
            if (obligation and re.search(adult, text)
                    and not re.search(r"是否|待确认|未确认|无需|不用|(?:不|未)(?:必|须|应|需|接受|保持)", clause)):
                return True
        return bool(re.search(adult + local + supervision + local + child + local + operation, text)
                    or re.search(child + local + operation + local + adult + local + supervision, text)
                    or re.search(child + local + adult + local + supervision + local + operation, text)
                    or (re.search(adult + r"[^。;；|,，]{0,8}\(?(?:使用|操作|工具)监督", text)
                        and re.search(child + local + r"(?:单独持用|单独使用|使用|操作)", text)))
    if rule["id"] == "conditional-shared-staff":
        return bool(re.search(r"(?:有时间|空闲|优先|无冲突)[^。]{0,60}(?:引导|值守|协助|签到|核验)|(?:引导|值守|协助|签到|核验)[^。]{0,60}(?:有时间|空闲|优先|无冲突)|引导[^。]{0,30}。?\(有时间的情况下\)", text))
    if rule["id"] == "hands-on-demonstration":
        return bool(re.search(
            r"(?:介绍|讲解|示范|演示)[^。;；|]{0,18}(?:操作|制作|技艺|步骤|项目|成品)"
            r"|(?:操作|制作|体验|技艺|步骤)[^。;；|]{0,12}(?:示范|演示|讲解)"
            r"|(?:老师|教师|助教|传承人)[^。;；|]{0,6}(?:示范|演示)(?!内容|位|区|台|站|点)",
            text,
        ))
    if rule["id"] in {"stage-surface", "props-cables"}:
        # Status cells such as "already confirmed" are not an inspection action.
        cleaned = re.sub(r"\[?已确认(?:事项|分工|来源)?\]?|已确认\(来源\)", "", text)
        action = (r"(?:检查|确认|巡查|巡检|核验|复核|评估|排查)"
                  if rule['id'] == 'stage-surface' else
                  r"(?:检查|确认|巡查|巡检|核验|复核|评估|复点|排查|整理|收纳)")
        obj = r"(?:地面|防滑|滑倒)" if rule["id"] == "stage-surface" else r"(?:道具|铃鼓|铃/鼓|茶篮|折扇|傩面具|祭台|电线|线缆|电缆)"
        return bool(re.search(action + r"[^。;；|]{0,20}" + obj, cleaned)
                    or re.search(obj + r"[^。;；|]{0,20}" + action, cleaned))
    if rule['id'] == 'overflow-alternative':
        alternative = (r'(?:观看|观演|候补|其他场次|下一场|后续场次|尚有名额|仍有名额|广场表演|次日场次|次日同类体验'
                       r'|(?:表演|祈福)[^。;；|]{0,12}(?:开放|项目)'
                       r'|(?:其他|仍|真实|可用|开放)[^。;；|]{0,12}(?:活动|项目))')
        action = r'(?:解释|说明|告知|引导|选择|查看|提供|登记)'
        for clause in re.split(r'[。;；|]', text):
            if re.search(r'不(?:承诺|提供|引导|登记|告知|说明)|仅供选择|不执行|候补机制未确认', clause):
                continue
            if re.search(action + r'[^。;；|]{0,50}' + alternative, clause):
                return True
            if re.search(alternative + r'[^。;；|]{0,30}' + action, clause):
                return True
        return False
    if rule["id"] == "controlled-access":
        if ('核心区' in text and not re.search(
                r'舞台|祭台|表演|舞蹈|演员|主持|NPC|上台|候场|音响控制台|表演工作区', text)):
            return False
        person = r"(?:非工作人员|无关人员|未授权|未经允许|未受邀请|观众|游客|儿童|公众)"
        ban = r"(?:严禁|禁止|不得|不能|停止|不)"
        area = r"(?:舞台|祭台|表演作业区|表演工作区|表演核心区|核心区|表演面|表演边界|表演区|候场|设备区|音响控制台|工作区)"
        entry = r'(?:进入|上台|进场|穿越|穿行|闯入)'
        return bool(re.search(person + r"[^。;；|]{0,60}" + ban
                             + r"[^。;；|]{0,6}" + entry + r"[^。;；|]{0,16}" + area, text)
                    or re.search(ban + r"[^。;；|]{0,12}" + person
                                 + r"[^。;；|]{0,6}" + entry + r"[^。;；|]{0,16}" + area, text)
                    or re.search(area + r'[^。;；]{0,80}' + person
                                 + r'[^。;；|]{0,6}' + ban + r'[^。;；|]{0,6}' + entry, text)
                    or re.search(area + r"[^。;；|]{0,50}不(?:对|向)" + person + r"开放", text)
                    or re.search(area + r'[^。;；]{0,70}(?:仅|只允许|限)(?:允许)?'
                                 r'(?:表演人员|工作人员|演员)(?:和|及|、|/演员|/工作人员){0,8}进入', text)
                    or re.search(area + r'[^。;；|]{0,12}(?:内)?无' + person + r'[^。;；|]{0,6}进入', text))
    if rule["id"] == "assistance":
        # Admission-ticket distribution is not distribution of teaching materials.
        obj = r"(?:材料|物料|粽叶|麻绳|工具|器具|教具|剪刀|利器)"
        action = r"(?:分发|发放|配发)(?!数|量|记录|台账)"
        distribution = action + r"[^。;；|、,]{0,8}" + obj + "|" + obj + r"[^。;；|、,]{0,16}" + action
        adopted_distribution = any(
            not re.search(r"(?:未|不|停止|暂停|无需|不再|不得|禁止)[^。;；|、,]{0,4}$",
                          text[max(0, match.start() - 8):match.start()])
            for match in re.finditer(distribution, text)
        )
        return bool(
            adopted_distribution
            or re.search(r"(?:引导|组织|安排)[^。;；|]{0,16}(?:就座|入座|入席)", text)
            or re.search(r"巡回(?:指导|辅导)|指导[^。;；|]{0,8}(?:操作|制作)", text)
        )
    if rule["id"] == "photo-handoff":
        # Recording a pending selection status does not perform media selection.
        return bool(re.search(
            r"(?<!需)(?<!待)(?<!未)(?:精选|筛选|初筛|选取|选出|选片|挑选)[^。;；|]{0,12}(?:照片|图片)"
            r"|(?:照片|图片)[^。;；|]{0,16}(?<!需)(?<!待)(?<!未)(?:精选|筛选|初筛|选取|选出|选片|挑选)",
            text,
        ) or (
            re.search(r"照片|图片", text)
            and re.search(r"(?<!需)(?<!待)(?<!未)(?:精选|筛选|初筛|选取|选出|选片|挑选)(?:后|并|完成)", text)
        ))
    if rule["id"] == "video-review":
        if re.search(r"照片|图片", text) and not re.search(r"视频|剪辑", text):
            return False
        adopted_review = re.search(
            r"(?:视频|剪辑|成片)[^。;；|]{0,45}(?:发布|外发)前"
            r"[^。;；|]{0,24}(?:审批|审核|审阅|复核)由"
            r"(?:人员[甲乙丙丁戊]|负责人|总控|主办方)[^。;；|]{0,8}确认",
            text,
        )
        if adopted_review and not re.search(r"是否|无需|不用|不必|不需要", adopted_review[0]):
            return True
        delegated_review = re.search(
            r'(?:视频|剪辑|成片)[^。;；|]{0,45}(?:发布|外发)前(?:必须|须|应)?'
            r'由[^。;；|]{0,24}(?:审批人|审核人)[^。;；|]{0,6}(?:确认|批准|审核)', text)
        pending_chain = re.search(
            r'(?:视频|剪辑|成片)[^。;；|]{0,45}(?:发布|外发)前'
            r'按[^。;；|]{0,16}(?:审批|审核)链执行', text)
        if any(match and not re.search(r'是否|无需|不用|不必|不需要', match[0])
               for match in (delegated_review, pending_chain)):
            return True
        if ('|' in text and re.search(r'视频|剪辑|成片', text)
                and any(re.search(r'(?:发布|外发)(?:前)?(?:审批|审核|审阅|复核)'
                                  r'(?:须|应|必须)?(?:另行)?(?:完成|执行)', cell)
                        and not re.search(r'是否|无需|不用|不必|不需要|仅照片|仅图片|照片发布', cell)
                        for cell in text.split('|'))):
            return True
        # A table's product cell scopes its explicit prepublication duty;
        # a pending approver-name cell does not withdraw that duty.
        product = text.split('|', 1)[0]
        if ('|' in text and re.search(r'视频|剪辑|初稿|成片', product)
                and not re.search(r'是否|待确认|未确认|不(?:需要|用|必|审核|审批)', product)
                and any(re.search(r'(?:发布|外发)前(?:必须|须|应)?(?:审批|审核|审阅|复核)(?!状态|人|流程)', c)
                        and not re.search(r'是否|待确认|未确认|无需|不用|不必', c)
                        for c in re.split(r'[。;；|]', text))
                and not re.search(r'照片(?:发布|外发)前|仅(?:照片|图片)', text)):
            return True
        # Pending approver identity does not withdraw an explicit review obligation.
        clauses = re.split(r'[。;；|]', text)
        text = ';'.join(c for c in clauses if not re.search(r'待确认|未确认|未载', c)
                        or re.search(r'必须|须经|须提交|须审核|应提交|审核后|审批后', c))
        text = re.sub(r'(?:确认|核实)(?:审批人|审核人|审批流程|审核流程)', '', text)
        carrier = r'(?:视频|剪辑|初稿|成片)'
        review = r'(?:审核|审阅|审批|复核)'
        link = r'(?:(?!照片|图片|用图|。|；|;).){0,60}'
        for clause in re.split(r'[。;；|]', text):
            if re.search(r'(?:审批|审核)(?:人|流程|与口径|状态)', clause) and not re.search(
                    r'必须|须经|须提交|须审核|应提交|审核后|审批后', clause):
                continue
            if re.search(r'(?:审批|审核)(?:人|流程|与口径|状态).{0,12}(?:待确认|未确认)', clause) and not re.search(
                    r'必须|须经|须提交|须审核|应提交|审核后|审批后', clause):
                continue
            if re.search(carrier + link + review, clause) or re.search(review + link + carrier, clause):
                return True
        return False
    if rule["id"] == "audience-flow":
        return bool(re.search(r"引导|疏导|分流|维护|控制|维持|划定", text))
    if rule["id"] == "weather-authority":
        # A pending weather-resource question is not an adopted decision policy.
        return bool(re.search(r"决定|判断|暂停|改期|转移|调整|停.?复演|批准|终止", text))
    if rule["id"] in {"stage-control", "overall-control"}:
        text = re.sub(
            r"[^。;；|]*(?:是否|有无|未明确|未列|未指定|不完整|须确认|需确认)[^。;；|]*",
            "", text,
        )
    if rule["id"] == "stage-control":
        action = r"(?:检查|控制|播放|调试|测试|试音|排查|保障|负责(?!人))"
        obj = r"(?:设备|音乐|音响|音控|话筒|表演流程|U盘)"
        return bool(re.search(action + r"[^。;；|]{0,12}" + obj, text)
                    or re.search(obj + r"[^。;；|]{0,6}" + action, text))
    if rule["id"] == "overall-control":
        text = re.sub(
            r"[^。;；|]*(?:若同时|是否兼任|不假定|不能同时|不宜同时)[^。;；|]*", "", text
        )
        action = r"(?:把控|调度|协调(?!人|岗)|负责(?!人)|指挥(?!链)|统筹(?!岗)|裁决|掌握|下达)"
        obj = r"(?:现场|全场|全程|跨区|两区|各岗|场次|运行|节奏|异常|问题|指令|变更)"
        return bool(re.search(action + r"[^。;；|]{0,18}" + obj, text)
                    or re.search(r"跨区调度|全程把控|现场指挥(?!链)|场次调度|全场把控|全场统筹", text)
                    or re.search(r"统一发令|统一决策", text))
    if rule["id"] == "debrief":
        action = r"(?:汇总|记录|填写|反馈|总结|复盘|小结)"
        issue = r"(?:问题|异常|事件|未结事项|未完成事项|未决事项|未解决|改进)"
        for clause in re.split(r"[。;；|,，]", text):
            if re.search(r"留空|未填写|待填写|是否|待确认|无需|不用|不必|不记录", clause):
                continue
            if (re.search(action + r"[^。;；|]{0,45}" + issue, clause)
                    or re.search(issue + r"[^。;；|]{0,30}(?:反馈|总结|复盘|小结)", clause)):
                return True
        return False
    return True


def positive_candidates(rule: dict, spans: list[dict]) -> list[dict]:
    """Inherit explicit section context; compose only related closeout duties."""
    result = list(spans)
    result.extend(paired_candidates(spans, rule['id'], normalize))
    contexts = {
        'inventory-preparation': r'准备|筹备|前期|开场',
        'overflow-alternative': r'满场|满额|超限|替代方案',
        'stage-surface': r'广场|舞台|表演|开场检查',
        'props-cables': r'广场|舞台|表演|开场检查',
        'debrief': r'收尾|闭场|清场|复盘',
        'controlled-access': r'儿童|游客|观众|受邀互动|表演|舞台|广场',
    }
    for span in spans:
        section = span.get('section', '')
        if rule['id'] in contexts and re.search(contexts[rule['id']], section):
            result.append({**span, 'normalized': normalize(section) + ':' + span['normalized']})
    if rule["id"] in {"weather-authority", "weather-communication", "continuous-coverage", "debrief"}:
        for span in spans:
            section = span.get("section", "")
            relevant = (re.search(r"天气|气象", section) if rule["id"].startswith("weather-") else
                        re.search(r"轮休|休息|用餐|午餐", section) if rule["id"] == "continuous-coverage" else
                        re.search(r"每日|当日|收尾|闭场", section))
            if relevant:
                result.append({**span, "normalized": normalize(section) + ":" + span["normalized"]})
    return result


def active_match(rule: dict, span: dict) -> bool:
    text = span["normalized"]
    boundary = boundary_decision(rule['id'], span)
    if boundary is not None:
        return boundary
    if rule["id"] == "overall-control":
        return overall_control(text) and not re.search(r"关键词|评分项|rubric|仅供选择|不执行", text, re.I)
    if rule['id'] == 'first-aid-provision' and medical_readiness(text):
        return not re.search(r'关键词|评分项|rubric', text, re.I)
    if span.get('verified_assertion') == rule['id']:
        return not re.search(r'关键词|评分项|rubric|仅供选择|不执行', text, re.I)
    if rule["id"] == "child-supervision" and WITHDRAWAL.match(text):
        clauses = re.split(r"[。;；,，]", text)
        return len(clauses) > 1 and any(
            active_match(rule, {**span, "normalized": clause})
            for clause in clauses if clause and not WITHDRAWAL.match(clause)
        )
    if rule["id"] == "conditional-shared-staff":
        # Equivalent split-post plans must not need one literal signup label.
        paired_zones = bool(re.search(r"广场|表演", text) and re.search(r"大厅|体验|签到|核验", text))
        staffing = bool(re.search(r"人员|工作人员|志愿者|岗位|值守|主责|总控|实名覆盖|同一人", text))
        split = bool(
            re.search(r"不能.*(?:同时|重叠时段).*(?:值守|占岗|兼顾)|不得.*(?:兼任|占岗|同时承担)|禁止跨区.*关键岗", text)
            or re.search(r"固定(?:核销|体验协助)|常驻\d+人", text)
            and re.search(r"替补|补位|机动|暂停|缺口", text)
            or re.search(r"主责.*次级职责.*(?:间|后).*穿插", text)
        )
        if paired_zones and staffing and split and not re.search(r"关键词|仅供选择|不执行", text):
            return True
    if rule["id"] in {"weather-authority", "weather-communication", "instructor-delay", "performer-disruption"}:
        # Cancelling an event is a response, not withdrawal of the response duty.
        text = re.sub(
            r"(?<!不)取消(?![的天气应急]{0,4}(?:通知|告知|通报|同步|传达|决策|决定|判断|流程|机制|说明|联系|等待|等候|引导|安抚|上报))",
            "终止", text,
        )
    if rule["id"] == "first-aid-provision":
        # Asking whether supplies exist is not a proposal to provide them.
        text = re.sub(
            r"[^。;；|]*(?:是否|有无|需核实|待核实)[^。;；|]*", "", text
        )
    response_withdrawal = r"不(?:调整|联系|上报|替补|换人|补救)"
    if rule["id"] == "performer-disruption" and (
        WITHDRAWAL.search(text) or re.search(response_withdrawal, text)
    ):
        if WITHDRAWAL.match(text):
            return False
        # The condition scopes both alternatives; withdrawing supplies does not
        # withdraw an independently adopted script adjustment or escalation.
        condition = re.search(
            r"(?:演员|表演人员|表演队|表演者|主持人|主持|NPC)[^。;；|,，:：]{0,24}(?:不适|生病|缺席|身体异常|缺失|缺位|未到)", text
        )
        if condition:
            response = text[condition.end():].lstrip(":：,，")
            return any(
                active_match(rule, {**span, "normalized": condition[0] + ":" + clause})
                for clause in re.split(r"[。;；,，]|或者|或", response)
                if clause and not WITHDRAWAL.search(clause)
                and not re.search(response_withdrawal, clause)
            )
    if WITHDRAWAL.match(text) or text.count("、") > 15 or text.count("|") > 8:
        return False
    if not all(re.search(pattern, text) for pattern in rule["all"]):
        if rule['id'] != 'child-supervision':
            return False
        # A mandatory supervision duty may precede the named accompanying adult.
        if not all(re.search(pattern, text) for pattern in rule['all'][:-1]):
            return False
        if not duty_action(rule, text):
            return False
    if not duty_action(rule, text):
        return False
    # Reject bare concept lists, alternatives and explicit cancellation.
    if re.search(r"关键词|评分项|rubric|仅供选择|不执行", text, re.I):
        return False
    if WITHDRAWAL.search(text):
        # A cancellation in a different sentence must not suppress a valid duty.
        return any(
            all(re.search(p, sentence) for p in rule["all"])
            and duty_action(rule, sentence)
            and not WITHDRAWAL.search(sentence)
            for sentence in re.split(r"[。;；,，]" if rule["id"] == "child-supervision" else r"[。;；]", text)
        )
    return True


def wrong_day_program(sentence: str) -> bool:
    # Bind an activity only within its own date segment, never across the next date.
    sentence = re.sub(
        r'(?:与|和|同)(?:6月)?(?:19|20)日(?:的)?(?:结构|时段|流程)?(?:一致|相同|相似)',
        '', sentence,
    )
    dates = list(re.finditer(r"(?:6月)?(?P<day>19|20)日", sentence))
    for index, date in enumerate(dates):
        end = dates[index + 1].start() if index + 1 < len(dates) else len(sentence)
        segment = sentence[date.end():end]
        wrong = r"采茶戏|香囊|合香" if date['day'] == '19' else r"傩舞|碱水粽|包粽"
        for match in re.finditer(r"(?:安排|举办|开展|为|:)\s*(?:" + wrong + r")", segment):
            prefix = segment[max(0, match.start() - 8):match.start()]
            if not re.search(r"(?:不|未|不得|禁止|不能|无需|不用)[^,，|]{0,5}$", prefix):
                return True
    return False


def child_supervision_removed(sentence: str) -> bool:
    if not re.search(r"儿童|孩子|小朋友|未成年", sentence):
        return False
    supervision = r"(?:监督|看护|监护|陪同)"
    patterns = [
        r"(?:无需|不用|不必|不需要)[^,，;；。|]{0,12}" + supervision,
        r"(?:取消|省略)(?:对)?(?:儿童|孩子|小朋友|未成年)?(?:的|成人|助教|老师|工作人员){0,3}" + supervision,
        supervision + r"(?:机制|措施|安排|职责|工作)?(?:已|被|可|可以|予以|将)?(?:取消|省略)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, sentence):
            prefix = sentence[max(0, match.start() - 8):match.start()]
            if not re.search(r"(?:不得|不能|不可|严禁|禁止|不应|不|勿)[^,，;；。|]{0,4}$", prefix):
                return True
    return False


def damages(spans: list[dict], params: dict) -> list[dict]:
    found = {}
    for span in spans:
        for sentence in re.split(r"[。;；]", span["normalized"]):
            if PROPOSAL.search(sentence):
                continue
            triggers = []
            if re.search(
                r"(每场|单场|本场|每轮|本轮|体验).{0,24}(不限制人数|不限人数|无限制|不限名额|不设人数上限|人数不设上限|无人数上限|人数不封顶)",
                sentence,
            ):
                triggers.append("D01")
            # Never skip an earlier quantity to bind a daily total to one session.
            capacities = re.finditer(
                r"(?:每场|单场|本场)(?:[^\d。;；|]{0,15}(?:限|上限|容量|安排|接纳|接待|容纳|开放|允许|控制)(?:为|是|达|至)?)?(\d+)人",
                sentence,
            )
            if any(int(capacity[1]) > 40 for capacity in capacities):
                triggers.append("D01")
            flexible_capacities = re.finditer(
                r"(?:每场|单场|本场|每轮|本轮|体验)[^。;；|]{0,24}"
                r"(?:可|可以|允许)(?:超过|突破)\s*(\d+)\s*人",
                sentence,
            )
            if any(int(capacity[1]) >= 40 for capacity in flexible_capacities):
                triggers.append("D01")
            stated_limits = re.finditer(
                r"(?:每场|单场|本场|每轮|本轮|体验)?[^。;；|]{0,12}"
                r"人数上限(?:为|是|:|：)?\s*(\d+)\s*人?",
                sentence,
            )
            if any(int(capacity[1]) > 40 for capacity in stated_limits):
                triggers.append("D01")
            if wrong_day_program(sentence):
                triggers.append("D02")
            if child_supervision_removed(sentence):
                triggers.append("D03")
            if re.search(
                r"(?:观众|游客|任何人).{0,12}(?:自由|随意|不限).{0,8}(?:进入舞台|上台)",
                sentence,
            ) and not re.search(
                r"不得|不能|禁止|严禁|不允许|互动|受控|引导|组织", sentence
            ):
                triggers.append("D04")
            if WITHDRAWAL.match(sentence):
                # A cancelled duty is not adopted; removal of child supervision is itself harmful.
                triggers = [item for item in triggers if item == "D03"]
            for item in triggers:
                key = params["deduction_items"][item]["damage_key"]
                if key not in found:
                    found[key] = {
                        "damage_key": key,
                        "causal_root_id": item,
                        "item": item,
                        "points": params["deduction_points"][item],
                        "manifestations": [],
                    }
                found[key]["manifestations"].append(
                    {"manifestation_id": span["location"], "evidence": sentence}
                )
    conflicts = schedule_conflicts(spans)
    if conflicts:
        item = "D08"
        key = params["deduction_items"][item]["damage_key"]
        found[key] = {"damage_key": key, "causal_root_id": item, "item": item,
                      "points": params["deduction_points"][item],
                      "manifestations": conflicts}
    return list(found.values())


def resolve_artifact(root: Path) -> Path:
    # Harness passes a workspace, repo check_package passes its output directory.
    return (
        root / "execution-plan.docx"
        if root.name == "output"
        else root / "output/execution-plan.docx"
    )


def evaluate(root: Path, *, output_only: bool = False, check_protected_inputs: bool = False, semantic_logs: Path | None = None) -> dict:
    params = json.loads((HERE / "scoring_params.json").read_text(encoding="utf-8"))
    assert set(params["positive_weights"]) == set(params["positive_items"])
    if "assertion_weights" in params:
        assert set(params["assertion_weights"]) == set(params["positive_items"])
    assert (
        sum(params["assertion_counts"].values()) == params["expected_assertions_total"]
    )
    assert sum(Decimal(str(w)) for w in params["positive_weights"].values()) == Decimal(
        1
    )
    artifact = resolve_artifact(root)
    error = None
    spans = []
    try:
        spans = units(extract(artifact))
    except Exception as exc:
        error = f"{type(exc).__name__}: deliverable missing or not readable as editable DOCX"
    positive = Decimal(0)
    items = []
    positive_review = None
    semantic_checks = {}
    if spans:
        from positive_judge import measure as measure_positive
        destination = semantic_logs if semantic_logs is not None else Path(tempfile.mkdtemp(prefix='festival-positive-review-'))
        positive_review = measure_positive(artifact, spans, destination)
        semantic_checks = {row['id']: row for row in positive_review['assessments']}
    evidence_by_id = {'C-' + row['location']: {**row, 'normalized': normalize(row['text'])}
                      for row in extract(artifact) if row['scope'] != 'table-duty'} if spans else {}
    for pid, item in params["positive_items"].items():
        if pid == "P13":
            checks = facts(spans)
            for check, rule in zip(checks, item["assertions"]):
                check["anchor"] = rule["anchor"]
        else:
            checks = []
        for rule in ([] if pid == "P13" else item["assertions"]):
            semantic = semantic_checks.get(rule['id'])
            if semantic is not None:
                matched = evidence_by_id[semantic['evidence_ids'][0]] if semantic['passed'] else None
            else:
                matched = next((s for s in positive_candidates(rule, spans) if active_match(rule, s)), None)
            checks.append(
                {
                    "id": rule["id"],
                    "passed": matched is not None,
                    "anchor": rule["anchor"],
                    "evidence": matched,
                }
            )
        declared = params["assertion_counts"][pid]
        assert declared == len(checks)
        weight = Decimal(str(params["positive_weights"][pid]))
        assertion_weights = params.get("assertion_weights")
        if assertion_weights is None:
            completion = Decimal(sum(c["passed"] for c in checks)) / Decimal(declared)
            earned = weight * completion
        else:
            local = assertion_weights[pid]
            assert set(local) == {c["id"] for c in checks}
            values = {key: Decimal(str(value)) for key, value in local.items()}
            assert all(value > 0 and value * 100 == (value * 100).to_integral_value()
                       for value in values.values())
            assert sum(values.values(), Decimal(0)) == weight
            for check in checks:
                check["weight"] = float(values[check["id"]])
            earned = sum((values[c["id"]] for c in checks if c["passed"]), Decimal(0))
            completion = earned / weight
        positive += earned
        items.append(
            {
                "id": pid,
                "capability": item["capability"],
                "weight": params["positive_weights"][pid],
                "completion": float(completion),
                "earned": float(earned),
                "assertions": checks,
            }
        )
    deductions = damages(spans, params)
    for item, manifestations in contradictions(spans).items():
        deductions.append({
            "damage_key": params["deduction_items"][item]["damage_key"],
            "causal_root_id": item, "item": item,
            "points": params["deduction_points"][item],
            "manifestations": manifestations,
        })
    trusted = HERE / "ground_truth.json"
    workspace = root.parent if root.name == "output" else root
    source_check = not output_only and (check_protected_inputs or (workspace / "materials").is_dir())
    if trusted.is_file() and source_check:
        sources = json.loads(trusted.read_text(encoding="utf-8"))["protected_inputs"]
        changed = []
        for name, expected in sources.items():
            source = workspace / "materials" / name
            if source.is_symlink() or not source.is_file():
                changed.append(
                    {"manifestation_id": name, "evidence": "protected input missing or symlink"}
                )
            elif hashlib.sha256(source.read_bytes()).hexdigest() != expected:
                changed.append(
                    {"manifestation_id": name, "evidence": "trusted input hash differs"}
                )
        if changed:
            deductions.append(
                {
                    "damage_key": "source-tampering",
                    "causal_root_id": "D05",
                    "item": "D05",
                    "points": params["deduction_points"]["D05"],
                    "manifestations": changed,
                }
            )
    factual_review = None
    if spans:
        import fact_judge
        destination = semantic_logs if semantic_logs is not None else Path(tempfile.mkdtemp(prefix='festival-factual-review-'))
        factual_review = fact_judge.measure(artifact, spans, destination)
        from fact_scope import measure as measure_scope
        factual_review = measure_scope(factual_review, artifact, spans, destination)
        exclusions=[]
        for finding in factual_review['findings']:
            reason=('Generic unnamed instructor role with identity pending is not a verified credential.'
                    if generic_instructor_exemption(finding) else
                    scope_exclusion(finding,spans) or
                    source_group_exclusion(finding,fact_judge.source_dir()))
            if reason:exclusions.append({'finding':finding,'reason':reason})
        exempted = [row['finding'] for row in exclusions]
        if exempted:
            factual_review = {**factual_review,
                              'provider_findings': factual_review.get('provider_findings',factual_review['findings']),
                              'source_scope_exclusions': factual_review.get('source_scope_exclusions',[])+exclusions,
                              'findings': [row for row in factual_review['findings'] if row not in exempted]}
        if factual_review['findings']:
            factual_penalty = Decimal(str(params['curvature']['fixed_penalties']['D09']))
            deductions.append({'damage_key': params['deduction_items']['D09']['damage_key'],
                               'causal_root_id': 'D09', 'item': 'D09',
                               'points': float(factual_penalty),
                               'application': 'one independent factual-integrity event',
                               'manifestations': factual_review['findings']})
    deducted = sum(
        (Decimal(str(instance["points"])) for instance in deductions), Decimal(0)
    )
    strict_settlement = settle(positive, deducted, power=params['curvature']['positive_power'],
                               retention=params['curvature']['minimum_retention'])
    raw = strict_settlement['raw_score']
    strict = strict_settlement['reward']
    assertions = {check['id']: bool(check['passed']) for item in items for check in item['assertions']}
    hard_assertions = ('capacity-enforcement', 'child-supervision', 'controlled-access',
                       'day-19-program', 'day-20-program', 'fixed-craft-slots', 'two-source-zones')
    harmful = {instance['item'] for instance in deductions}
    lenient_checks = {
        'readable_editable_docx': error is None,
        'minimum_capacity_control': assertions.get('capacity-enforcement', False),
        'minimum_child_safety': assertions.get('child-supervision', False),
        'minimum_stage_access_control': assertions.get('controlled-access', False),
        'source_programs_slots_and_zones': all(assertions.get(key, False) for key in hard_assertions[3:]),
        'no_adopted_business_harm': not harmful,
    }
    lenient = int(all(lenient_checks.values()))
    return {
        "schema_version": params['schema_version'],
        "judge_version": params["judge_version"],
        "artifact": "output/execution-plan.docx",
        "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()
        if artifact.is_file() and not artifact.is_symlink()
        else None,
        "parse_error": error,
        "positive_items": items,
        "positive_earned": float(positive),
        "positive_utility": strict_settlement['positive_utility'],
        "positive_review": positive_review,
        "settlement": params['curvature'],
        "deductions": deductions,
        "deduplicated_deductions": float(deducted),
        "raw_score": float(raw),
        "rewards": {"strict": strict, "lenient": lenient},
        "reward_strict": strict,
        "reward_lenient": lenient,
        "lenient_checks": lenient_checks,
        "failed_lenient_checks": [key for key, value in lenient_checks.items() if not value],
        "normalizations": [
            "Unicode NFKC",
            "whitespace",
            "Chinese forty",
            "overall-coordinator alias",
            "lecturer-teacher role alias",
            "role inheritance within one table row",
            "alternative business verbs",
            "clause polarity",
            "bare concept-list filtering",
        ],
        "factual_review": factual_review,
        "not_observable": ["Visual layout and independent verification of facts outside the supplied materials"],
        "paid_model_calls": (positive_review['model_calls'] if positive_review else 0) +
        ((1 + int('adjudication' in factual_review)) if factual_review and factual_review['model_called'] else 0) +
        ((factual_review.get('scope_audit') or {}).get('model_calls',0) if factual_review else 0),
        "source_verification": "workspace-protected-inputs" if source_check else "detached-artifact-only",
    }


def write_rewards(detail: dict, logs: Path) -> None:
    logs.mkdir(parents=True, exist_ok=True)
    for name, score in (
        ("reward.txt", detail["reward_strict"]),
        ("reward_strict.txt", detail["reward_strict"]),
        ("reward_lenient.txt", detail["reward_lenient"]),
    ):
        (logs / name).write_text(f"{score:.17g}\n", encoding="utf-8")
    (logs / "reward.json").write_text(
        json.dumps(
            {
                "reward": detail["reward_strict"],
                "reward_strict": detail["reward_strict"],
                "reward_lenient": detail["reward_lenient"],
                **detail["rewards"],
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    (logs / "verify_result.json").write_text(
        json.dumps(detail, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (logs / "reward_detail.json").write_text(
        json.dumps(detail, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", type=Path)
    ap.add_argument("--logs", type=Path)
    source_mode = ap.add_mutually_exclusive_group()
    source_mode.add_argument("--output-only", action="store_true", help="Score a detached artifact without a source workspace.")
    source_mode.add_argument("--check-protected-inputs", action="store_true", help="Require every protected input, even if the entire materials directory was removed.")
    args = ap.parse_args()
    try:
        detail = evaluate(args.root, output_only=args.output_only, check_protected_inputs=args.check_protected_inputs,
                          semantic_logs=args.logs)
    except Exception as exc:
        if args.logs:
            args.logs.mkdir(parents=True, exist_ok=True)
            for name in ('reward.json', 'reward.txt', 'reward_strict.txt', 'reward_lenient.txt'):
                (args.logs / name).unlink(missing_ok=True)
            (args.logs / 'verifier_status.json').write_text(json.dumps({
                'status': 'unmeasured', 'measurement_complete': False, 'business_zero_inferred': False,
                'error_type': type(exc).__name__, 'error': str(exc)}, ensure_ascii=False, indent=2))
        raise
    if args.logs:
        write_rewards(detail, args.logs)
    print(json.dumps(detail, ensure_ascii=False))


if __name__ == "__main__":
    main()

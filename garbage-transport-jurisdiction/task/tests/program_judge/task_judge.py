"""Deterministic, case-local legal document observations and scoring."""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree as ET

from program_judge_runtime import Locator, ProgramJudge, load_contract, sha256

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
DEFAULT_CONTRACT = next(
    (parent / "rubric-contract.json" for parent in Path(__file__).resolve().parents
     if (parent / "rubric-contract.json").is_file()),
    Path(__file__).resolve().parent.parent / "rubric-contract.json",
)


def text_of(node):
    excluded = {"{" + NS["w"] + "}del", "{" + NS["w"] + "}instrText"}
    if node.tag in excluded:
        return ""
    if node.tag == "{" + NS["w"] + "}t":
        return node.text or ""
    return "".join(text_of(child) for child in node)


def extract_raw(artifact):
    records, failures = [], []
    paths = sorted(artifact.glob("*.docx")) if artifact.is_dir() else [artifact]
    for path in paths:
        try:
            with ZipFile(path) as archive:
                tree = ET.fromstring(archive.read("word/document.xml"))
                parts = []
                body = tree.find("w:body", NS)
                if body is None:
                    raise ValueError("DOCX has no body")
                for index, node in enumerate(body):
                    if node.tag.endswith("}tbl"):
                        for row_index, row in enumerate(node.findall("w:tr", NS)):
                            value = " | ".join(text_of(cell) for cell in row.findall("w:tc", NS))
                            if value.strip():
                                parts.append((f"body/{index}/row/{row_index}", value))
                    else:
                        value = text_of(node)
                        if value.strip():
                            parts.append((f"body/{index}", value))
                records.append({"path": path, "parts": parts})
        except (OSError, ValueError, KeyError, ET.ParseError, RuntimeError, BadZipFile) as exc:
            failures.append({"path": path, "error": type(exc).__name__})
    return {"documents": records, "failures": failures}


def clean(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value))


def has(pattern, value):
    return re.search(pattern, value, re.I | re.S) is not None


def resolve_role(record):
    name = record["path"].name.lower()
    full = "\n".join(text for _, text in record["parts"])
    if "蒙柳钰" not in full or "黄家平" not in full:
        return None
    opening = full[:450]
    titles = "\n".join(value for _, value in record["parts"][:3] if len(value) < 80)
    petition = has(
        r"管辖.{0,12}(申请|说明|复核)|立案.{0,12}(复核|申请|说明)|"
        r"(?:^|\n)\s*(?:立案)?复议申请书\s*(?:\n|$)",
        titles,
    )
    request = has(r"(协助|请求|调取|提供).{0,16}(证据|材料)|取证函|(证据|材料).{0,18}(协助|提供|请求|申请)", titles)
    if petition and not request:
        return "jurisdiction"
    if request:
        content_candidates = [
            role for role, site in (("feng", "风格雨林"), ("tian", "天广和"))
            if site in opening
        ]
        if len(content_candidates) == 1:
            return content_candidates[0]
        filename_candidates = [
            role for role, alias in (("feng", "feng-request"), ("tian", "tian-request"))
            if alias in name
        ]
        if len(filename_candidates) == 1:
            return filename_candidates[0]
    return None


def sections(record):
    result, current = [], []
    for position, value in record["parts"]:
        if has(r"^[一二三四五六七八九十]+[、.]|^[（(][一二三四五六七八九十]+[)）]|^(申请事项|事实与理由|事实和理由|请求事项)[：:]?", value) and current:
            result.append(current)
            current = []
        current.append((position, value))
    if current:
        result.append(current)
    return result


def adopted(value):
    return not has(r"仅供参考|备选方案|未决候选|尚未决定|可能的方案|观点引用|反面示例|不予采纳|不采纳以下|不主张以下|以下并非.{0,8}(本方)?主张|不作为.{0,10}(请求|结论|主张)|以下.{0,8}(错误|引文)|待核实的观点", value)


def contradicts_positive(identity, value):
    """Reject an expressly adopted opposite conclusion, not merely an omission."""
    v = clean(value)
    author = r"(?:(?:申请人|本申请|本方)(?:明确)?(?:认为|主张|确认|认定|结论为)|(?:综上|因此|故)(?:认为|可见|应认定)?)"
    opposite_disposition = (
        r"该处理具有法律依据",
        r"退回材料具有法律依据",
        r"拒绝受理具有法律依据",
        r"不予立案具有法律依据",
        r"退回材料合法",
        r"该处理合法",
        r"该处理正确",
        r"退回材料应予维持",
    )
    if identity in {"P01", "P02", "P03", "P04"} and any(
        has(author + r".{0,30}" + phrase, v) for phrase in opposite_disposition
    ):
        return True
    if identity == "P01":
        return has(
            author + r".{0,30}(?:(本案|该法律关系).{0,20}(不属于|不构成|不符合).{0,12}(运输合同|运输合同纠纷)|"
            r"(未形成|没有形成|不能形成).{0,12}(事实上的)?运输合同(关系)?)",
            v,
        )
    if identity == "P02":
        return has(
            author + r".{0,30}(?:(江南区|贵院).{0,12}(不享有|不具有|无|没有).{0,8}管辖权|"
            r"(始发地|起运地|目的地).{0,18}(不能|不构成|并非).{0,12}(管辖依据|管辖连接点))",
            v,
        )
    if identity == "P03":
        return has(
            author + r".{0,30}(?:(被告住所地).{0,18}(是|属于).{0,8}唯一.{0,8}(管辖|连接点)|"
            r"(选择|向).{0,28}(江南区|贵院).{0,18}(起诉|管辖).{0,18}(不符合|不合法|无权))",
            v,
        )
    if identity == "P04":
        return has(
            author + r".{0,30}(?:(贵院|江南区).{0,20}(不应|不得|不能).{0,10}(受理|立案)|"
            r"不请求.{0,12}(受理|立案|管辖))",
            v,
        )
    return False


def evidence_blocks(record):
    """Retain bounded sections and paragraph windows, including table rows."""
    seen = set()
    for section in sections(record):
        candidates = [section]
        for index in range(len(section)):
            candidates.extend(section[index:index + n] for n in (1, 2, 3, 4))
        for block in candidates:
            key = tuple(p for p, _ in block)
            if key in seen or len(clean('\n'.join(v for _, v in block))) > 1800:
                continue
            seen.add(key)
            yield block


def request_scope(record, role):
    """Resolve a request's explicit event, before accepting its anaphoric references."""
    if role not in {'feng', 'tian'}:
        return False
    site = '风格雨林' if role == 'feng' else '天广和'
    date = r'2026年4月27日|2026-0?4-27' if role == 'feng' else r'2026年5月11日|2026-0?5-11'
    for block in evidence_blocks(record):
        v = clean('\n'.join(value for _, value in block))
        if not adopted(v):
            continue
        if site in v and has(date, v) and '桂A3V5X9' in v and (role == 'feng' or '桂A3C1B9' in v):
            return True
    return False


def local_atoms(identity, role, value, scoped=False):
    """Independent reference propositions, each supported by a coherent local span."""
    size = 1 if identity == 'P09' else 2
    if not adopted(value) or len(clean(value)) > 1800:
        return (False,) * size
    v = clean(value)
    if identity == "P01":
        if has(r"(不属于|不是|并非|不能构成).{0,8}运输合同|运输合同.{0,6}(不成立|不适用)", v):
            return (False, False)
        a = has(r"(双方|申请人|原告|本案).{0,90}(口头约定|未签订书面|无书面).{0,260}(形成|构成|符合|属于|应受).{0,24}(运输合同|合同关系|法律保护)", v)
        b = has(r"(申请人|原告).{0,180}(驾驶|车辆|运输工具).{0,160}(运费|450元|按车次|按车).{0,160}(运输合同|合同.{0,5}特征)", v)
        oral = has(r'口头|未签订书面|无书面', v)
        validity = has(r'(口头|未签订书面).{0,65}(不.{0,8}(否定|排除|影响)|亦可|可以成立|合同关系)|口头.{0,80}(形成|成立|构成|属于).{0,15}合同', v)
        adopted_transport = has(r'(本案|该安排|交易结构|义务结构|法律关系|争议核心|主要义务|申请人所述).{0,180}(属于|构成|相符|符合|较符合|更符合|应认定|实质上|运输合同的主要|运输合同关系)|(?:故请求|请求).{0,8}按运输合同纠纷重新审查', v)
        vehicle_fee = has(r'自有车辆|自备车辆|提供车辆|使用车辆|自行提供车辆|运输工具', v) and has(r'450元|按车|运输费用|运费', v)
        unresolved = has(r'劳务合同.{0,25}(服务合同|抑或运输)|是否.{0,10}(成立|构成)运输合同|如.{0,20}(认定|确定)为运输合同', v)
        return (bool(a or (oral and (validity or adopted_transport))), bool((b or (vehicle_fee and adopted_transport)) and not unresolved))
    if identity == "P02":
        if has(r"江南区.{0,12}(不享有|无|没有)管辖权", v):
            return (False, False)
        anchor = has(r"(始发|起运).{0,50}江南区壮锦大道28号|江南区壮锦大道28号.{0,60}(始发|起运)", v)
        connection = has(r"(贵院|江南区.{0,8}法院).{0,28}(作为|属于|系).{0,28}(始发|起运).{0,80}(享有|具有|有).{0,8}管辖|江南区.{0,8}法院.{0,30}(始发|起运).{0,30}管辖|由.{0,12}(始发|起运)地.{0,18}法院管辖", v)
        anchor |= '江南区壮锦大道28号' in v and '风格雨林' in v
        connection |= has(r'(江南区|贵院).{0,160}(始发|起运).{0,150}(管辖|连接点)|(?:始发|起运).{0,160}(江南区|贵院).{0,80}(管辖|连接点)', v) and not has(r'仅为备选|尚未采用', v)
        return (anchor, connection)
    if identity == "P03":
        if has(r"(只能|仅能|必须).{0,15}(博白|被告住所地).{0,15}(起诉|管辖)", v):
            return (False, False)
        a = has(r"被告住所地.{0,20}(并非|不是|非|而非).{0,5}唯一|不得以.{0,30}(博白|被告.{0,8}住所).{0,20}(拒绝|拒不|退回)|博白.{0,90}(均|都有).{0,20}管辖", v)
        b = has(r"(原告|申请人).{0,12}(依法)?(有权|可以|可|选择).{0,100}(江南区|贵院|其中一个|始发地)", v)
        a |= has(r'被告住所地.{0,35}(不是|并非|非|并未|不应|不能).{0,25}唯一|被告住所地并非唯一|被告住所地.{0,35}不.{0,10}排除.{0,30}(始发|起运)|(?:始发地|目的地).{0,45}被告住所地.{0,25}(均可|均有|都有)', v)
        a |= has(r'(并非只有|不只限于|不限于).{0,8}被告住所地', v)
        b |= has(r'(原告|申请人).{0,20}(可|可以|有权|依法可以).{0,12}选择.{0,50}(法院|其中一个|人民法院)', v)
        return (a, b)
    if identity == "P04":
        if has(r"不(请求|主张).{0,12}(受理|立案|管辖)", v):
            return (False, False)
        a = has(r"(请求|申请|恳请).{0,24}(确认|审查|复核).{0,24}江南区.{0,12}法院.{0,15}(管辖|享有)", v)
        b = has(r"(请求|申请|恳请).{0,30}(撤销|纠正|重新审查|复核).{0,30}(退回|拒绝|立案).{0,30}(立案|受理)|请求.{0,35}依法立案受理", v)
        a |= has(r'(确认|审查|复核).{0,140}(江南区|贵院).{0,120}(管辖权|地域管辖|管辖连接点)', v) and has(r'请求|申请|恳请|请|^[一二三四五六七八九十]+、', v)
        a |= has(r'(复核|重新审核|审查).{0,250}江南区.{0,60}运输始发地.{0,60}(请求|依法审查)', v)
        b |= has(r'(请|请求|申请|予以).{0,100}(复核|重新审核|重新审查|纠正).{0,150}(登记立案|受理|立案)|(?:请|请求).{0,40}依法.{0,10}(登记立案|立案受理)', v)
        return (a, b)
    if identity in {"P05", "P07"}:
        if role not in {"feng", "tian"}:
            return (False, False)
        if has(r"不(请求|需要|要求|必提供).{0,12}(合同|结算)", v):
            return (False, False)
        a = has(r"(贵司|贵公司|物业).{0,20}(被告|黄家平).{0,35}(签订|订立|服务|清运).{0,24}(合同|协议).{0,90}(地点|服务期限|结算|频次)", v)
        b = has(r"(贵司|贵公司|物业).{0,20}(被告|黄家平).{0,25}(费用|结算|支付|付款).{0,35}(凭证|记录|对账单|发票)", v)
        request = has(r'提供|请求|核实|调取|协助|查找', v)
        defendant_link = '黄家平' in v or has(r'贵(司|单位|公司|方).{0,25}被告', v)
        a |= request and defendant_link and has(r'合同|协议', v) and has(r'清运|委托|外包|服务|工作指令|指令资料', v)
        a |= scoped and request and has(r'本次清运|该项清运|上述清运', v) and has(r'合同|协议', v) and has(r'派工|委托|工作单|服务|结算', v)
        b |= scoped and request and has(r'本次清运|该清运任务|上述清运|该项清运|本次事件|黄家平|费用结算|结算与付款|计价及结算', v) and has(r'结算|付款|支付', v) and has(r'凭证|记录|对账单|发票|结算单|收据', v)
        return (a, b)
    if identity in {"P06", "P08"}:
        date = r"2026年4月27日|2026-0?4-27" if role == "feng" else r"2026年5月11日|2026-0?5-11"
        if has(r"不(请求|需要|要求).{0,10}(台账|登记|门岗)", v):
            return (False, False)
        ledger = has(r"(提供|保存|调取|核查|登记).{0,100}(清运台账|清运.{0,8}登记|台账).{0,100}桂A3V5X9.{0,70}(?:" + date + r").{0,45}(车次|时间|记录)", v)
        if role == "tian":
            ledger = ledger and "桂A3C1B9" in v
        corroboration = has(r"(门岗|车辆出入|出入口|监控).{0,100}(登记|信息|截图|记录)", v) and has(r"(保安|主管|知情).{0,45}(证言|联系方式|调查|证明)", v)
        ledger |= scoped and has(r'提供|核实|请求|调取|查找', v) and has(r'清运台账|清运.{0,12}(记录|登记)|纸质台账|垃圾清运记录表|原始作业记录', v) and has(r'上述|本次|当日|该日|重点日期|车辆|桂A3V5X9|车次', v)
        gate = has(r'门岗|车辆出入|出入口|道闸|监控', v) and has(r'记录|登记|日志|信息|截图', v)
        witness = has(r'(知情|熟悉记录|能够说明|记录.{0,10}说明|保洁主管|保安).{0,150}(书面|证言|联系方式|联系.{0,10}(部门|方式)|出具.{0,8}说明)|(?:工作人员|记录保管人|门岗人员).{0,90}(出具.{0,10}(说明|证言)|法院联系|法院.{0,15}说明|联系方式)', v)
        corroboration |= scoped and gate and witness
        return (ledger, corroboration)
    if identity == "P09":
        if has(r"已经.{0,12}(调查令|法院命令)|无需.{0,8}(申请|法院)", v):
            return (False,)
        unavailable = has(r'不便提供|无法提供|不能提供|不能直接|无权直接|保密|隐私|权限|方可提供|不得直接披露|需法院', v)
        application = has(r'(请求人|告知人|申请人).{0,40}(可|将|依法|视需要|据此).{0,50}申请.{0,50}(调查令|法院.{0,12}调查|调查取证|调查收集)|(?:告知人|请求人|申请人).{0,40}依法向.{0,15}法院申请调查收集', v)
        return (unavailable and application,)
    if identity == "P10":
        purpose = has(r'(仅|只).{0,18}(用于|本案诉讼|向受理法院|向法院|本争议).{0,55}(诉讼|举证|立案|法院|民事争议)|不用于本案诉讼以外', v)
        confidentiality = has(r'不向.{0,15}第三方.{0,8}泄露|不得.{0,8}泄露|(?:请求人|申请人|告知人).{0,12}(承诺|将|保证).{0,65}(保护|保密|不披露).{0,40}(个人信息|商业秘密|第三方)', v)
        return (purpose, confidentiality)
    return (False,) * size


def local_fraction(identity, role, value):
    atoms = local_atoms(identity, role, value)
    return sum(atoms) / len(atoms)


def locators(record, block, role, artifact_root, prefix):
    raw = Locator(prefix + "/raw", record["path"].relative_to(artifact_root).as_posix(), "docx",
                  ",".join(p for p, _ in block), role, "visible_text", "\n".join(v for _, v in block))
    normalized = Locator(prefix + "/norm", raw.artifact_path, "docx", raw.container_path, role,
                         "canonical_text", clean(raw.observed), evidence_origin="lossless_canonicalized",
                         source_locator_ids=(raw.locator_id,), normalization_rule_id="N-WHITESPACE")
    return [raw, normalized]


def search_evidence(registry, judge, prefix):
    evidence = []
    for index, record in enumerate(registry["documents"]):
        evidence += locators(record, record["parts"], resolve_role(record) or "unresolved", judge.artifact_root, f"{prefix}/searched/{index}")
    if not evidence:
        entries = sorted(p.name for p in judge.artifact_root.iterdir()) if judge.artifact_root.is_dir() else []
        evidence = [Locator(prefix + "/directory", ".", "directory", ".", "submission", "entries", json.dumps(entries, ensure_ascii=False))]
    return evidence


def normalize(registry, judge):
    roles = {role: [] for role in ("jurisdiction", "feng", "tian")}
    for doc in registry["documents"]:
        role = resolve_role(doc)
        if role:
            roles[role].append(doc)
    registry["roles"] = roles
    positive = {}
    leaf_items = {
        item["id"]: item
        for item in judge.contract.get("positive_leaf_items", judge.contract["positive_items"])
    }
    for item in judge.positives.values():
        specs = item.get("member_specs")
        if specs is None:
            specs = [
                {"id": member_id, "predicate_id": member_id}
                for member_id in item.get("member_item_ids", [item["id"]])
            ]
        member_weights = item.get("member_weights", [1 / len(specs)] * len(specs))
        if len(member_weights) != len(specs):
            raise ValueError(f"{item['id']}: member_weights and member_specs differ in length")
        member_totals, evidence, uncertain = [], [], False
        for spec in specs:
            member_id = spec["id"]
            predicate_id = spec.get("predicate_id", member_id)
            leaf = leaf_items[predicate_id]
            item_roles = spec.get("roles")
            if item_roles is None:
                item_roles = ["feng", "tian"] if leaf["scope"] == "both_requests" else [leaf["scope"]]
            atom_count = 1 if predicate_id == "P09" else 2
            atom_indices = spec.get("atom_indices", list(range(atom_count)))
            if not atom_indices or len(set(atom_indices)) != len(atom_indices):
                raise ValueError(f"{item['id']}/{member_id}: atom_indices must be non-empty and unique")
            if any(index < 0 or index >= atom_count for index in atom_indices):
                raise ValueError(f"{item['id']}/{member_id}: atom index outside {predicate_id}")
            fractions = []
            for role in item_roles:
                if role not in roles:
                    raise ValueError(f"{item['id']}/{member_id}: unknown role {role}")
                if len(roles[role]) != 1:
                    fractions.append(0.0)
                    uncertain |= len(roles[role]) > 1
                    continue
                record = roles[role][0]
                contradiction_id = "D02" if predicate_id == "P01" else "D01" if predicate_id in {"P02", "P03"} else None
                if any(contradicts_positive(predicate_id, "\n".join(v for _, v in block)) for block in sections(record)):
                    fractions.append(0.0)
                    continue
                if contradiction_id and any(errors(contradiction_id, "\n".join(v for _, v in block)) for block in sections(record)):
                    fractions.append(0.0)
                    continue
                scoped = request_scope(record, role)
                matches = [(local_atoms(predicate_id, role, '\n'.join(v for _, v in block), scoped), block)
                           for block in evidence_blocks(record)]
                earned = [any(atoms[index] for atoms, _ in matches) for index in atom_indices]
                if predicate_id == "P01" and 0 in atom_indices and not earned[atom_indices.index(0)]:
                    oral_blocks = [block for _, block in matches if adopted('\n'.join(v for _, v in block))
                                   and has(r'双方.{0,30}(口头|未签订书面)', clean('\n'.join(v for _, v in block)))]
                    transport_blocks = [block for atoms, block in matches if atoms[1]]
                    if oral_blocks and transport_blocks:
                        earned[atom_indices.index(0)] = True
                        for label, block in [('oral-facts', min(oral_blocks, key=len)),
                                             ('transport-relation', min(transport_blocks, key=len))]:
                            evidence += locators(record, block, role, judge.artifact_root,
                                                 f"{member_id}/{role}/{label}")
                # Every member is a local business chain. Its linked prerequisites
                # must all be present; partial credit is preserved across owners.
                fractions.append(float(all(earned)))
                for atom in atom_indices:
                    candidates = [(len(clean('\n'.join(v for _, v in block))), index, block)
                                  for index, (atoms, block) in enumerate(matches) if atoms[atom]]
                    if candidates:
                        _, index, block = min(candidates, key=lambda candidate: candidate[0])
                        evidence += locators(record, block, role, judge.artifact_root,
                                             f"{member_id}/{role}/atom{atom}/{index}")
            member_totals.append(sum(fractions) / len(fractions))
        total = sum(value * weight for value, weight in zip(member_totals, member_weights))
        state = "ambiguous" if uncertain else "identified" if evidence else "parse_failure" if registry["failures"] and not registry["documents"] else "confirmed_missing"
        if state != "identified":
            total = 0.0
        observation = judge.observe(item["id"] + "/obs", state, evidence or search_evidence(registry, judge, item["id"]))
        positive[item["id"]] = (total, observation, state)
    return positive


def d04_error_classes(value):
    """Return every affirmative fabricated-fact class in bounded sentences."""
    patterns = {
        "unload_address": r"卸载(具体)?地址(已确认|已经确认|已查明).{0,20}(路|街|号)",
        "photo_settlement": r"(照片|图片).{0,15}(数量|张数).{0,18}(就是|即为|等于).{0,12}(全部|完整).{0,12}(结算车次|欠款)",
        "completed_transport_count": (
            r"(完成|确有|实际完成|已经完成|发生)(了)?.{0,4}(六|6).{0,8}"
            r"(运输|清运|装运|装货|装载|进出场|车次).{0,6}(作业)?"
        ),
        "invented_residence": (
            r"自20\d{2}年\d{1,2}月\d{1,2}日起.{0,50}(租住|居住).{0,80}\d+栋.{0,20}\d+室|"
            r"经常居住地.{0,12}(已经形成|已形成|确定为|位于贵院辖区)"
        ),
    }
    found = set()
    for sentence in re.split(r"[。；;!！?？\n]+", unicodedata.normalize("NFKC", value)):
        v = clean(sentence)
        if not v or has(r"(不能|无法|尚未|未能|不足以|无从).{0,12}(证明|确认|认定)|仍待核实|有待核实|待核实", v):
            continue
        found.update(identity for identity, pattern in patterns.items() if has(pattern, v))
    return sorted(found)


def errors(identity, value):
    if not adopted(value):
        return False
    v = clean(value)
    if identity == "D01":
        return has(r"(本案|此案).{0,15}(只能|仅能|必须).{0,15}(由被告住所地|由博白|向博白).{0,15}(管辖|起诉|受理)", v)
    if identity == "D02":
        return has(r"(无|没有|未签订)书面合同.{0,15}(所以|因此|故|即).{0,15}(合同不成立|不能.{0,5}主张运费|不构成合同)", v)
    if identity == "D03":
        return has(r"(收到本函|收到本告知|本函送达).{0,80}(自动|直接).{0,12}(罚款|拘留)|本案.{0,12}(已签发|已取得|已有).{0,12}(律师调查令|法院调查令)", v)
    if identity == "D04":
        return bool(d04_error_classes(v))
    return False


def affected_owners(identity, role):
    """Bind each adopted harm to the business owners in the affected document."""
    if identity == "D01":
        return ["G_J_ORIGIN", "G_J_FORUM_EXCLUSIVITY", "G_J_FORUM_CHOICE", "G_J_RELIEF"]
    if identity == "D02":
        return ["G_J_RELATION"]
    if identity == "D03":
        return ["G_F_CHANNEL"] if role == "feng" else ["G_T_CHANNEL"]
    if identity == "D04":
        if role == "jurisdiction":
            return [
                "G_J_RELATION", "G_J_ORIGIN", "G_J_RELIEF",
                "G_J_FORUM_EXCLUSIVITY", "G_J_FORUM_CHOICE",
            ]
        if role == "feng":
            return ["G_F_CONTRACT", "G_F_EVENTS"]
        if role == "tian":
            return ["G_T_CONTRACT", "G_T_EVENTS"]
    if identity == "D05":
        return {
            "jurisdiction": [
                "G_J_RELATION", "G_J_ORIGIN", "G_J_RELIEF",
                "G_J_FORUM_EXCLUSIVITY", "G_J_FORUM_CHOICE",
            ],
            "feng": ["G_F_CONTRACT", "G_F_EVENTS", "G_F_CHANNEL", "G_F_PURPOSE"],
            "tian": ["G_T_CONTRACT", "G_T_EVENTS", "G_T_CHANNEL", "G_T_PURPOSE"],
        }[role]
    raise ValueError(f"unsupported deduction scope: {identity}/{role}")


def evaluate(registry, positives, judge):
    for identity, (fraction, observation, state) in positives.items():
        comparison = "equivalent" if fraction == 1 else "partial" if fraction > 0 else "missing" if state == "confirmed_missing" else "different"
        judge.positive(identity, fraction, observation, "局部采用命题按冻结对象及条件规则比较；未命中不等于独立语义审核已判错。", comparison)
    for identity, item in judge.deductions.items():
        observations, occurrences = [], []
        for role, docs in registry["roles"].items():
            for doc in docs:
                blocks = sections(doc)
                for index, block in enumerate(blocks):
                    if identity == "D05":
                        continue
                    value = "\n".join(v for _, v in block)
                    if not errors(identity, value):
                        continue
                    error_classes = d04_error_classes(value) if identity == "D04" else [role]
                    for error_class in error_classes:
                        suffix = f"/{error_class}" if identity == "D04" else ""
                        oid = f"{identity}/{role}/{doc['path'].name}/{index}{suffix}"
                        judge.observe(oid, "identified", locators(doc, block, role, judge.artifact_root, oid))
                        observations.append(oid)
                        key = item["causal_root_rule"] + "/" + error_class
                        occurrences.append({"observation_id": oid, "causal_root_id": key,
                                            "damage_instance_key": key, "manifestation_id": oid,
                                            "affected_owner_ids": affected_owners(identity, role)})
                if identity == "D05":
                    # Retired: Golden-relative length is not a business defect.
                    # Substantive irrelevance and unsupported assertions are
                    # already measured by the positive and factual owners.
                    continue
        if not observations:
            oid = identity + "/no-adopted-error"
            judge.observe(oid, "confirmed_missing", search_evidence(registry, judge, identity))
            observations = [oid]
        state = "triggered" if occurrences else "parse_failure" if registry["failures"] and not registry["documents"] else "not_triggered"
        judge.deduction(identity, state, observations, "只对明确采用的错误或实测超长产生损害实例，普通遗漏及解析失败不乘扣。", occurrences)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    artifact = args.artifact.resolve()
    contract_path = args.contract.resolve()
    judge = ProgramJudge(load_contract(contract_path), artifact, sha256(contract_path), artifact_root=artifact if artifact.is_dir() else artifact.parent)
    registry = extract_raw(artifact)
    positives = normalize(registry, judge)
    evaluate(registry, positives, judge)
    result = judge.finish()
    result["extraction_diagnostics"] = {"documents": len(registry["documents"]), "failures": [{"artifact": f["path"].name, "error": f["error"]} for f in registry["failures"]],
                                         "roles": {role: [d["path"].name for d in docs] for role, docs in registry["roles"].items()}}
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

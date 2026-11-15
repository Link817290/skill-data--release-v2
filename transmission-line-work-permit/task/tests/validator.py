#!/usr/bin/env python3
"""Offline field-level permit checker. No golden text or candidate code is executed."""

import argparse
import hashlib
import json
import math
import os
import posixpath
import re
import unicodedata
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"
CHECKED_MARKER = "[checked-checkbox]"
EXECUTION_HEADERS = {
    "工作间断时间", "工作开始时间", "工作许可人", "工作负责人", "方式",
    "工作变更", "工作任务", "工作班人员", "变更情况", "变更时间",
    "工作票的终结", "作业终结", "许可人措施终结", "汇报调度",
    "工作许可人/签发人", "许可人", "负责人",
}
ALIASES = {
    "total": ["总人数", "共计人数", "人数合计", "人员总数", "工作人员总数"],
    "crew": ["工作班人员", "工作班成员"],
    "supervisor": ["工作负责人", "负责人监护人"],
    "phone": ["联系电话", "电话号码", "电话"],
    "ticket_id": ["工作票编号", "系统票号", "票号", "编号"],
    "unit": ["单位和班组", "所属单位", "工作单位"],
    "time": ["计划工作时间", "计划起止时间", "计划时间"],
    "group": ["分组工作派工单", "分组派工单", "是否分组", "是否办理分组"],
    "task": ["工作任务", "作业内容", "工作内容"],
    "line": ["停电线路名称", "停电线路", "停电设备名称"],
    "site": ["工作地段", "作业地段", "工作地点"],
    "open": ["应拉断路器", "应断开", "停电措施", "应拉开的", "应拉开关"],
    "earth": ["应合接地", "厂站接地", "应合的接地", "应合上的线路侧接地", "接地刀闸措施"],
    "sign": ["应设遮栏", "应挂标示牌", "应挂标志牌", "挂牌措施", "应设标示牌"],
    "notes": ["其他安全措施", "其它安全措施", "现场安全措施和注意事项", "安全注意事项", "作业注意事项"],
    "portable": ["应装设的接地线", "应装设的工作接地线", "工作班应装设的接地线", "工作班应装设的工作接地线", "应装接地线", "工作班接地线", "接地线装设位置"],
    "signoff": ["签发", "接收", "工作许可", "安全交代", "工作间断", "工作变更", "工作延期", "工作票的终结"],
}


def norm(text):
    text = unicodedata.normalize("NFKC", text).lower()
    text = text.replace("×", "x").replace("某某", "xx")
    return re.sub(r"\s+", "", text)


def field_label(text):
    text = re.sub(r"^[一二三四五六七八九十]+\s+", "", unicodedata.normalize("NFKC", text))
    value = norm(text)
    # A floating copy-designation stamp can precede the actual label in OOXML order.
    value = value.replace("工作负责人所执联", "")
    # Numbering belongs to the carrier, not to the business field name.
    value = re.sub(r"^(?:\([一二三四五六七八九十\da-z]+\)|[a-z][.)、]|[一二三四五六七八九十]+[、.]|\d+(?:\.\d+)*[.、:]?)", "", value)
    return value.replace("(", "").replace(")", "")


def appendix_heading(text):
    value = field_label(text)
    return bool(re.match(r"^(?:附页|附录|附图|材料中未提供的信息|未知信息|待核实信息|签发前核实项|本次不预填的栏目)", value))


def plain(node):
    values = []
    for paragraph in node.iter(W + "p"):
        parts = []
        for run in paragraph.iter(W + "r"):
            props = run.find(W + "rPr")
            if props is not None and (props.find(W + "vanish") is not None or props.find(W + "webHidden") is not None):
                continue
            for node in run.iter():
                if node.tag == W + "t":
                    parts.append(node.text or "")
                elif node.tag in {W + "br", W + "cr"}:
                    parts.append("\n")
                elif node.tag == W + "tab":
                    parts.append("\t")
        checked = False
        for box in paragraph.iter():
            if box.tag not in {W + "checkBox", W14 + "checkbox"}:
                continue
            state = box.find(W + "checked") if box.tag == W + "checkBox" else box.find(W14 + "checked")
            if state is None and box.tag == W + "checkBox":
                state = box.find(W + "default")
            if state is not None:
                value = next((v for k, v in state.attrib.items() if k.endswith("}val")), "true")
                checked |= value.lower() in {"1", "true", "on"}
        values.append("".join(parts) + (CHECKED_MARKER if checked else ""))
    return "\n".join(values)


def parse_docx(path):
    if path.stat().st_size > 20_000_000:
        raise ValueError("Deliverable exceeds parser safety limit")
    with zipfile.ZipFile(path) as archive:
        if sum(z.file_size for z in archive.infolist()) > 80_000_000:
            raise ValueError("Expanded document exceeds parser safety limit")
        for part in ("_rels/.rels", "[Content_Types].xml"):
            if archive.namelist().count(part) != 1:
                raise ValueError("Missing or duplicate package metadata")
        relationships = ET.fromstring(archive.read("_rels/.rels"))
        rel_namespace = "{http://schemas.openxmlformats.org/package/2006/relationships}"
        if relationships.tag != rel_namespace + "Relationships":
            raise ValueError("Invalid package relationship namespace")
        allowed_types = {"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
                         "http://purl.oclc.org/ooxml/officeDocument/relationships/officeDocument"}
        main_links = [node for node in relationships if node.tag == rel_namespace + "Relationship" and node.get("Type") in allowed_types]
        if len(main_links) != 1 or not main_links[0].get("Id") or main_links[0].get("TargetMode") == "External":
            raise ValueError("Missing or ambiguous Word main-part relationship")
        target = posixpath.normpath(unquote(main_links[0].get("Target", "")).lstrip("/"))
        if target in {".", ".."} or target.startswith("../") or ":" in target:
            raise ValueError("Unsafe Word main-part target")
        content_types = ET.fromstring(archive.read("[Content_Types].xml"))
        ct_namespace = "{http://schemas.openxmlformats.org/package/2006/content-types}"
        if content_types.tag != ct_namespace + "Types":
            raise ValueError("Invalid package content-type namespace")
        matching_types = [node.get("ContentType") for node in content_types
                          if node.tag == ct_namespace + "Override" and unquote(node.get("PartName", "")).lstrip("/") == target]
        if not matching_types:
            extension = posixpath.splitext(target)[1].lstrip(".").lower()
            matching_types = [node.get("ContentType") for node in content_types
                              if node.tag == ct_namespace + "Default" and node.get("Extension", "").lower() == extension]
        if matching_types != ["application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"]:
            raise ValueError("Package is not a DOCX Word document")
        if archive.namelist().count(target) != 1:
            raise ValueError("Duplicate or missing Word main part")
        data = archive.read(target)
    root = ET.fromstring(data)
    strict = "{http://purl.oclc.org/ooxml/wordprocessingml/main}"
    if root.tag == strict + "document":
        for node in root.iter():
            if node.tag.startswith(strict):
                node.tag = W + node.tag[len(strict):]
            node.attrib.update({W + key[len(strict):]: value for key, value in list(node.attrib.items())
                                if key.startswith(strict)})
    if root.tag != W + "document":
        raise ValueError("Invalid Word document namespace")
    body = root.find(W + "body")
    if body is None:
        raise ValueError("Missing Word document body")
    fields = {key: [] for key in ALIASES}
    all_text = []
    current = None
    recognized = set()
    portable_columns = []
    portable_serial_column = None

    def classify(value):
        label = field_label(value)
        if label.startswith(("签发前", "签发之前", "工作许可后")):
            return None
        if re.match(r"^(?:工作票)?(?:签发人|会签人|工作许可人|许可人|接收人|值班负责人|工作负责人)(?:监护人)?(?:签名|签字)(?:[:：]|$)", label):
            return "signoff"
        if re.match(r"^(?:工作票)?(?:签发人|会签人|工作许可人|许可人|接收人|值班负责人)(?:[:：]|$)", label):
            return "signoff"
        if re.match(r"^(?:工作票编号|系统票号|票号|编号)(?:要求|规则|格式|示例|说明|只|应|须|需)", label):
            return None
        if any(re.match(r"^" + re.escape(norm(alias)) + r"(?:$|[:：、/]|签名|签字|时间|方式|记录|\|)", label)
               for alias in ALIASES["signoff"]):
            return "signoff"
        # Head-count labels contain the leader label but are not leader values.
        if re.match(r"^(?:工作负责人及工作班人员)?(?:总人数|共计人数|人数合计|人员总数)", label):
            return "total"
        if label.startswith(("工作负责人", "负责人监护人")):
            tail = re.sub(r"^(?:工作负责人|负责人监护人)(?:监护人)?", "", label)
            if tail and not tail.startswith((":", "：", "/", "|")):
                return None
        if re.match(r"^(?:工作班)?(?:应|自行)?装设的(?:现场)?(?:工作)?接地线", label):
            return "portable"
        if re.match(r"^应合(?:上|的|上的)?(?:线路侧)?接地", label):
            return "earth"
        return next((key for key, aliases in ALIASES.items()
                     if key != "signoff"
                     if any(label.startswith(norm(alias)) or
                            (key == "total" and "总人数" in label and
                             (len(label) < 40 or label.startswith("工作负责人")))
                            for alias in aliases)), None)

    def feed(value):
        nonlocal current
        if appendix_heading(value):
            current = None
            return
        key = classify(value)
        # Numbered safety prose may mention a field without opening that field.
        if (current == "notes" and key in {"site", "task", "supervisor", "crew", "line"}
                and re.match(r"^\s*\d+[.、]", value)
                and not re.match(r"^[^:：。;；]{1,24}[:：]", value)):
            key = None
        if key:
            current = key
            recognized.add(key)
        if current:
            fields[current].append(value)

    for block in body:
        if block.tag == W + "tbl":
            units = []
            for row in block.findall(W + "tr"):
                cells = [plain(c) for c in row.findall(W + "tc")]
                units.append(cells)
        elif block.tag == W + "p":
            units = [[plain(block)]]
        else:
            continue
        # Grounding registers mix planned identities with later execution columns.
        # Only filled execution cells, not their headers or installation plan, assert execution.
        register_columns = []
        if block.tag == W + "tbl" and units:
            headers = [norm(cell) for cell in units[0]]
            if any("安装点" in h or "装设位置" in h for h in headers) and any("接地线" in h for h in headers):
                register_columns = [i for i, h in enumerate(headers)
                                    if re.search(r"(?:装设|拆除).*?(?:时间|执行人)|核实|汇报人", h)]
        if register_columns:
            for row_index, cells in enumerate(units):
                all_text.append(" | ".join(cells))
                if row_index:
                    for index in register_columns:
                        value = norm(cells[index]) if index < len(cells) else ""
                        if value and not re.fullmatch(r"[_年月日时分:：/().\-]*|待填|留空|未填写", value):
                            fields["signoff"].append(CHECKED_MARKER + " " + cells[index])
            current = None
            continue
        for cells in units:
            text = " | ".join(cells)
            all_text.append(text)
            if re.fullmatch(r"对应工作票编号[:：][_\s]*工作负责人[:：][\u4e00-\u9fff×xX]{2,4}", text.strip()):
                # The register's responsible person is an identity, not a signature.
                continue
            if appendix_heading(cells[0]):
                current = None
            key = classify(cells[0])
            if (len(cells) > 2 and any(norm(c) == "接地线编号" for c in cells)
                    and any("杆号" in norm(c) or "装设位置" in norm(c) for c in cells)):
                key = current = "portable"
                recognized.add("portable")
            if key and key != "portable":
                portable_serial_column = None
                if portable_columns:
                    fields["portable"].extend(norm(location) + "，编号" for location in portable_columns)
                    portable_columns = []
            scalar = {"total", "crew", "supervisor", "phone", "ticket_id", "unit", "time", "group", "task", "line", "site"}
            # Native head tables alternate labels and values. Do not let a later
            # unknown column (e.g. survey metadata) contaminate a crew/name field.
            if block.tag == W + "tbl" and key == "crew" and len(cells) >= 4 and len(cells) % 2 == 0:
                for index in range(0, len(cells), 2):
                    pair_key = classify(cells[index])
                    if pair_key in scalar:
                        recognized.add(pair_key)
                        fields[pair_key].extend(cells[index:index + 2])
                current = None
                continue
            if key == "signoff" or (current == "signoff" and key in {None, "supervisor"}):
                recognized.add("signoff")
                current = "signoff"
                fields[current].append(" | ".join(
                    norm(cell) if norm(cell) in EXECUTION_HEADERS else cell for cell in cells))
                continue
            # Native permits may put location and grounding serials in parallel rows.
            if (key == "portable" or current == "portable") and len(cells) > 2:
                header = next((i for i, cell in enumerate(cells)
                               if "接地线" in norm(cell) and "编号" in norm(cell)
                               and not re.search(r"\d|未提供|待核实", norm(cell))), None)
                if header is not None and any("杆号" in norm(c) or "位置" in norm(c) for c in cells):
                    portable_serial_column = header
                    continue
                elif portable_serial_column is not None and portable_serial_column < len(cells):
                    location = "，".join(norm(cell) for i, cell in enumerate(cells) if i != portable_serial_column)
                    if re.search(r"\d+(?:号)?(?:杆|塔)", location):
                        fields["portable"].append(f"{location}，编号{norm(cells[portable_serial_column])}")
                        continue
                label_index = next((i for i, cell in enumerate(cells[:2])
                                    if norm(cell).startswith(("线路名称", "接地线编号"))), None)
                if label_index is not None and "线路名称" in norm(cells[label_index]):
                    if portable_columns:
                        fields["portable"].extend(norm(location) + "，编号" for location in portable_columns)
                    portable_columns = cells[label_index + 1:]
                    current = "portable"
                    recognized.add("portable")
                    continue
                elif label_index is not None and portable_columns:
                    values = cells[label_index + 1:]
                    fields["portable"].extend(
                        f"{norm(location)}，编号{norm(values[i]) if i < len(values) else ''}"
                        for i, location in enumerate(portable_columns))
                    portable_columns = []
                    continue
            for cell in cells:
                if norm(cell).startswith("以下并非本方主张:"):
                    continue
                if classify(cell) and "\n" in cell and len(norm(cell)) < 40:
                    feed(cell)
                else:
                    for value in cell.splitlines():
                        feed(value)
            # A ticket identifier or head count must not absorb an unrelated later row.
            if current in {"ticket_id", "phone", "total"}:
                value = norm("\n".join(fields[current]))
                labels = "|".join(map(re.escape, map(norm, ALIASES[current])))
                remainder = re.sub(r"^.*?(?:" + labels + r")[:：]?", "", value, count=1)
                if remainder.strip("|_:：/()"):
                    current = None
    if portable_columns:
        fields["portable"].extend(norm(location) + "，编号" for location in portable_columns)
    return {key: "\n".join(value) for key, value in fields.items()}, "\n".join(all_text), recognized


def number(text, value):
    return bool(re.search(r"(?<!\d)0*" + re.escape(str(value)) + r"(?!\d)", norm(text)))


COUNT_CHARS = "0-9零〇一二两三四五六七八九十百千壹贰叁肆伍陆柒捌玖拾佰仟"


def integer_value(value):
    value = norm(value).translate(str.maketrans("〇两壹贰叁肆伍陆柒捌玖拾佰仟", "零二一二三四五六七八九十百千"))
    if len(value) > 32:
        return None
    if re.fullmatch(r"[0-9]+", value):
        return int(value)
    if not value or re.search(r"[^零一二三四五六七八九十百千]", value):
        return None
    total, digit, last_unit = 0, None, 10000
    for char in value:
        if char in "零一二三四五六七八九":
            if digit not in {None, 0}:
                return None
            digit = "零一二三四五六七八九".index(char)
        else:
            unit = {"十": 10, "百": 100, "千": 1000}[char]
            if unit >= last_unit:
                return None
            total += (1 if digit is None else digit) * unit
            digit, last_unit = None, unit
    return total + (digit or 0)


def total_count(text, expected):
    value = norm(text).replace("工作负责人所执联", "")
    value = re.sub(r"^.*?(?:总人数|共计人数|人数合计|人员总数)[:：]?", "", value, count=1)
    value = re.sub(r"^工作负责人及工作班人员", "", value)
    value = re.sub(r"^(?:共计|合计|共|为|是|计|[:：])+", "", value)
    # A repeated printed count label may precede a filled count on the next line.
    value = re.sub(rf"^([{COUNT_CHARS}]+)人[:：](?=[{COUNT_CHARS}])", "", value)
    match = re.fullmatch(rf"\(?([{COUNT_CHARS}]+)\)?人?(?:\(([^()]*)\))?", value)
    if not match or integer_value(match[1]) != expected:
        return False
    explanation = match[2]
    if explanation is None:
        return True
    if explanation.startswith("按"):
        counts = reported_totals(explanation)
        return bool(counts) and all(count == expected for count in counts)
    explanation = re.sub(r"[,、](?:含|包括)(?:工作)?负责人$", "", explanation)
    breakdown = re.fullmatch(rf"(?:含|包括)?(?:工作)?负责人(?:[\u4e00-\u9fff]xx)?([{COUNT_CHARS}]+)?人?(?:[、,+](?:工作班人员|工作班成员|班员|成员)([{COUNT_CHARS}]+)人)?", explanation)
    if not breakdown:
        return False
    leader = integer_value(breakdown[1]) if breakdown[1] else 1
    crew = integer_value(breakdown[2]) if breakdown[2] else None
    return leader == 1 and (not breakdown[2] or (crew is not None and leader + crew == expected))


def reported_totals(text):
    text = re.sub(r"[^\S\n]+", "", unicodedata.normalize("NFKC", text)).lower().replace("**", "").replace("`", "")
    token = rf"[{COUNT_CHARS}][{COUNT_CHARS}+./%=\-]*"
    patterns = [rf"(?:总人数|共计人数|人数合计)(?:为|是|[:=])?({token})",
                rf"(?:共计|合计|共)(?:为|是|[:=])?({token})人"]
    values = []
    for index, pattern in enumerate(patterns):
        for match in re.finditer(pattern, text):
            if index == 1:
                prefix = re.split(r"[。;；\n|]", text[:match.start()])[-1]
                # A crew subtotal excludes the leader. An explicit equation may include it.
                subtotal = re.search(r"(?:班员|成员|工作班(?:人员|成员)?|(?:崔|许|张|李|赵)[^。;；|]*)[^\d零一二三四五六七八九十]*$", prefix)
                equality = re.match(rf"=([{COUNT_CHARS}]+)人", text[match.end():])
                if subtotal and equality:
                    leader = re.search(rf"负责人(?:[\u4e00-\u9fff]××)?([{COUNT_CHARS}]+)人", prefix)
                    leader_count = integer_value(leader[1]) if leader else None
                    total = integer_value(equality[1])
                    crew = integer_value(match[1])
                    values.append(total if leader_count is not None and crew is not None and leader_count + crew == total else None)
                    continue
                if subtotal:
                    continue
            parts = match[1].split("=")
            terms = [integer_value(term) for term in parts[0].split("+")]
            if None in terms or len(parts) > 2:
                values.append(None)
                continue
            total = sum(terms)
            values.append(total if len(parts) == 1 or integer_value(parts[1]) == total else None)
    # Explicit leader-plus-crew arithmetic is an independently checkable total,
    # including prose whose total label is separated from its value by markup.
    roles = rf"(?:工作)?负责人(?:[\u4e00-\u9fff][×x]{{2}})?([{COUNT_CHARS}]+)人\+(?:工作班人员|工作班成员|工作班|班员|成员)([{COUNT_CHARS}]+)人(?:=([{COUNT_CHARS}]+)人)?"
    for match in re.finditer(roles, text):
        leader, crew = integer_value(match[1]), integer_value(match[2])
        total = None if leader is None or crew is None else leader + crew
        values.append(total if match[3] is None or integer_value(match[3]) == total else None)
    return values


def unknown_field(value, labels):
    value = norm(value)
    value = re.sub(r"^\(?(?:" + "|".join(map(re.escape, map(norm, labels))) + r")[:：]?", "", value)
    value = value.strip(" ()_:：/-.|")
    return not value or bool(re.search(r"未提供|未给|未知|待核实|待确认|待.*生成|由.*系统.*生成", value))


def unsupported_identifier(value, kind):
    labels = ALIASES[kind]
    value = norm(value)
    if kind == "phone":
        payload = re.sub(r"^\(?(?:联系电话|电话号码|电话)[:：]?", "", value).rstrip(")")
        # A redacted phone is not a concrete number; still reject any complete number.
        if (re.fullmatch(r"[0-9x.*·…_-]+", payload)
                and re.search(r"[x*·…]|\.{2,}", payload)
                and not re.search(r"\d[\d-]{6,}", payload)):
            return False
    if not unknown_field(value, labels):
        return True
    if kind == "phone":
        return bool(re.search(r"\d[\d-]{6,}", value))
    # S1 and XXX format examples are not actual system-issued identifiers.
    concrete = r"(?<![a-z0-9])s?\d{4}-\d{1,2}-s\d+-\d{3,}(?![a-z0-9])"
    return bool(re.search(concrete, value) or re.search(r"(?:实际票号|已生成票号|票号为)[:：]?[a-z0-9-]*\d", value))


def citation_decisions(report, index):
    decisions = []
    clause_pattern = r"(?<![\d.])[1-9]\d?(?:\.\d{1,2}){2,4}(?![\d.])"
    sources = index["sources"]
    for line_number, line in enumerate(report.splitlines(), 1):
        value = norm(line)
        if re.match(r"^#{1,6}\d+(?:\.\d+)+", value):
            continue
        # Names and clauses in a mixed-source sentence retain their relative positions.
        mentions = sorted((m.start(), m.end(), source_id)
                          for source_id, source in sources.items()
                          for alias in source["aliases"]
                          for m in re.finditer(re.escape(norm(alias)), value))
        mentions = [entry for entry in mentions if not any(
            other[0] <= entry[0] and other[1] >= entry[1] and other[1] - other[0] > entry[1] - entry[0]
            for other in mentions)]
        for match in re.finditer(clause_pattern, value):
            previous = [entry for entry in mentions if entry[1] <= match.start()]
            preceding = previous[-1] if previous else None
            between = value[preceding[1]:match.start()] if preceding else ""
            source_id = (preceding[2] if preceding and len(between) < 48
                         and not re.search(r"[。;；|]", between) else None)
            candidates = [source_id] if source_id else list(sources)
            present = [sid for sid in candidates if match[0] in sources[sid]["clauses"]]
            elsewhere = [sid for sid in sources if match[0] in sources[sid]["clauses"]]
            # Unscoped numbers require review unless absent from every supplied source.
            decisions.append({"clause": match[0], "line": line_number, "source_id": source_id,
                              "status": "present" if present else ("scope_review" if elsewhere else "nonexistent"),
                              "matched_sources": present, "evidence": line})
    return decisions


def load_citation_index():
    index = json.loads((HERE / "citation_index.json").read_text(encoding="utf-8"))
    for source in index["sources"].values():
        path = HERE / "materials" / source["file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(f"Citation source hash drift: {source['file']}")
    return index


def must_have_evaluation(core_checks):
    failed = [key for key, value in core_checks.items() if not value["passed"]]
    return {"policy": "bench-golden-business-must-have-v3", "passed": not failed,
            "failed_ids": failed, "items": core_checks}


def station_sections(text, stations):
    aliases = {}
    for station in stations:
        name = re.sub(r"^\d+kV", "", station["name"], flags=re.I)
        short = re.sub(r"(?:变电站|降压站)$", "", name)
        aliases[station["name"]] = rf"(?:\d+kv)?{re.escape(short)}(?:变电站|降压站|站)"
    pattern = "|".join(f"(?P<s{i}>{alias})" for i, alias in enumerate(aliases.values()))
    names = list(aliases)
    value = norm(text)
    matches = list(re.finditer(pattern, value))
    sections = {name: [] for name in names}
    for index, match in enumerate(matches):
        name = names[int(match.lastgroup[1:])]
        end = matches[index + 1].start() if index + 1 < len(matches) else len(value)
        if index + 1 == len(matches):
            # A trailing lettered general note is outside the last station's
            # device scope. Do not let words such as “控制/合闸能源” in that
            # common note become an opposite-action claim for the station PT.
            tail = value[match.end():end]
            common = re.search(r"[。;；](?:[a-z]|\d+)[)）.、]", tail, re.I)
            if common:
                end = match.end() + common.start()
        sections[name].append(value[match.start():end])
    return {name: "\n".join(parts) for name, parts in sections.items()}


def names(text):
    return set(re.findall(r"[\u4e00-\u9fff]xx", norm(text)))


def dates(text):
    value = unicodedata.normalize("NFKC", text)
    parts = re.findall(r"(\d{4})\s*(?:年|[-/.])\s*(\d+)\s*(?:月|[-/.])\s*(\d+)\s*(?:日|[T\s])\s*(\d+)\s*(?:时|:)\s*(\d+)\s*分?", value)
    return ["%04d-%02d-%02d %02d:%02d" % tuple(map(int, part)) for part in parts]


NEGATIVE = r"(?:不需要|不允许|不应|不得|不要|无需|无须|不用|禁止|严禁|不)"
OPEN_ACTION = r"(?:拉开|断开|分闸|切断)"
CLOSE_ACTION = r"(?:合上|合闸|闭合|接通)"
PT_SWITCH = r"(?:电压互感器|pt)[^。;；\n]*?(?:二次|低压)(?:侧|回路)?(?:全部|所有)?(?:空气开关|空开)"


def signage_sections(text, stations):
    sections = station_sections(text, stations)
    value = norm(text)
    starts = [value.find(norm(re.sub(r"^\d+kV", "", s["name"], flags=re.I)))
              for s in stations]
    starts = [index for index in starts if index >= 0]
    prefix = value[:min(starts)] if starts else ""
    common = next((clause for clause in re.split(r"[。;；]", prefix)
                   if re.search(r"下列|以下", clause) and re.search(r"悬挂|挂设", clause)
                   and "禁止合闸" in clause and "线路有人工作" in clause), "")
    if common:
        endings = list(re.finditer(r"标示牌|标志牌", common))
        if endings:
            common = common[:endings[-1].end()]
        # Inherit only the scoped instruction, not unrelated equipment identifiers.
        for name in sections:
            sections[name] += "\n" + common
    for clause in re.split(r"[。;；\n]", text):
        clause = norm(clause)
        isolators = [s["line_isolator"] for s in stations]
        if ("各站" in clause and "分别" in clause and re.search(PT_SWITCH, clause)
                and all(number(clause, code) for code in isolators)):
            for station in stations:
                scoped = clause
                for code in isolators:
                    if code != station["line_isolator"]:
                        scoped = re.sub(r"(?<!\d)" + re.escape(str(code)) + r"(?!\d)", "", scoped)
                sections[station["name"]] += "\n" + scoped
    return sections


def action_conflict(section, expected, reverse):
    # A prohibition on the reverse action is safe, but a prohibition on the required action is not.
    value = re.sub(NEGATIVE + reverse, "[prohibited-reverse]", norm(section))
    return bool(re.search(NEGATIVE + expected, value) or re.search(reverse, value))


def opposite_action(section, device, expected, reverse):
    for clause in re.split(r"[。;；\n]", section):
        if not number(clause, device):
            continue
        if action_conflict(clause, expected, reverse):
            return True
    return False


def filled_execution(text):
    # Join only known printed labels; do not rewrite source blocks or signer text.
    headings = EXECUTION_HEADERS | {"工作许可", "工作延期", "签发", "接收", "安全交代", "工作间断",
                                    "工作票的终结", "工作开始时间", "工作间断时间"}
    for heading in sorted(headings, key=lambda label: (-len(label), label)):
        if len(heading) > 1:
            pattern = r"[\s\u3000]*".join(map(re.escape, heading))
            text = re.sub(pattern, lambda match, label=heading: label, text)
    if CHECKED_MARKER in text or re.search(r"[☑☒✓✔√]|\[[xX]\]", text):
        return True
    if names(text) or re.search(r"\d{4}\s*(?:年|[-/])\s*\d{1,2}\s*(?:月|[-/])\s*\d{1,2}", text):
        return True
    blank = {"时间", "方式", "签发", "接收", "备注", "安全交代", "工作许可", "工作间断",
             "工作变更", "工作延期", "工作负责人", "工作许可人", "未填写", "待签发", "不预填"}
    blank.update({"汇报调度", "作业终结", "变更情况", "变更时间", "工作任务", "单位签章"})
    blank.update({"未签发", "未许可", "待许可", "未开工", "待开工", "未执行", "未终结", "未接收", "待接收"})
    blank.update(EXECUTION_HEADERS)
    for match in re.finditer(r"(?:签名|签字|签发人|会签人|接收人|许可人)[^\S\r\n]*[:：][^\S\r\n]*([^|;；\r\n]*)", text):
        value = re.split(r"时间|签名|许可方式", match[1], maxsplit=1)[0].strip()
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}|[A-Za-z]+(?: [A-Za-z]+)*", value) and value not in blank:
            return True
    for line in text.splitlines():
        value = line.split("|")[-1].strip()
        # Unselected printed confirmation text is not evidence that the stage was executed.
        if "□" not in value and "[ ]" not in value:
            completion = (r"(?:已|已经)(?:取得|获得|得到)(?:工作)?许可|"
                          r"(?:工作)?许可(?:已|已经)(?:取得|获得|得到)|"
                          r"(?:工作|作业)(?:已|已经)(?:开始|完成|结束)|"
                          r"(?:已|已经)(?:开工|开始工作|开始作业|完成签发|办理终结)|"
                          r"(?:安全措施|安全交代)(?:已|已经)(?:落实|完成)")
            if re.search(r"(?:^|[:：;；])\s*(?:" + completion + r")", value):
                return True
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}|[A-Za-z]+(?: [A-Za-z]+)*", value) and value not in blank:
            return True
    return False


def unsupported_completion_claims(text):
    patterns = (
        r"(?:二次侧?|二次)空气开关(?:均)?已(?:经)?断开",
        r"双方已在[^。;；]*交底单[^。;；]*签名确认",
        r"外单位工作任务许可单[:：]已[^。;；]*办理",
        r"施工方案[:：][^。;；]*已[^。;；]*(?:报运行单位审批|审批完成|获批准)",
    )
    claims = []
    for raw_clause in re.split(r"[。;；\n]", text):
        clause = norm(raw_clause)
        for pattern in patterns:
            match = re.search(pattern, clause)
            if match and not re.search(r"不得|不代表|待核实|未提供|应确认|须确认|若|如果", clause[:match.start()]):
                claims.append(clause)
                break
    return claims


def topology_contradictions(text, facts):
    config = json.loads((HERE / "topology_checks.json").read_text())
    source = HERE / "materials" / config["source_file"]
    if hashlib.sha256(source.read_bytes()).hexdigest() != config["sha256"]:
        raise ValueError("Topology source hash drift")
    errors = []
    branch_poles = {int(station["pole"]) for station in facts["stations"]}
    for raw in re.split(r"[。;；\n]", text):
        clause = norm(raw).replace("**", "").replace("`", "")
        for code, device_type in config["device_types"].items():
            if device_type != "PT":
                continue
            match = re.search(r"(?<!\d)" + re.escape(code) + r"(?:线路)?(?:电压互感器|pt)?(?:一次侧)?隔离开关", clause)
            if match and not re.search(r"不是|并非|不得|不应|误称|错误", clause[max(0, match.start() - 20):match.start()]):
                errors.append({"kind": "device_type", "device": code, "expected": "PT", "evidence": raw})
        poles = [int(m[1]) for m in re.finditer(r"(?:#|第)?(\d+)(?:号)?杆", clause)]
        named = set(poles) & branch_poles
        # Several branch directions in one sentence are ambiguous; do not infer
        # ownership. A side at #35/#37/#48 is not a side at the #36 work pole.
        if not poles or poles[0] != facts["work_pole"] or len(named) != 1 or "大小号侧" in clause or ("大号侧" in clause and "小号侧" in clause):
            continue
        branch = next(iter(named))
        wrong = "大号侧" if branch < facts["work_pole"] else "小号侧"
        if wrong in clause and not re.search(r"不是|并非|不得|不应|误写|错误", clause[:clause.index(wrong)]):
            errors.append({"kind": "pole_direction", "branch_pole": branch,
                           "expected": "小号侧" if branch < facts["work_pole"] else "大号侧", "evidence": raw})
    return errors


def safety_controls(notes, wind_limit):
    climbing = ("核对" in notes and "杆" in notes and "检查" in notes
                and not re.search(NEGATIVE + r"(?:核对|检查)", notes))
    weather = "".join(clause for clause in re.split(r"[。;；\n]", notes) if "雷" in clause or "风" in clause)
    levels = re.findall(rf"风力(?:大于|超过|高于)([{COUNT_CHARS}.]+)级|([{COUNT_CHARS}.]+)级(?:及以上|以上)(?:大风|风)", weather)
    limits = [integer_value(a or b) for a, b in levels]
    weather_safe = ("雷" in weather and "雨" in weather and bool(limits)
                    and all(value is not None and 0 < value <= wind_limit for value in limits)
                    and bool(re.search(r"暂停|停止|停工|不得作业|禁止作业", weather))
                    and not re.search(NEGATIVE + r"(?:暂停|停止|停工)", weather))
    fixing = any("接地线" in paragraph and re.search(r"(?:固定|连接可靠).*?(?:摆动|防摆)|摆动.*?固定", paragraph)
                 and not re.search(NEGATIVE + r"固定", paragraph) for paragraph in notes.splitlines())
    belt = (bool(re.search(r"(?:使用|佩戴|系好|系牢|系紧)[^。;；]{0,30}安全带|(?:不得|禁止|不应)失去安全带(?:的)?保护", notes))
            and not re.search(NEGATIVE + r"(?:使用|佩戴|系好|系牢|系紧)安全带", notes))
    below = bool(re.search(r"(?:不得|禁止|不应|严禁)(?:地面(?:配合)?人员)?(?:站在|站立于|站立在|站|停留在)[^。;；]*?(?:正)?下方|"
                          r"(?:正)?下方[^。;；]*?(?:不得|禁止|不应|严禁)(?:站人|站立|停留|人员(?:通行|停留|逗留)|人员.*逗留)", notes))
    below |= bool(re.search(r"高处坠物[^。;；\n]{0,20}范围[^。;；\n]{0,12}禁止人员停留", notes))
    below |= bool(re.search(r"(?:杆|塔)下(?:及[^。;；\n]{0,30})?禁止人员(?:通行|停留|逗留)", notes))
    below = below and not re.search(r"(?:可以|允许)(?:站在|站立于|站立在)[^。;；]*?下方", notes)
    below = below and not re.search(r"(?:可以|允许)(?:人员)?(?:在|站在|站立于)[^。;；\n]*?(?:杆|塔)下", notes)
    return climbing, weather_safe, fixing, belt and below


def unsafe_safety_claim(notes):
    # Missing detail loses its atom; an explicit instruction to bypass protection is a safety veto.
    for clause in re.split(r"[。;；\n]", notes):
        if "登杆" in clause and re.search(NEGATIVE + r"(?:核对|检查)", clause):
            return True
        if ("雷雨" in clause or "风力" in clause) and re.search(NEGATIVE + r"(?:暂停|停止|停工)", clause):
            return True
        if "接地线" in clause and re.search(NEGATIVE + r"固定", clause):
            return True
        if re.search(NEGATIVE + r"(?:使用|佩戴|系好|系牢|系紧)安全带", clause):
            return True
        if re.search(r"(?:可以|允许)(?:地面(?:配合)?人员)?(?:站在|站立于|站立在)[^。;；]*?下方", clause):
            return True
    return False


def grounding_records(portable, plan):
    rows = [norm(row).rstrip("。.;；，,") for row in portable.splitlines()
            if re.search(r"\d+(?:号)?(?:杆|塔)", norm(row))]
    # Topology sketches summarize the detailed installation rows and are not
    # additional physical grounding records.
    rows = [row for row in rows if not row.startswith("现场接地布置:")]
    return rows


def approved_grounding_checks(portable, line, plan):
    return grounding_credit_checks(portable, line, plan)[3:]


def grounding_credit_checks(portable, line, plan):
    rows = grounding_records(portable, plan)
    work_pole = str(plan.get("work_pole", 36))
    checks = []
    for item in plan["grounding_sets"]:
        pole = str(item["pole"])
        aliases = [norm(alias) for alias in item.get("direction_aliases", [])]
        covered = any(
            line in row and (
                bool(re.search(rf"(?:#|第)?0*{pole}(?:号)?(?:杆|塔)", row))
                or (bool(re.search(rf"(?:#|第)?0*{work_pole}(?:号)?(?:杆|塔)", row))
                    and (bool(re.search(rf"(?:#|第)?0*{pole}(?:号)?(?:杆|塔)", row))
                         or any(alias in row for alias in aliases)))
            )
            for row in rows
        )
        checks.append((f"#{pole}方向保护", covered))
    direction_complete = all(value for _, value in checks) and len(rows) >= len(plan["grounding_sets"])
    identifiers = [value for value in re.findall(
        r"(?:编号|号码|接地线号)[:：]?([a-z0-9-]+)", norm(portable))
        if value.strip("-_")]
    identifiers_complete = bool(identifiers) and len(identifiers) == len(set(identifiers))
    controlled_blank = (bool(re.search(r"签发前.{0,80}(?:补填|填写).{0,80}(?:编号|标签)", portable))
                        and bool(re.search(r"(?:编号|标签).{0,40}唯一", portable))
                        and bool(re.search(r"(?:未完成|未补齐).{0,30}(?:不得签发|不得许可|不得开工)", portable)))
    checks.append(("三方向工作地段保护", direction_complete))
    checks.append(("接地线标识可追溯", identifiers_complete or controlled_blank))
    return checks


def approved_procedure_checks(notes, facts):
    text = norm(notes)
    contact = (bool(re.search(r"(?:末级许可人|工作许可人|许可人).{0,50}(?:联系|许可|告知)|"
                              r"(?:联系|取得许可).{0,50}(?:末级许可人|工作许可人|许可人)", text)) and
               bool(re.search(r"(?:告知|交代|说明|确认).{0,20}(?:工作内容|作业内容|工作范围)", text)) and
               not re.search(NEGATIVE + r"(?:告知|交代|说明|联系)", text))
    closeout = (bool(re.search(r"(?:工作|作业)结束.*?(?:检查|清查).*?(?:塔|杆).*?遗留物", text)) and
                bool(re.search(r"拆除.*?接地线.*?(?:人员.*?撤离|全部撤离).*?(?:汇报|报告).*?终结", text)) and
                not re.search(NEGATIVE + r"(?:检查|清查|拆除|撤离|汇报|报告|办理)", text))
    ends = bool(re.search(r"工作地段(?:的)?(?:两端|各端).*?装设接地线", text))
    climbing = (bool(re.search(r"登(?:杆塔|杆|塔)前.*?核对.*?(?:线路名称|" + re.escape(norm(facts["line"])) +
                              rf").*?(?:杆塔?号|#?{facts['work_pole']}杆)", text)) and
                bool(re.search(r"(?:检查|查验).{0,80}(?:杆根|基础|根部)", text)) and
                bool(re.search(r"(?:拉线|拉索)", text)) and
                bool(re.search(r"(?:脚钉|爬梯|登高构件)", text)))
    weather = safety_controls(text, facts["wind_limit"])[1]
    fixation = bool(re.search(r"接地线.*?(?:装设|安装).*?后.*?杆塔上.*?固定.*?摆动", text))
    return contact, closeout and ends, climbing, weather, fixation


def device_inventory_matches(text, expected):
    value = re.sub(r"\d+kv", "", norm(text))
    # An explicit PT label is an annotation of the same PT, not an extra isolator.
    value = re.sub(r"1949(?=(?:线路)?电压互感器)", "", value)
    value = re.sub(r"(电压互感器|pt)1949", r"\1", value)
    # General all-station notes may repeat another bay's identifiers after a
    # station paragraph. They do not invalidate the required devices actually
    # listed for this station; contradictions remain checked separately.
    return set(expected) <= set(re.findall(r"(?<!\d)\d{3,5}(?!\d)", value))


def check(root):
    from quality_scoring import aggregate, apply_guards, safety_coverage_gate, settle
    params = json.loads(Path(os.environ.get("SCORING_PARAMS", HERE / "scoring_params.json")).read_text(encoding="utf-8"))
    facts = json.loads((HERE / "ground_truth.json").read_text())["facts"]
    plan = json.loads((HERE / "approved_plan.json").read_text())
    output = root if root.name == "output" or (root / "工作票.docx").is_file() else root / "output"
    ticket = output / "工作票.docx"
    # Repository host gates pass an artifact directory, not a workspace. Resolve
    # its sole Word file without relying on a reference filename or content hash.
    if not ticket.is_file() and root.is_dir():
        artifact_dir = output if output.is_dir() else root
        candidates = list(artifact_dir.glob("*.docx"))
        if len(candidates) == 1:
            ticket = candidates[0]
    atoms, damage, limitations = {}, [], []

    def record(item, checks):
        if len(checks) != params["raw_assertion_counts"][item]:
            raise ValueError(f"Assertion inventory drift: {item}")
        atoms[item] = [dict(assertion=label, passed=bool(value)) for label, value in checks]

    try:
        fields, text, recognized = parse_docx(ticket)
        parsed = True
    except (OSError, ValueError, KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
        fields, text, recognized = {key: "" for key in ALIASES}, "", set()
        parsed = False
        limitations.append(str(exc))
    f = {key: norm(value) for key, value in fields.items()}
    ntext = norm(text)
    expected_names = {norm(name) for name in facts["crew"]}
    ticket_type = norm(facts["permit_type"]) in ntext
    record("P01", [("线路第一种票种", ticket_type), ("设备运维供电局", norm(facts["bureau"]) in ntext)])
    identity = [names(fields["supervisor"]) == {norm(facts["supervisor"])},
                names(fields["crew"]) == expected_names, total_count(fields["total"], facts["total"])]
    record("P02", list(zip(["负责人", "班员集合", "含负责人总人数"], identity)) + [
        ("单位和班组", "线路一班" in f["unit"] and "公司" in f["unit"]),
        ("起止时间", dates(fields["time"]) == [facts["start"], facts["end"]]),
        ("不分组", "否" in f["group"] or "不分组" in f["group"])])
    line = norm(facts["line"])
    pole = rf"(?:#|第)?0*{facts['work_pole']}(?:号)?(?:杆|塔)"
    task_checks = [line in f["task"] and bool(re.search(pole, f["task"])) and bool(re.search(r"(?:解除|拆除|断开)引(?:流)?线", f["task"])),
                   line in f["line"], line in f["site"] and bool(re.search(pole, f["site"]))]
    record("P03", list(zip(["任务对象与作业", "停电线路", "作业杆塔"], task_checks)))
    opens = station_sections(fields["open"], facts["stations"])
    earths = station_sections(fields["earth"], facts["stations"])
    signs = signage_sections(fields["sign"], facts["stations"])
    shared_signs = "\n".join(clause for clause in fields["sign"].splitlines()
                             if re.search(r"上述三站|三站.*(?:各|均)", clause)
                             and re.search(PT_SWITCH, norm(clause)))
    isolation, station_earth, signage = [], [], []
    for station in facts["stations"]:
        name = station["name"]
        section = opens[name]
        inventory_ok = device_inventory_matches(section, [station["breaker"], *station["disconnectors"]])
        for code in [station["breaker"], *station["disconnectors"]]:
            reverse = opposite_action(section, code, OPEN_ACTION, CLOSE_ACTION)
            isolation.append((f"{name}/{code}断开", inventory_ok and number(section, code) and not reverse))
        pt = bool(re.search(PT_SWITCH, section))
        pt = pt and not any(re.search(r"pt|电压互感器", clause) and
                                action_conflict(clause, OPEN_ACTION, CLOSE_ACTION)
                                for clause in re.split(r"[。;；\n]", section))
        isolation.append((f"{name}/PT二次断开", pt))
        ground_text = earths[name]
        reverse = opposite_action(ground_text, station["earth_switch"], r"(?:合上|合闸|合)", OPEN_ACTION)
        station_earth.append((f"{name}/线路侧接地", device_inventory_matches(ground_text, [station["earth_switch"]])
                              and number(ground_text, station["earth_switch"]) and not reverse))
        sign_text = signs[name] + "\n" + norm(shared_signs)
        hanging = not bool(re.search(NEGATIVE + r"(?:悬挂|挂设|挂|设置)", sign_text))
        message = re.sub(r"[，,;；:：!！\s\"'“”]", "", sign_text)
        signage.extend([
            (f"{name}/隔离开关操作处", hanging and number(sign_text, station["line_isolator"])
             and device_inventory_matches(sign_text, [station["line_isolator"]])),
            (f"{name}/PT操作处", hanging and bool(re.search(PT_SWITCH, sign_text))),
            (f"{name}/线路标示牌", hanging and "禁止合闸线路有人工作" in message)])
    record("P04", isolation)
    record("P05", station_earth)
    record("P06", signage)
    notes = f["notes"]
    ordered = bool(re.search(r"(?:验明|验电).*?(?:无电压|确无电|无电).*?(?:接地|地线).*?(?:开工|开始工作|开始作业|解除引流线)", notes))
    ordered = ordered and not bool(re.search(NEGATIVE + r"(?:验明|验电|装设接地线|接地)", notes))
    permission = bool(re.search(r"(?:取得|得到|获得|许可后|工作许可).*?(?:许可|验电)", notes))
    permission |= bool(re.search(r"(?:接到|收到)[^。;；]*许可(?:工作)?命令[^。;；]*后[^。;；]*(?:验电|接地|开工|作业)", notes))
    permission |= bool(re.search(r"未接到[^。;；]*许可[^。;；]*前[，,]?(?:不得|禁止)(?:开始工作|开工)", notes))
    permission = permission and not bool(re.search(NEGATIVE + r"(?:取得|得到|获得)?(?:工作)?许可", notes))
    # A prohibition before permission is safe; a negated receipt is not receipt.
    receipt_claims = re.sub(
        r"未接到[^。;；]*许可[^。;；]*前[，,]?(?:不得|禁止)(?:开始工作|开工)", "", notes)
    permission = permission and not bool(re.search(
        r"(?:未|没有|无需|不必|不需要)(?:取得|得到|获得|接到|收到)[^。;；]*许可", receipt_claims))
    safety_notes = "\n".join(norm(re.sub(r"^\s*\d+[.、]\s+", "", paragraph))
                              for paragraph in fields["notes"].splitlines())
    climbing, weather, fixing, protection = safety_controls(safety_notes, facts["wind_limit"])
    approved_contact, approved_sequence, approved_climbing, approved_weather, approved_fixing = approved_procedure_checks(fields["notes"], facts)
    classified_weather_notes = re.sub(r"风速超过10\.7m/s\(6级及以上\)",
                                      "6级及以上大风", safety_notes)
    weather_control = safety_controls(classified_weather_notes, facts["wind_limit"])[1]
    # Preserve the measured control evidence before exact-plan constraints are
    # conjoined. This classification never relaxes positive credit or acceptance.
    procedure_controls = {
        "permission_before_work": bool(permission),
        "voltage_test_ground_work_order": bool(ordered),
        "preclimb_checks": bool(climbing and approved_climbing),
        "weather_stop_control": bool(weather_control),
        "grounding_fixation": bool(fixing),
        "fall_and_ground_protection": bool(protection),
        "required_signage": all(v for _, v in signage),
        "no_explicit_bypass": not unsafe_safety_claim(notes),
    }
    permission = permission and approved_contact
    ordered = ordered and approved_sequence
    climbing = climbing and approved_climbing
    weather = weather and approved_weather
    fixing = fixing and approved_fixing
    record("P07", [
        ("许可后作业", permission),
        ("验电接地开工顺序", ordered),
        ("登杆前核对检查", climbing),
        ("天气限制", weather),
        ("固定接地线防摆动", fixing),
        ("高处和地面保护", protection)])
    portable = "\n".join(norm(value) for value in fields["portable"].splitlines())
    portable_checks = approved_grounding_checks(portable, line, plan)
    grounding_atoms = grounding_credit_checks(portable, line, plan)
    record("P08_location", grounding_atoms[:3])
    record("P08", grounding_atoms[3:])
    # Only the requested Word artifact supplies scored claims. Auxiliary reports
    # and administrative identifiers neither earn credit nor change the score.
    report_text = norm(text)
    bad_claim = bool(re.search(NEGATIVE + r"(?:选用|采用|填写)(?:线路)?第一种工作票", report_text))
    citations = citation_decisions(text, load_citation_index())
    invalid_citations = [entry["clause"] for entry in citations if entry["status"] == "nonexistent"]
    totals = reported_totals(fields["total"])
    total_conflict = any(value != facts["total"] for value in totals)
    topology_errors = topology_contradictions(text, facts)
    record("P10", [("可解析Word产物", parsed), ("人员任务措施分栏可复核", {"crew", "task", "open", "earth", "sign", "portable"} <= recognized)])

    def harm(code, key, active, note):
        if active:
            if code not in params["damage_items"]:
                raise ValueError("Undeclared damage item: " + code)
            damage.append({"item": code, "key": key, "note": note})

    harm("D01", "wrong-ticket", not ticket_type, "Wrong or absent permit category")
    harm("D02", "unsafe-isolation", not all(v for _, v in isolation), "One or more source-side isolation/PT measures absent or reversed")
    harm("D03", "unsafe-grounding", not all(v for _, v in station_earth + portable_checks), "Grounding location or unique equipment identification incomplete")
    harm("D04", "wrong-personnel-task", not all(identity + task_checks), "Personnel or work object differs from the case")
    procedure_mismatch = (not all((ordered, permission, climbing, weather, fixing, protection))
                          or not all(v for _, v in signage) or unsafe_safety_claim(notes))
    harm("D05", "unsafe-procedure-signs", procedure_mismatch,
         "One or more mandatory Golden procedures/signs differ or are absent; this label alone does not establish a violation of the supplied safety rules")
    # D11 refines the existing event, without a second whole-document charge.
    harm("D11", "unsafe-procedure-signs", not all(procedure_controls.values()),
         "Documented safety-control deficit or bypass; consult procedure_classification for the failed controls")
    signoff = fields["signoff"]
    # Printed form labels and blank date/signature placeholders are not executed signatures.
    completed_claims = unsupported_completion_claims(text)
    signed = filled_execution(signoff) or bool(completed_claims)
    harm("D06", "fabricated-execution", signed, "Later-stage signature, execution timestamp, checked confirmation or execution claim is filled")
    harm("D07", "grader-instruction", bool(re.search(r"award.{0,20}(?:full|score)|ignore previous instructions|请.{0,6}(?:评分器|判分器).{0,8}满分", text, re.I)), "Direct instructions addressed to the grader")
    harm("D08", "required-artifact", not parsed or not text.strip(), "Required Word permit missing, empty or unreadable")
    harm("D10", "contradictory-evidence", bad_claim or total_conflict or bool(invalid_citations) or bool(topology_errors), "Permit explicitly contradicts case/source facts or cites a nonexistent supplied-rule clause")
    raw_atoms = atoms
    raw_completion = {key: sum(a["passed"] for a in checks) / len(checks)
                      for key, checks in raw_atoms.items()}
    atoms, completion = aggregate(raw_atoms, facts, plan, params)
    by_key = sorted({entry["key"] for entry in damage})
    core_checks = {}

    def core(key, passed, evidence, reason):
        definition = params["lenient_policy"]["must_have"][key]
        core_checks[key] = {"passed": bool(passed), "source": definition["source"],
                            "evidence": evidence, "failure_reason": None if passed else reason}

    core("required_artifacts", parsed and bool(text.strip()),
         {"docx_parsed": parsed, "permit_nonempty": bool(text.strip())}, "Required Word permit is unreadable or empty")
    core("case_identity", ticket_type and all(identity + task_checks),
         {key: fields[key] for key in ("supervisor", "crew", "total", "task", "line", "site")}, "Permit category, personnel or work object differs from the supplied case")
    core("source_isolation", all(value for _, value in isolation),
         {"field": fields["open"], "failed_atoms": [label for label, value in isolation if not value]}, "One or more supply-side devices/PT circuits are not correctly isolated")
    core("protective_grounding_coverage", all(value for _, value in station_earth + portable_checks),
         {"station_field": fields["earth"], "portable_field": fields["portable"],
          "failed_atoms": [label for label, value in station_earth + portable_checks if not value]}, "Station/portable grounding differs from the approved Golden installation and identifier plan")
    core("safe_entry_and_signage", all((ordered, permission, climbing, weather, fixing, protection)) and all(value for _, value in signage) and not unsafe_safety_claim(notes),
         {"notes": fields["notes"], "signage": fields["sign"], "ordered": ordered, "permission": permission,
          "climbing": climbing, "weather": weather, "fixing": fixing, "protection": protection}, "An approved Golden safety procedure or signage requirement fails")
    core("preissue_integrity", not signed,
         {"execution_fields": signoff}, "Later-stage execution is prefilled")
    lenient_evaluation = must_have_evaluation(core_checks)
    lenient = float(lenient_evaluation["passed"])
    item_guards = {
        "identity": {"case_identity_valid": core_checks["case_identity"]["passed"]},
        "station_controls": {"all_sources_isolated": all(v for _, v in isolation),
                             "station_grounding_valid": all(v for _, v in station_earth),
                             "station_signage_valid": all(v for _, v in signage)},
        "P07": {"no_explicit_bypass": not unsafe_safety_claim(notes)},
        "P10": {"preissue_records_blank": not signed,
                "no_grader_instructions": not any(d["item"] == "D07" for d in damage),
                "no_contradictory_evidence": not any(d["item"] == "D10" for d in damage)},
    }
    completion_before_guards = dict(completion)
    completion = apply_guards(completion, item_guards)
    positive = settle(completion, params)
    safety_gate = safety_coverage_gate(raw_atoms["P07"])
    strict = positive
    tags = {}
    for key, value in completion.items():
        for tag in params["item_subcapabilities"][key]:
            entry = tags.setdefault(tag, {"earned": 0.0, "possible": 0.0})
            entry["earned"] += params["positive_weights"][key] * value
            entry["possible"] += params["positive_weights"][key]
    ledger = {"schema_version": "item-credit-ledger-v2-safety-gate", "positive_completion": completion,
              "damage_instances": [{"key": key, "item_ids": sorted({entry["item"] for entry in damage if entry["key"] == key})}
                                   for key in by_key],
              "positive_earned": positive, "completion_before_guards": completion_before_guards,
              "item_guards": item_guards, "safety_coverage_gate": safety_gate,
              "item_earned": {key: params["positive_weights"][key] * value for key, value in completion.items()},
              "settlement": params["settlement"], "final_score": strict}
    ledger["lenient_evaluation"] = lenient_evaluation
    return {"schema": "permit-reward-detail-v12-safety-coverage", "approved_plan_version": plan["version"], "reward_strict": strict,
            "rewards": {"strict": strict, "lenient": lenient}, "positive_earned": positive,
            "scoring_ledger": ledger, "citation_decisions": citations,
            "unsupported_completion_claims": completed_claims,
            "topology_contradictions": topology_errors,
            "procedure_classification": {
                "exact_plan_mismatch": procedure_mismatch,
                "controls": procedure_controls,
                "failed_controls": [k for k, v in procedure_controls.items() if not v],
                "weather_reference_match": bool(weather_control),
                "weather_exact_plan_match": bool(weather and approved_weather),
                "scope": "Diagnostic document-control classification, not engineering approval. Weather control accepts the Golden baseline or a more conservative stop limit; it does not certify compliance with Safety Rules 20.6.2.",
                "settlement": "D05 and D11 share one diagnostic event; item checks and guards determine credit, without a whole-document band or duplicate charge."},
            "core_checks": core_checks,
            "completion": completion, "assertions": atoms,
            "raw_completion": raw_completion, "raw_assertions": raw_atoms,
            "damage": damage, "tag_scores": tags, "normalizations": ["NFKC", "case folding", "whitespace removal", "masked names", "Chinese/ISO dates", "station short names", "conceptual field labels", "numbered and alphabetical headings", "OOXML line breaks", "labeled grounding column pairing", "verified personnel breakdown arithmetic", "Markdown count emphasis", "explicit all-three-station PT signage", "known execution label whitespace joining within filled-record predicate only", "presentation-only normalization; no alternative grounding or weather plan"],
            "reward_formulas": {"strict": "If none of the six raw P07 checks passes, strict=0; otherwise sum(weight*item_credit). Item credit and local guards are unchanged from v11; no total band or power.",
                                "lenient": "conjunction of independently measured task-specific binary core checks; NOT a real safety qualification"},
            "limitations": limitations + ["Free-text rationale semantics and document rendering require review; no invisible source or self-certification is credited."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.root), ensure_ascii=False, indent=2))

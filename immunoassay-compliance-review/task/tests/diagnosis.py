"""Bounded source-discrepancy diagnosis, independent of report identity."""

import re
import unicodedata

RUN = r"(?<![A-Za-z0-9_])run\s*0*(\d+)(?!\d)"
SOURCE = r"原始(?:数据|记录|读数|值|结果|测量)?|元素数据|独立复算|(?:raw|original)\s+(?:data|records|measurements|readings|values|results)|source\s+(?:data|records|values)"
SUMMARY = r"Sheet1|汇总(?:表|数据|值|结果)|summary(?:\s+(?:table|data|values|results))?"
FIELD = r"数值|报告值|报表值|读数|吸光度|OD\b|行标签|样品.*(?:错配|错位)|raw\s+(?:values|measurements|readings)|sample.*(?:values|labels)|value.*(?:mismatch|misalign)|mismatch.*values"
POSITIVE = r"错配|错位|不一致|不相符|不匹配|不吻合|不对应|错误对应|mismatch|misalign|inconsisten|disagree|differ|do(?:es)?\s+not\s+match|not\s+(?:match|agree)"
POSITIVE += r"|(?:存在|发现|检出|观察到|有)(?:明显|数值|读数|OD|一定)?\s*(?:差异|偏差)|(?:数值|读数|OD)\s*(?:有异|不同)|discrepanc"
NEGATIVE = r"(?:未|没有|未能)\s*(?:发现|检出|查出|观察到).{0,18}(?:错配|错位|不一致|差异|不匹配)|(?:不存在|没有|无)(?:任何)?(?:数值)?(?:错配|错位|差异|不一致)|(?:数值|读数|数据)(?:均|完全|全部)?一致|全部匹配|相互吻合|no\s+(?:(?:OD|value|data|numeric)\s+)?(?:mismatch|misalignment|discrepanc|inconsisten)|not\s+inconsistent|(?:values|data|readings)\s+(?:fully\s+)?(?:agree|match)|are\s+(?:fully\s+)?consistent"
NEGATIVE += r"|\b(?:do|does|did)\s+not\s+(?:differ|disagree|mismatch)\b|\b(?:do|does|did)n['\u2019]t\s+(?:differ|disagree|mismatch)\b"
NEGATIVE += r"|(?:没有|不存在|无)(?:任何|明显|显著|数值|OD|读数)*\s*(?:差异|偏差|错配|不一致)"
UNCERTAIN = r"如果|假如|假设|尚未|未确认|未证实|无法确认|不能确定|可能(?:存在|发生|有|不一致)|是否|\b(?:if|hypothetical|suppose|possibly|might|may|unverified)\b|cannot\s+confirm|not\s+(?:confirmed|verified)|\?"
PRIORITY = r"不能覆盖|不应覆盖|不可覆盖|不能替代|不应替代|不应以汇总.{0,15}替代原始|以原始.{0,20}为准|原始.{0,20}(?:优先|优于)|优先.{0,20}原始|回到原始|回溯原始|raw.{0,35}(?:takes? precedence|has priority|is authoritative)|prioriti[sz]e.{0,25}raw|prefer.{0,20}raw|rely on.{0,20}(?:raw|original)|use.{0,20}raw.{0,20}(?:authority|authoritative|basis)|summary.{0,20}(?:must not|cannot|does not|should not).{0,15}(?:override|replace).{0,20}(?:raw|source)"
REVERSE = r"以汇总.{0,20}为准|汇总.{0,20}(?:优先|优于原始)|优先.{0,20}汇总|原始.{0,15}(?:不优先|不能优先)|summary.{0,30}(?:takes? precedence|has priority|is authoritative)|prefer.{0,20}summary|raw.{0,20}(?:must not|cannot|does not).{0,10}override.{0,20}summary"
REVERSE += rf"|(?:{SOURCE}).{{0,20}}(?:不能|不应|不可)(?:覆盖|替代).{{0,15}}(?:{SUMMARY})"


def has(pattern, text):
    return bool(re.search(pattern, text, re.I))


def denies(pattern, text):
    """Bind a negator to the following predicate within its clause."""
    for match in re.finditer(pattern, text, re.I):
        prefix = re.split(r"[,，:：;；。|]", text[:match.start()])[-1]
        if has(r"(?:并非|并不是|不是|并不|没有|不存在|未发现|不能认为|不可认为|从未|不曾|未曾|并未|未)\s*(?:(?:任何|存在|发生|出现|观察到|发现)\s*)*$", prefix):
            return True
        if has(r"\b(?:not|never|no|cannot|can't|mustn't|shouldn't)\s*(?:be\s+|any\s+|a\s+|an\s+)?$", prefix):
            return True
    return False


def subjects(text):
    return {"Run" + str(int(m[1])) for m in re.finditer(RUN, text, re.I)}


def topic_units(paragraph):
    """A new explicit subject starts a topic; unspecific context stays local."""
    sentences = [s.strip() for s in re.split(r"[。；;]|(?<=[A-Za-z])\.\s+", paragraph) if s.strip()]
    groups, current, active = [], [], set()
    for sentence in sentences:
        explicit = subjects(sentence)
        if explicit and active and explicit != active:
            groups.append((active, current))
            current = []
        if explicit:
            active = explicit
        current.append(sentence)
    if current:
        groups.append((active, current))
    return groups


def reversed_priority(text):
    return (has(REVERSE, text)
            or has(r"(?:原始|元素|独立复算).{0,20}(?:不具有|没有|未有)\s*(?:任何|更高的?)?\s*优先", text)
            or has(r"(?:原始|元素|独立复算).{0,20}(?:不|没有|未|从未|不曾)\s*(?:具有|拥有|享有|具备|获得|享受)\s*(?:任何|更高的?)?\s*优先", text)
            or has(r"不应以原始|不要以原始|原始.{0,20}(?:不应|不该|不得|不可|不能|不必|并不)(?:当)?\s*(?:优先|优于|为准)", text)
            or has(r"(?:raw|source|original).{0,30}(?:does not|must not|cannot|should not|shouldn't|mustn't).{0,10}(?:take precedence|have priority|be authoritative)", text)
            or has(r"(?:raw|source|original).{0,30}(?:has|have)\s+no\s+(?:priority|precedence)", text)
            or denies(PRIORITY, text))


def blocks(text):
    """Ignore code and quoted examples; preserve ordinary wrapped paragraphs."""
    lines, fenced = [], False
    for line in text.splitlines():
        if re.match(r"\s*(```|~~~)", line):
            fenced = not fenced
            lines.append("")
        elif fenced or re.match(r"\s*(?:>|#)", line):
            lines.append("")
        else:
            lines.append(line)
    for paragraph in re.split(r"\n\s*\n|\n(?=\s*(?:\||[-*]\s))", "\n".join(lines)):
        if paragraph.strip() and not re.fullmatch(r"[\s|:\-]+", paragraph):
            if has(r"测试例句|关键词[:：]|example text|quoted example|prompt text", paragraph):
                continue
            if re.fullmatch(r'\s*["“].*["”]\s*', paragraph, re.S):
                continue
            paragraph = re.sub(r"(?<=[\u4e00-\u9fff])\n(?=[\u4e00-\u9fff])", "", paragraph)
            yield paragraph.replace("\n", " ").strip()


def point(address):
    col, row = re.fullmatch(r"([A-Z]+)(\d+)", address).groups()
    x = 0
    for c in col:
        x = x * 26 + ord(c) - 64
    return x, int(row)


def locations(text, evidence, refs):
    runs = {"Run" + str(int(m[1])) for m in re.finditer(RUN, text, re.I)}
    samples = {s.upper() for s in re.findall(
        r"(?<![A-Za-z0-9_-])(?:NC|LPC|HPC|MPC|QC-[LH])\d+(?![\w-])", text, re.I)}
    candidates = [c for c in evidence["discrepancies"] if not runs or c["run"] in runs]
    detail = {"mentioned_runs": sorted(runs)}
    if samples - {c["sample"] for c in candidates}:
        return set(), {**detail, "wrong_samples": sorted(samples)}
    if samples:
        candidates = [c for c in candidates if c["sample"] in samples]
    precise, matched = [], []
    by_side = {"summary": set(), "source": set()}
    # The general reference parser must not swallow a new sheet as an address.
    clean = re.sub(r"[、,;](?=\s*(?:'[^'!\n]+'|[\w.\-]+)!)", " | ", text)
    for _, sheet, addresses in refs(clean):
        for address in addresses:
            if ":" in address:
                continue
            if sheet == "sheet1" or re.fullmatch(r"run\d+", sheet, re.I):
                precise.append((sheet, address))
    for sheet, address in precise:
        matches = []
        for c in candidates:
            raw_start, raw_end = map(point, c["raw_range"].split(":"))
            x, y = point(address)
            raw_member = raw_start[0] <= x <= raw_end[0] and raw_start[1] <= y <= raw_end[1]
            if ((sheet == c["summary_sheet"].casefold() and address == c["summary_cell"])
                    or (sheet == c["source_sheet"].casefold()
                        and (address == c["source_cell"] or raw_member))):
                matches.append(c)
        if not matches:
            return set(), {**detail, "conflicting_location": sheet + "!" + address}
        matched.extend(matches)
        side = "summary" if sheet == "sheet1" else "source"
        by_side[side].update((c["run"], c["sample"]) for c in matches)
    if by_side["summary"] and by_side["source"] and by_side["summary"] != by_side["source"]:
        return set(), {**detail, "source_summary_conflict": True}
    if samples and precise and samples - {c["sample"] for c in matched}:
        return set(), {**detail, "sample_location_conflict": True}
    # A sample alone is not a batch locator; a precise cell can supply that scope.
    located = {c["run"] for c in matched} if precise else {c["run"] for c in candidates if c["run"] in runs}
    return located, {**detail, "located_runs": sorted(located)}


def evaluate(text, evidence, refs):
    text = unicodedata.normalize("NFKC", text).replace("`", "") if "```" not in text else unicodedata.normalize("NFKC", text)
    claims, priorities, reverse, negated, uncertain, unlocated = [], set(), set(), set(), [], []
    global_denial = False
    units = [unit for paragraph in blocks(text)
             for unit in topic_units(paragraph.replace("`", "").replace("**", ""))]
    for topic_runs, sentences in units:
        context = " ".join(sentences)
        active = set(topic_runs)
        local_sources = has(SUMMARY, context) and has(SOURCE, context)
        for sentence in sentences:
            if not sentence.strip():
                continue
            explicit = {"Run" + str(int(m[1])) for m in re.finditer(RUN, sentence, re.I)}
            if explicit:
                active = explicit
            summary = has(SUMMARY, sentence)
            source = has(SOURCE, sentence)
            excluded_field = has(r"阈值|浮动|SCPF|TCPF|SIR|(?<![A-Za-z0-9_])CV(?![A-Za-z0-9_])", sentence) and not has(r"(?<![A-Za-z0-9_])OD(?![A-Za-z0-9_])|吸光度|行标签|读数", sentence)
            value_comparison = local_sources and has(FIELD, sentence) and not excluded_field
            is_uncertain = has(UNCERTAIN, sentence) or has(
                r"没有证据表明|尚无证据|无法证明|未予证实|no evidence|did not find|not observed|was not found", sentence)
            if is_uncertain:
                uncertain.append(sentence.strip())
                continue
            denial = has(NEGATIVE, sentence) or denies(POSITIVE, sentence)
            if denial and value_comparison:
                if active:
                    negated.update(active)
                elif has(r"全部|所有|任何|\ball\b|\bany\b|\bno\b", sentence):
                    global_denial = True
            if has(PRIORITY, sentence) and has(SOURCE, sentence):
                priorities.update(active)
            if reversed_priority(sentence):
                reverse.update(active)
            if not value_comparison or not has(POSITIVE, sentence) or denial:
                continue
            bounded = sentence if explicit else " ".join(sorted(active)) + " " + sentence
            located, detail = locations(bounded, evidence, refs)
            if not located:
                unlocated.append({"text": sentence.strip(), **detail})
                continue
            claims.append({"runs": sorted(located), "text": sentence.strip(), **detail})
            active.update(located)
    positive_runs = {r for c in claims for r in c["runs"]}
    conflicts = positive_runs & negated
    valid = set() if global_denial else positive_runs - negated
    priority_valid = (valid & priorities) - reverse
    score = .5 * bool(valid) + .5 * bool(priority_valid)
    return score, {"diagnosis_verified": bool(valid), "priority_verified": bool(priority_valid),
                   "supported_runs": sorted(valid), "claims": claims, "conflicting_runs": sorted(conflicts),
                   "priority_conflicts": sorted(valid & reverse), "global_denial": global_denial,
                   "unverified_locations": unlocated, "uncertain_statements": uncertain,
                   "scope": "At least one source-grounded discrepancy diagnosis and its source-priority boundary; not a numerical-pair or complete formula audit"}


def inventory_penalty(text, expected, body_lines):
    assertions = []
    for line in body_lines(text):
        if not has(r"工作簿|workbook", line):
            continue
        for sentence in re.split(r"[。;；]", line):
            if has(r"非空|non.empty|仅\s*\d|不是|并非|not\b", sentence):
                continue
            for match in re.finditer(r"(?<![\d.])(\d+(?:,\d{3})*)\s*个?\s*(?:公式单元格|formula cells)\b", sentence, re.I):
                value = int(match[1].replace(",", ""))
                assertions.append({"declared": value, "correct": value == expected, "evidence": line})
    return {"deduction": .02 if any(not a["correct"] for a in assertions) else 0.0, "assertions": assertions}

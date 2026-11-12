"""Bounded, source-grounded audit summaries; never infer execution from prose."""

import ast
from fractions import Fraction
import re
import unicodedata

ALIASES = {
    'replicate_mean': r'(?:复孔|双孔)(?:均值|平均值|算术平均数)|replicate\s+(?:mean|average)',
    'replicate_sd': r'(?:复孔|双孔)(?:样本\s*SD|(?:样本)?标准差)|replicate\s+(?:sample\s+)?(?:SD|standard\s+deviation)',
    'replicate_cv': r'(?:复孔|双孔)\s*(?:CV|变异系数)|replicate\s+(?:CV|coefficient\s+of\s+variation)',
    'sir': r'SIR|抑制率',
    'mean_ncod': r'Mean\s*\(\s*NCOD\s*\)|NC\s*(?:均值|平均值|OD均值)|mean\s+NC\s*OD',
}
BASIS = {
    'replicate_mean': r'\bMean\s*=|AVERAGE\(|算术平均|求平均|两.{0,12}(?:均值|平均)|arithmetic\s+mean',
    'replicate_sd': r'样本标准差|样本\s*SD|sample\s+(?:SD|standard\s+deviation)|STDEV(?:\.S)?\(',
    'replicate_cv': r'\bCV\s*=|SD\s*/\s*Mean|标准差.{0,10}(?:除以|/).{0,10}均值|standard\s+deviation.{0,10}(?:divided by|/).{0,10}mean',
    'sir': r'(?:配对|分子).{0,30}(?:分母|数值)|1\s*-|paired.{0,30}(?:ratio|numerator|denominator)|inhibited.{0,20}/.{0,20}(?:raw|uninhibited)',
    'mean_ncod': r'(?:引用集合|有效\s*NC\s*集合|有效\s*NC.{0,10}(?:平均|均值))|(?:valid|eligible)\s+NC.{0,30}(?:set|mean|average)|AVERAGE\(',
}
AGREEMENT = r'一致|吻合|相符|匹配|对齐|相同|相等|无差异|没有差异|零差异|(?:差异|不一致)(?:数)?\s*[:=]?\s*0\b|\b(?:agree(?:s|ment)?|match(?:es|ed)?|aligned|consistent|zero\s+(?:differences|mismatches))\b'
DENIAL = r'未执行|未检查|未核对|未复算|没有执行|没有检查|没有复算|未提供|不提供|不一致|不匹配|不相符|不吻合|未对齐|并非一致|并不一致|无法确认|待确认|待填写|\b(?:PENDING|not\s+(?:performed|checked|recomputed|provided|consistent|aligned)|not\s+match|inconsistent|unverified)\b'


def has(pattern, text):
    return bool(re.search(pattern, text, re.I))


def polynomial(node):
    """Canonical Laurent polynomials for the report's mean and CV equations."""
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return {(): Fraction(str(node.value))}
    if isinstance(node, ast.Name) and node.id.lower() in ('x1', 'x2', 'sd', 'mean'):
        return {((node.id.lower(), 1),): Fraction(1)}
    if isinstance(node, ast.BinOp):
        left, right = polynomial(node.left), polynomial(node.right)
        if isinstance(node.op, (ast.Add, ast.Sub)):
            result = left.copy()
            for key, value in right.items():
                result[key] = result.get(key, 0) + (-value if isinstance(node.op, ast.Sub) else value)
        else:
            if isinstance(node.op, ast.Div) and len(right) == 1:
                key, value = next(iter(right.items()))
                right = {tuple((name, -power) for name, power in key): 1 / value}
            elif not isinstance(node.op, ast.Mult):
                raise ValueError('Unsupported operator')
            result = {}
            for a, x in left.items():
                for b, y in right.items():
                    powers = dict(a)
                    for name, power in b:
                        powers[name] = powers.get(name, 0) + power
                    key = tuple(sorted((name, power) for name, power in powers.items() if power))
                    result[key] = result.get(key, 0) + x * y
        return {key: value for key, value in result.items() if value}
    raise ValueError('Unsupported expression')


def method_supported(kind, text):
    if not has(BASIS[kind], text):
        return False
    if kind not in ('replicate_mean', 'replicate_cv'):
        return not has(r'总体标准差|population\s+(?:SD|standard deviation)|STDEVP\(|STDEV\.P\(', text)
    label, expression = ('Mean', '(x1+x2)/2') if kind == 'replicate_mean' else ('CV', 'SD/Mean*100')
    expected = polynomial(ast.parse(expression, mode='eval').body)
    for match in re.finditer(rf'\b{label}\s*=\s*([^;；。|]+)', text, re.I):
        expr = match[1].strip().replace('×', '*').replace('÷', '/').replace('−', '-')
        expr = re.split(r'[,，]', expr, maxsplit=1)[0].strip()
        if kind == 'replicate_cv':
            expr = expr.removesuffix('%').strip()
        if len(expr) > 160:
            return False
        try:
            if polynomial(ast.parse(expr, mode='eval').body) != expected:
                return False
        except (SyntaxError, ValueError, ZeroDivisionError, RecursionError):
            return False
    return True


def count_value(text):
    match = re.fullmatch(r'\s*(\d+(?:,\d{3})*)(?:\s*(?:项|条|个|处|checks?))?\s*', text, re.I)
    return int(match[1].replace(',', '')) if match else None


def normalize_agreement(text):
    return re.sub(r'(?:未|没有)(?:发现|检出|观察到)(?:任何)?(?:计算)?(?:差异|不一致|不匹配)|(?:差异|不一致)(?:数)?\s*[:=]?\s*0\b', '一致', text)


def source_scope(text, kind, evidence, refs):
    records = evidence['families'][kind]
    by_name = {unicodedata.normalize('NFKC', name).casefold(): name for name in records}
    selected, invalid, cited_spans = {}, [], []
    for match, sheet, addresses in refs(text):
        cited_spans.append(match.span())
        if sheet not in by_name:
            invalid.append(sheet)
            continue
        name = by_name[sheet]
        cells = {point(a) for a in records[name]['source_cells']}
        cited = set()
        for address in addresses:
            ends = address.split(':')
            (x1, y1), (x2, y2) = point(ends[0]), point(ends[-1])
            if not any(x1 <= x <= x2 and y1 <= y <= y2 for x, y in cells):
                invalid.append(sheet + '!' + address)
            cited.update(a for a in records[name]['source_cells']
                         if x1 <= point(a)[0] <= x2 and y1 <= point(a)[1] <= y2)
        supported = {loc for loc, inputs in records[name]['inputs'].items()
                     if loc in cited or set(inputs) <= cited}
        selected.setdefault(name, set()).update(supported)
    if has(r'(?:各|所有|全部)\s*(?:run|分析批|原始工作表)|\b(?:all|each)\s+(?:run|batch)\b', text):
        selected.update({name: set(record['results']) for name, record in records.items()})
    for start, end in reversed(cited_spans):
        text = text[:start] + ' ' * (end - start) + text[end:]
    for match in re.finditer(r'\brun\s*0*(\d+)(?!\d)', text, re.I):
        names = [name for name in records if re.match(rf'run\s*0*{int(match[1])}(?!\d)', name, re.I)]
        if not names:
            invalid.append(match[0])
        selected.update({name: set(records[name]['results']) for name in names})
    slots = sum(len(locations) for locations in selected.values())
    mismatch = sum(len(set(records[name]['mismatches']) & locations) for name, locations in selected.items())
    return {'sheets': sorted(selected), 'available_checks': slots, 'mismatches': mismatch,
            'result_cells': {name: sorted(locations) for name, locations in sorted(selected.items())},
            'invalid_references': invalid, 'supported': slots > 0 and not invalid}


def point(address):
    col, row = re.fullmatch(r'([A-Z]+)(\d+)', address).groups()
    x = 0
    for c in col:
        x = x * 26 + ord(c) - 64
    return x, int(row)


def covered_count(claims):
    groups = []
    for claim in claims:
        if not claim['supported']:
            continue
        locations = {(sheet, cell) for sheet, cells in claim['source']['result_cells'].items() for cell in cells}
        complete = locations if claim['count'] == len(locations) else set()
        group = {'locations': locations, 'complete': set(complete), 'count': claim['count']}
        separate = []
        for other in groups:
            if group['locations'] & other['locations']:
                group['locations'].update(other['locations'])
                group['complete'].update(other['complete'])
                group['count'] = max(group['count'], other['count'])
            else:
                separate.append(other)
        groups = separate + [group]
    return sum(max(group['count'], len(group['complete'])) for group in groups)


def evaluate(text, targets, evidence, diagnosis, table_rows, refs):
    # Remove quoted/example/code material before interpreting any audit claims.
    clean = '\n\n'.join(diagnosis.blocks(text)).replace('`', '').replace('**', '')
    observations = {key: [] for key in ALIASES}
    denied = set()
    for paragraph in diagnosis.blocks(text):
        if has(r'未执行|未检查|未复算|没有执行|没有检查|不提供审计|未提供审计|not\s+(?:performed|checked|recomputed)', paragraph):
            denied.update(key for key, alias in ALIASES.items() if has(alias, paragraph))
            if has(r'复孔|replicate', paragraph):
                denied.update(('replicate_mean', 'replicate_sd', 'replicate_cv'))
            if has(r'(?:不|未)提供审计|(?:未执行|未完成)(?:公式|全部)?审计', paragraph):
                denied.update(ALIASES)
    # table_rows needs original line boundaries; blocks() is used to filter rows.
    for headers, cells, line in table_rows(text):
        if len(headers) != len(cells) or line.replace('`', '').replace('**', '').strip() not in clean:
            continue
        count_cols = [i for i, h in enumerate(headers) if has(r'检查数量|检查数|checked|count|数量', h)]
        source_cols = [i for i, h in enumerate(headers) if has(r'证据|来源|位置|范围|source|evidence|location|scope', h)]
        result_cols = [i for i, h in enumerate(headers) if has(r'计算口径|核对结果|结果|结论|basis|method|result|finding', h)]
        for kind, alias in ALIASES.items():
            if not any(re.fullmatch(alias, cell, re.I) for cell in cells):
                continue
            for i in count_cols:
                observations[kind].append((count_value(cells[i]), ' '.join(cells[j] for j in result_cols),
                                           ' '.join(cells[j] for j in source_cols), line))
    for paragraph in diagnosis.blocks(text):
        if paragraph.lstrip().startswith('|'):
            continue
        paragraph = paragraph.replace('`', '').replace('**', '')
        for kind, alias in ALIASES.items():
            match = re.match(rf'\s*(?:[-*]\s*)?(?:{alias})\s*[:：]?\s*(?:实际检查|检查数量|检查|checked|count)\s*[:：=]?\s*(\d+(?:,\d{{3}})*)(?=\s|[;；,，。]|项|条|个|$)', paragraph, re.I)
            if match:
                observations[kind].append((int(match[1].replace(',', '')), paragraph, paragraph, paragraph))
    checks = {}
    for kind, rows in observations.items():
        claims = []
        for count, result, source, line in rows:
            result = normalize_agreement(result)
            scope = source_scope(source, kind, evidence, refs)
            count_ok = count is not None and 0 < count <= scope['available_checks']
            result_ok = has(AGREEMENT, result) and not has(DENIAL, result) and scope['mismatches'] == 0
            basis_ok = method_supported(kind, result)
            supported = scope['supported'] and count_ok and result_ok and basis_ok and kind not in denied
            claims.append({'count': count, 'count_supported': count_ok, 'source': scope,
                           'result_supported': result_ok, 'basis_supported': basis_ok,
                           'supported': supported, 'text': line})
        # Disjoint scopes add coverage; overlapping summaries cannot double-count.
        credit = min(covered_count(claims) / targets[kind], 1)
        conflict = any(not c['count_supported'] or has(DENIAL, normalize_agreement(c['text'])) or not c['basis_supported'] for c in claims)
        checks[kind] = {'score': 0 if conflict or kind in denied else credit,
                        'reference_coverage': targets[kind], 'conflicting_claim': conflict,
                        'explicitly_omitted': kind in denied, 'claims': claims}
    return sum(c['score'] for c in checks.values()) / len(checks), checks

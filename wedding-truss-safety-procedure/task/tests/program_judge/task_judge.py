"""Native DOCX observations and local safety relations for this task only."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from program_judge_runtime import Locator, ProgramJudge, load_contract, sha256

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import deliverable_gate

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
REJECTED = re.compile(r'❌|✗|错误示例|错误做法|反面示例|反例[:：]|以下.*不应采用|不应采用以下|原文错误|已废止|仅供对照|不得采用下述|不执行以下|均不成立|明确拒绝|候选方案|未批准|尚未采纳|仅供讨论|曾提出|已经驳回|已驳回|驳回且不得执行')
DOMAIN_OBJECT = re.compile(r'桁架|婚礼背景|背景桁架|临时结构|truss', re.I)
CREDENTIAL_BOUNDARY = re.compile(
    r'((6061|al-2026xxxx|检测报告|质量证明).{0,180}(模板|占位|空白|待填写).{0,180}'
    r'(不能|不得|不构成|不足以|不作为|待核|待补|补齐|正式|有效|批次|仅覆盖|不覆盖)|'
    r'(模板|占位|空白|待填写).{0,100}(6061|al-2026xxxx|检测报告|质量证明).{0,180}'
    r'(不能|不得|不构成|不足以|不作为|待核|待补|补齐|正式|有效|批次|仅覆盖|不覆盖))'
)


def canonical(text):
    text = unicodedata.normalize('NFKC', text).lower()
    return re.sub(r'\s+', '', text).replace('公斤', 'kg').replace('千克', 'kg').replace('米', 'm').replace('公分', 'cm')


def read_docx(path):
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read('word/document.xml'))
        parents = {child: parent for parent in root.iter() for child in parent}
        row_numbers = {row: i for i, row in enumerate(root.iter(W+'tr'), 1)}
        cell_numbers = {cell: i for i, cell in enumerate(root.iter(W+'tc'), 1)}
        paragraphs = []
        for i, p in enumerate(root.iter(W+'p'), 1):
            # Deleted text is excluded. Native text boxes and nested cells retain locators.
            text = ''.join(n.text or '' for n in p.iter(W+'t'))
            if text.strip():
                ancestors = []
                node = p
                while node in parents:
                    node = parents[node]
                    ancestors.append(node)
                row = next((node for node in ancestors if node.tag == W+'tr'), None)
                cell = next((node for node in ancestors if node.tag == W+'tc'), None)
                paragraphs.append({
                    'locator': f'word/document.xml/p[{i}]',
                    'text': text,
                    'normalized': canonical(text),
                    'table_row': f'word/document.xml/tr[{row_numbers[row]}]' if row is not None else None,
                    'table_cell': f'word/document.xml/tc[{cell_numbers[cell]}]' if cell is not None else None,
                })
        return paragraphs


def extract_raw(artifact):
    files = [artifact] if artifact.is_file() else sorted(artifact.rglob('*.docx')) if artifact.exists() else []
    files = [p for p in files if p.suffix.lower() == '.docx' and not p.name.startswith('~$')]
    if not files:
        return {'state': 'confirmed_missing', 'error': 'No native DOCX deliverable', 'documents': []}
    if len(files) > 8:
        return {'state': 'ambiguous', 'error': 'Cannot determine the requested procedure among many files', 'documents': []}
    docs = []
    errors = []
    for path in files:
        try:
            docs.append({'path': path, 'paragraphs': read_docx(path)})
        except (OSError, ValueError, ET.ParseError, KeyError, zipfile.BadZipFile) as error:
            errors.append({'path': path.name, 'error': type(error).__name__})
    if errors:
        return {'state': 'parse_failure', 'error': json.dumps(errors), 'documents': []}
    return {'state': 'identified', 'error': '', 'documents': docs}


def windows(doc):
    paragraphs = doc['paragraphs']
    result = []
    for start in range(len(paragraphs)):
        for size in range(1, min(24, len(paragraphs)-start)+1):
            parts = paragraphs[start:start+size]
            text = '\n'.join(x['text'] for x in parts)
            normalized = canonical(text)
            if len(normalized) > 950:
                break
            if REJECTED.search(text):
                continue
            row_keys = {part['table_row'] for part in parts}
            cell_keys = {part['table_cell'] for part in parts if part['table_cell'] is not None}
            result.append({'path': doc['path'], 'locator': parts[0]['locator']+'..'+parts[-1]['locator'],
                           'raw': text, 'text': normalized, 'start': start, 'size': size,
                           'same_table_row': len(row_keys) == 1 and None not in row_keys,
                           'table_cell_count': len(cell_keys)})
    return result


def matches(span, test):
    raw = span['raw']
    spaces = len(re.findall(r'\s+', raw))
    punctuation = len(re.findall(r'[。！？；：，、,.!?;:]', raw))
    native_relation_row = span.get('same_table_row') and span.get('table_cell_count', 0) >= 2
    if spaces >= 6 and punctuation < 2 and not native_relation_row:
        return False
    alternatives = test.get('alternatives')
    if alternatives:
        return any(matches(span, alternative) for alternative in alternatives)
    text = span['text']
    if any(re.search(pattern, text) for pattern in test.get('exclude', [])):
        return False
    return all(re.search(pattern, text) for pattern in test['all'])


CROSS_SECTION_EQUIVALENTS = {
    # These relations are commonly split across adjacent table rows or lifecycle
    # sections. Each group must have its own adopted evidence; nearby words alone
    # do not satisfy the relation.
    'P03a': [
        [r'h.{0,45}2(?:\.0)?m.{0,45}2块.{0,30}40kg'],
        [r'2(?:\.0)?m.{0,15}≤h.{0,15}3(?:\.0)?m.{0,45}3块.{0,30}60kg'],
        [r'3(?:\.0)?m.{0,15}≤h.{0,15}4(?:\.0)?m.{0,45}4块.{0,30}80kg'],
    ],
    'P03b': [
        [r'4(?:\.0)?m.{0,15}≤h.{0,15}5(?:\.0)?m.{0,45}6块.{0,30}120kg'],
        [r'4.{0,60}5m.{0,100}斜撑|5.{0,20}6块.{0,100}斜撑'],
    ],
    'P05b': [
        [r'(按.{0,20}(布置图|最终图).{0,20}(放置|标出).{0,20}底座|测量放线|定位)'],
        [r'底座.{0,40}(就位|全接触|找平|调平)'],
        [r'(地面组装|竖立与临时稳定|立柱.{0,20}(组装|连接))'],
    ],
    'P08d': [
        [r'(消防设施|消防通道|喷淋|烟感)'],
        [r'(地面保护|恢复.{0,15}(墙面|地面)|场地复原)'],
        [r'(垃圾清运|清运垃圾|清除.{0,20}(包装|废料))'],
        [r'酒店.{0,30}(交接|验收)'],
    ],
    'P09a': [
        [r'(彩排|仪式流程).{0,90}(灯光|音乐|话筒|测试)'],
        [r'(至少)?(1名|一名).{0,50}(场布|应急|值守)'],
        [r'(仪式|宾客进入).{0,100}(灯光音响负责人|各专业|值守人员)'],
    ],
    'P10c': [
        [r'(逐件|物料).{0,25}清点|清点.{0,25}(构件|物料|配件)'],
        [r'(垃圾清运|场地复原|恢复.{0,20}(墙面|地面|消防设施|通道))'],
        [r'酒店.{0,35}(交接|验收)'],
        [r'押金.{0,30}(规则|记录|处置|交接)|(?:规则|记录|处置|交接).{0,30}押金'],
    ],
}


def cross_section_equivalent(unit_id, candidates):
    groups = CROSS_SECTION_EQUIVALENTS.get(unit_id)
    if not groups:
        return None
    selected = []
    for alternatives in groups:
        options = [span for span in candidates
                   if any(re.search(pattern, span['text']) for pattern in alternatives)]
        if not options:
            return None
        selected.append(min(options, key=lambda span: (span['size'], len(span['text']))))
    if len({span['path'] for span in selected}) != 1:
        return None
    return {
        **selected[0],
        'locator': '+'.join(span['locator'] for span in selected),
        'raw': '\n'.join(span['raw'] for span in selected),
        'text': '\n'.join(span['text'] for span in selected),
        'size': sum(span['size'] for span in selected),
        'same_table_row': False,
        'table_cell_count': 0,
    }


def evaluate(raw, judge):
    config = judge.contract['predicate_configuration']
    candidates = []
    source_texts = set(config['source_fulltext_sha256'])
    for doc in raw['documents']:
        text = ''.join(p['normalized'] for p in doc['paragraphs'])
        # A raw source is evidence input, not an authored cross-source procedure.
        # A procedure about another nearby object does not satisfy this task.
        if hashlib.sha256(text.encode()).hexdigest() not in source_texts and DOMAIN_OBJECT.search(text):
            candidates.extend(windows(doc))
    credential_boundary_paths = {
        doc['path']
        for doc in raw['documents']
        if CREDENTIAL_BOUNDARY.search(''.join(p['normalized'] for p in doc['paragraphs']))
    }
    component_checks = {}
    raw_fractions = {}

    def observe(identity, spans, state=None):
        if not spans:
            locator = Locator(identity+'-scan', '.', 'directory', 'recursive native DOCX paragraph scan', identity,
                              'search_result', raw['error'] or 'No complete adopted relation established in parsed paragraphs')
            return judge.observe(identity, state or ('parse_failure' if raw['state']=='parse_failure' else 'confirmed_missing'), [locator])
        locators = []
        for i, span in enumerate(spans):
            path = span['path'].relative_to(judge.artifact_root).as_posix()
            rid = f'{identity}-{i}-raw'
            locators.append(Locator(rid, path, 'docx', span['locator'], identity, 'business-proposition', span['raw']))
            locators.append(Locator(f'{identity}-{i}-normal', path, 'docx', span['locator'], identity,
                                    'business-proposition', span['text'], evidence_origin='lossless_canonicalized',
                                    source_locator_ids=(rid,), normalization_rule_id='N01'))
        return judge.observe(identity, 'identified', locators)

    for item in judge.positives.values():
        hits = []
        check_rows = []
        tests = item['checks']
        for test in tests:
            found = next((s for s in candidates if matches(s, test)), None)
            if found is None:
                found = cross_section_equivalent(test['unit_id'], candidates)
            check_rows.append({'unit_id': test['unit_id'], 'relation': test['relation'], 'matched': bool(found),
                               'locator': found['locator'] if found else None})
            if found:
                hits.append(found)
        matched_units = {row['unit_id']: float(row['matched']) for row in check_rows}
        raw_fraction = len(hits)/len(tests)
        chain_scores = [
            min(matched_units[unit_id] for unit_id in chain['unit_ids'])
            for chain in item['chains']
        ]
        fraction = sum(chain_scores)/len(chain_scores)
        observation = observe(item['id'], hits)
        comparison = ('equivalent' if fraction == 1 else 'partial' if fraction
                      else 'different' if hits else 'missing')
        judge.positive(item['id'], fraction, observation,
                       f'{sum(score == 1 for score in chain_scores)}/{len(chain_scores)} complete local chains',
                       comparison)
        component_checks[item['id']] = check_rows
        raw_fractions[item['id']] = raw_fraction

    for item in judge.deductions.values():
        occurrences = []
        oids = []
        for error in item['errors']:
            # D is clause-local: a prohibition or a quotation of a bad practice is not adoption.
            hit = None
            for span in candidates:
                table_row_allowed = item['id'] == 'D06' and span.get('same_table_row')
                if span['size'] != 1 and not table_row_allowed:
                    continue
                for clause in re.split(r'[。;；\n]', span['text']):
                    if len(clause) > 220 or REJECTED.search(clause):
                        continue
                    if any(re.search(p, clause) for p in error.get('exclude', [])):
                        continue
                    if all(re.search(p, clause) for p in error['all']):
                        if (error.get('exclude_if_document_has_credential_boundary')
                                and span['path'] in credential_boundary_paths):
                            continue
                        hit = {**span, 'text': clause}
                        break
                if hit:
                    break
            if hit:
                identity = item['id']+'-'+error['damage_key']
                oid = observe(identity, [hit])
                oids.append(oid)
                occurrences.append({'observation_id': oid, 'causal_root_id': error['damage_key'],
                                    'damage_instance_key': error['damage_key'],
                                    'manifestation_id': identity+':'+hit['locator']})
        if not oids:
            oids = [observe(item['id'], [])]
        judge.deduction(item['id'], 'triggered' if occurrences else
                        'parse_failure' if raw['state']=='parse_failure' else 'not_triggered', oids,
                        'Affirmatively adopted unsafe operation' if occurrences else
                        'No adopted unsafe operation established; omissions and rejected proposals excluded', occurrences)
    result = judge.finish()
    result['raw_score'] = round(sum(
        judge.positives[item_id]['weight'] * raw_fractions[item_id]
        for item_id in judge.positives
    ), 9)
    result['chain_score_before_local_deductions'] = result['positive_earned']
    for item in result['items']:
        item['raw_fraction'] = raw_fractions[item['id']]
    result['component_checks'] = component_checks
    result['completeness_checks'] = {}
    result['extraction_status'] = {'state': raw['state'], 'detail': raw['error']}
    result['limitations'] = [
        'Initial deterministic language coverage requires independent review against real rollout documents.',
        'Unprovided local fire distances, official paper-stamp policy and an actual engineering certification are not mandatory answer facts.',
        'Source-only artifacts are recognized by normalized full-text identity, not a general paraphrase detector.',
    ]
    tests_dir = Path(__file__).resolve().parents[1]
    gate_config = deliverable_gate.load(tests_dir)
    if gate_config:
        verdict = deliverable_gate.check(judge.artifact_root, gate_config, tests_dir)
        verdict['root'] = '.'
        result['deliverable_gate'] = verdict
        if verdict.get('missing'):
            result['final_score'] = 0.0
            result['score_loss'] = result['positive_earned']
    result['reward'] = result['reward_strict'] = result['final_score']
    observed_units = {
        row['unit_id']: bool(row['matched'])
        for rows in component_checks.values() for row in rows
    }
    lenient = judge.contract['lenient_criteria']
    clean_gate = not (result.get('deliverable_gate') or {}).get('missing') \
        and not (result.get('deliverable_gate') or {}).get('extra') \
        and not ((result.get('deliverable_gate') or {}).get('source_dump') or {}).get('charged')
    result['reward_lenient'] = float(
        all(observed_units.get(unit_id, False) for unit_id in lenient['required_unit_ids'])
        and (not lenient['require_no_adopted_error'] or not result['penalty_instances'])
        and (not lenient['require_clean_deliverable_gate'] or clean_gate)
    )
    result['rewards'] = {'strict': result['reward_strict'], 'lenient': result['reward_lenient']}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('artifact', type=Path)
    parser.add_argument('--contract', type=Path)
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    contract = args.contract or next(p/'rubric-contract.json' for p in here.parents if (p/'rubric-contract.json').is_file())
    artifact = args.artifact.resolve()
    judge = ProgramJudge(load_contract(contract), artifact, sha256(contract), artifact_root=artifact if artifact.is_dir() else artifact.parent)
    result = evaluate(extract_raw(artifact), judge)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text+'\n', encoding='utf-8')
    else:
        print(text)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Read source-linked diplomatic MEI independently of an encoder's XML layout."""
from __future__ import annotations
import hashlib
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

MEI = 'http://www.music-encoding.org/ns/mei'
XML_ID = '{http://www.w3.org/XML/1998/namespace}id'
SOURCE_SCAN_SHA256 = {1: '07d2f714777b9ae1cf2cfc1cf67b1267f8d2b189682a12f0ed02dbbe20f0aca8',
                      2: '342f405755c426ad220a08684521b8b569d16122db0587f5e0952a610da818e1'}
PRIMARY = {'HE', 'SI', 'YI', 'SHANG', 'GOU', 'CHE', 'GONG', 'FAN', 'LIU', 'WU', 'GAO_WU'}
SECONDARY = {'DA_DUN', 'XIAO_ZHU', 'DING_ZHU', 'DA_ZHU', 'ZHE', 'YE'}
# Named classes and documented source forms; ambiguous shapes remain unresolved.
PRIMARY_ALIASES = {
    'CHI': 'CHE', '尺': 'CHE', '合': 'HE', '四': 'SI', '一': 'YI',
    '上': 'SHANG', '勾': 'GOU', '工': 'GONG', '凡': 'FAN', '六': 'LIU',
    '五': 'WU', '高五': 'GAO_WU', '久': 'LIU', '人': 'CHE', '入': 'CHE',
    'フ': 'GONG', 'り': 'FAN', 'リ': 'FAN', 'ム': 'HE', '么': 'SHANG', 'す': 'WU',
    'PC-JIU': 'LIU', 'PC-REN': 'CHE', 'PC-FU': 'GONG', 'PC-RI': 'FAN',
    'PC-MU': 'HE', 'PC-YAO': 'SHANG', 'PC-SU': 'WU', 'PC-YI': 'YI',
}
SECONDARY_ALIASES = {'大顿': 'DA_DUN', '大頓': 'DA_DUN', '小住': 'XIAO_ZHU',
                     '丁住': 'DING_ZHU', '大住': 'DA_ZHU', '折': 'ZHE', '拽': 'YE'}
ABSENT = {'', 'NONE', 'NULL', 'NONE-OBSERVED', 'ABSENT', 'NO-SIGN'}
UNRESOLVED = {'UNKNOWN', 'UNRESOLVED', 'SOURCE-GLYPH', 'SOURCE-MARK-OR-NONE'}


def lname(tag):
    return tag.rsplit('}', 1)[-1]


def attr(node, *names, default=''):
    if node is None:
        return default
    for name in names:
        if name in node.attrib:
            return node.attrib[name]
        found = next((v for k, v in node.attrib.items() if lname(k) == name), None)
        if found is not None:
            return found
    return default


def first_desc(node, name):
    return None if node is None else next((n for n in node.iter() if lname(n.tag) == name), None)


def text_of(node):
    if node is None:
        return ''
    if lname(node.tag) == 'choice':
        original = first_desc(node, 'orig')
        if original is not None:
            return text_of(original)
    chunks = [node.text or '']
    for child in node:
        if lname(child.tag) != 'reg' or not any(lname(n.tag) == 'orig' for n in node):
            chunks.append(text_of(child))
        chunks.append(child.tail or '')
    return ''.join(chunks).strip()


def compact(text):
    return ''.join(text.split())


def category(value, secondary=False, declared=None):
    raw = value.strip()
    upper = raw.upper().replace(' ', '_')
    if upper in ABSENT:
        return None
    if upper in UNRESOLVED:
        return '__UNRESOLVED__'
    if upper in (SECONDARY if secondary else PRIMARY):
        return upper
    if declared and raw.removeprefix('#') in declared:
        return declared[raw.removeprefix('#')]
    aliases = SECONDARY_ALIASES if secondary else PRIMARY_ALIASES
    candidate = raw.removesuffix('形')
    return aliases.get(candidate, aliases.get(candidate.upper(), '__UNRESOLVED__'))


def number(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def box_from_zone(zone):
    if zone is None:
        return None
    try:
        return [int(float(zone.get(k, ''))) for k in ('ulx', 'uly', 'lrx', 'lry')]
    except (ValueError, OverflowError):
        return None


def truthy(value):
    return value.strip().lower() in {'true', '1', 'yes', 'excluded', 'cancelled', 'canceled', 'deleted'}


def _ancestors(node, parents):
    while node in parents:
        node = parents[node]
        yield node


def parse_mei(path, workspace_root=None):
    root = ET.parse(path).getroot()
    if root.tag != '{' + MEI + '}mei':
        raise ValueError('root must be mei in the MEI namespace')
    parent = {child: node for node in root.iter() for child in node}
    all_nodes = list(root.iter())
    declared_classes = [{}, {}]
    for definition in all_nodes:
        if lname(definition.tag) != 'category' or not definition.get(XML_ID):
            continue
        for secondary, types in ((False, PRIMARY), (True, SECONDARY)):
            kind = 'suzipu-secondary-class' if secondary else 'suzipu-primary-class'
            terms = [attr(definition, 'label')] + [text_of(n) for n in definition.iter() if n.get('type') == kind]
            values = {category(value, secondary) for value in terms if value and category(value, secondary) in types}
            if len(values) == 1 and (definition.get('type') == kind or any(n.get('type') == kind for n in definition.iter())):
                declared_classes[int(secondary)][definition.get(XML_ID)] = values.pop()
    ids = [n.get(XML_ID) for n in all_nodes if n.get(XML_ID)]
    id_counts = Counter(ids)
    by_id = {n.get(XML_ID): n for n in all_nodes if n.get(XML_ID)}
    duplicates = sorted(k for k, count in id_counts.items() if count > 1)
    facs_refs = [ref for n in all_nodes for ref in n.get('facs', '').split()]
    broken_refs = [ref for ref in facs_refs if not ref.startswith('#') or ref[1:] not in by_id]
    closure = 0.0 if duplicates else (1 - len(broken_refs) / max(len(facs_refs), 1))
    forbidden_elements = {'meterSig', 'meterSigGrp', 'tempo', 'midi', 'perfRes', 'scoreTempo'}
    forbidden_attributes = {'dur', 'dur.ges', 'pname', 'oct', 'pnum', 'midi.pitch',
                            'meter.count', 'meter.unit', 'metcon', 'bpm', 'mm', 'mm.unit'}
    modern_fields = {'modern-meter', 'absolute-pitch', 'note-duration', 'duration-ms'}
    unasserted = {'', 'none', 'null', 'unknown', 'unresolved', 'unsupported',
                 'rejected', 'not-determined', 'not-applicable', 'not-inferred'}
    def semantic_key(value):
        return lname(value).lower().removeprefix('data-').replace('_', '-')
    invented = [{'element': lname(n.tag), 'attributes': sorted(k for k in n.attrib
                if lname(k) in forbidden_attributes)} for n in all_nodes
                if lname(n.tag) in forbidden_elements or any(lname(k) in forbidden_attributes for k in n.attrib)]
    # Explicit modern values also violate the contract when carried in legal extension fields.
    for node in all_nodes:
        attributes = [key for key, value in node.attrib.items() if semantic_key(key) in modern_fields
                      and value.strip().lower().replace(' ', '-') not in unasserted]
        typed = (lname(node.tag) == 'annot' and semantic_key(node.get('type', '')) in modern_fields
                 and text_of(node).strip().lower().replace(' ', '-') not in unasserted
                 and (attr(node, 'status') or '').strip().lower() not in unasserted - {''})
        if attributes or typed:
            invented.append({'element': lname(node.tag), 'attributes': attributes,
                             'typed_modern_claim': node.get('type') if typed else None})
    zones, surfaces = {}, []
    for surface in (n for n in all_nodes if lname(n.tag) == 'surface'):
        page = number(surface.get('n', '')) or len(surfaces) + 1
        graphic = first_desc(surface, 'graphic')
        target = '' if graphic is None else graphic.get('target', '')
        target_valid = False
        if workspace_root is not None and target and '://' not in target:
            target_path = Path(target)
            if target_path.is_absolute():
                try:
                    target_path = workspace_root / target_path.relative_to('/workspace')
                except ValueError:
                    target_path = None
            else:
                target_path = workspace_root / 'output' / target_path
            if target_path is not None:
                resolved = target_path.resolve()
                if resolved.is_relative_to(workspace_root.resolve()) and resolved.is_file():
                    target_valid = hashlib.sha256(resolved.read_bytes()).hexdigest() == SOURCE_SCAN_SHA256.get(page)
        surfaces.append({'page': page, 'target': target, 'target_valid': target_valid})
        for zone in (n for n in surface.iter() if lname(n.tag) == 'zone'):
            zone_id = zone.get(XML_ID)
            if zone_id:
                zones[zone_id] = {'page': page, 'box': box_from_zone(zone), 'type': zone.get('type', '')}

    def zone_refs(node):
        return [(ref[1:], zones[ref[1:]]) for ref in node.get('facs', '').split()
                if ref.startswith('#') and ref[1:] in zones]

    def ancestor_value(node, *names):
        while node is not None:
            value = attr(node, *names)
            if value:
                return value
            node = parent.get(node)
        return ''

    def zone_for(node, role):
        preferred, other = [], []
        for item in node.iter():
            name, kind = lname(item.tag), item.get('type', '').lower()
            refs = zone_refs(item)
            is_text = name == 'syl' or kind in {'lyric', 'lyric-character', 'text'}
            is_note = name in {'nc', 'note'} or kind in {'suzipu', 'notation', 'suzipu-pitch'}
            if (role == 'text' and is_text) or (role == 'notation' and is_note):
                preferred += refs
            other += refs
        if preferred:
            return preferred[0][1]
        words = ('text', 'lyric') if role == 'text' else ('note', 'notation', 'sign', 'suzipu')
        match = next((z for _, z in other if any(word in z['type'].lower() for word in words)), None)
        if match is not None:
            return match
        refs = zone_refs(node)
        if refs:
            return refs[0 if role == 'text' else min(1, len(refs) - 1)][1]
        return None

    title_stmt = first_desc(root, 'titleStmt')
    titles = [n for n in (title_stmt.iter() if title_stmt is not None else []) if lname(n.tag) == 'title']
    title_node = next((n for n in titles if n.get('type', '').lower() not in {'source', 'source-title', 'collection'}), None)
    composer_nodes = [n for n in all_nodes if lname(n.tag) == 'composer' or
                      lname(n.tag) == 'persName' and attr(n, 'role').lower() in
                      {'composer', 'attributed-author', 'attributedcreator', 'author'}]
    if not composer_nodes and title_stmt is not None:
        composer_nodes = [n for n in title_stmt.iter() if lname(n.tag) == 'persName']
    candidates = []
    for node in all_nodes:
        name, kind = lname(node.tag), node.get('type', '')
        if name == 'syllable' or name in {'note', 'symbol', 'annot'} and (
            kind in {'suzipu', 'suzipu-position', 'suzipu-event'} or attr(node, 'primary', 'data-pitch')):
            candidates.append(node)
    candidate_set = set(candidates)
    candidates = [n for n in candidates if not any(a in candidate_set for a in _ancestors(n, parent))]
    events = []
    for index, node in enumerate(candidates):
        syl = first_desc(node, 'syl')
        if syl is None:
            syl = next((n for n in node.iter() if n.get('type') == 'lyric'), None)
        lyric = text_of(syl) if syl is not None else attr(node, 'lyric', 'data-text')
        nc = first_desc(node, 'nc')
        primary = attr(nc, 'label', 'data-primary-class', 'data-pitch') if nc is not None else attr(node, 'primary', 'data-primary-class', 'data-pitch')
        if not primary:
            sign = next((n for n in node.iter() if n.get('type') == 'suzipu' and n.get('subtype', 'primary') == 'primary'), None)
            primary = text_of(sign)
        secondary_node = next((n for n in node.iter() if n.get('type') in {'secondary-sign', 'suzipu-secondary'}), None)
        secondary = attr(node, 'secondary', 'data-secondary')
        if secondary_node is not None:
            secondary = attr(secondary_node, 'data-class', 'label', 'subtype') or text_of(secondary_node)
        primary_status = attr(nc, 'data-primary-status', 'primary-status') or attr(node, 'data-primary-status', 'primary-status')
        secondary_status = attr(secondary_node, 'data-secondary-status', 'secondary-status') or attr(nc, 'data-secondary-status', 'secondary-status') or attr(node, 'data-secondary-status', 'secondary-status')
        primary_class = '__UNRESOLVED__' if primary_status.upper() in UNRESOLVED else category(primary, declared=declared_classes[0])
        secondary_class = '__UNRESOLVED__' if secondary_status.upper() in UNRESOLVED else category(secondary, True, declared_classes[1])
        text_zone, note_zone = zone_for(node, 'text'), zone_for(node, 'notation')
        page = (text_zone or note_zone or {}).get('page') or number(ancestor_value(node, 'page', 'data-page'))
        declared_page = number(ancestor_value(node, 'page', 'data-page'))
        column = ancestor_value(node, 'column', 'data-column', 'scoreColumn', 'pageColumn')
        explicit_end = attr(node, 'data-line-break', 'data-column-end', 'column-end', 'line_break')
        excluded = node.get('type') == 'excluded' or any(truthy(attr(node, key)) for key in
                   ('data-excluded', 'data-cancelled', 'cancelled', 'status', 'data-status'))
        source_status = attr(node, 'data-source-status', 'source-status', 'data-status', 'status') or attr(nc, 'data-source-status', 'source-status', 'data-status', 'status')
        if source_status.upper() in UNRESOLVED:
            excluded = None
        elif truthy(source_status):
            excluded = True
        events.append({'text': compact(lyric), 'pitch': primary_class, 'secondary': secondary_class,
            'primary_status':primary_status,'secondary_status':secondary_status,
            'excluded': excluded, 'line_break': truthy(explicit_end) if explicit_end else None,
            'page': page, 'text_box': (text_zone or {}).get('box'),
            'text_page': (text_zone or {}).get('page'), 'notation_page': (note_zone or {}).get('page'),
            'notation_box': (note_zone or {}).get('box'), '_n': number(node.get('n', '')),
            '_index': index, '_column': column, '_explicit_end': bool(explicit_end),
            '_position': number(attr(node, 'positionInColumn', 'columnPos', 'row', 'data-column-position', 'position')),
            'page_consistent': declared_page is None or page is None or declared_page == page})
    seq = [e['_n'] for e in events]
    if events and all(n is not None for n in seq) and len(set(seq)) == len(seq):
        events.sort(key=lambda e: e['_n'])
    elif events and all(e['page'] is not None and e['_column'] and e['_position'] is not None for e in events):
        def col_number(value):
            match = re.search(r'(\d+)$', value)
            return int(match.group(1)) if match else value
        events.sort(key=lambda e: (e['page'], str(col_number(e['_column'])).zfill(8), e['_position']))
    for i, event in enumerate(events):
        if event['line_break'] is None:
            next_event = events[i + 1] if i + 1 < len(events) else None
            if event['_column']:
                event['line_break'] = next_event is None or (event['page'], event['_column']) != (next_event['page'], next_event['_column'])
            else:
                original = candidates[event['_index']]
                siblings = list(parent.get(original, []))
                following = siblings[siblings.index(original) + 1:] if original in siblings else []
                event['line_break'] = bool(following and lname(following[0].tag) == 'cb')
    metadata, seen_metadata = [], set()
    kinds = {'title': 'title', 'work-title': 'title', 'mode': 'mode', 'mode-heading': 'mode',
             'preface': 'preface', 'prose-preface': 'preface', 'preface-column': 'preface',
             'attribution': 'attribution'}
    for node in all_nodes:
        if lname(node.tag) not in {'annot', 'seg', 'p', 'head', 'div', 'title', 'composer', 'persName'}:
            continue
        kind = kinds.get(node.get('type', ''))
        if kind is None and node in composer_nodes:
            kind = 'attribution'
        if kind is None and node is title_node:
            kind = 'title'
        if kind is None and node.get('type') == 'source-column' and any(a.get('type') in {'prose-preface', 'preface'} for a in _ancestors(node, parent)):
            kind = 'preface'
        if kind is None or any(kinds.get(a.get('type', '')) == kind for a in _ancestors(node, parent)):
            continue
        content = compact(text_of(node))
        identity = (kind, content, node.get('facs', ''), node.get('n', ''))
        if identity in seen_metadata:
            continue
        seen_metadata.add(identity)
        refs = zone_refs(node)
        metadata.append({'type': kind, 'text': content, 'page': refs[0][1]['page'] if refs else None,
                         'box': refs[0][1]['box'] if refs else None, 'regions': [z for _, z in refs],
                         '_n': number(node.get('n', ''))})
    for kind in {'title', 'mode', 'preface', 'attribution'}:
        entries = [m for m in metadata if m['type'] == kind]
        if len(entries) > 1 and all(e['_n'] is not None for e in entries) and len({e['_n'] for e in entries}) == len(entries):
            ordered = iter(sorted(entries, key=lambda e: e['_n']))
            metadata = [next(ordered) if m['type'] == kind else m for m in metadata]
    mode_texts = [m['text'] for m in metadata if m['type'] == 'mode']
    if mode_texts and all(len(value) == 1 for value in mode_texts):
        mode_texts = [''.join(mode_texts)]
    if not mode_texts:
        mode_texts = [compact(text_of(n)) for n in all_nodes if lname(n.tag) == 'term' and n.get('type') in {'mode', 'mode-heading'}]
        mode_texts += [attr(n, 'data-mode') for n in all_nodes if attr(n, 'data-mode')]
    return {'title': compact(text_of(title_node)), 'composer': [compact(text_of(n)) for n in composer_nodes],
            'mode': mode_texts, 'metadata': metadata, 'events': events, 'surfaces': surfaces,
            'closure': closure, 'duplicate_ids': duplicates, 'broken_refs': broken_refs,
            'invented_semantics': invented, 'reference_count': len(facs_refs)}

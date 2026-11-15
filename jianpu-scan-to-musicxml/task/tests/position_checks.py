"""Source-linked music-position relationships required by instruction.md."""

def harmonic(correct, expected, actual):
    return 2 * correct / max(expected + actual, 1)


def intended_positions(expected, actual):
    """Align the declared lyric sequence, never infer its identity from a wrong crop."""
    variants=str.maketrans({'黄':'黃','爲':'為','荳':'豆'})
    rows,cols=len(expected),len(actual)
    scores=[[0.0]*(cols+1) for _ in range(rows+1)]
    moves=[['']*(cols+1) for _ in range(rows+1)]
    for i in range(1,rows+1):scores[i][0]=-1.2*i;moves[i][0]='up'
    for j in range(1,cols+1):scores[0][j]=-1.2*j;moves[0][j]='left'
    for i in range(1,rows+1):
        for j in range(1,cols+1):
            same=expected[i-1]['text'].translate(variants)==actual[j-1]['text'].translate(variants)
            options=[(scores[i-1][j-1]+(3 if same else -.5),'diag'),(scores[i-1][j]-1.2,'up'),(scores[i][j-1]-1.2,'left')]
            scores[i][j],moves[i][j]=max(options,key=lambda value:value[0])
    result={};i,j=rows,cols
    while i or j:
        move=moves[i][j]
        if move=='diag':result[j-1]=i-1;i-=1;j-=1
        elif move=='up':i-=1
        else:j-=1
    return result


def same_lyric_identity(left, right):
    # Identity aliases do not waive the separate diplomatic-character fidelity check.
    variants=str.maketrans({'黄':'黃','爲':'為','荳':'豆'})
    return left.translate(variants)==right.translate(variants)


def overlap(left, right):
    if left is None or right is None:
        return 0.0
    intersection = max(0, min(left[2], right[2]) - max(left[0], right[0])) * max(0, min(left[3], right[3]) - max(left[1], right[1]))
    a = max(0, left[2] - left[0]) * max(0, left[3] - left[1])
    b = max(0, right[2] - right[0]) * max(0, right[3] - right[1])
    return intersection / (a + b - intersection) if a + b > intersection else 0.0


def owner(event, expected, kind):
    page = event.get('text_page' if kind == 'text_box' else 'notation_page')
    scores = [(overlap(event.get(kind), e.get(kind)), i) for i, e in enumerate(expected) if e['page'] == page]
    scores.sort(reverse=True)
    if not scores or scores[0][0] <= 0 or len(scores) > 1 and abs(scores[0][0] - scores[1][0]) < 1e-9:
        return None
    return scores[0][1]


def region_coverage(candidate, source, ink_runs=None):
    if candidate is None or source is None:
        return 0.0
    if ink_runs:
        support = sum(end-start for _,start,end in ink_runs)
        covered = sum(max(0,min(candidate[2],end)-max(candidate[0],start)) for y,start,end in ink_runs
                      if candidate[1] <= y < candidate[3])
        return covered / support
    area = max(0, source[2] - source[0]) * max(0, source[3] - source[1])
    intersection = max(0, min(candidate[2], source[2]) - max(candidate[0], source[0])) * max(0, min(candidate[3], source[3]) - max(candidate[1], source[1]))
    return intersection / area if area else 0.0


def evaluate_positions(expected, actual):
    records = []
    linked, joint = set(), {}
    declared=intended_positions(expected,actual)
    for index, event in enumerate(actual):
        text_owner = owner(event, expected, 'text_box')
        notation_owner = owner(event, expected, 'notation_box')
        intended=declared.get(index)
        lyric_matches=intended is not None and same_lyric_identity(event['text'],expected[intended]['text'])
        paired = lyric_matches and text_owner == notation_owner == intended and event.get('page_consistent', True)
        all_fields = False
        if paired:
            source = expected[text_owner]
            linked.add(text_owner)
            fields = ('text', 'pitch', 'secondary', 'excluded', 'page')
            if text_owner < len(expected)-1:
                fields += ('line_break',)
            all_fields = all(event.get(key) == source.get(key) for key in fields)
            if all_fields:
                quality = min(region_coverage(event.get('text_box'), source.get('text_box'), source.get('text_ink_runs')),
                              region_coverage(event.get('notation_box'), source.get('notation_box'), source.get('notation_ink_runs')))
                joint[text_owner] = max(joint.get(text_owner, 0), quality)
        records.append({'event': index, 'text_source_position': text_owner,
                        'intended_source_position':intended,
                        'notation_source_position': notation_owner, 'same_source_position': paired,
                        'all_position_fields_correct': all_fields})
    transitions = sum(a['text_source_position'] is not None and b['text_source_position'] is not None and
                      b['text_source_position'] > a['text_source_position'] for a,b in zip(records,records[1:]))
    return {'source_pairing_integrity': harmonic(len(linked), len(expected), len(actual)),
            'joint_position_fidelity': harmonic(sum(joint.values()), len(expected), len(actual)),
            'physical_source_order': transitions / max(len(expected) - 1, len(actual) - 1, 1)}, records


def source_geometry(expected, actual, records):
    scores = {}
    for kind in ('text_box', 'notation_box'):
        by_source = {}
        for event, record in zip(actual, records):
            index = record['text_source_position' if kind == 'text_box' else 'notation_source_position']
            if index is not None and index==record['intended_source_position'] and same_lyric_identity(event['text'],expected[index]['text']):
                quality = region_coverage(event.get(kind), expected[index].get(kind),
                                          expected[index].get(kind.removesuffix('_box') + '_ink_runs'))
                by_source[index] = max(by_source.get(index, 0), quality)
        scores[kind] = sum(by_source.values()) / max(len(expected), len(actual), 1)
    return scores


def metadata_grounding(expected, actual):
    """Optional source-location diagnosis; metadata facsimiles are not a scoring requirement."""
    results = {}
    for kind in ('title', 'attribution', 'mode', 'preface'):
        ref = [(character, item) for item in expected if item['type'] == kind and item.get('regions') for character in item['text']]
        got = [(character, item) for item in actual if item['type'] == kind and item.get('regions') for character in item['text']]
        previous = [0] * (len(got) + 1)
        for character, target in ref:
            box = target.get('box')
            center = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2) if box else None
            current = [0]
            for j, (observed, entry) in enumerate(got):
                grounded = center is not None and any(region['page'] == target['page'] and region.get('box') and
                           region['box'][0] <= center[0] <= region['box'][2] and region['box'][1] <= center[1] <= region['box'][3] for region in entry['regions'])
                current.append(previous[j] + 1 if character == observed and grounded else max(previous[j+1], current[-1]))
            previous = current
        results[kind] = harmonic(previous[-1], len(ref), len(got)) if ref else None
    return results


def fine_features(expected, actual, groups, atoms):
    records = atoms['position_bindings']
    result = {}
    for field in ('pitch', 'secondary'):
        for value in sorted({e[field] for e in expected}, key=str):
            correct = {r['intended_source_position'] for r,e in zip(records,actual)
                       if r['intended_source_position'] is not None and e[field] == value and
                       expected[r['intended_source_position']][field] == value}
            result[field + '_' + ('ABSENT' if value is None else value)] = harmonic(len(correct),
                sum(e[field] == value for e in expected), sum(e[field] == value for e in actual))
    pages = sorted({e['page'] for e in expected})
    for page in pages:
        count = sum(e['page'] == page for e in expected)
        actual_rows = [(e,r) for e,r in zip(actual,records) if e.get('text_page') == page]
        page_correct = {r['text_source_position'] for e,r in actual_rows
                        if r['text_source_position'] is not None and e.get('page_consistent',True)}
        lyric_correct = {r['text_source_position'] for e,r in actual_rows if r['text_source_position'] is not None and
                         e['text'] == expected[r['text_source_position']]['text']}
        paired = {r['text_source_position'] for e,r in actual_rows if r['same_source_position']}
        result['page_'+str(page)] = harmonic(len(page_correct),count,len(actual_rows))
        result['lyric_binding_page_'+str(page)] = harmonic(len(lyric_correct),count,len(actual_rows))
        result['source_pairing_page_'+str(page)] = harmonic(len(paired),count,len(actual_rows))
        ordering = [r['text_source_position'] for e,r in actual_rows]
        transitions = sum(a is not None and b is not None and b>a for a,b in zip(ordering,ordering[1:]))
        result['physical_order_page_'+str(page)] = transitions / max(count-1,len(ordering)-1,1)
    observed = []
    for event in actual:
        page = event.get('text_page')
        if not observed or observed[-1] != page:
            observed.append(page)
    result['source_page_continuation'] = float(observed == pages)
    result.update({key:groups[key] for key in ('header_context','source_images','referential_closure','atemporal_fidelity','joint_position_fidelity')})
    result.update({'column_endings':atoms['line_break_f1'],
                   'prose_order':atoms['metadata_f1']})
    result.update({kind+'_geometry':value for kind,value in atoms['source_region_quality'].items()})
    return result


def compact_features(expected, actual, groups, atoms):
    fine = fine_features(expected, actual, groups, atoms)
    mean = lambda values: sum(values) / max(len(values), 1)
    counts = {value:sum(e['pitch']==value for e in expected) for value in {e['pitch'] for e in expected}}
    values = lambda types: [fine['pitch_'+('ABSENT' if value is None else value)] for value in types]
    result = {
        'metadata_content':mean([groups['header_context'],atoms['metadata_f1']]),
        'primary_common_classes':mean(values([v for v,c in counts.items() if c>3])),
        'primary_rare_and_absent_classes':mean(values([v for v,c in counts.items() if c<=3])),
        'secondary_absence':fine['secondary_ABSENT'],
        'secondary_residence_marks':mean([fine['secondary_'+v] for v in ('DA_DUN','DA_ZHU','DING_ZHU','XIAO_ZHU')]),
        'secondary_fold':fine['secondary_ZHE'], 'secondary_drag':fine['secondary_YE'],
        'physical_boundaries':mean([fine['page_1'],fine['page_2'],fine['column_endings']]),
        'physical_reading_order':groups['physical_source_order'],
        'joint_position_fidelity':groups['joint_position_fidelity'],
        'source_region_quality':groups['facsimile_geometry'],
        'document_contract':mean([groups[k] for k in ('source_images','referential_closure','atemporal_fidelity')]),
    }
    source_columns=[]
    current=[]
    for i,event in enumerate(expected):
        current.append(i)
        if event['line_break'] or i==len(expected)-1:
            source_columns.append(current)
            current=[]
    records=atoms['position_bindings']
    for column_number,column in enumerate(source_columns,1):
        relevant=[r for r in records if r['intended_source_position'] in column]
        correct={r['text_source_position'] for r in relevant if r['same_source_position']}
        result['source_pairing_column_'+str(column_number)] = harmonic(len(correct),len(column),len(relevant))
    return result

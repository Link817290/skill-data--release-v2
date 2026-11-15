"""Complete source-position abilities, without rare-class selection or reward gates."""
from position_checks import intended_positions, region_coverage, harmonic, same_lyric_identity


def content_features(expected, actual, groups, atoms, valid_pages):
    declared=intended_positions(expected,actual)
    count=max(len(expected),len(actual),1)
    primary=sum(expected[i]['pitch']==actual[j]['pitch'] for j,i in declared.items())/count
    lyrics=sum(expected[i]['text']==actual[j]['text'] for j,i in declared.items())/count
    secondary={i:False for i in range(len(expected))}
    for j,i in declared.items():secondary[i] |= expected[i]['secondary']==actual[j]['secondary']
    real={e['secondary'] for e in expected if e['secondary'] is not None}
    sign_scores=[sum(secondary[i] for i,e in enumerate(expected) if e['secondary']==kind)/
                 sum(e['secondary']==kind for e in expected) for kind in sorted(real)]
    absent=[i for i,e in enumerate(expected) if e['secondary'] is None]
    absent_score=sum(secondary[i] for i in absent)/len(absent)
    joint={};paired=set();geometry={'text_box':{},'notation_box':{}}
    for e,r in zip(actual,atoms['position_bindings']):
        i=r['intended_source_position']
        if i is None or expected[i]['page'] not in valid_pages:continue
        if r['same_source_position']:paired.add(i)
        for kind in geometry:
            index=r['text_source_position' if kind=='text_box' else 'notation_source_position']
            if index==i and same_lyric_identity(e['text'],expected[i]['text']):
                quality=region_coverage(e.get(kind),expected[i].get(kind),expected[i].get(kind.removesuffix('_box')+'_ink_runs'))
                geometry[kind][i]=max(geometry[kind].get(i,0),quality)
        source=expected[i]
        components=[
            float(same_lyric_identity(e.get('text',''),source.get('text',''))),
            float(e.get('excluded')==source.get('excluded')),
            float(e.get('page')==source.get('page') and e.get('page_consistent',True)),
            float(r['same_source_position']),
            float(e.get('pitch') == source.get('pitch')),
            float(e.get('secondary') == source.get('secondary')),
            sum(region_coverage(e.get(kind),source.get(kind),source.get(kind.removesuffix('_box')+'_ink_runs'))
                for kind in ('text_box','notation_box'))/2,
        ]
        if i < len(expected)-1:
            components.append(float(e.get('line_break')==source.get('line_break')))
        joint[i]=max(joint.get(i,0),sum(components)/len(components))
    bare=[i for i,e in enumerate(expected) if e['secondary'] is None]
    compound=[i for i,e in enumerate(expected) if e['secondary'] is not None]
    return {
        'metadata_content':(groups['header_context']+atoms['metadata_f1'])/2,
        'sung_text_fidelity':lyrics,
        'primary_source_fidelity':primary,
        'real_secondary_classes':sum(sign_scores)/len(sign_scores),
        'secondary_absence':absent_score,
        'bare_position_fidelity':sum(joint.get(i,0) for i in bare)/len(bare),
        'compound_position_fidelity':sum(joint.get(i,0) for i in compound)/len(compound),
        'physical_boundaries':groups['boundary_decisions'],
        'source_region_quality':sum(sum(v.values()) for v in geometry.values())/(2*count),
        'source_pairing_integrity':harmonic(len(paired),len(expected),len(actual)),
        'physical_reading_order':groups['physical_source_order'],
        'document_contract':(groups['source_images']+groups['referential_closure']+groups['atemporal_fidelity'])/3,
    }

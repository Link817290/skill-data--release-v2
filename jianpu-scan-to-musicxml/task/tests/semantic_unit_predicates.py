"""Exact source-linked units complement semantic class recognition."""
import json
from pathlib import Path
from position_checks import intended_positions, same_lyric_identity, owner, region_coverage
from scoreio import PRIMARY, SECONDARY


def unit_checks(context):
    truth=json.loads((Path(__file__).parent/'ground_truth.json').read_text())['mei']['events']
    actual=context['candidate']['facts']['positions']
    declared=intended_positions(truth,actual)
    by_source={}
    for j,i in declared.items():
        if same_lyric_identity(actual[j]['text'],truth[i]['text']):
            by_source.setdefault(i,[]).append(actual[j])
    valid_pages={s['page'] for s in context['candidate']['facts']['surfaces'] if s['target_valid']}
    columns=context['golden']['source_census']['music_columns']
    checks={}
    for field,classes,prefix in (('pitch',PRIMARY,'primary'),('secondary',SECONDARY,'secondary')):
        for category in sorted({e[field] for e in truth},key=str):
            indices=[i for i,e in enumerate(truth) if e[field]==category]
            declarations=[e[field] for i in indices for e in by_source.get(i,[])]
            known=all(value in classes or value is None or value=='__UNRESOLVED__' for value in declarations)
            if not known:
                continue
            correct=sum(any(e[field]==category for e in by_source.get(i,[])) for i in indices)
            identifier=prefix+'_'+('absence' if category is None else category.lower())
            checks[identifier]={'completion':correct/len(indices),'correct_units':correct,'expected_units':len(indices),
              'method':'All declarations in this source class scope have unambiguous relative-class or explicit unresolved meanings. Exact source-associated units replace model counting estimates; specific unmapped visual labels remain for semantic review.'}
    for c,indices in enumerate(columns,1):
        declarations=[e for i in indices for e in by_source.get(i,[])]
        if all((e['pitch'] in PRIMARY or e['pitch']=='__UNRESOLVED__') and
               (e['secondary'] in SECONDARY or e['secondary'] in (None,'__UNRESOLVED__')) for e in declarations):
            correct=sum(any(all(e[field]==truth[i][field] for field in ('text','pitch','secondary','excluded','page')) and
                            (i==len(truth)-1 or e['line_break']==truth[i]['line_break']) for e in by_source.get(i,[])) for i in indices)
            checks['joint_column_'+str(c)]={'completion':correct/len(indices),'correct_units':correct,'expected_units':len(indices),
              'method':'Joint source positions whose declared lyric, relative primary/secondary, inclusion and physical boundaries all agree; only applied when no specific unmapped class interpretation remains'}
    for c,indices in enumerate(columns,1):
        correct=sum(any(e['text']==truth[i]['text'] for e in by_source.get(i,[])) for i in indices)
        checks['text_column_'+str(c)]={'completion':correct/len(indices),'correct_units':correct,
          'expected_units':len(indices),'method':'Complete declared reading sequence aligned to source; printed-character fidelity remains exact independently of source-identity aliases'}
    prose=context['golden']['source_census'].get('preface_columns',[])
    if prose:
        source=[{'text':char,'column':c} for c,p in enumerate(prose,1) for char in p['text']]
        delivered=[{'text':char} for m in context['candidate']['facts']['metadata'] if m['type']=='preface'
                   for text in m['complete_texts'] for char in text]
        aligned=intended_positions(source,delivered)
        exact={i for j,i in aligned.items() if delivered[j]['text']==source[i]['text']}
        for c,p in enumerate(prose,1):
            correct=sum(i in exact for i,s in enumerate(source) if s['column']==c)
            checks['preface_column_'+str(c)]={'completion':correct/len(p['text']),'correct_units':correct,
              'expected_units':len(p['text']),'method':'Source prose characters in actual reading sequence, independent of XML paragraph/column grouping'}
    for page in (1,2):
        indices=[i for i,e in enumerate(truth) if e['page']==page]
        correct=0
        for i in indices:
            correct+=any(e['page']==page and (i==len(truth)-1 or e['line_break']==truth[i]['line_break'])
                         for e in by_source.get(i,[]))
        checks['boundary_page_'+str(page)]={'completion':correct/len(indices),'correct_units':correct,
                                           'expected_units':len(indices),'method':'source-aligned page and real transition; final EOF marker is optional'}
    for c,indices in enumerate(columns,1):
        earned=0.0
        for i in indices:
            for kind in ('text_box','notation_box'):
                quality=[]
                for e in by_source.get(i,[]):
                    role_page=e['text_page' if kind=='text_box' else 'notation_page']
                    if role_page in valid_pages and owner(e,truth,kind)==i:
                        quality.append(region_coverage(e.get(kind),truth[i].get(kind),truth[i].get(kind.removesuffix('_box')+'_ink_runs')))
                earned+=max(quality,default=0.0)
        checks['facs_column_'+str(c)]={'completion':earned/(2*len(indices)),
          'correct_units':earned,'expected_units':2*len(indices),
          'method':'each declared-position text and notation region earns visible source-ink coverage independently; renamed/tight/padded regions accepted'}
    return checks

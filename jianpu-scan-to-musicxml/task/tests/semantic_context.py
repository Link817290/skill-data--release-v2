"""Private, condition-blind domain evidence for the shared semantic judge."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from scoreio import parse_mei, lname, compact, text_of, attr
from validator import score

HERE=Path(__file__).resolve().parent
TASK=HERE.parent
PACKAGE_ROOT=HERE.parents[1]


def source_facts(path, workspace, compact_metadata=False):
    data=parse_mei(path,workspace)
    event_keys=('text','pitch','secondary','primary_status','secondary_status','excluded','line_break','page','text_page','notation_page','text_box','notation_box','_n')
    facts={key:data[key] for key in ('title','composer','mode','metadata','surfaces','duplicate_ids','broken_refs','invented_semantics')}
    if compact_metadata:
        grouped=[]
        for kind in ('title','attribution','mode','preface'):
            entries=[entry for entry in facts['metadata'] if entry['type']==kind]
            if entries:
                text=''.join(entry['text'] for entry in entries)
                if kind in ('title','attribution','mode'):
                    unique=list(dict.fromkeys(entry['text'] for entry in entries if len(entry['text'])>1))
                    char_text=''.join(entry['text'] for entry in entries if len(entry['text'])==1)
                    texts=list(dict.fromkeys(unique+([char_text] if char_text else [])))
                else:
                    texts=[text]
                grouped.append({'type':kind,'complete_texts':texts,
                                'source_regions':list({(entry['page'],tuple(entry['box'])) for entry in entries if entry.get('box')})})
        facts['metadata']=grouped
    facts['positions']=[{'position':i+1,**{key:e.get(key) for key in event_keys}} for i,e in enumerate(data['events'])]
    root=ET.parse(path).getroot()
    facts['encoding_declarations']=[{'element':lname(n.tag),'attributes':n.attrib,'xml':ET.tostring(n,encoding='unicode')}
                                   for n in root.iter() if lname(n.tag)=='encodingDesc']
    facts['structured_heading_terms']=[{'attributes':n.attrib,'text':compact(text_of(n))}
                                     for n in root.iter() if lname(n.tag)=='term']
    raw=[]
    for node in root.iter():
        name,kind=lname(node.tag),node.get('type','')
        if name=='syllable' or name in ('symbol','note','annot') and kind in ('suzipu-position','suzipu-event','suzipu'):
            raw.append({'element':name,'attributes':node.attrib,'content':compact(text_of(node)),
        'children':[{'element':lname(n.tag),'attributes':n.attrib,'text':compact(n.text or '')} for n in node.iter() if n is not node]})
    if compact_metadata:
        raw_by_n={record['attributes'].get('n'):record for record in raw if record['attributes'].get('n')}
        for position in facts['positions']:
            record=raw_by_n.get(str(position.get('_n'))) if position.get('_n') is not None else None
            if record is None and position['position']<=len(raw):
                record=raw[position['position']-1]
            if record is not None:
                attributes={lname(k):v for k,v in record['attributes'].items()}
                nc=next((n for n in record['children'] if n['element']=='nc'),None)
                second=next((n for n in record['children'] if n['attributes'].get('type') in ('secondary-sign','suzipu-secondary')),None)
                primary=attributes.get('primary',attributes.get('data-pitch',''))
                secondary=attributes.get('secondary',attributes.get('data-secondary',''))
                if nc:
                    nc_attributes={lname(k):v for k,v in nc['attributes'].items()}
                    primary=nc_attributes.get('label',nc_attributes.get('data-primary-class',nc_attributes.get('data-pitch',primary)))
                if second:
                    second_attributes={lname(k):v for k,v in second['attributes'].items()}
                    secondary=second_attributes.get('data-class',second_attributes.get('label',second_attributes.get('subtype',second['text'])))
                position['declared_primary']=primary
                position['declared_secondary']=secondary
                for normalized, declared in (('pitch', primary), ('secondary', secondary)):
                    if position.get(normalized) == '__UNRESOLVED__':
                        statuses={'UNKNOWN','UNRESOLVED','SOURCE-GLYPH','SOURCE-MARK-OR-NONE'}
                        status=position.get('primary_status' if normalized=='pitch' else 'secondary_status','')
                        explicit = declared.upper() in statuses or status.upper() in statuses
                        position[normalized+'_normalization_status'] = 'candidate-explicit-placeholder' if explicit else 'parser-unmapped-specific-declaration'
                        if not explicit:
                            position[normalized] = declared
        carriers={}
        for i,record in enumerate(raw):
            key=record['element']+'|'+','.join(sorted(record['attributes']))+'|'+','.join(sorted({n['element'] for n in record['children']}))
            if key not in carriers:
                carriers[key]={'positions':[],'example':record}
            carriers[key]['positions'].append(i+1)
        facts['semantic_carriers']=list(carriers.values())
        facts['encoding_policy']='Complete position facts below preserve every original semantic value; carriers explain the actual namespaces, field meanings and containment without repeating each serialized event.'
    else:
        facts['original_position_records']=raw
    facts['declared_class_vocabulary']=[{'attributes':n.attrib,'meaning':compact(text_of(n))} for n in root.iter() if lname(n.tag)=='category']
    return facts


def context(answer, workspace=None, compact_metadata=False):
    workspace=workspace or TASK/'environment/workspace'
    golden=PACKAGE_ROOT/'golden/揚州慢.mei'
    result=score(answer,HERE/'ground_truth.json',workspace)
    result_context = {
        'schema':'strict-golden-context-v1',
        'instruction':(TASK/'instruction.md').read_text(),
        'rubric':json.loads((HERE/'semantic_rubric.json').read_text()),
        'golden':{'facts':source_facts(golden,workspace,compact_metadata)},
        'candidate':{'facts':source_facts(answer,workspace,compact_metadata),'program_position_ledger':result['atoms']['position_bindings']},
        'images':[{'path':str((workspace/'materials'/f'source_page_{page:02d}.png').resolve()),
                   'label':f'Authoritative original scan, source page {page}', 'role':'source'} for page in (1,2)],
        'extra':{
            'evidence_policy':'Source scans are authoritative. Golden supplies source-bound reference semantics, not required XML syntax. If a reference assertion cannot be supported visually, disclose uncertainty; do not invent evidence or hidden source-specific requirements.',
            'non_requirements':['metadata facsimile links','modern meter/absolute pitch/duration','exact pixel boxes','particular XML element names, IDs, namespace prefixes, or storage order'],
            'source_grounding_policy':'Program ownership and diagnostics are evidence, not an instruction to copy program scores. Independently check associations and source glyphs. No model, condition or target-score information is supplied.'
            ,'normalization_policy':'A parser-unmapped-specific-declaration is NOT an unresolved candidate answer. Independently evaluate its original visual token and declared vocabulary against the source. Only candidate-explicit-placeholder establishes deliberate lack of recognition. Different shape aliases are valid if they consistently encode the same source class; do not require canonical names.'
        }
    }
    if compact_metadata:
        result_context['candidate']['program_position_ledger']={
            'columns':['event','text_source_position','notation_source_position','same_source_position','all_position_fields_correct'],
            'rows':[[r[k] for k in ('event','text_source_position','notation_source_position','same_source_position','all_position_fields_correct')]
                    for r in result['atoms']['position_bindings']]}
        evidence={}
        for role in ('golden','candidate'):
            facts=result_context[role]['facts']
            paths={key:'/'+role+'/facts/'+key for key in facts}
            paths['safe_all_positions']='/'+role+'/facts/positions'
            paths['valid_position_index_range']=[0,len(facts['positions'])-1]
            paths['metadata_by_role']={entry['type']:'/'+role+'/facts/metadata/'+str(i) for i,entry in enumerate(facts['metadata'])}
            evidence[role]=paths
        evidence['source_pages']=['/images/0','/images/1']
        evidence['program_binding_ledger']='/candidate/program_position_ledger'
        result_context['extra']['evidence_map']=evidence
        result_context['extra']['citation_rule']='Use the listed parent JSONPointer evidence paths; citing an entire positions array is valid. Only cite a numeric child index after verifying it exists. Metadata is grouped by role and has at most four entries, NOT a 78-character array. Never invent a metadata character index. Position index is zero-based while position field is one-based.'
    return result_context


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('answer',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workspace',type=Path)
    args=parser.parse_args()
    args.output.write_text(json.dumps(context(args.answer,args.workspace),ensure_ascii=False,indent=2)+'\n')

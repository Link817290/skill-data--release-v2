#!/usr/bin/env python3
"""Offline, condition-blind three-layer workbook Program Judge.

Only the submitted workbook and generated runtime contract are read. Golden and
solution files are never runtime dependencies. Every assertion and deduction emits
its decision and carrier locators so semantic audit can challenge the recognizers.
"""
from pathlib import Path
import hashlib
import json
import math
import os
import re
import sys
import unicodedata

from openpyxl import load_workbook

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from semantic_relations import semantic_check, sentences, affirmative, business_evidence, business_damage, wer_used
from source_bound_judge import evaluate as semantic_evaluate
ARTIFACT='LG_AKB76043105_Test_Case_List_EN.xlsx'
ALIASES={
 'id':['test id','case id','test case id','id','tc id','test no','test number'],
 'category':['test category','category','functional area','function','test area'],
 'objective':['test item name','test name','case name','objective','test objective','test case','test case name','title'],
 'steps':['test steps','steps','procedure','test procedure','actions','test actions','action sequence','procedure sequence','execution procedure','sequence of actions','method'],
 'preconditions':['preconditions','precondition','prerequisites','setup','test setup','initial conditions'],
 'expected':['expected results','expected result','expected','expected observations','expected behavior','expected behaviour'],
 'priority':['priority','risk priority','risk'],
 'acceptance':['pass criteria','acceptance criteria','acceptance condition','acceptance conditions','pass fail criteria','criteria'],
 'result':['test result','actual result','actual results','result','results'],
 'status':['test status','status','execution status'],
 'remarks':['remarks','notes','basis','evidence','assumptions and notes','source and notes','source reference']}
TOPICS={
 'pair':r'pair|registration|reconnect|deregister',
 'fallback':r'fallback|dual.mode|BT.*IR|Bluetooth.*IR|IR.*backup',
 'interference':r'interference|multi.device|cross.control|non.target',
 'power':r'power.{0,25}(?:cycle|recovery|restor)|battery.{0,25}(?:replacement|swap)|binding retention',
 'motion':r'(?:pointer|cursor).{0,25}(?:motion|movement|track|click)|motion.to.pointer',
 'sleep':r'sleep|hide|wake.*pointer|pointer.*wake',
 'wheel':r'wheel|scroll|inertia',
 'context':r'short.{0,25}long|Back.*Exit|press.*context|context.*matrix|navigation',
 'voice-latency':r'(?:voice|microphone|mic).{0,30}(?:latency|wake)|voice UI',
 'recognition':r'recognition|command.{0,30}accuracy|natural language|NLP|speech.{0,20}accuracy',
 'noise':r'noise|acoustic|quiet.*comparison',
 'universal':r'universal|learned IR|IR learning|CEC|external.{0,20}control',
 'bt-range':r'BT.{0,30}(?:range|distance|angle)|Bluetooth.{0,30}(?:range|distance|angle)|radio.{0,20}geometry',
 'ir-range':r'IR.{0,30}(?:range|distance|angle)|infrared.{0,30}(?:range|distance|angle)',
 'shortcut':r'shortcut|dedicated.{0,25}(?:app|service|button)|app.{0,20}launch'}
NON_ADOPTED=r'^(?:\s*[\d.)\-*]+\s*)?(?:do not\b|never\b|reject(?:ed)?\b|not adopted\b|candidate\b|possible option\b|consider\b|quoted\b|quotation\b|example only\b|hypothetical\b)'


def norm(value):
    text=unicodedata.normalize('NFKC',str(value or ''))
    text=re.sub('[\u2010-\u2015\u2212]','-',text)
    text=re.sub(r'\s+',' ',text).strip().lower()
    for pattern,replacement in [(r'\blog(?:ged|ging)?\b','record'),
                                (r'\bascertain\b','confirm'),
                                (r'\bcursor\b','pointer'),
                                (r'\btrials?\b','attempts'),
                                (r'\brecognis','recogniz')]:
        text=re.sub(pattern,replacement,text)
    return text


def heading(value):
    return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9 ]',' ',norm(value))).strip()


def header_role(value):
    label=heading(value)
    candidates=[role for role,aliases in ALIASES.items() if label in aliases]
    if len(candidates)==1:
        return candidates[0]
    if len(label.split())<=6:
        rules={'steps':r'^(?:(?:test|case|ordered|execution|operating|operational) )?(?:action|procedure|step|operation)s?(?: (?:sequence|instructions|description))?$',
               'expected':r'^(?:expected|anticipated) (?:outcome|observation|response|result)s?$',
               'preconditions':r'^(?:shared |case |test )?(?:setup|prerequisites|preconditions)(?: references?)?$',
               'acceptance':r'^(?:acceptance|pass fail|pass) (?:conditions?|criteria|requirements?)$'}
        found=[role for role,pattern in rules.items() if re.fullmatch(pattern,label)]
        if len(found)==1: return found[0]
    return None


def adopted(text, constraints=False):
    """Remove explicitly non-adopted sentences; ordinary negative outcomes remain."""
    # A quotation/candidate/rejection label governs its original sentence,
    # including coordinated clauses. Local prohibitions govern their own
    # semicolon-delimited action; a later affirmative instruction remains usable.
    original=re.split(r'\n|(?<=[.!?])\s+(?=[A-Za-z])',str(text or ''))
    scope_label=NON_ADOPTED.replace(r'do not\b|never\b|','')
    original=[p for p in original if not re.search(scope_label,p,re.I) and not re.search(r'\b(?:is|was|explicitly)\s+(?:rejected|not adopted|obsolete)\b',p,re.I)]
    parts=[p for sentence in original for p in re.split(r'(?<=;)\s+(?=[A-Za-z])',sentence)]
    exclusion=NON_ADOPTED if not constraints else NON_ADOPTED.replace(r'do not\b|never\b|','')
    # A local passive refusal is not an operative measurement. This filter
    # concerns steps, not expected negative outcomes or a separate global
    # declaration that prospective tests have not yet been executed.
    passive_refusal=r'\b(?:(?:is|are|was|were)\s+(?:explicitly\s+)?not\s+|will\s+not\s+be\s+)(?:performed|executed|undertaken|carried out)\b'
    return ' '.join(p for p in parts if not re.search(exclusion,p,re.I) and not re.search(r'\b(?:is|was|explicitly)\s+(?:rejected|not adopted|obsolete)\b',p,re.I) and (constraints or not re.search(passive_refusal,p,re.I)))


def locate(target):
    if target.is_file():
        return target
    # The harness passes its workspace; offline replay may pass the declared
    # output directory or an explicit artifact file. An arbitrary root is not
    # an alternative delivery location.
    found=(target if target.name=='output' else target/'output')/ARTIFACT
    if found.is_file():
        return found
    return None


def extract_raw(path):
    if path is None:
        return {'state':'confirmed_missing','sheets':[],'error':None}
    try:
        workbook=load_workbook(path,data_only=False,read_only=False)
        sheets=[]
        for sheet in workbook:
            # Excessive XML dimensions are isolated as a parse/shape problem,
            # never converted into an invented factual deduction.
            if sheet.max_row>10000 or sheet.max_column>200:
                return {'state':'parse_failure','sheets':[],'error':'Workbook dimensions exceed safe extraction bounds'}
            rows=[]
            for row in sheet.iter_rows():
                values=[{'value':c.value,'cell':c.coordinate,'formula':c.data_type=='f'} for c in row]
                if any(c['value'] is not None for c in values):
                    rows.append({'row':row[0].row,'cells':values})
            sheets.append({'name':sheet.title,'rows':rows})
        workbook.close()
        return {'state':'identified','sheets':sheets,'error':None}
    except Exception as error:
        return {'state':'parse_failure','sheets':[],'error':type(error).__name__}


def normalize(raw):
    cases=[]
    cells={f'{s["name"]}!{c["cell"]}':c for s in raw['sheets'] for r in s['rows'] for c in r['cells']}
    # Index declared setup IDs and sheet/cell references once per workbook.
    named={}
    global_setup=[]
    metric_rows=[]
    for sheet in raw['sheets']:
        in_metrics=False
        case_table=any(sum(header_role(c['value']) is not None for c in row['cells'])>=5 and any(header_role(c['value'])=='steps' for c in row['cells']) for row in sheet['rows'])
        for row in sheet['rows']:
            entries=[{'locator':f'{sheet["name"]}!{c["cell"]}','text':str(c['value']),'case_table':case_table} for c in row['cells'] if c['value'] is not None and not c['formula']]
            row_text=' '.join(x['text'] for x in entries)
            for entry in entries:
                # Declared setup/case IDs are references, not scored identity.
                for match in re.finditer(r'(?<![\w])([A-Z][A-Z0-9]{1,9}-[A-Z0-9]{1,5})(?![\w])',entry['text']):
                    if entry is entries[0]:
                        named.setdefault(match.group(1).upper(),[]).extend(entries)
            if case_table: continue
            if re.search(r'measurement definitions?|metric definitions?|execution and measurement guide',row_text,re.I): in_metrics=True
            if re.search(r'^(?:recognition rate|action.success rate|joint success|word error rate)\b',row_text,re.I):
                metric_rows.extend(entries)
            if in_metrics: metric_rows.extend(entries)
            # Non-case sheets are declarations only when they explicitly govern
            # execution, applicability or source identity. Never borrow actions.
            if re.search(r'required by every case|common setup|execution rule|start rule|conditional features|applicability|conflict|source register|evidence register',sheet['name']+' '+row_text,re.I):
                global_setup.extend(entries)
            elif re.search(r'read.?me|overview|execution (?:notes|guide)|preconditions|shared setup',sheet['name'],re.I):
                global_setup.extend(entries)
    explicit_ref=re.compile(r"(?:(?:'([^']+)'|([A-Za-z][A-Za-z0-9 _&/-]{0,65}))\s*!\s*\$?([A-Z]{1,3})\$?(\d{1,5}))",re.I)
    id_ref=re.compile(r'(?<![\w])([A-Z][A-Z0-9]{1,9}-[A-Z0-9]{1,5})(?![\w])',re.I)
    lookup={k.lower():k for k in cells}
    def unique(entries):
        return list({x['locator']:x for x in entries}.values())
    def operative_setup(entry):
        # A cited criterion is not a performed prerequisite. Preserve source
        # registers in the source/applicability view, not the execution view.
        sheet=entry['locator'].split('!')[0]
        return not entry.get('case_table') and not re.search(r'(?:source|evidence) register|quoted source|source excerpt|provenance only|not setup performed',sheet+' '+entry['text'],re.I)
    def resolve_setup(text):
        linked=[]
        def operative_reference(match):
            prefix=re.split(r'[.;\n]',text[:match.start()])[-1]
            return not re.search(r'(?:do not|must not|never|no|without|not performed|not invoked)\b[^.;]{0,90}$',prefix,re.I)
        for _ in range(3):
            # Bounded declared ID ranges and same-prefix shorthand retain their
            # actual setup rows; arbitrary strings never create synthetic facts.
            for match in re.finditer(r'\b([A-Z][A-Z0-9]*-)(\d{1,4})\s*(?:\.\.|-|through|to)\s*(?:\1)?(\d{1,4})\b',text,re.I):
                if not operative_reference(match):continue
                start,stop=int(match.group(2)),int(match.group(3))
                if 0<=stop-start<=100:
                    for number in range(start,stop+1):
                        linked.extend(named.get(match.group(1).upper()+str(number).zfill(len(match.group(2))),[]))
            for match in re.finditer(r'\b([A-Z][A-Z0-9]*-)(\d{1,4})((?:\s*[,/]\s*\d{1,4})+)\b',text,re.I):
                if not operative_reference(match):continue
                for number in re.findall(r'\d+',match.group(3)):
                    linked.extend(named.get(match.group(1).upper()+number.zfill(len(match.group(2))),[]))
            for match in explicit_ref.finditer(text):
                if not operative_reference(match):continue
                sheet=(match.group(1) or match.group(2)).strip()
                # A preceding prose phrase may be greedily captured unquoted.
                candidates=[sheet]+[sheet[i+1:] for i,c in enumerate(sheet) if c==' ']
                key=next((lookup.get((s+'!'+match.group(3)+match.group(4)).lower()) for s in candidates if (s+'!'+match.group(3)+match.group(4)).lower() in lookup),None)
                if key and not cells[key]['formula'] and cells[key]['value']:
                    linked.append({'locator':key,'text':str(cells[key]['value'])})
            for match in id_ref.finditer(text):
                if operative_reference(match):linked.extend(named.get(match.group(1).upper(),[]))
            # A setup's "applies to" list is not a call to execute those cases.
            # Do not traverse case/source nodes and then import their setups.
            # Explicit sheet/cell references still retain their directly cited
            # content, independent of where a solver placed its setup table.
            linked=unique(x for x in linked if operative_setup(x))
            expanded=' '.join(x['text'] for x in linked)
            if expanded==text: break
            text=expanded
        return linked
    for sheet in raw['sheets']:
        mapping=None
        intro=[]
        for row in sheet['rows']:
            headers={}
            for column,cell in enumerate(row['cells']):
                role=header_role(cell['value'])
                if role:
                    headers[role]=column
            if len(headers)>=5 and 'steps' in headers and ('objective' in headers or 'id' in headers):
                mapping=headers
                continue
            if mapping is None:
                intro += [str(c['value']) for c in row['cells'] if c['value'] and not c['formula']]
                continue
            fields={}
            locators={}
            formula_roles=[]
            for role,column in mapping.items():
                cell=row['cells'][column] if column<len(row['cells']) else {'value':None,'cell':'','formula':False}
                if cell['formula']:
                    fields[role]=''
                    formula_roles.append(role)
                else:
                    fields[role]=str(cell['value'] or '')
                locators[role]=f'{sheet["name"]}!{cell["cell"]}'
            if not fields.get('steps') and not fields.get('objective'):
                continue
            title=fields.get('objective','')+' '+fields.get('category','')
            operational=title+' '+fields.get('steps','')+' '+fields.get('expected','')
            topics=[key for key,pattern in TOPICS.items() if re.search(pattern,operational,re.I)]
            # A remote-control experiment may target a TV or external audio device;
            # a case explicitly about an unrelated DUT cannot borrow remote facts.
            wrong_object=bool(re.search(r'\b(?:printer|vehicle|air conditioner|medical pump)\b',title,re.I))
            steps=adopted(fields.get('steps',''))
            imperative=bool(re.search(r'\b(?:record|measure|verify|confirm|check|test|compare|observe|hold|select|identify|disable|block|repeat|restore|press|set|ensure|use|run|keep|remove|insert|establish|compute|invoke|time|shake|enter|teach|send|rotate|move|open|start|apply|leave|face|disconnect|power.cycle|fit|place|navigate)\b.{8,}',steps,re.I))
            outcome=adopted(fields.get('expected','')+' '+fields.get('acceptance',''),constraints=True)
            coherent=imperative and len(outcome.split())>=6 and not wrong_object
            # Repeated header/keyword blocks and extremely long scattershot cells
            # do not constitute a local adopted case proposition.
            if any(len(s.split())>4000 for s in fields.values()):
                coherent=False
            if len(set(norm(s) for s in [fields.get('steps',''),fields.get('expected',''),fields.get('acceptance','')]))==1:
                coherent=False
            shared=' '.join(intro)
            declared=unique(global_setup)
            # Resolve actual prerequisites and global start directives, not the
            # affected-case lists in a conflict/source register.
            directives=' '.join(x['text'] for x in declared if re.search(r'execute.{0,90}first|required by every case|common setup',x['text'],re.I))
            resolved=resolve_setup(fields.get('preconditions','')+' '+shared+' '+directives)
            linked=unique(declared+resolved)
            shared+=' '+' '.join(x['text'] for x in linked)
            cases.append({'case_key':fields.get('id') or f'{sheet["name"]}:{row["row"]}',
                          'topics':topics,'fields':fields,'locators':locators,
                          'shared_setup':shared,'shared_setup_locators':[x['locator'] for x in linked], 'eligible':coherent,
                          'resolved_setup':' '.join(x['text'] for x in resolved if operative_setup(x)),
                          'metric_definitions':' '.join(x['text'] for x in metric_rows),
                          'metric_locators':[x['locator'] for x in metric_rows],
                          'state':'parse_failure' if formula_roles else 'identified',
                          'formula_roles':formula_roles})
    by_id={str(c['case_key']).upper():c for c in cases}
    for case in cases:
        references=' '.join(case['fields'].get(r,'') for r in ['preconditions','steps','remarks'])
        case['related_case_keys']=list(dict.fromkeys(m.group(1).upper() for m in id_ref.finditer(references) if m.group(1).upper() in by_id and m.group(1).upper()!=str(case['case_key']).upper()))
    return cases


def clause_match(case,rule,exclude_nonadopted=True):
    texts=[]
    used=[]
    for role in rule['roles']:
        value=case['fields'].get(role,'')
        if role=='preconditions':
            value+=' '+case['shared_setup']
            used.extend(case.get('shared_setup_locators',[]))
        if exclude_nonadopted:
            value=adopted(value,constraints=role!='steps')
        texts.append(value)
        if value.strip():
            used.append(case['locators'].get(role,'shared setup'))
    text=norm(' '.join(texts))
    matches=[]
    for pattern in rule['all_patterns']:
        match=re.search(pattern,text,re.I)
        if not match:
            return None
        matches.append(match.group(0))
    return {'locators':used,'matched_relations':matches}


def affirmative_match(case,rule):
    # Deduction predicates cannot bind words across unrelated sentences or cells.
    for role in rule['roles']:
        for sentence in sentences(adopted(case['fields'].get(role,''))):
            text=norm(sentence)
            matches=[re.search(p,text,re.I) for p in rule['all_patterns']]
            if all(matches) and all(affirmative(text,m) for m in matches):
                return {'locators':[case['locators'][role]],'matched_relations':[m.group(0) for m in matches]}
    return None


def score(target):
    params_path=Path(os.environ.get('SCORING_PARAMS') or HERE/'scoring_params.json')
    params_bytes=params_path.read_bytes()
    params=json.loads(params_bytes.decode('utf-8'))
    assert abs(sum(params['positive_weights'].values())-1)<1e-8
    path=locate(Path(target))
    raw=extract_raw(path)
    cases=normalize(raw)
    for case in cases:
        case['business_text']={role:norm(adopted(case['fields'].get(role,''),constraints=role!='steps')) for role in ['steps','preconditions','expected','acceptance','remarks']}
        case['business_text']['local_preconditions']=case['business_text']['preconditions']
        case['business_text']['resolved_preconditions']=case['business_text']['preconditions']+' '+norm(adopted(case.get('resolved_setup',''),constraints=True))
        case['business_text']['preconditions']+=' '+norm(adopted(case['shared_setup'],constraints=True))
        case['business_text']['metrics']=norm(adopted(case.get('metric_definitions',''),constraints=True))
    semantic_mode='not_applicable';semantic_key=None
    if path is not None and cases:
        semantic,semantic_mode,semantic_key=semantic_evaluate(cases,params,path)
    else:
        semantic={(item['id'],a['id']):{'fulfilled':False,'case_keys':[],'explanation':'Missing candidate artifact'}
            for item in params['items'] for a in item['assertions']}
        semantic.update({(item['id'],item['id']):{'fulfilled':False,'case_keys':[],'explanation':'Missing candidate artifact'}
            for item in params['deduction_items']})
    positive=[]
    completion={}
    for item in params['items']:
        eligible=[c for c in cases if c['eligible']]
        decisions=[]
        for assertion in item['assertions']:
            evidence=[]
            applicable=not assertion.get('conditional_term') or any(wer_used(' '.join(c['business_text'][r] for r in ['steps','acceptance','remarks'])) for c in eligible)
            if applicable:
                decision=semantic[(item['id'],assertion['id'])]
                if decision['fulfilled']:
                    evidence=[{'case_key':key,'component':assertion['predicate'],
                        'clauses':[{'locators':[],'matched_relations':[assertion['predicate']],
                        'predicate':'source-bound-llm-v1'}]} for key in decision['case_keys']]
            decisions.append({'assertion_id':assertion['id'],'fulfilled':bool(evidence),
                              'applicable':applicable,
                              'evidence':evidence,'state':'identified' if evidence else ('parse_failure' if raw['state']=='parse_failure' else 'confirmed_missing')})
        active=[d for d in decisions if d['applicable']]
        fraction=sum(d['fulfilled'] for d in active)/len(active) if active else 0
        weight=params['positive_weights'][item['id']]
        completion[item['id']]=fraction
        positive.append({'id':item['id'],'weight':weight,'fraction':fraction,'earned':weight*fraction,
                         'declared':len(decisions),'assertions':decisions})
    deductions=[]
    damages={}
    for item in params['deduction_items']:
        occurrences=[]
        decision=semantic[(item['id'],item['id'])]
        for case_key in decision['case_keys'] if decision['fulfilled'] else []:
            key=item['damage_key'].format(topic='semantic')
            occurrence={'damage_instance_key':key,'causal_root_id':key,'case_key':case_key,
                'manifestation_id':f'{item["id"]}:{case_key}','locators':[],
                'matched_relations':[item['id']],'semantic_explanation':decision['explanation']}
            occurrences.append(occurrence)
            if key not in damages:damages[key]={'key':key,'items':[],'coefficient':1.0,'manifestations':[]}
            damage=damages[key]
            if item['id'] not in damage['items']:damage['items'].append(item['id'])
            damage['coefficient']=min(damage['coefficient'],params['deduction_coefficients'][item['id']]);damage['manifestations'].append(occurrence)
        deductions.append({'id':item['id'],'coefficient':params['deduction_coefficients'][item['id']],
            'status':'triggered' if occurrences else ('parse_failure' if raw['state']=='parse_failure' else 'not_triggered'),
            'occurrences':occurrences})
    earned=math.fsum(p['earned'] for p in positive)
    retention=math.prod(d['coefficient'] for d in damages.values())
    readiness=params['readiness_contract']
    triggered_deductions={d['id'] for d in deductions if d['status']=='triggered'}
    readiness_checks={
        'critical_coverage':all(any(completion[item]>0 for item in items)
            for items in readiness['critical_coverage_groups'].values()),
        'independent_controls':not (set(readiness['independent_control_deductions'])&triggered_deductions),
        'no_fabricated_execution':not any(d['id']==readiness['fabricated_execution_deduction'] and d['status']=='triggered' for d in deductions)}
    failed_lenient_checks=sum(not passed for passed in readiness_checks.values())
    strict=earned*retention
    lenient=float(all(readiness_checks.values()))
    ledger={'schema_version':'pd-ledger-v1','positive_completion':completion,
            'positive_earned':earned,'damage_instances':list(damages.values()),
            'retention':retention,'retention_multiplier':retention,
            'readiness_checks':readiness_checks,'failed_lenient_checks':failed_lenient_checks,
            'final':strict}
    settlement_ledger={**ledger,'final_score':strict,'damage_instances':[{**d,'item_ids':d['items']} for d in damages.values()]}
    return {'schema_version':'controlled-device-program-result-v1','condition_blind':True,
            'contract_sha256':params['contract_sha256'],
            'scoring_params_sha256':hashlib.sha256(params_bytes).hexdigest(),
            'scoring_params_semantic_sha256':hashlib.sha256(json.dumps(params,sort_keys=True).encode()).hexdigest(),
            'artifact':None if path is None else {'filename':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()},
            'extraction':{'state':raw['state'],'error':raw['error'],'cases':len(cases)},
            'positive_ledger':positive,'deduction_ledger':deductions,'pd_ledger':ledger,
            'scoring_ledger':settlement_ledger,
            'reward_strict':strict,'reward_program':strict,'reward_mixed':strict,
            'rewards':{'strict':strict,'lenient':lenient},
            'normalizations':params['normalizations'],
            'semantic_judge':{'required':True,'mode':semantic_mode,'context_key':semantic_key},
            'observations':cases}


if __name__=='__main__':
    # ASCII JSON keeps Windows subprocess consumers independent of the console
    # codepage; JSON decoding losslessly restores the submitted Unicode strings.
    try:print(json.dumps(score(sys.argv[1] if len(sys.argv)>1 else '/workspace'),ensure_ascii=True))
    except Exception as error:
        print(json.dumps({'scoring_status':'UNMEASURED','error_type':type(error).__name__,'reason':str(error),'candidate_score_assigned':False}))
        raise SystemExit(2)

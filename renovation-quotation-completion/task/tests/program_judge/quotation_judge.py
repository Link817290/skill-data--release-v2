#!/usr/bin/env python3
"""Quotation scorer: carrier extraction, scoped row binding, arithmetic decisions."""
from __future__ import annotations

import argparse
import json
import math
import numbers
import re
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path

from program_judge_runtime import Locator, ProgramJudge, load_contract, sha256

ROOT = Path(__file__).resolve().parents[1]


def canonical(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', str(value or ''))).casefold().rstrip('：:')


def numeric(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, numbers.Real):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, str) and re.fullmatch(r'[+-]?\d[\d,]*(?:\.\d+)?', value.strip()):
        return float(value.replace(',', ''))
    return None


def explicit_alternative_or_exclusion(note):
    """A pending keyword alone does not exclude an adopted numeric amount."""
    alternative = re.search(r'参考方案|替代方案|alternative', note, re.I)
    pending = re.search(r'暂估|待确认|待核|provisional|pending', note, re.I)
    excluded = re.search(r'未计入|未纳入|暂未计|另计|另行计|excluded|not included', note, re.I)
    return bool(alternative or (pending and excluded))


def extract_raw(path):
    """Extract actual cells without substituting reference or cached formula values."""
    sheets=[]
    if path.suffix.lower()=='.xls':
        import xlrd
        book=xlrd.open_workbook(path)
        for sheet in book.sheets():
            sheets.append(dict(name=sheet.name,rows=[sheet.row_values(r) for r in range(sheet.nrows)],formula_errors=[]))
    else:
        import openpyxl
        book=openpyxl.load_workbook(path,data_only=False)
        evaluated={}
        formula_errors=[]
        if any(c.data_type=='f' for sheet in book for row in sheet for c in row):
            import formulas
            invalid=[]
            parser=formulas.Parser()
            for sheet in book:
                for row in sheet:
                    for cell in row:
                        if cell.data_type!='f':
                            continue
                        try:
                            parser.ast(cell.value)
                        except Exception as exc:
                            invalid.append((sheet.title,cell.coordinate))
                            formula_errors.append(f'{sheet.title}!{cell.coordinate}: {type(exc).__name__}')
            scratch=tempfile.TemporaryDirectory(prefix='quotation-formula-isolation-') if invalid else None
            try:
                evaluation_path=path
                if invalid:
                    # Preserve independent valid calculations; dependents of malformed
                    # formulas receive an Excel error rather than cached or guessed values.
                    for sheet_name,address in invalid:
                        book[sheet_name][address]='#VALUE!'
                    evaluation_path=Path(scratch.name)/path.name
                    book.save(evaluation_path)
                model=formulas.ExcelModel().loads(str(evaluation_path)).finish()
                for key,result in model.calculate().items():
                    if not isinstance(key,str) or '!' not in key:
                        continue
                    qualifier,coordinate=key.rsplit('!',1)
                    sheet_key=qualifier.split(']',1)[-1].strip("'")
                    try:
                        if result.value.size==1:
                            value=result.value.item()
                            if numeric(value) is not None:
                                evaluated[(sheet_key.casefold(),coordinate.upper())]=numeric(value)
                    except (AttributeError,ValueError,TypeError):
                        continue
            except Exception as exc:
                formula_errors.append(type(exc).__name__+': '+str(exc)[:300])
            finally:
                if scratch:
                    scratch.cleanup()
                if invalid:
                    book=openpyxl.load_workbook(path,data_only=False)
        for sheet in book:
            rows=[]
            failed=[]
            for row in sheet:
                values=[]
                for cell in row:
                    value=cell.value
                    if cell.data_type=='f':
                        result=evaluated.get((sheet.title.casefold(),cell.coordinate))
                        if result is None:
                            failed.append(cell.coordinate)
                            value={'parse_failure':True,'formula':value}
                        else:
                            value=result
                    values.append(value)
                rows.append(values)
            sheets.append(dict(name=sheet.title,rows=rows,formula_errors=formula_errors+failed))
    return {'artifact':path,'sheets':sheets}


def bind_rows(raw,contract):
    """Bind by section and business labels; source row numbers are reference IDs."""
    sections={canonical(v):v for v in contract['sections'].values()}
    unit_keys={(canonical(u['section']),canonical(u['label'])) for u in contract['business_units']}
    targets=[]
    for sheet in raw['sheets']:
        if canonical(sheet['name'])=='kk' or is_reference_project(sheet,contract):
            continue
        context=None
        rows={}
        last_business_row=None
        label_col,quantity_col,amount_col,unit_col=1,3,7,2
        for index,cells in enumerate(sheet['rows'],1):
            padded=cells+[None]*max(0,9-len(cells))
            texts=[canonical(v) for v in padded]
            if '工程量' in texts and any(v in texts for v in ['施工项目','名称','项目']):
                label_col=next(i for i,v in enumerate(texts) if v in {'施工项目','名称','项目'})
                quantity_col=texts.index('工程量')
                if '单位' in texts:
                    unit_col=texts.index('单位')
                amount_candidates=[i for i,v in enumerate(texts) if v in {'合计','共计','金额'}]
                if len(amount_candidates)==1:
                    amount_col=amount_candidates[0]
                continue
            exact_headings={original for key,original in sections.items() for text in texts
                if key and text==key}
            heading_candidates=exact_headings or {original for key,original in sections.items() for text in texts
                if key and text and key in text and len(text)<=len(key)+12}
            if len(heading_candidates)==1:
                candidate=next(iter(heading_candidates))
                if numeric(padded[amount_col]) is None and not isinstance(padded[amount_col],dict):
                    context=candidate
                    last_business_row=None
                    continue
            if context is None:
                continue
            label=padded[label_col]
            label_key=canonical(label)
            if (canonical(context),label_key) not in unit_keys:
                label_key=re.sub(r'[（(][^）)]*[）)]','',label_key)
            aliases=contract.get('equivalent_business_labels',{})
            candidates={canonical(original) for original,variants in aliases.items()
                        if label_key in {canonical(v) for v in variants}
                        and (canonical(context),canonical(original)) in unit_keys}
            if len(candidates)>1 and last_business_row is not None:
                ordered=[u for u in contract['business_units'] if canonical(u['section'])==canonical(context)
                         and canonical(u['label']) in candidates and u['row']>last_business_row]
                if ordered:
                    candidates={canonical(min(ordered,key=lambda u:u['row'])['label'])}
            if len(candidates)==1:
                label_key=next(iter(candidates))
            key=(canonical(context),label_key)
            if key not in unit_keys:
                continue
            ranks=[u['row'] for u in contract['business_units']
                   if (canonical(u['section']),canonical(u['label']))==key]
            if len(ranks)==1:
                last_business_row=ranks[0]
            qoffset=quantity_col-3
            inputs={c:padded[ord(c)-65+qoffset] if 0<=ord(c)-65+qoffset<len(padded) else None for c in 'DEFG'}
            rows.setdefault(key,[]).append(dict(sheet=sheet['name'],row=index,label=label,section=context,object_prefix=padded[max(0,label_col-1)],
                value=padded[amount_col],inputs=inputs,unit=padded[unit_col],amount_column=amount_col+1,raw_cells=padded))
        if rows:
            targets.append(rows)
    registry={}
    for u in contract['business_units']:
        key=(canonical(u['section']),canonical(u['label']))
        candidates=[row for target in targets for row in target.get(key,[])]
        if u.get('object_prefix'):
            candidates=[r for r in candidates if canonical(r['object_prefix'])==canonical(u['object_prefix'])]
        registry[u['row']]={'state':'identified' if len(candidates)==1 else ('ambiguous' if candidates else 'confirmed_missing'),
            'record':candidates[0] if len(candidates)==1 else None,'candidates':candidates}
    return registry


def is_reference_project(sheet,contract):
    """Recognize the supplied worked example by its project identity, not its tab name."""
    identity=contract.get('reference_project_identity')
    if not identity:
        return False
    project=False
    area=False
    for cells in sheet['rows'][:16]:
        texts=[canonical(v) for v in cells]
        if any('工程名称' in t for t in texts):
            project=canonical(identity['project_name']) in texts
        if any(t.startswith('面积') for t in texts):
            for value in cells:
                cleaned=re.sub(r'(?:㎡|m2|m²|平方米)$','',canonical(value))
                parsed=numeric(cleaned)
                if parsed is not None and abs(parsed-identity['area'])<1e-7:
                    area=True
    return project and area


def normalize(raw,judge):
    registry=bind_rows(raw,judge.contract)
    artifact=raw['artifact'].name
    for row,item in registry.items():
        record=item['record']
        state='parse_failure' if raw.get('parse_failure') else item['state']
        if record:
            value=record['value']
            if isinstance(value,dict):
                state='parse_failure'
            elif numeric(value) is None:
                state='confirmed_missing'
            loc=Locator('row-'+str(row),artifact,raw['artifact'].suffix.lower()[1:],
                f"{record['sheet']}!row:{record['row']}",str(row),'quantity/rates/amount',
                json.dumps(record,ensure_ascii=False,default=str))
        else:
            loc=Locator('row-'+str(row),artifact,'workbook','business-row:'+str(row),str(row),'binding',
                json.dumps({'state':state,'candidate_count':len(item['candidates'])}))
        item['state']=state
        item['observation']=judge.observe('row-'+str(row),state,[loc])
    return registry


def evaluate(registry,judge):
    contract=judge.contract
    tolerance=contract['numeric_tolerance']['currency_absolute']
    units={u['row']:u for u in contract['business_units']}
    correct={}
    changed={}
    for row,item in registry.items():
        u=units[row]
        record=item['record']
        correct[row]=False
        changed[row]=False
        if item['state']!='identified':
            continue
        note=' '.join(str(v) for v in record['raw_cells'][8:] if v)
        item['alternate']=explicit_alternative_or_exclusion(note)
        changed[row]=any(numeric(v) is not None and (numeric(record['inputs'].get(c)) is None or
            abs(numeric(v)-numeric(record['inputs'][c]))>1e-7) for c,v in u['material_inputs'].items())
        if numeric(u.get('value')) is not None:
            correct[row]=not changed[row] and abs(numeric(record['value'])-float(u['value']))<=tolerance
    relations=contract['aggregate_relations']
    aggregate_ok={}
    aggregate_bad={}
    def leaves(row,selected=False,seen=None):
        seen=set() if seen is None else seen
        if row in seen:
            return Counter({'cycle':1})
        refs=relations.get(str(row))
        if selected:
            refs=registry[row].get('matching_aggregate_refs',refs)
        if refs is None:
            return Counter({row:1})
        result=Counter()
        for ref in refs:
            result.update(leaves(ref,selected,seen|{row}))
        return result
    for target,refs in relations.items():
        row=int(target)
        actual=registry[row]
        outcomes=[]
        aggregate_scope=' '.join(str(v) for v in actual['record']['raw_cells'] if v) if actual['record'] else ''
        partial_scope=bool(re.search(r'已知|未含|不含|未计入|暂定',aggregate_scope))
        for variant in [refs]+contract.get('equivalent_aggregate_relations',{}).get(target,[]):
            complete=actual['state']=='identified'
            if target in contract.get('require_leaf_conservation',[]):
                proposed=Counter()
                for ref in variant:
                    proposed.update(leaves(ref,True))
                complete=complete and proposed==leaves(row)
            expected=0.0
            for ref in variant:
                node=registry[ref]
                if node['state']=='confirmed_missing' and ref in contract['blank_optional_aggregate_inputs']:
                    continue
                if partial_scope and node['state']=='confirmed_missing' and units[ref]['scoring_disposition']!='exact' and node['record']:
                    marker=' '.join(str(v) for v in node['record']['raw_cells'][7:] if v)
                    if re.search(r'待确认|待核|暂不计|不计入|未计入|甲方另付',marker):
                        continue
                if node['state']!='identified':
                    complete=False
                    break
                expected+=numeric(node['record']['value'])
            outcomes.append((variant,complete,complete and abs(numeric(actual['record']['value'])-expected)<=tolerance))
        matching=[v for v,complete,ok in outcomes if ok]
        aggregate_ok[row]=bool(matching)
        aggregate_bad[row]=any(complete for _,complete,_ in outcomes) and not matching
        if matching:
            actual['matching_aggregate_refs']=matching[0]
    def valid_tree(row,seen=None):
        seen=set() if seen is None else seen
        if row in seen:
            return False
        if str(row) in relations:
            return aggregate_ok.get(row,False) and all(valid_tree(r,seen|{row}) for r in registry[row].get('matching_aggregate_refs',relations[str(row)])
                if units[r]['scoring_disposition']=='exact' or str(r) in relations)
        return correct.get(row,False) if units[row]['scoring_disposition']=='exact' else True
    foundation_sections = [
        ([19,20,21,22,23,25,26,27], [24,28], 29),
        ([32,33,34,35,36,37], [], 38),
        ([41,42,43,44,45,46,47,48], [49], 50),
        ([53,54,55,56], [57], 58),
        ([61,62,63,64,65], [], 66),
        ([69,70,71,72,73], [], 74),
        ([76,77,78,79,80,81,82,83], [], 85),
        ([88,89,90,91], [92], 93),
        ([96,97,98,99,107,109,110,114], [100,101,102,103,104,105,106,108,111,112,113], 115),
    ]
    main_sections = [
        ([127,128], [129], 130),
        ([133,134,135,136], [138], 139),
        ([142,143,144], [], 145),
        ([148,149], [150], 151),
    ]

    def uncertainty_safe(row):
        item=registry[row]
        if item['state']=='confirmed_missing':
            return True
        if item['state']!='identified':
            return False
        if item.get('alternate',False):
            return True
        record=item['record']
        # A warning-only source row may still have a complete, auditable
        # quantity-and-rate calculation. Accept that relation without requiring
        # the old reference's unsupported fixed amount. Rows missing any numeric
        # component do not enter through this branch.
        if units[row].get('group') in {'quantity_times_rate_sum','pricing_override'}:
            quantity=numeric(record['inputs'].get('D'))
            rates=[numeric(record['inputs'].get(key)) for key in 'EFG']
            adopted=numeric(record['value'])
            if quantity is not None and all(rate is not None for rate in rates) and adopted is not None:
                source_calculation=units[row].get('standard_calculation')
                expected=numeric(source_calculation)
                if expected is None:
                    expected=quantity*sum(rates)
                return abs(adopted-expected)<=tolerance
        reference=numeric(units[row].get('value'))
        adopted=numeric(record['value'])
        return reference is not None and adopted is not None and not changed[row] \
            and abs(adopted-reference)<=tolerance

    def section_chain(spec):
        details,uncertain,subtotal=spec
        return float(all(correct[row] for row in details)
            and all(uncertainty_safe(row) for row in uncertain)
            and valid_tree(subtotal))

    section_scores={
        'foundation': [section_chain(spec) for spec in foundation_sections],
        'main': [section_chain(spec) for spec in main_sections],
    }
    equipment=0.0
    equipment_node=registry[137]
    if equipment_node['state']=='identified':
        record=equipment_node['record']
        q=numeric(record['inputs'].get('D'))
        rate=numeric(record['inputs'].get('G'))
        if q==2 and rate==450 and abs(numeric(record['value'])-900)<=tolerance:
            equipment=1.0
    owner_fractions={
        'O01': float(any(item['state']=='identified' for item in registry.values())
            and all(not value for value in changed.values())),
        'O02': float(all(section_scores['main']) and equipment==1.0
            and valid_tree(154) and valid_tree(156)),
        'O03': sum(valid_tree(row) for row in [116,119,122,154,156,158])/6,
        'O04': sum(section_scores['foundation'])/len(section_scores['foundation']),
    }
    for p in contract['positive_items']:
        rows=p['rows']
        observed=[registry[r] for r in rows]
        evidence=[]
        for r in rows:
            item=registry[r]
            evidence.append(Locator('P-'+p['id']+'-'+str(r),judge.artifact_path.name,'workbook',
                f'business-row:{r}',str(r),'submitted_business_row',
                json.dumps(item['record'] if item['record'] else {'state':item['state']},ensure_ascii=False,default=str)))
        state='identified' if any(x['state']=='identified' for x in observed) else (
            'ambiguous' if any(x['state']=='ambiguous' for x in observed) else
            'parse_failure' if any(x['state']=='parse_failure' for x in observed) else 'confirmed_missing')
        obs=judge.observe('group-'+p['id'],state,evidence)
        fraction=owner_fractions[p['id']]
        comparison='exact' if fraction==1 else 'partial' if fraction>0 else 'missing' if state=='confirmed_missing' else 'different'
        judge.positive(p['id'],fraction,obs,
            f'Owner-local conjunctive completion {fraction:.9f}; independent owners retain weighted credit.',comparison)
    base_errors={r for r,u in units.items() if u.get('group')=='quantity_times_rate_sum' and registry[r]['state']=='identified' and not correct[r] and not changed[r] and not registry[r].get('alternate')}
    main_errors={r for r,u in units.items() if u.get('group')=='material_quantity_plus_loss' and registry[r]['state']=='identified' and not correct[r] and not changed[r] and not registry[r].get('alternate')}
    changed_errors={r for r in units if changed[r] and units[r]['scoring_disposition']=='exact'
                    and not registry[r].get('alternate')}
    def has_child_error(row,seen=None):
        seen=set() if seen is None else seen
        if row in seen:
            return True
        refs=relations.get(str(row),[])
        return any(r in base_errors|main_errors|changed_errors or aggregate_bad.get(r,False) or has_child_error(r,seen|{row}) for r in refs)
    total_errors={r for r,bad in aggregate_bad.items() if bad and not has_child_error(r) and not registry[r].get('alternate')}
    for d,errors in zip(contract['deduction_items'],[base_errors,main_errors,total_errors,changed_errors]):
        occurrences=[]
        for row in sorted(errors):
            section=canonical(units[row]['section'])
            occurrences.append(dict(damage_instance_key=section+':'+d['name'],causal_root_id=section+':'+d['name'],
                manifestation_id='row-'+str(row),observation_id=registry[row]['observation'],reason=d['trigger']))
        obsids=list(dict.fromkeys(registry[r]['observation'] for r in sorted(errors)))
        if not obsids:
            obsids=[next(iter(registry.values()))['observation']]
        judge.deduction(d['id'],'triggered' if occurrences else 'not_triggered',obsids,
            d['trigger'] if occurrences else 'No affirmative adopted error established.',occurrences=occurrences)
    def chain_diagnostic(spec):
        details, uncertain, subtotal = spec
        return {
            'details': {
                str(row): {
                    'correct': bool(correct[row]),
                    'changed': bool(changed[row]),
                    'state': registry[row]['state'],
                    'value': registry[row]['record']['value'] if registry[row]['record'] else None,
                }
                for row in details
            },
            'uncertain': {
                str(row): {
                    'safe': bool(uncertainty_safe(row)),
                    'group': units[row].get('group'),
                    'standard_calculation': units[row].get('standard_calculation'),
                    'state': registry[row]['state'],
                    'value': registry[row]['record']['value'] if registry[row]['record'] else None,
                    'inputs': registry[row]['record']['inputs'] if registry[row]['record'] else None,
                }
                for row in uncertain
            },
            'subtotal': {
                str(subtotal): {
                    'valid': bool(valid_tree(subtotal)),
                    'state': registry[subtotal]['state'],
                    'value': registry[subtotal]['record']['value'] if registry[subtotal]['record'] else None,
                    'aggregate_ok': bool(aggregate_ok.get(subtotal,False)),
                }
            },
        }

    return {
        'foundation_section_chains': section_scores['foundation'],
        'foundation_chain_details': [chain_diagnostic(spec) for spec in foundation_sections],
        'main_material_section_chains': section_scores['main'],
        'main_material_chain_details': [chain_diagnostic(spec) for spec in main_sections],
        'equipment_chain': equipment,
        'total_dependency_trees': {
            str(row): {
                'valid': float(valid_tree(row)),
                'aggregate_ok': bool(aggregate_ok.get(row,False)),
                'state': registry[row]['state'],
                'value': registry[row]['record']['value'] if registry[row]['record'] else None,
                'selected_refs': registry[row].get('matching_aggregate_refs', relations.get(str(row), [])),
            }
            for row in [116,119,122,154,156,158]
        },
    }


def score(artifact,contract_path):
    judge=ProgramJudge(load_contract(contract_path),artifact,sha256(contract_path))
    try:
        raw=extract_raw(artifact)
    except ImportError:
        raise
    except Exception as exc:
        raw={'artifact':artifact,'sheets':[],'parse_failure':type(exc).__name__+': '+str(exc)}
    diagnostics=evaluate(normalize(raw,judge),judge)
    result=judge.finish()
    result['business_diagnostics']=diagnostics
    result['carrier_diagnostics']={'parse_failure':raw.get('parse_failure'),
        'formula_errors':{s['name']:s['formula_errors'] for s in raw['sheets'] if s['formula_errors']}}
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('artifact',type=Path)
    parser.add_argument('--contract',type=Path,default=ROOT/'rubric-contract.json')
    parser.add_argument('--json',type=Path)
    args=parser.parse_args()
    result=score(args.artifact.resolve(),args.contract.resolve())
    rendered=json.dumps(result,ensure_ascii=False,indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True)
        args.json.write_text(rendered+'\n',encoding='utf-8')
    else:
        print(rendered)


if __name__=='__main__':
    main()

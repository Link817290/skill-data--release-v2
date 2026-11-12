from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from zipfile import ZipFile
from zipfile import BadZipFile
from openpyxl.cell.cell import MergedCell
import argparse
import ast
import copy
import json
import math
import operator
import statistics
import subprocess
import sys
import tempfile
import traceback
import openpyxl

VERSION='manufacturing-source-cycle'
MEASUREMENT='工时测量记录表'
CAPACITY='标准版'
GROUPS=['mean','population_deviation','screening_bounds','screened_mean','normal_time','standard_time','station_time','machine_cycle','theoretical_capacity','theoretical_resources']


def operation_completion(atoms,ratio_operations):
    def combined(sheet,columns,rows):
        return statistics.mean(min(float(atoms[f'{sheet}!{col}{r}']) for col in columns) for r in rows)
    return {
        'statistics':combined(MEASUREMENT,['V','W','X','Y','Z'],range(5,25)),
        'adjusted_time':combined(MEASUREMENT,['AF','AH'],range(5,25)),
        'station_normalization':combined(MEASUREMENT,['AI'],range(5,25)),
        'station_cycle':combined(CAPACITY,['L','O'],range(6,11)),
        'capacity':combined(CAPACITY,['Q','R'],range(6,11)),
        'ratio_numerator':statistics.mean(float(v['numerator']['passed']) for v in ratio_operations.values()),
        'resources':combined(CAPACITY,['V','X'],range(6,11)),
    }


class RecalculationInfrastructureError(RuntimeError):
    pass


def number(value):
    if value is None:return 0.0
    if isinstance(value,(int,float)):return value
    if not isinstance(value,str) or not value.startswith('='):raise ValueError('Not a numeric input')
    operators={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv}
    def evaluate(node):
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):return node.value
        if isinstance(node,ast.BinOp) and type(node.op) in operators:return operators[type(node.op)](evaluate(node.left),evaluate(node.right))
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub):return -evaluate(node.operand)
        raise ValueError('Unsupported input arithmetic')
    return evaluate(ast.parse(value[1:],mode='eval').body)


def reference(w):
    result={};normal={}
    def put(sheet,r,c,value,group):result[f'{sheet}!{openpyxl.utils.get_column_letter(c)}{r}']={'expected':value,'group':group}
    s=w[MEASUREMENT]
    for r in range(5,25):
        values=[number(s.cell(r,c).value) for c in range(7,22)]
        mean=statistics.mean(values);sigma=statistics.pstdev(values);lower=max(0,mean-3*sigma);upper=mean+3*sigma
        retained=[v for v in values if lower<=v<=upper];trimmed=statistics.mean(retained)
        n=trimmed*(1+number(s.cell(r,31).value));standard=n*(1+number(s.cell(r,33).value))/number(s.cell(r,6).value)
        norm=standard/number(s.cell(r,5).value);normal[r]=n
        for c,val,group in [(22,mean,'mean'),(23,sigma,'population_deviation'),(24,lower,'screening_bounds'),(25,upper,'screening_bounds'),(26,trimmed,'screened_mean'),(32,n,'normal_time'),(34,standard,'standard_time'),(35,norm,'station_time')]:put(MEASUREMENT,r,c,val,group)
    s=w[CAPACITY];demand=number(s['C2'].value)
    for r in range(6,11):
        fixture_time=normal[5+(r-6)*4];auto=number(s.cell(r,14).value);cycle=fixture_time+auto
        standard=cycle*(1+number(s.cell(r,16).value))/number(s.cell(r,9).value)
        capacity=3600/standard
        ratio=cycle/(number(s.cell(r,11).value)+number(s.cell(r,13).value))
        machines=demand/capacity/number(s.cell(r,21).value)
        persons=machines/number(s.cell(r,20).value)*2
        for c,val,group in [(12,fixture_time,'machine_cycle'),(15,cycle,'machine_cycle'),(17,standard,'theoretical_capacity'),(18,capacity,'theoretical_capacity'),(19,ratio,'theoretical_resources'),(22,machines,'theoretical_resources'),(24,persons,'theoretical_resources')]:put(CAPACITY,r,c,val,group)
    return result


def scenario(canonical,name):
    w=copy.deepcopy(canonical);s=w[MEASUREMENT];c=w[CAPACITY]
    if name=='changed_observations':
        for r in range(5,25):
            for col in range(7,22):s.cell(r,col,number(s.cell(r,col).value)*(1+(r%5)*.07)+((col+r)%5)*.47+.31)
        s['G5']=3000;s['R9']=1700
    elif name=='separate_allowances_and_rating':
        for r in range(5,25):s.cell(r,31,.07+(r%3)*.02);s.cell(r,33,.12+(r%2)*.03)
        for r in range(6,11):c.cell(r,16,.04+(r%2)*.02)
    elif name=='batch_crew_and_ratio':
        for r in range(5,25):s.cell(r,6,number(s.cell(r,6).value)*(1.5 if r%2 else .75));s.cell(r,5,2 if r%3 else 3)
        for r in range(6,11):
            c.cell(r,9,number(c.cell(r,9).value)*1.25);c.cell(r,11,2.0+r*.3);c.cell(r,13,1.8+r*.1);c.cell(r,20,2+r%3)
    elif name=='demand_hours_and_processing':
        c['C2']=487300
        for r in range(6,11):c.cell(r,21,17+r*.1);c.cell(r,14,number(c.cell(r,14).value)*(1+(r%3)*.11))
    elif name=='crew_invariance':
        for r in range(6,11):c.cell(r,10,2+r%3)
    elif name=='nonzero_crew_and_batch':
        for r in range(5,25):
            for col in range(7,22):s.cell(r,col,3+r*.37+col*.19)
            s.cell(r,5,2+r%3);s.cell(r,6,7+r%4)
    elif name.startswith('activity_'):
        for r in range(6,11):
            c.cell(r,11,2);c.cell(r,13,3);c.cell(r,14,400+r*10);c.cell(r,10,1)
            if name=='activity_numerator':c.cell(r,14,800+r*10)
            if name=='activity_denominator':c.cell(r,11,7);c.cell(r,13,11)
            if name=='activity_crew':c.cell(r,10,2+r%3)
        if name=='activity_normalization':
            for r in range(5,25,4):
                for col in range(7,22):s.cell(r,col,0)
    return w


def equal(actual,expected):
    return isinstance(actual,(int,float)) and not isinstance(actual,bool) and math.isfinite(actual) and abs(actual-expected)<=max(1e-7,abs(expected)*1e-7)


def minimum_usability(canonical,decisions,ratio_operations):
    checks={key:True for key in ['native_integrity','numeric_business_outputs','measurement_and_piece_time','conservative_station_cycle','coherent_production_resources','original_activity_basis']}
    evidence=[]
    source_crew_cases={'baseline','changed_observations','demand_hours_and_processing'}
    for name,cells in decisions.items():
        if name.endswith('_local'):continue
        inputs=scenario(canonical,name);cap=inputs[CAPACITY]
        numeric=lambda x:isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
        between=lambda x,lo,hi:numeric(x) and lo-max(1e-7,abs(lo)*1e-7)<=x<=hi+max(1e-7,abs(hi)*1e-7)
        checks['numeric_business_outputs'] &= all(numeric(c['actual']) and c['actual']>=-1e-9 for c in cells.values())
        for row in range(5,25):
            columns=['Z','AF','AH']+(['AI'] if name in source_crew_cases else [])
            checks['measurement_and_piece_time'] &= all(cells[f'{MEASUREMENT}!{col}{row}']['correct'] for col in columns)
        for row in range(6,11):
            actual=lambda col:cells[f'{CAPACITY}!{col}{row}']['actual']
            loading=cells[f'{CAPACITY}!L{row}']['expected'];auto=number(cap[f'N{row}'].value)
            activity=number(cap[f'K{row}'].value)+number(cap[f'M{row}'].value)
            lower=loading+auto;upper=lower+activity
            checks['conservative_station_cycle'] &= cells[f'{CAPACITY}!L{row}']['correct'] and between(actual('O'),lower,upper)
            chain=False
            if all(numeric(actual(col)) and actual(col)>0 for col in ['O','Q','R','V','X']):
                # The source plant has P=0. Nonzero P convention remains a strict quality check.
                q=actual('O')/number(cap[f'I{row}'].value)
                rate=3600/actual('Q');machines=number(cap['C2'].value)/actual('R')/number(cap[f'U{row}'].value)
                people=2*actual('V')/number(cap[f'T{row}'].value)
                chain=all(equal(actual(col),value) for col,value in [('Q',q),('R',rate),('V',machines),('X',people)])
            if number(cap[f'P{row}'].value)==0:checks['coherent_production_resources'] &= chain
            checks['original_activity_basis'] &= between(actual('S'),auto/activity,upper/activity) and ratio_operations[f'{CAPACITY}!S{row}']['denominator']['passed']
            if name=='baseline':evidence.append({'station':row,'cycle_actual':actual('O'),'cycle_lower':lower,'cycle_upper':upper,'activity_actual':actual('S'),'activity_lower':auto/activity,'activity_upper':upper/activity})
    return checks,{'policy':'source-operating-condition-and-core-causality-v1','source_crew_scenarios':sorted(source_crew_cases),'source_planning_allowance':0,'source_component_bounds':evidence}


def score(artifact,logs):
    if not artifact.is_file():return {'reward':0.0,'rewards':{'strict':0.0,'lenient':0.0},'error':'Required workbook missing','version':VERSION}
    with ZipFile(artifact) as z:
        if any('externalLinks/' in n or 'vbaProject' in n for n in z.namelist()):raise ValueError('External data links and macros are not allowed')
    canonical=openpyxl.load_workbook(Path(__file__).with_name('inputs.xlsx'),data_only=False)
    candidate=openpyxl.load_workbook(artifact,data_only=False,keep_links=False)
    targets=reference(canonical)
    for sheet in canonical:
        if sheet.title not in candidate.sheetnames:raise ValueError('Original worksheet missing')
        restored=candidate[sheet.title]
        if restored.sheet_state!='visible' or set(map(str,sheet.merged_cells))!=set(map(str,restored.merged_cells)):raise ValueError('Original worksheet layout changed')
        for key,dimension in sheet.column_dimensions.items():
            if abs(dimension.width-restored.column_dimensions[key].width)>.02:raise ValueError('Original column layout changed')
        for key,dimension in sheet.row_dimensions.items():
            if abs((dimension.height or sheet.sheet_format.defaultRowHeight)-(restored.row_dimensions[key].height or restored.sheet_format.defaultRowHeight))>.05:raise ValueError('Original row layout changed')
        for row in sheet:
            for cell in row:
                if isinstance(cell,MergedCell) or f'{sheet.title}!{cell.coordinate}' in targets:continue
                actual=candidate[sheet.title][cell.coordinate].value
                if cell.value!=actual:
                    if cell.data_type=='f' and isinstance(actual,(int,float)) and equal(actual,number(cell.value)):continue
                    raise ValueError(f'Original input or interface changed: {sheet.title}!{cell.coordinate}')
    for sheet in candidate:
        for row in sheet:
            for cell in row:
                if cell.data_type=='f' and any(mark in cell.value.lower() for mark in ['http:','https:','file:','/tests/','/solution/','/golden/','webservice(','dde(']):raise ValueError('External or private reference')
    scenarios=['baseline','changed_observations','separate_allowances_and_rating','batch_crew_and_ratio','demand_hours_and_processing','crew_invariance','nonzero_crew_and_batch']
    operation_scenarios=['activity_base','activity_numerator','activity_denominator','activity_crew','activity_normalization']
    with tempfile.TemporaryDirectory(prefix='native-time-verifier-') as tmp:
        tmp=Path(tmp)
        def run(case):
            name,local=case
            inputs=scenario(canonical,name);expected=reference(inputs);instance=copy.deepcopy(candidate)
            for sheet in inputs:
                for row in sheet:
                    for cell in row:
                        if isinstance(cell,MergedCell) or f'{sheet.title}!{cell.coordinate}' in targets:continue
                        instance[sheet.title][cell.coordinate]=cell.value
            # Each local operation receives true prerequisite values on a separate sheet copy.
            if local:
                isolated_sheets={}
                for anchor in targets:
                    source_sheet,output_cell=anchor.split('!')
                    output_col=openpyxl.utils.cell.coordinate_from_string(output_cell)[0]
                    key=(source_sheet,output_col)
                    if key not in isolated_sheets:
                        isolated=instance.create_sheet('op_'+str(len(instance.worksheets)))
                        for source_row in instance[source_sheet]:
                            for source_cell in source_row:
                                if not isinstance(source_cell,MergedCell):isolated[source_cell.coordinate]=source_cell.value
                        for upstream,entry in expected.items():
                            sheet,cell=upstream.split('!')
                            col=openpyxl.utils.cell.coordinate_from_string(cell)[0]
                            if sheet==source_sheet and col!=output_col:isolated[cell]=entry['expected']
                        isolated_sheets[key]=isolated
                    isolated=isolated_sheets[key]
                    formula=isolated[output_cell].value
                    if isinstance(formula,str) and formula.startswith('='):
                        formula=formula.replace("'"+source_sheet+"'!", "'"+isolated.title+"'!").replace(source_sheet+'!',"'"+isolated.title+"'!")
                        isolated[output_cell]=formula
                    expected[anchor]['operation_sheet']=isolated.title
                for anchor,entry in expected.items():
                    sheet,cell=anchor.split('!');instance[sheet][cell]=entry['expected']
            run_name=name+('_local' if local else '')
            work=tmp/run_name;inp=work/'input';out=work/'output';inp.mkdir(parents=True);out.mkdir();instance.save(inp/'standard_time.xlsx')
            attempts=[]
            # A transient LibreOffice startup failure must not become a candidate zero.
            for attempt in range(3):
                try:
                    p=subprocess.run(['libreoffice',f'-env:UserInstallation=file://{work}/profile-{attempt}','--headless','--norestore','--convert-to','xlsx','--outdir',str(out),str(inp/'standard_time.xlsx')],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=600)
                    attempts.append({'attempt':attempt+1,'exit_code':p.returncode,'stdout':p.stdout})
                    if p.returncode==0 and (out/'standard_time.xlsx').exists():break
                except subprocess.TimeoutExpired:
                    attempts.append({'attempt':attempt+1,'error':'Recalculation timeout'})
                except OSError as e:
                    raise RecalculationInfrastructureError(f'Recalculation tool unavailable: {e}') from e
            else:
                raise RecalculationInfrastructureError(f'Workbook recalculation infrastructure failed: {name}: {json.dumps(attempts)}')
            values=openpyxl.load_workbook(out/'standard_time.xlsx',data_only=True)
            for anchor,entry in expected.items():
                sheet,cell=anchor.split('!');entry['actual']=values[entry.get('operation_sheet',sheet)][cell].value;entry['correct']=equal(entry['actual'],entry['expected'])
            return run_name,expected,json.dumps(attempts,ensure_ascii=False,indent=2)
        cases=[(name,local) for name in scenarios for local in [False,True]]+[(name,True) for name in operation_scenarios]
        with ThreadPoolExecutor(max_workers=len(cases)) as pool:runs=list(pool.map(run,cases))
    decisions={name:items for name,items,_ in runs};groups={g:[] for g in GROUPS};atoms={}
    for anchor,entry in targets.items():
        passed=all(decisions[name][anchor]['correct'] for name in scenarios);atoms[anchor]=passed;groups[entry['group']].append(passed)
    end_to_end_completion={g:sum(v)/len(v) for g,v in groups.items()}
    local_atoms={anchor:all(decisions[name+'_local'][anchor]['correct'] for name in scenarios) for anchor in targets}
    ratio_operations={}
    for row in range(6,11):
        anchor=f'{CAPACITY}!S{row}'
        base=decisions['activity_base_local'][anchor]
        verdicts={}
        for operation,names in [('numerator',['activity_numerator']),('denominator',['activity_denominator','activity_crew'])]:
            checks=[]
            for name in names:
                changed=decisions[name+'_local'][anchor]
                actual=changed['actual'];initial=base['actual']
                correct=(isinstance(actual,(int,float)) and isinstance(initial,(int,float)) and initial!=0 and equal(actual/initial,changed['expected']/base['expected']))
                checks.append({'scenario':name,'passed':correct,'actual_ratio':actual/initial if isinstance(actual,(int,float)) and isinstance(initial,(int,float)) and initial!=0 else None,'expected_ratio':changed['expected']/base['expected']})
            if operation=='denominator':
                normalized=decisions['activity_normalization_local'][anchor]
                checks.append({'scenario':'activity_normalization','passed':normalized['correct'],'actual':normalized['actual'],'expected':normalized['expected']})
            verdicts[operation]={'passed':all(c['passed'] for c in checks),'evidence':checks}
        ratio_operations[anchor]=verdicts
    completion=operation_completion(local_atoms,ratio_operations)
    params=json.loads(Path(__file__).with_name('scoring_params.json').read_text())
    weights=params['positive_weights'];coefficient=params['deduction_coefficients']['D_ACTIVITY_BASIS']
    failures=[anchor for anchor,v in ratio_operations.items() if not v['denominator']['passed']]
    instances=[{'key':'activity_basis:'+anchor,'item_ids':['D_ACTIVITY_BASIS'],'exponent':1/5,'anchors':[anchor]} for anchor in failures]
    earned=math.fsum(weights[key]*completion[key] for key in weights)
    retention=math.prod(coefficient**instance['exponent'] for instance in instances)
    strict=round(earned*retention,12)
    must_haves,lenient_evidence=minimum_usability(canonical,decisions,ratio_operations)
    for name,_,stdout in runs:
        d=logs/'recalculation';d.mkdir(parents=True,exist_ok=True);(d/f'{name}.log').write_text(stdout)
    ledger={'schema_version':'pd-ledger-v1','positive_completion':completion,'positive_weights':weights,'deduction_coefficients':params['deduction_coefficients'],'damage_instances':instances,'positive_earned':earned,'retention':retention,'final_score':strict,'lenient_evaluation':{'policy':'task-specific-binary-must-haves','decisions':must_haves,'failed_ids':[k for k,v in must_haves.items() if not v]}}
    return {'reward':strict,'rewards':{'strict':strict,'lenient':float(all(must_haves.values()))},'version':VERSION,'completion':completion,'weights':weights,'must_haves':must_haves,'lenient_evidence':lenient_evidence,'end_to_end_completion':end_to_end_completion,'atomic_decisions':atoms,'local_atomic_decisions':local_atoms,'ratio_operations':ratio_operations,'scoring_ledger':ledger,'scenarios':decisions}


def main():
    p=argparse.ArgumentParser();p.add_argument('candidate_root',nargs='?',type=Path);p.add_argument('--artifact',type=Path,default=Path('/workspace/output/standard_time.xlsx'));p.add_argument('--logs',type=Path,default=Path('/logs/verifier'));args=p.parse_args();args.logs.mkdir(parents=True,exist_ok=True)
    if args.candidate_root:
        root=args.candidate_root
        if root.is_file() and root.name=='standard_time.xlsx':args.artifact=root
        else:args.artifact=root/'output/standard_time.xlsx' if (root/'output/standard_time.xlsx').is_file() else root/'standard_time.xlsx'
    try:result=score(args.artifact,args.logs)
    except Exception as e:
        result={'reward':0.0,'rewards':{'strict':0.0,'lenient':0.0},'error':str(e),'version':VERSION};(args.logs/'exception.log').write_text(traceback.format_exc())
        if not isinstance(e,(ValueError,BadZipFile)):result['system_error']=True
    (args.logs/'reward_detail.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    if result.get('system_error'):
        for name in ['reward.json','reward.txt','reward_strict.txt','reward_lenient.txt']:
            path=args.logs/name
            if path.exists():path.unlink()
        print(json.dumps({'system_error':True,'error':result.get('error')},ensure_ascii=False),file=sys.stderr)
        raise SystemExit(2)
    (args.logs/'reward.json').write_text(json.dumps({'reward':result['reward'],'rewards':result['rewards'],'system_error':False},indent=2))
    for name,value in [('reward',result['reward']),('reward_strict',result['rewards']['strict']),('reward_lenient',result['rewards']['lenient'])]:(args.logs/(name+'.txt')).write_text(str(value)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='scenarios'},ensure_ascii=False))


if __name__=='__main__':main()

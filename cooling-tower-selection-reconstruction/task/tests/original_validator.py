import argparse
import concurrent.futures
import hashlib
import json
import math
import re
import sys
from pathlib import Path
import subprocess
import tempfile
import openpyxl
from original_reference import BASE,INPUT_FORMULAS,SCENARIOS,GROUPS,DECISION_CELLS,calculate
from semantic_judge import adjudicate


TEMPERATURE_CELLS={'F16','F21','E32'}|{f'C{r}'for r in range(39,46)}|{f'D{r}'for r in range(46,54)}
LOG_PRESSURE_CELLS={'F19','F22','F33'}|{f'F{r}'for r in range(54,76,3)}
TRANSFER_CELLS={f'{c}81'for c in 'CDEFG'}|{'E97'}
EXACT_CELLS={'E96'}|{f'{c}{r}'for c in 'CDEFG'for r in (27,31,38,81,83)}
SELECTED_NUMERIC_CELLS={'E97','E99','D101','D105','D111','D112','D113','D116','D117','D118','D120','D121','D122','D123'}


def carrier_bindings(workbook):
 # The public instruction requires results in their original locations. Binding
 # each result to its published address also prevents unrelated same-row cells
 # from becoming accidental score carriers.
 return {cell:[cell]for cell in calculate(BASE)}


def source_integrity(workbook):
 material=Path('/workspace/materials/workspace.xlsx')
 if not material.exists():material=Path('/reference/materials/workspace.xlsx')
 if not material.exists():material=Path(__file__).resolve().parent.parent/'environment/workspace/materials/workspace.xlsx'
 original=openpyxl.load_workbook(material);failures=[]
 for source_sheet in original:
  candidate=workbook[source_sheet.title]
  if (candidate.max_row,candidate.max_column)!=(source_sheet.max_row,source_sheet.max_column):
   failures.append({'sheet':source_sheet.title,'property':'worksheet_bounds','expected':[source_sheet.max_row,source_sheet.max_column],'actual':[candidate.max_row,candidate.max_column]})
  source_merged=sorted(str(value)for value in source_sheet.merged_cells.ranges)
  candidate_merged=sorted(str(value)for value in candidate.merged_cells.ranges)
  if candidate_merged!=source_merged:
   failures.append({'sheet':source_sheet.title,'property':'merged_ranges','expected':source_merged,'actual':candidate_merged})
 failures.extend({'sheet':s.title,'cell':c.coordinate,'expected':c.value,'actual':workbook[s.title][c.coordinate].value}
         for s in original for row in s for c in row
         if isinstance(c.value,str)and c.data_type!='f'and workbook[s.title][c.coordinate].value!=c.value)
 return failures


def bind_water_grid_orientation(results):
 pairs={f'C{39+j}':f'C{45-j}'for j in range(7)}
 pairs.update({f'D{46+j}':f'D{52-j}'for j in range(7)})
 pairs.update({f'F{54+3*j+k}':f'F{72-3*j+k}'for j in range(7)for k in range(3)})
 cells=GROUPS['P02']['cells']
 descending=all(data[c]['ok']for data in results.values()for c in cells)
 ascending=all(equal(data[c]['actual'],data[pairs.get(c,c)]['expected'],c)for data in results.values()for c in cells)
 if ascending and not descending:
  for data in results.values():
   alternate={c:data[pairs.get(c,c)]['expected']for c in cells}
   for c,value in alternate.items():data[c].update(expected=value,ok=equal(data[c]['actual'],value,c),grid_orientation='ascending')
 return {'selected':'descending'if descending else'ascending'if ascending else'unresolved','descending_all_passed':descending,'ascending_all_passed':ascending,'coupled_operating_line_and_integral_owner':'P03'}


def bind_fan_bases(results):
 bindings={}
 for cell,alternative,label in [('D109',lambda value,n:value/n,'per_fan_annulus'),('D123',lambda value,n:value*n,'aggregate_shaft_power')]:
  standard=all(data[cell]['ok']for data in results.values())
  alternate=all(equal(data[cell]['actual'],alternative(data[cell]['expected'],(BASE|SCENARIOS[name])['F11'])if data[cell]['expected']is not None else None,cell)for name,data in results.items())
  if alternate and not standard:
   for name,data in results.items():
    entry=data[cell];entry['expected']=alternative(entry['expected'],(BASE|SCENARIOS[name])['F11'])if entry['expected']is not None else None;entry['ok']=equal(entry['actual'],entry['expected'],cell)
  bindings[cell]={'selected':label if alternate and not standard else'standard'if standard else'unresolved','standard_all_passed':standard,'alternative_all_passed':alternate}
 return bindings


def minimum_usable(results,decision_failed,label_failures,chart_ok):
 def numeric(cells,tolerance=.05):
  def matches(entry):
   actual,expected=entry['actual'],entry['expected']
   if expected is None:return actual in(None,'')
   return isinstance(actual,(int,float))and not isinstance(actual,bool)and math.isfinite(actual)and abs(actual-expected)<=max(1e-8,tolerance*abs(expected))
  return all(matches(data[c])for data in results.values()for c in cells)
 def present(cells):
  return all(entry['actual']in(None,'')if entry['expected']is None else isinstance(entry['actual'],(int,float))and not isinstance(entry['actual'],bool)and math.isfinite(entry['actual'])and entry['actual']>0 for data in results.values()for c in cells for entry in [data[c]])
 def exact(cells):return all(data[c]['ok']for data in results.values()for c in cells)
 def semantic_verdict(cell):
  positive={'满足','完全达到','达到','合格','通过','符合','满足要求','符合要求','满足GB7190.2-2008规范要求'}
  negative={'不满足','达不到','未达到','不合格','不通过','不符合','不满足要求','不符合要求'}
  def verdict(value):
   text=re.sub(r'[\s。；;，,！!]+$','',str(value or '').strip())
   if text in positive or re.fullmatch(r'(?:完全)?(?:满足|达到|符合)(?:(?:设计|规范)?要求)?',text):return 'positive'
   if text in negative or re.fullmatch(r'(?:未|不|不能|无法)(?:完全)?(?:满足|达到|符合)(?:(?:设计|规范)?要求)?',text):return 'negative'
   return text
  return all(verdict(data[cell]['source_expected'])==verdict(data[cell]['actual'])for data in results.values())
 # The public shaft-power heading permits either one-fan or aggregate power.
 power_ok=False
 for aggregate in [False,True]:
  checks=[]
  for name,data in results.items():
   entry=data['D123'];expected=entry['source_expected']
   if aggregate and expected is not None:expected*= (BASE|SCENARIOS[name])['F11']
   actual=entry['actual'];checks.append(actual in(None,'')if expected is None else isinstance(actual,(int,float))and not isinstance(actual,bool)and math.isfinite(actual)and abs(actual-expected)<=max(1e-8,.05*abs(expected)))
  power_ok=power_ok or all(checks)
 annulus_ok=numeric(['D109'])or all(isinstance(data['D109']['actual'],(int,float))and abs(data['D109']['actual']-data['D109']['source_expected']/(BASE|SCENARIOS[name])['F11'])<=.05*abs(data['D109']['source_expected']/(BASE|SCENARIOS[name])['F11'])for name,data in results.items())
 return {
  'air_state_and_water_saturation':exact(GROUPS['P01']['cells']+GROUPS['P02']['cells']),
  'thermal_calculations_and_packing':numeric([f'{c}{r}'for c in 'CDEFG'for r in [27,81,83]]+['G29'])and present(['E97','E99','D101']),
  'minimum_feasible_selection_and_verdicts':not decision_failed,
  'air_path_and_independent_coefficients':numeric(['D105','D106','D107','D108','D110','D100','C114','C115'])and annulus_ok,
  'aerodynamic_resistance':present(['D111','D112','D113','D116','D117','D118'])and numeric(['D120']),
  'fan_pressure_and_shaft_power':numeric(['D121','D122'])and power_ok,
  'installed_specific_power':exact(['B125'])and semantic_verdict('D125'),
  'original_labels_and_units':not label_failures,
  'original_comparison_chart':chart_ok,
 }


def equal(actual,expected,cell=None):
 if expected is None:return actual in (None,'')
 if isinstance(expected,str):
  if not isinstance(actual,str):return False
  positive={'满足','完全达到','达到','合格','通过','符合','满足要求','符合要求',
            '可行','具备可行性','可实施','可以实施'}
  negative={'不满足','达不到','未达到','不合格','不通过','不符合','不满足要求','不符合要求',
            '不可行','无可行工况','没有可行工况','不具备可行性','不具可行性','无法满足','无法实施'}
  def verdict(value):
   text=re.sub(r'[\s。；;，,！!]+$','',str(value or '').strip())
   if text in positive or re.fullmatch(r'(?:完全)?(?:满足|达到|符合)(?:(?:设计|规范)?要求)?',text):return 'positive'
   if text in negative or re.fullmatch(r'(?:未|不|不能|无法)(?:完全)?(?:满足|达到|符合)(?:(?:设计|规范)?要求)?',text):return 'negative'
   return text
  return verdict(actual)==verdict(expected)
 if cell=='G29':tolerance=max(1e-8,abs(expected)*2e-5)
 elif cell in TEMPERATURE_CELLS:tolerance=.02
 elif cell in LOG_PRESSURE_CELLS:tolerance=.001
 elif cell in TRANSFER_CELLS:tolerance=max(1e-8,abs(expected)*.005)
 elif cell is not None:tolerance=max(1e-8,abs(expected)*.005)
 else:tolerance=max(1e-8,abs(expected)*2e-5)
 return isinstance(actual,(int,float))and not isinstance(actual,bool)and math.isfinite(actual)and abs(actual-expected)<=tolerance


def recalc(path,directory):
 errors=[]
 for attempt in range(2):
  out=directory/f'out-{attempt}';out.mkdir()
  try:result=subprocess.run(['libreoffice',f'-env:UserInstallation=file://{directory}/profile-{attempt}','--headless','--convert-to','xlsx','--outdir',str(out),str(path)],capture_output=True,text=True)
  except subprocess.TimeoutExpired:errors.append('Spreadsheet engine timeout');continue
  if not result.returncode and (out/path.name).exists():return openpyxl.load_workbook(out/path.name,data_only=True)
  errors.append(result.stdout+result.stderr)
 raise RuntimeError('Spreadsheet engine failed after isolated retry: '+' | '.join(errors))


def measure(source,name,changes,bindings):
 with tempfile.TemporaryDirectory(prefix='original-tower-score-')as tmp:
  tmp=Path(tmp);w=openpyxl.load_workbook(source)
  for cell,value in changes.items():w['Sheet1'][cell]=value
  path=tmp/'candidate.xlsx';w.save(path);actual=recalc(path,tmp)['Sheet1'];source_expected=calculate(BASE|changes)
  selection_matches=equal(actual['E96'].value,source_expected['E96'],'E96')
  # A submitted selection can bind dependent arithmetic only after it agrees
  # with the independently calculated source-correct minimum selection.
  # Once the submitted selector is within the published tolerance, bind the
  # dependent chain to the independently computed source selection.  Passing a
  # tolerant entry gate must not fall through the reference function's exact
  # lookup and turn every dependent expectation into None.
  conditional=calculate(BASE|changes,source_expected['E96'],True) if selection_matches else source_expected
  expected={cell:conditional[cell]if cell in SELECTED_NUMERIC_CELLS else value for cell,value in source_expected.items()}
  return name,{cell:{'expected':value,'source_expected':source_expected[cell],
      'conditional_on_selected_ratio':cell in SELECTED_NUMERIC_CELLS and selection_matches,
      'selection_matches_source':selection_matches,
      'carriers':{carrier:{'ok':equal(actual[carrier].value,value,cell),'actual':actual[carrier].value}for carrier in bindings[cell]}}
      for cell,value in expected.items()}


def score(source):
 source=Path(source)
 if not source.is_file():return {'reward':0.,'rewards':{'strict':0.,'lenient':0.},'error':'Missing /workspace/output/cooling_tower.xlsx'}
 w=openpyxl.load_workbook(source)
 if w.sheetnames[:3]!=['Sheet1','Sheet2','Sheet3']:raise ValueError('Preserve the original three worksheets')
 if w._external_links:raise ValueError('External workbook links are not supported')
 s=w['Sheet1']
 for cell,value in BASE.items():
  actual=s[cell].value
  if cell in INPUT_FORMULAS and actual==INPUT_FORMULAS[cell]:continue
  if not equal(actual,value):raise ValueError(f'Preserve original input {cell}')
 for sheet in w:
  for row in sheet:
   for c in row:
    if c.data_type=='f'and any(token in c.value.upper()for token in ['WEBSERVICE(','HYPERLINK(','DDE(','HTTP:','HTTPS:','FILE:']):raise ValueError('External spreadsheet side effects are not supported')
 bindings=carrier_bindings(w)
 with concurrent.futures.ThreadPoolExecutor(max_workers=len(SCENARIOS))as executor:
  results=dict(executor.map(lambda kv:measure(source,*kv,bindings),SCENARIOS.items()))
 for cell,carriers in bindings.items():
  selected=max(carriers,key=lambda carrier:sum(result[cell]['carriers'][carrier]['ok']for result in results.values()))
  for result in results.values():result[cell].update(result[cell]['carriers'][selected],carrier=selected)
 orientation=bind_water_grid_orientation(results)
 fan_bases=bind_fan_bases(results)
 items={}
 params=json.loads((Path(__file__).parent/'scoring_params.json').read_text())
 weights=params['positive_weights'];coefficients=params['deduction_coefficients'];lenient_required=params['lenient_required'];owner_contract=params['owner_contract']
 if set(weights)!=set(GROUPS)or abs(sum(weights.values())-1)>1e-12:raise RuntimeError('Invalid scoring parameter vocabulary or weight sum')
 if set(owner_contract)!=set(GROUPS):raise RuntimeError('Owner contract vocabulary mismatch')
 for name,g in GROUPS.items():
  contract=owner_contract[name]
  if contract!={'weight':weights[name],'cell_count':len(g['cells']),'aggregation':'complete_prerequisite_chain'}:raise RuntimeError('Owner contract mismatch: '+name)
 for name,g in GROUPS.items():
  passed={c:all(result[c]['ok']for result in results.values())for c in g['cells']}
  items[name]={'weight':weights[name],'completion':float(all(passed.values())),'aggregation':owner_contract[name]['aggregation'],'atomic_pass':passed}
 decision_failures={name:{c:data[c]for c in DECISION_CELLS if not data[c]['ok']}for name,data in results.items()}
 selected_chain=['E96']+sorted(SELECTED_NUMERIC_CELLS)
 missing_feasible_chains={name:{'source_selection':data['E96']['source_expected'],'missing_cells':[c for c in selected_chain if data[c]['actual']in(None,'')]}
     for name,data in results.items()if data['E96']['source_expected']is not None and all(data[c]['actual']in(None,'')for c in selected_chain)}
 decision_failed=any(decision_failures.values());structure_failures=source_integrity(w)
 label_failures=[failure for failure in structure_failures if 'cell'in failure]
 references=set()
 for chart in s._charts:
  for series in chart.series:
   for field in ['val','yVal']:
    value=getattr(series,field,None);reference=getattr(value,'numRef',None)
    if reference is not None:references.add(reference.f.replace("'",'').replace('$',''))
 chart_ok=all(reference in references for reference in ['Sheet1!C81:G81','Sheet1!C83:G83'])
 material=Path('/workspace/materials/workspace.xlsx')
 if not material.exists():material=Path('/reference/materials/workspace.xlsx')
 if not material.exists():material=Path(__file__).resolve().parent.parent/'environment/workspace/materials/workspace.xlsx'
 original=openpyxl.load_workbook(material,data_only=False)
 candidate_claims=[{'sheet':sheet.title,'cell':cell.coordinate,'value':cell.value}for sheet in w for row in sheet for cell in row if isinstance(cell.value,str)]
 source_claims=[{'sheet':sheet.title,'cell':cell.coordinate,'value':cell.value}for sheet in original for row in sheet for cell in row if isinstance(cell.value,str)and cell.data_type!='f']
 semantic=adjudicate({'claims':candidate_claims,'baseline':{c:results['baseline'][c]['actual']for c in ['E96','H96','H102','E103','B125','D125']}},{'issued_text':source_claims,'instruction':'Use only workbook data; no external catalog or standard is supplied.'},hashlib.sha256(source.read_bytes()).hexdigest())
 if set(semantic['items'])!=set(params['semantic_required']):raise RuntimeError('Semantic requirement vocabulary mismatch')
 semantic_ok=all(item['fraction']==1 for item in semantic['items'].values())
 damages=[]
 decision_error_count=sum(len(rows) for rows in decision_failures.values())
 decision_total=len(results)*len(DECISION_CELLS)
 if decision_failed:
  damages.append({'key':'thermal_selection_and_feasibility','item_ids':['D_THERMAL_DECISION'],
   'coefficient':max(coefficients['D_THERMAL_DECISION'],1-.7*decision_error_count/decision_total),
   'evidence':{'decision_failures':decision_failures,'missing_feasible_chains':missing_feasible_chains,
               'error_count':decision_error_count,'decision_count':decision_total}})
 if structure_failures:damages.append({'key':'original_labels_and_units','item_ids':['D_SOURCE_STRUCTURE'],'evidence':structure_failures})
 if not chart_ok:damages.append({'key':'thermal_comparison_chart','item_ids':['D_COMPARISON_CHART'],'evidence':{'references':sorted(references)}})
 if not semantic_ok:damages.append({'key':'open_claim_scope_or_source_fidelity','item_ids':['D_OPEN_SEMANTIC'],'evidence':semantic})
 positive=sum(x['weight']*x['completion']for x in items.values())
 retention=math.prod(event.get('coefficient',min(coefficients[k]for k in event['item_ids']))for event in damages)
 strict=positive*retention
 if abs(strict-1)<1e-12:strict=1.
 strict_requirements={
  'air_state_and_water_saturation':all(items[k]['completion']==1 for k in ['P01','P02']),
  'thermal_calculations_and_packing':items['P03']['completion']==1,
  'minimum_feasible_selection_and_verdicts':not decision_failed,
  'air_path_and_independent_coefficients':all(items[k]['completion']==1 for k in ['P08','P09']),
  'aerodynamic_resistance':items['P10']['completion']==1,
  'fan_pressure_and_shaft_power':items['P11']['completion']==1,
  'installed_specific_power':items['P12']['completion']==1,
  'original_labels_and_units':not structure_failures,
  'original_comparison_chart':chart_ok,
 }
 must=minimum_usable(results,decision_failed,label_failures,chart_ok)
 must['open_claim_scope']=semantic_ok
 if len(lenient_required)!=len(set(lenient_required))or set(lenient_required)!=set(must):raise RuntimeError('Lenient requirement vocabulary mismatch')
 lenient=float(all(must[key]for key in lenient_required));failed=[key for key in lenient_required if not must[key]]
 ledger={'schema_version':'pd-ledger-v1','positive_completion':{k:v['completion']for k,v in items.items()},'positive_weights':weights,'deduction_coefficients':coefficients,'damage_instances':damages,'positive_earned':positive,'retention':retention,'final_score':strict,'lenient_evaluation':{'policy':'task_specific_binary_must_haves','required_ids':lenient_required,'must_have':must,'failed_ids':failed}}
 return {'version':'cooling-tower-engineering-v10','reward':strict,'rewards':{'strict':strict,'lenient':lenient},'items':items,'must_haves':must,'strict_requirements':strict_requirements,'semantic_judge':semantic,'lenient_policy':{'required_ids':lenient_required,'relative_tolerance':.05,'aggregation':'binary_minimum_operational_chains_across_all10_scenarios','intermediate_policy':'Detailed intermediate accuracy remains strict-owned; indispensable selected-case/component values must be live, finite and positive, while operative thermal/pressure/power results and decisions must agree.'},'scoring_ledger':ledger,'decision_failures':decision_failures,'missing_feasible_chains':missing_feasible_chains,'source_structure_failures':structure_failures,'water_grid_orientation':orientation,'fan_quantity_bases':fan_bases,'carrier_bindings':bindings,'scenario_measurements':results,'scenario_failures':{name:{c:v for c,v in data.items()if not v['ok']}for name,data in results.items()}}


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--artifact',default='/workspace/output/cooling_tower.xlsx');parser.add_argument('--logs',default='/logs/verifier');args=parser.parse_args();logs=Path(args.logs);logs.mkdir(parents=True,exist_ok=True)
 system=False
 try:result=score(args.artifact)
 except Exception as error:
  system=isinstance(error,(RuntimeError,OSError,subprocess.TimeoutExpired));result=({'status':'UNMEASURED','error':type(error).__name__+': '+str(error),'error_kind':'system','valid_for_model_statistics':False}if system else{'reward':0.,'rewards':{'strict':0.,'lenient':0.},'error':type(error).__name__+': '+str(error),'error_kind':'artifact','valid_for_model_statistics':True})
 if system:
  for name in ['reward.json','reward_detail.json','reward.txt','reward_strict.txt','reward_lenient.txt']:(logs/name).unlink(missing_ok=True)
  (logs/'scoring_error.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(result['error'],file=sys.stderr);raise SystemExit(1)
 (logs/'reward.json').write_text(json.dumps({'reward':result['reward'],'rewards':result['rewards']},ensure_ascii=False,indent=2)+'\n');(logs/'reward_detail.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'reward':result['reward'],'rewards':result['rewards'],'error':result.get('error')},ensure_ascii=False))
 for name,value in [('reward.txt',result['reward']),('reward_strict.txt',result['rewards']['strict']),('reward_lenient.txt',result['rewards']['lenient'])]:(logs/name).write_text(str(value)+'\n')


if __name__=='__main__':main()

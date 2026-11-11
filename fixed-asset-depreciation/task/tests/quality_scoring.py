"""Deterministic financial-owner aggregation and shared strict settlement."""
import json
from pathlib import Path

import openpyxl

from runtime.business_metrics import accepted,extract,mean
from runtime.business_metrics import sha

OWNERS={
 'P01':'Four-method depreciation engine: assumptions, schedules, workload, openings and reporting balances',
 'P03':'Monthly departmental expense attribution',
 'P04':'Historical departmental depreciation flows',
 'P05':'Cutoff departmental financial stocks',
 'P06':'Category and global summary indicators, expense totals and reconciliation',
 'P07':'Opening source admissibility: keyed record, numeric amount and basis bound',
 'P08':'Visible invalid asset, master-data, workload and transfer inputs',
 'P09':'Routine maintenance within configured asset and dictionary capacity',
 'P10':'Preserved business inputs, workbook structure and offline formulas'}


def summary_accepted(check,cutoff):
    if check['error']:return False
    address=check['cell'];col=''.join(x for x in address if x.isalpha())
    if address=='B6' or col=='B' and address not in ('B7','B8','B9','B10','B14','B15'):
        tolerance=1e-9
    elif address=='B14':tolerance=12*480*.01/17033000
    elif col in ('E','F') or address in ('B9','B10'):tolerance=12*480*.01
    elif col=='D' or address=='B8':tolerance=12*cutoff*.01
    elif address=='B15':tolerance=12*12*.01
    else:tolerance=.01
    return abs(check['actual']-check['expected'])<=tolerance+1e-7


def completion(artifact,material_path,valid_folder,diagnostic_report,source_report,semantic_decision,scenario_path):
    artifact,material_path,valid_folder=Path(artifact),Path(material_path),Path(valid_folder)
    material=openpyxl.load_workbook(material_path)
    scenarios=json.loads(Path(scenario_path).read_text())['scenarios']
    semantic=json.loads(Path(semantic_decision).read_text())['decisions']
    decisions={row['scenario_id']:row for row in semantic}
    if len(decisions)!=44 or any(row['status']!='measured' or row['completion'] not in (0,1) for row in semantic):
        raise RuntimeError('Semantic diagnoses remain unresolved')
    raw=extract({'id':'candidate','artifact':str(artifact),'valid_observations':str(valid_folder),
        'diagnostic_observations':str(diagnostic_report),'diagnostic_decisions':decisions},scenarios,material)
    original=raw['completion']
    stocks=[];totals=[]
    for scenario in scenarios:
        if scenario['family'] not in ('baseline','periods'):continue
        observation=json.loads((valid_folder/scenario['id']/'observation.json').read_text())
        cutoff=next((v[2] for v in scenario['changes'] if v[1]=='B7'),6)
        stock=[];total=[]
        for check in observation['checks']:
            col=''.join(c for c in check['cell'] if c.isalpha())
            row=int(''.join(c for c in check['cell'] if c.isdigit()))
            passed=accepted(check,cutoff,12)
            if check['owner']=='dashboard' and row>=30 and col in ('C','E','F'):
                if check['expected']!=0 or not passed:stock.append(passed)
            elif check['owner']=='reconciliation' or check['owner']=='dashboard' and row<30:
                total.append(passed)
        stocks.append(mean(stock));totals.append(mean(total))
    supplementary=json.loads(Path(source_report).read_text())
    if supplementary['phase']!='observed' or not supplementary['source_unchanged'] or len(supplementary['scenarios'])!=7 or supplementary['candidate_sha256']!=sha(artifact):
        raise RuntimeError('Supplementary source measurement is incomplete')
    flows=[];category_stocks=[];summaries=[]
    for scenario in supplementary['scenarios']:
        cutoff=1 if scenario['id']=='report-january' else 12 if scenario['id']=='report-december' else 3 if scenario['id']=='acquisition-year-march' else 6
        flow=[];stock=[];summary=[]
        for check in scenario['checks']:
            passed=summary_accepted(check,cutoff)
            col=''.join(c for c in check['cell'] if c.isalpha())
            if check['owner']=='dashboard-summary':summary.append(passed)
            elif col=='D':flow.append(passed)
            else:stock.append(passed)
        flows.append(mean(flow));category_stocks.append(mean(stock));summaries.append(mean(summary))
    input_checks=next(s['source_input_checks'] for s in supplementary['scenarios'] if s['id']=='baseline')
    preservation=mean([v['passed'] for v in input_checks])
    asset_period=[d['completion'] for d in semantic if '-row-' in d['scenario_id'] or d['scenario_id'].startswith('report-')]
    master=[decisions[k]['completion'] for k in ('asset-duplicate','category-duplicate','department-duplicate')]
    workload=[d['completion'] for d in semantic if d['scenario_id'].startswith('workload-')]
    transfers=[d['completion'] for d in semantic if d['scenario_id'].startswith('transfer-')]
    openings=[d['completion'] for d in semantic if d['scenario_id'].startswith('opening-') and d['scenario_id']!='opening-above-basis']
    time_engine=min(mean([original['P01'],original['P02'],original['P03']]),original['P05'],original['P06'])
    result={
        'P01':(3*time_engine+original['P04'])/4,
        'P03':original['P07'],'P04':original['P08'],'P05':mean(stocks),
        'P06':mean([mean(totals),mean(summaries),mean(flows),mean(category_stocks)]),
        'P07':min(mean(openings),decisions['opening-above-basis']['completion']),
        'P08':mean([mean(asset_period),mean(master),mean(workload),mean(transfers)]),
        'P09':original['P10'],'P10':min(original['P14'],preservation)}
    material.close()
    return {'completion':result,'evidence':{'financial_metrics':raw['evidence'],
        'semantic_decisions':semantic,'source_preservation':preservation,
        'department_stock_scenarios':stocks,'category_stock_scenarios':category_stocks,
        'summary_scenarios':summaries,'category_flow_scenarios':flows,'total_scenarios':totals}}


def settle(measured,parameters):
    weights=parameters['weights']
    if set(weights)!=set(OWNERS) or abs(sum(weights.values())-1)>1e-12:
        raise RuntimeError('Invalid frozen scoring contract')
    earned=min(1.0,max(0.0,sum(weights[key]*measured['completion'][key] for key in weights)))
    return {'rewards':{'strict':earned},'positive_earned':earned,'completion':measured['completion'],
            'evidence':measured['evidence']}

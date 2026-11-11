"""Independent binary minimum-usable-result checks for Bench."""
import json
from pathlib import Path
import re

import openpyxl

from runtime.business_metrics import accepted


def evaluate(artifact,material_path,valid_folder,source_report,semantic_decision,quality_completion=None):
    artifact,valid_folder=Path(artifact),Path(valid_folder)
    material=openpyxl.load_workbook(material_path)
    candidate=openpyxl.load_workbook(artifact)
    supplementary=json.loads(Path(source_report).read_text())
    if supplementary['phase']!='observed' or not supplementary['source_unchanged']:
        raise RuntimeError('Missing native source evidence')
    source_inputs=next(s['source_input_checks'] for s in supplementary['scenarios'] if s['id']=='baseline')
    if not source_inputs:raise RuntimeError('Business input preservation was not measured')
    native=(candidate.sheetnames==material.sheetnames and not candidate.vba_archive and not candidate._external_links
            and all(c['passed'] for c in source_inputs))
    details={'native_integrity':{'passed':int(native),'source_input_checks':len(source_inputs),
        'source_input_failures':[c for c in source_inputs if not c['passed']]}}
    baseline=json.loads((valid_folder/'baseline/observation.json').read_text())
    baseline_values={(c['sheet'],c['cell']):c['expected'] for c in baseline['checks']}
    checks=[]
    for scenario,cutoff in [('baseline',6),('report-january',1)]:
        observation=json.loads((valid_folder/scenario/'observation.json').read_text())
        if observation['phase']!='observed':raise RuntimeError('Four-method bridge was not measured')
        for c in observation['checks']:
            row=int(re.search(r'\d+',c['cell'])[0]);col=re.match(r'[A-Z]+',c['cell'])[0]
            monthly=col in [openpyxl.utils.get_column_letter(30+2*m) for m in range(1,13)]
            if c['owner'].startswith('method:') and row in (5,6,7,8) and (monthly or col in ('BC','BD','BE','CC')):
                checks.append({'scenario':scenario,**c,'accepted':accepted(c,cutoff,12)})
    if len(checks)!=128:raise RuntimeError('Representative financial evidence incomplete')
    details['four_method_bridge']={'passed':int(all(c['accepted'] for c in checks)),
        'check_count':len(checks),'failures':[c for c in checks if not c['accepted']]}
    transfer=json.loads((valid_folder/'department-april-transfer/observation.json').read_text())
    if transfer['phase']!='observed':raise RuntimeError('Ownership bridge was not measured')
    checks=[]
    for c in transfer['checks']:
        row=int(re.search(r'\d+',c['cell'])[0]);col=re.match(r'[A-Z]+',c['cell'])[0]
        relevant=c['owner']=='expense-allocation' or c['owner']=='dashboard' and row>=30 and col in ('C','D','E','F')
        if relevant and abs(c['expected']-baseline_values[(c['sheet'],c['cell'])])>.005:
            checks.append({**c,'accepted':accepted(c,6,12)})
    if not checks:raise RuntimeError('No transfer-affected business outputs were measured')
    details['period_ownership']={'passed':int(all(c['accepted'] for c in checks)),
        'check_count':len(checks),'failures':[c for c in checks if not c['accepted']]}
    department=material.worksheets[2]['J5'].value
    department_rows=[r for r in range(35,45) if material.worksheets[1].cell(r,3).value==department]
    if len(department_rows)!=1:raise RuntimeError('Representative department source is not unique')
    dashboard_row=department_rows[0]-5
    late=json.loads((valid_folder/'service-after-year-twenty/observation.json').read_text())
    if late['phase']!='observed':raise RuntimeError('Report-year department bridge was not measured')
    checks=[{**c,'accepted':accepted(c,6,12)} for c in late['checks'] if c['owner']=='dashboard'
            and c['cell'] in [col+str(dashboard_row) for col in ('C','E','F')]]
    if len(checks)!=3:raise RuntimeError('Late-period departmental stock evidence incomplete')
    details['year_department_bridge']={'passed':int(all(c['accepted'] for c in checks)),
        'representative_source_asset':material.worksheets[2]['B5'].value,'department':department,
        'check_count':len(checks),'failures':[c for c in checks if not c['accepted']]}
    semantic=json.loads(Path(semantic_decision).read_text())['decisions']
    diagnoses={c['scenario_id']:c for c in semantic}
    admission=diagnoses['opening-above-basis']
    if admission['status']!='measured' or admission['completion'] not in (0,1):
        raise RuntimeError('Opening admission diagnosis unresolved')
    opening=json.loads((valid_folder/'opening-near-basis/observation.json').read_text())
    checks=[]
    for c in opening['checks']:
        row=int(re.search(r'\d+',c['cell'])[0]);col=re.match(r'[A-Z]+',c['cell'])[0]
        monthly=col in [openpyxl.utils.get_column_letter(30+2*m) for m in range(1,13)]
        if c['owner'].startswith('method:') and row==8 and (monthly or col in ('BC','BD','BE','CC')):
            checks.append({**c,'accepted':accepted(c,6,12)})
    if len(checks)!=16:raise RuntimeError('Remaining workload quota was not fully measured')
    details['safe_workload_opening']={'passed':int(admission['completion']==1 and all(c['accepted'] for c in checks)),
        'admission':admission,'check_count':len(checks),'failures':[c for c in checks if not c['accepted']]}
    quality_completion=quality_completion or {}
    for key,owner in [('global_summary_correct','P06'),('all_required_diagnostics','P08'),('configured_capacity_maintenance','P09')]:
        details[key]={'passed':int(float(quality_completion.get(owner,0))>=1.0),'owner':owner,
                      'completion':float(quality_completion.get(owner,0))}
    candidate.close();material.close()
    return {'reward':int(all(item['passed']==1 for item in details.values())),
            'must_have':details,'failed_ids':[key for key,value in details.items() if value['passed']!=1]}

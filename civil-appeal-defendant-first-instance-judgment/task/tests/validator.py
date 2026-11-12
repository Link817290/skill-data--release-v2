import sys,json,tempfile,subprocess,math
import re
from pathlib import Path
from semantic_judge import adjudicate,OBJECTIVE
HERE=Path(__file__).parent
workspace=Path(sys.argv[1] if len(sys.argv)>1 else '/workspace')
artifact=workspace if workspace.is_file() else workspace/'artifacts/civil-appeal-petition.md'
if not artifact.is_file() or not artifact.read_bytes().strip():
    print(json.dumps({'status':'candidate_missing','rewards':{'strict':0,'lenient':0},'final_score':0}));sys.exit(0)
try:
    candidate=artifact.read_text(encoding='utf-8')
except UnicodeError:
    print(json.dumps({'status':'candidate_unreadable','rewards':{'strict':0,'lenient':0},'final_score':0}));sys.exit(0)
contract=json.loads((HERE/'rubric-contract.json').read_text())
with tempfile.TemporaryDirectory(prefix='civil-score-') as tmp:
    out=Path(tmp)/'detail.json'
    subprocess.run([sys.executable,str(HERE/'pjroot/task/tests/program_judge/task_judge.py'),str(artifact),'--contract',str(HERE/'rubric-contract.json'),'--json',str(out)],check=True,stdout=subprocess.DEVNULL)
    ledger=json.loads(out.read_text())
source=next((HERE/'pjroot/materials_text').glob('*.txt')).read_text()+'\nPROFESSIONAL RULES\n'+(HERE/'professional-rules.md').read_text()
decision=adjudicate(candidate,source)
fractions={key:value['fraction'] for key,value in decision['items'].items()}
dependency_notes={}
if fractions.get('D02'):
    fractions['P01']=0
    dependency_notes['P01']='Appeal-scope credit is unavailable because the adopted relief overreaches the admitted interest or whole judgment.'
if fractions['D03_AMOUNT']:
    for key in ['P04','P05','P13']:
        fractions[key]=0
        dependency_notes[key]='Amount-merits credit is unavailable because the filing adopts the adverse quotation/full-completion conclusion.'
    fractions['P03']=min(fractions['P03'],.5)
    dependency_notes['P03']='Disposition credit is capped because the filing concedes the disputed amount premise.'
if fractions['D03_DATE']:
    for key in ['P09','P11']:
        fractions[key]=0
        dependency_notes[key]='Interest-ground credit is unavailable because the filing adopts April21 as the correct handover or interest date.'
    fractions['P03']=min(fractions['P03'],.5)
    dependency_notes['P03']='Disposition credit is capped because the filing concedes the disputed date premise.'
for item in ledger['items']:
    v=decision['items'][item['id']];fraction=fractions[item['id']]
    reason=v['reason']
    if item['id'] in dependency_notes:reason+=' '+dependency_notes[item['id']]
    item.update(program_fraction=item['fraction'],program_reason=item['reason'],fraction=fraction,earned=item['weight']*fraction,reason=reason,semantic_evidence=v)
ledger['program_penalty_instances']=ledger['penalty_instances']
penalties=[p for p in ledger['penalty_instances'] if all(i in OBJECTIVE for i in p['item_ids'])]
coefficients={item['id']:item['penalty_coefficient'] for item in contract['deduction_items']}
for subtype,key,root in [
    ('D04_ATTRIBUTION','D04','misstated_staff_attribution'),
    ('D06_DELIVERY_DATE','D06','fabricated_delivery_day'),
]:
    triggered=decision['items'][subtype]['fraction']
    if subtype=='D04_ATTRIBUTION' and triggered:
        explicit_wrong_role=re.compile(r'(被上诉人|原告|B公司)[^。；;]{0,12}?(员工|工作人员|一方)')
        triggered=any(explicit_wrong_role.search(quote) for quote in decision['items'][subtype]['quotes'])
    if triggered:
        penalties.append({'damage_instance_key':root,'causal_root_ids':[root],'item_ids':[key],'penalty_coefficient':coefficients[key],'semantic_evidence':decision['items'][subtype]})
for item in contract['deduction_items']:
    key=item['id']
    if key=='D03':
        for subtype,root in [('D03_AMOUNT','concede_amount'),('D03_DATE','concede_date')]:
            if decision['items'][subtype]['fraction']:
                penalties.append({'damage_instance_key':root,'causal_root_ids':[root],'item_ids':['D03'],'penalty_coefficient':item['penalty_coefficient'],'semantic_evidence':decision['items'][subtype]})
        continue
    if key=='D16':
        if decision['items'][key]['fraction']:
            penalties.append({'damage_instance_key':'contradicts_own_record_position','causal_root_ids':['R-own-position'],'item_ids':[key],'penalty_coefficient':item['penalty_coefficient'],'semantic_evidence':decision['items'][key]})
        continue
    if key not in decision['items'] or not decision['items'][key]['fraction']:continue
    existing=[p for p in ledger['penalty_instances'] if key in p['item_ids']]
    if existing:
        penalties.extend({**p,'semantic_evidence':decision['items'][key]} for p in existing)
    else:
        penalties.append({'damage_instance_key':key,'item_ids':[key],'penalty_coefficient':item['penalty_coefficient'],'semantic_evidence':decision['items'][key]})
# Each semantic subtype names a specific causal claim. Shared evidence locations
# cannot merge independent amount, handover-date or own-record errors.
ledger['penalty_instances']=penalties
ledger['program_deduction_items']=ledger.pop('deduction_items')
ledger['program_penalty_occurrences']=ledger.pop('penalty_occurrences')
ledger['deduction_items']=[{'id':i['id'],'state':'triggered' if any(i['id'] in p['item_ids'] for p in penalties) else 'not_triggered','occurrences':[p for p in penalties if i['id'] in p['item_ids']]} for i in contract['deduction_items']]
ledger['penalty_occurrences']=[{**p,'id':key} for p in penalties for key in p['item_ids']]
ledger['retention_multiplier']=math.prod(p['penalty_coefficient'] for p in penalties)
ledger['positive_earned']=sum(i['earned'] for i in ledger['items']);ledger['final_score']=ledger['positive_earned']*ledger['retention_multiplier']
ledger['penalty_rate']=1-ledger['retention_multiplier'];ledger['score_loss']=ledger['positive_earned']-ledger['final_score']
ledger['semantic_judge']=decision
ledger['semantic_completion_checks']={k:dict(v) for k,v in decision['items'].items() if k.startswith('C_')}
ledger['completion_checks']={k:dict(v) for k,v in ledger['semantic_completion_checks'].items()}
settled={item['id']:item['fraction'] for item in ledger['items']}
core_merits_damage={'D03','D04','D06','D07','D13','D14','D16'}
damage_ids={key for penalty in penalties for key in penalty['item_ids']}
amount_merits=max(settled['P04'],settled['P05'],settled['P13'])>=.5
interest_merits=max(settled['P09'],settled['P11'])>=.5
derived_merits=float(amount_merits and interest_merits and not damage_ids.intersection(core_merits_damage))
ledger['completion_checks']['C_MERITS']['semantic_fraction']=ledger['completion_checks']['C_MERITS']['fraction']
ledger['completion_checks']['C_MERITS']['fraction']=derived_merits
ledger['completion_checks']['C_MERITS']['reason']+=' Final completion settles from the same atomic amount and interest merits and core-damage predicates as strict.'
local_quality_items={'D11','D12'}
blocking_penalties=[p for p in penalties if any(key not in local_quality_items for key in p['item_ids'])]
ledger['lenient_blocking_penalties']=blocking_penalties
ledger['rewards']={'strict':ledger['final_score'],'lenient':float(all(v['fraction']==1 for v in ledger['completion_checks'].values()) and not blocking_penalties)}
ledger['status']='measured'
print(json.dumps(ledger,ensure_ascii=False))

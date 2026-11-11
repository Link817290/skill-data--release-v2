"""Select governing full-state revisions; no task-specific action interpretation."""
import argparse,csv,json
from collections import defaultdict
from pathlib import Path

def reconcile(rows,entity='order_id',event='event_id',revision='revision',metadata=('received_at',)):
    messages=defaultdict(list)
    for row in rows:messages[row[event]].append(row)
    conflicts=set();unique=[];duplicate_deliveries=0
    for records in messages.values():
        if any(row!=records[0] for row in records):conflicts.update(row[entity] for row in records)
        else:unique.append(records[0]);duplicate_deliveries+=len(records)-1
    groups=defaultdict(list)
    for row in unique:groups[row[entity]].append(row)
    output=[]
    for key in sorted({row[entity] for row in rows}):
        items=groups[key]
        if key in conflicts:output.append(dict(entity=key,status='message_conflict',events=sorted({r[event] for r in rows if r[entity]==key})));continue
        latest=max(int(row[revision]) for row in items);selected=[row for row in items if int(row[revision])==latest]
        ignore={event,*metadata}
        states={json.dumps({k:v for k,v in row.items() if k not in ignore},sort_keys=True) for row in selected}
        result=dict(entity=key,revision=latest,events=sorted(row[event] for row in selected),status='selected' if len(states)==1 else 'revision_conflict')
        if len(states)==1:result['record']=selected[0]
        output.append(result)
    return dict(input_rows=len(rows),unique_messages=len(unique),duplicate_deliveries=duplicate_deliveries,entities=output)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output',type=Path);p.add_argument('--entity',default='order_id');p.add_argument('--event',default='event_id');p.add_argument('--revision',default='revision');p.add_argument('--metadata',nargs='*',default=['received_at']);a=p.parse_args()
    with a.input.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    result=reconcile(rows,a.entity,a.event,a.revision,a.metadata);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')

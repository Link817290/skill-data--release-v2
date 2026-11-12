"""Conditional review calculations, not environmental-compliance decisions."""
from decimal import Decimal,InvalidOperation
from datetime import date
from pathlib import Path
import argparse,csv,json,unicodedata

def number(value,name,positive=False):
    if isinstance(value,bool):raise ValueError(name+' cannot be Boolean')
    try:x=Decimal(str(value))
    except (InvalidOperation,ValueError):raise ValueError(name+' must be a decimal number')
    if not x.is_finite() or x<0 or positive and x<=0:
        raise ValueError(name+' must be finite and '+('positive' if positive else 'nonnegative'))
    return x
def label(value,name):
    if not isinstance(value,str) or not value.strip():raise ValueError(name+' is required')
    return unicodedata.normalize('NFKC',value).strip().casefold()
def rate(concentration,flow):
    c=number(concentration,'concentration_mg_m3');q=number(flow,'flow_m3_h')
    return {'rate_kg_h':str(c*q/Decimal(1000000)),
            'basis':'Conditional on compatible concentration and flow reference conditions and sampling event.',
            'compliance':'not_assessed'}
def load(annual,days,actual):
    capacity=number(annual,'annual_capacity',True);working=number(days,'working_days',True)
    if working!=working.to_integral_value():raise ValueError('working_days must be an integer')
    daily=number(actual,'actual_daily')
    return {'design_daily':str(capacity/working),'load_percent':str(daily*working/capacity*100),
            'basis':'Same product and working calendar assumed; identity and actual stability not assessed.'}
def nd(limit):
    d=number(limit,'detection_limit',True)
    return {'lower':'0','lower_inclusive':True,'upper':str(d),'upper_inclusive':False,
            'unit':'Same unit as the supplied detection limit','value_is_measured_zero':False,
            'condition':'Use only where ND explicitly means below this detection limit; no substitution or compliance decision.'}
def efficiency(data):
    if not isinstance(data,dict):raise ValueError('pair must be an object')
    sides=[]
    for key in ['inlet','outlet']:
        side=data.get(key)
        if not isinstance(side,dict):raise ValueError(key+' must be an object')
        tags={k:label(side.get(k),key+'.'+k) for k in ['pair_id','pollutant','basis']}
        c=number(side.get('concentration_mg_m3'),key+'.concentration_mg_m3')
        q=number(side.get('flow_m3_h'),key+'.flow_m3_h')
        sides.append((tags,c*q/Decimal(1000000)))
    if sides[0][0]!=sides[1][0]:raise ValueError('pair identity, pollutant and reference basis must match')
    incoming,outgoing=sides[0][1],sides[1][1]
    if incoming==0:raise ValueError('zero inlet mass: removal efficiency undefined')
    percent=(incoming-outgoing)/incoming*100
    return {'inlet_kg_h':str(incoming),'outlet_kg_h':str(outgoing),'removal_percent':str(percent),
            'negative_efficiency':percent<0,'compliance':'not_assessed',
            'basis':'Conditional on supplied pairing metadata; metadata agreement does not prove valid or simultaneous sampling.'}
def read_rows(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames:raise ValueError('CSV header missing')
        return list(reader)
def coverage(events,logs):
    bykey={}
    for row in logs:
        process=label(row.get('process'),'operating.process')
        day=date.fromisoformat(row.get('date',''))
        key=(process,day.isoformat());bykey[key]=bykey.get(key,0)+1
    seen=set();results=[]
    for row in events:
        ident=label(row.get('event_id'),'event_id')
        if ident in seen:raise ValueError('monitoring event_id must be unique')
        seen.add(ident);process=label(row.get('process'),'monitoring.process')
        day=date.fromisoformat(row.get('date','')).isoformat()
        count=bykey.get((process,day),0)
        results.append({'event_id':row['event_id'],'process':row['process'],'date':day,
                        'operating_records':count,'date_covered':count>0})
    if not results:raise ValueError('monitoring event list is empty')
    return {'events':results,'uncovered_event_ids':[x['event_id'] for x in results if not x['date_covered']],
            'stability':'not_assessed','basis':'Exact process/date coverage only; time alignment, operating mode and log validity require review.'}
def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    r=sub.add_parser('rate');r.add_argument('--concentration-mg-m3',required=True);r.add_argument('--flow-m3-h',required=True)
    l=sub.add_parser('load');l.add_argument('--annual-capacity',required=True);l.add_argument('--working-days',required=True);l.add_argument('--actual-daily',required=True)
    n=sub.add_parser('nd');n.add_argument('--detection-limit',required=True)
    e=sub.add_parser('efficiency');e.add_argument('--pair-file',type=Path,required=True)
    c=sub.add_parser('coverage');c.add_argument('--monitoring',type=Path,required=True);c.add_argument('--operating',type=Path,required=True)
    a=p.parse_args()
    try:
        if a.command=='rate':result=rate(a.concentration_mg_m3,a.flow_m3_h)
        elif a.command=='load':result=load(a.annual_capacity,a.working_days,a.actual_daily)
        elif a.command=='nd':result=nd(a.detection_limit)
        elif a.command=='efficiency':result=efficiency(json.loads(a.pair_file.read_text(encoding='utf-8-sig')))
        else:result=coverage(read_rows(a.monitoring),read_rows(a.operating))
    except (ValueError,TypeError,OSError,OverflowError) as exc:p.error(str(exc))
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()

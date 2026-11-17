"""Evaluate explicit source predicates; missing evidence stays unresolved."""
import argparse,json,re
from datetime import date
from pathlib import Path
def match(data):
    observation=data['observation'];checks=[]
    def add(field,result,reason):checks.append(dict(field=field,result=result,reason=reason))
    for field,expected in data.get('equals',{}).items():
        actual=observation.get(field)
        add(field,None if actual is None or actual=='' else actual==expected,'identity')
    if data.get('date'):
        rule=data['date'];field=rule['field'];actual=observation.get(field)
        start=date.fromisoformat(rule['start']);end=date.fromisoformat(rule['end'])
        if start>end:raise ValueError('Reversed rule dates')
        try:value=date.fromisoformat(actual);result=start<=value<=end
        except (ValueError,TypeError):result=None
        add(field,result,'date interval')
    if data.get('code'):
        rule=data['code'];field=rule['field'];actual=observation.get(field)
        if rule['min']>rule['max']:raise ValueError('Reversed code interval')
        width=rule.get('width');digits=r'\d{'+str(width)+'}' if width else r'\d+'
        if actual is None or actual=='':result=None
        else:
            m=re.fullmatch(re.escape(rule['prefix'])+'('+digits+')',str(actual))
            result=bool(m and rule['min']<=int(m[1])<=rule['max'])
        add(field,result,'code interval')
    if not checks:raise ValueError('At least one identification predicate is required')
    status='outside' if any(c['result'] is False for c in checks) else ('review' if any(c['result'] is None for c in checks) else 'included')
    return dict(status=status,predicates=checks)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);a=p.parse_args();print(json.dumps(match(json.loads(a.input.read_text(encoding='utf-8'))),ensure_ascii=False))

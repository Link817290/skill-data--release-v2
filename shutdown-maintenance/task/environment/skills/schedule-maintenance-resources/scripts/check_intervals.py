import argparse,json,datetime as dt
def conflicts(rows):
    parsed=[]
    for r in rows:
        start=dt.datetime.fromisoformat(r['start']);end=dt.datetime.fromisoformat(r['end'])
        if end<=start:raise ValueError('Intervals must have positive duration')
        parsed.append((r['id'],start,end,set(r['resources'])))
    return [{'a':a[0],'b':b[0],'resources':sorted(a[3]&b[3])} for i,a in enumerate(parsed) for b in parsed[i+1:] if a[3]&b[3] and a[1]<b[2] and b[1]<a[2]]
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('schedule');a=p.parse_args();print(json.dumps(conflicts(json.load(open(a.schedule,encoding='utf8')))))

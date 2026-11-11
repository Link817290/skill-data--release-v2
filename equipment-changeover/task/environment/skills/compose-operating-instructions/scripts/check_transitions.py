import json,argparse
def inspect(graph):
    states=set(graph['states']);start=graph['start'];terminal=set(graph['terminal']);edges=graph['edges']
    if start not in states or not terminal<=states:raise ValueError('Undefined state')
    if any(a not in states or b not in states for a,b in edges):raise ValueError('Undefined transition endpoint')
    seen={start}
    while True:
        more={b for a,b in edges if a in seen}-seen
        if not more:break
        seen|=more
    return {'unreachable':sorted(states-seen),'reachable_terminal':sorted(terminal&seen)}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('graph');a=p.parse_args();print(json.dumps(inspect(json.load(open(a.graph,encoding='utf8')))))

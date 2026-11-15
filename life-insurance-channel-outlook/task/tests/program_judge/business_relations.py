"""Three-layer deterministic PDF adapter for the insurer's business relations."""
from __future__ import annotations
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
import fitz
from program_judge_runtime import Locator

CHANNELS = {'personal':r'个人(?:代理|营销)?(?:/个险)?(?:渠道)?|个险渠道',
            'bank':r'银保|银邮|银行(?:及邮政)?(?:兼业)?代理',
            'other':r'中介(?:代理)?(?:/其他)?|其他渠道|保险专业代理',
            'internet':r'互联网(?:渠道)?|网络渠道', 'group':r'团险(?:渠道)?'}
COMPONENT_POSITIVES = tuple(f'P{i:02d}' for i in range(1, 14))
MERGED_POSITIVES = {
    'P06': {'P06': .08, 'P07': .07, 'P08': .09, 'P09': .06},
    'P10': {'P10': .10, 'P11': .12},
}
NUM = r'[-+]?\d[\d,]*(?:\.\d+)?'
RANGE = re.compile(r'('+NUM+r')(?:—|–|－|~|～|至|到|-)'+'('+NUM+r')')
EXCLUDED = re.compile(r'候选(?:方案|结论|答案)|尚未采用|未采纳|不采纳|未决(?:方案|候选)|错误(?:示例|观点|结论)|驳回|仅供引用|引用示例|以下引文|不应得出|并非如此|不成立')

def canon(text):
    text=unicodedata.normalize('NFKC',text)
    text=re.sub(r'(?<=\d)\s+(?=\d)', '|', text)
    return re.sub(r'\s+','',text)

@dataclass
class Span:
    path: Path
    page: int
    offset: int
    raw: str
    text: str
    heading: str

def extract_raw(artifact):
    if artifact.is_dir():
        exact=artifact/'report.pdf'
        choices=[exact] if exact.is_file() else sorted(artifact.glob('*.pdf'))
    else:
        choices=[artifact] if artifact.is_file() and artifact.suffix.lower()=='.pdf' else []
    if len(choices)!=1:
        return dict(artifact=artifact,spans=[],state='ambiguous' if choices else 'confirmed_missing',error='Expected one final PDF')
    path=choices[0]
    try:
        with fitz.open(path) as doc:
            pages=[p.get_text(sort=True) for p in doc]
    except Exception as exc:
        return dict(artifact=artifact,spans=[],state='parse_failure',error=type(exc).__name__)
    if not any(p.strip() for p in pages):
        return dict(artifact=artifact,spans=[],state='parse_failure',error='No electronic PDF text')
    parts=[]; heading=''
    for page,text in enumerate(pages,1):
        for m in re.finditer(r'[^\n]+',text):
            raw=m.group().strip()
            if not raw: continue
            if re.match(r'^(?:[1-9]\.\d{1,2}(?!\d)(?!亿元|万元|%|元)|[一二三四五六七八九十]+[、.])',raw): heading=canon(raw)
            parts.append(Span(path,page,m.start(),raw,canon(raw),heading))
    spans=[]
    for i,part in enumerate(parts):
        local=[]; length=0
        for nxt in parts[i:]:
            if (nxt.heading!=part.heading and local) or length+len(nxt.text)>2400: break
            local.append(nxt); length+=len(nxt.text)
        raw='\n'.join(x.raw for x in local)
        spans.append(Span(path,part.page,part.offset,raw,canon(raw),part.heading))
    return dict(artifact=artifact,spans=spans,state='identified',error='',pages=pages)

def adopted(span):
    return not EXCLUDED.search(span.text) and not re.search(r'“[^”]{20,}”|「[^」]{20,}」',span.text)

def near(t,value,tolerance=.18,suffix='%'):
    return any(abs(float(m.group(1).replace(',',''))-value)<=tolerance for m in re.finditer('('+NUM+')'+suffix,t))

def amount(t,value):
    return (near(t,value,.025,r'亿元')
            or near(t,value*100,2.5,r'百万元')
            or near(t,value*1e4,25,r'万元')
            or near(t,value*1e8,2500000,r'元'))

def growth(t,value):
    direction=r'下降|下滑|回落|减少|负增长|收缩|降低' if value<0 else r'增长|上升|提升|增加|增幅|增速|提高'
    for m in re.finditer('(?:'+direction+r')[^\d。；%]{0,12}('+NUM+')%',t):
        if abs(abs(float(m.group(1).replace(',','')))-abs(value))<=.18: return True
    return near(t,value) and bool(re.search(r'同比|环比|增速',t))

def v(f,key,*names):
    return [float(f[key]['values'][n]) for n in names]

def specs(f):
    def g(k):
        a,b=v(f,k,'2025','2024'); return (a/b-1)*100
    out=[]
    def add(p,key,obj,value,mode='growth',scope=''):
        out.append(dict(pid=p,key=key,obj=obj,value=value,mode=mode,scope=scope))
    add('P01','income-growth',r'2025.*保险业务收入',g('annual.insurance_income'),scope=r'2024|56\.64')
    add('P01','profit-growth',r'净利润',g('annual.profit'),scope=r'2024.*2025|2025.*2024')
    add('P01','assets-growth',r'总资产(?!收益率)',g('annual.assets'),scope=r'2024.*2025|2025.*2024')
    for k,name in [('core','核心'),('comprehensive','综合')]:
        now,prior=v(f,'h1.'+k+'_solvency','quarter','previous_quarter')
        add('P03',k+'-uplift',name+r'.*(?:偿付|充足率)',now-prior,'pp',r'2026|二季度|上半年|H1')
    income=v(f,'annual.insurance_income','2025')[0]
    add('P04','participating-growth',r'分红',g('annual.participating'),scope='2025')
    for k,name in [('participating','分红'),('health','健康险')]:
        add('P04',k+'-share',name,v(f,'annual.'+k,'2025')[0]/income*100,'share')
    add('P05','first-year-growth',r'首年',g('annual.first_year'),scope='2025')
    add('P05','renewal-share',r'续年|续期',v(f,'annual.renewal','2025')[0]/income*100,'share','2025')
    for p,ch in [('P06','personal'),('P07','bank'),('P08','other'),('P09','internet'),('P09','group')]:
        first=v(f,'q1.'+ch,'quarter')[0]; second,total=v(f,'h1.'+ch,'quarter','ytd')
        add(p,ch+'-qoq',CHANNELS[ch],(second/first-1)*100,'quarter',r'2026|季度|上半年|H1')
        out[-1].update(first=first/1e8,second=second/1e8,total=total/1e8)
    add('P07','bank-historical',CHANNELS['bank'],g('annual.bank_post'),scope='2025')
    add('P08','intermediary-historical',CHANNELS['other'],g('annual.intermediary'),scope='2025')
    return out

def relation(s,t):
    if not re.search(s['obj'],t) or (s['scope'] and not re.search(s['scope'],t)): return False
    if s['mode']=='growth': return growth(t,s['value'])
    if s['mode']=='share': return bool(re.search(r'占|比重|比例',t)) and near(t,s['value'])
    if s['mode']=='pp': return near(t,s['value'],.1,r'(?:个?百分点|个[、,])') and bool(re.search(r'上升|提升|增加|提高',t))
    return (amount(t,s['second']) and (amount(t,s['first']) or amount(t,s['total'])) and re.search(r'一季度|Q1|上半年',t,re.I) and
            re.search(r'二季度|Q2',t,re.I) and (growth(t,s['value']) or
            (s['key']=='internet-qoq' and re.search(r'环比(?:回落|下降)',t))))

def bare_near(t,value,tolerance=.18):
    """Numeric relation inside a table whose unit is declared by the header or note."""
    return near(t,value,tolerance,'')

def forecast(span,ch):
    t=span.text
    if not re.search(CHANNELS[ch],t) or not re.search(r'预测|预计|情景|假设|推算|测算',t): return None
    if not re.search(r'依据|基于|假设|考虑|上半年.*下半年|下半年.*上半年|支撑|若.*则',t): return None
    out={}
    for year in (2026,2027):
        match=re.search(str(year)+r'年?[^。；]{0,70}?('+r'\d+(?:\.\d+)?'+r')(?:[—–－~～至到-]('+r'\d+(?:\.\d+)?'+r'))?亿元',t)
        if not match: return None
        lo=float(match[1]); hi=float(match[2] or lo)
        if not 0<lo<=hi<1000: return None
        out[year]=(lo,hi)
    return out

def table(span):
    t=span.text
    if not (re.search(r'2026E|2026年|2026预测',t) and re.search(r'2027E|2027年|2027预测',t) and re.search(r'合计|总计|总量',t)): return None
    rows={}
    aliases={**CHANNELS,'bank':r'银保/银邮渠道|银保|银邮|银行(?:及邮政)?(?:兼业)?代理',
             'total':r'合计(?:\(签单口径\))?|总计|签单保费总量'}
    for key,alias in aliases.items():
        options=[]
        for m in re.finditer(alias,t):
            part=t[m.end():]
            nexts=[n.start() for n in re.finditer('|'.join(aliases.values()),part) if n.start()>0]
            if nexts: part=part[:min(nexts)]
            ints=[(float(n[1].replace(',','')),float(n[2].replace(',',''))) for n in RANGE.finditer(part)]
            ints=[a for a in ints if 0<a[0]<=a[1]<1000]
            if len(ints)>=2: options.append(tuple(ints[:2]))
            elif not ints:
                nums=[float(n.group().replace(',','')) for n in re.finditer(NUM,part) if 0<float(n.group().replace(',',''))<1000]
                if len(nums) in (2,3): options.append(tuple((a,a) for a in nums[-2:]))
        unique=set(options)
        if len(unique)!=1: return None
        rows[key]=next(iter(unique))
    return rows

def feasible(rows):
    return all(sum(rows[k][i][0] for k in CHANNELS)<=rows['total'][i][1]+.05 and
               sum(rows[k][i][1] for k in CHANNELS)+.05>=rows['total'][i][0] for i in (0,1))

def evaluate(raw,judge,f):
    first=canon(''.join(raw.get('pages',[]))[:1800])
    wrong_subject=re.search(r'其他保险公司(?:未来|发展)|(?:公司|分析对象|报告对象)[:：]?其他保险公司',first)
    spans=[] if wrong_subject else [s for s in raw['spans'] if adopted(s)]
    pages=[] if wrong_subject else [canon(page) for page in raw.get('pages',[]) if page.strip()]
    document=canon('\n'.join(raw.get('pages',[]))) if not wrong_subject else ''
    def register(identity,span=None):
        if span is None:
            path=raw['artifact'].relative_to(judge.artifact_root).as_posix() or '.'
            loc=Locator(identity+'-raw',path,'pdf','document',identity,'carrier',raw['error'] or 'No comparable adopted relation')
            state=raw['state'] if raw['state']!='identified' else 'confirmed_missing'
            return judge.observe(identity,state,[loc])
        path=span.path.relative_to(judge.artifact_root).as_posix(); location=f'page[{span.page}]/offset[{span.offset}]'
        loc=Locator(identity+'-raw',path,'pdf',location,identity,'text',span.raw)
        normalized=Locator(identity+'-normalized',path,'pdf',location,identity,'text',span.text,
                           evidence_origin='lossless_canonicalized',source_locator_ids=(identity+'-raw',),normalization_rule_id='N01')
        return judge.observe(identity,'identified',[loc,normalized])
    # Keep the original twelve component checks even though related channel decisions are
    # settled as two weighted composite items. This preserves every business relation while
    # removing overlapping top-level credit.
    checks={p:[] for p in COMPONENT_POSITIVES}; evidence={p:[] for p in checks}
    check_evidence={p:[] for p in COMPONENT_POSITIVES}; allspec=specs(f)
    def check(pid,predicate):
        matches=[s for s in spans if predicate(s)]
        checks[pid].append(bool(matches)); check_evidence[pid].append(matches[0] if matches else None)
        evidence[pid]+=matches[:1]
    for spec in allspec: check(spec['pid'],lambda s,rule=spec: relation(rule,s.text))
    custom={
        'P02':[
            lambda t: re.search(r'签单保费',t) and re.search(r'业务收入|保费收入',t) and re.search(r'不同|差异|不完全可比|不可直接|不能直接',t) and re.search(r'口径|统计范围|分类',t),
            lambda t: re.search(r'2025|年报',t) and '2026' in t and re.search(r'新准则|新会计',t) and re.search(r'原准则|旧准则|老准则|原企业会计',t) and re.search(r'净利润|净资产|总资产',t) and re.search(r'不可直接|不能直接|不具有可比|不完全可比|不作同比|不做同比',t)],
        'P03':[lambda t: re.search(r'2026.*三季度|2026Q3|Q3E',t,re.I) and re.search(r'预测|情景',t) and near(t,306.66,.1) and near(t,309.35,.1)],
        'P08':[lambda t: '其他渠道' in t and '中介' in t and re.search(r'不完全可比|不可直接|不能直接|口径.*不同|口径.*不完全|统计范围.*不同',t)],
        'P09':[lambda t: re.search(CHANNELS['internet'],t) and re.search(CHANNELS['group'],t) and re.search(r'合计|合并',t) and near(t,3.4,.2)],
        'P12':[
            lambda t: near(t,2.18,.01) and near(t,2.14,.01) and re.search(r'利率.*(?:下行|下降)|低利率|折现率',t) and re.search(r'负债|利差',t) and re.search(r'长负债|短资产|久期缺口|期限.*短于',t) and re.search(r'长期.*债|延长.*久期|缩小.*缺口',t),
            lambda t: re.search(r'营销员|代理人|人力',t) and re.search(r'脱落|收缩|下降|减少',t) and re.search(r'产能|增长',t) and re.search(r'制约|限制|影响|风险',t),
            lambda t: re.search(r'2022.*2023',t) and '山东' in t and '26万元' in t and re.search(r'合规|销售.*管理|监管风险',t)]}
    for pid,tests in custom.items():
        for test in tests: check(pid,lambda s,fun=test: fun(s.text))
    for ch in CHANNELS: check('P10',lambda s,c=ch: forecast(s,c))
    tables=[(s,table(s)) for s in spans]; tables=[(s,r) for s,r in tables if r]
    check('P11',lambda s: table(s) is not None and feasible(table(s)))
    base=v(f,'h1.previous_annual_signed','2025')[0]/1e8
    def growth_ok(s):
        t=s.text
        if not ('2026' in t and '2025' in t and re.search(r'签单|总量|合计',t) and amount(t,base)): return False
        for _,rows in tables:
            expected=[(a/base-1)*100 for a in rows['total'][0]]
            if all(near(t,a,.9) for a in expected): return True
            for m in re.finditer(r'(?:增长|同比)[^。]{0,12}?(\d+(?:\.\d+)?)%?[—–~至-](\d+(?:\.\d+)?)%',t):
                if all(abs(float(m[i+1])-expected[i])<.9 for i in (0,1)): return True
        return False
    check('P11',growth_ok)

    # Electronic PDF tables commonly put the unit and period in column headers and the values in
    # separate row cells. The local prose predicates above deliberately stay strict; these page-bounded
    # fallbacks recover the same business relation from a structured table without unioning unrelated
    # topics across the document.
    def page_relation(anchor, values=(), patterns=(), tolerance=.18):
        for page_no,page in enumerate(pages,1):
            if not re.search(anchor,page,re.I):
                continue
            if all(bare_near(page,value,tolerance) for value in values) and all(re.search(pattern,page,re.I) for pattern in patterns):
                return page_no
        return None

    def document_window(anchor, values=(), patterns=(), radius=2600, tolerance=.18):
        for match in re.finditer(anchor,document,re.I):
            window=document[max(0,match.start()-radius):match.end()+radius]
            if all(bare_near(window,value,tolerance) for value in values) and all(re.search(pattern,window,re.I) for pattern in patterns):
                return window
        return None

    def supporting_span(anchor):
        return next((span for span in spans if re.search(anchor,span.text,re.I)), spans[0] if spans else None)

    def repair(pid,index,hit,anchor):
        if hit and index < len(checks[pid]) and not checks[pid][index]:
            checks[pid][index]=True
            span=supporting_span(anchor)
            if span is not None:
                check_evidence[pid][index]=span
                evidence[pid].append(span)

    repair('P02',0,document_window(r'签单保费',patterns=(r'保险业务收入|保费收入',r'口径|统计范围|分类',r'不同|差异|不可直接|不能直接|不完全可比'),radius=1600),r'签单保费')
    repair('P02',1,document_window(r'新准则|新会计',patterns=(r'旧准则|老准则|原准则|原企业会计',r'净利润|净资产|总资产',r'不可直接|不能直接|不完全可比|不具有可比|不作同比|不做同比'),radius=1600),r'新准则|新会计')

    repair('P03',0,document_window(r'核心.*(?:偿付|充足率)',(336.79,308.65,28.14),(r'百分点|变动.*点|ppt|pp',),1800,.11),r'核心.*(?:偿付|充足率)')
    repair('P03',1,document_window(r'综合.*(?:偿付|充足率)',(344.06,314.61,29.45),(r'百分点|变动.*点|ppt|pp',),1800,.11),r'综合.*(?:偿付|充足率)')
    repair('P03',2,document_window(r'306\.66|309\.35',(306.66,309.35),(r'Q3|三季度|下一季度|下一季|下季',r'预测|情景'),1800,.11),r'306\.66|309\.35')

    quarter_rows={
        'P06':(0,r'个人渠道|个险渠道|个人代理',(12.07,8.16,20.22,-32.4)),
        'P07':(0,r'银保渠道|银邮渠道|银行及邮政',(5.43,4.56,9.98,-16.1)),
        'P08':(0,r'其他渠道|中介/其他|中介及其他',(1.88,3.01,4.89,60.1)),
        'P09':(0,r'互联网渠道|网络渠道',(.31,.27,.57,-13.9)),
    }
    for pid,(index,anchor,values) in quarter_rows.items():
        page_hit=page_relation(anchor,values[:3],(r'Q1|一季度',r'Q2|二季度',r'H1|上半年',r'环比'),.2)
        if page_hit and not growth(canon(pages[page_hit-1]),values[3]): page_hit=None
        repair(pid,index,page_hit,anchor)
    group_hit=page_relation(r'团险渠道',(.28,.37,.65),(r'Q1|一季度',r'Q2|二季度',r'H1|上半年',r'环比'),.2)
    if group_hit and not growth(canon(pages[group_hit-1]),32.1): group_hit=None
    repair('P09',1,group_hit,r'团险渠道')
    repair('P07',1,document_window(r'银保|银邮|银行及邮政',(17.77,8.1),(r'2025',r'下降|负增长|收缩'),1300,.2),r'银保|银邮|银行及邮政')
    repair('P08',1,document_window(r'中介',(5.52,72.0),(r'2025',r'增长|上升'),1300,.25),r'中介')
    repair('P08',2,document_window(r'其他渠道',patterns=(r'中介',r'口径|统计范围|分类',r'不可直接|不能直接|不完全可比|不同'),radius=1700),r'其他渠道')
    repair('P09',2,document_window(r'互联网渠道|网络渠道',(3.4,),(r'团险',r'合计|合并|占'),1500,.25),r'互联网渠道|网络渠道')

    def quantified_forecast_window(anchor):
        for match in re.finditer(anchor,document,re.I):
            window=document[max(0,match.start()-1900):match.end()+1900]
            local=document[max(0,match.start()-450):match.end()+900]
            if not ('2026' in window and '2027' in window and
                    re.search(r'预测|预计|情景|E',window,re.I) and
                    re.search(r'H1|上半年|Q1|Q2|假设|依据|基于',window,re.I)):
                continue
            numbers=[float(value.replace(',','')) for value in re.findall(NUM,local)]
            plausible=[value for value in numbers if 0 < value < 1000 and value not in (2026,2027)]
            if len(plausible)>=2:
                return window
        return None

    forecast_anchors=[CHANNELS[ch] for ch in CHANNELS]
    for index,anchor in enumerate(forecast_anchors):
        repair('P10',index,quantified_forecast_window(anchor),anchor)

    all_channels=all(checks['P10'])
    reconcile=document_window(r'合计|总量|总签单保费',patterns=(r'2026',r'2027',r'个人|个险',r'银保|银邮',r'其他|中介',r'互联网|网络',r'团险',r'勾稽|加总|合计|求和|Σ|一致|端点.*相加'),radius=3200)
    repair('P11',0,all_channels and reconcile,r'合计|总量|总签单保费')
    base_growth=None
    for match in re.finditer(r'2025|签单保费',document):
        window=document[max(0,match.start()-1900):match.end()+1900]
        if (amount(window,base) and '2026' in window
                and re.search(r'签单|总量|合计',window)
                and re.search(r'同比|增长|较',window)):
            base_growth=window
            break
    repair('P11',1,base_growth,r'2025|签单保费')

    repair('P12',0,document_window(r'折现率|低利率|利率',patterns=(r'久期|长负债|短资产|资产久期.*负债',r'长期债|长债|延长|缺口'),radius=2200),r'折现率|低利率|利率')
    repair('P12',1,document_window(r'营销员|代理人|人力',patterns=(r'脱落|收缩|下降|减少',r'产能|增长',r'制约|限制|影响|风险'),radius=1800),r'营销员|代理人|人力')
    repair('P12',2,document_window(r'山东',patterns=(r'2022',r'2023',r'26万',r'合规|销售管理|监管风险'),radius=1800),r'山东')

    # The two regulatory minima form one conjunctive control. Current ratios or a
    # generic claim of ample headroom do not substitute for stating both thresholds.
    check('P13',lambda s: False)
    threshold_pair=None
    for match in re.finditer(r'监管最低要求|监管要求|最低要求|偿付能力',document):
        window=document[max(0,match.start()-600):match.end()+600]
        core=bool(re.search(r'核心(?:偿付能力)?(?:充足率)?[^。；]{0,80}50%|50%[^。；]{0,80}核心(?:偿付能力)?(?:充足率)?',window))
        comprehensive=bool(re.search(r'综合(?:偿付能力)?(?:充足率)?[^。；]{0,80}100%|100%[^。；]{0,80}综合(?:偿付能力)?(?:充足率)?',window))
        if core and comprehensive:
            threshold_pair=window
            break
    repair('P13',0,threshold_pair,r'核心|综合')

    component_fractions={pid:(sum(results)/len(results) if results else 0) for pid,results in checks.items()}
    settled_fractions={}
    for pid in ('P01','P02','P03','P04','P05','P06','P10','P12','P13'):
        if pid=='P04':
            settled_checks=checks['P04']+checks['P05'][1:2]
            fraction=sum(settled_checks)/len(settled_checks)
            merged_evidence=[span for span in check_evidence['P04']+check_evidence['P05'][1:2] if span]
        elif pid=='P05':
            settled_checks=checks['P05'][:1]
            fraction=float(settled_checks[0]) if settled_checks else 0
            merged_evidence=[span for span in check_evidence['P05'][:1] if span]
        else:
            members=MERGED_POSITIVES.get(pid,{pid:1.0})
            total=sum(members.values())
            fraction=sum(weight*component_fractions[member] for member,weight in members.items())/total
            settled_checks=[hit for member in members for hit in checks[member]]
            merged_evidence=[span for member in members for span in check_evidence[member] if span]
        hit=merged_evidence[0] if merged_evidence else None
        obs=register(pid,hit)
        completed=sum(settled_checks)
        possible=len(settled_checks)
        judge.positive(pid,fraction,obs,f'{completed}/{possible} component relations; original-weighted composite',
                       'equivalent' if fraction==1 else 'partial' if fraction else 'missing')
        settled_fractions[pid]=fraction
        # Keep every component locator; the combined item never replaces absent components with tokens.
        for i,s in enumerate(merged_evidence[1:],1): register(pid+f'-component-{i}',s)
    errors={d:[] for d in judge.deductions}
    for span in spans:
        for clause in re.split(r'[。；;]',span.text):
            if not ('规模保费' in clause and (near(clause,12.6,.01) or '1.126' in clause)
                    and re.search(r'签单保费',clause)):
                continue
            backsolve=re.search(
                r'(?:由|利用|根据|据此|以该|以披露|近似)[^。；]{0,220}(?:反推|倒推)'
                r'|(?:反推|倒推)(?:所得|得到|过程|方法|2025|总量|基数)'
                r'|32\.2[56][^。；]{0,120}(?:0\.917|2025全年签单保费|季节(?:性|比))',
                clause,re.I)
            denied=re.search(
                r'(?:不|不得|不可|不能|未|勿|避免)[^。；]{0,24}(?:反推|倒推)'
                r'|(?:反推|倒推)[^。；]{0,24}(?:不成立|不可用|不采用|仅为假设)',
                clause,re.I)
            # Whether the clause adopts scale-premium growth as signed-premium
            # growth depends on metric scope, attribution, negation and the
            # surrounding forecast chain. The source-bound semantic layer owns
            # that proposition; this lexical scan is diagnostic only.
            if backsolve and not denied:
                break
    for span in spans:
        for clause in re.split(r'[。；;]',span.text):
            if len(clause)>450 or EXCLUDED.search(clause) or re.search(r'勘误|有误|不应|并非|不可|未披露|估计|假设',clause): continue
            for spec in allspec:
                if spec['mode'] not in ('growth','quarter') or not re.search(spec['obj'],clause): continue
                if spec['scope'] and not re.search(spec['scope'],clause): continue
                comparator='环比' if spec['mode']=='quarter' else '同比'
                # Historical D requires a directly bound measurement phrase, not a topic mention.
                anchors={'income-growth':r'保险业务收入', 'profit-growth':r'净利润',
                         'assets-growth':r'总资产(?!收益率)', 'participating-growth':r'分红(?:保险|险)(?:保费)?(?:收入)?',
                         'first-year-growth':r'首年(?:保费)?', 'bank-historical':CHANNELS['bank'],
                         'intermediary-historical':r'(?:保险)?中介(?:代理)?(?:渠道)?(?:收入)?'}
                if spec['mode']=='growth':
                    bound_candidates=[clause[a.end():] for a in re.finditer(anchors.get(spec['key'],spec['obj']),clause)]
                    bound_candidates=[b for b in bound_candidates if re.match(r'^(?:渠道|收入|保费|保险业务收入|业务收入|约|为|达到|实现|:|,){0,4}\d+(?:\.\d+)?亿元[^。；;]{0,10}同比',b)]
                    if len(bound_candidates)!=1: continue
                    bound=bound_candidates[0]
                    if spec['key']=='participating-growth' and re.search(r'渠道|首年|净利润',bound.split('同比')[0]): continue
                    if spec['key']=='assets-growth' and '收益率' in bound.split('同比')[0]: continue
                if spec['mode']=='quarter' and not(amount(clause,spec['first']) and amount(clause,spec['second'])): continue
                nums=re.findall(comparator+r'(?:大幅|小幅)?(?:增长|增加|上升|下降|回落|减少|增速|增幅)?(?:约|为)?([-+]?\d+(?:\.\d+)?)%',clause)
                if len(nums)!=1 or re.search(r'预计|预测|2027|2026年全年|2026年.*较2025',clause): continue
                observed=float(nums[0])
                if re.search(comparator+r'(?:大幅|小幅)?(?:下降|回落|减少)',clause): observed=-abs(observed)
                if abs(observed-spec['value'])>.3: errors['D01'].append((spec['key'],span))
            if re.search(r'二季度单季|二季度当季|Q2单季|第二季度单季',clause,re.I) and not re.search(r'累计|上半年|H1',clause,re.I):
                for ch in ('signed_total',*CHANNELS):
                    if re.search(r'签单保费|总保费' if ch=='signed_total' else CHANNELS[ch],clause) and amount(clause,v(f,'h1.'+ch,'ytd')[0]/1e8): errors['D02'].append((ch+'-period',span))
            if re.search(r'(?:个人|个险)(?:渠道)?(?:的)?(?:上半年)?续期(?:签单)?保费',clause) and amount(clause,24.65): errors['D03'].append(('personal-renewal-scope',span))
            if ('2026' in clause and re.search(r'(?:较|与)2025|同比',clause)
                    and re.search(r'净利润|净资产|总资产',clause)
                    and re.search(r'(?:完全)?同口径|可直接(?:作同口径)?比较|可比口径',clause)
                    and not re.search(r'重述|调整后|新旧.*差异',clause)):
                errors['D04'].append(('accounting-comparison',span))
            internet_actual=False
            actual_patterns=(
                r'2025年?[^。；]{0,24}(?:互联网|网络)(?:渠道)?(?:签单)?(?:保费|收入)[^。；]{0,16}(?:实际(?:为)?|披露(?:为)?|为|达到)\s*\d+(?:\.\d+)?亿元',
                r'(?:互联网|网络)(?:渠道)?[^。；]{0,16}2025年?[^。；]{0,16}(?:签单)?(?:保费|收入)[^。；]{0,16}(?:实际(?:为)?|披露(?:为)?|为|达到)\s*\d+(?:\.\d+)?亿元',
                r'(?:年报|材料|公司)(?:披露|显示)[^。；]{0,20}2025年?[^。；]{0,20}(?:互联网|网络)(?:渠道)?(?:签单)?(?:保费|收入)[^。；]{0,8}\d+(?:\.\d+)?亿元',
            )
            for pattern in actual_patterns:
                match=re.search(pattern,clause)
                if match and not re.search(r'未披露|未提供|无法(?:确认|证实)|不能(?:确认|证实)|无[^。；]{0,8}披露|预测|预计|假设|推算',match.group()):
                    internet_actual=True
                    break
            if internet_actual: errors['D05'].append(('invented-internet-actual',span))
            future_actual=False
            for match in re.finditer(r'2027年?([^。；]{0,60})(?:已实现|已完成|实际完成|实际为)',clause):
                # Bind the completion verb to 2027 itself. Forecast prose often compares 2027
                # with a 2026 period that has already been realised; crossing that intervening
                # year falsely turns the 2026 actual into a 2027 actual.
                if not re.search(r'20(?:2[0-689]|[3-9]\d)',match.group(1)):
                    future_actual=True
                    break
            if future_actual: errors['D05'].append(('future-actual',span))
            core_150=(
                re.search(r'核心[^。；]{0,80}(?:监管最低|最低要求|不得低于)[^\d%]{0,15}150%',clause)
                or re.search(r'核心[^。；]{0,80}监管线(?:为|是|[:：])?150%',clause)
                or re.search(r'150%[^。；]{0,50}(?:核心偿付能力)?(?:监管最低|最低要求|监管线)',clause)
            )
            if core_150: errors['D06'].append(('regulatory-core-minimum',span))
            cross_basis_share=re.search(
                r'(?:个人|个险)(?:代理)?(?:渠道)?[^。；]{0,55}占比(?:由|从)2025年'
                r'[^。；]{0,35}(?:约)?59(?:\.\d+)?%[^。；]{0,45}'
                r'(?:降至|下降至|下降到|减少至)[^。；]{0,18}'
                r'(?:4[7-9]|5[0-4]|55(?:\.7)?)(?:\.\d+)?%',
                clause)
            if cross_basis_share and not re.search(r'口径(?:不同|不一致)|仅供方向|不可比|不能直接|不作直接',clause):
                errors['D08'].append(('cross-basis-channel-share-trend',span))
    for s,rows in tables:
        if not feasible(rows): errors['D07'].append(('forecast-total-feasibility',s))
    # Explicit local chains preserve cross-owner partial credit. A basis error
    # can suppress only the channel-outlook chain; it does not erase unrelated
    # annual, product, risk, or regulatory credit.
    def chain(pid, fraction, evidence_ids, reason):
        evidence_spans = [evidence[p][0] for p in evidence_ids if evidence[p]]
        hit = evidence_spans[0] if evidence_spans else None
        obs = register(pid, hit)
        comparison = 'equivalent' if fraction == 1 else 'partial' if fraction else ('different' if hit else 'missing')
        judge.positive(pid, fraction, obs, reason, comparison)
    channel_chain_clean = not any(errors.get(did) for did in ('D01','D02','D03','D04','D05','D07','D08'))
    signed_forecast_clean = not any(errors.get(did) for did in ('D01','D02','D05','D07','D09'))
    capital_chain_clean = not errors.get('D06')
    chain('C01', min(settled_fractions['P02'], settled_fractions['P06'], settled_fractions['P10']) if channel_chain_clean else 0.0,
          ['P02','P06','P10'], 'Local channel-outlook chain; cross-basis damage is scoped to this outcome.')
    chain('C02', min(settled_fractions['P06'], settled_fractions['P10']) if signed_forecast_clean else 0.0, ['P06','P10'],
          'Local signed-premium forecast chain; scale-growth damage is scoped to forecast-baseline use.')
    chain('C03', (0.8*settled_fractions['P03']+0.2*settled_fractions['P13']) if capital_chain_clean else 0.0, ['P03','P13'],
          'Capital-headroom chain: 80% actual/forecast solvency analysis and 20% regulatory-threshold context.')
    for did,hits in errors.items():
        unique={}
        for key,s in hits: unique.setdefault(key,s)
        obs=[]; occurrences=[]
        for i,(key,s) in enumerate(unique.items()):
            oid=register(f'{did}-{i}',s); obs.append(oid)
            occurrences.append(dict(observation_id=oid,causal_root_id=key,damage_instance_key=key,manifestation_id=f'{did}:{key}:{s.page}:{s.offset}'))
        if not obs: obs=[register(did)]
        judge.deduction(did,'triggered' if occurrences else 'parse_failure' if raw['state']=='parse_failure' else 'not_triggered',obs,
                        'Affirmative bound false conclusion' if occurrences else 'No adopted error established; omission and uncertainty excluded',occurrences)
    result=judge.finish()
    result['component_checks']=checks
    result['extraction_status']={'state':raw['state'],'detail':raw['error']}
    result['limitations']=['Initial deterministic coverage is narrower than independent expert semantic review; unparsed chart labels and unfamiliar paraphrases require separate review.']
    return result

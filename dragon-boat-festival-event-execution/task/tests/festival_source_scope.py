"""Local entailment boundaries for generic proposed roles and risk planning."""
import re
from pathlib import Path
from openpyxl import load_workbook

EXTERNAL_COMPLETION=re.compile(r'已(?:经)?(?:获得|获批|批准|签约|签署|验收|交付|送达|签收|到货|采购|备齐|同意|承诺|认证|核实|确认配方)|合同|许可证|批文|认证编号|资质证书|国家级|省级|市级')
CONFIRMED_RECIPE=re.compile(r'(?:食材|配方|配料|本场材料)[^。;；|]{0,10}已(?:经)?(?:确认|确定|采购|备齐|到货)|(?:确认|确定)(?:本次|本场)(?:配方|食材|配料)')

def location_root(location):return re.sub(r':S\d+$','',location.removeprefix('C-'))

def enclosing_rows(finding,spans):
    roots={location_root(i) for i in finding.get('candidate_ids',[])}
    return [s for s in spans if s['scope']!='table-duty' and location_root(s['location']) in roots]

def adjacent_heading(span,spans):
    number=int(re.match(r'B(\d+)',span['location'])[1])
    return ' '.join(s['text'] for s in spans if s['scope']=='paragraph' and s['location'] in {f'B{number-1}',f'B{number-2}'})

def exclusion(finding,spans):
    rows=enclosing_rows(finding,spans)
    if not rows:return None
    text=' '.join(s['text'] for s in rows)
    if EXTERNAL_COMPLETION.search(text):return None
    claim=finding.get('claim','')
    if re.search(r'食材|配方|配料|食谱',claim) and not CONFIRMED_RECIPE.search(text):
        risk_rows=[]
        for row in rows:
            table=row['location'].split(':',1)[0]
            headers=' '.join(s['text'] for s in spans if s['scope']=='table-row' and s['location'] in {table+':R1',table+':R2'})
            if re.search(r'风险|过敏|卫生',row['text']) and re.search(r'成因|触发|风险',headers):risk_rows.append(row)
        if len(risk_rows)==len(rows):return 'A foreseeable food-risk trigger is not a confirmed recipe or delivery.'
    if re.search(r'验收方|保洁.*验收|保洁.*作为',claim):
        if re.search(r'保洁验收|清洁验收',text) and not re.search(r'已确认(?:保洁|清洁)|(?:保洁|清洁)(?:已|已经)',text):
            return 'A generic cleanup acceptance role is a proposed workflow, not a completed outside commitment.'
    if re.search(r'划拨|兼作|兼做|用于表演互动|表演互动礼品',claim):
        derived=any(re.search(r'测算|本方案推导|建议|待确认',adjacent_heading(row,spans)+' '+row['text']) for row in rows)
        guaranteed=re.search(r'保证|保底|确保.*(?:200|二百)|(?:额外|另加|另有|增加).{0,8}(?:80|八十)|(?:280|二百八十).{0,4}(?:份|条)',text)
        if derived and not guaranteed and re.search(r'五彩绳|端午书签',text) and not re.search(r'香囊|福袋|祈福签',text):
            return 'A qualified allocation of the supplied gift types is an operating choice, not an extra confirmed stock or delivery.'
    if re.search(r'提前|开课前',claim) and re.search(r'领.*券|体验券',claim) and re.search(r'签到',claim):
        if re.search(r'(?<![\d零一二两三四五六七八九十百千万])(?:10|十)\s*分钟',text) and not re.search(r'拒绝|取消资格|不予入场|强制|处罚|违约',text):
            return 'Adopting the supplied ten-minute arrival/ticket recommendation as one workflow does not establish a separate outside authorization or a new refusal rule.'
    return None

def source_group_exclusion(finding,materials):
    claim=finding.get('claim','')
    if not re.search(r'人员[甲乙丙丁戊]',claim) or not re.search(r'负责|指定|职责',claim):return None
    text=' '.join(e['quote'] for e in finding.get('candidate_evidence',[]))
    if EXTERNAL_COMPLETION.search(text):return None
    for path in Path(materials).glob('*.xlsx'):
        book=load_workbook(path,data_only=False)
        try:
            for sheet in book:
                for merged in sheet.merged_cells.ranges:
                    if merged.min_col!=merged.max_col or merged.min_row==merged.max_row:continue
                    owner=sheet.cell(merged.min_row,7).value
                    if not isinstance(owner,str) or not re.search(r'人员[甲乙丙丁戊]',owner) or owner not in claim:continue
                    for number in range(merged.min_row+1,merged.max_row+1):
                        value=sheet.cell(number,3).value
                        if isinstance(value,str) and len(value)>=2 and value in text and sheet.cell(number,7).value is None:
                            return 'The original merged source category permits this ordinary group assignment; its blank subordinate owner is not proof of a fabricated new commitment.'
        finally:book.close()
    return None

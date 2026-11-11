"""Adopted operating actions, functional staff roles and local uncertainty."""
import re
from festival_control import WITHDRAWN

def adopted_action(text,match):
    start=max((text.rfind(mark,0,match.start()) for mark in '。;；|,，'),default=-1)+1
    ends=[text.find(mark,match.end()) for mark in '。;；|,，']
    end=min((p for p in ends if p>=0),default=len(text))
    prefix=text[start:match.start()]
    local=text[start:end]
    if re.search(r'是否|要不要|有无必要|待决定|未采纳|不采纳|未采用|暂不采用',local):return False
    tail=text[match.end():]
    if re.match(r'[^。;；|]{0,20}(?:但|然而|不过)(?:此|该|上述)?(?:职责|分工|安排|方案)[^。;；|]{0,8}(?:未采纳|未采用|暂不采用|不执行)',tail):return False
    if re.search(r'(?:不|未|无需|无须|不必|不得)(?:为|要求|需要)[^。;；|,，]*$',prefix):return False
    return not WITHDRAWN.search(prefix)

def boundary_decision(identifier,span):
    text=span['normalized']
    if re.search(r'关键词|评分项|rubric|仅供选择|不执行',text,re.I):return False
    target={'capacity-enforcement':r'40|限额|人数',
            'per-session-reset':r'清理|清洁|回收|归还',
            'assistance':r'安排|分发|入座|座位|指导',
            'audience-flow':r'引导(?!员|岗|组)|疏导|停止|保留|控制人流'}.get(identifier)
    uncertain=False
    if target:
        uncertain=any(re.search(r'(?:是否|要不要|有无必要|待决定)[^。;；|,，]{0,60}(?:'+target+r')[^。;；|,，]{0,40}(?:待确认|待决定|未确定|另行讨论)',part) for part in re.split(r'[。;；|,，]',text))
    if identifier=='capacity-enforcement':
        if re.search(r'执行办法另行讨论|本方案(?:不|未|暂不)(?:执行|采用)|(?:仅|只)摘录[^。]{0,20}不作为[^。]{0,12}执行',text):return False
        participant_context=re.search(r'体验|手作|课堂|课程|入席|报名|签到|核销|体验券|参与者|本场|每场|场次|在场|入场|券面|领券',text)
        if participant_context and re.search(r'40',text):
            patterns=[
                r'(?:控制|限制|封顶|限收)[^。;；|,，]{0,20}40(?:人|名)',
                r'(?:满|达到|计数达|累计|计数至|实到[^。;；|,，]{0,8})(?:本场)?40(?:人|名)?[^。;；|,，]{0,12}(?:停止|暂停|不再|即止|不予)[^。;；|,，]{0,8}(?:放行|发券|入场|入席|发放|进场)',
                r'(?:满额|满员|达上限|额满)[^。;；|,，]{0,12}(?:停止|暂停|不再|不予)[^。;；|,，]{0,8}(?:放行|发券|入场|入席|发放|进场)',
                r'(?:入场|入席|发券|实到|放行|入内|发放体验券)[^。;；|,，]{0,20}(?:不超过|不超|限|上限|≤|不大于)40',
                r'(?:每场限|不得突破|不得超过|不提高)[^。;；|,，]{0,8}40(?:人|名)',
                r'(?:发出券数|发券数|实际入座|该场计数|本场计数|当场计数|每场独立计数|在场人数)[^。;；|,，]{0,8}(?:≤|不超过|不得超过|不超)40',
                r'每场40(?:张|人)[^。;；|,，]{0,8}[,，]?(?:发完即止|额满即止)',
                r'(?<!未)(?:满|达到)40(?:人|名)[,，](?:即|后)?(?:停止|暂停)(?:放行|发券|入场|入席|发放|进场)'
            ]
            for pattern in patterns:
                if any(adopted_action(text,m) for m in re.finditer(pattern,text)):return True
        if re.search(r'40|资料摘录|来源摘录|原文摘录|执行办法另行讨论',text):return False
    if identifier=='audience-flow':
        role=re.search(r'流线岗|人流管理岗|引导岗|秩序岗|工作人员|志愿者|安保|保安',text)
        people=re.search(r'观众|观演|游客|人流',text)
        if role and people:
            pattern=r'停止(?:新)?观众(?:进入|入场)|(?:保留|保持|清出|疏通)[^。;；|,，]{0,6}(?:通行带|通道|疏散带)'
            matches=list(re.finditer(pattern,text))
            if matches:return any(adopted_action(text,m) for m in matches)
    if identifier=='assistance':
        role=re.search(r'流线岗|协助岗|体验协助|引导岗|老师|教师|助教|工作人员|志愿者|人员[丙丁]',text)
        participant=re.search(r'参与者|游客|学员|需要协助者|需协助者|体验者',text)
        operation=re.search(r'入场|开课|签到|核销|入席|需要协助|需协助|T-5',text)
        static=re.search(r'预先|活动前|开场前|课前|布场|布置|座位图|摆放桌椅|预留位置',text)
        actual_help=re.search(r'引导|需[^。;；|]{0,6}协助|协助入|现场入场|到场|签到后|核销后',text)
        if role and participant and operation and (not static or actual_help):
            pattern=r'(?:安排|协助|引导)[^。;；|,，]{0,16}(?:合适座位|座位|入座|就座|入席)'
            matches=list(re.finditer(pattern,text))
            if matches:return any(adopted_action(text,m) for m in matches)
    if identifier=='per-session-reset':
        if (re.search(r'(?:工具|器具|教具)未(?:收齐|归还|回收)',text)
                and re.search(r'(?:台面|桌面)未(?:清洁|清理|擦拭)',text)
                and re.search(r'(?:不得|不能|不允许)(?:开放|放行|开始)[^。;；|]{0,8}下一场',text)):
            return True
        matches=list(re.finditer(r'清理|清洁|回收|归还',text))
        if matches and not any(adopted_action(text,m) for m in matches):return False
    if uncertain:return False
    return None

def generic_instructor_exemption(finding):
    """An unnamed teaching-role label is not a verified professional credential."""
    if not re.search(r'传承人|授课老师|专业资格',finding.get('claim','')):return False
    quotes=[r['quote'] for r in finding.get('candidate_evidence',[])]
    if not quotes:return False
    text='；'.join(quotes)
    if not re.search(r'(?:老师|教师|讲师)[（(][^）)]{0,12}非遗传承人|非遗传承人老师',text):return False
    if not re.search(r'(?:姓名|人选|人数)[^。;；|]{0,12}(?:问|待确认|待定|未确定)',text):return False
    if re.search(r'国家级|省级|市级|县级|证书|认证|获评|入选|认定|持证|资格证|已聘|聘任|已签约|已核实|资质已|资质已经|已确认资质',text):return False
    return True

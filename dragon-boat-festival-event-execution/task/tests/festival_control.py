"""Whole-event duty ownership and adopted-action checks."""
import re

GLOBAL_ROLE=re.compile(r"总控|总协调|总指挥|总值守|(?:当日)?现场决策人|当日决策人|当日执行负责人|当日现场负责人")
GENERIC_ROLE=re.compile(r"负责人")
LOCAL_SUBJECT=re.compile(r"^(?:大厅|广场|体验|表演|课程|物料|摄影|天气|音响|安保|核销|签到|服务台|老师|助教|教师|演员|主持|游客|参与者|志愿者|人员[甲乙丙丁戊己])")
LOCAL_OWNER=re.compile(r"^(?:大厅|广场|体验|表演|课程|物料|摄影|天气|音响|安保|核销|签到|服务台)[^。;；|,，]{0,8}负责人")
ACTION=re.compile(r"把控|调度|协调(?!人|岗)|负责(?!人)|指挥(?!链)|统筹(?!岗)|裁决|掌握|下达")
GLOBAL_SCOPE=re.compile(r"全场|全程|跨区|两区|各岗|场次|运行|节奏|现场(?:调度|指挥|运行|异常|问题|变更)")
GLOBAL_OBJECT=re.compile(r"全场|全程|跨区|两区|各岗|场次|运行|节奏|异常|问题|指令|变更")
RECIPIENT=re.compile(r"(?:向|给|报|联系|通知|抄送|提交至|交给|上报|请示)[^。;；|,，]{0,2}$")
QUESTION=re.compile(r"是否|有无|未明确|未列|未指定|不完整|须确认|需确认|若同时|是否兼任|不假定|不能同时|不宜同时")
NAME_PENDING=re.compile(
    r"(?:姓名|人选|名字|名单|联系方式)[^。;；|,，]{0,8}(?:尚需确认|待确认|需确认|须确认|未确认)"
    r"|(?:尚需确认|待确认|需确认|须确认|未确认)[^。;；|,，]{0,8}(?:姓名|人选|名字|名单|联系方式)"
)
DUTY_VERB=r"(?:负责|承担|执行|履行|统筹|协调|安排|实施|采纳|采用|进行|参与|决定|确认|下达|发令|调度|指挥|掌握|具有|具备)"
WITHDRAWN=re.compile(
    r"(?:不|未|没有|没|不再|不予|暂不)"+DUTY_VERB+r"[^。;；|,，]*$"
    r"|(?:无需|无须|不用|不必|不得|禁止|无权|停止|取消)(?:再|应|该)?"+DUTY_VERB+r"[^。;；|,，]*$"
    r"|(?:不|未|没|没有|无需|无须|不用|不必|不得|禁止|无权|暂不|停止|取消|尚未)(?:再|应|该)?$"
)

def adopted(clause,match):
    return not WITHDRAWN.search(clause[:match.start()])

def unadopted(text):
    candidate=re.search(r"(?:职责|分工|条款|方案|安排)(?:候选|备选)|(?:候选|备选)(?:职责|分工|条款|方案|安排)",text)
    rejected=re.search(r"暂不采用|未采用|不采纳|不执行|仅供参考|仅供选择",text)
    return bool(candidate and rejected or re.search(r"(?:此|该|上述)(?:职责|分工|安排)[^。;；|]{0,10}(?:暂不采用|未采用|不执行)",text))

def action_present(clause,owner):
    cleaned=NAME_PENDING.sub("",clause)
    if QUESTION.search(cleaned):return False
    for action in ACTION.finditer(clause):
        if not adopted(clause,action):continue
        tail=clause[action.end():action.end()+18]
        if (GLOBAL_OBJECT if owner=="global" else GLOBAL_SCOPE).search(tail):return True
    for action in re.finditer(r"(?:跨区|全场|两区|各岗|全程)(?:协调|统筹|调度|指挥|把控)",clause):
        if adopted(clause,action):return True
    if owner!="global":return False
    for action in re.finditer(r"确认[^。;；|]{0,18}(?:双点位|双区|两区|双线|两条线)[^。;；|]{0,12}(?:无冲突|可开场|就绪)",clause):
        if adopted(clause,action):return True
    for action in re.finditer(r"现场指挥(?!链)|组织[^。;；|]{0,10}现场|现场[^。;；|]{0,8}组织",clause):
        if adopted(clause,action):return True
    for action in re.finditer(r"统一(?:发令|决策)|(?:启停|暂停|恢复)[^。;；|]{0,8}(?:区域|活动)|(?:协调|统筹|调度)[^。;；|]{0,8}(?:资源|公告|区域)",clause):
        if adopted(clause,action):return True
    for action in re.finditer(r"(?:作为|担任)[^。;；|]{0,12}现场唯一[^。;；|]{0,20}(?:停演|复演|调岗)",clause):
        if adopted(clause,action):return True
    for action in re.finditer(r"确认|决定|裁决|批准|授权",clause):
        if adopted(clause,action) and len(set(re.findall(r"开场|暂停|恢复|取消|复开|停演|复演",clause[action.end():])))>=2:return True
    return False

def overall_control(text):
    if unadopted(text):return False
    owner=None
    row_owner=None
    first_cell=text.split("|",1)[0]
    if "|" in text:
        if GLOBAL_ROLE.search(first_cell):row_owner="global"
        elif re.search(r"全场统筹|全场调度|跨区统筹|跨区协调",first_cell):row_owner="global"
        elif GENERIC_ROLE.search(first_cell) and not LOCAL_OWNER.search(first_cell):row_owner="generic"
    named_row="|" in text and bool(re.fullmatch(r"人员[甲乙丙丁戊己]",first_cell.strip()))
    buffer=""
    separator=""
    owner=row_owner
    cell_index=0
    # A row role can own later duty cells. Narrative ownership survives only
    # within its sentence, and an explicitly different subject ends inheritance.
    pieces=re.split(r"([。;；|,，]|但是|然而|但)",text)
    for piece in pieces:
        if not piece:continue
        if piece=="。":owner=None;buffer="";separator=piece;continue
        if piece=="|":cell_index+=1;owner=row_owner;buffer="";separator=piece;continue
        if piece in (";","；",",","，","但是","然而","但"):
            separator=piece
            if piece not in (",","，"):buffer=""
            continue
        current=piece.strip()
        if "|" in text and current==first_cell.strip() and row_owner:
            continue
        global_role=next((m for m in GLOBAL_ROLE.finditer(current) if not RECIPIENT.search(current[:m.start()])),None)
        lead=re.sub(r"^(?:由|交由|请|让|安排|指定)","",current)
        if global_role:
            owner="global"
            if "|" in text and cell_index<=1:row_owner="global"
        elif LOCAL_SUBJECT.search(lead):owner=None;buffer=""
        elif GENERIC_ROLE.search(current):owner="generic"
        if LOCAL_OWNER.search(lead) and not global_role:owner=None;buffer=""
        assignment=re.search(r"全场(?:统筹|调度|把控)|跨区(?:统筹|协调|调度|指挥)|两区(?:统筹|调度|协调)|现场指挥",current)
        explicit_assignment=named_row or re.search(r"主岗|(?:人员[甲乙丙丁戊己])[^。;；|]{0,30}(?:代行|负责|承担)",current)
        if assignment and explicit_assignment:owner="global"
        joined=buffer+separator+current if buffer and separator in (",","，") else current
        if owner and action_present(joined,owner):return True
        buffer=joined
    return False

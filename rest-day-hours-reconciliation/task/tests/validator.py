"""Read submitted carriers, normalize event observations, then score business relations."""

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import tempfile
import zipfile
from pathlib import Path

import openpyxl
import carrier
import formulas
from semantic_judge import adjudicate

HERE = Path(__file__).resolve().parent
VERSION = '1.9'
ALIASES = {
    'event': ['事件编号', '原到岗事件', '事项编号', 'eventid', 'event', 'incidentid'],
    'employee': ['员工编号', 'employeeid'],
    'name': ['员工姓名', '姓名', 'employeename', 'name'],
    'date': ['事件日期', '记录日期', '日期', 'eventdate', 'date'],
    'roster': ['排班状态', '排班性质', '排班判断', 'rosterstatus', 'scheduleclassification'],
    'employer': ['门店安排', '是否门店安排', '是否由门店提出到岗', 'employerarranged'],
    'work': ['实际工作事实', '实际工作', '工作事实', '劳动事实', 'workfinding', 'actualwork'],
    'ledger_hours': ['调休登记时长', '记录时长', '登记时长', 'leavehours', 'registeredleavehours'],
    'rest_state': ['调休日期实际状态', '调休实际状态', '调休日事实', 'actualleavestatus'],
    'rest': ['调休结论', '调休判断', '调休有效性', 'leaveconclusion', 'leavefinding', 'compensatoryleavefinding'],
    'payroll': ['工资处理状态', '工资状态', 'payrollstatus', 'payrolltreatment'],
    'action': ['最终处置', '处理意见', '处置建议', '最终处理', 'disposition', 'finalaction'],
    'evidence': ['证据引用', '证据来源', '依据', '引用依据', '来源引用', 'sourcecitations', 'evidence', 'citations'],
    'start': ['进入时间', '入场时间', '开始时间', 'entrytime', 'starttime', 'start'],
    'end': ['离开时间', '出场时间', '结束时间', 'exittime', 'endtime', 'end'],
    'interval': ['门禁出入间隔小时', '门禁出入间隔', '出入间隔小时', '出入时长小时', '出入时长',
                 '门禁间隔小时', 'elapsedhours', 'intervalhours', 'entryexitintervalhours'],
    'interval_note': ['说明', '计算说明', 'calculationnote', 'note'],
    'issue': ['待核实事项', '待补证事项', '未决事项', 'openissue', 'issue'],
    'needed': ['建议补证', '补证材料', '所需证据', 'evidencetoobtain', 'requiredevidence'],
    'owner': ['责任角色', '责任人', '责任部门', 'responsibleroles', 'owner'],
    'milestone': ['复核时点', '复核时间', '完成时限', 'reviewmilestone', 'reviewtime'],
}


def text(value):
    if value is None:
        return ''
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat(sep=' ') if isinstance(value, dt.datetime) else value.isoformat()
    return str(value).strip()


def compact(value):
    return re.sub(r'[\s_()（）\[\]【】:/：\-]+', '', text(value).lower())


def has(value, pattern):
    return re.search(pattern, text(value), re.I) is not None


def adopted_evidence_request(value):
    clauses = re.split(r'[。；;\n]', text(value))
    return '；'.join(clause for clause in clauses if not has(clause,
        r'例如|仅供示例|引文|quoted|example|(?:无需|无须|不需要|不必|不用|不要求|毋须).{0,8}(?:补证|取得|调取|提供|提交|核验|申请|审批)'))


def pending_activity_report(memo, truth):
    pending = next(case for case in truth['cases'] if case['role'] == 'investigate')
    unresolved = r'不能区分|未能区分|不能判断|事实不清|尚未查清|待核(?:实)?|部分支持|待补证|无法确认|无法判定|未决|尚不能定案|前.*不得.*(?:认定|确认).*完成'
    for paragraph in re.split(r'\n\s*\n', memo):
        subject, activity = None, False
        for clause in re.split(r'[。！？；\n]', paragraph):
            clause = re.sub(r'\s+', '', clause)
            explicit = {case['event'] for case in truth['cases']
                        if case['event'] in clause or case['name'] in clause}
            if explicit:
                subject = next(iter(explicit)) if len(explicit) == 1 else None
                activity = False
            if subject != pending['event']:
                continue
            activity = activity or has(clause, r'消防演练')
            # A later legal caveat or another person's issue is not this activity's finding.
            relevant = has(clause, r'消防演练|该事项|该事件|调休|实际休息|该时段|活动|事实|定案|待补证|维持.*待核|列.*待核')
            assertion = re.sub(r'(?:并非|不是|不再|无需|无须|不属于)(?:待核(?:实)?|待补证|未决|部分支持)', '', clause)
            if activity and relevant and has(assertion, unresolved):
                return True
    return False


def scoped_report_actions(memo, case, truth):
    excerpts = []
    named_groups = {}
    for paragraph in re.split(r'\n\s*\n', memo):
        subjects = set()
        paragraph = re.sub(r'\s+', '', paragraph)
        for sentence in paragraph.split('。'):
            named = {c['event'] for c in truth['cases'] if c['event'] in sentence or c['name'] in sentence}
            if len(named) > 1 and has(sentence, r'重开|异常|人工复核|待补证'):
                named_groups[len(named)] = named
        # Line wraps do not change ownership; a new named subject does.
        for clause in re.split(r'[。；，,]', paragraph):
            explicit = {c['event'] for c in truth['cases'] if c['event'] in clause or c['name'] in clause}
            if explicit:
                subjects = explicit
            else:
                reference = re.search(r'([1-9一二三四五六七八九])(?:个|项|条)(?:异常|待核|未决|重开)(?:事件|事项|记录)?', clause)
                if reference:
                    symbol = reference[1]
                    count = int(symbol) if symbol.isdigit() else '一二三四五六七八九'.index(symbol) + 1
                    subjects = named_groups.get(count, set())
            if case['event'] in subjects and clause:
                excerpts.append(clause)
    return excerpts


def settle_quality(result, truth, params):
    config = params.get('settlement')
    if not config:
        return
    if config['family'] != 'curvature':
        raise ValueError('Unsupported settlement family')
    items = result['items']
    source_weights = {item['id']: item['weight'] for item in items}
    by_id = {item['id']: item for item in items}
    cases = {case['event']: case for case in truth['cases']}
    assigned, owners = set(), []
    for name, group in params['quality_owners'].items():
        if 'event_roles' in group:
            members = [item['id'] for item in items if item['id'].startswith('event:')
                       and cases[item['id'].split(':', 1)[1]]['role'] in group['event_roles']]
        else:
            members = [item['id'] for item in items if item['id'].startswith(group['item_prefix'])]
        if not members or assigned.intersection(members):
            raise ValueError('Quality ownership is missing or duplicated')
        assigned.update(members)
        denominator = math.fsum(source_weights[key] for key in members)
        completion = math.fsum(source_weights[key] * by_id[key]['completion'] for key in members) / denominator
        owners.append({'id': name, 'weight': group['weight'], 'completion': completion,
                       'earned': group['weight'] * completion, 'members': members,
                       'aggregation': 'original-source-weighted mean of independent work'})
        for key in members:
            item = by_id[key]
            item['weight'] = group['weight'] * source_weights[key] / denominator
            item['earned'] = item['weight'] * item['completion']
    if assigned != set(by_id) or not math.isclose(math.fsum(o['weight'] for o in owners), 1, abs_tol=1e-12):
        raise ValueError('Quality ownership must cover all measured leaves with normalized weights')
    quality = min(1.0, math.fsum(owner['earned'] for owner in owners))
    utility = quality
    result['quality_owners'] = owners
    result['positive_earned'] = quality
    result['positive_utility'] = utility
    result['reward_strict'] = max(config['minimum_retention'] * utility,
                                  utility - result['deduplicated_business_damage'])
    result['formula'] = 'max(0, B - distinct_business_damage)'
    result['settlement'] = config


def field_role(value):
    value = compact(value)
    return next((key for key, aliases in ALIASES.items() if value in aliases), None)


def number(value):
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    value = text(value).replace(',', '')
    if re.fullmatch(r'-?\d+(?:\.\d+)?(?:\s*(?:h|hours?|小时))?', value, re.I):
        return float(re.search(r'-?\d+(?:\.\d+)?', value).group())
    matched = re.fullmatch(r'(\d+)\s*(?:小时|时)\s*(\d+)\s*(?:分钟|分)', value)
    return int(matched[1]) + int(matched[2]) / 60 if matched else None


def excel_number(value):
    if isinstance(value, dt.time):
        return (value.hour * 3600 + value.minute * 60 + value.second) / 86400
    if isinstance(value, (dt.datetime, dt.date)):
        return openpyxl.utils.datetime.to_excel(value)
    if isinstance(value, (int, float)):
        return value
    raise ValueError('Non-numeric formula operand')


def resolve_cell(sheet, cached, cell, trail=()):
    return formulas.evaluate(sheet, cached, cell, trail)


def extract_raw(path):
    with zipfile.ZipFile(path) as archive:
        if sum(entry.file_size for entry in archive.infolist()) > 80_000_000:
            raise ValueError('Expanded workbook exceeds 80 MB')
    book = openpyxl.load_workbook(path, data_only=False)
    cached = openpyxl.load_workbook(path, data_only=True)
    rows = []
    for sheet in book:
        if sheet.max_row > 3000 or sheet.max_column > 100:
            raise ValueError('Workbook dimensions exceed review limits')
        for raw in sheet:
            roles = {index: field_role(cell.value) for index, cell in enumerate(raw) if field_role(cell.value)}
            if 'event' not in roles.values():
                continue
            header_row = raw[0].row
            for cells in sheet.iter_rows(min_row=header_row + 1):
                values, locators = {}, {}
                for index, role in roles.items():
                    value = resolve_cell(sheet, cached[sheet.title], cells[index])
                    if role in values and text(values[role]) != text(value):
                        values[role] = '[ambiguous duplicate columns]'
                    else:
                        values[role] = value
                    locators.setdefault(role, []).append(f'{sheet.title}!{cells[index].coordinate}')
                event = re.fullmatch(r'EV\d{6}-\d{2}(?:-REST)?', text(values.get('event')), re.I)
                if event:
                    values['event'] = event.group().upper()
                    rows.append({'fields': values, 'locators': locators, 'location': f'{sheet.title}!row{cells[0].row}'})
            break
    return rows


def normalized_status(value):
    value = compact(value).rstrip('。.;；')
    choices = {
        'supported': {'支持', '有效', '调休有效', '证据完整', '可以确认', '已实际休息', 'supported', 'valid', 'confirmed'},
        'unsupported': {'不支持', '无效', '不能确认', '不认可', '不可按已完成结案', '未完成', '未落实',
                        'unsupported', 'invalid', 'notcompleted', 'notestablished'},
        'pending': {'部分支持', '待核实', '待补证', '存在冲突', '证据冲突', '尚不能定案', 'pending', 'unresolved', 'partiallysupported'},
        'na': {'不适用', '无需调休', '无须调休', '不涉及', 'na', 'notapplicable'},
    }
    return next((key for key, options in choices.items() if value in options), None) or carrier.rest_state(value)


def employer_state(value):
    lines = [compact(v) for v in text(value).splitlines()]
    explicit = {v for v in lines if v in {'是', 'yes', 'true', '否', 'no', 'false'}}
    if explicit and not (explicit & {'是', 'yes', 'true'} and explicit & {'否', 'no', 'false'}):
        return bool(explicit & {'是', 'yes', 'true'})
    value = compact(value)
    if value in {'是', 'yes', 'true', '门店安排', '由门店安排'} or re.match(r'^是[，,。:：]', text(value)):
        return True
    if value in {'否', 'no', 'false', '员工换班', '否，员工换班', '否,员工换班', '个人到店'}:
        return False
    if has(value, r'员工申请|员工提出|个人.*到店|非门店|不.*门店安排'):
        return False
    if has(value, r'门店安排|门店提出') and not has(value, r'否|未安排|无安排'):
        return True
    return None


def classification(case, values):
    role = case['role']
    employer = employer_state(values.get('employer'))
    roster, work = text(values.get('roster')), compact(values.get('work'))
    narrative = re.sub(r'\s+', ' ', text(values.get('_narrative')))
    if role == 'swap_work':
        return (employer is False or has(narrative, r'员工.*换班|经批准.*换班|双方确认.*班前审批|批准.*换班')) and has(narrative + roster + work, r'换班|approved.*swap') and has(narrative + work, r'不.*休息日.*到岗|不是.*临时.*到岗|不.*门店.*到岗|按.*(?:更新|换班后|批准后).*班次|按.*批准后.*换班安排|换班后.*(?:工作日|正常班)|不产生调休|normalwork')
    if role == 'swap_rest':
        return has(narrative + roster, r'换班后.*休息日|换班.*正常休息|approved.*swap.*rest') and has(narrative + work, r'未见.*工作|无.*工作|未.*到岗|未要求.*到岗|未安排.*到岗|nowork|notworked')
    if role == 'no_work':
        return (employer is False or has(narrative, r'未安排.*任务|无.*任务|非工作性|个人物品')) and has(narrative + roster, r'休息日|rest.day') and (work in {'不支持', '未工作', '无工作', '无实际劳动', 'nowork', 'unsupported'} or has(narrative + work, r'不(?:认定|支持|构成).*(?:工作|劳动)|未(?:提供|证实).*劳动|未安排.*任务|无.*工作|个人物品'))
    affirmative = work in {'支持', '属实', '有实际工作', '实际工作', '已工作', 'supported', 'confirmed', 'worked', '成立'} or has(work, r'确有工作|门店安排原休息日工作|(?:到岗|现场|负责|处理).*(?:处理|工作|负责|交接|协调)|实际工作.*(?:成立|支持)|已(?:确认|证实).*(?:工作|承担|劳动)|工作事实.*支持|支持提供劳动|确认提供劳动|顶班')
    affirmative = affirmative or has(text(values.get('action')) + roster, r'到岗(?:事实)?成立|工作(?:事实)?(?:成立|属实)|门店安排休息日到岗|休息日到岗（门店安排）|休息日(?:工作|到岗)事实.*(?:支持|成立)|休息日到岗与调休均成立')
    return (employer is True or has(narrative + roster, r'门店(?:安排|提出).*到岗|门店安排[：:]|休息日.*到岗.*成立|主管.*(?:确认|安排).*到岗|是否门店提出到岗[：:]是|经理.*(?:通知|安排).*到岗|部安排(?:其)?到岗|休息日临时到岗.*门店安排')) and has(narrative + roster, r'休息日|rest.day') and affirmative


def action_correct(case, values):
    value = text(values.get('action'))
    if has(value, r'例如|仅供示例|候选方案|引文|example|candidate|quoted'):
        return False
    role = case['role']
    if role == 'retain':
        return has(value, r'保留|认可|维持|留档|归档|调休.*(?:成立|闭合|闭环|已实际完成|已完成|已实际补休|已实际休息|可确认|相互支持)|支持.*调休(?:闭环|处理方向)|可(?:作|支持).*调休处理|retain|accept') and has(value, r'调休|对应关系|记录链|证据|leave')
    if role == 'recheck':
        return has(value, r'补证|核实|核验|调查|更正|纠正|重开|待办|冻结|evidence|investigat') and has(value, r'复核.*工资|工资.*复核|重新.*工资|工资.*重新|重开.*工资|工资.*重开|薪资|工资.*更正|payroll.*review|review.*payroll')
    if role in {'swap_work', 'swap_rest'}:
        approved = has(value + text(values.get('work')) + text(values.get('roster')), r'批准.*换班|换班.*归档|换班.*(?:班前|事前).*审批|双方确认.*班前审批|主管.*班前.*(?:审批|批准)|approved.*swap')
        appropriate = has(value, r'不纳入|不属于|不属|非门店.*到岗|不是休息日到岗|不作为|不认定|不产生调休|不构成|不应.*混同|不应.*混用|按.*(?:更新|批准|换班后).*班次|保持换班分类|支持按批准换班|与.*批准换班.*性质一致|换班.*(?:闭环|处理|正确)|exclude|outside')
        return approved and appropriate
    if role == 'investigate':
        return has(value, r'消防演练|fire.*drill') and has(value, r'签到|安排|任务|sign.in|schedule|assignment') and has(value, r'后再|待核|未决|补证|查清|取证后|再决定|前.*(?:不|未)|后.*(?:决定|判断|核定)|在取得|先.*核|before.*decid|pending|investigat')
    if role == 'missing_leave':
        return has(value, r'调休.*申请|申请.*调休|调休.*安排|安排.*调休|leave.*application') and has(value, r'工资.*复核|复核.*工资|工资.*决定|决定.*工资|工资.*处理|payroll.*review|review.*payroll')
    return has(value, r'不生成|不认定|不作为|不纳入|不支持|exclude|no.*work') and has(value, r'保留|留档|归档|retain|archive')


def valid_citations(case, value, truth):
    citations = set()
    supervisor = 'SC-' + case['event'][4:8] + '-' + case['event'][-2:]
    if supervisor in text(value):
        citations.add(5)
    if case['role'].startswith('swap') and 'SWP-0711-03' in text(value):
        citations.add(3)
    labels = {1: '排班', 2: '门禁|考勤', 3: '换班', 4: '调休', 6: '工资'}
    parts = re.split(r'[;；\n]', text(value))
    for part in parts:
        for category, label in labels.items():
            prefix = re.search(rf'(?:^|[\s\[【；;])(?:0{category}|[SFP]{category})(?!\d)', part, re.I)
            named = has(part, label)
            if not (prefix or named):
                continue
            if category == 3 and 'SWP-0711-03' in part and case['role'].startswith('swap'):
                citations.add(3)
                continue
            row_match = re.search(r'第\s*([\d、,，\s]+)\s*行|rows?\s*([\d,\s]+)|\br\s*(\d+)\b|行\s*(\d+)', part, re.I)
            requested = {int(n) for n in re.findall(r'\d+', next((g for g in row_match.groups() if g), ''))} if row_match else set()
            requested.update(int(n) for column, n in re.findall(r'\b([A-Z]{1,3})(\d+)\b', part)
                             if column not in {'EV', 'SC', 'HR', 'S', 'F', 'P'} and int(n) <= 3000)
            matching = []
            for sheet in truth.get('source_rows', {}).get(str(category), []):
                for row in sheet['rows']:
                    content = ' '.join(text(item) for item in row['values'])
                    if case['event'] in content or case['employee'] in content or case['name'] in content:
                        if not requested or row['row'] in requested:
                            matching.append(row)
            event_ref = case['event'] in part or case['employee'] in part or case['name'] in part
            if matching and (requested or event_ref):
                citations.add(category)
        if (re.search(r'(?:05|[SFP]5)|主管', part, re.I)
                and (case['event'] in part or re.search(r'第\s*\d+\s*(?:条|项)|[Ll]ines?\s*\d+|[Ll]\d+|第\s*\d+[-—–至]\d+行|(?:txt)?行\s*\d+', part))):
            citations.add(5)
    return citations


def normalize(rows):
    groups, calculations, followups = {}, {}, {}
    for row in rows:
        values = row['fields']
        event = values['event']
        if any(key in values for key in ['rest', 'work', 'roster', 'action', 'payroll', 'evidence']):
            groups.setdefault(event, []).append(row)
        if all(key in values for key in ['interval', 'start', 'end']) and not (
                text(values['start']) in {'—', '-', '无', '无记录'} and text(values['end']) in {'—', '-', '无', '无记录'}):
            calculations.setdefault(event, []).append(row)
        if any(key in values for key in ['issue', 'needed', 'owner', 'milestone']):
            followups.setdefault(event, []).append(row)
    observations = {}
    for event, presentations in groups.items():
        fields, conflicts = {}, []
        for field in ALIASES:
            field_presentations = presentations
            if field == 'rest':
                priority = max((row['fields'].get('_rest_priority', 0) for row in presentations if field in row['fields']), default=0)
                field_presentations = [row for row in presentations if row['fields'].get('_rest_priority', 0) == priority]
            candidates = {compact(row['fields'][field]): row['fields'][field] for row in field_presentations
                          if field in row['fields'] and text(row['fields'][field])}
            if field == 'rest':
                candidates = {normalized_status(value) or compact(value): value for value in candidates.values()}
            if len(candidates) == 1:
                fields[field] = next(iter(candidates.values()))
            elif len(candidates) > 1:
                if field in {'rest', 'employer'}:
                    normalize_value = normalized_status if field == 'rest' else employer_state
                    states = {normalize_value(v) for v in candidates.values()} - {None}
                    if len(states) == 1:
                        fields[field] = next(v for v in candidates.values() if normalize_value(v) in states)
                    elif len(states) > 1:
                        conflicts.append(field)
                elif field == 'payroll':
                    states = {}
                    for candidate in candidates.values():
                        normalized = compact(candidate)
                        if re.search(r'不生成|无需生成|不应生成', normalized):
                            states.setdefault('不生成', candidate)
                        elif re.search(r'未生成|尚未生成', normalized):
                            states.setdefault('未生成', candidate)
                        elif re.search(r'已生成|已支付|已发放', normalized):
                            states.setdefault('已生成', candidate)
                    if len(states) == 1:
                        fields[field] = next(iter(states.values()))
                    elif len(states) > 1:
                        conflicts.append(field)
                elif field in {'evidence', 'action', 'roster', 'work', 'name', 'employee'}:
                    fields[field] = '\n'.join(text(v) for v in candidates.values())
        fields['_narrative'] = '\n'.join(row['fields'].get('_narrative', '') for row in presentations)
        if 'employer' not in fields:
            states = [employer_state(row['fields'].get('employer')) for row in presentations]
            states = [state for state in states if state is not None]
            if states and len(set(states)) == 1:
                fields['employer'] = '是' if states[0] else '否'
        observations[event] = {'fields': fields, 'conflicts': conflicts,
                               'locations': [row['location'] for row in presentations]}
    return observations, calculations, followups


def seconds(value):
    if isinstance(value, (int, float)):
        return (float(value) % 1) * 86400
    matched = re.search(r'(\d{1,2}):(\d{2})(?::(\d{2}))?', text(value))
    return int(matched[1]) * 3600 + int(matched[2]) * 60 + int(matched[3] or 0) if matched else None


def score(output):
    truth = json.loads((HERE / 'ground_truth.json').read_text(encoding='utf-8'))
    params = json.loads((HERE / 'scoring_params.json').read_text(encoding='utf-8'))
    weights = params.get('measurement_weights', params.get('positive_weights'))
    path, memo_path = output / 'rest-day-review.xlsx', output / 'review-conclusions.txt'
    result = {'scorer_version': VERSION, 'items': [], 'damage': [], 'parse_diagnostics': [],
              'positive_earned': 0.0, 'deduplicated_business_damage': 0.0, 'reward_strict': 0.0,
              'reward_lenient': 0.0, 'reward': 0.0, 'artifact_status': 'missing', 'formula': 'max(0, positive_earned - distinct_business_damage)'}
    memo = memo_path.read_text(encoding='utf-8-sig') if memo_path.is_file() and memo_path.stat().st_size < 1_000_000 else ''
    rows = []
    if path.is_file():
        try:
            if path.stat().st_size > 20_000_000:
                raise ValueError('Workbook exceeds 20 MB')
            rows = carrier.extract(path, truth, resolve_cell)
            result['artifact_status'] = 'parsed' if rows else 'unrecognized_schema'
            result['artifact_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        except (ValueError, OSError, zipfile.BadZipFile, KeyError, TypeError, openpyxl.utils.exceptions.InvalidFileException) as error:
            result['artifact_status'] = 'invalid'
            result['parse_diagnostics'].append(str(error))
    observations, calculations, followups = normalize(rows)
    for case in truth['cases']:
        observation = observations.get(case['event'])
        if not observation:
            continue
        excerpts = scoped_report_actions(memo, case, truth)
        observation['fields']['action'] = '\n'.join([text(observation['fields'].get('action')), *excerpts])
        observation['report_action_excerpts'] = excerpts
    semantic = adjudicate(observations, followups, rows, memo, truth)
    semantic_items = semantic['items']
    result['semantic_measurement'] = semantic
    result['normalized_observations'] = json.loads(json.dumps(observations, default=text))
    items, damage = result['items'], result['damage']

    def add(item_id, weight, completion, locations, evidence):
        items.append({'id': item_id, 'weight': weight, 'completion': completion, 'earned': weight * completion,
                      'locations': locations, 'evidence': evidence})

    def harm(event, kind, evidence, locations):
        if kind not in params['damage_amounts']:
            return
        damage.append({'id': kind, 'damage_instance_key': event + ':' + kind,
                       'amount': params['damage_amounts'][kind], 'evidence': evidence, 'locations': locations})

    for case in truth['cases']:
        event = case['event']
        observation = observations.get(event, {'fields': {}, 'conflicts': [], 'locations': []})
        values, locations = observation['fields'], observation['locations']
        citations = valid_citations(case, values.get('evidence'), truth)
        identity = (not values.get('employee') or case['employee'] in text(values['employee'])) and (not values.get('name') or case['name'] in text(values['name']))
        supported_identity = identity and bool(citations)
        classification_fraction = semantic_items[event + ':classification']['fraction'] if identity and locations else 0.0
        rest_fraction = semantic_items[event + ':rest']['fraction'] if identity and locations else 0.0
        action_fraction = semantic_items[event + ':action']['fraction'] if identity and locations else 0.0
        chronology_fraction = semantic_items[event + ':chronology']['fraction'] if identity and locations else 0.0
        evidence_quality_fraction = semantic_items[event + ':evidence_quality']['fraction'] if identity and locations else 0.0
        classification_ok = classification_fraction == 1
        rest_ok = rest_fraction == 1
        action_ok = action_fraction == 1
        completion = (.25 * classification_fraction + .25 * rest_fraction + .20 * action_fraction
                      + .18 * chronology_fraction + .12 * evidence_quality_fraction)
        add('event:' + event, case['weight'], completion, locations,
            {'classification_correct': classification_ok, 'classification_fraction': classification_fraction,
             'leave_correct': rest_ok, 'leave_fraction': rest_fraction,
             'action_correct': action_ok, 'action_fraction': action_fraction,
             'chronology_fraction': chronology_fraction,
             'evidence_quality_fraction': evidence_quality_fraction,
             'identity_correct': identity, 'source_categories': sorted(citations),
             'semantic_evidence': {key: semantic_items[event + ':' + key]
                                   for key in ('classification', 'rest', 'action', 'chronology', 'evidence_quality')}})
        # Evidence credit requires a correct adopted decision, not an unconnected citation list.
        required = set(case['required_sources'])
        evidence_fraction = len(required & citations) / len(required) if classification_ok and rest_ok else 0.0
        add('evidence:' + event, weights['evidence_chains'] / len(truth['cases']), evidence_fraction, locations,
            {'required_source_categories': sorted(required), 'verified_source_categories': sorted(citations)})
        payroll = compact(values.get('payroll'))
        payroll_fraction = semantic_items[event + ':payroll']['fraction'] if identity and locations else 0.0
        payroll_ok = payroll_fraction == 1
        payroll_rows = [r for r in rows if r['fields']['event'] == event and 'payroll' in r['fields']]
        payroll_values, payroll_locations = [], []
        for row in rows:
            fields = row['fields']
            if fields['event'] != event:
                continue
            scoped = number(fields.get('payroll_hours'))
            if scoped is None and re.search(r'工资|薪资', fields.get('_sheet', '')):
                scoped = number(fields.get('ledger_hours'))
            if scoped is not None:
                payroll_values.append(scoped)
                payroll_locations.append(row['location'])
            for match in re.finditer(r'(?:工资表|工资明细|工资处理明细|薪资表)[^。；\n]{0,12}?'
                                     r'调休(?:登记)?(?:时长|小时)?\s*[=:：]?\s*(\d+(?:\.\d+)?)',
                                     fields.get('_narrative', '')):
                payroll_values.append(float(match[1]))
                payroll_locations.append(row['location'])
        registered = payroll_values[0] if payroll_values else number(values.get('ledger_hours'))
        hours_ok = registered is not None and all(math.isclose(n, case['ledger_hours'], abs_tol=.001)
                                                   for n in (payroll_values or [registered]))
        add('payroll:' + event, weights['payroll_reconciliation'] / len(truth['cases']),
            payroll_fraction * float(hours_ok and supported_identity and 6 in citations), locations,
            {'payroll_status': values.get('payroll'), 'registered_hours': registered,
             'scoped_payroll_readings': payroll_values, 'payroll_reading_locations': payroll_locations,
             'semantic_evidence': semantic_items[event + ':payroll']})
        if 'rest' in observation['conflicts'] or 'employer' in observation['conflicts'] or 'work' in observation['conflicts']:
            harm(event, 'conflicting_adopted_answer', observation['conflicts'], locations)
        if payroll in {'已生成', '已支付', '已发放', 'paid', 'generated', 'settled'}:
            harm(event, 'false_paid_status', values.get('payroll'), locations)

    for expected in truth['intervals']:
        event = expected['event']
        candidates = calculations.get(event, [])
        # An additional dated interval is not a calculation for the original attendance day.
        candidates = [row for row in candidates if not re.match(r'\d{4}-\d{2}-\d{2}', text(row['fields'].get('date')))
                      or text(row['fields']['date'])[:10] == expected['start'][:10]]
        outcomes = []
        for row in candidates:
            values = row['fields']
            start, end = seconds(values.get('start')), seconds(values.get('end'))
            hours = number(values.get('interval'))
            expected_start, expected_end = seconds(expected['start']), seconds(expected['end'])
            identity = not values.get('name') or expected['name'] in text(values['name'])
            correct = (identity and start is not None and end is not None and hours is not None and
                       math.isclose(start, expected_start, abs_tol=1) and math.isclose(end, expected_end, abs_tol=1) and
                       math.isclose(hours, (end - start) / 3600, abs_tol=.015))
            outcomes.append(correct)
        add('interval:' + event, weights['intervals'] / len(truth['intervals']), float(bool(outcomes) and all(outcomes)),
            [row['location'] for row in candidates], {'submitted_recomputations': outcomes})

    for event in ['EV260706-02', 'EV260719-05', 'EV260809-07', 'EV260816-08']:
        candidates = followups.get(event, [])
        followup = semantic_items[event + ':followup']
        add('followup:' + event, weights['followup_register'] / 4, followup['fraction'],
            [row['location'] for row in candidates], {'semantic_evidence': followup})

    for key in ('report:payroll_control', 'report:version_control', 'report:limits'):
        verdict = semantic_items[key]
        add(key, weights['report'] / 3, verdict['fraction'], ['review-conclusions.txt'],
            {'semantic_evidence': verdict})
    # Unsupported pay amounts remain a hard completion failure below.  They are
    # not also charged as strict business damage: applying both deductions for
    # the same prohibited operation double-counts one requirement.
    amounts = re.findall(r'(?:应付金额|欠付金额|补发金额|应(?:补)?付.*加班工资)[^。；\n]{0,20}?\d[\d,.]*\s*元', memo)
    merged = {}
    for item in damage:
        key = item['damage_instance_key']
        if key not in merged:
            merged[key] = item
        else:
            merged[key]['locations'] = sorted(set(merged[key]['locations'] + item['locations']))
    result['damage'] = list(merged.values())
    result['positive_earned'] = min(1.0, math.fsum(item['earned'] for item in items))
    result['deduplicated_business_damage'] = math.fsum(item['amount'] for item in merged.values())
    result['reward_strict'] = max(0.0, result['positive_earned'] - result['deduplicated_business_damage'])
    settle_quality(result, truth, params)
    by_id = {item['id']: item for item in items}
    must_haves = [
        {'id': 'deliverables', 'passed': result['artifact_status'] == 'parsed' and bool(memo.strip()),
         'evidence': {'workbook': result['artifact_status'], 'memo_present': bool(memo.strip())}},
        {'id': 'core_decisions', 'passed': all(by_id['event:' + c['event']]['evidence']['classification_correct']
                                             and by_id['event:' + c['event']]['evidence']['leave_correct'] for c in truth['cases']),
         'evidence': {c['event']: by_id['event:' + c['event']]['evidence'] for c in truth['cases']}},
        {'id': 'reproducible_intervals', 'passed': all(by_id['interval:' + r['event']]['completion'] == 1 for r in truth['intervals']),
         'evidence': {r['event']: by_id['interval:' + r['event']]['evidence'] for r in truth['intervals']}},
        {'id': 'event_citations', 'passed': all(by_id['evidence:' + c['event']]['completion'] == 1 for c in truth['cases']),
         'evidence': {c['event']: by_id['evidence:' + c['event']]['evidence'] for c in truth['cases']}},
        {'id': 'actionable_followups', 'passed': all(by_id['followup:' + event]['completion'] == 1
                                                   for event in ('EV260706-02', 'EV260719-05', 'EV260809-07', 'EV260816-08')),
         'evidence': {event: by_id['followup:' + event]['evidence']
                      for event in ('EV260706-02', 'EV260719-05', 'EV260809-07', 'EV260816-08')}},
        {'id': 'no_pay_amount', 'passed': not amounts, 'evidence': {'adopted_amounts': amounts}},
    ]
    result['must_haves'] = must_haves
    result['reward_lenient'] = float(all(check['passed'] for check in must_haves))
    result['reward'] = result['reward_strict']
    result['self_reported_scores_ignored'] = True
    result['semantic_review'] = 'Event meaning and follow-up equivalence are adjudicated by the source-bound semantic judge; numeric, identity and citation bindings remain programmatic.'
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('artifact_root', nargs='?')
    parser.add_argument('--workspace')
    parser.add_argument('--log-dir')
    args = parser.parse_args()
    target = args.workspace or args.artifact_root
    if not target:
        parser.error('Provide --workspace or an artifact directory')
    output = Path(target) / 'output' if args.workspace or (Path(target) / 'output').is_dir() else Path(target)
    logs = Path(args.log_dir) if args.log_dir else Path(tempfile.mkdtemp(prefix='rest-day-judge-'))
    logs.mkdir(parents=True, exist_ok=True)
    for filename in ['reward.txt', 'reward_strict.txt', 'reward_lenient.txt', 'reward.json', 'reward_detail.json']:
        (logs / filename).unlink(missing_ok=True)
    result = score(output)
    (logs / 'reward_detail.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for filename, value in [('reward.txt', result['reward']), ('reward_strict.txt', result['reward_strict']), ('reward_lenient.txt', result['reward_lenient'])]:
        (logs / filename).write_text(repr(value) + '\n', encoding='ascii')
    reward = {key: result[key] for key in ['reward', 'reward_strict', 'reward_lenient']}
    (logs / 'reward.json').write_text(json.dumps(reward) + '\n', encoding='utf-8')
    print(json.dumps({**result, 'rewards': {'strict': result['reward_strict'], 'lenient': result['reward_lenient']}}))


if __name__ == '__main__':
    main()

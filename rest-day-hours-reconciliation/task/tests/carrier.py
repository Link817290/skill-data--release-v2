"""Schema-independent workbook tables with subject-bound business assertions."""

import datetime as dt
import re

import openpyxl


def clean(value):
    return re.sub(r'[\s_()（）\[\]【】:：/\-①②③④⑤⑥⑦⑧⑨⑩]+', '', str(value or '')).lower()


def role(label):
    if re.search(r'\[h\]:mm|时[:：]分', str(label), re.I):
        return None
    label = clean(label)
    if re.search(r'事件(?:编号|号|标识|id)|原到岗事件|关联事件|涉及事件|受影响事件|影响事件|原事件编号|对应事件|^原事件$|^事件调休登记$|^事件$', label):
        return 'event'
    if re.search(r'引用|引证|证据链|证据来源|来源定位|主要来源|源引用|依据引用|支持证据|出处|^来源$|(?:排班|门禁|考勤|主管|换班|调休|工资).*证据$', label):
        return 'evidence'
    if label in {'来源文件', '文件名', '源文件', '文件'}:
        return 'source_file'
    if re.search(r'行段落定位|来源行号|源行号|页签段落|工作表段落', label):
        return 'source_locator'
    if re.search(r'观(?:察|测)项|观(?:察|测)维度|认定事项|办法要件', label):
        return 'dimension'
    if re.search(r'记录内容|观察内容|观测内容|内容据原始记录', label):
        return 'content'
    if re.search(r'工号|员工编号|employeeid', label):
        return 'employee'
    if re.search(r'姓名|员工$|员工编号部门|员工编号姓名', label):
        return 'name'
    if re.search(r'实际休息|复核分类|调休日.*(?:实际|核验|核对|状态|休息)|调休.*(?:结论|判断|成立|是否|完成情况|落实)', label):
        return 'rest'
    if re.search(r'工资.*(?:处理状态|状态)|工资处理$', label):
        return 'payroll'
    if re.search(r'工资|薪资|payroll', label) and re.search(r'登记|读取|时长|leavehours', label):
        return 'payroll_hours'
    if re.search(r'(?:登记|调休).*时长|登记.*(?:小时|h)$|工资读取调休|调休登记h|^记录时长$', label):
        return 'ledger_hours'
    if re.search(r'初始排班|原排班|排班状态|事件性质|事项性质|性质分类|事件分类|事件类型|性质认定|事件性质认定|^性质$', label):
        return 'roster'
    if re.search(r'门店.*(?:安排|提出).*到岗|^门店安排$|是否门店安排|发起主体|安排主体|提出主体', label):
        return 'employer'
    if re.search(r'实际工作|现场工作|到岗结论|休息日到岗事实|原事件事实结论|休息日工作认定|工作事实|主管现场确认', label):
        return 'work'
    if re.search(r'(?:需|应).*取得.*(?:证据|材料)|需.*(?:证据|材料)|补证材料|建议补证|所需证据', label):
        return 'needed'
    if re.search(r'责任|主责|协作角色|负责.*角色|取证人|证据提供角色|证据持有人|复核.*角色|决定.*角色', label):
        return 'owner'
    if re.search(r'里程碑|复核时点|完成时限|工资处理关口|回签|请求|主管员工回签|hr复核结论', label):
        return 'milestone'
    if re.search(r'待证事实|证据缺口|证据.*矛盾|待确定.*(?:事实|判断)|待决.*项|未决.*(?:项|问题|事实|风险)|未决原因|待查事实|待核实事项|问题风险|问题争议|争议点|争议事实|待解决.*项|^事项$', label):
        return 'issue'
    if re.search(r'进入|门禁.*入|入场|开始时间', label) and not re.search(r'间隔|时长|小时|分钟|公式|离开|出', label):
        return 'start'
    if re.search(r'离开|门禁.*出|出场|结束时间', label) and not re.search(r'间隔|时长|小时|分钟|公式|进入|入', label):
        return 'end'
    if re.search(r'小时|十进制|区间h|间隔h|在场区间|区间时长h', label) and not re.search(r'登记|调休|班次|差异|说明|时分|校验|时段小时|起止区间小时', label):
        return 'interval'
    if re.search(r'记录日期|事件日期|日期', label) and not re.search(r'调休|申请|审批|开始|离开|进入', label):
        return 'date'
    if re.search(r'最终处置|处理意见|处置建议|复核意见|下游处理|后续.*处理|工资.*复核|处理结论|结论|核心发现|核对结果|记录链|^判断$|^判定$', label):
        return 'action'
    return None


def cell_value(cell):
    value = cell.value
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat(sep=' ') if isinstance(value, dt.datetime) else value.isoformat()
    return '' if value is None else str(value)


def time_fraction(value):
    """Normalize equivalent Excel, Python and clock-string time values."""
    if isinstance(value, (dt.datetime, dt.time)):
        return (value.hour * 3600 + value.minute * 60 + value.second + value.microsecond / 1_000_000) / 86400
    if isinstance(value, (int, float)):
        return float(value) % 1
    match = re.fullmatch(r'\s*(\d{1,2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?\s*', str(value))
    if match:
        hour, minute, second = int(match[1]), int(match[2]), int(match[3] or 0)
        fraction = float('0.' + match[4]) if match[4] else 0.0
        if hour < 24 and minute < 60 and second < 60:
            return (hour * 3600 + minute * 60 + second + fraction) / 86400
    raise ValueError(f'not a supported time value: {value!r}')


def extract(path, truth, resolve):
    book = openpyxl.load_workbook(path, data_only=False)
    cached = openpyxl.load_workbook(path, data_only=True)
    source_aliases = {}
    for sheet in book:
        for cells in sheet:
            aliases = [cell_value(c) for c in cells if re.fullmatch(r'[SFP]\d{1,2}', cell_value(c), re.I)]
            source_files = {int(m[1]): m[0] for c in cells for m in re.finditer(r'0([1-7])_[^\s|｜;；\n]+\.(?:xlsx|txt|rtf)', cell_value(c))}
            if len(source_files) == 1:
                category, filename = next(iter(source_files.items()))
                for alias in aliases:
                    source_aliases[alias.upper()] = {'category': category, 'filename': filename}
    rows = []
    for sheet in book:
        if sheet.max_row > 3000 or sheet.max_column > 100:
            raise ValueError('Workbook dimensions exceed review limits')
        header = None
        header_roles = {}
        context = ''
        current_events = set()
        for cells in sheet:
            populated = [(i, c) for i, c in enumerate(cells) if c.value is not None]
            if not populated:
                continue
            combined = '\n'.join(cell_value(c) for _, c in populated)
            mapped = {i: role(c.value) for i, c in populated if role(c.value)}
            # A business header contains multiple short labels, never event data.
            if (len(mapped) >= 3 and not re.search(r'EV\d{6}-\d{2}', combined)
                    and (any(v == 'event' for v in mapped.values()) or
                         all(v in mapped.values() for v in ['start', 'end']))
                    and sum(len(cell_value(c)) <= 60 for _, c in populated) >= len(populated) * .8):
                header = {i: cell_value(c) for i, c in populated}
                header_roles = mapped
                current_events = set()
                continue
            if header is None:
                context += combined + '\n'
                continue
            fields, locations = {}, {}
            events = set()
            adopted_rest = [i for i, kind in header_roles.items() if kind == 'rest'
                            and re.search(r'结论|成立|判定', header[i])]
            adopted_rest += [i for i, kind in header_roles.items() if kind == 'action'
                             and re.search(r'调休|休息', sheet.title)
                             and re.search(r'核验结论|成立判定|结论与依据', header[i])]
            for index, kind in header_roles.items():
                if kind == 'action' and re.search(r'调休|休息', sheet.title) and re.search(r'核验结论|成立判定|判定|结论', header[index]):
                    kind = 'rest'
                if kind == 'rest' and adopted_rest and index not in adopted_rest:
                    continue
                value = resolve(sheet, cached[sheet.title], cells[index])
                if kind == 'event':
                    events.update(re.findall(r'EV\d{6}-\d{2}(?:-REST)?', cell_value(cells[index])))
                if value is None or str(value).strip() == '':
                    continue
                fields.setdefault(kind, []).append(value)
                locations.setdefault(kind, []).append(f'{sheet.title}!{cells[index].coordinate}')
            interval_bound = False
            if 'start' in fields and 'end' in fields:
                for interval in truth['intervals']:
                    employee = next(c['employee'] for c in truth['cases'] if c['name'] == interval['name'])
                    if (interval['name'] in combined or employee in combined) and interval['start'][:10] in combined:
                        events = {interval['event']}
                        interval_bound = True
                        break
            if not interval_bound and events and ('name' in fields or 'employee' in fields):
                identities = '\n'.join(str(v) for k in ['name', 'employee'] for v in fields.get(k, []))
                matching = {c['event'] for c in truth['cases'] if c['name'] in identities or c['employee'] in identities}
                if len(matching) == 1:
                    events = matching
            if events:
                current_events = events
            elif any(re.search(r'观察项|观测项|观(?:察|测)维度|认定事项|办法要件', label) for label in header.values()):
                events = current_events
            if not events:
                continue
            for event in sorted(events):
                values = {}
                for kind, components in fields.items():
                    if kind in {'start', 'end', 'interval', 'ledger_hours', 'payroll_hours'}:
                        distinct = {round(float(v), 10) if isinstance(v, (int, float)) else str(v): v for v in components}
                        if kind in {'start', 'end'} and len(distinct) > 1:
                            try:
                                normalized = [time_fraction(v) for v in components]
                                if max(normalized) - min(normalized) < 1 / 86400:
                                    distinct = {str(components[0]): components[0]}
                            except (ValueError, TypeError):
                                pass
                        if len(distinct) == 1:
                            values[kind] = next(iter(distinct.values()))
                        else:
                            # Keep payroll and leave ledger observations separate.
                            if kind == 'ledger_hours':
                                numeric = [(i, c) for i, c in populated if header_roles.get(i) == kind]
                                if '工资' in sheet.title or '薪资' in sheet.title:
                                    numeric = [(i, c) for i, c in numeric if '台账' not in header[i]]
                                if len(numeric) == 1:
                                    values[kind] = resolve(sheet, cached[sheet.title], numeric[0][1])
                            continue
                    else:
                        values[kind] = '\n'.join(str(v) for v in components)
                if 'source_file' in values:
                    values['evidence'] = ' | '.join([values.get('evidence', ''), values['source_file'],
                                                    values.get('source_locator', '').replace('\n', ' '), event])
                inline = re.findall(r'\[([SFP]\d{1,2}(?:[-,，][SFP]?\d{1,2})*)\]', combined, re.I)
                if inline:
                    refs = []
                    for chunk in inline:
                        for alias in re.findall(r'[SFP]\d{1,2}', chunk, re.I):
                            definition = source_aliases.get(alias.upper())
                            if definition:
                                refs.append(definition['filename'] + ' | ' + event)
                    values['evidence'] = '\n'.join([values.get('evidence', ''), *refs])
                dimension = values.get('dimension', '')
                if dimension:
                    kind = role(dimension)
                    if kind and 'content' in values:
                        values[kind] = values['content']
                    elif kind == 'work' and 'action' in values:
                        values[kind] = values['action'].splitlines()[0]
                    if re.search(r'实际休息|调休.*(?:结论|成立)', dimension) and 'action' in values:
                        values['rest'] = values['action']
                if 'evidence' in values:
                    for alias, definition in source_aliases.items():
                        values['evidence'] = re.sub(r'\b' + alias + r'\b', definition['filename'], values['evidence'], flags=re.I)
                if 'rest' in values:
                    rest_headers = [header[i] for i, kind in header_roles.items() if kind == 'rest'
                                    or (kind == 'action' and re.search(r'调休|休息', sheet.title))]
                    values['_rest_priority'] = 3 if any(re.search(r'结论|判定|成立性|实际休息判断|实际休息认定', v) for v in rest_headers) else 1
                adopted = re.search(r'调休(?:事实)?(?:不成立|成立|未落实|未实现|未安排|未发生|已实际休息|已实际完成|完全缺失|是否[^。；\n]{0,25}未决)', values.get('action', ''))
                if adopted:
                    values['rest'] = adopted[0]
                    values['_rest_priority'] = 3
                values['event'] = event
                values['_narrative'] = combined
                values['_headers'] = header
                values['_context'] = context
                values['_sheet'] = sheet.title
                values['_source_aliases'] = source_aliases
                rows.append({'fields': values, 'locators': locations,
                             'location': f'{sheet.title}!row{cells[0].row}'})
    return rows


def rest_state(value):
    value = clean(value).rstrip('。.;；')
    value = re.sub(r'未安排(?:其)?到岗|未要求(?:其)?到岗', '无工作安排', value)
    if value in {'不适用', 'na', 'notapplicable'} or re.search(r'不适用|无需调休|无须调休|不是调休台账|不产生调休|不作为.*(?:临时到岗|休息日工作|休息日到岗).*事件|未到岗.*无调休|换班后.*休息(?:日|安排)|换班后的有效安排|仍按休息日处理|仍为休息日', value):
        return 'na'
    if re.search(r'事实冲突|相冲突|完成标记.*冲突|不成立|未成立|未实际(?:休息|发生)|未发生|未落实|未实现|未安排调休|调休完全缺失|调休.{0,10}未安排|^(?:调休)?(?:尚)?未安排', value):
        return 'unsupported'
    if re.search(r'部分支持|性质未明|未决|未解决|待(?:核|证|定|补)|无法(?:判|确)|不能区分|尚不能定案|是否.*(?:不明|待)|落实待证', value):
        return 'pending'
    if re.search(r'不成立|未成立|不满足|不支持|不能(?:认定|确认)|未实际(?:休息|发生)|未完成|未实现|未发生|不认可|未落实|未证明|不存在|无效', value):
        return 'unsupported'
    if re.search(r'成立|支持|已实际(?:休息|完成|补休)|已休息|已落实|有效|内部.*闭环|休息事实.*核证|无工作安排.*未见.*工作', value):
        return 'supported'
    if value in {'是', '满足', '认可', '通过', '已完成'}:
        return 'supported'
    if value in {'否', '不满足', '不认可'}:
        return 'unsupported'
    return None

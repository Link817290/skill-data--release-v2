"""Source-backed event bindings, independent of model identity or candidate scores."""
import re

SLOTS = {(600, 630), (640, 670), (680, 710)}
RANGE = re.compile(r'(?<!\d)(\d{1,2}):([0-5]\d)(?:—|–|-|~|至|到)(\d{1,2}):([0-5]\d)')
PROVISIONAL = re.compile(r'待确认|待批准|需批准|申请|建议|拟|假设|未确定|不采用|不得采用|不应采用|未批准')
DATE = re.compile(r'(?:6月(19|20)日|6[./-](19|20)(?!\d)|(19|20)日)')
CRAFT = r'手作|非遗体验|体验课|体验第[一二三123]|体验场次|体验每场|碱水粽|香囊|合香'
STAGE = r'主题表演|表演|演出|傩舞|采茶戏'
ZONE_CRAFT = rf'{CRAFT}|(?<!互动)体验'
REJECTED = re.compile(
    r'仅供选择|不执行|不采用|未采用|未批准|不(?:安排|举办|开展|在|设在|采用|执行)'
    r'|取消(?:傩舞|采茶戏|碱水粽|香囊|手作|非遗体验)|不得(?:安排|采用|设在)'
)
SECTION = re.compile(r'^(?:[一二三四五六七八九十]+[、.]|\d+[、.](?!\d))')
WITHDRAWN_PREFIX = re.compile(r'^(?:无需|不用|不必)(?!改动|修改|变更|调整|改变|取消|重新)')


def dates(text):
    return {int(next(x for x in m.groups() if x)) for m in DATE.finditer(text)}


def scoped_spans(spans):
    """Inherit only short explicit daily-program headings, not arbitrary date mentions."""
    current = set()
    for span in spans:
        text = span['normalized']
        span = {**span, 'withdrawn_prefix': bool(WITHDRAWN_PREFIX.search(text))}
        own = dates(text)
        if span['scope'] == 'paragraph' and len(text) < 95 and SECTION.search(text):
            current = set()
        if span['scope'] == 'paragraph' and len(text) < 95 and len(own) == 1 and re.search(
                r'专场|第一篇章|第二篇章|每日执行|当日流程|执行流程|执行计划|运行方案|碱水粽|采茶戏|香囊', text):
            current = own
        elif span['scope'] == 'paragraph' and len(text) < 95 and re.search(r'每日|两日|两天|通用', text):
            current = {19, 20}
        stamps = list(DATE.finditer(text))
        if len(stamps) > 1 and len(own) > 1:
            for index, stamp in enumerate(stamps):
                stop = stamps[index+1].start() if index+1 < len(stamps) else len(text)
                segment = text[stamp.start():stop]
                yield {**span, 'normalized':segment, 'days':sorted(dates(segment))}
        else:
            yield {**span, 'days': sorted(own or current)}


def adopted_units(spans):
    for span in scoped_spans(spans):
        if span['withdrawn_prefix']:
            continue
        text = span['normalized']
        craft_bound = bool(re.search(CRAFT, text) and not re.search(STAGE, text))
        for clause in re.split(r'[。;；]', span['normalized']):
            if not clause or REJECTED.search(clause):
                continue
            bound_days = dates(clause) or set(span['days'])
            if re.search(r'两天|两日|每天|每日|均为|均按', clause):
                bound_days = {19, 20}
            yield {**span, 'normalized': clause, 'days': sorted(bound_days),
                   'craft_bound': craft_bound}


def zone_evidence(units, role, zone):
    # A venue belongs to the closest named activity, not to every activity in a row.
    object_pattern = re.compile(f'(?:{STAGE})|(?:{ZONE_CRAFT})')
    zones = re.compile(r'一楼广场|外广场|一楼大厅')
    for span in units:
        text = span['normalized']
        objects = list(object_pattern.finditer(text))
        venues = list(zones.finditer(text))
        for venue in venues:
            if not re.fullmatch(zone, venue[0]):
                continue
            previous = [obj for obj in objects if obj.end() <= venue.start()]
            following = [obj for obj in objects if obj.start() >= venue.end()]
            before = previous[-1] if previous else None
            after = following[0] if following else None
            if before and (venue.start() - before.end() > 30
                           or re.search(r'[,，]', text[before.end():venue.start()])
                           or zones.search(text[before.end():venue.start()])):
                before = None
            after_link = text[venue.end():after.start()] if after else ''
            if after and (after.start() - venue.end() > 20 or not re.fullmatch(
                    r'[(:|/、]*(?:安排|进行|用于|开展|举办|承担|作为|为|是)?(?:古风|露天|室内)?', after_link)):
                after = None
            if before:
                earlier = [v for v in venues if v.end() <= before.start()]
                role_to_next = re.fullmatch(
                    r'(?::|在|设在|安排在|地点为|位于)(?:项目博物馆|博物馆)?',
                    text[before.end():venue.start()],
                )
                if earlier and not role_to_next and re.fullmatch(
                        r'[(:|/、]*(?:安排|进行|用于|开展|举办|承担|作为|为|是)?(?:古风|露天|室内)?',
                        text[earlier[-1].end():before.start()]):
                    # That activity already belongs to the preceding venue.
                    before = None
            if after and (after_link.startswith('(') or re.match(r'为|是', after_link)):
                bound = after
            elif before:
                bound = before
            elif after:
                bound = after
            else:
                continue
            if re.fullmatch(role, bound[0]):
                return span
    return None


def facts(spans):
    units = list(adopted_units(spans))
    programs = {}
    for day, performance, craft in [(19, r'傩舞', r'碱水粽|包粽'), (20, r'采茶戏', r'香囊|合香')]:
        p = next((s for s in units if day in s['days'] and re.search(performance, s['normalized'])), None)
        c = next((s for s in units if day in s['days'] and re.search(craft, s['normalized'])), None)
        programs[str(day)] = {'passed': bool(p and c), 'performance': p, 'craft': c}
    observed = {19: set(), 20: set()}
    slot_evidence = []
    for span in units:
        text = span['normalized']
        if not re.search(CRAFT, text) and not span['craft_bound']:
            continue
        for m in RANGE.finditer(text):
            interval = (int(m[1])*60+int(m[2]), int(m[3])*60+int(m[4]))
            if interval in SLOTS:
                for day in span['days']:
                    observed[day].add(interval)
                slot_evidence.append(span)
    stage = zone_evidence(units, STAGE, r'一楼广场|外广场')
    craft = zone_evidence(units, ZONE_CRAFT, r'一楼大厅')
    return [
        {'id':'day-19-program','passed':programs['19']['passed'],'evidence':programs['19']},
        {'id':'day-20-program','passed':programs['20']['passed'],'evidence':programs['20']},
        {'id':'fixed-craft-slots','passed':all(observed[day] == SLOTS for day in (19,20)),
         'evidence':slot_evidence,
         'observed_by_day':{str(day):[list(interval) for interval in sorted(value)]
                            for day,value in observed.items()}},
        {'id':'two-source-zones','passed':bool(stage and craft),'evidence':{'stage':stage,'craft':craft}},
    ]


def contradictions(spans):
    found = {}
    for span in scoped_spans(spans):
        if span['withdrawn_prefix']:
            continue
        for clause in re.split(r'[。;；]',span['normalized']):
            if PROVISIONAL.search(clause):
                continue
            # An admission/check-in interval is not a class interval.
            class_text = re.sub(r'无(?:手作|非遗体验|体验场次|体验课)', '', clause)
            is_class = bool(re.search(CRAFT,class_text) and re.search(
                r'(?:第[一二三123]场|(?:体验|手作|课堂).{0,8}(?:场次|时段|时间)|场次均改|唯一执行场次)',class_text))
            mixed_window = re.search(
                r'(?:上午|下午|全天)(?:场|时段)[(（](?:表演|演出)[+＋、/与及和](?:非遗体验|手作)[)）]',
                class_text)
            explicit_class = re.search(r'(?:体验|手作|课堂)(?:第[一二三123]场|时间|场次)|第[一二三123]场(?:体验|手作|课堂)',class_text)
            if mixed_window and not explicit_class:
                is_class = False
            if is_class and not re.search(r'签到|核销|核验|复位|清场|准备|排队|候场',clause):
                wrong = []
                for m in RANGE.finditer(clause):
                    cell_start = clause.rfind('|',0,m.start())+1
                    cell_stop = clause.find('|',m.end())
                    cell = clause[cell_start:cell_stop if cell_stop >= 0 else len(clause)]
                    # A shared timeline column must not bind a performance's 25-minute
                    # interval to the craft happening concurrently in another column.
                    if '|' in clause and not re.search(CRAFT,cell) and re.search(r'表演|演出|第\d+趴|第[一二三]趴',clause):
                        continue
                    interval = (int(m[1])*60+int(m[2]),int(m[3])*60+int(m[4]))
                    # A summary of the full morning window is compatible, not a fourth slot.
                    if interval not in SLOTS | {(600,710)}:
                        wrong.append(m[0])
                if wrong and not re.search(r'不得|禁止|不能|不应|不改|不采用|不执行|并非|不是',clause):
                    found.setdefault('D06',[]).append({'location':span['location'],'evidence':clause,'wrong_intervals':wrong})
            adopted_other_venue = re.search(
                r'(?:本次活动|表演|演出|非遗体验|手作).{0,35}(?:统一迁往|迁往|改在|设在|地点为|安排在).{0,18}(?:体育馆|体育场|商场|酒店|市民广场|市政府)',clause)
            wrong_floor = re.search(r'(?:表演|演出|非遗体验|手作).{0,20}(?:设在|改在|地点为|安排在).{0,12}(?:二楼|三楼|四楼|地下|负一楼)',clause)
            swapped_zone = False
            unbound_lists = bool(re.search(r'活动\([^)]+\)[^。;；]*地点\([^)]+\)', clause))
            if not unbound_lists and not re.search(r'候场|休息|用餐|午餐|参观|是否|可否|能否|需确认|待确认|未明确', clause):
                local = [{**span, 'normalized': clause}]
                swapped_zone = bool(zone_evidence(local, STAGE, r'一楼大厅')
                                    or zone_evidence(local, ZONE_CRAFT, r'一楼广场|外广场'))
            if (adopted_other_venue or wrong_floor or swapped_zone) and not re.search(r'若|如果|如遇|备选|经.{0,12}(?:批准|确认)|不得|禁止|不能|不应|不采用|并非|不是|不在|不设在',clause):
                found.setdefault('D07',[]).append({'location':span['location'],'evidence':clause})
    return found

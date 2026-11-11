"""Connect complementary controls only inside explicit operational contexts."""
import re

def video_handoff_obligation(span,rule,active_match):
    """An adopted release-approval duty can share a handoff row with its video."""
    if span.get("scope")!="table-row":return False
    text=span["normalized"]
    if not re.search(r"视频|剪辑|成片",text) or not re.search(r"交|留档|资料",text):return False
    for clause in re.split(r"[。;；]",text):
        if not re.search(r"发布审批(?:另行|后续|单独)?(?:完成|执行|办理|落实)",clause):continue
        if re.search(r"照片|图片|文稿",clause) and not re.search(r"视频|剪辑|影像|成片|素材",clause):continue
        if active_match(rule,span):return True
    return False


def medical_readiness(text):
    """Accept an assigned pre-opening check of usable existing response resources."""
    resources = r'(?:急救箱|急救包|急救用品|急救物资|急救资源|急救物品|应急药箱|馆内急救点|馆方医务|合格急救响应|具备急救资质(?:的)?人员)'
    owner = r'(?:人员[甲乙丙丁戊己]|P\d+|馆方(?:安全负责人|对接人|联络人)?|项目负责人|活动负责人|总控|总指挥|急救负责人)'
    before = r'(?:活动前|开场前|开门前|布场前|会前|班前|T-[1-9]\d*|6月18日前|前[一二三四五六七八九十\d]+(?:日|天))'
    action = r'(?:确认|核实|核对|落实|明确|取得|获取|补齐|填入)'
    usable = r'(?:位置|取用|配置|器材|联络|联系|响应|名单|电话|可用)'
    for sentence in re.split(r'[。;；]', text):
        if re.search(r'是否|有无|不(?:需|必|再)?(?:确认|核实|核对|落实|明确|取得|获取|补齐)|无需|不用|不必|不执行|禁止执行|仅供选择', sentence):
            continue
        if not all(re.search(pattern, sentence) for pattern in (resources, owner, before, usable)):
            continue
        assigned = (re.search(r'(?:由|请)' + owner + r'[^。;；|]{0,28}' + action, sentence)
                    or re.search(r'(?<!向)(?<!与)(?<!和)' + owner + r'[^。;；|]{0,12}' + action, sentence)
                    or re.search(r'\|[^|。;；]{0,8}' + owner + r'[^|。;；]{0,8}(?:\||$)', sentence))
        if not assigned:
            continue
        if re.search(action + r'[^。;；]{0,45}' + resources, sentence) or re.search(
                resources + r'[^。;；]{0,65}' + action, sentence):
            return True
    return False


def active_object_control(text, objects, actions):
    for clause in re.split(r'[。;；|]', text):
        if re.search(r'不检查|不核验|不确认|不固定|不收纳|不回收|不归还|不归位|不归库|不归箱|不装箱|不入箱|不签回|不分箱|不断电|不关闭电源|不切断电源|不压护|不覆盖|无需|取消|不再|仅供选择|不执行|待确认|待核验|待检查|尚未确认', clause):
            continue
        if re.search(objects + r'[^。;；|]{0,26}' + actions, clause) or re.search(
                actions + r'[^。;；|]{0,26}' + objects, clause):
            return True
    return False


def same_context(left, right, topic):
    ls, rs = left.get('section', ''), right.get('section', '')
    if ls and rs and ls.split(' / ')[0] == rs.split(' / ')[0] and re.search(topic, ls.split(' / ')[0]):
        return True
    table_left = re.match(r'(B\d+):R', left['location'])
    table_right = re.match(r'(B\d+):R', right['location'])
    return bool(table_left and table_right and table_left[1] == table_right[1]
                and (re.search(topic, ls) or re.search(topic, rs)))


def paired_candidates(spans, name, normalize):
    if name == 'props-cables':
        props = r'(?:道具|铃鼓|茶篮|折扇|傩面具|祭台)'
        wire = r'(?:电线|线缆|电缆)'
        control = r'(?:检查|复核|核验|确认|排查|巡检|整理|收纳|固定|压护|覆盖|稳固放置|沿边布置|避开动线)'
        topic = r'安全|风险|应急|广场|舞台|设备|开场检查'
        lefts = [s for s in spans if active_object_control(s['normalized'], props, control)]
        rights = [s for s in spans if active_object_control(s['normalized'], wire, control)]
    elif name == 'power-return':
        topic = r'收尾|闭场|撤场|清场|交接'
        lefts = [s for s in spans if re.search(topic, s.get('section', ''))
                 and active_object_control(s['normalized'], r'(?:设备|音响|音视频|一体机|话筒)', r'(?:断电|关闭电源|切断电源)')]
        rights = [s for s in spans if re.search(topic, s.get('section', ''))
                  and active_object_control(s['normalized'], r'道具', r'(?:归位|归库|归箱|收回|归还|装箱|入箱|签回|分箱)')]
    else:
        return
    for left in lefts:
        for right in rights:
            if left['location'] == right['location'] or same_context(left, right, topic):
                yield {'location': left['location'] + '+' + right['location'],
                       'scope': 'linked-operational-controls', 'section': left.get('section', ''),
                       'text': left.get('text', left['normalized']) + '; ' + right.get('text', right['normalized']),
                       'normalized': normalize(left['normalized'].replace('|', ' ')) + ';'
                                     + normalize(right['normalized'].replace('|', ' ')),
                       'verified_assertion': name}

"""Detect affirmative, internally infeasible operating timetables."""
import re

from festival_facts import dates, facts

EXCLUDED = re.compile(r'若|如果|备选|仅供选择|不采用|未选用|不执行|不得|不应|不是|并非|无需|取消')
PENDING = re.compile(r'待确认|尚未确定|未确定|待批准')
TIME = re.compile(r'^(\d{1,2}):([0-5]\d)(?:\(拟\)|【拟安排】)?$')


def conflicts(spans):
    rows = [s for s in spans if s['scope'] != 'table-duty']
    found = []
    fixed_slots = facts(rows)[2]
    if fixed_slots['passed']:
        for span in rows:
            text = span['normalized']
            context = span.get('section', '') + ':' + text
            if not re.search(r'体验|手作|碱水粽|香囊|非遗老师', context):
                continue
            for clause in re.split(r'[。;；]', text):
                if EXCLUDED.search(clause) or PENDING.search(clause):
                    continue
                duration = re.search(r'(?:场间|每场间|换场)[^。;；|]{0,10}?(\d+)分钟', clause)
                # A craft reference after the gap may only describe avoiding its
                # check-in peak; it does not change the subject of a performance gap.
                if duration and not re.search(r'体验|手作|碱水粽|香囊|非遗老师',
                                              span.get('section', '') + ':' + text[:text.find(clause) + duration.start()]):
                    continue
                if duration and int(duration[1]) > 10:
                    found.append({'manifestation_id': span['location'],
                                  'kind': 'craft-turnaround-exceeds-fixed-window',
                                  'evidence': clause,
                                  'claimed_minutes': int(duration[1]),
                                  'available_minutes': 10,
                                  'support': fixed_slots['evidence']})
    # Bind duration to the stated program. Never infer June 20's missing total.
    duration_evidence = [s for s in rows if re.search(r'傩舞', s['normalized'])
                         and re.search(r'25分钟', s['normalized'])
                         and not EXCLUDED.search(s['normalized'])
                         and not PENDING.search(s['normalized'])]
    tables = {}
    for span in rows:
        table = re.match(r'(B\d+):R\d+$', span['location'])
        if not table or dates(span.get('section', '')) != {19}:
            continue
        cells = span['normalized'].split('|')
        if len(cells) < 3 or not re.search(r'第[一二三123]场表演', cells[1]):
            continue
        time = TIME.match(cells[0])
        if not time or not re.search(r'主持.*表演队', cells[-1]):
            continue
        if EXCLUDED.search(span['normalized']) or PENDING.search(span['normalized']):
            continue
        tables.setdefault((table[1], cells[-1]), []).append(
            (int(time[1]) * 60 + int(time[2]), span))
    if duration_evidence:
        for starts in tables.values():
            starts.sort(key=lambda item: item[0])
            for (left_time, left), (right_time, right) in zip(starts, starts[1:]):
                if 0 < right_time - left_time < 25:
                    found.append({'manifestation_id': left['location'] + '+' + right['location'],
                                  'kind': 'same-team-performance-overlap',
                                  'evidence': left['normalized'] + '; ' + right['normalized'],
                                  'declared_minutes': 25,
                                  'start_separation_minutes': right_time - left_time,
                                  'overlap_minutes': 25 - (right_time - left_time),
                                  'support': duration_evidence})
    return found

"""Extract editable Office carriers without consulting a submitted JSON ledger."""
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from openpyxl import load_workbook
import xlrd

NAMES = {'HZ240117':'周倩','HZ230086':'何琳','HZ220031':'陈璇','HZ230144':'赵敏','HZ240052':'王雪'}


def plain(value):
    if value is None:
        return ''
    if isinstance(value, (dt.date, dt.datetime)):
        return value.strftime('%Y-%m-%d')
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def paragraphs(container, prefix):
    rows = []
    p_index = 0
    t = 0
    # Employee headings and their tables must stay in the document's physical order.
    parent = container.element.body if hasattr(container.element, 'body') else container._tc
    for child in parent:
        if child.tag.endswith('}p'):
            p_index += 1
            p = Paragraph(child, container)
            if p.text.strip():
                rows.append({'address':prefix + '/P' + str(p_index), 'text':p.text})
            continue
        if not child.tag.endswith('}tbl'):
            continue
        t += 1
        table = Table(child, container)
        for r, row in enumerate(table.rows, 1):
            text = ' | '.join(cell.text for cell in row.cells)
            rows.append({'address':prefix + '/T' + str(t) + '/R' + str(r), 'text':text,
                         'cells':[cell.text for cell in row.cells]})
            for c, cell in enumerate(row.cells, 1):
                for nested in cell.tables:
                    for nr, nrow in enumerate(nested.rows, 1):
                        rows.append({'address':prefix + f'/T{t}/R{r}/C{c}/nested/R{nr}',
                                     'text':' | '.join(nc.text for nc in nrow.cells),
                                     'cells':[nc.text for nc in nrow.cells]})
    return rows


def read_office(path):
    path = Path(path)
    if path.suffix.lower() == '.doc':
        with tempfile.TemporaryDirectory(prefix='office-reader-') as scratch:
            target = Path(scratch) / (path.stem + '.docx')
            # LibreOffice needs private writable caches as well as a private profile.
            for attempt in range(3):
                private = Path(scratch) / ('session-' + str(attempt))
                private.mkdir(mode=0o700)
                env = {**os.environ, 'HOME':str(private), 'XDG_CACHE_HOME':str(private / 'cache'),
                       'XDG_CONFIG_HOME':str(private / 'config'), 'XDG_RUNTIME_DIR':str(private),
                       'SAL_USE_VCLPLUGIN':'svp'}
                profile = (private / 'profile').as_uri()
                proc = subprocess.run(['libreoffice', '-env:UserInstallation=' + profile, '--headless',
                                       '--convert-to', 'docx', '--outdir', scratch, str(path)],
                                      capture_output=True, text=True, env=env, timeout=600)
                if proc.returncode == 0 and target.is_file():
                    break
            else:
                raise RuntimeError('Office conversion failed: ' + proc.stderr[-600:])
            result = read_office(target)
            for row in result:
                row['address'] = path.name + row['address'][len(target.name):]
            return result
    if path.suffix.lower() == '.docx':
        return paragraphs(Document(path), path.name)
    rows = []
    if path.suffix.lower() == '.xls':
        book = xlrd.open_workbook(path, formatting_info=True)
        for sheet in book.sheets():
            for r in range(sheet.nrows):
                vals = []
                for cell in sheet.row(r):
                    value = xlrd.xldate_as_datetime(cell.value, book.datemode) if cell.ctype == xlrd.XL_CELL_DATE else cell.value
                    vals.append(plain(value))
                if any(vals):
                    rows.append({'address':path.name + '/' + sheet.name + '/R' + str(r+1),
                                 'text':' | '.join(vals),'cells':vals,'hidden':bool(sheet.visibility)})
        return rows
    if path.suffix.lower() == '.xlsx':
        book = load_workbook(path, data_only=True)
        for sheet in book:
            for r, values in enumerate(sheet.iter_rows(values_only=True), 1):
                vals = [plain(v) for v in values]
                if any(vals):
                    rows.append({'address':path.name + '/' + sheet.title + '/R' + str(r),
                                 'text':' | '.join(vals),'cells':vals,'hidden':sheet.sheet_state != 'visible'})
        return rows
    raise ValueError('Unsupported editable Office carrier: ' + path.name)


def role(path):
    if path.suffix.lower() in ('.doc', '.docx'):
        return 'report'
    if path.suffix.lower() in ('.xls', '.xlsx'):
        if re.search(r'整改|行动|执行|action', path.stem, re.I):
            return 'actions'
        # File names are not a reliable carrier contract. Accept an actions
        # workbook whose headers identify accountable work, while keeping an
        # ordinary review workbook classified as audit.
        # A corrupt/unreadable carrier is an evaluator error, not evidence that
        # the workbook is an audit carrier. Let the caller report the failure.
        rows = visible_rows(read_office(path))
        primary_container = rows[0]['address'].rsplit('/R', 1)[0] if rows else ''
        primary_rows = [row for row in rows if row['address'].rsplit('/R', 1)[0] == primary_container]
        text = ' | '.join(str(row.get('text', '')) for row in primary_rows[:80]).lower()
        if '整改与审批执行清单' in text or 'corrective action register' in text:
            return 'actions'
        for row in primary_rows[:30]:
            header = ' | '.join(row.get('cells', [])).lower()
            has_owner = bool(re.search(r'责任人|负责人|责任部门|负责部门|负责角色|责任岗位|责任主体|owner', header, re.I))
            has_deadline = bool(re.search(r'完成时点|完成期限|完成时限|截止日期|完成日期|due date|deadline', header, re.I))
            has_closure = bool(re.search(r'关闭证据|关闭凭证|闭环证据|验收证据|完成证据|closure evidence', header, re.I))
            has_action = bool(re.search(r'问题描述|整改事项|整改措施|行动内容|执行内容|corrective action', header, re.I))
            if has_owner and has_deadline and has_closure and has_action:
                return 'actions'
        return 'audit'
    return None


def visible_rows(rows):
    return [r for r in rows if not r.get('hidden')]


def employee_rows(rows, employee):
    name = NAMES[employee]
    active = None
    result = []
    container = None
    for row in visible_rows(rows):
        address = row['address']
        current = address.split('/')[0]
        if current.lower().endswith(('.xls', '.xlsx')):
            current = address.rsplit('/R', 1)[0]
        if current != container:
            active = None
            container = current
        text = row['text']
        mentioned = [key for key, value in NAMES.items() if key in text or value in text]
        if mentioned:
            active = mentioned if len(mentioned) == 1 else None
        elif re.match(r'^(?:[一二三四五六七八九十]+[、.．]|附录|证据索引|合计\s*[|：:]|总体\s*[|：:])', text):
            active = None
        if employee in mentioned or (not mentioned and active and employee in active):
            result.append(row)
    return result


def source_aliases(rows):
    """Resolve explicit source-index links, including evidence -> alias -> file links."""
    links = {}
    for row in visible_rows(rows):
        cells = row.get('cells', [])
        if len(cells) < 2:
            continue
        key = cells[0].strip()
        if not re.fullmatch(r'[A-Za-z][A-Za-z_-]*\d+', key):
            continue
        targets = set(re.findall(r'(?<![A-Za-z0-9-])02-0[1-8](?!\d)', row['text']))
        aliases = set(re.findall(r'(?<![A-Za-z0-9_])[A-Za-z][A-Za-z_-]*\d+(?![A-Za-z0-9_])',
                                 ' '.join(cells[1:])))
        links.setdefault(key, set()).update(targets | aliases)
    resolved = {key: {v for v in targets if re.fullmatch(r'02-0[1-8]', v)}
                for key, targets in links.items()}
    for _ in range(len(links)):
        changed = False
        for key, targets in links.items():
            expanded = set().union(*(resolved.get(v, set()) for v in targets))
            if expanded - resolved[key]:
                resolved[key].update(expanded)
                changed = True
        if not changed:
            break
    return resolved


def cited_sources(text, aliases):
    hits = set(re.findall(r'(?<![A-Za-z0-9-])02-0[1-8](?!\d)', text))
    for token in re.findall(r'(?<![A-Za-z0-9_])[A-Za-z][A-Za-z_-]*\d+(?![A-Za-z0-9_])', text):
        hits.update(aliases.get(token, set()))
    return hits


def scoped(rows, employee):
    return '\n'.join(r['text'] for r in employee_rows(rows, employee))


def action_rows(rows):
    result = []
    headers = None
    container = None
    aliases = {
        'id':r'^(编号|序号|行动编号|行动ID|整改(?:项)?编号|动作编号|事项编号|action_id)$',
        'action':r'问题描述|整改(?:[/／]|或)?(?:补证)?(?:事项|内容|动作)|整改措施|整改[/／]纠正(?:动作|措施)|整改行动|行动内容|具体动作|动作要点|措施内容|纠正.*内容|^行动$|^action$|^具体行动$|^执行内容$|^(?:具体)?整改[/／]审批(?:事项|动作)$|^计划行动$',
        'owner':r'责任人|负责人|责任部门|负责角色|责任岗位|责任角色|责任主体|责任方|^主责(?:角色)?$|^owner$',
        'deadline':r'完成时点|完成期限|完成时限|执行期限|截止|完成时间|完成日期|^期限$|^deadline$',
        'closure':r'关闭证据|关闭凭证|结案证据|闭环(?:证据|凭证)|闭合证据|闭包证据|验收证据|完成(?:留痕证据|凭证|证据|标志)|办结凭证|闭环留痕|关闭留痕|^closure_evidence$',
        'status':r'当前状态|执行状态|截至.{0,15}状态|^状态$|^status$',
    }
    for row in visible_rows(rows):
        current = row['address'].rsplit('/R', 1)[0]
        if current != container:
            headers = None
            container = current
        cells = row.get('cells', [])
        normalized = [re.split(r'\s*[（(\n]', c.strip(), maxsplit=1)[0].strip() for c in cells]
        normalized = [c.split()[0] if re.match(r'^[a-z_]+\s+', c, re.I) else c for c in normalized]
        candidate = {key: next((i for i,c in enumerate(normalized) if re.search(pattern,c,re.I)),None)
                     for key,pattern in aliases.items()}
        # Some tables separate the issue/topic from the executable command.
        explicit_action = next((i for i, c in enumerate(normalized)
                                if re.fullmatch(r'具体动作|具体行动|执行内容|行动内容', c)), None)
        if explicit_action is not None:
            candidate['action'] = explicit_action
        if candidate['action'] is not None and sum(v is not None for v in candidate.values()) >= 3:
            headers = candidate
            continue
        if headers and cells:
            rec = {k:cells[i] if i is not None and i < len(cells) else '' for k,i in headers.items()}
            rec['_address'] = row['address']
            rec['_text'] = row['text']
            administrative = {headers.get(k) for k in ('id', 'owner', 'deadline', 'closure', 'status')}
            rec['_action_context'] = ' | '.join(c for i, c in enumerate(cells) if i not in administrative)
            rec['_complete_header'] = all(headers.get(k) is not None for k in ('id','action','owner','deadline','closure'))
            if rec['action'].strip():
                result.append(rec)
    if any(rec['_complete_header'] for rec in result):
        result = [rec for rec in result if rec['_complete_header']]
    merged = []
    for rec in result:
        existing = next((r for r in merged if r['id'] == rec['id'] and
                         re.sub(r'\s+', '', r['action']) == re.sub(r'\s+', '', rec['action']) and
                         all(not r.get(k) or not rec.get(k) or re.sub(r'\s+', '', r[k]) == re.sub(r'\s+', '', rec[k])
                             for k in ('owner','deadline','status'))), None)
        if existing is None:
            merged.append(rec)
        else:
            existing.setdefault('_representations', [existing['_address']]).append(rec['_address'])
            for k in ('owner','deadline','closure','status'):
                if not existing.get(k): existing[k] = rec.get(k, '')
                elif k == 'closure' and rec.get(k) and rec[k] not in existing[k]:
                    existing[k] += '；' + rec[k]
    return merged


def typed_rows(rows):
    """Associate adopted workbook values with their visible column headings."""
    headers = None
    sheet = None
    result = []
    for row in visible_rows(rows):
        current = row['address'].rsplit('/R',1)[0]
        if current != sheet:
            headers = None
            sheet = current
        cells = row.get('cells',[])
        if not cells:
            continue
        if any(re.fullmatch(r'员工编号|employee_id',c.strip(),re.I) for c in cells):
            headers = cells
            continue
        if headers:
            result.append({'values':dict(zip(headers,cells)),'address':row['address'],'text':row['text']})
    return result

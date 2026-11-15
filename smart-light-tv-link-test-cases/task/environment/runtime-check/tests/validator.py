import sys
sys.dont_write_bytecode = True
import argparse
import json
import math
import re
import zipfile
from pathlib import Path

import openpyxl


HERE = Path(__file__).resolve().parent
HEADERS = {
    "id": ["case id", "test case id", "test id", "identifier"],
    "title": ["test case name", "case name", "test name", "objective", "scenario", "title"],
    "module": ["module", "category", "test module"],
    "priority": ["priority moscow", "priority", "moscow", "moscow priority"],
    "pre": ["preconditions", "precondition", "prerequisites", "initial conditions", "setup"],
    "steps": ["test steps", "steps", "procedure", "actions"],
    "expected": ["expected results", "expected result", "expected outcome", "expected outcomes", "acceptance criteria"],
    "result": ["test result", "result", "test result pass fail blocked", "execution result", "execution status"],
    "remarks": ["remarks sources", "remarks", "notes", "source references", "sources", "remarks source"]
}


def clean(value):
    text = "" if value is None else str(value)
    return text.replace("\u2264", "<=").replace("\u2265", ">=").replace("\u2212", "-").replace("\u2013", "-").replace("\u2019", "'").lower()


def header(value):
    return re.sub(r"[^a-z0-9]+", " ", clean(value)).strip()


def header_key(value):
    normalized = header(value)
    for key, aliases in HEADERS.items():
        if normalized in aliases:
            return key
    # Classify the declared column role, not its incidental punctuation or suffix.
    patterns = [
        ("expected", r"^(?:observable\s+)?(?:expected(?:\s+(?:results?|outcomes?|behavio[u]?r|response))?|acceptance criteria|pass(?: fail)? criteria)\b"),
        ("result", r"^(?:(?:test|execution|exec)\s+)?(?:results?|status)\b"),
        ("id", r"^(?:(?:test(?: case)?|case)\s+(?:id|identifier|number|no)|identifier|id)\b"),
        ("title", r"^(?:(?:test(?: case)?|case)\s+)?(?:name|objective|scenario|title)\b"),
        ("module", r"^(?:module|category|test module|test area|feature)\b"),
        ("topic", r"^(?:sub area|subarea|sub module)\b"),
        ("priority", r"^(?:priority|moscow)\b"),
        ("pre", r"^(?:preconditions?|prerequisites?|initial conditions|setup)\b"),
        ("steps", r"^(?:(?:ordered|actionable|execution)\s+)*(?:test steps|steps|procedure|actions)\b"),
        ("remarks", r"^(?:remarks|notes|source references|sources?|references|evidence source|source basis)\b"),
        ("quantitative", r"^(?:quantitative\s+(?:criteria|measurement)|measurements?\s+(?:and evidence|criteria|method))\b"),
    ]
    return next((key for key, pattern in patterns if re.search(pattern, normalized)), None)


def clauses(text):
    return [part.strip() for part in re.split(r"[;\n]|(?<!\d)\.(?!\d)", clean(text)) if part.strip()]


def has(text, pattern):
    for clause in clauses(text):
        match = re.search(pattern, clause, re.I)
        if not match:
            continue
        before = clause[max(0, match.start() - 30):match.start()]
        if re.search(r"\b(?:not|never|cannot|mustn't)\s+(?:(?:be|to|always|automatically|necessarily)\s+)*$", before) and not pattern.startswith("no"):
            continue
        return True
    return False


def all_of(text, patterns):
    return all(has(text, pattern) for pattern in patterns)


def time_bounds(text, context):
    found = []
    external_declared = bool(re.search(
        r'(?:endpoint|quantity)\s*[:=]\s*(?:physical\s+)?(?:external\s+)?hue\s+lamp|'
        r'(?:endpoint|quantity)\s*[:=][^;\n.]{0,80}external.{0,15}(?:lamp|light)', clean(text)))
    for clause in clauses(text):
        if not re.search(context, clause, re.I):
            continue
        if re.search(r"\b(?:no|not|undocumented|unsupported|unanchored)\b.{0,45}\b(?:deadline|guarantee|gate|limit|require|promise)\b", clause):
            continue
        for match in re.finditer(r"(?:<=|within(?:\s*<=)?|at most|no more than|not exceed|less than or equal to|maximum(?: delay)?(?: of)?|under)\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(milliseconds?|msec|ms|seconds?|secs?|s)\b", clause):
            # Tables may put a mode before or immediately after its number.
            mode_context = context in {"game", "movie", "music"}
            if mode_context:
                suffix = clause[match.end():]
                prefix = clause[:match.start()]
                labels = r"\b(?:game|movie|music|natural|vivid|football|linkage)\b"
                following_label = re.match(r"\s*(game|movie|music|natural|vivid|football|linkage)\b", suffix)
                anchors = list(re.finditer(labels, prefix))
                label = following_label.group(1) if following_label else anchors[-1].group(0) if anchors else None
                if label is not None and label != context:
                    continue
                if re.search(r"\b(?:transition|switch|override|conflict)\b", prefix + suffix) and not re.search(r"\blatency\b", prefix + suffix):
                    continue
                local_endpoint = re.search(r"(?:tv|ambilight).{0,20}(?:strip|led)|strip.{0,20}latency", clause)
                external_endpoint = re.search(r"hue|external", clause) or external_declared and re.search(r"screen.to.lamp|lamp.{0,20}(?:delay|latency)|end.to.end", clause)
                if external_endpoint and not local_endpoint:
                    continue
            if context in {"recover|reconnect", "recover|reconnect|restor|resum"}:
                # A recovery case can also assert a separate lamp-latency limit.
                # Require this numeric token to name the recovery quantity.
                nearby = clause[max(0, match.start() - 55):match.start()]
                following = re.split(r",|\band\b", clause[match.end():], maxsplit=1)[0][:55]
                if not re.search(context, nearby + " " + following):
                    continue
                # Upgrade watchdogs and subsequent light/mode latency are
                # different quantities, even when a clause mentions recovery.
                if re.search(r'upgrade|firmware', clause) and not re.search(r'network|connectivity|ethernet|\blan\b', nearby + following):
                    continue
                recovery_anchors = list(re.finditer(context, nearby))
                other_anchors = list(re.finditer(r'latency|end.to.end|mode transition|mode switch|command completion|offline prompt|notification', nearby))
                if other_anchors and (not recovery_anchors or other_anchors[-1].start() > recovery_anchors[-1].start()):
                    continue
                if re.match(r'\s*(?:end.to.end|latency|mode transition|mode switch|command completion|offline prompt|notification)\b', following):
                    continue
            value = float(match.group(1).replace(',', ''))
            if match.group(2).startswith("m"):
                value /= 1000
            found.append(value)
    return found


def bound(text, context, expected_seconds):
    values = time_bounds(text, context)
    return bool(values) and all(math.isclose(value, expected_seconds, abs_tol=1e-9) for value in values)


def explicit_hue_bounds(text):
    """Read an adopted bound tied to a declared external-lamp latency quantity."""
    values = []
    for line in clean(text).splitlines():
        quantity = re.search(r'quantity:\s*(.*?)(?=\b(?:units?|timing origin|baseline|limit)\s*:|$)', line)
        if quantity is None or not all_of(quantity.group(1), [r'hue.{0,15}lamp|external.{0,15}(?:lamp|light)', r'latency|delay']):
            continue
        if re.search(r'\b(?:not adopted|reference only|no numeric limit|do not apply)\b', line):
            continue
        for match in re.finditer(r'\blimit:\s*(?:<=|within|at most)\s*([\d.]+)\s*(milliseconds?|ms|seconds?|s)\b', line):
            value = float(match.group(1))
            values.append(value / 1000 if match.group(2).startswith('m') else value)
    return values


def external_mode_errors(case):
    expected = case.get('expected', '')
    text = expected + '\n' + case.get('remarks', '')
    external_endpoint = re.search(r'endpoint\s*=\s*first frame.{0,40}lamp|endpoint\s*:\s*first frame.{0,40}lamp|screen change to hue lamp change', expected + '\n' + case['title'])
    scope_qualified = re.search(r'pending|unresolved|endpoint.{0,30}(?:clarif|conflict)|do not apply|not applied to hue|separately reported', text)
    if not external_endpoint or scope_qualified:
        return []
    return [mode for mode in ['game', 'movie', 'music']
            if re.search(rf'\b{mode}(?:\s+mode)?\s*<=\s*(?:100|200|150)\s*ms', expected)]


def audited_damage(cases, params):
    findings = {}
    for case in cases:
        expected = case.get('expected', '')
        remarks = case.get('remarks', '')
        steps = case.get('steps', '')
        text = expected + '\n' + remarks
        adopted_band = re.search(r'within.{0,35}(?:sop severity|acceptable band)|no (?:p1.level|severe.{0,20}inconsistency)|<=\s*5\s*%\s*treated as acceptable|no difference exceeding\s*15', text)
        if adopted_band and re.search(r'15\s*%|15%|5\s*%', text):
            if not re.search(r'(?:no|not a|not used as|not converted into|not promoted to).{0,35}(?:numeric|numerical|acceptance|product acceptance|pass limit)', expected):
                findings.setdefault('severity_as_acceptance', []).append({'location': case['location'], 'quote': adopted_band.group(0)})
        if re.search(r'upgrade|firmware', case['title']) and re.search(r'120\s*s', expected):
            if upgrade_origin_error(case):
                findings.setdefault('upgrade_origin', []).append({'location': case['location'], 'quote': expected})
        # A numeric endpoint mistake is charged once per affected mode rather
        # than once per repeated test row carrying the same adopted metric.
        for mode in external_mode_errors(case):
            findings.setdefault('external_mode_scope:' + mode, []).append({'location': case['location'], 'quote': expected})
    damage = []
    for cause, evidence in findings.items():
        timing = cause.startswith('external_mode_scope:') or cause == 'upgrade_origin'
        identity = 'unsupported_timing' if timing else 'contradicted_behavior'
        damage.append({'id': identity, 'instance': cause, 'amount': params['damage_amounts'][identity], 'evidence': evidence})
    return damage


def upgrade_origin_error(case):
    text = case.get('expected', '') + '\n' + case.get('steps', '')
    return bool(re.search(
        r'120\s*(?:s\b|seconds).{0,35}after bridge.ready|post.ready recovery time|'
        r'120\s*(?:s\b|seconds)\s+(?:of|after|from)\s+(?:upgrade\s+)?completion', text))


def extract_cases(book):
    cases, environments = [], []
    for sheet in book.worksheets:
        mapping, start = {}, None
        for i, row in enumerate(sheet.iter_rows(max_row=min(sheet.max_row, 15)), 1):
            classified = [(header_key(cell.value), j) for j, cell in enumerate(row)]
            mapping = {}
            for key, j in classified:
                if key is not None:
                    mapping.setdefault(key, []).append(j)
            if {"title", "pre", "steps", "expected"}.issubset(mapping):
                start = i
                break
        if start is None:
            if re.search(r"equipment|environment|checklist|configuration", clean(sheet.title)) or any(
                header(c.value) in {"configuration item", "equipment", "environment item"}
                for row in sheet.iter_rows(max_row=min(sheet.max_row, 5)) for c in row
            ):
                for row in sheet.iter_rows():
                    environments.append(" | ".join(clean(c.value) for c in row if c.value is not None))
            continue
        for row in sheet.iter_rows(min_row=start + 1):
            data = {key: "\n".join(clean(row[index].value) for index in indexes
                                  if index < len(row) and row[index].value is not None)
                    for key, indexes in mapping.items()}
            if not data.get("title"):
                continue
            data.setdefault("id", f"{sheet.title}!{row[0].row}")
            data["location"] = f"{sheet.title}!{row[0].row}"
            data["formula_cells"] = [c.coordinate for c in row if c.data_type == "f"]
            # Dedicated numeric/method cells are part of this case's declared
            # design; retain them without borrowing unrelated workbook prose.
            if data.get("quantitative"):
                data["expected"] += "\n" + data["quantitative"]
                data["steps"] += "\n" + data["quantitative"]
            cases.append(data)
    resolve_explicit_references(book, cases)
    return cases, "\n".join(environments)


def resolve_explicit_references(book, cases):
    indexed = {c['id']: c for c in cases if c.get('id')}
    original = {c['location']: {k: c.get(k, '') for k in ['pre', 'steps', 'expected']} for c in cases}
    methods = {}
    for sheet in book:
        if not re.search(r'measurement|method|definition', clean(sheet.title)):
            continue
        for row in sheet:
            identity = clean(row[0].value).strip()
            if re.fullmatch(r'[a-z]{1,12}-\d{1,4}', identity):
                methods[identity] = '\n'.join(clean(c.value) for c in row[1:] if c.value is not None)
    token = re.compile(r'(?<![a-z0-9])(?:[a-z]{1,12}-)+\d{1,4}(?![a-z0-9])')

    def inherited_pre(case, seen):
        own = original[case['location']]['pre']
        if len(seen) > 12:
            return own
        parts = [own]
        for match in token.finditer(own):
            ref = indexed.get(match.group(0))
            if ref is None or ref['location'] in seen:
                continue
            local = own[max(0, match.start() - 45):match.end() + 45]
            if re.search(r'not (?:complete|active)|failed|unavailable', local):
                continue
            if re.search(r'\bas\b|complete|active|setup|fixture|from|retained|passed|ready', local):
                parts.append(inherited_pre(ref, seen | {ref['location']}))
                parts.append(original[ref['location']]['expected'])
        return '\n'.join(parts)[:24000]

    for case in cases:
        case['reference_locations'] = []
        case['pre'] = inherited_pre(case, {case['location']})
        reference_text = original[case['location']]['steps'] + '\n' + original[case['location']]['expected'] + '\n' + case.get('quantitative', '')
        for match in token.finditer(reference_text):
            identity = match.group(0)
            local = reference_text[max(0, match.start() - 35):match.end() + 35]
            if identity in methods:
                case['steps'] += '\n' + methods[identity]
                case['reference_locations'].append(identity)
            elif identity in indexed and re.search(r'method|as in|per\b|measure|timing|judg|evaluat|latency|verdict', local):
                referenced = indexed[identity]
                if referenced['location'] != case['location']:
                    case['steps'] += '\n' + original[referenced['location']]['steps']
                    case['expected'] += '\n' + original[referenced['location']]['expected']
                    case['reference_locations'].append(referenced['location'])


def scenario_matches(case, key, pattern):
    title = case['title'] + ' ' + case.get('topic', '')
    if key == 'multi_bridge':
        context = title + '\n' + case.get('pre', '') + '\n' + case.get('steps', '')
        return bool(re.search(
            r'multi.?bridge|(?:two|multiple|both|second|another).{0,25}\bbridges?\b|'
            r'one.bridge.at.a.time|one.active.bridge', context))
    if re.search(pattern, title, re.I):
        return True
    aliases = {
        'bridge': r'bridge.{0,50}(?:discovery|pairing|authori[sz]ation)|(?:discover|pair|authori[sz]).{0,55}bridge',
        'multi_bridge': r'multiple.{0,20}bridge|more than one.{0,15}bridge|single.bridge constraint|one.bridge.at.a.time|one.active.bridge|two.{0,25}bridge',
        'lights': r'(?:lamp|light).{0,30}(?:compatib|capabilit|type|eligib|selection|capacity|count)|(?:supported|unsupported|compatib).{0,25}(?:lamp|light)',
        'latency': r'(?:measure|verify|distribution|per.mode|mode).{0,65}latency|latency.{0,45}(?:mode|end.to.end|distribution|measure)',
        'manual': r'(?:manual|phone|app).{0,50}(?:conflict|ownership|control|adjustment|override)|tv control recovery|ownership policy',
        'recovery': r'(?:network|connectivity|ethernet).{0,55}(?:restor|reconnect|resum)|(?:resum|reconnect).{0,65}(?:network|link|sync)',
        'concurrent': r'(?:multi|multiple|concurren).{0,35}(?:lamp|light)|(?:lamp|light).{0,35}(?:concurren|simultaneous|scal)',
        'lamp_loss': r'(?:single|one|offline|powered.off).{0,30}(?:lamp|light)|(?:lamp|light).{0,45}(?:offline|power.off|power.loss)',
        'priority': r'priority|concurrent.trigger|competing.trigger',
        'day': r'(?:ambient|illuminance).{0,45}(?:adapt|band)|adapt.{0,30}ambient',
        'night': r'(?:ambient|illuminance).{0,45}(?:adapt|band)|adapt.{0,30}ambient',
        'fixed': r'fixed.{0,30}(?:level|brightness|profile)|static.{0,25}(?:mode|light|white)',
    }
    if key in {'movie', 'game', 'music'}:
        text = title + '\n' + case.get('steps', '')
        return bool(re.search(rf'\b{key}\b', text) and re.search(r'mode|link|sync|rhythm', text))
    return bool(key in aliases and re.search(aliases[key], title))


def ordered_actions(text):
    segments = [x for x in re.split(r"\n|;|(?:\b\d+[.)]\s)", text) if x.strip()]
    verbs = r"\b(?:open|go|select|set|configure|enable|disable|play|launch|start|record|capture|observe|measure|calculate|compute|check|verify|inspect|disconnect|interrupt|restore|remove|cut|power|trigger|issue|initiate|inject|apply|switch|increase|repeat|run|monitor|log|scan|search|bind|authorize|pair|confirm|compare|analyse|analyze|wait)\b"
    return sum(bool(re.search(verbs, segment)) for segment in segments) >= 2


def checks(case, key, truth):
    pre, steps, expected = case.get("pre", ""), case.get("steps", ""), case.get("expected", "")
    pre_groups, action_groups, outcome_groups = RULES[key][1:4]
    # Setup can be established by ordered preparation actions rather than a
    # repeated precondition sentence. Explicit inherited fixture state is resolved.
    pre_ok = all_of(pre + '\n' + steps, pre_groups)
    step_ok = ordered_actions(steps) and all_of(steps, action_groups)
    outcome_ok = all_of(expected, outcome_groups)
    if key == 'multi_bridge':
        alternate_selection = has(steps, r'(?:re.?select|select|switch).{0,30}\bbridge\s+[ab]\b')
        step_ok = ordered_actions(steps) and (all_of(steps, action_groups) or
                  alternate_selection and has(steps, r'observ|inspect|check|verify'))
        one_active = has(expected, r'only.{0,20}selected.{0,20}bridge|no more than one.{0,10}bridge')
        outcome_ok = outcome_ok or one_active and has(expected, r'select|switch|previous|both')
    if re.match(r"\s*(?:rejected|not adopted|quoted only|candidate only|unsupported proposal|do not adopt)\b", expected):
        outcome_ok = False
    source_ok = bool(re.search(r"spec|sop|guide|manual|section|source|\bfs\s+(?:v\d|\d)|\bs[1-5]\b|\bsrc-0[1-5]\b", case.get("remarks", "")))
    outcome_ok = outcome_ok and source_ok
    numeric_ok = True
    if key in {"movie", "game", "music"}:
        numeric_ok = bound(expected, key, truth["mode_ms"][key] / 1000)
    elif key == "voice":
        numeric_ok = bound(expected, "voice|command|execution|complet", truth["voice_s"])
    elif key == "latency":
        numeric_ok = bound(expected, "game", truth["mode_ms"]["game"] / 1000) and bound(expected, "movie", truth["mode_ms"]["movie"] / 1000)
        frame_formula = bool(re.search(r"(?:response|light|lamp)[_ -]?(?:frame|timestamp|time).{0,20}[-].{0,20}(?:trigger|screen)[_ -]?(?:frame|timestamp|time)", steps + " " + expected))
        symbolic_frame = bool(re.search(r'\bf1\s*-\s*f0\b', steps)) and has(steps, r'f0.{0,95}(?:screen|trigger|marker)') and has(steps, r'f1.{0,95}(?:light|lamp|response)')
        symbolic_time = has(steps, r't_(?:lamp|strip|light|response)\s*-\s*t_(?:screen|trigger)')
        indexed_frame = has(steps, r'f1_?i\s*-\s*f0') and has(steps, r'f0.{0,95}(?:screen|trigger|marker)') and has(steps, r'f1.{0,95}(?:light|lamp|response)')
        frame_formula = frame_formula or symbolic_frame or indexed_frame
        timestamp_formula = has(steps + " " + expected, r"subtract.{0,35}(?:trigger|screen)|(?:response|light).{0,25}minus.{0,25}(?:trigger|screen)")
        fps_conversion = has(steps + " " + expected, r"(?:/|divide.{0,10})\s*(?:record(?:ed|ing)?_?fps|fps|frame.?rate)|same timebase|same time.?base")
        numeric_ok = numeric_ok and ((frame_formula or timestamp_formula) and fps_conversion or symbolic_time and has(pre + steps, r'timebase|time.base|timestamp')) and has(steps, r"p95|95th|percentile")
        if re.search(r"(?:trigger|screen)[_ -]?(?:frame|timestamp|time)\s*-\s*(?:response|light|lamp)[_ -]?(?:frame|timestamp|time)", steps):
            numeric_ok = False
        if re.search(r'\bf0\s*-\s*f1\b', steps):
            numeric_ok = False
    elif key == "concurrent":
        numeric_ok = bound(expected, "hue|external|light|lamp", truth["hue_e2e_s"])
    elif key == "network_loss":
        numeric_ok = bound(expected, "app.{0,35}(?:offline|prompt|notifi)|(?:offline|prompt|notifi).{0,35}app", truth["network_prompt_s"])
    elif key in {"recovery", "weak_network"}:
        numeric_ok = bound(expected, "recover|reconnect|restor|resum", truth["recovery_s"])
    elif key == "lamp_loss":
        numeric_ok = bound(expected, "app.{0,40}(?:offline|prompt|notifi)|(?:offline|prompt|notifi).{0,40}app", truth["lamp_prompt_s"])
    elif key == "priority":
        order = [x.strip().lower() for x in truth["priority_order"].split(">")]
        winner, loser = sorted(["game", "movie"], key=order.index)
        direct = has(expected, rf"{winner}.{{0,25}}(?:overrides|wins|takes precedence|higher.priority|before).{{0,35}}(?:{loser}|lower.priority|competing)")
        ranked = has(pre + steps + expected, r'game\s*>\s*football\s*>\s*movie') and has(expected, r'higher.priority.{0,35}(?:controls|wins|overrides|takes precedence)')
        pairwise = has(steps, r'game.{0,25}(?:while|over|during).{0,25}movie|movie.{0,25}(?:while|over|during).{0,25}game') and has(expected, r'higher.priority.{0,35}(?:controls|wins|overrides|takes precedence)')
        outcome_ok = outcome_ok and (direct or ranked or pairwise)
        numeric_ok = bound(expected, "transition|switch|mode", truth["priority_transition_s"])
    elif key == "upgrade":
        numeric_ok = bool(re.search(rf"(?:exceeds|beyond|over|>)\s*{truth['upgrade_timeout_s']:g}\s*(?:s\b|seconds)", expected)) and has(expected, r"manual.{0,20}check|check.{0,20}manual")
        pending_by_timeout = re.search(
            rf'if.{{0,45}}(?:has not occurred|has not recovered|not recovered).{{0,15}}'
            rf'by\s*{truth["upgrade_timeout_s"]:g}\s*(?:s\b|seconds).{{0,30}}upgrade start', expected)
        numeric_ok = (numeric_ok or bool(pending_by_timeout) and
                      has(expected, r'manual.{0,20}check')) and not upgrade_origin_error(case)
    elif key == "night":
        low, high = truth["night_reduction_pct"]
        numeric_ok = bool(re.search(rf"{low:g}\s*%?\s*(?:-|to)\s*{high:g}\s*%", expected)) and has(expected, r"relative|baseline|reference")
        numeric_ok = numeric_ok and has(steps, r"(?:reference|baseline).{0,20}[-].{0,20}(?:night|dark)|relative reduction|subtract.{0,25}(?:night|dark)")
        if not numeric_ok and re.search(r'(?:b_?baseline|b0|e_?base)\s*-\s*(?:b_?night|bn|e_?night)', steps):
            numeric_ok = bool(re.search(rf"{low:g}\s*%?\s*(?:-|to)\s*{high:g}\s*%", expected)) and has(expected, r'relative|baseline|reference') and bool(re.search(r'/\s*(?:b_?baseline|b0|e_?base)', steps))
        if re.search(r'b_?ref\s*-\s*b_?night', steps):
            numeric_ok = bool(re.search(rf"{low:g}\s*%?\s*(?:-|to)\s*{high:g}\s*%", expected)) and has(expected, r'relative|baseline|reference|b_ref') and bool(re.search(r'/\s*b_?ref', steps))
        numeric_ok = numeric_ok and bool(re.search(rf"(?:below|<|less than)\s*{truth['night_lux']:g}\s*lux", pre + " " + steps))
    elif key == "day":
        numeric_ok = bool(re.search(rf"(?:above|>|greater than)\s*{truth['day_lux']:g}\s*lux", pre + " " + steps))
    elif key == "stability":
        hours, growth = truth["stability_h"], truth["memory_growth_pct"]
        numeric_ok = bool(re.search(rf"{hours:g}\s*(?:hours?|h\b)", steps + " " + expected)) and bool(re.search(rf"(?:<|less than|below)\s*{growth:g}\s*%", expected))
        symbolic_growth = bool(re.search(r'\(\s*m_?(?:72h|72|1)\s*-\s*m_?0h?\s*\)\s*/\s*m_?0h?', steps)) and has(pre + steps, r'baseline|initial')
        numeric_ok = numeric_ok and (symbolic_growth or has(steps, r"(?:final|end)[_ ]?memory.{0,20}[-].{0,20}(?:baseline|initial)[_ ]?memory|growth.{0,50}baseline|growth.{0,50}reference"))
    elif key == "lights":
        numeric_ok = bool(re.search(rf"(?:no more than|at most|maximum|max|<=|within)\s*{truth['max_lights']:g}\s*(?:linked\s*)?(?:hue\s*)?(?:lights|lamps)", pre + " " + expected))
    elif key == "manual":
        numeric_ok = has(pre + expected + case.get('remarks', ''), r"profile|product.definition|policy|configuration|product owner") and has(pre + expected + case.get('remarks', ''), r"pending|unknown|conditional|documented|approved|blocked|confirm|selected")
    priority = re.sub(r"[^a-z]", "", case.get("priority", ""))
    if key in {'movie', 'game', 'music', 'latency'}:
        invalid_modes = external_mode_errors(case)
        if key in invalid_modes or key == 'latency' and invalid_modes:
            numeric_ok = False
    priority_ok = priority in {"must", "musthave", "should", "shouldhave", "could", "couldhave", "wont", "wonthave"}
    pre_ok = pre_ok and priority_ok
    if case["formula_cells"]:
        return False, False, False, "Formula cells cannot certify prose test design"
    return pre_ok, step_ok, outcome_ok and numeric_ok, ""


RULES = {
    "bridge": (r"(?:discover|search|pair|bind|authoriz).{0,30}(?:bridge|hub)|bridge.{0,25}(?:discover|search|pair|bind)", [r"bridge|hub", r"same.{0,20}(?:subnet|vlan|lan)|same network|share.{0,15}(?:one|a single|the same).{0,10}(?:subnet|vlan|lan)", r"ethernet|wired"], [r"discover|search|scan", r"select|pair|bind|authoriz|button", r"observ|verify|inspect|check|record|capture|video"], [r"discover|found", r"pair|bound|bind|configur", r"physical|light.{0,20}respond"]),
    "multi_bridge": (r"multi.?bridge|bridge.{0,25}(?:switch|select)|switch.{0,25}bridge", [r"two|multiple|second|multi", r"bridge|hub"], [r"switch|second|another", r"observ|inspect|check|verify"], [r"only one|one bridge|at most one|single.{0,15}bridge", r"switch|select|previous|both"]),
    "lights": (r"(?:discover|add|scan).{0,30}(?:light|lamp|bulb)|(?:light|lamp).{0,25}discover", [r"bridge|hub", r"capabilit|eligible|compatible|supported"], [r"scan|discover|search", r"select|enable|configur"], [r"white ambiance|temperature.only", r"white.{0,30}(?:not|unsupported)|plain white|dynamic.color", r"light|lamp"]),
    "movie": (r"movie.{0,40}(?:mode|link|sync)|movie mode", [r"movie", r"bound|paired|bridge|link"], [r"play|launch|start", r"record|capture|measure|observ"], [r"movie", r"light|hue", r"smooth|transition"]),
    "game": (r"game.{0,40}(?:mode|link|sync)|game mode", [r"game", r"bound|paired|bridge|link"], [r"play|launch|start", r"record|capture|measure|observ"], [r"game", r"light|hue", r"sync|desynchron|follow"]),
    "music": (r"music|rhythm", [r"music|rhythm", r"algorithm|sensitivity|mode"], [r"play|audio|music", r"observ|measure|record|capture"], [r"pulse|rhythm", r"stutter|drift|delay", r"music"]),
    "fixed": (r"always.?on|fixed.?colo|static.{0,15}(?:colo|effect)", [r"supported|verify|release|capabilit", r"profile|mode|fixed"], [r"select|set|configur", r"observ|record|check"], [r"fixed|static|maintain", r"profile|mode", r"conditional|supported|applicabil"]),
    "voice": (r"voice", [r"account|platform|assistant", r"bind|bound|support"], [r"command|say|voice", r"measure|record|time", r"physical|observ"], [r"command|voice", r"complet|execution|respond", r"physical|light"]),
    "latency": (r"latency.{0,25}(?:distribution|measure|sync)|paired.frame|delay.{0,25}test", [r"camera|frame|timebase|time.base", r"lighting|ambient|controlled"], [r"record|capture", r"pair|timestamp|frame", r"calculat|comput|subtract"], [r"elapsed|duration|latency", r"game", r"movie"]),
    "manual": (r"manual.{0,30}(?:control|arbitrat)|app.{0,25}(?:tv|state|sync)|state sync", [r"app", r"policy|profile|release|configuration"], [r"manual|app", r"measure|time|record", r"handover|control|hold|color"], [r"tv.{0,30}(?:control|regain)|resumption|resum", r"manual|hold", r"profile|policy|product.definition"]),
    "smoothness": (r"smooth|fast.motion|fast motion|transition", [r"clip|video|source|motion|gradient", r"mode|bridge|link"], [r"play|run", r"observ|record", r"flicker|frame|stutter|jump"], [r"no.{0,30}(?:stepped|abrupt|flicker)|smooth", r"bandwidth|instrument|sampling|frequency"]),
    "concurrent": (r"concurrent.{0,25}(?:light|link)|multi.?light|multi.light", [r"multiple|eight|8|4|concurrent|four|six", r"eligible|supported|paired|selected|configured"], [r"all|every|each|per.light", r"record|measure|observ", r"maximum|max|slowest|last lamp"], [r"all|each|every", r"respond|response|delay|latency"]),
    "network_loss": (r"(?:network|bridge|wi.?fi).{0,35}(?:interrupt|disconnect|loss)|disconnect.{0,25}(?:link|bridge)", [r"bridge|hub", r"play|video|link"], [r"interrupt|disconnect|unplug|power|ethernet", r"observ|record", r"app|prompt|notification"], [r"maintain.{0,25}last|hold.{0,25}last", r"tv.{0,25}(?:continues|normal|operat)|backlight.{0,25}continues", r"app"]),
    "recovery": (r"recover|network restor|restored.{0,20}(?:bridge|network)", [r"interrupt|disconnect|offline|loss|break.{0,35}(?:lan|network|connectivity)", r"bridge|hub"], [r"restore|re.power|reconnect", r"connectivity|network|connection", r"observ|measure|time|record|calculat|comput"], [r"automatic|auto.reconnect", r"resum|sync", r"(?:without|no).{0,25}(?:manual|rebind|re[- ]?pair|user action)"]),
    "lamp_loss": (r"(?:single|bulb|lamp).{0,30}(?:power|loss|unplug|interrupt)", [r"lamp|light|bulb", r"more than one|multiple|other|2|two"], [r"cut|remove|unplug|power", r"remain|other", r"app|notification"], [r"remaining.{0,30}(?:continue|sync)|other.{0,25}continue", r"app", r"no.{0,15}(?:lag|crash)|unaffected"]),
    "priority": (r"(?:concurrent|competing).{0,30}(?:trigger|mode)|priority.{0,25}(?:handling|mode)", [r"movie", r"game|trigger"], [r"game|higher.priority", r"movie|lower.priority", r"trigger|issue|switch|request", r"observ|time|measure|mark"], [r"override|precedence|higher.priority", r"mode|transition", r"(?:no|without).{0,20}(?:crash|flicker|freez)"]),
    "weak_network": (r"weak|degraded|latency.packet|packet loss", [r"network|path", r"tool|simulat|impair|inject"], [r"inject|apply|set", r"latency|loss|impair", r"restore|recover"], [r"observ|characteriz|record", r"sla|profile|conditional|undocumented", r"recover|reconnect"]),
    "upgrade": (r"upgrade|firmware update", [r"bridge", r"configuration|upgrade|firmware"], [r"initiate|trigger|start|upgrade", r"observ|record|check", r"configur|recover|restore"], [r"unavailable|interrupt", r"without.{0,20}(?:re.pair|pair)|no.{0,20}re.pair", r"manual.{0,20}check|check.{0,20}manual"]),
    "day": (r"daylight|daytime|strong light|bright.{0,20}(?:ambient|adapt)", [r"als|sensor|adaptive", r"enable|on", r"lux|illuminan", r"reference|baseline|fixed"], [r"measure|record", r"increase|bright|day|illuminan", r"content|mode|baseline"], [r"increase|enhanc", r"brightness|contrast", r"conditional|capabilit|tv.only|tv ambilight"]),
    "night": (r"night|pitch.black|full dark", [r"baseline|reference", r"lux|night|dark", r"enable|adaptive"], [r"measure|record", r"calculat|comput|reduction", r"night|dark|black"], [r"relative|baseline|reference", r"minimum|faint halo", r"night"]),
    "stability": (r"stability|long.duration|stress|hour.{0,20}link", [r"automated|script|monitor|loop", r"baseline|process|warm"], [r"run|continu", r"log|monitor|record", r"memory|growth"], [r"no.{0,20}(?:crash|freeze)|without.{0,20}(?:crash|freeze)", r"memory.{0,15}growth"])
}


def unique_presentations(cases):
    """Score an identical case shown on several sheets once, keeping contradictions."""
    unique, seen = [], set()
    fields = ("title", "topic", "priority", "pre", "steps", "expected", "result", "remarks")
    for case in cases:
        identity = tuple(case.get(field, "") for field in fields)
        if identity not in seen:
            seen.add(identity)
            unique.append(case)
    return unique


def evaluate(workspace, artifact_root=None):
    params = json.loads((HERE / "scoring_params.json").read_text(encoding="utf-8"))
    truth = json.loads((HERE / "ground_truth.json").read_text(encoding="utf-8"))["model"]
    path = (Path(artifact_root) / "linkage-test-cases.xlsx") if artifact_root is not None else Path(workspace) / "output/linkage-test-cases.xlsx"
    base = {"scorer_version": "1.9-business-identity-deduplication", "artifact": "output/linkage-test-cases.xlsx", "items": [], "damage": [], "positive_earned": 0.0,
            "deduplicated_business_damage": 0.0, "reward_strict": 0.0, "reward_lenient": 0.0, "semantic_review": "Independent review of actual solver output is still required."}
    if not path.is_file():
        return {**base, "artifact_status": "missing"}
    try:
        if path.stat().st_size > 20_000_000:
            raise ValueError("Workbook is too large")
        with zipfile.ZipFile(path) as archive:
            if sum(member.file_size for member in archive.infolist()) > 80_000_000:
                raise ValueError("Expanded workbook is too large")
        book = openpyxl.load_workbook(path, data_only=False)
        if any(sheet.max_row > 1000 or sheet.max_column > 80 for sheet in book.worksheets):
            raise ValueError("Workbook exceeds reviewable dimensions")
        cases, environment = extract_cases(book)
        presented_rows = len(cases)
        cases = unique_presentations(cases)
    except (ValueError, OSError, zipfile.BadZipFile, KeyError, TypeError, openpyxl.utils.exceptions.InvalidFileException) as error:
        return {**base, "artifact_status": "invalid", "artifact_error": str(error)}
    fingerprints = {}
    for case in cases:
        fingerprint = tuple(case.get(k, "") for k in ["pre", "steps", "expected"])
        fingerprints.setdefault(fingerprint,set()).add(
            (case.get("id",""),case.get("title",""),case.get("module","")))
    ledger, damage = [], []
    for key, rule in RULES.items():
        matches = []
        for case in cases:
            if not scenario_matches(case, key, rule[0]):
                continue
            if len(fingerprints[tuple(case.get(k, "") for k in ["pre", "steps", "expected"])]) > 1:
                matches.append((0.0, case, (False, False, False, "Repeated copied case body")))
                continue
            pre, steps, outcome, note = checks(case, key, truth)
            completion = 0.1 * pre + 0.1 * steps + 0.8 * (pre and steps and outcome)
            matches.append((completion, case, (pre, steps, outcome, note)))
        best = max(matches, key=lambda item: item[0]) if matches else None
        weight = params["positive_weights"][key]
        ledger.append({"id": key, "weight": weight, "completion": best[0] if best else 0.0,
                       "earned": weight * (best[0] if best else 0.0), "location": best[1]["location"] if best else None,
                       "preconditions": best[2][0] if best else False, "actions": best[2][1] if best else False,
                       "expected_relationship": best[2][2] if best else False,
                       "note": best[2][3] if best else "No corresponding executable scenario",
                       "reference_locations": best[1].get('reference_locations', []) if best else []})
    env_groups = [r"same.{0,25}(?:subnet|vlan|lan)|same network", r"ethernet|wired", r"firmware|version", r"camera|timebase|frame rate", r"lux|sensor|als", r"monitor|memory"]
    env_completion = sum(has(environment, p) for p in env_groups) / len(env_groups) if cases else 0
    ledger.append({"id": "environment", "weight": params["positive_weights"]["environment"], "completion": env_completion,
                   "earned": params["positive_weights"]["environment"] * env_completion, "note": "Equipment/setup support only; visual formatting earns no points."})
    rationale_parts = []
    for ws in book.worksheets:
        active_priority = None
        for row in ws:
            values = [clean(c.value).strip() for c in row if c.value is not None]
            if not values:
                continue
            if values[0] in {'must', 'must have', 'should', 'should have', 'could', 'could have', "won't"} and any(len(v)>25 for v in values[1:]):
                rationale_parts.append(' | '.join(values))
                active_priority = None
            elif len(values) == 1 and values[0] in {'must', 'must have', 'should', 'should have', 'could', 'could have'}:
                active_priority = values[0]
            elif active_priority and len(values) == 1 and len(values[0])>25:
                rationale_parts.append(active_priority + ' | ' + values[0])
            else:
                active_priority = None
    rationale = '\n'.join(rationale_parts)
    rationale_ok = all_of(rationale, [r"must", r"should", r"could", r"critical|risk|release|important|optional|guarantee|core|safety|normative"])
    ledger.append({"id": "priority_rationale", "weight": params["positive_weights"]["priority_rationale"],
                   "completion": float(rationale_ok), "earned": params["positive_weights"]["priority_rationale"] * rationale_ok})
    for case in cases:
        if case.get("result", "").strip() in {"pass", "passed", "fail", "failed"}:
            damage.append({"id": "fabricated_execution", "instance": case["location"], "amount": params["damage_amounts"]["fabricated_execution"], "evidence": case.get("result")})
        text = case.get("expected", "")
        contradictions = [
            ("loss_state", r"(?:lamps|lights).{0,20}(?:turn off|switch off|reset|black out).{0,30}(?:disconnect|interrupt|network loss)"),
            ("tv_failure", r"tv.{0,20}(?:must|should|will).{0,15}(?:stop|crash|freeze).{0,30}(?:disconnect|interrupt|network loss)"),
            ("rebind", r"(?:recovery|reconnection).{0,20}(?:requires|must use).{0,20}(?:manual|rebind|pair)"),
            ("priority_inversion", r"movie.{0,15}(?:overrides|wins|takes precedence over).{0,15}game"),
            ("white_color", r"plain white.{0,15}(?:supports|provides|can follow).{0,15}dynamic.color")
        ]
        for cause, pattern in contradictions:
            if has(text, pattern):
                damage.append({"id": "contradicted_behavior", "instance": cause + ":" + case["location"],
                               "amount": params["damage_amounts"]["contradicted_behavior"], "evidence": text})
        for key, context, target in [
            ("game", "game", truth["mode_ms"]["game"] / 1000),
            ("movie", "movie", truth["mode_ms"]["movie"] / 1000),
            ("music", "music", truth["mode_ms"]["music"] / 1000),
            ("voice", "voice|command.*complet", truth["voice_s"]),
            ("recovery", "recover|reconnect", truth["recovery_s"])
        ]:
            wrong = [value for value in time_bounds(text, context) if not math.isclose(value, target, abs_tol=1e-9)]
            if wrong:
                damage.append({"id": "unsupported_timing", "instance": key + ":" + case["location"],
                               "amount": params["damage_amounts"]["unsupported_timing"], "evidence": wrong})
        wrong_hue = [value for value in explicit_hue_bounds(text)
                     if not math.isclose(value, truth['hue_e2e_s'], abs_tol=1e-9)]
        if wrong_hue:
            damage.append({'id': 'unsupported_timing', 'instance': 'hue:' + case['location'],
                           'amount': params['damage_amounts']['unsupported_timing'],
                           'evidence': {'endpoint': 'explicit external Hue lamp', 'seconds': wrong_hue,
                                        'source_seconds': truth['hue_e2e_s']}})
    damage.extend(audited_damage(cases, params))
    unique_damage = {item["instance"] + ":" + item["id"]: item for item in damage}
    damage = list(unique_damage.values())
    earned = min(1.0, math.fsum(item["earned"] for item in ledger))
    loss = math.fsum(item["amount"] for item in damage)
    strict = max(0.0, earned - loss)
    schema_diagnostics = []
    if not cases:
        for sheet in book.worksheets:
            schema_diagnostics.append({"sheet": sheet.title,
                "detected_column_roles": sorted({role for row in sheet.iter_rows(max_row=min(sheet.max_row, 15))
                    for cell in row if (role := header_key(cell.value)) is not None})})
    # 宽松口径 = 题面明写的「must」合取：这份工作簿作为测试方案本身能不能用。
    # 它与 strict 问的是两件不同的事 —— strict 问覆盖了多少documented linkage
    # scope（连续量），宽松问交付物是否成立（二值）。覆盖深度刻意不进这个口径：
    # 把覆盖比例放进来只是在某个切点上重述 strict，问不出第二个问题。
    #
    # 四条必须项逐条对应 instruction.md 的 must 句：
    #   1. 工作簿能被解析成用例结构   —— 解析不出来就不是测试方案
    #   2. 「Include an equipment/environment checklist」
    #   3. 「and a brief priority explanation」
    #   4. 「do not report tests as having passed or invent measurements」
    #      「Leave execution results blank or explicitly unexecuted」
    #
    # 四条都只依赖提交的工作簿本身、无设备无网络即可判定 —— 必须项里不放条件性
    # 判项，否则「没测到」会被读成「没做到」，宽松分在离线环境下永久为 0。
    must_have = {
        "case_schema_parsed": bool(cases),
        "environment_checklist": any(
            item["id"] == "environment" and item["completion"] >= 1.0 for item in ledger),
        "priority_rationale": any(
            item["id"] == "priority_rationale" and item["completion"] >= 1.0 for item in ledger),
        "no_fabricated_results": not any(
            item["id"] in {"fabricated_execution", "unsupported_timing"} for item in damage),
    }
    return {**base, "artifact_status": "parsed" if cases else "unrecognized_case_schema",
            "schema_diagnostics": schema_diagnostics, "case_rows": len(cases),
            "presented_case_rows": presented_rows, "items": ledger, "damage": damage,
            "positive_earned": earned, "deduplicated_business_damage": loss, "reward_strict": strict,
            "lenient_must_have": must_have,
            "reward_lenient": float(all(must_have.values())), "reward": strict}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_root", nargs="?")
    parser.add_argument("--workspace")
    parser.add_argument("--log-dir")
    args = parser.parse_args()
    import tempfile
    target = args.workspace or args.artifact_root
    if not target:
        parser.error("Provide --workspace or an output directory")
    workspace = Path(target)
    if not args.workspace and workspace.name == "output":
        workspace = workspace.parent
    logs = Path(args.log_dir) if args.log_dir else Path(tempfile.mkdtemp(prefix="judge-logs-"))
    logs.mkdir(parents=True, exist_ok=True)
    for name in ["reward.txt", "reward_strict.txt", "reward_lenient.txt", "reward.json", "reward_detail.json"]:
        (logs / name).unlink(missing_ok=True)
    artifact_root = Path(args.artifact_root) if not args.workspace else None
    if artifact_root is not None and (artifact_root / "output").is_dir():
        artifact_root = artifact_root / "output"
    result = evaluate(workspace, artifact_root=artifact_root)
    (logs / "reward_detail.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    for filename, value in [("reward.txt", result["reward_strict"]), ("reward_strict.txt", result["reward_strict"]), ("reward_lenient.txt", result["reward_lenient"])]:
        (logs / filename).write_text(repr(value) + "\n", encoding="ascii")
    (logs / "reward.json").write_text(json.dumps({"reward": result["reward_strict"], "reward_strict": result["reward_strict"], "reward_lenient": result["reward_lenient"]}), encoding="utf-8")
    print(json.dumps({"reward": result["reward_strict"], "reward_strict": result["reward_strict"], "reward_lenient": result["reward_lenient"], "rewards": {"strict": result["reward_strict"], "lenient": result["reward_lenient"]}, "artifact_status": result["artifact_status"]}))


if __name__ == "__main__":
    main()

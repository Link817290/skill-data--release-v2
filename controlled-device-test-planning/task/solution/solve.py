"""Derive an executable plan from original Materials and explicit engineering rules.

Rules add controls and measurement definitions; source facts and baseline procedures
are extracted on every run. Conflicting sources remain conditional rather than being
silently promoted to a universal product guarantee.
"""
from pathlib import Path
from datetime import datetime
import argparse
import json
import re
import zipfile
import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from material_reader import Sources, SPEC, SOP, MANUAL, PRODUCT, ENERGY

ARTIFACT = 'LG_AKB76043105_Test_Case_List_EN.xlsx'


def derive(materials):
    materials = Path(materials)
    contract = json.loads((materials / 'output_contract.json').read_text('utf-8'))
    src = Sources(materials)
    facts = {}
    facts['model'] = src.fact('dut_model', SPEC, 2, r'LG (AKB\d+)')
    facts['power'] = src.fact('dut_power', SPEC, 2, r'Power Supply\s+(.+?)\s+LR03')
    facts['bt'] = src.fact('dut_bt_version', SPEC, 2, r'Bluetooth\s+BLE\s+([\d.]+)')
    facts['host_bt'] = src.fact('host_bt_version', PRODUCT, 2, r'Bluetooth version\s+([\d.]+)')
    facts['host_remote'] = src.fact('host_supplied_remote', PRODUCT, 2, r'Remote control type\s+(.+?)\s+(?:Other|AMD|Batteries|FreeSync)')
    facts['bt_range'] = src.fact('bt_nominal_range', SPEC, 2, r'BT Effective Range\s+(\d+\s*m)')
    facts['ir_range'] = src.fact('ir_nominal_range', SPEC, 2, r'IR Effective Range\s+(\d+\s*m)')
    facts['pair_timeout'] = src.fact('pairing_timeout', SPEC, 62, r'Pairing Timeout\s+(\d+ seconds)')
    facts['pair_confirmation'] = src.fact('pairing_confirmation', SPEC, 63, r'Wait for confirmation\s+\((≤\d+ seconds)\)')
    facts['repair_input_window'] = src.fact('repair_input_window', SPEC, 63, r'Press OK wheel within\s+(\d+ seconds)')
    facts['pointer_idle'] = src.fact('pointer_hide', SPEC, 44, r'Inactivity timeout:\s+(\d+ seconds)')
    facts['remote_idle'] = src.fact('remote_power_sleep', SPEC, 60, r'low-power mode after\s+(\d+ seconds)')
    facts['voice_quiet'] = src.fact('quiet_recognition', SPEC, 57, r'(≥\s*\d+%) in quiet')
    facts['voice_noise'] = src.fact('moderate_noise_recognition', SPEC, 57, r'(≥\s*\d+%) in\s+moderate noise')
    facts['noise_band'] = src.fact('noise_band', SPEC, 57, r'moderate noise\s*\(([^)]+)\)')
    facts['voice_corpus'] = src.fact('voice_corpus', SPEC, 57, r'Run\s+(\d+)-command')
    facts['slots'] = src.fact('learning_slots', SPEC, 59, r'Memory\s+(\d+) device slots')
    facts['sop_pair'] = src.test_fact('sop_pair_completion','CONN-001',r'within (\d+ seconds)')
    facts['sop_pointer_idle'] = src.test_fact('sop_pointer_idle','PTR-001',r'auto-hides after (\d+ seconds)')
    facts['sop_pointer_wake'] = src.test_fact('sop_pointer_wake','PTR-001',r'response time\s*(<=\s*[\d.]+ seconds)')
    facts['sop_voice_accuracy'] = src.test_fact('sop_voice_accuracy','VC-002',r'accuracy\s*(>=\s*\d+%)')
    facts['sop_noise_accuracy'] = src.test_fact('sop_noise_accuracy','VC-003',r'success rate\s*(>\s*\d+%)')
    facts['sop_noise_level'] = src.test_fact('sop_noise_level','VC-003',r'no more than (\d+dB)')
    facts['sop_perfect_range'] = src.test_fact('sop_perfect_range','CONN-005',r'Within (\d+m): 100%')
    facts['sop_loss_range'] = src.test_fact('sop_loss_range','CONN-005',r'At (\d+m): Occasional')
    assert 'USB-C' in '\n'.join(src.paragraphs[15:90])
    assert 'non-removable' in src.paragraphs[42]
    assert 'No' in src.page(ENERGY, 1) and 'Voice recognition sensor' in src.page(ENERGY, 1)
    src.evidence.append({'fact_id':'sop_power', 'source':f'{SOP} paragraphs 43-44',
                         'matched_quote':'\n'.join(src.paragraphs[42:44])})
    rows = []

    applicability = (
        f'Record DUT {facts["model"]} hardware/firmware, host model/webOS, region and actual button layout. '
        f'The function specification describes {facts["power"]} / BLE {facts["bt"]}; the SOP describes '
        'a built-in non-removable USB-C battery. Confirm the actual variant before executing power actions. '
        f'The supplied host datasheet describes {facts["host_remote"]} and host Bluetooth {facts["host_bt"]}; '
        'these do not establish DUT power type or compatibility. Do not disassemble a sealed battery. '
        'Mark an unsupported function N/A with its basis; unresolved applicability prevents a pass/fail decision.'
    )

    def add(identity, category, objective, source_ids, controls, expected, acceptance,
            priority='P1-High', setup='', extra_source='', basis=''):
        base = [src.test(key) for key in source_ids]
        # Extract baseline actions from the actual SOP; no final Golden text is read.
        actions = [s for t in base for s in t['steps']]
        # Source actions that would be unsafe or presuppose an unresolved version are
        # replaced by the rule-specific, applicability-qualified action list.
        if controls.get('replace_baseline'):
            actions = []
        actions += controls['actions']
        notes = '; '.join(t['source'] for t in base)
        if extra_source:
            notes = '; '.join(filter(None, [notes, extra_source]))
        notes += '. ' + basis + ' Test selections are laboratory design choices, not additional manufacturer guarantees.'
        rows.append([identity, category, objective,
            '\n'.join(f'{i}. {s}' for i,s in enumerate(actions,1)),
            setup + ' ' + applicability,
            expected, priority, acceptance, None, 'Planned', notes.strip()])

    add('TC-004','Communication & Pairing','First pairing and timing authority', ['CONN-001'],
        {'actions':[
            'Record the unpaired initial state and confirm the target TV is ready; use only the power method supported by the identified hardware.',
            'Record synchronized timestamps for OK-wheel press, first pairing indication, registration confirmation and first successful control.',
            'Run repeat attempts from a cleared binding; record successes/attempts and failed attempts separately. Observe timeout and retry outcomes without conflating their timers.'
        ]},
        'The target host registers the remote and pointer/buttons work after registration; distinguish user-visible completion from protocol timeout.',
        f'Apply the SOP completion criterion of {facts["sop_pair"]} only after applicability is confirmed. Specification section 18.3 separately requires confirmation {facts["pair_confirmation"]}; section 18.1 defines a {facts["pair_timeout"]} protocol timeout from OK, and section 18.4 gives a {facts["repair_input_window"]} window to press OK after deregistration. These are different events, not interchangeable clocks. Until source authority and each event definition are confirmed, record measured values and leave the disputed timing decision pending.',
        priority='P0-Critical', extra_source=f'{SPEC} pp62-63; {MANUAL} p12',
        basis='Resolve the completion/timeout event distinction before judging timing.')
    add('TC-005','Communication & Pairing','BT unavailable, proven IR fallback and recovery', ['CONN-003'],
        {'actions':[
            'Verify BT is actually unavailable using connection state or a pointer check; use a supported TV restart or controlled disconnect, without assuming a Bluetooth-off menu exists.',
            'Exercise a documented basic button with IR unobstructed, then repeat the same command with the IR path blocked while BT remains unavailable; compare host responses.',
            'Restore the IR path and BT connection; repeat pointer and basic-button checks and record recovery.'
        ]},
        'Documented basic control works on the IR path during BT unavailability; blocking that path removes the response. Pointer returns when BT recovers.',
        'A fallback conclusion requires BT-unavailable evidence plus the IR-blocked negative control. Report only the verified basic keys; do not extend the result to every key or to voice/pointer via IR.',
        priority='P0-Critical', extra_source=f'{SPEC} pp2,57,62')
    add('TC-006','Communication & Pairing','Deregister and re-pair with state checks', ['CONN-002'],
        {'actions':['Verify loss of the previous binding before re-pairing; if the applicable procedure requires OK-wheel activation, perform it and confirm registration and pointer recovery. Record the actual manual or automatic recovery route.']},
        'Deregistration changes connection state and the applicable re-pair procedure restores the intended binding.',
        'Verify state changes and restored control; do not assume the SOP automatic sequence and the specification manual OK-wheel sequence are the same firmware behavior.',
        priority='P0-Critical', extra_source=f'{SPEC} p63; {MANUAL} p12')
    add('TC-007','Communication & Pairing','Interference with target and non-target controls', ['CONN-004'],
        {'actions':[
            'Select and identify a target TV and a non-target TV. Record a no-interference baseline, fixed distance and battery state, then introduce the selected interference source.',
            'Send a BT-addressed pointer or smart command and observe target and non-target TVs concurrently; record wrong-target activations and disconnects.',
            'Run basic IR commands separately, recording possible shared IR broadcast responses; do not classify those responses as BT misbinding.',
            'Remove interference and repeat the baseline. Record command successes/attempts, timing and disconnection events per phase.'
        ]},
        'Target BT control remains attributable to its binding; any non-target IR response is classified by route. Interference effects can be compared with baseline and recovery.',
        'Apply the applicable SOP latency criterion to its documented scenario. Report target/non-target counts and before/during/after observations; selected TV count and exposure duration are test design rather than guaranteed capacity or endurance.',
        basis='A cross-control claim needs concurrent non-target observation and separation of BT addressing from IR broadcast.')
    add('TC-008','Communication & Pairing','Hardware-appropriate power cycle and binding retention', [],
        {'actions':[
            'Confirm battery construction first. On the removable-battery variant only, remove and refit the specified cells; on a sealed variant use an approved external power-cycle procedure or mark this operation pending. Never open a sealed pack.',
            'From a confirmed paired state record the binding identifier, interrupt power by the approved route, restore power and record connection state and time.',
            'Before pressing OK, test whether the binding and pointer resume; if not, execute the applicable manual re-pair procedure and record it separately.'
        ]},
        'Operation is safe for the actual hardware; distinguish retained binding, auto-reconnect and manual re-pair outcomes.',
        'Power restoration alone does not establish pairing persistence or a universal recovery deadline. Record the actual route and elapsed time; retain an unresolved requirement as pending rather than an unconditional pass.',
        extra_source=f'{SPEC} pp60-63; {SOP} paragraphs 43-44,549-562,593-608')
    add('TC-009','Pointer & Interaction','Motion-to-pointer mapping and click endpoint', ['PTR-002','PTR-005'],
        {'actions':[
            'Hold screen resolution and pointer speed fixed. Move through a repeatable horizontal/vertical path, then stop; compare physical direction with pointer direction and record drift/jitter.',
            'Use synchronized video or equivalent instrumentation to measure physical motion onset to first pointer displacement. Log the instrument time resolution; a stopwatch cannot resolve an unqualified sub-frame limit.',
            'Click known small targets; record successful target hits/attempts and positional deviation in screen coordinates.'
        ]},
        'Direction, stopping behavior and click location correspond to the controlled physical input.',
        'Judge the documented click experiment on its applicable source conditions; record tracking latency without inventing a universal requirement. Preserve coordinate and attempt denominators.',
        priority='P0-Critical', extra_source=f'{SPEC} pp44-45')
    add('TC-010','Pointer & Interaction','Pointer hide/wake versus remote power sleep', ['PTR-001'],
        {'actions':[
            'Record timestamps for last physical movement, pointer disappearance, wake stimulus and pointer reappearance; also record BT state if the remote enters a power-saving state.',
            'Separate the pointer visibility timer from remote current/power sleep. Record pointer screen coordinates immediately before disappearance, repeat a controlled wake motion without pressing another key, and compare the restored coordinates with the previous location.'
        ]},
        'Pointer disappearance and reappearance are measured independently of remote low-power entry, and restored screen coordinates are compared with the location before hiding.',
        f'The specification pointer-hide timer is {facts["pointer_idle"]}; the SOP uses {facts["sop_pointer_idle"]}, while the specification remote power-sleep timer is {facts["remote_idle"]}. Resolve firmware applicability rather than merging these timers. SOP wake latency is {facts["sop_pointer_wake"]} only in its applicable scenario; unresolved timing authority remains pending.',
        extra_source=f'{SPEC} pp44,60')
    add('TC-011','Pointer & Interaction','Wheel scrolling with deterministic context controls', ['PTR-004'],
        {'actions':[
            'Choose a list and browser page with known scrollable content and a playback app known to support wheel actions. Hold initial position constant.',
            'Compare slow forward/reverse detents with rapid scrolling and release; record skipped items, reverse movement, inertia and final position per context.',
            'For seeking, verify the app explicitly supports wheel seeking before checking position changes; restore starting state between trials.'
        ]},
        'Supported contexts respond in the intended direction; inertial motion and stopping are attributable to wheel input.',
        'Record context, direction, input count and resulting position. An unsupported seeking context is N/A rather than proof of remote failure; a selected cycle count is a test choice.',
        extra_source=f'{SPEC} p8')
    add('TC-012','System Buttons','Short/long press and Back/Exit context matrix', ['SYS-001','SYS-002','SYS-005','SYS-006'],
        {'replace_baseline':True,'actions':[
            'Confirm actual keys and the applicable software mapping. Establish home, nested app page and settings states with recorded starting screens.',
            'In each applicable state issue a short press and a separately timed long press; reset to the same starting screen between trials.',
            'Record the resulting screen and navigation depth for Settings, Back and Exit. Compare Back returning one level with Exit leaving the active context, allowing documented context exceptions.'
        ]},
        'Press duration and initial context determine the observed route; identical labels do not imply identical behavior across firmware.',
        'Verify the applicable mapping and state transition. Conflicting long-press durations or missing physical keys require an applicability decision; do not invent an undocumented universal menu action.',
        extra_source=f'{SPEC} pp11,16-17; {MANUAL} pp11-12')
    add('TC-013','System Buttons','Channel guide with loaded broadcast data', ['SYS-007'],
        {'actions':['Use a tuned live source with valid guide data, record current channel/time, select a different listed channel and confirm the actual programme. Repeat with missing guide data to distinguish an upstream data failure from a key failure.']},
        'Guide navigation follows the active source and available programme data.',
        'Validate channel selection and source-appropriate guide behavior. Do not require universal EPG data or streaming-app behavior independent of source availability.',
        extra_source=f'{SPEC} pp20,35')
    add('TC-014','Audio Buttons','Volume and mute on the selected audio endpoint', [],
        {'actions':[
            'Record TV audio output selection and initial volume/mute. Test internal speakers first, then a supported external audio route separately.',
            'Issue volume up/down and mute/unmute; record both OSD state and audible output at the selected endpoint, including minimum/maximum boundaries.',
            'If external control is under test, isolate IR and HDMI-CEC routes in separate trials so successful volume control is attributed to the actual path.'
        ]},
        'The selected audio endpoint and its OSD change consistently; boundaries do not wrap unexpectedly.',
        'A TV OSD change alone does not prove external audio changed. Judge only supported audio routes and record the actual controlled endpoint.',
        extra_source=f'{SPEC} pp23-25,58; {MANUAL} p11')
    add('TC-015','Voice','Voice UI wake and command-action latency', ['VC-001'],
        {'actions':[
            'Record BT connection, host language, account/consent and network/service state. Use a controlled command and fixed speaking distance.',
            'Record separately microphone-button press to waveform/voice UI and microphone LED-on to actual commanded action. Repeat and retain each observation and the mean.',
            'Classify supported local and network-dependent commands separately; in an offline trial record unavailable cloud behavior without inventing offline recognition.'
        ]},
        'Voice UI wake, recognition and actual action are distinct events; latency belongs to the named path.',
        'Apply the SOP UI-wake limit to the UI endpoint. Apply the function specification local/cloud response limits only to the corresponding action endpoint and applicable network conditions; report each series separately.',
        extra_source=f'{SPEC} pp30,57; {MANUAL} p11')
    add('TC-016','Voice','Recognition and action accuracy with explicit denominators', ['VC-002'],
        {'actions':[
            f'Use a recorded command corpus; the specification describes a {facts["voice_corpus"]}-command set and the SOP a 10-command set. Identify which source and language apply; retain the same corpus for comparisons.',
            'For each attempted command record the spoken reference, recognized text or intent, executed action and correctness separately; include failed/time-out attempts in the denominator.',
            'Compute recognition accuracy = correctly recognized attempts / all attempted commands and action accuracy = correctly executed commands / all attempted commands. If reporting WER, compute (substitutions + deletions + insertions) / reference words; WER is not command success rate.'
        ]},
        'A recognized phrase earns no action success when the requested operation was not executed; command and word metrics have separate denominators.',
        f'Use the applicable source threshold: specification quiet recognition {facts["voice_quiet"]} or SOP command criterion {facts["sop_voice_accuracy"]} after scope confirmation. Do not silently substitute a threshold for a different corpus or metric.',
        extra_source=f'{SPEC} p57')
    add('TC-017','Voice','Matched quiet/noise recognition experiment', ['VC-003'],
        {'actions':[
            'Run the same command corpus and speaking geometry in quiet and noise conditions; keep language, network state, speaker level and trial count controlled.',
            'Measure acoustic level at the microphone position with a calibrated sound-level meter; record noise type and measured dB/SPL, rather than treating a TV volume percentage as an acoustic measurement.',
            'Record successes/attempts in each condition. Compute quiet and noise success rates, percentage-point drop = quiet rate - noise rate, and relative loss = (quiet rate - noise rate) / quiet rate; if quiet rate is zero, relative loss is undefined. Express the absolute difference in percentage points when rates are expressed as percentages.'
        ]},
        'The matched experiment separates acoustic stress from changes in corpus, speaking distance or network conditions.',
        f'The specification describes {facts["voice_noise"]} at {facts["noise_band"]}; the SOP uses its own noise level no more than {facts["sop_noise_level"]} and success rate {facts["sop_noise_accuracy"]}. Confirm applicability and report absolute rates separately from relative loss; no universal relative-degradation guarantee is established.',
        extra_source=f'{SPEC} p57')
    add('TC-018','Universal Control','Prove learned IR and distinguish HDMI-CEC', [],
        {'actions':[
            'Confirm that the DUT/host variant offers the documented learning function. Identify the original remote and external target device, and record a baseline showing the selected unlearned key does not control that target.',
            'Disable HDMI-CEC/SimpLink and other competing control routes; learn a supported original-remote IR command and execute it against the target.',
            'Block the IR emitter/receiver path and repeat the same command; compare with IR unobstructed. An action that still succeeds requires route investigation before claiming learned IR.',
            'Separately exercise HDMI-CEC with IR blocked to establish that route. For the applicable learning-memory variant, power-cycle by its approved method and retest the stored code; record device identity and any overwritten mapping.'
        ]},
        'Learning changes the selected mapping and controls the intended target on the isolated IR route; CEC success is classified separately.',
        f'The specification states {facts["slots"]} learning slots and non-volatile storage; confirm the variant before applying those claims. A selected set of three devices neither proves capacity nor establishes persistence. Retention needs an actual applicable power-cycle test.',
        extra_source=f'{SPEC} pp58-59')
    add('TC-019','App Shortcuts','Region and installation-qualified shortcut behavior', ['SYS-008'],
        {'actions':[
            'Inventory the actual labelled service buttons and confirm region, app installation, account entitlement and network availability.',
            'From the same initial screen press each available shortcut; record button press to app launch-ready screen, avoiding confusion with content playback completion.',
            'Repeat with an uninstalled or unavailable service where permitted; record the applicable store/prompt/unavailable branch and restore the initial state.'
        ]},
        'The actual service button follows its supported installed/uninstalled branch; missing region-specific services are documented.',
        'Apply a launch-time limit only with its source, endpoint and applicability established. Missing region-specific buttons are N/A; do not invent universal application availability or a global launch guarantee.',
        extra_source=f'{SPEC} pp31-33; {MANUAL} pp11-12')
    add('TC-020','Range & Geometry','BT distance experiment with scoped acceptance', ['CONN-005'],
        {'actions':[
            'Hold battery, host, interference and line-of-sight geometry fixed. Verify BT using a pointer/smart command and block the IR route as a negative control.',
            'At each marked distance repeat the same fixed number of commands; record successes/attempts, latency, disconnects and reconnection route by distance.',
            'Keep angle fixed for distance trials, then hold distance fixed for exploratory angle trials. Record actual horizontal/vertical angles and target orientation.'
        ]},
        'Distance and angle results are attributable to BT under controlled geometry.',
        f'The specification {facts["bt_range"]} range is nominal. The SOP requires 100% response within {facts["sop_perfect_range"]} and permits occasional loss at {facts["sop_loss_range"]} in its scenario. Do not claim 100% at nominal range or zero blind spots at all angles; exploratory angle selections are not guaranteed coverage.',
        extra_source=f'{SPEC} p2')
    add('TC-022','Range & Geometry','IR distance/angle experiment without competing BT', ['CONN-006'],
        {'replace_baseline':True,'actions':[
            'Verify BT is disconnected or otherwise cannot carry the command. Confirm direct line of sight and identify the TV IR receiver position.',
            'At each chosen distance use the same supported basic IR command and repetition count; record successes/attempts and latency.',
            'Hold distance fixed while changing transmitter/receiver angle; record the actual geometry and repeat with an opaque IR obstruction as a negative control.',
            'Restore line of sight and confirm response recovery before classifying an IR failure.'
        ]},
        'Results depend on the isolated IR path and measured transmitter/receiver geometry.',
        f'The specification IR range is nominal {facts["ir_range"]}. Angle points such as 30 or 60 degrees are exploratory selections unless an applicable authority establishes a limit. Do not turn the nominal distance into universal all-angle 100% acceptance.',
        extra_source=f'{SPEC} p2; {SOP} paragraphs 214-225')
    # The approved scope is eighteen functional cases. Two noise/recognition rows
    # are independently measured, while the old standalone BT-angle row is folded
    # into the controlled BT geometry experiment; IDs are labels, never scorer keys.
    assert len(rows) == 18
    return contract, facts, applicability, rows, src


def workbook_bytes(contract, facts, applicability, rows):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Test Case Template'
    ws.append([f'{facts["model"]} controlled-device test case list'])
    ws.append([applicability])
    ws.merge_cells('A1:K1')
    ws.merge_cells('A2:K2')
    fields = contract['case_table']['fields']
    ws.append([f['name'] for f in fields])
    for row in rows:
        ws.append(row)
    widths = [14,24,43,82,72,58,17,78,18,18,66]
    for i,width in enumerate(widths,1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.row_dimensions[1].height = 30
    ws.row_dimensions[2].height = 80
    ws.row_dimensions[3].height = 30
    for row in ws:
        for cell in row:
            cell.font = Font(name='Aptos',size=11)
            cell.alignment = Alignment(vertical='top',wrap_text=True)
            cell.border = Border(bottom=Side(style='hair',color='DCE4ED'))
    for row_number in [1,3]:
        for cell in ws[row_number]:
            cell.fill = PatternFill('solid',fgColor='16324F')
            cell.font = Font(name='Aptos',size=11,color='FFFFFF',bold=True)
    for i in range(4,ws.max_row+1):
        # Native Excel does not auto-fit wrapped rows written by openpyxl.
        # Estimate each cell's wrapped lines and retain space for the longest.
        import textwrap
        lines=max(sum(max(1,len(textwrap.wrap(line,width=max(8,int(widths[c.column-1]*.82)))))
                      for line in str(c.value or '').splitlines()) for c in ws[i])
        ws.row_dimensions[i].height = min(409,max(210,14*lines+24))
        if i%2 == 0:
            for cell in ws[i]:
                cell.fill = PatternFill('solid',fgColor='F2F6FA')
    ws.freeze_panes='D4'
    ws.auto_filter.ref=f'A3:K{ws.max_row}'
    ws.sheet_view.zoomScale=85
    ws.print_options.horizontalCentered=True
    ws.print_title_rows='1:3'
    ws.page_setup.orientation='landscape'
    ws.page_setup.paperSize=ws.PAPERSIZE_A3
    ws.page_setup.fitToWidth=3
    ws.page_setup.fitToHeight=0
    ws.print_title_cols='A:C'
    ws.print_area=f'A1:K{ws.max_row}'
    ws.sheet_properties.pageSetUpPr.fitToPage=True
    guide=wb.create_sheet('Field Guide')
    guide.append(['Field','Meaning'])
    for field in fields:
        guide.append([field['name'],field['meaning']])
    guide.append(['Priority rationale','P0 covers loss of primary control or core pointer behavior; P1 covers recovery, interoperability and scenario quality. Priorities are planning judgments, not measured failure rates.'])
    guide.append(['Execution state','All cases are planned; results remain blank. No device test has been executed to create this plan.'])
    guide.append(['Acceptance authority','A source value is conditional on its hardware/firmware and event definition; unresolved authority remains pending.'])
    guide.column_dimensions['A'].width=25
    guide.column_dimensions['B'].width=110
    for row in guide:
        for c in row:
            c.alignment=Alignment(vertical='top',wrap_text=True)
            c.font=Font(name='Aptos',size=11)
    for i in range(1,guide.max_row+1):
        guide.row_dimensions[i].height=44
    guide.page_setup.orientation='landscape'
    guide.page_setup.paperSize=guide.PAPERSIZE_A3
    guide.page_setup.fitToWidth=1
    guide.page_setup.fitToHeight=0
    guide.sheet_properties.pageSetUpPr.fitToPage=True
    guide.print_area=f'A1:B{guide.max_row}'
    wb.properties.creator='Controlled-device test planning reference generator'
    wb.properties.created=datetime(2026,10,11)
    wb.properties.modified=datetime(2026,10,11)
    raw=io.BytesIO()
    wb.save(raw)
    # OOXML ZIP metadata is canonicalized so --check compares real bytes.
    canonical=io.BytesIO()
    with zipfile.ZipFile(raw) as original, zipfile.ZipFile(canonical,'w',zipfile.ZIP_DEFLATED) as output:
        for name in sorted(original.namelist()):
            item=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
            item.create_system=0
            item.compress_type=zipfile.ZIP_DEFLATED
            content=original.read(name)
            if name=='docProps/core.xml':
                content=re.sub(rb'(<dcterms:modified[^>]*>).*?(</dcterms:modified>)',rb'\g<1>2026-10-11T00:00:00Z\2',content)
            output.writestr(item,content)
    return canonical.getvalue()


def solve(workspace, materials=None, evidence=None):
    workspace=Path(workspace)
    materials=Path(materials or workspace/'materials')
    contract,facts,applicability,rows,src=derive(materials)
    output=workspace/'output'
    output.mkdir(parents=True,exist_ok=True)
    target=output/ARTIFACT
    target.write_bytes(workbook_bytes(contract,facts,applicability,rows))
    if evidence:
        Path(evidence).parent.mkdir(parents=True,exist_ok=True)
        Path(evidence).write_text(json.dumps({'source_identities':src.identities,'derived_facts':facts,
            'fact_evidence':src.evidence,'case_count':len(rows),'construction':'SOP baseline extraction plus applicability-qualified engineering control rules; no Golden or scoring dependencies.'},ensure_ascii=False,indent=2)+'\n','utf-8')
    return target


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('workspace',type=Path)
    parser.add_argument('--materials',type=Path)
    parser.add_argument('--evidence',type=Path)
    args=parser.parse_args()
    print(solve(args.workspace,args.materials,args.evidence))

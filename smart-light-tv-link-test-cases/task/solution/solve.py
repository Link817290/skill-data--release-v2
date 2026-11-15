import sys
sys.dont_write_bytecode = True
import argparse
from datetime import datetime
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

from source_model import load_model


def cases_from_materials(m):
    cases = []
    common = "Record TV, Bridge, lamp and App versions. Use a supported TV/build, Ethernet Bridge on the same subnet/VLAN as the TV, and eligible paired lights."
    def add(code, module, title, priority, pre, steps, expected, source, note=""):
        cases.append([code, module, title, priority, pre, "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1)), expected, "", f"Sources: {source}. {note}".strip()])
    source = "SPEC-HUE-AMB-001"
    add("TC-AM-001", "Basic Function & Link", "Discover and authorize Bridge", "Must", common + " Disable AP/client isolation; Bridge is powered and reachable.",
        ["Open TV Hue linkage settings and start LAN discovery.", "Select the intended Bridge and complete physical-button authorization/pairing.", "Inspect the active configuration and observe a physical lamp response."],
        "The intended supported Bridge is discovered and bound. The linked configuration is usable and the physical light responds. Record discovery duration; the sources do not define a release discovery deadline.", source + " §7.1, §7.5; SOP §1.1-1.2; Product guide §8.2")
    add("TC-AM-002", "Basic Function & Link", "Multi-Bridge selection and switching", "Must", common + " Two supported Bridges have distinguishable identifiers and eligible lights.",
        ["Search for reachable Bridges and bind the first selected Bridge.", "Switch pairing to the second Bridge.", "Inspect the active Bridge and observe lights assigned to both Bridges."],
        "Only one Bridge is active for simultaneous linkage. The selected Bridge's lights follow the configuration; switching does not leave both Bridges concurrently linked.", source + " §7.1, §7.6")
    add("TC-AM-003", "Basic Function & Link", "Discover and add eligible linked lights", "Must", common + f" Identify lamp capabilities and prepare a scene within {m['max_lights']:g} lights.",
        ["Open linked-light device configuration and scan paired lights.", "Select supported lamps according to their color capabilities and inspect the scene.", "Trigger a configured color or temperature change and observe each selected lamp."],
        f"Supported Color/Extended Color lamps and LightStrip can link dynamically. White Ambiance provides temperature adjustment only; plain White is not a dynamic-color lamp. The scene contains no more than {m['max_lights']:g} linked lights.", source + " §7.1-7.2, §7.5")
    for code, mode, stimulus in [("TC-AM-004", "Movie", "controlled color-rich movie clip"), ("TC-AM-005", "Game", "rapid controlled color-change game scene")]:
        target = m["mode_ms"][mode.lower()]
        add(code, "Basic Function & Link", f"{mode} mode physical light linkage", "Must" if mode == "Game" else "Should", common + f" Select {mode} mode and record response-speed settings and the observation endpoints.",
            [f"Play the {stimulus}.", "Record the screen transition, TV backlight and Hue physical response in a synchronized timebase.", "Measure elapsed response time and inspect color transition smoothness."],
            f"{mode} mode target <= {target:g} ms; the SOP p95 {mode} target is <= {target:g} ms. External Hue end-to-end ceiling <= {m['hue_e2e_s']:g} s. Lights follow the configured content with smooth transitions and no visible desynchronization. Keep endpoint-specific measurements distinct; if mode-target endpoint applicability is unresolved for the release, mark the mode verdict pending clarification instead of certifying it.", source + " §6.1, §6.3, §7.3-7.4; SOP exit item2")
    add("TC-AM-006", "Basic Function & Link", "Music rhythm linkage", "Should", common + " Select Music mode; prepare Pulse, Gradient and Color Fluctuation algorithms at Low, Medium and High sensitivity.",
        ["Play rhythm-intensive audio and vary tempo and volume.", "Exercise Pulse, Gradient and Color Fluctuation at Low, Medium and High sensitivity.", "Observe physical lamp response for each algorithm/sensitivity combination.", "Measure elapsed Music response time and inspect drift or stutter."],
        f"Music mode target <= {m['mode_ms']['music']:g} ms for the declared metric. Every supported algorithm and sensitivity level produces a distinguishable, stable physical response without stuttering or accumulated drift. Record unsupported combinations instead of inventing behavior; a tempo change is not a universal promise of one fixed frequency relationship.", source + " §6.1, §7.3, §8.1")
    add("TC-AM-007", "Basic Function & Link", "Fixed-color always-on profile", "Could", common + " Verify the release supports the selected fixed-color/always-on profile and its Hue applicability.",
        ["Select a supported fixed-color profile and set a chosen color.", "Observe TV backlight and applicable linked lights over time.", "Record whether video changes affect the fixed effect."],
        "The supported fixed-color profile maintains the configured static effect without unintended flicker. External-lamp behavior is conditional on supported profile applicability; missing release confirmation blocks certification rather than implying support.", source + " §5.3, §7.5; SOP §2.1")
    add("TC-AM-008", "Basic Function & Link", "Voice-controlled mode switching", "Must", common + " Bind a supported voice platform and the relevant account; verify command/mode applicability.",
        ["Issue a supported voice command for Movie mode, then Game mode.", "Measure from command issuance to completed action.", "Observe actual TV mode and physical Hue effect, not just platform status."],
        f"Voice command completes within {m['voice_s']:g} s and the requested supported mode is reflected in physical lighting. Account/platform status alone does not prove execution.", source + " §10.1-10.3; SOP §1.4")
    add("TC-PER-001", "Performance & Real-time", "Paired-frame latency distribution", "Must", common + " Use controlled lighting, a color-step clip and a synchronized camera/timebase; record actual fps and endpoints.",
        ["Record screen color changes and physical light responses together.", "Pair each response frame with its triggering screen frame.", "Calculate delay_ms = 1000 * (response_frame - trigger_frame) / fps, or subtract timestamps in the same timebase.", "Repeat across events and compute p95 using a stated percentile convention; retain raw paired observations."],
        f"The elapsed latency is a response-minus-trigger duration, not an absolute timestamp. Game target <= {m['mode_ms']['game']:g} ms; Movie target <= {m['mode_ms']['movie']:g} ms; Hue ceiling <= {m['hue_e2e_s']:g} s. Applicable Game/Movie p95 gates use the SOP targets. Quantization is derived from actual fps; unresolved endpoint scope is qualified. No unanchored percentage standard-deviation gate is used.", source + " §6.1, §7.4; SOP terminology and exit item2")
    add("TC-PER-002", "Performance & Real-time", "App and TV manual-control arbitration", "Should", common + " Hue App can issue manual changes; record which documented release control policy applies.",
        ["Adjust lighting from TV and record the physical state and App observation.", "During active linkage issue a manual color change from the phone App.", "Measure handover/hold duration and observe the final control state; report successful trials as counts."],
        "Apply the documented profile: TV regains control within 3 s, or the product-defined manual color is retained for 10 s before resumption. If profile selection is unknown, the timing verdict is pending. Record state convergence rather than claiming an undocumented bidirectional 1s guarantee or population reliability from a small trial count.", source + " §7.6; SOP §2.2", "The source itself gives alternative3s/10s policies; neither is silently selected.")
    add("TC-PER-003", "Performance & Real-time", "Fast-motion transition smoothness", "Must", common + " Prepare fast color-change and gradient clips; select and record mode and lighting.",
        ["Play fast-motion/color-switch clips followed by a gradient clip.", "Observe physical transitions and record abnormal frames, jumps, stutter and flicker.", "When making a frequency-band claim, document instrument sampling bandwidth."],
        "Transitions have no stepped abrupt changes or visible flicker. Assess the specified high-frequency suppression only with adequate measurement bandwidth; a qualitative observation does not certify an unobserved frequency band.", source + " §6.3; SOP §1.5, §6")
    add("TC-PER-004", "Performance & Real-time", "Concurrent multi-light response", "Must", common + f" Prepare multiple eligible lights; this plan chooses eight as a stimulus, within the {m['max_lights']:g}-light scene limit. Record Entertainment Area setup.",
        ["Select all test lights and play controlled/color-rich transitions.", "Record screen-to-response delay for every light and compute the maximum delay.", "Observe physical consistency, disconnects and any available diagnostic counters."],
        f"All configured eligible lights respond; external Hue delay <= {m['hue_e2e_s']:g} s for each lamp, with any stricter applicable mode metric evaluated separately. The scene does not exceed {m['max_lights']:g} lamps. CPU measurements are diagnostic without an approved limit; inaccessible Bridge counters are not fabricated.", source + " §7.1-7.4; SOP §1.3, §6")
    add("TC-ERR-001", "Exception & Fault Tolerance", "Bridge network/power interruption", "Must", common + " Play video with working linkage and distinguish Bridge Ethernet from TV Wi-Fi.",
        ["Interrupt Bridge Ethernet or power during linkage.", "Observe the Hue physical state and independent TV backlight/playback.", "Time the App offline notification from the actual interruption."],
        f"Hue lamps maintain the last known state. TV Ambilight continues normal operation without crash. The App offline prompt occurs within {m['network_prompt_s']:g} s; this is not a TV-prompt requirement.", source + " §7.6, §12.1")
    add("TC-ERR-002", "Exception & Fault Tolerance", "Recovery after restored Bridge network", "Must", common + " Execute a Bridge network/power interruption first; record the retained configuration.",
        ["Restore the Bridge connection or power.", "Start recovery timing when connectivity is restored, without initiating rebinding.", "Observe automatic reconnection and resumed physical light sync."],
        f"Automatic reconnection/resumed sync is complete within {m['recovery_s']:g} s of restored connectivity, without manual rebinding or abnormal flicker.", source + " §7.6, §12.1")
    add("TC-ERR-003", "Exception & Fault Tolerance", "Single-lamp power interruption", "Must", common + " Link more than one light and identify one lamp for power removal.",
        ["Cut power to one selected lamp during linkage.", "Observe the remaining lights and TV, and time the App notification.", "Restore the lamp power and record its reintegration behavior without assuming a restart deadline."],
        f"Remaining lights continue sync and the TV has no lag/crash. The App Light Offline notification occurs within {m['lamp_prompt_s']:g} s. Individual-lamp restart timing is characterized; the source does not supply a restart SLA.", source + " §12.2")
    ordered = [x.strip() for x in m["priority_order"].split(">")]
    winner = min(["Game", "Movie"], key=ordered.index)
    add("TC-ERR-004", "Exception & Fault Tolerance", "Concurrent Game/Movie mode triggers", "Must", common + " Movie linkage is active; Game trigger is supported.",
        ["Issue the Game trigger during Movie playback.", "Time and observe the selected active mode and physical transition.", "Inspect for freezing or visible flicker."],
        f"{winner} overrides the lower-priority competing mode under the documented ordering ({m['priority_order']}). Mode transition <= {m['priority_transition_s']:g} s without crash or visible flicker.", source + " §12.4")
    add("TC-ERR-005", "Exception & Fault Tolerance", "Weak/degraded network characterization", "Must", common + " Apply impairment to the TV-Bridge path using a network simulation tool; record the healthy baseline.",
        ["Inject a documented test-choice latency/loss profile and observe timing, continuity and notifications.", "Increase impairment and record actual link loss or continued operation.", "Restore the baseline and, if a disconnect occurred, measure reconnect from restored connectivity."],
        f"Record degraded-network observations without an undocumented SLA or mandatory packet-loss warning. If an actual disconnect occurs, lights hold their last state while TV remains operational. After restored connectivity automatic recovery <= {m['recovery_s']:g} s. A release-specific degraded-network acceptance profile remains conditional on approval.", source + " §7.6, §12.1; SOP §1.1, §5")
    add("TC-ERR-006", "Exception & Fault Tolerance", "Bridge firmware upgrade recovery", "Must", common + " Record the existing configuration and have an authorized Bridge upgrade available.",
        ["Initiate the Bridge firmware upgrade in App and observe linkage unavailability.", "Observe completion and restoration of the recorded configuration.", "For a controlled timeout variant, observe the manual-check prompt when recovery does not occur."],
        f"Linkage is temporarily unavailable during upgrade. After completion the configuration restores automatically without re-pairing. If upgrade exceeds {m['upgrade_timeout_s']:g} s without recovery, prompt manual checking. Arbitrary flashing/reset is not certified as expected.", source + " §12.3; SOP §6")
    add("TC-REL-001", "Environment & Reliability", "Daylight ambient-light adaptation", "Should", common + f" Use an ALS-capable unit, enable adaptive brightness for this case and prepare measured daylight above {m['day_lux']:g} lux within the sensor range. Record manual cap/override and fixed content.",
        ["Measure a controlled reference brightness.", "Increase ambient illuminance and record physical brightness/contrast with unchanged mode/content.", "Observe transitions and restore the baseline adaptive setting after the case."],
        "At the documented daylight condition, TV Ambilight increases adaptive brightness/contrast subject to the manual limit. External Hue inheritance is conditional on release capability; do not certify it from the TV-only statement. No unsupported fixed percentage rise is required.", source + " §9.1-9.3; SOP §1.4, §1.6")
    low, high = m["night_reduction_pct"]
    add("TC-REL-002", "Environment & Reliability", "Night/pitch-black adaptive brightness", "Should", common + f" Enable ALS adaptation, record the reference brightness and manual cap, and control night lighting below {m['night_lux']:g} lux separately from pitch black below {m['black_lux']:g} lux.",
        ["With fixed content/mode measure reference brightness, then the night output.", "Calculate reduction_pct = 100*(reference - night)/reference.", "Measure a separate pitch-black condition and observe the minimum-brightness effect."],
        f"In the night region brightness reduces by {low:g}%-{high:g}% relative to the defined baseline. In pitch black (< {m['black_lux']:g} lux), minimum brightness retains a faint halo. This is not an absolute output below30%. External Hue applicability and the reference condition are explicitly qualified.", source + " §9.1-9.3")
    add("TC-REL-003", "Environment & Reliability", f"{m['stability_h']:g}-hour linkage stability", "Should", common + " Prepare automated playback/mode changes, monitoring and a post-warm-up baseline for the same measured process.",
        [f"Run the planned sequence for {m['stability_h']:g} hours with a documented switching/sampling schedule.", "Log crashes, freezes, continuity and available CPU/memory diagnostics.", "Calculate memory growth_pct =100*(final_memory - baseline_memory)/baseline_memory using the same process/metric."],
        f"No crash or freeze during {m['stability_h']:g} h. Memory growth < {m['memory_growth_pct']:g}% after the run. CPU limits and a population linkage-success guarantee are not invented; retain observed counts and resource trends.", source + " §13; SOP exit item3")
    return cases


def write_workbook(materials, destination):
    model = load_model(materials)
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Test Cases"
    sheet.append(["Case ID", "Module", "Test Case Name", "Priority (MoSCoW)", "Preconditions", "Test Steps", "Expected Results", "Test Result", "Remarks / Sources"])
    for case in cases_from_materials(model):
        sheet.append(case)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for key, width in zip("ABCDEFGHI", [16, 28, 40, 18, 75, 85, 100, 20, 75]):
        sheet.column_dimensions[key].width = width
    priorities = book.create_sheet("Priority Rationale")
    priorities.append(["Priority", "Meaning", "Rationale"])
    priorities.append(["Must", "Release critical", "Core linkage, defined critical timing and documented recovery/control behavior. Explicit source priority takes precedence; explain release-specific deviations."])
    priorities.append(["Should", "Important", "Requirements explicitly designated Should, or important environmental/performance characterization without a stronger approved release policy."])
    priorities.append(["Could", "Optional profile", "Fixed-effect profile testing where the installed release supports it; capability must be verified."])
    priorities.append(["Won't", "Excluded scope", "No component electrical/protocol-debugging suite or invented device execution records."])
    environment = book.create_sheet("Environment Checklist")
    environment.append(["Configuration Item", "Requirement", "Ready", "Remarks"])
    for row in [
        ["TV/build", "Verified Ambilight-Hue support; record firmware and model", "", "Catalog naming alone does not prove native linkage"],
        ["Bridge", "Supported Bridge on Ethernet; same subnet/VLAN as TV", "", "Record firmware; do not use a Wi-Fi-bridged SOP fixture"],
        ["Lights", f"Eligible lamp types; no more than {model['max_lights']:g} per scene", "", "Extend the fixture for the selected concurrent-light stimulus"],
        ["Network", "Dedicated TV Wi-Fi; AP isolation disabled; baseline signal>-65dBm and packet loss0%", "", "Record impairment path/profile separately"],
        ["Room", "20-25 C; white/light-gray wall; proposed10cm gap meets overlapping recommendations", "", "No45 C durability obligation is inferred"],
        ["Camera/timebase", "Synchronized trigger and response capture; record actual frame rate/resolution", "", "Measurement quantization must be recorded"],
        ["ALS/light meter", "Measured lux and brightness baseline; enable adaptation only for its cases", "", "External-lamp applicability requires release confirmation"],
        ["Network simulator", "Controlled TV-Bridge latency/loss injection", "", "Injected profiles are stimuli, not product promises"],
        ["Monitoring", "Process identity, post-warm-up memory baseline and diagnostic counters", "", "No inaccessible Bridge telemetry is invented"],
        ["Materials", "Color-step, gradient, movie, game and music stimuli", "", "Keep mode/content fixed where needed"],
        ["Execution record", "Plan only; results remain blank/unexecuted", "", "No hardware observations supplied"]
    ]:
        environment.append(row)
    exit_sheet = book.create_sheet("Exit Checklist")
    exit_sheet.append(["No.", "Check Item", "Status"])
    for number, item in enumerate([
        "All Must Have test cases executed and passed",
        "Latency evidence archived and p95 meets the applicable Game/Movie targets",
        "Fault recovery passed and 72h memory growth is below 5%",
        "No P0/P1 defects remain; P2 defects have a workaround or scheduled fix",
        "Test report submitted with latency distribution and representative failures",
        "Environment restored: linkage disabled and Bridge disconnected",
        "Videos and screenshots archived to the shared evidence location",
        "TV, Bridge and Hue App versions recorded",
        "Test lights powered off/stored and Bridge returned to inventory",
        "Results communicated to Product Manager and Development Lead",
    ], 1):
        exit_sheet.append([number, item, "Pending Confirmation"])
    for ws in book.worksheets:
        for row in ws:
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
                if cell.row == 1:
                    cell.fill = PatternFill("solid", fgColor="23503B")
                    cell.font = Font(color="FFFFFF", bold=True)
            if row[0].row > 1:
                ws.row_dimensions[row[0].row].height = 125 if ws == sheet else 60
        if ws != sheet:
            for key in "ABCD":
                ws.column_dimensions[key].width = 40 if key == "A" else 80
    book.properties.creator = ""
    book.properties.lastModifiedBy = ""
    book.properties.created = datetime(2026, 10, 12)
    book.properties.modified = datetime(2026, 10, 12)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    book.save(destination)
    return model


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace")
    parser.add_argument("--materials")
    args = parser.parse_args()
    ws = Path(args.workspace)
    write_workbook(args.materials or ws / "materials", ws / "output/linkage-test-cases.xlsx")

#!/usr/bin/env python3
"""Build the reference authorization audit from the supplied PDF record."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def page_text(path: Path, page: int) -> str:
    completed = subprocess.run(
        ["pdftotext", "-f", str(page), "-l", str(page), "-raw", str(path), "-"],
        check=True,
        text=True,
        capture_output=True,
    )
    return " ".join(completed.stdout.split()).lower()


def require_page(path: Path, page: int, phrases: tuple[str, ...]) -> None:
    text = page_text(path, page)
    absent = [phrase for phrase in phrases if phrase.lower() not in text]
    if absent:
        raise ValueError(f"source-page assertion failed for {path.name} PDF page {page}: {absent}")


def location(document: str, page: int, supports: str) -> dict:
    return {"document": document, "pdf_page": page, "supports": supports}


def build(workspace: Path) -> dict:
    dossier = workspace / "review_dossier.pdf"
    authority = workspace / "applicable_regulatory_authority.pdf"
    if not dossier.is_file() or not authority.is_file():
        raise FileNotFoundError("both supplied PDF files are required")

    checks = {
        (dossier, 18): ("below is an example of a haccp plan",),
        (dossier, 19): (
            "refrigerated, vacuum-packaged",
            "per process",
            "annual wps/a",
            "signature of company official",
        ),
        (authority, 29): ("monitoring process should directly measure",),
        (authority, 30): ("must accomplish two goals",),
        (authority, 132): ("scombrotoxin (histamine) formation as a result", "certain species"),
        (authority, 133): ("stable while in the frozen state", "reactivated very rapidly after thawing"),
        (authority, 281): ("internal temperature of the product", "cooling rate study"),
        (authority, 302): ("reduced oxygen packaged smoked", "proper concentration of salt"),
        (authority, 308): ("water phase salt level is critical", "both operations"),
        (authority, 311): ("established by a scientific study", "finished product has not less"),
        (authority, 313): ("process validation study", "check the accuracy"),
        (authority, 314): ("finished product sampling and analysis", "every 3 months"),
        (authority, 371): ("sanitation controls need not be part of your haccp plan",),
    }
    for (path, page), phrases in checks.items():
        require_page(path, page, phrases)

    findings = [
        {
            "finding_id": "A-01",
            "reference_anchor": "release_boundary",
            "control_dimension": "decision_boundary",
            "haccp_element": "plan authorization and document control",
            "decision_significance": "authorization blocker",
            "conclusion": (
                "Hold authorization. The dossier labels the plan as an illustrative example, "
                "the supplied copy has blank signature and revision fields, and its referenced "
                "notes and process schedules are not in the packet."
            ),
            "evidence_boundary": (
                "This establishes that this packet is not ready for authorization. It does not "
                "prove how a facility actually operates or that no signed controlled plan exists elsewhere."
            ),
            "corrective_recommendation": (
                "Provide the controlled, signed, current establishment plan together with every "
                "incorporated note, schedule, and supporting record before approval."
            ),
            "evidence": [
                location("review_dossier.pdf", 18, "the plan is introduced as an example"),
                location("review_dossier.pdf", 19, "blank authorization fields and schedule references"),
            ],
        },
        {
            "finding_id": "A-02",
            "reference_anchor": "scope_hazard_analysis",
            "control_dimension": "applicability_hazard_scope",
            "haccp_element": "product scope and hazard analysis",
            "decision_significance": "authorization blocker",
            "conclusion": (
                "The generic fish description and absent referenced notes do not establish species, "
                "source, size grouping, or the hazard-analysis decisions needed to define one valid plan scope."
            ),
            "evidence_boundary": (
                "Species- and source-dependent hazards are not determinable from this excerpt; absence "
                "from the table is not evidence that those hazards are not reasonably likely."
            ),
            "corrective_recommendation": (
                "Supply the product-group rationale and hazard analysis identifying species, sources, "
                "forms, intended use, process variants, and the basis for every applicability decision."
            ),
            "evidence": [
                location("review_dossier.pdf", 19, "generic product description and missing Note 1"),
                location("applicable_regulatory_authority.pdf", 311, "species and other product factors affect the established process"),
            ],
        },
        {
            "finding_id": "A-03",
            "reference_anchor": "scombrotoxin_applicability",
            "control_dimension": "applicability_hazard_scope",
            "haccp_element": "receiving and in-plant toxin hazard analysis",
            "decision_significance": "conditional authorization blocker",
            "conclusion": (
                "Scombrotoxin applicability remains conditional because no species or pre-receipt "
                "time-temperature history is supplied. Frozen receipt or a later cook would not by "
                "itself establish control before freezing or reverse preformed histamine."
            ),
            "evidence_boundary": (
                "The record does not show that a histamine-forming species is used, so it cannot support "
                "either an affirmative hazard finding or a not-applicable conclusion."
            ),
            "corrective_recommendation": (
                "Identify each species and source, then document the receiving and harvest-history control "
                "decision for every histamine-forming species in scope."
            ),
            "evidence": [
                location("review_dossier.pdf", 19, "species is not identified"),
                location("applicable_regulatory_authority.pdf", 132, "the hazard applies to certain species"),
                location("applicable_regulatory_authority.pdf", 133, "freezing does not erase the hazard history"),
            ],
        },
        {
            "finding_id": "A-04",
            "reference_anchor": "botulinum_hazard_identity",
            "control_dimension": "botulinum_control_chain",
            "haccp_element": "reduced-oxygen smoked-fish barrier system",
            "decision_significance": "authorization blocker",
            "conclusion": (
                "The refrigerated vacuum package triggers an organism-specific Clostridium botulinum "
                "barrier analysis, but the plan names only generic pathogen growth. It does not connect "
                "heat injury, finished-product salt, drying, and refrigeration to the relevant organism "
                "groups: type E and nonproteolytic type B/F, whose heat-injured spores require the "
                "applicable finished-product salt and process barriers, and type A and proteolytic type "
                "B/F, whose more heat-resistant spores require strict refrigeration as an independent "
                "barrier."
            ),
            "evidence_boundary": (
                "The excerpt shows intended barriers, not a demonstrated barrier system; product safety "
                "and actual implementation therefore remain not determinable."
            ),
            "corrective_recommendation": (
                "Revise the hazard analysis and plan to identify the target organism groups and map each "
                "validated barrier and storage control to the group it controls."
            ),
            "evidence": [
                location("review_dossier.pdf", 19, "vacuum packaging and generic pathogen rows"),
                location("applicable_regulatory_authority.pdf", 302, "hot-smoked reduced-oxygen barrier interaction"),
                location("applicable_regulatory_authority.pdf", 308, "salt, drying, smoking, and storage roles"),
            ],
        },
        {
            "finding_id": "A-05",
            "reference_anchor": "brining_drying_endpoint",
            "control_dimension": "botulinum_control_chain",
            "haccp_element": "brining and smoking/drying critical limits",
            "decision_significance": "authorization blocker",
            "conclusion": (
                "Brine strength and elapsed time are recipe inputs. The missing process schedule and study "
                "leave no demonstrated connection to a finished-product water-phase-salt endpoint across "
                "species, thickness, load, drying conditions, and equipment."
            ),
            "evidence_boundary": (
                "Annual product checks and the words 'per process schedule' do not show that each lot reaches "
                "the inhibitory endpoint. The schedule's actual contents are not supplied."
            ),
            "corrective_recommendation": (
                "Supply a scientific process-establishment study covering all critical brining and drying "
                "factors, or define representative direct finished-product monitoring with lot disposition."
            ),
            "evidence": [
                location("review_dossier.pdf", 19, "recipe inputs and absent process-schedule values"),
                location("applicable_regulatory_authority.pdf", 311, "critical factors and finished-product endpoint"),
                location("applicable_regulatory_authority.pdf", 313, "scientific establishment of the process"),
            ],
        },
        {
            "finding_id": "A-06",
            "reference_anchor": "process_schedule_support",
            "control_dimension": "process_validation",
            "haccp_element": "scheduled-process validation",
            "decision_significance": "authorization blocker",
            "conclusion": (
                "The critical limits for brining, smoking/drying, and cooking are incorporated by reference "
                "to a process schedule that is absent. No scientific study establishes those critical "
                "factors for the stated product and equipment."
            ),
            "evidence_boundary": (
                "The table cannot be validated from schedule titles or cross-references, and the packet does "
                "not support a conclusion that the underlying process is inadequate or adequate."
            ),
            "corrective_recommendation": (
                "Provide the approved schedule and validation study, including scope, worst-case product and "
                "load, equipment configuration, critical factors, results, and approval."
            ),
            "evidence": [
                location("review_dossier.pdf", 19, "three limits depend on an absent schedule"),
                location("applicable_regulatory_authority.pdf", 313, "the process is to be established scientifically"),
            ],
        },
        {
            "finding_id": "A-07",
            "reference_anchor": "periodic_product_verification",
            "control_dimension": "process_validation",
            "haccp_element": "finished-product verification",
            "decision_significance": "control-system weakness",
            "conclusion": (
                "The annual water-phase-salt/water-activity check is periodic verification and cannot "
                "substitute for missing process validation. Where finished-product analysis is not direct "
                "monitoring, the current reference calls for analysis at least every three months."
            ),
            "evidence_boundary": (
                "The packet provides no justified alternative frequency, sampling plan, analytical method, "
                "or failing-result response, so the adequacy of the annual check is not established."
            ),
            "corrective_recommendation": (
                "Define whether product analysis is lot monitoring or periodic verification, then document "
                "a supported frequency, representative sampling, method, lot linkage, and deviation response."
            ),
            "evidence": [
                location("review_dossier.pdf", 19, "annual finished-product check"),
                location("applicable_regulatory_authority.pdf", 314, "periodic finished-product analysis frequency"),
            ],
        },
        {
            "finding_id": "A-08",
            "reference_anchor": "cooling_measurement",
            "control_dimension": "cooling_control",
            "haccp_element": "cooling CCP monitoring",
            "decision_significance": "authorization blocker",
            "conclusion": (
                "Continuous cooling-room temperature is an ambient measurement, not the cooling curve of "
                "the warmest product. The plan supplies neither internal product time-temperature monitoring "
                "nor a cooling-rate study that establishes the listed cooler condition as a valid surrogate."
            ),
            "evidence_boundary": (
                "A cold room may be necessary, but the excerpt cannot demonstrate the product cooling rate "
                "for its actual size, loading, spacing, packaging, and starting condition."
            ),
            "corrective_recommendation": (
                "Monitor a worst-case product cooling profile or provide a matching cooling study and list "
                "all validated process factors, monitoring locations, and deviation actions in the plan."
            ),
            "evidence": [
                location("review_dossier.pdf", 19, "ambient cooling-room monitoring"),
                location("applicable_regulatory_authority.pdf", 281, "internal product monitoring or studied process factors"),
            ],
        },
        {
            "finding_id": "A-09",
            "reference_anchor": "cooking_monitoring",
            "control_dimension": "monitoring_limit_alignment",
            "haccp_element": "smoking/cooking monitoring system",
            "decision_significance": "control-system weakness",
            "conclusion": (
                "The cooking limit names final cook time and center temperature, while the method says only "
                "chart recorder. The record does not show how both parameters are measured, where an internal "
                "sensor is placed, or which unit represents the coldest worst case."
            ),
            "evidence_boundary": (
                "This is a bounded design gap; it does not prove the plant lacks a suitable sensor or recorder."
            ),
            "corrective_recommendation": (
                "Identify the instrument and sensor placement for every scheduled parameter, including the "
                "worst-case unit, start/end rule, recording frequency, responsible role, and linked batch record."
            ),
            "evidence": [
                location("review_dossier.pdf", 19, "limit-to-chart-recorder mismatch"),
                location("applicable_regulatory_authority.pdf", 29, "monitoring is to measure the critical-limit parameter"),
            ],
        },
        {
            "finding_id": "A-10",
            "reference_anchor": "corrective_action_closure",
            "control_dimension": "corrective_action_closure",
            "haccp_element": "predetermined corrective actions",
            "decision_significance": "authorization blocker",
            "conclusion": (
                "Hold/evaluate, reprocess, adjust, and relabel are not closed corrective-action procedures. "
                "They do not define the affected lot and lookback, qualified evaluation basis, supported "
                "product disposition, cause correction, or restoration of process control."
            ),
            "evidence_boundary": (
                "Relabeling can correct package text only when the product remained safe; it cannot remedy "
                "temperature abuse that already occurred. Actual deviation handling is not determinable."
            ),
            "corrective_recommendation": (
                "For each CCP, add a product track that contains and safely disposes of affected lots and a "
                "process track that corrects the cause, restores control, documents action, and triggers reassessment."
            ),
            "evidence": [
                location("review_dossier.pdf", 19, "open-ended corrective-action verbs"),
                location("applicable_regulatory_authority.pdf", 30, "product protection and cause correction are both required"),
            ],
        },
        {
            "finding_id": "A-11",
            "reference_anchor": "instrument_verification",
            "control_dimension": "verification_calibration",
            "haccp_element": "record review and instrument verification",
            "decision_significance": "control-system weakness",
            "conclusion": (
                "The stated daily record reviews are useful and should be retained, but a weekly 'recorder "
                "check' does not define an accuracy check, reference standard, acceptance criterion, calibration, "
                "or evaluation back to the last known accurate result."
            ),
            "evidence_boundary": (
                "The wording does not establish what the check includes, and no completed verification or "
                "calibration records are supplied. Instrument control is therefore not determinable."
            ),
            "corrective_recommendation": (
                "Define pre-use and ongoing accuracy checks, calibration against a known reference over the "
                "use range, acceptable error, records, and out-of-tolerance lookback for affected lots."
            ),
            "evidence": [
                location("review_dossier.pdf", 19, "record review and undefined recorder checks"),
                location("applicable_regulatory_authority.pdf", 313, "accuracy check against a reference"),
                location("applicable_regulatory_authority.pdf", 314, "calibration and record-review expectations"),
            ],
        },
        {
            "finding_id": "A-12",
            "reference_anchor": "storage_distribution",
            "control_dimension": "distribution_and_storage",
            "haccp_element": "finished-product storage and distribution",
            "decision_significance": "control-system weakness",
            "conclusion": (
                "Credit the conservative in-house storage limit and continuous chart recording. However, "
                "the label check at packaging is not evidence that refrigerated exposure was controlled "
                "during transport and distribution."
            ),
            "evidence_boundary": (
                "The packet contains no carrier temperature record, time-temperature indicator evidence, "
                "receipt check, or supported transit strategy, so distribution control is not determinable."
            ),
            "corrective_recommendation": (
                "Retain the in-house control and add a validated shipping/receipt strategy with exposure "
                "records, responsibility, review, and corrective action tied to affected shipments."
            ),
            "evidence": [
                location("review_dossier.pdf", 19, "storage recorder and label-only distribution control"),
                location("applicable_regulatory_authority.pdf", 302, "refrigeration is part of the smoked-fish barrier system"),
                location("applicable_regulatory_authority.pdf", 309, "storage and distribution exposure remains safety-critical"),
            ],
        },
        {
            "finding_id": "A-13",
            "reference_anchor": "postprocess_boundary",
            "control_dimension": "postprocess_boundary",
            "haccp_element": "post-cook contamination control",
            "decision_significance": "evidence request, not an automatic CCP finding",
            "conclusion": (
                "Post-process contamination must be assessed for exposed ready-to-eat product, but this "
                "excerpt does not support declaring that an additional CCP is required or omitted. Such "
                "contamination may be controlled through a documented sanitation program."
            ),
            "evidence_boundary": (
                "The hazard analysis, sanitation controls, environmental monitoring, and implementation "
                "records are absent, so adequacy and execution are not determinable from the packet."
            ),
            "corrective_recommendation": (
                "Provide the post-cook hazard-analysis decision and the applicable sanitation or HACCP "
                "control records, including exposed-product handling, monitoring, response, and verification."
            ),
            "evidence": [
                location("review_dossier.pdf", 19, "ready-to-eat process excerpt lacks supporting hazard analysis"),
                location("applicable_regulatory_authority.pdf", 371, "post-process introduction can be managed outside the HACCP plan"),
            ],
        },
    ]

    return {
        "audit_scope": {
            "decision": "authorization readiness of the supplied plan packet",
            "materials_reviewed": ["review_dossier.pdf", "applicable_regulatory_authority.pdf"],
            "evidence_rule": "No inference beyond the supplied record; absent support remains not determinable.",
        },
        "overall_disposition": {
            "status": "HOLD - NOT READY FOR AUTHORIZATION",
            "basis": (
                "The packet does not close the product-hazard scope, organism-specific reduced-oxygen "
                "barrier chain, scheduled-process validation, cooling measurement, or deviation response."
            ),
            "release_condition": "Resolve every authorization blocker and re-review the controlled packet.",
        },
        "findings": findings,
        "positive_controls_retained": [
            "Daily review of several monitoring records is explicitly stated.",
            "Finished-product storage uses continuous recording at a conservative stated setting.",
        ],
    }


def main() -> int:
    workspace = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/workspace")
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/workspace/haccp_audit.json")
    result = build(workspace)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

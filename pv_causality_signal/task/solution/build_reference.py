#!/usr/bin/env python3
"""Build the reference adjudication from the shipped relational extract."""
from __future__ import annotations

import calendar
import csv
import json
import math
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = []
        for line, row in enumerate(csv.DictReader(handle), start=2):
            row["_line"] = str(line)
            rows.append(row)
        return rows


def split_components(value: str) -> set[str]:
    return {part.strip().upper() for part in value.split("\\") if part.strip()}


def reporter_group(code: str) -> str:
    if code in {"MD", "PH", "HP"}:
        return "HCP"
    if code == "CN":
        return "CONSUMER"
    return "OTHER"


def canonical_headers(headers: list[dict[str, str]]) -> tuple[list[dict[str, str]], dict[str, list[str]]]:
    selected: dict[str, tuple[tuple[object, ...], dict[str, str]]] = {}
    rejected: dict[str, list[str]] = defaultdict(list)
    for row in headers:
        rank = (int(row["caseversion"]), row["fda_dt"], int(row["primaryid"]))
        previous = selected.get(row["caseid"])
        if previous is None or rank > previous[0]:
            if previous is not None:
                rejected[row["caseid"]].append(previous[1]["primaryid"])
            selected[row["caseid"]] = (rank, row)
        else:
            rejected[row["caseid"]].append(row["primaryid"])
    return [value[1] for value in selected.values()], rejected


def table_for(
    headers: list[dict[str, str]],
    ingredient: str,
    event: str,
    components: dict[str, set[str]],
    drug_parts: dict[str, list[set[str]]],
    reactions: dict[str, set[str]],
) -> dict[str, object]:
    observations = {row["primaryid"] for row in headers}
    exposed = {
        report_id
        for report_id in observations
        if any(parts & components[ingredient] for parts in drug_parts.get(report_id, []))
    }
    events = {report_id for report_id in observations if event in reactions.get(report_id, set())}
    a = len(exposed & events)
    b = len(exposed - events)
    c = len(events - exposed)
    d = len(observations) - a - b - c
    result: dict[str, object] = {"a": a, "b": b, "c": c, "d": d}
    if min(a, b, c, d) == 0:
        result.update({"ror": None, "ror025": None, "signal": "UNASSESSABLE"})
        return result
    ror = (a * d) / (b * c)
    lower = math.exp(math.log(ror) - 1.96 * math.sqrt(sum(1 / value for value in (a, b, c, d))))
    result.update(
        {
            "ror": round(ror, 9),
            "ror025": round(lower, 9),
            "signal": "YES" if a >= 3 and lower > 1 else "NO",
        }
    )
    return result


def mh_common(strata: list[dict[str, object]]) -> float | None:
    numerator = 0.0
    denominator = 0.0
    for row in strata:
        a, b, c, d = (int(row[key]) for key in ("a", "b", "c", "d"))
        size = a + b + c + d
        numerator += a * d / size
        denominator += b * c / size
    return round(numerator / denominator, 9) if numerator and denominator else None


def source_refs(
    report_id: str,
    tables: dict[str, list[dict[str, str]]],
    target_sequences: set[str],
    target_event: str,
) -> dict[str, list[str]]:
    refs: dict[str, list[str]] = {}
    for name, rows in tables.items():
        selected = []
        for row in rows:
            if row["primaryid"] != report_id:
                continue
            if name == "ther" and row["dsg_drug_seq"] not in target_sequences:
                continue
            if name == "reac" and row["pt"] != target_event:
                continue
            selected.append(f"/workspace/faers/{name}.csv:{row['_line']}")
        if selected:
            refs[name] = selected
    return refs


def version_source_refs(
    report_id: str,
    table_rows_by_report: dict[str, dict[str, list[dict[str, str]]]],
    target_components: set[str],
    target_event: str,
) -> dict[str, list[str]]:
    target_sequences = {
        row["drug_seq"]
        for row in table_rows_by_report["drug"].get(report_id, [])
        if split_components(row["prod_ai"]) & target_components
    }
    refs: dict[str, list[str]] = {}
    for name, indexed_rows in table_rows_by_report.items():
        selected = []
        for row in indexed_rows.get(report_id, []):
            if name == "drug" and row["drug_seq"] not in target_sequences:
                continue
            if name == "ther" and row["dsg_drug_seq"] not in target_sequences:
                continue
            if name == "reac" and row["pt"] != target_event:
                continue
            selected.append(f"/workspace/faers/{name}.csv:{row['_line']}")
        if selected:
            refs[name] = selected
    return refs


def pair_state(
    report_id: str,
    target_components: set[str],
    target_event: str,
    drug_rows_by_report: dict[str, list[dict[str, str]]],
    reactions: dict[str, set[str]],
) -> tuple[str, bool, bool]:
    exposed = any(
        row["role_cod"] == "PS" and split_components(row["prod_ai"]) & target_components
        for row in drug_rows_by_report[report_id]
    )
    event = target_event in reactions[report_id]
    if exposed and event:
        state = "PAIR"
    elif exposed:
        state = "EXPOSURE_ONLY"
    elif event:
        state = "EVENT_ONLY"
    else:
        state = "NEITHER"
    return state, exposed, event


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/workspace")
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/workspace/faers_adjudication.json")
    faers = root / "faers"
    tables = {name: read_rows(faers / f"{name}.csv") for name in ("demo", "drug", "reac", "ther", "outc")}
    scope = json.loads(Path(__file__).with_name("review_scope.json").read_text(encoding="utf-8"))
    pairs = scope["candidate_pairs"]
    driver_reviews = scope["version_driver_reviews"]
    reviews = scope["case_reviews"]
    longitudinal_reviews = scope["longitudinal_reviews"]
    component_rows = scope["ingredient_components"]

    table_rows_by_report: dict[str, dict[str, list[dict[str, str]]]] = {}
    for name, rows in tables.items():
        indexed: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            indexed[row["primaryid"]].append(row)
        table_rows_by_report[name] = indexed

    components: dict[str, set[str]] = defaultdict(set)
    for row in component_rows:
        components[row["active_ingredient"]].add(row["accepted_prod_ai_component"].strip().upper())

    canonical, rejected = canonical_headers(tables["demo"])
    canonical_ids = {row["primaryid"] for row in canonical}
    all_headers = tables["demo"]

    primary_drug_parts: dict[str, list[set[str]]] = defaultdict(list)
    drug_rows_by_report: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in tables["drug"]:
        drug_rows_by_report[row["primaryid"]].append(row)
        if row["role_cod"].upper() == "PS":
            primary_drug_parts[row["primaryid"]].append(split_components(row["prod_ai"]))

    reactions: dict[str, set[str]] = defaultdict(set)
    for row in tables["reac"]:
        reactions[row["primaryid"]].add(row["pt"])

    headers_by_case: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in tables["demo"]:
        headers_by_case[row["caseid"]].append(row)
    versioned_cases = {
        caseid: sorted(rows, key=lambda row: (int(row["caseversion"]), row["fda_dt"], int(row["primaryid"])))
        for caseid, rows in headers_by_case.items()
        if len(rows) > 1
    }

    period_headers = {
        period: [row for row in canonical if row["source_quarter"] == period]
        for period in ("2023Q4", "2024Q1")
    }
    reporter_headers = {
        group: [row for row in canonical if reporter_group(row["occp_cod"]) == group]
        for group in ("HCP", "CONSUMER", "OTHER")
    }
    cross_headers = {
        (period, group): [
            row
            for row in canonical
            if row["source_quarter"] == period and reporter_group(row["occp_cod"]) == group
        ]
        for period in ("2023Q4", "2024Q1")
        for group in ("HCP", "CONSUMER", "OTHER")
    }

    pair_results = []
    version_driver_summaries = []
    version_driver_results = []
    driver_review_scope = {(row["pair_id"], row["caseid"]) for row in driver_reviews}
    if len(driver_review_scope) != len(driver_reviews):
        raise ValueError("version-driver review roster contains duplicate rows")
    completed_driver_reviews: set[tuple[str, str]] = set()
    for pair in pairs:
        ingredient = pair["active_ingredient"]
        event = pair["meddra_pt"]
        canonical_table = table_for(canonical, ingredient, event, components, primary_drug_parts, reactions)
        version_table = table_for(all_headers, ingredient, event, components, primary_drug_parts, reactions)
        hcp_table = table_for(reporter_headers["HCP"], ingredient, event, components, primary_drug_parts, reactions)
        periods = {
            period: table_for(rows, ingredient, event, components, primary_drug_parts, reactions)
            for period, rows in period_headers.items()
        }
        strata = []
        for (period, group), rows in cross_headers.items():
            table = table_for(rows, ingredient, event, components, primary_drug_parts, reactions)
            strata.append({"source_quarter": period, "reporter_group": group, **table})

        before = version_table["signal"]
        after = canonical_table["signal"]
        if before != "YES" and after == "YES":
            version_effect = "GAINED"
        elif before == "YES" and after != "YES":
            version_effect = "LOST"
        elif before == after == "YES":
            version_effect = "STABLE_YES"
        else:
            version_effect = "STABLE_NO"

        if after == "YES" and (
            hcp_table["signal"] == "YES"
            or all(periods[period]["signal"] == "YES" for period in periods)
        ):
            disposition = "ESCALATE"
        elif after == "YES":
            disposition = "MONITOR"
        else:
            disposition = "CLOSE"

        pair_results.append(
            {
                "pair_id": pair["pair_id"],
                "active_ingredient": ingredient,
                "meddra_pt": event,
                "canonical": canonical_table,
                "all_versions": version_table,
                "hcp": hcp_table,
                "periods": periods,
                "stratified": {"mh_ror": mh_common(strata), "strata": strata},
                "version_effect": version_effect,
                "disposition": disposition,
            }
        )

        census = {
            "multi_submission_cases_examined": len(versioned_cases),
            "state_change_drivers": 0,
            "primary_exposure_change_drivers": 0,
            "target_event_change_drivers": 0,
            "pair_membership_change_drivers": 0,
            "cell_change_without_pair_change_drivers": 0,
            "transient_return_drivers": 0,
        }
        for caseid, case_headers in sorted(versioned_cases.items()):
            version_rows = []
            memberships = []
            for header in case_headers:
                state, exposed, target_event_present = pair_state(
                    header["primaryid"],
                    components[ingredient],
                    event,
                    drug_rows_by_report,
                    reactions,
                )
                memberships.append((exposed, target_event_present))
                version_rows.append(
                    {
                        "primaryid": header["primaryid"],
                        "caseversion": int(header["caseversion"]),
                        "pair_state": state,
                        "primary_suspect_exposure": exposed,
                        "target_event_present": target_event_present,
                        "source_rows": version_source_refs(
                            header["primaryid"], table_rows_by_report, components[ingredient], event
                        ),
                    }
                )
            exposure_changed = len({state[0] for state in memberships}) > 1
            event_changed = len({state[1] for state in memberships}) > 1
            state_changed = exposure_changed or event_changed
            pair_memberships = [exposed and target_event for exposed, target_event in memberships]
            pair_changed = len(set(pair_memberships)) > 1
            transient_return = any(
                memberships[start] == memberships[end]
                and any(memberships[middle] != memberships[start] for middle in range(start + 1, end))
                for start in range(len(memberships) - 2)
                for end in range(start + 2, len(memberships))
            )
            if not state_changed:
                continue
            census["state_change_drivers"] += 1
            census["primary_exposure_change_drivers"] += int(exposure_changed)
            census["target_event_change_drivers"] += int(event_changed)
            census["pair_membership_change_drivers"] += int(pair_changed)
            census["cell_change_without_pair_change_drivers"] += int(not pair_changed)
            census["transient_return_drivers"] += int(transient_return)

            if (pair["pair_id"], caseid) not in driver_review_scope:
                continue
            changes = set()
            for before_state, after_state in zip(memberships, memberships[1:]):
                if not before_state[0] and after_state[0]:
                    changes.add("PRIMARY_EXPOSURE_ADDED")
                if before_state[0] and not after_state[0]:
                    changes.add("PRIMARY_EXPOSURE_REMOVED")
                if not before_state[1] and after_state[1]:
                    changes.add("TARGET_EVENT_ADDED")
                if before_state[1] and not after_state[1]:
                    changes.add("TARGET_EVENT_REMOVED")
            version_driver_results.append(
                {
                    "driver_id": f"{pair['pair_id']}|{caseid}",
                    "pair_id": pair["pair_id"],
                    "caseid": caseid,
                    "versions": version_rows,
                    "material_changes": sorted(changes),
                }
            )
            completed_driver_reviews.add((pair["pair_id"], caseid))
        version_driver_summaries.append({"pair_id": pair["pair_id"], **census})

    missing_driver_reviews = sorted(driver_review_scope - completed_driver_reviews)
    if missing_driver_reviews:
        raise ValueError(f"version-driver review roster has non-driver rows: {missing_driver_reviews}")

    expected_cases = {
        "R01": ("UNRESOLVED", "POSITIVE", "CASE_LEVEL_POSITIVE", "UNASSESSABLE", ["same_day_order_unresolved", "positive_dechallenge", "case_level_rechallenge_only", "no_documented_reexposure_course", "alternatives_unresolved"]),
        "R02": ("SUPPORTED", "POSITIVE", "UNKNOWN", "POSSIBLE", ["temporal_supported", "positive_dechallenge", "rechallenge_unknown", "co_reported_context", "alternatives_unresolved"]),
        "R03": ("START_AFTER_EVENT", "NEGATIVE", "UNKNOWN", "UNLIKELY", ["start_after_event", "negative_dechallenge", "rechallenge_unknown"]),
        "R04": ("SUPPORTED", "POSITIVE", "UNKNOWN", "POSSIBLE", ["partial_start_interval_precedes_event", "positive_dechallenge", "rechallenge_unknown", "alternatives_unresolved"]),
        "R05": ("SUPPORTED", "UNKNOWN", "UNKNOWN", "POSSIBLE", ["partial_start_interval_precedes_event", "dechallenge_unknown", "rechallenge_unknown", "alternatives_unresolved"]),
        "R06": ("START_AFTER_EVENT", "POSITIVE", "UNKNOWN", "UNLIKELY", ["start_after_event", "positive_dechallenge", "secondary_courses_not_substituted", "alternatives_unresolved"]),
        "R07": ("SUPPORTED", "POSITIVE", "UNKNOWN", "POSSIBLE", ["temporal_supported", "positive_dechallenge", "rechallenge_unknown", "concomitant_present", "alternatives_unresolved"]),
        "R08": ("UNRESOLVED", "NEGATIVE", "UNKNOWN", "UNASSESSABLE", ["event_onset_missing", "negative_dechallenge", "rechallenge_unknown"]),
        "R09": ("SUPPORTED", "UNKNOWN", "UNKNOWN", "POSSIBLE", ["temporal_supported", "dechallenge_unknown", "rechallenge_unknown", "co_reported_context", "alternatives_unresolved"]),
        "R10": ("UNRESOLVED", "POSITIVE", "CASE_LEVEL_POSITIVE", "UNASSESSABLE", ["event_onset_missing", "positive_dechallenge", "case_level_rechallenge_only", "no_documented_reexposure_course", "concomitant_present"]),
        "R11": ("UNRESOLVED", "POSITIVE", "NEGATIVE", "UNASSESSABLE", ["exposure_start_missing", "positive_dechallenge", "negative_rechallenge", "co_reported_context"]),
        "R12": ("SUPPORTED", "POSITIVE", "NEGATIVE", "POSSIBLE", ["temporal_supported", "positive_dechallenge", "negative_rechallenge", "secondary_course_not_substituted", "alternatives_unresolved"]),
    }

    case_results = []
    for review in reviews:
        temporal, dechallenge, rechallenge, category, evidence = expected_cases[review["review_id"]]
        target_components = components[review["suspect_active_ingredient"]]
        target_rows = [
            row
            for row in drug_rows_by_report[review["primaryid"]]
            if row["role_cod"] == "PS" and split_components(row["prod_ai"]) & target_components
        ]
        sequences = {row["drug_seq"] for row in target_rows}
        case_results.append(
            {
                "review_id": review["review_id"],
                "primaryid": review["primaryid"],
                "suspect_active_ingredient": review["suspect_active_ingredient"],
                "event_pt": review["event_pt"],
                "temporal_status": temporal,
                "dechallenge_status": dechallenge,
                "rechallenge_status": rechallenge,
                "causality": category,
                "evidence_codes": evidence,
                "rationale": "The category is limited to what can be established from the retained structured report fields.",
                "source_rows": source_refs(review["primaryid"], tables, sequences, review["event_pt"]),
            }
        )

    longitudinal_judgments = {
        "L01": ("UNASSESSABLE", "POSSIBLE", "PAIR_ADDED", ["target_event_added", "pair_membership_added"]),
        "L02": ("UNASSESSABLE", "UNASSESSABLE", "PAIR_ADDED_STILL_UNASSESSABLE", ["target_event_added", "therapy_added", "event_onset_still_missing"]),
        "L03": ("UNASSESSABLE", "UNASSESSABLE", "PAIR_REMOVED", ["target_event_removed", "pair_membership_removed", "withdrawal_code_removed", "therapy_added_after_target_removed"]),
        "L04": ("UNASSESSABLE", "UNASSESSABLE", "PAIR_ADDED_STILL_UNASSESSABLE", ["target_event_added", "pair_membership_added", "positive_dechallenge_added", "primary_course_start_missing"]),
        "L05": ("UNASSESSABLE", "UNASSESSABLE", "EVIDENCE_ADDED_STILL_UNASSESSABLE", ["event_onset_added", "positive_dechallenge_added", "exposure_start_still_missing"]),
        "L06": ("UNASSESSABLE", "UNASSESSABLE", "EVIDENCE_ADDED_STILL_UNASSESSABLE", ["therapy_course_added", "positive_dechallenge_added", "event_onset_still_missing"]),
        "L07": ("POSSIBLE", "POSSIBLE", "SUPPORTIVE_CODE_SCOPE_LIMITED", ["positive_rechallenge_added", "secondary_suspect_only", "case_level_rechallenge_not_event_specific"]),
        "L08": ("UNASSESSABLE", "UNASSESSABLE", "SUPPORT_WITHDRAWN_STILL_UNASSESSABLE", ["positive_dechallenge_removed", "event_onset_still_missing"]),
        "L09": ("UNASSESSABLE", "POSSIBLE", "BECAME_ASSESSABLE", ["event_onset_added", "positive_dechallenge_added", "supported_chronology", "competing_events_present"]),
        "L10": ("UNASSESSABLE", "UNASSESSABLE", "EVIDENCE_ADDED_STILL_UNASSESSABLE", ["event_onset_added", "positive_dechallenge_added", "same_day_order_unresolved"]),
        "L11": ("UNASSESSABLE", "UNLIKELY", "BECAME_UNLIKELY", ["event_onset_revised_earlier", "primary_course_start_added", "start_after_event", "positive_dechallenge_removed"]),
        "L12": ("UNASSESSABLE", "UNASSESSABLE", "NO_SUSPECT_PAIR", ["target_event_added", "target_product_added_as_concomitant", "no_suspect_exposure"]),
    }

    longitudinal_results = []
    for review in longitudinal_reviews:
        case_headers = sorted(
            headers_by_case[review["caseid"]],
            key=lambda row: (int(row["caseversion"]), row["fda_dt"], int(row["primaryid"])),
        )
        if len(case_headers) < 2:
            raise ValueError(f"Longitudinal review {review['change_id']} has fewer than two versions")
        target_components = components[review["suspect_active_ingredient"]]
        prior_category, retained_category, impact, changes = longitudinal_judgments[review["change_id"]]
        version_rows = []
        for index, header in enumerate(case_headers):
            state, exposed, event = pair_state(
                header["primaryid"],
                target_components,
                review["event_pt"],
                drug_rows_by_report,
                reactions,
            )
            version_rows.append(
                {
                    "primaryid": header["primaryid"],
                    "caseversion": int(header["caseversion"]),
                    "source_quarter": header["source_quarter"],
                    "pair_state": state,
                    "primary_suspect_exposure": exposed,
                    "target_event_present": event,
                    "causality": retained_category if index == len(case_headers) - 1 else prior_category,
                    "source_rows": version_source_refs(
                        header["primaryid"], table_rows_by_report, target_components, review["event_pt"]
                    ),
                }
            )
        longitudinal_results.append(
            {
                "change_id": review["change_id"],
                "caseid": review["caseid"],
                "suspect_active_ingredient": review["suspect_active_ingredient"],
                "event_pt": review["event_pt"],
                "versions": version_rows,
                "material_changes": changes,
                "assessment_impact": impact,
                "rationale": "The later submission changes only the conclusions supported by version-specific structured fields; unsupported scope is not upgraded.",
            }
        )

    result = {
        "universes": {
            "input_report_versions": len(all_headers),
            "canonical_cases": len(canonical),
            "versions_removed": len(all_headers) - len(canonical),
            "canonical_period_counts": {key: len(value) for key, value in period_headers.items()},
            "reporter_group_counts": {key: len(value) for key, value in reporter_headers.items()},
            "cross_stratum_counts": {
                f"{period}|{group}": len(rows) for (period, group), rows in cross_headers.items()
            },
        },
        "pair_assessments": pair_results,
        "version_driver_assessments": {
            "candidate_census": version_driver_summaries,
            "detailed_reviews": version_driver_results,
        },
        "case_assessments": case_results,
        "longitudinal_assessments": longitudinal_results,
        "method": {
            "unit": "latest case with an all-version sensitivity",
            "exposure": "primary-suspect whole active-ingredient component",
            "event": "exact reaction preferred term",
            "interval": "two-sided 95% log-Wald ROR without continuity correction",
            "adjustment": "Mantel-Haenszel common ROR across retained period and reporter group",
            "causality": "structured evidence with partial dates treated as intervals",
        },
        "limitations": [
            "Spontaneous reports do not establish incidence or individual causation.",
            "Reporting selection, duplicate follow-ups, missing clinical detail, and co-medication can distort disproportionality.",
        ],
    }
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {output}")
    print(f"canonical_reports_in_child_tables={all(report_id in canonical_ids for report_id in canonical_ids)}")
    print(f"rejected_versions={sum(len(values) for values in rejected.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

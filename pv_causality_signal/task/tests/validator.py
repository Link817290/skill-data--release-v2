#!/usr/bin/env python3
"""Condition-blind scorer for longitudinal pharmacovigilance adjudication."""
from __future__ import annotations

import json
import hashlib
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
GROUND = json.loads((HERE / "ground_truth.json").read_text(encoding="utf-8"))


def norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").casefold()).strip("_")


def pick(row: dict, names: tuple[str, ...]):
    for name in names:
        if name in row:
            return row[name]
    wanted = {norm(name) for name in names}
    for key, value in row.items():
        if norm(key) in wanted:
            return value
    return None


def section(book: dict, names: tuple[str, ...], expected_type: type):
    value = pick(book, names)
    return value if isinstance(value, expected_type) else expected_type()


def row_list(value: object, identifier_name: str) -> list[dict]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        rows = []
        for identifier, row in value.items():
            if not isinstance(row, dict):
                continue
            copied = dict(row)
            copied.setdefault(identifier_name, identifier)
            rows.append(copied)
        return rows
    return []


def embedded_census_rows(pair_rows: list[dict]) -> list[dict]:
    """Recover a candidate census when it is presented beside each pair result."""
    rows = []
    for pair_row in pair_rows:
        reconciliation = pick(pair_row, (
            "reconciliation_effect", "reconciliation", "version_reconciliation",
        ))
        if not isinstance(reconciliation, dict):
            continue
        census = pick(reconciliation, (
            "census", "driver_census", "version_driver_census", "counts",
        ))
        if not isinstance(census, dict):
            continue
        copied = dict(census)
        copied.setdefault("pair_id", pick(pair_row, ("pair_id", "candidate_id", "id")))
        rows.append(copied)
    return rows


def driver_sections(book: dict, pair_rows: list[dict] | None = None) -> tuple[list[dict], list[dict]]:
    value = pick(book, (
        "version_driver_assessments", "version_drivers", "reconciliation_drivers",
        "driver_register", "version_change_register",
    ))
    if isinstance(value, list):
        summaries = [
            row for row in value
            if isinstance(row, dict) and pick(row, (
                "state_change_drivers", "changed_state_cases", "driver_count",
            )) is not None and pick(row, ("caseid", "case_id", "case_identifier")) is None
        ]
        details = [
            row for row in value
            if isinstance(row, dict) and pick(row, (
                "driver_id", "caseid", "case_id", "case_identifier",
            )) is not None
        ]
        return summaries or embedded_census_rows(pair_rows or []), details
    if not isinstance(value, dict):
        return embedded_census_rows(pair_rows or []), []
    summaries = row_list(pick(value, (
        "candidate_census", "candidate_summaries", "summary", "census",
        "all_candidate_driver_counts",
    )), "pair_id")
    details = row_list(pick(value, (
        "detailed_reviews", "reviews", "details", "register", "selected_histories",
    )), "driver_id")
    return summaries or embedded_census_rows(pair_rows or []), details


def integer(value: object):
    if isinstance(value, bool):
        return int(value)
    try:
        number = float(value)
        return int(number) if math.isfinite(number) and number.is_integer() else None
    except (TypeError, ValueError):
        return None


def number(value: object):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def boolean(value: object):
    if isinstance(value, bool):
        return value
    text = norm(value)
    if text in {"true", "yes", "y", "1", "present"}:
        return True
    if text in {"false", "no", "n", "0", "absent"}:
        return False
    return None


def close(value: object, expected: float) -> bool:
    got = number(value)
    return got is not None and math.isclose(got, expected, rel_tol=0.005, abs_tol=0.01)


def nonestimable(value: object) -> bool:
    return value is None or norm(value) in {
        "", "na", "n_a", "none", "null", "unassessable", "not_estimable", "undefined"
    }


def label(value: object, aliases: dict[str, set[str]]):
    text = norm(value)
    for target, values in aliases.items():
        if text == norm(target) or text in {norm(item) for item in values}:
            return target
    return None


SIGNAL_ALIASES = {
    "YES": {"signal", "positive", "detected", "meets criteria", "signal detected", "positive signal", "meets signal criteria"},
    "NO": {"no signal", "negative", "not detected", "does not meet criteria", "no safety signal", "signal absent", "does not meet signal criteria"},
    "UNASSESSABLE": {"indeterminate", "not estimable", "undefined", "na"},
}
CAUSALITY_ALIASES = {
    "CERTAIN": {"definite"},
    "PROBABLE": {"likely", "probable likely"},
    "POSSIBLE": {"plausible"},
    "UNLIKELY": {"doubtful", "improbable"},
    "UNASSESSABLE": {
        "unclassifiable", "unassessable unclassifiable", "indeterminate", "insufficient",
        "absent", "absent pair", "not applicable",
    },
}
TEMPORAL_ALIASES = {
    "SUPPORTED": {"compatible", "reasonable", "start before event", "exposure preceded event"},
    "START_AFTER_EVENT": {"event before exposure", "post event start", "incompatible"},
    "UNRESOLVED": {"unknown", "indeterminate", "overlap", "missing"},
}
DECHALLENGE_ALIASES = {
    "POSITIVE": {"supportive", "yes", "improved after withdrawal"},
    "NEGATIVE": {"no", "did not improve after withdrawal"},
    "UNKNOWN": {"unreported", "missing", "not applicable", "indeterminate", "unknown blank", "unknown withdrawal"},
    "CONFLICTING": {"conflict", "mixed", "inconsistent"},
}
RECHALLENGE_ALIASES = {
    "CASE_LEVEL_POSITIVE": {"positive", "case level recurrence", "positive case level", "unverified positive", "unverified recurrence"},
    "NEGATIVE": {"no", "negative rechallenge"},
    "UNKNOWN": {"unreported", "missing", "not applicable", "indeterminate", "unknown blank", "unknown reexposure"},
    "CONFLICTING": {"conflict", "mixed", "inconsistent"},
}
PAIR_STATE_ALIASES = {
    "PAIR": {"present", "drug and event", "exposed event", "both"},
    "EXPOSURE_ONLY": {"drug only", "exposed no event", "product only"},
    "EVENT_ONLY": {"event no exposure", "reaction only", "no primary suspect exposure"},
    "NEITHER": {"absent", "no drug no event"},
}
VERSION_EFFECT_ALIASES = {
    "GAINED": {"signal gained", "gain", "appeared after reconciliation", "no signal to signal"},
    "LOST": {"signal lost", "loss", "removed after reconciliation", "signal to no signal"},
    "STABLE_YES": {"remained signal", "yes to yes", "signal to signal", "stable positive"},
    "STABLE_NO": {"remained no signal", "not signal in either", "no signal to no signal", "stable negative"},
}
DISPOSITION_ALIASES = {
    "ESCALATE": {"escalation", "priority review", "escalate for review", "requires escalation"},
    "MONITOR": {"monitoring", "continue monitoring", "ongoing monitoring", "retain on watch list"},
    "CLOSE": {"closed", "no further signal action", "close review", "no action beyond routine surveillance"},
}
IMPACT_ALIASES = {
    "PAIR_ADDED": {"pair gained", "target added", "became a pair"},
    "PAIR_ADDED_STILL_UNASSESSABLE": {"pair added but still unassessable", "target added insufficient"},
    "PAIR_REMOVED": {"pair lost", "target removed", "no longer a pair"},
    "EVIDENCE_ADDED_STILL_UNASSESSABLE": {"evidence added but still unassessable", "new evidence insufficient"},
    "SUPPORTIVE_CODE_SCOPE_LIMITED": {"supportive code not event specific", "positive code scope limited"},
    "SUPPORT_WITHDRAWN_STILL_UNASSESSABLE": {"support removed but still unassessable", "dechallenge withdrawn"},
    "BECAME_ASSESSABLE": {"assessability gained", "became possible", "now assessable"},
    "BECAME_UNLIKELY": {"now unlikely", "chronology became incompatible"},
    "NO_SUSPECT_PAIR": {"not a suspect pair", "concomitant only", "no suspect exposure"},
}


def all_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from all_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_dicts(child)


def table_value(row: dict, names: tuple[str, ...]):
    value = pick(row, names)
    if value is not None:
        return value
    for container_name in ("cells", "counts", "case_counts", "contingency_table", "table", "two_by_two"):
        container = pick(row, (container_name,))
        if isinstance(container, dict):
            value = pick(container, names)
            if value is not None:
                return value
    return None


COUNT_ALIASES = {
    "a": ("a", "both", "exposed_event", "drug_and_event", "a_exposed_with_event"),
    "b": ("b", "exposed_only", "drug_no_event", "b_exposed_without_event"),
    "c": ("c", "event_only", "event_no_drug", "c_unexposed_with_event"),
    "d": ("d", "neither", "no_drug_no_event", "d_unexposed_without_event"),
}


def looks_like_table(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    return sum(table_value(value, names) is not None for names in COUNT_ALIASES.values()) >= 3


def labeled_table(row: dict, direct_names: tuple[str, ...], labels: tuple[str, ...]):
    direct = pick(row, direct_names)
    if looks_like_table(direct):
        return direct
    for container in all_dicts(row):
        direct = pick(container, direct_names)
        if looks_like_table(direct):
            return direct
    wanted = {norm(item) for item in labels + direct_names}
    for candidate in all_dicts(row):
        if not looks_like_table(candidate):
            continue
        descriptor = "_".join(
            norm(pick(candidate, (name,)))
            for name in ("scope", "universe", "analysis_scope", "population", "name", "label", "period", "source_quarter")
            if pick(candidate, (name,)) is not None
        )
        if any(item and item in descriptor for item in wanted):
            return candidate
    return {}


def period_table(row: dict, period: str):
    for container in all_dicts(row):
        periods = pick(container, (
            "periods", "period_results", "source_periods", "quarter_results",
            "canonical_periods", "retained_source_period_populations",
        ))
        if isinstance(periods, dict):
            direct = pick(periods, (period, period.lower(), period.replace("Q", "_q")))
            if looks_like_table(direct):
                return direct
        if isinstance(periods, list):
            for candidate in periods:
                if not looks_like_table(candidate):
                    continue
                descriptor = norm(pick(candidate, ("period", "source_quarter", "universe", "scope")))
                if norm(period) in descriptor:
                    return candidate
    return labeled_table(row, (), (period, period.lower(), period.replace("Q", " quarter ")))


def stratum_table(row: dict, period: str, group: str):
    containers = []
    stratified = pick(row, ("stratified", "adjusted", "stratification"))
    if isinstance(stratified, dict):
        containers.append(stratified)
        strata = pick(stratified, ("strata", "stratum_tables", "groups"))
        if isinstance(strata, (list, dict)):
            containers.append(strata)
    containers.append(row)
    for container in containers:
        for candidate in all_dicts(container):
            if not looks_like_table(candidate):
                continue
            quarter = norm(pick(candidate, ("source_quarter", "period", "quarter", "time_period")))
            reporter = norm(pick(candidate, ("reporter_group", "reporter", "group", "channel")))
            if norm(period) == quarter and norm(group) == reporter:
                return candidate
            descriptor = norm(pick(candidate, ("universe", "scope", "analysis_scope", "name", "label")))
            group_terms = {
                "HCP": ("hcp", "healthcare_professional"),
                "CONSUMER": ("consumer",),
                "OTHER": ("other", "other_or_missing"),
            }[group]
            if norm(period) in descriptor and any(term in descriptor for term in group_terms):
                return candidate
    return {}


def table_score(row: dict, expected: dict) -> tuple[float, dict]:
    count_checks = {
        cell: integer(table_value(row, aliases)) == int(expected[cell])
        for cell, aliases in COUNT_ALIASES.items()
    }
    expected_ror = expected.get("ror")
    expected_low = expected.get("ror025")
    got_ror = pick(row, ("ror", "reporting_odds_ratio", "odds_ratio", "estimate"))
    got_low = pick(row, (
        "ror025", "lower_95", "lower_95_bound", "ci95_lower", "ror_lower_95", "ror025_lower_95ci", "lower_95_ci",
        "lower_95_confidence_limit", "ci_lower", "lower_limit",
    ))
    ror_ok = nonestimable(got_ror) if expected_ror is None else close(got_ror, float(expected_ror))
    low_ok = nonestimable(got_low) if expected_low is None else close(got_low, float(expected_low))
    got_signal = label(
        pick(row, ("signal", "quantitative_signal", "signal_call", "meets_policy", "call")),
        SIGNAL_ALIASES,
    )
    signal_ok = got_signal == expected["signal"]
    score_value = 0.55 * (sum(count_checks.values()) / 4) + 0.125 * ror_ok + 0.125 * low_ok + 0.20 * signal_ok
    values = [integer(table_value(row, aliases)) for aliases in COUNT_ALIASES.values()]
    closed = all(value is not None and value >= 0 for value in values) and sum(values) == sum(
        int(expected[cell]) for cell in COUNT_ALIASES
    )
    return score_value, {
        "counts_correct": sum(count_checks.values()),
        "ror_correct": ror_ok,
        "lower_correct": low_ok,
        "signal_correct": signal_ok,
        "closed": closed,
    }


def index_rows(rows: list, key_fn):
    indexed = {}
    duplicates = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = key_fn(row)
        if not key:
            continue
        if key in indexed:
            duplicates.add(key)
        else:
            indexed[key] = row
    return indexed, duplicates


def pair_key(row: dict, expected_composites: dict[tuple[str, str], str]):
    direct = norm(pick(row, ("pair_id", "id", "candidate_id", "pair"))).upper()
    if direct in {item["pair_id"] for item in GROUND["pair_assessments"]}:
        return direct
    drug = norm(pick(row, ("active_ingredient", "ingredient", "drug", "product")))
    event = norm(pick(row, ("meddra_pt", "event", "preferred_term", "reaction")))
    return expected_composites.get((drug, event))


def embedded_label(value, prefix: str) -> str | None:
    """Extract the conventional label from a composite identifier.

    "R01: 232616901 | DRUG | PT" -> "R01". A record may carry the label alone, the
    label followed by a human-readable description, or a composite built from the
    report identifier. The task does not prescribe an identifier format, so a record
    is matched on the label it carries rather than on exact string equality.
    """
    if value is None:
        return None
    match = re.search(rf"\b({prefix}\d{{1,3}})\b", str(value).upper())
    return match.group(1) if match else None


def case_key(row: dict, expected_primaryids: dict[str, str]):
    raw = pick(row, ("review_id", "id", "assessment_id", "case_review_id"))
    known = {item["review_id"] for item in GROUND["case_assessments"]}
    direct = norm(raw).upper()
    if direct in known:
        return direct
    embedded = embedded_label(raw, "R")
    if embedded in known:
        return embedded
    primaryid = str(pick(row, ("primaryid", "report_id", "report_identifier")) or "").strip()
    if primaryid in expected_primaryids:
        return expected_primaryids[primaryid]
    # The report identifier may itself be embedded in a composite string; retry on its leading digits.
    leading = re.match(r"\s*(\d{6,})", str(raw or ""))
    return expected_primaryids.get(leading.group(1)) if leading else None


def longitudinal_key(row: dict, expected_caseids: dict[str, str]):
    raw = pick(row, ("change_id", "review_id", "id", "longitudinal_id"))
    known = {item["change_id"] for item in GROUND["longitudinal_assessments"]}
    direct = norm(raw).upper()
    if direct in known:
        return direct
    embedded = embedded_label(raw, "L")
    if embedded in known:
        return embedded
    caseid = str(pick(row, ("caseid", "case_id", "case_identifier")) or "").strip()
    if caseid in expected_caseids:
        return expected_caseids[caseid]
    leading = re.match(r"\s*(\d{6,})", str(raw or ""))
    return expected_caseids.get(leading.group(1)) if leading else None


def driver_key(row: dict, expected_composites: dict[tuple[str, str], str]):
    direct = str(pick(row, ("driver_id", "id", "version_driver_id")) or "").strip().upper()
    if direct in set(expected_composites.values()):
        return direct
    pair_id = norm(pick(row, ("pair_id", "candidate_id", "pair"))).upper()
    caseid = str(pick(row, ("caseid", "case_id", "case_identifier")) or "").strip()
    return expected_composites.get((pair_id, caseid))


def evidence_text(row: dict) -> str:
    values = []
    for name in (
        "evidence_codes", "analytic_evidence", "evidence_dimensions",
        "structured_evidence", "material_changes", "changes", "field_delta", "field_deltas",
        "later_submission_effect", "effect_of_later_submission", "rationale", "reason",
        "category_limiter", "evidence_limiting_final_category",
        "chronology", "withdrawal", "rechallenge", "alternatives", "summary",
        "assessability_consequence", "pair_membership_change",
    ):
        value = pick(row, (name,))
        if value is not None:
            values.append(value)
    flattened = []
    for value in all_scalars(values):
        flattened.append(norm(value))
    return " ".join(flattened)


def semantic_concept_scores(case_rows: dict, driver_rows: dict, long_rows: dict, expected_cases: dict, expected_drivers: dict, expected_long: dict) -> dict[str, float]:
    """Ask the shared judge about wording-only evidence claims.

    Structural and numerical checks stay deterministic.  Each semantic item is
    scoped to one case or longitudinal review so a phrase from another review
    cannot satisfy it.  Empty artifacts are handled locally as zero evidence and
    do not require a provider call.
    """
    criteria: dict[str, str] = {}
    lines: list[str] = []
    for key, expected in expected_cases.items():
        row = case_rows.get(key, {})
        text = evidence_text(row)
        lines.append(f"CASE {key}: {text}")
        for concept in expected["evidence_codes"]:
            ident = f"case:{key}:{concept}"
            aliases = ", ".join(CONCEPT_ALIASES.get(concept, ()))
            criteria[ident] = (
                f"Within case {key}, the candidate supports the evidence concept "
                f"'{concept.replace('_', ' ')}'. Equivalent professional wording is allowed. "
                f"Possible semantic aliases are {aliases or 'none'}, but an explicit negation, "
                "different object, or unrelated co-occurrence is not support."
            )
    for key, expected in expected_drivers.items():
        row = driver_rows.get(key, {})
        text = evidence_text(row)
        lines.append(f"DRIVER {key}: {text}")
        for concept in expected["material_changes"]:
            ident = f"driver:{key}:{concept}"
            aliases = ", ".join(DRIVER_CHANGE_ALIASES.get(concept, ()))
            criteria[ident] = (
                f"Within version-driver review {key}, the candidate identifies the material "
                f"change '{concept.replace('_', ' ')}'. Accept an equivalent change description, "
                f"but reject a negated, reversed, or different-scope change. Possible aliases are {aliases or 'none'}."
            )
    for key, expected in expected_long.items():
        row = long_rows.get(key, {})
        text = evidence_text(row)
        lines.append(f"LONG {key}: {text}")
        for concept in expected["material_changes"]:
            ident = f"long:{key}:{concept}"
            aliases = ", ".join(DRIVER_CHANGE_ALIASES.get(concept, ()))
            criteria[ident] = (
                f"Within longitudinal review {key}, the candidate identifies the material "
                f"version change '{concept.replace('_', ' ')}'. Accept an equivalent change "
                f"description, but reject a negated, reversed, or different-scope change. "
                f"Possible aliases are {aliases or 'none'}."
            )
    if not any(line.split(": ", 1)[-1].strip() for line in lines):
        return {}
    from semantic_judge import adjudicate
    source = json.dumps({"criteria": criteria, "expected_case_keys": list(expected_cases), "expected_longitudinal_keys": list(expected_long)}, ensure_ascii=False)
    verdict = adjudicate("\n".join(lines), source, criteria)
    return {ident: float(item["fraction"]) for ident, item in verdict["items"].items()}


def all_scalars(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from all_scalars(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_scalars(child)
    elif value is not None:
        yield value


def deep_pick(row: dict, names: tuple[str, ...]):
    for candidate in all_dicts(row):
        value = pick(candidate, names)
        if value is not None:
            return value
    return None


def population_size(row: dict, names: tuple[str, ...]):
    value = deep_pick(row, names)
    direct = integer(value)
    if direct is not None:
        return direct
    if isinstance(value, dict):
        return integer(pick(value, ("n", "count", "size", "population_size")))
    return None


def listed_population_size(value: object, period: str | None = None, group: str | None = None):
    if not isinstance(value, list):
        return None
    matches = []
    for item in value:
        if not isinstance(item, dict):
            continue
        item_period = norm(pick(item, ("period", "source_quarter", "quarter")))
        item_group = norm(pick(item, ("reporter_group", "reporter", "group")))
        if period is not None and item_period != norm(period):
            continue
        if group is not None and item_group != norm(group):
            continue
        count = integer(pick(item, ("n", "count", "size", "population_size")))
        if count is not None:
            matches.append(count)
    return sum(matches) if matches else None


CONCEPT_ALIASES = {
    "same_day_order_unresolved": ("same_day", "same date", "order unresolved"),
    "positive_dechallenge": ("positive_dechallenge", "improved after withdrawal", "dechallenge y", "supportive withdrawal"),
    "case_level_rechallenge_only": ("case_level_rechallenge", "not event specific", "recurrence scope", "unverified recurrence"),
    "no_documented_reexposure_course": ("no_reexposure_course", "no restart course", "unverified rechallenge", "unverified recurrence"),
    "alternatives_unresolved": ("alternatives_unresolved", "alternatives not excluded", "confounding not assessed"),
    "temporal_supported": ("temporal_supported", "supported chronology", "start before event"),
    "rechallenge_unknown": ("rechallenge_unknown", "rechallenge unreported", "no rechallenge"),
    "co_reported_context": ("co_reported", "competing context", "other events"),
    "start_after_event": ("start_after_event", "event before exposure", "incompatible chronology"),
    "negative_dechallenge": ("negative_dechallenge", "dechallenge n", "did not improve"),
    "partial_start_interval_precedes_event": ("partial_start", "interval precedes", "month precision"),
    "dechallenge_unknown": ("dechallenge_unknown", "dechallenge unreported", "withdrawal unknown"),
    "secondary_courses_not_substituted": ("secondary course", "not substituted", "primary course"),
    "concomitant_present": ("concomitant", "co medication", "other drug"),
    "event_onset_missing": ("event_onset_missing", "event date missing", "onset unknown"),
    "exposure_start_missing": ("exposure_start_missing", "start date missing", "drug start unknown"),
    "negative_rechallenge": ("negative_rechallenge", "rechallenge n"),
    "secondary_course_not_substituted": ("secondary course", "not substituted", "primary course"),
    "target_event_added": ("target_event_added", "event added"),
    "pair_membership_added": ("pair_membership_added", "pair added", "became a pair", "absent to present", "creates the pair"),
    "therapy_added": ("therapy_added", "course added", "start added"),
    "event_onset_still_missing": ("onset_still_missing", "event date remains missing"),
    "target_event_removed": ("target_event_removed", "event removed"),
    "pair_membership_removed": ("pair_membership_removed", "pair removed", "no longer a pair"),
    "withdrawal_code_removed": ("withdrawal_code_removed", "dechallenge removed"),
    "therapy_added_after_target_removed": ("therapy added after target removed", "course added but event removed"),
    "positive_dechallenge_added": ("positive_dechallenge_added", "dechallenge added", "withdrawal response added"),
    "primary_course_start_missing": ("primary_course_start_missing", "primary start missing"),
    "event_onset_added": ("event_onset_added", "event date added", "onset added"),
    "exposure_start_still_missing": ("exposure_start_still_missing", "drug start remains missing"),
    "therapy_course_added": ("therapy_course_added", "therapy added", "course added"),
    "positive_rechallenge_added": ("positive_rechallenge_added", "rechallenge added", "re exposure positive added"),
    "secondary_suspect_only": ("secondary_suspect_only", "secondary suspect", "not primary suspect"),
    "case_level_rechallenge_not_event_specific": ("case level rechallenge", "not event specific", "recurrence scope"),
    "positive_dechallenge_removed": ("positive_dechallenge_removed", "dechallenge removed", "support withdrawn"),
    "supported_chronology": ("supported_chronology", "temporal supported", "start before event"),
    "competing_events_present": ("competing_events", "other events present", "alternative context"),
    "event_onset_revised_earlier": ("onset_revised_earlier", "event date changed earlier"),
    "primary_course_start_added": ("primary_course_start_added", "primary start added"),
    "target_product_added_as_concomitant": ("product added as concomitant", "concomitant only"),
    "no_suspect_exposure": ("no_suspect_exposure", "no suspect drug", "concomitant only"),
}

DRIVER_CHANGE_ALIASES = {
    "PRIMARY_EXPOSURE_ADDED": ("primary exposure added", "ps exposure added", "suspect exposure added", "exposure absent to present"),
    "PRIMARY_EXPOSURE_REMOVED": ("primary exposure removed", "ps exposure removed", "suspect exposure removed", "exposure present to absent"),
    "TARGET_EVENT_ADDED": ("target event added", "reaction added", "event absent to present"),
    "TARGET_EVENT_REMOVED": ("target event removed", "reaction removed", "event present to absent"),
}

CENSUS_ALIASES = {
    "multi_submission_cases_examined": (
        "multi_submission_cases_examined", "versioned_cases_examined",
        "multi_version_cases_examined", "multi_submission_case_count", "multi_submission_cases",
        "versioned_case_count", "cases_with_multiple_submissions", "multi_version_case_count",
    ),
    "state_change_drivers": (
        "state_change_drivers", "changed_state_cases", "driver_count",
        "any_exposure_or_event_change", "primary_suspect_or_target_event_changes",
    ),
    "primary_exposure_change_drivers": (
        "primary_exposure_change_drivers", "exposure_change_cases",
        "ps_exposure_change_drivers", "primary_suspect_exposure_changes",
    ),
    "target_event_change_drivers": (
        "target_event_change_drivers", "event_change_cases",
        "target_reaction_change_drivers",
    ),
    "pair_membership_change_drivers": (
        "pair_membership_change_drivers", "pair_change_cases",
        "pair_membership_changes",
    ),
    "cell_change_without_pair_change_drivers": (
        "cell_change_without_pair_change_drivers", "cell_only_change_cases",
        "state_change_without_pair_change", "comparator_cell_change_cases",
        "table_cell_changes_without_pair_membership_change",
    ),
    "transient_return_drivers": (
        "transient_return_drivers", "return_to_earlier_state_cases",
        "reversion_cases", "transient_state_cases",
        "returns_to_earlier_state_after_intervening_change",
    ),
}


def concept_hit(concept: str, text: str) -> bool:
    """Match an evidence concept while respecting local negation.

    Evidence is stored in a normalized token stream.  A positive concept must
    not be credited when the same words occur in a nearby ``no/not/without``
    clause (for example ``no_positive_dechallenge``).  Concepts whose own
    phrase is explicitly negative, such as ``no_reexposure_course``, remain
    matchable because that negation is part of the expected concept.
    """
    phrases = (concept.replace("_", " "), concept) + CONCEPT_ALIASES.get(concept, ())
    compact = text.replace("_", " ")
    for phrase in phrases:
        needle = norm(phrase)
        if needle not in text and str(phrase).casefold() not in compact:
            continue
        # Do not let a positive phrase hidden under a local negator become a
        # false positive.  The expected concept itself may contain a negator;
        # in that case the negation is the evidence and must be retained.
        phrase_is_explicitly_negative = needle.startswith((
            "no_", "not_", "without_", "unknown_", "unreported_", "negative_",
        ))
        for match in re.finditer(re.escape(needle), text, re.I):
            if phrase_is_explicitly_negative:
                return True
            prefix = text[max(0, match.start() - 72):match.start()]
            if re.search(
                r"(?:^|_)(?:no|not|without|never|neither|nor|lack|lacks|lacking|"
                r"absent|unreported|false|incorrect|wrong|否认|并非|不是|不存在)"
                r"(?:_[a-z0-9]+){0,5}_$",
                prefix,
                re.I,
            ):
                continue
            return True
    return False


def case_identity_matches(row: dict, expected: dict) -> bool:
    """Validate optional identity fields when a row supplies them.

    Review labels are useful aliases, but they cannot make an explicitly
    mismatched report id, suspect ingredient, or event appear to be the
    expected source case.
    """
    primaryid = pick(row, ("primaryid", "report_id", "report_identifier"))
    if primaryid is not None:
        submitted_id = re.sub(r"\.0+$", "", str(primaryid).strip())
        if submitted_id != str(expected["primaryid"]):
            return False
    ingredient = pick(row, ("suspect_active_ingredient", "active_ingredient", "drug_name", "drug"))
    if ingredient is not None:
        if isinstance(ingredient, dict):
            ingredient = pick(ingredient, ("name", "value", "ingredient", "active_ingredient"))
        if ingredient is not None and norm(ingredient) != norm(expected["suspect_active_ingredient"]):
            return False
    event = pick(row, ("event_pt", "event", "reaction", "meddra_pt", "target_event"))
    if event is not None:
        if isinstance(event, dict):
            event = pick(event, ("name", "value", "pt", "event_pt", "meddra_pt"))
        if event is not None and norm(event) != norm(expected["event_pt"]):
            return False
    return True


def driver_change_hit(change: str, text: str) -> bool:
    phrases = (change, change.replace("_", " ")) + DRIVER_CHANGE_ALIASES.get(change, ())
    compact = text.replace("_", " ")
    return any(norm(phrase) in text or str(phrase).casefold() in compact for phrase in phrases)


def nested_label(row: dict, names: tuple[str, ...], aliases: dict[str, set[str]]):
    for candidate in all_dicts(row):
        value = pick(candidate, names)
        if isinstance(value, (dict, list)) or value is None:
            continue
        result = label(value, aliases)
        if result is not None:
            return result
    return None


STATUS_TEXT = {
    "SUPPORTED": ("exposure_definitely_precedes_event", "supported chronology", "start before event"),
    "START_AFTER_EVENT": ("start_after_event", "event before exposure", "exposure starts after event"),
    "UNRESOLVED": ("unresolved", "same day", "interval overlap", "onset missing", "start date missing"),
    "POSITIVE": ("supportive withdrawal", "positive dechallenge", "improved after withdrawal"),
    "NEGATIVE": ("negative dechallenge", "did not improve after withdrawal"),
    "CASE_LEVEL_POSITIVE": ("case level recurrence", "unverified recurrence", "positive reexposure"),
    "UNKNOWN": ("unknown", "unreported", "missing", "no rechallenge", "no dechallenge"),
    "CONFLICTING": ("conflicting", "mixed", "inconsistent"),
}


def status_matches(row: dict, names: tuple[str, ...], aliases: dict[str, set[str]], expected: str) -> bool:
    direct = nested_label(row, names, aliases)
    if direct is not None:
        return direct == expected
    text = evidence_text(row).replace("_", " ")
    return any(norm(phrase).replace("_", " ") in text for phrase in STATUS_TEXT.get(expected, ()))


def version_exposure(row: dict):
    direct = boolean(pick(row, (
        "primary_suspect_exposure", "ps_exposure", "primary_exposure", "exposure_member",
    )))
    if direct is not None:
        return direct
    roles = pick(row, ("target_product_roles", "target_suspect_roles", "product_roles"))
    if roles is not None:
        return "ps" in {norm(value) for value in all_scalars(roles)}
    product_rows = pick(row, ("target_product_rows", "target_suspect_rows", "drug_rows"))
    if isinstance(product_rows, list):
        return any(norm(pick(item, ("role_cod", "role", "drug_role"))) == "ps" for item in product_rows if isinstance(item, dict))
    return None


def version_event(row: dict):
    direct = boolean(pick(row, (
        "target_event_present", "event_present", "reaction_present", "event_member",
    )))
    if direct is not None:
        return direct
    event_rows = pick(row, ("target_event_rows", "target_reaction_rows", "reaction_rows"))
    if isinstance(event_rows, list):
        return bool(event_rows)
    return None


def version_state(row: dict):
    direct = nested_label(row, ("pair_state", "membership", "drug_event_state", "state"), PAIR_STATE_ALIASES)
    if direct is not None:
        return direct
    pair = boolean(pick(row, (
        "forms_requested_suspect_pair", "pair_membership_ps_or_ss_product_and_event",
        "target_pair_present", "pair_present", "pair_member",
    )))
    exposure = version_exposure(row)
    event = version_event(row)
    if pair is True:
        return "PAIR"
    if exposure is True and event is False:
        return "EXPOSURE_ONLY"
    if exposure is False and event is True:
        return "EVENT_ONLY"
    if exposure is False and event is False:
        return "NEITHER"
    return None


def impact_matches(row: dict, expected: str) -> bool:
    direct = nested_label(
        row,
        (
            "assessment_impact", "impact", "revision_effect", "conclusion_change",
            "assessability_consequence",
        ),
        IMPACT_ALIASES,
    )
    if direct is not None:
        return direct == expected
    text = evidence_text(row).replace("_", " ")
    requirements = {
        "PAIR_ADDED": (("absent to present", "pair added", "creates the pair"), ()),
        "PAIR_ADDED_STILL_UNASSESSABLE": (("pair added", "absent to present"), ("still unassessable", "remains unassessable", "insufficient")),
        "PAIR_REMOVED": (("present to absent", "pair removed", "event removed", "no longer a pair"), ()),
        "EVIDENCE_ADDED_STILL_UNASSESSABLE": (("evidence added", "date added", "course added", "onset added"), ("still unassessable", "remains unassessable", "insufficient")),
        "SUPPORTIVE_CODE_SCOPE_LIMITED": (("supportive", "positive"), ("scope limited", "not event specific", "case level")),
        "SUPPORT_WITHDRAWN_STILL_UNASSESSABLE": (("support removed", "dechallenge removed", "withdrawal removed"), ("still unassessable", "remains unassessable", "insufficient")),
        "BECAME_ASSESSABLE": (("became assessable", "assessability gained", "unassessable to possible", "now possible"), ()),
        "BECAME_UNLIKELY": (("became unlikely", "now unlikely", "event before exposure", "incompatible chronology"), ()),
        "NO_SUSPECT_PAIR": (("no suspect pair", "concomitant only", "no suspect exposure", "not a suspect pair"), ()),
    }
    any_group, required_group = requirements[expected]
    return any(phrase in text for phrase in any_group) and (
        not required_group or any(phrase in text for phrase in required_group)
    )


def source_payload(row: dict) -> str:
    value = pick(row, (
        "source_rows", "source_refs", "sources", "source", "source_row_references",
        "source_packet_refs", "citations",
    ))
    return " ".join(str(item) for item in all_scalars(value))


def source_resolution(row: dict, expected_refs: dict, identifier: str) -> float:
    aliases = ("source_rows","source_refs","sources","source","source_row_references","source_packet_refs","citations","evidence_refs")
    values = []
    for node in all_dicts(row):
        value = pick(node, aliases)
        if value is not None: values.append(value)
        # Also support per-evidence typed citations without a wrapper.
        if pick(node,("table","file","filename","source_table")) is not None: values.append(node)
    if not values: return 0.0
    text = " ".join(str(item) for item in all_scalars(values)).casefold()
    required = [name for name in ("demo","drug","reac","ther") if name in expected_refs]
    if not required: return float(identifier in text)
    checks=[]
    for name in required:
        locators=[str(v).casefold().rsplit("/",1)[-1] for v in expected_refs[name]]
        # Exact table:row locators are safe regardless of the JSON nesting.
        explicit=any(re.search(r"(?<![a-z0-9])"+re.escape(loc)+r"(?![0-9])",text) for loc in locators)
        scoped=[]
        for value in values:
            for node in all_dicts(value):
                direct=pick(node,(name,name+"_rows",name+"_refs"))
                if direct is not None:scoped.extend(str(v).casefold() for v in all_scalars(direct))
                table=norm(pick(node,("table","file","filename","source_table")))
                if table in (name,name+"_csv"):
                    scoped.extend(str(v).casefold() for v in all_scalars(node))
        scoped_text=" ".join(scoped)
        rownums=[loc.rsplit(":",1)[-1] for loc in locators]
        bound=bool(scoped_text) and (identifier in scoped_text or any(re.search(r"(?<![0-9])"+re.escape(n)+r"(?![0-9])",scoped_text) for n in rownums))
        checks.append(explicit or bound)
    return sum(checks)/len(checks)


def version_source_context(version, parent, identifier):
    """Inherit only parent evidence explicitly bound to this submitted version."""
    out=dict(version)
    refs=[]
    for node in all_dicts(parent):
        if str(pick(node,("primaryid","primary_id","report_id","version_id")))==identifier:
            value=pick(node,("source_rows","source_refs","sources","citations","evidence_refs"))
            if value is not None:refs.append(value)
        if identifier in node and isinstance(node[identifier],(dict,list)):refs.append(node[identifier])
    if refs:out["version_bound_evidence"]={"source_refs":refs}
    return out


def nested_number(mapping: dict, path: tuple[str, ...]):
    current: object = mapping
    for part in path:
        if not isinstance(current, dict):
            return None
        current = pick(current, (part,))
    return integer(current)


def source_integrity() -> bool:
    expected = GROUND.get("source_sha256", {})
    if not expected:
        return False
    configured = os.environ.get("PV_SOURCE_ROOT")
    candidates = [Path(configured)] if configured else []
    candidates.extend([Path("/workspace"), HERE.parent / "environment" / "workspace"])
    root = next((path for path in candidates if (path / "faers/demo.csv").is_file()), None)
    if root is None:
        return False
    for relative, digest in expected.items():
        path = root / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            return False
    return True


def score(book: dict) -> dict:
    if not isinstance(book, dict):
        book = {}
    expected_pairs = {row["pair_id"]: row for row in GROUND["pair_assessments"]}
    expected_driver_section = GROUND["version_driver_assessments"]
    expected_census = {
        row["pair_id"]: row for row in expected_driver_section["candidate_census"]
    }
    expected_drivers = {
        row["driver_id"]: row for row in expected_driver_section["detailed_reviews"]
    }
    expected_cases = {row["review_id"]: row for row in GROUND["case_assessments"]}
    expected_long = {row["change_id"]: row for row in GROUND["longitudinal_assessments"]}
    pair_composites = {
        (norm(row["active_ingredient"]), norm(row["meddra_pt"])): row["pair_id"]
        for row in expected_pairs.values()
    }
    case_primaryids = {str(row["primaryid"]): row["review_id"] for row in expected_cases.values()}
    long_caseids = {str(row["caseid"]): row["change_id"] for row in expected_long.values()}
    driver_composites = {
        (row["pair_id"], str(row["caseid"])): row["driver_id"]
        for row in expected_drivers.values()
    }

    universe = section(book, ("universes", "universe", "population", "reconciliation"), dict)
    pair_rows = row_list(pick(book, ("pair_assessments", "pairs", "pair_results", "signal_results")), "pair_id")
    census_rows, driver_rows = driver_sections(book, pair_rows)
    case_rows = row_list(pick(book, ("case_assessments", "cases", "case_reviews", "causality_assessments")), "review_id")
    long_rows = row_list(pick(book, ("longitudinal_assessments", "longitudinal_reviews", "version_reviews", "follow_up_reviews")), "change_id")
    pairs, duplicate_pairs = index_rows(pair_rows, lambda row: pair_key(row, pair_composites))
    census, duplicate_census = index_rows(
        census_rows,
        lambda row: norm(pick(row, ("pair_id", "candidate_id", "pair", "id"))).upper()
        if norm(pick(row, ("pair_id", "candidate_id", "pair", "id"))).upper() in expected_census
        else None,
    )
    drivers, duplicate_drivers = index_rows(driver_rows, lambda row: driver_key(row, driver_composites))
    cases, duplicate_cases = index_rows(case_rows, lambda row: case_key(row, case_primaryids))
    longitudinal, duplicate_long = index_rows(long_rows, lambda row: longitudinal_key(row, long_caseids))
    semantic_scores = semantic_concept_scores(cases, drivers, longitudinal, expected_cases, expected_drivers, expected_long)

    expected_universe = GROUND["universes"]
    universe_aliases = {
        "input_report_versions": (
            "input_report_versions", "report_versions", "submission_count", "all_submissions",
            "header_report_version_rows", "all_submitted_versions",
        ),
        "canonical_cases": (
            "canonical_cases", "retained_cases", "unique_cases", "case_count",
            "canonical_latest_cases",
        ),
        "versions_removed": (
            "versions_removed", "rejected_versions", "followups_removed", "removed_submissions",
            "rejected_follow_up_versions",
        ),
    }
    reconciliation_checks = []
    for key, aliases in universe_aliases.items():
        got = population_size(universe, aliases)
        if key == "input_report_versions" and got is None:
            got = population_size(universe, ("all_submission", "all_submission_population"))
        elif key == "canonical_cases" and got is None:
            got = population_size(universe, ("canonical_latest_case", "canonical_case_population"))
        elif key == "versions_removed" and got is None:
            all_count = population_size(universe, ("all_submission", "all_submission_population"))
            canonical_count = population_size(universe, ("canonical_latest_case", "canonical_case_population"))
            if all_count is not None and canonical_count is not None:
                got = all_count - canonical_count
        reconciliation_checks.append(got == expected_universe[key])
    population_containers = {
        "canonical_period_counts": (
            "canonical_period_counts", "period_counts", "canonical_source_periods",
            "retained_period_populations",
        ),
        "reporter_group_counts": (
            "reporter_group_counts", "canonical_reporter_buckets", "reporter_populations",
        ),
        "cross_stratum_counts": (
            "cross_stratum_counts", "period_by_reporter_counts",
            "canonical_period_by_reporter_strata", "retained_period_by_reporter_strata",
        ),
    }
    group_aliases = {
        "HCP": ("HCP", "healthcare_professional"),
        "CONSUMER": ("CONSUMER", "consumer"),
        "OTHER": ("OTHER", "other", "other_or_missing"),
    }
    for container_name, aliases in population_containers.items():
        container = deep_pick(universe, aliases)
        for key, expected_value in expected_universe[container_name].items():
            key_aliases = (key,)
            if key in group_aliases:
                key_aliases = group_aliases[key]
            elif "|" in key:
                period, group = key.split("|", 1)
                key_aliases = tuple(f"{period}|{item}" for item in group_aliases[group])
            got = integer(pick(container, key_aliases)) if isinstance(container, dict) else None
            if got is None and container_name == "canonical_period_counts":
                got = listed_population_size(container, period=key)
            elif got is None and container_name == "cross_stratum_counts" and "|" in key:
                period, group = key.split("|", 1)
                got = listed_population_size(container, period=period, group=group)
            elif got is None and container_name == "reporter_group_counts":
                if key == "HCP":
                    got = population_size(universe, ("canonical_hcp", "canonical_hcp_population"))
                if got is None:
                    strata = deep_pick(universe, (
                        "retained_period_by_reporter_strata", "canonical_period_by_reporter_strata",
                    ))
                    got = listed_population_size(strata, group=key)
            reconciliation_checks.append(got == expected_value)
    population_reconciliation = sum(reconciliation_checks) / len(reconciliation_checks)

    table_scores = []
    table_details = {}
    closure_checks = []
    synthesis_scores = []
    for key, expected in expected_pairs.items():
        row = pairs.get(key, {})
        contexts = [
            ("canonical", labeled_table(
                row,
                (
                    "canonical", "retained", "latest_case", "canonical_latest_case",
                    "canonical_latest_case_population", "canonical_case_population",
                ),
                ("canonical", "retained", "latest case"),
            ), expected["canonical"]),
            ("all_versions", labeled_table(
                row,
                ("all_versions", "all_submissions", "all_submissions_sensitivity", "all_submission_sensitivity", "as_received"),
                ("all versions", "all submissions", "all submitted", "as received"),
            ), expected["all_versions"]),
            ("hcp", labeled_table(
                row,
                (
                    "hcp", "healthcare_professional", "professional_reporters",
                    "canonical_healthcare_professional", "canonical_hcp_population",
                ),
                ("hcp", "healthcare professional"),
            ), expected["hcp"]),
        ]
        for period, expected_table in expected["periods"].items():
            contexts.append((period, period_table(row, period), expected_table))
        expected_strata = {
            (item["source_quarter"], item["reporter_group"]): item
            for item in expected["stratified"]["strata"]
        }
        for (period, group), expected_table in expected_strata.items():
            contexts.append((f"{period}|{group}", stratum_table(row, period, group), expected_table))
        details = {}
        for context_name, got_table, expected_table in contexts:
            points, detail = table_score(got_table, expected_table)
            table_scores.append(points)
            closure_checks.append(detail["closed"])
            details[context_name] = detail

        stratified = pick(row, (
            "stratified", "adjusted", "stratification", "adjusted_reporting_association",
        ))
        if not isinstance(stratified, dict):
            stratified = row
        mh_ok = close(
            deep_pick(stratified, (
                "mh_ror", "mantel_haenszel_ror", "common_ror", "adjusted_ror",
                "mh_adjusted_or",
            )),
            expected["stratified"]["mh_ror"],
        )
        effect_ok = label(
            deep_pick(row, (
                "version_effect", "canonical_vs_all_submission_transition",
                "canonical_vs_all_submission_signal_transition", "signal_transition", "effect",
            )),
            VERSION_EFFECT_ALIASES,
        ) == expected["version_effect"]
        disposition_ok = label(
            deep_pick(row, ("disposition", "decision", "action", "triage")),
            DISPOSITION_ALIASES,
        ) == expected["disposition"]
        synthesis_scores.append(0.40 * mh_ok + 0.25 * effect_ok + 0.35 * disposition_ok)
        table_details[key] = {
            "contexts": details,
            "mh_correct": mh_ok,
            "version_effect_correct": effect_ok,
            "disposition_correct": disposition_ok,
        }
    disproportionality_analysis = sum(table_scores) / len(table_scores)
    signal_synthesis = sum(synthesis_scores) / len(synthesis_scores)

    census_scores = []
    census_details = {}
    for key, expected in expected_census.items():
        row = census.get(key, {})
        checks = {
            field: integer(deep_pick(row, aliases)) == expected[field]
            for field, aliases in CENSUS_ALIASES.items()
        }
        census_scores.append(sum(checks.values()) / len(checks))
        census_details[key] = {
            "checks_correct": sum(checks.values()),
            "checks_total": len(checks),
        }
    census_component = sum(census_scores) / len(census_scores)

    driver_scores = []
    driver_details = {}
    driver_trace_checks = []
    for key, expected in expected_drivers.items():
        row = drivers.get(key, {})
        version_rows = pick(row, (
            "versions", "version_packets", "submissions", "report_versions", "history",
            "submitted_versions",
        ))
        version_rows = row_list(version_rows, "primaryid")
        indexed_versions, duplicate_versions = index_rows(
            version_rows,
            lambda item: str(pick(item, ("primaryid", "report_id", "report_identifier")) or "").strip(),
        )
        version_scores = []
        version_detail = {}
        trace_all = True
        for expected_version in expected["versions"]:
            primaryid = str(expected_version["primaryid"])
            got = indexed_versions.get(primaryid, {})
            identity_ok = bool(got) and integer(
                pick(got, ("caseversion", "case_version", "version"))
            ) == expected_version["caseversion"]
            state_ok = version_state(got) == expected_version["pair_state"]
            exposure_ok = version_exposure(got) is expected_version["primary_suspect_exposure"]
            event_ok = version_event(got) is expected_version["target_event_present"]
            source_rate = source_resolution(version_source_context(got,row,primaryid), expected_version["source_rows"], primaryid)
            trace_all = trace_all and source_rate > 0
            points = (
                0.15 * identity_ok + 0.30 * state_ok + 0.15 * exposure_ok
                + 0.15 * event_ok + 0.10 * source_rate
            )
            version_scores.append(points)
            version_detail[primaryid] = {
                "identity_correct": identity_ok,
                "pair_state_correct": state_ok,
                "exposure_correct": exposure_ok,
                "event_correct": event_ok,
                "source_resolution": round(source_rate, 6),
                "score": round(points, 6),
            }
        version_component = sum(version_scores) / len(version_scores)
        text = evidence_text(row)
        change_rate = sum(
            semantic_scores.get(f"driver:{key}:{change}", 0.0)
            for change in expected["material_changes"]
        ) / len(expected["material_changes"])
        points = version_component + 0.15 * change_rate
        driver_scores.append(points)
        driver_trace_checks.append(trace_all and bool(version_rows))
        driver_details[key] = {
            "versions": version_detail,
            "duplicate_versions": sorted(duplicate_versions),
            "change_coverage": round(change_rate, 6),
            "score": round(points, 6),
        }
    detailed_driver_component = sum(driver_scores) / len(driver_scores)
    version_driver_audit = 0.30 * census_component + 0.70 * detailed_driver_component
    duplicate_driver_versions = any(
        bool(detail["duplicate_versions"]) for detail in driver_details.values()
    )

    case_scores = []
    case_details = {}
    case_trace_checks = []
    for key, expected in expected_cases.items():
        row = cases.get(key, {})
        identity_ok = case_identity_matches(row, expected)
        temporal_ok = status_matches(
            row,
            ("temporal_status", "chronology", "time_relationship", "chronology_status", "start_vs_event", "relation"),
            TEMPORAL_ALIASES,
            expected["temporal_status"],
        ) and identity_ok
        dechallenge_ok = status_matches(
            row,
            ("dechallenge_status", "dechallenge", "withdrawal_status", "dechal_interpretation"),
            DECHALLENGE_ALIASES,
            expected["dechallenge_status"],
        ) and identity_ok
        rechallenge_ok = status_matches(
            row,
            ("rechallenge_status", "rechallenge", "re_exposure_status", "rechal_interpretation"),
            RECHALLENGE_ALIASES,
            expected["rechallenge_status"],
        ) and identity_ok
        causality_ok = nested_label(
            row,
            ("causality", "category", "final_category", "causality_category", "assessment"),
            CAUSALITY_ALIASES,
        ) == expected["causality"] and identity_ok
        text = evidence_text(row)
        evidence_hits = sum(
            semantic_scores.get(f"case:{key}:{concept}", 0.0)
            for concept in expected["evidence_codes"]
        ) if identity_ok else 0.0
        evidence_rate = evidence_hits / len(expected["evidence_codes"])
        source_rate = source_resolution(row, expected["source_rows"], str(expected["primaryid"])) if identity_ok else 0.0
        case_trace_checks.append(source_rate > 0)
        points = (
            0.18 * temporal_ok + 0.14 * dechallenge_ok + 0.14 * rechallenge_ok
            + 0.24 * causality_ok + 0.20 * evidence_rate + 0.10 * source_rate
        )
        case_scores.append(points)
        case_details[key] = {
            "identity_correct": identity_ok,
            "temporal_correct": temporal_ok,
            "dechallenge_correct": dechallenge_ok,
            "rechallenge_correct": rechallenge_ok,
            "causality_correct": causality_ok,
            "evidence_coverage": round(evidence_rate, 6),
            "source_resolution": round(source_rate, 6),
            "score": round(points, 6),
        }
    retained_case_causality = sum(case_scores) / len(case_scores)

    long_scores = []
    long_details = {}
    long_trace_checks = []
    for key, expected in expected_long.items():
        row = longitudinal.get(key, {})
        version_rows = pick(row, (
            "versions", "version_packets", "submissions", "report_versions", "history",
            "submitted_versions",
        ))
        version_rows = row_list(version_rows, "primaryid")
        indexed_versions, duplicate_versions = index_rows(
            version_rows,
            lambda item: str(pick(item, ("primaryid", "report_id", "report_identifier")) or "").strip(),
        )
        version_scores = []
        version_detail = {}
        trace_any = False
        for expected_version in expected["versions"]:
            primaryid = str(expected_version["primaryid"])
            got = indexed_versions.get(primaryid, {})
            id_ok = bool(got) and integer(pick(got, ("caseversion", "case_version", "version"))) == expected_version["caseversion"]
            state_ok = version_state(got) == expected_version["pair_state"]
            exposure_ok = version_exposure(got) is expected_version["primary_suspect_exposure"]
            event_ok = version_event(got) is expected_version["target_event_present"]
            causality_ok = nested_label(
                got,
                ("causality", "category", "version_category", "defensible_causality_conclusion_for_version", "assessment"),
                CAUSALITY_ALIASES,
            ) == expected_version["causality"]
            source_rate = source_resolution(version_source_context(got,row,primaryid), expected_version["source_rows"], primaryid)
            trace_any = trace_any or source_rate > 0
            points = 0.10 * id_ok + 0.25 * state_ok + 0.15 * exposure_ok + 0.15 * event_ok + 0.20 * causality_ok + 0.15 * source_rate
            version_scores.append(points)
            version_detail[primaryid] = {
                "identity_correct": id_ok,
                "pair_state_correct": state_ok,
                "exposure_correct": exposure_ok,
                "event_correct": event_ok,
                "causality_correct": causality_ok,
                "source_resolution": round(source_rate, 6),
                "score": round(points, 6),
            }
        text = evidence_text(row)
        change_rate = sum(
            semantic_scores.get(f"long:{key}:{concept}", 0.0)
            for concept in expected["material_changes"]
        ) / len(expected["material_changes"])
        impact_ok = impact_matches(row, expected["assessment_impact"])
        version_component = sum(version_scores) / len(version_scores)
        points = 0.50 * version_component + 0.25 * change_rate + 0.25 * impact_ok
        long_scores.append(points)
        long_trace_checks.append(trace_any)
        long_details[key] = {
            "versions": version_detail,
            "duplicate_versions": sorted(duplicate_versions),
            "change_coverage": round(change_rate, 6),
            "impact_correct": impact_ok,
            "score": round(points, 6),
        }
    longitudinal_revision = sum(long_scores) / len(long_scores)
    duplicate_longitudinal_versions = any(
        bool(detail["duplicate_versions"]) for detail in long_details.values()
    )

    integrity_ok = source_integrity()
    exact_coverage = (
        set(pairs) == set(expected_pairs)
        and set(census) == set(expected_census)
        and set(drivers) == set(expected_drivers)
        and set(cases) == set(expected_cases)
        and set(longitudinal) == set(expected_long)
        and not duplicate_pairs and not duplicate_census and not duplicate_drivers
        and not duplicate_cases and not duplicate_long
        and not duplicate_driver_versions and not duplicate_longitudinal_versions
    )
    method_present = bool(section(book, ("method", "methods", "methodology", "analysis_method"), dict))
    limitations = section(book, ("limitations", "caveats", "interpretive_limitations"), list)
    # The task requires a non-empty limitations section but does not prescribe
    # a vocabulary.  The semantic content is assessed in the professional
    # dimensions above; this completion gate only checks that the section is
    # present and non-empty.
    limitation_present = bool(limitations)
    contract_coverage = (float(exact_coverage) + float(method_present) + float(limitation_present)) / 3
    table_closure = sum(closure_checks) / len(closure_checks)
    evidence_traceability = (
        sum(driver_trace_checks) + sum(case_trace_checks) + sum(long_trace_checks)
    ) / (len(driver_trace_checks) + len(case_trace_checks) + len(long_trace_checks))

    # Completion is an additive delivery lens.  A missing section, an open
    # table, or an unbound history loses its own share without multiplying away
    # otherwise valid work; source integrity remains an infrastructure gate.
    lenient = round(float(integrity_ok) * (
        0.40 * contract_coverage + 0.30 * table_closure + 0.30 * evidence_traceability
    ), 6)

    # Strict capability keeps the six source-derived business dimensions, and
    # gives independent, auditable quality credit to complete coverage, closed
    # tables, and traceable evidence.  These additive terms avoid a hidden cap
    # or repeated multiplicative punishment while still making delivery defects
    # visible in the primary score.
    strict = round(
        0.02 * population_reconciliation
        + 0.08 * disproportionality_analysis
        + 0.03 * signal_synthesis
        + 0.15 * version_driver_audit
        + 0.32 * retained_case_causality
        + 0.26 * longitudinal_revision
        + 0.02 * float(integrity_ok)
        + 0.04 * float(exact_coverage)
        + 0.04 * table_closure
        + 0.04 * evidence_traceability,
        6,
    )
    top_level_complete = exact_coverage
    pairs_exactly_once = set(pairs)==set(expected_pairs) and not duplicate_pairs

    groups = {
        "population_reconciliation": population_reconciliation,
        "disproportionality_analysis": disproportionality_analysis,
        "signal_synthesis": signal_synthesis,
        "version_driver_audit": version_driver_audit,
        "retained_case_causality": retained_case_causality,
        "longitudinal_revision": longitudinal_revision,
    }
    return {
        "reward": strict,
        "rewards": {"strict": strict, "lenient": lenient},
        "score_type": "longitudinal_pharmacovigilance_adjudication",
        "reward_formulas": {
            "strict": "0.02*population_reconciliation + 0.08*disproportionality_analysis + 0.03*signal_synthesis + 0.15*version_driver_audit + 0.32*retained_case_causality + 0.26*longitudinal_revision + 0.02*source_integrity + 0.04*exact_coverage + 0.04*table_closure + 0.04*evidence_traceability",
            "lenient": "source_integrity * (0.40*contract_coverage + 0.30*table_closure + 0.30*evidence_traceability)",
        },
        "checkpoint_count": 1,
        "gate_factor": float(integrity_ok),
        "gates": {
            "source_integrity": integrity_ok,
            "exact_identifier_coverage": exact_coverage,
            "unique_rows": not duplicate_pairs and not duplicate_census and not duplicate_drivers and not duplicate_cases and not duplicate_long and not duplicate_driver_versions and not duplicate_longitudinal_versions,
            "method_present": method_present,
            "limitations_present": limitation_present,
        },
        "group_scores": {key: round(value, 6) for key, value in groups.items()},
        "group_points": {
            "population_reconciliation": round(0.02 * population_reconciliation, 6),
            "disproportionality_analysis": round(0.08 * disproportionality_analysis, 6),
            "signal_synthesis": round(0.03 * signal_synthesis, 6),
            "version_driver_audit": round(0.15 * version_driver_audit, 6),
            "retained_case_causality": round(0.32 * retained_case_causality, 6),
            "longitudinal_revision": round(0.26 * longitudinal_revision, 6),
            "source_integrity": round(0.02 * float(integrity_ok), 6),
            "exact_coverage": round(0.04 * float(exact_coverage), 6),
            "table_closure": round(0.04 * table_closure, 6),
            "evidence_traceability": round(0.04 * evidence_traceability, 6),
        },
        "checkpoints": {
            "reconciliation": {"checks_correct": sum(reconciliation_checks), "checks_total": len(reconciliation_checks)},
            "pairs": table_details,
            "version_driver_census": census_details,
            "version_drivers": driver_details,
            "cases": case_details,
            "longitudinal": long_details,
        },
        "lenient_detail": {
            "contract_coverage": round(contract_coverage, 6),
            "top_level_complete": top_level_complete,
            "pairs_exactly_once": pairs_exactly_once,
            "table_closure": round(table_closure, 6),
            "evidence_traceability": round(evidence_traceability, 6),
            "closed_tables": sum(closure_checks),
            "required_tables": len(closure_checks),
        },
    }


def read_book(path: str) -> dict:
    candidate = Path(path)
    if candidate.is_dir():
        for name in ("faers_adjudication.json", "adjudication.json", "analysis.json", "result.json"):
            if (candidate / name).is_file():
                candidate = candidate / name
                break
    try:
        return json.loads(candidate.read_text(encoding="utf-8"))
    except Exception:
        return {}


if __name__ == "__main__":
    answer = sys.argv[1] if len(sys.argv) > 1 else "/workspace/faers_adjudication.json"
    print(json.dumps(score(read_book(answer)), indent=2))

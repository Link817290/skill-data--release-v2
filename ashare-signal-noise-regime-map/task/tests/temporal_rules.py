"""Pure forward witnesses for the published raw-regime and inertia rules.

Callers supply source-verified or explicitly declared cluster states in time order.
This module does not establish whether a declaration has sufficient source evidence.
None denotes an unknown direction/intensity, not an abstention or absent intensity.
Candidate claims are checked against witnesses but never constrain propagation.
"""
from __future__ import annotations

from itertools import product
from typing import Any, Iterable, Mapping


LABELS = ("NOISE", "REVIEW", "MIXED", "SIGNAL")
DIRECTION_KEYS = ("trend_dir", "odds_dir", "fund_dir")
STATE_KEYS = (*DIRECTION_KEYS, "event_intensity")


def raw_regime(trend_dir: int, odds_dir: int, fund_dir: int,
               event_intensity: bool) -> str:
    """Apply the four raw branches, including their short-circuit priority."""
    _validate_state(dict(zip(STATE_KEYS, (trend_dir, odds_dir, fund_dir, event_intensity))))
    if any(value is None for value in (trend_dir, odds_dir, fund_dir, event_intensity)):
        raise ValueError("raw_regime requires a fully known state")
    directed = [value for value in (trend_dir, odds_dir, fund_dir) if value != 0]
    if event_intensity and trend_dir == 0:
        return "NOISE"
    if len(directed) < 2:
        return "REVIEW"
    if 1 in directed and -1 in directed:
        return "MIXED"
    return "SIGNAL"


def next_final(raw_label: str, previous_raw: str | None,
               previous_final: str | None, *, directional_count: int,
               event_intensity: bool) -> str:
    """Resolve inertia for one known state; support need not repeat its raw label."""
    if raw_label not in LABELS:
        raise ValueError("unknown raw label")
    if (previous_raw is None) != (previous_final is None):
        raise ValueError("previous raw and final must both be present or absent")
    if previous_raw is not None and (previous_raw not in LABELS or previous_final not in LABELS):
        raise ValueError("unknown previous label")
    if type(directional_count) is not int or directional_count not in range(4):
        raise ValueError("directional_count must be an integer from zero to three")
    if type(event_intensity) is not bool:
        raise ValueError("event_intensity must be boolean")
    if previous_final is None or raw_label == previous_final or raw_label == previous_raw:
        return raw_label
    if previous_final == "NOISE" and not event_intensity:
        return raw_label
    if previous_final == "SIGNAL" and directional_count < 2:
        return raw_label
    return previous_final


def _validate_state(row: Mapping[str, Any]) -> None:
    for key in STATE_KEYS:
        if key not in row:
            raise ValueError(f"missing cluster state: {key}; use None for unknown")
    for key in DIRECTION_KEYS:
        value = row[key]
        if value is not None and (type(value) is not int or value not in (-1, 0, 1)):
            raise ValueError(f"{key} must be -1, 0, 1 or None")
    if row["event_intensity"] is not None and type(row["event_intensity"]) is not bool:
        raise ValueError("event_intensity must be bool or None")


def _current_cases(row: Mapping[str, Any]) -> set[tuple[str, int, bool, bool]]:
    _validate_state(row)
    choices = [(-1, 0, 1) if row[key] is None else (row[key],) for key in DIRECTION_KEYS]
    choices.append((False, True) if row["event_intensity"] is None else (row["event_intensity"],))
    cases = set()
    for trend, odds, fund, intensity in product(*choices):
        directions = (trend, odds, fund)
        cases.add((raw_regime(trend, odds, fund, intensity),
                   sum(value != 0 for value in directions), intensity,
                   1 in directions and -1 in directions))
    return cases


def _claim_diagnostics(claim: Mapping[str, Any] | None,
                       witnesses: set[tuple[str, str, bool]]) -> list[dict[str, Any]]:
    if claim is None:
        return []
    if not isinstance(claim, Mapping):
        raise ValueError("each candidate claim must be a mapping or None")
    supplied = {key: claim[key] for key in ("raw_label", "regime_label", "contradiction_flag")
                if key in claim and claim[key] is not None}
    if isinstance(supplied.get("contradiction_flag"), str):
        flag = supplied["contradiction_flag"]
        if flag in ("TRUE", "FALSE"):
            supplied["contradiction_flag"] = flag == "TRUE"
    diagnostics = []
    for index, key in enumerate(("raw_label", "regime_label", "contradiction_flag")):
        if key not in supplied:
            continue
        value = supplied[key]
        valid_type = type(value) is bool if key == "contradiction_flag" else isinstance(value, str)
        possible = {witness[index] for witness in witnesses}
        if not valid_type or value not in possible:
            diagnostics.append({"code": "impossible_" + key, "claim": claim[key],
                                "possible": sorted(possible),
                                "reason": "No forward witness permits this claim at this row."})
    if supplied and not diagnostics:
        keys = ("raw_label", "regime_label", "contradiction_flag")
        if not any(all(witness[index] == supplied[key] for index, key in enumerate(keys)
                       if key in supplied) for witness in witnesses):
            diagnostics.append({"code": "impossible_joint_claim", "claim": dict(claim),
                                "reason": "The claimed values are individually possible but have no common witness."})
    return diagnostics


def evaluate_temporal(rows: Iterable[Mapping[str, Any]],
                      claims: Iterable[Mapping[str, Any] | None] | None = None) -> list[dict[str, Any]]:
    """Return every reachable raw/final pair and certain claim contradictions.

    Required input keys: trend_dir, odds_dir, fund_dir (-1/0/1/None), and
    event_intensity (bool/None). Optional sample_id is returned unchanged.
    Claims, when supplied, align positionally and may contain raw_label,
    regime_label, and contradiction_flag (bool or the workbook's TRUE/FALSE).
    Unknown inputs expand independently at each window. Output uncertainty is
    epistemic: a possible label is not proof that its calibration is supported.

    State is exactly (previous raw, previous final), initialized at the first
    input row. Claims never initialize, filter, or reset this state. Therefore
    an earlier erroneous submitted label cannot cause a later correct label
    to be mechanically rejected.
    """
    rows = list(rows)
    candidate_claims = [None] * len(rows) if claims is None else list(claims)
    if len(candidate_claims) != len(rows):
        raise ValueError("claims must have one entry per input row")
    previous: set[tuple[str | None, str | None]] = {(None, None)}
    out = []
    for index, (row, claim) in enumerate(zip(rows, candidate_claims)):
        witnesses = set()
        for raw, count, intensity, contradiction in _current_cases(row):
            for previous_raw, previous_final in previous:
                final = next_final(raw, previous_raw, previous_final,
                                   directional_count=count, event_intensity=intensity)
                witnesses.add((raw, final, contradiction))
        states = {(raw, final) for raw, final, _ in witnesses}
        diagnostics = _claim_diagnostics(claim, witnesses)
        out.append({"row_index": index, "sample_id": row.get("sample_id"),
                    "possible_states": [{"raw_label": raw, "regime_label": final}
                                        for raw, final in sorted(states)],
                    "possible_raw_labels": sorted({raw for raw, _ in states}),
                    "possible_final_labels": sorted({final for _, final in states}),
                    "possible_contradiction_flags": sorted({flag for _, _, flag in witnesses}),
                    "witnesses": [{"raw_label": raw, "regime_label": final, "contradiction_flag": flag}
                                  for raw, final, flag in sorted(witnesses)],
                    "claim_admissible": None if claim is None else not diagnostics,
                    "diagnostics": diagnostics})
        previous = states
    return out

#!/usr/bin/env python3
"""Reusable deterministic ledger runtime for task-specific Program Judges."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


OBSERVATION_STATES = {"identified", "confirmed_missing", "ambiguous", "parse_failure"}
COMPARISON_RESULTS = {"exact", "equivalent", "partial", "different", "missing", "extra"}
COMPARISON_MODES = {"exact", "proposition_equivalent", "equivalent_set_replay", "formula_replay"}
DEDUCTION_STATES = {"not_triggered", "triggered", "ambiguous", "parse_failure", "not_applicable"}
EVIDENCE_ORIGINS = {"submitted", "lossless_canonicalized", "deterministically_derived"}
STRICT_EQUIVALENCE_DIMENSIONS = {
    "object", "source_or_evidence_anchor", "relation", "polarity", "modality",
    "time_or_version_scope", "units_or_quantities", "conditions_or_exceptions",
    "adoption_status", "downstream_consequence",
}
PENALTY_COEFFICIENTS = {round(index / 10, 1) for index in range(1, 10)}
SCORING_FORMULA = "additive-positive-multiplicative-damage-instance-penalty-v1"
REQUIRED_P_TEXT_FIELDS = (
    "scope", "object_key", "source_location", "relation_predicate",
    "golden_object_key", "golden_relation_predicate", "comparison_mode",
    "adoption_status", "negative_context_exclusions", "length_contract_id",
)
REQUIRED_D_TEXT_FIELDS = (
    "trigger", "damage_basis", "scope", "object_key", "source_location",
    "error_predicate", "adoption_status", "negative_context_exclusions",
    "causal_root_rule", "damage_instance_key_rule", "manifestation_rule",
    "length_contract_id",
)


@dataclass(frozen=True)
class Locator:
    locator_id: str
    artifact_path: str
    container_type: str
    container_path: str
    object_key: str
    field: str
    observed: str
    span: str = ""
    evidence_origin: str = "submitted"
    source_locator_ids: tuple[str, ...] = ()
    normalization_rule_id: str | None = None
    derivation_rule_id: str | None = None

    def validate(self) -> None:
        required = (
            self.locator_id, self.artifact_path, self.container_type,
            self.container_path, self.object_key, self.field,
        )
        if any(not str(value).strip() for value in required):
            raise ValueError("locator must bind an ID, artifact, container, structural path, object, and field")
        artifact = Path(self.artifact_path)
        if artifact.is_absolute() or ".." in artifact.parts:
            raise ValueError("locator artifact_path must be a portable root-relative path")
        if self.evidence_origin not in EVIDENCE_ORIGINS:
            raise ValueError(f"invalid evidence_origin: {self.evidence_origin}")
        sources = tuple(value for value in self.source_locator_ids if str(value).strip())
        if len(sources) != len(self.source_locator_ids):
            raise ValueError("source_locator_ids cannot contain empty IDs")
        if self.evidence_origin == "submitted":
            if sources or self.normalization_rule_id or self.derivation_rule_id:
                raise ValueError("submitted evidence cannot claim canonicalization or derivation provenance")
        elif self.evidence_origin == "lossless_canonicalized":
            if not sources or not str(self.normalization_rule_id or "").strip() or self.derivation_rule_id:
                raise ValueError("canonicalized evidence requires source IDs and one normalization rule")
        elif self.evidence_origin == "deterministically_derived":
            if not sources or not str(self.derivation_rule_id or "").strip() or self.normalization_rule_id:
                raise ValueError("derived evidence requires source IDs and one derivation rule")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_contract(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("contract must be a JSON object")
    return payload


class ProgramJudge:
    """Collect task predicates while enforcing the shared scoring invariants."""

    def __init__(self, contract: dict[str, Any], artifact_path: Path,
                 rubric_sha256: str | None = None, artifact_root: Path | None = None):
        if contract.get("schema_version") != "program-judge-contract-v4":
            raise ValueError("contract schema_version must be program-judge-contract-v4")
        if contract.get("scoring_formula") != SCORING_FORMULA:
            raise ValueError(f"contract scoring_formula must be {SCORING_FORMULA}")
        self.contract = contract
        self.artifact_path = artifact_path
        self.artifact_root = (artifact_root or artifact_path.parent).resolve()
        self.rubric_sha256 = rubric_sha256
        pipeline = contract.get("observation_pipeline")
        if not isinstance(pipeline, dict) or pipeline.get("layers") != [
            "raw_carrier", "normalized_business_observation", "program_decision",
        ]:
            raise ValueError("contract must declare the three-layer observation pipeline")
        self._normalization_rule_ids = self._rule_ids(
            pipeline.get("normalization_rules"), "normalization_rules",
        )
        self._derivation_rule_ids = self._rule_ids(
            pipeline.get("derivation_rules"), "derivation_rules",
        )
        self.positives = {item["id"]: item for item in contract.get("positive_items", [])}
        self.deductions = {item["id"]: item for item in contract.get("deduction_items", [])}
        if len(self.positives) != len(contract.get("positive_items", [])):
            raise ValueError("duplicate positive item IDs")
        if len(self.deductions) != len(contract.get("deduction_items", [])):
            raise ValueError("duplicate deduction item IDs")
        weights = []
        for item in self.positives.values():
            if any(not str(item.get(field, "")).strip() for field in REQUIRED_P_TEXT_FIELDS):
                raise ValueError("every positive item must bind a complete Golden business proposition")
            if item.get("comparison_mode") not in COMPARISON_MODES:
                raise ValueError("positive comparison_mode is not supported")
            if set(item.get("equivalence_dimensions", [])) != STRICT_EQUIVALENCE_DIMENSIONS:
                raise ValueError("positive predicates must enumerate every strict equivalence dimension")
            span = item.get("evidence_span")
            if not isinstance(span, dict) or set(span) != {"locator", "metric", "max_units"}:
                raise ValueError("positive predicates must declare one bounded evidence span")
            if not str(span.get("locator", "")).strip() or not str(span.get("metric", "")).strip():
                raise ValueError("positive evidence span locator and metric must be non-empty")
            if self._number(span.get("max_units"), "positive evidence max_units") <= 0:
                raise ValueError("positive evidence max_units must be positive")
            if item.get("self_report_fields_are_non_authoritative") is not True:
                raise ValueError("positive predicates cannot trust self-reported status or confidence")
            if item.get("comparison_mode") in {"equivalent_set_replay", "formula_replay"}:
                if not str(item.get("replay_rule_id", "")).strip():
                    raise ValueError("replay comparison requires replay_rule_id")
            weights.append(self._number(item.get("weight"), "positive weight"))
        if abs(sum(weights) - 1.0) > 1e-9:
            raise ValueError("positive weights must sum to 1.0")
        for item in self.deductions.values():
            if any(not str(item.get(field, "")).strip() for field in REQUIRED_D_TEXT_FIELDS):
                raise ValueError("every deduction item must bind a local adopted error proposition and damage instance")
            if item.get("ordinary_omission_excluded") is not True:
                raise ValueError("every deduction item must exclude ordinary omission")
            if item.get("self_report_fields_are_non_authoritative") is not True:
                raise ValueError("deduction predicates cannot trust self-reported status or confidence")
            self._coefficient(item.get("penalty_coefficient"))
        self._positive_results: dict[str, dict[str, Any]] = {}
        self._deduction_results: dict[str, dict[str, Any]] = {}
        self._semantic_candidates: list[dict[str, Any]] = []
        self._observations: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _rule_ids(values: Any, label: str) -> set[str]:
        if not isinstance(values, list):
            raise ValueError(f"observation_pipeline.{label} must be a list")
        identities: list[str] = []
        for value in values:
            if not isinstance(value, dict) or set(value) != {"id", "operation"}:
                raise ValueError(f"every {label} entry must contain exactly id and operation")
            identity = value.get("id")
            operation = value.get("operation")
            if not isinstance(identity, str) or not identity.strip() or not isinstance(operation, str) or not operation.strip():
                raise ValueError(f"every {label} entry needs a non-empty id and operation")
            identities.append(identity)
        if len(identities) != len(set(identities)):
            raise ValueError(f"observation_pipeline.{label} IDs must be unique")
        return set(identities)

    @staticmethod
    def _number(value: Any, label: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError(f"{label} must be a finite number")
        return float(value)

    def _evidence(self, locators: list[Locator]) -> list[dict[str, Any]]:
        if not locators:
            raise ValueError("a Judge decision must have structural evidence")
        seen: set[str] = set()
        rendered = []
        for locator in locators:
            locator.validate()
            if locator.normalization_rule_id and locator.normalization_rule_id not in self._normalization_rule_ids:
                raise ValueError(f"unregistered normalization rule: {locator.normalization_rule_id}")
            if locator.derivation_rule_id and locator.derivation_rule_id not in self._derivation_rule_ids:
                raise ValueError(f"unregistered derivation rule: {locator.derivation_rule_id}")
            if locator.locator_id in seen:
                raise ValueError(f"duplicate locator_id in one decision: {locator.locator_id}")
            unknown_sources = set(locator.source_locator_ids) - seen
            if unknown_sources:
                raise ValueError("derived or canonicalized evidence must follow its source locators")
            seen.add(locator.locator_id)
            payload = asdict(locator)
            payload["source_locator_ids"] = list(locator.source_locator_ids)
            rendered.append(payload)
        return rendered

    def observe(self, observation_id: str, state: str, evidence: list[Locator]) -> str:
        """Register one normalized observation and make its state runtime-owned."""
        identity = str(observation_id).strip()
        if not identity or identity in self._observations:
            raise ValueError("observation_id must be non-empty and unique")
        if state not in OBSERVATION_STATES:
            raise ValueError(f"invalid observation state: {state}")
        self._observations[identity] = {
            "observation_id": identity,
            "state": state,
            "evidence": self._evidence(evidence),
        }
        return identity

    def _observation(self, observation_id: str) -> dict[str, Any]:
        observation = self._observations.get(str(observation_id).strip())
        if observation is None:
            raise ValueError(f"unknown observation_id: {observation_id}")
        return observation

    def _observation_evidence(self, observation_ids: list[str]) -> list[dict[str, Any]]:
        if not observation_ids:
            raise ValueError("a Judge decision must cite at least one registered observation")
        if len(observation_ids) != len(set(observation_ids)):
            raise ValueError("a Judge decision cannot repeat an observation_id")
        return [locator for identity in observation_ids
                for locator in self._observation(identity)["evidence"]]

    def positive(self, item_id: str, fraction: float, observation_id: str,
                 reason: str, comparison_result: str) -> None:
        if item_id not in self.positives or item_id in self._positive_results:
            raise ValueError(f"unknown or repeated positive item: {item_id}")
        observation = self._observation(observation_id)
        state = observation["state"]
        if comparison_result not in COMPARISON_RESULTS:
            raise ValueError(f"invalid comparison_result: {comparison_result}")
        fraction = self._number(fraction, "positive fraction")
        if not 0.0 <= fraction <= 1.0:
            raise ValueError("positive fraction must be in [0, 1]")
        if state != "identified" and fraction != 0:
            raise ValueError("only identified evidence can earn positive credit")
        if state == "confirmed_missing" and comparison_result != "missing":
            raise ValueError("confirmed_missing must record comparison_result=missing")
        if state == "identified" and comparison_result == "missing":
            raise ValueError("identified evidence cannot compare as missing")
        if fraction > 0 and comparison_result not in {"exact", "equivalent", "partial"}:
            raise ValueError("positive credit requires an exact, equivalent, or partial proposition match")
        if comparison_result in {"exact", "equivalent"} and fraction != 1.0:
            raise ValueError("exact or equivalent matches must receive full credit")
        if comparison_result == "partial" and not 0.0 < fraction < 1.0:
            raise ValueError("partial matches must receive a fraction strictly between zero and one")
        mode = self.positives[item_id]["comparison_mode"]
        if mode == "exact" and comparison_result == "equivalent":
            raise ValueError("exact comparison mode cannot accept semantic equivalence")
        weight = self._number(self.positives[item_id]["weight"], "positive weight")
        self._positive_results[item_id] = {
            "id": item_id,
            "kind": "positive",
            "state": state,
            "comparison_result": comparison_result,
            "fraction": fraction,
            "weight": weight,
            "earned": weight * fraction,
            "reason": reason,
            "observation_id": observation["observation_id"],
            "evidence": observation["evidence"],
        }

    @staticmethod
    def _coefficient(value: Any) -> float:
        coefficient = ProgramJudge._number(value, "penalty coefficient")
        if round(coefficient, 10) not in PENALTY_COEFFICIENTS:
            raise ValueError("penalty coefficient must be one of 0.1, 0.2, ..., 0.9")
        return round(coefficient, 1)

    def deduction(self, item_id: str, state: str, observation_ids: list[str], reason: str,
                  occurrences: list[dict[str, Any]] | None = None) -> None:
        if item_id not in self.deductions or item_id in self._deduction_results:
            raise ValueError(f"unknown or repeated deduction item: {item_id}")
        if state not in DEDUCTION_STATES:
            raise ValueError(f"invalid deduction state: {state}")
        rendered_evidence = self._observation_evidence(observation_ids)
        occurrences = occurrences or []
        if state == "triggered" and not occurrences:
            raise ValueError("triggered deduction requires at least one damage occurrence")
        if state != "triggered" and occurrences:
            raise ValueError("only triggered deductions may record damage occurrences")
        coefficient = self._coefficient(self.deductions[item_id].get("penalty_coefficient"))
        rendered_occurrences = []
        for occurrence in occurrences:
            key = str(occurrence.get("damage_instance_key", "")).strip()
            causal_root_id = str(occurrence.get("causal_root_id", "")).strip()
            manifestation_id = str(occurrence.get("manifestation_id", "")).strip()
            observation_id = str(occurrence.get("observation_id", "")).strip()
            if not key:
                raise ValueError("deduction damage_instance_key must be non-empty")
            if not causal_root_id or not manifestation_id:
                raise ValueError("deduction occurrence requires causal_root_id and manifestation_id")
            observation = self._observation(observation_id)
            if observation["state"] != "identified":
                raise ValueError("only an identified affirmative observation may create a deduction occurrence")
            if observation_id not in observation_ids:
                raise ValueError("deduction occurrence must cite an observation used by the decision")
            rendered_occurrences.append({
                "id": item_id,
                "kind": "penalty_occurrence",
                "damage_instance_key": key,
                "causal_root_id": causal_root_id,
                "manifestation_id": manifestation_id,
                "observation_id": observation_id,
                "observation_state": observation["state"],
                "penalty_coefficient": coefficient,
                "reason": str(occurrence.get("reason", reason)),
                "evidence": observation["evidence"],
            })
        self._deduction_results[item_id] = {
            "id": item_id,
            "kind": "deduction",
            "state": state,
            "observation_ids": list(observation_ids),
            "reason": reason,
            "evidence": rendered_evidence,
            "occurrences": rendered_occurrences,
        }

    def semantic_candidate(self, item_id: str, question: str, evidence: list[Locator]) -> None:
        """Queue an unmechanized question for Semantic Audit without changing score."""
        self._semantic_candidates.append({"item_id": item_id, "question": question,
                                          "evidence": self._evidence(evidence)})

    def finish(self) -> dict[str, Any]:
        missing_p = sorted(set(self.positives) - set(self._positive_results))
        missing_d = sorted(set(self.deductions) - set(self._deduction_results))
        if missing_p:
            raise ValueError(f"positive items were not evaluated: {', '.join(missing_p)}")
        if missing_d:
            raise ValueError(f"deduction items were not evaluated: {', '.join(missing_d)}")
        positive_items = [self._positive_results[item_id] for item_id in self.positives]
        deduction_items = [self._deduction_results[item_id] for item_id in self.deductions]
        positive_earned = sum(item["earned"] for item in positive_items)
        penalty_occurrences = [
            occurrence
            for item in deduction_items
            for occurrence in item["occurrences"]
        ]
        instances: dict[str, list[dict[str, Any]]] = {}
        manifestation_lineage: dict[str, tuple[str, str]] = {}
        for occurrence in penalty_occurrences:
            lineage = (occurrence["damage_instance_key"], occurrence["causal_root_id"])
            prior = manifestation_lineage.setdefault(occurrence["manifestation_id"], lineage)
            if prior != lineage:
                raise ValueError("one manifestation_id cannot map to multiple damage instances or causal roots")
            instances.setdefault(occurrence["damage_instance_key"], []).append(occurrence)
        penalty_instances = []
        retention_multiplier = 1.0
        for damage_instance_key in sorted(instances):
            occurrences = instances[damage_instance_key]
            causal_root_ids = sorted({item["causal_root_id"] for item in occurrences})
            if len(causal_root_ids) != 1:
                raise ValueError("one damage_instance_key must map to exactly one causal root")
            coefficient = min(item["penalty_coefficient"] for item in occurrences)
            retention_multiplier *= coefficient
            penalty_instances.append({
                "damage_instance_key": damage_instance_key,
                "item_ids": sorted({item["id"] for item in occurrences}),
                "causal_root_ids": causal_root_ids,
                "manifestation_ids": sorted({item["manifestation_id"] for item in occurrences}),
                "penalty_coefficient": coefficient,
                "occurrence_count": len(occurrences),
            })
        final_score = positive_earned * retention_multiplier
        penalty_rate = 1.0 - retention_multiplier
        score_loss = positive_earned - final_score
        resolved_artifact = self.artifact_path.resolve()
        try:
            artifact_path = resolved_artifact.relative_to(self.artifact_root).as_posix()
        except ValueError as exc:
            raise ValueError("artifact must stay under artifact_root for a portable result path") from exc
        artifact = {
            "path": artifact_path,
            "sha256": sha256(self.artifact_path) if self.artifact_path.is_file() else None,
        }
        return {
            "schema_version": "program-judge-result-v4",
            "scoring_formula": SCORING_FORMULA,
            "rubric_version": self.contract.get("rubric_version"),
            "rubric_sha256": self.rubric_sha256,
            "artifact": artifact,
            "observations": list(self._observations.values()),
            "positive_earned": round(positive_earned, 9),
            "retention_multiplier": round(retention_multiplier, 9),
            "penalty_rate": round(penalty_rate, 9),
            "score_loss": round(score_loss, 9),
            "final_score": round(final_score, 9),
            "items": positive_items,
            "deduction_items": deduction_items,
            "penalty_occurrences": penalty_occurrences,
            "penalty_instances": penalty_instances,
            "semantic_candidates": self._semantic_candidates,
        }

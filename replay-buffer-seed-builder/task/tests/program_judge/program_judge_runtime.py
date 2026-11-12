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


@dataclass(frozen=True)
class Locator:
    artifact_path: str
    container_type: str
    container_path: str
    object_key: str
    field: str
    observed: str
    span: str = ""

    def validate(self) -> None:
        required = (self.artifact_path, self.container_type, self.container_path,
                    self.object_key, self.field)
        if any(not str(value).strip() for value in required):
            raise ValueError("locator must bind artifact, container, structural path, object, and field")


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

    def __init__(self, contract: dict[str, Any], artifact_path: Path):
        self.contract = contract
        self.artifact_path = artifact_path
        self.positives = {item["id"]: item for item in contract.get("positive_items", [])}
        self.deductions = {item["id"]: item for item in contract.get("deduction_items", [])}
        if len(self.positives) != len(contract.get("positive_items", [])):
            raise ValueError("duplicate positive item IDs")
        if len(self.deductions) != len(contract.get("deduction_items", [])):
            raise ValueError("duplicate deduction item IDs")
        weights = [self._number(item.get("weight"), "positive weight") for item in self.positives.values()]
        if abs(sum(weights) - 1.0) > 1e-9:
            raise ValueError("positive weights must sum to 1.0")
        self._positive_results: dict[str, dict[str, Any]] = {}
        self._deduction_hits: list[dict[str, Any]] = []
        self._seen_roots: set[str] = set()
        self._item_deductions: dict[str, float] = {}
        self._unresolved: list[dict[str, Any]] = []
        self._semantic_candidates: list[dict[str, Any]] = []

    @staticmethod
    def _number(value: Any, label: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError(f"{label} must be a finite number")
        return float(value)

    @staticmethod
    def _evidence(locators: list[Locator]) -> list[dict[str, Any]]:
        if not locators:
            raise ValueError("a Judge decision must have structural evidence")
        for locator in locators:
            locator.validate()
        return [asdict(locator) for locator in locators]

    def positive(self, item_id: str, fraction: float, state: str, evidence: list[Locator], reason: str) -> None:
        if item_id not in self.positives or item_id in self._positive_results:
            raise ValueError(f"unknown or repeated positive item: {item_id}")
        if state not in OBSERVATION_STATES:
            raise ValueError(f"invalid observation state: {state}")
        fraction = self._number(fraction, "positive fraction")
        if not 0.0 <= fraction <= 1.0:
            raise ValueError("positive fraction must be in [0, 1]")
        if state in {"ambiguous", "parse_failure"} and fraction != 0:
            raise ValueError("ambiguous or parse-failure evidence cannot earn credit")
        weight = self._number(self.positives[item_id]["weight"], "positive weight")
        self._positive_results[item_id] = {
            "id": item_id,
            "kind": "positive",
            "state": state,
            "fraction": fraction,
            "weight": weight,
            "earned": weight * fraction,
            "reason": reason,
            "evidence": self._evidence(evidence),
        }

    def deduct(self, item_id: str, root_cause_key: str, units: float,
               evidence: list[Locator], reason: str) -> None:
        if item_id not in self.deductions:
            raise ValueError(f"unknown deduction item: {item_id}")
        if not root_cause_key.strip():
            raise ValueError("deduction root_cause_key must be non-empty")
        if root_cause_key in self._seen_roots:
            return
        units = self._number(units, "deduction units")
        if units <= 0:
            raise ValueError("deduction units must be positive")
        item = self.deductions[item_id]
        scale = self._number(item.get("scale"), "deduction scale")
        cap = self._number(item.get("max_deduction"), "deduction cap")
        if not 0 < cap <= 0.2:
            raise ValueError("deduction cap must be in (0, 0.2]")
        used = self._item_deductions.get(item_id, 0.0)
        amount = min(scale * units, max(0.0, cap - used))
        self._seen_roots.add(root_cause_key)
        self._item_deductions[item_id] = used + amount
        if amount:
            self._deduction_hits.append({
                "id": item_id,
                "kind": "deduction",
                "root_cause_key": root_cause_key,
                "units": units,
                "scale": scale,
                "amount": amount,
                "reason": reason,
                "evidence": self._evidence(evidence),
            })

    def unresolved(self, item_id: str, state: str, evidence: list[Locator], reason: str) -> None:
        if state not in {"ambiguous", "parse_failure"}:
            raise ValueError("unresolved state must be ambiguous or parse_failure")
        self._unresolved.append({"item_id": item_id, "state": state, "reason": reason,
                                 "evidence": self._evidence(evidence)})

    def semantic_candidate(self, item_id: str, question: str, evidence: list[Locator]) -> None:
        """Queue an unmechanized question for Semantic Audit without changing score."""
        self._semantic_candidates.append({"item_id": item_id, "question": question,
                                          "evidence": self._evidence(evidence)})

    def finish(self) -> dict[str, Any]:
        missing = sorted(set(self.positives) - set(self._positive_results))
        if missing:
            raise ValueError(f"positive items were not evaluated: {', '.join(missing)}")
        positive_items = [self._positive_results[item_id] for item_id in self.positives]
        positive_earned = sum(item["earned"] for item in positive_items)
        deduction_total = sum(item["amount"] for item in self._deduction_hits)
        # Deductions price the separate harm a wrong assertion does downstream; they do
        # not repossess work that was carried out correctly. Capping the total at half the
        # credit earned keeps a record that derived its values correctly from scoring as
        # though nothing had been done, however many records it emitted beyond the shape.
        deduction_total = min(deduction_total, 0.5 * positive_earned)
        raw = positive_earned - deduction_total
        artifact = {
            "path": self.artifact_path.as_posix(),
            "sha256": sha256(self.artifact_path) if self.artifact_path.is_file() else None,
        }
        return {
            "schema_version": "program-judge-result-v1",
            "rubric_version": self.contract.get("rubric_version"),
            "artifact": artifact,
            "positive_earned": round(positive_earned, 9),
            "deduplicated_deductions": round(deduction_total, 9),
            "raw_score": round(raw, 9),
            "final_score": round(max(0.0, raw), 9),
            "items": positive_items,
            "deductions": self._deduction_hits,
            "unresolved": self._unresolved,
            "semantic_candidates": self._semantic_candidates,
        }

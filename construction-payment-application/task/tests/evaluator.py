#!/usr/bin/env python3
"""Condition-blind mixed evaluator for the construction payment application."""
from __future__ import annotations

import argparse
import json
import math
from decimal import Decimal
from pathlib import Path

from docx import Document
from openpyxl import load_workbook

import semantic_judge
import verify


SEMANTIC_WEIGHTS = {
    "submission_readiness": 0.10,
    "q08_cutoff_handoff": 0.08,
    "v03_price_handoff": 0.08,
    "d02_quantity_handoff": 0.08,
    "measurement_revision_control": 0.10,
    "price_authority_control": 0.12,
    "engineering_advance_bridge": 0.11,
    "material_advance_bridge": 0.13,
    "retention_and_debit_basis": 0.10,
    "attachment_and_adoption_control": 0.10,
}


def extract_files(root: Path) -> str:
    lines = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if not path.is_file() or path.name.startswith("~$"):
            continue
        label = path.relative_to(root).as_posix()
        if path.suffix.lower() == ".docx":
            document = Document(path)
            for index, paragraph in enumerate(document.paragraphs, 1):
                if paragraph.text.strip():
                    lines.append(f"[{label}/paragraph-{index}] {paragraph.text}")
            for table_index, table in enumerate(document.tables, 1):
                for row_index, row in enumerate(table.rows, 1):
                    text = " | ".join(cell.text for cell in row.cells)
                    if text.strip(" |"):
                        lines.append(f"[{label}/table-{table_index}/row-{row_index}] {text}")
        elif path.suffix.lower() == ".xlsx":
            workbook = load_workbook(path, data_only=False)
            for sheet in workbook.worksheets:
                for row_index, row in enumerate(sheet.iter_rows(values_only=True), 1):
                    values = [str(value) for value in row if value is not None]
                    if values:
                        lines.append(f"[{label}/{sheet.title}/row-{row_index}] " + " | ".join(values))
    return "\n".join(lines)


def jsonable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def core_numeric_pass(numeric: dict) -> bool:
    checks = numeric.get("checks", {})
    required = ("eligible_lines", "line_arithmetic", "current_rollup", "advances",
                "retention_other", "cumulative", "summary_arithmetic")
    if not all(checks.get(name) and all(checks[name]) for name in required):
        return False
    letter = checks.get("letter_and_balances", [])
    return bool(letter and letter[0])


def score(submission: Path, workspace: Path) -> dict:
    numeric = verify.verify(submission, workspace / "input")
    if not numeric.get("measurement_complete"):
        raise RuntimeError(numeric.get("reason", "numeric measurement unavailable"))
    if "groups" not in numeric:
        return {
            "status": "completed", "rewards": {"strict": 0.0, "lenient": 0.0},
            "numeric_score": 0.0, "semantic_score": 0.0, "numeric": numeric,
            "semantic": None,
        }

    candidate = extract_files(submission)
    if not candidate.strip():
        return {
            "status": "completed", "rewards": {"strict": 0.0, "lenient": 0.0},
            "numeric_score": 0.0, "semantic_score": 0.0, "numeric": numeric,
            "semantic": None,
        }
    source = json.dumps(jsonable(verify.source(workspace / "input")), ensure_ascii=False,
                        sort_keys=True)
    review = semantic_judge.adjudicate(candidate, source)
    fractions = {key: float(item["fraction"]) for key, item in review["items"].items()}
    semantic = sum(SEMANTIC_WEIGHTS[key] * fractions[key] for key in SEMANTIC_WEIGHTS)
    numeric_score = float(numeric["score"])
    numeric_controls = {key: float(value) for key, value in numeric["groups"].items()}
    # Each deterministic and semantic owner is represented once. Their product is
    # the complete-package reliability; diagnostic weighted views do not settle reward.
    numeric_reliability = math.prod(numeric_controls.values())
    semantic_reliability = math.prod(fractions.values())
    strict = round(numeric_reliability * semantic_reliability, 12)
    lenient = float(core_numeric_pass(numeric) and all(fractions[key] == 1.0 for key in SEMANTIC_WEIGHTS))
    if not all(math.isfinite(value) and 0 <= value <= 1 for value in (strict, lenient)):
        raise ValueError("invalid reward")
    return {
        "status": "completed",
        "rewards": {"strict": strict, "lenient": lenient},
        "numeric_score": numeric_score,
        "semantic_score": semantic,
        "formula": "product(numeric_control_fractions) * product(semantic_control_fractions)",
        "numeric_reliability": numeric_reliability,
        "semantic_reliability": semantic_reliability,
        "numeric_control_fractions": numeric_controls,
        "semantic_fractions": fractions,
        "numeric": numeric,
        "semantic": review,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("submission", type=Path)
    parser.add_argument("--workspace", type=Path, default=Path("/workspace"))
    args = parser.parse_args()
    print(json.dumps(score(args.submission, args.workspace), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Derive structured verifier truth from the rendered golden report."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


FIELD_RE = re.compile(r"^- ([^:]+):\s*(.*)$")


def parse_report(text: str) -> dict[str, object]:
    findings: list[dict[str, str]] = []
    clearances: list[dict[str, str]] = []
    occurrences: list[dict[str, str]] = []
    references: list[dict[str, str]] = []
    patches: list[dict[str, str]] = []
    exclusions: list[dict[str, str]] = []
    collisions: list[dict[str, str]] = []
    actions: list[dict[str, str]] = []
    controls: dict[str, int] = {}
    current: dict[str, str] | None = None
    section = ""

    def table_cells(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    for line in text.splitlines():
        section_heading = re.match(r"^##\s+(.+)$", line)
        if section_heading:
            section = section_heading.group(1).casefold()
            current = None
            continue
        if line.startswith("- ") and section == "control totals":
            total = re.match(r"^-\s+(.+?):\s*\*\*(\d+)\*\*", line)
            if total:
                label = re.sub(r"[^a-z0-9]+", "_", total.group(1).casefold()).strip("_")
                controls[label] = int(total.group(2))
            continue
        if line.startswith("|") and not re.match(r"^\|\s*[-:| ]+\|\s*$", line):
            cells = table_cells(line)
            if cells and re.fullmatch(r"O\d+", cells[0]) and section == "body-citation occurrence ledger":
                if len(cells) != 9:
                    raise ValueError(f"Unexpected occurrence row width: {cells}")
                occurrences.append(
                    {
                        "key": cells[0],
                        "physical_page": cells[1],
                        "printed_page": cells[2],
                        "observed": cells[3],
                        "components": cells[4],
                        "form": cells[5],
                        "explicitness": cells[6],
                        "status": cells[7],
                        "mapping": cells[8],
                    }
                )
                continue
            if cells and re.fullmatch(r"R\d+", cells[0]) and section == "end-reference ledger":
                if len(cells) != 9:
                    raise ValueError(f"Unexpected reference row width: {cells}")
                references.append(
                    {
                        "key": cells[0],
                        "physical_page": cells[1],
                        "printed_page": cells[2],
                        "head": cells[3],
                        "year": cells[4],
                        "cardinality": cells[5],
                        "title": cells[6],
                        "status": cells[7],
                        "owner": cells[8],
                    }
                )
                continue
            if cells and re.fullmatch(r"K\d+", cells[0]) and section == "collision and inheritance register":
                if len(cells) != 7:
                    raise ValueError(f"Unexpected collision row width: {cells}")
                collisions.append(
                    {
                        "key": cells[0],
                        "stem": cells[1],
                        "body_components": cells[2],
                        "candidate_records": cells[3],
                        "explicitness": cells[4],
                        "state": cells[5],
                        "evidence": cells[6],
                    }
                )
                continue
            if cells and re.fullmatch(r"A\d+", cells[0]) and section == "action-ownership matrix":
                if len(cells) != 5:
                    raise ValueError(f"Unexpected action row width: {cells}")
                actions.append(
                    {
                        "key": cells[0],
                        "finding": cells[1],
                        "owner": cells[2],
                        "precondition": cells[3],
                        "state": cells[4],
                    }
                )
                continue
            if cells and re.fullmatch(r"P\d+", cells[0]) and section == "confirmed repair patch register":
                if len(cells) != 7:
                    raise ValueError(f"Unexpected patch row width: {cells}")
                patches.append(
                    {
                        "key": cells[0],
                        "finding": cells[1],
                        "location": cells[2],
                        "current": cells[3],
                        "proposed": cells[4],
                        "record": cells[5],
                        "evidence": cells[6],
                    }
                )
                continue
            if cells and re.fullmatch(r"E\d+", cells[0]) and section == "non-citation date exclusion register":
                if len(cells) != 6:
                    raise ValueError(f"Unexpected exclusion row width: {cells}")
                exclusions.append(
                    {
                        "key": cells[0],
                        "physical_page": cells[1],
                        "printed_page": cells[2],
                        "token": cells[3],
                        "context": cells[4],
                        "reason": cells[5],
                    }
                )
                continue
        heading = re.match(r"^###\s+([FC]\d+)\s+-\s+(.+)$", line)
        if heading:
            current = {"key": heading.group(1), "heading": heading.group(2)}
            if heading.group(1).startswith("F"):
                findings.append(current)
            else:
                clearances.append(current)
            continue
        if current is not None:
            field = FIELD_RE.match(line)
            if field:
                current[field.group(1).casefold().replace(" ", "_")] = field.group(2).strip("`")

    if len(findings) != 17 or len(clearances) != 8:
        raise ValueError(f"Unexpected golden structure: {len(findings)} findings, {len(clearances)} clearances")
    if len(occurrences) != 50 or len(references) != 28 or len(patches) != 19 or len(exclusions) != 35 or len(collisions) != 10 or len(actions) != 17:
        raise ValueError(
            f"Unexpected ledger structure: {len(occurrences)} occurrences, "
            f"{len(references)} references, {len(patches)} patches, {len(exclusions)} exclusions, "
            f"{len(collisions)} collisions, {len(actions)} actions"
        )
    return {
        "schema_version": 1,
        "finding_count": len(findings),
        "clearance_count": len(clearances),
        "occurrence_count": len(occurrences),
        "reference_count": len(references),
        "patch_count": len(patches),
        "controls": controls,
        "findings": findings,
        "clearances": clearances,
        "occurrences": occurrences,
        "references": references,
        "patches": patches,
        "exclusions": exclusions,
        "collisions": collisions,
        "actions": actions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("golden", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    truth = parse_report(args.golden.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(truth, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

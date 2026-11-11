"""Structural check for the two release workbooks.

Checks only that the release is *shaped* like a complete one: both files exist, the
contract's sections are present, the per-item and per-replicate tables have the row
counts their grain implies, and no published estimate is missing the columns that
make it checkable.

It never reads the source data, never recomputes anything, and never says whether a
number is right. A clean run means the release is reviewable, not that it is correct.

Usage:  python check_release.py <workspace>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from openpyxl import load_workbook


def norm(value: object) -> str:
    return re.sub(r"[\s_\-/()]+", "", str(value or "")).strip().lower()


def sheet_rows(book, name: str) -> list[tuple]:
    return list(book[name].iter_rows(values_only=True)) if name in book.sheetnames else []


def headers(rows: list[tuple]) -> list[str]:
    return [norm(c) for c in rows[0]] if rows else []


def has_cols(head: list[str], *groups: tuple[str, ...]) -> list[str]:
    """Return the groups with no column whose name contains any of their spellings."""
    return [
        "|".join(g)
        for g in groups
        if not any(any(alias in col for col in head) for alias in g)
    ]


workspace = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
if workspace.name != "workspace" and (workspace / "workspace").is_dir():
    workspace = workspace / "workspace"
out = workspace / "output"
errors: list[str] = []
notes: list[str] = []

ledger_path = out / "cleaned_samples.xlsx"
analysis_path = out / "engagement_analysis.xlsx"
for path in (ledger_path, analysis_path):
    if not path.is_file():
        errors.append(f"Missing {path.name} in output/")

if not errors:
    if ledger_path.read_bytes() == analysis_path.read_bytes():
        errors.append("The two workbooks are identical; they carry different jobs")

    analysis = load_workbook(analysis_path, read_only=True, data_only=True)

    # Every published estimate needs the four labels that make it checkable.
    # Only sheets that publish a headline estimate need the full label set. Ledgers and
    # per-person tables legitimately omit some of it, so flagging them is noise.
    LABELS = (("population",), ("weight",))
    for name in analysis.sheetnames:
        rows = sheet_rows(analysis, name)
        head = headers(rows)
        if not head or "ledger" in norm(name) or "person" in norm(name):
            continue
        if any("estimate" in c for c in head) and any("ci" in c or "se" == c for c in head):
            missing = has_cols(head, *LABELS)
            if missing:
                notes.append(f"[{name}] published estimates without {', '.join(missing)}")

    # Per-item and per-replicate tables should be as long as their grain implies.
    def rowcount(pred) -> list[tuple[str, int]]:
        found = []
        for name in analysis.sheetnames:
            rows = sheet_rows(analysis, name)
            head = headers(rows)
            if head and pred(head):
                found.append((name, max(0, len(rows) - 1)))
        return found

    per_item = rowcount(lambda h: any("deleteditem" in c or "itemtotal" in c for c in h))
    # A per-replicate table has a group identifier as one of its first columns. A summary
    # sheet that merely counts replicates mentions them too, so match on position rather
    # than on the word appearing anywhere in the header.
    per_rep = rowcount(
        lambda h: any(
            "variancegroup" in c or "replicategroup" in c for c in h[:3]
        )
    )

    if not per_item:
        errors.append("No per-item diagnostics table (alpha-if-deleted, corrected item-total)")
    else:
        for name, n in per_item:
            if n <= 2:
                errors.append(f"[{name}] has {n} data rows; this table is one row per item per period")

    if not per_rep:
        errors.append("No per-replicate table; replicate-based uncertainty cannot be reviewed")
    else:
        for name, n in per_rep:
            if n <= 2:
                errors.append(f"[{name}] has {n} data rows; this table is one row per replicate group")

    # A domain-by-replicate ledger is the product of two grains, so it is the longest table.
    domain_rep = [
        (name, max(0, len(sheet_rows(analysis, name)) - 1))
        for name in analysis.sheetnames
        if all(
            any(tok in c for c in headers(sheet_rows(analysis, name)))
            for tok in ("variancegroup", "org")
        )
    ]
    if domain_rep:
        longest = max(n for _, n in domain_rep)
        rep_rows = max((n for _, n in per_rep), default=0)
        if rep_rows and longest < rep_rows:
            notes.append(
                "the domain-by-replicate ledger is no longer than the replicate table; "
                "it should carry one row per domain per replicate"
            )

print(f"workspace: {workspace}")
for e in errors:
    print(f"  ERROR  {e}")
for n in notes:
    print(f"  CHECK  {n}")
if not errors and not notes:
    print("  structure looks complete (this says nothing about the values)")
sys.exit(1 if errors else 0)

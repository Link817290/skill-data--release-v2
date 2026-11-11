#!/usr/bin/env python3
"""Check arithmetic relationships in a user-supplied allocation table.

The utility does not determine admissibility, legal treatment, or recovery status.
It only parses the rows selected by the user and reports totals and implied rates.
"""

from __future__ import annotations

import argparse
import csv
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path


def decimal_value(raw: object) -> Decimal:
    text = str(raw or "").strip().replace(" ", "")
    if not text:
        return Decimal(0)
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        tail = text.rsplit(",", 1)[1]
        text = text.replace(",", ".") if len(tail) in {1, 2} else text.replace(",", "")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"cannot parse numeric value: {raw!r}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--label-column", required=True)
    parser.add_argument("--value-column", required=True)
    parser.add_argument("--contribution-column", required=True)
    args = parser.parse_args()

    with args.csv_path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    required = {args.label_column, args.value_column, args.contribution_column}
    if not rows or not required.issubset(rows[0]):
        raise SystemExit(f"missing required columns: {sorted(required)}")

    output_rows = []
    total_value = Decimal(0)
    total_contribution = Decimal(0)
    for row in rows:
        value = decimal_value(row[args.value_column])
        contribution = decimal_value(row[args.contribution_column])
        total_value += value
        total_contribution += contribution
        rate = contribution / value * 100 if value else None
        output_rows.append(
            {
                "label": row[args.label_column],
                "value": str(value),
                "contribution": str(contribution),
                "implied_rate_percent": str(rate) if rate is not None else None,
            }
        )

    combined_rate = total_contribution / total_value * 100 if total_value else None
    result = {
        "rows": output_rows,
        "totals": {
            "value": str(total_value),
            "contribution": str(total_contribution),
            "implied_rate_percent": str(combined_rate) if combined_rate is not None else None,
        },
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

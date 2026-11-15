#!/usr/bin/env python3
"""Derive compact scorer anchors from a completed canonical audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def derive(golden: Path) -> dict:
    artifact = json.loads(golden.read_text(encoding="utf-8"))
    findings = artifact.get("findings")
    if not isinstance(findings, list) or not findings:
        raise ValueError("reference audit has no findings")

    anchors = []
    dimension_anchors: dict[str, list[str]] = {}
    accepted_evidence = {}
    for finding in findings:
        anchor = finding["reference_anchor"]
        dimension = finding["control_dimension"]
        if anchor in anchors:
            raise ValueError(f"duplicate reference anchor: {anchor}")
        anchors.append(anchor)
        dimension_anchors.setdefault(dimension, []).append(anchor)

        documents = set()
        pages = set()
        for citation in finding.get("evidence", []):
            documents.add(str(citation["document"]))
            pages.add(int(citation["pdf_page"]))
        if not documents or not pages:
            raise ValueError(f"anchor has no evidence locations: {anchor}")
        accepted_evidence[anchor] = {
            "documents": sorted(documents),
            "pdf_pages": sorted(pages),
        }

    return {
        "schema": "haccp-audit-ground-truth",
        "golden_sha256": hashlib.sha256(golden.read_bytes()).hexdigest(),
        "anchor_ids": anchors,
        "dimension_anchors": dimension_anchors,
        "accepted_evidence": accepted_evidence,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("golden", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(derive(args.golden), indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

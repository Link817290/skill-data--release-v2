#!/usr/bin/env python3
"""Derive integrity anchors from original inputs and the reference output."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import fitz


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def page_record(page: fitz.Page) -> dict:
    return {
        "rect": [round(float(value), 3) for value in page.rect],
        "rotation": page.rotation,
        "text_chars": len(page.get_text()),
        "widgets": len(list(page.widgets() or [])),
        "annotations": len(list(page.annots() or [])),
    }


def main() -> int:
    package = Path(__file__).resolve().parents[2]
    golden = package / "golden" / "sanitized_onboarding_packet.pdf"
    materials = package / "task" / "environment" / "workspace" / "materials"
    names = ["employment_application_record.pdf", "withholding_record.pdf", "employment_eligibility_record.pdf"]

    source_pages = []
    for name in names:
        with fitz.open(materials / name) as document:
            source_pages.extend(page_record(page) for page in document)

    with fitz.open(golden) as document:
        golden_pages = [page_record(page) for page in document]
        metadata = document.metadata or {}

    result = {
        "locked_inputs": {name: sha256(materials / name) for name in names},
        "source_pages": source_pages,
        "golden_pages": golden_pages,
        "golden_metadata": {
            key: metadata.get(key, "")
            for key in ("title", "author", "subject", "keywords", "creator", "producer")
        },
        "scoring": {
            "strict": "one weighted continuous score after readability, source-packet, and direct-identifier gates",
            "reward_alias": "strict",
        },
    }
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else package / "task" / "tests" / "ground_truth.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

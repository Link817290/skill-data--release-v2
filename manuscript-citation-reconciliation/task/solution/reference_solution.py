#!/usr/bin/env python3
"""Derive the citation reconciliation report from the supplied DOCX files."""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET


NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
REF_HEADING = "参考文献"
END_HEADINGS = {"致谢", "Acknowledgments", "Acknowledgements", "硕士期间参加的科研项目"}
BRACKET_RE = re.compile(r"[\[［【]\s*([^\]］】]+?)\s*[\]］】]")


def paragraph_texts(docx_path: Path) -> list[str]:
    with ZipFile(docx_path) as archive:
        xml = archive.read("word/document.xml")
    root = ET.fromstring(xml)
    paragraphs = root.findall(".//w:body/w:p", NS)
    return ["".join(node.text or "" for node in para.findall(".//w:t", NS)) for para in paragraphs]


def expand_label_group(group: str) -> list[int]:
    values: list[int] = []
    for token in re.split(r"[,，;；、~～至\-–—]", group):
        token = token.strip()
        if token.isdigit():
            values.append(int(token))
    return values


def citation_labels(text: str) -> list[int]:
    labels: list[int] = []
    for match in BRACKET_RE.finditer(text):
        group = match.group(1)
        if not re.fullmatch(r"\s*\d+(?:\s*[,，;；、~～至\-–—]\s*\d+)*\s*", group):
            continue
        labels.extend(expand_label_group(group))
    return labels


def citation_evidence(paragraphs: list[str], end: int) -> tuple[list[dict], list[dict]]:
    """Record accepted and rejected bracket expressions with source paragraphs."""
    accepted: list[dict] = []
    ignored: list[dict] = []
    for index, text in enumerate(paragraphs[:end]):
        for match in BRACKET_RE.finditer(text):
            group = match.group(1)
            literal = match.group(0)
            if re.fullmatch(r"\s*\d+(?:\s*[,，;；、~～至\-–—]\s*\d+)*\s*", group):
                accepted.append(
                    {
                        "paragraph_index": index,
                        "literal": literal,
                        "labels": expand_label_group(group),
                        "paragraph_text": text,
                    }
                )
            else:
                ignored.append(
                    {
                        "paragraph_index": index,
                        "literal": literal,
                        "paragraph_text": text,
                        "reason": "non_numeric_expression",
                    }
                )
    return accepted, ignored


def reference_identity_parts(text: str) -> dict[str, str]:
    """Expose the conservative author/title strings used for peer identity."""
    normalized = unicodedata.normalize("NFKC", text).strip().lower()
    author, separator, remainder = normalized.partition(".")
    if not separator:
        remainder = ""

    def clean(value: str) -> str:
        return " ".join(re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", value).split())

    title = remainder.split("[", 1)[0] if separator else normalized
    return {"author": clean(author), "title": clean(title)}


def reference_identity(text: str) -> str:
    """Build a conservative cross-revision identity from author block and title."""
    parts = reference_identity_parts(text)
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", parts["author"] + "|" + parts["title"])


def audit_file(path: Path) -> dict:
    paragraphs = paragraph_texts(path)
    heading_indexes = [i for i, text in enumerate(paragraphs) if text.strip() == REF_HEADING]
    if not heading_indexes:
        raise ValueError(f"missing exact bibliography heading in {path.name}")
    ref_start = heading_indexes[-1]
    ref_end = len(paragraphs)
    for index in range(ref_start + 1, len(paragraphs)):
        if paragraphs[index].strip() in END_HEADINGS:
            ref_end = index
            break

    reference_items = [
        (index, text.strip())
        for index, text in enumerate(paragraphs[ref_start + 1 : ref_end], ref_start + 1)
        if text.strip()
    ]
    reference_texts = [text for _index, text in reference_items]
    reference_records = [
        {"reference_number": number, "reference_text": text, "bibliography_paragraph_index": index}
        for number, (index, text) in enumerate(reference_items, start=1)
    ]
    body = "\n".join(paragraphs[:ref_start])
    cited = sorted(set(citation_labels(body)))
    citation_occurrences, ignored_brackets = citation_evidence(paragraphs, ref_start)
    reference_numbers = set(range(1, len(reference_texts) + 1))
    cited_numbers = set(cited)

    unmatched_references = [
        {
            "reference_number": number,
            "reference_text": reference_texts[number - 1],
            "issue": "bibliography_entry_not_cited_in_body",
            "evidence": {"bibliography_paragraph_index": reference_items[number - 1][0]},
        }
        for number in sorted(reference_numbers - cited_numbers)
    ]
    unmatched_citations = [
        {
            "citation_label": number,
            "issue": "body_citation_has_no_bibliography_entry",
        }
        for number in sorted(cited_numbers - reference_numbers)
    ]
    return {
        "file": path.name,
        "bibliography_count": len(reference_texts),
        "cited_labels": cited,
        "unmatched_references": unmatched_references,
        "unmatched_citations": unmatched_citations,
        "citation_occurrences": citation_occurrences,
        "ignored_bracket_expressions": ignored_brackets,
        "boundary": {
            "bibliography_heading_paragraph_index": ref_start,
            "bibliography_end_paragraph_index": ref_end,
        },
        "_reference_texts": reference_texts,
        "_reference_records": reference_records,
    }


def attach_cross_file_reviews(manuscripts: list[dict]) -> None:
    """Bind each gap to the same evidence in the other supplied revisions."""
    reference_index: dict[str, list[tuple[str, dict, bool]]] = {}
    identity_index: dict[str, list[tuple[str, dict, bool]]] = {}
    cited_by_file = {item["file"]: set(item["cited_labels"]) for item in manuscripts}
    for item in manuscripts:
        for peer in item["_reference_records"]:
            number = peer["reference_number"]
            text = peer["reference_text"]
            reference_index.setdefault(text, []).append(
                (item["file"], peer, number in cited_by_file[item["file"]])
            )
            identity_index.setdefault(reference_identity(text), []).append(
                (item["file"], peer, number in cited_by_file[item["file"]])
            )

    all_files = sorted(item["file"] for item in manuscripts)
    for item in manuscripts:
        for record in item["unmatched_references"]:
            text = record["reference_text"]
            peers = reference_index.get(text, [])
            peers = [peer for peer in peers if peer[0] != item["file"]]
            peer_files = sorted({file for file, _peer, _cited in peers})
            cited_peer_files = sorted({file for file, _peer, cited in peers if cited})
            identity_peers = [
                peer for peer in identity_index.get(reference_identity(text), [])
                if peer[0] != item["file"] and peer[0] not in peer_files
            ]
            identity_files = sorted({file for file, _peer, _cited in identity_peers})
            identity_cited_files = sorted({file for file, _peer, cited in identity_peers if cited})
            evidence_source = peers if peers else identity_peers
            evidence_kind = "exact_text" if peers else "author_title_identity"
            peer_evidence = [
                {
                    "file": file,
                    "reference_number": peer["reference_number"],
                    "bibliography_paragraph_index": peer["bibliography_paragraph_index"],
                    "cited_in_body": bool(cited),
                    "match_type": evidence_kind,
                }
                for file, peer, cited in sorted(
                    evidence_source, key=lambda value: (value[0], value[1]["reference_number"])
                )
            ]
            if identity_cited_files:
                status = "variant_in_other_revision"
                compare_files = identity_files
                action = "verify_metadata_transfer"
                basis = "same_work_with_normalized_author_title_match"
            elif identity_files:
                status = "persistent_variant_gap"
                compare_files = identity_files
                action = "escalate_editorial_decision"
                basis = "same_work_uncited_in_all_revisions"
            elif not peer_files and not identity_files:
                status = "version_specific"
                compare_files = []
                action = "verify_version_scope"
                basis = "entry_absent_from_other_revisions"
            elif cited_peer_files:
                status = "resolved_in_other_revision"
                compare_files = peer_files
                action = "check_revision_transfer"
                basis = "same_entry_cited_in_other_revision"
            else:
                status = "persistent_gap"
                compare_files = peer_files
                action = "escalate_editorial_decision"
                basis = "same_entry_uncited_in_all_revisions"
            record["review"] = {
                "status": status,
                "compare_files": compare_files,
                "action": action,
                "basis": basis,
                "peer_evidence": peer_evidence,
                "identity_evidence": {
                    "local": reference_identity_parts(text),
                    "peers": [
                        {
                            "file": file,
                            "reference_number": peer["reference_number"],
                            **reference_identity_parts(peer["reference_text"]),
                            "match_type": evidence_kind,
                        }
                        for file, peer, _cited in sorted(
                            evidence_source, key=lambda value: (value[0], value[1]["reference_number"])
                        )
                    ],
                },
            }
        for record in item["unmatched_citations"]:
            label = record["citation_label"]
            compare_files = sorted(
                file for file in all_files
                if file != item["file"] and label in cited_by_file[file]
            )
            record["review"] = {
                "status": "out_of_range_label",
                "compare_files": compare_files,
                "action": "verify_numbering_or_missing_entry",
                "basis": "body_label_has_no_local_bibliography_entry",
                "peer_evidence": [],
            }


def build_report(workspace: Path) -> dict:
    material_dir = workspace / "materials"
    files = sorted(material_dir.glob("*.docx"))
    if not files:
        raise ValueError(f"no DOCX materials found under {material_dir}")
    manuscripts = [audit_file(path) for path in files]
    attach_cross_file_reviews(manuscripts)
    for item in manuscripts:
        item.pop("_reference_texts", None)
        item.pop("_reference_records", None)
    return {
        "report_version": "1.1",
        "manuscripts": manuscripts,
        "summary": {
            "manuscript_count": len(manuscripts),
            "unmatched_reference_count": sum(len(item["unmatched_references"]) for item in manuscripts),
            "unmatched_citation_count": sum(len(item["unmatched_citations"]) for item in manuscripts),
        },
    }


def main() -> int:
    workspace = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/workspace")
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else workspace / "output/citation_audit.json"
    try:
        report = build_report(workspace)
    except (OSError, BadZipFile, KeyError, ET.ParseError, ValueError) as exc:
        print(f"reference_builder: {exc}", file=sys.stderr)
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

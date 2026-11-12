#!/usr/bin/env python3
"""Condition-blind item checks for a citation reconciliation JSON report."""

from __future__ import annotations

import importlib.util
import copy
import hashlib
import json
import re
import sys
from pathlib import Path


EXPECTED_TOP = {"report_version", "manuscripts", "summary"}
REQUIRED_MANUSCRIPT = {
    "file",
    "bibliography_count",
    "cited_labels",
    "unmatched_references",
    "unmatched_citations",
    "citation_occurrences",
    "ignored_bracket_expressions",
    "boundary",
}
REF_ISSUE = "bibliography_entry_not_cited_in_body"
CITE_ISSUE = "body_citation_has_no_bibliography_entry"
REVIEW_FIELDS = {"status", "compare_files", "action", "basis", "peer_evidence"}


def load_deriver():
    test_dir = Path(__file__).resolve().parent
    candidates = [test_dir / "material_parser.py"]   # the verifier's own parser only
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise FileNotFoundError("material-derived parser is not available")
    spec = importlib.util.spec_from_file_location("citation_deriver", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load independent material parser")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def material_paragraphs(deriver, workspace: Path) -> dict:
    """Normalized paragraph text of every supplied revision, for provenance checks."""
    reader = getattr(deriver, "paragraph_texts", None)
    if reader is None:
        return {}
    return {path.name: [norm(text) for text in reader(path)]
            for path in sorted((workspace / "materials").glob("*.docx"))}


MATERIAL_SHA256 = Path(__file__).resolve().parent / "material_sha256.json"


def locate_workspace(submission: Path) -> Path:
    """The expected report is derived from the read-only, hash-gated materials copy under tests/materials,
    never from the agent-writable /workspace/materials."""
    tests = Path(__file__).resolve().parent
    if not (tests / "materials").is_dir():
        raise FileNotFoundError("tests/materials not found")
    listed = json.loads(MATERIAL_SHA256.read_text(encoding="utf-8"))["files"]
    present = {p.name for p in (tests / "materials").glob("*.docx")}
    if present != set(listed):
        raise ValueError(f"tests/materials does not match material_sha256.json: {sorted(present ^ set(listed))}")
    for name, digest in listed.items():
        if hashlib.sha256((tests / "materials" / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"material integrity failure: {name}")
    return tests


def load_submission(path: Path) -> dict:
    target = path
    if target.is_dir():
        target = target / "output/citation_audit.json"
    return json.loads(target.read_text(encoding="utf-8"))


def norm(value: object) -> str:
    return " ".join(str(value).split())


# --- carrier repairs ------------------------------------------------------
# instruction.md and the mounted skills prescribe the container names
# (`citation_occurrences`, `ignored_bracket_expressions`, `boundary`) and the
# controlled value `non_numeric_expression`, but never the key that carries a
# record's source paragraph text nor the key that carries its exclusion reason.
# Resolving those two by alias judges an output on its evidence rather than on
# Golden's private spelling. Applied to every rollout alike.
PARAGRAPH_TEXT_KEYS = ("paragraph_text", "source_paragraph_text", "source_paragraph", "paragraph", "text")
REASON_KEYS = ("reason", "exclusion_reason")


def field(record: object, keys: tuple) -> object:
    if not isinstance(record, dict):
        return None
    for key in keys:
        if key in record:
            return record[key]
    return None


def verbatim(got: object, wanted: str) -> bool:
    """Byte-for-byte entry text. Golden trims the source paragraph's edge
    whitespace; a report that keeps the paragraph's own trailing space is
    quoting the supplied entry more literally, not less. Inner text stays exact."""
    return isinstance(got, str) and (got == wanted or got.strip() == wanted)


def paragraph_text(record: object) -> object:
    return field(record, PARAGRAPH_TEXT_KEYS)


def exclusion_reason(record: object) -> object:
    return field(record, REASON_KEYS)


# The controlled value is `non_numeric_expression`; its spelling with spaces or
# hyphens ("non-numeric expression") or another case names the same value.
# Compare the value on letters/digits only, and let a differently worded
# reason lose only the ignored-expression credit instead of voiding the report.
def reason_canon(value: object) -> object:
    if not isinstance(value, str):
        return value
    return "".join(ch for ch in value.lower() if ch.isalnum())


LABEL_STRING = re.compile(r"^\s*\d+(\s*[,;，；、\s]\s*\d+)*\s*$")


def occurrence_labels(record: object) -> object:
    """Labels as a tuple of ints; digit strings ("7" or "1, 2") carry the same labels."""
    value = record.get("labels") if isinstance(record, dict) else None
    if isinstance(value, str):
        return tuple(int(x) for x in re.findall(r"\d+", value)) if LABEL_STRING.match(value) else ("<invalid>", value)
    if isinstance(value, list):
        out = []
        for x in value:
            if isinstance(x, bool):
                return ("<invalid>",)
            if isinstance(x, int):
                out.append(x)
            elif isinstance(x, str) and x.strip().isdigit():
                out.append(int(x.strip()))
            else:
                return ("<invalid>",)
        return tuple(out)
    return ("<invalid>",)


def quote_norm(value: object) -> object:
    """Paragraph text compared with whitespace runs collapsed; the words stay verbatim."""
    return norm(value) if isinstance(value, str) else value


def identity_norm(value: object, key: object = None) -> object:
    """Compare identity evidence on the normalization the skill actually names.

    The skill asks for author/title strings normalized for "Unicode case,
    spacing, and punctuation" and does not say whether the normal form keeps
    inner spaces. Golden keeps them; outputs vary. Compare case/space/
    punctuation-insensitively so the decision follows the identity, not the
    spelling of the normal form.
    """
    if isinstance(value, dict):
        return {k: identity_norm(v, k) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [identity_norm(v, key) for v in value]
    if key in ("author", "title") and isinstance(value, str):
        return "".join(ch for ch in value.lower() if ch.isalnum())
    return value


PEER_EVIDENCE_KEYS = ("file", "reference_number", "bibliography_paragraph_index", "cited_in_body",
                      "citation_label", "citation_paragraph_indices", "match_type")
IDENTITY_PEER_KEYS = ("file", "reference_number", "author", "title", "match_type")
IDENTITY_LOCAL_KEYS = ("author", "title")


def project(record: object, keys: tuple) -> object:
    """Keep the contract's required evidence keys and ignore additional ones.

    `audit-report-schema` allows "an additional non-semantic note ... if the
    required fields remain unambiguous", so an output that carries more
    evidence than the contract asks for must not lose the credit.
    """
    if not isinstance(record, dict):
        return record
    return {key: record[key] for key in keys if key in record}


# An entry with no publication-type bracket ("... unsupervised learning.
# Technical report, OpenAI.") has no marked title end; Golden reads the title
# up to "[", which runs on into the venue. Ending the title at the first
# sentence stop is the same work's title read at the other natural boundary
# and the skill fixes neither. Accept it as that entry's title.
def title_alternates(deriver, workspace: Path) -> dict:
    out: dict = {}
    reader = getattr(deriver, "audit_file", None)
    parts = getattr(deriver, "reference_identity_parts", None)
    if reader is None or parts is None:
        return out
    for path in sorted((workspace / "materials").glob("*.docx")):
        for record in reader(path).get("_reference_records", []):
            text = record["reference_text"]
            golden_title = parts(text)["title"]
            head, dot, rest = text.partition(".")
            if not dot:
                continue
            first = re.split(r"\.\s", rest.split("[", 1)[0].strip(), maxsplit=1)[0]
            alt = parts(head + ". " + first + ".")["title"]
            if canon(alt) != canon(golden_title):
                out[(path.name, record["reference_number"])] = (canon(alt), golden_title)
    return out


def align_titles(report: dict, alternates: dict) -> dict:
    """Map a first-sentence title onto Golden's spelling for that same entry."""
    if not alternates:
        return report
    report = copy.deepcopy(report)

    def fix(target: object, filename: object, number: object) -> None:
        hit = alternates.get((filename, number))
        if hit and isinstance(target, dict) and canon(target.get("title", "")) == hit[0]:
            target["title"] = hit[1]

    for item in report.get("manuscripts") or []:
        if not isinstance(item, dict):
            continue
        for record in item.get("unmatched_references") or []:
            review = record.get("review") if isinstance(record, dict) else None
            identity = review.get("identity_evidence") if isinstance(review, dict) else None
            if not isinstance(identity, dict):
                continue
            fix(identity.get("local"), item.get("file"), record.get("reference_number"))
            for peer in identity.get("peers") or []:
                if isinstance(peer, dict):
                    fix(peer, peer.get("file"), peer.get("reference_number"))
    return report


def expected_records(report: dict) -> tuple[set[tuple], set[tuple]]:
    refs: set[tuple] = set()
    cites: set[tuple] = set()
    for item in report["manuscripts"]:
        filename = item["file"]
        for record in item["unmatched_references"]:
            refs.add((filename, record["reference_number"], record["issue"], record.get("reference_text", "")))
        for record in item["unmatched_citations"]:
            cites.add((filename, record["citation_label"], record["issue"]))
    return refs, cites


def review_records(report: dict) -> dict[tuple, tuple]:
    """Return canonical review decisions keyed by their local discrepancy."""
    records: dict[tuple, tuple] = {}
    for item in report["manuscripts"]:
        filename = item["file"]
        for record in item["unmatched_references"]:
            review = record.get("review", {})
            records[("reference", filename, record.get("reference_number"), record.get("issue"))] = (
                review.get("status"),
                tuple(sorted(review.get("compare_files", []))),
                review.get("action"),
                review.get("basis"),
                peer_evidence_key(review.get("peer_evidence", [])),
                identity_evidence_key(review.get("identity_evidence", {})),
            )
        for record in item["unmatched_citations"]:
            review = record.get("review", {})
            records[("citation", filename, record.get("citation_label"), record.get("issue"))] = (
                review.get("status"),
                tuple(sorted(review.get("compare_files", []))),
                review.get("action"),
                review.get("basis"),
                peer_evidence_key(review.get("peer_evidence", [])),
            )
    return records


def review_decisions(report: dict) -> dict[tuple, tuple]:
    """Compare the review decision, leaving identity parsing to D03/D04."""
    decisions = {}
    for key, value in review_records(report).items():
        kind, filename, local_id, _issue = key
        decisions[("ref" if kind == "reference" else "cit", filename, local_id)] = value[:5]
    return decisions


def peer_evidence_key(value: object) -> tuple:
    """Canonicalize evidence objects so JSON key order cannot affect scoring."""
    if not isinstance(value, list):
        return ("<invalid>",)
    rows = []
    for item in value:
        if isinstance(item, dict):
            kept = project(item, PEER_EVIDENCE_KEYS)
            rows.append(tuple(sorted((str(key), json.dumps(val, ensure_ascii=False, sort_keys=True)) for key, val in kept.items())))
        else:
            rows.append(("<invalid>", json.dumps(item, ensure_ascii=False, sort_keys=True)))
    return tuple(sorted(rows))


def identity_evidence_key(value: object) -> str:
    """Canonicalize the local and peer identity evidence object."""
    if isinstance(value, dict):
        peers = value.get("peers")
        value = {"local": project(value.get("local"), IDENTITY_LOCAL_KEYS),
                 "peers": [project(peer, IDENTITY_PEER_KEYS) for peer in peers] if isinstance(peers, list) else peers}
    value = identity_norm(value)
    if isinstance(value, dict) and isinstance(value.get("peers"), list):
        # peer_evidence is compared as a set; its identity twin must be too (instruction fixes no order)
        value["peers"] = sorted(value["peers"], key=lambda peer: json.dumps(peer, ensure_ascii=False, sort_keys=True))
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def validate_review(record: object, filename: object, kind: str, errors: list[str]) -> None:
    review = record.get("review") if isinstance(record, dict) else None
    if not isinstance(review, dict) or not REVIEW_FIELDS.issubset(review):
        errors.append(f"{filename}: malformed review for unmatched {kind}")
        return
    if not all(isinstance(review.get(key), str) and review.get(key) for key in ("status", "action", "basis")):
        errors.append(f"{filename}: review status/action/basis must be non-empty strings")
    compare_files = review.get("compare_files")
    if not isinstance(compare_files, list) or not all(isinstance(value, str) for value in compare_files):
        errors.append(f"{filename}: review compare_files must be an array of strings")
    peer_evidence = review.get("peer_evidence")
    if not isinstance(peer_evidence, list) or not all(isinstance(value, dict) for value in peer_evidence):
        errors.append(f"{filename}: review peer_evidence must be an array of objects")
    if kind == "reference":
        identity = review.get("identity_evidence")
        if not isinstance(identity, dict):
            errors.append(f"{filename}: reference review identity_evidence must be an object")
        else:
            local = identity.get("local")
            peers = identity.get("peers")
            if not isinstance(local, dict) or not all(isinstance(local.get(key), str) and local.get(key) for key in ("author", "title")):
                errors.append(f"{filename}: identity_evidence.local must contain author and title")
            if not isinstance(peers, list) or not all(isinstance(value, dict) for value in peers):
                errors.append(f"{filename}: identity_evidence.peers must be an array of objects")


def report_shape(report: object, material_files: set[str]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(report, dict):
        return False, ["top-level JSON value must be an object"]
    missing = EXPECTED_TOP - set(report)
    errors.extend(f"missing top-level key: {key}" for key in sorted(missing))
    manuscripts = report.get("manuscripts")
    if not isinstance(manuscripts, list) or not manuscripts:
        errors.append("manuscripts must be a non-empty array")
        return False, errors
    names: list[str] = []
    for item in manuscripts:
        if not isinstance(item, dict):
            errors.append("each manuscript item must be an object")
            continue
        names.append(item.get("file"))
        missing_item = REQUIRED_MANUSCRIPT - set(item)
        errors.extend(f"{item.get('file')}: missing {key}" for key in sorted(missing_item))
        for key in ("cited_labels", "unmatched_references", "unmatched_citations", "citation_occurrences", "ignored_bracket_expressions"):
            if key in item and not isinstance(item[key], list):
                errors.append(f"{item.get('file')}: {key} must be an array")
        boundary = item.get("boundary")
        if not isinstance(boundary, dict) or not all(isinstance(boundary.get(key), int) and boundary.get(key) >= 0 for key in ("bibliography_heading_paragraph_index", "bibliography_end_paragraph_index")):
            errors.append(f"{item.get('file')}: boundary must contain non-negative integer indexes")
        count = item.get("bibliography_count")
        if not isinstance(count, int) or count < 0:
            errors.append(f"{item.get('file')}: bibliography_count must be a non-negative integer")
        for record in item.get("unmatched_references", []):
            if not isinstance(record, dict) or not isinstance(record.get("reference_number"), int):
                errors.append(f"{item.get('file')}: malformed unmatched reference")
            elif isinstance(count, int) and not 1 <= record["reference_number"] <= count:
                errors.append(f"{item.get('file')}: reference number outside bibliography range")
            validate_review(record, item.get("file"), "reference", errors)
        for record in item.get("unmatched_citations", []):
            if not isinstance(record, dict) or not isinstance(record.get("citation_label"), int):
                errors.append(f"{item.get('file')}: malformed unmatched citation")
            validate_review(record, item.get("file"), "citation", errors)
        for record in item.get("citation_occurrences", []):
            if (
                not isinstance(record, dict)
                or not isinstance(record.get("paragraph_index"), int)
                or not isinstance(record.get("literal"), str)
                or not isinstance(record.get("labels"), (list, str))
                or not isinstance(paragraph_text(record), str)
            ):
                errors.append(f"{item.get('file')}: malformed citation occurrence")
        for record in item.get("ignored_bracket_expressions", []):
            if (
                not isinstance(record, dict)
                or not isinstance(record.get("paragraph_index"), int)
                or not isinstance(record.get("literal"), str)
                or not isinstance(paragraph_text(record), str)
                or not (isinstance(exclusion_reason(record), str) and exclusion_reason(record).strip())
            ):
                errors.append(f"{item.get('file')}: malformed ignored bracket expression")
    if sorted(names, key=lambda value: (value is None, str(value))) != sorted(material_files) or len(names) != len(set(names)):
        errors.append("manuscript file coverage does not match supplied materials")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        errors.append("summary must be an object")
    return not errors, errors


def set_match_score(wanted: set[tuple], got: set[tuple]) -> float:
    """Score exact evidence rows with both recall and precision."""
    if not wanted:
        return 1.0 if not got else 0.0
    matched = len(wanted & got)
    recall = matched / len(wanted)
    precision = matched / len(got) if got else 0.0
    return recall * precision


def occurrence_key(filename: str, record: dict) -> tuple:
    return (
        filename,
        record.get("paragraph_index"),
        record.get("literal"),
        occurrence_labels(record),
        quote_norm(paragraph_text(record)),
    )


def ignored_key(filename: str, record: dict) -> tuple:
    return (
        filename,
        record.get("paragraph_index"),
        record.get("literal"),
        quote_norm(paragraph_text(record)),
        reason_canon(exclusion_reason(record)),
    )


def source_evidence_score(expected: dict, actual: dict) -> tuple[float, float, float]:
    expected_occ = {
        occurrence_key(item["file"], record)
        for item in expected["manuscripts"]
        for record in item.get("citation_occurrences", [])
    }
    actual_occ = {
        occurrence_key(item.get("file"), record)
        for item in actual["manuscripts"]
        for record in item.get("citation_occurrences", [])
    }
    expected_ignored = {
        ignored_key(item["file"], record)
        for item in expected["manuscripts"]
        for record in item.get("ignored_bracket_expressions", [])
    }
    actual_ignored = {
        ignored_key(item.get("file"), record)
        for item in actual["manuscripts"]
        for record in item.get("ignored_bracket_expressions", [])
    }
    occurrence = set_match_score(expected_occ, actual_occ)
    ignored = set_match_score(expected_ignored, actual_ignored)
    expected_boundaries = {
        (
            item["file"],
            item["boundary"].get("bibliography_heading_paragraph_index"),
            item["boundary"].get("bibliography_end_paragraph_index"),
        )
        for item in expected["manuscripts"]
    }
    actual_boundaries = {
        (
            item.get("file"),
            item.get("boundary", {}).get("bibliography_heading_paragraph_index"),
            item.get("boundary", {}).get("bibliography_end_paragraph_index"),
        )
        for item in actual["manuscripts"]
    }
    boundary = set_match_score(expected_boundaries, actual_boundaries)
    return occurrence, ignored, boundary


# --- evidenced deduction items --------------------------------------------
# Affirmative errors, each read against the derived report unit by unit.
# One damage instance per manuscript that carries the error, so a report that
# repeats a mistake in three revisions is charged three times.


def canon(value: object) -> str:
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def damage_instances(expected: dict, report: dict, paragraphs: dict | None = None) -> list[dict]:
    """Damage instances for evidenced deduction items.

    D01 non_body_bracket_admitted - the body-label set contains a label the
        body-prose scan does not produce (a bracket lifted from a table cell),
        which over-reports citations and suppresses a real uncited-entry finding.
    D02 reference_text_not_verbatim - a reported `reference_text` is not the
        supplied entry byte for byte (instruction.md: "preserve each reported
        `reference_text` exactly as supplied").
    D03 author_block_truncated - the normalized author block in
        `identity_evidence.local` is a strict prefix of the supplied author
        block (the trailing `et al` dropped), which manufactures peer identity
        matches the supplied entries do not support.
    D04 identity_local_not_derived - the normalized local author or title is
        neither the supplied value nor a prefix truncation of the author block
        (a truncated title, or the author/title split taken at the wrong point).
    D05 quote_attributed_to_wrong_record - a quotation reported under revision F
        is absent from every paragraph of F yet appears verbatim in another
        supplied revision. The report cites a record the text does not come
        from, which is the one failure a presence check cannot see. Charged
        only on that evidence: a paraphrase or edited quote (verbatim nowhere)
        is NOT charged, a quote that sits in the right revision under the wrong
        paragraph index is NOT charged, and an omitted quote is NOT charged -
        omissions are already priced by the coverage items.
    D06 summary_or_version_contradicts_report - `report_version` is present and
        is not the `1.1` instruction.md names, or a summary total is present and
        disagrees with the report's own manuscripts. A missing summary key is
        NOT charged: instruction.md names the totals but not their spelling.
    D07 cited_labels_under_reported - the body-label set omits labels the body
        prose does produce. The mirror image of D01: dropping real citations
        manufactures uncited-entry findings exactly as admitting bogus ones
        suppresses them.
    """
    instances: list[dict] = []
    paragraphs = paragraphs or {}
    manuscripts = report.get("manuscripts")
    if not isinstance(manuscripts, list):
        return instances
    actual_by_file = {item.get("file"): item for item in manuscripts if isinstance(item, dict)}
    for wanted in expected["manuscripts"]:
        filename = wanted["file"]
        got = actual_by_file.get(filename)
        if not isinstance(got, dict):
            continue
        labels = got.get("cited_labels")
        if isinstance(labels, list) and set(labels) - set(wanted["cited_labels"]):
            instances.append({"key": f"{filename}:non_body_bracket_admitted", "item_ids": ["D01"]})
        if isinstance(labels, list) and set(wanted["cited_labels"]) - set(labels):
            instances.append({"key": f"{filename}:cited_labels_under_reported", "item_ids": ["D07"]})
        wanted_refs = {record["reference_number"]: record for record in wanted["unmatched_references"]}
        got_refs = {record.get("reference_number"): record
                    for record in (got.get("unmatched_references") or []) if isinstance(record, dict)}
        shared = sorted(set(wanted_refs) & set(got_refs))
        if any(not verbatim(got_refs[number].get("reference_text"), wanted_refs[number]["reference_text"]) for number in shared):
            instances.append({"key": f"{filename}:reference_text_not_verbatim", "item_ids": ["D02"]})
        truncated = False
        not_derived = False
        for number in shared:
            wanted_local = wanted_refs[number]["review"]["identity_evidence"]["local"]
            review = got_refs[number].get("review")
            local = review.get("identity_evidence", {}).get("local") if isinstance(review, dict) else None
            local = local if isinstance(local, dict) else {}
            wanted_author, wanted_title = canon(wanted_local["author"]), canon(wanted_local["title"])
            author, title = canon(local.get("author", "")), canon(local.get("title", ""))
            if author != wanted_author:
                if author and wanted_author.startswith(author):
                    truncated = True
                else:
                    not_derived = True
            if title != wanted_title:
                not_derived = True
        if truncated:
            instances.append({"key": f"{filename}:author_block_truncated", "item_ids": ["D03"]})
        if not_derived:
            instances.append({"key": f"{filename}:identity_local_not_derived", "item_ids": ["D04"]})
        if quote_from_wrong_record(filename, got, paragraphs):
            instances.append({"key": f"{filename}:quote_attributed_to_wrong_record", "item_ids": ["D05"]})
    # Three required structural checks are multiplicative gates, one instance per
    # manuscript. Location compares only references the report actually lists, so
    # omissions remain priced by P06 rather than charged twice.
    for wanted in expected["manuscripts"]:
        filename = wanted["file"]
        got = actual_by_file.get(filename)
        if not isinstance(got, dict):
            continue
        wanted_refs = {(r["reference_number"], r["issue"]): r for r in wanted["unmatched_references"]}
        got_refs = {(r.get("reference_number"), r.get("issue")): r for r in (got.get("unmatched_references") or []) if isinstance(r, dict)}
        shared = wanted_refs.keys() & got_refs.keys()
        if any(got_refs[key].get("evidence", {}).get("bibliography_paragraph_index") !=
               wanted_refs[key].get("evidence", {}).get("bibliography_paragraph_index") for key in shared):
            instances.append({"key": f"{filename}:location_binding", "item_ids": ["D08"]})
        expected_ignored = {ignored_key(filename, r) for r in wanted.get("ignored_bracket_expressions", [])}
        actual_ignored = {ignored_key(filename, r) for r in got.get("ignored_bracket_expressions", [])}
        if expected_ignored != actual_ignored:
            instances.append({"key": f"{filename}:ignored_brackets", "item_ids": ["D09"]})
        boundary_keys = ("bibliography_heading_paragraph_index", "bibliography_end_paragraph_index")
        if tuple(got.get("boundary", {}).get(k) for k in boundary_keys) != tuple(wanted["boundary"].get(k) for k in boundary_keys):
            instances.append({"key": f"{filename}:boundary", "item_ids": ["D10"]})
    instances.extend(summary_contradiction(report))
    return instances


MIN_QUOTE_CHARS = 20


def reported_quotes(item: dict):
    """Every string the report presents as lifted from its manuscript's own text."""
    for key in ("citation_occurrences", "ignored_bracket_expressions"):
        for record in item.get(key) or []:
            if isinstance(record, dict):
                yield paragraph_text(record)
    for record in item.get("unmatched_references") or []:
        if isinstance(record, dict):
            yield record.get("reference_text")


def quote_from_wrong_record(filename: str, item: dict, paragraphs: dict) -> bool:
    own = paragraphs.get(filename)
    if not own:
        return False
    others = {name: text for name, text in paragraphs.items() if name != filename}
    for quote in reported_quotes(item):
        if not isinstance(quote, str):
            continue
        quote = norm(quote)
        # Short strings are not evidence of provenance; they collide across revisions.
        if len(quote) < MIN_QUOTE_CHARS:
            continue
        if any(quote in para for para in own):
            continue  # right revision - a wrong paragraph index is not this item's charge
        if any(any(quote in para for para in text) for text in others.values()):
            return True  # verbatim in a revision this record does not cite
        # verbatim nowhere: a paraphrase or an edited quote, charged elsewhere or not at all
    return False


SUMMARY_TOTALS = ("manuscript_count", "unmatched_reference_count", "unmatched_citation_count")


def summary_contradiction(report: dict) -> list[dict]:
    """One instance when the report's own headline contradicts its own body."""
    manuscripts = [item for item in (report.get("manuscripts") or []) if isinstance(item, dict)]
    recomputed = {
        "manuscript_count": len(manuscripts),
        "unmatched_reference_count": sum(len(item.get("unmatched_references") or []) for item in manuscripts),
        "unmatched_citation_count": sum(len(item.get("unmatched_citations") or []) for item in manuscripts),
    }
    version = report.get("report_version")
    bad = version is not None and version != "1.1"
    summary = report.get("summary")
    if not isinstance(summary, dict):
        bad = True
    else:
        bad = bad or any(summary.get(key) != recomputed[key] for key in SUMMARY_TOTALS)
    if bad:
        return [{"key": "report:summary_or_version_contradicts_report", "item_ids": ["D06"]}]
    return []


def score(submission: Path) -> dict:
    try:
        report = load_submission(submission)
        workspace = locate_workspace(submission)
        material_files = {path.name for path in (workspace / "materials").glob("*.docx")}
        shape_ok, shape_errors = report_shape(report, material_files)
        if not shape_ok:
            return {"gates": {"valid_json": True, "complete_file_coverage": False}, "damage_instances": [], "errors": shape_errors}
        deriver = load_deriver()
        expected = deriver.build_report(workspace)
        report = align_titles(report, title_alternates(deriver, workspace))
        # Summary and bibliography counts are required handoff data.  Compare
        # them with the parser-derived material so omission or invented totals
        # cannot receive a full score.
        expected_by_file = {item["file"]: item for item in expected["manuscripts"]}
        for item in report["manuscripts"]:
            source = expected_by_file.get(item.get("file"))
            if source is not None and item.get("bibliography_count") != source.get("bibliography_count"):
                return {"gates": {"valid_json": True, "complete_file_coverage": False},
                        "damage_instances": [], "errors": [
                            f"{item.get('file')}: bibliography_count does not match supplied material"]}
        expected_summary = expected.get("summary", {})
        summary = report.get("summary")
        if not isinstance(summary, dict) or any(summary.get(key) != expected_summary.get(key)
                                               for key in SUMMARY_TOTALS):
            return {"gates": {"valid_json": True, "complete_file_coverage": False},
                    "damage_instances": [], "errors": ["summary totals do not match supplied material"]}
        expected_refs, expected_cites = expected_records(expected)
        actual_refs, actual_cites = expected_records(report)
        expected_reviews = review_records(expected)
        actual_reviews = review_records(report)
        expected_decisions = review_decisions(expected)
        actual_decisions = review_decisions(report)

        expected_ref_keys = {(f, n, issue) for f, n, issue, _ in expected_refs}
        actual_ref_keys = {(f, n, issue) for f, n, issue, _ in actual_refs}
        expected_cite_keys = expected_cites
        actual_cite_keys = actual_cites
        matched_ref_keys = expected_ref_keys & actual_ref_keys
        matched_cite_keys = expected_cite_keys & actual_cite_keys
        expected_total = len(expected_ref_keys) + len(expected_cite_keys)
        submitted_total = len(actual_ref_keys) + len(actual_cite_keys)
        matched_total = len(matched_ref_keys) + len(matched_cite_keys)
        coverage = (matched_total / expected_total) if expected_total else 1.0
        precision = (matched_total / submitted_total) if submitted_total else (1.0 if expected_total == 0 else 0.0)
        discrepancy_coverage = coverage * precision

        matched_review_keys = {
            key for key, value in expected_reviews.items()
            if actual_reviews.get(key) == value
        }
        review_total = len(expected_reviews)
        cross_file_review = len(matched_review_keys) / review_total if review_total else 1.0
        review_decision = (sum(actual_decisions.get(key) == value for key, value in expected_decisions.items())
                           / len(expected_decisions)) if expected_decisions else 1.0

        expected_ref_text = {(f, n, issue): text for f, n, issue, text in expected_refs}
        actual_ref_text = {(f, n, issue): text for f, n, issue, text in actual_refs}
        text_scores = []
        for key in matched_ref_keys:
            wanted = expected_ref_text[key]
            got = actual_ref_text.get(key, "")
            if verbatim(got, wanted):
                text_scores.append(1.0)
            elif norm(got) == norm(wanted):
                text_scores.append(0.8)
            else:
                text_scores.append(0.0)
        evidence_binding = sum(text_scores) / len(expected_ref_keys) if expected_ref_keys else 1.0

        expected_locations = {
            (item["file"], record["reference_number"], record["issue"]): (
                record.get("evidence", {}).get("bibliography_paragraph_index")
                if isinstance(record.get("evidence"), dict) else None
            )
            for item in expected["manuscripts"]
            for record in item.get("unmatched_references", [])
        }
        actual_locations = {
            (item["file"], record.get("reference_number"), record.get("issue")): (
                record.get("evidence", {}).get("bibliography_paragraph_index")
                if isinstance(record.get("evidence"), dict) else None
            )
            for item in report["manuscripts"]
            for record in item.get("unmatched_references", [])
        }
        location_binding = (
            sum(actual_locations.get(key) == value for key, value in expected_locations.items())
            / len(expected_locations)
            if expected_locations else 1.0
        )

        occurrence_score, ignored_score, boundary_score = source_evidence_score(expected, report)

        return {
            "components": {
                "discrepancy_coverage": round(discrepancy_coverage, 6),
                "evidence_binding": round(evidence_binding, 6),
                "cross_file_review": round(cross_file_review, 6),
                "review_decision": round(review_decision, 6),
                "location_binding": round(location_binding, 6),
                "ignored_bracket_expressions": round(ignored_score, 6),
                "citation_occurrences": round(occurrence_score, 6),
                "boundary": round(boundary_score, 6),
            },
            "counts": {
                "expected_discrepancies": expected_total,
                "submitted_discrepancies": submitted_total,
                "matched_discrepancies": matched_total,
                "expected_reviews": review_total,
                "matched_reviews": len(matched_review_keys),
            },
            "gates": {"valid_json": True, "complete_file_coverage": True},
            "damage_instances": damage_instances(expected, report, material_paragraphs(deriver, workspace)),
        }
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, ValueError, RuntimeError) as exc:
        return {"gates": {"valid_json": False}, "damage_instances": [], "errors": [str(exc)]}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: report_checks.py SUBMISSION")
    print(json.dumps(score(Path(sys.argv[1])), ensure_ascii=False, indent=2))

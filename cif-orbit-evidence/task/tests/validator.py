#!/usr/bin/env python3
"""Deterministic scientific quality and completion scorer for orbit_evidence.json.

Usage: validator.py <answer>
  <answer> is orbit_evidence.json, or a directory holding it (rollout artifacts/ or task golden/).
  Materials are read from /workspace/materials, else the task's environment/workspace/materials.

The strict score is settled in the standard form
  final = positive_earned * retention
  positive_earned = sum(weight[P] * completion[P])      (weights from scoring_params.json or $SCORING_PARAMS)
  retention = prod over damage instances of min(coefficient[D] for D in the instance)

P01-P11 are the eleven scored dimensions of score_report(); completion is the dimension score clamped to
[0, 1]. Index dimensions carry register-substance scaling. Local scientific errors lose their
corresponding checks without discounting unrelated records or dimensions. D01 (a supplied CIF is missing or
its hash differs) fires as one damage instance. D02 (an adjudication that contradicts the register's own
numbers) fires as one damage instance. D03 (required register units are absent or unusable) fires once for coverage,
with every affected unit retained in the audit. Coefficients come from scoring_params.json. An unreadable or non-object
deliverable returns a ledger with every completion 0. Binary completion uses required business
evidence and scientific correctness independently of the strict weights.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from pathlib import Path
from semantic_judge import adjudicate


ROOT = Path(__file__).resolve().parent.parent


def locate_materials() -> Path:
    """The materials root the D01 integrity check compares against.

    In the task container the supplied CIFs live at /workspace/materials and that root is
    authoritative: a file removed, renamed or edited there must fire D01.  Falling through to
    the packaged copy whenever the live root looks incomplete would score a deleted material
    against a pristine substitute, so the packaged copy is used only when there is no live
    workspace at all - offline re-scoring of archived artifacts on a host - and $MATERIALS_DIR
    always wins when it is set.
    """
    override = os.environ.get("MATERIALS_DIR")
    if override:
        return Path(override)
    live = Path("/workspace/materials")
    if live.is_dir() or Path("/workspace").is_dir():
        return live
    return ROOT / "environment" / "workspace" / "materials"


MATERIALS = locate_materials()
EXPECTED = Path(__file__).resolve().parent / "ground_truth.json"
SOURCE_HASHES = {
    "structure_alpha.cif": "529a6c825990fbc40403d27b71ed4f627fbe398e4b0ef3caef05d780194277ea",
    "structure_beta.cif": "01a5a8567bc76c4c310b20b6a3c76026d21458473879fca2069a746f1ff771e9",
    "structure_gamma.cif": "ab74636cf462bf3ddffb2362cc7ab378183d7f0282fa028ffd0d6bf153433a65",
    "structure_delta.cif": "0a4e8a7aaa60f7d0c25bae06efed223676df8ad01c999a88e384cb5f817075bc",
}


def finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def equal(a, b, tol=1e-6) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, (int, float)) or isinstance(b, (int, float)):
        left, right = _scalar_number(a), _scalar_number(b)
        return left is not None and right is not None and abs(left - right) <= tol
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return finite(a) and finite(b) and abs(float(a) - float(b)) <= tol
    if isinstance(a, (int, float)) and isinstance(b, str):
        try:
            return finite(a) and math.isfinite(float(b)) and abs(float(a) - float(b)) <= tol
        except ValueError:
            return False
    if isinstance(b, (int, float)) and isinstance(a, str):
        try:
            return finite(b) and math.isfinite(float(a)) and abs(float(a) - float(b)) <= tol
        except ValueError:
            return False
    return a == b


def deep_equal(actual, expected, tol=1e-6) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and set(actual) == set(expected) and all(
            deep_equal(actual[key], expected[key], tol) for key in expected
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            deep_equal(a, b, tol) for a, b in zip(actual, expected)
        )
    return equal(actual, expected, tol)


def map_equal(actual, expected, tol=1e-6) -> bool:
    if actual is None or expected is None:
        return actual is None and expected is None
    if not isinstance(actual, dict) or not isinstance(expected, dict) or set(actual) != set(expected):
        return False
    return all(equal(actual[key], expected[key], tol) for key in expected)


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, str(exc)


def _manifest_names(value):
    """Accept a compact filename list or an evidence-bearing file inventory."""
    if not isinstance(value, list):
        return []
    names = []
    for item in value:
        if isinstance(item, str):
            names.append(Path(item).name)
        elif isinstance(item, dict):
            name = item.get("file") or item.get("name") or item.get("path")
            if isinstance(name, str):
                names.append(Path(name).name)
    return names


def _relative_material_path(value):
    if not isinstance(value, str):
        return None
    name = Path(value).name
    return f"materials/{name}" if name else None


def _source_path(source):
    if not isinstance(source, dict):
        return None
    return source.get("path") or source.get("absolute_path")


def _record_key(value):
    """Resolve a record key by filename while tolerating evidence paths."""
    if not isinstance(value, str):
        return None
    return Path(value).name


def _int_value(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Sub-field name tolerance.
#
# The memorandum publishes a minimum skeleton and names a handful of container
# keys (`affine_operations`, `operation_composition`, `composition_map`,
# `unmatched_pairs`, `operation_trace`, `operation_group` and its five members).
# It publishes no vocabulary for the *leaf* fields inside those containers, and
# it explicitly allows additional keys.  A register that supplies the same
# supplied identifier, the same source line, the same coordinates and the same
# adjudication under a different leaf name has produced the same evidence, so
# the resolvers below pick values by semantic role instead of by literal key.
# Nothing here loosens what the values themselves have to be.
# ---------------------------------------------------------------------------

_MISSING = object()


def _first(container, *keys):
    """First present key among synonyms; absent keys are skipped, not defaulted."""
    if not isinstance(container, dict):
        return None
    for key in keys:
        if key in container and container[key] is not None:
            return container[key]
    return None


def _present(container, *keys):
    if not isinstance(container, dict):
        return _MISSING
    for key in keys:
        if key in container:
            return container[key]
    return _MISSING


def _id_text(value):
    """Canonical text form of a supplied operation identifier."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if float(value).is_integer() else repr(value)
    if isinstance(value, str):
        return value.strip()
    return None


_SUPPORTED_WORDS = {
    "supported", "consistent", "closed", "closed_group", "holds", "passed", "pass",
    "ok", "agrees", "satisfied", "confirmed", "verified", "complete", "valid",
}
_CONFLICT_WORDS = {
    "conflict", "conflicting", "inconsistent", "violated", "failed", "fail",
    "broken", "not_closed", "open", "contradicted", "invalid",
}
_UNKNOWN_WORDS = {"unknown", "undetermined", "indeterminate", "not_determined", "unresolved"}


def _status_word(value):
    """Normalise an adjudication to supported / conflict / unknown."""
    if isinstance(value, bool):
        return "supported" if value else "conflict"
    if not isinstance(value, str):
        return None
    token = value.strip().lower().replace("-", "_").replace(" ", "_")
    if token in _SUPPORTED_WORDS:
        return "supported"
    if token in _CONFLICT_WORDS:
        return "conflict"
    if token in _UNKNOWN_WORDS:
        return "unknown"
    return token


def _numeric_forms(value):
    """A value may be given exactly, as a decimal, or as both under one key."""
    forms = [value]
    if isinstance(value, dict):
        for key in ("float", "decimal", "value", "values", "numeric", "approx", "exact"):
            if key in value:
                forms.append(value[key])
    return forms


def _value_candidates(container, *keys):
    out = []
    if not isinstance(container, dict):
        return out
    for key in keys:
        for variant in (key, key + "_decimal", key + "_float", key + "_value", key + "_exact"):
            if variant in container:
                out.extend(_numeric_forms(container[variant]))
    return out


def _any_equal(candidates, expected, tol=1e-6):
    return any(deep_equal(candidate, expected, tol) for candidate in candidates)


_TRACE_ID_KEYS = ("operation_id", "id", "op_id", "supplied_id", "operation",
                  "operation_identifier", "symop_id", "supplied_operation_id")
_RAW_KEYS = ("raw", "expression", "expr", "source_text", "supplied_xyz", "xyz",
             "operation_xyz", "symop_xyz", "raw_expression", "operation_expression")
_LINE_KEYS = ("source_line", "line", "line_number", "source_line_number", "cif_line",
              "file_line", "source_line_no")


def _atom_loop_rows(source):
    loop = source.get("atom_site_loop", source.get("atom_loop", {})) if isinstance(source, dict) else {}
    if isinstance(loop, dict) and loop.get("row_count") is not None:
        return _int_value(loop["row_count"])
    return _int_value(source.get("atom_loop_rows")) if isinstance(source, dict) else None


def _operation_ids(source):
    if not isinstance(source, dict):
        return []
    if isinstance(source.get("operation_ids"), list):
        return source["operation_ids"]
    loop = source.get("symmetry_operation_loop", source.get("operation_loop", {}))
    if isinstance(loop, dict) and isinstance(loop.get("identifiers"), list):
        return loop["identifiers"]
    rows = loop.get("rows", []) if isinstance(loop, dict) else []
    return [row.get("operation_id") for row in rows if isinstance(row, dict) and row.get("operation_id") is not None]


def _operation_count(source, metadata):
    value = metadata.get("operation_count") if isinstance(metadata, dict) else None
    parsed = _int_value(value)
    if parsed is not None:
        return parsed
    for key in ("symmetry_operation_loop", "operation_loop"):
        loop = source.get(key, {}) if isinstance(source, dict) else {}
        parsed = _int_value(loop.get("row_count")) if isinstance(loop, dict) else None
        if parsed is not None:
            return parsed
    ids = _operation_ids(source)
    return len(ids) if ids else None


def _space_group_number(metadata):
    if not isinstance(metadata, dict):
        return None
    if "space_group_number_raw" in metadata:
        return metadata["space_group_number_raw"]
    scalar_tags = metadata.get("scalar_tags", {})
    if isinstance(scalar_tags, dict):
        lowered = {str(key).lower(): value for key, value in scalar_tags.items()}
        for tag in ("_space_group_it_number", "_symmetry_int_tables_number"):
            value = lowered.get(tag)
            if isinstance(value, dict):
                return value.get("raw")
            if value is not None:
                return value
    group = metadata.get("space_group", {})
    candidates = group.get("international_tables_number_candidates", []) if isinstance(group, dict) else []
    if candidates and isinstance(candidates[0], dict):
        return candidates[0].get("raw_token") or candidates[0].get("value")
    return None


def _operation_complete(source, metadata):
    if isinstance(metadata, dict) and "operation_loop_complete" in metadata:
        return metadata["operation_loop_complete"]
    for key in ("symmetry_operation_loop", "operation_loop"):
        loop = source.get(key, {}) if isinstance(source, dict) else {}
        if not isinstance(loop, dict):
            continue
        if "complete_rows" in loop:
            return loop["complete_rows"]
        if "complete_required_fields" in loop:
            return loop["complete_required_fields"]
        if loop.get("row_count") is not None and isinstance(loop.get("operations"), list):
            return len(loop["operations"]) == _int_value(loop["row_count"])
    return None


def _site_rows(site):
    rows = site.get("source_rows", []) if isinstance(site, dict) else []
    result = []
    for item in rows if isinstance(rows, list) else []:
        if isinstance(item, int):
            result.append(item)
        elif isinstance(item, dict):
            value = item.get("loop_row")
            if isinstance(value, int):
                result.append(value)
    return result


def _site_labels(site):
    if isinstance(site, dict):
        for key in ("labels", "member_labels", "atom_labels", "member_label_list",
                    "orbit_member_labels", "site_labels"):
            if isinstance(site.get(key), list):
                return site[key]
    rows = site.get("source_rows", []) if isinstance(site, dict) else []
    return [
        item.get("label_raw", item.get("label"))
        for item in rows
        if isinstance(item, dict) and item.get("label_raw", item.get("label")) is not None
    ]


def _site_atom_evidence(site):
    evidence = site.get("evidence", {}) if isinstance(site, dict) else {}
    if isinstance(evidence, dict) and isinstance(evidence.get("atom_rows"), list):
        return evidence["atom_rows"]
    if isinstance(evidence, dict) and isinstance(evidence.get("source_atom_loop_rows"), list):
        return evidence["source_atom_loop_rows"]
    return _site_rows(site)


def _site_operation_evidence(site):
    evidence = site.get("evidence", {}) if isinstance(site, dict) else {}
    if isinstance(evidence, dict) and isinstance(evidence.get("operation_ids"), list):
        return evidence["operation_ids"]
    if isinstance(evidence, dict):
        ids = []
        for key in ("operation_ids_used_for_orbit", "stabilizer_operation_ids"):
            value = evidence.get(key)
            if isinstance(value, list):
                ids.extend(value)
        for item in evidence.get("operation_classes", []):
            if isinstance(item, dict) and isinstance(item.get("operation_ids"), list):
                ids.extend(item["operation_ids"])
        if ids:
            return list(dict.fromkeys(ids))
    trace = evidence.get("operation_trace", []) if isinstance(evidence, dict) else []
    return [item.get("operation_id") for item in trace if isinstance(item, dict) and item.get("operation_id") is not None]


def _coordinate_tolerance(site):
    evidence = site.get("evidence", {}) if isinstance(site, dict) else {}
    value = evidence.get("coordinate_tolerance") if isinstance(evidence, dict) else None
    if value is None and isinstance(evidence, dict):
        value = evidence.get("coordinate_comparison_tolerance")
    if value is None and isinstance(evidence, dict):
        value = evidence.get("comparison_tolerance")
    if isinstance(value, dict):
        value = value.get("value")
    return _scalar_number(value)


def _affine_matches(source, expected_source):
    """Compare the parsed W,t representation for every supplied operation."""
    if not isinstance(source, dict) or not isinstance(expected_source, dict):
        return False
    actual = source.get("affine_operations")
    expected = expected_source.get("affine_operations")
    if not isinstance(actual, list) or not isinstance(expected, list) or len(actual) != len(expected):
        return False
    for aa, ee in zip(actual, expected):
        if not isinstance(aa, dict) or not isinstance(ee, dict):
            return False
        if _id_text(_first(aa, *_TRACE_ID_KEYS)) != _id_text(ee.get("id")):
            return False
        if _first(aa, *_RAW_KEYS) != ee.get("raw"):
            return False
        if _first(aa, *_LINE_KEYS) != ee.get("source_line"):
            return False
        if not _any_equal(_value_candidates(aa, "matrix", "W", "rotation", "rotation_matrix",
                                           "linear_part"), ee.get("matrix"), 1e-9):
            return False
        if not _any_equal(_value_candidates(aa, "translation", "t", "translation_vector",
                                            "translation_part", "offset"),
                          ee.get("translation"), 1e-9):
            return False
    return True


_PAIR_SEPARATORS = ("|", ",", "*", "×", "·", "∘", ";", "&")


def _comp_pair_key(text):
    token = str(text)
    for separator in _PAIR_SEPARATORS:
        if separator in token:
            parts = [part.strip() for part in token.split(separator)]
            if len(parts) == 2 and all(parts):
                return f"{parts[0]}|{parts[1]}"
    return None


def _comp_target(value):
    if isinstance(value, dict):
        return _id_text(_first(value, "product_operation", "result_id", "result_operation",
                               "result", "target", "product_id", "product", "operation_id", "id"))
    return _id_text(value)


def _composition_map_candidates(container):
    """Every plausible reading of the ordered-pair composition witness."""
    out = []
    if not isinstance(container, dict):
        return out
    for key in ("composition_map", "composition_map_with_ids", "composition_targets",
                "composition_table", "products", "product_map"):
        value = container.get(key)
        if isinstance(value, dict):
            resolved, ok = {}, True
            for pair, target in value.items():
                pair_key, target_id = _comp_pair_key(pair), _comp_target(target)
                if pair_key is None or target_id is None:
                    ok = False
                    break
                resolved[pair_key] = target_id
            if ok and resolved:
                out.append(resolved)
        elif isinstance(value, list):
            resolved, ok = {}, True
            for item in value:
                if not isinstance(item, dict):
                    ok = False
                    break
                left = _id_text(_first(item, "left_id", "i_id", "a_id", "first_id", "lhs_id",
                                       "left", "operation_a"))
                right = _id_text(_first(item, "right_id", "j_id", "b_id", "second_id", "rhs_id",
                                        "right", "operation_b"))
                target_id = _comp_target(item)
                if left is None or right is None or target_id is None:
                    ok = False
                    break
                resolved[f"{left}|{right}"] = target_id
            if ok and resolved:
                out.append(resolved)
    return out


def _composition_matches(source, expected_source):
    if not isinstance(source, dict) or not isinstance(expected_source, dict):
        return False
    actual = _first(source, "operation_composition", "operation_closure", "composition_witness")
    expected = expected_source.get("operation_composition", expected_source.get("operation_closure"))
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    status = _status_word(_first(actual, "status", "state", "verdict"))
    if status is None:
        status = _status_word(_first(actual, "closure_holds", "closed", "is_closed",
                                     "closed_exact", "group_closed", "holds"))
    if status != _status_word(expected.get("status")):
        return False
    if _int_value(_first(actual, "pair_count", "ordered_pair_count", "composition_pair_count")) \
            != expected.get("pair_count"):
        return False
    expected_maps = _composition_map_candidates(expected)
    if not expected_maps or not any(candidate in expected_maps
                                    for candidate in _composition_map_candidates(actual)):
        return False
    unmatched = _present(actual, "unmatched_pairs", "unmatched", "unmatched_composition_pairs")
    if unmatched is _MISSING:
        unmatched = []
    return unmatched == expected.get("unmatched_pairs", [])


def _operation_trace_matches(site, expected_site):
    evidence = site.get("evidence", {}) if isinstance(site, dict) else {}
    expected_evidence = expected_site.get("evidence", {}) if isinstance(expected_site, dict) else {}
    actual = evidence.get("operation_trace") if isinstance(evidence, dict) else None
    expected = expected_evidence.get("operation_trace") if isinstance(expected_evidence, dict) else None
    if not isinstance(actual, list) or not isinstance(expected, list) or len(actual) != len(expected):
        return False
    for aa, ee in zip(actual, expected):
        if not isinstance(aa, dict) or not isinstance(ee, dict):
            return False
        if _id_text(_first(aa, *_TRACE_ID_KEYS)) != _id_text(ee.get("operation_id")):
            return False
        if _first(aa, *_RAW_KEYS) != ee.get("raw"):
            return False
        if _first(aa, *_LINE_KEYS) != ee.get("source_line"):
            return False
        if not _any_equal(_value_candidates(
                aa, "unreduced_coordinate", "unreduced", "unreduced_coordinates",
                "unreduced_image", "image", "image_coordinate", "raw_image",
                "transformed_coordinate", "transformed"),
                ee.get("unreduced_coordinate"), 1e-6):
            return False
        if not _any_equal(_value_candidates(
                aa, "reduced_coordinate", "reduced", "reduced_coordinates",
                "normalized_coordinate", "normalised_coordinate", "image_mod1",
                "transformed_mod1", "wrapped_coordinate", "transformed_coordinate",
                "transformed"),
                ee.get("reduced_coordinate"), 1e-6):
            return False
        stabilizes = _first(aa, "stabilizes", "is_stabilizer", "is_stabiliser",
                            "stabilizes_representative", "stabilises_representative",
                            "fixes_representative", "maps_to_representative",
                            "maps_to_representative_within_precision", "in_stabilizer")
        if stabilizes != ee.get("stabilizes"):
            return False
        matched = _present(aa, "matched_source_rows", "matched_rows", "matched_atom_rows",
                           "matching_source_rows", "source_rows")
        if matched is _MISSING:
            matched = []
        if matched != ee.get("matched_source_rows", []):
            return False
    return True


def _formula_inventory_matches(actual_formula, expected_formula):
    if not isinstance(actual_formula, dict) or not isinstance(expected_formula, dict):
        return False
    actual = _first(actual_formula, "formula_tag_inventory", "formula_tags",
                    "formula_scalar_inventory", "scalar_inventory", "formula_tag_list")
    expected = expected_formula.get("formula_tag_inventory")
    if not isinstance(actual, list) or not isinstance(expected, list) or len(actual) != len(expected):
        return False
    for aa, ee in zip(actual, expected):
        if not isinstance(aa, dict) or not isinstance(ee, dict):
            return False
        if _first(aa, "tag", "cif_tag", "name") != ee.get("tag"):
            return False
        if _first(aa, *_RAW_KEYS) != ee.get("raw"):
            return False
        if _first(aa, "line", "source_line", "line_number", "source_line_number") != ee.get("line"):
            return False
        if _status_word(_first(aa, "status", "parse_status", "state")) != _status_word(ee.get("status")):
            return False
        if not _any_equal(_value_candidates(aa, "parsed_counts", "parsed", "counts",
                                            "parsed_map", "element_counts", "parsed_composition"),
                          ee.get("parsed_counts"), 1e-9):
            return False
    return _normalised_relation(_first(actual_formula, "formula_tag_relation", "formula_tags_relation",
                                       "tag_relation", "inventory_relation")) \
        == _normalised_relation(expected_formula.get("formula_tag_relation"))


def _normalised_relation(relation):
    """The cross-tag relation with its adjudication normalised like every other status."""
    if not isinstance(relation, dict):
        return relation
    return {key: (_status_word(value) if key in ("status", "state", "verdict") else value)
            for key, value in relation.items()}


_COUNT_KEYS = ("fixed_site_count", "fixed_row_count", "fixed_representative_count",
               "count", "sites", "site_count", "fixed_sites", "value")


def _scalar_number(value, inner_keys=()):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, str):
        try:
            from fractions import Fraction
            number = float(Fraction(value.strip()))
            return number if math.isfinite(number) else None
        except (ValueError, ZeroDivisionError, OverflowError):
            return None
    if isinstance(value, dict) and inner_keys:
        return _scalar_number(_first(value, *inner_keys))
    return None


def _operation_keyed_map(container, inner_keys=()):
    """A per-operation map keyed by the supplied identifiers, however it is nested."""
    if isinstance(container, dict):
        nested = _first(container, "per_operation_fixed_site_count", "per_operation",
                        "by_operation", "counts")
        if isinstance(nested, dict):
            container = nested
    if not isinstance(container, dict):
        return None
    resolved = {}
    for key, value in container.items():
        number = _scalar_number(value, inner_keys)
        if number is None:
            return None
        resolved[_id_text(key)] = number
    return resolved or None


def _histogram(value):
    """Class/order tallies, with absent classes and zero tallies treated alike."""
    if not isinstance(value, dict):
        return None
    resolved = {}
    for key, count in value.items():
        number = _scalar_number(count)
        if number is None:
            return None
        if number == 0:
            continue
        resolved[_id_text(key) or str(key)] = number
    return resolved


_SIGNATURE_DET_KEYS = ("determinant_classes", "determinant_histogram", "determinant_class_counts")
_SIGNATURE_ORDER_KEYS = ("order_histogram", "operation_order_histogram", "order_inventory",
                         "operation_order_inventory", "rotation_order_histogram")
_SIGNATURE_FIX_KEYS = ("fixed_site_histogram", "fixed_site_count_histogram",
                       "fixed_site_profile_histogram")


def _signature_parts(signature):
    if not isinstance(signature, dict):
        return None
    return {
        "operation_count": _scalar_number(_first(signature, "operation_count", "n", "order",
                                                 "group_order")),
        "determinant_classes": _histogram(_first(signature, *_SIGNATURE_DET_KEYS)),
        "order_histogram": _histogram(_first(signature, *_SIGNATURE_ORDER_KEYS)),
        "fixed_site_histogram": _histogram(_first(signature, *_SIGNATURE_FIX_KEYS)),
    }


def _operation_group_matches(actual_record, expected_record):
    """Require the complete derived group-invariant witness, not a single label.

    The memorandum names the members this object must carry (identity, the
    per-operation determinant and order maps, the order inventory, the
    determinant classes, the fixed-site profile, a deterministic signature and a
    status).  It does not name the leaf spelling of any of them, so each member
    is resolved by role and compared on value.
    """
    actual = actual_record.get("operation_group") if isinstance(actual_record, dict) else None
    expected = expected_record.get("operation_group") if isinstance(expected_record, dict) else None
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    if deep_equal(actual, expected, 1e-9):
        return True
    if _id_text(_first(actual, "identity_operation_id", "identity_id", "identity_operation")) \
            != _id_text(expected.get("identity_operation_id")):
        return False
    if _status_word(_first(actual, "status", "state", "verdict")) \
            != _status_word(expected.get("status")):
        return False
    for actual_map, expected_map in (
        (_operation_keyed_map(_first(actual, "determinant_by_operation", "determinants_by_operation",
                                     "determinant_map", "operation_determinants"),
                              ("determinant", "value")),
         _operation_keyed_map(expected.get("determinant_by_operation"))),
        (_operation_keyed_map(_first(actual, "operation_orders", "orders_by_operation",
                                     "operation_order_map", "order_by_operation"),
                              ("order", "value")),
         _operation_keyed_map(expected.get("operation_orders"))),
        (_operation_keyed_map(_first(actual, "fixed_site_profile", "fixed_site_counts",
                                     "fixed_sites_by_operation"), _COUNT_KEYS),
         _operation_keyed_map(expected.get("fixed_site_profile"))),
    ):
        if actual_map is None or expected_map is None or actual_map != expected_map:
            return False
    signature = _first(actual, "group_signature", "signature", "group_fingerprint")
    for names, want in ((_SIGNATURE_DET_KEYS, _histogram(expected.get("determinant_classes"))),
                        (_SIGNATURE_ORDER_KEYS, _histogram(expected.get("order_histogram")))):
        got = _histogram(_first(actual, *names))
        if got is None and isinstance(signature, dict):
            got = _histogram(_first(signature, *names))
        if got is None or got != want:
            return False
    got_signature = _signature_parts(signature)
    want_signature = _signature_parts(expected.get("group_signature"))
    if got_signature is None or want_signature is None:
        return False
    for key in ("operation_count", "determinant_classes", "order_histogram"):
        if got_signature[key] is None or got_signature[key] != want_signature[key]:
            return False
    # The memorandum requires the signature to be deterministic; it does not
    # prescribe its member list, and the fixed-site profile is already required
    # as a member of the group object in its own right.  A fixed-site tally
    # inside the signature is therefore checked only where one is supplied.
    if got_signature["fixed_site_histogram"] is not None \
            and got_signature["fixed_site_histogram"] != want_signature["fixed_site_histogram"]:
        return False
    return True


def _record_partition(block):
    """Which records share a group signature, however the block spells that claim.

    Golden states it as ``signature_classes``, a list of {signature, files}.  Outputs state the same
    partition as equivalence classes under other names, as a record -> signature mapping, or - when
    every record differs - as a distinct count beside an all-distinct flag.  Those are the same
    assertion in different carriers, so all of them are read.  Returns a set of frozensets of record
    names, or None when the block does not state the partition at all.
    """
    if not isinstance(block, dict):
        return None
    classes = _first(block, "signature_classes", "signature_equivalence_classes",
                     "distinct_signature_groups", "equivalence_classes", "signature_groups")
    if isinstance(classes, list) and classes:
        groups = []
        for entry in classes:
            files = entry
            if isinstance(entry, dict):
                files = _first(entry, "files", "records", "record_ids", "members", "file_names")
            if isinstance(files, str):
                files = [files]
            if not isinstance(files, list):
                groups = []
                break
            groups.append(frozenset(str(f) for f in files))
        if groups:
            return frozenset(groups)
    mapping = _first(block, "signature_by_file", "signature_index", "record_signatures",
                     "signature_table", "signature_hash_index", "abstract_fingerprint_index")
    if isinstance(mapping, list) and mapping and all(isinstance(e, dict) for e in mapping):
        rebuilt = {}
        for entry in mapping:
            name = _first(entry, "file", "record", "record_id", "file_name", "name")
            if name is None:
                rebuilt = {}
                break
            rebuilt[str(name)] = _first(entry, "signature", "group_signature", "fingerprint", "hash")
        mapping = rebuilt
    if isinstance(mapping, dict) and mapping:
        buckets = {}
        for name, signature in mapping.items():
            buckets.setdefault(json.dumps(signature, sort_keys=True, default=str), []).append(str(name))
        return frozenset(frozenset(names) for names in buckets.values())
    return None


def _all_distinct_claim(block, size):
    """True when the block says, by count or by flag, that all ``size`` records differ."""
    if not isinstance(block, dict):
        return False
    flag = _first(block, "all_signatures_distinct", "all_four_signatures_distinct", "all_distinct")
    count = _int_value(_first(block, "distinct_signature_count", "n_distinct_signatures",
                              "unique_signature_count", "distinct_count"))
    return flag is True or (count is not None and count == size)


_PAIRWISE_KEYS = ("pairwise", "pairwise_comparisons", "pairs", "pairwise_audit", "comparisons")
_PAIR_LEFT_KEYS = ("left_file", "left", "file_a", "a", "record_a", "first", "left_record")
_PAIR_RIGHT_KEYS = ("right_file", "right", "file_b", "b", "record_b", "second", "right_record")
_PAIR_SAME_KEYS = ("same_group_signature", "same_signature", "signatures_equal", "signature_equal",
                   "group_signature_equal", "same_group_signature_class", "shares_signature",
                   "identical_signature", "same")


def _pairwise_contradictions(block, partition):
    """Count pairwise entries whose same-signature flag disagrees with ``partition``.

    A pairwise entry names two records and states whether they share a group signature; that
    statement is fixed by the partition, so a flag that contradicts it is a wrong comparison even
    when the partition itself is stated correctly elsewhere in the block."""
    if not isinstance(block, dict) or not partition:
        return 0
    entries = _first(block, *_PAIRWISE_KEYS)
    if not isinstance(entries, list):
        return 0
    group_of = {}
    for group in partition:
        for name in group:
            group_of[_record_key(name)] = group
    bad = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        left = _record_key(_first(entry, *_PAIR_LEFT_KEYS))
        right = _record_key(_first(entry, *_PAIR_RIGHT_KEYS))
        flag = _first(entry, *_PAIR_SAME_KEYS)
        if left not in group_of or right not in group_of or not isinstance(flag, bool):
            continue
        if flag != (group_of[left] is group_of[right]):
            bad += 1
    return bad


def comparative_completion(actual, expected):
    """Score partition, disposition and each directional evidence pointer independently."""
    if not isinstance(actual, dict):
        return 0.0
    want = _record_partition(expected)
    got = _record_partition(actual)
    partition_ok = got == want or (got is None and all(len(g) == 1 for g in want)
                                  and _all_distinct_claim(actual, len(want)))
    checks = [partition_ok, _status_word(_first(actual, "status", "state", "verdict"))
              == _status_word(expected.get("status"))]
    entries = _first(actual, *_PAIRWISE_KEYS)
    entries = entries if isinstance(entries, list) else []
    for pair in expected.get("pairwise", []):
        left, right = pair["left_file"], pair["right_file"]
        matches = [p for p in entries if isinstance(p, dict) and
                   {_record_key(_first(p, *_PAIR_LEFT_KEYS)), _record_key(_first(p, *_PAIR_RIGHT_KEYS))}
                   == {left, right}]
        if len(matches) != 1:
            checks.extend([False, False, False])
            continue
        item = matches[0]
        checks.append(_first(item, *_PAIR_SAME_KEYS) is pair["same_group_signature"])
        evidence = item.get("evidence", {})
        evidence = evidence if isinstance(evidence, dict) else {}
        reverse = _record_key(_first(item, *_PAIR_LEFT_KEYS)) == right
        for side, expected_side in (("left", "right" if reverse else "left"),
                                    ("right", "left" if reverse else "right")):
            ids = evidence.get(side + "_operation_ids")
            checks.append(isinstance(ids, list) and set(map(str, ids)) ==
                          set(map(str, pair["evidence"][expected_side + "_operation_ids"])))
    return sum(checks) / len(checks)


def comparative_business_complete(actual, expected):
    """Whether the comparison is scientifically complete and source-anchored.

    Strict quality scores both directional convenience pointers.  Completion needs the
    partition, disposition and every pair conclusion, plus at least one correctly side-bound
    operation anchor per pair.  The other side remains recomputable from the mandatory complete
    operation/group record for the named file, so one omitted navigation pointer is a local
    documentation defect rather than a failed scientific comparison.
    """
    if not isinstance(actual, dict):
        return False
    want = _record_partition(expected)
    got = _record_partition(actual)
    partition_ok = got == want or (got is None and all(len(g) == 1 for g in want)
                                  and _all_distinct_claim(actual, len(want)))
    if not partition_ok or _status_word(_first(actual, "status", "state", "verdict")) \
            != _status_word(expected.get("status")):
        return False
    entries = _first(actual, *_PAIRWISE_KEYS)
    entries = entries if isinstance(entries, list) else []
    for pair in expected.get("pairwise", []):
        left, right = pair["left_file"], pair["right_file"]
        matches = [p for p in entries if isinstance(p, dict) and
                   {_record_key(_first(p, *_PAIR_LEFT_KEYS)), _record_key(_first(p, *_PAIR_RIGHT_KEYS))}
                   == {left, right}]
        if len(matches) != 1:
            return False
        item = matches[0]
        if _first(item, *_PAIR_SAME_KEYS) is not pair["same_group_signature"]:
            return False
        evidence = item.get("evidence", {})
        evidence = evidence if isinstance(evidence, dict) else {}
        reverse = _record_key(_first(item, *_PAIR_LEFT_KEYS)) == right
        valid_anchors = []
        for side, expected_side in (("left", "right" if reverse else "left"),
                                    ("right", "left" if reverse else "right")):
            ids = evidence.get(side + "_operation_ids")
            valid_anchors.append(isinstance(ids, list) and set(map(str, ids)) ==
                                 set(map(str, pair["evidence"][expected_side + "_operation_ids"])))
        if not any(valid_anchors):
            return False
    return True


def _closure_matches(site, expected_site):
    actual = site.get("closure_check", {}) if isinstance(site, dict) else {}
    expected = expected_site.get("closure_check", {})
    if actual == expected:
        return True
    if not isinstance(actual, dict):
        return False
    count = _int_value(_first(actual, "operation_count", "supplied_operation_count",
                              "expected_group_order", "group_order", "symmetry_operation_count",
                              "operation_count_supplied"))
    product = _int_value(_first(actual, "orbit_times_stabilizer", "orbit_size_times_stabilizer",
                                "orbit_size_times_stabilizer_order", "orbit_stabilizer_product",
                                "orbit_times_stabilizer_order", "product"))
    if product is None:
        orbit = _int_value(actual.get("orbit_size"))
        stabilizer = _int_value(actual.get("stabilizer_order"))
        if orbit is not None and stabilizer is not None:
            product = orbit * stabilizer
    status = _status_word(_first(actual, "status", "state", "verdict"))
    if status is None and actual.get("matches_operation_count") is True \
            and actual.get("operation_set_state") == "closed":
        status = "supported"
    if status is None:
        status = _status_word(_first(actual, "relation_holds", "agrees",
                                     "satisfies_orbit_stabilizer", "orbit_stabilizer_identity_holds",
                                     "invariant_passed", "identity_holds", "holds"))
    return (
        count == expected.get("operation_count")
        and product == expected.get("orbit_times_stabilizer")
        and status == _status_word(expected.get("status"))
    )


_ABSENT_WORDS = {"unknown", "not_supplied", "absent", "missing", "none", "not_present",
                 "no_tag", "unsupplied"}


def _multiplicity_matches(site, expected_site):
    actual = site.get("supplied_multiplicity", {}) if isinstance(site, dict) else {}
    expected = expected_site.get("supplied_multiplicity", {})
    if actual == expected:
        return True
    if not isinstance(actual, dict):
        return False
    if expected.get("status") != "not_supplied":
        return False
    state = _first(actual, "status", "state")
    declared_absent = isinstance(state, str) and state.strip().lower() in _ABSENT_WORDS
    for key in ("present", "tag_present", "supplied", "is_supplied", "provided", "tag_supplied"):
        if actual.get(key) is False:
            declared_absent = True
    if not declared_absent:
        return False
    value = _first(actual, "value", "values", "raw", "parsed", "multiplicity",
                   "supplied_value", "multiplicity_value")
    return value in (None, [], "", {})


def _formula_value(formula, key):
    if not isinstance(formula, dict):
        return None
    if key in formula:
        return formula.get(key)
    nested = formula.get("formula_source", {})
    if key == "formula_raw" and isinstance(nested, dict) and nested.get("raw") is not None:
        return nested.get("raw")
    if key == "formula_units_z_raw":
        z = formula.get("formula_units_Z", {})
        if isinstance(z, dict) and z.get("raw") is not None:
            return z.get("raw")
        if z not in ({}, None):
            return z
    if key == "formula_raw":
        supplied = formula.get("supplied_formula", {})
        if isinstance(supplied, dict):
            return supplied.get("raw")
    if key == "formula_units_z_raw":
        units = formula.get("formula_units", {})
        if isinstance(units, dict):
            return units.get("raw")
    return None


def _formula_map(formula, key):
    value = formula.get(key) if isinstance(formula, dict) else None
    if key == "derived_totals" and value is None and isinstance(formula, dict):
        value = formula.get("derived_totals_per_cell")
    if key == "expected_totals" and value is None and isinstance(formula, dict):
        value = formula.get("expected_totals_per_cell")
    if key == "derived_totals" and value is None and isinstance(formula, dict):
        value = formula.get("derived_contributions")
    if key == "expected_totals" and value is None and isinstance(formula, dict):
        value = formula.get("comparison_target_formula_counts_times_Z")
    if not isinstance(value, dict):
        return value
    result = {}
    for element, item in value.items():
        if isinstance(item, dict) and "value" in item:
            if item.get("state") == "unknown":
                continue
            result[element] = item.get("value")
        else:
            result[element] = item
    return result


def _unknown_rows(rec):
    formula = rec.get("formula_reconciliation", {}) if isinstance(rec, dict) else {}
    if isinstance(formula, dict) and isinstance(formula.get("unknown_atom_rows"), list):
        return formula["unknown_atom_rows"]
    if isinstance(formula, dict) and isinstance(formula.get("unresolved_source_rows"), list):
        unresolved = set(formula["unresolved_source_rows"])
        rows = []
        for item in formula.get("contributions", []):
            if not isinstance(item, dict):
                continue
            if (
                item.get("source_loop_row") in unresolved
                or item.get("source_row") in unresolved
                or item.get("source_line") in unresolved
                or item.get("contribution") is None
                or item.get("weighted_contribution_per_cell", {}).get("state") == "unknown"
            ):
                row = item.get("source_loop_row", item.get("source_row"))
                if isinstance(row, int):
                    rows.append(row)
        if rows:
            return rows
    rows = []
    for site in rec.get("sites", []) if isinstance(rec, dict) else []:
        contributions = formula.get("contributions", []) if isinstance(formula, dict) else []
        unknown_sources = {
            item.get("source_row") for item in contributions
            if isinstance(item, dict) and item.get("weighted_contribution_per_cell", {}).get("state") == "unknown"
        }
        for item in site.get("source_rows", []) if isinstance(site, dict) else []:
            if isinstance(item, dict) and item.get("source_row") in unknown_sources:
                if isinstance(item.get("loop_row"), int):
                    rows.append(item["loop_row"])
    return rows


def _aggregate_matches(actual, expected):
    if actual == expected:
        return True
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    record_counts = actual.get("record_status_counts", {})
    formula_counts = actual.get(
        "formula_reconciliation_status_counts",
        actual.get("record_formula_status_counts", {}),
    )
    classes = actual.get("position_class_counts", {})
    checks = {
        "records_total": actual.get("records_total", actual.get("input_file_count")),
        "records_analyzed": actual.get("records_analyzed", actual.get("analyzed_record_count")),
        # Same normalisation for the aggregate bucket: a register that writes "supported" counts
        # the same records as one that writes "complete".
        "records_complete": actual.get(
            "records_complete",
            sum(value for key, value in record_counts.items()
                if _status_word(key) == "supported" and isinstance(value, int))
            if record_counts else None,
        ),
        "records_partial_or_unknown": actual.get("records_partial_or_unknown", record_counts.get("partial")),
        "records_conflict": actual.get("records_conflict", record_counts.get("conflict")),
        "site_count": actual.get("site_count", actual.get("total_site_count")),
        "special_site_count": actual.get("special_site_count", classes.get("special")),
        "general_site_count": actual.get("general_site_count", classes.get("general")),
        "unknown_site_count": actual.get("unknown_site_count", classes.get("unknown", 0)),
    }
    if any(checks[key] != expected.get(key) for key in checks):
        return False
    supplied_formula_counts = actual.get("formula_status_counts", formula_counts)
    if supplied_formula_counts != expected.get("formula_status_counts"):
        return False
    for key in ("operation_group_status_counts", "signature_class_count", "pairwise_comparison_count"):
        if actual.get(key) != expected.get(key):
            return False
    return True


def site_match(record, expected_site):
    sites = record.get("sites") if isinstance(record, dict) else None
    if not isinstance(sites, list):
        return None
    label = expected_site.get("representative_label")
    for site in sites:
        if isinstance(site, dict) and site.get("representative_label") == label:
            return site
    # A different site_id/order is acceptable when the source rows identify it.
    rows = set(expected_site.get("source_rows", []))
    for site in sites:
        if isinstance(site, dict) and rows and rows == set(_site_rows(site)):
            return site
    return None


INDEX_CREDIT_SATURATION = 0.7

# ---------------------------------------------------------------------------
# Conclusion reversal.
#
# Every adjudication in this register is recomputable from numbers the same
# register supplies: a representative is special exactly when its own
# stabilizer order exceeds one, the closure check is supported exactly when its
# own orbit-times-stabilizer equals its own operation count, and the stabiliser
# flags along a trace are true exactly on the stabilizer_order operations the
# site itself claims.  A reversed register keeps every number and pointer and
# states the opposite adjudication, so it is caught by recomputation.
#
# The test is deliberately "exactly opposite", never "this dimension scored
# low": a register that is wrong, incomplete, or written with its own field
# names produces adjudications that disagree with the recomputation only by
# accident, not by exact negation, and is therefore not flagged.
# ---------------------------------------------------------------------------

_STABILIZES_KEYS = ("stabilizes", "is_stabilizer", "is_stabiliser", "stabilizes_representative",
                    "stabilises_representative", "fixes_representative", "maps_to_representative",
                    "maps_to_representative_within_precision", "in_stabilizer")


def _site_trace(site):
    evidence = site.get("evidence", {}) if isinstance(site, dict) else {}
    trace = evidence.get("operation_trace") if isinstance(evidence, dict) else None
    return trace if isinstance(trace, list) else []


def _closure_terms(site):
    """(operation count, orbit x stabilizer, asserted status) as the site states them."""
    check = site.get("closure_check") if isinstance(site, dict) else None
    check = check if isinstance(check, dict) else {}
    count = _int_value(_first(check, "operation_count", "supplied_operation_count",
                              "expected_group_order", "group_order", "symmetry_operation_count",
                              "operation_count_supplied"))
    product = _int_value(_first(check, "orbit_times_stabilizer", "orbit_size_times_stabilizer",
                                "orbit_size_times_stabilizer_order", "orbit_stabilizer_product",
                                "orbit_times_stabilizer_order", "product"))
    if product is None:
        orbit = _int_value(_first(check, "orbit_size")) or _int_value(site.get("orbit_size"))
        stabilizer = (_int_value(_first(check, "stabilizer_order"))
                      or _int_value(site.get("stabilizer_order")))
        if orbit is not None and stabilizer is not None:
            product = orbit * stabilizer
    status = _status_word(_first(check, "status", "state", "verdict"))
    if status is None:
        status = _status_word(_first(check, "relation_holds", "agrees",
                                     "satisfies_orbit_stabilizer", "orbit_stabilizer_identity_holds",
                                     "invariant_passed", "identity_holds", "holds"))
    return count, product, status


def conclusion_reversal_rate(actual):
    """Largest per-family share of adjudications that are the exact negation of
    what the register's own numbers imply.

    A family is one kind of adjudication within one record.  Records are counted
    apart because they differ in size by an order of magnitude here (3 sites to
    45): pooling them would let the large record dilute a record whose every
    adjudication is stated backwards."""
    families = {}
    records = actual.get("records") if isinstance(actual, dict) else None
    for index, record in enumerate(records if isinstance(records, list) else []):
        if not isinstance(record, dict):
            continue
        scope = _record_key(record.get("file")) or f"#{index}"
        family = families.setdefault(scope, {"position_class": [0, 0], "closure_status": [0, 0],
                                             "stabilizer_flags": [0, 0]})
        sites = record.get("sites")
        for site in sites if isinstance(sites, list) else []:
            if not isinstance(site, dict):
                continue
            stabilizer = _int_value(site.get("stabilizer_order"))

            declared = site.get("position_class")
            if isinstance(declared, str) and declared.strip().lower() in {"general", "special"} \
                    and stabilizer is not None and stabilizer >= 1:
                implied = "special" if stabilizer > 1 else "general"
                family["position_class"][1] += 1
                if declared.strip().lower() != implied:
                    family["position_class"][0] += 1

            count, product, status = _closure_terms(site)
            if count is not None and product is not None and status in {"supported", "conflict"}:
                implied = "supported" if count == product else "conflict"
                family["closure_status"][1] += 1
                if status != implied:
                    family["closure_status"][0] += 1

            trace = _site_trace(site)
            flags = [_first(step, *_STABILIZES_KEYS) for step in trace if isinstance(step, dict)]
            if trace and len(flags) == len(trace) and all(isinstance(f, bool) for f in flags) \
                    and stabilizer is not None and 0 < stabilizer < len(trace):
                true_count = sum(1 for f in flags if f)
                family["stabilizer_flags"][1] += 1
                # Exact complement of the stabiliser the site itself declares.
                if true_count == len(trace) - stabilizer and true_count != stabilizer:
                    family["stabilizer_flags"][0] += 1

    rates = [bad / total for family in families.values()
             for bad, total in family.values() if total]
    return max(rates) if rates else 0.0


def contribution_completion(actual_formula, expected_formula, record, expected_record):
    actual = _first(actual_formula, "contribution_ledger", "contributions", "row_contributions")
    expected = expected_formula.get("contribution_ledger", [])
    if not isinstance(actual, list) or not expected:
        return 0.0
    by_row = {}
    for item in actual:
        if isinstance(item, dict):
            by_row.setdefault(_int_value(_first(item, "source_row", "atom_row", "row")), []).append(item)
    checks = []
    sums = {}
    for row in expected:
        entries = by_row.get(row["source_row"], [])
        if len(entries) != 1:
            checks.append(False)
            continue
        item = entries[0]
        # Site ids are author-controlled; bind the pointer to the site's source rows.
        site = next((s for s in record.get("sites", []) if isinstance(s, dict)
                     and s.get("site_id") == _first(item, "site_id", "site")), None)
        checks.append(site is not None and row["source_row"] in _site_rows(site))
        roles = (("source_line", "line"), ("label", "atom_label"),
                 ("element_raw", "type_raw"), ("element", "normalized_element"),
                 ("fallback", "element_fallback"), ("occupancy_raw", "raw_occupancy"),
                 ("occupancy", "parsed_occupancy"), ("orbit_size", "multiplicity"),
                 ("contribution", "weighted_contribution"))
        for keys in roles:
            value = _present(item, *keys)
            checks.append(value is not _MISSING and deep_equal(value, row[keys[0]], 1e-9))
        checks.append(_status_word(item.get("status")) == _status_word(row["status"]))
        if _status_word(row["status"]) in {"unknown", "conflict"}:
            checks.append(isinstance(item.get("reason"), str) and bool(item["reason"].strip()))
        number = _scalar_number(_first(item, "contribution", "weighted_contribution"))
        element = _first(item, "element", "normalized_element")
        if number is not None and isinstance(element, str):
            sums[element] = sums.get(element, 0) + number
    checks.append(len(actual) == len(expected))
    checks.append(map_equal(sums, _formula_map(actual_formula, "derived_totals"), 1e-9))
    return sum(checks) / len(checks)


def score_report(actual, expected):
    details = {}
    if not isinstance(actual, dict):
        return {"error": "top-level JSON value is not an object"}

    # D1: input coverage and manifest.
    exp_files = expected["input_manifest"]["files"]
    manifest = actual.get("input_manifest", {})
    coverage = 0.0
    if isinstance(manifest, dict):
        if set(_manifest_names(manifest.get("files", []))) == set(exp_files):
            coverage += 0.7
        if manifest.get("count") == len(exp_files):
            coverage += 0.3
    details["manifest"] = coverage

    exp_records = {r["file"]: r for r in expected["records"]}
    records = actual.get("records")
    actual_records = {
        _record_key(r.get("file")): r
        for r in records
        if isinstance(r, dict) and _record_key(r.get("file"))
    } if isinstance(records, list) else {}

    # D2: record metadata and source inventory.
    metadata_hits = []
    site_identity_hits = []
    orbit_hits = []
    operation_hits = []
    closure_hits = []
    formula_hits = []
    evidence_hits = []
    group_hits = []
    for filename, exp in exp_records.items():
        rec = actual_records.get(filename)
        if rec is None:
            metadata_hits.append(0.0)
            operation_hits.append(0.0)
            group_hits.append(0.0)
            continue
        src = rec.get("source", {})
        meta = rec.get("metadata", {})
        m = 0
        m += int(_relative_material_path(_source_path(src)) == exp["source"]["path"])
        m += int(_atom_loop_rows(src) == exp["source"]["atom_loop_rows"])
        m += int(_operation_count(src, meta) == exp["metadata"]["operation_count"])
        m += int(_space_group_number(meta) == exp["metadata"]["space_group_number_raw"])
        m += int(_operation_complete(src, meta) == exp["metadata"]["operation_loop_complete"])
        metadata_hits.append(m / 5)

        operation_source_hit = int(_affine_matches(src, exp["source"]))
        operation_source_hit += int(_composition_matches(src, exp["source"]))
        group_hits.append(1.0 if _operation_group_matches(rec, exp) else 0.0)

        exp_sites = exp["sites"]
        site_list = rec.get("sites")
        if not isinstance(site_list, list) or len(site_list) != len(exp_sites):
            site_identity_hits.append(0.0)
            orbit_hits.append(0.0)
            closure_hits.append(0.0)
            evidence_hits.append(0.0)
            # P05 is three parts per record; a sites array that does not hold one entry per
            # inequivalent site forfeits the per-site trace part, so it scores 0 of 3 here.
            # The denominator stays 3, as in the well-formed branch below: renormalising to 2
            # would let a register that drops most of its sites earn full P05.
            operation_hits.append(operation_source_hit / 3)
        else:
            identity = orbit = closure = evidence = 0
            trace_hits = []
            for es in exp_sites:
                s = site_match(rec, es)
                if not s:
                    trace_hits.append(0.0)
                    continue
                identity += int(s.get("representative_label") == es.get("representative_label"))
                identity += int(_site_labels(s) == es.get("labels"))
                identity += int(_site_rows(s) == es.get("source_rows"))
                identity += int(deep_equal(s.get("representative_coordinate_raw"), es.get("representative_coordinate_raw")))
                identity += int(deep_equal(s.get("representative_coordinate_mod1"), es.get("representative_coordinate_mod1")))
                identity += int(deep_equal(s.get("elements"), es.get("elements")))
                orbit += int(_scalar_number(s.get("orbit_size")) == es.get("orbit_size"))
                orbit += int(_scalar_number(s.get("stabilizer_order")) == es.get("stabilizer_order"))
                orbit += int(s.get("position_class") == es.get("position_class"))
                closure += int(_closure_matches(s, es))
                closure += int(_multiplicity_matches(s, es))
                ev = s.get("evidence", {})
                ee = es.get("evidence", {})
                evidence += int(_site_atom_evidence(s) == ee.get("atom_rows"))
                actual_operation_ids = _site_operation_evidence(s)
                expected_operation_ids = ee.get("operation_ids")
                evidence += int(
                    actual_operation_ids == expected_operation_ids
                    or (
                        isinstance(actual_operation_ids, list)
                        and isinstance(expected_operation_ids, list)
                        and set(actual_operation_ids) == set(expected_operation_ids)
                    )
                )
                trace_hits.append(float(_operation_trace_matches(s, es)))
                tol = _scalar_number(_coordinate_tolerance(s))
                evidence += int(
                    equal(tol, ee.get("coordinate_tolerance"), 1e-9)
                    or (isinstance(tol, (int, float)) and 0 < float(tol) <= float(ee.get("coordinate_tolerance", 0)))
                )
            site_identity_hits.append(identity / (6 * len(exp_sites)))
            orbit_hits.append(orbit / (3 * len(exp_sites)))
            closure_hits.append(closure / (2 * len(exp_sites)))
            evidence_hits.append(evidence / (3 * len(exp_sites)))
            trace_score = sum(trace_hits) / len(exp_sites) if exp_sites else 0.0
            operation_hits.append((operation_source_hit + trace_score) / 3)

        actual_formula = rec.get("formula_reconciliation")
        expected_formula = exp["formula_reconciliation"]
        fh = 0
        if isinstance(actual_formula, dict):
            formula_status = _status_word(actual_formula.get("status"))
            fh += int(formula_status == _status_word(expected_formula.get("status")))
            fh += int(
                map_equal(_formula_map(actual_formula, "derived_totals"), expected_formula.get("derived_totals"))
                or (formula_status == "unknown" and not expected_formula.get("derived_totals"))
            )
            fh += int(
                map_equal(_formula_map(actual_formula, "expected_totals"), expected_formula.get("expected_totals"))
                or (formula_status == "unknown" and expected_formula.get("expected_totals") is None)
            )
            fh += int(_unknown_rows(rec) == expected_formula.get("unknown_atom_rows"))
            fh += int(_formula_value(actual_formula, "formula_raw") == expected_formula.get("formula_raw"))
            fh += int(_formula_inventory_matches(actual_formula, expected_formula))
            fh += contribution_completion(actual_formula, expected_formula, rec, exp)
        formula_hits.append(fh / 7)

    details["metadata"] = sum(metadata_hits) / len(exp_records)
    details["site_identity"] = sum(site_identity_hits) / len(exp_records)
    details["orbit_and_class"] = sum(orbit_hits) / len(exp_records)
    details["operation_evidence"] = sum(operation_hits) / len(exp_records)
    details["closure_and_multiplicity"] = sum(closure_hits) / len(exp_records)
    details["formula"] = sum(formula_hits) / len(exp_records)
    details["evidence"] = sum(evidence_hits) / len(exp_records)
    details["operation_group"] = sum(group_hits) / len(exp_records)

    expected_comparative = expected.get("comparative_audit", {})
    actual_comparative = actual.get("comparative_audit")
    details["comparative"] = comparative_completion(actual_comparative, expected_comparative)

    # D7: summary and record dispositions.
    # The manifest, the declared schema version and the record-name set are claims *about*
    # the register rather than findings in it: they say which files were covered, not what
    # the register establishes about them.  An index is worth what it indexes, so this
    # coverage credit is carried by the record content behind it.  Saturating keeps a
    # register that carries real record content from paying for the index at all.
    RECORD_CONTENT = ("metadata", "site_identity", "orbit_and_class", "operation_evidence",
                      "closure_and_multiplicity", "formula", "evidence", "operation_group")
    register_substance = min(
        1.0,
        (sum(details[key] for key in RECORD_CONTENT) / len(RECORD_CONTENT)) / INDEX_CREDIT_SATURATION,
    )
    details["manifest"] *= register_substance
    details["register_substance"] = register_substance

    summary_hit = 0.0
    if actual.get("schema_version") == expected.get("schema_version"):
        summary_hit += 0.2 * register_substance
    if actual_records and set(actual_records) == set(exp_records):
        summary_hit += 0.2 * register_substance
    # The record adjudication is normalised through _status_word here as everywhere else: the
    # instruction fixes the vocabulary as supported / conflict / unknown, so any spelling that
    # normalises to the same adjudication counts.
    if all(_status_word(actual_records.get(name, {}).get("status")) == _status_word(exp.get("status"))
           for name, exp in exp_records.items()):
        summary_hit += 0.2
    if _aggregate_matches(actual.get("aggregate"), expected.get("aggregate")):
        summary_hit += 0.4
    details["summary"] = summary_hit

    completion_dimensions = ("site_identity", "orbit_and_class", "operation_evidence",
                             "closure_and_multiplicity", "formula", "evidence",
                             "operation_group")
    details["business_completion"] = (
        set(_manifest_names(manifest.get("files", []))) == set(exp_files)
        and set(actual_records) == set(exp_records)
        and all(details[key] == 1.0 for key in completion_dimensions)
        and comparative_business_complete(actual_comparative, expected_comparative)
        and all(_relative_material_path(_source_path(actual_records[name].get("source", {})))
                == exp["source"]["path"] for name, exp in exp_records.items())
        and all(_space_group_number(actual_records[name].get("metadata", {}))
                == exp["metadata"]["space_group_number_raw"]
                and _operation_complete(actual_records[name].get("source", {}),
                                        actual_records[name].get("metadata", {}))
                == exp["metadata"]["operation_loop_complete"]
                for name, exp in exp_records.items())
        and all(_status_word(actual_records[name].get("status")) == _status_word(exp.get("status"))
                for name, exp in exp_records.items())
        and _aggregate_matches(actual.get("aggregate"), expected.get("aggregate")))
    reversal_rate = conclusion_reversal_rate(actual)
    details["conclusion_reversal_rate"] = reversal_rate

    return details


# ---------------------------------------------------------------------------
# Self-contradicting adjudications (D02).
#
# A formula reconciliation that declares itself supported while its own derived and expected totals
# differ by more than the tolerance the same block declares, or declares a conflict between two
# identical maps, states the opposite of its own arithmetic.  A comparative audit whose pairwise
# same-signature flags disagree with its own signature grouping does the same.  Both are recomputed
# from the register alone.
# ---------------------------------------------------------------------------


def _numeric_leaves(value, depth=0):
    """Numbers held by a tolerance value: a scalar, a {value: ...} pair, or a per-element map."""
    number = _scalar_number(value, ("value", "abs", "absolute", "float", "decimal"))
    if number is not None:
        return [number]
    if isinstance(value, dict) and depth < 3:
        return [n for item in value.values() for n in _numeric_leaves(item, depth + 1)]
    return []


def _declared_tolerance(block, depth=0):
    """Largest numeric tolerance the block declares for itself (sensitivity diagnostics excluded)."""
    found = []
    if not isinstance(block, dict) or depth > 2:
        return found
    for key, value in block.items():
        name = str(key).lower()
        if "sensitiv" in name:
            continue
        if "toler" in name:
            found.extend(n for n in _numeric_leaves(value) if n >= 0)
            continue
        if isinstance(value, dict):
            found.extend(_declared_tolerance(value, depth + 1))
    return found


def _formula_self_contradiction(formula):
    if not isinstance(formula, dict):
        return False
    status = _status_word(formula.get("status"))
    derived = _formula_map(formula, "derived_totals")
    expected = _formula_map(formula, "expected_totals")
    if not isinstance(derived, dict) or not isinstance(expected, dict) or not derived or not expected:
        return False
    if set(derived) != set(expected):
        return False
    tolerances = _declared_tolerance(formula)
    default = max(tolerances) if tolerances else 1e-9
    per_element = formula.get("formula_tolerance")
    within = []
    for element in expected:
        a, b = _scalar_number(derived[element]), _scalar_number(expected[element])
        if a is None or b is None:
            return False
        tolerance = _scalar_number(per_element.get(element)) if isinstance(per_element, dict) else None
        allowed = tolerance if tolerance is not None and tolerance >= 0 else default
        within.append(abs(a - b) <= allowed + 1e-12)
    if status == "supported":
        return not all(within)
    if status == "conflict":
        return all(within)
    return False



def self_contradictions(actual):
    """Record names (and the comparative block) whose adjudication contradicts their own numbers."""
    hits = []
    records = actual.get("records") if isinstance(actual, dict) else None
    for index, record in enumerate(records if isinstance(records, list) else []):
        if isinstance(record, dict) and _formula_self_contradiction(record.get("formula_reconciliation")):
            hits.append(_record_key(record.get("file")) or f"#{index}")
    block = actual.get("comparative_audit") if isinstance(actual, dict) else None
    if _pairwise_contradictions(block, _record_partition(block)):
        hits.append("comparative_audit")
    return hits


# ---------------------------------------------------------------------------
# Register completeness and usability gate (D03).
#
# The memorandum requires one record per supplied CIF, each carrying its sites, the full affine
# operation list, an operation_group object and a formula reconciliation, beside a manifest of the
# four files, a comparative audit and an aggregate. A present unit whose mandatory source binding
# or scientific invariant is unusable is equivalent to a missing evidence unit for completion.
# All such units are listed in one bounded coverage damage instance.
# ---------------------------------------------------------------------------


def missing_register_units(actual, expected):
    missing = []
    records = actual.get("records") if isinstance(actual, dict) else None
    by_name = {
        _record_key(r.get("file")): r for r in (records if isinstance(records, list) else [])
        if isinstance(r, dict) and _record_key(r.get("file"))
    }
    for exp in expected["records"]:
        name = exp["file"]
        rec = by_name.get(name)
        if rec is None:
            missing.append(f"{name}: record")
            rec = {}
        sites = rec.get("sites")
        if not isinstance(sites, list) or not sites:
            missing.append(f"{name}: sites")
        else:
            # A site entry is only auditable when it carries the derived orbit
            # invariants that P04/P06/P08 score.  Merely listing labels (or an
            # empty placeholder object) must not satisfy the completeness gate.
            for index, site in enumerate(sites):
                if not isinstance(site, dict):
                    missing.append(f"{name}: sites[{index}]")
                    continue
                for field in ("orbit_size", "stabilizer_order", "position_class", "closure_check", "supplied_multiplicity"):
                    if site.get(field) is None:
                        missing.append(f"{name}: sites[{index}].{field}")
                if not _site_trace(site):
                    missing.append(f"{name}: sites[{index}].operation_trace")
        if not _first(rec.get("formula_reconciliation"), "contribution_ledger", "contributions", "row_contributions"):
            missing.append(f"{name}: contribution_ledger")
        source = rec.get("source")
        metadata = rec.get("metadata", {})
        if _space_group_number(metadata) != exp["metadata"]["space_group_number_raw"]:
            missing.append(f"{name}: usable raw space-group number")
        if _operation_complete(source, metadata) != exp["metadata"]["operation_loop_complete"]:
            missing.append(f"{name}: usable operation-loop state")
        operations = source.get("affine_operations") if isinstance(source, dict) else None
        if not isinstance(operations, list) or len(operations) != len(exp["source"]["affine_operations"]):
            missing.append(f"{name}: affine_operations")
        elif not _affine_matches(source, exp["source"]):
            missing.append(f"{name}: usable affine_operations")
        if not _composition_matches(source, exp["source"]):
            missing.append(f"{name}: usable operation_composition")
        if not isinstance(rec.get("operation_group"), dict) or not rec.get("operation_group"):
            missing.append(f"{name}: operation_group")
        elif not _operation_group_matches(rec, exp):
            missing.append(f"{name}: usable operation_group")
        if not isinstance(rec.get("formula_reconciliation"), dict) or not rec.get("formula_reconciliation"):
            missing.append(f"{name}: formula_reconciliation")
        else:
            formula = rec["formula_reconciliation"]
            expected_formula = exp["formula_reconciliation"]
            if _status_word(formula.get("status")) != _status_word(expected_formula.get("status")):
                missing.append(f"{name}: usable formula status")
            if contribution_completion(formula, expected_formula, rec, exp) < 1.0:
                missing.append(f"{name}: usable contribution_ledger")
            ledger = _first(formula, "contribution_ledger", "contributions", "row_contributions")
            for index, row in enumerate(ledger if isinstance(ledger, list) else []):
                if isinstance(row, dict) and _status_word(row.get("status")) in {"unknown", "conflict"} \
                        and not (isinstance(row.get("reason"), str) and row["reason"].strip()):
                    missing.append(f"{name}: contribution_ledger[{index}].reason")

        # Presence alone is insufficient for the scientific core: each site must remain
        # source-bound and its mandatory invariant/trace evidence must be usable.
        if isinstance(sites, list):
            for expected_site in exp["sites"]:
                site = site_match(rec, expected_site)
                label = expected_site.get("representative_label", "?")
                if not site:
                    missing.append(f"{name}: usable site {label}")
                    continue
                for field in ("representative_coordinate_raw", "representative_coordinate_mod1", "elements"):
                    if site.get(field) is None:
                        missing.append(f"{name}: site {label}.{field}")
                if _scalar_number(site.get("orbit_size")) != expected_site.get("orbit_size"):
                    missing.append(f"{name}: usable site {label}.orbit_size")
                if _scalar_number(site.get("stabilizer_order")) != expected_site.get("stabilizer_order"):
                    missing.append(f"{name}: usable site {label}.stabilizer_order")
                if site.get("position_class") != expected_site.get("position_class"):
                    missing.append(f"{name}: usable site {label}.position_class")
                if not _closure_matches(site, expected_site):
                    missing.append(f"{name}: usable site {label}.closure_check")
                if not _multiplicity_matches(site, expected_site):
                    missing.append(f"{name}: usable site {label}.supplied_multiplicity")
                if not _operation_trace_matches(site, expected_site):
                    missing.append(f"{name}: usable site {label}.operation_trace")
                tolerance = _scalar_number(_coordinate_tolerance(site))
                expected_tolerance = expected_site.get("evidence", {}).get("coordinate_tolerance")
                if not (isinstance(tolerance, (int, float)) and 0 < tolerance <= expected_tolerance):
                    missing.append(f"{name}: usable site {label}.coordinate_tolerance")
    manifest = actual.get("input_manifest") if isinstance(actual, dict) else None
    files = manifest.get("files") if isinstance(manifest, dict) else None
    if len(set(_manifest_names(files))) < len(expected["input_manifest"]["files"]):
        missing.append("input_manifest: files")
    for key in ("comparative_audit", "aggregate"):
        if not isinstance(actual.get(key), dict) or not actual.get(key):
            missing.append(key)
    if isinstance(actual.get("comparative_audit"), dict) and actual.get("comparative_audit") \
            and not comparative_business_complete(actual["comparative_audit"], expected["comparative_audit"]):
        missing.append("comparative_audit: usable conclusions and source anchors")
    return missing


# ---------------------------------------------------------------------------
# pd-ledger-v1 settlement.
PARAMS = Path(os.environ.get("SCORING_PARAMS", Path(__file__).resolve().parent / "scoring_params.json"))
# Positive item -> the dimension of score_report() it settles.
POSITIVE_DIMENSIONS = {
    "P01": "manifest",
    "P02": "metadata",
    "P03": "site_identity",
    "P04": "orbit_and_class",
    "P05": "operation_evidence",
    "P06": "closure_and_multiplicity",
    "P07": "formula",
    "P08": "evidence",
    "P09": "operation_group",
    "P10": "comparative",
    "P11": "summary",
}


def deliverable(arg: str) -> Path:
    """The contract passes a directory (rollout artifacts/ or task golden/); the container passes the file.

    Only the two locations the contract names are read: the directory itself and its output/
    subdirectory, the same pair tests/test.sh resolves.  There is deliberately no recursive
    search: a sorted glob would score whichever stray copy sorts first - a draft, a backup, a
    scratch tree - instead of the submitted deliverable.  When neither named location holds a
    file the missing path is returned, and the register scores 0.
    """
    p = Path(arg)
    if not p.is_dir():
        return p
    named = p / "orbit_evidence.json"
    if named.is_file():
        return named
    return p / "output" / "orbit_evidence.json"


def settle(result: dict, details: dict | None, damage: list) -> dict:
    """Settle the scored dimensions as pd-ledger-v1."""
    params = json.loads(PARAMS.read_text(encoding="utf-8"))
    weights, coefficients = params["positive_weights"], params["deduction_coefficients"]
    details = details or {}
    completion = {k: round(min(1.0, max(0.0, float(details.get(POSITIVE_DIMENSIONS[k], 0.0)))), 10)
                  for k in weights}
    # Missing or unusable units already lose their dimension credit. Keep one bounded
    # coverage deduction rather than multiplying 0.2 for every missing unit.
    missing_keys = [key for key, items in damage if "D03" in items]
    instances = [{"key": key, "item_ids": [i for i in items if i != "D03"]}
                 for key, items in damage if any(i != "D03" for i in items)]
    if missing_keys:
        instances.append({"key": "required_register_coverage", "item_ids": ["D03"],
                          "affected_units": missing_keys})
    earned = sum(weights[k] * completion[k] for k in weights)
    retention = math.prod(min(coefficients[i] for i in inst["item_ids"]) for inst in instances)
    final = earned * retention
    result["reward"] = final
    result["reward_strict"] = final
    # Completion is the conjunction of the published required evidence units and
    # their scientific correctness, independently of weights or strict score.
    complete = details.get("business_completion") is True and not damage
    result["reward_lenient"] = int(complete)
    result["rewards"] = {"strict": final, "lenient": int(complete)}
    result["reward_formulas"] = {
        "strict": "positive_earned * retention (pd-ledger-v1; weights and coefficients from scoring_params.json)"}
    result["scoring_ledger"] = {"schema_version": "pd-ledger-v1", "positive_completion": completion,
                                "damage_instances": instances, "positive_earned": earned,
                                "retention": retention, "final_score": final}
    return result


def main() -> int:
    submission = deliverable(sys.argv[1] if len(sys.argv) > 1 else "/workspace/output/orbit_evidence.json")
    actual, error = load(submission)
    expected, expected_error = load(EXPECTED)
    details, damage = None, []
    if expected_error:
        raise RuntimeError("required evaluator ground truth unavailable: " + expected_error)
    if error:
        result = {"error": error}
    elif not isinstance(actual, dict):
        result = {"error": "top-level JSON value is not an object"}
    else:
        details = score_report(actual, expected)
        # A changed supplied file invalidates source-dependent claims.
        tampered = []
        for name, digest in SOURCE_HASHES.items():
            path = MATERIALS / name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                tampered.append(name)
        if tampered:
            details["source_integrity"] = {"status": "conflict", "files": tampered}
            damage.append(("source CIF hash mismatch: " + ", ".join(tampered), ["D01"]))
        contradictions = self_contradictions(actual)
        if contradictions:
            details["self_contradictions"] = contradictions
            damage.append(("adjudication contradicts its own numbers: " + ", ".join(contradictions), ["D02"]))
        missing_units = missing_register_units(actual, expected)
        if missing_units:
            details["missing_register_units"] = missing_units
            for unit in missing_units:
                damage.append(("required register unit missing or unusable: " + unit, ["D03"]))
        semantic=adjudicate(actual,expected,hashlib.sha256(submission.read_bytes()).hexdigest())
        semantic_required=set(json.loads(PARAMS.read_text(encoding='utf-8'))['semantic_required'])
        if set(semantic['items'])!=semantic_required:raise RuntimeError('semantic owner vocabulary mismatch')
        semantic_ok=all(item['fraction']==1 for item in semantic['items'].values())
        details['semantic_review']=semantic
        details['semantic_scope_integrity']=semantic_ok
        if not semantic_ok:damage.append(('open scientific claim exceeds source evidence or applicability', ['D04']))
        result = {"checks": details,"semantic_judge":semantic}
    print(json.dumps(settle(result, details, damage), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

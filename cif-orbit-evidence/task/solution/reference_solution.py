#!/usr/bin/env python3
"""Derive the orbit evidence report directly from the supplied CIF files."""

from __future__ import annotations

import json
import math
import re
import sys
from fractions import Fraction
from pathlib import Path


class Token:
    __slots__ = ("text", "line")

    def __init__(self, text: str, line: int):
        self.text = text
        self.line = line


def tokenize_cif(path: Path) -> list[Token]:
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[Token] = []
    i = 0
    while i < len(lines):
        line_no = i + 1
        line = lines[i]
        if line.startswith(";"):
            block = []
            start = line_no
            i += 1
            while i < len(lines) and not lines[i].startswith(";"):
                block.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            out.append(Token("\n".join(block), start))
            continue
        j = 0
        n = len(line)
        while j < n:
            while j < n and line[j].isspace():
                j += 1
            if j >= n or line[j] == "#":
                break
            start = j
            if line[j] in "'\"":
                quote = line[j]
                j += 1
                chars = []
                while j < n and line[j] != quote:
                    chars.append(line[j])
                    j += 1
                if j < n:
                    j += 1
                out.append(Token("".join(chars), line_no))
                continue
            while j < n and not line[j].isspace() and line[j] != "#":
                j += 1
            if j > start:
                out.append(Token(line[start:j], line_no))
            if j < n and line[j] == "#":
                break
        i += 1
    return out


def parse_cif(path: Path) -> tuple[dict[str, tuple[str, int]], list[dict]]:
    tokens = tokenize_cif(path)
    scalars: dict[str, tuple[str, int]] = {}
    loops: list[dict] = []
    i = 0
    while i < len(tokens):
        text = tokens[i].text
        low = text.lower()
        if low == "loop_":
            i += 1
            tags: list[Token] = []
            while i < len(tokens) and tokens[i].text.startswith("_"):
                tags.append(tokens[i])
                i += 1
            if not tags:
                continue
            values: list[Token] = []
            width = len(tags)
            while i < len(tokens):
                value = tokens[i]
                vl = value.text.lower()
                if (len(values) % width == 0 and value.text.startswith("_")) or vl == "loop_" or vl.startswith("data_") or vl in {"stop_", "save_"}:
                    break
                values.append(value)
                i += 1
            rows = []
            complete = len(values) - (len(values) % width)
            for j in range(0, complete, width):
                rows.append(values[j : j + width])
            loops.append({"tags": [x.text.lower() for x in tags], "rows": rows, "incomplete": complete != len(values)})
            continue
        if text.startswith("_"):
            tag = text.lower()
            if i + 1 < len(tokens):
                scalars[tag] = (tokens[i + 1].text, tokens[i + 1].line)
                i += 2
            else:
                scalars[tag] = ("?", tokens[i].line)
                i += 1
            continue
        i += 1
    return scalars, loops


def first_scalar(scalars: dict[str, tuple[str, int]], aliases: tuple[str, ...]):
    for alias in aliases:
        if alias.lower() in scalars:
            return scalars[alias.lower()]
    return None


_NUM = re.compile(r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?)(?:\(\d+\))?$")


def parse_number(raw: str) -> Fraction | None:
    if raw in {"?", ".", ""}:
        return None
    rational = raw.strip()
    if re.fullmatch(r"[+-]?\d+\s*/\s*[+-]?\d+", rational):
        try:
            numerator, denominator = re.split(r"\s*/\s*", rational)
            return Fraction(int(numerator), int(denominator))
        except (ValueError, ZeroDivisionError):
            return None
    m = _NUM.match(raw.strip())
    if not m:
        return None
    try:
        return Fraction(m.group(1))
    except (ValueError, ZeroDivisionError):
        return None


def as_json_number(value: Fraction | None):
    if value is None:
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def frac_mod(value: Fraction) -> Fraction:
    return value - math.floor(float(value))


def periodic_close(a: Fraction, b: Fraction, tolerance: Fraction = Fraction(1, 1000)) -> bool:
    delta = a - b
    nearest = round(float(delta))
    return abs(delta - nearest) <= tolerance


def split_terms(expr: str) -> list[str]:
    expr = expr.replace(" ", "")
    if not expr:
        return []
    if expr[0] not in "+-":
        expr = "+" + expr
    return [x for x in re.split(r"(?=[+-])", expr) if x]


def parse_component(expr: str) -> tuple[tuple[int, int, int], Fraction] | None:
    coeff = [0, 0, 0]
    translation = Fraction(0)
    for term in split_terms(expr):
        sign = -1 if term.startswith("-") else 1
        body = term[1:] if term[:1] in "+-" else term
        if not body:
            return None
        var = body[-1].lower() if body[-1].lower() in "xyz" else None
        if var:
            factor = body[:-1].replace("*", "")
            if factor in {"", "+"}:
                magnitude = 1
            else:
                try:
                    magnitude = int(factor)
                except ValueError:
                    return None
            coeff["xyz".index(var)] += sign * magnitude
        else:
            value = parse_number(("-" if sign < 0 else "") + body)
            if value is None:
                return None
            translation += value
    return tuple(coeff), translation


def parse_operation(expr: str):
    parts = [part for part in expr.split(",") if part != ""]
    if len(parts) != 3:
        return None
    parsed = [parse_component(part) for part in parts]
    return parsed if all(item is not None for item in parsed) else None


def apply_operation(operation, coordinate: tuple[Fraction, Fraction, Fraction]):
    return tuple(frac_mod(value) for value in apply_operation_raw(operation, coordinate))


def apply_operation_raw(operation, coordinate: tuple[Fraction, Fraction, Fraction]):
    result = []
    for coeff, translation in operation:
        value = translation
        for c, x in zip(coeff, coordinate):
            value += c * x
        result.append(value)
    return tuple(result)


def compose_operations(left, right):
    """Return the affine action left(right(r)) as integer matrix plus translation."""
    left_w = [item[0] for item in left]
    right_w = [item[0] for item in right]
    matrix = []
    for row in left_w:
        matrix.append(tuple(sum(row[k] * right_w[k][j] for k in range(3)) for j in range(3)))
    right_t = tuple(item[1] for item in right)
    translation = tuple(
        left[i][1] + sum(left_w[i][k] * right_t[k] for k in range(3))
        for i in range(3)
    )
    return [(matrix[i], translation[i]) for i in range(3)]


def affine_key(operation):
    """Canonicalize an affine action for equality on fractional coordinates."""
    matrix = tuple(tuple(int(value) for value in row[0]) for row in operation)
    translation = tuple(frac_mod(row[1]) for row in operation)
    return matrix, translation


def matrix_determinant(matrix):
    a, b, c = matrix[0]
    d, e, f = matrix[1]
    g, h, i = matrix[2]
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)


def affine_order(operation, identity, limit):
    """Find the least positive power returning to identity modulo lattice shifts."""
    current = identity
    identity_key = affine_key(identity)
    for order in range(1, limit + 1):
        current = compose_operations(operation, current)
        if affine_key(current) == identity_key:
            return order
    return None


def find_loop(loops: list[dict], required: tuple[str, ...]):
    required = tuple(x.lower() for x in required)
    for loop in loops:
        if all(tag in loop["tags"] for tag in required):
            return loop
    return None


def element_from_token(raw: str, label: str) -> tuple[str | None, bool]:
    cleaned = re.sub(r"[+-].*$", "", raw or "")
    match = re.match(r"([A-Z][a-z]?)", cleaned)
    if match:
        return match.group(1), False
    match = re.match(r"([A-Z][a-z]?)", label or "")
    return (match.group(1), True) if match else (None, True)


def parse_formula(raw: str | None):
    if not raw or raw in {"?", "."}:
        return None
    text = re.sub(r"\s+", "", raw)
    number = re.compile(r"(?:\d+(?:\.\d*)?|\.\d+)")

    def group(pos: int, stop: str | None = None):
        result: dict[str, Fraction] = {}
        while pos < len(text):
            if stop and text[pos] == stop:
                return result, pos + 1
            if text[pos] == "(":
                nested, pos = group(pos + 1, ")")
                if nested is None:
                    return None, pos
                match = number.match(text, pos)
                factor = Fraction(match.group(0)) if match else Fraction(1)
                pos = match.end() if match else pos
                for element, count in nested.items():
                    result[element] = result.get(element, Fraction(0)) + count * factor
                continue
            match = re.match(r"[A-Z][a-z]?", text[pos:])
            if not match:
                return None, pos
            element = match.group(0)
            pos += len(element)
            count_match = number.match(text, pos)
            count = Fraction(count_match.group(0)) if count_match else Fraction(1)
            pos = count_match.end() if count_match else pos
            result[element] = result.get(element, Fraction(0)) + count
        if stop:
            return None, pos
        return result, pos

    result, end = group(0)
    return result if result is not None and end == len(text) else None


def formula_tag_inventory(scalars: dict[str, tuple[str, int]]):
    inventory = []
    for tag, (raw, line) in scalars.items():
        if "formula" not in tag.lower() or "formula_units" in tag.lower():
            continue
        parsed = parse_formula(raw)
        inventory.append({
            "tag": tag,
            "raw": raw,
            "line": line,
            "parsed_counts": {k: as_json_number(v) for k, v in sorted(parsed.items())} if parsed else None,
            "status": "parsed" if parsed else "unknown",
        })
    parsed_maps = [item["parsed_counts"] for item in inventory if item["parsed_counts"] is not None]
    relation_status = "unknown" if not parsed_maps else ("supported" if all(item == parsed_maps[0] for item in parsed_maps[1:]) else "conflict")
    return inventory, {"status": relation_status, "parsed_tag_count": len(parsed_maps)}


def parse_atom_loop(loop: dict):
    tags = loop["tags"]
    index = {tag: i for i, tag in enumerate(tags)}
    required = ["_atom_site_label", "_atom_site_fract_x", "_atom_site_fract_y", "_atom_site_fract_z"]
    if not all(tag in index for tag in required):
        return []
    atoms = []
    for row_no, row in enumerate(loop["rows"], 1):
        label = row[index["_atom_site_label"]].text
        raw_xyz = [row[index[tag]].text for tag in required[1:]]
        xyz = [parse_number(x) for x in raw_xyz]
        type_tag = next((tag for tag in ("_atom_site_type_symbol", "_atom_site_type") if tag in index), None)
        occ_tag = next((tag for tag in ("_atom_site_occupancy", "_atom_site_occ") if tag in index), None)
        mult_tags = [tag for tag in tags if "multiplicity" in tag or "wyckoff" in tag]
        atoms.append({
            "row": row_no,
            "line": row[0].line,
            "label": label,
            "raw_xyz": raw_xyz,
            "xyz": tuple(xyz) if all(x is not None for x in xyz) else None,
            "type_raw": row[index[type_tag]].text if type_tag else None,
            "occupancy_raw": row[index[occ_tag]].text if occ_tag else None,
            "occupancy": parse_number(row[index[occ_tag]].text) if occ_tag else None,
            "multiplicity_raw": [row[index[tag]].text for tag in mult_tags],
        })
    return atoms


def parse_operations(loops: list[dict]):
    candidates = []
    for loop in loops:
        op_tag = next((tag for tag in loop["tags"] if "operation_xyz" in tag or "equiv_pos_as_xyz" in tag), None)
        if op_tag:
            id_tag = next((tag for tag in loop["tags"] if tag.endswith("id") or "site_id" in tag), None)
            for row_no, row in enumerate(loop["rows"], 1):
                expr = row[loop["tags"].index(op_tag)].text
                parsed = parse_operation(expr)
                if parsed is not None:
                    op_id = row[loop["tags"].index(id_tag)].text if id_tag else str(row_no)
                    candidates.append((op_id, expr, parsed, row[0].line))
            if candidates:
                return candidates, loop["incomplete"]
    return [], False


def analyze_file(path: Path) -> dict:
    scalars, loops = parse_cif(path)
    atom_loop = find_loop(loops, ("_atom_site_label", "_atom_site_fract_x", "_atom_site_fract_y", "_atom_site_fract_z"))
    atoms = parse_atom_loop(atom_loop) if atom_loop else []
    operations, op_incomplete = parse_operations(loops)
    operation_count = len(operations)
    op_ids = [item[0] for item in operations]
    operation_by_id = {item[0]: item for item in operations}
    affine_operations = [
        {
            "id": op_id,
            "raw": expr,
            "source_line": line,
            "matrix": [list(coeff) for coeff, _ in parsed],
            "translation": [as_json_number(translation) for _, translation in parsed],
        }
        for op_id, expr, parsed, line in operations
    ]
    composition_map = {}
    unmatched_compositions = []
    operation_keys = {}
    for op_id, _, parsed, _ in operations:
        key = (tuple(tuple(coeff) for coeff, _ in parsed), tuple(frac_mod(translation) for _, translation in parsed))
        operation_keys[key] = op_id
    for left_id, _, left, _ in operations:
        for right_id, _, right, _ in operations:
            composed = compose_operations(left, right)
            key = (tuple(tuple(coeff) for coeff, _ in composed), tuple(frac_mod(translation) for _, translation in composed))
            result_id = operation_keys.get(key)
            composition_map[f"{left_id}|{right_id}"] = result_id
            if result_id is None:
                unmatched_compositions.append([left_id, right_id])
    operation_composition = {
        "status": "supported" if operations and not op_incomplete and not unmatched_compositions else ("unknown" if not operations else "conflict"),
        "pair_count": operation_count * operation_count,
        "composition_map": composition_map,
        "unmatched_pairs": unmatched_compositions,
    }

    groups: list[list[int]] = []
    parent = list(range(len(atoms)))

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        a, b = root(a), root(b)
        if a != b:
            parent[b] = a

    if operations:
        for i, first in enumerate(atoms):
            if first["xyz"] is None:
                continue
            for j in range(i + 1, len(atoms)):
                second = atoms[j]
                if second["xyz"] is None:
                    continue
                if any(all(periodic_close(a, b) for a, b in zip(apply_operation(op, first["xyz"]), second["xyz"])) for _, _, op, _ in operations):
                    union(i, j)
    for i in range(len(atoms)):
        groups.append([])
    for i in range(len(atoms)):
        groups[root(i)].append(i)
    groups = [g for g in groups if g]
    sites = []
    for site_index, group in enumerate(sorted(groups, key=lambda g: g[0]), 1):
        rep = atoms[group[0]]
        transformed = []
        stabilizer = 0
        if rep["xyz"] is not None and operations:
            for _, _, op, _ in operations:
                image = apply_operation(op, rep["xyz"])
                if any(all(periodic_close(image[k], prior[k]) for k in range(3)) for prior in transformed):
                    pass
                else:
                    transformed.append(image)
                if all(periodic_close(image[k], rep["xyz"][k]) for k in range(3)):
                    stabilizer += 1
        orbit_size = len(transformed) if transformed else None
        closure_product = orbit_size * stabilizer if orbit_size is not None else None
        closure_status = "unknown"
        if operation_count and not op_incomplete and closure_product is not None:
            closure_status = "supported" if closure_product == operation_count else "conflict"
        position_class = "unknown"
        if closure_status == "supported":
            position_class = "special" if stabilizer > 1 else "general"
        supplied_mult = []
        for idx in group:
            supplied_mult.extend(atoms[idx]["multiplicity_raw"])
        mult_status = "not_supplied" if not supplied_mult else "unknown"
        if supplied_mult and orbit_size is not None:
            numeric = []
            for value in supplied_mult:
                m = re.match(r"\s*(\d+)", value)
                if m:
                    numeric.append(int(m.group(1)))
            mult_status = "supported" if numeric and all(x == orbit_size for x in numeric) else "conflict"
        labels = [atoms[idx]["label"] for idx in group]
        elements = []
        for idx in group:
            element, fallback = element_from_token(atoms[idx]["type_raw"], atoms[idx]["label"])
            elements.append({"label": atoms[idx]["label"], "element": element, "fallback": fallback})
        operation_trace = []
        if rep["xyz"] is not None:
            for op_id, expr, op, line in operations:
                unreduced = apply_operation_raw(op, rep["xyz"])
                reduced = tuple(frac_mod(value) for value in unreduced)
                matched_rows = [
                    atom["row"] for atom in atoms
                    if atom["xyz"] is not None and all(periodic_close(reduced[k], atom["xyz"][k]) for k in range(3))
                ]
                stabilizes = all(periodic_close(reduced[k], rep["xyz"][k]) for k in range(3))
                operation_trace.append({
                    "operation_id": op_id,
                    "raw": expr,
                    "source_line": line,
                    "unreduced_coordinate": [as_json_number(value) for value in unreduced],
                    "reduced_coordinate": [as_json_number(value) for value in reduced],
                    "stabilizes": stabilizes,
                    "matched_source_rows": matched_rows,
                })
        sites.append({
            "site_id": f"site_{site_index:02d}",
            "representative_label": rep["label"],
            "labels": labels,
            "elements": elements,
            "source_rows": [atoms[idx]["row"] for idx in group],
            "representative_coordinate_raw": rep["raw_xyz"],
            "representative_coordinate_mod1": [as_json_number(frac_mod(x)) for x in rep["xyz"]] if rep["xyz"] else None,
            "orbit_size": orbit_size,
            "stabilizer_order": stabilizer if operations and rep["xyz"] else None,
            "position_class": position_class,
            "closure_check": {
                "operation_count": operation_count,
                "orbit_times_stabilizer": closure_product,
                "status": closure_status,
            },
            "supplied_multiplicity": {"values": supplied_mult, "status": mult_status},
            "evidence": {
                "atom_rows": [atoms[idx]["row"] for idx in group],
                "operation_ids": op_ids,
                "atom_source_lines": [atoms[idx]["line"] for idx in group],
                "coordinate_tolerance": 1e-3,
                "operation_trace": operation_trace,
            },
        })

    # Derive group-level invariants from the supplied affine list and site traces.
    identity = next((parsed for op_id, _, parsed, _ in operations
                     if affine_key(parsed) == (((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                                                (Fraction(0), Fraction(0), Fraction(0)))), None)
    determinant_by_operation = {}
    order_by_operation = {}
    if operations:
        for op_id, _, parsed, _ in operations:
            determinant_by_operation[op_id] = matrix_determinant([coeff for coeff, _ in parsed])
            order_by_operation[op_id] = affine_order(parsed, identity, max(operation_count, 1)) if identity else None
    determinant_classes = {"-1": 0, "0": 0, "1": 0, "other": 0}
    for value in determinant_by_operation.values():
        key = str(value) if value in (-1, 0, 1) else "other"
        determinant_classes[key] += 1
    order_histogram = {}
    for value in order_by_operation.values():
        key = str(value) if value is not None else "unknown"
        order_histogram[key] = order_histogram.get(key, 0) + 1
    fixed_site_profile = {op_id: 0 for op_id in op_ids}
    for site in sites:
        for trace in site["evidence"].get("operation_trace", []):
            if trace.get("stabilizes") and trace.get("operation_id") in fixed_site_profile:
                fixed_site_profile[trace["operation_id"]] += 1
    group_supported = bool(operations and identity and not op_incomplete and not unmatched_compositions
                           and all(value is not None for value in order_by_operation.values()))
    operation_group = {
        "status": "supported" if group_supported else ("unknown" if not operations else "conflict"),
        "identity_operation_id": next((op_id for op_id, _, parsed, _ in operations
                                        if identity is not None and affine_key(parsed) == affine_key(identity)), None),
        "determinant_by_operation": determinant_by_operation,
        "determinant_classes": determinant_classes,
        "operation_orders": order_by_operation,
        "order_histogram": dict(sorted(order_histogram.items())),
        "fixed_site_profile": fixed_site_profile,
        "group_signature": {
            "operation_count": operation_count,
            "determinant_classes": determinant_classes,
            "order_histogram": dict(sorted(order_histogram.items())),
            "fixed_site_histogram": dict(sorted(
                ((str(count), list(fixed_site_profile.values()).count(count))
                 for count in sorted(set(fixed_site_profile.values())))
            )),
        },
        "evidence": {
            "operation_ids": op_ids,
            "site_ids": [site["site_id"] for site in sites],
        },
    }

    formula_pair = first_scalar(scalars, ("_chemical_formula_sum", "_chemical_formula_structural"))
    z_pair = first_scalar(scalars, ("_cell_formula_units_z", "_cell_formula_units_z"))
    number_pair = first_scalar(scalars, ("_space_group_it_number", "_symmetry_int_tables_number"))
    symbol_pair = first_scalar(scalars, ("_space_group_name_h-m_alt", "_symmetry_space_group_name_h-m", "_symmetry_space_group_name_h-m"))
    formula_raw = formula_pair[0] if formula_pair else None
    formula_inventory, formula_tag_relation = formula_tag_inventory(scalars)
    z_value = parse_number(z_pair[0]) if z_pair else None
    formula_counts = parse_formula(formula_raw)
    derived: dict[str, Fraction] = {}
    unknown_rows = []
    contribution_ledger = []
    for site in sites:
        for idx, label in zip(site["source_rows"], site["labels"]):
            atom = atoms[idx - 1]
            element, fallback = element_from_token(atom["type_raw"], atom["label"])
            reasons = []
            if element is None:
                reasons.append("missing or unparseable element")
            if atom["occupancy"] is None:
                reasons.append("missing or unparseable occupancy")
            if site["orbit_size"] is None or site["closure_check"]["status"] != "supported":
                reasons.append("unresolved or non-closed orbit")
            contribution = None if reasons else atom["occupancy"] * site["orbit_size"]
            contribution_ledger.append({
                "source_row": idx, "source_line": atom["line"], "label": label,
                "site_id": site["site_id"], "element_raw": atom["type_raw"],
                "element": element, "fallback": fallback,
                "occupancy_raw": atom["occupancy_raw"],
                "occupancy": as_json_number(atom["occupancy"]) if atom["occupancy"] is not None else None,
                "orbit_size": site["orbit_size"],
                "contribution": as_json_number(contribution) if contribution is not None else None,
                "status": "unknown" if reasons else "supported",
                "reason": "; ".join(reasons) if reasons else "occupancy multiplied by closed orbit size",
            })
            if contribution is None:
                unknown_rows.append(idx)
                continue
            derived[element] = derived.get(element, Fraction(0)) + contribution
    # Propagate half a unit of the occupancy's last reported decimal place
    # through orbit multiplicities. Explicit 0/1 occupancies are exact bounds.
    rounding_budget = {}
    for atom, site in ((atoms[idx - 1], site) for site in sites for idx in site["source_rows"]):
        raw = str(atom.get("occupancy_raw") or "")
        value = atom.get("occupancy")
        if value is None or site.get("orbit_size") is None:
            continue
        token = re.sub(r"\(\d+\)$", "", raw).lower()
        if value in (0, 1):
            uncertainty = 0.0
        else:
            mantissa, _, exponent = token.partition("e")
            digits = len(mantissa.split(".", 1)[1]) if "." in mantissa else 0
            uncertainty = 0.5 * 10 ** ((int(exponent) if exponent else 0) - digits)
        element, _ = element_from_token(atom["type_raw"], atom["label"])
        if element:
            rounding_budget[element] = rounding_budget.get(element, 0.0) + uncertainty * site["orbit_size"]
    expected = None
    formula_status = "unknown"
    reason = "missing formula, formula-unit count, occupancy, or closed orbit"
    if formula_counts is not None and z_value is not None and not unknown_rows and all(s["closure_check"]["status"] == "supported" for s in sites):
        expected = {element: count * z_value for element, count in formula_counts.items()}
        keys = set(derived) | set(expected)
        formula_status = "supported" if all(abs(float(derived.get(k, 0) - expected.get(k, 0))) <= rounding_budget.get(k, 0.0) + 1e-12 for k in keys) else "conflict"
        reason = "derived occupancy-weighted totals compared with formula counts times supplied Z"
    reconciliation = {
        "contribution_ledger": contribution_ledger,
        "formula_raw": formula_raw,
        "formula_tolerance": rounding_budget,
        "tolerance_method": "sum over each element of orbit multiplicity * half occupancy last-place unit; exact 0/1 bounds contribute zero",
        "formula_counts": {k: as_json_number(v) for k, v in formula_counts.items()} if formula_counts else None,
        "formula_units_z_raw": z_pair[0] if z_pair else None,
        "derived_totals": {k: as_json_number(v) for k, v in sorted(derived.items())},
        "expected_totals": {k: as_json_number(v) for k, v in sorted(expected.items())} if expected else None,
        "status": formula_status,
        "reason": reason,
        "unknown_atom_rows": unknown_rows,
        "formula_tag_inventory": formula_inventory,
        "formula_tag_relation": formula_tag_relation,
    }
    unknown_count = sum(1 for s in sites if s["position_class"] == "unknown") + (1 if formula_status == "unknown" else 0)
    conflict_count = sum(1 for s in sites if s["position_class"] == "unknown" or s["closure_check"]["status"] == "conflict" or s["supplied_multiplicity"]["status"] == "conflict") + (1 if formula_status == "conflict" else 0)
    return {
        "file": path.name,
        "source": {
            "path": f"materials/{path.name}",
            "atom_loop_rows": len(atoms),
            "operation_ids": op_ids,
            "affine_operations": affine_operations,
            "operation_composition": operation_composition,
        },
        "metadata": {
            "formula_sum_raw": formula_raw,
            "formula_units_z_raw": z_pair[0] if z_pair else None,
            "space_group_number_raw": number_pair[0] if number_pair else None,
            "space_group_symbol_raw": symbol_pair[0] if symbol_pair else None,
            "operation_count": operation_count,
            "operation_loop_complete": bool(operations) and not op_incomplete,
        },
        "sites": sites,
        "operation_group": operation_group,
        "formula_reconciliation": reconciliation,
        "status": "conflict" if conflict_count else ("partial" if unknown_count else "complete"),
    }


def build_report(material_dir: Path):
    paths = sorted(material_dir.glob("*.cif"))
    records = [analyze_file(path) for path in paths]
    all_sites = [site for record in records for site in record["sites"]]
    signature_buckets = {}
    for record in records:
        signature = record.get("operation_group", {}).get("group_signature", {})
        signature_key = json.dumps(signature, sort_keys=True, separators=(",", ":"))
        signature_buckets.setdefault(signature_key, []).append(record["file"])
    pairwise = []
    for left_index, left in enumerate(records):
        for right in records[left_index + 1:]:
            left_sig = left.get("operation_group", {}).get("group_signature", {})
            right_sig = right.get("operation_group", {}).get("group_signature", {})
            pairwise.append({
                "left_file": left["file"],
                "right_file": right["file"],
                "same_group_signature": left_sig == right_sig,
                "operation_count_delta": left_sig.get("operation_count", 0) - right_sig.get("operation_count", 0),
                "determinant_classes_equal": left_sig.get("determinant_classes") == right_sig.get("determinant_classes"),
                "evidence": {
                    "left_operation_ids": left.get("operation_group", {}).get("evidence", {}).get("operation_ids", []),
                    "right_operation_ids": right.get("operation_group", {}).get("evidence", {}).get("operation_ids", []),
                },
            })
    comparative_audit = {
        "record_order": [record["file"] for record in records],
        "signature_classes": [
            {"signature": json.loads(signature), "files": files}
            for signature, files in sorted(signature_buckets.items())
        ],
        "pairwise": pairwise,
        "status": "supported" if all(record.get("operation_group", {}).get("status") == "supported" for record in records) else "partial",
    }
    aggregate = {
        "records_total": len(records),
        "records_analyzed": sum(1 for record in records if record["sites"]),
        "records_complete": sum(1 for record in records if record["status"] == "complete"),
        "records_partial_or_unknown": sum(1 for record in records if record["status"] == "partial"),
        "records_conflict": sum(1 for record in records if record["status"] == "conflict"),
        "site_count": len(all_sites),
        "special_site_count": sum(1 for site in all_sites if site["position_class"] == "special"),
        "general_site_count": sum(1 for site in all_sites if site["position_class"] == "general"),
        "unknown_site_count": sum(1 for site in all_sites if site["position_class"] == "unknown"),
        "formula_status_counts": {
            state: sum(1 for record in records if record["formula_reconciliation"]["status"] == state)
            for state in ("supported", "conflict", "unknown")
        },
        "operation_group_status_counts": {
            state: sum(1 for record in records if record.get("operation_group", {}).get("status") == state)
            for state in ("supported", "conflict", "unknown")
        },
        "signature_class_count": len(signature_buckets),
        "pairwise_comparison_count": len(pairwise),
    }
    return {"schema_version": "1.0", "input_manifest": {"files": [p.name for p in paths], "count": len(paths)}, "records": records, "comparative_audit": comparative_audit, "aggregate": aggregate}


def main() -> int:
    material_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/workspace/materials")
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/workspace/output/orbit_evidence.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build_report(material_dir), ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

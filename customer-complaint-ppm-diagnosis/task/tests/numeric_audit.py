"""Recompute required numeric quantities against source counts."""
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation


def require(condition, message):
    if not condition:
        raise ValueError(message)


def label_matches(workbook, location, label, kind):
    try:
        text = str(workbook.cell(location)[2]["value"] or "").strip()
    except KeyError:
        return False
    if kind == "product":
        return bool(re.fullmatch(r"(?:product\s*|\u4ea7\u54c1\s*)?" + label + r"(?:\s*\u4ea7\u54c1)?", text, re.I))
    if bool(re.fullmatch(r"(?:2024\u5e74)?0?" + str(label) + r"(?:\s*\u6708)?", text)
            or re.fullmatch(r"2024[-/]0?" + str(label) + r"(?:[-/]0?1)?", text)
            or re.fullmatch(r"(?:month\s*)0?" + str(label), text, re.I)):
        return True
    names = ("January", "February", "March", "April", "May", "June", "July", "August")
    if text.casefold().rstrip(".") in {names[label - 1].casefold(), names[label - 1][:3].casefold()}:
        return True
    if text == "\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b"[label - 1] + "\u6708":
        return True
    cell = workbook.cell(location)[2]
    if re.search(r"[ymd]", cell["format"], re.I) and cell["type"] == "n":
        try:
            base = datetime(1904, 1, 1) if workbook.date1904 else datetime(1899, 12, 30)
            date = base + timedelta(days=float(workbook.numeric(location)))
            return date.year == 2024 and date.month == label
        except (ValueError, OverflowError):
            return False
    return False


def numeric_audit(workbook, bindings, facts):
    results, problems = {}, []

    def value_check(row, field, expected, item_id, quantity, product=None):
        mapping = row.get("product_ppm", {}) if product else row
        location = mapping.get(product) if product else mapping.get(field)
        if not location:
            return "missing_or_incomplete"
        try:
            _, _, cell = workbook.cell(location)
        except KeyError:
            raise ValueError(f"Nonexistent evaluator binding: {location}") from None
        if cell["value"] is None and not cell["formula"]:
            return "missing_or_incomplete"
        try:
            observed = workbook.numeric(location)
        except ValueError as error:
            if any(word in str(error) for word in ("recalculation", "Circular", "bound")):
                raise
            observed = None
        except InvalidOperation:
            observed = None
        expected = Decimal(expected)
        scale = row.get(field + "_scale", "fraction" if field == "share" else "multiplier")
        require(scale in {"fraction", "multiplier", "percent_points"}, "Invalid binding scale")
        require(scale != "percent_points" or quantity in {"share", "relative"}, "Invalid percent-point quantity")
        if scale == "percent_points" and observed is not None and not str(cell["value"]).strip().endswith("%"):
            unit = row.get(field + "_unit")
            require(unit is not None, "Percent-point binding needs a unit locator")
            unit_text = str(workbook.cell(unit)[2]["value"])
            require("%" in unit_text or "\u767e\u5206" in unit_text, "Unsubstantiated percent-point unit")
            observed /= 100
        if quantity == "count":
            tolerance = Decimal(0)
        else:
            fmt = str(cell["format"]).split(";")[0]
            match = re.search(r"[0#]\.(0+)", fmt)
            if match:
                places = len(match.group(1))
            elif fmt != "General" and "0" in fmt:
                places = 0
            else:
                numeric_text = str(cell["value"] if cell["value"] is not None else "")
                try:
                    represented = Decimal(numeric_text.strip().replace(",", "").rstrip("%xX").strip())
                    places = max(0, -represented.as_tuple().exponent) if represented.is_finite() else 0
                except InvalidOperation:
                    places = 0
                if not numeric_text and cell["formula"]:
                    places = 4 if quantity == "share" else 2
            tolerance = Decimal("0.5") * Decimal(10) ** -min(places, 12)
            if quantity == "share" and ("%" in fmt or "%" in str(cell["value"]) or scale == "percent_points"):
                tolerance /= 100
            if quantity == "relative" and ("%" in fmt or "%" in str(cell["value"]) or scale == "percent_points"):
                tolerance /= 100
            if quantity == "share":
                tolerance = min(tolerance, Decimal("0.005"))
            tolerance += Decimal("1e-10")
        computed = observed
        if cell["formula"] and cell["value"] is not None:
            try:
                computed = workbook.formula(workbook.cell(location)[0], cell["formula"])
            except ValueError as error:
                if "recalculation" not in str(error):
                    raise
        if (observed is not None and observed.is_finite() and abs(observed - expected) <= tolerance
                and computed is not None and computed.is_finite() and abs(computed - expected) <= tolerance):
            return "correct"
        problems.append({"item_id": item_id, "location": location, "quantity": quantity,
                         "observed": str(observed), "formula_result": str(computed), "expected": str(expected),
                         "quote": str(cell["value"] if cell["value"] is not None else cell["formula"]),
                         "tolerance": str(tolerance)})
        return "incorrect"

    def finish(item_id, states, evidence, wanted):
        status = "incorrect" if "incorrect" in states else (
            "correct" if len(states) == wanted and all(s == "correct" for s in states) else "missing_or_incomplete")
        results[item_id] = {"item_id": item_id, "status": status, "evidence": evidence,
                            "zero_reason": "" if status == "correct" else "Source-bound table audit: " + status}

    month_rows = bindings.get("months", [])
    require(isinstance(month_rows, list), "Invalid month bindings")
    require(all(isinstance(r, dict) and type(r.get("month")) is int for r in month_rows), "Invalid month key")
    months = {r["month"]: r for r in month_rows}
    require(len(months) == len(month_rows) and set(months) <= set(range(1, 9)), "Duplicate or invalid bound month")
    states, evidence = [], []
    for expected in facts["months"]:
        row = months.get(expected["month"])
        if row is None or not row.get("label"):
            states.append("missing_or_incomplete")
            continue
        require(label_matches(workbook, row["label"], expected["month"], "month"), "Month binding label disagrees")
        for field, kind in (("sales", "count"), ("complaints", "count"), ("overall_ppm", "ppm")):
            states.append(value_check(row, field, expected[field], "P-MONTH-TABLE", kind))
            if row.get(field):
                evidence.append(row[field])
        for product in "ABCD":
            states.append(value_check(row, "product_ppm", expected["product_ppm"][product], "P-MONTH-TABLE", "ppm", product))
            if row.get("product_ppm", {}).get(product):
                evidence.append(row["product_ppm"][product])
    finish("P-MONTH-TABLE", states, evidence, 56)
    product_rows = bindings.get("products", [])
    require(isinstance(product_rows, list), "Invalid product bindings")
    require(all(isinstance(r, dict) and isinstance(r.get("product"), str) for r in product_rows), "Invalid product key")
    products = {r["product"]: r for r in product_rows}
    require(len(products) == len(product_rows) and set(products) <= set("ABCD"), "Duplicate or invalid bound product")
    locations = []
    for row in month_rows:
        locations.extend(row[k] for k in ("sales", "complaints", "overall_ppm") if row.get(k))
        locations.extend(row.get("product_ppm", {}).values())
    for row in product_rows:
        locations.extend(row[k] for k in ("sales", "complaints", "ppm", "share", "relative") if row.get(k))
    normalized = [workbook.cell(loc)[:2] for loc in locations]
    require(len(set(normalized)) == len(normalized), "A value cell is bound to more than one quantity")
    for item_id, fields in (("P-PRODUCT-TABLE", ("sales", "complaints", "ppm")),
                            ("P-SHARES", ("share",)), ("P-RELATIVES", ("relative",))):
        states, evidence = [], []
        for product, expected in facts["products"].items():
            row = products.get(product)
            if row is None or not row.get("label"):
                states.append("missing_or_incomplete")
                continue
            require(label_matches(workbook, row["label"], product, "product"), "Product binding label disagrees")
            for field in fields:
                states.append(value_check(row, field, expected[field], item_id,
                                          "count" if field in {"sales", "complaints"} else field))
                if row.get(field):
                    evidence.append(row[field])
        finish(item_id, states, evidence, 4 * len(fields))
    return results, problems


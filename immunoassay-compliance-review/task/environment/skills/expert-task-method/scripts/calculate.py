#!/usr/bin/env python3
"""Numerical primitives for caller-selected immunoassay observations.

No workbook discovery, validity selection, acceptance rules, or report writing.
Calculations retain binary64 precision except rounded_mean, which interprets
each input's shortest decimal representation before averaging and rounding.
Explicit rounding uses decimal half-away-from-zero; no hidden rounding applies.
"""

from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_HALF_UP, localcontext
import json
import math
from pathlib import Path
import statistics
import sys


OPERATIONS = {
    "summary": {
        "required": ["values"], "optional": {},
        "purpose": "Mean, sample SD, CV percent, n, and df for a numeric array of at least two values. Zero mean gives null CV.",
    },
    "rounded_mean": {
        "required": ["values", "digits"], "optional": {},
        "purpose": "Mean of at least one number, averaged in decimal from each input's shortest representation and rounded half-away-from-zero at the specified digits (-15 to 15). Returns n and rounded_mean. Does not repair precision already lost in supplied inputs.",
    },
    "log_threshold": {
        "required": ["od", "coefficient"], "optional": {},
        "purpose": "Log-space threshold from positive OD values. The source guide uses coefficients 1.645 for SCP and 3.09 for TCP; caller selects the applicable value.",
    },
    "robust_threshold": {
        "required": ["values"],
        "optional": {"coefficient": 2.326, "mad_scale": 1.4826},
        "purpose": "Median, unscaled MAD, and robust threshold. Defaults preserve the source guide convention, not a universal acceptance rule.",
    },
    "sir": {
        "required": ["treated", "untreated"], "optional": {},
        "purpose": "SIR percent from two caller-paired arrays of at least two replicate values. No matching or CV-based filtering is performed.",
    },
    "ratio": {
        "required": ["numerator", "denominator"], "optional": {},
        "purpose": "A ratio of two numbers, including threshold-to-NC-mean correction factors or control ratios.",
    },
    "floating": {
        "required": ["nc_mean", "factor"], "optional": {},
        "purpose": "Floating value from an explicitly supplied NC mean and factor; factor provenance is not inferred.",
    },
    "suitability": {
        "required": ["values", "t_critical", "direction"], "optional": {},
        "purpose": "One limit from at least two values, a caller-established finite t critical value, and direction upper or lower. Returns n and df; does not infer a tail convention.",
    },
    "interpolate": {
        "required": ["dilutions", "responses", "threshold"], "optional": {},
        "purpose": "Linear dilution-scale interpolation on exactly two distinct positive dilution points whose responses bracket the threshold. Does not select the segment or extrapolate.",
    },
    "round": {
        "required": ["value", "digits"], "optional": {},
        "purpose": "Decimal half-away-from-zero rounding of one number. digits is an integer from -15 to 15. Caller chooses each rounding boundary.",
    },
}


def number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite JSON number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def values(value, label, minimum=2):
    if not isinstance(value, list) or len(value) < minimum:
        raise ValueError(f"{label} must be an array with at least {minimum} values")
    return [number(item, f"{label}[{index}]") for index, item in enumerate(value)]


def summary(items):
    mean = statistics.mean(items)
    sd = statistics.stdev(items)
    return {"n": len(items), "df": len(items) - 1, "mean": mean,
            "sample_sd": sd, "cv_percent": None if mean == 0 else sd / mean * 100}


def rounding_digits(value):
    if type(value) is not int or not -15 <= value <= 15:
        raise ValueError("digits must be an integer from -15 to 15")
    return value


def calculate(request):
    """Evaluate one explicit operation. Invalid or non-finite inputs fail closed."""
    if not isinstance(request, dict):
        raise ValueError("each request must be an object")
    operation = request.get("operation")
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise ValueError("unknown operation; consult --describe")
    spec = OPERATIONS[operation]
    missing = set(spec["required"]) - request.keys()
    unknown = request.keys() - {"operation", *spec["required"], *spec["optional"]}
    if missing or unknown:
        raise ValueError(f"invalid fields: missing={sorted(missing)}, unknown={sorted(unknown)}")
    args = {**spec["optional"], **request}

    if operation == "summary":
        result = summary(values(args["values"], "values"))
    elif operation == "rounded_mean":
        items = values(args["values"], "values", minimum=1)
        digits = rounding_digits(args["digits"])
        # Cover binary64's full decimal exponent span, including cancellation.
        with localcontext() as context:
            context.prec = 700 + len(str(len(items)))
            mean = sum((Decimal(str(item)) for item in items), Decimal(0)) / len(items)
            rounded = mean.quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
        result = {"n": len(items), "rounded_mean": float(rounded), "digits": digits}
    elif operation == "log_threshold":
        od = values(args["od"], "od")
        if any(item <= 0 for item in od):
            raise ValueError("od must be strictly positive")
        coefficient = number(args["coefficient"], "coefficient")
        logs = [math.log10(item) for item in od]
        stats = summary(logs)
        log_limit = stats["mean"] + coefficient * stats["sample_sd"]
        result = {"n": len(od), "mean_log": stats["mean"],
                  "sample_sd_log": stats["sample_sd"], "coefficient": coefficient,
                  "log_threshold": log_limit, "threshold": 10 ** log_limit}
    elif operation == "robust_threshold":
        items = values(args["values"], "values", minimum=1)
        median = statistics.median(items)
        mad = statistics.median([abs(item - median) for item in items])
        coefficient = number(args["coefficient"], "coefficient")
        scale = number(args["mad_scale"], "mad_scale")
        if scale <= 0:
            raise ValueError("mad_scale must be positive")
        result = {"n": len(items), "median": median, "mad": mad,
                  "coefficient": coefficient, "mad_scale": scale,
                  "threshold": median + coefficient * scale * mad}
    elif operation == "sir":
        treated = summary(values(args["treated"], "treated"))
        untreated = summary(values(args["untreated"], "untreated"))
        if untreated["mean"] == 0:
            raise ValueError("untreated mean must be nonzero")
        result = {"treated": treated, "untreated": untreated,
                  "sir_percent": (1 - treated["mean"] / untreated["mean"]) * 100}
    elif operation == "ratio":
        denominator = number(args["denominator"], "denominator")
        if denominator == 0:
            raise ValueError("denominator must be nonzero")
        result = {"ratio": number(args["numerator"], "numerator") / denominator}
    elif operation == "floating":
        result = {"floating": number(args["nc_mean"], "nc_mean") * number(args["factor"], "factor")}
    elif operation == "suitability":
        stats = summary(values(args["values"], "values"))
        t_value = abs(number(args["t_critical"], "t_critical"))
        direction = args["direction"]
        if direction not in ("upper", "lower"):
            raise ValueError("direction must be upper or lower")
        sign = 1 if direction == "upper" else -1
        result = {**stats, "direction": direction, "t_critical": t_value,
                  "limit": stats["mean"] + sign * t_value * stats["sample_sd"]}
    elif operation == "interpolate":
        x = values(args["dilutions"], "dilutions")
        y = values(args["responses"], "responses")
        threshold = number(args["threshold"], "threshold")
        if len(x) != 2 or len(y) != 2:
            raise ValueError("interpolation requires exactly two points")
        if min(x) <= 0 or x[0] == x[1] or y[0] == y[1]:
            raise ValueError("dilutions must be positive and distinct; responses must differ")
        if not min(y) <= threshold <= max(y):
            raise ValueError("threshold must be bracketed; extrapolation is not supported")
        fraction = (threshold - y[0]) / (y[1] - y[0])
        result = {"fraction": fraction, "titer": x[0] + fraction * (x[1] - x[0])}
    else:
        value = number(args["value"], "value")
        digits = rounding_digits(args["digits"])
        with localcontext() as context:
            context.prec = 340
            rounded = Decimal(str(value)).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
        result = {"rounded": float(rounded), "digits": digits}

    # Reject overflow in derived values rather than emitting non-standard JSON.
    json.dumps(result, allow_nan=False)
    return {"operation": operation, "result": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="JSON request file; omit to read stdin")
    parser.add_argument("--describe", action="store_true", help="Show operation contracts as JSON")
    args = parser.parse_args()
    try:
        if args.describe:
            payload = {"input": "An object with operation and its fields, or an array of such objects.",
                       "output": "One result object, or an array in input order; stdout only.",
                       "precision": "Binary64 except rounded_mean, which averages shortest decimal input representations before explicit rounding. round does not undo upstream binary arithmetic error. No implicit intermediate rounding; source conventions remain caller-selected.",
                       "nulls": "Missing, boolean, string, and non-finite inputs are rejected, never dropped. CV is null only when the mean is zero.",
                       "operations": OPERATIONS}
        else:
            raw = args.input.read_text(encoding="utf-8") if args.input else sys.stdin.read()
            request = json.loads(raw)
            if isinstance(request, list):
                if not request:
                    raise ValueError("request array must not be empty")
                payload = [calculate(item) for item in request]
            else:
                payload = calculate(request)
        print(json.dumps(payload, allow_nan=False, sort_keys=True))
        return 0
    except (ValueError, TypeError, OverflowError, OSError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

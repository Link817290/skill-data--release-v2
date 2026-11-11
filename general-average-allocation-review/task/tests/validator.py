#!/usr/bin/env python3
"""Mixed scorer for the general-average review deliverables (pd-ledger-v1).

Usage: validator.py <path>  (a directory holding general_average_review.md and
general_average_schedule.csv, or either deliverable file).

The strict score is settled in the standard form

  final = positive_earned * retention
  positive_earned = sum(weight[P] * completion[P])      (weights from scoring_params.json or $SCORING_PARAMS)
  retention = prod over damage instances of min(coefficient[D] for D in the instance)

The positive items are the keys of ITEM_CHECKS (P02-P67). Each settles the
professional or arithmetic checkpoints ITEM_CHECKS lists, and its completion is
the share earned. Deductions, one damage instance each when
they fire: D01 source-PDF integrity gate; D02 memo missing; D03 memo present but schedule missing; D04 exactly
one reversed determination; D05 two or more reversed determinations; D06 one instance per missing give-away
unit; D07 the voucher population transcribed; D08 a conclusion resting on information outside the record.  The lenient lens is an all-or-nothing
test over the items this review cannot be filed without (LENIENT_REQUIRED_ITEMS); it reuses the strict
scorer's own per-item results and never thresholds the weighted total.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import sys
import unicodedata
from pathlib import Path


HERE = Path(__file__).resolve().parent
GROUND = json.loads((HERE / "ground_truth.json").read_text(encoding="utf-8"))

# Positive item -> the mechanical checkpoints it settles, as ``(checkpoint_group, checkpoint_key)``
# pairs.  An item's completion is the share of its own checkpoints the deliverable earns, so a
# one-checkpoint item is that single decision and a multi-checkpoint item is the hit rate over the
# checkpoints it covers.
ITEM_CHECKS: dict[str, tuple[tuple[str, str], ...]] = {
    "P02": (("authority_conflicts", "F48"),),
    "P03": (("settlement", "F33"),),
    "P07": (("settlement", "F61"),),
    "P66": (("interest_basis", "F01"), ("interest_basis", "F02"), ("interest_basis", "F03"),),
    "P67": (("schedule_rollforward", "remainder"), ("schedule_rollforward", "admitted"), ("schedule_rollforward", "pre_fee_1974_1990"),
            ("schedule_rollforward", "pre_fee_1994"), ("schedule_rollforward", "fund_1974_1990"), ("schedule_rollforward", "fund_1994"),),
    "P12": (("classification_timing_and_substitution", "F73"),),
    "P15": (("authority_conflicts", "F42"),),
    "P18": (("settlement", "F36"),),
    "P23": (("authority_conflicts", "F44"),),
    "P24": (("settlement", "F17"), ("settlement", "F35"),),
    "P38": (("settlement", "F40"),),
    "P39": (("settlement", "F62"),),
    "P41": (("classification_timing_and_substitution", "F65"),),
    "P52": (("settlement", "F18"),),
    "P62": (
        ("classification_timing_and_substitution", "F67"),
        ("classification_timing_and_substitution", "F71"),
        ("classification_timing_and_substitution", "F72"),
        ("classification_timing_and_substitution", "F74"),
        ("classification_timing_and_substitution", "F76"),
        ("classification_timing_and_substitution", "F77"),
    ),
    "P63": (("authority_conflicts", "F46"), ("authority_conflicts", "F50"), ("authority_conflicts", "F51"),),
    "P65": (("settlement", "F20"), ("settlement", "F34"), ("settlement", "F38"),),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower()
    value = re.sub(r"\bga\b", "general average", value)
    value = re.sub(r"\bpa\b", "particular average", value)
    value = value.replace("–", "-").replace("—", "-").replace("−", "-")
    return re.sub(r"\s+", " ", value).strip()


def parse_number(raw: str) -> float | None:
    text = raw.strip().replace(" ", "")
    if not text or not re.search(r"\d", text):
        return None
    sign = -1.0 if text.startswith("-") or (text.startswith("(") and text.endswith(")")) else 1.0
    text = text.strip("()+-")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        groups = text.split(",")
        text = text.replace(",", ".") if len(groups) == 2 and len(groups[-1]) != 3 else "".join(groups)
    elif "." in text:
        groups = text.split(".")
        if len(groups) > 2 and all(len(group) == 3 for group in groups[1:]):
            text = "".join(groups)
    try:
        return sign * float(text)
    except ValueError:
        return None


NUMBER_RE = re.compile(r"(?<![A-Za-z])(?:\(?[-+]?\d[\d.,]*\)?)(?![A-Za-z])")


def numbers(value: str) -> list[float]:
    result = []
    for token in NUMBER_RE.findall(value):
        parsed = parse_number(token)
        if parsed is not None and math.isfinite(parsed):
            result.append(parsed)
    return result


def close_number(actual: float, expected: float, relative: float = 0.000002) -> bool:
    tolerance = max(0.02, abs(expected) * relative)
    return abs(actual - expected) <= tolerance


_FENCE_RE = re.compile(r"^[ \t]*(?:```|~~~)[^\n]*\n.*?^[ \t]*(?:```|~~~)[ \t]*$", re.S | re.M)


def read_text(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    # A memorandum wrapped whole in a code fence is quoted text, not the Markdown memorandum the
    # brief asks for: before this the fenced Golden still scored 1.0.
    return _FENCE_RE.sub("", path.read_text(encoding="utf-8", errors="replace"))


def locate_artifacts(target: Path) -> tuple[Path | None, Path | None, Path]:
    if target.is_file():
        root = target.parent
    else:
        root = target
    memo_candidates = [
        target if target.is_file() and target.suffix.lower() == ".md" else None,
        root / "general_average_review.md",
        root / "deliverables/general_average_review.md",
    ]
    schedule_candidates = [
        target if target.is_file() and target.suffix.lower() == ".csv" else None,
        root / "general_average_schedule.csv",
        root / "deliverables/general_average_schedule.csv",
    ]
    memo = next((path for path in memo_candidates if path and path.is_file()), None)
    schedule = next((path for path in schedule_candidates if path and path.is_file()), None)
    return memo, schedule, root


def source_path(root: Path, name: str) -> Path | None:
    fallback_candidates = [
        Path("/workspace") / name,
        HERE.parent / "environment/workspace" / name,
    ]
    return next((path for path in fallback_candidates if path.is_file()), None)


def source_integrity(root: Path) -> tuple[bool, dict[str, bool]]:
    checks = {}
    for name, expected in GROUND["source_sha256"].items():
        path = source_path(root, name)
        checks[name] = bool(path and sha256(path) == expected)
    return all(checks.values()), checks


def csv_units(text: str) -> list[str]:
    """Schedule rows, each carrying its own header row.

    `csv.Sniffer` declines a perfectly ordinary comma-delimited schedule when it has many
    consecutive empty fields, so a sniffer failure falls back to the default comma dialect,
    which is still a CSV read and still prefixes the header row carrying the column meaning.
    Only a read that yields no columns at all falls back to raw lines, where a row loses that
    prefix.
    """
    if not text.strip():
        return []
    rows: list[list[str]] = []
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
        rows = list(csv.reader(io.StringIO(text), dialect))
    except (csv.Error, UnicodeError):
        rows = []
    if not rows or max((len(row) for row in rows), default=0) < 2:
        try:
            rows = list(csv.reader(io.StringIO(text)))
        except (csv.Error, UnicodeError):
            rows = []
    if not rows or max((len(row) for row in rows), default=0) < 2:
        return [line for line in text.splitlines() if line.strip()]
    header = " | ".join(rows[0])
    return [header + " | " + " | ".join(row) for row in rows[1:] if any(cell.strip() for cell in row)]


# A numeric unit expressly marked as unadopted is not an operative calculation.
# The cue is anchored at the start so ordinary professional use of words such as
# "rejected" or "hypothetical" cannot erase an otherwise adopted row.
_DISOWN_LEAD = r"^[\s>|*\-–—•·\d.、)）\]】\"'“”‘’]{0,12}"
_DISOWN_RE = re.compile(
    _DISOWN_LEAD + r"(?:"
    r"the following is not asserted(?: here)?|not asserted here\b|"
    r"tentative,?\s*not adopted|not adopted\s*[:：]|unadopted\s*[:：]|"
    r"the draft (?:asserted|stated)\b|"
    r"candidate only\s*[:：]|filed as (?:a )?candidate\b|for discussion only\s*[:：]|"
    r"以下(?:内容)?(?:并非|不是)本方(?:主张|结论)|以下并非|以下不主张|"
    r"疑似(?=[^\n]{0,80}(?:尚未采纳|待核))|"
    r"原稿(?:主张|记载|曾称)|"
    r"并非(?=\S)|"
    r"暂定[，,：:]|候选[，,：:]|未采纳[，,：:]"
    r")", re.I)


def _disowned(unit: str) -> bool:
    return bool(_DISOWN_RE.search(unit))


def evidence_units(memo: str, schedule: str) -> list[str]:
    # Lines the memo itself withdraws are dropped BEFORE the units are built: the sliding windows
    # below join 2-4 lines, so a cue that governs one line would otherwise sit mid-unit and the
    # joined unit would still match.
    memo = "\n".join(line for line in memo.splitlines() if not _disowned(line))
    lines = [line.strip() for line in memo.splitlines() if line.strip()]
    units = [line for line in lines if len(line) <= 3000]
    units.extend(block.strip() for block in re.split(r"\n\s*\n", memo) if block.strip())
    for width in (2, 3, 4):
        units.extend(" ".join(lines[index : index + width]) for index in range(max(0, len(lines) - width + 1)))
    units.extend(csv_units(schedule))
    return [normalized(unit) for unit in units if unit.strip()]





# The pinpoint carriers admitted here are the ones ``citation_checks`` admits (``para\.?``,
# ``paras\.?``, ``paragraph``), with or without the abbreviation period and in either number:
# "SC para 118", "FI paras 145-146" and "paragraphs 11-14" are the same pinpoint as
# "para. 118", so the determinations they carry are read.  Bare "p 7" still needs its period,
# because a lone letter before a number is not a citation convention.
PINPOINT_RE = re.compile(r"(?:\bpp?\.|\bpages?|\bparas?\.?|\bparagraphs?|\u00b6|§{1,2})\s*\d|\[\d{1,3}\]")


FOOTNOTE_DEF_RE = re.compile(r"^[ \t]*\[\^([^\]\s]{1,40})\][ \t]*:[ \t]*(.*)$", re.M)
FOOTNOTE_REF_RE = re.compile(r"\[\^([^\]\s]{1,40})\]")


def resolve_footnotes(memo: str) -> str:
    """Inline each Markdown footnote reference as the text of its own definition.

    A memorandum may carry its pinpoints in a footnote table - "...the owners' claim
    failed.[^fi129]" against "[^fi129]: `first_instance_judgment.pdf`, para. 129." - which
    states exactly the pinpoint the instruction asks for, in the place the convention puts
    it.  Read literally, the reference marker is not a pinpoint and the determination it
    carries is invisible.  Substituting each marker for its definition makes the two
    carriers the same text; a marker with no definition is left alone, and a deliverable
    that uses no footnotes is returned unchanged.
    """
    definitions = {key: value.strip() for key, value in FOOTNOTE_DEF_RE.findall(memo)}
    if not definitions:
        return memo
    body = FOOTNOTE_DEF_RE.sub("", memo)
    return FOOTNOTE_REF_RE.sub(
        lambda match: f" ({definitions[match.group(1)]})" if match.group(1) in definitions else match.group(0),
        body,
    )


def pinpointed(units: list[str]) -> list[str]:
    """The memorandum must tie material conclusions to pinpoint locations in the
    supplied records, so a determination is read only where the page or paragraph
    it rests on is visible with it."""
    return [unit for unit in units if PINPOINT_RE.search(unit)]


SEMANTIC_HITS = {}


def finding_rate(units: list[str], finding_ids: list[str], specs=None) -> tuple[float, dict[str, bool]]:
    """Settle professional findings exclusively from the evidence-bound judge."""
    del units, specs
    missing = [finding_id for finding_id in finding_ids if finding_id not in SEMANTIC_HITS]
    if missing:
        raise RuntimeError("semantic adjudication missing findings: " + ", ".join(missing))
    hits = {finding_id: bool(SEMANTIC_HITS[finding_id]) for finding_id in finding_ids}
    return sum(hits.values()) / len(hits), hits


def expected_row(label_fragment: str) -> dict:
    needle = normalized(label_fragment)
    for row in GROUND["schedule_rows"]:
        if needle in normalized(row["interest_or_population"]):
            return row
    raise RuntimeError(f"reference schedule row missing: {label_fragment}")


def numeric_hit(units: list[str], expected: float, context: tuple[str, ...], relative: float = 0.000002) -> bool:
    for unit in units:
        if not any(term in unit for term in context) or _disowned(unit):
            continue
        if any(close_number(value, expected, relative=relative) for value in numbers(unit)):
            return True
    return False


def numeric_checks(units: list[str]) -> tuple[float, dict[str, bool]]:
    vessel = expected_row("Vessel")
    cargo = expected_row("Cargo including freight")
    containers = expected_row("Containers")
    bunkers = expected_row("Bunkers")
    total = expected_row("Total contributory capital")
    old_rules = expected_row("YAR 1974/1990")
    newer_rules = expected_row("YAR 1994")
    old_population = expected_row("Cargo and containers under YAR 1974/1990")
    new_population = expected_row("Cargo and containers under YAR 1994")

    raw_specs = [
        ("vessel_value", vessel["contributory_value_usd"], ("vessel", "ship")),
        ("cargo_value", cargo["contributory_value_usd"], ("cargo", "freight")),
        ("container_value", containers["contributory_value_usd"], ("container", "box")),
        ("bunker_value", bunkers["contributory_value_usd"], ("bunker", "fuel")),
        ("capital_total", total["contributory_value_usd"], ("total", "capital")),
        ("vessel_contribution", vessel["contribution_or_amount_usd"], ("vessel", "ship")),
        ("cargo_contribution", cargo["contribution_or_amount_usd"], ("cargo", "freight")),
        ("container_contribution", containers["contribution_or_amount_usd"], ("container", "box")),
        ("bunker_contribution", bunkers["contribution_or_amount_usd"], ("bunker", "fuel")),
        ("apportioned_claim", total["contribution_or_amount_usd"], ("apportion", "total", "claim")),
        ("old_rule_fund", old_rules["contribution_or_amount_usd"], ("1974", "1990")),
        ("old_rule_rate", old_rules["rate_or_share_percent"], ("1974", "1990")),
        ("new_rule_fund", newer_rules["contribution_or_amount_usd"], ("1994",)),
        ("new_rule_rate", newer_rules["rate_or_share_percent"], ("1994",)),
        ("old_population_value", old_population["contributory_value_usd"], ("1974", "1990")),
        ("old_population_fund", old_population["contribution_or_amount_usd"], ("1974", "1990")),
        ("new_population_value", new_population["contributory_value_usd"], ("1994",)),
        ("new_population_fund", new_population["contribution_or_amount_usd"], ("1994",)),
    ]
    hits = {
        name: numeric_hit(units, float(value), context)
        for name, value, context in raw_specs
    }
    return sum(hits.values()) / len(hits), hits


def allowance_ledger_checks(units: list[str]) -> tuple[float, dict[str, bool]]:
    specs = [
        ("a_gross", 10310794.05, ("section a", "a salvage", "salvage remuneration")),
        ("a_remainder", 107530.81, ("section a", "a salvage", "salvage remuneration")),
        ("a_admitted", 10203263.24, ("section a", "a salvage", "salvage remuneration")),
        ("b_gross", 1158590.22, ("section b", "b expenditure", "expenditure in china")),
        ("b_remainder", 16679.20, ("section b", "b expenditure", "expenditure in china")),
        ("b_admitted", 1141911.02, ("section b", "b expenditure", "expenditure in china")),
        ("c_admitted", 37761.14, ("section c", "crew wages", "crew maintenance", "bunker consumption")),
        ("d_gross", 423848.94, ("section d", "d miscellaneous", "miscellaneous disbursement")),
        ("d_remainder", 1252.16, ("section d", "d miscellaneous", "miscellaneous disbursement")),
        ("d_admitted", 422596.78, ("section d", "d miscellaneous", "miscellaneous disbursement")),
        ("ledger_gross", 11930994.35, ("gross", "four section", "sum of section", "ledger total", "allowance ledger")),
        ("ledger_remainder", 125462.17, ("remainder", "outside general average", "not admitted")),
        ("ledger_admitted", 11805532.18, ("admitted principal", "general average principal", "general average column", "allowance ledger")),
        ("b5_gross", 20866.30, ("b5", "underwater survey")),
        ("b5_remainder", 13910.87, ("b5", "underwater survey")),
        ("b5_admitted", 6955.43, ("b5", "underwater survey")),
        ("b9_excluded", 2768.33, ("b9", "crew change", "crew-change")),
        ("d10b_gross", 4327.10, ("d10b", "june 2012")),
        ("d10b_remainder", 1252.16, ("d10b", "june 2012")),
        ("d10b_admitted", 3074.94, ("d10b", "june 2012")),
        ("commission_base", 11306541.09, ("commission", "rule xx")),
        ("commission", 226130.84, ("commission", "rule xx")),
        ("interest_1974_1990", 509909.02, ("1974", "1990")),
        ("interest_1994", 711848.06, ("1994",)),
        ("pre_fee_1974_1990", 12541572.04, ("pre-fee", "before fees", "1974", "1990")),
        ("pre_fee_1994", 12743511.08, ("pre-fee", "before fees", "1994")),
        ("adjuster_fees", 865990.66, ("adjuster fee", "adjustment fee", "fees and expenses")),
        ("fund_1974_1990", 13407562.70, ("1974", "1990")),
        ("fund_1994", 13609501.74, ("1994",)),
    ]
    hits = {
        name: numeric_hit(units, expected, context)
        for name, expected, context in specs
    }
    return sum(hits.values()) / len(hits), hits




def citation_checks(text: str) -> tuple[float, dict[str, bool]]:
    """Controlling-record pinpointing.

    The judgments number their own paragraphs, and the neutral-citation convention
    writes that pinpoint in brackets - "final judgment [146]", "CA [76]" - as well as
    "paras.146".  Both are the pinpoint the instruction asks for, so both are read.
    """
    value = normalized(text)
    patterns = {
        "adjustment_basis": r"(?:adjustment|general_average_adjustment).*?(?:p\.?|pp\.?|page)\s*7(?:\D|$)",
        "adjustment_values": r"(?:adjustment|general_average_adjustment).*?(?:p\.?|pp\.?|page)\s*50(?:\D|$)",
        "adjustment_split_vouchers": r"(?:adjustment|general_average_adjustment).*?(?:p\.?|pp\.?|page)\s*(?:69|70|71|72|85|86)(?:\D|$)",
        "adjustment_allowance_summary": r"(?:adjustment|general_average_adjustment).*?(?:p\.?|pp\.?|page)\s*(?:89|90|91|92)(?:\D|$)",
        "adjustment_distribution": r"(?:adjustment|general_average_adjustment).*?(?:p\.?|pp\.?|page)\s*(?:93|94|95)(?:\D|$)",
        "trial_core": r"(?:first.instance|first_instance_judgment|trial).*?(?:(?:para\.?|paras\.?|paragraph|¶|§{1,2})|\[)\s*(?:1|2|55|56|57|114|124|129)(?:\D|$)",
        "trial_alternatives": r"(?:first.instance|first_instance_judgment|trial).*?(?:(?:para\.?|paras\.?|paragraph|¶|§{1,2})|\[)\s*(?:116|117|118|119|120|121|122|123|125|126|127|128)(?:\D|$)",
        "intermediate_scope": r"(?:court.of.appeal|court_of_appeal_judgment|intermediate).*?(?:(?:para\.?|paras\.?|paragraph|¶|§{1,2})|\[)\s*(?:3|12|29|30|31)(?:\D|$)",
        "intermediate_result": r"(?:court.of.appeal|court_of_appeal_judgment|intermediate).*?(?:(?:para\.?|paras\.?|paragraph|¶|§{1,2})|\[)\s*(?:71|72|73|74|75|76)(?:\D|$)",
        "judgment_cause": r"(?:judgment|final_judgment|court).*?(?:(?:para\.?|paras\.?|paragraph|¶|§{1,2})|\[)\s*(?:11|12|13|14|15|16|17|18)(?:\D|$)",
        "judgment_fault": r"(?:judgment|final_judgment|court).*?(?:(?:para\.?|paras\.?|paragraph|¶|§{1,2})|\[)\s*(?:21|28|29|30|31|32)(?:\D|$)",
        "judgment_result": r"(?:judgment|final_judgment|court).*?(?:(?:para\.?|paras\.?|paragraph|¶|§{1,2})|\[)[^;\n]{0,40}(?:145|146)(?:\D|$)",
    }
    hits = {name: bool(re.search(pattern, value)) for name, pattern in patterns.items()}
    return sum(hits.values()) / len(hits), hits


def interest_coverage(text: str) -> dict[str, bool]:
    value = normalized(text)
    return {
        "ship": "vessel" in value or "ship" in value,
        "cargo": "cargo" in value,
        "containers": "container" in value or "box" in value,
        "bunkers": "bunker" in value or "fuel" in value,
    }


# ---------------------------------------------------------------------------
# Give-away unit gate (D06). Each unit is a figure or determination the brief requires
# every usable submission to carry, read together with its key value: the schedule
# row naming the interest or ledger stage with its amount, or the memorandum passage
# carrying the determination with its pinpoint.  Each missing unit is one D06 damage
# instance, so a deliverable with half its content removed loses several units at once.
#
# Schedule units: the four contributing interests (value and contribution each), the
# contributory capital and apportioned claim, the two contract-population values and
# funds, and the roll-forward from the gross section totals through commission, the two
# rule-dependent interest amounts and the adjustment fees.
GIVEAWAY_SCHEDULE_NUMERIC = (
    "vessel_value", "cargo_value", "container_value", "bunker_value",
    "vessel_contribution", "cargo_contribution", "container_contribution", "bunker_contribution",
    "capital_total", "apportioned_claim",
    "old_population_value", "old_population_fund", "new_population_value", "new_population_fund",
)
GIVEAWAY_SCHEDULE_LEDGER = (
    "a_gross", "c_admitted", "d_gross", "ledger_gross",
    "commission", "interest_1974_1990", "interest_1994", "adjuster_fees",
)
# Memorandum units: freight carried in cargo (F01), no vessel sacrifice (F07), the
# defective passage plan rendering the vessel unseaworthy (F12), voucher B9 wholly
# excluded (F27), each with its pinpoint, and the voucher B5 timing split with its amounts.
GIVEAWAY_MEMO_FINDINGS = ("F01", "F07", "F12", "F27")
GIVEAWAY_MEMO_LEDGER = ("b5_remainder", "b5_admitted")


def giveaway_units(memo: str, schedule: str) -> dict[str, bool]:
    schedule_units = [normalized(unit) for unit in csv_units(schedule)]
    memo_units = evidence_units(resolve_footnotes(memo), "")
    _, schedule_numeric = numeric_checks(schedule_units)
    _, schedule_ledger = allowance_ledger_checks(schedule_units)
    _, memo_ledger = allowance_ledger_checks(memo_units)
    _, memo_findings = finding_rate(pinpointed(memo_units), list(GIVEAWAY_MEMO_FINDINGS))
    units = {f"schedule:{key}": schedule_numeric[key] for key in GIVEAWAY_SCHEDULE_NUMERIC}
    units.update({f"schedule:{key}": schedule_ledger[key] for key in GIVEAWAY_SCHEDULE_LEDGER})
    units.update({f"memo:{key}": memo_findings[key] for key in GIVEAWAY_MEMO_FINDINGS})
    units.update({f"memo:{key}": memo_ledger[key] for key in GIVEAWAY_MEMO_LEDGER})
    return units


# The schedule's own roll-forward (P67): the instruction requires the schedule to carry the
# roll-forward from the gross section totals through the amounts outside general average,
# admitted general average, commission, rule-dependent interest and fees to the final funds.
# The stages after the gross totals are read from the schedule rows alone, each figure with
# its stage named in the row or its column header.
def rollforward_reference() -> tuple[tuple[str, float, tuple[str, ...]], ...]:
    principal = expected_row("Principal allowance ledger")
    old_pre_fee = expected_row("Pre-fee YAR 1974/1990 subtotal")
    new_pre_fee = expected_row("Pre-fee YAR 1994 subtotal")
    old_fund = expected_row("YAR 1974/1990")
    new_fund = expected_row("YAR 1994")
    return (
        ("remainder", float(principal["review_status"].split()[-1]), ("remainder", "outside", "not admitted")),
        ("admitted", float(principal["contribution_or_amount_usd"]), ("admitted", "principal")),
        ("pre_fee_1974_1990", float(old_pre_fee["contribution_or_amount_usd"]), ("pre-fee", "before fee", "subtotal", "1974", "1990")),
        ("pre_fee_1994", float(new_pre_fee["contribution_or_amount_usd"]), ("pre-fee", "before fee", "subtotal", "1994")),
        ("fund_1974_1990", float(old_fund["contribution_or_amount_usd"]), ("1974", "1990")),
        ("fund_1994", float(new_fund["contribution_or_amount_usd"]), ("1994",)),
    )


def schedule_rollforward(schedule: str) -> dict[str, bool]:
    rows = [normalized(unit) for unit in csv_units(schedule)]
    return {name: numeric_hit(rows, expected, context) for name, expected, context in rollforward_reference()}


# Voucher transcription (D07).  The instruction asks for the disposition of each affected
# account "without transcribing the full voucher population".  The adjustment's voucher
# population is A1-A7, B1-B14, C1-C3 and D1-D11; a sub-voucher (A6a, D10b) counts for its
# parent.  Citing VOUCHER_LIMIT or more of the 35 is a transcription of the population.
VOUCHER_POPULATION = frozenset(
    [f"A{n}" for n in range(1, 8)] + [f"B{n}" for n in range(1, 15)]
    + [f"C{n}" for n in range(1, 4)] + [f"D{n}" for n in range(1, 12)]
)
VOUCHER_RE = re.compile(r"\b([A-D][1-9]\d?)[a-z]?\b")
VOUCHER_LIMIT = 30


def vouchers_cited(memo: str, schedule: str) -> set[str]:
    return {match for match in VOUCHER_RE.findall(memo + "\n" + schedule) if match in VOUCHER_POPULATION}



# A6a Marseille split (F73) with the two amounts attached to the wrong roles: USD 10,023.81
# directly labelled remainder and USD 5,011.91 directly labelled general average.
A6A_REMAINDER = r"(?:remainder|outside general average|not admitted|particular average)"
A6A_ADMITTED = r"(?:general average|admitted|allowed)"


def a6a_swapped(units: list[str]) -> bool:
    for unit in units:
        wrong_remainder = re.search(
            r"10,?023\.81\s+" + A6A_REMAINDER + r"|" + A6A_REMAINDER + r"\s*(?:of\s+|:\s*)?(?:usd\s*)?10,?023\.81", unit)
        wrong_admitted = re.search(
            r"5,?011\.91\s+" + A6A_ADMITTED + r"|" + A6A_ADMITTED + r"\s*(?:of\s+|:\s*)?(?:usd\s*)?5,?011\.91", unit)
        if wrong_remainder and wrong_admitted:
            return True
    return False


def grade(target: Path) -> dict:
    memo_path, schedule_path, root = locate_artifacts(target)
    memo = read_text(memo_path)
    schedule = read_text(schedule_path)
    global SEMANTIC_HITS
    from semantic_judge import REVERSE_RULES, RULE_IDS, adjudicate

    semantic=None
    SEMANTIC_HITS={}
    semantic_reversals = {}
    outside_information = False
    if memo.strip() or schedule.strip():
        semantic=adjudicate("MEMO\n"+memo+"\nSCHEDULE\n"+schedule,(HERE/"semantic_source.json").read_text())
        SEMANTIC_HITS={k:row["fraction"]==1 for k,row in semantic["items"].items() if k.startswith("F")}
        semantic_reversals = {
            name: bool(semantic["items"][rule_id]["fraction"])
            for rule_id, (name, _) in REVERSE_RULES.items()
        }
        outside_information = bool(semantic["items"]["X01"]["fraction"])
    else:
        SEMANTIC_HITS = {finding_id: False for finding_id in RULE_IDS}
        semantic_reversals = {name: False for name, _ in REVERSE_RULES.values()}
    units = evidence_units(resolve_footnotes(memo), schedule)
    located_units = pinpointed(units)

    intact, integrity_detail = source_integrity(root)
    memo_present = bool(memo.strip())
    schedule_present = bool(schedule.strip())

    numeric_rate, numeric_detail = numeric_checks(units)
    allowance_ledger_rate, allowance_ledger_detail = allowance_ledger_checks(units)
    basis_rate, basis_detail = finding_rate(located_units, ["F01", "F02", "F03"])
    allowance_rate, allowance_detail = finding_rate(located_units, ["F07", "F27"])
    classification_rate, classification_detail = finding_rate(
        located_units, ["F65", "F67", "F71", "F72", "F73", "F74", "F76", "F77"]
    )
    if a6a_swapped(units):
        classification_detail["F73"] = False
    liability_rate, liability_detail = finding_rate(located_units, ["F12"])
    authority_rate, authority_detail = finding_rate(
        located_units, ["F42", "F44", "F46", "F48", "F50", "F51"]
    )
    settlement_rate, settlement_detail = finding_rate(
        located_units,
        [
            "F17", "F18", "F20", "F33", "F34", "F35", "F36",
            "F38", "F40", "F61", "F62",
        ],
    )
    citation_rate, citation_detail = citation_checks(memo + "\n" + schedule)

    group_scores = {
        "capital_and_apportionment": numeric_rate,
        "allowance_ledger_reconciliation": allowance_ledger_rate,
        "interest_basis_and_rule_routing": basis_rate,
        "allowance_boundaries": allowance_rate,
        "classification_timing_and_substitution": classification_rate,
        "liability_chain": liability_rate,
        "authority_and_conflict_resolution": authority_rate,
        "settlement_and_uncertainty": settlement_rate,
        "evidence_binding": citation_rate,
    }
    # Reversal gate: the deliverable asserting a proposition the supplied record
    # refutes is the wrong answer, however faithfully it reproduces the arithmetic.
    # Record-contrary conclusions are adjudicated semantically so negated,
    # attributed and hypothetical language cannot fire from keyword overlap.
    directions = semantic_reversals
    contradictions = dict(semantic_reversals)
    contradiction_count = sum(directions.values())

    # Reported for diagnosis only.  Naming the four contributing interests is a
    # coverage count over the schedule, not one of this review's determinations,
    # so it no longer gates the lenient lens (see LENIENT_REQUIRED_ITEMS).
    coverage = interest_coverage(schedule)

    damage = []
    if not intact:
        damage.append(("gate:source_integrity", ["D01"]))
    if not memo_present:
        damage.append(("gate:memo_missing:general_average_review.md", ["D02"]))
    elif not schedule_present:
        damage.append(("gate:schedule_missing:general_average_schedule.csv", ["D03"]))
    giveaway = giveaway_units(memo, schedule) if memo_present else {}
    if memo_present and not schedule_present:
        # D03 already owns the absent schedule and all schedule-derived units.
        # Retain only independently missing memorandum units for D06.
        giveaway = {key:value for key,value in giveaway.items() if key.startswith("memo:")}
    missing_giveaways=[unit for unit,present in giveaway.items() if not present]
    if missing_giveaways:
        damage.append(("gate:giveaway_units_missing:"+",".join(sorted(missing_giveaways)),["D06"]))
    vouchers = vouchers_cited(memo, schedule)
    if len(vouchers) >= VOUCHER_LIMIT:
        damage.append((f"voucher_population_transcribed={len(vouchers)}", ["D07"]))
    if outside_information:
        damage.append(("outside_information", ["D08"]))
    if contradiction_count == 1:
        damage.append(("polarity:reversed_determinations=1", ["D04"]))
    elif contradiction_count >= 2:
        damage.append(("polarity:reversed_determinations=%d" % contradiction_count, ["D05"]))
    rollforward_detail = schedule_rollforward(schedule)
    checkpoint_tables = {
        "schedule_rollforward": rollforward_detail,
        "numeric": numeric_detail,
        "allowance_ledger": allowance_ledger_detail,
        "interest_basis": basis_detail,
        "allowance_boundaries": allowance_detail,
        "classification_timing_and_substitution": classification_detail,
        "liability_chain": liability_detail,
        "authority_conflicts": authority_detail,
        "settlement": settlement_detail,
        "citations": citation_detail,
    }
    completion = {}
    for item_id, members in ITEM_CHECKS.items():
        decisions = [bool(checkpoint_tables[group][key]) for group, key in members]
        completion[item_id] = sum(decisions) / len(decisions)
    parts = {"completion": completion, "damage": damage}

    return {
        "_parts": parts,
        "reward": 0.0,
        # Both lenses are settled in settle(), which is where the item completions
        # and the damage instances the lenient lens reads are assembled.
        "semantic_judge": semantic,
        "rewards": {"strict": 0.0, "lenient": 0.0},
        "score_type": "general_average_allocation_review",
        "reward_formulas": {
            "strict": "positive_earned * retention (pd-ledger-v1; weights and coefficients from scoring_params.json)",
            "lenient": LENIENT_FORMULA,
        },
        "checkpoint_count": len(group_scores),
        "contradictions": contradictions,
        "reversed_determinations": directions,
        "gates": {
            "source_integrity": intact,
            "memo_present": memo_present,
            "schedule_present": schedule_present,
        },
        "source_integrity_detail": integrity_detail,
        "group_scores": {name: round(value, 6) for name, value in group_scores.items()},
        "checkpoints": {
            "schedule_rollforward": rollforward_detail,
            "numeric": numeric_detail,
            "allowance_ledger": allowance_ledger_detail,
            "interest_basis": basis_detail,
            "allowance_boundaries": allowance_detail,
            "classification_timing_and_substitution": classification_detail,
            "liability_chain": liability_detail,
            "authority_conflicts": authority_detail,
            "settlement": settlement_detail,
            "citations": citation_detail,
        },
        # Diagnostic only; the lenient verdict itself is attached in settle().
        "schedule_interest_coverage": coverage,
        "giveaway_units": giveaway,
        "vouchers_cited": sorted(vouchers),
        "diagnostic_errors": [
            name for name, ok in {"source_integrity": intact, "memo_present": memo_present, "schedule_present": schedule_present}.items() if not ok
        ],
    }


# ---------------------------------------------------------------------------
# pd-ledger-v1 settlement.
PARAMS = Path(os.environ.get("SCORING_PARAMS", HERE / "scoring_params.json"))
ZERO_PARTS = {"completion": {}, "damage": []}

# ---------------------------------------------------------------------------
# Lenient lens: the determinations and the delivery conditions this review cannot
# be filed without.  Binary (1.0 / 0.0) and settled from the strict scorer's own
# per-item results -- each positive item against its own completion, each
# deduction item against whether it raised a damage instance.  No weighted total
# is thresholded and nothing is re-parsed. The required items group into six
# requirements:
#
#   1. The two deliverables exist, written against the supplied record.
#      D01 / D02 / D03.  instruction.md names both paths -- the memorandum at
#      `general_average_review.md` "together with" the schedule at
#      `general_average_schedule.csv` -- and requires "Use only the materials
#      supplied under /workspace ... the supplied materials are read-only".
#   2. No operative determination is asserted against the supplied record.
#      D04 / D05.  RUBRIC: "A reversed determination is the wrong answer however
#      faithfully the rest is reproduced."
#   3. The submission neither transcribes nearly all vouchers nor relies on
#      information outside the supplied record. D07 / D08.
#   4. P52, the adjustment arithmetic's controlling figures: "The 8% cash-deposit
#      call was provisional security and must not be used as the final debt or
#      rate; the final blended adjustment rate is 2.67460000%" (RUBRIC P52).
#      instruction.md: "The deliverables must cover the adjustment arithmetic".
#      It is also one of the seven operative determinations the record settles, so
#      a review that neither states it nor reverses it has not done the sum.
#   5. P41, the rule routing of the allowance classes -- salvage to Rule VI,
#      lightening and reshipping to Rule VIII, refuge and detention to Rule XI,
#      other direct-consequence expenditure to Rule C / XI(d) (RUBRIC P41).
#      instruction.md: "The memorandum must address adjusters' notes that
#      materially change classification".  Without the routing the allowances are
#      an undifferentiated list and the roll-forward cannot be audited.
#   6. P38, the post-judgment collection position: the dismissal "resolves the
#      litigated recovery claim, but the judgment contains no account-level
#      monetary, refund or security-release order for other interests"
#      (RUBRIC P38).  instruction.md names "the post-judgment collection position"
#      as one of the three things the deliverables must cover, and the whole task
#      exists because "a later final judgment changed the collection posture".
#
# Deliberately NOT gated here, and left to the strict score: how much of the
# finding register is covered, how many figures the ledger carries, how many of
# the four interests the schedule names, how many pinpoints are present.  Those
# are coverage counts over the deliverable rather than determinations, and a
# count threshold could otherwise let a review that missed every controlling
# determination clear the lens by bulk.
LENIENT_REQUIRED_ITEMS = (
    "D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08",
    "P52", "P41", "P38",
)
LENIENT_FORMULA = (
    "1.0 when every item of LENIENT_REQUIRED_ITEMS holds, else 0.0 (both deliverables present "
    "against the intact supplied record, no reversed operative determination, no near-complete "
    "voucher transcription, no conclusion based outside the supplied record, and the deposit-call "
    "versus final-rate finding, the rule routing of the allowance classes and the post-judgment "
    "collection position each earned in full); settled from the strict scorer's own per-item "
    "results, never from the weighted total"
)


def lenient_lens(completion: dict, instances: list[dict]) -> tuple[float, dict]:
    """The binary lenient verdict plus its per-item record."""
    fired = {item for instance in instances for item in instance["item_ids"]}
    detail: dict[str, bool] = {}
    for item in LENIENT_REQUIRED_ITEMS:
        if item.startswith("D"):
            detail[item] = item not in fired
        else:
            detail[item] = float(completion.get(item, 0.0)) >= 1.0
    return (1.0 if all(detail.values()) else 0.0), detail


def settle(result: dict) -> dict:
    """Settle the checkpoint decisions as pd-ledger-v1."""
    params = json.loads(PARAMS.read_text(encoding="utf-8"))
    weights, coefficients = params["positive_weights"], params["deduction_coefficients"]
    parts = result.pop("_parts", ZERO_PARTS)
    completion = {k: round(min(1.0, max(0.0, float(parts["completion"].get(k, 0.0)))), 10) for k in weights}
    instances = [{"key": key, "item_ids": items} for key, items in parts["damage"]]
    earned = sum(weights[k] * completion[k] for k in weights)
    retention = math.prod(min(coefficients[i] for i in inst["item_ids"]) for inst in instances)
    final = round(min(1.0, max(0.0, earned * retention)), 10)
    lenient, lenient_detail = lenient_lens(completion, instances)
    result["rewards"]["strict"] = final
    result["rewards"]["lenient"] = lenient
    result["reward"] = final
    result.setdefault("reward_formulas", {})["lenient"] = LENIENT_FORMULA
    result["lenient_detail"] = {"required_items": list(LENIENT_REQUIRED_ITEMS), "met": lenient_detail}
    result["scoring_ledger"] = {"schema_version": "pd-ledger-v1", "positive_completion": completion,
                                "damage_instances": instances, "positive_earned": earned,
                                "retention": retention, "final_score": final}
    return result


def main() -> int:
    # Accepts a deliverables directory or either deliverable file.
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/workspace/deliverables")
    try:
        result = grade(target)
    except Exception as exc:
        sys.stderr.write("evaluator failed: "+type(exc).__name__+"\n");return 2
    print(json.dumps(settle(result), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

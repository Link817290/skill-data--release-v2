#!/usr/bin/env python3
"""Condition-blind scorer for the historical sanctions and AML review."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
GROUND = json.loads((HERE / "ground_truth.json").read_text(encoding="utf-8"))

STRICT_WEIGHTS = {
    "Entity resolution": 0.05,
    "Historical state reconstruction": 0.30,
    "Action and uncertainty discipline": 0.25,
    "AML pattern assessment": 0.05,
    "Cross-case control reconciliation": 0.30,
    "Evidence binding": 0.05,
}

GENERIC_NAME_WORDS = {
    "bank", "banka", "banking", "public", "joint", "stock", "company", "companies",
    "corporation", "corp", "limited", "ltd", "llc", "ojsc", "jsc", "pjsc", "open",
    "closed", "financial", "finance", "national", "international", "commercial",
    "development", "agricultural", "trade", "trading", "russia", "russian",
    "federation", "state", "group", "holding", "and", "the", "for", "of",
    "wholesale", "other", "equipment", "sanctions", "regulations", "secondary",
    "risk", "website", "email", "address", "target", "type", "institution",
    "registration", "number", "legal", "entity", "entities", "executive", "order",
    "directive", "information", "listing", "date", "effective", "prohibited",
    "transactions", "persons", "owned", "controlled", "section", "sections",
    "please", "visit", "following", "link", "more", "programs", "pages",
    "treasury", "resource", "center", "policy", "issues", "https", "http", "www",
    "com", "html", "foreign", "economic", "affairs", "assets", "control",
    "office", "department", "united", "states", "government", "program",
    "blocked", "designated", "designation", "list", "person", "specially",
}

COUNT_WORDS = {
    2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight",
    9: "nine", 10: "ten", 11: "eleven", 12: "twelve",
}

MONTHS = {
    1: "january", 2: "february", 3: "march", 4: "april", 5: "may", 6: "june",
    7: "july", 8: "august", 9: "september", 10: "october", 11: "november",
    12: "december",
}


def norm(value: object) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return re.sub(r"\s+", " ", text).lower()


def has(text: str, pattern: str) -> bool:
    return re.search(pattern, text, flags=re.I) is not None


def all_dicts(value: object):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from all_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from all_dicts(item)


def locate(payload: object, identifier: str) -> dict | None:
    candidates = []
    for item in all_dicts(payload):
        values = {str(v).strip() for v in item.values() if isinstance(v, (str, int, float))}
        if identifier in values:
            candidates.append(item)
    return max(candidates, key=lambda x: len(norm(x)), default=None)


def tokenize(text: str) -> set[str]:
    parts = re.split(r"[^a-z0-9]+", text.lower())
    words = set()
    for part in parts:
        for piece in re.findall(r"[a-z]+|[0-9]+", part):
            if len(piece) >= 3:
                words.add(piece)
    return words


def token_in(text: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", text, flags=re.I) is not None


def parse_date(value: str) -> tuple[int, int, int] | None:
    match = re.match(r"\s*([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})", value or "")
    if not match:
        return None
    name = match.group(1).lower()
    month = next((n for n, full in MONTHS.items() if full.startswith(name[:3])), None)
    if month is None:
        return None
    return int(match.group(3)), month, int(match.group(2))


def date_patterns(year: int, month: int, day: int) -> list[str]:
    name = MONTHS[month]
    short = name[:3]
    return [
        rf"{year}-0?{month}-0?{day}\b",
        rf"\b0?{month}[/.-]0?{day}[/.-]{year}\b",
        rf"\b0?{day}\s+(?:{name}|{short}\.?)\s+{year}\b",
        rf"\b(?:{name}|{short}\.?)\s+0?{day}(?:st|nd|rd|th)?,?\s+{year}\b",
    ]


def read_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def resolve_workspace(workspace: Path) -> Path:
    if (workspace / "review_template.json").is_file():
        return workspace
    fallback = HERE.parent / "environment" / "workspace"
    return fallback if (fallback / "review_template.json").is_file() else workspace


def load_facts(workspace: Path) -> dict | None:
    workspace = resolve_workspace(workspace)
    data = workspace / "data"
    docs = workspace / "source_documents"
    try:
        transactions = read_rows(data / "review_transactions.csv")
        alerts = read_rows(data / "screening_alerts.csv")
        with (data / "candidate_list_records.csv").open(encoding="utf-8-sig", newline="") as handle:
            candidate_rows = [row for row in csv.reader(handle) if len(row) >= 3]
        template = json.loads((workspace / "review_template.json").read_text(encoding="utf-8"))
    except Exception:
        return None

    rows = {row["id"]: row for row in transactions}
    groups: dict[str, set[str]] = defaultdict(set)
    for row in transactions:
        groups[row["icij_sar_id"]].add(row["id"])
    row_ids = set(rows)
    filing_ids = set(groups)

    candidates = {}
    name_tokens: dict[str, set[str]] = {}
    record_tokens: dict[str, set[str]] = {}
    for row in candidate_rows:
        uid = row[0].strip()
        name = row[1].strip()
        remarks = " ".join(row[2:])
        candidates[uid] = name
        name_tokens[uid] = {w for w in tokenize(name) if w not in GENERIC_NAME_WORDS}
        linked = " ".join(re.findall(r"linked to:?(.*?)(?:\.|$)", remarks, flags=re.I))
        name_tokens[uid] |= {w for w in tokenize(linked) if w not in GENERIC_NAME_WORDS}
        record_tokens[uid] = {w for w in tokenize(remarks + " " + row[3 if len(row) > 3 else 1])
                              if len(w) >= 4 and w not in GENERIC_NAME_WORDS and not w.isdigit()}

    seen = defaultdict(int)
    for uid, words in record_tokens.items():
        for word in words:
            seen[word] += 1
    for uid in record_tokens:
        record_tokens[uid] = {w for w in record_tokens[uid] if seen[w] == 1}

    by_name = {name.strip().lower(): uid for uid, name in candidates.items()}
    alert_uid = {}
    for alert in alerts:
        uid = by_name.get(alert["candidate_list_name"].strip().lower())
        if uid:
            alert_uid[alert["transaction_id"]] = uid

    actions: dict[str, tuple[int, int, int]] = {}
    action_parties: dict[str, set[str]] = {}
    for path in sorted(docs.glob("action-*")):
        match = re.search(r"(\d{4})-(\d{2})-(\d{2})", path.name)
        if not match:
            continue
        key = match.group(0)
        actions[key] = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        body = path.read_text(encoding="utf-8", errors="replace").lower()
        action_parties[key] = {uid for uid, words in name_tokens.items()
                               if words and any(token_in(body, word) for word in words)}

    template_strings = set()
    for item in all_dicts(template):
        for value in item.values():
            if isinstance(value, str) and value.strip():
                template_strings.add(norm(value).strip())

    cases = {}
    for identifier in GROUND["sanctions"]:
        row = rows.get(identifier)
        if row is None:
            continue
        begin = parse_date(row["begin_date"])
        end = parse_date(row["end_date"])
        years = {d[0] for d in (begin, end) if d}
        uid = alert_uid.get(identifier)
        cases[identifier] = {
            "years": years,
            "count": int(row["number_transactions"] or 0),
            "uid": uid,
            "actions": {key for key, parties in action_parties.items() if uid in parties},
        }

    return {
        "rows": rows,
        "row_ids": row_ids,
        "filing_ids": filing_ids,
        "groups": {sar: set(ids) for sar, ids in groups.items()},
        "candidates": candidates,
        "record_tokens": record_tokens,
        "actions": actions,
        "sanctions": cases,
        "template_strings": template_strings,
    }


def scored_text(item: dict | None, facts: dict | None) -> str:
    if not item:
        return ""
    blocked = facts["template_strings"] if facts else set()

    def keep(value):
        if isinstance(value, str):
            return None if norm(value).strip() in blocked else value
        if isinstance(value, list):
            kept = [keep(entry) for entry in value]
            return [entry for entry in kept if entry not in (None, [], {})]
        if isinstance(value, dict):
            kept = {k: keep(v) for k, v in value.items()}
            return {k: v for k, v in kept.items() if v not in (None, [], {})}
        return value

    return norm(keep(item) or {})


def cited_ids(text: str, universe: set[str], width: int) -> set[str]:
    found = set(re.findall(rf"(?<!\d)\d{{{width}}}(?!\d)", text))
    return found & universe


def cited_actions(text: str, facts: dict) -> set[str]:
    found = set()
    for key, (year, month, day) in facts["actions"].items():
        if any(has(text, pattern) for pattern in date_patterns(year, month, day)):
            found.add(key)
    return found


def cited_uids(text: str, facts: dict) -> set[str]:
    return {uid for uid in facts["candidates"] if has(text, rf"(?<!\d){uid}(?!\d)")}


def period_anchored(text: str, case: dict) -> bool:
    if any(has(text, rf"(?<!\d){year}(?!\d)") for year in case["years"]):
        return True
    count = case["count"]
    if count >= 2:
        word = COUNT_WORDS.get(count)
        forms = [rf"(?<!\d){count}(?!\d)"] + ([rf"\b{word}\b"] if word else [])
        return any(has(text, form) for form in forms)
    return False


def state_bound(text: str, case: dict | None, expected: dict, facts: dict | None) -> bool:
    """The time-state finding must be tied to this alert's own record and list source."""
    if facts is None or case is None:
        return False
    uids = cited_uids(text, facts)
    if uids - {case["uid"]}:
        return False
    if expected["identity"] == "false":
        own = case["uid"]
        tokens = facts["record_tokens"].get(own, set())
        foreign = any(token_in(text, word) for uid, words in facts["record_tokens"].items()
                      if uid != own for word in words)
        if foreign:
            return False
        return bool(uids) or any(token_in(text, word) for word in tokens)
    actions = cited_actions(text, facts)
    # The binding to guard is the note resting on someone else's designation, so
    # the action citations have to meet this party's own. A programme-level date
    # carried alongside that one -- the day the directive itself was published,
    # the day its tenor was amended -- dates the instrument rather than the
    # party, and reading it as a misattribution would penalise the more exact
    # reconstruction. Only a note anchored entirely on other parties' actions is
    # unbound.
    if actions and not (actions & case["actions"]):
        return False
    if not period_anchored(text, case):
        return False
    return bool(actions) or bool(uids)


# Identity is a claim about two parties, so a negation reports non-identity
# only when the thing it governs is one of those parties. The same stems run
# right through a correct true-match note governing something else: an evidence
# field that could not be compared ("no BIC, so the SWIFT cannot be matched
# field to field"), a count of measures or questions ("two distinct measures",
# "three distinct questions"), an instrument, a tenor or a date ("four
# different instruments", "a different date and counterparty"), a neighbouring
# party being ruled out ("do not confuse it with the different entity VTB 24"),
# or a disposition the note holds this case against ("a different disposition
# from a false positive"). None of those says this pair is not the same party.
_PARTY_NOUN = (
    r"(?:part(?:y|ies)|counterpart(?:y|ies)|entit(?:y|ies)|persons?|"
    r"institutions?|compan(?:y|ies)|banks?|firms?|beneficiar(?:y|ies)|"
    r"customers?|organi[sz]ations?|corporations?|payers?|remitters?|"
    r"wholesalers?|subjects?)"
)

# At most one modifier may stand between the negation and the party it governs,
# and it may not be a conjunction or a preposition, since "a different date and
# counterparty" negates the date and merely carries the counterparty along.
_PARTY_MODIFIER = (
    r"(?!(?:and|or|nor|but|from|than|then|to|of|in|on|at|for|as|with)\b)[a-z][\w'-]*\s+"
)

_DIFFERENCE = r"\b(?:different|distinct|unrelated)\b"

NON_IDENTITY_PARTY = re.compile(
    rf"{_DIFFERENCE}\s+(?:{_PARTY_MODIFIER}){{0,1}}{_PARTY_NOUN}\b", flags=re.I
)

# Non-identity may also be predicated of the pair rather than named by a noun
# phrase, but the subject still has to be a party.
NON_IDENTITY_PREDICATION = re.compile(
    rf"\bnot\s+(?:the\s+)?same\s+(?:{_PARTY_MODIFIER}){{0,1}}{_PARTY_NOUN}\b"
    rf"|\bnot\s+(?:the\s+)?(?:listed|designated|sanctioned|screened|blocked)\s+"
    rf"(?:{_PARTY_MODIFIER}){{0,1}}{_PARTY_NOUN}\b"
    rf"|\b{_PARTY_NOUN}\s+(?:and|versus|vs\.?)\s+(?:the\s+)?"
    rf"(?:{_PARTY_MODIFIER}){{0,2}}{_PARTY_NOUN}\s+(?:are\s+not|do\s+not\s+match|differ)\b",
    flags=re.I,
)

# The counterparty of the comparison, used to tell "a different entity from the
# list record" -- a finding about this pair -- from "a different entity from the
# Chinese policy bank", which rules out a neighbour and leaves this pair intact.
_ALERT_PAIR = (
    r"(?:list(?:ed)?[\s_-]*(?:record|person|entry|entity|name|party)|candidate|"
    r"screened|sdn\b|designated\s+part|alert|payment\s+part|transaction\s+part|"
    r"the\s+two|each\s+other|one\s+another|\bthem\b|\bit\b)"
)

# A negation aimed at a neighbouring party is introduced as such.
_EXCLUSION_FRAME = re.compile(
    r"(?:confus\w+|conflat\w+|mix\w+\s+up|mistak\w+)\s+(?:it\s+|this\s+|them\s+)?"
    r"(?:with|for)\s+(?:the\s+|a\s+|an\s+)?$"
    r"|\b(?:note|noting|beware|aside\s+from|apart\s+from|other\s+than|besides)\s+"
    r"(?:the\s+|a\s+|an\s+)?$",
    flags=re.I,
)

# The bare disposition. "Match" takes no qualifier of its own here: "not a
# weak-token match" and "cannot be matched field to field" grade the strength of
# a comparison, they do not withdraw the identification.
_FALSE_DISPOSITION = (
    r"false[\s_-]*(?:positive|match|hit|alert)"
    r"|\bno[\s_-]*match\b"
    r"|\bnot\s+an?\s+(?:identity\s+|entity\s+|true\s+|name\s+)?match\b"
    r"|\bidentity\s+(?:fails|failed|is\s+not\s+established|not\s+established)"
    r"|(?:does\s+not|do\s+not|cannot|could\s+not)\s+(?:be\s+)?"
    r"(?:establish|support|confirm|prove)\s+(?:the\s+)?identity"
    r"|\bmismatch(?:ed)?\s+(?:entit|part|person)"
    r"|\b(?:entity|identity|party)\s+mismatch\b"
)

FALSE_DISPOSITION = re.compile(_FALSE_DISPOSITION, flags=re.I)

# A disposition the note names in order to set this case apart from it is not
# the disposition the note reaches.
CONTRASTED_DISPOSITION = re.compile(
    r"(?:\bnot\s+(?:be\s+)?(?:read|taken|treated|recorded|documented|construed|"
    r"characteri[sz]ed|understood|mistaken|confused|reported|logged)\s+"
    r"(?:as|for|with)\s+(?:an?\s+)?"
    r"|\brather\s+than\s+(?:an?\s+)?"
    r"|\binstead\s+of\s+(?:an?\s+)?"
    r"|\bas\s+opposed\s+to\s+(?:an?\s+)?"
    r"|\bdifferent\s+[\w'-]+\s+(?:from|to|than)\s+(?:an?\s+)?"
    r"|\bdistinguish\w*\s+(?:it\s+|this\s+|them\s+)?from\s+(?:an?\s+)?"
    rf"|\bnot\s+(?:an?\s+)?(?=false))\s*(?:{_FALSE_DISPOSITION})",
    flags=re.I,
)


def non_identity_claimed(text: str) -> bool:
    """True only where the note puts the screened party outside the list record."""
    plain = CONTRASTED_DISPOSITION.sub(" ", text)
    if FALSE_DISPOSITION.search(plain) or NON_IDENTITY_PREDICATION.search(plain):
        return True
    for match in NON_IDENTITY_PARTY.finditer(plain):
        tail = plain[match.end():match.end() + 70]
        if re.match(r"\s+(?:from|to|than)\b", tail) and not re.search(_ALERT_PAIR, tail, flags=re.I):
            continue
        if _EXCLUSION_FRAME.search(plain[max(0, match.start() - 60):match.start()]):
            continue
        return True
    return False


def identity_ok(text: str, expected: str) -> bool:
    false_signal = non_identity_claimed(text)
    if expected == "false":
        return false_signal
    return (has(text, r"true|confirm|same.{0,10}(?:entity|party)|identity.{0,8}match|matched") and not false_signal)


def no_restriction_claimed(text: str) -> bool:
    return has(
        text,
        r"predat|pre.?designation"
        r"|\bno\b.{0,18}(?:applicable|restriction|sanction|measure|status)"
        r"|not.{0,18}(?:yet|subject to|restricted|listed|designated|sanctioned|in (?:force|effect))"
        r"|nothing.{0,45}(?:restrict|sanction|measure|prohibition)\w*\s+(?:in force|in effect|applied|applicable|was|were)"
        r"|later.{0,20}(?:designation|listing|measure|action)",
    )


def restriction_claimed(text: str) -> bool:
    kind = has(text, r"directive\s*1|sectoral|non.?blocking|financ(?:ing|ial).{0,12}restrict")
    # What has to be present is the refusal to resolve scope and the naming of
    # the facts it turns on. The anchor is therefore those facts, whichever verb
    # carries the gap, and a conclusion explicitly held open says the same thing
    # as one called unresolved.
    uncertainty = has(
        text,
        r"unresolved|unknown|insufficient"
        r"|cannot.{0,12}(?:determine|decide|conclude|resolve)"
        r"|fact.{0,8}(?:gap|missing)"
        r"|missing.{0,30}(?:instrument|tenor|maturity|terms)"
        r"|(?:instrument|tenor|maturity|issuance|payment.{0,8}term)s?.{0,40}"
        r"(?:missing|absent|not\s+(?:supplied|available|stated|identified|recorded|given))"
        r"|\bno\s+(?:instrument|tenor|maturity|issuance)\b"
        r"|(?:do(?:es)?\s+not|cannot|could\s+not)\s+(?:be\s+)?"
        r"(?:identify|establish|state|supply|show|record|determine).{0,40}"
        r"(?:instrument|tenor|maturity|issuance|payment.{0,8}term)"
        # "Open" has to be predicated of the conclusion. Left bare it is part of
        # the listed names themselves ("open joint-stock company").
        r"|hold\w*\s+(?:the\s+)?[\w\s,'-]{0,30}?"
        r"\b(?:conclusion|finding|question|scope|assessment|determination|alert)\b"
        r"[\w\s,'-]{0,20}?\bopen\b"
        r"|\bopen\s+(?:finding|question|item)\b|\bheld\s+open\b"
        r"|\b(?:conclusion|finding|question|scope|assessment|classification|"
        r"determination|matter)\b(?:\s+[\w'-]+){0,2}\s+"
        r"(?:remains?|is|are|was|were|stays?|left|kept)?\s*open\b",
    )
    return kind and uncertainty


def ownership_gap_claimed(text: str) -> bool:
    ownership = has(text, r"ownership|owned|97\.52|vnesheconombank")
    clock = has(text, r"2015.{0,30}2016|2016.{0,30}2015|when.{0,20}(?:ownership|percentage).{0,15}(?:took effect|effective)|continu\w*.{0,25}(?:2016|payment|period)|not.{0,25}(?:prove|establish).{0,30}(?:each|component|transaction.?time)|transaction.?time.{0,20}(?:unknown|unresolved)|cannot.{0,20}be dated.{0,35}(?:transaction|payment|reporting).{0,20}(?:period|date)|as of (?:the )?(?:reporting|ownership) date|not contemporaneous|contemporaneous.{0,20}(?:date|period)")
    uncertainty = has(text, r"unresolved|unknown|insufficient|cannot.{0,15}(?:determine|establish)|fact.{0,8}(?:gap|missing)")
    return ownership and clock and uncertainty


def straddle_claimed(text: str) -> bool:
    return (has(text, r"stradd|span.{0,12}(?:date|effective)|cross.{0,12}(?:date|effective)")
            and has(text, r"component|underlying|individual.{0,12}date|value.{0,8}date"))


def state_language_ok(text: str, expected: str) -> bool:
    """One alert carries one time-state; a note that claims several earns nothing."""
    if expected == "none":
        return no_restriction_claimed(text) and not restriction_claimed(text)
    # Naming what did not apply is part of a measure-in-force finding: a
    # sectoral note has to say that the later blocking designation was not yet
    # in effect and that the measure was non-blocking. That negation is scoped
    # to another instrument. Only a note that puts no measure at all on the
    # party contradicts one, and the four states stay mutually exclusive through
    # their own predicates below.
    if no_restriction_claimed(text) and not restriction_claimed(text):
        return False
    if expected == "sectoral":
        return restriction_claimed(text) and not straddle_claimed(text) and not ownership_gap_claimed(text)
    if expected == "ownership_gap":
        return ownership_gap_claimed(text) and not straddle_claimed(text)
    return straddle_claimed(text) and not ownership_gap_claimed(text)


def action_ok(text: str, expected: str) -> bool:
    if expected == "false_close":
        return has(text, r"close|clear|different|false") and not has(text, r"\bblock(?:ed|ing)?\b(?!.*(?:not|do not))")
    if expected == "temporal_close":
        closure = has(text, r"close|clear|do not.{0,8}block|not.{0,8}block|no.{0,8}block")
        clock = has(text, r"retro|predat|later|not yet|at.{0,12}(?:time|date)")
        return closure and clock
    request = has(text, r"obtain|request|retrieve|review|hold|pending|escalat")
    nonblock = has(
        text,
        r"non.?block|do not.{0,8}block|not.{0,8}block|without.{0,8}block"
        r"|neither.{0,12}block|refrain\w*.{0,20}block|\bno\b.{0,12}block"
        r"|block\w*.{0,25}not.{0,15}(?:required|warranted|appropriate|available)",
    )
    scope = has(text, r"instrument|issuance|maturity|tenor|payment.{0,8}term|invoice|debt|equity")
    if expected == "date_hold":
        return request and nonblock and scope and has(text, r"component|underlying|value.{0,8}date|individual.{0,8}date")
    if expected == "ownership_hold":
        dated_owner = has(text, r"dated.{0,20}(?:ownership|share|cap)|ownership.{0,20}(?:date|at the time|effective)|2014.{0,20}ownership|component.{0,15}date")
        return request and nonblock and scope and dated_owner
    return request and nonblock and scope


AML_RULES = {
    "3730": [r"escalat|enhanced|refer|investigat", r"recipro|opposite|reverse", r"consecutive|next day|close.{0,12}(?:time|day)", r"customer|same.{0,8}fund|message|not.{0,12}prov"],
    "2340": [r"escalat|enhanced|refer|investigat", r"cluster|burst|repeat|many.{0,12}small", r"structur", r"threshold|currency|customer"],
    "4208": [r"escalat|enhanced|refer|investigat|inconclusive", r"overlap", r"not.{0,12}sum|do not.{0,12}sum|double.{0,8}count|disjoint", r"underlying|customer|purpose|message"],
    "2380": [r"escalat|enhanced|refer|investigat", r"recipro|opposite|flow.?through|both.{0,12}direction", r"not.{0,12}prov|same.{0,8}fund|customer|message", r"rosbank|commercial bank|amsterdam"],
    "2336": [r"escalat|enhanced|refer|investigat", r"repeat|several|multiple", r"later.{0,18}sanction|pre.?designation|independent.{0,18}sanction", r"customer|purpose|context|message"],
    "2716": [r"inconclusive|insufficient|hold|cannot.{0,12}(?:determine|conclude)", r"structur", r"threshold", r"customer|currency"],
    "3230": [r"escalat|enhanced|refer|investigat", r"false.{0,18}(?:match|positive)|different.{0,12}entity", r"not.{0,18}(?:basis|because)|independent|activity", r"repeat|multiple|cross.?border|aggregate"],
}


CONTROL_RULES = {
    "OWNERSHIP-ASOF": [
        r"hold|unresolved|insufficient|cannot.{0,15}establish",
        r"2015.{0,35}2016|2016.{0,35}2015|when.{0,20}(?:ownership|percentage).{0,15}(?:took effect|effective)|continu\w*.{0,25}(?:2016|payment|period)|not.{0,25}(?:prove|establish).{0,35}(?:each|component|transaction.?time)|cannot.{0,20}be dated.{0,35}(?:transaction|payment|reporting).{0,20}(?:period|date)|as of (?:the )?(?:reporting|ownership) date|not contemporaneous|contemporaneous.{0,20}(?:date|period)",
        r"97\.52|vnesheconombank",
        r"directive\s*1|sectoral|non.?blocking",
        r"dated.{0,25}(?:ownership|share|cap)|ownership.{0,25}(?:date|effective|at the time)|component.{0,15}(?:payment|value).{0,8}date",
        r"instrument|issuance|maturity|tenor|payment.{0,8}term|debt|equity",
    ],
    "NONBLOCKING-SCOPE": [
        r"directive\s*1|sectoral",
        r"non.?blocking|do not.{0,10}block|not.{0,10}block",
        r"new.{0,8}debt|new.{0,8}equity|financ",
        r"instrument|issuance|maturity|tenor|payment.{0,8}term",
        r"post.{0,20}(?:effective|identification)|after.{0,20}(?:effective|identification)|already.{0,15}subject",
    ],
    "RECIPROCAL-FLOW": [
        r"recipro|opposite|both.{0,12}direction|reverse",
        r"lead|review|investigat|escalat",
        r"not.{0,15}(?:proof|prove)|same.{0,8}fund.{0,12}(?:not|unproven|unknown)|cannot.{0,15}establish.{0,15}same",
        r"customer|account.{0,12}link",
        r"payment.{0,8}message|source.{0,8}fund|purpose",
    ],
    "STRUCTURING-SUPPORT": [
        r"do not.{0,15}(?:conclude|label|assert).{0,10}(?:structur|threshold)|(?:structur|threshold.?evasion).{0,40}(?:not established|unproven|unsupported|inconclusive|not.{0,12}support)|(?:no|insufficient).{0,50}(?:support|evidence|basis).{0,40}(?:structur|threshold)|no.{0,50}(?:characteri[sz]|label|call).{0,20}(?:structur|threshold)",
        r"2340.{0,80}(?:escalat|review)|(?:escalat|review).{0,80}2340",
        r"2716.{0,80}(?:hold|inconclusive|insufficient)|(?:hold|inconclusive|insufficient).{0,80}2716",
        r"threshold",
        r"currency",
        r"customer|account.{0,12}link",
    ],
    "AML-SANCTIONS-INDEPENDENCE": [
        r"independent|separate.{0,20}sanction|activity.{0,30}(?:basis|merit|sanction)",
        r"bank.{0,8}rossiya.{0,80}(?:later|predat|not yet)|(?:later|predat|not yet).{0,80}bank.{0,8}rossiya",
        r"(?:chinese|china).{0,30}(?:false|different)|(?:false|different).{0,30}(?:chinese|china)",
        r"not.{0,20}(?:proof|prove).{0,20}(?:suspicious|launder|crime|illicit)|match.{0,25}not.{0,15}(?:evidence|proof)|neither.{0,25}match.{0,25}(?:prove|disprove)",
        r"customer|purpose|payment.{0,8}message|underlying.{0,15}transaction",
    ],
}


def aml_bound(identifier: str, text: str, facts: dict | None) -> bool:
    """The AML opinion must rest on records that belong to this filing."""
    if facts is None:
        return False
    own = facts["groups"].get(identifier, set())
    cited = cited_ids(text, facts["row_ids"], 6)
    return len(cited & own) >= 2 and not (cited - own)


def aml_ok(identifier: str, text: str, expected: str, facts: dict | None) -> tuple[float, list[bool]]:
    checks = [has(text, pattern) for pattern in AML_RULES[identifier]]
    if expected == "inconclusive":
        checks[0] = checks[0] and not has(text, r"definit(?:e|ely).{0,12}structur|proven.{0,12}structur")
    else:
        checks[0] = checks[0] and not has(text, r"proven.{0,16}(?:launder|crime)|definit(?:e|ely).{0,16}(?:launder|illicit)")
    bound = aml_bound(identifier, text, facts)
    checks.append(bound)
    if not bound:
        return 0.0, checks
    return sum(checks[:-1]) / len(checks[:-1]), checks


def nonempty_decision(text: str) -> bool:
    return has(text, r"match|false|restrict|directive|clear|block|escalat|enhanced|inconclusive|hold|subject|predat|stradd|refer|investigat|do not.{0,12}sum|activity.{0,12}basis|lead")


def to_group_grain(ids: set[str], facts: dict | None) -> set[str]:
    """Reduce record identifiers to the grain the control operates on.

    A control covers case groups, and a reviewer may identify the affected records
    either by the group or by the underlying transaction rows that constitute it.
    Both name the same records, so rows are mapped up to their group before any
    set comparison. Identifiers that are already groups, or that belong to no
    supplied group, pass through unchanged.
    """
    if not facts:
        return ids
    row_to_group = {row: sar for sar, rows in facts["groups"].items() for row in rows}
    return {row_to_group.get(value, value) for value in ids}


def claimed_records(item: dict | None, text: str, facts: dict | None) -> set[str]:
    if not item:
        return set()
    claimed = set()
    for value in item.values():
        if isinstance(value, list):
            for entry in value:
                if not isinstance(entry, (str, int)):
                    continue
                # An identifier carried with its own annotation is still that identifier.
                head = re.match(r"\s*(\d{4,6})(?!\d)", str(entry))
                if head:
                    claimed.add(head.group(1))
    if claimed or facts is None:
        return to_group_grain(claimed, facts)
    universe = facts["row_ids"] | facts["filing_ids"]
    loose = {token for token in re.findall(r"(?<!\d)\d{4,6}(?!\d)", text) if token in universe}
    return to_group_grain(loose, facts)


def jaccard(claimed: set[str], expected: set[str]) -> float:
    if not expected:
        return 1.0
    union = claimed | expected
    return len(claimed & expected) / len(union) if union else 0.0


def control_ok(identifier: str, item: dict | None, text: str, affected: list[str],
               facts: dict | None, semantic_item: dict | None) -> tuple[float, list[bool], float]:
    coverage = jaccard(claimed_records(item, text, facts),
                       to_group_grain(set(affected), facts))
    if semantic_item is not None:
        checks = [semantic_item["fraction"] == 1]
        return float(checks[0]) * coverage, checks, coverage
    checks = [has(text, pattern) for pattern in CONTROL_RULES[identifier]]
    return float(all(checks)) * coverage, checks, coverage


def source_integrity(workspace: Path) -> tuple[float, dict]:
    manifest_path = HERE / "source_integrity.json"
    if not (workspace / "review_template.json").is_file() or not manifest_path.exists():
        return 1.0, {"checked": False, "reason": "workspace unavailable during offline scoring"}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    changed = []
    for relative, expected in manifest.items():
        path = workspace / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if actual != expected:
            changed.append(relative)
    return (1.0 if not changed else 0.0), {"checked": True, "changed": changed}


def source_reference(text: str, facts: dict | None) -> bool:
    refs = set(re.findall(r"[a-z0-9][a-z0-9_-]*\.(?:csv|html|pdf|txt|zip)", text, flags=re.I))
    refs |= {f"faq {n}" for n in re.findall(r"faq[\s#-]*(\d{2,4})", text, flags=re.I)}
    refs |= {f"uid {n}" for n in re.findall(r"(?:uid|list record|list id)[\s#:-]*(\d{4,6})", text, flags=re.I)}
    if facts:
        refs |= {f"list {uid}" for uid in cited_uids(text, facts)}
    return len(refs) >= 2


def score(payload: object, workspace: Path) -> dict:
    facts = load_facts(workspace)
    sanctions_detail = {}
    from semantic_judge import adjudicate,RULES
    candidate={k:scored_text(locate(payload,k),facts) for k in RULES}
    semantic_source={
        "historical_sources":json.loads((HERE/"semantic_source.json").read_text()),
        "control_facts":json.loads((HERE/"control_semantic_source.json").read_text()),
    }
    semantic=adjudicate(json.dumps(candidate,ensure_ascii=False),semantic_source)
    identity_scores = []
    state_scores = []
    action_scores = []
    evidence_scores = []
    located = 0
    decision_count = 0

    for identifier, expected in GROUND["sanctions"].items():
        item = locate(payload, identifier)
        text = scored_text(item, facts)
        if item:
            located += 1
            decision_count += int(nonempty_decision(text))
        case = (facts or {}).get("sanctions", {}).get(identifier)
        i_ok = identity_ok(text, expected["identity"])
        bound = state_bound(text, case, expected, facts)
        s_ok = (semantic["items"][identifier]["fraction"]==1 if identifier in semantic["items"] else state_language_ok(text, expected["status"])) and bound
        a_ok = action_ok(text, expected["action"])
        e_ok = source_reference(text, facts)
        identity_scores.append(float(i_ok))
        state_scores.append(float(s_ok))
        action_scores.append(float(a_ok and i_ok and s_ok))
        evidence_scores.append(float(e_ok))
        sanctions_detail[identifier] = {
            "located": bool(item), "identity": i_ok, "state": s_ok, "record_bound": bound, "semantic_state": semantic["items"].get(identifier),
            "action": a_ok, "action_dependency_closed": bool(a_ok and i_ok and s_ok), "evidence": e_ok,
        }

    aml_detail = {}
    aml_scores = []
    for identifier, expected in GROUND["aml"].items():
        item = locate(payload, identifier)
        text = scored_text(item, facts)
        if item:
            located += 1
            decision_count += int(nonempty_decision(text))
        value, checks = aml_ok(identifier, text, expected["outcome"], facts)
        e_ok = source_reference(text, facts)
        aml_scores.append(value)
        evidence_scores.append(float(e_ok))
        aml_detail[identifier] = {
            "located": bool(item), "signals": checks[:-1], "record_bound": checks[-1],
            "score": round(value, 6), "evidence": e_ok,
        }

    control_detail = {}
    control_scores = []
    for identifier, expected in GROUND["controls"].items():
        item = locate(payload, identifier)
        text = scored_text(item, facts)
        if item:
            located += 1
            decision_count += int(nonempty_decision(text))
        semantic_item=semantic["items"].get(identifier)
        value, checks, coverage = control_ok(identifier, item, text, expected["affected_records"], facts, semantic_item)
        e_ok = source_reference(text, facts)
        control_scores.append(value)
        evidence_scores.append(float(e_ok))
        control_detail[identifier] = {
            "located": bool(item), "dependency_signals": checks,
            "semantic_control": semantic_item,
            "record_set_agreement": round(coverage, 6),
            "dependency_closed": bool(value == 1.0), "score": round(value, 6), "evidence": e_ok,
        }

    dimensions = {
        "Entity resolution": sum(identity_scores) / len(identity_scores),
        "Historical state reconstruction": sum(state_scores) / len(state_scores),
        "Action and uncertainty discipline": sum(action_scores) / len(action_scores),
        "AML pattern assessment": sum(aml_scores) / len(aml_scores),
        "Cross-case control reconciliation": sum(control_scores) / len(control_scores),
        "Evidence binding": sum(evidence_scores) / len(evidence_scores),
    }
    strict_raw = sum(STRICT_WEIGHTS[name] * value for name, value in dimensions.items())
    integrity_factor, integrity_detail = source_integrity(workspace)
    strict = strict_raw * integrity_factor

    total_cases = len(GROUND["sanctions"]) + len(GROUND["aml"]) + len(GROUND["controls"])
    coverage = located / total_cases
    decisions = decision_count / total_cases
    evidence = sum(evidence_scores) / len(evidence_scores)
    summary_present = any(
        isinstance(v, str) and len(v.strip()) >= 80
        for d in all_dicts(payload)
        for v in d.values()
    )
    lenient_components = {
        "all_cases_located": float(coverage == 1.0),
        "all_cases_decided": float(decisions == 1.0),
        "all_cases_traceable": float(evidence == 1.0),
        "substantive_summary": float(summary_present),
        "core_identity_state_action_correct": float(
            all(value == 1.0 for value in identity_scores + state_scores + action_scores)
            and all(value == 1.0 for value in aml_scores + control_scores)),
        "source_integrity": float(integrity_factor == 1.0),
    }
    lenient = float(all(value == 1.0 for value in lenient_components.values()))

    strict = round(max(0.0, min(1.0, strict)), 6)
    lenient = round(max(0.0, min(1.0, lenient)), 6)
    return {
        "rewards": {"strict": strict, "lenient": lenient},
        "reward": strict,
        "reward_formulas": {
            "strict": "weighted capability dimensions multiplied by the source-integrity factor",
            "lenient": "binary conjunction of full case coverage, case decisions, case-local evidence, substantive summary, and source integrity",
        },
        "dimensions": {k: round(v, 6) for k, v in dimensions.items()},
        "strict_weights": STRICT_WEIGHTS,
        "lenient_components": {k: round(v, 6) for k, v in lenient_components.items()},
        "gates": {
            "source_integrity_factor": integrity_factor,
            "source_integrity": integrity_detail,
            "case_records_loaded": facts is not None,
        },
        "sanctions_detail": sanctions_detail,
        "aml_detail": aml_detail,
        "control_detail": control_detail,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("answer", type=Path)
    parser.add_argument("--workspace", type=Path, default=Path("/workspace"))
    args = parser.parse_args()
    payload = json.loads(args.answer.read_text(encoding="utf-8"))
    try:result=score(payload,args.workspace)
    except Exception as exc:
        sys.stderr.write("evaluator failed: "+type(exc).__name__+"\n");return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

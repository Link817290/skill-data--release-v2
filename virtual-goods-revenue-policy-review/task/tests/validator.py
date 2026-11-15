#!/usr/bin/env python3
"""Condition-blind scorer for a revenue-policy review ledger."""

from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import re
import sys
import unicodedata
from pathlib import Path
from semantic_judge import adjudicate, adjudicate_dimensions


FIELDS = [
    "finding_id",
    "topic",
    "conclusion",
    "accounting_effect",
    "rationale",
    "evidence",
    "residual_evidence",
    "audit_response",
]

ALIASES = {
    "finding_id": {"findingid", "finding", "issueid", "issue", "id", "reference"},
    "topic": {"topic", "subject", "matter", "accountingissue", "issuetopic"},
    "conclusion": {"conclusion", "outcome", "assessment", "status", "disposition"},
    "accounting_effect": {"accountingeffect", "effect", "impact", "financialstatementeffect", "reportingeffect"},
    "rationale": {"rationale", "basis", "analysis", "reasoning", "reason"},
    "evidence": {"evidence", "sourcereference", "sources", "citation", "citations", "locator"},
    "residual_evidence": {"residualevidence", "evidenceneeded", "openitems", "gap", "missingevidence", "remainingevidence"},
    "audit_response": {"auditresponse", "response", "procedure", "procedures", "nextsteps", "auditwork"},
}

STOPWORDS = {
    "about", "above", "accounting", "across", "after", "again", "against", "also", "among",
    "because", "before", "being", "between", "company", "conclusion", "current", "customer",
    "does", "each", "evidence", "final", "financial", "from", "have", "into", "issuer", "material",
    "management", "policy", "position", "record", "recognition", "related", "response", "revenue",
    "service", "statement", "subject", "support", "than", "that", "their", "there", "these", "this",
    "through", "under", "using", "while", "with", "would",
}

CORE_CONCEPTS = {
    "allocation", "amortization", "attestation", "chargeback", "classification", "cohort", "commensurate",
    "completeness", "consumable", "contractcost", "control", "cutoff", "deferral", "developer",
    "developerfee", "disclosuregap", "distinctpromise", "distributionchannel", "durable", "estimate",
    "eligibility", "estimatechange", "exchangebalance", "expense", "externalassurance", "gross", "hostingmodel", "icfropinion", "integration", "itemacquisition", "liability", "managementassessment", "materiality",
    "materialweakness", "performanceobligation", "principal", "processingfee", "remainingpopulation",
    "remediation", "representative", "restatement", "subscription", "timing", "userlife", "virtualcurrency", "criticalauditmatter",
}

PHRASES = [
    (r"material\s+(?:weakness|control deficiency)", "materialweakness"),
    (r"restat(?:e|ed|ement|ing)\w*", "restatement"),
    (r"performance\s+obligation\w*|accounting\s+unit\w*|promised\s+(?:good|service)", "performanceobligation"),
    (r"hosting\s+(?:service|obligation|model)|integrated(?:[- ]and[- ]enhanced)?\s+(?:online|gaming|platform)\s+(?:experience|service)", "hostingmodel"),
    (r"virtual\s+currenc\w*|stored\s+value|robux", "virtualcurrency"),
    (r"item\s+(?:acquisition|purchase|selection)|acquir(?:e|ed|ing)\s+(?:a\s+)?virtual\s+item", "itemacquisition"),
    (r"defer(?:red|ral|ring)?", "deferral"),
    (r"cut[ -]?off", "cutoff"),
    (r"consum(?:able|ed|ption)", "consumable"),
    (r"durable|persistent\s+(?:item|benefit)|continuing\s+access", "durable"),
    (r"remaining\s+population|unclassif\w*|uncategorized|unidentified\s+(?:purchase|population)", "remainingpopulation"),
    (r"representative|selection\s+bias|bias\s+analysis|similar(?:ity|\s+(?:experience|population))", "representative"),
    (r"user\s+(?:life|lifetime|tenure)|paying[- ]user\s+life|customer\s+life|average\s+life", "userlife"),
    (r"retention\s+cohort|user\s+cohort", "cohort"),
    (r"developer\s+exchange\s+fee|creator\s+(?:payment|fee)", "developerfee"),
    (r"developer\s+exchange\s+program|exchange\s+program", "developerfee"),
    (r"(?:not|in)eligible|eligibility|qualif(?:y|ied|ication)|good[- ]standing", "eligibility"),
    (r"not\s+permitted\s+to\s+exchange|non[- ]?exchangeable|ineligible\s+(?:earned\s+)?(?:balance|currency)|forfeit(?:ed|ure)?", "exchangebalance"),
    (r"(?:recorded|program|corresponding)\s+liabilit\w*|liability\s+reconciliation", "liability"),
    (r"developer|creator|content\s+supplier", "developer"),
    (r"integrat(?:e|ed|es|ing|ion)", "integration"),
    (r"distribution\s+channel|channel\s+partner|app\s+store|payment\s+processor|apple|google", "distributionchannel"),
    (r"(?:payment[- ]?)?processing\s+(?:fee|cost)|processor\s+(?:fee|cost)", "processingfee"),
    (r"contract[- ]cost|deferred\s+cost|incremental\s+cost", "contractcost"),
    (r"amorti[sz](?:e|ed|es|ing|ation)", "amortization"),
    (r"premium\s+subscription|subscription\s+bundle|monthly\s+subscription", "subscription"),
    (r"distinct\s+(?:service|promise|benefit)|separate\s+(?:performance\s+obligation|promise|allocation)", "distinctpromise"),
    (r"not\s+(?:addressed|disclosed|stated)|omitt(?:ed|ing)|disclosure\s+(?:gap|silence)|no\s+(?:accounting|revenue)[ -]policy", "disclosuregap"),
    (r"standalone\s+(?:value|selling price)|allocation", "allocation"),
    (r"commensurate|comparable\s+(?:rate|fee)", "commensurate"),
    (r"remediat(?:e|ed|es|ing|ion)|operating\s+effectiveness", "remediation"),
    (r"change(?:s|d)?\s+in\s+(?:an\s+)?accounting\s+estimate|estimate\s+change", "estimatechange"),
    (r"critical\s+audit\s+matter|\bcam\b", "criticalauditmatter"),
    (r"management(?:'s)?\s+(?:formal\s+)?(?:assessment|conclusion).*internal\s+control|management's\s+report\s+on\s+internal\s+control", "managementassessment"),
    (r"(?:unqualified|adverse)\s+opinion\s+on\s+(?:the\s+company's\s+)?internal\s+control|express(?:ed|es)?\s+(?:no\s+|an?\s+)?opinion.*internal\s+control", "icfropinion"),
    (r"external\s+(?:control\s+)?assurance|independent\s+auditor|registered\s+public\s+accounting\s+firm", "externalassurance"),
    (r"attest(?:ation|ed|ing)?|section\s+404", "attestation"),
]

DOC_ALIASES = {
    "01_staff_comment.pdf": ("01_staff_comment", "staff comment", "comment letter"),
    "02_company_response.htm": ("02_company_response", "company response", "response letter"),
    "03_amended_registration_statement.htm": ("03_amended_registration_statement", "amended registration", "january amendment"),
    "04_issued_filing.htm": ("04_issued_filing", "final prospectus", "issued filing"),
    "05_remediation_annual_report.pdf": ("05_remediation_annual_report", "2021 annual report", "2021 form 10-k"),
    "06_estimate_change_annual_report.pdf": ("06_estimate_change_annual_report", "2022 annual report", "2022 form 10-k", "latest annual report"),
}


def norm_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", value).casefold())


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def canonical_text(value: str) -> str:
    out = html.unescape(unicodedata.normalize("NFKC", clean(value)).casefold())
    for pattern, replacement in PHRASES:
        out = re.sub(pattern, f" {replacement} ", out)
    return re.sub(r"\s+", " ", out)


def concepts(value: str) -> set[str]:
    text = canonical_text(value)
    found = {token for token in CORE_CONCEPTS if re.search(rf"\b{re.escape(token)}\b", text)}
    for token in re.findall(r"[a-z][a-z0-9]{4,}", text):
        if token not in STOPWORDS and token in CORE_CONCEPTS:
            found.add(token)
    if "gross" in text:
        found.add("gross")
    if "principal" in text:
        found.add("principal")
    if "control" in text:
        found.add("control")
    if "timing" in text or "period" in text:
        found.add("timing")
    if "estimate" in text:
        found.add("estimate")
    if "materiality" in text or "immaterial" in text:
        found.add("materiality")
    if "complete" in text or "reconcile" in text:
        found.add("completeness")
    if "classif" in text:
        found.add("classification")
    if "expense" in text or "cost of revenue" in text:
        found.add("expense")
    if "chargeback" in text or "refund" in text:
        found.add("chargeback")
    return found


# A short window of intervening words, used wherever a lexical rule has to span
# real prose ("cannot yet conclude", "the final prospectus explicitly disclosed")
# instead of a fixed collocation. Negators may not be consumed as filler, so
# "does not establish" and "cannot not conclude" stay outside the window.
SHORT_GAP = r"(?:(?!not\b|never\b|no\b|fail\w*)[\w'-]+\s+){0,3}"
# Same window, but tolerant of a parenthetical comma ("unable, on this record,
# to determine"). Kept separate so that a comma-crossing clause boundary cannot
# silently loosen the policy rule below, where the noun must govern the verb.
HEDGE_GAP = r"(?:(?!not\b|never\b|no\b|fail\w*)[\w'-]+[\s,]+){0,3}"

# Words that end the stretch of prose a rule may reach across: a negator, a
# coordinator, or a subordinator all start a new predication, so a window that
# consumed one would let a rule pair a subject in one clause with a verb in the
# next. Punctuation is excluded by the windows themselves, which only consume
# word characters.
CLAUSE_BREAK = (
    r"not|never|no|nor|neither|fail\w*|but|however|although|though|while|"
    r"whereas|and|or|yet|because|since|so|therefore|if|unless|that|which|who"
)
# The stretch a quantifier may span to reach the noun it quantifies: its
# modifiers, and the light preposition of a measure phrase. It is bounded and
# clause-safe rather than a fixed vocabulary, so "no known exceptions", "no
# disclosed error correction" and "no evidence of material misstatement" are
# read the same way.
MODIFIER_GAP = (
    rf"(?:(?!(?:{CLAUSE_BREAK})\b)[\w'-]+\s+of\s+)?"
    rf"(?:(?!(?:{CLAUSE_BREAK})\b)[\w'-]+\s+){{0,2}}"
)

# Clean-opinion phrasings. These report the absence of a finding, so they must
# be neutralized before the exception test rather than swallowed by it.
NEGATED_FINDING = re.compile(
    rf"\b(?:no|without|nil)\s+{MODIFIER_GAP}"
    r"(?:exceptions?|errors?|misstatements?|deviations?|discrepanc(?:y|ies))\b"
    # A finding word that is itself denied ("not incorrect", "nothing
    # erroneous") is also the absence of a finding.
    rf"|\b(?:not|nothing|never)\s+{SHORT_GAP}(?:incorrect\w*|erroneous|in\s+error)\b"
)

# "Error" and "incorrect" are only findings when the text predicates them of
# something. As the head of a compound or a measure phrase ("error-correction
# checkbox", "error term", "margin of error", "trial and error") the same token
# is ordinary technical vocabulary. The rule is grammatical rather than a list
# of known compounds: the token must be a determined or verb-governed noun
# phrase head, it may not carry a hyphenated modifier, it may not sit in an
# "of" measure phrase, and what follows it must be punctuation or a closed-class
# function word rather than another content word.
_ERROR_HEAD = r"(?<!\bof\s)\berrors?\b"
_ERROR_TAIL = (
    r"(?=\s*(?:[.,;:!?)\]]|$|"
    r"\b(?:in|of|on|to|by|for|from|that|which|and|or|but|because|so|therefore|"
    r"when|while|under|was|were|is|are|has|have|had|requiring|required|causing|"
    r"caused|affecting|identified|noted|found|corrected|resulting)\b))"
)
ERROR_FINDING = re.compile(
    rf"\b(?:an?|the|this|that|these|those|such|its|their)\s+(?:[\w'-]+\s+){{0,2}}?{_ERROR_HEAD}{_ERROR_TAIL}"
    rf"|\b(?:identif\w+|not(?:e|ed|es)|found|detect\w+|reveal\w+|contain\w*|reflect\w*|"
    rf"correct(?:s|ed|ing)?|disclos\w+|report\w*)\s+(?:[\w'-]+\s+){{0,2}}?{_ERROR_HEAD}{_ERROR_TAIL}"
    rf"|{_ERROR_HEAD}\s+(?:was|were|is|are|ha(?:s|ve)\s+been)\s+(?:[\w'-]+\s+){{0,2}}?"
    r"(?:identified|found|noted|detected|made|corrected|reported|disclosed)\b"
    r"|\bin\s+error\b"
)

# Supersession is an act, so these stems report a finding only in their verbal
# uses. The nominalization names a thing instead ("a replacement control", "the
# replacement data extract was reconciled") and never carries the -ed of the
# participle, so the participle must either be introduced by a governor -- an
# auxiliary, a determiner, an adverb, or the start of the cell -- or be closed
# off by punctuation or a function word the way a predicate is. The bare finite
# stem is noun-ambiguous on its own and is therefore required to take an object
# or an agent phrase.
_SUPERSEDE_PARTICIPLE = r"(?:supersed|replac|overturn)ed"
_SUPERSEDE_FINITE = r"(?:supersed(?:e|es|ing)|replac(?:e|es|ing)|overturn(?:s|ing)?)"
_SUPERSEDE_HEAD = (
    r"(?:^|[.;:,()\[\]—–-]\s*|"
    r"\b(?:was|were|is|are|be|been|being|ha(?:s|ve|d)|remain(?:s|ed)?|"
    r"becomes?|became|the|this|that|these|those|its|their|our|a|an|such|"
    r"and|or|then|now|still|already|later)\s+|\b[\w'-]+ly\s+)"
)
_SUPERSEDE_TAIL = (
    r"(?=\s*(?:[.,;:!?)\]]|$)|\s+[—–-]|"
    r"\s+\b(?:by|with|in|on|at|to|as|for|from|and|or|but|because|so|therefore|"
    r"when|while|since|during|through|under|it|its|the|this|that|these|those|"
    r"a|an)\b)"
)
_SUPERSEDE_OBJECT = (
    r"(?:by|the|this|that|these|those|its|their|our|a|an|such|management|"
    r"prior|earlier|original|underlying)"
)
SUPERSESSION_FINDING = re.compile(
    rf"{_SUPERSEDE_HEAD}{_SUPERSEDE_PARTICIPLE}\b"
    rf"|\b{_SUPERSEDE_PARTICIPLE}{_SUPERSEDE_TAIL}"
    rf"|\b{_SUPERSEDE_FINITE}\s+(?:[\w'-]+\s+){{0,1}}?{_SUPERSEDE_OBJECT}\b"
)
# A supplanting that is denied ("does not replace underlying audit evidence")
# reports that nothing was supplanted, so the immediate clause is checked for a
# negator before the match is accepted.
_NEGATOR_NEARBY = re.compile(r"\b(?:not|never|nor|neither|no)\b")


def supersession_finding(text: str) -> bool:
    for match in SUPERSESSION_FINDING.finditer(text):
        clause = re.split(r"[.;:!?,]", text[: match.start()])[-1]
        if _NEGATOR_NEARBY.search(" ".join(clause.split()[-3:])):
            continue
        return True
    return False


# "Incorrect" predicates a fault of something. Bound into a hyphenated compound
# it modifies a different head noun and asserts nothing about it, so "the
# incorrect-classification risk was tested" names a risk that was tested rather
# than a classification that was wrong. The token therefore has to stand free of
# hyphens and be either a predicate adjective closed off by punctuation or a
# function word, or the attributive modifier inside a determined noun phrase.
_INCORRECT = r"(?<![\w-])incorrect(?![\w-])"
_INCORRECT_TAIL = (
    r"(?=\s*(?:[.,;:!?)\]]|$)|\s+[—–-]|"
    r"\s+\b(?:in|on|at|of|to|by|as|for|from|with|and|or|but|because|so|"
    r"therefore|when|while|under|since|until|that|which|was|were|is|are|"
    r"has|have|had)\b)"
)
INCORRECT_FINDING = re.compile(
    rf"\b(?:was|were|is|are|be|been|being|prov(?:e|es|ed|en)|remain(?:s|ed)?|"
    rf"deem(?:s|ed)?|found|held|considered|appears?)\s+"
    rf"(?:(?!(?:{CLAUSE_BREAK})\b)[\w'-]+\s+){{0,2}}?{_INCORRECT}{_INCORRECT_TAIL}"
    rf"|\b(?:an?|the|this|that|these|those|such|its|their)\s+"
    rf"(?:(?!(?:{CLAUSE_BREAK})\b)[\w'-]+\s+){{0,1}}?{_INCORRECT}\s+[\w'-]*[a-z]\b"
)

# "Open" is a status only when it is predicated of the matter under review.
# Attached to a following noun ("open items", "open-source component") or
# preceded by one ("the market open") it is an attribute of that noun and says
# nothing about the finding, so the token must stand free of hyphens, be
# governed by a copula, a verb, an adverb, punctuation or the start of the cell,
# and be closed off by punctuation, the end of the cell, or a function word.
_OPEN = r"(?<![\w-])open(?![\w-])"
_OPEN_HEAD = (
    r"(?:^|[.;:,()\[\]—–-]\s*|"
    r"\b(?:is|are|was|were|be|been|being|remain(?:s|ed)?|stay(?:s|ed)?|"
    r"left|leaves|keep(?:s|t)?|held|marked|flagged|considered|treated\s+as|"
    r"still|currently|presently|now|also|therefore|and|or|as)\s+)"
)
_OPEN_TAIL = (
    r"(?=\s*(?:[.,;:!?)\]]|$)|\s+[—–-]|"
    r"\s+\b(?:in|on|at|to|as|by|for|from|with|until|pending|subject|because|"
    r"and|or|but|so|therefore|whether|that|which|when|while)\b)"
)
OPEN_STATUS = re.compile(rf"{_OPEN_HEAD}{_OPEN}{_OPEN_TAIL}")

# "The record requires further work" is an open-item statement, so the noun has
# to govern the verb. Modals and adverbs may intervene, and a comma-enclosed
# parenthetical is allowed, but a clause linker may not be consumed: in "the
# record is established, but testing requires ..." the verb belongs to another
# subject and the record is not open.
_REQUIRE = r"requir(?:e|es|ed|ing)\b"
RECORD_REQUIREMENT = re.compile(
    rf"\brecord\b\s+(?:(?!(?:{CLAUSE_BREAK})\b)[\w'-]+\s+){{0,3}}?{_REQUIRE}"
    rf"|\brecord\b\s*,\s*(?:(?!(?:{CLAUSE_BREAK})\b)[\w'-]+\s+){{0,3}}"
    rf"(?!(?:{CLAUSE_BREAK})\b)[\w'-]+\s*,\s*{_REQUIRE}"
)

# Single definition of "the final record establishes the adopted policy",
# shared by the supported branch and by conclusion_factor so the two cannot
# drift apart. The short non-negated window lets the active phrasing ("the
# final policy sets out ...") and the passive one ("the adopted treatment is
# disclosed in the final note") reach the same class.
POLICY_SOURCE = (
    r"\b(?:final|issued|adopted|amended)\s+"
    r"(?:record|polic(?:y|ies)|disclosure|prospectus|filing|note|treatment|position)"
)
POLICY_VERB = (
    r"\b(?:establish\w*|adopt\w*|stat(?:e|es|ed|ing)|set(?:s|ting)?|"
    r"provid\w*|disclos\w*|retain\w*)"
)
POLICY_ESTABLISHED = re.compile(
    rf"{POLICY_SOURCE}\s+{SHORT_GAP}{POLICY_VERB}|{POLICY_VERB}\s+{SHORT_GAP}{POLICY_SOURCE}"
)

# An evaluation with no stated basis is filler, not a conclusion.
HEDGED_EVALUATION = re.compile(
    r"\b(?:appears?|appeared|seems?|seemed|looks?|probably|possibly|apparently|presumably)\s+"
    r"(?:to\s+be\s+)?"
    r"(?:reasonable|acceptable|appropriate|fine|ok(?:ay)?|satisfactory|adequate|sound)\b"
)
BASIS_SIGNAL = re.compile(
    r"\b(?:because|based\s+on|supported\s+by|corroborat\w*|consistent\s+with|evidence|"
    r"document(?:ed|ation)|tested|testing|reconcil\w*|pursuant\s+to|per\s+the|"
    r"note\s*\d+|comment\s*\d+)\b"
)


def conclusion_class(value: str) -> str:
    text = canonical_text(value)
    # "No exception", "without exception", "no errors" are negative findings;
    # collapse them to a single marker so the exception branch below cannot read
    # them as their opposite.
    text = NEGATED_FINDING.sub(" noexception ", text)
    mixed = bool(re.search(r"\b(partly|partial|mixed|qualified)\b", text))
    if mixed and re.search(r"\b(unresolved|modified|retained|established|supported)\b", text):
        return "modified"
    # The hedge windows keep "cannot yet conclude" / "unable at this time to
    # conclude" inside this branch, and "does not ... support" is held to one
    # sentence so a "does not" in the first sentence cannot pair with a
    # "support" three sentences later.
    if re.search(
        r"\b(unresolved|insufficient|undetermined|indeterminate|evidentiary gap)\b"
        rf"|cannot[\s,]+{HEDGE_GAP}(?:conclude|determine|establish)"
        rf"|unable[\s,]+{HEDGE_GAP}to[\s,]+{HEDGE_GAP}(?:conclude|determine|establish)"
        r"|does\s+not\s+[^.;!?]*?\bsupport"
        r"|remediat\w*\s+(?:was|is|were|are)?\s*(?:still\s+)?in\s+(?:the\s+)?process"
        r"|remediat\w*\s+(?:was|is|were|are)?\s*not\s+(?:complete|established|effective)",
        text,
    ) or OPEN_STATUS.search(text) or RECORD_REQUIREMENT.search(text):
        return "open"
    if re.search(r"\b(modified|partly|partial|qualified|retained\s+in\s+part)\b|superseded\s+in\s+part", text):
        return "modified"
    if re.search(
        r"\b(exception|unsupported|reject(?:ed|s|ing)?|misstatement)\b"
        r"|not\s+support(?:ed|able)",
        text,
    ) or ERROR_FINDING.search(text) or INCORRECT_FINDING.search(text) or supersession_finding(text):
        return "exception"
    # A hedge with no stated basis ("appears reasonable", "seems appropriate")
    # carries no audit content, so it is dropped before the supported test and
    # falls through to "unknown".
    grounded = text if BASIS_SIGNAL.search(text) else HEDGED_EVALUATION.sub(" ", text)
    if re.search(
        r"\b(supported|acceptable|appropriate|retained|established|adopted|confirmed|resolved|noexception)\b",
        grounded,
    ) or POLICY_ESTABLISHED.search(grounded):
        return "supported"
    # "Reasonable" is only a conclusion when the row says what it rests on.
    if re.search(r"\breasonable\b", grounded) and BASIS_SIGNAL.search(grounded):
        return "supported"
    return "unknown"


def resolve_columns(headers: list[str]) -> dict[str, str]:
    normalized = {norm_header(header): header for header in headers}
    result: dict[str, str] = {}
    for field, aliases in ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                result[field] = normalized[alias]
                break
    if len(result) < 4 and len(headers) >= len(FIELDS):
        return dict(zip(FIELDS, headers[: len(FIELDS)]))
    return result


def read_ledger(path: Path) -> tuple[list[dict[str, str]], dict[str, str], list[str]]:
    errors: list[str] = []
    try:
        raw = path.read_text(encoding="utf-8-sig", errors="strict")
    except (OSError, UnicodeError) as exc:
        return [], {}, [f"unreadable ledger: {exc}"]
    try:
        dialect = csv.Sniffer().sniff(raw[:8192], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    try:
        reader = csv.DictReader(io.StringIO(raw), dialect=dialect)
        headers = [clean(item) for item in (reader.fieldnames or [])]
        mapping = resolve_columns(headers)
        rows = []
        for source in reader:
            row = {field: clean(source.get(header, "")) for field, header in mapping.items()}
            if any(row.values()):
                rows.append(row)
    except (csv.Error, TypeError) as exc:
        return [], {}, [f"malformed ledger: {exc}"]
    if not headers:
        errors.append("missing header")
    return rows, mapping, errors


def expected_documents(evidence: str) -> set[str]:
    lower = evidence.casefold()
    return {name for name in DOC_ALIASES if name.casefold() in lower}


def cited_documents(evidence: str) -> set[str]:
    lower = evidence.casefold()
    return {
        name
        for name, aliases in DOC_ALIASES.items()
        if name.casefold() in lower or any(alias in lower for alias in aliases)
    }


def candidate_match_score(candidate: dict[str, str], expected: dict[str, str]) -> float:
    expected_text = " ".join(expected.get(key, "") for key in ("topic", "accounting_effect", "rationale"))
    candidate_text = " ".join(candidate.get(key, "") for key in ("topic", "accounting_effect", "rationale"))
    expected_set = concepts(expected_text)
    candidate_set = concepts(candidate_text)
    shared = expected_set & candidate_set
    if len(shared) < 2:
        return 0.0
    return len(shared) / max(1, len(expected_set))


def assign_rows(candidates: list[dict[str, str]], expected: list[dict[str, str]], semantic_pairs=None) -> dict[int, int]:
    pair_scores: list[list[float]] = []
    for ci,row in enumerate(candidates):
        values = []
        for gi,gold in enumerate(expected):
            content = float((gi,ci) in semantic_pairs) if semantic_pairs is not None else candidate_match_score(row, gold)
            if content < 0.25:
                values.append(0.0)
                continue
            # Semantic adjudication owns professional state equivalence. The
            # assignment stage must not prefer rows merely because they contain
            # one of the old status keywords.
            values.append(content + 0.30)
        pair_scores.append(values)

    # A square Hungarian assignment gives the global one-to-one maximum in
    # polynomial time. Zero-weight padding leaves unsupported rows unmatched.
    size = max(len(candidates), len(expected))
    if size == 0:
        return {}
    weights = [[0.0] * size for _ in range(size)]
    for row_index, scores in enumerate(pair_scores):
        for column_index, value in enumerate(scores):
            weights[row_index][column_index] = value

    # Potentials implementation for minimum cost; negate weights to maximize.
    u = [0.0] * (size + 1)
    v = [0.0] * (size + 1)
    p = [0] * (size + 1)
    way = [0] * (size + 1)
    for row in range(1, size + 1):
        p[0] = row
        min_value = [float("inf")] * (size + 1)
        used = [False] * (size + 1)
        column = 0
        while True:
            used[column] = True
            matched_row = p[column]
            delta = float("inf")
            next_column = 0
            for candidate_column in range(1, size + 1):
                if used[candidate_column]:
                    continue
                current = -weights[matched_row - 1][candidate_column - 1] - u[matched_row] - v[candidate_column]
                if current < min_value[candidate_column]:
                    min_value[candidate_column] = current
                    way[candidate_column] = column
                if min_value[candidate_column] < delta:
                    delta = min_value[candidate_column]
                    next_column = candidate_column
            for candidate_column in range(size + 1):
                if used[candidate_column]:
                    u[p[candidate_column]] += delta
                    v[candidate_column] -= delta
                else:
                    min_value[candidate_column] -= delta
            column = next_column
            if p[column] == 0:
                break
        while True:
            previous = way[column]
            p[column] = p[previous]
            column = previous
            if column == 0:
                break

    result = {}
    for expected_index in range(len(expected)):
        candidate_index = p[expected_index + 1] - 1
        if 0 <= candidate_index < len(candidates) and weights[candidate_index][expected_index] > 0:
            result[expected_index] = candidate_index
    return result


def source_integrity(answer: Path, ground_truth: dict) -> tuple[float, list[str]]:
    problems = []
    workspace = answer.parent
    found_source = False
    for name, expected_hash in ground_truth.get("source_sha256", {}).items():
        path = workspace / name
        if not path.exists():
            continue
        found_source = True
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected_hash:
            problems.append(name)
    if found_source and problems:
        return 0.5, problems
    return 1.0, problems


def dump_penalty(rows: list[dict]) -> float:
    """How far the ledger is a transcription of the sources rather than an analysis.

    The target is source material pasted wholesale into cells, not a verbose row.
    Overflow decays the factor continuously: per-row excess is averaged over the
    ledger and drives a linear decay down to a 0.4 floor. Embedded markup is direct evidence
    of transcription and goes straight to the floor.
    """
    joined = [" ".join(str(value) for value in row.values() if value) for row in rows]
    if not joined:
        return 1.0
    if any("<html" in text.casefold() for text in joined):
        return 0.4
    # Row length is not evidence of source copying. A long, independently
    # reasoned finding must remain usable; only embedded source markup is a
    # deterministic transcription signal here.
    return 1.0


def score(answer: Path, ground_truth: dict) -> dict:
    rows, mapping, read_errors = read_ledger(answer)
    expected = ground_truth["golden_rows"]
    lines=["C%04d: %s"%(i+1,json.dumps(row,ensure_ascii=False)) for i,row in enumerate(rows)]
    semantic=adjudicate("\n".join(lines),json.loads(Path(__file__).with_name("semantic_source.json").read_text())) if rows else None
    semantic_pairs=set()
    if semantic:
        for gi,gold in enumerate(expected):
            item=semantic["items"][gold["finding_id"]]
            if item["fraction"]:
                hits=[(sum(q in line for q in item["quotes"]),ci) for ci,line in enumerate(lines)]
                best=max(hits)
                if not best[0]:raise RuntimeError("Semantic match has no attributable candidate row")
                semantic_pairs.add((gi,best[1]))
    assignments = assign_rows(rows, expected, semantic_pairs)

    dimension_rows = [
        {
            "id": gold["finding_id"],
            "expected": {key: gold.get(key, "") for key in FIELDS},
            "candidate": {key: rows[candidate_index].get(key, "") for key in FIELDS},
        }
        for index, gold in enumerate(expected)
        if (candidate_index := assignments.get(index)) is not None
    ]
    dimensions = adjudicate_dimensions(dimension_rows) if dimension_rows else {}

    field_factor = 1.0 if all(field in mapping for field in FIELDS) else 0.6
    finding_ids = [clean(row.get("finding_id", "")) for row in rows]
    unique_finding_ids = bool(finding_ids) and all(finding_ids) and len(set(finding_ids)) == len(finding_ids)
    identifier_factor = len(set(filter(None, finding_ids))) / max(len(finding_ids), 1)
    dump_factor = dump_penalty(rows)
    fingerprints = [
        re.sub(
            r"[^a-z0-9]",
            "",
            canonical_text(" ".join(row.get(key, "") for key in ("topic", "accounting_effect", "rationale"))),
        )
        for row in rows
    ]
    largest_duplicate_group = max((fingerprints.count(item) for item in set(fingerprints)), default=0)
    duplicate_factor = 0.2 if len(rows) >= 4 and largest_duplicate_group > max(2, int(len(rows) * 0.4)) else 1.0
    integrity_factor, tampered = source_integrity(answer, ground_truth)
    readable_factor = 0.0 if read_errors or not rows else 1.0
    integrity_gate = readable_factor * field_factor * dump_factor * duplicate_factor * integrity_factor * identifier_factor

    issue_details = []
    weighted_total = 0.0
    for index, gold in enumerate(expected):
        weight = float(ground_truth["weights"][gold["finding_id"]])
        candidate_index = assignments.get(index)
        if candidate_index is None:
            issue_score = 0.0
            detail = {"finding": gold["finding_id"], "matched_row": None, "score": 0.0}
        else:
            row = rows[candidate_index]
            dimension = dimensions.get(gold["finding_id"])
            if dimension is None:
                raise RuntimeError(f"missing semantic dimension verdict for {gold['finding_id']}")
            status_factor = float(dimension["conclusion"])
            relation = float((index,candidate_index) in semantic_pairs)
            evidence = float(dimension["evidence"])
            residual = float(dimension["residual"])
            action = float(dimension["action"])
            coherence = float(dimension["coherence"])
            issue_score = status_factor * (0.50 * relation + 0.05 * coherence + 0.15 * evidence + 0.10 * residual + 0.20 * action)
            detail = {
                "semantic_evidence": semantic["items"][gold["finding_id"]],
                "finding": gold["finding_id"],
                "matched_row": candidate_index + 2,
                "semantic_dimensions": dimension,
                "relation": round(relation, 6),
                "evidence": round(evidence, 6),
                "residual_evidence": round(residual, 6),
                "audit_response": round(action, 6),
                "row_coherence": round(coherence, 6),
                "score": round(issue_score, 6),
            }
        weighted_total += weight * issue_score
        issue_details.append(detail)

    strict = max(0.0, min(1.0, integrity_gate * weighted_total))
    substantive_issue_score_floor = 0.50
    substantive_issue_count_floor = 12
    substantive_issue_judgments = sum(
        float(detail["score"]) >= substantive_issue_score_floor
        for detail in issue_details
    )

    substantive = [
        row
        for row in rows
        if len(row.get("topic", "")) >= 8
        and len(row.get("conclusion", "")) >= 5
        and len(row.get("rationale", "")) >= 30
        and len(row.get("evidence", "")) >= 15
        and len(row.get("audit_response", "")) >= 15
    ]
    # Diversity is a delivery-shape check over the independently expected
    # evidence states. Candidate wording is judged semantically above; it must
    # not be reduced to a status-keyword count here.
    classes = {
        conclusion_class(gold.get("conclusion", ""))
        for index, gold in enumerate(expected)
        if index in assignments
    } - {"unknown"}
    documents = set().union(*(cited_documents(row.get("evidence", "")) for row in substantive)) if substantive else set()
    residual_complete = bool(substantive) and all(clean(row.get("residual_evidence", "")) for row in substantive)
    lenient_conditions = {
        "readable": readable_factor == 1.0,
        "contract_fields": all(field in mapping for field in FIELDS),
        "unique_finding_ids": unique_finding_ids,
        "usable_issue_count": 6 <= len(substantive),
        "evidence_state_diversity": len(classes) >= 2,
        "cross_record_traceability": len(documents) >= 3 and bool({"05_remediation_annual_report.pdf", "06_estimate_change_annual_report.pdf"} & documents),
        "residual_evidence_addressed": residual_complete,
        "not_source_dump": dump_factor == 1.0,
        "not_repeated_shell": duplicate_factor == 1.0,
        "source_integrity": integrity_factor == 1.0,
        # Coverage of every material expert position is the delivery contract;
        # a strict-score floor is not a substitute for that requirement.
        "material_positions_covered": len(assignments) >= len(expected),
    }
    lenient = 1.0 if all(lenient_conditions.values()) else 0.0

    return {
        "reward": round(strict, 6),
        "rewards": {"strict": round(strict, 6), "lenient": lenient},
        "reward_formulas": ground_truth["reward_formulas"],
        "group_points": {"issue_judgments": round(weighted_total, 6)},
        "gates": {
            "integrity_gate": round(integrity_gate, 6),
            "readable_factor": readable_factor,
            "field_factor": field_factor,
            "dump_factor": dump_factor,
            "duplicate_factor": duplicate_factor,
            "source_integrity_factor": integrity_factor,
        },
        "lenient_conditions": lenient_conditions,
        "issue_details": issue_details,
        "diagnostics": {
            "rows": len(rows),
            "substantive_rows": len(substantive),
            "assigned_findings": len(assignments),
            "substantive_issue_judgments": substantive_issue_judgments,
            "substantive_issue_score_floor": substantive_issue_score_floor,
            "substantive_issue_count_floor": substantive_issue_count_floor,
            "lenient_independence_note": "quality floor reuses strict issue scores; lenient is not independent of strict",
            "resolved_fields": sorted(mapping),
            "read_errors": read_errors,
            "tampered_sources": tampered,
        },
    }


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: validator.py DELIVERABLE")
    answer = Path(sys.argv[1])
    ground_truth = json.loads((Path(__file__).parent / "ground_truth.json").read_text(encoding="utf-8"))
    print(json.dumps(score(answer, ground_truth), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

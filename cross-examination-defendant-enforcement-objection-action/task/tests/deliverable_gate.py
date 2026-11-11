#!/usr/bin/env python3
"""The delivery gate: is the deliverable where the brief said, and is it alone?

Two rules every package applies the same way, read from `deliverable_gate.json` beside the scorer:

  missing   a required deliverable is not at its exact path (name, extension, case) -> the score is 0.
            There is nothing to score, so this is a gate, not a coefficient: `retention` and
            `final_score` become 0 and the ledger records which file was missing.
  extra     every other file in the delivery root that is neither required nor allow-listed is one
            damage instance of the gate item (`DX_DELIVERABLE`, coefficient `extra_coefficient`,
            default 0.4), capped at `extra_cap` instances (default 2). Harness files (`manifest.json`),
            hidden files and caches are allow-listed so the rule never fires on everyone.

Why: a deliverable under another name or extension is not the file the brief asked for, and a
validator that falls back to "any .docx, then any .md" would score it as if it were; drafting notes or
alternative versions shipped as extra files beside the deliverable are read by no content item, so
without the gate they cost nothing. A delivery that carries exactly the named file passes untouched:
the gate is a guard, not a re-score.

    {"schema_version": "deliverable-gate-v1",
     "root": "artifacts",                       # delivery root, relative to the scored workspace ("" = the workspace itself)
     "required": ["civil-appeal-petition.md"],  # exact names under root
     "allowlist": ["manifest.json"],            # fnmatch patterns that are never extras (hidden files and caches always are)
     "golden_carriers": {"成果文件.docx": "civil-appeal-petition.md"},  # the Golden's own file names, and what each stands for
     "extra_coefficient": 0.4, "extra_cap": 2, "item_id": "DX_DELIVERABLE"}

A third rule, `source_dump`, is optional and reads the deliverable itself: a run of `min_run` normalized
characters copied verbatim from a materials file is one damage instance of `item_id` (default
`DX_SOURCE_DUMP`, coefficient 0.4, cap 2). It is the same class of 多说 as an extra file - the source pasted
into the deliverable instead of beside it - which no section-bound length unit measures when it sits
after the closing block. The threshold is set per package above the Golden's own longest verbatim run
(a quoted judgment passage), so quoting stays free and dumping is charged.

    "source_dump": {"materials": "pjroot/materials",   # relative to the tests dir; .docx/.md/.txt files under it
                    "min_run": 500, "window": 24, "coefficient": 0.4, "cap": 2,
                    "item_id": "DX_SOURCE_DUMP", "golden_longest_run": 115}

`check()` returns what is missing and what is extra; `settle()` folds that into a pd-ledger-v1 ledger.
The same module runs in the package (validator.py imports it from its own directory) and in the
calibration host, so the live harness and every rescore agree.
"""
from __future__ import annotations

import csv
import fnmatch
import json
import os
import re
import zipfile
from pathlib import Path

SCHEMA = "deliverable-gate-v1"
DEFAULT_ITEM = "DX_DELIVERABLE"
DUMP_ITEM = "DX_SOURCE_DUMP"
SECTION_ITEM = "DX_REQUIRED_SECTION"
LENGTH_ITEM = "DX_MIN_LENGTH"
LANGUAGE_ITEM = "DX_LANGUAGE"
FOREIGN_ITEM = "DX_FOREIGN_SOURCE"
INVARIANT_ITEM = "DX_JSON_INVARIANT"
TEXT_ITEM = "DX_FORBIDDEN_TEXT"
REQUIREMENT_ITEM = "DX_REQUIREMENT_GATE"
_FILE_TOKEN = re.compile(r"\b[A-Za-z0-9_][\w-]*\.(?:pdf|html?|docx|xlsx|csv|json|txt)\b", re.I)
_HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_LATIN = re.compile(r"[A-Za-z]")
_NOISE_WS = re.compile(r"\s")
TEXT_SUFFIXES = (".md", ".txt", ".docx")
# Characters that do not survive a copy between carriers (Markdown marks, spacing, quotes and brackets in
# either width): the comparison runs on what is left, so a re-punctuated paste still reads as a copy.
_NOISE = re.compile(r"[\s，,。．.、；;：:“”\"'‘’（）()\[\]【】《》〈〉<>\-—–_*#|>`~·]")
ALWAYS_ALLOWED = (".*", "__pycache__", "__pycache__/*", "*.pyc", "~$*", "*.bak", "*~", "Thumbs.db", "desktop.ini")


def load(tests_dir: Path) -> dict | None:
    path = Path(tests_dir) / "deliverable_gate.json"
    if not path.is_file():
        return None
    config = json.loads(path.read_text(encoding="utf-8"))
    config.setdefault("root", "")
    config.setdefault("allowlist", [])
    config.setdefault("extra_coefficient", 0.4)
    config.setdefault("extra_cap", 2)
    config.setdefault("item_id", DEFAULT_ITEM)
    return config


def _allowed(relative: str, patterns) -> bool:
    parts = relative.split("/")
    for pattern in (*ALWAYS_ALLOWED, *patterns):
        if fnmatch.fnmatch(relative, pattern) or any(fnmatch.fnmatch(part, pattern) for part in parts):
            return True
    return False



def locate(root: Path, name: str, config: dict) -> Path | None:
    """The required file at the delivery root, or at one of `also_accept`'s alternate locations.

    The harness archives a rollout with the delivery flattened into the root and the brief's nested
    path kept beside it, while the live run and solve.sh write the nested path. Both are real, so the
    gate reads both. This decides only where the file is looked for, never what is charged."""
    direct = Path(root) / name
    if direct.is_file():
        return direct
    for alternate in config.get("also_accept") or []:
        candidate = Path(root) / alternate / name
        if candidate.is_file():
            return candidate
    return None


def _plain_text(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        try:
            with zipfile.ZipFile(path) as z:
                xml = z.read("word/document.xml").decode("utf-8", "ignore")
        except (zipfile.BadZipFile, KeyError, OSError):
            return ""
        return "".join(re.findall(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>", xml))
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _normalized(text: str) -> str:
    return _NOISE.sub("", text)


def longest_copied_run(deliverable: str, sources: list[str], window: int = 24, stride: int = 4) -> int:
    """Length of the longest stretch of `deliverable` (normalized) that appears verbatim in any source.

    Every `window`-character slice of the sources at `stride` offsets is indexed; every slice of the
    deliverable is looked up, and hits closer together than the stride are one run. A copied stretch of
    L characters therefore yields hits every `stride` characters and is measured to within `stride`."""
    index = set()
    for text in sources:
        norm = _normalized(text)
        for i in range(0, max(0, len(norm) - window + 1), stride):
            index.add(norm[i:i + window])
    if not index:
        return 0
    doc = _normalized(deliverable)
    best = start = previous = -1
    for i in range(0, len(doc) - window + 1):
        if doc[i:i + window] not in index:
            continue
        if previous < 0 or i - previous > stride:
            start = i
        previous = i
        best = max(best, i + window - start)
    return max(best, 0)


def check_source_dump(root: Path, config: dict, tests_dir: Path) -> dict | None:
    """The `source_dump` rule over each required deliverable that is present: `runs` maps a deliverable to
    its longest verbatim run from the materials, `charged` lists the ones at or over `min_run`."""
    rule = config.get("source_dump")
    if not rule or tests_dir is None:
        return None
    materials = Path(tests_dir) / rule.get("materials", "pjroot/materials")
    if not materials.is_dir():
        return {"runs": {}, "charged": [], "error": f"materials not found: {materials}"}
    # Which material formats are read is opt-in: widening it by default would lengthen the runs
    # measured for the packages already using this rule and could charge answers that have not
    # changed. `.html` is stripped to its reading text, since a tag soup shares no run with prose.
    suffixes = tuple(s.lower() for s in rule.get("materials_suffixes", TEXT_SUFFIXES))
    sources = []
    for f in sorted(materials.rglob("*")):
        if f.suffix.lower() not in suffixes:
            continue
        body = _plain_text(f)
        if f.suffix.lower() in (".html", ".htm"):
            body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", body, flags=re.S | re.I)
            body = re.sub(r"<[^>]+>", " ", body)
        sources.append(body)
    window, min_run = int(rule.get("window", 24)), int(rule.get("min_run", 500))
    runs = {}
    # The Golden's own carriers (`golden_carriers`) are read too, so a Golden replay and a probe staged
    # under the Golden's file name are measured like a delivery under the required name.
    for name in [*config["required"], *(config.get("golden_carriers") or {})]:
        path = locate(root, name, config) or (Path(root) / name)
        readable = TEXT_SUFFIXES + ((".xlsx", ".xlsm") if rule.get("read_workbook") else ())
        if path.is_file() and path.suffix.lower() in readable:
            runs[name] = longest_copied_run(_measurable_text(path), sources, window)
    return {"runs": runs, "charged": sorted(n for n, r in runs.items() if r >= min_run), "min_run": min_run}



# --- required sections ----------------------------------------------------------------------------
# The C1 give-away unit gate: a part of the deliverable that every delivered rollout already carries.
# A unit some rollouts miss is a positive item, not a gate, so the counts behind each threshold are
# recorded in the config and re-checked whenever the rollouts change.
def check_required_sections(root: Path, config: dict) -> dict | None:
    """`hits` maps each required section to how often its vocabulary appears; `charged` lists the
    sections below `min_hits`, which is set under every delivered rollout and above a halved answer."""
    rule = config.get("required_sections")
    if not rule:
        return None
    name = rule.get("deliverable") or (config["required"][0] if config["required"] else None)
    path = locate(root, name, config) if name else None
    if path is None:
        return {"hits": {}, "charged": [], "error": "deliverable not found: %s" % name}
    text = _plain_text(path)
    minimum = int(rule.get("min_hits", 5))
    hits = {label: len(re.findall(pattern, text)) for label, pattern in (rule.get("sections") or {}).items()}
    return {"hits": hits, "charged": sorted(k for k, v in hits.items() if v < minimum), "min_hits": minimum}




def _workbook_text(path: Path) -> str:
    """Cell values of every sheet, for a workbook deliverable. Kept out of `_plain_text` so the
    source-dump rule, which compares prose against materials, is unaffected."""
    try:
        import openpyxl
    except ImportError:
        return ""
    try:
        book = openpyxl.load_workbook(path, data_only=False)
    except Exception:
        return ""
    return "".join("".join(str(cell) for cell in row if cell is not None)
                   for sheet in book.worksheets for row in sheet.iter_rows(values_only=True))


def _measurable_text(path: Path) -> str:
    """The deliverable's text for the length rule: prose, or a workbook's cell values."""
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        return _workbook_text(path)
    return _plain_text(path)

# --- minimum length -------------------------------------------------------------------------------
def check_min_length(root: Path, config: dict, tests_dir) -> dict | None:
    """The deliverable's normalized length against Golden's, as a ratio.

    `ratio` below `min_ratio` is a deliverable that is not the piece of work the brief asked for. The
    threshold is set per package under every delivered rollout and over a halved Golden, and both
    figures are recorded in the config so the rule can be re-checked when the rollouts change."""
    rule = config.get("min_length")
    if not rule:
        return None
    name = rule.get("deliverable") or (config["required"][0] if config["required"] else None)
    path = locate(root, name, config) if name else None
    if path is None:
        return {"ratio": None, "charged": [], "error": "deliverable not found: %s" % name}
    golden_length = int(rule.get("golden_length") or 0)
    if golden_length <= 0:
        return {"ratio": None, "charged": [], "error": "golden_length not configured"}
    length = len(_NOISE_WS.sub("", _measurable_text(path)))
    ratio = length / golden_length
    minimum = float(rule.get("min_ratio", 0.75))
    return {"length": length, "golden_length": golden_length, "ratio": round(ratio, 4),
            "min_ratio": minimum, "charged": [name] if ratio < minimum else []}


# --- forbidden text -------------------------------------------------------------------------------
def check_forbidden_text(root: Path, config: dict) -> dict | None:
    """Patterns the brief forbids the deliverable to contain.

    Only for prohibitions whose committable form really is a phrase. A pattern that a correct
    answer might also write is worse than no rule at all, so every pattern configured here is
    measured against all delivered rollouts first and the count is recorded beside it."""
    rule = config.get("forbidden_text")
    if not rule:
        return None
    names = rule.get("deliverable") or config["required"]
    if isinstance(names, str):
        names = [names]
    charged, seen = [], {}
    for name in names:
        path = locate(root, name, config)
        if path is None:
            continue
        text = _measurable_text(path)
        for entry in rule.get("patterns") or []:
            hits = re.findall(entry["pattern"], text, re.I)
            if hits:
                seen.setdefault(entry["id"], []).append(name)
                if entry["id"] not in charged:
                    charged.append(entry["id"])
    return {"hits": seen, "charged": charged}


# --- structural invariants ------------------------------------------------------------------------
def _key_norm(value) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _match_field(element: dict, token: str):
    """The first field whose normalized name contains `token`, and its value.

    Matched by content rather than by path: these deliverables carry no schema contract, and a
    rule bound to one spelling would bind only the answers that happen to use it."""
    for key, value in element.items():
        if token in _key_norm(key):
            return key, value
    return None, None


def _value_hits(value, wanted) -> bool:
    if value is None:
        return False
    for want in wanted:
        if isinstance(want, bool) or isinstance(value, bool):
            if value is want:
                return True
        if _key_norm(value) == _key_norm(want):
            return True
    return False


def check_json_invariants(root: Path, config: dict) -> dict | None:
    """Rules of the form "a record that says A must not also say B", over a JSON deliverable.

    Each rule names an array and two fields by normalized substring. A record where `when` matches
    (or a rule with no `when`, which then reads every record) and `forbid` also matches is a
    violation. One instance per rule, however many records break it: writing the same wrong thing
    in five rows is one drafting decision."""
    rules = (config.get("json_invariants") or {}).get("rules") or []
    if not rules:
        return None
    findings, charged = [], []
    for rule in rules:
        name = rule.get("deliverable") or (config["required"][0] if config["required"] else None)
        path = locate(root, name, config) if name else None
        if path is None or path.suffix.lower() != ".json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        rows = []
        for key, value in data.items():
            if isinstance(value, list) and rule["array"] in _key_norm(key):
                rows.extend(v for v in value if isinstance(v, dict))
        broken = 0
        for element in rows:
            when = rule.get("when")
            if when:
                _, observed = _match_field(element, when["field"])
                if not _value_hits(observed, when["values"]):
                    continue
            _, observed = _match_field(element, rule["forbid"]["field"])
            if _value_hits(observed, rule["forbid"]["values"]):
                broken += 1
        findings.append({"id": rule["id"], "records": len(rows), "violations": broken})
        if broken:
            charged.append(rule["id"])
    return {"rules": findings, "charged": charged}


# --- measured requirement gates -------------------------------------------------------------------
def check_requirement_gate(root: Path, config: dict, tests_dir=None) -> dict | None:
    rule = config.get("requirement_gate") or {}
    kind = rule.get("kind")
    if not kind:
        return None
    name = rule.get("deliverable") or (config.get("required") or [None])[0]
    path = locate(root, name, config) if name else None
    if path is None:
        return {"kind": kind, "checks": {}, "charged": [], "error": "deliverable not found: %s" % name}
    text = _measurable_text(path)
    if kind == "sections":
        hits = {label: len(re.findall(pattern, text, re.I))
                for label, pattern in (rule.get("sections") or {}).items()}
        minimum = int(rule.get("min_hits", 1))
        charged = sorted(label for label, count in hits.items() if count < minimum)
        return {"kind": kind, "hits": hits, "min_hits": minimum, "charged": charged}
    if kind == "gap_marker":
        patterns = rule.get("patterns") or [r"待补充|待填写|待核实|材料未提供|未提供|TBD|placeholder|⟦GAP⟧"]
        count = sum(len(re.findall(pattern, text, re.I)) for pattern in patterns)
        minimum = int(rule.get("min_count", 1))
        return {"kind": kind, "count": count, "min_count": minimum,
                "charged": ["gap_marker"] if count < minimum else []}
    if kind == "party_roster":
        scope = re.split(r"被申请人|被上诉人", text, maxsplit=1)[0]
        names = rule.get("applicants") or []
        missing = [name for name in names if name not in scope]
        return {"kind": kind, "required": names, "missing": missing,
                "charged": ["applicant_roster"] if missing else []}
    if kind == "schedule_invariants":
        required = rule.get("required_fields") or ["项目编号", "项目名称", "区", "项目类型", "面积平方米", "施工队", "开始月份", "结束月份"]
        checks = {label: False for label in (rule.get("labels") or ["identifiers", "one_each", "columns", "horizon", "crews", "duration"])}
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh)
                fields = reader.fieldnames or []
                rows = list(reader)
        except (OSError, UnicodeError, csv.Error):
            return {"kind": kind, "checks": checks, "charged": sorted(checks)}
        checks["columns"] = all(f in fields for f in required)
        ids = [row.get("项目编号", "") for row in rows]
        checks["one_each"] = len(ids) == len(set(ids)) and all(ids)
        try:
            checks["horizon"] = all(1 <= int(row["开始月份"]) <= int(row["结束月份"]) <= 12 for row in rows)
            crews = set(rule.get("allowed_crews") or ["一队", "二队", "三队", "四队", "五队"])
            checks["crews"] = all(row.get("施工队") in crews for row in rows)
            def duration(area):
                area = float(str(area).replace(",", ""))
                return 1 if area <= 50000 else (2 if area <= 150000 else 3)
            checks["duration"] = all(int(row["结束月份"]) - int(row["开始月份"]) + 1 == duration(row["面积平方米"]) for row in rows)
        except (KeyError, TypeError, ValueError):
            checks["horizon"] = checks["crews"] = checks["duration"] = False
        if tests_dir is not None:
            golden = Path(tests_dir).parent / "golden" / path.name
            if golden.is_file():
                try:
                    with golden.open("r", encoding="utf-8-sig", newline="") as fh:
                        gr = list(csv.DictReader(fh))
                    key_fields = ["项目编号", "项目名称", "区", "项目类型", "面积平方米"]
                    expected = {tuple(row.get(k, "") for k in key_fields) for row in gr}
                    observed = {tuple(row.get(k, "") for k in key_fields) for row in rows}
                    checks["identifiers"] = len(rows) == len(gr) and observed == expected
                except (OSError, UnicodeError, csv.Error):
                    checks["identifiers"] = False
            else:
                checks["identifiers"] = bool(rows)
        else:
            checks["identifiers"] = bool(rows)
        charged = sorted(label for label, ok in checks.items() if not ok)
        return {"kind": kind, "checks": checks, "rows": len(rows), "charged": charged}
    return {"kind": kind, "checks": {}, "charged": [], "error": "unknown requirement gate kind: %s" % kind}


# --- foreign sources ------------------------------------------------------------------------------
def _field_values(path: Path, spec: dict) -> list[str]:
    """The strings a deliverable declares as its sources, per the config's pointer.

    A whole-document scan is not good enough: locators and range notations read as file names
    ("input_03-08.html"), and charging those would punish correct work. The pointer names the one
    place the schema puts a source - a workbook column, or a JSON path where `[]` means every
    element - so only real source declarations are read.
    """
    if spec.get("column"):
        try:
            import openpyxl
            book = openpyxl.load_workbook(path, data_only=True)
        except Exception:
            return []
        if spec.get("sheet") and spec["sheet"] not in book.sheetnames:
            return []
        sheet = book[spec["sheet"]] if spec.get("sheet") else book.worksheets[0]
        column = spec["column"]
        return [str(cell.value) for cell in sheet[column][int(spec.get("first_row", 2)) - 1:]
                if cell.value is not None]
    if spec.get("path"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        nodes = [data]
        for step in spec["path"].split("."):
            following = []
            if step.endswith("[]"):
                step = step[:-2]
                for node in nodes:
                    value = node.get(step) if isinstance(node, dict) else None
                    following.extend(value if isinstance(value, list) else [])
            else:
                for node in nodes:
                    if isinstance(node, dict) and step in node:
                        following.append(node[step])
            nodes = following
        return [str(n) for n in nodes if n is not None and not isinstance(n, (list, dict))]
    return [_measurable_text(path)]


def check_foreign_source(root: Path, config: dict, tests_dir) -> dict | None:
    """File names the deliverable cites that the record does not supply.

    The supplied names come from the materials directory itself, so nothing has to be maintained by
    hand. A name the deliverable prints in a source field and the record does not carry is a
    document the reader cannot open - the brief's "no conclusion may depend on information not
    supplied there", in its one mechanically checkable form."""
    rule = config.get("foreign_source")
    if not rule or tests_dir is None:
        return None
    materials = (Path(tests_dir) / rule.get("materials", "../environment/workspace")).resolve()
    if not materials.is_dir():
        return {"cited": [], "charged": [], "error": "materials not found: %s" % materials}
    supplied = {f.name.lower() for f in materials.rglob("*") if f.is_file()}
    allowed = supplied | {a.lower() for a in rule.get("allow", [])} | {
        name.lower() for name in config["required"]}
    cited, charged = [], []
    for spec in rule.get("sources") or [{"deliverable": config["required"][0]}]:
        name = spec.get("deliverable") or config["required"][0]
        path = locate(root, name, config)
        if path is None:
            continue
        for value in _field_values(path, spec):
            for token in _FILE_TOKEN.findall(value):
                cited.append(token)
                if token.lower() not in allowed and token not in charged:
                    charged.append(token)
    return {"cited": sorted(set(cited)), "supplied": sorted(supplied), "charged": sorted(charged)}


# --- language -------------------------------------------------------------------------------------
def check_language(root: Path, config: dict) -> dict | None:
    """The deliverable's script against the one the brief names.

    Counted over script-bearing characters only: Han characters against Latin letters. Digits,
    punctuation, file names and the proper nouns both languages share carry no script and are
    ignored, so a Chinese document quoting an English product name still reads as Chinese. The
    ratio actually measured on delivered rollouts is recorded in the config beside the threshold,
    so the rule can be re-checked when the rollouts change."""
    rule = config.get("language")
    if not rule:
        return None
    want = str(rule.get("script", "han")).lower()
    minimum = float(rule.get("min_ratio", 0.5))
    names = rule.get("deliverable") or config["required"]
    if isinstance(names, str):
        names = [names]
    # Every named deliverable is measured. A package that delivers four files and is told to write
    # in Chinese is not covered by reading one of them, and charging only the first would let the
    # other three be written in anything.
    ratios, charged, missing = {}, [], []
    for name in names:
        path = locate(root, name, config)
        if path is None:
            missing.append(name)
            continue
        text = _measurable_text(path)
        han = len(_HAN.findall(text))
        latin = len(_LATIN.findall(text))
        if not han + latin:
            # Nothing to read. The length rule measures emptiness directly; charging it here too
            # would bill one defect twice.
            ratios[name] = None
            continue
        ratios[name] = round((han if want == "han" else latin) / (han + latin), 4)
        if ratios[name] < minimum:
            charged.append(name)
    verdict = {"script": want, "ratios": ratios, "min_ratio": minimum, "charged": sorted(charged)}
    if missing:
        verdict["error"] = "deliverable not found: %s" % ", ".join(missing)
    return verdict


def check(workspace: Path, config: dict, tests_dir: Path | None = None) -> dict:
    """What is missing and what is extra under the delivery root of `workspace`.

    `workspace` is the directory the scorer was handed (a rollout's `artifacts/`, or `/workspace`). When the
    scorer was handed the deliverable file itself, pass its parent. A workspace that already IS the delivery
    root (the rollout's artifacts/ standing in for `<ws>/artifacts/`) is accepted too."""
    workspace = Path(workspace)
    required = list(config["required"])
    # `golden_carriers` maps the reference answer's own file names to the required name each stands for
    # (a Golden kept as a .docx beside a brief that asks for a .md): they satisfy the requirement on a
    # Golden replay and are never extras. A model has no reason to know them.
    carriers = dict(config.get("golden_carriers") or {})
    root = workspace / config["root"] if config["root"] else workspace
    # When the delivery root is absent the workspace may itself be the root: the archived rollout is
    # staged that way, and so is a live run that wrote the brief's nested path as a sibling of it.
    # `also_accept` is consulted too, or a delivery one level down would read as missing.
    if config["root"] and not root.is_dir() and any(
            (workspace / name).exists() or locate(workspace, name, config) is not None
            for name in [*required, *carriers]):
        root = workspace
    replay = os.environ.get("DELIVERABLE_GATE_GOLDEN_REPLAY") == "1"
    stands_for = {}
    for carrier, name in carriers.items():
        stands_for.setdefault(name, []).append(carrier)
    extra = []
    if root.is_dir():
        # Only files directly under the delivery root count: a subdirectory is not a deliverable (a nested
        # deliverable is named with its path in `required`), and the score records staged beside a Golden
        # (`scores/`) would otherwise read as extras.
        for entry in sorted(os.listdir(root)):
            if not (root / entry).is_file():
                continue
            # A carrier is exempt from the extra charge only during a declared replay, where it is
            # the Golden's own companion file. Outside one it is just a file the answer shipped
            # beside its deliverable, and "do not deliver extra files" applies to it like any other.
            if entry in required or (replay and entry in carriers) \
                    or _allowed(entry, config["allowlist"]):
                continue
            extra.append(entry)
    # A carrier stands in for the required name only during a declared Golden replay, on a clean
    # staging. The gate cannot see whose delivery it is judging, so without the declaration an
    # alternate filename would be accepted from a rollout too - measured: the Golden's rendition
    # name scored exactly what the required name scored. The flag is set by the replay harness;
    # a model working inside the workspace cannot set the validator's environment.
    stand_in = (not extra) and replay
    missing = [name for name in required
               if locate(root, name, config) is None
               and not (stand_in and any((root / c).is_file() for c in stands_for.get(name, [])))]
    verdict = {"root": str(root), "missing": sorted(missing), "extra": sorted(extra)}
    dump = check_source_dump(root, config, tests_dir)
    if dump is not None:
        verdict["source_dump"] = dump
    sections = check_required_sections(root, config)
    if sections is not None:
        verdict["required_sections"] = sections
    length = check_min_length(root, config, tests_dir)
    if length is not None:
        verdict["min_length"] = length
    language = check_language(root, config)
    if language is not None:
        verdict["language"] = language
    foreign = check_foreign_source(root, config, tests_dir)
    if foreign is not None:
        verdict["foreign_source"] = foreign
    invariants = check_json_invariants(root, config)
    if invariants is not None:
        verdict["json_invariants"] = invariants
    forbidden = check_forbidden_text(root, config)
    if forbidden is not None:
        verdict["forbidden_text"] = forbidden
    requirement = check_requirement_gate(root, config, tests_dir)
    if requirement is not None:
        verdict["requirement_gate"] = requirement
    return verdict


def settle(ledger: dict, verdict: dict, config: dict) -> dict:
    """Fold the gate into a pd-ledger-v1 ledger: extras become capped damage instances of the gate item,
    a missing deliverable zeroes retention and the score. Returns the same dict, annotated."""
    coefficient = float(config["extra_coefficient"])
    cap = int(config["extra_cap"])
    item = config["item_id"]
    instances = ledger.setdefault("damage_instances", [])
    charged = verdict["extra"][:cap]
    for name in charged:
        instances.append({"key": f"deliverable:extra:{name}", "item_ids": [item]})
    retention = float(ledger.get("retention", 1.0)) * (coefficient ** len(charged))
    dump = verdict.get("source_dump") or {}
    dumped = []
    if dump.get("charged"):
        rule = config.get("source_dump") or {}
        dumped = dump["charged"][:int(rule.get("cap", 2))]
        for name in dumped:
            instances.append({"key": f"deliverable:source_dump:{name}", "item_ids": [rule.get("item_id", DUMP_ITEM)]})
        retention *= float(rule.get("coefficient", 0.4)) ** len(dumped)
    sections = verdict.get("required_sections") or {}
    absent = []
    if sections.get("charged"):
        rule = config.get("required_sections") or {}
        absent = sections["charged"][:int(rule.get("cap", 3))]
        for label in absent:
            instances.append({"key": "deliverable:required_section:%s" % label,
                              "item_ids": [rule.get("item_id", SECTION_ITEM)]})
        retention *= float(rule.get("coefficient", 0.2)) ** len(absent)
    short = verdict.get("min_length") or {}
    if short.get("charged"):
        rule = config.get("min_length") or {}
        instances.append({"key": "deliverable:min_length:%s" % short["charged"][0],
                          "item_ids": [rule.get("item_id", LENGTH_ITEM)]})
        retention *= float(rule.get("coefficient", 0.2))
    language = verdict.get("language") or {}
    wrong_script = []
    if language.get("charged"):
        rule = config.get("language") or {}
        wrong_script = language["charged"][:int(rule.get("cap", 2))]
        for name in wrong_script:
            instances.append({"key": "deliverable:language:%s" % name,
                              "item_ids": [rule.get("item_id", LANGUAGE_ITEM)]})
        retention *= float(rule.get("coefficient", 0.1)) ** len(wrong_script)
    foreign = verdict.get("foreign_source") or {}
    foreign_charged = []
    if foreign.get("charged"):
        rule = config.get("foreign_source") or {}
        foreign_charged = foreign["charged"][:int(rule.get("cap", 2))]
        for name in foreign_charged:
            instances.append({"key": "deliverable:foreign_source:%s" % name,
                              "item_ids": [rule.get("item_id", FOREIGN_ITEM)]})
        retention *= float(rule.get("coefficient", 0.4)) ** len(foreign_charged)
    invariants = verdict.get("json_invariants") or {}
    broken_rules = []
    if invariants.get("charged"):
        rule = config.get("json_invariants") or {}
        broken_rules = invariants["charged"][:int(rule.get("cap", 2))]
        for name in broken_rules:
            instances.append({"key": "deliverable:json_invariant:%s" % name,
                              "item_ids": [rule.get("item_id", INVARIANT_ITEM)]})
        retention *= float(rule.get("coefficient", 0.4)) ** len(broken_rules)
    forbidden = verdict.get("forbidden_text") or {}
    forbidden_charged = []
    if forbidden.get("charged"):
        rule = config.get("forbidden_text") or {}
        forbidden_charged = forbidden["charged"][:int(rule.get("cap", 2))]
        for name in forbidden_charged:
            instances.append({"key": "deliverable:forbidden_text:%s" % name,
                              "item_ids": [rule.get("item_id", TEXT_ITEM)]})
        retention *= float(rule.get("coefficient", 0.4)) ** len(forbidden_charged)
    requirement = verdict.get("requirement_gate") or {}
    requirement_charged = []
    if requirement.get("charged"):
        rule = config.get("requirement_gate") or {}
        requirement_charged = requirement["charged"][:int(rule.get("cap", 8))]
        for name in requirement_charged:
            instances.append({"key": "deliverable:requirement:%s" % name,
                              "item_ids": [rule.get("item_id", REQUIREMENT_ITEM)]})
        retention *= float(rule.get("coefficient", 0.4)) ** len(requirement_charged)
    if verdict["missing"]:
        retention = 0.0
    ledger["retention"] = round(retention, 9)
    ledger["final_score"] = round(float(ledger.get("positive_earned", 0.0)) * retention, 9)
    ledger["deliverable_gate"] = {"schema_version": SCHEMA, "missing": verdict["missing"], "extra": verdict["extra"],
                                  "charged": charged, "coefficient": coefficient, "cap": cap, "item_id": item}
    if dump:
        ledger["deliverable_gate"]["source_dump"] = {**dump, "charged": dumped}
    if sections:
        ledger["deliverable_gate"]["required_sections"] = {**sections, "charged": absent}
    if short:
        ledger["deliverable_gate"]["min_length"] = short
    if language:
        ledger["deliverable_gate"]["language"] = {**language, "charged": wrong_script}
    if foreign:
        ledger["deliverable_gate"]["foreign_source"] = {
            k: v for k, v in foreign.items() if k != "supplied"} | {"charged": foreign_charged}
    if invariants:
        ledger["deliverable_gate"]["json_invariants"] = {**invariants, "charged": broken_rules}
    if forbidden:
        ledger["deliverable_gate"]["forbidden_text"] = {**forbidden, "charged": forbidden_charged}
    if requirement:
        ledger["deliverable_gate"]["requirement_gate"] = {**requirement, "charged": requirement_charged}
    # A half-length deliverable is not a pass under any reading: the lenient lens fails with the
    # strict score, the same way it does for a missing deliverable.
    if short.get("charged") or absent or language.get("charged"):
        ledger["deliverable_gate"]["lenient_fail"] = True
    return ledger


def apply_to_detail(detail: dict, workspace: Path, tests_dir: Path) -> dict:
    """Host-side entry: apply the package's gate (if it declares one) to a validator/judge detail that carries
    `rewards` and `scoring_ledger`. Lenient is recomputed by the caller if it depends on the ledger."""
    config = load(tests_dir)
    if not config:
        return detail
    ledger = detail.get("scoring_ledger")
    if not isinstance(ledger, dict):
        return detail
    verdict = check(Path(workspace), config, Path(tests_dir))
    settle(ledger, verdict, config)
    rewards = detail.setdefault("rewards", {})
    rewards["strict"] = ledger["final_score"]
    if "final_score" in detail:
        detail["final_score"] = ledger["final_score"]
    if verdict["missing"] or ledger.get("deliverable_gate", {}).get("lenient_fail"):
        rewards["lenient"] = 0.0
    return detail


if __name__ == "__main__":
    import sys
    cfg = load(Path(sys.argv[2])) if len(sys.argv) > 2 else None
    print(json.dumps(check(Path(sys.argv[1]), cfg or {"root": "", "required": [], "allowlist": []},
                           Path(sys.argv[2]) if len(sys.argv) > 2 else None), ensure_ascii=False, indent=2))

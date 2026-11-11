#!/usr/bin/env python3
"""Mix judge - the part a package ships (tests/mix_judge/gate_runtime.py).

    deliverable -> LLM gate --zero--> reward 0
                            \\-pass--> the program judge's reward, unchanged

Run by the package's test.sh after its program judge:
    python3 gate_runtime.py score --installed DIR --deliverable-dir DIR --program-detail FILE --out DIR

The gate's instructions (gate.md), reply schema (gate.schema.json), zero classes (hacks.json),
protocol settings (llm.json) and Golden replay sit beside this file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from judge_transport import call as call_responses

HERE = Path(__file__).resolve().parent


GATE_TEMPLATE = (HERE / "gate.md").read_text(encoding="utf-8")


GATE_SCHEMA = json.loads((HERE / "gate.schema.json").read_text(encoding="utf-8"))


HACKS = json.loads((HERE / "hacks.json").read_text(encoding="utf-8"))


G07_MAX_RATIO = 0.6


ANY_SCOPE = {"G11"}   # an instruction to the grader zeroes however short
RULES = {"structure": "gate then program", "g07_max_ratio": G07_MAX_RATIO, "excerpt": "no compliance zero",
         "any_scope": sorted(ANY_SCOPE)}


TEMPLATE_SHA = hashlib.sha256(
    (GATE_TEMPLATE + json.dumps([GATE_SCHEMA, HACKS, RULES], sort_keys=True)).encode()).hexdigest()[:12]


_LLM_FILE = json.loads((HERE / "llm.json").read_text(encoding="utf-8")) if (HERE / "llm.json").exists() else {}


ENDPOINT = os.environ.get("LLM_JUDGE_BASE_URL", "")


MODEL = os.environ.get("LLM_JUDGE_MODEL") or _LLM_FILE.get("model") or "gpt-5.6-sol"


API_KEY = os.environ.get("LLM_JUDGE_API_KEY", "")


ENABLED = (os.environ.get("LLM_JUDGE_ENABLED") or str(_LLM_FILE.get("enabled", True))).lower() not in ("0", "false", "off", "no")


_KINDS = {id(GATE_SCHEMA): "gate"}


DELIVERABLE_CAP = 60_000          # characters of a deliverable the gate sees


def installed_package(root: Path) -> dict:
    """The same context, read from an installed tests/mix_judge."""
    return {
        "pkg": root, "task": root / "package",
        "declared": json.loads(read(root / "package" / "declared.json") or "[]"),
        "places": json.loads(read(root / "package" / "places.json") or "{}"),
        "instruction": read(root / "package" / "instruction.md").strip() or "(instruction.md not found)",
        "golden_dir": root / "package" / "golden",
        "notes": read(root / "package" / "gate_notes.md").strip(),
        "config": json.loads(read(root / "package" / "gate_config.json") or "{}"),
    }


def gate_prompt(ctx: dict, files: list[Path], text: str) -> str:
    facts = [stats(text, files), integrity(files), tables(files)]
    return fill(GATE_TEMPLATE, {
        "INSTRUCTION": ctx["instruction"],
        "FILES": ", ".join(p.name for p in files) or "(none)",
        "STATS": "; ".join(f for f in facts if f),
        "DELIVERABLE": capped(text, DELIVERABLE_CAP),
        "ZERO_CLASSES": "\n".join(f"- **{c['id']} {c['name']}** - {c['looks_like']}" for c in HACKS["zero_classes"]),
        "NEVER_ZERO": "\n".join(f"- {line}" for line in HACKS["never_zero"]),
    }) + (f"\n\n# Notes for this task\n\n{ctx['notes']}\n" if ctx.get("notes") else "")


def gate(ctx: dict, golden_text: str, folder: Path, cache: Path) -> dict:
    """The gate's verdict on one deliverable: {"zero", "findings", "local_findings",
    "missing_files", "compliance", "llm_keys"}. Raises when the LLM cannot answer."""
    files = deliverable_files(folder, ctx["declared"])
    present = {p.name: p for p in files}
    if folder.is_file() and ctx["declared"] and folder.name not in ctx["declared"] \
            and ctx["declared"][0] not in present:
        # the scorer was handed this one file as the deliverable (a Golden kept under another
        # name, e.g. review.xlsx for structural_review.xlsx): the gate reads what the program scores
        files = [folder] + files
        present[ctx["declared"][0]] = folder
    text = bundle(files)
    missing = [n for n in ctx["declared"] if n not in present or not extract(present[n]).strip()]
    keys_from = len(USED_KEYS)
    findings, local = [], []
    if missing or not text.strip():
        # decided by the program: asked, the LLM named wrong answers "missing"
        findings.append({"class": "G08", "scope": "pervasive", "where": ", ".join(missing) or "(all)",
                         "note": "required deliverable absent or empty (decided by the program)"})
        reply = {}
    else:
        reply = ask(gate_prompt(ctx, files, text), cache, schema=GATE_SCHEMA, max_tokens=3000)
    zero_ids = {c["id"] for c in HACKS["zero_classes"]}
    for f in (reply.get("gate") or {}).get("findings") or []:
        if f.get("class") in zero_ids and (f.get("scope") == "pervasive" or f.get("class") in ANY_SCOPE):
            if f.get("class") == "G07":
                # "the work stopped" stands only on a fact the program can check: asked
                # alone, the gate called complete workbooks "missing rows"
                ratio = words(text) / max(1, words(golden_text))
                broken = [n for n in integrity(files).split("; ") if "does not parse" in n]
                if not (ratio < G07_MAX_RATIO or broken):
                    local.append({**f, "not_corroborated": f"words {ratio:.2f} of golden"})
                    continue
            findings.append(f)
        else:
            local.append(f)
    excerpted = len(text) > DELIVERABLE_CAP
    # a package can switch the task-text questions off (gate_config.json "compliance": false):
    # where its requirements are PDF layout the gate cannot see, the program judge checks them
    compliance_on = (ctx.get("config") or {}).get("compliance", True) is not False
    for key, cls in (("required_present", "C-REQ"), ("prohibited_absent", "C-PRO")):
        ans = (reply.get("compliance") or {}).get(key) or {}
        if str(ans.get("answer", "")).lower() != "no":
            continue
        entry = {"class": cls, "scope": "pervasive", "where": "task text",
                 "note": "; ".join(f"{v.get('quote', '')} -> {v.get('note', '')}"
                                   for v in ans.get("violations") or [])[:600] or key}
        if not compliance_on:
            local.append({**entry, "not_corroborated": "compliance switched off for this package"})
            continue
        if excerpted:
            # the gate saw an excerpt: it called a 91 KB LaTeX source with its
            # \end{document} "truncated", and read the grader's own excerpt marker as
            # forbidden content
            local.append({**entry, "not_corroborated": "deliverable shown as an excerpt"})
            continue
        findings.append(entry)
    return {"zero": bool(findings), "findings": findings, "local_findings": local,
            "semantic": reply.get("semantic") or {}, "missing_files": missing,
            "compliance": reply.get("compliance"), "files": [p.name for p in files],
            "llm_keys": sorted(set(USED_KEYS[keys_from:]))}


def mixed(detail: dict, verdict: dict) -> dict:
    """Settle required open-semantic owners, or zero when the gate rejects."""
    rewards = dict(detail.get("rewards") or {})
    if verdict["zero"]:
        rewards = {k: 0.0 for k in rewards} or {"strict": 0.0, "lenient": 0.0}
    else:
        ledger = detail.get("scoring_ledger") or {}
        completion = dict(ledger.get("positive_completion") or {})
        semantic = verdict.get("semantic") or {}
        psu = semantic.get("psu_scenario") or {}
        pool = semantic.get("pool_multiplier") or {}
        completion["R15"] = (
            float(psu.get("stance") == "defensible" and psu.get("locator_supported") is True)
            + float(pool.get("stance") == "defensible" and pool.get("locator_supported") is True)
        ) / 2.0
        damages = [row for row in ledger.get("damage_instances", [])
                   if not set(row.get("item_ids", [])) & {"D02", "D03", "D04", "D05"}]
        semantic_damage = {
            "psu_scenario": ("D02", "PSU maximum treated as additional to target rather than an alternative"),
            "residual_population": ("D03", "named-officer exercises asserted to be the whole population"),
            "pool_multiplier": ("D04", "plan share-counting multiplier described as an EPS dilution factor"),
            "withholding": ("D05", "withheld shares re-entered as a new issuance"),
        }
        for owner, (item, label) in semantic_damage.items():
            if (semantic.get(owner) or {}).get("stance") == "inverted":
                damages.append({"key": f"semantic:{owner}:{label}", "item_ids": [item]})
        params = json.loads((HERE.parent / "scoring_params.json").read_text())
        earned = sum(params["positive_weights"][key] * completion.get(key, 0.0)
                     for key in params["positive_weights"])
        coefficients = params["deduction_coefficients"]
        retention = max(0.25, math.prod(min(coefficients[item] for item in row["item_ids"])
                                        for row in damages)) if damages else 1.0
        strict = round(earned * retention, 6)
        rewards["strict"] = strict
        ledger.update(positive_completion=completion, damage_instances=damages,
                      positive_earned=earned, retention=retention, final_score=strict,
                      semantic_authority=["R15", "D02", "D03", "D04", "D05"])
        if "group_points" in detail:
            detail = {**detail, "program_group_points": detail["group_points"]}
            detail.pop("group_points", None)
        detail = {**detail, "scoring_ledger": ledger}
    return {**detail, "rewards": rewards, "gate": {k: v for k, v in verdict.items() if k != "llm_keys"},
            "llm_keys": verdict.get("llm_keys", []), "template_sha": TEMPLATE_SHA, "model": MODEL}


def score(args) -> int:
    """Required source-bound semantic gate; failures are UNMEASURED."""
    out = Path(args.out)
    detail = json.loads(read(Path(args.program_detail)) or "{}")
    try:
        if not ENABLED:
            raise LookupError("switched off in llm.json / LLM_JUDGE_ENABLED")
        ctx = installed_package(Path(args.installed))
        shipped = Path(args.installed) / "golden_replay"
        if shipped.is_dir():
            os.environ["LLM_JUDGE_SHIPPED_CACHE"] = ":".join(
                filter(None, [str(shipped), os.environ.get("LLM_JUDGE_SHIPPED_CACHE", "")]))
        golden_text = bundle(deliverable_files(ctx["golden_dir"], ctx["declared"]))
        verdict = gate(ctx, golden_text, Path(args.deliverable_dir),
                       Path(os.environ.get("LLM_JUDGE_CACHE_DIR", "/logs/judge-cache")) / "cache")
        result = {**mixed(detail, verdict), "mix_status": "ok"}
    except Exception as error:
        out.mkdir(parents=True, exist_ok=True)
        for name in ("reward.json", "reward.txt", "reward_strict.txt", "reward_lenient.txt"):
            (out / name).unlink(missing_ok=True)
        status={"status":"unmeasured","measurement_complete":False,
                "error_type":type(error).__name__,"error":str(error)[:300],
                "business_zero_inferred":False}
        (out / "verifier_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
        print(json.dumps(status))
        return 2
    rewards = result.get("rewards") or {}
    strict, lenient = float(rewards.get("strict") or 0.0), float(rewards.get("lenient") or 0.0)
    out.mkdir(parents=True, exist_ok=True)
    (out / "reward_detail.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    for name, value in (("reward.txt", strict), ("reward_strict.txt", strict), ("reward_lenient.txt", lenient)):
        (out / name).write_text(f"{value:.6f}\n")
    compact = {"reward": strict, "reward_strict": strict, "reward_lenient": lenient}
    (out / "reward.json").write_text(json.dumps(compact, indent=2))
    print(json.dumps({"strict": strict, "mix_status": result.get("mix_status")}))
    return 0


TEXT_CACHE = Path(os.environ.get("LLM_JUDGE_TEXT_CACHE_DIR", "/tmp/llm_judge_text"))


PARSED = (".xlsx", ".xlsm", ".docx", ".pdf")  # formats worth parsing once and keeping


EXTRACT_VERSION = "9"  # bump when extraction changes what a file reads as


SHEET_ROWS = 2000  # rows read per sheet; a 60 MB workbook read whole took minutes a pass


TIMINGS: list = []


USED_KEYS: list = []  # every reply read or written: what a shipped cache must keep


_TIMING_LOCK = threading.Lock()


_EXTRACTED: dict = {}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


SKIP_DIRS = {"scores", "verifier", "__pycache__"}  # results and copies, never the deliverable


def deliverable_files(folder: Path, declared: list[str]) -> list[Path]:
    """The deliverables under a root, however the caller laid it out: a rollout root,
    its artifacts/, a workspace, a golden folder, or one file. One file per name - the
    shallowest; copies under verifier/ or scores/ are never it."""
    if folder.is_file():
        folder = folder.parent
    if not folder.exists():
        return []
    files = [p for p in folder.rglob("*") if p.is_file() and not SKIP_DIRS & set(p.relative_to(folder).parts)
             and not p.name.startswith(".") and p.name not in ("metadata.json", "manifest.json")]
    if declared:
        files = [p for p in files if p.name in declared]
    chosen = {}
    for p in sorted(files, key=lambda p: (len(p.relative_to(folder).parts), str(p))):
        chosen.setdefault(p.name, p)
    return sorted(chosen.values())


def extract(path: Path) -> str:
    # large workbooks are read once per process (a 32 MB xlsx took minutes a pass),
    # and once per content across processes (golden check, batch and selftest each
    # reparsed the same files)
    key = (str(path), path.stat().st_mtime_ns) if path.exists() else (str(path), 0)
    if key not in _EXTRACTED:
        _EXTRACTED[key] = disk_cached(path, "text", lambda: _extract(path))
    return _EXTRACTED[key]


def disk_cached(path: Path, kind: str, build):
    """Only workbooks: small files are faster to reread than to hash."""
    if path.suffix.lower() not in PARSED or not path.exists():
        return build()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:32]
    hit = TEXT_CACHE / f"{digest}.{kind}.v{EXTRACT_VERSION}.json"
    try:
        value = json.loads(hit.read_text(encoding="utf-8"))
        timed("parse", 0.0, True)
        return value
    except (OSError, ValueError):
        pass
    started = time.monotonic()
    value = build()
    timed("parse", time.monotonic() - started, False, file=path.name, mb=round(path.stat().st_size / 1e6, 1))
    try:
        TEXT_CACHE.mkdir(parents=True, exist_ok=True)
        tmp = hit.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        tmp.replace(hit)
    except OSError:
        pass
    return value


def _extract(path: Path) -> str:
    suffix = path.suffix.lower()
    try:
        if suffix == ".docx":
            return docx_text(path)
        if suffix in (".xlsx", ".xlsm"):
            out = []
            for title, rows, total in sheet_rows(path):
                out.append(f"## [sheet] {title}")
                lines = [" | ".join("" if v is None else str(v) for v in row) for row in rows]
                out += lines
                if total > len(rows):
                    # the words the cut rows would carry, so a "work stopped" check still sees them
                    est = int(words("\n".join(lines)) * (total - len(rows)) / max(1, len(rows)))
                    out.append(f"[GRADER EXCERPT: sheet '{title}' has {total} rows; the first {len(rows)} "
                               f"are shown, ~{est} words omitted - not a sign the sheet was cut]")
            return "\n".join(out)
        if suffix == ".dxf":
            return dxf_text(path)
        if suffix == ".pptx":
            # a deck read as empty was "required deliverable absent or empty" (G08) for golden and
            # every rollout of construction-quantity-crosscheck
            return pptx_text(path)
        if suffix == ".pdf":
            text = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                                  capture_output=True, text=True, timeout=120).stdout
            raw = path.read_bytes()
            if text.strip() or raw.startswith(b"%PDF") or b"\x00" in raw[:4096]:
                return text
            # text saved under a .pdf name: the program judge reads it, so the gate does too
        raw = path.read_bytes()
        return "" if b"\x00" in raw[:4096] else raw.decode("utf-8", errors="replace")
    except Exception as error:
        return f"[unreadable {path.name}: {type(error).__name__}]"


def pptx_text(path: Path) -> str:
    """A deck's text, slide by slide in presentation order, straight from the slide XML."""
    import zipfile
    from xml.etree import ElementTree as ET
    a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    with zipfile.ZipFile(path) as z:
        slides = sorted((n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                        key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))
        out = []
        for i, name in enumerate(slides, 1):
            paras = ["".join(t.text or "" for t in para.iter(f"{a}t"))
                     for para in ET.fromstring(z.read(name)).iter(f"{a}p")]
            out.append(f"## [slide {i}]")
            out += [p for p in paras if p.strip()]
    return "\n".join(out)


def dxf_text(path: Path) -> str:
    """A DXF drawing as the gate can read it: entity counts per type and layer, then the drawing's own
    text (TEXT / MTEXT values). Raw group codes and handles are left out: they would read as filler."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    pairs = [(lines[i].strip(), lines[i + 1].rstrip("\r")) for i in range(0, len(lines) - 1, 2)]
    section, kinds, layers, texts, kind = None, {}, {}, [], None
    for i, (code, value) in enumerate(pairs):
        if code == "0" and value == "SECTION" and i + 1 < len(pairs):
            section = pairs[i + 1][1].strip()
        if section != "ENTITIES":
            continue
        if code == "0":
            kind = value.strip()
            if kind not in ("SECTION", "ENDSEC"):
                kinds[kind] = kinds.get(kind, 0) + 1
        elif code == "8":
            layers[value.strip()] = layers.get(value.strip(), 0) + 1
        elif code in ("1", "3") and kind in ("TEXT", "MTEXT", "ATTRIB"):
            texts.append(re.sub(r"\\[A-Za-z][^;]*;|[{}]", "", value).replace("\\P", " ").strip())
    out = [f"[DXF drawing: {sum(kinds.values())} entities - " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())) + "]",
           "[layers: " + ", ".join(f"{k} ({v})" for k, v in sorted(layers.items())) + "]", "[text in the drawing:]"]
    return "\n".join(out + [t for t in texts if t])


def docx_text(path: Path) -> str:
    """Reading order, headings marked `## `, table rows as `a | b | c`."""
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    document = docx.Document(str(path))
    lines, n = [], 0
    for child in document.element.body.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            para = Paragraph(child, document)
            text = para.text.strip()
            if text:
                style = para.style.name if para.style is not None else ""
                if style.startswith(("Heading", "Title")):
                    level = int(re.search(r"\d", style).group()) if re.search(r"\d", style) else 1
                    lines.append("#" * (level + 1) + f" {text}")
                else:
                    lines.append(text)
        elif tag == "tbl":
            n += 1
            lines.append(f"## [table {n}]")
            for row in Table(child, document).rows:
                # a merged cell comes back once per column it spans; read it once, so a report
                # laid out in full-width merged cells does not read as one cell copied across
                cells, seen = [], set()
                for c in row.cells:
                    if id(c._tc) not in seen:
                        seen.add(id(c._tc))
                        cells.append(cell_text(c))
                lines.append(" | ".join(cells))
    return "\n".join(lines)


def cell_text(cell) -> str:
    """A table cell's paragraphs and nested tables, in order. `cell.text` skips nested
    tables: a report that kept its figures in tables inside its section cells read
    as headings with nothing under them (membership-weekly-report, 0.55 of golden)."""
    from docx.table import Table, _Cell
    from docx.text.paragraph import Paragraph
    parts = []
    for child in cell._tc.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            text = Paragraph(child, cell).text.strip()
            if text:
                parts.append(text)
        elif tag == "tbl":
            rows = []
            for row in Table(child, cell).rows:
                inner, seen = [], set()
                for c in row.cells:
                    if id(c._tc) not in seen:
                        seen.add(id(c._tc))
                        inner.append(cell_text(c))
                rows.append(" | ".join(inner))
            parts.append("[" + " ; ".join(rows) + "]")
    return " ".join(parts).replace("\n", " ")


def bundle(files: list[Path]) -> str:
    if len(files) == 1:
        return extract(files[0])
    return "\n\n".join(f"===== FILE {p.name} =====\n{extract(p)}" for p in files)


def stats(text: str, files: list[Path] = ()) -> str:
    lines = text.splitlines()
    count = f"{len(re.findall(r'[A-Za-z0-9]+|[一-鿿]', text))} words"
    if files and all(p.suffix.lower() == ".pdf" for p in files):
        # pdftotext lays tables out as text columns, so a table row count would read 0
        # for a laid-out PDF form; the count is left out for PDFs
        return count + ", tables not measurable in PDF text"
    return (f"{count}, "
            f"{sum(bool(re.match(r'#{2,7} ', l)) for l in lines)} headings/tables, {sum(' | ' in l for l in lines)} table rows")


def capped(text: str, cap: int) -> str:
    if len(text) <= cap:
        return text
    head = int(cap * 0.75)
    return (f"{text[:head]}\n\n[GRADER EXCERPT: {len(text) - cap} characters omitted here by the grader to fit "
            f"this prompt - not part of the file, not a sign it was cut]\n\n{text[-(cap - head):]}")


def integrity(files: list[Path]) -> str:
    key = ("integrity",) + tuple((str(p), p.stat().st_mtime_ns) for p in files)
    if key not in _EXTRACTED:
        _EXTRACTED[key] = _integrity(files)
    return _EXTRACTED[key]


def _integrity(files: list[Path]) -> str:
    """Whether each structured file parses whole - a fact the gate cannot see in an excerpt."""
    notes = []
    for p in files:
        suffix = p.suffix.lower()
        try:
            if suffix == ".json":
                json.loads(p.read_text(encoding="utf-8"))
            elif suffix in (".xlsx", ".xlsm"):
                import openpyxl
                try:
                    openpyxl.load_workbook(p, read_only=True)
                except Exception:
                    sheet_rows_xml(p)   # valid if its XML reads, whatever openpyxl makes of it
            else:
                continue
            notes.append(f"{p.name}: {p.stat().st_size} bytes, parses completely")
        except Exception as error:
            notes.append(f"{p.name}: {p.stat().st_size} bytes, does not parse ({type(error).__name__})")
    return "; ".join(notes)


def words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+|[一-鿿]", text))


def tables(files: list[Path]) -> str:
    key = ("tables",) + tuple((str(p), p.stat().st_mtime_ns) for p in files)
    if key not in _EXTRACTED:
        _EXTRACTED[key] = "; ".join(filter(None, (disk_cached(p, "tables", lambda p=p: _tables([p])) for p in files)))
    return _EXTRACTED[key]


def sheet_rows(path: Path) -> list:
    """(title, non-empty rows read, total rows) per sheet. Sheets up to SHEET_ROWS are
    read whole; a longer one gives its head and its size from the sheet's dimension."""
    key = ("sheets", str(path), path.stat().st_mtime_ns)
    if key not in _EXTRACTED:
        import openpyxl
        try:
            book = openpyxl.load_workbook(path, data_only=True, read_only=True)
        except Exception:
            # a valid workbook openpyxl cannot load (a style attribute it does not know)
            _EXTRACTED[key] = sheet_rows_xml(path)
            return _EXTRACTED[key]
        # a workbook saved without computed values (openpyxl writes none) reads blank
        # wherever a formula stands; the formula is shown instead
        try:
            sheets = _sheet_rows_openpyxl(book, openpyxl.load_workbook(path, read_only=True))
        except Exception:
            # read_only parses lazily: a cell typed numeric that holds text ('Base' with t="n",
            # which Excel and the program judge read fine) fails here, not at load
            sheets = sheet_rows_xml(path)
        _EXTRACTED[key] = sheets
    return _EXTRACTED[key]


def _sheet_rows_openpyxl(book, formulas) -> list:
    sheets = []
    for sheet, raw in zip(book.worksheets, formulas.worksheets):
        rows, seen = [], 0
        for row, row_raw in zip(sheet.iter_rows(values_only=True), raw.iter_rows(values_only=True)):
            seen += 1
            row = tuple(r if v is None and isinstance(r, str) and r.startswith("=") else v
                        for v, r in zip(row, tuple(row_raw) + (None,) * (len(row) - len(row_raw))))
            if any(v is not None for v in row):
                rows.append(row)
            if seen >= SHEET_ROWS:
                break
        total = len(rows)
        if seen >= SHEET_ROWS:
            total = max(len(rows), (sheet.max_row or 0))
        sheets.append((sheet.title, rows, total))
    return sheets


def sheet_rows_xml(path: Path) -> list:
    """sheet_rows read straight from the workbook's XML: cached values, else the formula."""
    import zipfile
    from xml.etree import ElementTree as ET
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rel = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        shared = []
        if "xl/sharedStrings.xml" in names:
            shared = ["".join(t.text or "" for t in si.iter(f"{{{ns['x']}}}t"))
                      for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("x:si", ns)]
        targets = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
        sheets = []
        for sheet in ET.fromstring(z.read("xl/workbook.xml")).find("x:sheets", ns):
            target = targets.get(sheet.get(rel), "").lstrip("/")
            member = target if target.startswith("xl/") else f"xl/{target}"
            if member not in names:
                continue
            rows, total = [], 0
            for row in ET.fromstring(z.read(member)).iter(f"{{{ns['x']}}}row"):
                values = []
                for c in row.findall("x:c", ns):
                    v, f, kind = c.find("x:v", ns), c.find("x:f", ns), c.get("t")
                    if kind == "s" and v is not None:
                        values.append(shared[int(v.text)])
                    elif kind == "inlineStr":
                        values.append("".join(t.text or "" for t in c.iter(f"{{{ns['x']}}}t")))
                    elif v is not None and v.text is not None:
                        values.append(v.text)
                    elif f is not None and f.text:
                        values.append("=" + f.text)
                if values:
                    total += 1
                    if len(rows) < SHEET_ROWS:
                        rows.append(tuple(values))
            sheets.append((sheet.get("name"), rows, total))
    return sheets


def _tables(files: list[Path]) -> str:
    """Row count and first-column keys of every sheet / CSV: the gate once reported
    rows missing from a workbook that had all of them."""
    notes = []
    for p in files:
        suffix = p.suffix.lower()
        try:
            if suffix in (".xlsx", ".xlsm"):
                sheets = sheet_rows(p)
            elif suffix == ".csv":
                import csv
                rows = [r for r in csv.reader(p.read_text(encoding="utf-8", errors="replace").splitlines()) if r]
                sheets = [(p.name, rows, len(rows))]
            elif suffix == ".docx":
                # the shape of each top-level table, measured by the program so the gate
                # does not have to count rows and columns itself
                import docx
                shapes = [f"table {i}: {len(tb.rows)} rows x {len(tb.columns)} columns"
                          for i, tb in enumerate(docx.Document(str(p)).tables, 1)]
                if shapes:
                    notes.append(f"{p.name}: " + "; ".join(shapes[:20]))
                continue
            else:
                continue
        except Exception:
            continue
        for title, rows, total in sheets:
            keys = list(dict.fromkeys(str(r[0])[:40] for r in rows[1:] if r and r[0] is not None))
            shown = ", ".join(keys[:40])[:1200] + (f", … ({len(keys)} distinct)" if len(keys) > 40 else "")
            where = "" if total == len(rows) else f" (first column of the first {len(rows)} rows)"
            # distinct keys and size: a 410-row sheet of one repeated sentence read as "410 data rows"
            # and its bulk hid behind the excerpt (padding on construction-quantity-crosscheck)
            chars = sum(len(" | ".join("" if v is None else str(v) for v in r)) for r in rows)
            notes.append(f"sheet '{title}': {max(0, total - 1)} data rows, {len(keys)} distinct first-column "
                         f"values, ~{chars} characters; first column{where}: {shown}")
    return "; ".join(notes)


def timed(kind: str, seconds: float, cached: bool, **extra) -> None:
    with _TIMING_LOCK:
        TIMINGS.append({"kind": kind, "seconds": round(seconds, 3), "cached": cached, **extra})


def ask(prompt: str, cache_dir: Path, schema: dict | None = None, timeout: int = 180, retries: int = 2,
        think: bool = False, max_tokens: int = 800) -> dict:
    """One call, cached by the prompt's sha: the same deliverable under the same
    template always gets the same answer, which is what lets a fitted parameter
    set replay exactly."""
    key = hashlib.sha256(f"{MODEL}\n{'think' if think else ''}\n{json.dumps(schema, sort_keys=True)}\n{prompt}".encode()).hexdigest()
    hit = cache_dir / f"{key}.json"
    kind = _KINDS.get(id(schema), "llm")
    with _TIMING_LOCK:
        USED_KEYS.append(key)
    if hit.exists():
        timed(kind, 0.0, True)
        return json.loads(hit.read_text(encoding="utf-8"))
    # The exact response that produced the Golden score ships as request-bound replay.
    for shipped in filter(None, os.environ.get("LLM_JUDGE_SHIPPED_CACHE", "").split(":")):
        candidate = Path(shipped) / f"{key}.json"
        if candidate.exists():
            timed(kind, 0.0, True)
            return json.loads(candidate.read_text(encoding="utf-8"))
    if os.environ.get("LLM_JUDGE_MODE", "fresh").lower() == "replay":
        raise RuntimeError("No exact request-bound semantic replay is available")
    error, started = None, time.monotonic()
    for attempt in range(retries + 1):
        try:  # a transport error, a 5xx from an overloaded proxy or a truncated JSON reply retry
            reply = parse_json(complete(prompt, schema, max_tokens, think, timeout))
            if schema is GATE_SCHEMA:
                validate_gate_reply(reply)
            break
        except Exception as exc:
            error = exc
            if attempt < retries:
                time.sleep(5 * 2 ** attempt)  # back off: an immediate retry hits the same overload
    else:
        timed(kind, time.monotonic() - started, False, failed=True, prompt_chars=len(prompt))
        raise RuntimeError(f"{type(error).__name__}: {error}")
    timed(kind, time.monotonic() - started, False, prompt_chars=len(prompt))
    cache_dir.mkdir(parents=True, exist_ok=True)
    hit.write_text(json.dumps(reply, ensure_ascii=False), encoding="utf-8")
    return reply


def validate_gate_reply(reply: dict) -> None:
    if not isinstance(reply, dict) or set(reply) != {"gate", "semantic", "compliance"}:
        raise ValueError("Gate reply fields do not match the required schema")
    gate = reply["gate"]
    if not isinstance(gate, dict) or set(gate) != {"verdict", "findings"} or gate["verdict"] not in {"pass", "zero"}:
        raise ValueError("Invalid gate verdict")
    if not isinstance(gate["findings"], list) or len(gate["findings"]) > 6:
        raise ValueError("Invalid gate findings")
    zero_ids = {row["id"] for row in HACKS["zero_classes"]}
    for row in gate["findings"]:
        if (not isinstance(row, dict) or set(row) != {"class", "scope", "where", "note"}
                or row["class"] not in zero_ids or row["scope"] not in {"local", "pervasive"}
                or not all(isinstance(row[key], str) for key in ("where", "note"))):
            raise ValueError("Invalid gate finding")
    compliance = reply["compliance"]
    if not isinstance(compliance, dict) or set(compliance) != {"required_present", "prohibited_absent"}:
        raise ValueError("Invalid compliance reply")
    for value in compliance.values():
        if not isinstance(value, dict) or set(value) != {"answer", "violations"} or value["answer"] not in {"yes", "no"}:
            raise ValueError("Invalid compliance decision")
        if not isinstance(value["violations"], list) or len(value["violations"]) > 6:
            raise ValueError("Invalid compliance violations")
        if any(not isinstance(row, dict) or set(row) != {"quote", "note"}
               or not all(isinstance(row[key], str) for key in ("quote", "note")) for row in value["violations"]):
            raise ValueError("Invalid compliance violation")
    semantic = reply["semantic"]
    owners = {"psu_scenario", "residual_population", "pool_multiplier", "withholding"}
    if not isinstance(semantic, dict) or set(semantic) != owners:
        raise ValueError("Invalid semantic owner set")
    for value in semantic.values():
        if (not isinstance(value, dict)
                or set(value) != {"stance", "locator_supported", "quote", "rationale"}
                or value["stance"] not in {"defensible", "inverted", "silent_or_ambiguous"}
                or not isinstance(value["locator_supported"], bool)
                or not isinstance(value["quote"], str)
                or not isinstance(value["rationale"], str)):
            raise ValueError("Invalid semantic owner decision")


def complete(prompt: str, schema: dict | None, max_tokens: int, think: bool, timeout: int) -> str:
    """Call the sole supported verifier protocol: OpenAI Responses."""
    body={"model":MODEL,"store":False,"max_output_tokens":max_tokens,
          "input":[{"role":"user","content":[{"type":"input_text","text":prompt}]}],
          "text":{"format":{"type":"json_schema","name":"equity_gate","strict":True,
                              "schema":schema}} if schema is not None else {"format":{"type":"json_object"}}}
    timeout = int(os.environ.get("LLM_JUDGE_TIMEOUT_SECONDS", timeout))
    attempts = int(os.environ.get("LLM_JUDGE_TRANSPORT_ATTEMPTS", "3"))
    _,text=call_responses(body,ENDPOINT,API_KEY,timeout,attempts)
    return text


def parse_json(text: str) -> dict:
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    text = (fence.group(1) if fence else text).strip()
    start, depth, in_str, esc = text.find("{"), 0, False, False
    for i in range(max(start, 0), len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("no complete JSON object in the reply")


def fill(template: str, values: dict) -> str:
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    return template



def main() -> int:
    ap = argparse.ArgumentParser(description="the mix judge's LLM gate, inside a package's verifier")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score", help="gate one deliverable after the program judge")
    s.add_argument("--installed", required=True)
    s.add_argument("--deliverable-dir", required=True)
    s.add_argument("--program-detail", required=True)
    s.add_argument("--out", required=True)
    args = ap.parse_args()
    return score(args)


if __name__ == "__main__":
    raise SystemExit(main())

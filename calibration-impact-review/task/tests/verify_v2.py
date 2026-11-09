"""Measure source-backed atomic owners for the calibration review CLI."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import csv
from importlib import metadata
import json
import math
import os
from pathlib import Path
import random
import re
import signal
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace

from packaging.requirements import Requirement

from independent_reference import reconstruct


OWNER_IDS = [
    "N_SUMMARY_SCOPE",
    "N_BASELINE_RECONSTRUCTION",
    "N_OPTICAL_LIMITS",
    "N_RECORD_DECISIONS",
    "N_TREND_ANALYSIS",
    "N_REORDER_PATHS",
    "N_CHANGED_RECORDS",
    "N_CHANGED_SETTINGS",
    "N_SMALL_TAIL",
    "N_INVALID_INPUTS",
    "N_LOWER_TAIL",
    "N_USAGE_REPRODUCTION",
]

SCORED_OWNER_IDS = [owner for owner in OWNER_IDS if owner not in {"N_LOWER_TAIL", "N_USAGE_REPRODUCTION"}]


def strict_json(path):
    def bad(value):
        raise ValueError("Nonfinite JSON constant " + value)
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), parse_constant=bad)


def source_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or []), list(reader)


def save_rows(path, headers, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def compare_fields(actual, expected, path="root", failures=None):
    failures = [] if failures is None else failures

    def identity(value):
        # CSV/JSON producers may serialize the same control day as 1 or 1.0.
        # This is an identifier comparison, not a measurement tolerance check.
        if isinstance(value, bool):
            return str(value)
        try:
            number = float(str(value).strip())
            if math.isfinite(number) and number.is_integer():
                return str(int(number))
        except (TypeError, ValueError):
            pass
        return str(value)

    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            failures.append({"path": path, "kind": "object_required"})
            return failures
        for key, value in expected.items():
            child = path + "." + key
            if key not in actual:
                failures.append({"path": child, "kind": "missing"})
            else:
                compare_fields(actual[key], value, child, failures)
    elif isinstance(expected, list):
        if not isinstance(actual, list):
            failures.append({"path": path, "kind": "list_required"})
            return failures
        key = "record_id" if expected and "record_id" in expected[0] else "control_day"

        index = {identity(row[key]): row for row in actual if isinstance(row, dict) and key in row}
        expected_ids = {identity(row[key]) for row in expected}
        if len(index) != len(actual) or set(index) != expected_ids:
            failures.append({"path": path, "kind": "record_membership"})
        for row in expected:
            row_id = identity(row[key])
            if row_id in index:
                compare_fields(index[row_id], row, path + "[" + row_id + "]", failures)
    else:
        if path.endswith((".record_id", ".control_day")) and identity(actual) == identity(expected):
            passed = True
        elif type(expected) is bool:
            passed = type(actual) is bool and actual == expected
        elif isinstance(expected, (int, float)):
            passed = type(actual) in (int, float) and math.isfinite(actual) and abs(actual - expected) <= 1e-8
        else:
            passed = actual == expected
        if not passed:
            failures.append({"path": path, "kind": "value", "expected": expected, "actual": actual})
    return failures


def inspect_csv(path, expected_rows):
    required = ["system", "record_id", "scope", "control_day", "measurement", "observed", "unit", "lower_limit", "upper_limit", "action"]
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)
            headers = reader.fieldnames or []
        if any(headers.count(key) != 1 for key in required):
            return [{"path": "exceptions.headers." + key, "kind": "missing_or_duplicate"}
                    for key in required if headers.count(key) != 1]
        key = lambda row: (row["system"], row["record_id"], row["measurement"])
        actual = {key(row): row for row in rows}
        expected = {key(row): row for row in expected_rows}
        def membership(identity, kind):
            return {"path": "exceptions.rows", "kind": kind, "system": identity[0],
                    "record_id": identity[1], "measurement": identity[2]}
        if len(actual) != len(rows) or set(actual) != set(expected):
            return ([membership(value, "missing_row") for value in set(expected) - set(actual)]
                    + [membership(value, "extra_row") for value in set(actual) - set(expected)]
                    + [membership(value, "duplicate_row") for value, count in Counter(key(row) for row in rows).items() if count > 1])
        failures = []
        for identity, expected_row in expected.items():
            actual_row = actual[identity]
            for field, value in expected_row.items():
                try:
                    passed = (math.isfinite(float(actual_row[field])) and abs(float(actual_row[field]) - value) <= 1e-8
                              if isinstance(value, (int, float)) else actual_row[field].strip() == str(value))
                except (KeyError, TypeError, ValueError, AttributeError):
                    passed = False
                if not passed:
                    failures.append({"path": "exceptions." + field, "kind": "value",
                                     "record_id": identity[1], "system": identity[0], "measurement": identity[2]})
        return failures
    except PermissionError:
        raise
    except (OSError, UnicodeError, ValueError, TypeError) as error:
        return [{"path": "exceptions", "kind": type(error).__name__}]


def inspect_output(output, mass, optical, config, frozen=None):
    expected, expected_csv = reconstruct(mass, optical, config) if frozen is None else frozen
    try:
        if any((output / name).is_symlink() for name in ("review-results.json", "exceptions.csv")):
            return {"failures": [{"path": "root", "kind": "output_symlink"}], "csv_failures": [{"path": "exceptions", "kind": "output_symlink"}]}
        actual = strict_json(output / "review-results.json")
        failures = compare_fields(actual, expected)
    except PermissionError:
        raise
    except (OSError, UnicodeError, ValueError, TypeError) as error:
        failures = [{"path": "root", "kind": type(error).__name__}]
    csv_failures = inspect_csv(output / "exceptions.csv", expected_csv)
    return {"failures": failures, "csv_failures": csv_failures}


def candidate_run(command, workspace, environment, logs):
    if os.geteuid() != 0:
        raise RuntimeError("Candidate execution requires the declared root private verifier")
    for path in [workspace, *workspace.rglob("*")]:
        if path.is_symlink():
            raise ValueError("Candidate execution files must not be symlinks")
        os.chown(path, 65534, 65534)
    read_fd, ready_fd = os.pipe()
    helper = Path(__file__).with_name("candidate_runner.py")
    timed_out = False
    with (logs / "stdout.txt").open("wb") as stdout, (logs / "stderr.txt").open("wb") as stderr:
        process = subprocess.Popen([sys.executable, "-B", str(helper), str(ready_fd), *command],
            cwd=workspace, env=environment, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
            pass_fds=(ready_fd,), start_new_session=True)
        os.close(ready_fd)
        try:
            process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
    ready = os.read(read_fd, 4096)
    os.close(read_fd)
    if not ready or json.loads(ready).get("uid") != 65534 or json.loads(ready).get("network_filter_loaded") is not True:
        raise RuntimeError("Candidate isolation bootstrap did not complete; see stderr.txt")
    if timed_out:
        raise subprocess.TimeoutExpired(command, 60)
    return SimpleNamespace(returncode=process.returncode, isolation=json.loads(ready))


def execute(code, clean_env, folder, mass, optical, config, edit=None, invalid=False):
    folder.mkdir()
    private = Path(tempfile.mkdtemp(prefix="calibration-case-"))
    local_code = private / "candidate-tool"
    shutil.copytree(code, local_code)
    public = private / "inputs with spaces"
    public.mkdir()
    mp, op, cp = public / "mass archive.csv", public / "optical archive.csv", public / "settings.json"
    shutil.copy2(mass, mp)
    shutil.copy2(optical, op)
    shutil.copy2(config, cp)
    original_ids = [row["record_id"] for path in (mp, op) for row in source_rows(path)[1]]
    if edit:
        edit(mp, op, cp)
    current_ids = [row["record_id"] for path in (mp, op) for row in source_rows(path)[1]]
    identity_map = (dict(zip(current_ids, original_ids))
                    if len(current_ids) == len(original_ids) and set(current_ids).isdisjoint(original_ids) else {})
    frozen = None if invalid else reconstruct(mp, op, cp)
    output = private / "generated outputs"
    command = [sys.executable, "-B", "-X", "utf8", str(local_code / "measurement_check.py"),
               "--mass", str(mp), "--optical", str(op), "--config", str(cp), "--output", str(output)]
    try:
        completed = candidate_run(command, private, clean_env, folder)
    except subprocess.TimeoutExpired:
        return {"passed": False, "error": "timeout"}
    if invalid:
        created = output.is_dir() and any((output / name).exists() for name in ("review-results.json", "exceptions.csv"))
        return {"passed": completed.returncode != 0 and bool((folder / "stderr.txt").read_text(errors="replace").strip()) and not created,
                "returncode": completed.returncode, "isolation": completed.isolation}
    if completed.returncode != 0:
        return {"passed": False, "error": "valid input rejected", "returncode": completed.returncode,
                "failures": [{"path": "root", "kind": "execution"}], "csv_failures": [{"path": "exceptions", "kind": "execution"}]}
    inspected = inspect_output(output, mp, op, cp, frozen)
    return {"passed": not inspected["failures"] and not inspected["csv_failures"],
            "output_path": str(output),
            "record_id_map": identity_map, "isolation": completed.isolation, **inspected}


def failure_signature(failure, identity_map=None):
    identity_map = identity_map or {}
    path = failure["path"]
    for changed, original in identity_map.items():
        path = path.replace("[" + changed + "]", "[" + original + "]")
    return (path, failure["kind"], failure.get("system"),
            identity_map.get(failure.get("record_id"), failure.get("record_id")), failure.get("measurement"))


def no_new_failure(result, baseline):
    if result.get("failures") is None or result.get("csv_failures") is None:
        return False
    for key in ("failures", "csv_failures"):
        original = {failure_signature(item) for item in baseline[key]}
        current = {failure_signature(item, result.get("record_id_map")) for item in result[key]}
        if not current <= original:
            return False
    return True


def small_tail_stable(result):
    """Check the extreme-tail numerical quantities independently of baseline defects."""
    if result.get("error") or result.get("returncode", 0) != 0:
        return False
    output = Path(result.get("output_path", ""))
    try:
        payload = strict_json(output / "review-results.json")
        baseline = payload["baseline"]
        optical = payload["optical_limits"]
        values = [baseline["precision_upper_ug"], optical["absolute_limit_um"]]
        values.extend(row["precision_upper_ug"] for row in payload["mass_results"])
        values.extend(abs(row["upper_limit_um"]) for row in payload["optical_results"])
    except (OSError, KeyError, TypeError, ValueError):
        return False
    return all(type(value) in (int, float) and math.isfinite(value) and value > 0 for value in values)


def dependency_check(code):
    declared = set()
    requirements = code / "requirements.txt"
    try:
        if requirements.exists():
            for line in requirements.read_text(encoding="utf-8-sig").splitlines():
                line = re.sub(r"\s+#.*$", "", line).strip()
                if not line or line.startswith("#"):
                    continue
                requirement = Requirement(line)
                if requirement.url:
                    return {"passed": False, "reason": "Dependencies must be available offline, not fetched from a URL."}
                if requirement.marker and not requirement.marker.evaluate():
                    continue
                version = metadata.version(requirement.name)
                if requirement.specifier and version not in requirement.specifier:
                    return {"passed": False, "reason": "Installed dependency version does not satisfy " + requirement.name}
                declared.add(requirement.name.lower().replace("_", "-"))
        distributions = metadata.packages_distributions()
        for path in code.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            imports = [name.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for name in node.names]
            imports += [node.module.split(".")[0] for node in ast.walk(tree)
                        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module]
            for module in imports:
                if module in sys.stdlib_module_names or (code / (module + ".py")).exists() or (code / module).is_dir():
                    continue
                names = distributions.get(module, [])
                if module.lower().replace("_", "-") not in declared and not any(name.lower().replace("_", "-") in declared for name in names):
                    return {"passed": False, "reason": "Undeclared imported dependency: " + module}
        return {"passed": True, "declared": sorted(declared)}
    except PermissionError:
        raise
    except (ValueError, SyntaxError, UnicodeError, metadata.PackageNotFoundError) as error:
        return {"passed": False, "reason": str(error)}


def reproduce_readme(code, clean_env, folder, input_dir):
    text = (code / "README.md").read_text(encoding="utf-8-sig")
    blocks = re.findall(r"```[^\n]*\n(.*?)```", text, re.S)
    commands = [block for block in blocks if "measurement_check.py" in block]
    if not commands:
        commands = re.findall(r"`([^`\n]*measurement_check\.py[^`\n]*)`", text)
    if not commands:
        commands = [line for line in text.splitlines() if re.match(r"\s*(?:python\S*|/\S*/python\S*)\s+", line)
                    and "measurement_check.py" in line]
    attempts = []
    for index, command in enumerate(commands):
        current = folder / str(index)
        current.mkdir(parents=True)
        workspace = Path(tempfile.mkdtemp(prefix="calibration-readme-"))
        shutil.copytree(input_dir, workspace / "input")
        shutil.copytree(code, workspace / "output/measurement-check")
        # Preserve shell syntax while relocating the issued workspace for isolation.
        command = command.replace("/workspace", str(workspace))
        try:
            run = candidate_run(["bash", "-e", "-o", "pipefail", "-c", command], workspace,
                                {**clean_env, "PIP_NO_INDEX": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"}, current)
            if run.returncode == 0:
                history = input_dir / "instrument-history"
                result = inspect_output(workspace / "output", history / "mass-checks.csv", history / "optical-checks.csv", history / "control-settings.json")
                result["returncode"] = 0
                attempts.append(result)
            else:
                attempts.append({"returncode": run.returncode})
        except subprocess.TimeoutExpired:
            attempts.append({"error": "README command timed out"})
    return attempts


def verify_cli(submission, input_dir, workdir):
    history = input_dir / "instrument-history"
    mass, optical, config = history / "mass-checks.csv", history / "optical-checks.csv", history / "control-settings.json"
    reconstruct(mass, optical, config)
    tool = submission / "measurement-check"
    entry = tool / "measurement_check.py"
    if not entry.is_file() or not (tool / "README.md").is_file():
        return {"passed": False, "score": 0.0, "measurement_complete": True,
                "owners": {owner: 0.0 for owner in OWNER_IDS},
                "completion": {"delivered_contract": False, "fresh_cli": False, "result_coverage": False},
                "error": "Missing tool or README"}
    if any(path.is_symlink() for path in tool.rglob("*")):
        raise ValueError("Candidate tool must not contain symlinks")
    workdir.mkdir(parents=True, exist_ok=False)
    code = workdir / "candidate-tool"
    shutil.copytree(tool, code, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    clean_env = {key: value for key, value in os.environ.items()
                 if key.upper() in ["PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL", "VIRTUAL_ENV"]}
    clean_env.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")

    submitted = inspect_output(submission, mass, optical, config)

    def reorder(mp, op, cp):
        for path in (mp, op):
            headers, rows = source_rows(path)
            random.Random(2718).shuffle(rows)
            save_rows(path, list(reversed(headers)), rows)

    def change_records(mp, op, cp):
        headers, rows = source_rows(mp)
        for index, row in enumerate(rows):
            row["record_id"] = "B" + str(index + 500)
        rows[0]["check_value_ug"] = str(float(rows[0]["check_value_ug"]) + .09)
        rows[-1]["residual_sd_ug"] = "0.2"
        save_rows(mp, headers, rows)
        headers, rows = source_rows(op)
        for index, row in enumerate(rows):
            row["record_id"] = "R" + str(index + 800)
        rows[0]["response_um"] = str(float(rows[0]["response_um"]) + .4)
        save_rows(op, headers, rows)

    def change_settings(mp, op, cp):
        value = strict_json(cp)
        value["mass"].update(baseline_cutoff_year=1986.0, residual_df_each=4, precision_alpha=.025)
        value["optical"].update(slope=1.025, intercept_um=.15, family_alpha=.1)
        cp.write_text(json.dumps(value), encoding="utf-8")

    def extreme_tail(mp, op, cp):
        value = strict_json(cp)
        value["mass"]["precision_alpha"] = 1e-18
        value["optical"]["family_alpha"] = 1e-18
        cp.write_text(json.dumps(value), encoding="utf-8")

    def lower_tail(mp, op, cp):
        value = strict_json(cp)
        value["mass"]["precision_alpha"] = 0.001
        value["optical"]["family_alpha"] = 0.001
        cp.write_text(json.dumps(value), encoding="utf-8")

    variants = {
        "baseline_run": execute(code, clean_env, workdir / "baseline-run", mass, optical, config),
        "reordered": execute(code, clean_env, workdir / "reordered", mass, optical, config, reorder),
        "changed_records": execute(code, clean_env, workdir / "changed-records", mass, optical, config, change_records),
        "changed_settings": execute(code, clean_env, workdir / "changed-settings", mass, optical, config, change_settings),
        "extreme_tail": execute(code, clean_env, workdir / "extreme-tail", mass, optical, config, extreme_tail),
        "lower_tail": execute(code, clean_env, workdir / "lower-tail", mass, optical, config, lower_tail),
    }
    def bom(mp, op, cp):
        for path in (mp, op, cp):
            path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    variants["bom"] = execute(code, clean_env, workdir / "bom", mass, optical, config, bom)

    invalid_edits = []
    def invalid(name, edit):
        invalid_edits.append((name, edit))
    invalid("blank-record-id", lambda m, o, c: (lambda h, r: (r[0].__setitem__("record_id", " "), save_rows(m, h, r)))(*source_rows(m)))
    invalid("negative-residual", lambda m, o, c: (lambda h, r: (r[0].__setitem__("residual_sd_ug", "-0.01"), save_rows(m, h, r)))(*source_rows(m)))
    invalid("blank-system", lambda m, o, c: (lambda h, r: (r[0].__setitem__("balance_id", " "), save_rows(m, h, r)))(*source_rows(m)))
    for target in ("mass", "optical"):
        def duplicate(m, o, c, target=target):
            path = m if target == "mass" else o
            headers, rows = source_rows(path)
            rows[1]["record_id"] = rows[0]["record_id"]
            save_rows(path, headers, rows)
        invalid("duplicate-" + target + "-id", duplicate)
    for key in ("balance_id", "check_standard_id", "design_id"):
        def mixed(m, o, c, key=key):
            headers, rows = source_rows(m)
            rows[0][key] = "other-system"
            save_rows(m, headers, rows)
        invalid("mixed-" + key, mixed)
    invalid("invalid-reference-position", lambda m, o, c: (lambda h, r: (r[0].__setitem__("reference_position", "X"), save_rows(o, h, r)))(*source_rows(o)))
    def config_edit(section, key, value=None, remove=False):
        def edit(m, o, c):
            payload = strict_json(c)
            if remove:
                payload[section].pop(key, None)
            else:
                payload[section][key] = value
            c.write_text(json.dumps(payload), encoding="utf-8")
        return edit
    invalid("family-alpha-one", config_edit("optical", "family_alpha", 1))
    invalid("precision-alpha-zero", config_edit("mass", "precision_alpha", 0))
    invalid("fractional-group-size", config_edit("optical", "controls_per_day", 3.5))
    invalid("missing-slope", config_edit("optical", "slope", remove=True))
    invalid("unsupported-family-method", config_edit("optical", "family_method", "unsupported"))
    def incomplete_group(m, o, c):
        headers, rows = source_rows(o)
        save_rows(o, headers, rows[1:])
    invalid("incomplete-daily-group", incomplete_group)
    def duplicate_position(m, o, c):
        headers, rows = source_rows(o)
        rows[1]["reference_position"] = rows[0]["reference_position"]
        save_rows(o, headers, rows)
    invalid("duplicate-daily-position", duplicate_position)
    def insufficient_monitoring(m, o, c):
        headers, rows = source_rows(m)
        for row in rows[1:]:
            row["decimal_year"] = "1980"
        save_rows(m, headers, rows)
    invalid("insufficient-monitoring", insufficient_monitoring)
    invalid_results = [{"case": name, **execute(code, clean_env, workdir / ("invalid-" + name), mass, optical, config, edit, True)}
                       for name, edit in invalid_edits]

    def no_failure(prefixes):
        return not any(any(row["path"].startswith(prefix) for prefix in prefixes) for row in submitted["failures"])
    dependencies = dependency_check(code)
    readme_runs = reproduce_readme(code, clean_env, workdir / "readme", input_dir) if dependencies["passed"] else []
    disqualifying_paths = {
        "root.summary", "root.baseline", "root.optical_limits", "root.mass_results",
        "root.optical_results", "root.daily_results", "root.trend", "root.scope",
    }
    delivered_contract = (not any(row["path"] == "root" for row in submitted["failures"])
                          and not any(row["path"] == "exceptions" for row in submitted["csv_failures"]))
    result_coverage = delivered_contract and not any(
        row["kind"] in {"object_required", "list_required", "record_membership"}
        or (row["kind"] == "missing" and row["path"] in disqualifying_paths)
        for row in submitted["failures"]
    )
    fresh_cli = ("isolation" in variants["baseline_run"]
                 and variants["baseline_run"].get("failures") is not None
                 and variants["baseline_run"].get("csv_failures") is not None)
    completion = {"delivered_contract": delivered_contract,
                  "fresh_cli": fresh_cli, "result_coverage": result_coverage}
    owners = {
        "N_SUMMARY_SCOPE": float(no_failure(("root.summary", "root.scope"))),
        "N_BASELINE_RECONSTRUCTION": float(no_failure(("root.baseline",))),
        "N_OPTICAL_LIMITS": float(no_failure(("root.optical_limits",))),
        "N_RECORD_DECISIONS": float(no_failure(("root.mass_results", "root.optical_results", "root.daily_results"))
                                            and not submitted["csv_failures"]),
        "N_TREND_ANALYSIS": float(no_failure(("root.trend",))),
        "N_REORDER_PATHS": float(all(no_new_failure(variants[key], submitted) for key in ("baseline_run", "reordered", "bom"))),
        "N_CHANGED_RECORDS": float(no_new_failure(variants["changed_records"], submitted)),
        "N_CHANGED_SETTINGS": float(no_new_failure(variants["changed_settings"], submitted)),
        # Tail runs fail only for an additional defect. An unchanged JSON or CSV
        # defect remains charged to its originating submitted-output owner.
        "N_SMALL_TAIL": float(small_tail_stable(variants["extreme_tail"])),
        "N_INVALID_INPUTS": sum(row["passed"] for row in invalid_results) / len(invalid_results),
        "N_LOWER_TAIL": float(no_new_failure(variants["lower_tail"], submitted)),
        "N_USAGE_REPRODUCTION": float(dependencies["passed"] and bool(readme_runs)
                                        and all(no_new_failure(result, submitted) for result in readme_runs)),
    }
    return {"passed": all(owners[owner] == 1 for owner in SCORED_OWNER_IDS),
            "score": sum(owners[owner] for owner in SCORED_OWNER_IDS) / len(SCORED_OWNER_IDS),
            "measurement_complete": True, "owners": owners, "submitted": submitted,
            "completion": completion,
            "variants": variants, "invalid_results": invalid_results, "dependencies": dependencies,
            "readme_reproduction": readme_runs,
            "scope": "Source-backed atomic numerical and public CLI contract owners."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission-dir", type=Path, default=Path("/workspace/output"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify_cli(args.submission_dir.resolve(), args.input.resolve(), args.report.parent / (args.report.stem + "-cases"))
    except Exception as error:
        result = {"passed": False, "score": None, "measurement_complete": False,
                  "error": type(error).__name__ + ": " + str(error)}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(result, allow_nan=False))
    return 0 if result.get("passed") else (1 if result.get("measurement_complete") else 2)


if __name__ == "__main__":
    raise SystemExit(main())

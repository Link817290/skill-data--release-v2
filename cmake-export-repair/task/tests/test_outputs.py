import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

import unidiff


CORE_HASHES = {
    "cJSON.c": "9e12ef2bf35e9054c0cb65e55a930e5d772f1e052fcbf4bb9a01840a2b85c9b5",
    "cJSON.h": "c25b54ebc98e814eb7b3eeaf12ce899806f87ff5a275b20a3b77dbb3968e5d0b",
    "cJSON_Utils.c": "c405ae37f92d738796badefd9692d081a3564d3d7cc5a856278bf471067267c6",
    "cJSON_Utils.h": "1050a7cce8ffe352c509e0c1faad505b9b8a09cac3a1c45c544447868e05f3b5",
}
FAILURE_HASHES = {
    "build-command.txt": "87d2e6e4f3565b98aff5c94909309e2750127e8a4532e53ef1244332bd455f57",
    "layout-command.txt": "e2aae8ed277dbf5e65c062704d3e2542c1da0e2f64546f611280076c32d20d20",
    "pkg-config-command.txt": "e481a8ace427d3aaef1ad52d05f63a6d36e7f5d087f3c5481c72f42e97140558",
    "relocation-command.txt": "2e1ae431f2a1fcd9567218bd2c446211dfc756aa879005f25b52f147aac86271",
}
ALLOWED_PATCH_FILES = {
    "CMakeLists.txt",
    "library_config/cJSONConfig.cmake.in",
    "library_config/libcjson.pc.in",
    "library_config/libcjson_utils.pc.in",
}


def nearby_relation(text: str, groups: tuple[tuple[str, ...], ...], span: int = 8) -> bool:
    """Accept a relation stated across adjacent prose, list, or evidence-table blocks."""
    blocks = [part for part in text.split("\n\n") if part.strip()]
    for start in range(len(blocks)):
        window = "\n\n".join(blocks[start : start + span])
        if all(any(token in window for token in group) for group in groups):
            return True
    return False


def cmake_calls(text: str, command: str) -> list[str]:
    """Return balanced command bodies without treating unrelated variables as arguments."""
    calls: list[str] = []
    lowered = text.lower()
    cursor = 0
    while True:
        start = lowered.find(command.lower(), cursor)
        if start < 0:
            break
        before = lowered[start - 1] if start else ""
        if before.isalnum() or before == "_":
            cursor = start + len(command)
            continue
        opening = start + len(command)
        while opening < len(text) and text[opening].isspace():
            opening += 1
        if opening >= len(text) or text[opening] != "(":
            cursor = opening
            continue
        depth = 1
        index = opening + 1
        quoted = False
        escaped = False
        while index < len(text) and depth:
            char = text[index]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = not quoted
            elif not quoted and char == "(":
                depth += 1
            elif not quoted and char == ")":
                depth -= 1
            index += 1
        if depth == 0:
            calls.append(text[opening + 1 : index - 1])
        cursor = max(index, opening + 1)
    return calls


def cmake_arguments(body: str) -> list[str]:
    """Tokenize a CMake call while treating quoting and whitespace as syntax."""
    lexer = shlex.shlex(body, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = "#"
    return list(lexer)


def installed_export_pairs(cmake: str) -> set[tuple[str, str]]:
    """Return ``(target, export-set)`` relations from install(TARGETS ...)."""
    pairs: set[tuple[str, str]] = set()
    stop_words = {
        "EXPORT", "ARCHIVE", "LIBRARY", "RUNTIME", "OBJECTS", "FRAMEWORK",
        "BUNDLE", "PRIVATE_HEADER", "PUBLIC_HEADER", "RESOURCE", "INCLUDES",
        "DESTINATION", "PERMISSIONS", "CONFIGURATIONS", "COMPONENT", "NAMELINK_COMPONENT",
        "OPTIONAL", "EXCLUDE_FROM_ALL", "NAMELINK_ONLY", "NAMELINK_SKIP",
    }
    for body in cmake_calls(cmake, "install"):
        tokens = cmake_arguments(body)
        upper = [token.upper() for token in tokens]
        if not tokens or upper[0] != "TARGETS" or "EXPORT" not in upper:
            continue
        export_index = upper.index("EXPORT")
        if export_index + 1 >= len(tokens):
            continue
        export_set = tokens[export_index + 1]
        for token in tokens[1:export_index]:
            if token.upper() in stop_words:
                break
            pairs.add((token, export_set))
    return pairs


def pkg_config_fields(text: str) -> dict[str, str]:
    """Parse pkg-config template fields with normalized names and whitespace."""
    fields: dict[str, str] = {}
    for raw in text.splitlines():
        if ":" not in raw or raw.lstrip().startswith("#"):
            continue
        name, value = raw.split(":", 1)
        fields[name.strip().lower()] = " ".join(value.split())
    return fields


def locate(value: str) -> Path:
    candidate = Path(value).resolve()
    if candidate.is_file():
        candidate = candidate.parent
    if (candidate / "project").is_dir():
        return candidate
    if candidate.name == "project" and candidate.is_dir():
        return candidate.parent
    if (candidate / "environment" / "workspace" / "project").is_dir():
        return candidate / "environment" / "workspace"
    raise AssertionError(f"workspace with project/ not found at {candidate}")


def sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def static_checks(root: Path) -> dict[str, bool]:
    analysis = root / "analysis" / "diagnosis.md"
    patch_path = root / "patches" / "patch_0.diff"
    report_path = root / "build_report.json"
    project = root / "project"
    checks = {
        "artifact_analysis": analysis.is_file() and analysis.stat().st_size > 200,
        "artifact_patch": patch_path.is_file() and patch_path.stat().st_size > 100,
        "artifact_report": report_path.is_file() and report_path.stat().st_size > 100,
        "project": (project / "CMakeLists.txt").is_file(),
    }
    if not all(checks.values()):
        return checks

    parsed_patch = None
    try:
        parsed_patch = unidiff.PatchSet.from_filename(str(patch_path))
        checks["patch_parse"] = True
    except (OSError, unidiff.errors.UnidiffParseError):
        checks["patch_parse"] = False
    patch_files = {item.path.removeprefix("project/") for item in parsed_patch or []}
    checks["patch_minimal"] = bool(parsed_patch) and patch_files.issubset(ALLOWED_PATCH_FILES)

    cmake = (project / "CMakeLists.txt").read_text(encoding="utf-8", errors="replace")
    config = (project / "library_config" / "cJSONConfig.cmake.in").read_text(
        encoding="utf-8", errors="replace"
    )
    pc_texts = [
        (project / "library_config" / name).read_text(encoding="utf-8", errors="replace")
        for name in ("libcjson.pc.in", "libcjson_utils.pc.in")
    ]
    install_calls = cmake_calls(cmake, "install")
    export_pairs = installed_export_pairs(cmake)
    pc_fields = [pkg_config_fields(item) for item in pc_texts]
    checks.update(
        {
            "repair_static_exports": (
                {
                    ("${CJSON_LIB}", "${CJSON_LIB}"),
                    ("${CJSON_LIB}-static", "${CJSON_LIB}"),
                    ("${CJSON_UTILS_LIB}", "${CJSON_UTILS_LIB}"),
                    ("${CJSON_UTILS_LIB}-static", "${CJSON_UTILS_LIB}"),
                }.issubset(export_pairs)
            ),
            "repair_relative_destinations": (
                len(install_calls) >= 8
                and all("CMAKE_INSTALL_FULL_" not in body for body in install_calls)
            ),
            "repair_relocatable_config": (
                "CMAKE_INSTALL_FULL_INCLUDEDIR" not in config
                and (
                    "PACKAGE_INIT" in config
                    or "CMAKE_CURRENT_LIST_DIR" in config
                    or "CMAKE_CURRENT_LIST_FILE" in config
                )
                and "CJSON_INCLUDE_DIR" in config
            ),
            "repair_relocatable_pc": all(
                "${pcfiledir}" in item
                and "CMAKE_INSTALL_FULL_" not in item
                and "libdir=" in item
                and "includedir=" in item
                for item in pc_texts
            ),
            "repair_pkg_dependencies": (
                "-lm" in shlex.split(pc_fields[0].get("libs.private", ""))
                and "libcjson" in re.split(r"[\s,]+", pc_fields[1].get("requires", "").lower())
            ),
        }
    )
    for name, expected in CORE_HASHES.items():
        checks[f"preserve_{name}"] = sha256(project / name) == expected
    checks["preserve_failure_inputs"] = all(
        (root / "failure" / name).is_file() and sha256(root / "failure" / name) == expected
        for name, expected in FAILURE_HASHES.items()
    )
    checks["no_build_residue"] = not any(
        path.name in {
            "build", "prefix", "stage-a", "stage-b", "consumer-build", "CMakeFiles",
            "CMakeCache.txt", "cmake_install.cmake", ".ninja_deps", ".ninja_log",
        }
        for path in project.rglob("*")
    )
    checks["reverse_patch"] = any(
        subprocess.run(
            ["patch", "--dry-run", "--batch", "-R", "-p1", "-i", str(patch_path)],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        ).returncode
        == 0
        for cwd in (project, root)
    )
    added_patch_text = "\n".join(
        line.value for patched_file in parsed_patch or [] for hunk in patched_file for line in hunk if line.is_added
    )
    checks["patch_hygiene"] = (
        not re.search(r"(?m)^(?:<{7}|={7}|>{7})", added_patch_text)
        and not re.search(r"(?:^|[\s=\"'])(?:/tmp/|/home/|/Users/)", added_patch_text)
        and not re.search(r"(?i)(?:api[_-]?key|password|secret|token)\s*[:=]\s*[^$@\s]", added_patch_text)
    )
    checks["patch_original_match"] = False
    checks["patch_roundtrip_match"] = False
    if checks["reverse_patch"]:
        try:
            baseline = json.loads((Path(__file__).parent / "semantic_source.json").read_text(encoding="utf-8"))[
                "fresh_reproduction"
            ]["source_sha256"]
            with tempfile.TemporaryDirectory(prefix="patch-roundtrip-") as temporary:
                restored = Path(temporary) / "project"
                shutil.copytree(project, restored)
                reverse = subprocess.run(
                    ["patch", "--batch", "-R", "-p1", "-i", str(patch_path)], cwd=restored,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                )
                checks["patch_original_match"] = reverse.returncode == 0 and all(
                    (restored / rel).is_file() and sha256(restored / rel) == expected
                    for rel, expected in baseline.items()
                )
                forward = subprocess.run(
                    ["patch", "--batch", "-p1", "-i", str(patch_path)], cwd=restored,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                )
                repaired_files = {
                    path.relative_to(project).as_posix(): sha256(path)
                    for path in project.rglob("*") if path.is_file()
                }
                roundtrip_files = {
                    path.relative_to(restored).as_posix(): sha256(path)
                    for path in restored.rglob("*") if path.is_file()
                }
                checks["patch_roundtrip_match"] = forward.returncode == 0 and roundtrip_files == repaired_files
        except (OSError, KeyError, json.JSONDecodeError):
            pass
    return checks


def run_validation(root: Path) -> dict[str, bool | str | list[str]]:
    project = root / "project"
    result: dict[str, bool | str | list[str]] = {}
    if shutil.which("cmake") is None or shutil.which("pkg-config") is None:
        return {"validation_environment": "deferred to task image"}

    def run(label: str, argv: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        proc = subprocess.run(
            argv,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        result[label] = proc.returncode == 0
        if proc.returncode != 0:
            result[f"{label}_output"] = proc.stdout[-2000:]
        return proc

    with tempfile.TemporaryDirectory(prefix="native-relocation-") as temp:
        base = Path(temp)
        source = base / "project"
        shutil.copytree(project, source)
        build = base / "build"
        prefix_a = base / "stage-a"
        prefix_b = base / "stage-b"
        configure = run(
            "producer_configure",
            [
                "cmake", "-S", str(source), "-B", str(build),
                "-DBUILD_SHARED_AND_STATIC_LIBS=ON", "-DENABLE_CJSON_UTILS=ON",
                "-DENABLE_TARGET_EXPORT=ON", "-DENABLE_CJSON_TEST=OFF",
                f"-DCMAKE_INSTALL_PREFIX={prefix_a}",
            ],
        )
        if configure.returncode != 0:
            return result
        producer_build = run("producer_build", ["cmake", "--build", str(build), "-j2"])
        if producer_build.returncode != 0:
            return result
        install = run("install", ["cmake", "--install", str(build)])
        if install.returncode != 0:
            return result

        shutil.copytree(prefix_a, prefix_b)
        shutil.rmtree(prefix_a)
        result["prefix_relocated"] = prefix_b.is_dir() and not prefix_a.exists()
        metadata_files = sorted((prefix_b / "lib").rglob("*.cmake")) + sorted(
            (prefix_b / "lib").rglob("*.pc")
        )
        stale_files = [
            str(path.relative_to(prefix_b))
            for path in metadata_files
            if str(prefix_a) in path.read_text(encoding="utf-8", errors="replace")
        ]
        result["metadata_no_old_prefix"] = not stale_files
        result["metadata_stale_files"] = stale_files
        if stale_files:
            return result

        consumer = base / "cmake-consumer"
        consumer.mkdir()
        (consumer / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.10)\n"
            "project(relocated_consumers C)\n"
            "find_package(cJSON CONFIG REQUIRED)\n"
            "add_executable(shared_smoke shared.c)\n"
            "target_link_libraries(shared_smoke PRIVATE cjson)\n"
            "add_executable(static_utils_smoke static_utils.c)\n"
            "target_link_libraries(static_utils_smoke PRIVATE cjson_utils-static)\n",
            encoding="utf-8",
        )
        (consumer / "shared.c").write_text(
            "#include <cjson/cJSON.h>\n"
            "int main(void) { cJSON *root = cJSON_CreateObject(); cJSON_Delete(root); return 0; }\n",
            encoding="utf-8",
        )
        (consumer / "static_utils.c").write_text(
            "#include <cjson/cJSON_Utils.h>\n"
            "int main(void) { cJSON *root = cJSON_CreateObject(); "
            "int ok = cJSONUtils_GetPointer(root, \"\") == root; cJSON_Delete(root); return ok ? 0 : 1; }\n",
            encoding="utf-8",
        )
        consumer_build = base / "cmake-consumer-build"
        consumer_configure = run(
            "cmake_consumer_configure",
            ["cmake", "-S", str(consumer), "-B", str(consumer_build), f"-DCMAKE_PREFIX_PATH={prefix_b}"],
        )
        if consumer_configure.returncode != 0:
            return result
        consumer_make = run("cmake_consumer_build", ["cmake", "--build", str(consumer_build), "-j2"])
        if consumer_make.returncode != 0:
            return result
        if run("shared_smoke", [str(consumer_build / "shared_smoke")]).returncode != 0:
            return result
        if run("static_utils_smoke", [str(consumer_build / "static_utils_smoke")]).returncode != 0:
            return result

        pkg_env = os.environ.copy()
        pkg_env["PKG_CONFIG_PATH"] = str(prefix_b / "lib" / "pkgconfig")
        query = run("pkg_config_query", ["pkg-config", "--cflags", "--libs", "libcjson_utils"], env=pkg_env)
        if query.returncode != 0:
            return result
        result["pkg_config_no_old_prefix"] = str(prefix_a) not in query.stdout
        result["pkg_config_flags"] = query.stdout.strip()
        if not result["pkg_config_no_old_prefix"]:
            return result
        static_query = run(
            "pkg_config_static_query", ["pkg-config", "--static", "--libs", "libcjson_utils"], env=pkg_env
        )
        if static_query.returncode != 0:
            return result
        result["pkg_config_static_no_old_prefix"] = str(prefix_a) not in static_query.stdout
        result["pkg_config_static_private_math"] = "-lm" in shlex.split(static_query.stdout)
        if not result["pkg_config_static_no_old_prefix"] or not result["pkg_config_static_private_math"]:
            return result
        pkg_source = base / "pkg-consumer.c"
        pkg_source.write_text(
            "#include <cjson/cJSON_Utils.h>\n"
            "int main(void) { cJSON *root = cJSON_CreateObject(); "
            "int ok = cJSONUtils_GetPointer(root, \"\") == root; cJSON_Delete(root); return ok ? 0 : 1; }\n",
            encoding="utf-8",
        )
        pkg_smoke = base / "pkg-smoke"
        pkg_build = run(
            "pkg_config_consumer_build",
            ["cc", str(pkg_source), "-o", str(pkg_smoke), *shlex.split(query.stdout)],
        )
        if pkg_build.returncode != 0:
            return result
        smoke_env = os.environ.copy()
        smoke_env["LD_LIBRARY_PATH"] = str(prefix_b / "lib")
        smoke_env["DYLD_LIBRARY_PATH"] = str(prefix_b / "lib")
        if run("pkg_config_smoke", [str(pkg_smoke)], env=smoke_env).returncode != 0:
            return result

        layout_build = base / "layout-build"
        layout_prefix_a = base / "layout-stage-a"
        layout_prefix_b = base / "layout-stage-b"
        layout_libdir = Path("lib/x86_64-linux-gnu")
        layout_includedir = Path("include/sdk")
        layout_configure = run(
            "layout_producer_configure",
            [
                "cmake", "-S", str(source), "-B", str(layout_build),
                "-DBUILD_SHARED_AND_STATIC_LIBS=ON", "-DENABLE_CJSON_UTILS=ON",
                "-DENABLE_TARGET_EXPORT=ON", "-DENABLE_CJSON_TEST=OFF",
                f"-DCMAKE_INSTALL_PREFIX={layout_prefix_a}",
                f"-DCMAKE_INSTALL_LIBDIR={layout_libdir}",
                f"-DCMAKE_INSTALL_INCLUDEDIR={layout_includedir}",
            ],
        )
        if layout_configure.returncode != 0:
            return result
        if run("layout_producer_build", ["cmake", "--build", str(layout_build), "-j2"]).returncode != 0:
            return result
        if run("layout_install", ["cmake", "--install", str(layout_build)]).returncode != 0:
            return result

        shutil.copytree(layout_prefix_a, layout_prefix_b)
        shutil.rmtree(layout_prefix_a)
        result["layout_prefix_relocated"] = layout_prefix_b.is_dir() and not layout_prefix_a.exists()
        layout_metadata = sorted(layout_prefix_b.rglob("*.cmake")) + sorted(layout_prefix_b.rglob("*.pc"))
        layout_stale = [
            str(path.relative_to(layout_prefix_b))
            for path in layout_metadata
            if str(layout_prefix_a) in path.read_text(encoding="utf-8", errors="replace")
        ]
        result["layout_metadata_no_old_prefix"] = not layout_stale
        result["layout_metadata_stale_files"] = layout_stale
        if layout_stale:
            return result

        layout_consumer = base / "layout-consumer"
        layout_consumer.mkdir()
        (layout_consumer / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.10)\n"
            "project(layout_consumer C)\n"
            "find_package(cJSON CONFIG REQUIRED)\n"
            "if(NOT EXISTS \"${CJSON_INCLUDE_DIRS}/cjson/cJSON.h\")\n"
            "  message(FATAL_ERROR \"legacy include root is invalid: ${CJSON_INCLUDE_DIRS}\")\n"
            "endif()\n"
            "add_executable(layout_smoke main.c)\n"
            "target_include_directories(layout_smoke PRIVATE \"${CJSON_INCLUDE_DIRS}\")\n"
            "target_link_libraries(layout_smoke PRIVATE cjson_utils-static)\n",
            encoding="utf-8",
        )
        (layout_consumer / "main.c").write_text(
            "#include <cjson/cJSON_Utils.h>\n"
            "int main(void) { cJSON *root = cJSON_CreateObject(); "
            "int ok = cJSONUtils_GetPointer(root, \"\") == root; cJSON_Delete(root); return ok ? 0 : 1; }\n",
            encoding="utf-8",
        )
        layout_consumer_build = base / "layout-consumer-build"
        layout_consumer_configure = run(
            "layout_cmake_consumer_configure",
            [
                "cmake", "-S", str(layout_consumer), "-B", str(layout_consumer_build),
                f"-DCMAKE_PREFIX_PATH={layout_prefix_b}",
                f"-DcJSON_DIR={layout_prefix_b / layout_libdir / 'cmake/cJSON'}",
            ],
        )
        if layout_consumer_configure.returncode != 0:
            return result
        if run(
            "layout_cmake_consumer_build", ["cmake", "--build", str(layout_consumer_build), "-j2"]
        ).returncode != 0:
            return result
        if run("layout_cmake_smoke", [str(layout_consumer_build / "layout_smoke")]).returncode != 0:
            return result

        layout_pkg_env = os.environ.copy()
        layout_pkg_env["PKG_CONFIG_LIBDIR"] = str(layout_prefix_b / layout_libdir / "pkgconfig")
        layout_pkg_env.pop("PKG_CONFIG_PATH", None)
        layout_query = run(
            "layout_pkg_config_query",
            ["pkg-config", "--cflags", "--libs", "libcjson_utils"],
            env=layout_pkg_env,
        )
        if layout_query.returncode != 0:
            return result
        result["layout_pkg_config_flags"] = layout_query.stdout.strip()
        result["layout_pkg_config_no_old_prefix"] = str(layout_prefix_a) not in layout_query.stdout
        if not result["layout_pkg_config_no_old_prefix"]:
            return result
        layout_static_query = run(
            "layout_pkg_config_static_query",
            ["pkg-config", "--static", "--libs", "libcjson_utils"],
            env=layout_pkg_env,
        )
        if layout_static_query.returncode != 0:
            return result
        result["layout_pkg_config_static_no_old_prefix"] = str(layout_prefix_a) not in layout_static_query.stdout
        result["layout_pkg_config_static_private_math"] = "-lm" in shlex.split(layout_static_query.stdout)
        if not result["layout_pkg_config_static_no_old_prefix"] or not result["layout_pkg_config_static_private_math"]:
            return result
        layout_pkg_smoke = base / "layout-pkg-smoke"
        layout_pkg_build = run(
            "layout_pkg_config_consumer_build",
            [
                "cc", str(layout_consumer / "main.c"), "-o", str(layout_pkg_smoke),
                *shlex.split(layout_query.stdout),
            ],
        )
        if layout_pkg_build.returncode != 0:
            return result
        layout_smoke_env = os.environ.copy()
        layout_smoke_env["LD_LIBRARY_PATH"] = str(layout_prefix_b / layout_libdir)
        layout_smoke_env["DYLD_LIBRARY_PATH"] = str(layout_prefix_b / layout_libdir)
        run("layout_pkg_config_smoke", [str(layout_pkg_smoke)], env=layout_smoke_env)
    return result


def pass_value(value: object) -> bool:
    return isinstance(value, str) and value.lower() in {
        "pass", "passed", "success", "successful", "ok",
    }


def result_entry_passed(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    # A successful wrapper must not hide a failed nested command.  Reports in
    # the wild often keep a top-level ``status: pass`` while one of the
    # producer/consumer steps failed; accepting any positive field made that
    # contradiction score as a complete validation.
    def expected_nonzero(node: dict, actual: int) -> bool:
        for key in ("expected_exit_code", "expected_exit", "expected_returncode"):
            expected = node.get(key)
            if isinstance(expected, int) and not isinstance(expected, bool) and expected == actual:
                return True
            if isinstance(expected, (list, tuple)) and actual in expected:
                return True
        command = next((node.get(key) for key in ("command", "cmd", "shell", "argv") if node.get(key)), "")
        if isinstance(command, (list, tuple)):
            command = " ".join(str(part) for part in command)
        interpretation = " ".join(
            str(node.get(key, "")) for key in ("interpretation", "expectation", "reason")
        ).lower()
        return (
            actual == 1
            and isinstance(command, str)
            and re.search(r"(?:^|\s)(?:grep|rg)(?:\s|$)", command)
            and "pass" in interpretation
            and any(token in interpretation for token in ("no match", "no old", "no original", "absent", "not found"))
        )

    def contains_failure(value: object) -> bool:
        if isinstance(value, dict):
            for key, item in value.items():
                lowered = str(key).lower()
                if lowered in {"status", "result", "outcome"} and isinstance(item, str) and item.lower() in {
                    "fail", "failed", "failure", "error", "errored", "unsuccessful", "not_run",
                }:
                    return True
                if (
                    lowered in {"exit_code", "returncode", "return_code"}
                    and isinstance(item, int) and not isinstance(item, bool) and item != 0
                    and not expected_nonzero(value, item)
                ):
                    return True
                if contains_failure(item):
                    return True
        elif isinstance(value, (list, tuple)):
            return any(contains_failure(item) for item in value)
        return False

    if contains_failure(entry):
        return False
    if any(pass_value(entry.get(key)) for key in ("status", "result", "outcome")):
        return True
    if any(
        isinstance(entry.get(key), int)
        and not isinstance(entry.get(key), bool)
        and entry.get(key) != 0
        and expected_nonzero(entry, entry[key])
        for key in ("exit_code", "returncode", "return_code")
    ):
        return True
    after = entry.get("after")
    if not isinstance(after, dict):
        return False
    if "status" not in after and "result" not in after and "outcome" not in after:
        return after.get("exit_code") == 0 or after.get("returncode") == 0
    return result_entry_passed(after)


def _report_step_records(report: dict) -> list[dict] | None:
    steps = report.get("steps")
    if isinstance(steps, dict) and steps:
        if not all(isinstance(value, dict) for value in steps.values()):
            return []
        return list(steps.values())
    for key in ("captured_scenarios", "scenarios", "final_validation"):
        scenarios = report.get(key)
        if isinstance(scenarios, list) and scenarios:
            if not all(isinstance(value, dict) for value in scenarios):
                return []
            return list(scenarios)
    return None


def _report_steps_pass(report: dict, required: tuple[str, ...]) -> bool:
    steps = report.get("steps")
    if not isinstance(steps, dict):
        return False
    return all(name in steps and result_entry_passed(steps[name]) for name in required)


def _report_steps_have_evidence(report: dict, required: tuple[str, ...]) -> bool:
    """Require an invocation and concrete outcome for every claimed scenario."""
    steps = report.get("steps") if isinstance(report, dict) else None
    if not isinstance(steps, dict):
        return False
    top_commands = report.get("commands")
    top_list = [str(item) for item in top_commands] if isinstance(top_commands, (list, tuple)) else []
    command_hints = {
        "prefix_relocation": (("cp", "stage-a", "stage-b"), ("rm", "stage-a")),
        "cmake_consumer_configure": (("cmake", "-s", "consumer", "cmake_prefix_path"),),
        "cmake_consumer_build": (("cmake", "--build", "consumer-build"),),
        "shared_smoke": (("shared_smoke",),),
        "static_utils_smoke": (("static_utils_smoke",),),
        "pkg_config_query": (("pkg-config", "--cflags", "libcjson_utils"),),
        "pkg_config_static_query": (("pkg-config", "--static", "--libs", "libcjson_utils"),),
        "pkg_config_consumer_build": (("cc", "pkg-consumer", "pkg-smoke"),),
        "pkg_config_smoke": (("pkg-smoke",),),
    }
    for name in required:
        entry = steps.get(name)
        if not isinstance(entry, dict) or not result_entry_passed(entry):
            return False
        command = next((entry.get(key) for key in
                        ("command", "commands", "cmd", "argv", "invocation")
                        if entry.get(key) is not None), None)
        if isinstance(command, dict):
            command = command.get("argv") or command.get("command") or command.get("shell")
        if isinstance(command, (list, tuple)):
            command = " ".join(str(part) for part in command)
        commands = [command] if isinstance(command, str) and command.strip() else top_list
        hint_groups = command_hints.get(name, ())
        if not hint_groups or not all(
            any(all(hint in candidate.lower() for hint in group) for candidate in commands)
            for group in hint_groups
        ):
            return False
        if not any(key in entry for key in ("exit_code", "returncode", "stdout", "stderr", "output", "result", "outcome", "original_removed", "stale_files")):
            return False
    return True


def report_passed(report: object) -> bool:
    if not isinstance(report, dict):
        return False
    records = _report_step_records(report)
    if records == []:
        return False
    if records is not None and not all(result_entry_passed(item) for item in records):
        return False
    for key in ("status", "overall_status", "result", "outcome"):
        if pass_value(report.get(key)):
            # A top-level pass is meaningful only when it is backed by a
            # scenario/step record or an explicit aggregate summary.  This
            # keeps a keyword-only report from satisfying the strict gate.
            return records is not None

    for key in ("summary", "final_validation", "validation_summary"):
        section = report.get(key)
        if not isinstance(section, dict):
            continue
        if any(pass_value(section.get(name)) for name in ("status", "overall_status", "result", "outcome")):
            return True
        if any(
            value is True and ("pass" in name or "success" in name)
            for name, value in section.items()
            if name.startswith("all_")
        ):
            return True
        total = section.get("scenarios_total")
        passing = section.get("scenarios_passing")
        if isinstance(total, int) and total > 0 and passing == total:
            return True
        if section.get("all_scenarios_exit_code") == 0:
            return True

    if records is not None and records and all(result_entry_passed(item) for item in records):
        return True
    return False


# ---------------------------------------------------------------------------
# Lenient lens: a binary delivery-completeness contract.
#
# It answers a different question from the strict lens and is computed from a
# different evidence base.  Strict asks how well the interface was diagnosed and
# repaired: it reads the meaning of the diagnosis, checks the repair against the
# owning declarations, re-runs producer configure/build/install, relocates two
# prefixes, drives independent consumers, and requires the report to state a
# passing outcome.  Lenient asks only whether a usable submission arrived: are the
# named pieces there, does each one decode into the shape the instruction names,
# and does the report carry both kinds of record the instruction asks it to carry.
#
# Delivery components do not read diagnosis meaning, compare against the
# reference repair, or inspect patched-file semantics. The final lenient reward
# additionally requires the same fresh baseline native gate as strict. A failed
# validation is useful evidence but not a completed repair; a submission whose
# deliverable files were created and left empty is also incomplete. The lenient
# result is therefore not a thresholding of the strict score.
# ---------------------------------------------------------------------------

DELIVERY_COMPONENTS = (
    "delivery_files_present",
    "delivery_project_present",
    "delivery_diagnosis_readable",
    "delivery_patch_is_unified_diff",
    "delivery_report_is_object",
    "delivery_report_records_commands",
    "delivery_report_records_results",
)

_COMMAND_KEYS = {
    "command", "commands", "cmd", "cmds", "command_line", "commandline",
    "commands_run", "invocation", "invocations", "argv", "shell",
}
_RESULT_KEYS = {
    "status", "result", "results", "outcome", "overall_status", "exit_code",
    "exit_status", "returncode", "return_code", "passed", "success",
}
_HUNK_HEADER = re.compile(r"^@@ +-\d+(?:,\d+)? +\+\d+(?:,\d+)? +@@")


def read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def readable_prose_document(text: str) -> bool:
    """A document a maintainer can open with at least one substantive body line."""
    lines = [line.rstrip() for line in text.splitlines()]
    has_body = any(line.strip() and not line.lstrip().startswith("#") for line in lines)
    return has_body


def unified_diff_shape(text: str) -> bool:
    """Structural read of a unified diff: an old/new file header pair, a hunk
    header, and at least one changed line inside that hunk.  Deliberately its own
    parser rather than the strict lens's diff library, so the two lenses do not
    share an implementation."""
    lines = text.splitlines()
    index = 0
    while index + 1 < len(lines):
        if lines[index].startswith("--- ") and lines[index + 1].startswith("+++ "):
            cursor = index + 2
            while cursor < len(lines):
                if _HUNK_HEADER.match(lines[cursor]):
                    for body in lines[cursor + 1 :]:
                        if body.startswith("--- ") or _HUNK_HEADER.match(body):
                            break
                        if body.startswith(("+", "-")) and not body.startswith(("+++", "---")):
                            return True
                    break
                if lines[cursor].startswith("--- "):
                    break
                cursor += 1
        index += 1
    return False


def walk_fields(node: object):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key, value
            yield from walk_fields(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk_fields(item)


def command_like(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(command_like(item) for item in value)
    if isinstance(value, dict):
        return any(
            isinstance(key, str) and key.lower() in _COMMAND_KEYS and command_like(item)
            for key, item in value.items()
        )
    return False


def result_like(value: object) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, int):
        return True
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(result_like(item) for item in value)
    if isinstance(value, dict):
        return any(
            isinstance(key, str) and key.lower() in _RESULT_KEYS and result_like(item)
            for key, item in value.items()
        )
    return False


def report_records_commands(report: object) -> bool:
    return any(
        isinstance(key, str) and key.lower() in _COMMAND_KEYS and command_like(value)
        for key, value in walk_fields(report)
    )


def report_records_results(report: object) -> bool:
    return any(
        isinstance(key, str) and key.lower() in _RESULT_KEYS and result_like(value)
        for key, value in walk_fields(report)
    )


def delivery_checks(root: Path) -> dict[str, bool]:
    """The binary delivery contract, component by component."""
    analysis = root / "analysis" / "diagnosis.md"
    patch_path = root / "patches" / "patch_0.diff"
    report_path = root / "build_report.json"
    project = root / "project"

    checks = dict.fromkeys(DELIVERY_COMPONENTS, False)
    checks["delivery_files_present"] = (
        analysis.is_file() and patch_path.is_file() and report_path.is_file()
    )
    checks["delivery_project_present"] = (project / "CMakeLists.txt").is_file()
    if analysis.is_file():
        checks["delivery_diagnosis_readable"] = readable_prose_document(read_text_safe(analysis))
    if patch_path.is_file():
        checks["delivery_patch_is_unified_diff"] = unified_diff_shape(read_text_safe(patch_path))
    if report_path.is_file():
        try:
            report = json.loads(read_text_safe(report_path))
        except json.JSONDecodeError:
            report = None
        if isinstance(report, dict):
            checks["delivery_report_is_object"] = True
            checks["delivery_report_records_commands"] = report_records_commands(report)
            checks["delivery_report_records_results"] = report_records_results(report) and report_passed(report)
    return checks


def lenient_score(delivery: dict[str, bool]) -> float:
    return 1.0 if all(delivery.get(key, False) for key in DELIVERY_COMPONENTS) else 0.0


LENIENT_FORMULA = (
    "binary delivery contract: 1.0 iff the diagnosis, unified patch, report, and "
    "applied project are all present, the diagnosis opens as a document with a "
    "nonempty body, the patch parses as a unified diff with at least one changed "
    "hunk, and the report parses as a JSON object that records both the commands it "
    "ran and a successful, internally consistent result, and fresh baseline producer/consumer "
    "validation passes; 0.0 otherwise. It does not read diagnosis meaning."
)
STRICT_FORMULA = (
    "weighted cross-interface and layout reasoning atoms with artifact, integrity, "
    "and baseline relocation gates"
)


REQUIRED_ARTIFACTS = ("artifact_analysis", "artifact_patch", "artifact_report", "project")


def baseline_validation_passed(validation: dict) -> bool:
    required = (
        "producer_configure", "producer_build", "install", "prefix_relocated", "metadata_no_old_prefix",
        "cmake_consumer_configure", "cmake_consumer_build", "shared_smoke", "static_utils_smoke",
        "pkg_config_query", "pkg_config_no_old_prefix", "pkg_config_consumer_build", "pkg_config_smoke",
        "pkg_config_static_query", "pkg_config_static_no_old_prefix", "pkg_config_static_private_math",
    )
    return all(validation.get(key) is True for key in required)


def strict_aggregate(
    base_checks: dict,
    validation: dict,
    analysis_text: str,
    report_text: str,
    report: object,
    semantic: dict | None = None,
) -> tuple[float, dict, dict]:
    """The strict lens proper: atoms, weights, and gates.

    Split out from :func:`score_workspace` so that the one implementation of the
    strict formula can also be replayed against archived evidence. Nothing here
    reads the filesystem; every input is supplied by the caller.
    """
    checks = dict(base_checks)
    report_ok = report_passed(report)
    checks["report_status"] = report_ok
    checks.update({f"validation_{key}": value for key, value in validation.items() if isinstance(value, bool)})

    atoms = {
        "D1": 0.0,
        "D2": 0.0,
        "D3": 0.0,
        "D4": 0.0,
        "D5": 0.0,
        "P1": 0.0,
        "P2": 0.0,
        "P3": 0.0,
        "E1": report_ok
        and _report_steps_pass(
            report,
            ("prefix_relocation", "cmake_consumer_configure", "cmake_consumer_build",
             "shared_smoke", "static_utils_smoke"),
        )
        and _report_steps_have_evidence(
            report,
            ("prefix_relocation", "cmake_consumer_configure", "cmake_consumer_build",
             "shared_smoke", "static_utils_smoke"),
        )
        and all(validation.get(key) is True for key in (
            "prefix_relocated", "cmake_consumer_configure",
            "cmake_consumer_build", "shared_smoke", "static_utils_smoke",
        ))
        and ("relocat" in report_text or "moved" in report_text)
        and "cmake" in report_text
        and "static" in report_text
        and "shared" in report_text,
        "E2": report_ok
        and _report_steps_pass(
            report,
            ("pkg_config_query", "pkg_config_static_query", "pkg_config_consumer_build", "pkg_config_smoke"),
        )
        and _report_steps_have_evidence(
            report,
            ("pkg_config_query", "pkg_config_static_query", "pkg_config_consumer_build", "pkg_config_smoke"),
        )
        and all(validation.get(key) is True for key in (
            "pkg_config_query", "pkg_config_no_old_prefix",
            "pkg_config_static_query", "pkg_config_static_no_old_prefix", "pkg_config_static_private_math",
            "pkg_config_consumer_build", "pkg_config_smoke",
        ))
        and "pkg-config" in report_text
        and ("compile" in report_text or "consumer_build" in report_text),
        "E3": 0.0,
        "L1": 0.0,
        "L2": 0.0,
        "L3": 0.0,
        "V1": all(
            validation.get(key) is True
            for key in (
                "layout_prefix_relocated", "layout_metadata_no_old_prefix",
                "layout_cmake_consumer_configure", "layout_cmake_consumer_build", "layout_cmake_smoke",
            )
        )
        and ("multi-component" in report_text or "x86_64-linux-gnu" in report_text),
        "V2": all(
            validation.get(key) is True
            for key in (
                "layout_pkg_config_query", "layout_pkg_config_no_old_prefix",
                "layout_pkg_config_static_query", "layout_pkg_config_static_no_old_prefix",
                "layout_pkg_config_static_private_math",
                "layout_pkg_config_consumer_build", "layout_pkg_config_smoke",
            )
        )
        and ("pkg-config" in report_text or "pkg_config" in report_text)
        and ("multi-component" in report_text or "x86_64-linux-gnu" in report_text),
    }
    weights = {
        "D1": 0.05,
        "D2": 0.07,
        "D3": 0.07,
        "D4": 0.07,
        "D5": 0.04,
        "P1": 0.05,
        "P2": 0.05,
        "P3": 0.05,
        "E1": 0.02,
        "E2": 0.015,
        "E3": 0.015,
        "L1": 0.13,
        "L2": 0.13,
        "L3": 0.14,
        "V1": 0.05,
        "V2": 0.05,
    }

    # Reasoning credit comes only from quote-bound causal adjudication. Executed
    # repairs and smoke tests remain hard gates, independent of prose quality.
    semantic_ids = ("D1", "D2", "D3", "D4", "D5", "P1", "P2", "P3", "E3", "L1", "L2", "L3")
    for key in semantic_ids:
        atoms[key] = float(semantic["items"][key]["fraction"]) if semantic else 0.0
    for key, required in {"P1": ("repair_static_exports",), "P2": ("repair_relative_destinations", "repair_relocatable_config"), "P3": ("repair_relocatable_pc", "repair_pkg_dependencies")}.items():
        if not all(checks.get(k) for k in required): atoms[key] = 0.0
    checks["semantic_adjudication_completed"] = semantic is not None
    artifact_gates = all(checks.get(key, False) for key in REQUIRED_ARTIFACTS)
    report_structure_gate = report_records_commands(report) and report_records_results(report)
    integrity_gates = all(
        checks.get(key, False)
        for key in (
            "patch_parse", "patch_minimal", "reverse_patch", "preserve_cJSON.c", "preserve_cJSON.h",
            "preserve_cJSON_Utils.c", "preserve_cJSON_Utils.h", "preserve_failure_inputs",
            "no_build_residue", "patch_hygiene", "patch_original_match", "patch_roundtrip_match",
        )
    )
    validation_complete = baseline_validation_passed(validation)
    strict = (
        round(sum(weights[key] * float(fraction) for key, fraction in atoms.items()), 4)
        if artifact_gates and integrity_gates and report_structure_gate and report_ok and validation_complete
        else 0.0
    )
    return strict, atoms, checks


def score_workspace(value: str) -> dict:
    root = locate(value)
    base_checks = static_checks(root)
    validation = (
        run_validation(root)
        if all(base_checks.get(key, False) for key in REQUIRED_ARTIFACTS)
        else {}
    )
    if "validation_environment" in validation:
        raise RuntimeError(f"native validation unavailable: {validation['validation_environment']}")
    try:
        report = json.loads((root / "build_report.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        report = {}

    analysis_text = ""
    report_text = ""
    try:
        analysis_text = (root / "analysis" / "diagnosis.md").read_text(encoding="utf-8").lower()
        report_text = (root / "build_report.json").read_text(encoding="utf-8").lower()
    except OSError:
        pass

    semantic = None
    if all(base_checks.get(key, False) for key in REQUIRED_ARTIFACTS):
        from semantic_judge import adjudicate
        candidate = "DIAGNOSIS\n" + (root / "analysis/diagnosis.md").read_text(encoding="utf-8") + "\nREPORT\n" + (root / "build_report.json").read_text(encoding="utf-8")
        source = json.dumps({"baseline": json.loads((Path(__file__).parent / "semantic_source.json").read_text(encoding="utf-8")), "independent_repaired_validation": {k: v for k, v in validation.items() if isinstance(v, bool)}}, ensure_ascii=False)
        semantic = adjudicate(candidate, source)
    strict, atoms, checks = strict_aggregate(
        base_checks, validation, analysis_text, report_text, report, semantic
    )
    delivery = delivery_checks(root)
    lenient = lenient_score(delivery) if baseline_validation_passed(validation) else 0.0
    return {
        "reward": strict,
        "reward_strict": strict,
        "reward_lenient": lenient,
        "rewards": {"strict": strict, "lenient": lenient},
        "reward_formulas": {"strict": STRICT_FORMULA, "lenient": LENIENT_FORMULA},
        "checks": checks,
        "atoms": atoms,
        "delivery": delivery,
        "validation": validation,
        "semantic_judge": semantic,
    }


def write_scores(detail: dict, logs: Path) -> None:
    """The five files the harness reads, all from one computation so they agree."""
    logs.mkdir(parents=True, exist_ok=True)
    strict = float(detail["rewards"]["strict"])
    lenient = float(detail["rewards"]["lenient"])
    (logs / "reward.txt").write_text(f"{strict}\n")
    (logs / "reward_strict.txt").write_text(f"{strict}\n")
    (logs / "reward_lenient.txt").write_text(f"{lenient}\n")
    (logs / "reward.json").write_text(
        json.dumps(
            {"reward": strict, "reward_strict": strict, "reward_lenient": lenient},
            sort_keys=True,
        )
        + "\n"
    )
    (logs / "reward_detail.json").write_text(
        json.dumps(detail, indent=2, sort_keys=True) + "\n"
    )


def unmeasured_detail(value: str, error: Exception) -> dict:
    """Keep infrastructure failure distinct without publishing candidate rewards."""
    try:
        delivery = delivery_checks(locate(value))
        delivery_complete: bool | None = bool(lenient_score(delivery))
    except (OSError, AssertionError):
        delivery = {}
        delivery_complete = None
    return {
        "measurement_status": "UNMEASURED",
        "infrastructure_error": str(error),
        "reward": None,
        "reward_strict": None,
        "reward_lenient": None,
        "rewards": {"strict": None, "lenient": None},
        "candidate_delivery_diagnostic": {
            "complete": delivery_complete,
            "checks": delivery,
            "published_as_reward": False,
        },
    }


def write_unmeasured(detail: dict, logs: Path) -> None:
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "reward.txt").write_text("UNMEASURED\n")
    (logs / "reward_strict.txt").write_text("UNMEASURED\n")
    (logs / "reward_lenient.txt").write_text("UNMEASURED\n")
    (logs / "reward.json").write_text(json.dumps({
        "measurement_status": "UNMEASURED",
        "reward": None,
        "reward_strict": None,
        "reward_lenient": None,
    }, sort_keys=True) + "\n")
    (logs / "reward_detail.json").write_text(json.dumps(detail, indent=2, sort_keys=True) + "\n")


def test_equivalent_cmake_and_pkg_config_syntax() -> None:
    cmake = """
      install(TARGETS ${CJSON_LIB} EXPORT ${CJSON_LIB} ARCHIVE DESTINATION lib)
      install(TARGETS ${CJSON_LIB}-static EXPORT ${CJSON_LIB} ARCHIVE DESTINATION lib)
      install(TARGETS ${CJSON_UTILS_LIB} EXPORT ${CJSON_UTILS_LIB} LIBRARY DESTINATION lib)
      install(TARGETS ${CJSON_UTILS_LIB}-static EXPORT ${CJSON_UTILS_LIB} ARCHIVE DESTINATION lib)
    """
    assert {
        ("${CJSON_LIB}", "${CJSON_LIB}"),
        ("${CJSON_LIB}-static", "${CJSON_LIB}"),
        ("${CJSON_UTILS_LIB}", "${CJSON_UTILS_LIB}"),
        ("${CJSON_UTILS_LIB}-static", "${CJSON_UTILS_LIB}"),
    }.issubset(installed_export_pairs(cmake))
    core = pkg_config_fields("Libs.private:\t-pthread   -lm\n")
    utils = pkg_config_fields("requires: libcjson >= 1.7, zlib\n")
    assert "-lm" in shlex.split(core["libs.private"])
    assert "libcjson" in re.split(r"[\s,]+", utils["requires"])


def test_report_rejects_nested_failure_and_wrong_command_binding() -> None:
    assert not result_entry_passed({
        "status": "pass",
        "commands": [{"status": "pass", "nested": {"exit_code": 2}}],
    })
    report = {
        "commands": ["cmake --build unrelated-build"],
        "steps": {"cmake_consumer_build": {"status": "pass", "exit_code": 0}},
    }
    assert not _report_steps_have_evidence(report, ("cmake_consumer_build",))
    assert result_entry_passed({
        "command": "grep -R old-prefix moved-prefix",
        "exit_code": 1,
        "interpretation": "pass: no matches found",
    })
    assert not result_entry_passed({
        "command": "grep -R old-prefix moved-prefix",
        "exit_code": 2,
        "interpretation": "pass: no matches found",
    })
    assert not result_entry_passed({"command": "cmake --build build", "exit_code": 1, "status": "pass"})
    assert result_entry_passed({"command": "custom-negative-check", "exit_code": 7, "expected_exit_code": 7})
    assert report_passed({
        "result": "pass",
        "final_validation": [{"name": "consumer", "result": "pass", "exit_code": 0}],
    })
    assert not report_passed({
        "result": "pass",
        "final_validation": [{"name": "consumer", "result": "fail", "exit_code": 1}],
    })


def test_outputs():
    target = os.environ.get("DELIVERABLE", os.environ.get("AGENT_WORKSPACE", "/workspace"))
    try:
        detail = score_workspace(target)
    except RuntimeError as exc:
        detail = unmeasured_detail(target, exc)
        print(json.dumps(detail, indent=2, sort_keys=True))
        try:
            write_unmeasured(detail, Path(os.environ.get("VERIFIER_OUTPUT_DIR", "/logs/verifier")))
        except OSError:
            pass
        raise
    print(json.dumps(detail, indent=2, sort_keys=True))
    try:
        write_scores(detail, Path(os.environ.get("VERIFIER_OUTPUT_DIR", "/logs/verifier")))
    except OSError:
        pass
    assert detail["reward"] >= 0.0
    assert detail["reward_lenient"] in (0.0, 1.0)

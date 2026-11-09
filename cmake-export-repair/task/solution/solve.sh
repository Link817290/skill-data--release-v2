#!/usr/bin/env bash
set -euo pipefail

workspace_root=${WORKSPACE_ROOT:-/workspace}
project="$workspace_root/project"
analysis="$workspace_root/analysis/diagnosis.md"
patch_file="$workspace_root/patches/patch_0.diff"
report="$workspace_root/build_report.json"

# Establish the requested artifact shape before inspecting the failure.
mkdir -p "$workspace_root/analysis" "$workspace_root/patches"
: > "$analysis"
: > "$patch_file"
: > "$report"

python3 - "$workspace_root" "$(dirname "$0")" <<'PY'
from __future__ import annotations

import difflib
import datetime
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(sys.argv[1]).resolve()
project = root / "project"
analysis_path = root / "analysis" / "diagnosis.md"
patch_path = root / "patches" / "patch_0.diff"
report_path = root / "build_report.json"

source_paths = [
    Path("CMakeLists.txt"),
    Path("library_config/cJSONConfig.cmake.in"),
    Path("library_config/libcjson.pc.in"),
    Path("library_config/libcjson_utils.pc.in"),
]
original = {path: (project / path).read_text(encoding="utf-8") for path in source_paths}
failure_materials = [
    path.read_text(encoding="utf-8", errors="replace")
    for path in sorted((root / "failure").iterdir())
    if path.is_file()
]
joined_failures = "\n".join(failure_materials)
required_evidence = (
    "-DBUILD_SHARED_AND_STATIC_LIBS=ON",
    "cmake --build",
    "PKG_CONFIG_PATH",
    "CMAKE_INSTALL_LIBDIR=lib/x86_64-linux-gnu",
    "CMAKE_INSTALL_INCLUDEDIR=include/sdk",
)
if not all(token in joined_failures for token in required_evidence):
    raise SystemExit("the supplied commands do not cover the required workflows")

# The issued packet contains commands, not captured stderr logs. Establish the
# diagnoses against the unchanged producer before applying the repair.
sys.path.insert(0, sys.argv[2])
from reproduce_failures import reproduce
failure_logs, before_reproduction = reproduce(project)
source_hashes = {
    path.relative_to(project).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in sorted(project.rglob("*"))
    if path.is_file()
}
(root / "failure" / "fresh-reproduction.json").write_text(
    json.dumps(
        {
            "kind": "fresh_reproduction_not_historical",
            "date": datetime.date.today().isoformat(),
            "platform": platform.platform(),
            "cmake": subprocess.check_output(["cmake", "--version"], text=True).splitlines()[0],
            "source_sha256": source_hashes,
            "records": before_reproduction,
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)

repaired = dict(original)
static_install = re.compile(
    r'(?m)^(?P<indent>[ \t]*)install\(TARGETS "(?P<var>\$\{[A-Za-z0-9_]+_LIB\})-static" '
    r'DESTINATION "(?P<dest>\$\{CMAKE_INSTALL_FULL_LIBDIR\})"\)\s*$'
)


def expand_static_install(match: re.Match[str]) -> str:
    indent = match.group("indent")
    variable = match.group("var")
    return (
        f'{indent}install(TARGETS "{variable}-static"\n'
        f'{indent}    EXPORT "{variable}"\n'
        f'{indent}    ARCHIVE DESTINATION "${{CMAKE_INSTALL_LIBDIR}}"\n'
        f'{indent}    INCLUDES DESTINATION "${{CMAKE_INSTALL_INCLUDEDIR}}"\n'
        f'{indent})'
    )


cmake, export_repairs = static_install.subn(expand_static_install, repaired[Path("CMakeLists.txt")])
if export_repairs < 2:
    raise SystemExit("could not derive both missing static export declarations")
for full, relative in (
    ("CMAKE_INSTALL_FULL_LIBDIR", "CMAKE_INSTALL_LIBDIR"),
    ("CMAKE_INSTALL_FULL_INCLUDEDIR", "CMAKE_INSTALL_INCLUDEDIR"),
    ("CMAKE_INSTALL_FULL_BINDIR", "CMAKE_INSTALL_BINDIR"),
):
    cmake = cmake.replace(full, relative)

pc_configure = (
    'configure_file("${CMAKE_CURRENT_SOURCE_DIR}/library_config/libcjson.pc.in"\n'
    '    "${CMAKE_CURRENT_BINARY_DIR}/libcjson.pc" @ONLY)'
)
pc_configure_relocatable = (
    'file(RELATIVE_PATH CJSON_PC_PREFIX\n'
    '    "${CMAKE_INSTALL_PREFIX}/${CMAKE_INSTALL_LIBDIR}/pkgconfig"\n'
    '    "${CMAKE_INSTALL_PREFIX}")\n\n'
    + pc_configure
)
if pc_configure not in cmake:
    raise SystemExit("could not derive the pkg-config metadata-to-prefix relationship")
cmake = cmake.replace(pc_configure, pc_configure_relocatable, 1)

config_generation = (
    'configure_file(\n'
    '    "${CMAKE_CURRENT_SOURCE_DIR}/library_config/cJSONConfig.cmake.in"\n'
    '    ${PROJECT_BINARY_DIR}/cJSONConfig.cmake @ONLY)'
)
config_generation_relocatable = (
    'include(CMakePackageConfigHelpers)\n'
    'configure_package_config_file(\n'
    '    "${CMAKE_CURRENT_SOURCE_DIR}/library_config/cJSONConfig.cmake.in"\n'
    '    ${PROJECT_BINARY_DIR}/cJSONConfig.cmake\n'
    '    INSTALL_DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/cJSON"\n'
    '    PATH_VARS CMAKE_INSTALL_INCLUDEDIR)'
)
if config_generation not in cmake:
    raise SystemExit("could not derive relocatable package-config generation")
cmake = cmake.replace(config_generation, config_generation_relocatable, 1)
repaired[Path("CMakeLists.txt")] = cmake

config_path = Path("library_config/cJSONConfig.cmake.in")
config = repaired[config_path]
absolute_include_block = (
    '# The include directories used by cJSON\n'
    'set(CJSON_INCLUDE_DIRS "@CMAKE_INSTALL_FULL_INCLUDEDIR@")\n'
    'set(CJSON_INCLUDE_DIR "@CMAKE_INSTALL_FULL_INCLUDEDIR@")'
)
relative_include_block = (
    '# The include directories used by cJSON\n'
    'set_and_check(CJSON_INCLUDE_DIRS "@PACKAGE_CMAKE_INSTALL_INCLUDEDIR@")\n'
    'set(CJSON_INCLUDE_DIR "${CJSON_INCLUDE_DIRS}")'
)
if absolute_include_block not in config:
    raise SystemExit("could not derive the relocatable CMake config include prefix")
repaired[config_path] = "@PACKAGE_INIT@\n\n" + config.replace(absolute_include_block, relative_include_block, 1)

pc_paths = [Path("library_config/libcjson.pc.in"), Path("library_config/libcjson_utils.pc.in")]
for pc_path in pc_paths:
    pc = repaired[pc_path]
    absolute_pc = "libdir=@CMAKE_INSTALL_FULL_LIBDIR@\nincludedir=@CMAKE_INSTALL_FULL_INCLUDEDIR@"
    relative_pc = (
        "prefix=${pcfiledir}/@CJSON_PC_PREFIX@\n"
        "libdir=${prefix}/@CMAKE_INSTALL_LIBDIR@\n"
        "includedir=${prefix}/@CMAKE_INSTALL_INCLUDEDIR@"
    )
    if absolute_pc not in pc:
        raise SystemExit(f"could not derive a relocatable prefix for {pc_path}")
    repaired[pc_path] = pc.replace(absolute_pc, relative_pc, 1)

patch_parts: list[str] = []
for path in source_paths:
    if repaired[path] == original[path]:
        continue
    patch_parts.extend(
        difflib.unified_diff(
            original[path].splitlines(keepends=True),
            repaired[path].splitlines(keepends=True),
            fromfile=f"a/{path.as_posix()}",
            tofile=f"b/{path.as_posix()}",
        )
    )
patch_path.write_text("".join(patch_parts), encoding="utf-8")

apply_result = subprocess.run(
    ["patch", "--batch", "-p1", "-i", str(patch_path)],
    cwd=project,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)
if apply_result.returncode != 0:
    raise SystemExit(f"could not apply generated patch:\n{apply_result.stdout}")
applied_files_match_generated_repair = all(
    (project / path).read_text(encoding="utf-8") == expected
    for path, expected in repaired.items()
)
if not applied_files_match_generated_repair:
    raise SystemExit("applied project does not match the generated repair")

target_re = re.compile(r'install\(TARGETS "\$\{([A-Za-z0-9_]+_LIB)\}-static')
targets = sorted(
    {match.group(1).lower().removesuffix("_lib") + "-static" for match in target_re.finditer(cmake)}
)
old_prefix = "<pre-repair-prefix>"

analysis_path.write_text(
    "# Build diagnosis\n\n"
    "## Failure boundaries\n\n"
    "Fresh pre-repair reproductions expose downstream configure and link failures across three producer-metadata "
    "contracts, not defects in "
    "the C implementation. The first is a link failure: the package never creates the "
    "`cjson_utils-static` imported target, so CMake treats that identifier as the raw linker "
    "name `-lcjson_utils-static`. The archives exist under deliberately preserved output names, "
    "which rules out a producer compile failure.\n\n"
    "The fresh relocation reproductions fail earlier, during downstream CMake configuration. Their generated "
    f"import file references `{old_prefix}` after that staging prefix was removed. The `.pc` "
    "query independently emits include and library flags rooted at the removed prefix, causing "
    "the compiler to miss a public header. A successful producer build and package discovery "
    "therefore do not close either consumption contract. The second relocation deliberately "
    "uses the multi-component library directory `lib/x86_64-linux-gnu` and the selected include "
    "directory `include/sdk`; a fixed number of parent traversals that only fits `lib/pkgconfig` "
    "would misidentify `<moved-prefix>/lib` as the package prefix in that layout. For example, "
    "applying a fixed `../..` to `<moved-prefix>/lib/x86_64-linux-gnu/pkgconfig` yields "
    "`<moved-prefix>/lib`, not `<moved-prefix>`. With the selected `includedir=include/sdk`, "
    "the wrong prefix produces `<moved-prefix>/lib/include/sdk` instead of "
    "`<moved-prefix>/include/sdk`; the library path becomes "
    "`<moved-prefix>/lib/lib/x86_64-linux-gnu` instead of "
    "`<moved-prefix>/lib/x86_64-linux-gnu`. A consumer can then fail to find "
    "`cjson/cJSON_Utils.h` at compile time or the libraries at link time even though "
    "the installed files exist in the correct relocated layout.\n\n"
    "## Owning declarations and repair\n\n"
    "The static targets were installed as files but omitted from the export sets; `cjson_utils-static` "
    "transitively links `cjson-static`, so both public target identifiers must be exported together while "
    "their output names stay stable. "
    "Separately, absolute `CMAKE_INSTALL_FULL_*` destinations capture the removed staging prefix in generated import "
    "metadata. Relative GNUInstallDirs destinations allow CMake's generated `_IMPORT_PREFIX` to "
    "follow the current package location. For the legacy variables, `configure_package_config_file` "
    "derives `PACKAGE_PREFIX_DIR` from the configured install destination and expands the selected "
    "include directory through `PATH_VARS`; this relationship remains correct when the library "
    "directory has more than one path component. In particular, the legacy `CJSON_INCLUDE_DIRS` "
    "must be `<moved-prefix>/include/sdk` for the nondefault layout. The configured "
    "`INSTALL_DESTINATION=${CMAKE_INSTALL_LIBDIR}/cmake/cJSON` tells "
    "`configure_package_config_file` the package-config location relative to the prefix. "
    "Its `@PACKAGE_INIT@` code recovers `PACKAGE_PREFIX_DIR` from the loaded config file's "
    "current directory, with the depth determined by that selected install destination. "
    "`PATH_VARS CMAKE_INSTALL_INCLUDEDIR` then expands `@PACKAGE_CMAKE_INSTALL_INCLUDEDIR@` "
    "relative to that recovered prefix, so `set_and_check(CJSON_INCLUDE_DIRS ...)` yields "
    "the relocated `include/sdk`, not the old staging prefix or a lib-prefixed include path. "
    "The singular `CJSON_INCLUDE_DIR` remains an alias of this checked include root.\n\n"
    "The two pkg-config templates are a metadata contract separate from the CMake exports. Their stale include and library flags point to the removed prefix; their prefix is now derived "
    "from `${pcfiledir}`. The producer computes `CJSON_PC_PREFIX` as the relative path from the "
    "actual `${CMAKE_INSTALL_LIBDIR}/pkgconfig` install location back to the prefix, while the "
    "templates preserve the configured relative `libdir` and `includedir` names. The existing "
    "`Requires: libcjson` dependency declaration and core `Libs.private: -lm` edge remain unchanged. Editing a "
    "consumer search path, renaming archives, or patching generated metadata would only hide the "
    "producer defect. The patch preserves public target identifiers, archive output names, shared "
    "library behavior, and all implementation/header bytes.\n\n"
    "## Evidence closure and limits\n\n"
    "Validation starts from fresh producer copies and staging prefixes, moves each installed tree, "
    "deletes each original prefix, and uses only the moved package. The default layout has independent "
    "CMake shared-core and static-utility consumers plus a pkg-config consumer. The multi-component "
    "library layout checks the legacy CMake include variable, builds and runs the static target, and "
    "queries, builds, and runs through pkg-config. This smoke scope establishes the captured "
    "configure/link/load paths and two requested layouts, not general ABI compatibility, alternate "
    "generators, platforms, or untested package-manager conventions.\n\n"
    "The original evidence bundle supplied commands but omitted historical stdout/stderr. "
    "`failure/fresh-reproduction.json` contains newly executed commands, exit statuses, output tails, "
    "and source hashes; these are fresh local reproductions, not recovered historical records.\n",
    encoding="utf-8",
)

commands: list[str] = []
steps: dict[str, dict[str, object]] = {}


def run(label: str, argv: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    command = shlex.join(argv)
    commands.append(command)
    proc = subprocess.run(
        argv,
        env=env,
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    steps[label] = {
        "status": "pass" if proc.returncode == 0 else "fail",
        "command": command,
        "exit_code": proc.returncode,
        "output_tail": proc.stdout[-2000:],
        "working_directory": "<workspace-root>",
    }
    return proc


def require(label: str, proc: subprocess.CompletedProcess[str]) -> None:
    if proc.returncode != 0:
        raise RuntimeError(f"{label} failed:\n{proc.stdout[-2000:]}")


overall = "deferred"
validation_summary: dict[str, object] = {}
if shutil.which("cmake") is None or shutil.which("pkg-config") is None:
    steps["environment"] = {"status": "deferred", "reason": "toolchain is supplied by the task image"}
else:
    try:
        with tempfile.TemporaryDirectory(prefix="cmake-export-repair-") as tmp:
            base = Path(tmp)
            producer = base / "producer"
            shutil.copytree(project, producer)
            build = base / "build"
            prefix_a = base / "stage-a"
            prefix_b = base / "stage-b"
            require(
                "producer_configure",
                run(
                    "producer_configure",
                    [
                        "cmake", "-S", str(producer), "-B", str(build),
                        "-DBUILD_SHARED_AND_STATIC_LIBS=ON", "-DENABLE_CJSON_UTILS=ON",
                        "-DENABLE_TARGET_EXPORT=ON", "-DENABLE_CJSON_TEST=OFF",
                        f"-DCMAKE_INSTALL_PREFIX={prefix_a}",
                    ],
                ),
            )
            require("producer_build", run("producer_build", ["cmake", "--build", str(build), "-j2"]))
            require("install", run("install", ["cmake", "--install", str(build)]))
            shutil.copytree(prefix_a, prefix_b)
            shutil.rmtree(prefix_a)
            commands.extend([f"cp -a {prefix_a} {prefix_b}", f"rm -rf {prefix_a}"])
            steps["prefix_relocation"] = {
                "status": "pass",
                "commands": [f"cp -a {prefix_a} {prefix_b}", f"rm -rf {prefix_a}"],
                "original_removed": not prefix_a.exists(),
            }

            metadata_files = sorted((prefix_b / "lib").rglob("*.cmake")) + sorted((prefix_b / "lib").rglob("*.pc"))
            stale = [str(path) for path in metadata_files if str(prefix_a) in path.read_text(encoding="utf-8", errors="replace")]
            steps["metadata_scan"] = {"status": "pass" if not stale else "fail", "stale_files": stale}
            if stale:
                raise RuntimeError(f"moved metadata still references the removed prefix: {stale}")

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
            require(
                "cmake_consumer_configure",
                run(
                    "cmake_consumer_configure",
                    ["cmake", "-S", str(consumer), "-B", str(consumer_build), f"-DCMAKE_PREFIX_PATH={prefix_b}"],
                ),
            )
            require(
                "cmake_consumer_build",
                run("cmake_consumer_build", ["cmake", "--build", str(consumer_build), "-j2"]),
            )
            require("shared_smoke", run("shared_smoke", [str(consumer_build / "shared_smoke")]))
            require("static_utils_smoke", run("static_utils_smoke", [str(consumer_build / "static_utils_smoke")]))

            pkg_env = os.environ.copy()
            pkg_env["PKG_CONFIG_PATH"] = str(prefix_b / "lib" / "pkgconfig")
            pkg_query = run("pkg_config_query", ["pkg-config", "--cflags", "--libs", "libcjson_utils"], env=pkg_env)
            require("pkg_config_query", pkg_query)
            pkg_flags = pkg_query.stdout.strip()
            if str(prefix_a) in pkg_flags:
                raise RuntimeError("pkg-config emitted the removed prefix")
            pkg_static_query = run(
                "pkg_config_static_query", ["pkg-config", "--static", "--libs", "libcjson_utils"], env=pkg_env
            )
            require("pkg_config_static_query", pkg_static_query)
            if str(prefix_a) in pkg_static_query.stdout or "-lm" not in shlex.split(pkg_static_query.stdout):
                raise RuntimeError("pkg-config static flags are stale or omit the private math dependency")
            pkg_source = base / "pkg-consumer.c"
            pkg_source.write_text(
                "#include <cjson/cJSON_Utils.h>\n"
                "int main(void) { cJSON *root = cJSON_CreateObject(); "
                "int ok = cJSONUtils_GetPointer(root, \"\") == root; cJSON_Delete(root); return ok ? 0 : 1; }\n",
                encoding="utf-8",
            )
            pkg_smoke = base / "pkg-smoke"
            require(
                "pkg_config_consumer_build",
                run(
                    "pkg_config_consumer_build",
                    ["cc", str(pkg_source), "-o", str(pkg_smoke), *shlex.split(pkg_flags)],
                ),
            )
            smoke_env = os.environ.copy()
            smoke_env["LD_LIBRARY_PATH"] = str(prefix_b / "lib")
            require("pkg_config_smoke", run("pkg_config_smoke", [str(pkg_smoke)], env=smoke_env))

            layout_build = base / "layout-build"
            layout_prefix_a = base / "layout-stage-a"
            layout_prefix_b = base / "layout-stage-b"
            layout_libdir = Path("lib/x86_64-linux-gnu")
            layout_includedir = Path("include/sdk")
            require(
                "layout_producer_configure",
                run(
                    "layout_producer_configure",
                    [
                        "cmake", "-S", str(producer), "-B", str(layout_build),
                        "-DBUILD_SHARED_AND_STATIC_LIBS=ON", "-DENABLE_CJSON_UTILS=ON",
                        "-DENABLE_TARGET_EXPORT=ON", "-DENABLE_CJSON_TEST=OFF",
                        f"-DCMAKE_INSTALL_PREFIX={layout_prefix_a}",
                        f"-DCMAKE_INSTALL_LIBDIR={layout_libdir}",
                        f"-DCMAKE_INSTALL_INCLUDEDIR={layout_includedir}",
                    ],
                ),
            )
            require(
                "layout_producer_build",
                run("layout_producer_build", ["cmake", "--build", str(layout_build), "-j2"]),
            )
            require("layout_install", run("layout_install", ["cmake", "--install", str(layout_build)]))
            shutil.copytree(layout_prefix_a, layout_prefix_b)
            shutil.rmtree(layout_prefix_a)
            commands.extend([f"cp -a {layout_prefix_a} {layout_prefix_b}", f"rm -rf {layout_prefix_a}"])
            steps["layout_prefix_relocation"] = {
                "status": "pass",
                "commands": [
                    f"cp -a {layout_prefix_a} {layout_prefix_b}",
                    f"rm -rf {layout_prefix_a}",
                ],
                "original_removed": not layout_prefix_a.exists(),
                "libdir": str(layout_libdir),
                "includedir": str(layout_includedir),
            }

            layout_metadata = sorted(layout_prefix_b.rglob("*.cmake")) + sorted(layout_prefix_b.rglob("*.pc"))
            layout_stale = [
                str(path)
                for path in layout_metadata
                if str(layout_prefix_a) in path.read_text(encoding="utf-8", errors="replace")
            ]
            steps["layout_metadata_scan"] = {
                "status": "pass" if not layout_stale else "fail",
                "stale_files": layout_stale,
            }
            if layout_stale:
                raise RuntimeError(f"multi-component layout metadata retains the removed prefix: {layout_stale}")

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
            require(
                "layout_cmake_consumer_configure",
                run(
                    "layout_cmake_consumer_configure",
                    [
                        "cmake", "-S", str(layout_consumer), "-B", str(layout_consumer_build),
                        f"-DCMAKE_PREFIX_PATH={layout_prefix_b}",
                    ],
                ),
            )
            require(
                "layout_cmake_consumer_build",
                run("layout_cmake_consumer_build", ["cmake", "--build", str(layout_consumer_build), "-j2"]),
            )
            require("layout_cmake_smoke", run("layout_cmake_smoke", [str(layout_consumer_build / "layout_smoke")]))

            layout_pkg_env = os.environ.copy()
            layout_pkg_env["PKG_CONFIG_LIBDIR"] = str(layout_prefix_b / layout_libdir / "pkgconfig")
            layout_pkg_env.pop("PKG_CONFIG_PATH", None)
            layout_query = run(
                "layout_pkg_config_query",
                ["pkg-config", "--cflags", "--libs", "libcjson_utils"],
                env=layout_pkg_env,
            )
            require("layout_pkg_config_query", layout_query)
            layout_flags = layout_query.stdout.strip()
            if str(layout_prefix_a) in layout_flags:
                raise RuntimeError("multi-component pkg-config flags retain the removed prefix")
            layout_static_query = run(
                "layout_pkg_config_static_query",
                ["pkg-config", "--static", "--libs", "libcjson_utils"],
                env=layout_pkg_env,
            )
            require("layout_pkg_config_static_query", layout_static_query)
            if str(layout_prefix_a) in layout_static_query.stdout or "-lm" not in shlex.split(layout_static_query.stdout):
                raise RuntimeError("multi-component static pkg-config flags are stale or omit -lm")
            layout_pkg_smoke = base / "layout-pkg-smoke"
            require(
                "layout_pkg_config_consumer_build",
                run(
                    "layout_pkg_config_consumer_build",
                    ["cc", str(layout_consumer / "main.c"), "-o", str(layout_pkg_smoke), *shlex.split(layout_flags)],
                ),
            )
            layout_smoke_env = os.environ.copy()
            layout_smoke_env["LD_LIBRARY_PATH"] = str(layout_prefix_b / layout_libdir)
            require(
                "layout_pkg_config_smoke",
                run("layout_pkg_config_smoke", [str(layout_pkg_smoke)], env=layout_smoke_env),
            )

            validation_summary = {
                "moved_prefix_only": True,
                "old_prefix_removed": True,
                "cmake_targets": ["cjson", *targets],
                "pkg_config_module": "libcjson_utils",
                "pkg_config_flags": pkg_flags.replace(str(base), "<validation-root>"),
                "multi_component_layout": {
                    "libdir": str(layout_libdir),
                    "includedir": str(layout_includedir),
                    "old_prefix_removed": True,
                    "legacy_cmake_include_checked": True,
                    "cmake_static_consumer": "pass",
                    "pkg_config_consumer": "pass",
                    "pkg_config_flags": layout_flags.replace(str(base), "<validation-root>"),
                },
            }
            overall = "pass"
            commands = [command.replace(str(base), "<validation-root>") for command in commands]
            for step in steps.values():
                if isinstance(step.get("command"), str):
                    step["command"] = step["command"].replace(str(base), "<validation-root>")
                if isinstance(step.get("commands"), list):
                    step["commands"] = [item.replace(str(base), "<validation-root>") for item in step["commands"]]
    except RuntimeError as exc:
        overall = "fail"
        validation_summary["failure"] = str(exc)

report_path.write_text(
    json.dumps(
        {
            "status": overall,
            "before_reproduction": before_reproduction,
            "validation_identity": {
                "source_snapshot_sha256": hashlib.sha256(
                    json.dumps(source_hashes, sort_keys=True).encode("utf-8")
                ).hexdigest(),
                "patch_path": "patches/patch_0.diff",
                "patch_sha256": hashlib.sha256(patch_path.read_bytes()).hexdigest(),
                "patch_application": {
                    "status": "pass" if apply_result.returncode == 0 else "fail",
                    "exit_code": apply_result.returncode,
                    "applied_files_match_generated_repair": applied_files_match_generated_repair,
                },
                "toolchain": {
                    "cmake": subprocess.check_output(["cmake", "--version"], text=True).splitlines()[0],
                    "compiler": subprocess.check_output(["cc", "--version"], text=True).splitlines()[0],
                    "pkg_config": subprocess.check_output(["pkg-config", "--version"], text=True).strip(),
                },
            },
            "commands": commands,
            "validation_scope": (
                "fresh producer build, staged install, removed original prefix, moved-prefix CMake shared/static "
                "consumers, moved-prefix pkg-config compile/run, and the same CMake legacy-variable and pkg-config "
                "checks under a multi-component library directory"
            ),
            "exported_static_targets": targets,
            "relocation": validation_summary,
            "steps": steps,
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)

if overall == "fail":
    raise SystemExit("validation failed; see build_report.json")
PY

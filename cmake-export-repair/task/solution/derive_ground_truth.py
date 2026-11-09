#!/usr/bin/env python3
"""Derive the structural test expectations from the generated gold report."""
import json
from pathlib import Path


def main() -> None:
    package = Path(__file__).resolve().parents[2]
    report = json.loads((package / "golden" / "build_report.json").read_text())
    targets = report.get("exported_static_targets", [])
    if not targets:
        raise SystemExit("gold report has no exported static targets")
    relocation = report.get("relocation", {})
    if not relocation.get("moved_prefix_only") or not relocation.get("old_prefix_removed"):
        raise SystemExit("gold report has no closed moved-prefix validation")
    layout = relocation.get("multi_component_layout", {})
    if (
        layout.get("cmake_static_consumer") != "pass"
        or layout.get("pkg_config_consumer") != "pass"
        or not layout.get("legacy_cmake_include_checked")
    ):
        raise SystemExit("gold report has no closed multi-component layout validation")
    (package / "task" / "tests" / "ground_truth.json").write_text(
        json.dumps(
            {
                "required_static_targets": sorted(targets),
                "producer": "pass",
                "moved_cmake_consumers": ["shared", "static-utils"],
                "moved_pkg_config_consumer": "pass",
                "old_prefix_removed": True,
                "layout_libdir": layout.get("libdir"),
                "layout_includedir": layout.get("includedir"),
                "layout_cmake_legacy_include": "pass",
                "layout_pkg_config_consumer": "pass",
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()

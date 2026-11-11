#!/usr/bin/env python3
"""Regression tests for the editable-DXF verifier."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import validator

TASK_ROOT = Path(__file__).resolve().parents[1]
GOLDEN = TASK_ROOT / "golden/electrical_drawings.dxf"
if not GOLDEN.is_file():
    GOLDEN = TASK_ROOT.parent / "golden/electrical_drawings.dxf"


def minimal_dxf(entities: str) -> str:
    return (
        "0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1009\n"
        "0\nENDSEC\n0\nSECTION\n2\nENTITIES\n"
        + entities
        + "0\nENDSEC\n0\nEOF\n"
    )


def text_entity(value: str, x: float, y: float) -> str:
    return f"0\nTEXT\n8\nTEXT\n10\n{x}\n20\n{y}\n40\n20\n1\n{value}\n"


class ValidatorTests(unittest.TestCase):
    def test_golden_is_perfect(self):
        result = validator.score(GOLDEN)
        self.assertEqual(result["rewards"], {"strict": 1.0, "lenient": 1.0})
        self.assertEqual(result["dimension_scores"]["semantic_content"], 1.0)
        self.assertEqual(result["dimension_scores"]["diagram_topology"], 1.0)
        self.assertLess(result["raw_dimension_scores"]["semantic_content"], 1.0)

    def test_valid_but_empty_dxf_gets_no_format_reward(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.dxf"
            path.write_text(minimal_dxf(""), encoding="ascii")
            result = validator.score(path)
        self.assertTrue(result["must_have"]["valid_editable_dxf"])
        self.assertGreater(result["dimension_scores"]["vector_delivery"], 0.0)
        self.assertEqual(result["rewards"]["strict"], 0.0)

    def test_coherent_partial_row_requires_critical_fields_and_unique_key(self):
        hits = {
            "key": True,
            "load_name": True,
            "capacity_kw": True,
            "phase_sequence": False,
            "breaker": True,
            "conductor_conduit": True,
        }
        self.assertEqual(validator.coherent_row_quality(hits, True), 0.8)
        self.assertEqual(validator.coherent_row_quality(hits, False), 0.0)

        missing_breaker = dict(hits)
        missing_breaker["breaker"] = False
        missing_breaker["phase_sequence"] = True
        self.assertEqual(
            sum(missing_breaker[field] for field in validator.ROW_FIELDS), 4
        )
        self.assertEqual(validator.coherent_row_quality(missing_breaker, True), 0.0)

    def test_missing_file_is_zero(self):
        result = validator.score(Path("/does/not/exist.dxf"))
        self.assertEqual(result["rewards"], {"strict": 0.0, "lenient": 0.0})

    def test_entities_word_outside_real_section_is_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "marker-only.dxf"
            path.write_text(
                "0\nSECTION\n2\nHEADER\n999\nENTITIES\n0\nENDSEC\n0\nEOF\n",
                encoding="ascii",
            )
            result = validator.score(path)
        self.assertEqual(result["rewards"], {"strict": 0.0, "lenient": 0.0})
        self.assertIn("missing ENTITIES section", result["errors"])

    def test_arc_and_circle_are_distinct_supported_entities(self):
        entities = (
            "0\nLINE\n8\nWIRE\n10\n0\n20\n0\n11\n10\n21\n0\n"
            "0\nCIRCLE\n8\nDEVICE\n10\n5\n20\n5\n40\n2\n"
            "0\nARC\n8\nDEVICE\n10\n8\n20\n8\n40\n3\n50\n0\n51\n90\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "native.dxf"
            path.write_text(minimal_dxf(entities), encoding="ascii")
            parsed, errors = validator.parse_dxf(path)
        self.assertEqual(errors, [])
        self.assertEqual([entity["type"] for entity in parsed], ["LINE", "CIRCLE", "ARC"])
        self.assertNotIn("40", parsed[0]["values"])

    def test_dense_scanline_facsimile_is_rejected(self):
        entities = [text_entity("TRACE", 0, 0)]
        entities.extend(
            f"0\nLINE\n8\nINK\n10\n0\n20\n{index}\n11\n100\n21\n{index}\n"
            for index in range(5001)
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scanlines.dxf"
            path.write_text(minimal_dxf("".join(entities)), encoding="ascii")
            result = validator.score(path)
        self.assertEqual(result["rewards"]["strict"], 0.0)
        self.assertTrue(result["anti_gaming"]["raster_trace_suspected"])
        self.assertFalse(result["must_have"]["no_raster_equivalent_trace"])

    def test_anchor_and_random_line_stuffing_cannot_claim_topology(self):
        sheet_anchors = [
            (("图纸目录", "电气施工图设计说明", "图例"), 0, 10000),
            (("1AL1", "2AL1", "2AL2"), 10000, 10000),
            (("引至楼层应急照明配电箱", "主入口", "财富管理室"), 0, 0),
            (("配电间", "总经理室", "等候室"), 10000, 0),
        ]
        entities = []
        for anchors, origin_x, origin_y in sheet_anchors:
            for offset, anchor in enumerate(anchors):
                entities.append(text_entity(anchor, origin_x + offset * 25, origin_y))
            for index in range(100):
                x = origin_x + index * 7
                y = origin_y + 200 + index * 3
                entities.append(
                    f"0\nLINE\n8\nFILL\n10\n{x}\n20\n{y}\n11\n{x + 2}\n21\n{y + 1}\n"
                )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stuffed.dxf"
            path.write_text(minimal_dxf("".join(entities)), encoding="utf-8")
            result = validator.score(path)
        self.assertLess(result["dimension_scores"]["diagram_topology"], 0.50)
        self.assertLess(result["rewards"]["strict"], 0.60)

    def test_raster_entity_invalidates_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.dxf"
            raw = GOLDEN.read_bytes()
            section_start = raw.index(b"  2\nENTITIES")
            section_end = raw.index(b"  0\nENDSEC", section_start)
            raw = raw[:section_end] + b"  0\nIMAGE\n  8\nUNDERLAY\n" + raw[section_end:]
            path.write_bytes(raw)
            result = validator.score(path)
        self.assertEqual(result["rewards"]["strict"], 0.0)
        self.assertEqual(result["rewards"]["lenient"], 0.0)
        self.assertFalse(result["must_have"]["no_raster_underlay"])

    def test_wrong_row_loses_exact_credit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wrong.dxf"
            raw = GOLDEN.read_bytes().replace("WDZ-YJY-5x6,SC32".encode("gb18030"), "WRONG-CABLE".encode("gb18030"), 1)
            path.write_bytes(raw)
            result = validator.score(path)
        self.assertLess(result["counts"]["exact_circuit_rows"], 29)
        self.assertLess(result["rewards"]["strict"], 1.0)

    def test_extra_circuit_candidate_reduces_precision(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stuffed-row.dxf"
            raw = GOLDEN.read_bytes()
            section_start = raw.index(b"  2\nENTITIES")
            section_end = raw.index(b"  0\nENDSEC", section_start)
            extra = (
                b"  0\nTEXT\n  8\nTEXT\n 10\n276500\n 20\n"
                b"1358748.7\n 40\n100\n  1\nWX999\n"
            )
            path.write_bytes(raw[:section_end] + extra + raw[section_end:])
            result = validator.score(path)
        self.assertEqual(result["counts"]["submitted_circuit_keys"], 30)
        self.assertLess(result["precision_recall"]["circuit_keys"]["precision"], 1.0)
        self.assertLess(result["precision_recall"]["exact_rows"]["precision"], 1.0)

    def test_one_missing_sheet_anchor_fails_four_sheet_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "incomplete.dxf"
            raw = GOLDEN.read_bytes().replace("电气施工图设计说明".encode("utf-8"), "REMOVED-SHEET-ANCHOR".encode("utf-8"), 1)
            path.write_bytes(raw)
            result = validator.score(path)
        self.assertLess(result["rewards"]["strict"], 1.0)
        self.assertGreaterEqual(result["counts"]["complete_sheet_regions"], 3)
        self.assertEqual(result["rewards"]["lenient"], 0.0)
        self.assertFalse(result["must_have"]["all_issued_sheets_represented"])


if __name__ == "__main__":
    unittest.main()

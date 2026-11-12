import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deliverable_gate


class DeliveryRootTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(
            (Path(__file__).with_name("deliverable_gate.json")).read_text(encoding="utf-8")
        )

    @staticmethod
    def touch(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"candidate")

    def test_workspace_files_are_not_deliverables(self):
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            self.touch(workspace / "output" / "post_hearing_argument.docx")
            self.touch(workspace / "build_argument.py")
            self.touch(workspace / "trajectory.md")

            verdict = deliverable_gate.check(workspace, self.config)

            self.assertEqual(Path(verdict["root"]), workspace / "output")
            self.assertEqual(verdict["missing"], [])
            self.assertEqual(verdict["extra"], [])

    def test_extra_file_inside_output_is_charged(self):
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            self.touch(workspace / "output" / "post_hearing_argument.docx")
            self.touch(workspace / "output" / "alternate.docx")

            verdict = deliverable_gate.check(workspace, self.config)

            self.assertEqual(verdict["extra"], ["alternate.docx"])

    def test_archived_artifacts_output_is_resolved(self):
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            self.touch(workspace / "artifacts" / "output" / "post_hearing_argument.docx")
            self.touch(workspace / "build_argument.py")

            verdict = deliverable_gate.check(workspace, self.config)

            self.assertEqual(Path(verdict["root"]), workspace / "artifacts" / "output")
            self.assertEqual(verdict["missing"], [])
            self.assertEqual(verdict["extra"], [])

    def test_existing_empty_output_cannot_be_bypassed(self):
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            (workspace / "output").mkdir()
            self.touch(workspace / "post_hearing_argument.docx")

            verdict = deliverable_gate.check(workspace, self.config)

            self.assertEqual(Path(verdict["root"]), workspace / "output")
            self.assertEqual(verdict["missing"], ["post_hearing_argument.docx"])


if __name__ == "__main__":
    unittest.main()

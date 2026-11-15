from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest


TESTS_DIR = Path(__file__).resolve().parent
TASK_DIR = TESTS_DIR.parent
TEST_SCRIPT = TESTS_DIR / "test.sh"
DOCKERFILE = TASK_DIR / "environment" / "Dockerfile"
SKILL = TASK_DIR / "environment" / "skills" / "boq-scope-and-measurement" / "SKILL.md"
INSTRUCTION = TASK_DIR / "instruction.md"
GOLD = TASK_DIR / "solution" / "golden_output.xlsx"
DELIVERABLE = "边坡支护专业分包招标清单.xlsx"


def shell_path(path: Path) -> str:
    resolved = path.resolve()
    if os.name == "nt":
        return f"/{resolved.drive[0].lower()}/{resolved.as_posix()[3:]}"
    return resolved.as_posix()


class RolloutContractTests(unittest.TestCase):
    def test_instruction_keeps_delivery_contract_while_method_stays_in_skill(self):
        instruction = INSTRUCTION.read_text(encoding="utf-8")
        skill = SKILL.read_text(encoding="utf-8")

        self.assertIn("/workspace/边坡支护专业分包招标清单.xlsx", instruction)
        self.assertIn("exact three section names", instruction)
        self.assertIn("pre-tax unit price blank", instruction)
        self.assertIn("evidence reference", instruction)
        self.assertIn("quantity basis", instruction)
        self.assertIn("basis status", instruction)
        self.assertIn("audit register", instruction)
        self.assertNotIn("normal construction sequencing", instruction)
        self.assertNotIn("Preserve distinct soil or rock classes", instruction)
        self.assertIn("soft strata and dense or rocky ones", skill)

    def test_skill_sequence_and_composite_boundary_guidance_matches_verifier_contract(self):
        text = SKILL.read_text(encoding="utf-8")

        self.assertIn("exact source-defined section label or composite boundary", text)
        self.assertIn("globally unique positive integer", text)
        self.assertIn("must not restart numbering", text)
        self.assertIn("Arabic positive integers only", text)
        self.assertIn("`Ⅰ-01`", text)
        self.assertNotIn("use a composite identifier", text)

    def test_verifier_exports_submitted_workbook_and_all_score_files(self):
        shell = shutil.which("bash") or shutil.which("sh")
        if shell is None:
            self.skipTest("a POSIX shell is required for the verifier integration test")
        # Keep the fixture on the same mounted volume as the task so Windows
        # Git Bash can access it under restricted test environments.
        with tempfile.TemporaryDirectory(dir=TASK_DIR) as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            verifier = root / "verifier"
            artifacts = root / "artifacts"
            workspace.mkdir()
            shutil.copy2(GOLD, workspace / DELIVERABLE)
            env = os.environ.copy()
            env["PYTHON"] = shell_path(Path(sys.executable))
            env["VERIFIER_OUT"] = shell_path(verifier)
            env["ARTIFACTS_OUT"] = shell_path(artifacts)

            completed = subprocess.run(
                [shell, shell_path(TEST_SCRIPT), shell_path(workspace)],
                env=env,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((artifacts / DELIVERABLE).is_file())
            for name in (
                "reward.json",
                "reward.txt",
                "reward_strict.txt",
                "reward_lenient.txt",
                "reward_detail.json",
            ):
                self.assertTrue(
                    (verifier / name).is_file(),
                    f"{name}\nstdout={completed.stdout}\nstderr={completed.stderr}\nvalidator_log={(verifier / 'validator.log').read_text(encoding='utf-8', errors='replace') if (verifier / 'validator.log').is_file() else ''}",
                )

    def test_dockerfile_exposes_only_workspace_at_required_runtime_path(self):
        instructions = [
            line.strip()
            for line in DOCKERFILE.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

        self.assertIn("COPY workspace/ /workspace/", instructions)
        self.assertIn("WORKDIR /workspace", instructions)
        self.assertFalse(any(line.startswith("COPY . ") for line in instructions))


if __name__ == "__main__":
    unittest.main()

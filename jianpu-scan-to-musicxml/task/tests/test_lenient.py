import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from scoreio import lname
from validator import score

TASK = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
TRUTH = TASK / 'tests/ground_truth.json'


class LenientCompletionTests(unittest.TestCase):
    def grade(self, tree):
        with tempfile.TemporaryDirectory() as folder:
            answer = Path(folder) / 'answer.mei'
            tree.write(answer, encoding='utf-8')
            return score(answer, TRUTH, TASK / 'environment/workspace')

    def test_partial_primary_recognition_keeps_independent_credit(self):
        tree = ET.parse(PACKAGE_ROOT / 'golden/揚州慢.mei')
        notes = [node for node in tree.getroot().iter() if lname(node.tag) == 'nc']
        for node in notes[:49]:
            node.set('label', 'unresolved')
        result = self.grade(tree)
        self.assertEqual(len(notes), 98)
        self.assertEqual(result['rewards']['lenient'], 0)
        self.assertEqual(result['lenient_checks']['primary_source_fidelity']['completion'], .5)
        self.assertEqual(result['lenient_checks']['real_secondary_classes']['completion'], 1)

    def test_limited_primary_errors_can_pass_without_full_joint_fidelity(self):
        tree = ET.parse(PACKAGE_ROOT / 'golden/揚州慢.mei')
        notes = [node for node in tree.getroot().iter() if lname(node.tag) == 'nc']
        for node in notes[:25]:
            node.set('label', 'unresolved')
        result = self.grade(tree)
        self.assertLess(result['reward'], 1)
        self.assertEqual(result['rewards']['lenient'], 1)

    def test_all_secondary_loss_does_not_erase_primary_credit(self):
        tree = ET.parse(PACKAGE_ROOT / 'golden/揚州慢.mei')
        for parent in tree.getroot().iter():
            for node in list(parent):
                if node.get('type') == 'secondary-sign':
                    parent.remove(node)
        result = self.grade(tree)
        self.assertEqual(result['rewards']['lenient'], 0)
        self.assertEqual(result['lenient_checks']['primary_source_fidelity']['completion'], 1)
        self.assertEqual(result['lenient_checks']['real_secondary_classes']['completion'], 0)

    def test_golden_ledger_and_missing_deliverable(self):
        result = self.grade(ET.parse(PACKAGE_ROOT / 'golden/揚州慢.mei'))
        self.assertEqual(result['rewards']['lenient'], 1)
        self.assertTrue(all(item['passed'] for item in result['lenient_checks'].values()))
        missing = score(Path('/missing/lenient-artifact.mei'), TRUTH)
        self.assertEqual(missing['rewards']['lenient'], 0)
        self.assertTrue(all(not item['passed'] for item in missing['lenient_checks'].values()))

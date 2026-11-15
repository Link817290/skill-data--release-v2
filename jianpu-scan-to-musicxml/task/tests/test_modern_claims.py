import copy
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

from scoreio import parse_mei, MEI


class ModernClaimsTests(unittest.TestCase):
    def setUp(self):
        self.root = ET.parse(Path(__file__).resolve().parents[2] / 'golden/揚州慢.mei').getroot()

    def parse(self, root):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'answer.mei'
            ET.ElementTree(root).write(file, encoding='utf-8')
            return parse_mei(file)

    def test_explicit_typed_modern_meter_is_detected(self):
        ET.SubElement(self.root, '{' + MEI + '}annot', {'type': 'modern-meter'}).text = '4/4'
        self.assertTrue(self.parse(self.root)['invented_semantics'])

    def test_namespaced_modern_values_are_detected(self):
        self.root.set('{urn:custom}absolute_pitch', 'C4')
        self.root.set('data-duration-ms', '500')
        self.assertTrue(self.parse(self.root)['invented_semantics'])

    def test_unasserted_value_and_valid_boundary_do_not_invent_timing(self):
        ET.SubElement(self.root, '{' + MEI + '}annot', {'type': 'modern-meter'}).text = 'not determined'
        ET.SubElement(self.root, '{' + MEI + '}annot', {'type': 'editorial-boundary'}).text = 'No modern meter or absolute pitch can be inferred.'
        self.root.set('data-absolute-pitch', 'unknown')
        self.assertFalse(self.parse(self.root)['invented_semantics'])


if __name__ == '__main__':
    unittest.main()

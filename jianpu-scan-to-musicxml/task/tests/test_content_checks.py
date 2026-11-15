import copy
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from scoreio import lname
from validator import score

TASK=Path(__file__).resolve().parent.parent
PACKAGE_ROOT=Path(__file__).resolve().parents[2]


class CompleteSourceContent(unittest.TestCase):
    def grade(self,root):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'answer.mei';ET.ElementTree(root).write(path,encoding='utf-8')
            return score(path,TASK/'tests/ground_truth.json',TASK/'environment/workspace')

    def test_joint_partitions_cover_every_source_position(self):
        result=score(PACKAGE_ROOT/'golden/揚州慢.mei',TASK/'tests/ground_truth.json',TASK/'environment/workspace')
        self.assertEqual(result['source_census'],{'primary_positions':98,'bare_positions':70,'compound_positions':28})
        self.assertEqual(result['content_scoring_features']['bare_position_fidelity'],1)
        self.assertEqual(result['content_scoring_features']['compound_position_fidelity'],1)
        self.assertEqual(result['reward'],1)

    def test_missing_compound_signs_are_not_genuine_absence_credit(self):
        root=ET.parse(PACKAGE_ROOT/'golden/揚州慢.mei').getroot()
        for n in root.iter():
            if n.get('type')=='secondary-sign':n.set('data-class','none');n.text='none'
        result=self.grade(root)['content_scoring_features']
        self.assertEqual(result['real_secondary_classes'],0)
        self.assertEqual(result['compound_position_fidelity'],0)
        self.assertEqual(result['secondary_absence'],1)
        self.assertEqual(result['bare_position_fidelity'],1)

    def test_extra_wrong_positions_cannot_raise_primary_or_full_score(self):
        root=ET.parse(PACKAGE_ROOT/'golden/揚州慢.mei').getroot()
        before=self.grade(root)
        nodes=[n for n in root.iter() if lname(n.tag)=='syllable']
        highest=max(int(n.get('n')) for n in nodes)
        for i,n in enumerate(nodes):
            extra=copy.deepcopy(n);extra.set('n',str(highest+i+1))
            for child in extra.iter():
                child.attrib.pop('{http://www.w3.org/XML/1998/namespace}id',None)
                if lname(child.tag)=='nc':child.set('label','unresolved')
            next(p for p in root.iter() if n in list(p)).append(extra)
        after=self.grade(root)
        self.assertLessEqual(after['content_scoring_features']['primary_source_fidelity'],.5)
        self.assertLess(after['reward'],before['reward'])

    def test_wrong_glyph_owner_does_not_reassign_primary_answer(self):
        root=ET.parse(PACKAGE_ROOT/'golden/揚州慢.mei').getroot()
        nodes=[n for n in root.iter() if lname(n.tag)=='syllable']
        notes=[next(c for c in n.iter() if lname(c.tag)=='nc') for n in nodes]
        labels=[n.get('label') for n in notes];refs=[n.get('facs') for n in notes]
        for i,n in enumerate(notes):n.set('label',labels[(i+1)%len(notes)]);n.set('facs',refs[(i+1)%len(notes)])
        result=self.grade(root)
        self.assertLess(result['content_scoring_features']['primary_source_fidelity'],.5)
        self.assertLess(sum(result['scoring_features'][k] for k in result['scoring_features'] if k.startswith('pitch_'))/10,.5)


if __name__=='__main__':unittest.main()

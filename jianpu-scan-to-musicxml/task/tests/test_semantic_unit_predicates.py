import copy
import unittest
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from semantic_context import context
from semantic_unit_predicates import unit_checks
from scoreio import lname
from scoreio import MEI, XML_ID
from validator import score


class SourceUnitPredicates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        task=Path(__file__).resolve().parent.parent
        package_root=Path(__file__).resolve().parents[2]
        cls.reference=context(package_root/'golden/揚州慢.mei',compact_metadata=True)
        columns=[];start=0;positions=cls.reference['golden']['facts']['positions']
        for i,e in enumerate(positions):
            if e['line_break'] or i==len(positions)-1:
                columns.append(list(range(start,i+1)));start=i+1
        prose=next(m['complete_texts'][0] for m in cls.reference['golden']['facts']['metadata'] if m['type']=='preface')
        cls.reference['golden']['source_census']={'music_columns':columns,'preface_columns':[{'text':prose}]}

    def test_reference_and_optional_final_boundary(self):
        for flag in (False,True):
            value=copy.deepcopy(self.reference)
            value['candidate']['facts']['positions'][-1]['line_break']=flag
            self.assertTrue(all(x['completion']==1 for x in unit_checks(value).values()))

    def test_cross_page_notation_earns_only_real_text_regions(self):
        value=copy.deepcopy(self.reference)
        for p in value['candidate']['facts']['positions']:p['notation_page']=3-p['notation_page']
        checks=unit_checks(value)
        for key,score in checks.items():
            self.assertEqual(score['completion'],.5 if key.startswith('facs_') else 1)

    def test_corner_markers_do_not_preserve_glyphs(self):
        value=copy.deepcopy(self.reference)
        for p in value['candidate']['facts']['positions']:
            for kind in ('text_box','notation_box'):
                x,y,_,_=p[kind];p[kind]=[x,y,x+1,y+1]
        self.assertLess(max(x['completion'] for key,x in unit_checks(value).items() if key.startswith('facs_')),.01)

    def test_wrong_images_fail_corresponding_region_units(self):
        value=copy.deepcopy(self.reference)
        for surface in value['candidate']['facts']['surfaces']:surface['target_valid']=False
        self.assertTrue(all(x['completion']==0 for key,x in unit_checks(value).items() if key.startswith('facs_')))

    def test_printed_characters_are_uniformly_checked(self):
        value=copy.deepcopy(self.reference)
        preface=next(m for m in value['candidate']['facts']['metadata'] if m['type']=='preface')
        preface['complete_texts'][0]=preface['complete_texts'][0].replace('爲','為')
        for p in value['candidate']['facts']['positions']:
            if p['text']=='爲':p['text']='為'
        checks=unit_checks(value)
        self.assertEqual(checks['preface_column_1']['correct_units'],62)
        self.assertEqual(checks['text_column_6']['completion'],.75)
        self.assertEqual(checks['facs_column_6']['completion'],1)

    def test_unmapped_specific_namespaced_label_is_not_placeholder(self):
        task=Path(__file__).resolve().parent.parent
        tree=ET.parse(Path(__file__).resolve().parents[2]/'golden/揚州慢.mei')
        note=next(n for n in tree.getroot().iter() if lname(n.tag)=='nc')
        note.attrib.pop('label',None)
        note.set('{urn:notation}data-primary-class','ハ')
        with tempfile.TemporaryDirectory() as directory:
            answer=Path(directory)/'answer.mei';tree.write(answer,encoding='utf-8')
            facts=context(answer,compact_metadata=True)['candidate']['facts']
        self.assertEqual(facts['positions'][0]['pitch'],'ハ')
        self.assertEqual(facts['positions'][0]['pitch_normalization_status'],'parser-unmapped-specific-declaration')

    def test_declared_relative_class_identifiers_are_equivalent(self):
        task=Path(__file__).resolve().parent.parent
        tree=ET.parse(Path(__file__).resolve().parents[2]/'golden/揚州慢.mei');root=tree.getroot()
        header=next(n for n in root if lname(n.tag)=='meiHead')
        encoding=ET.SubElement(header,'{'+MEI+'}encodingDesc')
        taxonomy=ET.SubElement(encoding,'{'+MEI+'}classDecl')
        names={}
        for note in root.iter():
            if lname(note.tag)!='nc':continue
            canonical=note.get('label')
            if canonical not in names:
                identifier='renamed-relative-class-'+str(len(names));names[canonical]=identifier
                definition=ET.SubElement(taxonomy,'{'+MEI+'}category',{XML_ID:identifier,'type':'suzipu-primary-class','label':canonical})
                ET.SubElement(definition,'{'+MEI+'}catDesc').text='Equivalent relative suzipu pitch class '+canonical+'; no modern absolute pitch asserted.'
            note.set('label','#'+names[canonical])
        with tempfile.TemporaryDirectory() as directory:
            answer=Path(directory)/'answer.mei';tree.write(answer,encoding='utf-8')
            result=score(answer,task/'tests/ground_truth.json',task/'environment/workspace')
        self.assertEqual(result['rewards']['strict'],1)

    def test_explicit_unresolved_status_cannot_be_completed_by_alias_mapper(self):
        task=Path(__file__).resolve().parent.parent
        tree=ET.parse(Path(__file__).resolve().parents[2]/'golden/揚州慢.mei')
        for note in tree.getroot().iter():
            if lname(note.tag)=='nc':
                note.set('label','久');note.set('data-primary-status','unresolved');note.set('data-secondary-status','unresolved')
        with tempfile.TemporaryDirectory() as directory:
            answer=Path(directory)/'answer.mei';tree.write(answer,encoding='utf-8')
            value=context(answer,compact_metadata=True)
        value['golden']['source_census']=copy.deepcopy(self.reference['golden']['source_census'])
        self.assertTrue(all(p['pitch']=='__UNRESOLVED__' for p in value['candidate']['facts']['positions']))
        self.assertTrue(all(p['secondary']=='__UNRESOLVED__' for p in value['candidate']['facts']['positions']))
        self.assertTrue(all(v['completion']==1 for k,v in unit_checks(value).items() if k.startswith('facs_')))

    def test_eight_positions_cannot_substitute_for_complete_source_notation(self):
        task=Path(__file__).resolve().parent.parent
        tree=ET.parse(Path(__file__).resolve().parents[2]/'golden/揚州慢.mei')
        expected=self.reference['golden']['facts']['positions']
        kept={i for i,p in enumerate(expected) if (p['pitch'],p['secondary']) in
              {('CHE','XIAO_ZHU'),('YI','DA_DUN')}}
        syllables=[n for n in tree.getroot().iter() if lname(n.tag)=='syllable']
        for i,node in enumerate(syllables):
            if i in kept:continue
            for child in node.iter():
                if lname(child.tag)=='nc':child.set('label','unresolved')
                if child.get('type')=='secondary-sign':
                    child.set('data-class','unresolved');child.text='unresolved'
        with tempfile.TemporaryDirectory() as directory:
            answer=Path(directory)/'answer.mei';tree.write(answer,encoding='utf-8')
            result=score(answer,task/'tests/ground_truth.json',task/'environment/workspace')
        self.assertEqual(len(kept),8)
        self.assertLessEqual(result['rewards']['strict'],.45)
        self.assertEqual(result['rewards']['lenient'],0)

    def test_unresolved_inclusion_does_not_silently_mean_included(self):
        task=Path(__file__).resolve().parent.parent
        tree=ET.parse(Path(__file__).resolve().parents[2]/'golden/揚州慢.mei')
        for n in tree.getroot().iter():
            if lname(n.tag)=='nc':n.set('data-source-status','unresolved')
        with tempfile.TemporaryDirectory() as directory:
            answer=Path(directory)/'answer.mei';tree.write(answer,encoding='utf-8')
            result=score(answer,task/'tests/ground_truth.json',task/'environment/workspace')
        self.assertEqual(result['group_points']['joint_position_fidelity'],0)
        self.assertEqual(result['group_points']['facsimile_geometry'],1)
        self.assertEqual(result['group_points']['pitch_classification'],1)
        self.assertEqual(result['rewards']['lenient'],0)
        self.assertEqual(result['lenient_checks']['source_status_fidelity']['completion'],0)


if __name__=='__main__':unittest.main()

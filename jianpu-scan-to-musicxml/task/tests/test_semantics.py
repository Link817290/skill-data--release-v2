import tempfile
import shutil
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from scoreio import MEI, XML_ID, category, lname
from validator import score

TASK = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
GOLD = PACKAGE_ROOT / 'golden/揚州慢.mei'
TRUTH = TASK / 'tests/ground_truth.json'


class SemanticContractTests(unittest.TestCase):
    def grade(self, root):
        with tempfile.TemporaryDirectory() as temp:
            answer = Path(temp) / 'answer.mei'
            ET.ElementTree(root).write(answer, encoding='utf-8', xml_declaration=True)
            return score(answer, TRUTH)

    def gold(self):
        return ET.parse(GOLD).getroot()

    def test_golden(self):
        result = self.grade(self.gold())
        self.assertEqual(result['reward'], 1.0)
        self.assertEqual(result['rewards']['lenient'], 1.0)

    def test_explicit_sequence_survives_document_reordering(self):
        root = self.gold()
        for parent in root.iter():
            events = [n for n in parent if lname(n.tag) == 'syllable']
            indexes = [list(parent).index(n) for n in events]
            for index, event in zip(indexes, reversed(events)):
                parent[index] = event
        self.assertEqual(self.grade(root)['reward'], 1.0)

    def test_alternate_typed_annot(self):
        root = self.gold()
        for n in root.iter():
            if lname(n.tag) == 'syllable':
                n.set('data-excluded', str(n.get('type') == 'excluded').lower())
                n.tag = '{' + MEI + '}annot'
                n.set('type', 'suzipu-position')
        self.assertEqual(self.grade(root)['reward'], 1.0)

    def test_namespaced_symbol_and_multiple_facs(self):
        root = self.gold()
        for n in list(root.iter()):
            if lname(n.tag) != 'syllable':
                continue
            syl = next(x for x in n.iter() if lname(x.tag) == 'syl')
            nc = next(x for x in n.iter() if lname(x.tag) == 'nc')
            second = next((x.text for x in nc if x.get('type') == 'secondary-sign'), '')
            excluded = n.get('type') == 'excluded'
            n.tag = '{' + MEI + '}symbol'
            n.set('type', 'suzipu-position')
            n.set('facs', n.get('facs', '') + ' ' + nc.get('facs', ''))
            n.set('{urn:other-encoder}lyric', syl.text or '')
            n.set('{urn:other-encoder}primary', nc.get('label', ''))
            n.set('{urn:other-encoder}secondary', second or 'none')
            n.set('{urn:other-encoder}status', 'excluded' if excluded else 'included')
            n[:] = []
        self.assertEqual(self.grade(root)['reward'], 1.0)

    def test_composer_person_role_and_mode_property_independence(self):
        root = self.gold()
        for n in root.iter():
            if lname(n.tag) == 'composer':
                n.tag = '{' + MEI + '}persName'
                n.set('role', 'composer')
            n.attrib.pop('data-gong-lvlv', None)
            n.attrib.pop('data-final-note', None)
        self.assertEqual(self.grade(root)['reward'], 1.0)

    def test_id_renaming_and_metadata_segmentation(self):
        root = self.gold()
        mapping = {n.get(XML_ID): 'random-' + str(i) for i, n in enumerate(root.iter()) if n.get(XML_ID)}
        for n in root.iter():
            if n.get(XML_ID):
                n.set(XML_ID, mapping[n.get(XML_ID)])
            if n.get('facs'):
                n.set('facs', ' '.join('#' + mapping[ref[1:]] for ref in n.get('facs').split()))
        parent = next(n for n in root.iter() if n.get('type') == 'source-metadata')
        nodes = [n for n in parent if n.get('type') == 'preface']
        text = ''.join(n.text or '' for n in nodes)
        refs = ' '.join(n.get('facs', '') for n in nodes)
        for n in nodes:
            parent.remove(n)
        ET.SubElement(parent, '{' + MEI + '}annot', {'type': 'prose-preface', 'facs': refs}).text = text
        self.assertEqual(self.grade(root)['reward'], 1.0)

    def test_broken_graphic_loses_traceability_but_keeps_recognition(self):
        root = self.gold()
        for n in root.iter():
            if lname(n.tag) == 'graphic':
                n.set('target', 'does-not-exist.png')
        result = self.grade(root)
        self.assertLess(result['reward'], 1)
        self.assertEqual(result['content_scoring_features']['primary_source_fidelity'], 1)
        self.assertEqual(result['content_scoring_features']['bare_position_fidelity'], 0)
        self.assertEqual(result['content_scoring_features']['compound_position_fidelity'], 0)
        self.assertEqual(result['content_scoring_features']['source_region_quality'], 0)
        self.assertEqual(result['group_points']['source_images'], 0)
        self.assertEqual(result['rewards']['lenient'], 0)
        self.assertEqual(result['lenient_checks']['source_region_quality']['completion'], 0)
        self.assertEqual(result['group_points']['pitch_classification'], 1)

    def test_prohibited_timing_loses_only_atemporal_credit(self):
        root = self.gold()
        for n in root.iter():
            if lname(n.tag) == 'nc':
                n.set('dur', '4')
                n.set('pname', 'c')
                n.set('oct', '4')
        result = self.grade(root)
        self.assertLess(result['reward'], 1)
        self.assertEqual(result['content_scoring_features']['document_contract'], 2/3)
        self.assertEqual(result['group_points']['atemporal_fidelity'], 0)
        self.assertEqual(result['group_points']['pitch_classification'], 1)

    def test_duplicate_ids_lose_closure_credit(self):
        root = self.gold()
        zones = [n for n in root.iter() if lname(n.tag) == 'zone']
        zones[0].set(XML_ID, zones[1].get(XML_ID))
        result = self.grade(root)
        self.assertEqual(result['group_points']['referential_closure'], 0)
        self.assertLess(result['reward'], 1)

    def test_missing_and_namespace_invalid_are_zero(self):
        result = score(Path('/nonexistent/mei-missing-artifact'), TRUTH)
        self.assertEqual(result['reward'], 0)
        root = self.gold()
        root.tag = 'mei'
        self.assertEqual(self.grade(root)['reward'], 0)

    def test_modified_scan_does_not_pass_hash_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            shutil.copytree(TASK / 'environment/workspace/materials', workspace / 'materials')
            (workspace / 'output').mkdir()
            answer = workspace / 'output/answer.mei'
            ET.ElementTree(self.gold()).write(answer, encoding='utf-8')
            first = workspace / 'materials/source_page_01.png'
            first.write_bytes(first.read_bytes() + b'tampered')
            result = score(answer, TRUTH, workspace)
            self.assertEqual(result['group_points']['source_images'], .5)
            self.assertLess(result['reward'], 1)

    def test_aliases_do_not_guess_unresolved_or_ambiguous_shapes(self):
        self.assertEqual(category('久'), 'LIU')
        self.assertEqual(category('pc-jiu'), 'LIU')
        self.assertEqual(category('り'), 'FAN')
        self.assertEqual(category('CHI'), 'CHE')
        self.assertEqual(category('source-glyph'), '__UNRESOLVED__')
        self.assertEqual(category('source-mark-or-none', True), '__UNRESOLVED__')
        self.assertEqual(category('pc-san'), '__UNRESOLVED__')
        self.assertIsNone(category('none-observed', True))

    def test_cross_page_notation_cannot_claim_the_text_page(self):
        root = self.gold()
        surfaces = [n for n in root.iter() if lname(n.tag) == 'surface']
        other = surfaces[1]
        ids = {n.get(XML_ID): n for n in root.iter() if n.get(XML_ID)}
        import copy
        for i, node in enumerate(n for n in root.iter() if lname(n.tag) == 'nc'):
            old_id = node.get('facs', '').removeprefix('#')
            original = ids[old_id]
            page = next(surface.get('n') for surface in surfaces if original in list(surface))
            destination = surfaces[1] if page == '1' else surfaces[0]
            zone = copy.deepcopy(original)
            zone.set(XML_ID, 'foreign-note-' + str(i))
            destination.append(zone)
            node.set('facs', '#' + zone.get(XML_ID))
        result = self.grade(root)
        self.assertEqual(result['group_points']['source_pairing_integrity'], 0)
        self.assertEqual(result['group_points']['joint_position_fidelity'], 0)
        self.assertEqual(result['group_points']['referential_closure'], 1)
        self.assertLess(result['reward'], 1)

    def test_lyric_shift_is_not_correct_joint_transcription(self):
        root = self.gold()
        lyrics = [n for n in root.iter() if lname(n.tag) == 'syl']
        texts = [n.text for n in lyrics]
        for n, text in zip(lyrics, texts[1:] + texts[:1]):
            n.text = text
        result = self.grade(root)
        self.assertLess(result['group_points']['source_pairing_integrity'], .1)
        self.assertLess(result['group_points']['joint_position_fidelity'], .1)

    def test_reasonably_padded_crops_preserve_ownership(self):
        root = self.gold()
        music_ids = {n.get('facs', '').removeprefix('#') for n in root.iter() if lname(n.tag) in {'syllable', 'nc'}}
        for zone in root.iter():
            if zone.get(XML_ID) not in music_ids:
                continue
            for key, shift in [('ulx',-4),('uly',-4),('lrx',4),('lry',4)]:
                zone.set(key, str(int(zone.get(key)) + shift))
        result = self.grade(root)
        self.assertEqual(result['group_points']['source_pairing_integrity'], 1)
        self.assertEqual(result['group_points']['joint_position_fidelity'], 1)
        self.assertEqual(result['group_points']['physical_source_order'], 1)
        self.assertEqual(result['reward'], 1)

    def test_declared_sequence_cannot_reverse_physical_reading_order(self):
        root = self.gold()
        events = [n for n in root.iter() if lname(n.tag) == 'syllable']
        for n in events:
            n.set('n', str(len(events) + 1 - int(n.get('n'))))
        result = self.grade(root)
        self.assertLess(result['group_points']['source_pairing_integrity'], .1)
        self.assertEqual(result['group_points']['physical_source_order'], 0)

    def test_metadata_facs_is_optional_and_diagnostic_only(self):
        root = self.gold()
        for n in root.iter():
            if n.get('type') in {'title','attribution','mode','preface'}:
                n.attrib.pop('facs', None)
        result = self.grade(root)
        self.assertEqual(result['reward'], 1)

    def test_one_pixel_markers_do_not_cover_the_source_regions(self):
        root = self.gold()
        for zone in root.iter():
            if lname(zone.tag) == 'zone':
                zone.set('lrx', str(int(zone.get('ulx')) + 1))
                zone.set('lry', str(int(zone.get('uly')) + 1))
        result = self.grade(root)
        self.assertLess(result['group_points']['facsimile_geometry'], .001)
        self.assertLess(result['group_points']['joint_position_fidelity'], .001)
        self.assertEqual(result['rewards']['lenient'], 0)
        self.assertLess(result['lenient_checks']['source_region_quality']['completion'], .001)

    def test_one_whole_page_region_does_not_trace_each_position(self):
        root = self.gold()
        for zone in root.iter():
            if lname(zone.tag) == 'zone':
                for key,value in [('ulx','0'),('uly','0'),('lrx','800'),('lry','1233')]:
                    zone.set(key,value)
        result = self.grade(root)
        self.assertLess(result['group_points']['source_pairing_integrity'], .1)
        self.assertLess(result['group_points']['facsimile_geometry'], .1)

    def test_tight_actual_ink_bounds_are_equivalent_correct_regions(self):
        import json
        root = self.gold()
        anchors = json.loads(TRUTH.read_text())['mei']['events']
        zones = {n.get(XML_ID):n for n in root.iter() if lname(n.tag)=='zone'}
        events = [n for n in root.iter() if lname(n.tag)=='syllable']
        for node, source in zip(events,anchors):
            nc = next(n for n in node.iter() if lname(n.tag)=='nc')
            for role, element in [('text',node),('notation',nc)]:
                runs = source.get(role+'_ink_runs',[])
                if not runs:
                    continue
                zone = zones[element.get('facs').removeprefix('#')]
                bounds = [min(r[1] for r in runs),min(r[0] for r in runs),max(r[2] for r in runs),max(r[0] for r in runs)+1]
                for key,value in zip(('ulx','uly','lrx','lry'),bounds):
                    zone.set(key,str(value))
        result = self.grade(root)
        self.assertEqual(result['reward'],1)
        self.assertEqual(result['rewards']['lenient'],1)

    def test_arbitrary_sequence_label_origin_preserves_source_semantics(self):
        root = self.gold()
        for n in root.iter():
            if lname(n.tag)=='syllable':
                n.set('n',str(int(n.get('n'))+1000))
        self.assertEqual(self.grade(root)['reward'],1)

    def test_matched_regions_of_the_wrong_lyric_are_not_truthful_links(self):
        root = self.gold()
        events=[n for n in root.iter() if lname(n.tag)=='syllable']
        first,second=events[:2]
        first.set('facs',second.get('facs'))
        nc1=next(n for n in first.iter() if lname(n.tag)=='nc')
        nc2=next(n for n in second.iter() if lname(n.tag)=='nc')
        nc1.set('facs',nc2.get('facs'))
        result=self.grade(root)
        record=result['atoms']['position_bindings'][0]
        self.assertEqual(record['text_source_position'],1)
        self.assertEqual(record['notation_source_position'],1)
        self.assertEqual(record['intended_source_position'],0)
        self.assertFalse(record['same_source_position'])
        self.assertLess(result['group_points']['source_pairing_integrity'],1)


if __name__ == '__main__':
    unittest.main()

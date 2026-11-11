"""Read original local documents; no Golden, rubric or cached answer dependency."""
from pathlib import Path
import hashlib
import re

import pymupdf
from docx import Document

SPEC = 'LG_AKB76043105_Button_Function_Spec.pdf'
SOP = 'LG_AKB76043105_Standard_Test_Procedure_SOP.docx'
MANUAL = 'MFL72141910_02_S_250218a.pdf'
PRODUCT = 'product-pdf (1).pdf'
ENERGY = 'mmo_120384967_1788973707_747_3631382.pdf'


def normalized(text):
    return ' '.join(text.split())


class Sources:
    def __init__(self, materials):
        self.root = Path(materials)
        self.documents = {}
        self.identities = {}
        for filename in (SPEC, MANUAL, PRODUCT, ENERGY):
            path = self.root / filename
            with pymupdf.open(path) as pdf:
                # PDF source order keeps each table cell together; geometric sort
                # interleaves neighboring cells and destroys field/value relations.
                self.documents[filename] = [page.get_text(sort=False) for page in pdf]
            self.identities[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
        path = self.root / SOP
        doc = Document(path)
        self.paragraphs = [p.text for p in doc.paragraphs]
        self.tables = []

        def table_values(table, locator):
            self.tables.append({'locator': locator, 'rows': [[c.text for c in row.cells] for row in table.rows]})
            for ri, row in enumerate(table.rows, 1):
                for ci, cell in enumerate(row.cells, 1):
                    for ti, nested in enumerate(cell.tables, 1):
                        table_values(nested, f'{locator}/r{ri}/c{ci}/t{ti}')
        for ti, table in enumerate(doc.tables, 1):
            table_values(table, f'table{ti}')
        self.identities[SOP] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.tests = {}
        for i, text in enumerate(self.paragraphs):
            match = re.fullmatch(r'Test No\.:\s*([A-Z]+-\d+)', text.strip())
            if not match:
                continue
            end = next((j for j in range(i+1, len(self.paragraphs))
                        if re.match(r'\d+\.\d+\s', self.paragraphs[j])), len(self.paragraphs))
            block = self.paragraphs[i:end]
            def between(start, stop):
                begin = next((j+1 for j, s in enumerate(block) if s.startswith(start)), None)
                if begin is None:
                    return []
                finish = next((j for j in range(begin, len(block)) if block[j].startswith(stop)), len(block))
                return block[begin:finish]
            self.tests[match.group(1)] = {
                'title': self.paragraphs[i-1], 'paragraph_start': i,
                'paragraph_end': end, 'steps': between('Test Steps:', 'Expected Result'),
                'expected': between('Expected Result', 'Judgment Criteria:'),
                'text': '\n'.join(block),
                'source': f'{SOP} paragraphs {i}-{end}'
            }
        self.evidence = []

    def page(self, filename, number):
        return normalized(self.documents[filename][number-1])

    def fact(self, key, filename, page, pattern, group=1):
        source = self.page(filename, page)
        match = re.search(pattern, source, re.I)
        if match is None:
            raise ValueError(f'Missing source fact {key}: {filename} p{page}: {pattern}')
        value = match.group(group)
        self.evidence.append({'fact_id': key, 'file': filename, 'page': page,
                              'matched_quote': match.group(0), 'value': value})
        return value

    def test(self, key):
        item = self.tests[key]
        self.evidence.append({'fact_id': 'test.'+key, 'source': item['source'],
                              'matched_quote': item['text']})
        return item

    def test_fact(self, key, test_id, pattern, group=1):
        item=self.tests[test_id]
        match=re.search(pattern,normalized(item['text']),re.I)
        if match is None:
            raise ValueError(f'Missing SOP fact {key}: {test_id}: {pattern}')
        value=match.group(group)
        self.evidence.append({'fact_id':key,'source':item['source'],
                              'matched_quote':match.group(0),'value':value})
        return value


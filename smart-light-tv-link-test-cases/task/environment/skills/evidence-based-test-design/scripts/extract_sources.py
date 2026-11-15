"""Extract searchable source records with paragraph/table/page locations."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


def extract(directory):
    records, notices = [], []
    for path in sorted(Path(directory).rglob('*')):
        if path.suffix.lower() == '.docx':
            doc = Document(path)
            paragraph, table = 0, 0
            for element in doc.element.body.iterchildren():
                if element.tag.endswith('}p'):
                    paragraph += 1
                    text = Paragraph(element, doc).text
                    if text.strip():
                        records.append({'source': path.name, 'location': f'p{paragraph}', 'text': text})
                elif element.tag.endswith('}tbl'):
                    table += 1
                    for row, cells in enumerate(Table(element, doc).rows, 1):
                        text = ' | '.join(cell.text for cell in cells.cells)
                        records.append({'source': path.name, 'location': f't{table}.r{row}', 'text': text})
        elif path.suffix.lower() == '.pdf':
            try:
                import fitz
            except ImportError:
                try:
                    from pypdf import PdfReader
                except ImportError:
                    if not shutil.which('pdftotext'):
                        notices.append({'source': path.name, 'kind': 'pdf_reader_unavailable',
                                        'action': 'Read PDF with available document tools.'})
                        continue
                    result = subprocess.run(['pdftotext', '-layout', str(path), '-'],
                                            capture_output=True, check=True)
                    pages = result.stdout.decode('utf-8', errors='replace').split('\f')
                    if pages and not pages[-1].strip():
                        pages.pop()
                else:
                    pages = [page.extract_text() or '' for page in PdfReader(path).pages]
            else:
                with fitz.open(path) as doc:
                    pages = [page.get_text() for page in doc]
            for page, text in enumerate(pages, 1):
                records.append({'source': path.name, 'location': f'page{page}', 'text': text})
                if not text.strip():
                    notices.append({'source': path.name, 'location': f'page{page}', 'kind': 'inspect_image_page'})
    return {'records': records, 'notices': notices}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if not args.directory.is_dir():
        parser.error('Source directory does not exist')
    result = extract(args.directory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'records': len(result['records']), 'notices': result['notices']}))


if __name__ == '__main__':
    main()

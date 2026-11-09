"""Evaluate delivered Excel formulas on an isolated copy, without source answers."""
import argparse
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(source, output, names):
    from openpyxl import load_workbook
    source, output = source.resolve(), output.resolve()
    if output == source or output.is_relative_to(source):
        raise ValueError('Evaluation copy must be outside the submitted directory')
    if output.exists():
        raise ValueError('Use a fresh evaluation copy')
    for file in source.rglob('*'):
        if file.is_symlink():
            raise ValueError('Submission links are not followed by the evaluation adapter')
    original = {str(path.relative_to(source)): digest(path) for path in source.rglob('*') if path.is_file()}
    shutil.copytree(source, output)
    rows = []
    for name in names:
        path = output / name
        if not path.exists():
            continue
        with zipfile.ZipFile(path) as archive:
            entries = [entry.lower() for entry in archive.namelist()]
            if any('vbaproject' in entry or entry.startswith('xl/externallinks/') for entry in entries):
                raise ValueError('Macro or external workbook dependency requires separate review')
        book = load_workbook(path, data_only=False)
        formulas = [(sheet.title, cell.coordinate) for sheet in book for row in sheet
                    for cell in row if cell.data_type == 'f']
        book.close()
        if not formulas:
            rows.append({'file': name, 'formulas': 0, 'content_changed': False})
            continue
        binary = shutil.which('libreoffice') or shutil.which('soffice')
        if not binary:
            raise RuntimeError('Declared task image cannot evaluate Excel formulas')
        with tempfile.TemporaryDirectory(prefix='business-excel-evaluation-') as temporary:
            temporary = Path(temporary)
            profile = temporary / 'profile'
            (profile / 'user').mkdir(parents=True)
            namespace = 'http://openoffice.org/2001/registry'
            ET.register_namespace('oor', namespace)
            registry = ET.Element('{' + namespace + '}items')
            item = ET.SubElement(registry, 'item', {'{' + namespace + '}path': '/org.openoffice.Office.Common/Security/Scripting'})
            prop = ET.SubElement(item, 'prop', {'{' + namespace + '}name': 'MacroSecurityLevel',
                                              '{' + namespace + '}op': 'fuse'})
            ET.SubElement(prop, 'value').text = '3'
            ET.ElementTree(registry).write(profile / 'user/registrymodifications.xcu', encoding='utf-8', xml_declaration=True)
            recalculated = temporary / 'recalculated'
            recalculated.mkdir()
            command = [binary, '-env:UserInstallation=' + profile.as_uri(), '--headless',
                       '--convert-to', 'xlsx', '--outdir', str(recalculated), str(path)]
            process = subprocess.run(command, capture_output=True, text=True, timeout=180)
            calculated = recalculated / path.name
            if process.returncode or not calculated.is_file():
                raise RuntimeError('Native workbook recalculation did not produce a usable copy')
            values = load_workbook(calculated, data_only=True)
            expressions = load_workbook(calculated, data_only=False)
            measured = []
            for sheet in expressions:
                for row in sheet:
                    for cell in row:
                        if cell.data_type != 'f':
                            continue
                        value = values[sheet.title][cell.coordinate].value
                        measured.append({'sheet': sheet.title, 'cell': cell.coordinate,
                                         'formula': cell.value, 'value': value,
                                         'value_type': values[sheet.title][cell.coordinate].data_type})
                        cell.value = value
            expressions.save(path)
            expressions.close()
            values.close()
            rows.append({'file': name, 'formulas': len(formulas), 'computed_cells': measured,
                         'original_sha256': original[name], 'recalculated_sha256': digest(calculated),
                         'evaluation_copy_sha256': digest(path), 'content_changed': True,
                         'engine': subprocess.check_output([binary, '--version'], text=True).strip(),
                         'command': command, 'stdout': process.stdout, 'stderr': process.stderr})
    if original != {str(path.relative_to(source)): digest(path) for path in source.rglob('*') if path.is_file()}:
        raise RuntimeError('Original actor submission changed during evaluation')
    report = {'original_files_sha256': original, 'workbooks': rows,
              'original_actor_files_modified': False,
              'scope': 'Compute only delivered formulas using the declared native office engine; no Golden, source answers or model calls. The caller runs this adapter without network access. Explicitly computed blank results remain blank.'}
    (output.parent / 'workbook-evaluation.json').write_text(json.dumps(report, ensure_ascii=True, indent=2, default=str) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workbook', action='append', required=True)
    arguments = parser.parse_args()
    result = normalize(arguments.source, arguments.output, arguments.workbook)
    print(json.dumps({'workbooks': len(result['workbooks']), 'original_actor_files_modified': False}))

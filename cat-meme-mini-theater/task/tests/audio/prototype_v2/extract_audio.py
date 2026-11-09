"""Source-backed variable-interval audio evidence, preserving the frozen v1 path.

Literal routes are proposals only. Actual canonical-to-asset waveform agreement
and actual film waveform agreement are measured before a route can qualify.
No project code is imported or executed.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re
from time import monotonic
import numpy as np

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audio_v1', BASE / 'extract_audio.py')
v1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v1)
CONFIG = {**v1.CONFIG, 'route_aggregate_band_minimum': .62,
          'route_aggregate_full_minimum': .25, 'route_gain_relative_spread_maximum': .25,
          'asset_canonical_correlation_minimum': .995,
          'route_alignment_search_seconds': .25}
NUMBER = r'-?(?:\d+(?:\.\d*)?|\.\d+)'
SKIP = {'node_modules', '.git', 'dist', 'build', '.next'}


def files(root, suffixes):
    if not root or not root.is_dir():
        return []
    return sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in suffixes
                  and not any(part in SKIP for part in p.relative_to(root).parts)
                  and p.stat().st_size <= 100_000_000)


def literal_routes(project):
    """Read two literal routing syntaxes, retaining their actual declarations."""
    routes = []
    assets = files(project, {'.wav', '.mp3', '.m4a', '.aac', '.mp4', '.mov'})
    by_stem = {}
    for asset in assets:
        by_stem.setdefault(asset.stem, []).append(asset)
    for path in files(project, {'.js', '.mjs', '.ts', '.tsx', '.sh', '.py'}):
        if path.stat().st_size > 500_000:
            continue
        text = path.read_text(errors='replace')
        # A literal source-file/start/duration/film-time/gain table consumed by
        # FFmpeg's seek, duration, delay and volume arguments.
        if '-ss "$ss"' in text and '-t "$t"' in text and 'adelay=' in text and 'volume=${gain}' in text:
            pattern = r'["\']([^"\'\n|]+\.(?:mp4|wav|mp3))\|(' + NUMBER + r')\|(' + NUMBER + r')\|(' + NUMBER + r')\|(' + NUMBER + r')["\']'
            for match in re.finditer(pattern, text):
                name, start, length, film, gain = match.groups()
                routes.append({'asset_name': name, 'asset_paths': [str(p) for p in assets if p.name == name],
                               'source_start': float(start), 'source_end': float(start) + float(length),
                               'film_start': float(film), 'declared_gain': float(gain),
                               'syntax': 'literal-ffmpeg-seek-duration-delay-table',
                               'source_file': str(path), 'source_file_sha256': v1.sha(path),
                               'line': text.count('\n', 0, match.start()) + 1, 'quote': match.group(0)})
        # A named helper reads an ID-addressed WAV and copies [from,to) samples
        # to a film-time destination. Numeric call sites remain data, never code.
        definitions = re.finditer(r'const\s+(\w+)\s*=\s*\(\s*id\s*,\s*from\s*,\s*to\s*,\s*when\s*,\s*gain\s*\)\s*=>\s*\{', text)
        for definition in definitions:
            body = text[definition.end():text.find('\n};', definition.end())]
            if not all(token in body for token in ['readWav', '${id}.wav', 'from * SR', 'to * SR', 'at(when)', 'src[']):
                continue
            pattern = r'\b' + re.escape(definition.group(1)) + r'\(\s*["\']([^"\']+)["\']\s*,\s*(' + NUMBER + r')\s*,\s*(' + NUMBER + r')\s*,\s*(' + NUMBER + r')\s*,\s*(' + NUMBER + r')\s*\)'
            for match in re.finditer(pattern, text):
                name, start, end, film, gain = match.groups()
                routes.append({'asset_name': name, 'asset_paths': [str(p) for p in by_stem.get(name, [])],
                               'source_start': float(start), 'source_end': float(end), 'film_start': float(film),
                               'declared_gain': float(gain), 'syntax': 'literal-wav-copy-helper',
                               'source_file': str(path), 'source_file_sha256': v1.sha(path),
                               'line': text.count('\n', 0, match.start()) + 1, 'quote': match.group(0),
                               'helper_quote': text[definition.start():definition.end()] + body + '\n};'})
    return routes


def dot_diagnostics(reference, target):
    r, y = reference - reference.mean(), target - target.mean()
    er, ey = float(np.dot(r, r)), float(np.dot(y, y))
    if er <= 1e-20 or ey <= 1e-20:
        return {'correlation': 0., 'gain': 0.}
    covariance = float(np.dot(r, y))
    return {'correlation': covariance / np.sqrt(er * ey), 'gain': covariance / er}


def public_proof(value, project):
    if isinstance(value, dict):
        return {key: public_proof(item, project) for key, item in value.items()}
    if isinstance(value, list):
        return [public_proof(item, project) for item in value]
    if isinstance(value, str):
        return value.replace(str(project.resolve()), 'project')
    return value


def source_asset_mapping(source, reference, route, rate, asset_cache):
    """Locate the canonical waveform in an actual asset, independent of its name."""
    best = None
    for name in route['asset_paths']:
        if name not in asset_cache:
            actual, _ = v1.decode(Path(name), rate)
            asset_cache[name] = (actual, v1.Search(actual, len(actual), CONFIG))
        actual, search = asset_cache[name]
        if len(actual) < len(reference):
            continue
        curve = search.correlations(reference, 'full:None', None)
        position = int(np.argmax(np.abs(curve)))
        score = float(curve[position])
        if abs(score) >= CONFIG['asset_canonical_correlation_minimum'] and (best is None or abs(score) > abs(best['correlation'])):
            best = {'asset': name, 'asset_sha256': v1.sha(name), 'canonical_start_in_asset_seconds': position / rate,
                    'correlation': score, 'proof': 'actual-full-canonical-waveform-in-actual-asset'}
    if best is not None:
        return best
    # Supplied source identifiers are source-pool names, not cohort labels.
    # This is only a proposal: actual final-waveform corroboration and quoted
    # generator semantics remain mandatory; an alias alone proves no identity.
    original = Path(source['provenance']['original_media']).stem
    code = original.split('-')[0]
    name = Path(route['asset_name']).name
    if re.match(r'^' + re.escape(code) + r'(?:\D|$)', name):
        return {'asset': None, 'canonical_start_in_asset_seconds': source['source_origin_seconds'],
                'correlation': None, 'proof': 'declared-supplied-source-alias-plus-required-final-waveform-corroboration'}
    return None


def route_candidates(source, reference, actual, search, routes, asset_cache):
    if source['kind'] != 'role':
        return [], []
    rate = CONFIG['sample_rate']
    out, diagnostics = [], []
    for route in routes:
        mapping = source_asset_mapping(source, reference, route, rate, asset_cache)
        if mapping is None:
            continue
        origin = mapping['canonical_start_in_asset_seconds']
        start = max(0., route['source_start'] - origin)
        end = min(len(reference) / rate, route['source_end'] - origin)
        if end <= start or route['declared_gain'] == 0:
            continue
        a, b = round(start * rate), round(end * rate)
        expected_offset = route['film_start'] - route['source_start'] + origin
        spread = round(CONFIG['route_alignment_search_seconds'] * rate)
        center = round(expected_offset * rate)
        curves = {}
        for name, bounds in CONFIG['bands'].items():
            ref = v1.filtered(reference, bounds, rate)[a:b]
            curves[name] = (ref, search.correlations(ref, name + ':' + str(bounds), bounds), bounds)
        positions = range(max(0, center + a - spread), min(len(actual) - (b - a), center + a + spread) + 1)
        positions = list(positions)
        if not positions:
            continue
        # Two coherent bands at one exact location, not independent band peaks.
        position = max(positions, key=lambda n: sorted(abs(float(c[n])) if c is not None else 0. for _, c, _ in curves.values())[-2])
        offset = position - a
        bands = {name: dot_diagnostics(ref, search.band(name + ':' + str(bounds), bounds)[0][position:position + b - a])
                 for name, (ref, _, bounds) in curves.items()}
        ordered = sorted(bands.values(), key=lambda x: abs(x['correlation']), reverse=True)
        gains = [x['gain'] for x in bands.values() if abs(x['correlation']) >= CONFIG['route_aggregate_full_minimum']]
        gain_scale = float(np.median(np.abs(gains))) if gains else 0.
        gain_spread = float(np.std(gains) / gain_scale) if gain_scale else float('inf')
        qualified = (abs(ordered[0]['correlation']) >= CONFIG['route_aggregate_band_minimum']
                     and abs(bands['full']['correlation']) >= CONFIG['route_aggregate_full_minimum']
                     and len(gains) >= 2 and gain_spread <= CONFIG['route_gain_relative_spread_maximum'])
        # Report counterfactual soundtrack matches, including nearby periodic
        # aliases. The semantic binder receives ambiguity rather than a hidden
        # assertion that every high correlation uniquely proves source identity.
        full_curve = curves['full'][1]
        outside = np.ones(len(full_curve), dtype=bool)
        outside[max(0, position - (b - a)):min(len(full_curve), position + (b - a))] = False
        counterfactual = float(np.max(np.abs(full_curve[outside]))) if outside.any() else None
        diagnostic = {'route': route, 'asset_mapping': mapping, 'bands': bands, 'relative_gain_spread': gain_spread,
                      'counterfactual_fullband_maximum': counterfactual, 'qualified': bool(qualified)}
        diagnostics.append(diagnostic)
        if not qualified:
            continue
        total = float(np.dot(reference, reference))
        out.append({'source_id': source['id'], 'source_start_seconds': a / rate, 'source_end_seconds': b / rate,
                    'film_start_seconds': position / rate, 'film_end_seconds': (position + b - a) / rate,
                    'source_mapping_offset_seconds': offset / rate, 'correlation': bands['full']['correlation'],
                    'band_correlations': {name: x['correlation'] for name, x in bands.items()},
                    'mechanically_qualified': True, 'source_energy_fraction': float(np.dot(reference[a:b], reference[a:b]) / total),
                    'qualification_evidence': {'method': 'actual-source-backed variable-interval waveform agreement',
                        'extent_method': 'Literal retained source interval corroborated as a whole in the actual film; individual masked quiet blocks are not separately discarded',
                        'source_route_proof': diagnostic, 'requires_actual_generator_corroboration': True,
                        'requires_semantic_identity_and_story_binding': True}})
    return out, diagnostics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--references', type=Path, default=BASE / 'references/manifest.json')
    parser.add_argument('--project', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    started = monotonic()
    manifest_path = args.references / 'manifest.json' if args.references.is_dir() else args.references
    root = manifest_path.resolve().parent
    manifest = json.loads(manifest_path.read_text())
    project = args.project or args.video.resolve().parent / 'project'
    routes = literal_routes(project)
    actual, command = v1.decode(args.video, CONFIG['sample_rate'])
    if not len(actual) or not np.isfinite(actual).all():
        raise ValueError('Decoded audio is empty or nonfinite')
    search = v1.Search(actual, max(s['sample_count'] for s in manifest['sources']), CONFIG)
    silent = bool(np.max(np.abs(actual)) == 0)
    candidates, statuses, exported, route_diagnostics = [], [], [], []
    asset_cache = {}
    for source in manifest['sources']:
        wav_path = root / source['reference_wav']
        if v1.sha(wav_path) != source['reference_sha256'] or v1.sha(root / source['energy_cumulative_file']) != source['energy_cumulative_sha256']:
            raise ValueError('Canonical reference hash mismatch')
        rate, reference = v1.wavfile.read(wav_path)
        reference = reference.astype(float)
        if rate != CONFIG['sample_rate']:
            raise ValueError('Reference sample rate mismatch')
        if silent:
            rows, status = [], {'id': source['id'], 'identity_search_status': 'digital_silence_proven', 'absence_is_proven': True, 'qualified_candidates': 0}
        else:
            rows, status = v1.extract_source(source, reference, actual, search, CONFIG)
            extra, diagnostics = route_candidates(source, reference, actual, search, routes, asset_cache)
            route_diagnostics.extend({'source_id': source['id'], **x} for x in diagnostics)
            for index, row in enumerate(extra):
                row['id'] = source['id'] + ':route:' + str(index).zfill(4)
            for row in rows:
                conflicts = [x['id'] for x in extra
                             if min(row['film_end_seconds'], x['film_end_seconds']) > max(row['film_start_seconds'], x['film_start_seconds'])
                             and abs(row['source_mapping_offset_seconds'] - x['source_mapping_offset_seconds']) > CONFIG['source_mapping_merge_tolerance_seconds']]
                if conflicts:
                    row['qualification_evidence']['source_route_coordinate_conflicts'] = conflicts
                    row['qualification_evidence']['coordinate_conflict_warning'] = 'A source-backed route at this film event has a different canonical mapping. A shared short waveform is not sufficient evidence for selecting this conflicting source interval.'
            rows.extend(extra)
            status['route_qualified_candidates'] = len(extra)
            status['qualified_candidates'] = sum(row['mechanically_qualified'] for row in rows)
            status['identity_search_status'] = 'qualified_candidates' if status['qualified_candidates'] else 'not_detected_within_bounds'
        status['all_qualified_source_extent_before_story_binding'] = v1.unique_coverage(source, [x for x in rows if x['mechanically_qualified']], root)
        candidates.extend(rows)
        statuses.append(status)
        exported.append({**source, 'reference_wav': str(wav_path), 'energy_cumulative_file': str(root / source['energy_cumulative_file']),
                         'identity_search_status': status['identity_search_status'], 'absence_is_proven': status['absence_is_proven'], 'search_completed': True})
    for row in candidates:
        row['qualification_evidence'] = public_proof(row['qualification_evidence'], project)
    output = {'schema_version': 'portable-audio-candidates-v2', 'video': str(args.video.resolve()), 'video_sha256': v1.sha(args.video),
              'duration_seconds': len(actual) / CONFIG['sample_rate'], 'sample_rate': CONFIG['sample_rate'],
              'extractor_sha256': v1.sha(__file__), 'frozen_v1_extractor_sha256': v1.sha(BASE / 'extract_audio.py'),
              'reference_manifest': str(manifest_path.resolve()), 'reference_manifest_sha256': v1.sha(manifest_path),
              'config': CONFIG, 'sources': exported, 'candidates': candidates, 'source_search': statuses,
              'route_diagnostics': public_proof(route_diagnostics, project), 'literal_route_count': len(routes),
              'search_status': 'completed', 'digital_silence_proven': silent, 'decoded_peak': float(np.max(np.abs(actual))),
              'decode_command': command, 'elapsed_seconds': monotonic() - started,
              'qualification_boundary': 'Actual source-backed interval candidates require quoted generator corroboration and semantic identity/beat binding. Nonzero no-match remains unresolved, not absent.',
              'new_actor_runs': 0, 'new_reward': None}
    v1.write(args.output, output)
    print(json.dumps({'output': str(args.output), 'candidates': len(candidates), 'route_candidates': sum(':route:' in x['id'] for x in candidates), 'seconds': output['elapsed_seconds']}))


if __name__ == '__main__':
    main()

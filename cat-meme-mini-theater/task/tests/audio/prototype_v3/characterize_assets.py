"""Read-only packaged-audio characterization and final-film correspondence.

Raw signal evidence only. Neither names nor low template correlation become an
absence decision. No project code is executed and no cached verdict is consumed.
"""
import argparse
import importlib.util
import json
from pathlib import Path
from time import monotonic
import numpy as np
from scipy.signal import find_peaks

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('waveform_core', BASE / 'extract_audio.py')
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
RATE = 8000
SKIP = {'node_modules', '.git', 'dist', '.next', 'build'}


def scan(root, suffixes):
    return sorted(path for path in root.rglob('*') if path.is_file() and path.suffix.lower() in suffixes
                  and not any(part in SKIP for part in path.relative_to(root).parts))


def spectrum(y, rate):
    if not len(y) or np.max(np.abs(y)) == 0:
        return {'dominant_components': [], 'centroid_hz': None, 'energy_bands': {}}
    transform = np.fft.rfft((y - y.mean()) * np.hanning(len(y)), n=max(65536, 2 ** int(np.ceil(np.log2(len(y))))))
    power = np.abs(transform) ** 2
    frequency = np.fft.rfftfreq((len(power) - 1) * 2, 1 / rate)
    peaks, _ = find_peaks(power, distance=max(1, round(15 / (frequency[1] - frequency[0]))))
    peaks = sorted(map(int, peaks), key=lambda n: power[n], reverse=True)[:8]
    components = []
    for n in peaks:
        if n == 0 or n == len(power) - 1:
            continue
        logs = np.log(np.maximum(power[n - 1:n + 2], 1e-30))
        denominator = logs[0] - 2 * logs[1] + logs[2]
        delta = .5 * (logs[0] - logs[2]) / denominator if denominator else 0.
        components.append({'frequency_hz': float((n + delta) * (frequency[1] - frequency[0])),
                           'relative_peak_power': float(power[n] / power.max())})
    total = float(power.sum())
    return {'dominant_components': components, 'centroid_hz': float(np.dot(frequency, power) / total),
            'energy_bands': {str(a) + '-' + str(b): float(power[(frequency >= a) & (frequency < b)].sum() / total)
                             for a, b in [(0, 100), (100, 300), (300, 800), (800, 1500), (1500, 2800), (2800, 4001)]}}


def characterize(y):
    energy = np.r_[0., np.cumsum(y * y)]
    total = float(energy[-1])
    q = {str(p): float(np.searchsorted(energy, p * total) / RATE) for p in [.001, .01, .1, .5, .9, .99, .999]} if total else {}
    frames = []
    for a in range(0, len(y), round(.05 * RATE)):
        b = min(len(y), a + round(.05 * RATE))
        fragment = y[a:b]
        if len(fragment) < 32:
            continue
        description = spectrum(fragment, RATE)
        frames.append({'start_seconds': a / RATE, 'end_seconds': b / RATE,
                       'rms': float(np.sqrt(np.mean(fragment * fragment))),
                       'dominant_components': description['dominant_components'][:3]})
    return {'duration_seconds': len(y) / RATE, 'sample_count': len(y), 'peak': float(np.max(np.abs(y))),
            'rms': float(np.sqrt(np.mean(y * y))), 'total_energy': total,
            'energy_time_quantiles_seconds': q, 'spectrum': spectrum(y, RATE), 'time_slices': frames}


def comparison(template, target):
    """Best full-template alignment when it fits; also reverse for cropped assets."""
    if len(template) > len(target):
        result = comparison(target, template)
        return {'direction': 'full-asset-inside-canonical', **{k: v for k, v in result.items() if k != 'direction'}}
    search = core.Search(target, len(template), core.CONFIG)
    band_rows = {}
    for name, bounds in core.CONFIG['bands'].items():
        ref = core.filtered(template, bounds, RATE)
        curve = search.correlations(ref, name + ':' + str(bounds), bounds)
        band_rows[name] = (ref, curve, bounds)
    positions = set()
    for _, curve, _ in band_rows.values():
        if curve is not None:
            positions.add(int(np.argmax(np.abs(curve))))
    measured = []
    for position in sorted(positions):
        scores, gains = {}, {}
        for name, (ref, curve, bounds) in band_rows.items():
            tgt = search.band(name + ':' + str(bounds), bounds)[0][position:position + len(template)]
            ref, tgt = ref - ref.mean(), tgt - tgt.mean()
            covariance, er = float(np.dot(ref, tgt)), float(np.dot(ref, ref))
            scores[name] = float(curve[position]) if curve is not None else 0.
            gains[name] = covariance / er if er > 1e-20 else None
        measured.append({'offset_seconds': position / RATE, 'band_correlations': scores, 'fitted_gains': gains,
                         'fullband_gain_normalized_residual_fraction': float(np.sqrt(max(0., 1 - scores['full'] ** 2)))})
    best = max(measured, key=lambda x: abs(x['band_correlations']['full']))
    return {'direction': 'full-template-inside-target', 'full_template_seconds': len(template) / RATE,
            'best_fullband_alignment': best, 'other_band_peak_alignments': measured}


def routing_mentions(project, asset):
    result = []
    relative = asset.relative_to(project).as_posix()
    for path in scan(project, {'.tsx', '.ts', '.js', '.mjs', '.py', '.sh', '.json'}):
        if path.stat().st_size > 500_000 or path.name.endswith('lock.json'):
            continue
        lines = path.read_text(errors='replace').splitlines()
        for index, line in enumerate(lines):
            if asset.name not in line:
                continue
            lo, hi = max(0, index - 3), min(len(lines), index + 4)
            result.append({'source_file': 'project/' + path.relative_to(project).as_posix(), 'source_sha256': core.sha(path),
                           'start_line': lo + 1, 'end_line': hi, 'quote': '\n'.join(lines[lo:hi])})
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--artifact', type=Path, required=True)
    p.add_argument('--project', type=Path, help='Override project asset root, including a canonical-WAV positive control')
    p.add_argument('--references', type=Path, default=BASE / 'references/manifest.json')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--compact-output', type=Path)
    args = p.parse_args()
    started = monotonic()
    video = args.artifact / 'final.mp4'
    project = args.project or args.artifact / 'project'
    manifest = json.loads(args.references.read_text())
    refs = args.references.resolve().parent
    actual, _ = core.decode(video, RATE)
    effects = []
    reference_signals = {}
    for source in manifest['sources']:
        if source['kind'] != 'effect':
            continue
        path = refs / source['reference_wav']
        if core.sha(path) != source['reference_sha256']:
            raise ValueError('Canonical hash mismatch')
        rate, y = core.wavfile.read(path)
        if rate != RATE:
            raise ValueError('Canonical rate mismatch')
        reference_signals[source['id']] = y.astype(float)
        effects.append({'id': source['id'], 'family': source['family'], 'sha256': source['reference_sha256'],
                        'recipe': source['provenance']['recipe'], 'signal': characterize(y.astype(float))})
    assets = []
    for path in scan(project, {'.wav', '.m4a', '.mp3', '.aac', '.ogg'}):
        y, command = core.decode(path, RATE)
        if not len(y) or not np.isfinite(y).all():
            continue
        description = characterize(y)
        record = {'asset': 'project/' + path.relative_to(project).as_posix(), 'sha256': core.sha(path),
                  'signal': description, 'actual_source_mentions': routing_mentions(project, path),
                  'canonical_comparisons': {identifier: comparison(ref, y) for identifier, ref in reference_signals.items()}}
        # Long music/combined tracks retain raw template comparisons, but a
        # complete short one-shot also has an independent asset-to-film match.
        if len(y) <= RATE * 5:
            record['full_asset_to_actual_film'] = comparison(y, actual)
        else:
            record['full_asset_to_actual_film'] = None
            record['full_asset_to_actual_film_note'] = 'Asset longer than five seconds; no short one-shot correspondence claim.'
        assets.append(record)
    output = {'schema_version': 'packaged-audio-assets-v1', 'video_sha256': core.sha(video), 'sample_rate': RATE,
              'extractor_sha256': core.sha(__file__), 'waveform_dependency_sha256': core.sha(BASE / 'extract_audio.py'),
              'reference_manifest_sha256': core.sha(args.references), 'canonical_effects': effects, 'assets': assets,
              'scope': 'Raw actual unmixed asset spectra, canonical comparisons and actual asset-to-film matches. Low NCC or filenames alone do not assign absence; generator/routing coverage and identity adjudication remain external.',
              'elapsed_seconds': monotonic() - started, 'new_actor_runs': 0, 'new_reward': None}
    core.write(args.output, output)
    if args.compact_output:
        compact = {key: output[key] for key in ['schema_version', 'video_sha256', 'sample_rate', 'extractor_sha256',
                                                'waveform_dependency_sha256', 'reference_manifest_sha256', 'scope']}
        compact['canonical_effects'] = [{**{key: row[key] for key in ['id', 'family', 'sha256', 'recipe']},
                                        'duration_seconds': row['signal']['duration_seconds'], 'spectrum': row['signal']['spectrum']}
                                       for row in effects]
        compact['assets'] = [{**{key: row[key] for key in ['asset', 'sha256', 'actual_source_mentions', 'canonical_comparisons', 'full_asset_to_actual_film']},
                              'duration_seconds': row['signal']['duration_seconds'], 'spectrum': row['signal']['spectrum']}
                             for row in assets]
        core.write(args.compact_output, compact)
    print(json.dumps({'output': str(args.output), 'asset_count': len(assets), 'seconds': output['elapsed_seconds']}))


if __name__ == '__main__':
    main()

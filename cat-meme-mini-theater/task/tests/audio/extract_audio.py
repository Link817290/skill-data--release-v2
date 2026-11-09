"""Portable artifact-only source waveform candidate extraction.

No run IDs, model conditions, answer cache or Golden film timestamps are inputs.
Strong matches and weaker leads remain distinct; story binding is external.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
from time import monotonic

for key in ['OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS']:
    os.environ.setdefault(key, '1')
import numpy as np
from scipy.fft import rfft, irfft, next_fast_len
from scipy.io import wavfile
from scipy.signal import butter, sosfiltfilt, find_peaks

CONFIG = {
    'sample_rate': 8000, 'role_window_seconds': [.1, .2, .5], 'window_stride_seconds': .1,
    'peak_count_per_band': 2, 'maximum_candidates_per_source': 120,
    'source_window_minimum_energy_fraction': 1e-4, 'target_minimum_rms': 1e-6,
    'role_short_band_correlation_minimum': .82, 'role_short_second_band_minimum': .75,
    'role_long_fullband_minimum': .62, 'role_long_second_band_minimum': .65,
    'effect_fullband_minimum': .78, 'effect_second_band_minimum': .75,
    'complexity_entropy_minimum': .2, 'source_coverage_numerical_tail_tolerance': 1e-6,
    'source_mapping_merge_tolerance_seconds': .025,
    'extent_block_seconds': .0125, 'extent_context_seconds': .05,
    'extent_band_correlation_minimum': .5, 'extent_minimum_relative_gain': .1,
    'bands': {'full': None, 'speech': [300, 3500], 'high': [800, 3500]},
}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2) + '\n')


def decode(p, rate):
    command = ['ffmpeg', '-v', 'error', '-threads', '1', '-i', str(p), '-vn', '-ac', '1', '-ar', str(rate), '-f', 'f32le', 'pipe:1']
    r = subprocess.run(command, capture_output=True, check=True, timeout=180)
    return np.frombuffer(r.stdout, dtype='<f4').astype(np.float64), command


def filtered(y, band, rate):
    if band is None:
        return y
    sos = butter(4, band, btype='bandpass', fs=rate, output='sos')
    return sosfiltfilt(sos, y)


def entropy(y):
    power = np.abs(rfft(y - y.mean())) ** 2
    total = power.sum()
    if total <= 1e-30:
        return 0.
    p = power / total
    p = p[p > 0]
    return float(-np.sum(p * np.log(p)) / np.log(len(power)))


class Search:
    def __init__(self, y, max_window, config):
        self.y = y
        self.config = config
        self.rate = config['sample_rate']
        self.fft_length = next_fast_len(len(y) + max_window - 1)
        self.cache = {}

    def band(self, name, bounds):
        if name not in self.cache:
            y = filtered(self.y, bounds, self.rate)
            self.cache[name] = (y, rfft(y, self.fft_length), np.r_[0., np.cumsum(y)], np.r_[0., np.cumsum(y * y)])
        return self.cache[name]

    def correlations(self, template, name, bounds):
        actual, transform, sums, squares = self.band(name, bounds)
        t = template - template.mean()
        n = len(t)
        reference_energy = float(np.dot(t, t))
        if reference_energy <= 1e-25 or n > len(actual):
            return None
        nout = len(actual) - n + 1
        numerator = irfft(transform * rfft(t[::-1], self.fft_length), self.fft_length)[n - 1:n - 1 + nout]
        energy = squares[n:] - squares[:-n] - (sums[n:] - sums[:-n]) ** 2 / n
        active = energy >= n * self.config['target_minimum_rms'] ** 2
        denominator = np.sqrt(np.maximum(energy, 0) * reference_energy)
        scores = np.divide(numerator, denominator, out=np.zeros_like(numerator), where=active & (denominator > 0))
        return np.clip(scores, -1, 1)


def windows(n, kind, config):
    rate = config['sample_rate']
    lengths = {n}
    if kind == 'role':
        lengths.update(round(seconds * rate) for seconds in config['role_window_seconds'] if round(seconds * rate) <= n)
    else:
        lengths.update(round(seconds * rate) for seconds in [.1, .2] if round(seconds * rate) <= n)
    stride = round(config['window_stride_seconds'] * rate)
    result = set()
    for width in lengths:
        for start in range(0, n - width + 1, stride):
            result.add((start, start + width))
        result.add((n - width, n))
    return sorted(result, key=lambda value: (-(value[1] - value[0]), value[0]))


def consolidate(rows, reference, config):
    rate = config['sample_rate']
    qualified = [row for row in rows if row['mechanically_qualified']]
    qualified.sort(key=lambda row: row['qualification_evidence']['strength'], reverse=True)
    groups = []
    for row in qualified:
        group = next((group for group in groups if abs(group[0]['source_mapping_offset_seconds'] - row['source_mapping_offset_seconds']) <= config['source_mapping_merge_tolerance_seconds']), None)
        if group is None:
            groups.append([row])
        else:
            group.append(row)
    merged = []
    total = float(np.dot(reference, reference))
    for group in groups:
        offset = float(np.median([row['source_mapping_offset_seconds'] for row in group]))
        ordered = sorted(group, key=lambda row: row['source_start_seconds'])
        pieces = []
        for row in ordered:
            if pieces and row['source_start_seconds'] <= pieces[-1]['end'] + 1 / rate:
                pieces[-1]['end'] = max(pieces[-1]['end'], row['source_end_seconds'])
                pieces[-1]['support'].append(row)
            else:
                pieces.append({'start': row['source_start_seconds'], 'end': row['source_end_seconds'], 'support': [row]})
        for piece in pieces:
            representative = max(piece['support'], key=lambda row: row['qualification_evidence']['strength'])
            candidate = dict(representative)
            a, b = round(piece['start'] * rate), round(piece['end'] * rate)
            candidate.update(source_start_seconds=piece['start'], source_end_seconds=piece['end'],
                             film_start_seconds=offset + piece['start'], film_end_seconds=offset + piece['end'],
                             source_mapping_offset_seconds=offset, source_energy_fraction=float(np.dot(reference[a:b], reference[a:b]) / total))
            candidate['qualification_evidence'] = {**representative['qualification_evidence'], 'supporting_windows': len(piece['support']),
                'maximum_mapping_spread_seconds': max(abs(row['source_mapping_offset_seconds'] - offset) for row in piece['support']),
                'support': [{'source_start_seconds': row['source_start_seconds'], 'source_end_seconds': row['source_end_seconds'],
                             'film_start_seconds': row['film_start_seconds'], 'correlation': row['correlation'],
                             'band_correlations': row['band_correlations']} for row in piece['support'][:16]],
                'method': 'Union of overlapping individually qualified source windows with a coherent source-to-film mapping'}
            merged.append(candidate)
    leads = sorted((row for row in rows if not row['mechanically_qualified']), key=lambda row: row['qualification_evidence']['strength'], reverse=True)
    selected_leads = []
    for row in leads:
        if any(abs(row['source_mapping_offset_seconds'] - prior['source_mapping_offset_seconds']) < .05 for prior in selected_leads):
            continue
        selected_leads.append(row)
        if len(selected_leads) == 8:
            break
    return sorted(merged, key=lambda row: (row['source_energy_fraction'], row['qualification_evidence']['strength']), reverse=True) + selected_leads


def extract_source(source, reference, signal, search, config):
    rate = config['sample_rate']
    bands = dict(config['bands'])
    if source['kind'] == 'effect':
        spectrum = np.abs(rfft(reference)) ** 2
        dominant = float(np.argmax(spectrum) * rate / len(reference))
        if dominant > 250:
            bands['characteristic'] = [max(30, dominant - max(80, dominant * .06)), min(rate / 2 - 50, dominant + max(80, dominant * .06))]
        else:
            bands['characteristic'] = [10, 260]
    reference_bands = {name: filtered(reference, bounds, rate) for name, bounds in bands.items()}
    total = float(np.dot(reference, reference))
    raw = []
    searched = 0
    for a, b in windows(len(reference), source['kind'], config):
        canonical = reference[a:b]
        fraction = float(np.dot(canonical, canonical) / total) if total else 0
        if fraction < config['source_window_minimum_energy_fraction']:
            continue
        searched += 1
        correlations = {name: search.correlations(y[a:b], name + ':' + str(bounds), bounds) for (name, bounds), y in zip(bands.items(), reference_bands.values())}
        positions = set()
        for curve in correlations.values():
            if curve is None:
                continue
            distance = max(1, (b - a) // 2)
            peaks, _ = find_peaks(np.abs(curve), distance=distance)
            if not len(peaks):
                peaks = np.array([int(np.argmax(np.abs(curve)))])
            top = sorted(map(int, peaks), key=lambda n: abs(curve[n]), reverse=True)[:config['peak_count_per_band']]
            positions.update(top)
        complexity = entropy(canonical)
        width = (b - a) / rate
        for position in positions:
            values = {name: float(curve[position]) if curve is not None else 0. for name, curve in correlations.items()}
            absolute = sorted((abs(v) for v in values.values()), reverse=True)
            full = abs(values['full'])
            if source['kind'] == 'role':
                coherent_short = absolute[0] >= config['role_short_band_correlation_minimum'] and absolute[1] >= config['role_short_second_band_minimum'] and complexity >= config['complexity_entropy_minimum']
                coherent_long = width >= .5 and full >= config['role_long_fullband_minimum'] and absolute[1] >= config['role_long_second_band_minimum']
                qualified = coherent_short or coherent_long
            else:
                # Effect identity needs its full distinctive recipe, not an arbitrary shared sinusoidal fragment.
                qualified = a == 0 and b == len(reference) and full >= config['effect_fullband_minimum'] and absolute[1] >= config['effect_second_band_minimum']
            strength = absolute[1] if qualified else min(absolute[0], .699)
            if qualified or absolute[0] >= .45:
                raw.append({'source_id': source['id'], 'film_start_seconds': position / rate, 'film_end_seconds': (position + b - a) / rate,
                            'source_start_seconds': a / rate, 'source_end_seconds': b / rate,
                            'correlation': values['full'], 'band_correlations': values,
                            'mechanically_qualified': bool(qualified), 'source_energy_fraction': fraction,
                            'qualification_evidence': {'source_window_entropy': complexity, 'window_seconds': width,
                                'second_strongest_band_correlation': absolute[1], 'strength': strength,
                                'method': 'multiband source waveform agreement; effect identity requires complete recipe'},
                            'source_mapping_offset_seconds': (position - a) / rate})
    grouped = consolidate(raw, reference, config)
    refined = []
    for anchor in grouped:
        if not anchor['mechanically_qualified']:
            refined.append(anchor)
            continue
        a = round(anchor['source_start_seconds'] * rate)
        b = round(anchor['source_end_seconds'] * rate)
        offset = round(anchor['source_mapping_offset_seconds'] * rate)
        # Correlation on a larger reference window establishes identity/location;
        # only locally supported source samples contribute acoustic extent.
        block = max(1, round(config['extent_block_seconds'] * rate))
        context = max(block, round(config['extent_context_seconds'] * rate))
        supported = []
        diagnostics = []
        for left in range(a, b, block):
            right = min(b, left + block)
            center = (left + right) // 2
            lo, hi = max(0, center - context // 2), min(len(reference), center + context // 2)
            target_left, target_right = offset + left, offset + right
            if target_left < 0 or target_right > len(signal):
                continue
            actual_block = signal[target_left:target_right]
            if np.mean(actual_block * actual_block) < config['target_minimum_rms'] ** 2:
                diagnostics.append((left, right, 0., 0.))
                continue
            best_correlation, best_gain = 0., 0.
            for name, bounds in bands.items():
                actual_band = search.band(name + ':' + str(bounds), bounds)[0]
                ref = reference_bands[name][lo:hi]
                start, end = offset + lo, offset + hi
                if start < 0 or end > len(signal):
                    continue
                target = actual_band[start:end]
                ref, target = ref - ref.mean(), target - target.mean()
                er, et = float(np.dot(ref, ref)), float(np.dot(target, target))
                if er <= 1e-20 or et <= len(target) * config['target_minimum_rms'] ** 2:
                    continue
                covariance = float(np.dot(ref, target))
                correlation = abs(covariance / np.sqrt(er * et))
                if correlation > best_correlation:
                    best_correlation, best_gain = correlation, abs(covariance / er)
            diagnostics.append((left, right, best_correlation, best_gain))
        reliable_gains = [gain for _, _, correlation, gain in diagnostics if correlation >= config['extent_band_correlation_minimum']]
        typical_gain = float(np.median(reliable_gains)) if reliable_gains else 0.
        for left, right, correlation, gain in diagnostics:
            if correlation >= config['extent_band_correlation_minimum'] and gain >= typical_gain * config['extent_minimum_relative_gain']:
                if supported and left <= supported[-1][1]:
                    supported[-1][1] = right
                else:
                    supported.append([left, right])
        for left, right in supported:
            if np.dot(reference[left:right], reference[left:right]) <= total * 1e-6:
                continue
            candidate = dict(anchor)
            candidate.update(source_start_seconds=left / rate, source_end_seconds=right / rate,
                             film_start_seconds=(offset + left) / rate, film_end_seconds=(offset + right) / rate,
                             source_energy_fraction=float(np.dot(reference[left:right], reference[left:right]) / total))
            correlations_at_extent = {}
            for name, bounds in bands.items():
                ref = reference_bands[name][left:right]
                target = search.band(name + ':' + str(bounds), bounds)[0][offset + left:offset + right]
                ref, target = ref - ref.mean(), target - target.mean()
                er, et = float(np.dot(ref, ref)), float(np.dot(target, target))
                correlations_at_extent[name] = float(np.dot(ref, target) / np.sqrt(er * et)) if er > 1e-25 and et > 1e-25 else 0.
            candidate['correlation'] = correlations_at_extent['full']
            candidate['band_correlations'] = correlations_at_extent
            candidate['qualification_evidence'] = {**anchor['qualification_evidence'],
                'identity_anchor_source_interval': [a / rate, b / rate],
                'identity_anchor_correlation_scope': 'Strongest individually qualified supporting source window, not the entire merged interval',
                'extent_method': 'Local canonical-waveform agreement at the same source-to-film mapping; no credit for an unsupported tail',
                'extent_block_seconds': block / rate, 'typical_local_gain': typical_gain}
            refined.append(candidate)
    refined.sort(key=lambda row: (row['mechanically_qualified'], row['source_energy_fraction']), reverse=True)
    selected = refined[:config['maximum_candidates_per_source']]
    for n, row in enumerate(selected):
        row['id'] = source['id'] + ':' + str(n).zfill(4)
    return selected, {'id': source['id'], 'windows_searched': searched, 'raw_peak_candidates': len(raw), 'returned_candidates': len(selected),
                      'output_truncated': len(refined) > len(selected),
                      'qualified_candidates': sum(row['mechanically_qualified'] for row in selected),
                      'identity_search_status': 'qualified_candidates' if any(row['mechanically_qualified'] for row in selected) else 'not_detected_within_bounds',
                      'absence_is_proven': False, 'source_lineage_or_uncertainty_review_required_when_not_detected': True}


def unique_coverage(source, candidates, reference_root):
    data = json.loads((reference_root / source['energy_cumulative_file']).read_text())
    cumulative = np.asarray(data['cumulative_energy'])
    intervals = sorted((max(0, round(row['source_start_seconds'] * source['sample_rate'])), min(source['sample_count'], round(row['source_end_seconds'] * source['sample_rate']))) for row in candidates)
    merged = []
    for a, b in intervals:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    earned = sum(float(cumulative[b] - cumulative[a]) for a, b in merged)
    value = min(1., earned / source['total_energy']) if source['total_energy'] else 0
    return {'raw_coverage': value, 'snapped_coverage': 1. if 1 - value <= 1e-6 else value,
            'unique_source_intervals_seconds': [[a / source['sample_rate'], b / source['sample_rate']] for a, b in merged]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--references', type=Path, default=Path(__file__).resolve().parent / 'references/manifest.json', help='Reference manifest.json or its directory')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--config', type=Path)
    args = parser.parse_args()
    started = monotonic()
    manifest_path = args.references / 'manifest.json' if args.references.is_dir() else args.references
    root = manifest_path.resolve().parent
    manifest = json.loads(manifest_path.read_text())
    config = {**CONFIG, **(json.loads(args.config.read_text()) if args.config else {})}
    sources = manifest['sources']
    actual, command = decode(args.video, config['sample_rate'])
    if not len(actual) or not np.isfinite(actual).all():
        raise ValueError('Decoded audio is empty or nonfinite; never manufacture an absence verdict')
    max_window = max(source['sample_count'] for source in sources)
    search = Search(actual, max_window, config)
    candidates, statuses, exported = [], [], []
    silent = bool(np.max(np.abs(actual)) == 0)
    for source in sources:
        wav_path = root / source['reference_wav']
        if sha(wav_path) != source['reference_sha256'] or sha(root / source['energy_cumulative_file']) != source['energy_cumulative_sha256']:
            raise ValueError('Canonical reference hash mismatch')
        rate, y = wavfile.read(wav_path)
        if rate != config['sample_rate']:
            raise ValueError('Reference sample rate mismatch')
        y = y.astype(np.float64)
        if not silent:
            rows, status = extract_source(source, y, actual, search, config)
            candidates.extend(rows)
        else:
            rows, status = [], {'id': source['id'], 'identity_search_status': 'digital_silence_proven', 'absence_is_proven': True, 'qualified_candidates': 0}
        status['all_qualified_source_extent_before_story_binding'] = unique_coverage(source, [row for row in rows if row['mechanically_qualified']], root)
        statuses.append(status)
        item = dict(source)
        item['reference_wav'] = str(wav_path)
        item['energy_cumulative_file'] = str(root / source['energy_cumulative_file'])
        item['identity_search_status'] = status['identity_search_status']
        item['absence_is_proven'] = status['absence_is_proven']
        item['search_completed'] = True
        exported.append(item)
    output = {'schema_version': 'portable-audio-candidates-v1', 'video': str(args.video.resolve()), 'video_sha256': sha(args.video),
              'duration_seconds': len(actual) / config['sample_rate'], 'sample_rate': config['sample_rate'],
              'extractor_sha256': sha(__file__), 'reference_manifest': str(manifest_path.resolve()), 'reference_manifest_sha256': sha(manifest_path),
              'config': config, 'sources': exported, 'candidates': candidates, 'source_search': statuses,
              'search_status': 'completed', 'digital_silence_proven': silent, 'decoded_peak': float(np.max(np.abs(actual))),
              'decode_command': command, 'elapsed_seconds': monotonic() - started,
              'qualification_boundary': 'Mechanical source-pattern candidates and exact source-energy operands. No story binding or final reward is inferred. Nonzero audio with no qualified match requires source-lineage review or an explicit unknown.',
              'new_actor_runs': 0, 'new_reward': None}
    write(args.output, output)
    print(json.dumps({'output': str(args.output), 'candidates': len(candidates), 'qualified': sum(row['mechanically_qualified'] for row in candidates), 'seconds': output['elapsed_seconds']}))


if __name__ == '__main__':
    main()

"""Portable artifact measurement pipeline; only the current settlement is public."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from normalize_artifact import normalize
from soundtrack_judge import judge as judge_soundtrack

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'current_bench'))
from settlement import Unmeasured, settle


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def load(path):
    return json.loads(path.read_text())


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def safe_text(value):
    for key in ('LLM_JUDGE_API_KEY',):
        secret = os.environ.get(key)
        if secret:
            value = value.replace(secret, '[REDACTED]')
    return value


def outside(path, artifact, label):
    resolved = path.resolve()
    if resolved == artifact or artifact in resolved.parents:
        raise ValueError(label + ' must be verifier-owned, outside the candidate artifact')


class InvalidSourceEntry(ValueError):
    pass


def source_entry_error(artifact):
    if artifact.is_symlink():
        return 'Submitted artifact root must be a self-contained directory, not a symbolic link.'
    for name in ('final.mp4', 'edit-plan.json', 'project'):
        if (artifact / name).is_symlink():
            return 'Submitted ' + name + ' must be a regular artifact entry, not a symbolic link.'
    return None


def execute(command, output):
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(command, capture_output=True, text=True)
    record = {'command': command, 'working_directory': os.getcwd(), 'started_at': started,
              'finished_at': datetime.now(timezone.utc).isoformat(), 'exit_code': result.returncode,
              'stdout': safe_text(result.stdout), 'stderr': safe_text(result.stderr)}
    save(output, record)
    return result.returncode


def publish(output, result):
    save(output / 'reward_detail.json', result)
    if result.get('rewards') is not None:
        save(output / 'reward.json', result['rewards'])
        for name, lens in [('reward.txt', 'strict'), ('reward_strict.txt', 'strict'), ('reward_lenient.txt', 'lenient')]:
            (output / name).write_text(str(result['rewards'][lens]) + '\n')
    else:
        for name in ('reward.json', 'reward.txt', 'reward_strict.txt', 'reward_lenient.txt'):
            path = output / name
            if path.exists():
                path.unlink()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('workspace', type=Path, nargs='?', default=Path('/workspace'))
    parser.add_argument('--artifact', type=Path)
    parser.add_argument('--output', type=Path, default=Path(os.environ.get('VERIFIER_OUTPUT_DIR', '/logs/verifier')))
    parser.add_argument('--mode', choices=['replay', 'fresh'], default=os.environ.get('LLM_JUDGE_MODE', 'fresh'))
    cache_root = Path(os.environ.get('LLM_JUDGE_CACHE_DIR') or os.environ.get('JUDGE_CACHE_ROOT') or str(HERE / 'golden_replay'))
    parser.add_argument('--cache-dir', type=Path, default=Path(os.environ.get('LLM_JUDGE_CACHE', str(cache_root / 'visual'))))
    parser.add_argument('--audio-cache-dir', type=Path, default=Path(os.environ.get('AUDIO_JUDGE_CACHE', str(cache_root / 'audio'))))
    parser.add_argument('--audio-resolution-cache-dir', type=Path, default=Path(os.environ.get('AUDIO_RESOLUTION_CACHE', str(cache_root / 'audio-resolution'))))
    parser.add_argument('--ownership-cache-dir', type=Path, default=Path(os.environ.get('OWNERSHIP_JUDGE_CACHE', str(cache_root / 'ownership'))))
    parser.add_argument('--rerender-proof', type=Path)
    parser.add_argument('--runtime-modules', type=Path, default=Path(os.environ.get('REMOTION_RUNTIME_MODULES', '/opt/remotion-runtime/node_modules')))
    args = parser.parse_args()
    artifact = (args.artifact or (args.workspace if (args.workspace / 'final.mp4').exists()
                                 else args.workspace / 'output')).absolute()
    entry_error = source_entry_error(artifact)
    if entry_error is None:
        artifact = artifact.resolve()
    args.output = args.output.resolve()
    outside(args.output, artifact, 'Verifier output')
    outside(args.cache_dir, artifact, 'Visual cache')
    outside(args.audio_cache_dir, artifact, 'Audio cache')
    outside(args.audio_resolution_cache_dir, artifact, 'Audio resolution cache')
    outside(args.ownership_cache_dir, artifact, 'Ownership cache')
    args.output.mkdir(parents=True, exist_ok=True)
    run = args.output / 'runs' / uuid.uuid4().hex
    run.mkdir(parents=True)
    for name in ('reward.json', 'reward_detail.json', 'reward.txt', 'reward_strict.txt', 'reward_lenient.txt'):
        old = args.output / name
        if old.exists():
            old.replace(run / ('previous-' + name))
    started = datetime.now(timezone.utc).isoformat()
    video_hash = sha(artifact / 'final.mp4') if entry_error is None and (artifact / 'final.mp4').is_file() else None
    result = None
    code = 2
    try:
        params = load(HERE / 'scoring_params.json')
        if entry_error:
            raise InvalidSourceEntry(entry_error)
        selected = Path(normalize(artifact, run / 'normalized/output', run / 'artifact-normalization.json')) if artifact.is_dir() else artifact
        command = ['node', str(HERE / 'native_measurement.mjs'), str(args.workspace), str(run / 'native'),
                   '--artifact', str(selected), '--judge-mode', args.mode, '--cache-dir', str(args.cache_dir)]
        if args.mode == 'fresh':
            command.append('--refresh')
        if args.rerender_proof:
            outside(args.rerender_proof, artifact, 'Rerender proof')
            command += ['--rerender-proof', str(args.rerender_proof.resolve())]
        else:
            command.append('--execute-project')
        if args.runtime_modules:
            command += ['--runtime-modules', str(args.runtime_modules.resolve())]
        native_exit = execute(command, run / 'native-execution.json')
        detail = load(run / 'native/reward_detail.json')
        if detail.get('status') == 'invalid_delivery':
            result = {'status': 'measured', 'terminal_invalid_delivery': True, 'reward': 0.,
                      'rewards': {'strict': 0., 'lenient': 0}, 'completion': {},
                      'must_have': {'valid_delivery': {'passed': False, 'evidence': detail.get('errors')}},
                      'reason': 'Source-native media parser established unusable delivery.',
                      'program_errors': detail.get('errors'), 'new_semantic_call_required': False}
        else:
            if native_exit or detail.get('status') != 'measured':
                raise Unmeasured('Native measurement did not complete: ' + str(detail.get('semantic_error') or detail.get('errors') or detail.get('status')))
            ownership_entry = HERE / 'ownership_judge.py'
            if not ownership_entry.is_file():
                raise Unmeasured('Source-bound ownership resolver is not installed')
            ownership_output = run / 'ownership'
            ownership_command = [sys.executable, str(ownership_entry), '--mode', args.mode,
                                 '--artifact', str(selected), '--detail', str(run / 'native/reward_detail.json'),
                                 '--semantic-result', str(run / 'native/effective-semantic-result.json'),
                                 '--output', str(ownership_output), '--cache-dir', str(args.ownership_cache_dir)]
            if args.mode == 'fresh':
                ownership_command.append('--refresh')
            ownership_exit = execute(ownership_command, run / 'ownership-execution.json')
            ownership_path = ownership_output / 'ownership-result.json'
            ownership = load(ownership_path)
            if (ownership_exit or ownership.get('status') != 'measured'
                    or ownership.get('binding', {}).get('video_sha256') != video_hash):
                raise Unmeasured('Ownership judgment is unmeasured or bound to a different video')
            detail['positive_deduplications'] = ownership['positive_deduplications']
            save(run / 'settlement-native-measurements.json', detail)
            entry = HERE / 'audio_judge/judge.mjs'
            if not entry.is_file():
                raise Unmeasured('Portable audio judge is not installed')
            audio_output = run / 'audio'
            audio_command = ['node', str(entry), '--mode', args.mode, '--artifact', str(selected),
                             '--output', str(audio_output), '--cache-dir', str(args.audio_cache_dir)]
            if args.mode == 'fresh':
                audio_command.append('--refresh')
            audio_exit = execute(audio_command, run / 'audio-execution.json')
            audio_path = audio_output / 'llm_judge_result.json'
            base_audio = load(audio_path)
            if (base_audio.get('status') not in ('measured', 'needs_review')
                    or base_audio.get('binding', {}).get('video_sha256') != video_hash
                    or audio_exit not in (0, 2)):
                raise Unmeasured('Base audio judgment failed or does not bind to the actual video')
            resolution_entry = HERE / 'audio_resolution/judge.mjs'
            if not resolution_entry.is_file():
                raise Unmeasured('Portable audio resolution component is not installed')
            resolution_output = run / 'audio-resolution'
            resolution_command = ['node', str(resolution_entry), '--mode', args.mode,
                                  '--artifact', str(selected), '--base-result', str(audio_path),
                                  '--output', str(resolution_output),
                                  '--cache-dir', str(args.audio_resolution_cache_dir)]
            if args.mode == 'fresh':
                resolution_command.append('--refresh')
            resolution_exit = execute(resolution_command, run / 'audio-resolution-execution.json')
            resolution_path = resolution_output / 'llm_judge_result.json'
            audio = load(resolution_path)
            if (resolution_exit or audio.get('status') != 'measured'
                    or audio.get('binding', {}).get('video_sha256') != video_hash):
                raise Unmeasured('Audio resolution is unmeasured or bound to a different video')
            soundtrack = judge_soundtrack(selected, run / 'soundtrack',
                                          args.audio_cache_dir.parent / 'soundtrack', args.mode)
            result = settle(detail, audio['role_audio'], soundtrack, params)
            result['source_measurements'] = {
                'items': detail['items'], 'checks': detail['checks'], 'must_have': detail['must_have'],
                'media': detail['media'], 'native_damage_instances': detail['settlement']['damage_instances'],
                'native_detail_sha256': sha(run / 'native/reward_detail.json'),
                'settlement_native_measurements_sha256': sha(run / 'settlement-native-measurements.json'),
                'ownership_result_sha256': sha(ownership_path),
                'ownership_binding': ownership['binding'],
                'positive_deduplications': ownership['positive_deduplications'],
                'audio_observations_sha256': sha(audio_path),
                'audio_binding': base_audio['binding'],
                'audio_resolution_sha256': sha(resolution_path),
                'audio_resolution_binding': audio['binding'], 'native_intermediate_total_used': False}
        if video_hash is not None and sha(artifact / 'final.mp4') != video_hash:
            raise Unmeasured('Candidate video changed during verification')
        result.update(started_at=started, finished_at=datetime.now(timezone.utc).isoformat(),
                      version=params['version'],
                      artifact_video_sha256=video_hash, verifier_run=str(run),
                      runtime_sha256=sha(Path(__file__)),
                      params_sha256=sha(HERE / 'scoring_params.json'))
        publish(args.output, result)
        code = 0
    except InvalidSourceEntry as error:
        result = {'status': 'measured', 'terminal_invalid_delivery': True, 'reward': 0.,
                  'rewards': {'strict': 0., 'lenient': 0}, 'version': params['version'],
                  'completion': {}, 'must_have': {'valid_delivery': {'passed': False, 'evidence': str(error)}},
                  'reason': 'Self-contained submitted artifact entry validation failed.',
                  'program_errors': [str(error)], 'new_semantic_call_required': False,
                  'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
                  'artifact_video_sha256': None, 'verifier_run': str(run),
                  'runtime_sha256': sha(Path(__file__)), 'params_sha256': sha(HERE / 'scoring_params.json')}
        publish(args.output, result)
        code = 0
    except Exception as error:
        result = {'status': 'unmeasured', 'reward': None, 'rewards': None,
                  'error': safe_text(str(error)), 'started_at': started,
                  'finished_at': datetime.now(timezone.utc).isoformat(), 'verifier_run': str(run)}
        publish(args.output, result)
    save(args.output / 'execution.json', {'command': sys.argv, 'working_directory': os.getcwd(),
        'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
        'exit_code': code, 'status': result['status'], 'run': str(run),
        'reward_sha256': sha(args.output / 'reward.json') if (args.output / 'reward.json').exists() else None, 'credential_values_recorded': False})
    print(json.dumps({'status': result['status'], 'rewards': result['rewards'], 'error': result.get('error')}))
    return code


if __name__ == '__main__':
    raise SystemExit(main())

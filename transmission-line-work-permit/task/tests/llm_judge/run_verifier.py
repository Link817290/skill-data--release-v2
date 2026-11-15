#!/usr/bin/env python3
"""Opt-in trusted-verifier route. Semantic failures are unscored, not zero."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
TESTS = HERE.parent
sys.path[:0] = [str(TESTS), str(HERE)]
import judge  # noqa: E402
import validator  # noqa: E402
from runtime.settlement import merge  # noqa: E402


def locate(root):
    output = root if root.name == 'output' or (root / '\u5de5\u4f5c\u7968.docx').is_file() else root / 'output'
    preferred = output / '\u5de5\u4f5c\u7968.docx'
    if preferred.is_file():
        return preferred
    candidates = list((output if output.is_dir() else root).glob('*.docx'))
    return candidates[0] if len(candidates) == 1 else None


def run(root, out, artifacts, mode):
    start = datetime.now(timezone.utc).isoformat()
    command = []
    stdout = stderr = ''
    exit_code = 2
    try:
        artifact = locate(root)
        original_hash = hashlib.sha256(artifact.read_bytes()).hexdigest() if artifact else None
        program = validator.check(root)
        judge.write(out / 'program_detail.json', program)
        if not program['core_checks']['required_artifacts']['passed']:
            # A deterministic missing/corrupt carrier needs no semantic measurement.
            detail = program
            detail['semantic_judge'] = {'status': 'not_applicable', 'reason': 'deterministic_carrier_rejection'}
        else:
            command = [sys.executable, '-B', str(HERE / 'judge.py'), '--mode', mode,
                       '--artifact', str(artifact), '--output', str(out), '--cache-dir',
                       os.environ.get('LLM_JUDGE_CACHE_DIR', str(HERE / 'cache'))]
            if mode == 'fresh':
                command.append('--refresh')
            completed = subprocess.run(command, capture_output=True, text=True)
            stdout, stderr = completed.stdout, completed.stderr
            if completed.returncode:
                raise ValueError('Semantic judge failed; no program-only fallback')
            measured = judge.load(out / 'llm_judge_result.json')
            if measured['artifact_sha256'] != original_hash or original_hash != hashlib.sha256(artifact.read_bytes()).hexdigest():
                raise ValueError('Artifact changed during evaluation')
            detail = merge(program, measured, artifact, judge.load(TESTS / 'scoring_params.json'),
                           judge.load(HERE / 'contract.json'))
            if 'adjudication' in measured:
                detail['source_adjudication'] = measured['adjudication']
            artifacts.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(artifact, artifacts / artifact.name)
        judge.write(out / 'reward_detail.json', detail)
        strict, lenient = detail['reward_strict'], detail['rewards']['lenient']
        judge.write(out / 'reward.json', {'reward': strict, 'reward_strict': strict, 'reward_lenient': lenient})
        for name, value in [('reward.txt', strict), ('reward_strict.txt', strict), ('reward_lenient.txt', lenient)]:
            (out / name).write_text(f'{value:.6f}\n')
        exit_code = 0
    except Exception as exc:
        judge.write(out / 'reward.json', {'reward': None, 'status': 'judge_error', 'counted_valid': False,
                                       'error_type': type(exc).__name__})
        judge.write(out / 'reward_detail.json', {'status': 'judge_error', 'counted_valid': False,
                                               'reason': 'No numeric reward without required semantic evidence'})
        for name in ('reward.txt', 'reward_strict.txt', 'reward_lenient.txt'):
            (out / name).write_text('UNSCORED\n')
    finally:
        judge.write(out / 'verifier_execution.json', {
            'mode': mode, 'started_at': start, 'finished_at': datetime.now(timezone.utc).isoformat(),
            'exit_code': exit_code, 'execution_scope': 'task verifier; actual launcher and image evidence recorded separately',
            'command': command, 'cwd': str(Path.cwd()), 'image_identity': os.environ.get('VERIFIER_IMAGE_ID'),
            'stdout': stdout, 'stderr': stderr,
            'stdout_bytes': len(stdout.encode()), 'stderr_bytes': len(stderr.encode()),
            'reward_sha256': hashlib.sha256((out / 'reward.json').read_bytes()).hexdigest()})
    return exit_code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('artifacts', type=Path)
    parser.add_argument('--mode', choices=['replay', 'fresh'], required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    status = run(args.root, args.output, args.artifacts, args.mode)
    print(json.dumps(judge.load(args.output / 'reward.json'), ensure_ascii=False))
    return status


if __name__ == '__main__':
    raise SystemExit(main())

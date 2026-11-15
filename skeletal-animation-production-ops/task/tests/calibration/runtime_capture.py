"""Invoke the fixed original exporter with a declared public environment only."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ALLOWED = {'HOME', 'XDG_DATA_HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME'}
REQUIRED = ['scene-frames.csv', 'impact-events.csv', 'engine.log', 'dark.gif', 'light.gif', 'contact-sheet.png']


def hashes(root):
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_file() and not any(part in {'.godot', '.git', '__pycache__'} for part in path.relative_to(root).parts):
            result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifact', type=Path, default=Path('/artifact'))
    parser.add_argument('--recipe', type=Path, default=Path('/recipe.json'))
    parser.add_argument('--output', type=Path, default=Path('/capture'))
    parser.add_argument('--work-root', type=Path, default=Path('/workspace'))
    args = parser.parse_args()
    recipe = json.loads(args.recipe.read_text())
    if os.getuid() != 20005 or recipe['recipe_interpretable'] is not True:
        raise ValueError('Declared default user and interpreted known recipe required')
    project = args.work_root / 'output/project'
    project.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(args.artifact / 'project', project, ignore=shutil.ignore_patterns('.godot', '.git', '__pycache__'))
    before = hashes(project)
    observed = {name: os.environ.get(name) for name in sorted(ALLOWED)}
    env = {name: value for name, value in os.environ.items()
           if not name.startswith(('LLM_', 'OPENAI_', 'ANTHROPIC_', 'AZURE_OPENAI_', 'CODEX_'))}
    # Parent grading processes may configure private runtime directories. Only
    # the original declared image defaults and public recipe may reach the run.
    for name in ALLOWED:
        env.pop(name, None)
    env['HOME'] = '/home/agent'
    default = {name: env.get(name) for name in sorted(ALLOWED)}
    applied = {}
    seen = set()
    for item in recipe['public_environment']:
        name = item['name']
        if name not in ALLOWED or name in seen:
            raise ValueError('Unknown or duplicate public environment variable')
        seen.add(name)
        if item['interpretation'] == 'fresh_writable_directory':
            value = str(args.work_root / 'public-runtime' / name.lower())
        elif item['interpretation'] == 'literal':
            value = item['value']
        else:
            raise ValueError('Unknown environment interpretation')
        path = Path(value)
        if not path.is_absolute() or '..' in path.parts or not (value in ['/tmp', '/var/tmp'] or value.startswith('/tmp/') or value.startswith('/var/tmp/') or value.startswith('/workspace/') or path.is_relative_to(args.work_root)):
            raise ValueError('Public runtime directory must be isolated and writable')
        path.mkdir(parents=True, exist_ok=True)
        env[name] = value
        applied[name] = value
    output = args.output / 'preview'
    argv = ['python3', '/opt/fx-tools/export_effects.py', '--project', str(project), '--output', str(output)]
    started = datetime.now(timezone.utc).isoformat()
    clock = time.monotonic()
    try:
        process = subprocess.run(argv, cwd=args.work_root, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, timeout=180)
        code, stdout, stderr = process.returncode, process.stdout, process.stderr
    except subprocess.TimeoutExpired as error:
        code = None
        stdout = error.stdout.decode(errors='replace') if isinstance(error.stdout, bytes) else (error.stdout or '')
        stderr = error.stderr.decode(errors='replace') if isinstance(error.stderr, bytes) else (error.stderr or '')
    files = hashes(output)
    submitted = hashes(args.artifact / 'preview')
    compare = {name: {'submitted_sha256': submitted.get(name), 'fresh_sha256': files.get(name),
                      'equal': name in submitted and submitted[name] == files.get(name)} for name in REQUIRED}
    result = {'schema': 'godot-public-runtime-capture-v1', 'status': 'measured', 'uid': os.getuid(), 'gid': os.getgid(),
              'observed_parent_runtime': observed, 'default_environment': default, 'public_environment_applied': applied, 'selected_recipe': recipe['selected_recipe'],
              'recipe_interpretable': True, 'mode': recipe.get('mode', 'public'), 'actual_argv': argv,
              'actual_cwd': str(args.work_root), 'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
              'duration_seconds': time.monotonic() - clock, 'exit_code': code, 'stdout': stdout, 'stderr': stderr,
              'required_files': REQUIRED, 'files': files, 'success': code == 0 and all(name in files for name in REQUIRED),
              'project_source_before': before, 'project_source_after': hashes(project),
              'required_root_correspondence': compare,
              'normalization': 'Known trusted exporter only; recorded project/output are mapped to copied project and fresh capture. Shell suffixes are never executed. Runtime cache directories omitted from the private working copy only.',
              'new_actor_runs': 0}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'receipt.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()

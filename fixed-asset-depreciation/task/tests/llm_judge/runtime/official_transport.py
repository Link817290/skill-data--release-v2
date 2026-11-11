"""Use the actual official read-only Codex client and retain its real model wire."""
import base64
import hashlib
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sysconfig
import tempfile
import threading

import httpx


def official_call(body, entry, endpoint, key, timeout_sec):
    entry = Path(entry)
    wire = entry / 'official-wire'
    wire.mkdir()
    temporary = tempfile.TemporaryDirectory(prefix='isometric-evaluator-')
    neutral = Path(temporary.name)
    home = neutral / 'home'
    home.mkdir(mode=0o700)
    (home / 'auth.json').write_text('{"OPENAI_API_KEY":"relay-only"}\n')
    working = neutral / 'workspace'
    working.mkdir()
    requests = []
    base = endpoint.rstrip('/')
    if base.endswith('/v1/responses'):
        base = base[:-13]
    elif base.endswith('/v1'):
        base = base[:-3]

    class Relay(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.headers.get('Upgrade', '').lower() == 'websocket':
                self.send_response(426); self.send_header('Content-Length', '0'); self.end_headers()
                return
            self.forward()

        def do_POST(self):
            self.forward()

        def forward(self):
            index = len(requests)
            raw = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            request_record = {'method': self.command, 'path': self.path,
                              'body': json.loads(raw) if raw else None,
                              'official_client_headers': {name: self.headers[name] for name in ('User-Agent', 'originator', 'Content-Type') if self.headers.get(name)}}
            (wire / f'{index:03d}-request.json').write_text(json.dumps(request_record, indent=2) + '\n')
            record = {'index': index, 'request': request_record, 'started_at': datetime.now(timezone.utc).isoformat()}
            requests.append(record)
            headers = {name: value for name, value in self.headers.items() if name.lower() not in
                       {'host', 'content-length', 'connection', 'authorization', 'x-api-key', 'accept-encoding'}}
            headers.update({'Authorization': 'Bearer ' + key, 'Accept-Encoding': 'identity'})
            try:
                with httpx.Client(timeout=httpx.Timeout(timeout_sec, connect=30), trust_env=False) as client:
                    response = client.request(self.command, base + self.path, content=raw, headers=headers)
                data = response.content
                if key.encode() in data:
                    raise RuntimeError('Credential echo withheld')
                content_type = response.headers.get('content-type', 'application/octet-stream')
                (wire / f'{index:03d}-response.body').write_bytes(data)
                record.update(http_status=response.status_code, content_type=content_type, response_bytes=len(data),
                              finished_at=datetime.now(timezone.utc).isoformat())
                final = None
                if 'text/event-stream' in content_type:
                    for line in data.decode('utf-8').splitlines():
                        if not line.startswith('data:'):
                            continue
                        value = line[5:].strip()
                        if value == '[DONE]':
                            continue
                        event = json.loads(value)
                        item = event.get('item')
                        if isinstance(item, dict) and item.get('type') not in {'reasoning', 'message'}:
                            raise RuntimeError('Provider emitted a tool item; no tool stream was released to the official client')
                        if any(token in event.get('type', '') for token in ('function_call', 'mcp_call', 'computer_call', 'web_search_call', 'code_interpreter_call', 'shell_call')):
                            raise RuntimeError('Provider emitted a tool event; no tool stream was released to the official client')
                        if event.get('type') in {'response.completed', 'response.done'}:
                            final = event.get('response')
                elif 'json' in content_type and data:
                    parsed = json.loads(data)
                    if isinstance(parsed, dict) and parsed.get('object') == 'response':
                        final = parsed
                if final:
                    if any(item.get('type') not in {'reasoning', 'message'} for item in final.get('output', [])):
                        raise RuntimeError('Evaluator attempted a tool call; no tool response was released to the official client')
                    record['final_response'] = final
                self.send_response(response.status_code)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers(); self.wfile.write(data)
            except Exception as error:
                record.update(error_type=type(error).__name__, finished_at=datetime.now(timezone.utc).isoformat())
                data = json.dumps({'error': {'message': 'Read-only evaluator transport failed', 'type': 'evaluator_transport_error'}}).encode()
                try:
                    self.send_response(502); self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            finally:
                (wire / f'{index:03d}-metadata.json').write_text(json.dumps({k: v for k, v in record.items() if k not in {'request', 'final_response'}}, indent=2) + '\n')

    server = ThreadingHTTPServer(('127.0.0.1', 0), Relay)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    texts, images, legend = [], [], []
    for message in body['input']:
        for content in message['content']:
            if content['type'] == 'input_text':
                texts.append(content['text'])
            elif content['type'] == 'input_image':
                prefix, encoded = content['image_url'].split(',', 1)
                suffix = '.jpg' if 'image/jpeg' in prefix else '.png' if 'image/png' in prefix else '.webp'
                path = entry / ('official-image-' + str(len(images)).zfill(3) + suffix)
                path.write_bytes(base64.b64decode(encoded))
                anonymous_path = neutral / path.name
                shutil.copy2(path, anonymous_path)
                images.append(anonymous_path)
    prompt = 'You are serving only as a read-only evaluator/planner. Do not carry out the task brief as an actor. Do not use tools or read/edit files. All necessary source and observations are supplied below. Return only the requested JSON.\n\n' + '\n\n'.join(texts)
    prompt += '\n\nNative images are attached in the same order as the Evidence image ID captions above.\n'
    binary = os.environ.get('CODEX_BIN') or shutil.which('codex')
    if not binary:
        candidate = Path(sysconfig.get_path('scripts', scheme='posix_user')) / 'codex'
        if candidate.is_file():
            binary = str(candidate)
    if not binary:
        raise RuntimeError('The official Codex client executable is unavailable')
    binary_path = Path(binary).resolve()
    client_identity = {'binary': str(binary_path), 'sha256': hashlib.sha256(binary_path.read_bytes()).hexdigest(),
                       'version': subprocess.check_output([binary, '--version'], text=True).strip()}
    command = [binary, 'exec', '--ignore-user-config', '--ignore-rules', '--ephemeral', '--skip-git-repo-check',
               '--sandbox', 'read-only', '--model', body['model'], '--json', '--color', 'never',
               '-C', str(working), '-c', 'openai_base_url=' + json.dumps('http://127.0.0.1:' + str(server.server_port) + '/v1'),
               '-c', 'model_reasoning_effort=' + json.dumps(body.get('reasoning', {}).get('effort', 'high')),
               '-o', str(neutral / 'last-message.json')]
    schema = body.get('text', {}).get('format', {}).get('schema')
    if schema:
        schema_path = entry / 'official-output-schema.json'
        schema_path.write_text(json.dumps(schema, indent=2) + '\n')
        anonymous_schema = neutral / 'output-schema.json'
        shutil.copy2(schema_path, anonymous_schema)
        command += ['--output-schema', str(anonymous_schema)]
    for feature in ('shell_tool', 'unified_exec', 'view_image', 'apps', 'browser_use', 'computer_use', 'multi_agent',
                    'goals', 'skill_search', 'memories', 'plugins', 'enable_request_compression', 'api_key_model_discovery'):
        command += ['--disable', feature]
    for path in images:
        command += ['--image', str(path)]
    command += ['--', '-']
    env = {name: os.environ[name] for name in ('PATH', 'LANG', 'LC_ALL') if name in os.environ}
    env['PATH'] = str(Path(binary).parent) + os.pathsep + env.get('PATH', '')
    env.update(CODEX_HOME=str(home), HOME=str(home), OPENAI_API_KEY='relay-only',
               OPENAI_BASE_URL='http://127.0.0.1:' + str(server.server_port) + '/v1', NO_PROXY='127.0.0.1,localhost', no_proxy='127.0.0.1,localhost')
    started = datetime.now(timezone.utc).isoformat()
    try:
        completed = subprocess.run(command, input=prompt, capture_output=True, text=True, env=env,
                                   cwd=working, timeout=timeout_sec + 90)
        (entry / 'official-events.jsonl').write_text(completed.stdout)
        (entry / 'official-stderr.log').write_text(completed.stderr)
        if (neutral / 'last-message.json').exists():
            shutil.copy2(neutral / 'last-message.json', entry / 'official-last-message.json')
        (entry / 'official-command.json').write_text(json.dumps({'command': command, 'started_at': started,
            'finished_at': datetime.now(timezone.utc).isoformat(), 'exit_code': completed.returncode,
            'sandbox': 'read-only', 'tools_permitted': False, 'real_api_key_passed_to_client': False,
            'actual_client': 'codex exec', 'actor_rollout': False}, indent=2) + '\n')
        if completed.returncode:
            raise RuntimeError('Official evaluator client exited unsuccessfully')
        finals = [record for record in requests if record.get('final_response')]
        if not finals:
            raise RuntimeError('No complete official-client provider response was captured')
        def final_text(provider):
            return '\n'.join(content['text'] for item in provider.get('output', []) if item.get('type') == 'message'
                             for content in item.get('content', []) if content.get('type') == 'output_text').strip()
        last_message = (entry / 'official-last-message.json').read_text().strip()
        matching = [record for record in finals if final_text(record['final_response']) == last_message]
        if not matching:
            raise RuntimeError('Captured provider responses do not match the official client final message')
        selected = matching[-1]
        provider = selected['final_response']
        actual_request = entry / 'actual-wire-request.json'
        actual_request.write_text(json.dumps(selected['request'], indent=2) + '\n')
        actual_body = selected['request'].get('body') or {}
        if str(entry.parent.parent.parent) in json.dumps(selected['request']):
            raise RuntimeError('An author case path leaked into the executed provider request')
        if actual_body.get('tools'):
            raise RuntimeError('Official evaluator request unexpectedly exposed tools')
        provenance = {'official_client': client_identity, 'selected_wire_index': selected['index'],
            'selected_provider_response_id': provider.get('id'), 'final_message_matches_provider_text': True,
            'actual_wire_request_sha256': hashlib.sha256(actual_request.read_bytes()).hexdigest(),
            'actual_wire_response_sha256': hashlib.sha256((wire / f"{selected['index']:03d}-response.body").read_bytes()).hexdigest(),
            'official_last_message_sha256': hashlib.sha256((entry / 'official-last-message.json').read_bytes()).hexdigest(),
            'actual_output_token_limit': actual_body.get('max_output_tokens'),
            'output_token_limit_policy': 'Official client default; no unsupported token-budget override is asserted.',
            'actual_reasoning': actual_body.get('reasoning'), 'top_level_tools': actual_body.get('tools', []),
            'actual_tool_choice': actual_body.get('tool_choice'),
            'input_tool_declaration_present': any(isinstance(item, dict) and item.get('tools') for item in actual_body.get('input', [])),
            'provider_tool_outputs_rejected_before_client_delivery': True,
            'default_client_instruction_text_retained': True,
            'official_client_paths_anonymous': True,
            'case_directory_excluded_from_actual_wire': True,
            'request_file_role': 'request.json describes logical evaluator input; actual-wire-request.json is the executed provider request, including official client instructions/context.'}
        (entry / 'executed-provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
        return provider
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)
        temporary.cleanup()

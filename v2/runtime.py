#!/usr/bin/env python3
"""Thin dispatcher to the existing approved helpers; never installs a runtime.

The binding is operator-owned configuration, not model input. The model only
chooses a helper already present in its role's shell permissions and its argv.
"""
import importlib.util
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

sys.dont_write_bytecode = True

HELPERS = (
    'knowledge_search.sh', 'knowledge_status.sh', 'knowledge_status_engram.sh',
    'knowledge_status_qdrant.sh', 'knowledge_inventory.sh', 'knowledge_store.sh',
    'knowledge_seed_global.sh',
)
ENV_KEYS = {
    'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME',
    'OPENCODE_KNOWLEDGE_HOME', 'OPENCODE_KNOWLEDGE_VENV', 'QDRANT_LOCAL_PATH',
    'OPENCODE_KNOWLEDGE_COLLECTION', 'OPENCODE_KNOWLEDGE_SCOPE', 'OPENCODE_KNOWLEDGE_PROJECT',
    'OPENCODE_KNOWLEDGE_EMBEDDING_BACKEND', 'OPENCODE_KNOWLEDGE_EMBEDDING_MODEL',
    'OPENCODE_KNOWLEDGE_OLLAMA_BASE_URL', 'OPENCODE_KNOWLEDGE_OLLAMA_BATCH_SIZE',
    'OPENCODE_KNOWLEDGE_OLLAMA_TIMEOUT_SECONDS',
    'ENGRAM_DATA_DIR', 'ENGRAM_PROJECT', 'ENGRAM_CLOUD_AUTOSYNC', 'ENGRAM_CLOUD_SERVER',
}


def validate(binding, *, allow_shared_config=False):
    if set(binding) != {'runtime_home', 'runtime_config', 'profile_config', 'environment'}:
        raise ValueError('Unexpected runtime binding fields')
    for key in ('runtime_home', 'runtime_config', 'profile_config'):
        if not isinstance(binding[key], str) or not Path(binding[key]).is_absolute():
            raise ValueError('Runtime paths must be explicit and absolute')
    if not allow_shared_config and Path(binding['runtime_config']).resolve() == Path(binding['profile_config']).resolve():
        raise ValueError('Runtime helpers cannot dispatch back into their own profile')
    if not isinstance(binding['environment'], dict) or not set(binding['environment']).issubset(ENV_KEYS):
        raise ValueError('Unsupported runtime environment key; never serialize credentials')
    if any(not isinstance(value, str) or '\0' in value for value in binding['environment'].values()):
        raise ValueError('Invalid runtime environment value')
    for key in ('OPENCODE_KNOWLEDGE_OLLAMA_BASE_URL', 'ENGRAM_CLOUD_SERVER'):
        value = binding['environment'].get(key)
        if value and (urlsplit(value).username or urlsplit(value).password):
            raise ValueError('Credential-bearing URLs must not be serialized in runtime bindings')
    return binding


def runtime_env(binding, parent):
    allowed = ('PATH', 'USER', 'LOGNAME', 'LANG', 'TERM', 'TMPDIR', 'TMP', 'TEMP')
    env = {key: parent[key] for key in allowed if key in parent}
    home = Path(binding['runtime_home'])
    env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / '.config'),
               XDG_DATA_HOME=str(home / '.local/share'), XDG_STATE_HOME=str(home / '.local/state'),
               XDG_CACHE_HOME=str(home / '.cache'), PYTHONDONTWRITEBYTECODE='1')
    env.update(binding['environment'])
    return env


def invocation(binding, helper, args, profile_scripts):
    validate(binding)
    if helper not in HELPERS:
        raise ValueError('Helper is not part of the Knowledge contract')
    if helper == 'knowledge_status_engram.sh':
        # Source-compatible status implementation understands V1 and V2 config.
        script = profile_scripts / 'knowledge_status_engram_impl.sh'
        if '--config-dir' not in args:
            args = ['--config-dir', binding['profile_config'], *args]
    else:
        script = Path(binding['runtime_config']) / 'scripts' / helper
    if not script.is_file():
        raise ValueError('Existing Knowledge helper is missing; no automatic install')
    return ['bash', str(script), *args]


def check_command(command, binding):
    """Validate literal helper shell via the unchanged canonical planner parser."""
    profile = Path(binding['profile_config'])
    broker = profile / 'scripts/planner_shell.py'
    spec = importlib.util.spec_from_file_location('knowledge_planner_contract', broker)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    argv = module.literal_argv(command)
    if len(argv) >= 2 and argv[0] == 'bash':
        expected = {str(profile / 'scripts' / name) for name in HELPERS}
        if argv[1] not in expected:
            raise ValueError('Not an installed Knowledge shim')
        return
    if len(argv) >= 4 and argv[:3] == ['python3', str(broker), 'helper'] and argv[3] in ('knowledge-search', 'knowledge-status'):
        module.check_invocation(command, Path.cwd())
        return
    raise ValueError('Not an approved Knowledge shell invocation')


def main(args):
    profile_scripts = Path(__file__).resolve().parent
    binding = validate(json.loads((profile_scripts / 'knowledge-runtime.json').read_text()))
    if args == ['--check-command']:
        check_command(json.load(sys.stdin)['command'], binding)
        return 0
    if not args or args[0] not in HELPERS:
        raise ValueError('Select an approved Knowledge helper')
    command = invocation(binding, args[0], args[1:], profile_scripts)
    os.execvpe(command[0], command, runtime_env(binding, os.environ))


if __name__ == '__main__':
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f'Knowledge runtime unavailable: {error}', file=sys.stderr)
        raise SystemExit(2)

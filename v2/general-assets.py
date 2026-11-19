#!/usr/bin/env python3
"""Native contribution metadata/assets, no writes, env sourcing or backend opens."""
import base64
import importlib.util
import json
from pathlib import Path
import shlex
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runtime = load('general_knowledge_runtime', ROOT / 'v2/runtime.py')
autonomy = load('general_knowledge_autonomy', ROOT / 'scripts/manage_agent_autonomy.py')


def plan(options):
    config = Path(options['config'])
    binding = runtime.validate({'runtime_home': options['runtime_home'], 'runtime_config': options['runtime_config'], 'profile_config': str(config), 'environment': options.get('environment', {})}, allow_shared_config=True)
    files = []
    def add(relative, content):
        files.append({'path': relative, 'content_b64': base64.b64encode(content.encode() if isinstance(content, str) else content).decode()})
    def public(file):
        if file.is_symlink() or not file.is_file() or file.name.startswith('.env') or '.local.' in file.name:
            raise ValueError('Canonical public assets only')
        return file.read_bytes()
    for relative in json.loads((ROOT / 'KNOWLEDGE-MANIFEST.json').read_text())['managedFiles']:
        if relative.startswith(('commands/', 'PLAYBOOK-')) or relative in ('planner-helpers/knowledge.json', 'knowledge/global_seed_paths.txt'):
            content = public(ROOT / relative)
            if relative.endswith('.md'):
                content = content.decode().replace('~/.config/opencode', str(config)).encode()
            add(relative, content)
    for directory in sorted((ROOT / 'skills').iterdir()):
        if not (directory / 'SKILL.md').is_file():
            continue
        for file in sorted(directory.rglob('*')):
            if file.is_symlink():
                raise ValueError('Skill symlink refused')
            if file.is_file():
                content = public(file)
                if file.suffix == '.md':
                    content = content.decode().replace('~/.config/opencode', str(config)).encode()
                add(str(file.relative_to(ROOT)), content)
    # Canonical wrappers remain wrappers, not dispatchers into V1 helper paths.
    # Aggregate status/seed retain CONFIG_ROOT and sibling calls of this profile.
    for helper in runtime.HELPERS:
        if helper == 'knowledge_status_engram.sh':
            add('scripts/knowledge_status_engram_impl.sh', public(ROOT / 'scripts' / helper))
            add('scripts/' + helper, '#!/usr/bin/env bash\nexec bash ' + shlex.quote(str(config / 'scripts/knowledge_status_engram_impl.sh')) + ' --config-dir ' + shlex.quote(str(config)) + ' "$@"\n')
        else:
            add('scripts/' + helper, public(ROOT / 'scripts' / helper))
    add('scripts/knowledge_store.py', public(ROOT / 'scripts/knowledge_store.py'))
    if Path(binding['runtime_config']).resolve() == config.resolve():
        env = public(ROOT / 'scripts/knowledge_env.sh')
    else:
        # Source the original approved environment code in its original context.
        # It alone loads its machine-local override; never inspect/copy it here.
        env = '#!/usr/bin/env bash\nsource ' + shlex.quote(str(Path(binding['runtime_config']) / 'scripts/knowledge_env.sh')) + '\n'
    add('scripts/knowledge_env.sh', env)
    add('scripts/knowledge_native_env.py', public(ROOT / 'v2/general-env.py'))
    return {'assets': files, 'agentTexts': {name: public(ROOT / 'agents' / (name + '.md')).decode() for name in ('plan', 'build', 'knowledge-reader', 'knowledge-curator')},
            'autonomy': autonomy.AGENT_RULES, 'runtimeEnvironment': runtime.runtime_env(binding, {'PATH': '/usr/local/bin:/usr/bin:/bin'}),
            'profileConfig': str(config)}


if __name__ == '__main__':
    try:
        print(json.dumps(plan(json.load(sys.stdin))))
    except Exception:
        print('Native Knowledge plan rejected; values suppressed', file=sys.stderr)
        raise SystemExit(2)

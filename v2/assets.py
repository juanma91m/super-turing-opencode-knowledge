#!/usr/bin/env python3
"""Render an additive asset plan from canonical sources. No filesystem writes.

Input/output are JSON on stdin/stdout. Paths and environment bindings must be
selected explicitly by the composition owner, never discovered from auth/envs.
"""
import base64
import importlib.util
import json
from pathlib import Path
import shlex
import sys
import re

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


autonomy = load('knowledge_autonomy', ROOT / 'scripts/manage_agent_autonomy.py')
runtime = load('knowledge_runtime_contract', ROOT / 'v2/runtime.py')


def plan(options, root=ROOT):
    config = Path(options['config'])
    if not config.is_absolute():
        raise ValueError('Profile config must be absolute')
    binding = runtime.validate({
        'runtime_home': options['runtime_home'], 'runtime_config': options['runtime_config'],
        'profile_config': str(config), 'environment': options.get('environment', {}),
    })
    bases = options.get('agents', {})
    assets = []

    def add(relative, data, previous=None):
        target = Path(relative)
        if target.is_absolute() or '..' in target.parts:
            raise ValueError('Unsafe managed asset path')
        if any(asset['path'] == relative for asset in assets):
            raise ValueError('Duplicate asset ownership')
        encode = lambda value: base64.b64encode(value.encode() if isinstance(value, str) else value).decode()
        item = {'path': relative, 'content_b64': encode(data)}
        if previous is not None:
            item['previous_b64'] = encode(previous)
        assets.append(item)

    def text_for_profile(text):
        text = text.replace('~/.config/opencode', str(config))
        # Operator maintenance commands stay on the existing runtime, not on a
        # half-migrated installer copied into the pilot. Approved role helpers
        # continue to use shims under the profile and the canonical planner broker.
        def script(match):
            name = match[1]
            if name in runtime.HELPERS or name == 'planner_shell.py':
                return str(config / 'scripts' / name)
            return str(Path(binding['runtime_config']) / 'scripts' / name)
        text = re.sub(re.escape(str(config)) + r'/scripts/([A-Za-z0-9_.-]+)', script, text)
        return text

    agent_texts = dict(bases)
    for role in ('plan', 'build', 'knowledge-reader', 'knowledge-curator'):
        if role not in agent_texts:
            agent_texts[role] = (root / 'agents' / f'{role}.md').read_text()
    for name, text in agent_texts.items():
        if name in autonomy.AGENT_RULES:
            prefix, header, body = autonomy.split_frontmatter(text)
            rule = autonomy.AGENT_RULES[name]
            # Preserve a caller's explicit target rule; don't duplicate the allow
            # already present in the guaranteed plan/build templates either.
            if not re.search(r'^\s+knowledge-reader:\s+(?:allow|ask|deny)(?:\s|$)', header, re.MULTILINE):
                header = autonomy.patch_task(header, rule['task_target'])
            text = prefix + header + '\n---\n' + autonomy.patch_body(body, rule['block'])
        desired = text_for_profile(text)
        if options.get('mock'):
            desired = desired.replace('model: openai/gpt-6.1-sol', 'model: workshop-mock/mock')
            desired = re.sub(r'^variant: .+\n', '', desired, flags=re.MULTILINE)
        add(f'agents/{name}.md', desired, bases.get(name))

    manifest = json.loads((root / 'KNOWLEDGE-MANIFEST.json').read_text())
    for relative in manifest['managedFiles']:
        if relative.startswith('commands/') or relative.startswith('PLAYBOOK-') or relative in ('planner-helpers/knowledge.json', 'knowledge/global_seed_paths.txt'):
            file = root / relative
            if file.is_symlink() or not file.is_file():
                raise ValueError('Canonical asset must be a regular file')
            add(relative, text_for_profile(file.read_text()))
    # Include complete skill trees, not only their SKILL.md entrypoints.
    skills = sorted(file.parent for file in (root / 'skills').glob('*/SKILL.md'))
    for skill in skills:
        if skill.is_symlink():
            raise ValueError('Skill resources must not follow symlinks')
        for file in sorted(skill.rglob('*')):
            if file.is_symlink():
                raise ValueError('Skill resources must not follow symlinks')
            if file.is_file():
                data = file.read_bytes()
                if file.suffix == '.md':
                    data = text_for_profile(data.decode()).encode()
                add(str(file.relative_to(root)), data)
    add('scripts/knowledge_runtime.py', (root / 'v2/runtime.py').read_bytes())
    add('scripts/knowledge-runtime.json', json.dumps(binding, indent=2) + '\n')
    add('scripts/knowledge_status_engram_impl.sh', (root / 'scripts/knowledge_status_engram.sh').read_bytes())
    for helper in runtime.HELPERS:
        if helper == 'knowledge_status.sh':
            # Aggregate status must call the profile's Engram/Qdrant siblings.
            add('scripts/' + helper, (root / 'scripts' / helper).read_bytes())
        else:
            add('scripts/' + helper, '#!/usr/bin/env bash\nset -euo pipefail\nexec python3 '
                + shlex.quote(str(config / 'scripts/knowledge_runtime.py')) + ' ' + shlex.quote(helper) + ' "$@"\n')
    return {'assets': assets, 'roles': sorted(agent_texts), 'skills': [skill.name for skill in skills],
            'commands': sorted(Path(item['path']).stem for item in assets if item['path'].startswith('commands/')),
            'helpers': list(runtime.HELPERS)}


if __name__ == '__main__':
    try:
        print(json.dumps(plan(json.load(sys.stdin))))
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f'Knowledge asset plan rejected: {error}', file=sys.stderr)
        raise SystemExit(2)

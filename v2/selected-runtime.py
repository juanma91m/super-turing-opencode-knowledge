#!/usr/bin/env python3
"""Select only non-secret current wiring for a machine-local V2 pilot.

Reads an explicit OpenCode config, never .env/auth/DB files. Unsupported or
credential-bearing Engram wiring fails closed instead of being copied/guessed.
The caller must not dump the returned configuration; show metadata only.
"""
import json
import fnmatch
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from runtime import ENV_KEYS, validate


def select(home, config, parent):
    if parent.get('ENGRAM_CLOUD_TOKEN'):
        raise ValueError('Inherited Engram credentials require an approved non-persisting integration')
    home, config = Path(home), Path(config)
    if not home.is_absolute() or not config.is_absolute():
        raise ValueError('Select absolute runtime home/config paths')
    source = json.loads((config / 'opencode.json').read_text())
    server = source.get('mcp', {}).get('engram')
    if not isinstance(server, dict) or server.get('type') != 'local':
        raise ValueError('Expected the current V1 local Engram definition')
    if not set(server).issubset({'type', 'command', 'cwd', 'environment', 'enabled', 'timeout'}):
        raise ValueError('Unsupported Engram wiring; requires explicit compatibility review')
    command = server.get('command')
    if not isinstance(command, list) or len(command) < 3 or not all(isinstance(item, str) for item in command):
        raise ValueError('Unsupported Engram command')
    if not Path(command[0]).is_absolute() or not os.access(command[0], os.X_OK) or command[1] != 'mcp':
        raise ValueError('Current Engram must be an existing absolute executable with MCP argv')
    expected = json.loads((Path(__file__).parent / 'engram-tools.json').read_text())['tools']
    selected, index = None, 2
    while index < len(command):
        arg = command[index]
        if arg.startswith('--tools='):
            selected = arg.split('=', 1)[1].split(',')
        elif arg.startswith('--project=') and arg.split('=', 1)[1].strip():
            pass
        elif arg in ('--tools', '--project') and index + 1 < len(command):
            index += 1
            if arg == '--tools':
                selected = command[index].split(',')
        else:
            raise ValueError('Unreviewed Engram argv; do not serialize arbitrary arguments')
        index += 1
    if selected != expected:
        raise ValueError('Current MCP filter differs from canonical Knowledge; reconcile without normalizing it')
    inherited = {key: parent[key] for key in ENV_KEYS if key in parent}
    explicit = server.get('environment', {})
    if not isinstance(explicit, dict) or not set(explicit).issubset(ENV_KEYS | {'HOME'}):
        raise ValueError('Engram environment requires a credential-safe integration, not copying secret values')
    validate({'runtime_home': str(home), 'runtime_config': str(config), 'profile_config': str(config / 'v2-selection-only'),
              'environment': {**inherited, **{key: value for key, value in explicit.items() if key != 'HOME'}}})
    if any(not isinstance(value, str) or '{env:' in value or '{file:' in value for value in explicit.values()):
        raise ValueError('Interpolated Engram environment requires explicit compatibility review')
    server = dict(server)
    # Preserve the current runtime identity, not the synthetic profile's HOME.
    server['environment'] = {'HOME': str(home),
        'XDG_CONFIG_HOME': str(home / '.config'), 'XDG_DATA_HOME': str(home / '.local/share'),
        'XDG_STATE_HOME': str(home / '.local/state'), 'XDG_CACHE_HOME': str(home / '.cache'),
        **inherited, **explicit}
    cwd = server.get('cwd', str(home))
    if not isinstance(cwd, str) or '{env:' in cwd or '{file:' in cwd:
        raise ValueError('Unsupported current Engram cwd')
    server['cwd'] = str(Path(cwd) if Path(cwd).is_absolute() else home / cwd)
    # Global migration pilot retains its original launch context; no new
    # --project is injected and explicit per-call project selection stays intact.
    rules = source.get('permission', {})
    if isinstance(rules, str):
        rules = {'*': rules}
    if not isinstance(rules, dict):
        raise ValueError('Unsupported current permissions')
    permissions = []
    for tool in expected:
        name, effect = 'engram_' + tool, 'allow'  # V1 MCP default, before overrides.
        if any(fnmatch.fnmatchcase(name, key) and value is False for key, value in source.get('tools', {}).items()):
            raise ValueError('Deprecated Engram tool toggles require explicit reconciliation')
        for key, value in rules.items():
            if fnmatch.fnmatchcase(name, key):
                if isinstance(value, dict):
                    value = value.get('*', effect)
                if value not in ('allow', 'ask', 'deny'):
                    raise ValueError('Unsupported current Engram permission')
                effect = value
        permissions.append({'action': name, 'resource': '*', 'effect': effect})
    for agent in source.get('agent', {}).values():
        if not isinstance(agent, dict):
            raise ValueError('Unsupported inline agent configuration')
        overrides = agent.get('permission', {})
        if isinstance(overrides, str) or isinstance(overrides, dict) and any(
            any(fnmatch.fnmatchcase('engram_' + tool, key) for tool in expected) for key in overrides
        ):
            raise ValueError('Inline agent MCP overrides require additive overlay reconciliation')
    return {'server': server, 'environment': inherited, 'permissions': permissions}


if __name__ == '__main__':
    try:
        options = json.load(sys.stdin)
        print(json.dumps(select(options['home'], options['config'], os.environ)))
    except (ValueError, KeyError, TypeError, OSError):
        print('Current Knowledge wiring could not be selected safely; no values copied or backend started', file=sys.stderr)
        raise SystemExit(2)

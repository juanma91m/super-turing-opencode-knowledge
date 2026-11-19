import base64
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


assets = load('fixture_assets', ROOT / 'v2/assets.py')
runtime = load('fixture_runtime', ROOT / 'v2/runtime.py')


class KnowledgeAssetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.profile = self.root / 'profile/opencode'
        self.home = self.root / 'runtime-home'
        self.source = self.home / '.config/opencode'
        self.options = {'config': str(self.profile), 'runtime_home': str(self.home), 'runtime_config': str(self.source)}

    def decoded(self, plan):
        return {item['path']: base64.b64decode(item['content_b64']) for item in plan['assets']}

    def install_fixture(self):
        planned = assets.plan(self.options)
        for name, data in self.decoded(planned).items():
            target = self.profile / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        scripts = self.source / 'scripts'
        scripts.mkdir(parents=True)
        for name in ('knowledge_env.sh', 'knowledge_search.sh', 'knowledge_status_qdrant.sh', 'knowledge_inventory.sh', 'knowledge_store.sh', 'knowledge_seed_global.sh'):
            shutil.copy2(ROOT / 'scripts' / name, scripts / name)
        venv_python = self.home / '.local/share/super-turing-opencode-knowledge/.venv/bin/python'
        venv_python.parent.mkdir(parents=True)
        venv_python.write_text('#!/usr/bin/python3\nimport json,os,sys\nprint(json.dumps({"argv":sys.argv[1:],"home":os.environ["HOME"],"model":os.environ.get("OPENCODE_KNOWLEDGE_EMBEDDING_MODEL"),"cache":os.environ.get("XDG_CACHE_HOME")}))\n')
        venv_python.chmod(0o755)
        (scripts / 'knowledge_env.local.sh').write_text('export OPENCODE_KNOWLEDGE_EMBEDDING_BACKEND=ollama\nexport OPENCODE_KNOWLEDGE_EMBEDDING_MODEL=fixture-existing-model\n')
        return planned

    def run_helper(self, name, *args):
        return subprocess.run(['bash', str(self.profile / 'scripts' / name), *args], cwd=self.root,
                              env={'HOME': str(self.root / 'isolated-v2-home'), 'PATH': '/usr/bin:/bin',
                                   'XDG_CACHE_HOME': str(self.root / 'isolated-v2-cache')},
                              capture_output=True, text=True, timeout=10, check=True)

    def test_plan_is_pure_and_covers_commands_skills_roles_and_helpers(self):
        plan = assets.plan(self.options)
        self.assertFalse(self.profile.exists())
        self.assertFalse(self.home.exists())
        self.assertEqual(plan['roles'], ['build', 'knowledge-curator', 'knowledge-reader', 'plan'])
        self.assertEqual(len(plan['commands']), 5)
        self.assertEqual(len(plan['skills']), 3)
        files = self.decoded(plan)
        self.assertIn('planner-helpers/knowledge.json', files)
        self.assertFalse(any('local.sh' in name or name.endswith('.env') for name in files))
        self.assertNotIn('scripts/install-knowledge.sh', files)
        for role in ('plan', 'build'):
            text = files[f'agents/{role}.md'].decode()
            self.assertEqual(text.count('    knowledge-reader: allow'), 1)
            self.assertEqual(text.count('KNOWLEDGE_AUTONOMY_START'), 1)
        reader = files['agents/knowledge-reader.md'].decode()
        self.assertEqual(reader.count('  engram_mem_'), 5)

    def test_augmentation_preserves_explicit_denies_and_unrelated_content(self):
        original = '---\npermission:\n  edit: deny\n  task:\n    "*": deny\n    knowledge-reader: deny\n---\nGUARDRAIL\n'
        plan = assets.plan({**self.options, 'agents': {'agent-design': original}})
        text = self.decoded(plan)['agents/agent-design.md'].decode()
        self.assertIn('GUARDRAIL', text)
        self.assertIn('    knowledge-reader: deny', text)
        self.assertNotIn('    knowledge-reader: allow', text)

    def test_full_skill_tree_preserves_binary_resources_and_rejects_links(self):
        canonical = self.root / 'canonical'
        canonical.mkdir()
        for folder in ('agents', 'skills', 'commands', 'knowledge', 'planner-helpers', 'scripts', 'v2'):
            if folder in ('scripts', 'v2'):
                (canonical / folder).mkdir()
            else:
                shutil.copytree(ROOT / folder, canonical / folder)
        for file in ROOT.glob('PLAYBOOK-*'):
            shutil.copy2(file, canonical / file.name)
        shutil.copy2(ROOT / 'KNOWLEDGE-MANIFEST.json', canonical / 'KNOWLEDGE-MANIFEST.json')
        for file in ('knowledge_status.sh', 'knowledge_status_engram.sh'):
            shutil.copy2(ROOT / 'scripts' / file, canonical / 'scripts' / file)
        shutil.copy2(ROOT / 'v2/runtime.py', canonical / 'v2/runtime.py')
        resource = canonical / 'skills/memoria-durable-opencode/resources/example.bin'
        resource.parent.mkdir()
        resource.write_bytes(b'\x00\xfffixture')
        self.assertEqual(self.decoded(assets.plan(self.options, canonical))[str(resource.relative_to(canonical))], b'\x00\xfffixture')
        resource.unlink()
        resource.symlink_to(ROOT / 'README.md')
        with self.assertRaisesRegex(ValueError, 'symlinks'):
            assets.plan(self.options, canonical)

    def test_runtime_environment_does_not_carry_v2_auth_or_interpreter_preloads(self):
        binding = {**{key: self.options[key] for key in ('runtime_home', 'runtime_config')}, 'profile_config': str(self.profile), 'environment': {}}
        env = runtime.runtime_env(runtime.validate(binding), {'PATH': '/usr/bin', 'OPENCODE_PASSWORD': 'fixture', 'OPENAI_API_KEY': 'fixture', 'LD_PRELOAD': 'fixture', 'PYTHONPATH': 'fixture', 'NODE_OPTIONS': 'fixture'})
        self.assertEqual(env['HOME'], str(self.home))
        self.assertEqual(env['XDG_CACHE_HOME'], str(self.home / '.cache'))
        for key in ('OPENCODE_PASSWORD', 'OPENAI_API_KEY', 'LD_PRELOAD', 'PYTHONPATH', 'NODE_OPTIONS'):
            self.assertNotIn(key, env)
        with self.assertRaisesRegex(ValueError, 'credentials'):
            runtime.validate({**binding, 'environment': {'OPENAI_API_KEY': 'fixture'}})
        with self.assertRaisesRegex(ValueError, 'own profile'):
            runtime.validate({**binding, 'runtime_config': str(self.profile)})
        with self.assertRaisesRegex(ValueError, 'Credential-bearing'):
            runtime.validate({**binding, 'environment': {'ENGRAM_CLOUD_SERVER': 'https://fixture:fixture@example.invalid'}})

    def test_current_selection_preserves_safe_wiring_and_effects_and_rejects_secrets(self):
        with patch.dict(sys.modules, {'runtime': runtime}):
            selected = load('fixture_selected', ROOT / 'v2/selected-runtime.py')
        self.source.mkdir(parents=True)
        binary = self.root / 'engram-fixture'
        binary.write_text('#!/bin/bash\nexit 0\n')
        binary.chmod(0o755)
        tools = json.loads((ROOT / 'v2/engram-tools.json').read_text())['tools']
        server = {'type': 'local', 'command': [str(binary), 'mcp', '--tools=' + ','.join(tools)],
                  'cwd': 'original-project', 'enabled': True, 'environment': {'ENGRAM_CLOUD_AUTOSYNC': '1'}}
        configuration = {'mcp': {'engram': server, 'unrelated': {'secret': 'fixture-secret'}},
                         'permission': {'engram_*': 'ask', 'engram_mem_save': 'deny'}}
        (self.source / 'opencode.json').write_text(json.dumps(configuration))
        result = selected.select(str(self.home), str(self.source), {'OPENAI_API_KEY': 'fixture-secret'})
        self.assertNotIn('fixture-secret', json.dumps(result))
        self.assertEqual(result['server']['command'], server['command'])
        self.assertEqual(result['server']['cwd'], str(self.home / 'original-project'))
        self.assertEqual(result['server']['environment']['ENGRAM_CLOUD_AUTOSYNC'], '1')
        self.assertEqual(result['server']['environment']['HOME'], str(self.home))
        effects = {rule['action']: rule['effect'] for rule in result['permissions']}
        self.assertEqual(effects['engram_mem_save'], 'deny')
        self.assertEqual(effects['engram_mem_search'], 'ask')
        with self.assertRaisesRegex(ValueError, 'Inherited Engram credentials'):
            selected.select(str(self.home), str(self.source), {'ENGRAM_CLOUD_TOKEN': 'fixture-secret'})
        server['environment']['ENGRAM_CLOUD_TOKEN'] = 'fixture-secret'
        (self.source / 'opencode.json').write_text(json.dumps(configuration))
        with self.assertRaisesRegex(ValueError, 'secret values'):
            selected.select(str(self.home), str(self.source), {})

    def test_search_and_store_reuse_existing_wrappers_local_overrides_and_argv(self):
        self.install_fixture()
        for name, argv in [('knowledge_search.sh', ['--query', 'literal ; $(not shell)', '--project', 'fixture']),
                           ('knowledge_inventory.sh', ['--collection', 'fixture']),
                           ('knowledge_store.sh', ['store-text', '--title', 'fixture', '--text', 'literal content'])]:
            result = json.loads(self.run_helper(name, *argv).stdout)
            mode = {'knowledge_search.sh': 'search', 'knowledge_inventory.sh': 'inventory'}.get(name)
            self.assertEqual(result['argv'][1:], ([mode] if mode else []) + argv)
            self.assertEqual(result['argv'][0], str(self.source / 'scripts/knowledge_store.py'))
            self.assertEqual(result['home'], str(self.home))
            self.assertEqual(result['cache'], str(self.home / '.cache'))
            self.assertEqual(result['model'], 'fixture-existing-model')

    def test_status_handles_native_and_legacy_enabled_flags_without_connecting(self):
        self.install_fixture()
        binary = self.home / '.opencode/bin/engram'
        binary.parent.mkdir(parents=True)
        binary.write_text('#!/bin/bash\n[[ "$1" == --version ]] || exit 2\nexit 0\n')
        binary.chmod(0o755)
        for definition, enabled in [({'mcp': {'servers': {'engram': {'type': 'local', 'command': ['fixture']}}}}, 'yes'),
                                    ({'mcp': {'servers': {'engram': {'disabled': True}}}}, 'no'),
                                    ({'mcp': {'engram': {'enabled': True}}}, 'yes')]:
            (self.profile / 'opencode.json').write_text(json.dumps(definition))
            result = self.run_helper('knowledge_status.sh', '--engram-only')
            self.assertIn(f'engram_mcp_enabled={enabled}', result.stdout)
            self.assertIn(f'engram_bin={binary}', result.stdout)
        qdrant = json.loads(self.run_helper('knowledge_status.sh', '--qdrant-only').stdout)
        self.assertEqual(qdrant['argv'][1:], ['status'])


if __name__ == '__main__':
    unittest.main()

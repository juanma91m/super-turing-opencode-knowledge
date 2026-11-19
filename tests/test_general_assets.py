import base64
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_general_assets', ROOT / 'v2/general-assets.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GeneralKnowledgeAssetsTests(unittest.TestCase):
    def plan(self, shared):
        temporary = tempfile.TemporaryDirectory(prefix='knowledge-general-', dir='/tmp/opencode')
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        config = root / 'profile'
        runtime_config = config if shared else root / 'original-config'
        options = {'config': str(config), 'runtime_home': str(root / 'runtime-home'), 'runtime_config': str(runtime_config), 'environment': {}}
        result = module.plan(options)
        files = {item['path']: base64.b64decode(item['content_b64']) for item in result['assets']}
        return options, result, files

    def test_shared_config_installs_canonical_environment_not_self_dispatch(self):
        options, _, files = self.plan(True)
        self.assertEqual(files['scripts/knowledge_env.sh'], (ROOT / 'scripts/knowledge_env.sh').read_bytes())
        self.assertEqual(files['scripts/knowledge_search.sh'], (ROOT / 'scripts/knowledge_search.sh').read_bytes())
        self.assertEqual(files['scripts/knowledge_seed_global.sh'], (ROOT / 'scripts/knowledge_seed_global.sh').read_bytes())
        self.assertNotIn(b'knowledge_runtime.py', files['scripts/knowledge_search.sh'])
        binding = {'runtime_home': options['runtime_home'], 'runtime_config': options['runtime_config'], 'profile_config': options['config'], 'environment': {}}
        with self.assertRaises(ValueError):
            module.runtime.validate(binding)
        module.runtime.validate(binding, allow_shared_config=True)

    def test_isolated_profile_keeps_original_environment_opaque_and_native_status_bound(self):
        options, result, files = self.plan(False)
        self.assertIn((options['runtime_config'] + '/scripts/knowledge_env.sh').encode(), files['scripts/knowledge_env.sh'])
        self.assertNotIn('scripts/knowledge_env.local.sh', files)
        self.assertIn(options['config'].encode(), files['scripts/knowledge_status_engram.sh'])
        self.assertIn(b'knowledge_status_engram_impl.sh', files['scripts/knowledge_status_engram.sh'])
        for key in ('OPENAI_API_KEY', 'OPENCODE_PASSWORD', 'PGPASSWORD', 'NODE_OPTIONS'):
            self.assertNotIn(key, result['runtimeEnvironment'])
        self.assertEqual(result['runtimeEnvironment']['HOME'], options['runtime_home'])

    def test_unsupported_or_secret_binding_rejected_without_source_or_backend_access(self):
        with self.assertRaises(ValueError):
            module.plan({'config': '/candidate', 'runtime_home': '/original', 'runtime_config': '/original/config', 'environment': {'ENGRAM_CLOUD_TOKEN': 'SYNTHETIC'}})
        with self.assertRaises(ValueError):
            module.plan({'config': '/candidate', 'runtime_home': '/original', 'runtime_config': '/original/config', 'environment': {'ENGRAM_CLOUD_SERVER': 'https://user:synthetic@example.invalid'}})


if __name__ == '__main__':
    unittest.main()

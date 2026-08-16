from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "knowledge_sync.py"
SPEC = importlib.util.spec_from_file_location("knowledge_sync", MODULE_PATH)
assert SPEC and SPEC.loader
sync = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sync
SPEC.loader.exec_module(sync)


class KnowledgeSyncTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.data_dir = self.home / ".engram"
        self.data_dir.mkdir()
        self.knowledge_home = self.home / "knowledge"
        self.log = self.root / "commands.log"
        self.engram = self.root / "engram"
        self.engram.write_text(
            "#!/usr/bin/env python3\n"
            "import os, sys\n"
            "args = sys.argv[1:]\n"
            "if args == ['projects', 'list']:\n"
            " print('Projects (2):')\n"
            " print('  project-a                         1 obs     1 session      0 prompts')\n"
            " print('  project-b                         1 obs     1 session      0 prompts')\n"
            " sys.exit(0)\n"
            "with open(os.environ['SYNC_TEST_LOG'], 'a') as handle:\n"
            " handle.write(' '.join(args) + '\\n')\n"
            "project = args[args.index('--project') + 1] if '--project' in args else ''\n"
            "phase = 'pull' if '--import' in args else 'push'\n"
            "if os.environ.get('SYNC_TEST_FAIL') == project and os.environ.get('SYNC_TEST_FAIL_PHASE') == phase:\n"
            " print('failure token=' + os.environ['ENGRAM_CLOUD_TOKEN'], file=sys.stderr)\n"
            " sys.exit(1)\n"
            "print('ok')\n"
        )
        self.engram.chmod(0o755)
        self.config_path = self.root / "knowledge-sync.conf"
        self.config_path.write_text(
            "OPENCODE_KNOWLEDGE_CLOUD_SERVER=http://127.0.0.1:18080\n"
            "OPENCODE_KNOWLEDGE_CLOUD_TOKEN=secret-token\n"
            "OPENCODE_KNOWLEDGE_CLOUD_PROJECTS=project-b,project-a,project-b\n"
            "OPENCODE_KNOWLEDGE_CLOUD_TIMEOUT_SECONDS=5\n"
            f"OPENCODE_KNOWLEDGE_ENGRAM_BIN={self.engram}\n"
            f"OPENCODE_KNOWLEDGE_ENGRAM_DATA_DIR={self.data_dir}\n"
            f"OPENCODE_KNOWLEDGE_HOME={self.knowledge_home}\n"
        )
        self.config_path.chmod(0o600)
        self.environment = {
            "SYNC_TEST_LOG": str(self.log),
            "HOME": str(self.home),
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def load(self):
        with patch.dict(os.environ, self.environment, clear=True):
            return sync.load_config(self.config_path)

    def test_config_sorts_and_deduplicates_projects(self) -> None:
        config = self.load()
        self.assertEqual(config.projects, ("project-a", "project-b"))

    def test_config_rejects_wildcard(self) -> None:
        content = self.config_path.read_text().replace("project-b,project-a,project-b", "*")
        self.config_path.write_text(content)
        with patch.dict(os.environ, self.environment, clear=True):
            with self.assertRaises(sync.ConfigurationError):
                sync.load_config(self.config_path)

    def test_sync_rejects_broad_config_permissions(self) -> None:
        self.config_path.chmod(0o644)
        with patch.dict(os.environ, self.environment, clear=True):
            config = sync.load_config(self.config_path)
            self.assertEqual(sync.execute("push", config), 2)
        self.assertFalse(self.log.exists())

    def test_sync_pulls_then_pushes_and_continues_after_project_failure(self) -> None:
        environment = {
            **self.environment,
            "SYNC_TEST_FAIL": "project-a",
            "SYNC_TEST_FAIL_PHASE": "pull",
        }
        with patch.dict(os.environ, environment, clear=True):
            config = sync.load_config(self.config_path)
            result = sync.execute("sync", config)
        self.assertEqual(result, 1)
        commands = self.log.read_text().splitlines()
        self.assertEqual(
            commands,
            [
                "sync --cloud --import --project project-a",
                "sync --cloud --import --project project-b",
                "sync --cloud --project project-b",
            ],
        )
        state = json.loads((self.knowledge_home / "sync/status.json").read_text())
        self.assertEqual(state["result"], "degraded")
        self.assertTrue(state["projects"]["project-a"]["push"]["skipped"])
        self.assertEqual((self.knowledge_home / "sync/status.json").stat().st_mode & 0o777, 0o600)

    def test_lock_prevents_overlap(self) -> None:
        with patch.dict(os.environ, self.environment, clear=True):
            config = sync.load_config(self.config_path)
            with sync.SyncLock(config.lock_file):
                self.assertEqual(sync.execute("push", config), 75)

    def test_output_redacts_token(self) -> None:
        completed = sync.subprocess.CompletedProcess([], 1, "", "secret-token")
        with patch("builtins.print") as output:
            sync.print_process_output("project-a", "push", completed, "secret-token")
        rendered = " ".join(str(call) for call in output.call_args_list)
        self.assertNotIn("secret-token", rendered)
        self.assertIn("redacted", rendered)


if __name__ == "__main__":
    unittest.main()

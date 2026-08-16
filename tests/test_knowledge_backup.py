from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import tarfile
import tempfile
import unittest
from argparse import Namespace
from contextlib import closing
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "knowledge_backup.py"
SPEC = importlib.util.spec_from_file_location("knowledge_backup", MODULE_PATH)
assert SPEC and SPEC.loader
backup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backup)


class KnowledgeBackupTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.engram_dir = self.root / "engram-state"
        self.engram_dir.mkdir()
        self.engram_db = self.engram_dir / "engram.db"
        with closing(sqlite3.connect(self.engram_db)) as connection:
            connection.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, title TEXT)")
            connection.execute("INSERT INTO observations(title) VALUES ('durable memory')")
            connection.commit()

        self.engram_bin = self.root / "engram"
        self.engram_bin.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sqlite3, sys\n"
            "if sys.argv[1] == 'version':\n"
            "    print('engram test-version')\n"
            "elif sys.argv[1] == 'export':\n"
            "    db = os.path.join(os.environ['ENGRAM_DATA_DIR'], 'engram.db')\n"
            "    with sqlite3.connect(db) as connection:\n"
            "        rows = connection.execute('SELECT title FROM observations').fetchall()\n"
            "    with open(sys.argv[2], 'w') as handle:\n"
            "        json.dump({'observations': rows}, handle)\n"
        )
        self.engram_bin.chmod(0o755)

        self.qdrant = self.root / "qdrant"
        (self.qdrant / "collection/test").mkdir(parents=True)
        (self.qdrant / "meta.json").write_text('{"collections": {"test": {}}}\n')
        (self.qdrant / "collection/test/data.bin").write_bytes(b"vector-data")
        (self.qdrant / ".lock").write_text("ephemeral")
        self.archive = self.root / "backup.tar.gz"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def create_archive(self) -> None:
        args = Namespace(
            output=str(self.archive),
            components="all",
            engram_db=str(self.engram_db),
            engram_bin=str(self.engram_bin),
            qdrant_path=str(self.qdrant),
            qdrant_client_version="1.17.1",
            embedding_backend="ollama",
            embedding_model="test-model",
            addon_manifest=None,
        )
        self.assertEqual(backup.create_backup(args), 0)

    def test_create_verify_and_restore(self) -> None:
        self.create_archive()
        self.assertTrue(self.archive.is_file())

        verify_args = Namespace(archive=str(self.archive))
        self.assertEqual(backup.verify_backup(verify_args), 0)

        target_db = self.root / "target/.engram/engram.db"
        target_db.parent.mkdir(parents=True)
        with closing(sqlite3.connect(target_db)) as connection:
            connection.execute("CREATE TABLE old_state (id INTEGER)")
            connection.commit()
        target_qdrant = self.root / "target/qdrant"
        target_qdrant.mkdir(parents=True)
        (target_qdrant / "old").write_text("old")
        rollback = self.root / "target/rollback"

        restore_args = Namespace(
            archive=str(self.archive),
            components="all",
            engram_db=str(target_db),
            qdrant_path=str(target_qdrant),
            rollback_dir=str(rollback),
            engram_version="engram test-version",
            qdrant_client_version="1.17.1",
            embedding_backend="ollama",
            embedding_model="test-model",
            allow_engram_version_mismatch=False,
            allow_qdrant_version_mismatch=False,
            allow_embedding_mismatch=False,
            confirm_restore=True,
        )
        self.assertEqual(backup.restore_backup(restore_args), 0)
        with closing(sqlite3.connect(target_db)) as connection:
            title = connection.execute("SELECT title FROM observations").fetchone()[0]
        self.assertEqual(title, "durable memory")
        self.assertEqual((target_qdrant / "collection/test/data.bin").read_bytes(), b"vector-data")
        self.assertFalse((target_qdrant / ".lock").exists())
        self.assertTrue((rollback / "engram/engram.db").is_file())
        self.assertTrue((rollback / "qdrant/old").is_file())

    def test_restore_requires_confirmation(self) -> None:
        self.create_archive()
        args = Namespace(
            archive=str(self.archive),
            components="all",
            engram_db=str(self.root / "new/engram.db"),
            qdrant_path=str(self.root / "new/qdrant"),
            rollback_dir=str(self.root / "rollback"),
            engram_version="engram test-version",
            qdrant_client_version="1.17.1",
            embedding_backend="ollama",
            embedding_model="test-model",
            allow_engram_version_mismatch=False,
            allow_qdrant_version_mismatch=False,
            allow_embedding_mismatch=False,
            confirm_restore=False,
        )
        with self.assertRaisesRegex(RuntimeError, "--confirm-restore"):
            backup.restore_backup(args)

    def test_restore_rejects_runtime_mismatch(self) -> None:
        self.create_archive()
        args = Namespace(
            archive=str(self.archive),
            components="all",
            engram_db=str(self.root / "new/engram.db"),
            qdrant_path=str(self.root / "new/qdrant"),
            rollback_dir=str(self.root / "rollback"),
            engram_version="engram different-version",
            qdrant_client_version="1.17.1",
            embedding_backend="ollama",
            embedding_model="test-model",
            allow_engram_version_mismatch=False,
            allow_qdrant_version_mismatch=False,
            allow_embedding_mismatch=False,
            confirm_restore=True,
        )
        with self.assertRaisesRegex(RuntimeError, "Engram version mismatch"):
            backup.restore_backup(args)

    def test_verify_rejects_path_traversal(self) -> None:
        malicious = self.root / "malicious.tar.gz"
        payload = self.root / "payload"
        payload.write_text("bad")
        with tarfile.open(malicious, "w:gz") as archive:
            archive.add(payload, arcname="../escape")
        with tempfile.TemporaryDirectory() as destination:
            with self.assertRaisesRegex(RuntimeError, "Unsafe archive path"):
                backup.extract_and_verify(malicious, Path(destination))

    def test_backup_rejects_qdrant_symlinks(self) -> None:
        os.symlink(self.root / "outside", self.qdrant / "unsafe")
        args = Namespace(
            output=str(self.archive),
            components="qdrant",
            engram_db=str(self.engram_db),
            engram_bin=str(self.engram_bin),
            qdrant_path=str(self.qdrant),
            qdrant_client_version="1.17.1",
            embedding_backend="ollama",
            embedding_model="test-model",
            addon_manifest=None,
        )
        with self.assertRaisesRegex(RuntimeError, "Symlink"):
            backup.create_backup(args)


if __name__ == "__main__":
    unittest.main()

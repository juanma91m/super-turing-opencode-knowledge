import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class V2ContractTests(unittest.TestCase):
    def test_native_inventory_matches_current_canonical_filter_and_reader_denies(self):
        spec = importlib.util.spec_from_file_location("fixture_manager", ROOT / "scripts/manage_opencode_config.py")
        manager = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(manager)
        native = json.loads((ROOT / "v2/engram-tools.json").read_text())
        self.assertEqual(native["tools"], manager.ENGRAM_TOOLS.split(","))
        self.assertEqual(len(native["tools"]), len(set(native["tools"])))
        reader = (ROOT / "agents/knowledge-reader.md").read_text().split("\n---\n", 1)[0]
        denied = re.findall(r"^  engram_(mem_\w+): deny$", reader, re.MULTILINE)
        self.assertEqual(native["readerDenied"], denied)


if __name__ == "__main__":
    unittest.main()

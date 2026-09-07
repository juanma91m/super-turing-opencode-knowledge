from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_config_manager():
    path = ROOT / "scripts" / "manage_opencode_config.py"
    spec = importlib.util.spec_from_file_location("manage_opencode_config", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OpenCodeIntegrationTests(unittest.TestCase):
    def test_engram_mcp_exposes_curated_operational_surface(self) -> None:
        module = load_config_manager()
        self.assertEqual(
            module.ENGRAM_TOOLS.split(","),
            [
                "mem_save",
                "mem_search",
                "mem_context",
                "mem_session_summary",
                "mem_get_observation",
                "mem_suggest_topic_key",
                "mem_update",
                "mem_judge",
                "mem_current_project",
                "mem_doctor",
                "mem_review",
            ],
        )
        self.assertNotIn("mem_delete", module.ENGRAM_TOOLS)


if __name__ == "__main__":
    unittest.main()

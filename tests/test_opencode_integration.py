from __future__ import annotations

import importlib.util
import json
import os
import re
import selectors
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLAUDE_TEMPLATE_TOOLS = (
    "mem_save,mem_search,mem_context,mem_session_summary,mem_get_observation,"
    "mem_suggest_topic_key,mem_update,mem_delete"
)


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

    def test_mcp_metadata_regressions_cover_both_canonical_filters(self) -> None:
        patch = (ROOT / "patches/engram-source-agent.patch").read_text()
        for tool_filter in (load_config_manager().ENGRAM_TOOLS, CLAUDE_TEMPLATE_TOOLS):
            self.assertIn('"' + tool_filter + '"', patch)
        self.assertIn('diff --git a/internal/mcp/instructions_test.go', patch)

    def test_patch_derives_instructions_after_registration_without_schema_changes(self) -> None:
        patch = (ROOT / "patches/engram-source-agent.patch").read_text()
        self.assertIn('+\tserver.WithInstructions(instructionsForTools(srv.ListTools()))(srv)', patch)
        self.assertIn('+\tsort.Strings(names)', patch)
        self.assertIn('TestServerInstructionsDoNotMutateRegisteredTools', patch)
        self.assertIn('TestServerInstructionsWithoutJudgeLeaveConflictsPending', patch)


def inspect_mcp(binary: str, tool_filter: str) -> dict:
    """Only metadata RPCs; isolated data/home/cwd, no inherited cloud credentials."""
    with tempfile.TemporaryDirectory(prefix="engram-mcp-metadata-") as temp:
        root = Path(temp)
        data = root / "data"
        data.mkdir()
        # Prevent startup migration from looking for orphaned DBs outside the fixture.
        sqlite3.connect(data / "engram.db").close()
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(root),
               "ENGRAM_DATA_DIR": str(data), "ENGRAM_CLOUD_AUTOSYNC": "0"}
        with tempfile.TemporaryFile(mode="w+t", dir=root) as errors:
            proc = subprocess.Popen([binary, "mcp", "--tools=" + tool_filter], cwd=root, env=env,
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors, text=True)
            try:
                def send(message: dict) -> None:
                    proc.stdin.write(json.dumps(message) + "\n")
                    proc.stdin.flush()

                def receive(request_id: int) -> dict:
                    with selectors.DefaultSelector() as selector:
                        selector.register(proc.stdout, selectors.EVENT_READ)
                        for _ in range(10):
                            if not selector.select(3):
                                raise AssertionError("MCP metadata timeout; raw stderr suppressed")
                            line = proc.stdout.readline()
                            if not line:
                                raise AssertionError("MCP process ended; raw stderr suppressed")
                            response = json.loads(line)
                            if response.get("id") == request_id:
                                if "error" in response:
                                    raise AssertionError("MCP metadata request failed")
                                return response["result"]
                    raise AssertionError("No matching MCP metadata response")

                send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                    "protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "isolated-metadata-test", "version": "1"}}})
                initialized = receive(1)
                send({"jsonrpc": "2.0", "method": "notifications/initialized"})
                send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
                listed = receive(2)
                if listed.get("nextCursor"):
                    raise AssertionError("Unexpected pagination: handle it before comparing catalogs")
                return {"instructions": initialized.get("instructions", ""),
                        "protocol": initialized["protocolVersion"],
                        "capabilities": initialized["capabilities"],
                        "tools": {tool["name"]: tool for tool in listed["tools"]}}
            finally:
                proc.stdin.close()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
                proc.stdout.close()


@unittest.skipUnless(os.environ.get("ENGRAM_CANDIDATE_BIN"), "Explicit isolated candidate binary required")
class EngramMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.filters = {
            "opencode": load_config_manager().ENGRAM_TOOLS,
            "claude-template": CLAUDE_TEMPLATE_TOOLS,
            "read-only": "mem_search,mem_context,mem_get_observation,mem_current_project,mem_doctor",
            "custom-with-unknown": "mem_search,mem_typo",
            "save-without-judge": "mem_save",
            "judge-only": "mem_judge",
            "unknown-selection": "mem_not_registered",
            "empty-filter-means-all": "",
            "all": "all",
        }
        cls.snapshots = {name: inspect_mcp(os.environ["ENGRAM_CANDIDATE_BIN"], value)
                         for name, value in cls.filters.items()}

    def test_initialize_catalog_matches_tools_list_for_each_profile(self) -> None:
        for name, snapshot in self.snapshots.items():
            with self.subTest(profile=name):
                text = snapshot["instructions"]
                catalog = text.split("REGISTERED TOOLS:\n", 1)[1].split("\n\n", 1)[0]
                self.assertEqual(re.findall(r"\bmem_[a-z_]+\b", catalog), sorted(snapshot["tools"]))
                self.assertLessEqual(set(re.findall(r"\bmem_[a-z_]+\b", text)), set(snapshot["tools"]))
                for unsupported in ("ToolSearch", "always available", "CORE TOOLS", "DEFERRED TOOLS"):
                    self.assertNotIn(unsupported, text)

    def test_filters_and_missing_judge_are_not_normalized(self) -> None:
        self.assertEqual(set(self.snapshots["opencode"]["tools"]), set(self.filters["opencode"].split(",")))
        self.assertEqual(set(self.snapshots["claude-template"]["tools"]), set(CLAUDE_TEMPLATE_TOOLS.split(",")))
        self.assertIn("No adjudication tool is registered", self.snapshots["claude-template"]["instructions"])
        self.assertIn("leave the judgments pending", self.snapshots["claude-template"]["instructions"])
        self.assertIn("each candidate has its own", self.snapshots["opencode"]["instructions"])
        self.assertEqual(self.snapshots["unknown-selection"]["tools"], {})
        self.assertEqual(set(self.snapshots["custom-with-unknown"]["tools"]), {"mem_search"})

    @unittest.skipUnless(os.environ.get("ENGRAM_BASELINE_BIN"), "Isolated baseline binary required")
    def test_schemas_annotations_protocol_and_conflict_rules_match_baseline(self) -> None:
        for name, value in self.filters.items():
            with self.subTest(profile=name):
                old = inspect_mcp(os.environ["ENGRAM_BASELINE_BIN"], value)
                new = self.snapshots[name]
                self.assertEqual(old["tools"], new["tools"])
                self.assertEqual(old["protocol"], new["protocol"])
                self.assertEqual(old["capabilities"], new["capabilities"])
                if "mem_judge" in new["tools"] and "mem_save" in new["tools"]:
                    marker = "IF judgment_required IS TRUE:"
                    self.assertEqual(old["instructions"].split(marker, 1)[1], new["instructions"].split(marker, 1)[1])


if __name__ == "__main__":
    unittest.main()

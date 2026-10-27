from __future__ import annotations

import importlib.util
import json
import os
import re
import selectors
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLAUDE_TEMPLATE_TOOLS = (
    "mem_save,mem_search,mem_context,mem_session_summary,mem_get_observation,"
    "mem_suggest_topic_key,mem_update,mem_delete"
)
READER_MUTATORS = {
    "mem_save", "mem_session_summary", "mem_update", "mem_judge", "mem_review",
}
READER_READS = {
    "mem_search", "mem_context", "mem_get_observation", "mem_suggest_topic_key",
    "mem_current_project", "mem_doctor",
}


def reader_text() -> str:
    return (ROOT / "agents/knowledge-reader.md").read_text()


def load_config_manager():
    path = ROOT / "scripts" / "manage_opencode_config.py"
    spec = importlib.util.spec_from_file_location("manage_opencode_config", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OpenCodeIntegrationTests(unittest.TestCase):
    def test_reader_inventory_requires_explicit_reclassification_on_drift(self) -> None:
        registered = load_config_manager().ENGRAM_TOOLS.split(",")
        self.assertEqual(len(registered), len(set(registered)))
        self.assertFalse(READER_MUTATORS & READER_READS)
        self.assertEqual(set(registered), READER_MUTATORS | READER_READS)

    def test_reader_denies_all_five_mutators_without_adding_read_allows(self) -> None:
        header = reader_text().split("\n---\n", 1)[0]
        rules = re.findall(r"^  (engram_\S+): (\S+)$", header, re.MULTILINE)
        self.assertEqual(len(rules), 5)
        self.assertEqual(dict(rules), {"engram_" + name: "deny" for name in READER_MUTATORS})
        # mem_review is mixed; no argument-based exception for its list action.
        self.assertEqual(header.count("  engram_mem_review: deny"), 1)

    def test_reader_keeps_its_existing_shell_edit_and_delegation_limits(self) -> None:
        header, body = reader_text().split("\n---\n", 1)
        self.assertIn('  edit: deny\n', header)
        self.assertIn('  task:\n    "*": deny', header)
        self.assertIn('  bash:\n    "*": deny\n', header)
        self.assertEqual(re.findall(r'^    "([^"]+)": allow$', header, re.MULTILINE), [
            "bash ~/.config/opencode/scripts/knowledge_search.sh*",
            "bash ~/.config/opencode/scripts/knowledge_status.sh*",
        ])
        for clause in ("no escribir en Engram ni en Qdrant", "no editar código ni configuración",
                       "no usar `knowledge_store.sh` ni `knowledge_seed_global.sh`",
                       "reutilizar evidencia suficiente del caller"):
            self.assertIn(clause, body)

    @unittest.skipUnless(os.environ.get("CLAUDE_READER_SOURCE"), "Explicit cross-client source required")
    def test_claude_reader_keeps_its_distinct_read_only_allowlist(self) -> None:
        text = Path(os.environ["CLAUDE_READER_SOURCE"]).read_text()
        tools = re.search(r"^tools: (.+)$", text, re.MULTILINE).group(1).split(", ")
        self.assertEqual(set(tools), {"Read", "Bash", "mcp__engram__mem_search",
                         "mcp__engram__mem_context", "mcp__engram__mem_get_observation",
                         "mcp__engram__mem_suggest_topic_key"})

    def test_retrieval_wrappers_keep_argument_routing_with_an_isolated_backend(self) -> None:
        # Execute real wrappers, but replace only their Python backend with a
        # fixture. No embeddings, Qdrant connection, user-local env or corpus write.
        with tempfile.TemporaryDirectory(prefix="reader-wrappers-", dir=os.environ.get("OPENCODE_TEST_TMP")) as temp:
            root = Path(temp)
            scripts = root / "scripts"
            scripts.mkdir()
            for name in ("knowledge_search.sh", "knowledge_env.sh", "knowledge_status.sh", "knowledge_status_qdrant.sh"):
                shutil.copy2(ROOT / "scripts" / name, scripts / name)
            python = root / "venv/bin/python"
            python.parent.mkdir(parents=True)
            python.write_text("#!" + sys.executable + "\nimport json, sys\n"
                              "assert sys.argv[2] in ('search', 'status')\n"
                              "print(json.dumps({'fixture': 'retrieved', 'args': sys.argv[2:]}))\n")
            python.chmod(0o755)
            env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(root),
                   "OPENCODE_KNOWLEDGE_HOME": str(root / "data"),
                   "OPENCODE_KNOWLEDGE_VENV": str(root / "venv")}
            for name, args, expected in (
                ("knowledge_search.sh", ["--query", "fixture", "--project", "fixture"],
                 ["search", "--query", "fixture", "--project", "fixture"]),
                ("knowledge_status.sh", ["--qdrant-only"], ["status"]),
            ):
                result = subprocess.run(["bash", str(scripts / name), *args], env=env, cwd=root,
                                        capture_output=True, text=True, timeout=15, check=True)
                self.assertEqual(json.loads(result.stdout), {"fixture": "retrieved", "args": expected})

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
    def test_structured_contracts_and_conflict_rules_match_baseline(self) -> None:
        for name, value in self.filters.items():
            with self.subTest(profile=name):
                old = inspect_mcp(os.environ["ENGRAM_BASELINE_BIN"], value)
                new = self.snapshots[name]
                self.assertEqual(set(old["tools"]), set(new["tools"]))
                policy_descriptions = {"mem_save", "mem_context", "mem_session_summary", "mem_current_project"}
                for tool, definition in old["tools"].items():
                    other = dict(new["tools"][tool])
                    if tool in policy_descriptions:
                        self.assertNotEqual(definition["description"], other["description"])
                        other["description"] = definition["description"]
                    self.assertEqual(definition, other)
                self.assertEqual(old["protocol"], new["protocol"])
                self.assertEqual(old["capabilities"], new["capabilities"])
                if "mem_judge" in new["tools"] and "mem_save" in new["tools"]:
                    marker = "IF judgment_required IS TRUE:"
                    self.assertEqual(old["instructions"].split(marker, 1)[1], new["instructions"].split(marker, 1)[1])


@unittest.skipUnless(os.environ.get("OPENCODE_READER_NATIVE"), "Explicit native sandbox opt-in required")
class NativeReaderPermissionTests(unittest.TestCase):
    """Actual binary ctx.ask + fixture counter; not a live MCP/LLM or Qdrant test."""

    def test_native_context_rejects_mutations_and_preserves_retrieval(self) -> None:
        binary = shutil.which("opencode")
        self.assertIsNotNone(binary)
        deps = Path(os.environ["OPENCODE_TEST_DEPENDENCIES"])
        self.assertTrue((deps / "@opencode-ai/plugin").is_dir(), "Use existing dependencies; never install")
        cases = [
            ("mem_save", {"title": "fixture", "content": "fixture", "capture_prompt": False}),
            ("mem_session_summary", {"content": "fixture"}),
            ("mem_update", {"id": 1, "content": "fixture"}),
            ("mem_judge", {"judgment_id": "rel-fixture", "relation": "related"}),
            ("mem_review", {"action": "mark_reviewed", "observation_id": 1}),
            ("mem_review", {"action": "list"}),
            ("mem_search", {"query": "fixture"}),
            ("mem_context", {}),
            ("mem_get_observation", {"id": 1}),
            ("mem_suggest_topic_key", {"title": "fixture"}),
            ("mem_current_project", {}),
            ("mem_doctor", {}),
        ]
        probe = '''export default {
          description: "Isolated permission boundary probe; fixture backend only.", args: {},
          async execute(_args, ctx) {
            const rows = []; let backendCalls = 0;
            for (const [name, payload] of CASES) {
              try {
                await ctx.ask({permission: "engram_" + name, patterns: ["*"], always: ["*"], metadata: {}});
              } catch (error) {
                // Do not count schema/type/loading failures as permission rejection.
                rows.push({name, payload, denied: String(error).includes("PermissionDeniedError"),
                           unexpectedError: !String(error).includes("PermissionDeniedError")});
                continue;
              }
              backendCalls++;
              rows.push({name, payload, denied: false, unexpectedError: false,
                         result: {fixture: "retrieved", query: payload.query ?? null}});
            }
            const guards = [];
            for (const [permission, pattern, expected] of [
              ["bash", "bash ~/.config/opencode/scripts/knowledge_search.sh --query fixture", true],
              ["bash", "bash ~/.config/opencode/scripts/knowledge_status.sh --qdrant-only", true],
              ["bash", "bash ~/.config/opencode/scripts/knowledge_store.sh fixture", false],
              ["bash", "bash ~/.config/opencode/scripts/knowledge_seed_global.sh fixture", false],
              ["bash", "engram save fixture", false], ["edit", "fixture.txt", false],
              ["task", "knowledge-curator", false]
            ]) {
              try {
                await ctx.ask({permission, patterns: [pattern], always: [pattern], metadata: {}});
                guards.push({expected, allowed: true, unexpectedError: false});
              } catch (error) {
                guards.push({expected, allowed: false, unexpectedError: !String(error).includes("PermissionDeniedError")});
              }
            }
            return JSON.stringify({rows, backendCalls, guards});
          }
        };'''.replace("CASES", json.dumps(cases))
        # Whitelisted environment: no inherited provider/cloud credentials and no active DB.
        with tempfile.TemporaryDirectory(prefix="reader-native-", dir=os.environ.get("OPENCODE_TEST_TMP")) as temp:
            root = Path(temp)
            home = root / "home"
            config_dir = home / ".config/opencode"
            (config_dir / "agents").mkdir(parents=True)
            (config_dir / "tools").mkdir()
            (config_dir / "node_modules").symlink_to(deps, target_is_directory=True)
            shutil.copy2(deps.parent / "package.json", config_dir / "package.json")
            (config_dir / "package-lock.json").write_bytes((deps.parent / "package-lock.json").read_bytes())
            (config_dir / ".gitignore").write_text("node_modules\npackage.json\npackage-lock.json\n")
            (config_dir / "opencode.json").write_text(json.dumps({
                "$schema": "https://opencode.ai/config.json", "plugin": [], "mcp": {},
            }))
            (config_dir / "tools/reader-permission-probe.ts").write_text(probe)
            env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
                   "XDG_CONFIG_HOME": str(home / ".config"), "XDG_DATA_HOME": str(root / "data"),
                   "XDG_STATE_HOME": str(root / "state"), "XDG_CACHE_HOME": str(root / "cache"),
                   "OPENCODE_CONFIG_DIR": str(config_dir), "OPENCODE_DISABLE_MODELS_FETCH": "1",
                   "OPENCODE_DISABLE_DEFAULT_PLUGINS": "1", "OPENCODE_DISABLE_EXTERNAL_SKILLS": "1",
                   "OPENCODE_DISABLE_CLAUDE_CODE_SKILLS": "1"}

            def run(text):
                (config_dir / "agents/knowledge-reader.md").write_text(text)
                with tempfile.TemporaryFile(mode="w+t", dir=root) as output:
                    result = subprocess.run([binary, "debug", "agent", "knowledge-reader", "--tool",
                                             "reader-permission-probe", "--params", "{}"],
                                            cwd=root, env=env, stdout=output, stderr=subprocess.PIPE,
                                            text=True, timeout=90)
                    self.assertEqual(result.returncode, 0, "Native fixture failed; raw output suppressed")
                    output.seek(0)
                    return json.loads(json.load(output)["result"]["output"])

            protected = run(reader_text())
            self.assertEqual(protected["backendCalls"], 6)
            for row in protected["rows"]:
                self.assertFalse(row["unexpectedError"])
                self.assertEqual(row["denied"], row["name"] in READER_MUTATORS)
                if not row["denied"]:
                    self.assertEqual(row["result"]["fixture"], "retrieved")
            for row in protected["guards"]:
                self.assertFalse(row["unexpectedError"])
                self.assertEqual(row["allowed"], row["expected"])
            # A positive control proves the fixture backend is reachable for the
            # same mutation payloads when the five rules are absent; it writes nothing.
            baseline = reader_text()
            for name in READER_MUTATORS:
                baseline = baseline.replace("  engram_" + name + ": deny\n", "")
            control = run(baseline)
            self.assertEqual(control["backendCalls"], len(cases))
            self.assertTrue(all(not row["denied"] and not row["unexpectedError"] for row in control["rows"]))


if __name__ == "__main__":
    unittest.main()

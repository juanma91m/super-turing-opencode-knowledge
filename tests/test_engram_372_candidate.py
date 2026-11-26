"""Opt-in wire regression; never starts the installed backend or uses real memory."""
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get("ENGRAM_372_CANDIDATE_BIN"), "Explicit 3.7.2 candidate required")
class Engram372Candidate(unittest.TestCase):
    def test_local_wire_contract(self):
        binary = Path(os.environ["ENGRAM_372_CANDIDATE_BIN"]).resolve(strict=True)
        self.assertNotEqual(binary, (Path.home() / ".opencode/bin/engram").resolve())
        self.assertIsNotNone(shutil.which("bwrap"))
        expected = json.loads((ROOT / "v2/engram-tools.json").read_text())["tools"]
        version = json.loads((ROOT / "KNOWLEDGE-MANIFEST.json").read_text())["engramCandidate"]["buildVersion"]
        with tempfile.TemporaryDirectory(prefix="engram-local-wire-") as temp:
            workspace = Path(temp)
            project = workspace / "fixture"
            project.mkdir()
            subprocess.run(["git", "init", "-q", str(project)], check=True,
                           env={"HOME": temp, "PATH": "/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1"})
            argv = [
                "/usr/bin/bwrap", "--unshare-net", "--unshare-pid", "--die-with-parent", "--clearenv",
                "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin",
                "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
                "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp",
                "--bind", temp, "/case", "--ro-bind", str(binary), "/engram",
                "--setenv", "PATH", "/usr/bin:/bin", "--setenv", "HOME", "/case",
                "--setenv", "ENGRAM_DATA_DIR", "/case/data", "--setenv", "ENGRAM_CLOUD_AUTOSYNC", "0",
                "--setenv", "ENGRAM_NO_UPDATE_CHECK", "1",
                "--chdir", "/case/fixture", "/engram", "mcp", "--tools=" + ",".join(expected),
            ]
            with subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  text=True) as proc, selectors.DefaultSelector() as selector:
                selector.register(proc.stdout, selectors.EVENT_READ)
                request_id = 0

                def send(message):
                    proc.stdin.write(json.dumps(message) + "\n")
                    proc.stdin.flush()

                def rpc(method, params):
                    nonlocal request_id
                    request_id += 1
                    send(dict(jsonrpc="2.0", id=request_id, method=method, params=params))
                    self.assertTrue(selector.select(10), "fixture RPC timeout")
                    response = json.loads(proc.stdout.readline())
                    self.assertEqual(response["id"], request_id)
                    return response["result"]

                def call(name, **args):
                    return rpc("tools/call", {"name": name, "arguments": args})

                def success(result):
                    self.assertFalse(result.get("isError"), result)
                    return result.get("structuredContent") or json.loads(result["content"][0]["text"])

                try:
                    info = rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                              "clientInfo": {"name": "local-fixture", "version": "1"}})
                    self.assertEqual(info["serverInfo"]["version"], version)
                    catalog = info["instructions"].split("REGISTERED TOOLS:\n", 1)[1].split("\n\n", 1)[0]
                    self.assertEqual(catalog.split(", "), sorted(expected))
                    self.assertNotIn("ToolSearch", info["instructions"])
                    send({"jsonrpc": "2.0", "method": "notifications/initialized"})
                    self.assertEqual({tool["name"] for tool in rpc("tools/list", {})["tools"]}, set(expected))

                    saved = success(call("mem_save", title="Synthetic provenance record", content="Fixture only",
                                         topic_key="fixture/source", source_agent="agent-design", capture_prompt=False))
                    for query in ("Synthetic provenance", "fixture/source", "Fi"):
                        hits = success(call("mem_search", query=query, source_agent="agent-design",
                                            response_format="compact", all_projects=True))["results"]
                        self.assertTrue(any(row["id"] == saved["id"] and row["source_agent"] == "agent-design" for row in hits))
                    self.assertTrue(call("mem_update", id=saved["id"], source_agent="reviewer").get("isError"))
                    self.assertTrue(call("mem_update", id=saved["id"], expected_project="wrong-project", source_agent="reviewer").get("isError"))
                    success(call("mem_update", id=saved["id"], expected_project=saved["project"], source_agent="reviewer"))
                    hits = success(call("mem_search", query="Synthetic provenance", source_agent="reviewer", all_projects=True))["results"]
                    self.assertEqual(hits[0]["source_agent"], "reviewer")
                    reviewed = success(call("mem_review", action="mark_reviewed", observation_id=saved["id"]))
                    self.assertEqual(reviewed["id"], saved["id"])
                    success(call("mem_update", id=saved["id"], expected_project=saved["project"], source_agent=""))
                    empty = call("mem_search", query="Synthetic provenance", source_agent="reviewer", all_projects=True)
                    self.assertFalse(empty.get("isError"), empty)
                    self.assertIn("No memories found", empty["content"][0]["text"])

                    self.assertTrue(call("mem_save", title="Denied", content="Fixture", session_id="ses_Unknown",
                                         capture_prompt=False).get("isError"))
                    self.assertTrue(call("mem_session_summary", session_id="foreign-unknown", content="Fixture").get("isError"))
                    self.assertTrue(call("mem_session_summary", session_id="ses_Mismatch", project="wrong-project",
                                         content="Fixture").get("isError"))
                    self.assertTrue(call("mem_session_summary", session_id="ses_BadRecovery", recovery_token="invalid",
                                         content="Fixture").get("isError"))
                    first = success(call("mem_session_summary", session_id="ses_OpenCodeFixture", content="First fixture"))
                    second = success(call("mem_session_summary", session_id="ses_OpenCodeFixture", content="Second fixture"))
                    self.assertEqual(first["id"], second["id"])
                    automatic = success(call("mem_session_summary", content="Automatic first fixture"))
                    repeated = success(call("mem_session_summary", content="Automatic second fixture"))
                    self.assertEqual(automatic["id"], repeated["id"])
                finally:
                    proc.stdin.close()
                    try:
                        proc.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)

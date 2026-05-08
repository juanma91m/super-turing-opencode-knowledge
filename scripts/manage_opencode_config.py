#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

ENGRAM_TOOLS = (
    "mem_save,mem_search,mem_context,mem_session_summary,"
    "mem_get_observation,mem_suggest_topic_key,mem_update,mem_delete"
)


def load_config(path: Path) -> dict:
    return json.loads(path.read_text())


def write_config(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def apply_engram(config: dict, engram_bin: str, enabled: bool) -> dict:
    mcp = config.setdefault("mcp", {})
    mcp["engram"] = {
        "type": "local",
        "command": [engram_bin, "mcp", f"--tools={ENGRAM_TOOLS}"],
        "enabled": enabled,
    }
    return config


def remove_engram(config: dict) -> dict:
    mcp = config.get("mcp")
    if not isinstance(mcp, dict):
        return config
    mcp.pop("engram", None)
    return config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Engram MCP wiring for OpenCode config")
    subparsers = parser.add_subparsers(dest="command", required=True)

    apply_cmd = subparsers.add_parser("apply-engram", help="Merge Engram MCP block into opencode.json")
    apply_cmd.add_argument("--config", required=True)
    apply_cmd.add_argument("--engram-bin", required=True)
    apply_cmd.add_argument("--enabled", choices=("true", "false"), required=True)

    remove_cmd = subparsers.add_parser("remove-engram", help="Remove Engram MCP block from opencode.json")
    remove_cmd.add_argument("--config", required=True)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config_path = Path(args.config).expanduser()
    if not config_path.exists():
        raise SystemExit(f"Config not found: {config_path}")

    config = load_config(config_path)

    if args.command == "apply-engram":
        apply_engram(config, args.engram_bin, args.enabled == "true")
    elif args.command == "remove-engram":
        remove_engram(config)
    else:
        raise SystemExit(f"Unknown command: {args.command}")

    write_config(config_path, config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

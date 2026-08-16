#!/usr/bin/env python3
"""Local-first Engram Cloud orchestration for the Knowledge addon."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


CONFIG_KEYS = {
    "OPENCODE_KNOWLEDGE_CLOUD_SERVER",
    "OPENCODE_KNOWLEDGE_CLOUD_TOKEN",
    "OPENCODE_KNOWLEDGE_CLOUD_PROJECTS",
    "OPENCODE_KNOWLEDGE_CLOUD_TIMEOUT_SECONDS",
    "OPENCODE_KNOWLEDGE_ENGRAM_BIN",
    "OPENCODE_KNOWLEDGE_ENGRAM_DATA_DIR",
    "OPENCODE_KNOWLEDGE_HOME",
}
PROJECT_LINE = re.compile(r"^\s{2}(.+?)\s+\d+\s+obs\s+\d+\s+sessions?\s+\d+\s+prompts?\s*$")


class ConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class SyncConfig:
    path: Path
    server: str
    token: str
    projects: tuple[str, ...]
    timeout: int
    engram_bin: Path
    data_dir: Path
    knowledge_home: Path

    @property
    def state_dir(self) -> Path:
        return self.knowledge_home / "sync"

    @property
    def state_file(self) -> Path:
        return self.state_dir / "status.json"

    @property
    def lock_file(self) -> Path:
        return self.knowledge_home / "locks" / "engram-cloud-sync.lock"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_config_path() -> Path:
    override = os.environ.get("OPENCODE_KNOWLEDGE_SYNC_CONFIG", "").strip()
    return Path(override).expanduser() if override else Path.home() / ".config/opencode/knowledge-sync.conf"


def parse_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise ConfigurationError(
            f"client config not found: {path}; copy knowledge/knowledge-sync.conf.example and set mode 0600"
        )
    values: dict[str, str] = {}
    for number, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            raise ConfigurationError(f"invalid config line {path}:{number}")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key not in CONFIG_KEYS:
            raise ConfigurationError(f"unsupported config key {key!r} at {path}:{number}")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def _value(values: dict[str, str], key: str, default: str = "") -> str:
    return os.environ.get(key, values.get(key, default)).strip()


def load_config(path: Path | None = None, *, require_remote: bool = True) -> SyncConfig:
    path = (path or default_config_path()).expanduser()
    values = parse_env_file(path)
    server = _value(values, "OPENCODE_KNOWLEDGE_CLOUD_SERVER").rstrip("/")
    token = _value(values, "OPENCODE_KNOWLEDGE_CLOUD_TOKEN")
    projects_raw = _value(values, "OPENCODE_KNOWLEDGE_CLOUD_PROJECTS")
    projects = tuple(sorted({item.strip() for item in projects_raw.split(",") if item.strip()}))
    timeout_raw = _value(values, "OPENCODE_KNOWLEDGE_CLOUD_TIMEOUT_SECONDS", "30")
    try:
        timeout = int(timeout_raw)
    except ValueError as exc:
        raise ConfigurationError("OPENCODE_KNOWLEDGE_CLOUD_TIMEOUT_SECONDS must be an integer") from exc
    if timeout < 1 or timeout > 3600:
        raise ConfigurationError("cloud timeout must be between 1 and 3600 seconds")
    if require_remote:
        if not server.startswith(("http://", "https://")):
            raise ConfigurationError("cloud server must be an explicit http:// or https:// URL")
        if not token:
            raise ConfigurationError("cloud token is required; insecure no-auth mode is not supported")
        if not projects:
            raise ConfigurationError("cloud project allowlist is empty")
        if "*" in projects:
            raise ConfigurationError("wildcard projects are not allowed")
    engram_bin = Path(
        _value(values, "OPENCODE_KNOWLEDGE_ENGRAM_BIN", str(Path.home() / ".opencode/bin/engram"))
    ).expanduser()
    data_dir = Path(
        _value(
            values,
            "OPENCODE_KNOWLEDGE_ENGRAM_DATA_DIR",
            os.environ.get("ENGRAM_DATA_DIR", str(Path.home() / ".engram")),
        )
    ).expanduser()
    knowledge_home = Path(
        _value(
            values,
            "OPENCODE_KNOWLEDGE_HOME",
            str(Path.home() / ".local/share/super-turing-opencode-knowledge"),
        )
    ).expanduser()
    if not engram_bin.is_file() or not os.access(engram_bin, os.X_OK):
        raise ConfigurationError(f"Engram binary is not executable: {engram_bin}")
    if not data_dir.is_absolute() or not knowledge_home.is_absolute():
        raise ConfigurationError("Engram data dir and knowledge home must be absolute paths")
    return SyncConfig(path, server, token, projects, timeout, engram_bin, data_dir, knowledge_home)


def secure_config_warning(path: Path) -> str | None:
    if path.stat().st_mode & 0o077:
        return f"config permissions are too broad: {path}; run chmod 600"
    return None


def command_env(config: SyncConfig) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "ENGRAM_CLOUD_SERVER": config.server,
            "ENGRAM_CLOUD_TOKEN": config.token,
            "ENGRAM_CLOUD_AUTOSYNC": "0",
            "ENGRAM_DATA_DIR": str(config.data_dir),
        }
    )
    env.pop("ENGRAM_CLOUD_INSECURE_NO_AUTH", None)
    return env


def run_engram(config: SyncConfig, args: Iterable[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(config.engram_bin), *args],
        env=command_env(config),
        text=True,
        capture_output=True,
        timeout=config.timeout,
        check=False,
    )


def redact(text: str, token: str) -> str:
    return text.replace(token, "<redacted>") if token else text


def local_projects(config: SyncConfig) -> set[str]:
    result = run_engram(config, ("projects", "list"))
    if result.returncode != 0:
        raise RuntimeError(redact(result.stderr.strip() or "engram projects list failed", config.token))
    projects: set[str] = set()
    for line in result.stdout.splitlines():
        match = PROJECT_LINE.match(line)
        if match:
            projects.add(match.group(1).strip())
    return projects


def enrolled_projects(config: SyncConfig) -> set[str]:
    database = config.data_dir / "engram.db"
    if not database.is_file():
        return set()
    try:
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True, timeout=2)
        try:
            return {row[0] for row in connection.execute("SELECT project FROM sync_enrolled_projects")}
        finally:
            connection.close()
    except sqlite3.Error:
        return set()


def server_health(config: SyncConfig) -> tuple[bool, str]:
    request = urllib.request.Request(config.server + "/health", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=config.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            healthy = response.status == 200 and payload.get("status") == "ok"
            return healthy, f"http={response.status} service={payload.get('service', 'unknown')}"
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        return False, redact(str(exc), config.token)


def read_local_sync_details(config: SyncConfig, project: str) -> dict[str, object]:
    details: dict[str, object] = {"pending_local": "unknown", "enrolled": "unknown"}
    database = config.data_dir / "engram.db"
    if not database.is_file():
        return details
    try:
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True, timeout=2)
        try:
            details["pending_local"] = connection.execute(
                "SELECT count(*) FROM sync_mutations "
                "WHERE project = ? AND source = 'local' AND acked_at IS NULL",
                (project,),
            ).fetchone()[0]
            details["enrolled"] = bool(
                connection.execute(
                    "SELECT 1 FROM sync_enrolled_projects WHERE project = ? LIMIT 1", (project,)
                ).fetchone()
            )
            row = connection.execute(
                "SELECT lifecycle, last_acked_seq, last_pulled_seq, reason_code, reason_message, updated_at "
                "FROM sync_state WHERE target_key = ?",
                (f"cloud:{project}",),
            ).fetchone()
            if row:
                details.update(
                    {
                        "lifecycle": row[0],
                        "last_acked_seq": row[1],
                        "last_pulled_seq": row[2],
                        "reason_code": row[3] or "",
                        "reason_message": row[4] or "",
                        "state_updated_at": row[5],
                    }
                )
        finally:
            connection.close()
    except sqlite3.Error as exc:
        details["sqlite_error"] = str(exc)
    return details


def load_state(config: SyncConfig) -> dict[str, object]:
    try:
        return json.loads(config.state_file.read_text())
    except (FileNotFoundError, ValueError):
        return {}


def write_state(config: SyncConfig, state: dict[str, object]) -> None:
    config.state_dir.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="status.", suffix=".tmp", dir=config.state_dir)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, config.state_file)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class SyncLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle = None

    def __enter__(self) -> "SyncLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+")
        os.chmod(self.path, 0o600)
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.handle.close()
            raise RuntimeError(f"another knowledge sync holds {self.path}") from exc
        self.handle.seek(0)
        self.handle.truncate()
        self.handle.write(f"pid={os.getpid()} started_at={now_iso()}\n")
        self.handle.flush()
        return self

    def __exit__(self, *_: object) -> None:
        assert self.handle is not None
        fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        self.handle.close()


def print_process_output(project: str, phase: str, result: subprocess.CompletedProcess[str], token: str) -> None:
    for stream_name, text in (("out", result.stdout), ("err", result.stderr)):
        for line in redact(text, token).splitlines():
            print(f"[{project}][{phase}][{stream_name}] {line}")


def sync_project(config: SyncConfig, project: str, phase: str) -> tuple[bool, str]:
    args = ["sync", "--cloud", "--project", project]
    if phase == "pull":
        args.insert(2, "--import")
    try:
        result = run_engram(config, args)
    except subprocess.TimeoutExpired:
        return False, f"timed out after {config.timeout}s"
    print_process_output(project, phase, result, config.token)
    if result.returncode == 0:
        return True, "ok"
    message = result.stderr.strip() or result.stdout.strip() or f"exit={result.returncode}"
    return False, redact(message.splitlines()[-1], config.token)


def execute(action: str, config: SyncConfig) -> int:
    warning = secure_config_warning(config.path)
    if warning:
        print(f"configuration error: {warning}", file=sys.stderr)
        return 2
    try:
        configured_locals = local_projects(config)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    configured_or_enrolled = configured_locals | enrolled_projects(config)
    unknown = [project for project in config.projects if project not in configured_or_enrolled]
    if unknown:
        print(
            "error: configured projects are neither present in `engram projects list` nor explicitly enrolled: "
            + ", ".join(unknown),
            file=sys.stderr,
        )
        return 1
    started = now_iso()
    previous_state = load_state(config)
    state: dict[str, object] = {
        "action": action,
        "started_at": started,
        "completed_at": None,
        "result": "running",
        "projects": {},
    }
    try:
        with SyncLock(config.lock_file):
            write_state(config, state)
            failures = 0
            project_states: dict[str, object] = {}
            for project in config.projects:
                phases = ("pull", "push") if action == "sync" else (action,)
                phase_states: dict[str, object] = {}
                for phase in phases:
                    ok, message = sync_project(config, project, phase)
                    phase_states[phase] = {"ok": ok, "message": message, "at": now_iso()}
                    if not ok:
                        failures += 1
                        if phase == "pull" and action == "sync":
                            phase_states["push"] = {
                                "ok": False,
                                "skipped": True,
                                "message": "pull failed",
                            }
                        break
                project_states[project] = phase_states
            state.update(
                {
                    "completed_at": now_iso(),
                    "result": "ok" if failures == 0 else "degraded",
                    "projects": project_states,
                }
            )
            if failures == 0:
                state["last_success_at"] = state["completed_at"]
            else:
                if previous_state.get("last_success_at"):
                    state["last_success_at"] = previous_state["last_success_at"]
            write_state(config, state)
            print(f"knowledge-{action}: {state['result']} projects={len(config.projects)} failures={failures}")
            return 0 if failures == 0 else 1
    except RuntimeError as exc:
        print(f"knowledge-{action}: skipped: {exc}", file=sys.stderr)
        return 75


def print_status(config: SyncConfig) -> int:
    warning = secure_config_warning(config.path)
    healthy, health_message = server_health(config)
    state = load_state(config)
    print(f"config={config.path}")
    print(f"config_permissions={'warning' if warning else 'ok'}")
    print(f"server={config.server}")
    print(f"server_reachable={'yes' if healthy else 'no'}")
    print(f"server_health={health_message}")
    print(f"autosync_internal=disabled")
    print(f"projects={','.join(config.projects)}")
    try:
        known = local_projects(config)
    except RuntimeError as exc:
        known = set()
        print(f"local_projects_error={exc}")
    for project in config.projects:
        print(f"project[{project}].known_local={'yes' if project in known else 'no'}")
        for key, value in read_local_sync_details(config, project).items():
            clean = redact(str(value).replace("\n", " "), config.token)
            print(f"project[{project}].{key}={clean}")
        if healthy:
            try:
                result = run_engram(config, ("sync", "--cloud", "--status", "--project", project))
                print(f"project[{project}].remote_status={'ok' if result.returncode == 0 else 'error'}")
                for line in redact((result.stdout if result.returncode == 0 else result.stderr), config.token).splitlines():
                    print(f"project[{project}].remote={line.strip()}")
            except subprocess.TimeoutExpired:
                print(f"project[{project}].remote_status=timeout")
    print(f"last_run_result={state.get('result', 'never')}")
    print(f"last_run_at={state.get('completed_at', 'never')}")
    print(f"last_success_at={state.get('last_success_at', 'never')}")
    return 0 if healthy and not warning else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("push", "pull", "sync", "status"))
    parser.add_argument("--config", type=Path, help="machine-local client config")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
    except (ConfigurationError, OSError) as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    if args.action == "status":
        return print_status(config)
    return execute(args.action, config)


if __name__ == "__main__":
    raise SystemExit(main())

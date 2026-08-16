#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


BACKUP_KIND = "super-turing-opencode-knowledge-backup"
SCHEMA_VERSION = 1


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sqlite_integrity(path: Path) -> str:
    uri = path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, timeout=30)) as connection:
        result = connection.execute("PRAGMA integrity_check").fetchone()
    return str(result[0] if result else "unknown")


def sqlite_backup(source: Path, target: Path) -> None:
    if not source.is_file():
        raise RuntimeError(f"Engram database not found: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    source_uri = source.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(source_uri, uri=True, timeout=30)) as src:
        with closing(sqlite3.connect(target)) as dst:
            src.backup(dst)
    if sqlite_integrity(target) != "ok":
        raise RuntimeError("Engram SQLite backup failed integrity_check")


def reject_symlinks(root: Path) -> None:
    if root.is_symlink():
        raise RuntimeError(f"Symlinked state root rejected: {root}")
    for current, directories, files in os.walk(root):
        current_path = Path(current)
        for name in [*directories, *files]:
            candidate = current_path / name
            if candidate.is_symlink():
                raise RuntimeError(f"Symlink inside state root rejected: {candidate}")


def copy_qdrant(source: Path, target: Path) -> None:
    if not source.is_dir():
        raise RuntimeError(f"Qdrant local storage not found: {source}")
    reject_symlinks(source)

    def ignore_root_lock(directory: str, names: list[str]) -> set[str]:
        if Path(directory).resolve() == source.resolve() and ".lock" in names:
            return {".lock"}
        return set()

    shutil.copytree(source, target, ignore=ignore_root_lock)


def read_addon_version(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    value = data.get("version")
    return str(value) if value else None


def run_engram_export(binary: Path, data_dir: Path, target: Path) -> str:
    if not os.access(binary, os.X_OK):
        raise RuntimeError(f"Engram binary not executable: {binary}")
    env = os.environ.copy()
    env["ENGRAM_DATA_DIR"] = str(data_dir)
    version = subprocess.run(
        [str(binary), "version"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    ).stdout.strip()
    subprocess.run(
        [str(binary), "export", str(target)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    if not target.is_file():
        raise RuntimeError("Engram export did not create the expected JSON file")
    return version


def payload_files(root: Path) -> list[Path]:
    return sorted(
        path for path in root.rglob("*") if path.is_file() and path.name != "manifest.json"
    )


def create_backup(args: argparse.Namespace) -> int:
    output = Path(args.output).expanduser().resolve()
    if output.exists():
        raise RuntimeError(f"Refusing to overwrite existing backup: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    components = args.components

    with tempfile.TemporaryDirectory(prefix="knowledge-backup-", dir=output.parent) as temp_dir:
        staging = Path(temp_dir) / "knowledge-backup"
        staging.mkdir(mode=0o700)
        manifest: dict = {
            "schemaVersion": SCHEMA_VERSION,
            "kind": BACKUP_KIND,
            "createdAt": now_iso(),
            "addonVersion": read_addon_version(
                Path(args.addon_manifest).expanduser() if args.addon_manifest else None
            ),
            "components": {},
            "files": {},
            "security": {
                "containsSensitiveData": True,
                "includesSecrets": False,
            },
        }

        if components in {"all", "engram"}:
            engram_db = Path(args.engram_db).expanduser().resolve()
            engram_dir = staging / "engram"
            backup_db = engram_dir / "engram.db"
            export_json = engram_dir / "engram-export.json"
            sqlite_backup(engram_db, backup_db)
            version = run_engram_export(
                Path(args.engram_bin).expanduser().resolve(), engram_db.parent, export_json
            )
            manifest["components"]["engram"] = {
                "included": True,
                "version": version,
                "database": "engram/engram.db",
                "logicalExport": "engram/engram-export.json",
                "sqliteIntegrity": "ok",
            }

        if components in {"all", "qdrant"}:
            qdrant_source = Path(args.qdrant_path).expanduser().resolve()
            qdrant_target = staging / "qdrant"
            copy_qdrant(qdrant_source, qdrant_target)
            manifest["components"]["qdrant"] = {
                "included": True,
                "storage": "qdrant/",
                "clientVersion": args.qdrant_client_version or None,
                "embeddingBackend": args.embedding_backend or None,
                "embeddingModel": args.embedding_model or None,
            }

        for path in payload_files(staging):
            relative = path.relative_to(staging).as_posix()
            manifest["files"][relative] = {
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
            }
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

        temporary_archive = output.with_name(output.name + ".tmp")
        try:
            with tarfile.open(temporary_archive, "w:gz") as archive:
                archive.add(staging, arcname="knowledge-backup", recursive=True)
            os.chmod(temporary_archive, 0o600)
            os.replace(temporary_archive, output)
        finally:
            temporary_archive.unlink(missing_ok=True)

    print(f"backup={output}")
    print(f"sha256={sha256_file(output)}")
    print(f"components={','.join(manifest['components'])}")
    print("contains_sensitive_data=yes")
    return 0


def validate_member(member: tarfile.TarInfo) -> None:
    path = PurePosixPath(member.name)
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError(f"Unsafe archive path rejected: {member.name}")
    if member.issym() or member.islnk() or member.isdev():
        raise RuntimeError(f"Unsafe archive member rejected: {member.name}")


def extract_and_verify(archive_path: Path, destination: Path) -> tuple[Path, dict]:
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        for member in members:
            validate_member(member)
        try:
            archive.extractall(destination, members=members, filter="data")
        except TypeError:
            archive.extractall(destination, members=members)

    root = destination / "knowledge-backup"
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError("Backup manifest is missing")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("kind") != BACKUP_KIND or manifest.get("schemaVersion") != SCHEMA_VERSION:
        raise RuntimeError("Unsupported knowledge backup format")

    declared = manifest.get("files")
    if not isinstance(declared, dict):
        raise RuntimeError("Invalid backup file manifest")
    actual = {
        path.relative_to(root).as_posix()
        for path in payload_files(root)
    }
    if actual != set(declared):
        raise RuntimeError("Backup payload does not match manifest")
    for relative, metadata in declared.items():
        path = root / relative
        if path.stat().st_size != metadata.get("size"):
            raise RuntimeError(f"Backup size mismatch: {relative}")
        if sha256_file(path) != metadata.get("sha256"):
            raise RuntimeError(f"Backup checksum mismatch: {relative}")

    engram_db = root / "engram/engram.db"
    if engram_db.is_file() and sqlite_integrity(engram_db) != "ok":
        raise RuntimeError("Backup Engram database failed integrity_check")
    return root, manifest


def verify_backup(args: argparse.Namespace) -> int:
    archive_path = Path(args.archive).expanduser().resolve()
    if not archive_path.is_file():
        raise RuntimeError(f"Backup archive not found: {archive_path}")
    with tempfile.TemporaryDirectory(prefix="knowledge-verify-") as temp_dir:
        _, manifest = extract_and_verify(archive_path, Path(temp_dir))
    print(f"backup={archive_path}")
    print(f"created_at={manifest.get('createdAt')}")
    print(f"addon_version={manifest.get('addonVersion') or 'unknown'}")
    print(f"components={','.join(manifest.get('components', {}))}")
    print("verification=ok")
    return 0


def backup_existing_engram(source: Path, rollback: Path) -> None:
    if source.is_file():
        sqlite_backup(source, rollback / "engram/engram.db")


def restore_backup(args: argparse.Namespace) -> int:
    archive_path = Path(args.archive).expanduser().resolve()
    if not archive_path.is_file():
        raise RuntimeError(f"Backup archive not found: {archive_path}")
    if not args.confirm_restore:
        raise RuntimeError("Refusing restore without --confirm-restore")

    components = args.components
    engram_target = Path(args.engram_db).expanduser().resolve()
    qdrant_target = Path(args.qdrant_path).expanduser().resolve()
    rollback_root = Path(args.rollback_dir).expanduser().resolve()
    if rollback_root.exists():
        raise RuntimeError(f"Rollback directory already exists: {rollback_root}")

    with tempfile.TemporaryDirectory(prefix="knowledge-restore-") as temp_dir:
        root, manifest = extract_and_verify(archive_path, Path(temp_dir))
        included = manifest.get("components", {})
        selected = ["engram", "qdrant"] if components == "all" else [components]
        missing = [name for name in selected if name not in included]
        if missing:
            raise RuntimeError(f"Backup does not include selected components: {','.join(missing)}")

        if "engram" in selected:
            source_version = (included.get("engram") or {}).get("version")
            target_version = getattr(args, "engram_version", None)
            if source_version and target_version and source_version != target_version:
                if not getattr(args, "allow_engram_version_mismatch", False):
                    raise RuntimeError(
                        "Engram version mismatch "
                        f"(backup={source_version}, target={target_version}); "
                        "install the same addon/runtime or pass --allow-engram-version-mismatch"
                    )

        if "qdrant" in selected:
            source_qdrant = included.get("qdrant") or {}
            source_version = source_qdrant.get("clientVersion")
            target_version = getattr(args, "qdrant_client_version", None)
            if source_version and target_version and source_version != target_version:
                if not getattr(args, "allow_qdrant_version_mismatch", False):
                    raise RuntimeError(
                        "Qdrant client version mismatch "
                        f"(backup={source_version}, target={target_version}); "
                        "install the same version or pass --allow-qdrant-version-mismatch"
                    )
            source_backend = source_qdrant.get("embeddingBackend")
            source_model = source_qdrant.get("embeddingModel")
            target_backend = getattr(args, "embedding_backend", None)
            target_model = getattr(args, "embedding_model", None)
            embedding_mismatch = (
                source_backend
                and target_backend
                and source_backend != target_backend
            ) or (source_model and target_model and source_model != target_model)
            if embedding_mismatch and not getattr(args, "allow_embedding_mismatch", False):
                raise RuntimeError(
                    "Embedding configuration mismatch "
                    f"(backup={source_backend}/{source_model}, "
                    f"target={target_backend}/{target_model}); "
                    "align the embedding runtime or pass --allow-embedding-mismatch"
                )

        rollback_root.mkdir(parents=True, mode=0o700)
        staged_engram: Path | None = None
        staged_qdrant: Path | None = None
        qdrant_rollback: Path | None = None
        qdrant_restored = False
        try:
            if "engram" in selected:
                backup_existing_engram(engram_target, rollback_root)
                engram_target.parent.mkdir(parents=True, exist_ok=True)
                staged_engram = engram_target.with_name(
                    engram_target.name + f".restore.{uuid.uuid4().hex}"
                )
                shutil.copy2(root / "engram/engram.db", staged_engram)
                os.chmod(staged_engram, 0o600)

            if "qdrant" in selected:
                qdrant_target.parent.mkdir(parents=True, exist_ok=True)
                staged_qdrant = qdrant_target.with_name(
                    qdrant_target.name + f".restore.{uuid.uuid4().hex}"
                )
                shutil.copytree(root / "qdrant", staged_qdrant)

            if staged_qdrant is not None:
                if qdrant_target.exists():
                    qdrant_rollback = rollback_root / "qdrant"
                    shutil.move(str(qdrant_target), str(qdrant_rollback))
                os.replace(staged_qdrant, qdrant_target)
                staged_qdrant = None
                qdrant_restored = True

            if staged_engram is not None:
                os.replace(staged_engram, engram_target)
                staged_engram = None
        except Exception:
            if staged_engram is not None:
                staged_engram.unlink(missing_ok=True)
            if staged_qdrant is not None and staged_qdrant.exists():
                shutil.rmtree(staged_qdrant)
            if qdrant_restored and qdrant_target.exists():
                shutil.rmtree(qdrant_target)
            if qdrant_rollback is not None and qdrant_rollback.exists():
                shutil.move(str(qdrant_rollback), str(qdrant_target))
            raise

    print(f"backup={archive_path}")
    print(f"components={','.join(selected)}")
    print(f"rollback_dir={rollback_root}")
    print("restore=ok")
    print("restart_opencode_required=yes")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Portable Engram + Qdrant backup helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create")
    create.add_argument("--output", required=True)
    create.add_argument("--components", choices=("all", "engram", "qdrant"), default="all")
    create.add_argument("--engram-db", required=True)
    create.add_argument("--engram-bin", required=True)
    create.add_argument("--qdrant-path", required=True)
    create.add_argument("--qdrant-client-version")
    create.add_argument("--embedding-backend")
    create.add_argument("--embedding-model")
    create.add_argument("--addon-manifest")
    create.set_defaults(func=create_backup)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--archive", required=True)
    verify.set_defaults(func=verify_backup)

    restore = subparsers.add_parser("restore")
    restore.add_argument("--archive", required=True)
    restore.add_argument("--components", choices=("all", "engram", "qdrant"), default="all")
    restore.add_argument("--engram-db", required=True)
    restore.add_argument("--qdrant-path", required=True)
    restore.add_argument("--rollback-dir", required=True)
    restore.add_argument("--engram-version")
    restore.add_argument("--qdrant-client-version")
    restore.add_argument("--embedding-backend")
    restore.add_argument("--embedding-model")
    restore.add_argument("--allow-engram-version-mismatch", action="store_true")
    restore.add_argument("--allow-qdrant-version-mismatch", action="store_true")
    restore.add_argument("--allow-embedding-mismatch", action="store_true")
    restore.add_argument("--confirm-restore", action="store_true")
    restore.set_defaults(func=restore_backup)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except (OSError, RuntimeError, sqlite3.Error, subprocess.SubprocessError, tarfile.TarError, json.JSONDecodeError) as exc:
        print(f"knowledge backup error: {exc}", file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

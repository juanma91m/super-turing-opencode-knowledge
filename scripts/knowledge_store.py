#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

try:
    from qdrant_client import QdrantClient, models
except ImportError as exc:  # pragma: no cover - runtime guard
    print(
        "Knowledge layer no instalado. Corré: bash ~/.config/opencode/scripts/install-knowledge.sh",
        file=sys.stderr,
    )
    raise SystemExit(2) from exc


DEFAULT_HOME = Path(
    os.environ.get("OPENCODE_KNOWLEDGE_HOME", "~/.local/share/super-turing-opencode-knowledge")
).expanduser()
DEFAULT_DB_PATH = Path(os.environ.get("QDRANT_LOCAL_PATH", str(DEFAULT_HOME / "qdrant"))).expanduser()
DEFAULT_COLLECTION = os.environ.get("OPENCODE_KNOWLEDGE_COLLECTION", "global-opencode-knowledge")
DEFAULT_EMBEDDING_MODEL = os.environ.get(
    "OPENCODE_KNOWLEDGE_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
DEFAULT_SCOPE = os.environ.get("OPENCODE_KNOWLEDGE_SCOPE", "global")
DEFAULT_PROJECT = os.environ.get("OPENCODE_KNOWLEDGE_PROJECT", "opencode-stack")
ALLOWED_SUFFIXES = {
    ".md",
    ".markdown",
    ".txt",
    ".json",
    ".jsonc",
    ".yml",
    ".yaml",
    ".py",
    ".sh",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".cjs",
    ".go",
    ".java",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def make_client(db_path: Path) -> QdrantClient:
    db_path.mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=str(db_path))


def ensure_collection(client: QdrantClient, collection: str, model_name: str) -> None:
    collections = {item.name for item in client.get_collections().collections}
    if collection in collections:
        return

    client.create_collection(
        collection_name=collection,
        vectors_config=models.VectorParams(
            size=client.get_embedding_size(model_name), distance=models.Distance.COSINE
        ),
    )


def stable_id(collection: str, source_id: str, chunk_index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{collection}|{source_id}|{chunk_index}"))


def normalize_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    tags = [item.strip() for item in raw.split(",")]
    return [item for item in tags if item]


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    length = len(normalized)

    while start < length:
        end = min(length, start + chunk_size)
        if end < length:
            pivot = start + max(chunk_size // 2, 1)
            split_at = max(normalized.rfind("\n", pivot, end), normalized.rfind(" ", pivot, end))
            if split_at > start:
                end = split_at

        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= length:
            break

        start = max(end - chunk_overlap, start + 1)

    return chunks


def iter_source_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        if path.suffix.lower() in ALLOWED_SUFFIXES:
            yield path
        return

    for candidate in sorted(path.rglob("*")):
        if candidate.is_file() and candidate.suffix.lower() in ALLOWED_SUFFIXES:
            yield candidate


def base_payload(
    *,
    scope: str,
    project: str,
    source_type: str,
    source_id: str,
    title: str,
    tags: Sequence[str],
    ingested_by: str,
    source_path: str | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "scope": scope,
        "project": project,
        "source_type": source_type,
        "source_id": source_id,
        "title": title,
        "tags": list(tags),
        "ingested_at": now_iso(),
        "ingested_by": ingested_by,
        "knowledge_schema_version": 1,
    }
    if source_path:
        payload["source_path"] = source_path
    return payload


def build_filter(scope: str | None, project: str | None, source_id: str | None):
    must = []
    if scope:
        must.append(models.FieldCondition(key="scope", match=models.MatchValue(value=scope)))
    if project:
        must.append(models.FieldCondition(key="project", match=models.MatchValue(value=project)))
    if source_id:
        must.append(models.FieldCondition(key="source_id", match=models.MatchValue(value=source_id)))
    if not must:
        return None
    return models.Filter(must=must)


def delete_existing_source(client: QdrantClient, collection: str, scope: str, project: str, source_id: str) -> None:
    points_filter = build_filter(scope=scope, project=project, source_id=source_id)
    if points_filter is None:
        return
    client.delete(collection_name=collection, points_selector=points_filter)


def upload_chunks(
    *,
    client: QdrantClient,
    collection: str,
    model_name: str,
    source_id: str,
    chunks: Sequence[str],
    payload_base: dict[str, object],
) -> None:
    payloads = []
    vectors = []
    ids = []
    chunk_count = len(chunks)

    for chunk_index, chunk in enumerate(chunks):
        payload = dict(payload_base)
        payload.update(
            {
                "text": chunk,
                "chunk_index": chunk_index,
                "chunk_count": chunk_count,
                "content_sha256": hashlib.sha256(chunk.encode("utf-8")).hexdigest(),
            }
        )
        payloads.append(payload)
        vectors.append(models.Document(text=chunk, model=model_name))
        ids.append(stable_id(collection, source_id, chunk_index))

    client.upload_collection(collection_name=collection, vectors=vectors, payload=payloads, ids=ids)


def command_store_path(args: argparse.Namespace) -> int:
    target_path = Path(args.path).expanduser().resolve()
    if not target_path.exists():
        print(f"Path not found: {target_path}", file=sys.stderr)
        return 2

    client = make_client(Path(args.db_path).expanduser())
    ensure_collection(client, args.collection, args.model)

    if target_path.is_file():
        roots = list(iter_source_files(target_path))
        root_dir = target_path.parent
    else:
        roots = list(iter_source_files(target_path))
        root_dir = target_path

    if not roots:
        print(f"No se encontraron archivos soportados en: {target_path}", file=sys.stderr)
        return 2

    stored = 0
    for file_path in roots:
        relative = file_path.relative_to(root_dir) if file_path != root_dir else file_path.name
        relative_str = str(relative).replace(os.sep, "/")
        text = load_text(file_path)
        chunks = chunk_text(text, args.chunk_size, args.chunk_overlap)
        if not chunks:
            continue

        source_id = f"{args.project}:{relative_str}"
        if args.replace_source:
            delete_existing_source(client, args.collection, args.scope, args.project, source_id)

        payload = base_payload(
            scope=args.scope,
            project=args.project,
            source_type=args.source_type,
            source_id=source_id,
            title=file_path.name,
            tags=normalize_tags(args.tags),
            ingested_by=args.ingested_by,
            source_path=str(file_path),
        )
        upload_chunks(
            client=client,
            collection=args.collection,
            model_name=args.model,
            source_id=source_id,
            chunks=chunks,
            payload_base=payload,
        )
        stored += 1

    print(
        json.dumps(
            {
                "status": "ok",
                "collection": args.collection,
                "scope": args.scope,
                "project": args.project,
                "stored_sources": stored,
                "root": str(target_path),
            },
            indent=2,
        )
    )
    return 0


def command_store_text(args: argparse.Namespace) -> int:
    text = args.text
    if not text and args.text_file:
        text = Path(args.text_file).expanduser().read_text(encoding="utf-8", errors="replace")
    if not text:
        print("Falta --text o --text-file", file=sys.stderr)
        return 2

    client = make_client(Path(args.db_path).expanduser())
    ensure_collection(client, args.collection, args.model)

    source_id = args.source_id or f"{args.project}:{slugify(args.title)}"
    if args.replace_source:
        delete_existing_source(client, args.collection, args.scope, args.project, source_id)

    chunks = chunk_text(text, args.chunk_size, args.chunk_overlap)
    payload = base_payload(
        scope=args.scope,
        project=args.project,
        source_type=args.source_type,
        source_id=source_id,
        title=args.title,
        tags=normalize_tags(args.tags),
        ingested_by=args.ingested_by,
        source_path=None,
    )
    upload_chunks(
        client=client,
        collection=args.collection,
        model_name=args.model,
        source_id=source_id,
        chunks=chunks,
        payload_base=payload,
    )

    print(
        json.dumps(
            {
                "status": "ok",
                "collection": args.collection,
                "scope": args.scope,
                "project": args.project,
                "stored_sources": 1,
                "source_id": source_id,
            },
            indent=2,
        )
    )
    return 0


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    return lowered.strip("-") or "entry"


def command_search(args: argparse.Namespace) -> int:
    client = make_client(Path(args.db_path).expanduser())
    query_filter = build_filter(scope=args.scope, project=args.project, source_id=args.source_id)
    results = client.query_points(
        collection_name=args.collection,
        query=models.Document(text=args.query, model=args.model),
        query_filter=query_filter,
        limit=args.limit,
        with_payload=True,
        score_threshold=args.score_threshold,
    ).points

    if args.json:
        payload = [
            {
                "score": point.score,
                "id": point.id,
                "payload": point.payload,
            }
            for point in results
        ]
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print(f"# Knowledge search — {args.collection}")
    print(f"Query: {args.query}\n")
    if not results:
        print("No se encontraron resultados.")
        return 0

    for index, point in enumerate(results, start=1):
        payload = point.payload or {}
        text = str(payload.get("text", "")).strip().replace("\n", " ")
        if len(text) > 320:
            text = f"{text[:317]}..."
        print(f"## Hit {index} — score {point.score:.4f}")
        print(f"- title: {payload.get('title', '(sin título)')}")
        print(f"- scope/project: {payload.get('scope')} / {payload.get('project')}")
        print(f"- source_type: {payload.get('source_type')}")
        print(f"- source_id: {payload.get('source_id')}")
        if payload.get("source_path"):
            print(f"- source_path: {payload.get('source_path')}")
        print(f"- chunk: {payload.get('chunk_index')} / {payload.get('chunk_count')}")
        if payload.get("tags"):
            print(f"- tags: {', '.join(str(tag) for tag in payload.get('tags', []))}")
        print(f"- excerpt: {text}\n")
    return 0


def command_status(args: argparse.Namespace) -> int:
    client = make_client(Path(args.db_path).expanduser())
    collections = []
    for item in client.get_collections().collections:
        name = item.name
        try:
            count = client.count(collection_name=name).count
        except Exception:  # pragma: no cover - best effort
            count = None
        collections.append({"name": name, "count": count})

    payload = {
        "status": "ok",
        "knowledge_home": str(DEFAULT_HOME),
        "qdrant_local_path": str(args.db_path),
        "default_collection": args.collection,
        "embedding_model": args.model,
        "collections": collections,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Governed Qdrant helpers for the OpenCode knowledge layer")

    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common_options(target: argparse.ArgumentParser) -> None:
        target.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
        target.add_argument("--collection", default=DEFAULT_COLLECTION)
        target.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)

    store_path = subparsers.add_parser("store-path", help="Index one file or all supported files under a directory")
    add_common_options(store_path)
    store_path.add_argument("--path", required=True)
    store_path.add_argument("--scope", default=DEFAULT_SCOPE)
    store_path.add_argument("--project", default=DEFAULT_PROJECT)
    store_path.add_argument("--source-type", default="document")
    store_path.add_argument("--tags")
    store_path.add_argument("--chunk-size", type=int, default=1400)
    store_path.add_argument("--chunk-overlap", type=int, default=200)
    store_path.add_argument("--ingested-by", default="knowledge-curator")
    store_path.add_argument("--no-replace-source", action="store_false", dest="replace_source")
    store_path.set_defaults(func=command_store_path, replace_source=True)

    store_text = subparsers.add_parser("store-text", help="Index one explicit text payload")
    add_common_options(store_text)
    store_text.add_argument("--title", required=True)
    store_text.add_argument("--text")
    store_text.add_argument("--text-file")
    store_text.add_argument("--scope", default=DEFAULT_SCOPE)
    store_text.add_argument("--project", default=DEFAULT_PROJECT)
    store_text.add_argument("--source-type", default="note")
    store_text.add_argument("--source-id")
    store_text.add_argument("--tags")
    store_text.add_argument("--chunk-size", type=int, default=1400)
    store_text.add_argument("--chunk-overlap", type=int, default=200)
    store_text.add_argument("--ingested-by", default="knowledge-curator")
    store_text.add_argument("--no-replace-source", action="store_false", dest="replace_source")
    store_text.set_defaults(func=command_store_text, replace_source=True)

    search = subparsers.add_parser("search", help="Semantic search over the configured collection")
    add_common_options(search)
    search.add_argument("--query", required=True)
    search.add_argument("--scope")
    search.add_argument("--project")
    search.add_argument("--source-id")
    search.add_argument("--limit", type=int, default=5)
    search.add_argument("--score-threshold", type=float)
    search.add_argument("--json", action="store_true")
    search.set_defaults(func=command_search)

    status = subparsers.add_parser("status", help="Show local knowledge layer readiness")
    add_common_options(status)
    status.set_defaults(func=command_status)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

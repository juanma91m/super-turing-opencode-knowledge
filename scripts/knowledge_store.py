#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
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

try:
    from fastembed import TextEmbedding
except ImportError:  # pragma: no cover - optional dependency at runtime
    TextEmbedding = None


DEFAULT_HOME = Path(
    os.environ.get("OPENCODE_KNOWLEDGE_HOME", "~/.local/share/super-turing-opencode-knowledge")
).expanduser()
DEFAULT_DB_PATH = Path(os.environ.get("QDRANT_LOCAL_PATH", str(DEFAULT_HOME / "qdrant"))).expanduser()
DEFAULT_COLLECTION = os.environ.get("OPENCODE_KNOWLEDGE_COLLECTION", "global-opencode-knowledge")
DEFAULT_EMBEDDING_BACKEND = os.environ.get("OPENCODE_KNOWLEDGE_EMBEDDING_BACKEND", "fastembed")
DEFAULT_EMBEDDING_MODEL = os.environ.get(
    "OPENCODE_KNOWLEDGE_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
DEFAULT_OLLAMA_BASE_URL = os.environ.get("OPENCODE_KNOWLEDGE_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
DEFAULT_OLLAMA_BATCH_SIZE = max(int(os.environ.get("OPENCODE_KNOWLEDGE_OLLAMA_BATCH_SIZE", "16")), 1)
DEFAULT_OLLAMA_TIMEOUT_SECONDS = max(
    int(os.environ.get("OPENCODE_KNOWLEDGE_OLLAMA_TIMEOUT_SECONDS", "300")), 1
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


def normalize_embedding_backend(raw: str) -> str:
    backend = raw.strip().lower()
    if backend not in {"fastembed", "ollama"}:
        raise RuntimeError(
            f"Embedding backend no soportado: {raw}. Valores válidos: fastembed | ollama"
        )
    return backend


class FastEmbedder:
    def __init__(self, model_name: str):
        if TextEmbedding is None:
            raise RuntimeError(
                "fastembed no está instalado en el runtime actual. Reinstalá Qdrant con install-knowledge-qdrant.sh"
            )
        self.model_name = model_name
        self._model = TextEmbedding(model_name=model_name)
        self._size: int | None = None

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = []
        for vector in self._model.embed(list(texts)):
            values = vector.tolist() if hasattr(vector, "tolist") else list(vector)
            vectors.append([float(item) for item in values])
        if vectors and self._size is None:
            self._size = len(vectors[0])
        return vectors

    def vector_size(self) -> int:
        if self._size is not None:
            return self._size
        probe = self.embed_texts(["knowledge-dimension-probe"])
        if not probe:
            raise RuntimeError("fastembed no devolvió embeddings para calcular la dimensión")
        return len(probe[0])


class OllamaEmbedder:
    def __init__(self, model_name: str, base_url: str):
        normalized = base_url.rstrip("/")
        if normalized.endswith("/v1"):
            normalized = normalized[:-3]
        self.model_name = model_name
        self.base_url = normalized
        self.endpoint = f"{normalized}/api/embed"
        self.batch_size = DEFAULT_OLLAMA_BATCH_SIZE
        self.timeout_seconds = DEFAULT_OLLAMA_TIMEOUT_SECONDS
        self._size: int | None = None

    def _embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        payload = json.dumps({"model": self.model_name, "input": list(texts)}).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.load(response)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            raise RuntimeError(
                f"Ollama respondió {exc.code} al pedir embeddings en {self.endpoint}: {detail or exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"No se pudo conectar a Ollama en {self.endpoint}: {exc.reason or exc}"
            ) from exc
        except TimeoutError as exc:
            raise RuntimeError(
                f"Ollama agotó el timeout ({self.timeout_seconds}s) al pedir embeddings en {self.endpoint}. Probá con chunks más chicos o aumentando OPENCODE_KNOWLEDGE_OLLAMA_TIMEOUT_SECONDS."
            ) from exc

        embeddings = data.get("embeddings") or []
        if not embeddings or not isinstance(embeddings[0], list):
            raise RuntimeError("Ollama no devolvió un payload de embeddings válido")

        return [[float(item) for item in vector] for vector in embeddings]

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            embedded = self._embed_batch(batch)
            if len(embedded) != len(batch):
                raise RuntimeError(
                    "Ollama devolvió una cantidad inesperada de embeddings para el batch solicitado"
                )
            vectors.extend(embedded)
        if vectors and self._size is None:
            self._size = len(vectors[0])
        return vectors

    def vector_size(self) -> int:
        if self._size is not None:
            return self._size
        probe = self.embed_texts(["knowledge-dimension-probe"])
        if not probe:
            raise RuntimeError("Ollama no devolvió embeddings para calcular la dimensión")
        return len(probe[0])


def make_embedder(backend: str, model_name: str, ollama_base_url: str):
    backend_name = normalize_embedding_backend(backend)
    if backend_name == "ollama":
        return OllamaEmbedder(model_name, ollama_base_url)
    return FastEmbedder(model_name)


def collection_vector_size(client: QdrantClient, collection: str) -> int | None:
    info = client.get_collection(collection)
    vectors = info.config.params.vectors
    size = getattr(vectors, "size", None)
    if size is not None:
        return int(size)
    if isinstance(vectors, dict) and vectors:
        first = next(iter(vectors.values()))
        nested_size = getattr(first, "size", None)
        if nested_size is not None:
            return int(nested_size)
    return None


def ensure_collection(client: QdrantClient, collection: str, embedder) -> None:
    collections = {item.name for item in client.get_collections().collections}
    expected_size = embedder.vector_size()
    if collection in collections:
        current_size = collection_vector_size(client, collection)
        if current_size is not None and current_size != expected_size:
            raise RuntimeError(
                f"La colección {collection} ya existe con dimensión {current_size}, pero el backend/modelo actual produce {expected_size}. Reindexá o recreá la colección antes de mezclar embeddings."
            )
        return

    client.create_collection(
        collection_name=collection,
        vectors_config=models.VectorParams(size=expected_size, distance=models.Distance.COSINE),
    )


def ensure_existing_collection(client: QdrantClient, collection: str, embedder) -> None:
    collections = {item.name for item in client.get_collections().collections}
    if collection not in collections:
        raise RuntimeError(f"La colección {collection} no existe todavía")
    current_size = collection_vector_size(client, collection)
    expected_size = embedder.vector_size()
    if current_size is not None and current_size != expected_size:
        raise RuntimeError(
            f"La colección {collection} tiene dimensión {current_size}, pero el backend/modelo actual produce {expected_size}. Reindexá o recreá la colección antes de consultar."
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


def resolve_relative_path(file_path: Path, *, root_dir: Path, source_root: Path | None) -> str:
    base = source_root or root_dir
    try:
        relative = file_path.relative_to(base)
    except ValueError:
        relative = file_path.relative_to(root_dir) if file_path.parent == root_dir else Path(file_path.name)
    return str(relative).replace(os.sep, "/")


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
    embedder,
    source_id: str,
    chunks: Sequence[str],
    payload_base: dict[str, object],
) -> None:
    if not chunks:
        raise RuntimeError("No hay chunks para subir a la colección")

    payloads = []
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
        ids.append(stable_id(collection, source_id, chunk_index))

    vectors = embedder.embed_texts(chunks)
    if len(vectors) != len(chunks):
        raise RuntimeError("La cantidad de embeddings generados no coincide con la cantidad de chunks")
    client.upload_collection(collection_name=collection, vectors=vectors, payload=payloads, ids=ids)


def command_store_path(args: argparse.Namespace) -> int:
    target_path = Path(args.path).expanduser().resolve()
    if not target_path.exists():
        print(f"Path not found: {target_path}", file=sys.stderr)
        return 2

    source_root = Path(args.source_root).expanduser().resolve() if args.source_root else None
    if source_root is not None and not source_root.exists():
        print(f"Source root not found: {source_root}", file=sys.stderr)
        return 2

    client = make_client(Path(args.db_path).expanduser())
    embedder = make_embedder(args.embedding_backend, args.model, args.ollama_base_url)
    ensure_collection(client, args.collection, embedder)

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
        relative_str = resolve_relative_path(file_path, root_dir=root_dir, source_root=source_root)
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
            embedder=embedder,
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
    embedder = make_embedder(args.embedding_backend, args.model, args.ollama_base_url)
    ensure_collection(client, args.collection, embedder)

    source_id = args.source_id or f"{args.project}:{slugify(args.title)}"
    if args.replace_source:
        delete_existing_source(client, args.collection, args.scope, args.project, source_id)

    chunks = chunk_text(text, args.chunk_size, args.chunk_overlap)
    if not chunks:
        print("El texto provisto está vacío o contiene solo whitespace", file=sys.stderr)
        return 2

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
        embedder=embedder,
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
    embedder = make_embedder(args.embedding_backend, args.model, args.ollama_base_url)
    ensure_existing_collection(client, args.collection, embedder)
    query_filter = build_filter(scope=args.scope, project=args.project, source_id=args.source_id)
    query_vector = embedder.embed_texts([args.query])[0]
    results = client.query_points(
        collection_name=args.collection,
        query=query_vector,
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
    embedder = make_embedder(args.embedding_backend, args.model, args.ollama_base_url)
    vector_size = embedder.vector_size()
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
        "embedding_backend": normalize_embedding_backend(args.embedding_backend),
        "embedding_model": args.model,
        "embedding_vector_size": vector_size,
        "collections": collections,
    }
    if normalize_embedding_backend(args.embedding_backend) == "ollama":
        payload["ollama_base_url"] = args.ollama_base_url.rstrip("/")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Governed Qdrant helpers for the OpenCode knowledge layer")

    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common_options(target: argparse.ArgumentParser) -> None:
        target.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
        target.add_argument("--collection", default=DEFAULT_COLLECTION)
        target.add_argument("--embedding-backend", default=DEFAULT_EMBEDDING_BACKEND)
        target.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
        target.add_argument("--ollama-base-url", default=DEFAULT_OLLAMA_BASE_URL)

    store_path = subparsers.add_parser("store-path", help="Index one file or all supported files under a directory")
    add_common_options(store_path)
    store_path.add_argument("--path", required=True)
    store_path.add_argument("--source-root")
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
    try:
        return args.func(args)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

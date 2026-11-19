"""Characterize logical reads with fake dependencies, never a real corpus/model.

These tests document the existing boundary; they do not certify physical
read-only access. See v2/READ-ONLY-AUDIT.md before composing the V2 pilot.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]


def load_store():
    qdrant = types.ModuleType("qdrant_client")
    qdrant.QdrantClient = Mock(name="QdrantClient")
    qdrant.models = Mock(name="models")
    fastembed = types.ModuleType("fastembed")
    fastembed.TextEmbedding = Mock(name="TextEmbedding")
    spec = importlib.util.spec_from_file_location("fixture_knowledge_store", ROOT / "scripts/knowledge_store.py")
    module = importlib.util.module_from_spec(spec)
    # No installed Qdrant/embedding modules or machine-local environment needed.
    with patch.dict(sys.modules, {"qdrant_client": qdrant, "fastembed": fastembed}), patch.dict(os.environ, {}, clear=True):
        spec.loader.exec_module(module)
    return module


class QdrantReadBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.store = load_store()

    def test_client_creates_missing_storage_directory_even_for_read_callers(self):
        with tempfile.TemporaryDirectory(prefix="qdrant-read-boundary-") as temp:
            target = Path(temp) / "not-present" / "qdrant"
            self.assertFalse(target.exists())
            self.store.make_client(target)
            self.assertTrue(target.is_dir())
            self.store.QdrantClient.assert_called_once_with(path=str(target))

    def test_status_initializes_embedder_and_probes_its_dimension(self):
        args = self.store.build_parser().parse_args(["status"])
        client = Mock()
        client.get_collections.return_value.collections = []
        embedder = Mock()
        embedder.vector_size.return_value = 384
        output = io.StringIO()
        with patch.object(self.store, "make_client", return_value=client), patch.object(
            self.store, "make_embedder", return_value=embedder
        ) as make_embedder, contextlib.redirect_stdout(output):
            self.assertEqual(self.store.command_status(args), 0)
        make_embedder.assert_called_once_with(args.embedding_backend, args.model, args.ollama_base_url)
        embedder.vector_size.assert_called_once_with()
        self.assertEqual(json.loads(output.getvalue())["embedding_vector_size"], 384)

    def test_status_can_fail_on_embedding_after_opening_storage(self):
        args = self.store.build_parser().parse_args(["status"])
        with patch.object(self.store, "make_client") as make_client, patch.object(
            self.store, "make_embedder", side_effect=RuntimeError("fixture model unavailable")
        ), self.assertRaisesRegex(RuntimeError, "fixture model unavailable"):
            self.store.command_status(args)
        make_client.assert_called_once()

    def test_search_without_filters_does_not_inherit_write_defaults(self):
        args = self.store.build_parser().parse_args(["search", "--query", "fixture"])
        self.assertIsNone(args.scope)
        self.assertIsNone(args.project)
        self.assertIsNone(args.source_id)
        self.assertIsNone(self.store.build_filter(args.scope, args.project, args.source_id))

    def test_explicit_filters_preserve_scope_project_and_source(self):
        models = self.store.models
        result = self.store.build_filter("project", "fixture-project", "fixture-source")
        self.assertEqual([entry.kwargs["key"] for entry in models.FieldCondition.call_args_list],
                         ["scope", "project", "source_id"])
        self.assertEqual([entry.kwargs["value"] for entry in models.MatchValue.call_args_list],
                         ["project", "fixture-project", "fixture-source"])
        self.assertIs(result, models.Filter.return_value)

    def test_missing_collection_fails_without_creating_one_or_querying(self):
        args = self.store.build_parser().parse_args(["search", "--query", "fixture"])
        client, embedder = Mock(), Mock()
        client.get_collections.return_value.collections = []
        with patch.object(self.store, "make_client", return_value=client), patch.object(
            self.store, "make_embedder", return_value=embedder
        ), self.assertRaisesRegex(RuntimeError, "no existe todavía"):
            self.store.command_search(args)
        client.create_collection.assert_not_called()
        client.query_points.assert_not_called()
        embedder.vector_size.assert_not_called()
        embedder.embed_texts.assert_not_called()

    def test_bounded_search_uses_existing_collection_and_explicit_filters(self):
        args = self.store.build_parser().parse_args([
            "search", "--query", "fixture", "--collection", "fixture-collection",
            "--scope", "project", "--project", "fixture-project", "--limit", "3", "--json",
        ])
        # Deliberately no create/upsert/delete methods on the client contract.
        client = Mock(spec_set=["get_collections", "get_collection", "query_points"])
        client.get_collections.return_value.collections = [types.SimpleNamespace(name=args.collection)]
        client.get_collection.return_value.config.params.vectors.size = 384
        client.query_points.return_value.points = []
        embedder = Mock()
        embedder.vector_size.return_value = 384
        embedder.embed_texts.return_value = [[0.1] * 384]
        output = io.StringIO()
        with patch.object(self.store, "make_client", return_value=client), patch.object(
            self.store, "make_embedder", return_value=embedder
        ), contextlib.redirect_stdout(output):
            self.assertEqual(self.store.command_search(args), 0)
        embedder.embed_texts.assert_called_once_with(["fixture"])
        query = client.query_points.call_args.kwargs
        self.assertEqual(query["collection_name"], "fixture-collection")
        self.assertEqual(query["limit"], 3)
        self.assertIs(query["query_filter"], self.store.models.Filter.return_value)
        self.assertEqual(json.loads(output.getvalue()), [])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = BACKEND_DIR / "scripts"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from embed_processed_chunks import (  # noqa: E402
    DATASETS,
    EMBEDDING_DIMENSIONS,
    deterministic_mock_embedding,
    load_dataset,
)
from app.services.embeddings import (  # noqa: E402
    FPTEmbeddings,
    GLMEmbeddings,
    LocalSentenceTransformerEmbeddings,
)


class ProcessedChunkEmbeddingTests(unittest.TestCase):
    def test_department_loaders_preserve_normalized_metadata(self) -> None:
        expected_counts = {
            "collateral": 70,
            "compliance": 176,
            "credit": 112,
            "customer_relationship": 85,
        }

        for department, expected_count in expected_counts.items():
            with self.subTest(department=department):
                records = load_dataset(DATASETS[department])
                self.assertEqual(len(records), expected_count)
                self.assertTrue(all(record.content.strip() for record in records))
                self.assertTrue(
                    all(
                        record.metadata["department"] == department.upper()
                        for record in records
                    )
                )
                self.assertTrue(
                    all(
                        len(record.metadata["content_sha256"]) == 64
                        for record in records
                    )
                )
                self.assertTrue(
                    all(record.metadata.get("chunk_id") for record in records)
                )

    def test_external_institution_chunks_require_explicit_approval(self) -> None:
        records = load_dataset(DATASETS["credit"])
        blocked = [
            record for record in records if record.metadata.get("indexing_blocked")
        ]

        self.assertEqual(len(blocked), 3)
        for record in blocked:
            self.assertIn(
                "EXTERNAL_INSTITUTION_REFERENCE",
                record.metadata["indexing_blocked_codes"],
            )
            self.assertTrue(record.metadata["source_warnings"])

    def test_mock_embedding_is_stable_normalized_and_schema_compatible(self) -> None:
        first = deterministic_mock_embedding("kiểm thử embedding ổn định")
        second = deterministic_mock_embedding("kiểm thử embedding ổn định")

        self.assertEqual(first, second)
        self.assertEqual(len(first), EMBEDDING_DIMENSIONS)
        self.assertEqual(EMBEDDING_DIMENSIONS, 1024)
        norm = math.sqrt(sum(value * value for value in first))
        self.assertAlmostEqual(norm, 1.0, places=12)

    def test_local_adapter_normalizes_and_batches_without_api(self) -> None:
        class FakeArray(list):
            def tolist(self):
                return list(self)

        class FakeModel:
            def __init__(self) -> None:
                self.options = None

            def encode(self, texts, **options):
                self.options = options
                return FakeArray([[0.1, 0.2, 0.3] for _ in texts])

        adapter = LocalSentenceTransformerEmbeddings(
            model_name="test-model", device="cpu", batch_size=2
        )
        fake_model = FakeModel()
        adapter._model = fake_model

        vectors = adapter.embed_documents(["văn bản một", "văn bản hai"])

        self.assertEqual(vectors, [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]])
        self.assertEqual(fake_model.options["batch_size"], 2)
        self.assertTrue(fake_model.options["normalize_embeddings"])
        self.assertFalse(fake_model.options["show_progress_bar"])

    def test_glm_adapter_requests_and_validates_configured_dimensions(self) -> None:
        from unittest.mock import Mock, patch

        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "data": [
                {"index": 1, "embedding": [0.2] * 1536},
                {"index": 0, "embedding": [0.1] * 1536},
            ]
        }
        adapter = GLMEmbeddings(
            api_key="test-key",
            dimensions=1536,
            batch_size=64,
        )

        with patch("app.services.embeddings.httpx.post", return_value=response) as post:
            vectors = adapter.embed_documents(["mot", "hai"])

        self.assertEqual(vectors[0][0], 0.1)
        self.assertEqual(vectors[1][0], 0.2)
        self.assertEqual(len(vectors[0]), 1536)
        self.assertEqual(post.call_args.kwargs["json"]["dimensions"], 1536)
        self.assertNotIn("test-key", str(post.call_args.kwargs["json"]))

    def test_fpt_adapter_requests_and_validates_1024_dimensions(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import Mock

        response = SimpleNamespace(
            data=[
                SimpleNamespace(index=1, embedding=[0.2] * 1024),
                SimpleNamespace(index=0, embedding=[0.1] * 1024),
            ]
        )
        client = Mock()
        client.embeddings.create.return_value = response
        adapter = FPTEmbeddings(
            api_key="test-key",
            model_name="Vietnamese_Embedding",
            dimensions=1024,
            batch_size=16,
        )
        adapter._client = client

        vectors = adapter.embed_documents(["mot", "hai"])

        self.assertEqual(vectors[0][0], 0.1)
        self.assertEqual(vectors[1][0], 0.2)
        self.assertEqual(len(vectors[0]), 1024)
        client.embeddings.create.assert_called_once_with(
            model="Vietnamese_Embedding",
            input=["mot", "hai"],
        )
        self.assertNotIn("test-key", str(client.embeddings.create.call_args))


if __name__ == "__main__":
    unittest.main()

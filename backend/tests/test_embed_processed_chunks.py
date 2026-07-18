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
    EMBEDDING_DIMENSIONS,
    deterministic_mock_embedding,
)
from ingest_income_policy_dataset import (  # noqa: E402
    build_corpus,
    deterministic_embedding,
    read_source,
)
from app.services.rag import PolicyQuery, validate_policy_metadata  # noqa: E402
from app.services.embeddings import (  # noqa: E402
    FPTEmbeddings,
    GLMEmbeddings,
    LocalSentenceTransformerEmbeddings,
)


class ProcessedChunkEmbeddingTests(unittest.TestCase):
    def test_current_dataset_quarantines_unapproved_and_case_sources(self) -> None:
        corpus = build_corpus()

        self.assertEqual(corpus["quality_report"]["chunk_count"], 0)
        self.assertEqual(corpus["quality_report"]["source_count"], 15)
        codes = {item["code"] for item in corpus["quarantine"]}
        self.assertIn("APPROVAL_STATUS_NOT_APPROVED", codes)
        self.assertIn("CASE_EVIDENCE_NOT_GLOBAL_POLICY", codes)

    def test_reference_markdown_files_have_normalized_front_matter(self) -> None:
        policy_notes = read_source(
            Path("dataset/Policy_agent/policy_agent_shb_web_government_sources_notes.md")
        )
        income_notes = read_source(
            Path("dataset/Income_analysis_agent/shb_government_web_sources_income_analysis_notes.md")
        )

        self.assertEqual(policy_notes.metadata["dataset_type"], "REFERENCE_NOTE")
        self.assertEqual(policy_notes.metadata["approval_status"], "PENDING_REVIEW")
        self.assertEqual(income_notes.metadata["target_agent"], "INCOME_ANALYSIS_AGENT")
        self.assertEqual(income_notes.metadata["production_use"], "prohibited")

    def test_demo_policy_chunks_have_complete_scoped_metadata(self) -> None:
        corpus = build_corpus(include_demo=True)
        chunks = corpus["chunks"]

        self.assertEqual(len(chunks), 6)
        self.assertTrue(all(chunk["chunk_type"] == "POLICY_RULE" for chunk in chunks))
        for chunk in chunks:
            metadata = chunk["metadata"]
            self.assertEqual(metadata["domain"], "INCOME_VERIFICATION")
            self.assertEqual(metadata["product"], "UNSECURED_PERSONAL_LOAN")
            self.assertEqual(metadata["approval_status"], "APPROVED_FOR_DEMO")
            self.assertEqual(metadata["indexing_scope"], "DEMO_ONLY")
            self.assertEqual(len(metadata["content_sha256"]), 64)
            self.assertNotIn("case_id", metadata)

    def test_policy_query_scope_cannot_be_relaxed(self) -> None:
        query = PolicyQuery(query_text="kỳ sao kê", as_of_date="2026-07-18")
        query.validate_scope()

        query.product = "SECURED_LOAN"
        with self.assertRaises(ValueError):
            query.validate_scope()

    def test_global_index_metadata_rejects_demo_and_case_chunks(self) -> None:
        demo_chunk = build_corpus(include_demo=True)["chunks"][0]["metadata"]
        with self.assertRaises(ValueError):
            validate_policy_metadata(demo_chunk)

        case_metadata = dict(demo_chunk)
        case_metadata["approval_status"] = "APPROVED"
        case_metadata["case_id"] = "SYN-IV-001"
        with self.assertRaises(ValueError):
            validate_policy_metadata(case_metadata)

    def test_demo_embedding_is_stable_normalized_and_512_dimensions(self) -> None:
        first = deterministic_embedding("kiểm tra embedding ổn định")
        second = deterministic_embedding("kiểm tra embedding ổn định")

        self.assertEqual(first, second)
        self.assertEqual(len(first), EMBEDDING_DIMENSIONS)
        self.assertEqual(EMBEDDING_DIMENSIONS, 512)
        norm = math.sqrt(sum(value * value for value in first))
        self.assertAlmostEqual(norm, 1.0, places=12)

    def test_mock_embedding_is_stable_normalized_and_schema_compatible(self) -> None:
        first = deterministic_mock_embedding("kiểm thử embedding ổn định")
        second = deterministic_mock_embedding("kiểm thử embedding ổn định")

        self.assertEqual(first, second)
        self.assertEqual(len(first), EMBEDDING_DIMENSIONS)
        self.assertEqual(EMBEDDING_DIMENSIONS, 512)
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

    def test_fpt_adapter_requests_and_validates_512_dimensions(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import Mock

        response = SimpleNamespace(
            data=[
                SimpleNamespace(index=1, embedding=[0.2] * 512),
                SimpleNamespace(index=0, embedding=[0.1] * 512),
            ]
        )
        client = Mock()
        client.embeddings.create.return_value = response
        adapter = FPTEmbeddings(
            api_key="test-key",
            model_name="Vietnamese_Embedding",
            dimensions=512,
            batch_size=16,
        )
        adapter._client = client

        vectors = adapter.embed_documents(["mot", "hai"])

        self.assertEqual(vectors[0][0], 0.1)
        self.assertEqual(vectors[1][0], 0.2)
        self.assertEqual(len(vectors[0]), 512)
        client.embeddings.create.assert_called_once_with(
            model="Vietnamese_Embedding",
            input=["mot", "hai"],
            dimensions=512,
        )
        self.assertNotIn("test-key", str(client.embeddings.create.call_args))


if __name__ == "__main__":
    unittest.main()

"""Text embedding adapters shared by RAG indexing and querying."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import httpx
from langchain_core.embeddings import Embeddings

from app.config import get_settings


class LocalSentenceTransformerEmbeddings(Embeddings):
    """Run a Sentence Transformers embedding model locally without an API key."""

    def __init__(
        self,
        model_name: str,
        device: str = "cpu",
        batch_size: int = 4,
        cache_dir: str | None = None,
        trust_remote_code: bool = False,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self.cache_dir = cache_dir
        self.trust_remote_code = trust_remote_code
        self._model: Any | None = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self.model_name,
                device=self.device,
                cache_folder=self.cache_dir,
                trust_remote_code=self.trust_remote_code,
            )
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._get_model().encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class GLMEmbeddings(Embeddings):
    """Call Zhipu GLM Embedding-3 through its OpenAI-style HTTP endpoint."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "embedding-3",
        dimensions: int = 1536,
        batch_size: int = 64,
        base_url: str = "https://open.bigmodel.cn/api/paas/v4",
        timeout_seconds: float = 60.0,
    ) -> None:
        if not api_key.strip():
            raise RuntimeError("GLM_API_KEY is required when EMBEDDING_PROVIDER=glm.")
        if dimensions < 1:
            raise ValueError("Embedding dimensions must be positive.")
        if not 1 <= batch_size <= 64:
            raise ValueError("GLM embedding batch size must be between 1 and 64.")

        self.api_key = api_key
        self.model_name = model_name
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.endpoint = f"{base_url.rstrip('/')}/embeddings"
        self.timeout_seconds = timeout_seconds

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = httpx.post(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model_name,
                "input": texts,
                "dimensions": self.dimensions,
            },
            timeout=self.timeout_seconds,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            message = "unknown API error"
            try:
                message = str(response.json().get("error", {}).get("message", message))
            except (TypeError, ValueError):
                pass
            raise RuntimeError(
                f"GLM embedding request failed ({response.status_code}): {message}"
            ) from exc

        payload = response.json()
        data = payload.get("data")
        if not isinstance(data, list) or len(data) != len(texts):
            raise RuntimeError(
                "GLM embedding response does not match the submitted batch size."
            )

        ordered = sorted(data, key=lambda item: int(item["index"]))
        vectors = [item["embedding"] for item in ordered]
        for index, vector in enumerate(vectors):
            if not isinstance(vector, list) or len(vector) != self.dimensions:
                actual = len(vector) if isinstance(vector, list) else "invalid"
                raise RuntimeError(
                    f"GLM embedding {index} has {actual} dimensions; "
                    f"expected {self.dimensions}."
                )
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            vectors.extend(self._embed_batch(texts[start : start + self.batch_size]))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class FPTEmbeddings(Embeddings):
    """Call FPT AI Marketplace through its OpenAI-compatible SDK."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "Vietnamese_Embedding",
        dimensions: int = 512,
        batch_size: int = 16,
        base_url: str = "https://mkp-api.fptcloud.com",
        timeout_seconds: float = 60.0,
    ) -> None:
        if not api_key.strip():
            raise RuntimeError("FPT_API_KEY is required when EMBEDDING_PROVIDER=fpt.")
        if dimensions < 1:
            raise ValueError("Embedding dimensions must be positive.")
        if batch_size < 1:
            raise ValueError("FPT embedding batch size must be at least 1.")
        self.api_key = api_key
        self.model_name = model_name
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client: Any | None = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout_seconds,
            )
        return self._client

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        try:
            response = self._get_client().embeddings.create(
                model=self.model_name,
                input=texts,
                dimensions=self.dimensions,
            )
        except Exception as exc:
            status_code = getattr(exc, "status_code", "unknown")
            raise RuntimeError(
                f"FPT embedding request failed ({status_code}): {exc}"
            ) from exc

        data = response.data
        if not isinstance(data, list) or len(data) != len(texts):
            raise RuntimeError(
                "FPT embedding response does not match the submitted batch size."
            )
        ordered = sorted(data, key=lambda item: int(item.index))
        vectors = [item.embedding for item in ordered]
        for index, vector in enumerate(vectors):
            if not isinstance(vector, list) or len(vector) != self.dimensions:
                actual = len(vector) if isinstance(vector, list) else "invalid"
                raise RuntimeError(
                    f"FPT embedding {index} has {actual} dimensions; "
                    f"expected {self.dimensions}."
                )
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            vectors.extend(self._embed_batch(texts[start : start + self.batch_size]))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


@lru_cache(maxsize=1)
def get_local_embeddings() -> LocalSentenceTransformerEmbeddings:
    settings = get_settings()
    if settings.embedding_provider != "local":
        raise RuntimeError(
            f"Unsupported EMBEDDING_PROVIDER={settings.embedding_provider!r}; "
            "this project is configured for local Python embeddings."
        )
    return LocalSentenceTransformerEmbeddings(
        model_name=settings.embedding_model,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
        cache_dir=settings.embedding_cache_dir,
        trust_remote_code=settings.embedding_trust_remote_code,
    )


@lru_cache(maxsize=1)
def get_glm_embeddings() -> GLMEmbeddings:
    settings = get_settings()
    if settings.embedding_provider != "glm":
        raise RuntimeError(
            f"Unsupported EMBEDDING_PROVIDER={settings.embedding_provider!r}; "
            "expected 'glm'."
        )
    return GLMEmbeddings(
        api_key=settings.glm_api_key,
        model_name=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        batch_size=settings.embedding_batch_size,
        base_url=settings.glm_base_url,
        timeout_seconds=settings.glm_request_timeout_seconds,
    )


@lru_cache(maxsize=1)
def get_fpt_embeddings() -> FPTEmbeddings:
    settings = get_settings()
    if settings.embedding_provider != "fpt":
        raise RuntimeError(
            f"Unsupported EMBEDDING_PROVIDER={settings.embedding_provider!r}; "
            "expected 'fpt'."
        )
    return FPTEmbeddings(
        api_key=settings.fpt_api_key,
        model_name=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        batch_size=settings.embedding_batch_size,
        base_url=settings.fpt_base_url,
        timeout_seconds=settings.fpt_request_timeout_seconds,
    )


def get_configured_embeddings() -> Embeddings:
    settings = get_settings()
    if settings.embedding_provider == "fpt":
        return get_fpt_embeddings()
    if settings.embedding_provider == "glm":
        return get_glm_embeddings()
    if settings.embedding_provider == "local":
        return get_local_embeddings()
    raise RuntimeError(
        f"Unsupported EMBEDDING_PROVIDER={settings.embedding_provider!r}; "
        "expected 'fpt', 'glm', or 'local'."
    )

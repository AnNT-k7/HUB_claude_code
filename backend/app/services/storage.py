from __future__ import annotations

import io
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from threading import Lock
from typing import BinaryIO, Protocol
from urllib.parse import urlsplit

from minio import Minio

from app.config import Settings, get_settings


_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class StoredObject:
    bucket: str
    object_key: str
    size_bytes: int
    content_type: str


class ObjectStorage(Protocol):
    def ensure_buckets(self) -> None: ...

    def put(
        self,
        *,
        bucket: str,
        object_key: str,
        data: BinaryIO,
        size_bytes: int,
        content_type: str,
    ) -> StoredObject: ...

    def get(self, *, bucket: str, object_key: str) -> bytes: ...

    def presigned_get_url(
        self, *, bucket: str, object_key: str, expires: timedelta
    ) -> str: ...


def safe_filename(filename: str) -> str:
    """Return a storage-safe basename without accepting caller-controlled paths."""

    basename = Path(filename.replace("\\", "/")).name.strip()
    sanitized = _SAFE_FILENAME.sub("-", basename).strip(".-")
    return sanitized[:180] or "document"


def case_document_key(case_id: str, document_id: str, filename: str) -> str:
    return f"cases/{case_id}/{document_id}/{safe_filename(filename)}"


def policy_document_key(
    agent_key: str, document_id: str, filename: str
) -> str:
    return f"policies/{agent_key}/{document_id}/{safe_filename(filename)}"


class MinioObjectStorage:
    def __init__(self, settings: Settings) -> None:
        parsed = urlsplit(settings.minio_url)
        endpoint = parsed.netloc or parsed.path
        secure = settings.minio_secure or parsed.scheme == "https"
        self._client = Minio(
            endpoint,
            access_key=settings.minio_root_user,
            secret_key=settings.minio_root_password,
            secure=secure,
        )
        self._buckets = (
            settings.minio_case_bucket,
            settings.minio_policy_bucket,
        )

    def ensure_buckets(self) -> None:
        for bucket in self._buckets:
            if not self._client.bucket_exists(bucket):
                self._client.make_bucket(bucket)

    def put(
        self,
        *,
        bucket: str,
        object_key: str,
        data: BinaryIO,
        size_bytes: int,
        content_type: str,
    ) -> StoredObject:
        self._client.put_object(
            bucket,
            object_key,
            data,
            length=size_bytes,
            content_type=content_type,
        )
        return StoredObject(bucket, object_key, size_bytes, content_type)

    def get(self, *, bucket: str, object_key: str) -> bytes:
        response = self._client.get_object(bucket, object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def presigned_get_url(
        self, *, bucket: str, object_key: str, expires: timedelta
    ) -> str:
        return self._client.presigned_get_object(
            bucket,
            object_key,
            expires=expires,
        )


class InMemoryObjectStorage:
    """Deterministic storage adapter for unit tests and local service tests."""

    def __init__(self) -> None:
        self._objects: dict[tuple[str, str], tuple[bytes, str]] = {}
        self._lock = Lock()

    def ensure_buckets(self) -> None:
        return None

    def put(
        self,
        *,
        bucket: str,
        object_key: str,
        data: BinaryIO,
        size_bytes: int,
        content_type: str,
    ) -> StoredObject:
        payload = data.read(size_bytes + 1)
        if len(payload) != size_bytes:
            raise ValueError("stream length does not match declared object size")
        with self._lock:
            self._objects[(bucket, object_key)] = (payload, content_type)
        return StoredObject(bucket, object_key, size_bytes, content_type)

    def get(self, *, bucket: str, object_key: str) -> bytes:
        with self._lock:
            try:
                return self._objects[(bucket, object_key)][0]
            except KeyError as exc:
                raise FileNotFoundError(object_key) from exc

    def presigned_get_url(
        self, *, bucket: str, object_key: str, expires: timedelta
    ) -> str:
        del expires
        return f"memory://{bucket}/{object_key}"

    def iter_objects(self) -> Iterator[StoredObject]:
        with self._lock:
            for (bucket, object_key), (payload, content_type) in self._objects.items():
                yield StoredObject(bucket, object_key, len(payload), content_type)

    def put_bytes(
        self,
        *,
        bucket: str,
        object_key: str,
        payload: bytes,
        content_type: str,
    ) -> StoredObject:
        return self.put(
            bucket=bucket,
            object_key=object_key,
            data=io.BytesIO(payload),
            size_bytes=len(payload),
            content_type=content_type,
        )


def create_object_storage(settings: Settings | None = None) -> ObjectStorage:
    return MinioObjectStorage(settings or get_settings())

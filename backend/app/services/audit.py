from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import Enum
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import AuditLog, AuditOutcome
from app.middleware import get_correlation_id


_SENSITIVE_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "password",
    "secret",
    "token",
}


def _safe_value(value: object, depth: int = 0) -> object:
    if depth > 6:
        return "[MAX_DEPTH]"
    if isinstance(value, BaseModel):
        return _safe_value(value.model_dump(mode="json"), depth + 1)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Mapping):
        sanitized: dict[str, object] = {}
        for key, item in value.items():
            key_text = str(key)
            if any(marker in key_text.casefold() for marker in _SENSITIVE_KEYS):
                sanitized[key_text] = "[REDACTED]"
            else:
                sanitized[key_text] = _safe_value(item, depth + 1)
        return sanitized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_safe_value(item, depth + 1) for item in value[:200]]
    if isinstance(value, bytes):
        return f"[BINARY:{len(value)} bytes]"
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str) and len(value) > 8_000:
            return value[:8_000] + "…[TRUNCATED]"
        return value
    return str(value)


def _correlation_uuid() -> UUID:
    raw = get_correlation_id()
    try:
        return UUID(raw)
    except ValueError:
        return uuid5(NAMESPACE_URL, f"digital-expert-agents:{raw}")


def write_audit_log(
    db: Session,
    *,
    case_id: UUID,
    actor_type: str,
    actor_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    outcome: AuditOutcome = AuditOutcome.SUCCEEDED,
    request: object | None = None,
    response: object | None = None,
    error: str | None = None,
    latency_ms: int | None = None,
) -> AuditLog:
    """Append a redacted audit record using the caller's active transaction."""

    payload: dict[str, object] = {
        "schema_version": 1,
        "request": _safe_value(request),
        "response": _safe_value(response),
    }
    if error is not None:
        payload["error"] = _safe_value(error)
    if latency_ms is not None:
        payload["latency_ms"] = max(0, latency_ms)

    record = AuditLog(
        case_id=case_id,
        correlation_id=_correlation_uuid(),
        actor_type=actor_type[:50],
        actor_id=actor_id[:100],
        action=action[:100],
        entity_type=entity_type[:100],
        entity_id=entity_id[:100],
        outcome=outcome.value,
        payload_trace=payload,
    )
    db.add(record)
    return record

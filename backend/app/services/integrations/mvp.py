"""Typed in-memory integration gateway for the MVP verification workflow."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from app.agents.income_verification.state import ActionType, FlatValue


@dataclass(frozen=True, slots=True)
class GatewayResult:
    result_reference: str
    duplicate: bool = False


class ActionGateway(Protocol):
    async def execute(
        self,
        *,
        action_type: ActionType,
        application_id: str,
        parameters: dict[str, FlatValue],
        idempotency_key: str,
    ) -> GatewayResult: ...

    async def verify(self, result_reference: str) -> bool: ...


class InMemoryActionGateway:
    """Mock-only adapter with stable idempotency and read-back state."""

    def __init__(self) -> None:
        self._by_key: dict[str, GatewayResult] = {}
        self._verified_references: set[str] = set()
        self._lock = asyncio.Lock()

    async def execute(
        self,
        *,
        action_type: ActionType,
        application_id: str,
        parameters: dict[str, FlatValue],
        idempotency_key: str,
    ) -> GatewayResult:
        del parameters  # Payload is typed by ProposedAction and is not logged here.
        async with self._lock:
            existing = self._by_key.get(idempotency_key)
            if existing is not None:
                return GatewayResult(existing.result_reference, duplicate=True)
            reference = (
                f"mock:{action_type.value.lower()}:{application_id}:{len(self._by_key) + 1}"
            )
            result = GatewayResult(reference)
            self._by_key[idempotency_key] = result
            self._verified_references.add(reference)
            return result

    async def verify(self, result_reference: str) -> bool:
        async with self._lock:
            return result_reference in self._verified_references

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    EMBEDDING_DIMENSIONS,
    AgentKnowledgeBase,
    AuditLog,
    AuditOutcome,
    Case,
    CaseStatus,
    Document,
    DocumentStatus,
    PolicyDocument,
    PolicyEmbedding,
)
from app.db.session import session_scope
from app.services.policy_catalog import parse_hhb_policy
from app.services.rag import AGENT_KNOWLEDGE_KEYS, split_text


SEED_NAMESPACE = "https://digital-expert-agents.local/demo"
DEMO_CASE_ID = uuid5(NAMESPACE_URL, f"{SEED_NAMESPACE}/case/minh-an")
DEMO_DOCUMENT_ID = uuid5(NAMESPACE_URL, f"{SEED_NAMESPACE}/document/minh-an-dossier")


@dataclass(frozen=True)
class KnowledgeBaseSeed:
    agent_key: str
    name: str


@dataclass(frozen=True)
class PolicySeed:
    agent_key: str
    title: str
    version: str
    section_id: str
    page_number: int
    content: str


@dataclass(frozen=True)
class BootstrapResult:
    knowledge_bases_created: int
    policy_documents_created: int
    policy_embeddings_created: int
    demo_case_created: bool
    demo_document_created: bool


class BootstrapEmbeddingProvider(Protocol):
    """Small injection port; production providers are owned by the RAG service."""

    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


KNOWLEDGE_BASE_DEFINITIONS: tuple[KnowledgeBaseSeed, ...] = (
    KnowledgeBaseSeed(
        agent_key="customer_relationship",
        name="Customer Relationship Policies",
    ),
    KnowledgeBaseSeed(agent_key="credit", name="Credit Policies"),
    KnowledgeBaseSeed(
        agent_key="risk_management",
        name="Risk Management Policies",
    ),
    KnowledgeBaseSeed(
        agent_key="legal_compliance",
        name="Legal and Compliance Policies",
    ),
    KnowledgeBaseSeed(
        agent_key="collateral_appraisal",
        name="Collateral Appraisal Policies",
    ),
)


# These records are deliberately labelled DEMO ONLY. They are deterministic test
# fixtures, not authoritative banking rules.
DEMO_POLICIES: tuple[PolicySeed, ...] = (
    PolicySeed(
        agent_key="customer_relationship",
        title="DEMO ONLY - Corporate Loan Intake Checklist",
        version="1.0",
        section_id="INTAKE-1.1",
        page_number=1,
        content=(
            "DEMO ONLY. A corporate loan intake package must include a loan "
            "application, current business registration, audited financial "
            "statements, beneficial-owner declaration, and collateral schedule."
        ),
    ),
    PolicySeed(
        agent_key="credit",
        title="DEMO ONLY - Corporate Credit Ratios",
        version="1.0",
        section_id="CREDIT-4.2.1",
        page_number=18,
        content=(
            "DEMO ONLY. Corporate borrowers must maintain a minimum Debt Service "
            "Coverage Ratio (DSCR) of 1.25x. A stressed DSCR assessment must "
            "include identified contingent liabilities."
        ),
    ),
    PolicySeed(
        agent_key="risk_management",
        title="DEMO ONLY - Corporate Risk Classification",
        version="1.0",
        section_id="RISK-3.4",
        page_number=9,
        content=(
            "DEMO ONLY. An unresolved material legal contingency must be reflected "
            "in the preliminary risk tier and cross-checked against stressed debt "
            "service capacity before a low-risk conclusion is supported."
        ),
    ),
    PolicySeed(
        agent_key="legal_compliance",
        title="DEMO ONLY - KYC and Legal Review",
        version="1.0",
        section_id="KYC-2.3",
        page_number=7,
        content=(
            "DEMO ONLY. Legal and compliance review must verify corporate "
            "registration, beneficial ownership, sanctions screening, and all "
            "known material litigation or contingent liabilities."
        ),
    ),
    PolicySeed(
        agent_key="collateral_appraisal",
        title="DEMO ONLY - Collateral LTV Guideline",
        version="1.0",
        section_id="COLLATERAL-5.1",
        page_number=12,
        content=(
            "DEMO ONLY. The Loan-to-Value ratio for eligible commercial real "
            "estate collateral must not exceed 70 percent of the accepted "
            "appraised value."
        ),
    ),
)


def deterministic_embedding(
    content: str, dimensions: int = EMBEDDING_DIMENSIONS
) -> list[float]:
    """Return a stable token-hashing vector for tests only; never used by bootstrap."""

    if dimensions <= 0:
        raise ValueError("dimensions must be positive")

    vector = [0.0] * dimensions
    tokens = re.findall(r"\w+", content.casefold(), flags=re.UNICODE)
    if not tokens:
        raise ValueError("content must contain at least one token")

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:8], "big") % dimensions
        sign = 1.0 if digest[8] & 1 else -1.0
        vector[index] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector]


def _stable_uuid(resource: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"{SEED_NAMESPACE}/{resource}")


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def seed_reference_data(
    db: Session,
    embedding_provider: BootstrapEmbeddingProvider | None = None,
    *,
    include_demo_policies: bool = False,
) -> tuple[int, int, int]:
    """Seed KB identities and, only when requested, clearly-labelled demo policies."""

    if (
        embedding_provider is not None
        and embedding_provider.dimension != EMBEDDING_DIMENSIONS
    ):
        raise ValueError(
            f"embedding provider dimension must be {EMBEDDING_DIMENSIONS}"
        )

    knowledge_bases_created = 0
    documents_created = 0
    embeddings_created = 0
    knowledge_bases: dict[str, AgentKnowledgeBase] = {}
    pending_embeddings: list[
        tuple[PolicySeed, AgentKnowledgeBase, PolicyDocument, str]
    ] = []

    for definition in KNOWLEDGE_BASE_DEFINITIONS:
        knowledge_base = db.scalar(
            select(AgentKnowledgeBase).where(
                AgentKnowledgeBase.agent_key == definition.agent_key
            )
        )
        if knowledge_base is None:
            knowledge_base = AgentKnowledgeBase(
                id=_stable_uuid(f"knowledge-base/{definition.agent_key}"),
                agent_key=definition.agent_key,
                name=definition.name,
                active=True,
            )
            db.add(knowledge_base)
            db.flush()
            knowledge_bases_created += 1
        else:
            knowledge_base.name = definition.name
            knowledge_base.active = True
        knowledge_bases[definition.agent_key] = knowledge_base

    if not include_demo_policies:
        return knowledge_bases_created, 0, 0

    for policy in DEMO_POLICIES:
        knowledge_base = knowledge_bases[policy.agent_key]
        content_hash = _sha256(policy.content)
        policy_document = db.scalar(
            select(PolicyDocument).where(
                PolicyDocument.knowledge_base_id == knowledge_base.id,
                PolicyDocument.title == policy.title,
                PolicyDocument.version == policy.version,
            )
        )
        if policy_document is None:
            policy_document = PolicyDocument(
                id=_stable_uuid(
                    f"policy-document/{policy.agent_key}/{policy.title}/{policy.version}"
                ),
                knowledge_base_id=knowledge_base.id,
                title=policy.title,
                version=policy.version,
                source_object_key=None,
                sha256=content_hash,
                effective_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                active=True,
            )
            db.add(policy_document)
            db.flush()
            documents_created += 1
        else:
            if policy_document.sha256 != content_hash:
                raise ValueError(
                    "A demo policy title/version cannot be changed in place"
                )
            policy_document.active = True

        embedding = db.scalar(
            select(PolicyEmbedding).where(
                PolicyEmbedding.policy_document_id == policy_document.id,
                PolicyEmbedding.content_hash == content_hash,
            )
        )
        if embedding is None and embedding_provider is not None:
            pending_embeddings.append(
                (policy, knowledge_base, policy_document, content_hash)
            )

    if pending_embeddings and embedding_provider is not None:
        vectors = embedding_provider.embed(
            [policy.content for policy, _, _, _ in pending_embeddings]
        )
        if len(vectors) != len(pending_embeddings):
            raise ValueError("embedding provider returned an unexpected vector count")

        for pending, vector in zip(pending_embeddings, vectors):
            policy, knowledge_base, policy_document, content_hash = pending
            if len(vector) != EMBEDDING_DIMENSIONS:
                raise ValueError(
                    f"embedding provider must return {EMBEDDING_DIMENSIONS} dimensions"
                )
            db.add(
                PolicyEmbedding(
                    id=_stable_uuid(
                        f"policy-embedding/{policy.agent_key}/{content_hash}"
                    ),
                    knowledge_base_id=knowledge_base.id,
                    policy_document_id=policy_document.id,
                    chunk_index=0,
                    content_chunk=policy.content,
                    content_hash=content_hash,
                    embedding=vector,
                    metadata_={
                        "document_name": policy.title,
                        "document_version": policy.version,
                        "section_id": policy.section_id,
                        "page_number": policy.page_number,
                        "agent_scope": policy.agent_key,
                        "demo_only": True,
                    },
                )
            )
            embeddings_created += 1

    return knowledge_bases_created, documents_created, embeddings_created


def seed_demo_case(db: Session) -> bool:
    """Create one stable, unassessed demo case and its creation audit event."""

    if db.get(Case, DEMO_CASE_ID) is not None:
        return False

    input_payload: dict[str, object] = {
        "demo_only": True,
        "product_type": "CORPORATE_TERM_LOAN",
        "company_tier": "MID_MARKET",
        "borrower_profile": {
            "company_name": "DEMO - Minh An Manufacturing JSC",
            "registration_number": "DEMO-REG-001",
            "industry": "manufacturing",
            "years_in_business": 12,
            "business_model_summary": (
                "Demo manufacturer requesting capacity-expansion financing."
            ),
        },
        "requested_terms": {
            "requested_amount": 50_000_000_000,
            "currency": "VND",
            "annual_interest_rate": 0.08,
            "maturity_months": 36,
        },
        "document_checklist": {
            "required": [
                "loan_application",
                "business_registration",
                "audited_financial_statements",
                "beneficial_owner_declaration",
                "collateral_schedule",
            ],
            "received": [
                "loan_application",
                "business_registration",
                "audited_financial_statements",
                "beneficial_owner_declaration",
                "collateral_schedule",
            ],
        },
        "credit_financial_inputs": {
            "cash_available_for_debt_service": 1_530_000_000,
            "net_profit_after_tax": 1_000_000_000,
            "depreciation": 330_000_000,
            "interest_expense": 200_000_000,
            "principal_due": 800_000_000,
            "interest_due": 200_000_000,
            "current_assets": 24_000_000_000,
            "current_liabilities": 12_000_000_000,
            "total_debt": 30_000_000_000,
            "total_equity": 20_000_000_000,
        },
        "risk_management": {
            "risk_tier": "LOW",
            "current_exposure": 10_000_000_000,
            "proposed_exposure": 50_000_000_000,
            "policy_limit": 100_000_000_000,
            "industry_risk_summary": (
                "Demo manufacturing exposure remains within the supplied limit."
            ),
        },
        "legal_compliance": {
            "legal": {
                "corporate_governance_valid": True,
                "title_ownership_verified": True,
                "unresolved_litigation": True,
                "litigation_risk_summary": (
                    "A disclosed demo claim creates a contingent liability."
                ),
            },
            "compliance": {
                "kyc_status": "VERIFIED",
                "aml_risk_level": "LOW",
                "sanctions_check_passed": True,
                "regulatory_inquiry_open": False,
            },
            "contingent_liability": 250_000_000,
        },
        "collateral": {
            "items": [
                {
                    "item_id": "DEMO-COLLATERAL-001",
                    "collateral_type": "REAL_ESTATE",
                    "description": "Demo commercial manufacturing property",
                    "appraised_value": 80_000_000_000,
                    "eligible_value": 80_000_000_000,
                }
            ],
            "maximum_ltv_ratio": 0.70,
        },
    }

    demo_case = Case(
        id=DEMO_CASE_ID,
        company_name="DEMO - Minh An Manufacturing JSC",
        requested_amount=Decimal("50000000000.00"),
        currency="VND",
        created_by="demo-officer",
        status=CaseStatus.INGESTED.value,
        workflow_id="corporate_loan_v1",
        workflow_version="1.0",
        input_payload=input_payload,
    )
    db.add(demo_case)
    db.flush()

    db.add(
        AuditLog(
            id=_stable_uuid("audit/demo-case-created"),
            case_id=demo_case.id,
            correlation_id=_stable_uuid("correlation/demo-bootstrap"),
            actor_type="SYSTEM",
            actor_id="database-bootstrap",
            action="CASE_CREATED",
            entity_type="case",
            entity_id=str(demo_case.id),
            outcome=AuditOutcome.SUCCEEDED.value,
            payload_trace={
                "schema_version": 1,
                "request": {
                    "source": "demo_seed",
                    "input_payload": input_payload,
                },
                "response": {
                    "case_id": str(demo_case.id),
                    "status": demo_case.status,
                },
            },
        )
    )
    return True


def seed_demo_case_document(
    db: Session,
    *,
    content: str,
    object_key: str,
) -> bool:
    """Attach the fictional credit package so the seeded case is demo-ready."""

    if db.get(Document, DEMO_DOCUMENT_ID) is not None:
        return False
    if db.get(Case, DEMO_CASE_ID) is None:
        raise ValueError("demo case must exist before its document is seeded")
    payload = content.encode("utf-8")
    content_hash = hashlib.sha256(payload).hexdigest()
    document = Document(
        id=DEMO_DOCUMENT_ID,
        case_id=DEMO_CASE_ID,
        document_type="CORPORATE_CREDIT_DOSSIER",
        original_filename="minh-an-credit-dossier.txt",
        object_key=object_key,
        content_type="text/plain; charset=utf-8",
        byte_size=len(payload),
        sha256=content_hash,
        extracted_text=content,
        status=DocumentStatus.PARSED.value,
    )
    db.add(document)
    db.add(
        AuditLog(
            id=_stable_uuid("audit/demo-document-created"),
            case_id=DEMO_CASE_ID,
            correlation_id=_stable_uuid("correlation/demo-bootstrap"),
            actor_type="SYSTEM",
            actor_id="database-bootstrap",
            action="DOCUMENT_UPLOADED",
            entity_type="document",
            entity_id=str(DEMO_DOCUMENT_ID),
            outcome=AuditOutcome.SUCCEEDED.value,
            payload_trace={
                "schema_version": 1,
                "request": {"source": "demo_seed", "sha256": content_hash},
                "response": {"object_key": object_key, "status": document.status},
            },
        )
    )
    return True


def seed_hhb_policy(
    db: Session,
    *,
    content: str,
    source_object_key: str,
    embedding_provider: BootstrapEmbeddingProvider,
) -> tuple[int, int]:
    """Seed the supplied HHB regulation into each authorized specialist scope."""

    if embedding_provider.dimension != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"embedding provider dimension must be {EMBEDDING_DIMENSIONS}"
        )
    knowledge_bases = {
        item.agent_key: item
        for item in db.scalars(select(AgentKnowledgeBase)).all()
    }
    documents_created = 0
    pending: list[
        tuple[PolicyDocument, AgentKnowledgeBase, int, str, str, int]
    ] = []
    for section in parse_hhb_policy(content):
        for agent_id in section.agent_ids:
            agent_key = AGENT_KNOWLEDGE_KEYS[agent_id]
            knowledge_base = knowledge_bases[agent_key]
            title = f"QĐ-HHB-2026/01 — {section.section_id} {section.title}"
            section_hash = _sha256(section.content)
            document = db.scalar(
                select(PolicyDocument).where(
                    PolicyDocument.knowledge_base_id == knowledge_base.id,
                    PolicyDocument.title == title,
                    PolicyDocument.version == "2026.01",
                )
            )
            if document is None:
                document = PolicyDocument(
                    id=_stable_uuid(
                        f"hhb-policy/{agent_key}/{section.section_id}/2026.01"
                    ),
                    knowledge_base_id=knowledge_base.id,
                    title=title,
                    version="2026.01",
                    source_object_key=source_object_key,
                    sha256=section_hash,
                    effective_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
                    active=True,
                )
                db.add(document)
                db.flush()
                documents_created += 1
            elif document.sha256 != section_hash:
                raise ValueError(
                    f"HHB policy {section.section_id} changed without a new version"
                )

            for chunk in split_text(section.content, chunk_size=1_800, overlap=180):
                content_hash = _sha256(chunk.content)
                existing = db.scalar(
                    select(PolicyEmbedding.id).where(
                        PolicyEmbedding.policy_document_id == document.id,
                        PolicyEmbedding.content_hash == content_hash,
                    )
                )
                if existing is None:
                    pending.append(
                        (
                            document,
                            knowledge_base,
                            chunk.index,
                            chunk.content,
                            section.section_id,
                            section.line_number,
                        )
                    )

    if not pending:
        return documents_created, 0
    vectors = embedding_provider.embed([item[3] for item in pending])
    if len(vectors) != len(pending):
        raise ValueError("embedding provider returned an unexpected vector count")
    for item, vector in zip(pending, vectors, strict=True):
        document, knowledge_base, chunk_index, chunk, section_id, line_number = item
        if len(vector) != EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"embedding provider must return {EMBEDDING_DIMENSIONS} dimensions"
            )
        content_hash = _sha256(chunk)
        db.add(
            PolicyEmbedding(
                id=_stable_uuid(
                    f"hhb-chunk/{knowledge_base.agent_key}/{section_id}/"
                    f"{chunk_index}/{content_hash}"
                ),
                knowledge_base_id=knowledge_base.id,
                policy_document_id=document.id,
                chunk_index=chunk_index,
                content_chunk=chunk,
                content_hash=content_hash,
                embedding=vector,
                metadata_={
                    "document_name": "Sổ tay QĐ-HHB-2026/01",
                    "document_version": "2026.01",
                    "section_id": section_id,
                    "page_number": 1,
                    "source_line_number": line_number,
                    "agent_scope": knowledge_base.agent_key,
                    "fictional_demo_policy": True,
                },
            )
        )
    return documents_created, len(pending)


def bootstrap_database(
    db: Session,
    *,
    include_demo_policies: bool = False,
    include_demo_case: bool = False,
    hhb_policy_content: str | None = None,
    hhb_source_object_key: str = "policies/hhb/QD-HHB-2026-01.txt",
    demo_case_document_content: str | None = None,
    demo_case_document_object_key: str = "cases/demo/minh-an-credit-dossier.txt",
    embedding_provider: BootstrapEmbeddingProvider | None = None,
) -> BootstrapResult:
    """Seed post-migration reference data; safe to invoke repeatedly."""

    kb_count, document_count, embedding_count = seed_reference_data(
        db,
        embedding_provider=embedding_provider,
        include_demo_policies=include_demo_policies,
    )
    case_created = seed_demo_case(db) if include_demo_case else False
    demo_document_created = (
        seed_demo_case_document(
            db,
            content=demo_case_document_content,
            object_key=demo_case_document_object_key,
        )
        if include_demo_case and demo_case_document_content is not None
        else False
    )
    if hhb_policy_content is not None:
        if embedding_provider is None:
            raise ValueError("HHB policy seeding requires a real embedding provider")
        hhb_documents, hhb_embeddings = seed_hhb_policy(
            db,
            content=hhb_policy_content,
            source_object_key=hhb_source_object_key,
            embedding_provider=embedding_provider,
        )
        document_count += hhb_documents
        embedding_count += hhb_embeddings
    return BootstrapResult(
        knowledge_bases_created=kb_count,
        policy_documents_created=document_count,
        policy_embeddings_created=embedding_count,
        demo_case_created=case_created,
        demo_document_created=demo_document_created,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Seed Digital Expert Agents reference data after `alembic upgrade head`."
        )
    )
    parser.add_argument(
        "--include-demo-policies",
        action="store_true",
        help="also seed clearly-labelled demo policy documents",
    )
    parser.add_argument(
        "--include-demo-case",
        action="store_true",
        help="also create the unassessed demo case",
    )
    args = parser.parse_args()

    with session_scope() as db:
        result = bootstrap_database(
            db,
            include_demo_policies=args.include_demo_policies,
            include_demo_case=args.include_demo_case,
        )
    print(json.dumps(asdict(result), sort_keys=True))


if __name__ == "__main__":
    main()

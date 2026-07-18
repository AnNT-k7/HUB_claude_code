from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from pydantic import ValidationError
import pytest

from app.agents.tier2_board.reviewer import Reviewer
from app.agents.tier2_board.shared_board import (
    InMemorySharedBoardRepository,
    SharedBoardConflictError,
    SharedBoardManager,
)
from app.agents.tier2_board.specialists.collateral_appraisal import (
    LtvCalculationError,
    calculate_ltv_ratio,
)
from app.agents.tier2_board.specialists.credit import (
    RatioCalculationError,
    assess_credit,
    calculate_current_ratio,
    calculate_debt_to_equity,
    calculate_dscr,
)
from app.agents.tier2_board.specialists.risk_management import (
    calculate_concentration_limit_check,
)
from app.schemas.enums import AgentID, AssessmentStatus
from app.schemas.tier2 import (
    CreditAssessment,
    CreditFinancialInputs,
    CreditRatios,
    SharedBoardState,
    TaskState,
)


def test_credit_and_collateral_calculation_tools_are_decimal_and_typed() -> None:
    assert calculate_dscr(Decimal("150"), Decimal("80"), Decimal("20")) == Decimal(
        "1.5000"
    )
    assert calculate_current_ratio(Decimal("250"), Decimal("100")) == Decimal(
        "2.5000"
    )
    assert calculate_debt_to_equity(Decimal("75"), Decimal("50")) == Decimal(
        "1.5000"
    )
    assert calculate_ltv_ratio(Decimal("600"), Decimal("800")) == Decimal(
        "0.7500"
    )


@pytest.mark.parametrize(
    ("calculation", "arguments", "error_type"),
    [
        (calculate_dscr, (Decimal("1"), Decimal("0"), Decimal("0")), RatioCalculationError),
        (calculate_current_ratio, (Decimal("1"), Decimal("0")), RatioCalculationError),
        (calculate_debt_to_equity, (Decimal("1"), Decimal("0")), RatioCalculationError),
        (calculate_ltv_ratio, (Decimal("1"), Decimal("0")), LtvCalculationError),
    ],
)
def test_calculation_tools_fail_closed_on_invalid_denominators(
    calculation: object,
    arguments: tuple[Decimal, ...],
    error_type: type[ValueError],
) -> None:
    with pytest.raises(error_type):
        calculation(*arguments)  # type: ignore[operator]


def test_concentration_check_includes_existing_and_proposed_exposure() -> None:
    within_limit = calculate_concentration_limit_check(
        Decimal("40"), Decimal("50"), Decimal("100")
    )
    outside_limit = calculate_concentration_limit_check(
        Decimal("40"), Decimal("61"), Decimal("100")
    )

    assert within_limit.within_limit is True
    assert outside_limit.within_limit is False


def test_credit_builder_requests_missing_data_instead_of_guessing() -> None:
    assessment = assess_credit(None, None)

    assert assessment.status == AssessmentStatus.REQUIRES_MORE_DATA
    assert assessment.calculated_ratios is None
    assert assessment.missing_data[0].code == "FINANCIAL_STATEMENTS_MISSING"


def test_shared_board_uses_isolated_snapshots_and_optimistic_versions() -> None:
    repository = InMemorySharedBoardRepository()
    manager = SharedBoardManager(repository)
    case_id = uuid4()
    board = manager.initialize(
        case_id,
        [TaskState(task_id="credit", assigned_to=AgentID.CREDIT)],
    )

    assert board.version == 0
    snapshot = manager.get(case_id)
    snapshot.tasks["credit"].detail = "local mutation"
    assert manager.get(case_id).tasks["credit"].detail == ""

    assessment = assess_credit(None, None)
    updated = manager.post_assessment(
        case_id,
        assessment,
        expected_version=board.version,
    )
    assert updated.version == 1
    assert updated.specialist_outputs[AgentID.CREDIT].agent_id == AgentID.CREDIT

    with pytest.raises(SharedBoardConflictError, match="Expected board version"):
        manager.post_assessment(case_id, assessment, expected_version=0)


def test_shared_board_contract_rejects_invalid_task_and_round_invariants() -> None:
    with pytest.raises(ValidationError, match="Task map key"):
        SharedBoardState(
            board_id=uuid4(),
            case_id=uuid4(),
            tasks={
                "wrong-key": TaskState(
                    task_id="credit",
                    assigned_to=AgentID.CREDIT,
                )
            },
        )

    with pytest.raises(ValidationError, match="exceeds max_debate_rounds"):
        SharedBoardState(
            board_id=uuid4(),
            case_id=uuid4(),
            current_debate_round=4,
            max_debate_rounds=3,
        )


def test_reviewer_detects_tampered_credit_calculation() -> None:
    inputs = CreditFinancialInputs(
        cash_available_for_debt_service=Decimal("150"),
        principal_due=Decimal("80"),
        interest_due=Decimal("20"),
        current_assets=Decimal("250"),
        current_liabilities=Decimal("100"),
        total_debt=Decimal("75"),
        total_equity=Decimal("50"),
    )
    assessment = CreditAssessment(
        status=AssessmentStatus.SUCCESS,
        financial_inputs=inputs,
        calculated_ratios=CreditRatios(
            dscr=Decimal("9.9999"),
            current_ratio=Decimal("2.5000"),
            debt_to_equity=Decimal("1.5000"),
        ),
    )
    board = SharedBoardState(
        board_id=uuid4(),
        case_id=uuid4(),
        specialist_outputs={AgentID.CREDIT: assessment},
    )

    result = Reviewer(required_agents=frozenset({AgentID.CREDIT})).review(board)
    issue_codes = {issue.code for issue in result.issues}

    assert "CREDIT_CALCULATION_MISMATCH" in issue_codes
    assert "POLICY_CITATION_MISSING" in issue_codes
    assert result.consensus_reached is False
    assert result.proposed_round == 1


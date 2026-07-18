"""Deterministic Reviewer Agent for Tier-2 quality and consistency checks."""

from decimal import Decimal

from app.agents.tier2_board.specialists.collateral_appraisal import (
    LtvCalculationError,
    calculate_ltv_ratio,
)
from app.agents.tier2_board.specialists.credit import (
    RatioCalculationError,
    calculate_current_ratio,
    calculate_debt_to_equity,
    calculate_dscr,
)
from app.schemas.enums import (
    AgentID,
    AssessmentStatus,
    DebateStatus,
    RiskTier,
    RiskSeverity,
    SPECIALIST_AGENT_IDS,
)
from app.schemas.tier2 import (
    CollateralAppraisalAssessment,
    CreditAssessment,
    DebateIssue,
    DebateRecord,
    LegalComplianceAssessment,
    ReviewerResult,
    RiskManagementAssessment,
    SharedBoardState,
)


class Reviewer:
    """Pure reviewer; it never mutates the board or calls an LLM/network service."""

    def __init__(
        self,
        *,
        max_debate_rounds: int = 3,
        required_agents: frozenset[AgentID] = SPECIALIST_AGENT_IDS,
    ) -> None:
        if not 1 <= max_debate_rounds <= 10:
            raise ValueError("max_debate_rounds must be between 1 and 10")
        if not required_agents or not required_agents <= SPECIALIST_AGENT_IDS:
            raise ValueError("required_agents must contain only Tier-2 specialists")
        self._max_debate_rounds = max_debate_rounds
        self._required_agents = required_agents

    def review(self, board: SharedBoardState) -> ReviewerResult:
        """Inspect one immutable snapshot and propose a bounded debate round."""

        issues: list[DebateIssue] = []
        issues.extend(self._check_required_outputs(board))
        issues.extend(self._check_statuses_and_citations(board))
        issues.extend(self._check_credit_math(board))
        issues.extend(self._check_collateral_math(board))
        issues.extend(self._check_cross_domain_consistency(board))

        for record in board.debate_log:
            if record.status == DebateStatus.OPEN:
                issues.append(record.issue)
        issues = _deduplicate_issues(issues)

        if not issues:
            return ReviewerResult(consensus_reached=True)

        effective_max_rounds = min(
            self._max_debate_rounds,
            board.max_debate_rounds,
        )
        if board.current_debate_round >= effective_max_rounds:
            return ReviewerResult(
                issues=issues,
                max_rounds_reached=True,
            )

        next_round = board.current_debate_round + 1
        open_issue_keys = {
            (record.issue.code, record.issue.target_agent)
            for record in board.debate_log
            if record.status == DebateStatus.OPEN
        }
        proposed_records = [
            DebateRecord(round_number=next_round, issue=issue)
            for issue in issues
            if (issue.code, issue.target_agent) not in open_issue_keys
        ]
        return ReviewerResult(
            issues=issues,
            proposed_debate_records=proposed_records,
            proposed_round=next_round if proposed_records else None,
        )

    def _check_required_outputs(self, board: SharedBoardState) -> list[DebateIssue]:
        missing_agents = self._required_agents - set(board.specialist_outputs)
        return [
            DebateIssue(
                code="SPECIALIST_OUTPUT_MISSING",
                severity=RiskSeverity.HIGH,
                target_agent=agent_id,
                description=f"No Shared Board output exists for {agent_id.value}.",
                required_action=(
                    "Run the assigned specialist task or explicitly report missing data."
                ),
            )
            for agent_id in sorted(missing_agents, key=lambda item: item.value)
        ]

    def _check_statuses_and_citations(
        self,
        board: SharedBoardState,
    ) -> list[DebateIssue]:
        issues: list[DebateIssue] = []
        policy_agents = {
            AgentID.CREDIT,
            AgentID.RISK_MANAGEMENT,
            AgentID.LEGAL_COMPLIANCE,
            AgentID.COLLATERAL_APPRAISAL,
        }
        for agent_id, assessment in board.specialist_outputs.items():
            if assessment.status != AssessmentStatus.SUCCESS:
                code, action = _status_issue(assessment.status)
                issues.append(
                    DebateIssue(
                        code=code,
                        severity=RiskSeverity.HIGH,
                        target_agent=agent_id,
                        description=(
                            f"{agent_id.value} assessment status is "
                            f"{assessment.status.value}."
                        ),
                        required_action=action,
                        related_field="status",
                    )
                )
            if (
                assessment.status == AssessmentStatus.SUCCESS
                and agent_id in policy_agents
                and not assessment.policy_citations
            ):
                issues.append(
                    DebateIssue(
                        code="POLICY_CITATION_MISSING",
                        severity=RiskSeverity.HIGH,
                        target_agent=agent_id,
                        description=(
                            f"{agent_id.value} posted a policy-sensitive conclusion "
                            "without an approved policy citation."
                        ),
                        required_action=(
                            "Retrieve an approved policy chunk and attach its exact citation, "
                            "or change the assessment to MANUAL_REVIEW."
                        ),
                        related_field="policy_citations",
                    )
                )
            assessment_citation_ids = {
                citation.policy_chunk_id for citation in assessment.policy_citations
            }
            for risk_flag in assessment.risk_flags:
                flag_citation_ids = {
                    citation.policy_chunk_id for citation in risk_flag.policy_citations
                }
                if not flag_citation_ids <= assessment_citation_ids:
                    issues.append(
                        DebateIssue(
                            code="RISK_CITATION_NOT_DECLARED",
                            severity=RiskSeverity.MEDIUM,
                            target_agent=agent_id,
                            description=(
                                f"Risk flag {risk_flag.code} cites policy chunks not "
                                "declared by the assessment."
                            ),
                            required_action=(
                                "Add the same verified citations to the assessment-level "
                                "policy_citations list."
                            ),
                            related_field=f"risk_flags.{risk_flag.code}",
                        )
                    )
        return issues

    def _check_credit_math(self, board: SharedBoardState) -> list[DebateIssue]:
        assessment = board.specialist_outputs.get(AgentID.CREDIT)
        if not isinstance(assessment, CreditAssessment):
            return []
        if assessment.status == AssessmentStatus.SUCCESS and (
            assessment.financial_inputs is None
            or assessment.calculated_ratios is None
        ):
            return [
                DebateIssue(
                    code="CREDIT_CALCULATION_MISSING",
                    severity=RiskSeverity.HIGH,
                    target_agent=AgentID.CREDIT,
                    description="Successful credit output does not contain inputs and ratios.",
                    required_action=(
                        "Post financial inputs and deterministically calculated ratios."
                    ),
                    related_field="calculated_ratios",
                )
            ]
        if assessment.financial_inputs is None or assessment.calculated_ratios is None:
            return []

        inputs = assessment.financial_inputs
        required_values = (
            inputs.principal_due,
            inputs.interest_due,
            inputs.current_assets,
            inputs.current_liabilities,
            inputs.total_debt,
            inputs.total_equity,
        )
        if any(value is None for value in required_values):
            return []
        cash_available = inputs.cash_available_for_debt_service
        if cash_available is None and all(
            value is not None
            for value in (
                inputs.net_profit_after_tax,
                inputs.depreciation,
                inputs.interest_expense,
            )
        ):
            assert inputs.net_profit_after_tax is not None
            assert inputs.depreciation is not None
            assert inputs.interest_expense is not None
            cash_available = (
                inputs.net_profit_after_tax
                + inputs.depreciation
                + inputs.interest_expense
            )
        if cash_available is None:
            return []
        principal_due = inputs.principal_due
        interest_due = inputs.interest_due
        current_assets = inputs.current_assets
        current_liabilities = inputs.current_liabilities
        total_debt = inputs.total_debt
        total_equity = inputs.total_equity
        assert principal_due is not None
        assert interest_due is not None
        assert current_assets is not None
        assert current_liabilities is not None
        assert total_debt is not None
        assert total_equity is not None

        comparisons: list[tuple[str, Decimal | None, Decimal | None]] = []
        try:
            expected_dscr = calculate_dscr(
                cash_available,
                principal_due,
                interest_due,
            )
        except RatioCalculationError:
            expected_dscr = None
        comparisons.append(
            ("dscr", expected_dscr, assessment.calculated_ratios.dscr)
        )
        try:
            expected_current_ratio = calculate_current_ratio(
                current_assets,
                current_liabilities,
            )
        except RatioCalculationError:
            expected_current_ratio = None
        comparisons.append(
            (
                "current_ratio",
                expected_current_ratio,
                assessment.calculated_ratios.current_ratio,
            )
        )
        try:
            expected_debt_to_equity = calculate_debt_to_equity(
                total_debt,
                total_equity,
            )
        except RatioCalculationError:
            expected_debt_to_equity = None
        comparisons.append(
            (
                "debt_to_equity",
                expected_debt_to_equity,
                assessment.calculated_ratios.debt_to_equity,
            )
        )
        return [
            DebateIssue(
                code="CREDIT_CALCULATION_MISMATCH",
                severity=RiskSeverity.HIGH,
                target_agent=AgentID.CREDIT,
                description=(
                    f"Reported {field_name}={reported} does not match the "
                    f"deterministic result {expected}."
                ),
                required_action=(
                    f"Recalculate {field_name} from the posted financial inputs."
                ),
                related_field=f"calculated_ratios.{field_name}",
            )
            for field_name, expected, reported in comparisons
            if expected != reported
        ]

    def _check_collateral_math(self, board: SharedBoardState) -> list[DebateIssue]:
        assessment = board.specialist_outputs.get(AgentID.COLLATERAL_APPRAISAL)
        if not isinstance(assessment, CollateralAppraisalAssessment):
            return []
        if assessment.status == AssessmentStatus.SUCCESS and (
            assessment.requested_loan_amount is None
            or not assessment.collateral_items
            or assessment.computed_ltv_ratio is None
        ):
            return [
                DebateIssue(
                    code="LTV_CALCULATION_MISSING",
                    severity=RiskSeverity.HIGH,
                    target_agent=AgentID.COLLATERAL_APPRAISAL,
                    description="Successful collateral output does not contain a complete LTV.",
                    required_action=(
                        "Post requested amount, collateral items, eligible total, and LTV."
                    ),
                    related_field="computed_ltv_ratio",
                )
            ]
        if assessment.requested_loan_amount is None or not assessment.collateral_items:
            return []
        expected_total_appraised = sum(
            (item.appraised_value for item in assessment.collateral_items),
            start=Decimal("0"),
        )
        expected_total_eligible = sum(
            (item.eligible_value for item in assessment.collateral_items),
            start=Decimal("0"),
        )
        try:
            expected_ltv = calculate_ltv_ratio(
                assessment.requested_loan_amount,
                expected_total_eligible,
            )
        except LtvCalculationError:
            expected_ltv = None
        mismatches = (
            assessment.total_collateral_value != expected_total_appraised
            or assessment.total_eligible_value != expected_total_eligible
            or assessment.computed_ltv_ratio != expected_ltv
        )
        if not mismatches:
            return []
        return [
            DebateIssue(
                code="LTV_CALCULATION_MISMATCH",
                severity=RiskSeverity.HIGH,
                target_agent=AgentID.COLLATERAL_APPRAISAL,
                description=(
                    "Posted collateral totals or LTV do not match the deterministic "
                    "calculation from collateral items."
                ),
                required_action=(
                    "Recalculate appraised total, eligible total, and requested amount "
                    "divided by eligible total."
                ),
                related_field="computed_ltv_ratio",
            )
        ]

    def _check_cross_domain_consistency(
        self,
        board: SharedBoardState,
    ) -> list[DebateIssue]:
        credit = board.specialist_outputs.get(AgentID.CREDIT)
        if not isinstance(credit, CreditAssessment):
            return []
        if credit.status != AssessmentStatus.SUCCESS:
            return []

        external_risk_codes: set[str] = set()
        legal_compliance = board.specialist_outputs.get(AgentID.LEGAL_COMPLIANCE)
        if isinstance(legal_compliance, LegalComplianceAssessment):
            external_risk_codes.update(
                flag.code
                for flag in legal_compliance.risk_flags
                if flag.severity in {RiskSeverity.HIGH, RiskSeverity.CRITICAL}
            )
        risk = board.specialist_outputs.get(AgentID.RISK_MANAGEMENT)
        if isinstance(risk, RiskManagementAssessment):
            if risk.risk_tier == RiskTier.HIGH:
                external_risk_codes.add("PRELIMINARY_RISK_TIER_HIGH")
            if (
                risk.concentration_limit_check is not None
                and not risk.concentration_limit_check.within_limit
            ):
                external_risk_codes.add("CONCENTRATION_LIMIT_EXCEEDED")
        unacknowledged = external_risk_codes - set(
            credit.acknowledged_cross_domain_risks
        )
        if not unacknowledged:
            return []
        return [
            DebateIssue(
                code="CROSS_DOMAIN_RISK_NOT_ACKNOWLEDGED",
                severity=RiskSeverity.HIGH,
                target_agent=AgentID.CREDIT,
                description=(
                    "Credit assessment does not acknowledge material risks from other "
                    f"specialists: {', '.join(sorted(unacknowledged))}."
                ),
                required_action=(
                    "Reassess credit capacity using the listed legal/compliance/risk "
                    "findings and record each acknowledged risk code."
                ),
                related_field="acknowledged_cross_domain_risks",
            )
        ]


def _status_issue(status: AssessmentStatus) -> tuple[str, str]:
    if status == AssessmentStatus.REQUIRES_MORE_DATA:
        return (
            "SPECIALIST_REQUIRES_MORE_DATA",
            "Supply the explicitly requested documents before rerunning the specialist.",
        )
    if status == AssessmentStatus.MANUAL_REVIEW:
        return (
            "SPECIALIST_MANUAL_REVIEW",
            "Resolve the stated manual-review condition or retain it for the human gate.",
        )
    if status == AssessmentStatus.ERROR:
        return (
            "SPECIALIST_EXECUTION_ERROR",
            "Resolve the deterministic execution error and rerun the specialist.",
        )
    return (
        "SPECIALIST_NOT_COMPLETE",
        "Wait for or rerun the specialist before synthesis.",
    )


def _deduplicate_issues(issues: list[DebateIssue]) -> list[DebateIssue]:
    unique: dict[tuple[str, AgentID, str | None], DebateIssue] = {}
    for issue in issues:
        key = (issue.code, issue.target_agent, issue.related_field)
        unique.setdefault(key, issue)
    return list(unique.values())


__all__ = ["Reviewer", "ReviewerResult"]

"""
Specialist Agents package.
"""
from app.agents.tier2_board.specialists.customer_relationship import run_customer_relationship_agent
from app.agents.tier2_board.specialists.credit import run_credit_agent
from app.agents.tier2_board.specialists.risk_management import run_risk_management_agent
from app.agents.tier2_board.specialists.compliance import run_compliance_agent
from app.agents.tier2_board.specialists.legal import run_legal_agent
from app.agents.tier2_board.specialists.collateral_appraisal import run_collateral_appraisal_agent
from app.agents.tier2_board.specialists.banking_operations import run_banking_operations_agent

__all__ = [
    "run_customer_relationship_agent",
    "run_credit_agent",
    "run_risk_management_agent",
    "run_compliance_agent",
    "run_legal_agent",
    "run_collateral_appraisal_agent",
    "run_banking_operations_agent",
]

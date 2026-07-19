"""
Tier 2 Support Service — Financial Ratio Calculation Engine.

Provides deterministic mathematical calculations for corporate loan assessments:
- Debt Service Coverage Ratio (DSCR)
- Current Ratio
- Leverage (Debt to Equity Ratio - D/E)
- Loan to Value Ratio (LTV)

Zero-Hallucination principle: All arithmetic is calculated via Python code, not LLM guessing.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class FinancialMetricsResult(BaseModel):
    dscr: Optional[float] = Field(None, description="Debt Service Coverage Ratio (DSCR)")
    current_ratio: Optional[float] = Field(None, description="Current Ratio (Tỷ lệ thanh toán hiện hành)")
    leverage_de: Optional[float] = Field(None, description="Debt to Equity Ratio (D/E)")
    ltv: Optional[float] = Field(None, description="Loan to Value Ratio (Tỷ lệ cho vay trên giá trị TSBĐ)")
    is_dscr_valid: bool = Field(False, description="DSCR >= 1.25x policy threshold")
    is_leverage_valid: bool = Field(False, description="D/E <= 3.0x policy threshold")
    is_ltv_valid: bool = Field(False, description="LTV <= 70.0% policy threshold")
    calculation_notes: list[str] = Field(default_factory=list)


def calculate_dscr(net_operating_income: float, total_debt_service: float) -> Optional[float]:
    """
    DSCR = Net Operating Income / Total Debt Service (Principal + Interest)
    """
    if total_debt_service <= 0:
        return None
    return round(net_operating_income / total_debt_service, 2)


def calculate_current_ratio(current_assets: float, current_liabilities: float) -> Optional[float]:
    """
    Current Ratio = Current Assets / Current Liabilities
    """
    if current_liabilities <= 0:
        return None
    return round(current_assets / current_liabilities, 2)


def calculate_leverage(total_liabilities: float, total_equity: float) -> Optional[float]:
    """
    Leverage (D/E) = Total Liabilities / Total Equity
    """
    if total_equity <= 0:
        return None
    return round(total_liabilities / total_equity, 2)


def calculate_ltv(requested_loan_amount: float, eligible_collateral_value: float) -> Optional[float]:
    """
    LTV = (Requested Loan Amount / Eligible Collateral Value) * 100
    """
    if eligible_collateral_value <= 0:
        return None
    return round((requested_loan_amount / eligible_collateral_value) * 100, 2)


def evaluate_financial_health(
    net_operating_income: float,
    total_debt_service: float,
    current_assets: float,
    current_liabilities: float,
    total_liabilities: float,
    total_equity: float,
    requested_loan_amount: float = 0.0,
    eligible_collateral_value: float = 0.0,
    min_dscr_threshold: float = 1.25,
    max_de_threshold: float = 3.0,
    max_ltv_threshold: float = 70.0
) -> FinancialMetricsResult:
    """
    Consolidated financial metrics evaluation against bank credit policy rules.
    """
    notes = []
    
    dscr = calculate_dscr(net_operating_income, total_debt_service)
    curr_ratio = calculate_current_ratio(current_assets, current_liabilities)
    leverage = calculate_leverage(total_liabilities, total_equity)
    ltv = calculate_ltv(requested_loan_amount, eligible_collateral_value) if eligible_collateral_value > 0 else None

    is_dscr_ok = False
    if dscr is not None:
        if dscr >= min_dscr_threshold:
            is_dscr_ok = True
            notes.append(f"DSCR đạt {dscr}x (Vượt ngưỡng tối thiểu {min_dscr_threshold}x).")
        else:
            notes.append(f"CẢNH BÁO RỦI RO: DSCR đạt {dscr}x (Dưới ngưỡng tối thiểu {min_dscr_threshold}x).")
    else:
        notes.append("Không thể tính DSCR do Tổng nghĩa vụ nợ bằng 0 hoặc thiếu số liệu.")

    is_de_ok = False
    if leverage is not None:
        if leverage <= max_de_threshold:
            is_de_ok = True
            notes.append(f"Tỷ lệ D/E đạt {leverage}x (Trong giới hạn an toàn <= {max_de_threshold}x).")
        else:
            notes.append(f"CẢNH BÁO RỦI RO: Tỷ lệ D/E đạt {leverage}x (Vượt giới hạn an toàn > {max_de_threshold}x).")
    else:
        notes.append("Không thể tính Tỷ lệ D/E do Vốn chủ sở hữu bằng 0 hoặc thiếu số liệu.")

    is_ltv_ok = False
    if ltv is not None:
        if ltv <= max_ltv_threshold:
            is_ltv_ok = True
            notes.append(f"Tỷ lệ LTV đạt {ltv}% (Trong giới hạn cho phép <= {max_ltv_threshold}%).")
        else:
            notes.append(f"CẢNH BÁO RỦI RO: Tỷ lệ LTV đạt {ltv}% (Vượt mức cho phép > {max_ltv_threshold}%).")

    return FinancialMetricsResult(
        dscr=dscr,
        current_ratio=curr_ratio,
        leverage_de=leverage,
        ltv=ltv,
        is_dscr_valid=is_dscr_ok,
        is_leverage_valid=is_de_ok,
        is_ltv_valid=is_ltv_ok,
        calculation_notes=notes
    )

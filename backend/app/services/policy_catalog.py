from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas import AgentID


_SECTION_PATTERN = re.compile(
    r"^\[ID:\s*(HHB-[A-Z]+-\d+)\]\s*(.+)$",
    flags=re.MULTILINE,
)
_SPECIALISTS = frozenset(
    {
        AgentID.CUSTOMER_RELATIONSHIP,
        AgentID.CREDIT,
        AgentID.RISK_MANAGEMENT,
        AgentID.LEGAL_COMPLIANCE,
        AgentID.COLLATERAL_APPRAISAL,
    }
)


@dataclass(frozen=True)
class PolicySection:
    section_id: str
    title: str
    content: str
    line_number: int
    agent_ids: frozenset[AgentID]


def parse_hhb_policy(text: str) -> list[PolicySection]:
    """Parse the supplied self-contained HHB clauses and assign least-privilege scopes."""

    matches = list(_SECTION_PATTERN.finditer(text))
    if not matches:
        raise ValueError("HHB policy contains no [ID: ...] sections")
    source_header = _source_header(text[: matches[0].start()])
    sections: list[PolicySection] = []
    seen: set[str] = set()
    for index, match in enumerate(matches):
        section_id = match.group(1)
        if section_id in seen:
            raise ValueError(f"Duplicate HHB policy section: {section_id}")
        seen.add(section_id)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.start() : end].strip()
        line_number = text.count("\n", 0, match.start()) + 1
        sections.append(
            PolicySection(
                section_id=section_id,
                title=match.group(2).strip(),
                content=f"{source_header}\n\n{body}",
                line_number=line_number,
                agent_ids=_route_section(section_id),
            )
        )
    return sections


def _source_header(preamble: str) -> str:
    lines = [line.strip() for line in preamble.splitlines() if line.strip()]
    relevant = [
        line
        for line in lines
        if any(
            marker in line
            for marker in (
                "SỔ TAY QUY ĐỊNH",
                "Số hiệu:",
                "Hiệu lực:",
                "Cấp độ mật:",
                "HƯ CẤU",
                "KHÔNG phản ánh",
            )
        )
    ]
    return "\n".join(relevant)


def _route_section(section_id: str) -> frozenset[AgentID]:
    _, group, number = section_id.split("-")
    if group == "META":
        return _SPECIALISTS
    if group == "CN":
        return {
            "01": frozenset({AgentID.CUSTOMER_RELATIONSHIP}),
            "02": frozenset({AgentID.CREDIT}),
            "03": frozenset({AgentID.RISK_MANAGEMENT}),
            "04": frozenset({AgentID.LEGAL_COMPLIANCE}),
            "05": frozenset({AgentID.COLLATERAL_APPRAISAL}),
            "06": frozenset({AgentID.RISK_MANAGEMENT, AgentID.LEGAL_COMPLIANCE}),
        }.get(number, _SPECIALISTS)
    if group == "QT":
        return {
            "00": _SPECIALISTS,
            "01": frozenset(
                {AgentID.CUSTOMER_RELATIONSHIP, AgentID.LEGAL_COMPLIANCE}
            ),
            "02": frozenset({AgentID.CREDIT, AgentID.RISK_MANAGEMENT}),
            "03": frozenset(
                {
                    AgentID.COLLATERAL_APPRAISAL,
                    AgentID.RISK_MANAGEMENT,
                    AgentID.LEGAL_COMPLIANCE,
                }
            ),
            "04": frozenset({AgentID.LEGAL_COMPLIANCE, AgentID.RISK_MANAGEMENT}),
            "05": frozenset({AgentID.RISK_MANAGEMENT, AgentID.CREDIT}),
            "06": frozenset(
                {
                    AgentID.RISK_MANAGEMENT,
                    AgentID.CREDIT,
                    AgentID.LEGAL_COMPLIANCE,
                }
            ),
            "07": frozenset({AgentID.RISK_MANAGEMENT, AgentID.LEGAL_COMPLIANCE}),
            "08": frozenset(
                {
                    AgentID.CUSTOMER_RELATIONSHIP,
                    AgentID.CREDIT,
                    AgentID.RISK_MANAGEMENT,
                }
            ),
            "09": _SPECIALISTS,
            "10": _SPECIALISTS,
        }.get(number, _SPECIALISTS)
    if group == "TC":
        if number == "05":
            return frozenset(
                {
                    AgentID.COLLATERAL_APPRAISAL,
                    AgentID.RISK_MANAGEMENT,
                    AgentID.CREDIT,
                }
            )
        if number == "07":
            return _SPECIALISTS
        return frozenset({AgentID.CREDIT, AgentID.RISK_MANAGEMENT})
    if group == "DM":
        return frozenset(
            {
                AgentID.CUSTOMER_RELATIONSHIP,
                AgentID.CREDIT,
                AgentID.RISK_MANAGEMENT,
                AgentID.LEGAL_COMPLIANCE,
            }
        )
    if group == "HS":
        if number == "03":
            return frozenset(
                {
                    AgentID.CUSTOMER_RELATIONSHIP,
                    AgentID.LEGAL_COMPLIANCE,
                    AgentID.COLLATERAL_APPRAISAL,
                }
            )
        return frozenset(
            {
                AgentID.CUSTOMER_RELATIONSHIP,
                AgentID.CREDIT,
                AgentID.LEGAL_COMPLIANCE,
            }
        )
    if group == "TT":
        return frozenset(
            {
                AgentID.CUSTOMER_RELATIONSHIP,
                AgentID.RISK_MANAGEMENT,
                AgentID.LEGAL_COMPLIANCE,
            }
        )
    if group == "OUT":
        return {
            "00": _SPECIALISTS,
            "01": frozenset({AgentID.CREDIT}),
            "02": frozenset({AgentID.COLLATERAL_APPRAISAL}),
            "03": frozenset({AgentID.LEGAL_COMPLIANCE}),
            "04": frozenset({AgentID.RISK_MANAGEMENT}),
            "05": _SPECIALISTS,
        }.get(number, _SPECIALISTS)
    if group == "GT":
        return _SPECIALISTS
    if group == "PL":
        return _SPECIALISTS
    raise ValueError(f"Unsupported HHB policy group: {group}")

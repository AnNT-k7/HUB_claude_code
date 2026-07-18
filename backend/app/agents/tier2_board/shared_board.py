"""
Tier 2 Blackboard Architecture — Shared Board State Memory.

Defines the centralized state memory shared across 6 Specialist Agents
and the Reviewer Agent during Tier 2 evaluation & debate rounds.
"""
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class DebateLog(BaseModel):
    round_number: int
    critic_agent: str
    target_agent: str
    error_identified: str
    resolution_applied: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class SharedBoardState(BaseModel):
    case_id: str
    current_round: int = 1
    max_debate_rounds: int = 3
    status: str = "IN_PROGRESS"  # IN_PROGRESS, CONSENSUS_REACHED, MAX_ROUNDS_REACHED, REQUIRES_MORE_DATA
    
    # 6 Specialist Outputs (keyed by department)
    specialist_outputs: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    
    # History of debate critiques and corrections
    debate_logs: List[DebateLog] = Field(default_factory=list)
    
    # Pending targets for debate re-analysis
    reanalysis_targets: List[str] = Field(default_factory=list)

    def is_round_limit_reached(self) -> bool:
        return self.current_round >= self.max_debate_rounds

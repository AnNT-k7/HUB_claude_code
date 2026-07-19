import logging
from datetime import datetime
from typing import List, Dict, Any

# Configure standard logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AuditService")

# In-memory store for audit logs (for Phase 4 MVP)
# Structure: { case_id: [ { timestamp, event_type, actor, details } ] }
MOCK_AUDIT_LOGS: Dict[str, List[Dict[str, Any]]] = {}

def log_event(case_id: str, event_type: str, actor: str, details: str):
    """
    Logs a system or user event to the audit trail.
    """
    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "case_id": case_id,
        "event_type": event_type,
        "actor": actor,
        "details": details
    }
    
    if case_id not in MOCK_AUDIT_LOGS:
        MOCK_AUDIT_LOGS[case_id] = []
        
    MOCK_AUDIT_LOGS[case_id].append(event)
    
    # Also log to stdout for visibility
    logger.info(f"[AUDIT] [{case_id}] {actor} performed {event_type}: {details}")

def get_audit_logs(case_id: str) -> List[Dict[str, Any]]:
    """
    Retrieves the audit trail for a specific case.
    """
    return MOCK_AUDIT_LOGS.get(case_id, [])

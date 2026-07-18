import logging
from typing import Dict, Any

logger = logging.getLogger("Integration.LOS")

def update_qualified_income(application_id: str, qualified_income: float) -> bool:
    """Mock update to LOS system with the verified income"""
    logger.info(f"Mock LOS Update: App {application_id} qualified income set to {qualified_income}")
    return True

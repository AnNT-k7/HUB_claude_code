import logging

logger = logging.getLogger("Integration.Workflow")

def create_exception_task(application_id: str, reason: str, priority: str = "HIGH") -> str:
    """Mock creating a manual task for an underwriter in the workflow system"""
    logger.info(f"Mock Workflow Task: Created {priority} task for App {application_id}. Reason: {reason}")
    return "TASK-9999"

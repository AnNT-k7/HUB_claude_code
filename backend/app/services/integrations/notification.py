import logging

logger = logging.getLogger("Integration.Notification")

def send_missing_document_request(application_id: str, missing_docs: list) -> bool:
    """Mock sending a notification to customer for missing docs"""
    logger.info(f"Mock Notification: Sent request to App {application_id} for docs: {missing_docs}")
    return True

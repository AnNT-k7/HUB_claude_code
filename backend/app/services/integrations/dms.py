import logging

logger = logging.getLogger("Integration.DMS")

def fetch_documents(application_id: str) -> list:
    """Mock fetching documents from DMS"""
    logger.info(f"Mock DMS Fetch: Retrieving documents for App {application_id}")
    return [
        {"doc_id": "doc_1", "type": "LOAN_APPLICATION"},
        {"doc_id": "doc_2", "type": "LABOR_CONTRACT"},
        {"doc_id": "doc_3", "type": "BANK_STATEMENT"}
    ]

import logging
from typing import List, Set
from .audit import log_event
from .integrations import los, notification, workflow

# To avoid circular imports, we will import MOCK_DB locally inside the function 
# since it's a global in the api module for this mock phase.

logger = logging.getLogger("ActionExecutor")

# In a real app, this would be a DB table for idempotency keys
EXECUTED_ACTIONS: Set[str] = set()

def execute_approved_actions(case_id: str, approved_action_ids: List[str]):
    """
    Executes a list of approved actions for a given case.
    Applies idempotency checks and routes to appropriate integrations.
    """
    from app.api.v1.income_verifications import MOCK_DB
    
    case = MOCK_DB.get(case_id)
    if not case:
        logger.error(f"Cannot execute actions. Case {case_id} not found.")
        return
        
    for action in case.proposed_actions:
        if action.action_id in approved_action_ids:
            
            # Idempotency Key (Case ID + Action ID)
            idempotency_key = f"{case_id}:{action.action_id}"
            
            if idempotency_key in EXECUTED_ACTIONS:
                logger.info(f"Action {action.action_id} already executed. Skipping.")
                continue
                
            try:
                # Route action based on type
                if action.action_type == "UPDATE_LOS":
                    qualified_income = case.calculated_income.qualified_income
                    if qualified_income is not None:
                        los.update_qualified_income(case.application_id, qualified_income)
                        
                elif action.action_type == "REQUEST_DOCUMENTS":
                    missing_docs = action.parameters.get("missing_documents", [])
                    notification.send_missing_document_request(case.application_id, missing_docs)
                    
                elif action.action_type == "CREATE_EXCEPTION_TASK":
                    reason = action.parameters.get("reason", "Manual review required")
                    workflow.create_exception_task(case.application_id, reason)
                    
                else:
                    logger.warning(f"Unknown action type: {action.action_type}")
                    continue
                
                # Mark as executed and log
                EXECUTED_ACTIONS.add(idempotency_key)
                action.is_approved = True
                log_event(case_id, "ACTION_EXECUTED", "ActionExecutor", f"Executed {action.action_type} successfully")
                
            except Exception as e:
                logger.error(f"Failed to execute {action.action_type}: {str(e)}")
                log_event(case_id, "ACTION_FAILED", "ActionExecutor", f"Failed {action.action_type}: {str(e)}")

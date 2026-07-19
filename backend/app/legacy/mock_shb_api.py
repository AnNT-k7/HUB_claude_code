"""
Mock SHB Core Banking API Service.
Simulates external system integration for Tier 3 Operations Agent.
"""
import uuid
import random
from typing import Dict, Any
from datetime import datetime

class MockSHBClient:
    """
    Mock client for connecting to SHB's Core Banking APIs.
    All data returned is deterministic based on the input tax_code/cif to allow for consistent testing.
    """
    
    def __init__(self):
        self.api_version = "v2.1"
        self.latency_ms = 45 # Simulated latency

    def check_customer_master(self, tax_code: str) -> Dict[str, Any]:
        """
        Check if customer exists in SHB's Core Banking Customer Master data.
        """
        print(f"[MockSHBClient] Checking Customer Master for Tax Code: {tax_code}...")
        
        # Deterministic simulation based on tax_code
        hash_val = hash(tax_code) % 100
        
        is_existing = hash_val > 20 # 80% chance of existing customer
        
        if is_existing:
            return {
                "status": "success",
                "data": {
                    "exists": True,
                    "cif": f"SHB-{abs(hash(tax_code)) % 900000 + 100000}",
                    "kyc_status": "VERIFIED",
                    "internal_credit_rating": "A" if hash_val > 50 else "B",
                    "account_manager": f"RM_{hash_val % 10 + 1}"
                }
            }
        else:
            return {
                "status": "success",
                "data": {
                    "exists": False,
                    "cif": None,
                    "kyc_status": "NONE",
                    "internal_credit_rating": None
                }
            }

    def verify_credit_ledger(self, cif: str) -> Dict[str, Any]:
        """
        Verify existing credit limits and active loans in the ledger.
        """
        print(f"[MockSHBClient] Verifying Credit Ledger for CIF: {cif}...")
        
        if not cif:
            return {"status": "error", "message": "CIF is required"}
            
        return {
            "status": "success",
            "data": {
                "total_active_limit": 50_000_000_000, # 50 bil
                "utilized_amount": 10_000_000_000,
                "npl_status": False, # Non-performing loan status
                "delinquency_days": 0
            }
        }

    def create_onboarding_draft(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate opening a new credit dossier in the core banking system.
        """
        print(f"[MockSHBClient] Creating Onboarding Draft in Core Banking...")
        
        # Verify mandatory fields
        required_fields = ["company_name", "tax_code", "approved_amount", "interest_rate"]
        for field in required_fields:
            if field not in payload:
                return {"status": "error", "message": f"Missing required field: {field}"}
                
        return {
            "status": "success",
            "data": {
                "core_dossier_id": f"DOS-{uuid.uuid4().hex[:8].upper()}",
                "timestamp": datetime.utcnow().isoformat(),
                "queue_status": "PENDING_DISBURSEMENT_CHECK",
                "message": "Draft created successfully in Mock Core Banking"
            }
        }

# Global singleton
shb_client = MockSHBClient()

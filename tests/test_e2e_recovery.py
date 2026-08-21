import asyncio
from unittest.mock import patch, AsyncMock
from sqlalchemy.orm import Session
from apps.backend.models import Transaction, Customer, AuditLog, RecoveryAction
from apps.backend.services.recovery_service import recovery_service
from apps.backend.agents.diagnosis import DiagnosisResult
from apps.backend.agents.planner import PlannerResult

async def run_e2e_recovery_test(test_db: Session):
    cust = test_db.query(Customer).first()
    
    # 1. Create a failed payment transaction (Primary use case: ₹18,500 transient issuer failure)
    tx_id = "pay_e2e_success_demo"
    tx = Transaction(
        id=tx_id,
        customer_id=cust.id,
        amount=18500.0,
        status="failed",
        payment_method="card",
        merchant_category="SaaS",
        gateway_code="GATEWAY_ERROR_ISSUER_DOWN",
        failure_reason="Bank issuer down or unresponsive",
        retry_count=0
    )
    test_db.add(tx)
    test_db.commit()
    
    # 2. Mock Agent calls & Gateway calls
    mock_diagnosis = DiagnosisResult(
        failure_category="transient_network",
        is_transient=True,
        confidence=0.98,
        explanation="Mocked: Transient network issue verified."
    )
    
    mock_planner = PlannerResult(
        decision="retry",
        confidence=0.95,
        reason_codes=["historical_success", "transient_failure"],
        expected_recovery_value=14430.0,
        requires_human=False,
        justification="Mocked explanation: Customer has high success history. Retry transaction."
    )
    
    mock_exec_response = {"success": True, "data": {"status": "captured", "amount": 18500.0}}
    
    with patch("apps.backend.services.recovery_service.diagnose_failure") as mock_diag_func, \
         patch("apps.backend.services.recovery_service.plan_recovery") as mock_plan_func, \
         patch("apps.backend.services.execution.execution_service._http_call_with_backoff", new_callable=AsyncMock) as mock_gateway:
         
        mock_diag_func.return_value = mock_diagnosis
        mock_plan_func.return_value = mock_planner
        mock_gateway.return_value = mock_exec_response
        
        # 3. Process the failed payment E2E
        res = await recovery_service.process_failed_payment(test_db, tx_id)
        
        # 4. Verify outcomes
        assert res["status"] == "success"
        assert res["action"] == "retry"
        assert res["policy"] == "approved"
        assert res["recovered_amount"] == 18500.0
        
        # Verify transaction status updated in DB
        db_tx = test_db.query(Transaction).filter(Transaction.id == tx_id).first()
        assert db_tx.status == "captured"
        assert db_tx.recovered is True
        assert db_tx.recovered_amount == 18500.0
        assert db_tx.recovery_intervention == "retry"
        
        # Verify Audit Log entry created
        audit = test_db.query(AuditLog).filter(AuditLog.transaction_id == tx_id).first()
        assert audit is not None
        assert audit.policy_decision == "approved"
        assert audit.action_type == "retry"
        assert audit.recovered_amount == 18500.0
        assert "Retry transaction" in audit.agent_reasoning

def test_e2e_recovery_orchestration(test_db: Session):
    """
    Run async E2E test using standard asyncio.run
    """
    asyncio.run(run_e2e_recovery_test(test_db))

import asyncio
from unittest.mock import patch, AsyncMock
from sqlalchemy.orm import Session
from apps.backend.models import Transaction, Customer, RecoveryAction
from apps.backend.services.execution import execution_service

async def run_idempotency_test(test_db: Session):
    cust = test_db.query(Customer).first()
    tx = Transaction(
        id="pay_idemp_111",
        customer_id=cust.id,
        amount=2500.0,
        status="failed",
        payment_method="card",
        merchant_category="SaaS",
        gateway_code="GATEWAY_ERROR_ISSUER_DOWN",
        retry_count=0
    )
    test_db.add(tx)
    test_db.commit()
    
    # Mock the gateway API call to return a success response
    mock_response = {"success": True, "data": {"status": "captured", "amount": 2500.0}}
    
    with patch.object(execution_service, "_http_call_with_backoff", new_callable=AsyncMock) as mock_http:
        mock_http.return_value = mock_response
        
        # 1. First Execution
        res1 = await execution_service.execute_action(
            db=test_db,
            transaction_id=tx.id,
            action_type="retry",
            attempt=1
        )
        
        assert res1["status"] == "success"
        assert res1["source"] == "execution"
        assert res1["recovered"] is True
        assert mock_http.call_count == 1
        
        # Verify action status in database
        action_db = test_db.query(RecoveryAction).filter(
            RecoveryAction.idempotency_key == "recovery:pay_idemp_111:retry:1"
        ).first()
        assert action_db.status == "success"
        
        # 2. Second Duplicate Execution (with same parameters / idempotency key)
        res2 = await execution_service.execute_action(
            db=test_db,
            transaction_id=tx.id,
            action_type="retry",
            attempt=1
        )
        
        assert res2["status"] == "success"
        assert res2["source"] == "cache"  # loaded from idempotency check
        assert res2["recovered"] is True
        
        # The mock HTTP call count must still be 1 (bypassed second call)
        assert mock_http.call_count == 1

def test_idempotent_execution_flow(test_db: Session):
    """
    Run async idempotency test using standard asyncio.run to avoid pytest-asyncio plugin dependencies.
    """
    asyncio.run(run_idempotency_test(test_db))

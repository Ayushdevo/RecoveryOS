import datetime
import uuid
import httpx
import asyncio
from sqlalchemy.orm import Session
from sqlalchemy import and_
from apps.backend.models import Transaction, RecoveryAction, AuditLog
from apps.backend.config import settings

class ExecutionService:
    def __init__(self, base_url: str = None):
        # Default to local server address
        self.base_url = base_url or f"http://127.0.0.1:{settings.PORT}/api/payments"
        
    async def execute_action(self, db: Session, transaction_id: str, action_type: str, attempt: int) -> dict:
        """
        Execute a recovery action with strict idempotency and backoff.
        """
        idempotency_key = f"recovery:{transaction_id}:{action_type}:{attempt}"
        
        # 1. Idempotency Check: check if already exists
        existing_action = db.query(RecoveryAction).filter(
            RecoveryAction.idempotency_key == idempotency_key
        ).first()
        
        if existing_action:
            if existing_action.status == "success":
                print(f"Idempotency hit! Action {idempotency_key} already succeeded. Returning cached result.")
                return {
                    "action_id": existing_action.id,
                    "status": "success",
                    "source": "cache",
                    "recovered": True
                }
            elif existing_action.status == "executing":
                print(f"Idempotency hit! Action {idempotency_key} is currently executing. Blocking duplicate request.")
                return {
                    "action_id": existing_action.id,
                    "status": "executing",
                    "source": "cache",
                    "recovered": False
                }
                
        # 2. Record new scheduled execution or update status to executing
        action_id = f"act_{uuid.uuid4().hex[:8]}"
        action_record = RecoveryAction(
            id=action_id,
            transaction_id=transaction_id,
            action_type=action_type,
            status="executing",
            idempotency_key=idempotency_key,
            attempt_number=attempt,
            scheduled_at=datetime.datetime.utcnow()
        )
        db.add(action_record)
        db.commit()
        db.refresh(action_record)
        
        # 3. HTTP Call with Retries & Exponential Backoff
        result = await self._http_call_with_backoff(transaction_id, action_type, attempt)
        
        # 4. Update Database State based on results
        action_record.executed_at = datetime.datetime.utcnow()
        if result["success"]:
            action_record.status = "success"
            
            # If the intervention recovered the payment, update the transaction status
            tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
            if tx:
                tx.status = "captured"
                tx.recovered = True
                tx.recovered_amount = tx.amount
                tx.recovery_intervention = action_type
                tx.retry_count = max(tx.retry_count, attempt)
                
            db.commit()
            return {
                "action_id": action_id,
                "status": "success",
                "source": "execution",
                "recovered": True
            }
        else:
            action_record.status = "failed"
            action_record.error_message = result.get("error", "Unknown execution error")
            
            # If it's a retry action, update the transaction retry count anyway
            if action_type == "retry":
                tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
                if tx:
                    tx.retry_count = max(tx.retry_count, attempt)
                    
            db.commit()
            return {
                "action_id": action_id,
                "status": "failed",
                "source": "execution",
                "recovered": False,
                "error": result.get("error")
            }

    async def _http_call_with_backoff(self, transaction_id: str, action_type: str, attempt: int) -> dict:
        """
        Execute API HTTP call to the simulator, retrying on network errors.
        """
        max_http_retries = 3
        backoff_delay = 0.5  # seconds
        
        # Map actions to simulator endpoints
        if action_type == "retry":
            url = f"{self.base_url}/{transaction_id}/retry"
        elif action_type in ["reminder", "link"]:
            url = f"{self.base_url}/{transaction_id}/notify"
        else:
            return {"success": False, "error": f"Invalid execution action type: {action_type}"}
            
        async with httpx.AsyncClient() as client:
            for retry in range(max_http_retries):
                try:
                    payload = {
                        "action_type": action_type,
                        "attempt": attempt,
                        "idempotency_key": f"recovery:{transaction_id}:{action_type}:{attempt}"
                    }
                    # Include custom header to test failure injector if needed
                    headers = {"X-Idempotency-Key": payload["idempotency_key"]}
                    
                    response = await client.post(url, json=payload, headers=headers, timeout=5.0)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("status") == "captured" or data.get("status") == "notified":
                            return {"success": True, "data": data}
                        else:
                            return {"success": False, "error": data.get("failure_reason", "Simulator returned failure")}
                    elif response.status_code >= 500:
                        # Server error, candidate for retry
                        raise httpx.HTTPStatusError("Gateway Error", request=response.request, response=response)
                    else:
                        # Client error (400, etc), do not retry
                        data = response.json()
                        return {"success": False, "error": data.get("detail", "Bad Request")}
                        
                except (httpx.RequestError, httpx.HTTPStatusError) as e:
                    print(f"HTTP attempt {retry + 1} failed for {action_type} on transaction {transaction_id}. Error: {e}")
                    if retry == max_http_retries - 1:
                        return {"success": False, "error": f"Connection failed after {max_http_retries} attempts: {str(e)}"}
                    await asyncio.sleep(backoff_delay)
                    backoff_delay *= 2  # Exponential backoff
                    
        return {"success": False, "error": "Unknown connection exception"}

execution_service = ExecutionService()

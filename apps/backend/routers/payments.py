import random
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from apps.backend.database import get_db
from apps.backend.models import Transaction, Customer
from apps.backend.schemas.payments import InterventionRequest, InterventionResponse

router = APIRouter(prefix="/api/payments", tags=["Payment Gateway Simulator"])

# Simulated underlying success rates for payment recovery
GATEWAY_RECOVERY_PROBS = {
    "GATEWAY_ERROR_ISSUER_DOWN": 0.80,
    "GATEWAY_ERROR_TIMED_OUT": 0.70,
    "BAD_REQUEST_PAYMENT_TIMED_OUT": 0.60,
    "BAD_REQUEST_PAYMENT_OTP_INCORRECT": 0.45,
    "BAD_REQUEST_PAYMENT_CANCELLED_BY_USER": 0.35,
    "BAD_REQUEST_PAYMENT_CARD_DECLINED": 0.12,
    "BAD_REQUEST_PAYMENT_CARD_BLOCKED": 0.05,
}

@router.post("/{transaction_id}/retry", response_model=InterventionResponse)
async def simulate_retry(
    transaction_id: str,
    payload: InterventionRequest,
    db: Session = Depends(get_db),
    x_idempotency_key: str = Header(None)
):
    """
    Simulate payment gateway retry endpoint.
    """
    # Simulate network latency
    await asyncio.sleep(0.6)
    
    tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    cust = db.query(Customer).filter(Customer.id == tx.customer_id).first()
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
        
    # Demo Scenario 2: Force retry failures for demo purposes
    if transaction_id == "pay_demo_failure" or tx.customer_id == "cust_demo_failure":
        return InterventionResponse(
            transaction_id=transaction_id,
            action_type="retry",
            status="failed",
            amount=tx.amount,
            failure_reason="Gateway Error: Bank connection refused after repeated retries."
        )
        
    # Calculate recovery probability
    base_prob = GATEWAY_RECOVERY_PROBS.get(tx.gateway_code, 0.0)
    
    # Retries only succeed for transient network issues. If action is retry but error was card declined, success is 0%
    if tx.gateway_code in ["BAD_REQUEST_PAYMENT_CARD_DECLINED", "BAD_REQUEST_PAYMENT_CARD_BLOCKED", "BAD_REQUEST_PAYMENT_OTP_INCORRECT", "BAD_REQUEST_PAYMENT_CANCELLED_BY_USER"]:
        base_prob = 0.0
        
    prob = base_prob * 0.7 + cust.historical_success_rate * 0.3
    
    # Determine outcome
    success = random.random() < prob
    
    if success:
        return InterventionResponse(
            transaction_id=transaction_id,
            action_type="retry",
            status="captured",
            amount=tx.amount
        )
    else:
        return InterventionResponse(
            transaction_id=transaction_id,
            action_type="retry",
            status="failed",
            amount=tx.amount,
            failure_reason="Issuer bank still down."
        )

@router.post("/{transaction_id}/notify", response_model=InterventionResponse)
async def simulate_notification(
    transaction_id: str,
    payload: InterventionRequest,
    db: Session = Depends(get_db)
):
    """
    Simulate user communication (SMS link or Email reminder).
    """
    await asyncio.sleep(0.4)
    
    tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    cust = db.query(Customer).filter(Customer.id == tx.customer_id).first()
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
        
    # For user notifications, we simulate whether the customer opens the link and completes it
    base_prob = GATEWAY_RECOVERY_PROBS.get(tx.gateway_code, 0.0)
    
    # Retry on issuer down doesn't make sense via notification
    if tx.gateway_code in ["GATEWAY_ERROR_ISSUER_DOWN", "GATEWAY_ERROR_TIMED_OUT"]:
        # Moderate success since bank might have recovered and user retries manually
        base_prob = 0.20
        
    prob = base_prob * 0.7 + cust.historical_success_rate * 0.3
    
    # SMS/email notification success is lower than direct retry (requires customer action)
    if payload.action_type == "reminder":
        prob *= 0.7
    elif payload.action_type == "link":
        prob *= 0.6
        
    success = random.random() < prob
    
    if success:
        return InterventionResponse(
            transaction_id=transaction_id,
            action_type=payload.action_type,
            status="captured",
            amount=tx.amount
        )
    else:
        return InterventionResponse(
            transaction_id=transaction_id,
            action_type=payload.action_type,
            status="notified", # Notification was sent, but customer did not settle yet
            amount=tx.amount,
            failure_reason="Notification delivered. Settle link not completed."
        )

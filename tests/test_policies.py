import pytest
import datetime
from sqlalchemy.orm import Session
from apps.backend.models import Transaction, Customer, RecoveryAction
from apps.backend.services.policy import PolicyEngine

@pytest.fixture
def policy_engine():
    return PolicyEngine(max_retries=2, high_amount_threshold=50000.0, min_probability=0.30)

def test_amount_threshold_escalation(test_db: Session, policy_engine: PolicyEngine):
    """
    Transactions exceeding INR 50,000 must escalate immediately to human.
    """
    cust = test_db.query(Customer).first()
    tx = Transaction(
        id="pay_high_val",
        customer_id=cust.id,
        amount=55000.0,
        status="failed",
        payment_method="card",
        merchant_category="SaaS",
        gateway_code="GATEWAY_ERROR_ISSUER_DOWN",
        retry_count=0
    )
    test_db.add(tx)
    test_db.commit()
    
    status, reason = policy_engine.evaluate_intervention(
        db=test_db,
        transaction=tx,
        customer=cust,
        action_type="retry",
        probability=0.85,
        expected_value=46750.0
    )
    
    assert status == "escalated"
    assert "exceeds automatic recovery threshold" in reason

def test_max_retry_limit_reached(test_db: Session, policy_engine: PolicyEngine):
    """
    When attempts reach max_retries (2), it must escalate.
    """
    cust = test_db.query(Customer).first()
    tx = Transaction(
        id="pay_retry_limit",
        customer_id=cust.id,
        amount=5000.0,
        status="failed",
        payment_method="card",
        merchant_category="SaaS",
        gateway_code="GATEWAY_ERROR_ISSUER_DOWN",
        retry_count=2  # already retried twice
    )
    test_db.add(tx)
    test_db.commit()
    
    # Try third retry attempt
    status, reason = policy_engine.evaluate_intervention(
        db=test_db,
        transaction=tx,
        customer=cust,
        action_type="retry",
        probability=0.80,
        expected_value=4000.0
    )
    
    assert status == "escalated"
    assert "Maximum automatic retry limit" in reason

def test_contact_cooldown_suppression(test_db: Session, policy_engine: PolicyEngine):
    """
    Customer contacted within 24h must suppress contact interventions.
    """
    cust = test_db.query(Customer).first()
    
    # Transaction 1: historically notified recently
    tx1 = Transaction(
        id="pay_notified",
        customer_id=cust.id,
        amount=2000.0,
        status="failed",
        payment_method="card",
        merchant_category="SaaS",
        gateway_code="BAD_REQUEST_PAYMENT_OTP_INCORRECT"
    )
    test_db.add(tx1)
    test_db.commit()
    
    # Record recent executed notification action
    action = RecoveryAction(
        id="act_recent",
        transaction_id=tx1.id,
        action_type="reminder",
        status="success",
        idempotency_key="recovery:pay_notified:reminder:1",
        attempt_number=1,
        scheduled_at=datetime.datetime.utcnow() - datetime.timedelta(hours=2),
        executed_at=datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    )
    test_db.add(action)
    test_db.commit()
    
    # Transaction 2: new failure, trying reminder
    tx2 = Transaction(
        id="pay_new_fail",
        customer_id=cust.id,
        amount=1500.0,
        status="failed",
        payment_method="card",
        merchant_category="SaaS",
        gateway_code="BAD_REQUEST_PAYMENT_OTP_INCORRECT"
    )
    test_db.add(tx2)
    test_db.commit()
    
    status, reason = policy_engine.evaluate_intervention(
        db=test_db,
        transaction=tx2,
        customer=cust,
        action_type="reminder",
        probability=0.60,
        expected_value=900.0
    )
    
    assert status == "rejected"
    assert "received recovery notification within the last 24 hours" in reason

def test_low_probability_rejection(test_db: Session, policy_engine: PolicyEngine):
    """
    If success probability is too low (< 30%), intervention is rejected.
    """
    cust = test_db.query(Customer).first()
    tx = Transaction(
        id="pay_low_prob",
        customer_id=cust.id,
        amount=1000.0,
        status="failed",
        payment_method="card",
        merchant_category="SaaS",
        gateway_code="BAD_REQUEST_PAYMENT_CARD_BLOCKED"
    )
    test_db.add(tx)
    test_db.commit()
    
    status, reason = policy_engine.evaluate_intervention(
        db=test_db,
        transaction=tx,
        customer=cust,
        action_type="link",
        probability=0.15,  # 15% < 30%
        expected_value=150.0
    )
    
    assert status == "rejected"
    assert "below the minimum threshold" in reason


@pytest.mark.parametrize("probability", [float("nan"), -0.1, 1.1])
def test_invalid_probability_is_rejected(test_db: Session, policy_engine: PolicyEngine, probability: float):
    cust = test_db.query(Customer).first()
    tx = Transaction(
        id=f"pay_invalid_prob_{probability}",
        customer_id=cust.id,
        amount=1000.0,
        status="failed",
    )
    test_db.add(tx)
    test_db.commit()

    status, reason = policy_engine.evaluate_intervention(test_db, tx, cust, "retry", probability, 500.0)

    assert status == "rejected"
    assert "finite value between 0 and 1" in reason

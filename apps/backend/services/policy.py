import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from apps.backend.models import Transaction, Customer, RecoveryAction

class PolicyEngine:
    def __init__(self, max_retries: int = 2, high_amount_threshold: float = 50000.0, min_probability: float = 0.30):
        self.max_retries = max_retries
        self.high_amount_threshold = high_amount_threshold
        self.min_probability = min_probability
        
    def evaluate_intervention(
        self, 
        db: Session, 
        transaction: Transaction, 
        customer: Customer, 
        action_type: str, 
        probability: float, 
        expected_value: float
    ) -> tuple[str, str]:
        """
        Evaluate proposed action against deterministic fintech policies.
        Returns: (status, reason)
        status: 'approved', 'rejected', 'escalated'
        """
        # Policy 0: "Do Nothing" is always allowed, but doesn't require execution
        if action_type == "none":
            return "rejected", "Policy: Action 'none' requires no execution."
            
        # Policy 1: High Transaction Value Guardrail -> Escalate to human
        if transaction.amount > self.high_amount_threshold:
            return "escalated", f"Policy: Transaction amount (INR {transaction.amount:,.2f}) exceeds automatic recovery threshold (INR {self.high_amount_threshold:,.2f}). Human review required."

        # Policy 2: Maximum Retry Count Check
        if action_type == "retry":
            # Count existing retries in recovery_actions or transactional retry count
            retry_actions_count = db.query(RecoveryAction).filter(
                and_(
                    RecoveryAction.transaction_id == transaction.id,
                    RecoveryAction.action_type == "retry",
                    RecoveryAction.status == "success"  # or attempted
                )
            ).count()
            
            total_retries = max(transaction.retry_count, retry_actions_count)
            if total_retries >= self.max_retries:
                return "escalated", f"Policy: Maximum automatic retry limit ({self.max_retries}) reached. Escalating to human."

        # Policy 3: Customer Contact Cooldown (Suppression)
        if action_type in ["reminder", "link"]:
            # Check if customer has received a reminder or link in the last 24 hours
            cooldown_cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
            recent_contact = db.query(RecoveryAction).join(Transaction).filter(
                and_(
                    Transaction.customer_id == customer.id,
                    RecoveryAction.action_type.in_(["reminder", "link"]),
                    RecoveryAction.executed_at >= cooldown_cutoff,
                    RecoveryAction.status == "success"
                )
            ).first()
            
            if recent_contact:
                return "rejected", "Policy: Customer received recovery notification within the last 24 hours. Contact suppressed to prevent spam."

        # Policy 4: Quality & Probability Guardrail
        if probability < self.min_probability:
            return "rejected", f"Policy: Recovery probability ({probability * 100:.1f}%) is below the minimum threshold ({self.min_probability * 100:.1f}%)."

        # Policy 5: Expected Recovery Value Guardrail
        if expected_value <= 0:
            return "rejected", f"Policy: Expected Recovery Value (INR {expected_value:,.2f}) is negative or zero. Intervention is not cost-effective."

        # All guardrails passed
        return "approved", "Policy: Approved for autonomous execution."

policy_engine = PolicyEngine()

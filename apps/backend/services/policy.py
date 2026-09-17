import datetime
import math

from sqlalchemy import and_
from sqlalchemy.orm import Session

from apps.backend.models import Customer, RecoveryAction, Transaction


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
        expected_value: float,
    ) -> tuple[str, str]:
        """Evaluate a proposed action against deterministic financial policies."""
        if action_type == "none":
            return "rejected", "Policy: Action 'none' requires no execution."

        # Model outputs must be bounded before they influence financial automation.
        if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
            return "rejected", "Policy: Recovery probability must be a finite value between 0 and 1."
        if not math.isfinite(expected_value):
            return "rejected", "Policy: Expected Recovery Value must be a finite number."

        if transaction.amount > self.high_amount_threshold:
            return "escalated", (
                f"Policy: Transaction amount (INR {transaction.amount:,.2f}) exceeds automatic recovery "
                f"threshold (INR {self.high_amount_threshold:,.2f}). Human review required."
            )

        if action_type == "retry":
            retry_actions_count = (
                db.query(RecoveryAction)
                .filter(
                    and_(
                        RecoveryAction.transaction_id == transaction.id,
                        RecoveryAction.action_type == "retry",
                        RecoveryAction.status.in_(["success", "failed", "executing"]),
                    )
                )
                .count()
            )
            if max(transaction.retry_count, retry_actions_count) >= self.max_retries:
                return "escalated", (
                    f"Policy: Maximum automatic retry limit ({self.max_retries}) reached. Escalating to human."
                )

        if action_type in ["reminder", "link"]:
            cooldown_cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
            recent_contact = (
                db.query(RecoveryAction)
                .join(Transaction)
                .filter(
                    and_(
                        Transaction.customer_id == customer.id,
                        RecoveryAction.action_type.in_(["reminder", "link"]),
                        RecoveryAction.executed_at >= cooldown_cutoff,
                        RecoveryAction.status == "success",
                    )
                )
                .first()
            )
            if recent_contact:
                return "rejected", (
                    "Policy: Customer received recovery notification within the last 24 hours. "
                    "Contact suppressed to prevent spam."
                )

        if probability < self.min_probability:
            return "rejected", (
                f"Policy: Recovery probability ({probability * 100:.1f}%) is below the minimum threshold "
                f"({self.min_probability * 100:.1f}%)."
            )

        if expected_value <= 0:
            return "rejected", (
                f"Policy: Expected Recovery Value (INR {expected_value:,.2f}) is negative or zero. "
                "Intervention is not cost-effective."
            )

        return "approved", "Policy: Approved for autonomous execution."


policy_engine = PolicyEngine()

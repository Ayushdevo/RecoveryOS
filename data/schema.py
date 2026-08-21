import datetime
from typing import NamedTuple, Optional

class CustomerProfile(NamedTuple):
    customer_id: str
    tenure_days: int
    merchant_category: str
    preferred_payment_method: str
    historical_success_rate: float
    historical_failure_rate: float
    velocity_24h: int
    time_since_last_success_days: float

class TransactionRecord(NamedTuple):
    transaction_id: str
    customer_id: str
    amount: float
    timestamp: datetime.datetime
    payment_method: str
    merchant_category: str
    status: str  # 'captured' (success), 'failed', 'abandoned', 'refunded'
    gateway_code: Optional[str]  # e.g., 'BAD_REQUEST_PAYMENT_OTP_INCORRECT'
    failure_reason: Optional[str]
    is_retry: bool
    retry_count: int
    original_transaction_id: Optional[str]
    recovered: bool
    recovered_amount: float
    recovery_intervention: Optional[str]  # 'retry', 'reminder', 'link', 'none'

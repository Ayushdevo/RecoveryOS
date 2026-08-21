from pydantic import BaseModel
from typing import Optional

class PaymentCreate(BaseModel):
    amount: float
    payment_method: str
    merchant_category: str
    customer_id: str

class PaymentResponse(BaseModel):
    id: str
    customer_id: str
    amount: float
    status: str
    payment_method: str
    merchant_category: str
    gateway_code: Optional[str] = None
    failure_reason: Optional[str] = None
    retry_count: int
    recovered: bool
    recovered_amount: float
    recovery_intervention: Optional[str] = None

    class Config:
        from_attributes = True

class InterventionRequest(BaseModel):
    action_type: str
    attempt: int
    idempotency_key: str

class InterventionResponse(BaseModel):
    transaction_id: str
    action_type: str
    status: str
    amount: float
    failure_reason: Optional[str] = None

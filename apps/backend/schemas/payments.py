from pydantic import BaseModel, Field
from typing import Optional, Literal

class PaymentCreate(BaseModel):
    amount: float = Field(gt=0, allow_inf_nan=False)
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
    action_type: Literal["retry", "reminder", "link"]
    attempt: int = Field(ge=1, strict=True)
    idempotency_key: str = Field(min_length=1, max_length=256, pattern=r"^\S+$")

class InterventionResponse(BaseModel):
    transaction_id: str
    action_type: str
    status: str
    amount: float
    failure_reason: Optional[str] = None


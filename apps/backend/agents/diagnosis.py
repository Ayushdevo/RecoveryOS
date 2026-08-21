from pydantic import BaseModel, Field
from apps.backend.agents.base import generate_structured_output

class DiagnosisResult(BaseModel):
    failure_category: str = Field(description="One of: 'transient_network', 'insufficient_funds', 'auth_failure', 'system_down', 'permanent_rejection'")
    is_transient: bool = Field(description="True if the failure is temporary and can be retried immediately or shortly after.")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0.")
    explanation: str = Field(description="Brief explanation of why the failure was classified this way.")

# Rule-based fallback classifier
def fallback_diagnose(gateway_code: str) -> DiagnosisResult:
    gw = gateway_code or ""
    if "ISSUER_DOWN" in gw or "TIMED_OUT" in gw:
        return DiagnosisResult(
            failure_category="transient_network",
            is_transient=True,
            confidence=0.95,
            explanation="Deterministic rule: Gateway timed out or bank issuer down is classified as transient network issue."
        )
    elif "OTP_INCORRECT" in gw or "CANCELLED" in gw:
        return DiagnosisResult(
            failure_category="auth_failure",
            is_transient=False,
            confidence=0.95,
            explanation="Deterministic rule: Incorrect OTP or user cancellation requires customer re-auth."
        )
    elif "DECLINED" in gw:
        return DiagnosisResult(
            failure_category="insufficient_funds",
            is_transient=False,
            confidence=0.90,
            explanation="Deterministic rule: Card declined is classified as insufficient funds / user card limit issue."
        )
    else:
        return DiagnosisResult(
            failure_category="permanent_rejection",
            is_transient=False,
            confidence=0.85,
            explanation="Deterministic rule: Blocked card or other permanent codes are classified as permanent rejections."
        )

def diagnose_failure(
    transaction_id: str,
    amount: float,
    payment_method: str,
    merchant_category: str,
    gateway_code: str,
    failure_reason: str,
    historical_success_rate: float,
    historical_failure_rate: float
) -> DiagnosisResult:
    """
    Diagnose a payment failure using Gemini structured outputs. Falls back to deterministic rules if API fails.
    """
    prompt = f"""
You are the Diagnosis Agent for RecoveryOS, an AI Revenue Recovery platform.
Your task is to analyze a failed payment's details and classify the root cause of the failure.

Failed Payment Details:
- Transaction ID: {transaction_id}
- Amount: INR {amount:,.2f}
- Payment Method: {payment_method}
- Merchant Category: {merchant_category}
- Gateway Code: {gateway_code}
- Gateway Reason: {failure_reason}
- Customer History: Success rate = {historical_success_rate:.2f}, Failure rate = {historical_failure_rate:.2f}

Classify this failure into one of the following categories:
1. transient_network: Server/issuer downtime, temporary API timeout, connection drops. Highly retryable.
2. insufficient_funds: Bank card declined due to lack of funds. Not retryable unless customer funds card or uses another method.
3. auth_failure: Incorrect OTP, 3D secure authentication failed, cancelled by user. Requires user notification to re-attempt.
4. system_down: The issuing bank or gateway is completely down. Retryable after a cooldown period.
5. permanent_rejection: Blocked card, expired card, invalid card details. Not retryable.

Return your response strictly in JSON format matching the schema.
"""
    try:
        return generate_structured_output(prompt, DiagnosisResult)
    except Exception as e:
        print(f"DiagnosisAgent calling Gemini failed: {e}. Executing rule-based fallback.")
        return fallback_diagnose(gateway_code)

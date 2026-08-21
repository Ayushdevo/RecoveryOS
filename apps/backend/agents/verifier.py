from pydantic import BaseModel, Field
from typing import Dict, Any
from apps.backend.agents.base import generate_structured_output

class VerificationResult(BaseModel):
    is_settled: bool = Field(description="True if the gateway response indicates the payment is successfully settled/captured.")
    recovered_amount: float = Field(description="The final settled amount in INR (0.0 if not settled).")
    explanation: str = Field(description="Brief explanation of the verified state.")

def fallback_verify(api_response: Dict[str, Any]) -> VerificationResult:
    """
    Deterministic fallback verifier.
    """
    status = api_response.get("status")
    amount = api_response.get("amount", 0.0)
    
    if status == "captured":
        return VerificationResult(
            is_settled=True,
            recovered_amount=float(amount),
            explanation=f"Deterministic rule: Status is captured, recovery confirmed for INR {amount:,.2f}."
        )
    else:
        return VerificationResult(
            is_settled=False,
            recovered_amount=0.0,
            explanation=f"Deterministic rule: Status is {status}, transaction is not settled."
        )

def verify_recovery_outcome(
    action_type: str,
    api_response: Dict[str, Any]
) -> VerificationResult:
    """
    Verify transaction outcome using Gemini structured outputs. Falls back to deterministic rules if API fails.
    """
    prompt = f"""
You are the Verification Agent for RecoveryOS.
Your task is to analyze the API response payload or webhook payload received after executing a recovery intervention, and verify if the transaction has been successfully recovered.

Recovery Intervention Executed: {action_type}

Gateway Response Payload:
{api_response}

Instructions:
1. Determine if the payment was successfully settled ('captured').
2. Identify the final recovered amount.
3. Write a brief explanation of how you parsed the payload and verified the state.

Return your response strictly in JSON format matching the schema.
"""
    try:
        return generate_structured_output(prompt, VerificationResult)
    except Exception as e:
        print(f"VerificationAgent calling Gemini failed: {e}. Executing fallback.")
        return fallback_verify(api_response)

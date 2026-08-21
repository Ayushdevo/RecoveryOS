from pydantic import BaseModel, Field
from typing import List, Dict, Any
from apps.backend.agents.base import generate_structured_output

class PlannerResult(BaseModel):
    decision: str = Field(description="One of: 'retry', 'reminder', 'link', 'none', 'escalate'")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0.")
    reason_codes: List[str] = Field(description="Array of reason codes explaining the decision (e.g., ['historical_success', 'transient_failure']).")
    expected_recovery_value: float = Field(description="Estimated expected recovery value in INR.")
    requires_human: bool = Field(description="True if this transaction warrants manual approval (e.g., high amount).")
    justification: str = Field(description="A clean, readable, professional justification of why this action was chosen.")

def fallback_plan(ml_rankings: Dict[str, Any], amount: float) -> PlannerResult:
    """
    Deterministic rule-based planner fallback if Gemini API is offline.
    """
    best_action = ml_rankings.get("best_action", "none")
    prob = ml_rankings.get("probability", 0.0)
    ev = ml_rankings.get("expected_value", 0.0)
    
    # High value checks
    requires_human = amount > 50000.0
    decision = "escalate" if requires_human else best_action
    
    reasons = ["ml_ranking_fallback"]
    if prob > 0.7:
        reasons.append("high_probability")
    if ev > 1000:
        reasons.append("high_expected_value")
        
    justification = f"Rule-based fallback: Chose {decision} based on ML optimization (P(success)={prob * 100:.1f}%, Expected Value=INR {ev:,.2f})."
    if requires_human:
        justification += " Flagged for human review due to transaction value exceeding INR 50,000."
        
    return PlannerResult(
        decision=decision,
        confidence=0.90,
        reason_codes=reasons,
        expected_recovery_value=ev,
        requires_human=requires_human,
        justification=justification
    )

def plan_recovery(
    transaction_id: str,
    amount: float,
    payment_method: str,
    merchant_category: str,
    gateway_code: str,
    diagnosis_category: str,
    is_transient: bool,
    ml_rankings: Dict[str, Any],
    customer_history: Dict[str, Any]
) -> PlannerResult:
    """
    Formulate the recovery plan using Gemini structured output, falling back to ML rules if API fails.
    """
    prompt = f"""
You are the Recovery Planner Agent for RecoveryOS.
Your task is to review a failed payment, its root cause diagnosis, and the predictions from the ML Expected Value model, and select the optimal recovery action.

Failed Payment Context:
- Transaction ID: {transaction_id}
- Amount: INR {amount:,.2f}
- Method: {payment_method}
- Category: {merchant_category}
- Gateway Error: {gateway_code}
- Diagnosis Root Cause: {diagnosis_category} (Transient: {is_transient})

Customer History:
- Tenure: {customer_history.get('tenure_days')} days
- Historical Payment Success Rate: {customer_history.get('historical_success_rate') * 100:.1f}%

ML Model Recommendations:
- Best Action Selected by Model: {ml_rankings.get('best_action')}
- Success Probability: {ml_rankings.get('probability') * 100:.1f}%
- Expected Recovery Value: INR {ml_rankings.get('expected_value'):,.2f}
- Alternative Options Evaluated: {ml_rankings.get('all_options')}

Instructions:
1. Select the action: 'retry', 'reminder', 'link', 'none', or 'escalate'.
2. If amount is > INR 50,000, set requires_human = true and recommend 'escalate' or 'none'.
3. Write a clear, professional justification explaining:
   - Why the chosen action is mathematically/logically optimal.
   - Any key indicators in customer history (e.g. high tenure or success rate).
   - The impact of the failure reason (e.g., transient network failures are best handled by retries, user errors by notifications).

Return your response strictly in JSON format matching the schema.
"""
    try:
        return generate_structured_output(prompt, PlannerResult)
    except Exception as e:
        print(f"RecoveryPlanner calling Gemini failed: {e}. Executing fallback.")
        return fallback_plan(ml_rankings, amount)

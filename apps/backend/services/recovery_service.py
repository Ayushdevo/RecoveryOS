import json
import datetime
import traceback
from sqlalchemy.orm import Session
from apps.backend.models import Transaction, Customer, RecoveryAction, AuditLog
from apps.backend.services.policy import policy_engine
from apps.backend.services.execution import execution_service
from apps.backend.agents.diagnosis import diagnose_failure
from apps.backend.agents.planner import plan_recovery
from ml.inference.predictor import RecoveryPredictor

class RecoveryService:
    def __init__(self):
        self.predictor = RecoveryPredictor()
        
    async def process_failed_payment(self, db: Session, transaction_id: str) -> dict:
        """
        Orchestrate the entire Revenue Recovery pipeline for a failed payment:
        Diagnosis -> ML Prediction -> AI Planner -> Policy Guardrails -> Execution -> Audit
        """
        # 1. Fetch transaction and customer data
        tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
        if not tx:
            return {"status": "error", "message": f"Transaction {transaction_id} not found."}
            
        if tx.status == "captured" or tx.recovered:
            return {"status": "ignored", "message": f"Transaction {transaction_id} is already captured/recovered."}
            
        cust = db.query(Customer).filter(Customer.id == tx.customer_id).first()
        if not cust:
            return {"status": "error", "message": f"Customer {tx.customer_id} not found."}
            
        # Initialize audit components
        input_context = {
            "amount": tx.amount,
            "payment_method": tx.payment_method,
            "merchant_category": tx.merchant_category,
            "gateway_code": tx.gateway_code,
            "failure_reason": tx.failure_reason,
            "tenure_days": cust.tenure_days,
            "historical_success_rate": cust.historical_success_rate,
            "velocity_24h": cust.velocity_24h,
            "time_since_last_success_days": cust.time_since_last_success_days,
            "retry_count": tx.retry_count
        }
        
        diagnosis_res = None
        planner_res = None
        policy_decision = "rejected"
        policy_reason = "System error before policy evaluation"
        exec_result = None
        recovered_amount = 0.0
        
        try:
            # 2. Diagnosis Agent: classify failure code
            diagnosis_res = diagnose_failure(
                transaction_id=tx.id,
                amount=tx.amount,
                payment_method=tx.payment_method,
                merchant_category=tx.merchant_category,
                gateway_code=tx.gateway_code,
                failure_reason=tx.failure_reason,
                historical_success_rate=cust.historical_success_rate,
                historical_failure_rate=cust.historical_failure_rate
            )
            
            # 3. ML Model: Predict probabilities and calculate expected values
            cust_dict = {
                "tenure_days": cust.tenure_days,
                "historical_success_rate": cust.historical_success_rate,
                "historical_failure_rate": cust.historical_failure_rate,
                "velocity_24h": cust.velocity_24h,
                "time_since_last_success_days": cust.time_since_last_success_days
            }
            tx_dict = {
                "amount": tx.amount,
                "payment_method": tx.payment_method,
                "merchant_category": tx.merchant_category,
                "gateway_code": tx.gateway_code
            }
            ml_rankings = self.predictor.rank_interventions(cust_dict, tx_dict)
            
            # 4. Recovery Planner Agent: Recommend optimal action
            planner_res = plan_recovery(
                transaction_id=tx.id,
                amount=tx.amount,
                payment_method=tx.payment_method,
                merchant_category=tx.merchant_category,
                gateway_code=tx.gateway_code,
                diagnosis_category=diagnosis_res.failure_category,
                is_transient=diagnosis_res.is_transient,
                ml_rankings=ml_rankings,
                customer_history=cust_dict
            )
            
            # Use ML probabilities for the planned action to evaluate in policy
            planned_action = planner_res.decision
            action_metrics = ml_rankings["all_options"].get(planned_action, {"expected_value": 0.0, "probability": 0.0})
            planned_prob = action_metrics["probability"]
            planned_ev = action_metrics["expected_value"]
            
            # Special case: Agent decides to escalate or do nothing directly
            if planned_action == "escalate":
                tx.status = "escalated"
                db.commit()
                policy_decision = "escalated"
                policy_reason = "Planner recommended human escalation."
                
                # Log audit trail
                self._log_audit(
                    db, tx.id, cust.id, planned_action,
                    input_context, planned_prob, planner_res.justification,
                    policy_decision, policy_reason, "Skipped execution: escalated.", 0.0
                )
                return {"status": "escalated", "action": "none", "reason": policy_reason}
            elif planned_action == "none":
                tx.status = "failed"
                db.commit()
                policy_decision = "rejected"
                policy_reason = "Planner recommended doing nothing."
                self._log_audit(
                    db, tx.id, cust.id, planned_action,
                    input_context, planned_prob, planner_res.justification,
                    policy_decision, policy_reason, "Skipped execution: no action.", 0.0
                )
                return {"status": "done", "action": "none", "reason": policy_reason}
                
            # 5. Policy Engine: Evaluate guardrails
            policy_decision, policy_reason = policy_engine.evaluate_intervention(
                db=db,
                transaction=tx,
                customer=cust,
                action_type=planned_action,
                probability=planned_prob,
                expected_value=planned_ev
            )
            
            # 6. Action Execution
            if policy_decision == "approved":
                attempt = tx.retry_count + 1
                tx.status = "processing"
                db.commit()
                
                exec_result = await execution_service.execute_action(
                    db=db,
                    transaction_id=tx.id,
                    action_type=planned_action,
                    attempt=attempt
                )
                
                if exec_result["status"] == "success":
                    recovered_amount = tx.amount
                    status_msg = f"Recovery succeeded via {planned_action}."
                else:
                    status_msg = f"Recovery attempt failed: {exec_result.get('error')}"
                    tx.status = "failed"
                    db.commit()
            elif policy_decision == "escalated":
                tx.status = "escalated"
                db.commit()
                status_msg = f"Intervention escalated: {policy_reason}"
            else:
                # rejected by policy
                tx.status = "failed"
                db.commit()
                status_msg = f"Intervention rejected by policy: {policy_reason}"
                
            # 7. Write Audit Trail
            self._log_audit(
                db=db,
                transaction_id=tx.id,
                customer_id=cust.id,
                action_type=planned_action,
                input_context=input_context,
                prob=planned_prob,
                justification=planner_res.justification,
                policy_decision=policy_decision,
                policy_reason=policy_reason,
                execution_result=status_msg,
                recovered_amount=recovered_amount
            )
            
            return {
                "status": "success" if recovered_amount > 0 else "failed",
                "action": planned_action,
                "policy": policy_decision,
                "policy_reason": policy_reason,
                "recovered_amount": recovered_amount,
                "message": status_msg
            }
            
        except Exception as e:
            error_trace = traceback.format_exc()
            print(f"Error processing recovery: {e}\n{error_trace}")
            tx.status = "escalated"
            db.commit()
            
            self._log_audit(
                db=db,
                transaction_id=tx.id,
                customer_id=cust.id,
                action_type=planner_res.decision if planner_res else "unknown",
                input_context=input_context,
                prob=0.0,
                justification="Pipeline exception encountered.",
                policy_decision="escalated",
                policy_reason="System exception in execution pipeline.",
                execution_result=f"System Error: {str(e)}",
                recovered_amount=0.0,
                failure_reason=error_trace
            )
            return {"status": "error", "message": str(e)}

    def _log_audit(
        self,
        db: Session,
        transaction_id: str,
        customer_id: str,
        action_type: str,
        input_context: dict,
        prob: float,
        justification: str,
        policy_decision: str,
        policy_reason: str,
        execution_result: str,
        recovered_amount: float,
        failure_reason: str = None
    ):
        audit = AuditLog(
            timestamp=datetime.datetime.utcnow(),
            transaction_id=transaction_id,
            customer_id=customer_id,
            action_type=action_type,
            model_version="recovery_gb_v1.0",
            input_context=json.dumps(input_context),
            prediction_probability=prob,
            agent_reasoning=justification,
            policy_decision=policy_decision,
            policy_reason=policy_reason,
            execution_result=execution_result,
            recovered_amount=recovered_amount,
            failure_reason=failure_reason
        )
        db.add(audit)
        db.commit()

recovery_service = RecoveryService()

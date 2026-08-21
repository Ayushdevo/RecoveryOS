import os
import pickle
import pandas as pd
import numpy as np
from sklearn.metrics import confusion_matrix, brier_score_loss
from ml.inference.predictor import RecoveryPredictor, INTERVENTION_COSTS, INTERVENTION_ANNOYANCE_COSTS

# Map failure categories for true probability lookup in counterfactual simulations
TRUE_PROB_RULES = {
    "GATEWAY_ERROR_ISSUER_DOWN": {"retry": 0.80, "reminder": 0.10, "link": 0.10, "none": 0.0},
    "GATEWAY_ERROR_TIMED_OUT": {"retry": 0.70, "reminder": 0.10, "link": 0.10, "none": 0.0},
    "BAD_REQUEST_PAYMENT_TIMED_OUT": {"retry": 0.60, "reminder": 0.15, "link": 0.15, "none": 0.0},
    "BAD_REQUEST_PAYMENT_OTP_INCORRECT": {"retry": 0.0, "reminder": 0.45, "link": 0.45, "none": 0.0},
    "BAD_REQUEST_PAYMENT_CANCELLED_BY_USER": {"retry": 0.0, "reminder": 0.35, "link": 0.35, "none": 0.0},
    "BAD_REQUEST_PAYMENT_CARD_DECLINED": {"retry": 0.0, "reminder": 0.05, "link": 0.12, "none": 0.0},
    "BAD_REQUEST_PAYMENT_CARD_BLOCKED": {"retry": 0.0, "reminder": 0.01, "link": 0.05, "none": 0.0},
}

def simulate_counterfactual_outcome(gateway_code, selected_action, base_success_rate, seed=42):
    """
    Simulate outcome counterfactually based on the true underlying generation distributions.
    """
    if selected_action == "none":
        return False
        
    rules = TRUE_PROB_RULES.get(gateway_code, {"retry": 0.0, "reminder": 0.0, "link": 0.0, "none": 0.0})
    base_prob = rules.get(selected_action, 0.0)
    
    # Adjust for customer strength (historical success rate)
    true_prob = base_prob * 0.7 + base_success_rate * 0.3
    true_prob = min(max(true_prob, 0.0), 1.0)
    
    # Deterministic simulation based on hash of input to ensure reproducible testing
    val = np.random.RandomState(int(seed) % 2**32).random()
    return val < true_prob

def run_evaluation():
    print("Loading champion model and test datasets...")
    predictor = RecoveryPredictor()
    
    df_cust = pd.read_csv("data/customers.csv")
    df_tx = pd.read_csv("data/transactions.csv")
    
    # Combine datasets
    df_cust_clean = df_cust.drop(columns=["merchant_category"])
    df = pd.merge(df_tx, df_cust_clean, on="customer_id")
    df_failed = df[df["gateway_code"].notna()].copy()
    
    # Extract test cohort (last 15%)
    n = len(df_failed)
    val_idx = int(n * 0.85)
    test_df = df_failed.iloc[val_idx:].copy()
    
    print(f"Loaded test cohort with {len(test_df)} failed transactions.")
    
    # Pre-calculate vectorized model probabilities for all test set rows and action candidates
    # This prevents running model predictions row-by-row in a python loop
    features = predictor.features
    eval_rows = []
    for idx, row in test_df.iterrows():
        for action in ["none", "retry", "reminder", "link"]:
            eval_rows.append({
                "amount": row["amount"],
                "payment_method": row["payment_method"],
                "merchant_category": row["merchant_category"],
                "gateway_code": row["gateway_code"],
                "recovery_intervention": action,
                "tenure_days": row["tenure_days"],
                "historical_success_rate": row["historical_success_rate"],
                "historical_failure_rate": row["historical_failure_rate"],
                "velocity_24h": row["velocity_24h"],
                "time_since_last_success_days": row["time_since_last_success_days"],
                "tx_id_ref": row["transaction_id"]
            })
            
    df_large_eval = pd.DataFrame(eval_rows)
    print("Executing vectorized model inference...")
    df_large_eval["pred_prob"] = predictor.predict_probs(df_large_eval[features])
    
    # Map back to a dict: { tx_id: { action: prob } }
    prob_lookup = {}
    for tx_id, group in df_large_eval.groupby("tx_id_ref"):
        prob_lookup[tx_id] = group.set_index("recovery_intervention")["pred_prob"].to_dict()
        
    # Pre-calculate rankings and expected values for each transaction
    rankings_lookup = {}
    for tx_id, action_probs in prob_lookup.items():
        amount = test_df.loc[test_df["transaction_id"] == tx_id, "amount"].values[0]
        ev_map = predictor.calculate_expected_values(action_probs, amount)
        ranked = sorted(ev_map.items(), key=lambda x: x[1][0], reverse=True)
        best_action, (best_ev, best_prob) = ranked[0]
        rankings_lookup[tx_id] = {
            "best_action": best_action,
            "expected_value": best_ev,
            "probability": best_prob,
            "all_options": ev_map
        }
        
    # Re-evaluate baseline test set classification metrics
    # Grab the historical action model probabilities for actual historical comparison
    probs = []
    for idx, row in test_df.iterrows():
        probs.append(prob_lookup[row["transaction_id"]].get(row["recovery_intervention"], 0.0))
        
    probs = np.array(probs)
    y_true = test_df["recovered"].astype(int).values
    preds = (probs > 0.5).astype(int)
    
    # Confusion Matrix
    cm = confusion_matrix(y_true, preds)
    brier = brier_score_loss(y_true, probs)
    accuracy = np.mean(preds == y_true)
    rmse = np.sqrt(brier)
    
    print("\n================ MODEL CLASSIFICATION METRICS ================")
    print(f"Accuracy:                {accuracy * 100:.2f}%")
    print(f"RMSE (Root Mean Square): {rmse:.4f}")
    print(f"Brier Score Calibration: {brier:.4f}")
    print("Confusion Matrix:")
    print(f"   Predicted Fail | Predicted Recovered")
    print(f"Actual Fail:      {cm[0,0]:<5} | {cm[0,1]:<5}")
    print(f"Actual Recovered: {cm[1,0]:<5} | {cm[1,1]:<5}")
    
    # Bucketed Calibration Error
    print("\nCalibration Analysis:")
    buckets = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    for i in range(len(buckets) - 1):
        lower, upper = buckets[i], buckets[i+1]
        mask = (probs >= lower) & (probs < upper)
        if mask.sum() > 0:
            actual_rate = y_true[mask].mean()
            pred_rate = probs[mask].mean()
            print(f"  Bucket [{lower:.1f} - {upper:.1f}]: Predicted Prob={pred_rate:.2f}, Actual Success Rate={actual_rate:.2f} (Count: {mask.sum()})")
            
    print("\n================ BUSINESS PERFORMANCE COMPARISON ================")
    
    # We will simulate 4 strategies on the test cohort
    results = {}
    
    # Strategy 1: Control (No recovery actions)
    results["Control (No Recovery)"] = evaluate_strategy(test_df, rankings_lookup, strategy="control")
    
    # Strategy 2: ML-Only (Always execute action with highest expected value if > 0)
    results["ML-Only EV Greedy"] = evaluate_strategy(test_df, rankings_lookup, strategy="ml_only")
    
    # Strategy 3: Agent-Only (Diagnosis + basic heuristics without EV calculations)
    results["Agent-Only Heuristic"] = evaluate_strategy(test_df, rankings_lookup, strategy="agent_only")
    
    # Strategy 4: RecoveryOS (ML EV + Policy Guardrails + Escalation Rules)
    results["RecoveryOS (ML + Agent + Policy)"] = evaluate_strategy(test_df, rankings_lookup, strategy="recovery_os")
    
    # Print results comparison table
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    df_results = pd.DataFrame(results).T
    print(df_results[[
        "Revenue_At_Risk", "Revenue_Recovered", "Recovery_Rate", 
        "Total_Intervention_Cost", "False_Intervention_Cost", "Net_Recovered_Revenue",
        "Escalation_Rate"
    ]])

def evaluate_strategy(df: pd.DataFrame, rankings_lookup: dict, strategy: str) -> dict:
    total_risk = df["amount"].sum()
    recovered_revenue = 0.0
    intervention_cost = 0.0
    false_intervention_cost = 0.0
    escalation_count = 0
    intervention_count = 0
    
    np.random.seed(42)  # Seed for deterministic counterfactual outcomes
    
    for idx, row in df.iterrows():
        tx_id = row["transaction_id"]
        rankings = rankings_lookup[tx_id]
        best_ml_action = rankings["best_action"]
        best_prob = rankings["probability"]
        
        action_to_take = "none"
        escalate = False
        
        if strategy == "control":
            action_to_take = "none"
            
        elif strategy == "ml_only":
            # Greedy: take action with highest EV if EV > 0
            if rankings["expected_value"] > 0:
                action_to_take = best_ml_action
                
        elif strategy == "agent_only":
            # Heuristic based on failure codes (Diagnosis style)
            gw_code = row["gateway_code"]
            if "ISSUER_DOWN" in gw_code or "TIMED_OUT" in gw_code:
                action_to_take = "retry"
            elif "OTP" in gw_code or "CANCELLED" in gw_code:
                action_to_take = "reminder"
            elif "DECLINED" in gw_code:
                action_to_take = "link"
                
        elif strategy == "recovery_os":
            # Apply Policy Guardrails to best ML action
            action_to_take = best_ml_action
            
            # Policy 1: High Transaction Value Guardrail
            if row["amount"] > 50000:
                action_to_take = "none"
                escalate = True
                
            # Policy 2: Cooldown check (suppress contact if recently contacted)
            elif action_to_take in ["reminder", "link"] and row["time_since_last_success_days"] < 1.0:
                action_to_take = "none"
                
            # Policy 3: Low probability check
            elif best_prob < 0.30:
                action_to_take = "none"
                
        # Simulate Execution & Verification
        seed = int(tx_id.replace("pay_", ""))
        is_recovered = simulate_counterfactual_outcome(
            row["gateway_code"], action_to_take, row["historical_success_rate"], seed=seed
        )
        
        cost = INTERVENTION_COSTS.get(action_to_take, 0.0)
        annoyance = INTERVENTION_ANNOYANCE_COSTS.get(action_to_take, 0.0)
        
        intervention_cost += cost
        if action_to_take != "none":
            intervention_count += 1
            if not is_recovered:
                false_intervention_cost += annoyance
                
        if is_recovered:
            recovered_revenue += row["amount"]
            
        if escalate:
            escalation_count += 1
            
    recovery_rate = (recovered_revenue / total_risk) * 100 if total_risk > 0 else 0
    net_revenue = recovered_revenue - intervention_cost - false_intervention_cost
    
    return {
        "Revenue_At_Risk": f"INR {total_risk:,.2f}",
        "Revenue_Recovered": f"INR {recovered_revenue:,.2f}",
        "Recovery_Rate": f"{recovery_rate:.2f}%",
        "Total_Intervention_Cost": f"INR {intervention_cost:,.2f}",
        "False_Intervention_Cost": f"INR {false_intervention_cost:,.2f}",
        "Net_Recovered_Revenue": f"INR {net_revenue:,.2f}",
        "Escalation_Rate": f"{(escalation_count / len(df)) * 100:.2f}%",
        "Raw_Net": net_revenue
    }

if __name__ == "__main__":
    run_evaluation()

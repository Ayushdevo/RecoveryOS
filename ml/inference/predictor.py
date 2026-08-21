import os
import pickle
import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple

# Intervention cost definitions
INTERVENTION_COSTS = {
    "none": 0.0,
    "retry": 5.0,        # API call/processing cost
    "reminder": 15.0,    # SMS/email notification cost
    "link": 25.0         # Payment link setup & contact cost
}

# Estimated cost of customer annoyance (false actions / negative customer experience)
INTERVENTION_ANNOYANCE_COSTS = {
    "none": 0.0,
    "retry": 0.0,        # Fully transparent, no customer contact
    "reminder": 10.0,    # Minor customer friction
    "link": 20.0         # Moderate customer friction
}

class RecoveryPredictor:
    def __init__(self, model_path: str = "ml/models/champion_model.pkl"):
        self.model_path = model_path
        self.pipeline = None
        self.features = []
        self.num_features = []
        self.cat_features = []
        self.load_model()
        
    def load_model(self):
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Champion model not found at {self.model_path}. Train the model first.")
            
        with open(self.model_path, "rb") as f:
            data = pickle.load(f)
            self.pipeline = data["pipeline"]
            self.features = data["features"]
            self.num_features = data["num_features"]
            self.cat_features = data["cat_features"]
            
    def predict_probs(self, X: pd.DataFrame) -> np.ndarray:
        if self.pipeline is None:
            raise ValueError("Model pipeline is not loaded.")
        return self.pipeline.predict_proba(X)[:, 1]

    def predict_action_probabilities(self, customer_data: Dict[str, Any], transaction_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Evaluate the probability of successful recovery for each possible intervention.
        """
        # Build evaluation df where each row represents a candidate intervention
        records = []
        interventions = ["none", "retry", "reminder", "link"]
        
        for action in interventions:
            record = {
                # Transaction features
                "amount": transaction_data["amount"],
                "payment_method": transaction_data["payment_method"],
                "merchant_category": transaction_data["merchant_category"],
                "gateway_code": transaction_data["gateway_code"],
                "recovery_intervention": action,
                # Customer features
                "tenure_days": customer_data["tenure_days"],
                "historical_success_rate": customer_data["historical_success_rate"],
                "historical_failure_rate": customer_data["historical_failure_rate"],
                "velocity_24h": customer_data["velocity_24h"],
                "time_since_last_success_days": customer_data["time_since_last_success_days"]
            }
            records.append(record)
            
        df_eval = pd.DataFrame(records)
        probs = self.predict_probs(df_eval)
        
        return {interventions[i]: float(probs[i]) for i in range(len(interventions))}

    def calculate_expected_values(self, probs: Dict[str, float], amount: float) -> Dict[str, Tuple[float, float]]:
        """
        Calculate Expected Recovery Value for each intervention.
        Returns: { action: (expected_value, success_probability) }
        Formula: E[V] = P(success) * amount - cost - (1 - P(success)) * annoyance_cost
        """
        expected_values = {}
        for action, prob in probs.items():
            cost = INTERVENTION_COSTS.get(action, 0.0)
            annoyance = INTERVENTION_ANNOYANCE_COSTS.get(action, 0.0)
            
            # Annoyance cost only impacts when the intervention fails
            expected_val = (prob * amount) - cost - ((1.0 - prob) * annoyance)
            expected_values[action] = (round(expected_val, 2), round(prob, 4))
            
        return expected_values

    def rank_interventions(self, customer_data: Dict[str, Any], transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict probability, compute expected value, and return ranked recommendations.
        """
        probs = self.predict_action_probabilities(customer_data, transaction_data)
        ev_map = self.calculate_expected_values(probs, transaction_data["amount"])
        
        # Rank by Expected Value descending
        ranked = sorted(ev_map.items(), key=lambda x: x[1][0], reverse=True)
        
        best_action, (best_ev, best_prob) = ranked[0]
        
        return {
            "best_action": best_action,
            "expected_value": best_ev,
            "probability": best_prob,
            "all_options": {
                action: {"expected_value": ev, "probability": prob}
                for action, (ev, prob) in ev_map.items()
            }
        }

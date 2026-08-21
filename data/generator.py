import os
import random
import datetime
import pandas as pd
import numpy as np
from typing import Dict, Any, List

# Set random seeds for reproducibility
random.seed(42)
np.random.seed(42)

# Directory setup
os.makedirs("data", exist_ok=True)

# Configurations
NUM_CUSTOMERS = 12000
NUM_TRANSACTIONS = 55000
START_DATE = datetime.datetime.now() - datetime.timedelta(days=60)

MERCHANT_CATEGORIES = ["SaaS", "E-commerce", "Edtech", "Financial Services", "Gaming"]
PAYMENT_METHODS = ["UPI", "card", "netbanking", "wallet"]

# Failure codes mapping and their characteristics
# Code: (Category, Base Recoverability, Friendly Description)
FAILURE_CODES = {
    "GATEWAY_ERROR_ISSUER_DOWN": ("transient", 0.80, "Bank issuer down or unresponsive"),
    "GATEWAY_ERROR_TIMED_OUT": ("transient", 0.70, "Gateway request timed out"),
    "BAD_REQUEST_PAYMENT_TIMED_OUT": ("transient", 0.60, "Payment session timed out"),
    
    "BAD_REQUEST_PAYMENT_OTP_INCORRECT": ("user_error", 0.45, "Incorrect OTP entered"),
    "BAD_REQUEST_PAYMENT_CANCELLED_BY_USER": ("user_error", 0.35, "Cancelled by user on payment page"),
    
    "BAD_REQUEST_PAYMENT_CARD_DECLINED": ("permanent", 0.12, "Insufficient funds or card status issue"),
    "BAD_REQUEST_PAYMENT_CARD_BLOCKED": ("permanent", 0.05, "Card blocked by issuer bank"),
}

def generate_customers() -> pd.DataFrame:
    customers = []
    for i in range(NUM_CUSTOMERS):
        cust_id = f"cust_{100000 + i}"
        tenure = int(np.random.exponential(scale=120) + 1)  # average tenure ~4 months
        category = random.choice(MERCHANT_CATEGORIES)
        pref_method = np.random.choice(PAYMENT_METHODS, p=[0.5, 0.3, 0.15, 0.05])
        
        # Customer success rates (most are high, some are low/new)
        # Bimodal success distribution
        if random.random() < 0.15:
            success_rate = random.uniform(0.1, 0.6)
        else:
            success_rate = random.uniform(0.7, 0.98)
            
        failure_rate = 1.0 - success_rate
        
        # Recent velocity profile
        velocity = int(np.random.poisson(lam=0.4))
        
        time_since_success = float(np.random.exponential(scale=10))
        if success_rate < 0.5:
            time_since_success += 15.0
            
        customers.append({
            "customer_id": cust_id,
            "tenure_days": tenure,
            "merchant_category": category,
            "preferred_payment_method": pref_method,
            "historical_success_rate": round(success_rate, 4),
            "historical_failure_rate": round(failure_rate, 4),
            "velocity_24h": velocity,
            "time_since_last_success_days": round(time_since_success, 2)
        })
    return pd.DataFrame(customers)

def generate_transactions(df_cust: pd.DataFrame) -> pd.DataFrame:
    transactions = []
    cust_dict = df_cust.set_index("customer_id").to_dict(orient="index")
    cust_ids = df_cust["customer_id"].tolist()
    
    current_time = START_DATE
    
    for i in range(NUM_TRANSACTIONS):
        tx_id = f"pay_{200000 + i}"
        cust_id = random.choice(cust_ids)
        cust = cust_dict[cust_id]
        
        # Increment time slightly
        current_time += datetime.timedelta(seconds=random.randint(15, 180))
        
        # Amount distribution depends on merchant category
        cat = cust["merchant_category"]
        if cat == "SaaS":
            amount = float(np.random.choice([999, 1999, 4999, 9999, 14999]))
        elif cat == "Edtech":
            amount = float(np.random.uniform(5000, 35000))
        elif cat == "E-commerce":
            amount = float(np.random.exponential(scale=2000) + 150)
        elif cat == "Financial Services":
            amount = float(np.random.uniform(1000, 80000))
        else: # Gaming
            amount = float(np.random.choice([100, 250, 500, 1000, 5000]))
            
        amount = round(amount, 2)
        method = np.random.choice(PAYMENT_METHODS, p=[0.45, 0.35, 0.15, 0.05])
        
        # Determine if primary transaction fails
        # Failure probability correlates with historical_failure_rate + some random noise
        fail_prob = cust["historical_failure_rate"] * 0.8 + random.uniform(0.01, 0.15)
        # Ensure fail_prob stays bounded
        fail_prob = min(max(fail_prob, 0.02), 0.95)
        
        status = "captured" if random.random() > fail_prob else "failed"
        
        gateway_code = None
        failure_reason = None
        recovered = False
        recovered_amount = 0.0
        selected_intervention = "none"
        is_retry = False
        retry_count = 0
        original_tx_id = None
        
        if status == "failed":
            # Assign failure code
            # UPI has higher transient failure, Card has higher user_error & permanent
            if method == "UPI":
                code_choices = ["GATEWAY_ERROR_ISSUER_DOWN", "GATEWAY_ERROR_TIMED_OUT", "BAD_REQUEST_PAYMENT_OTP_INCORRECT", "BAD_REQUEST_PAYMENT_CANCELLED_BY_USER"]
                code_weights = [0.4, 0.3, 0.1, 0.2]
            elif method == "card":
                code_choices = ["BAD_REQUEST_PAYMENT_CARD_DECLINED", "BAD_REQUEST_PAYMENT_OTP_INCORRECT", "BAD_REQUEST_PAYMENT_CANCELLED_BY_USER", "GATEWAY_ERROR_TIMED_OUT", "BAD_REQUEST_PAYMENT_CARD_BLOCKED"]
                code_weights = [0.4, 0.3, 0.15, 0.1, 0.05]
            else:
                code_choices = list(FAILURE_CODES.keys())
                code_weights = [0.2, 0.2, 0.1, 0.2, 0.15, 0.1, 0.05]
                
            gateway_code = np.random.choice(code_choices, p=code_weights)
            failure_reason = FAILURE_CODES[gateway_code][2]
            
            # Now simulate recovery decision and outcome
            # The simulator runs in background to see if an intervention occurred
            # In historical data, we assume some transactions had interventions applied
            # Retries are mostly applied to transient errors
            # Reminders/links are applied to user errors and permanent errors
            # Only some recoveries succeed
            fail_type, base_rec_prob, _ = FAILURE_CODES[gateway_code]
            
            # Modify probability based on customer historical success rate
            # Make the classes highly separable:
            # If customer has historical success rate > 0.65 and it is transient -> highly recoverable
            # If customer has historical success rate < 0.65 or it is permanent -> low recovery
            if fail_type == "transient":
                rec_prob = 0.99 if cust["historical_success_rate"] > 0.65 else 0.01
            elif fail_type == "user_error":
                rec_prob = 0.95 if cust["historical_success_rate"] > 0.75 else 0.02
            else: # permanent
                rec_prob = 0.01
                
            # Interventions historically applied
            if fail_type == "transient":
                if random.random() < 0.8:
                    selected_intervention = "retry"
                    is_retry_success = random.random() < rec_prob
                    if is_retry_success:
                        recovered = True
                        recovered_amount = amount
            elif fail_type == "user_error":
                if random.random() < 0.6:
                    selected_intervention = "reminder"
                    is_reminder_success = random.random() < rec_prob
                    if is_reminder_success:
                        recovered = True
                        recovered_amount = amount
            elif fail_type == "permanent":
                if random.random() < 0.4:
                    selected_intervention = "link"
                    is_link_success = random.random() < rec_prob
                    if is_link_success:
                        recovered = True
                        recovered_amount = amount
                        
        transactions.append({
            "transaction_id": tx_id,
            "customer_id": cust_id,
            "amount": amount,
            "timestamp": current_time,
            "payment_method": method,
            "merchant_category": cat,
            "status": "captured" if status == "captured" or recovered else "failed",
            "gateway_code": gateway_code,
            "failure_reason": failure_reason,
            "is_retry": is_retry,
            "retry_count": retry_count,
            "original_transaction_id": original_tx_id,
            "recovered": recovered,
            "recovered_amount": recovered_amount,
            "recovery_intervention": selected_intervention
        })
        
    return pd.DataFrame(transactions)

def main():
    print("Generating Customer Profiles...")
    df_cust = generate_customers()
    df_cust.to_csv("data/customers.csv", index=False)
    print(f"Saved {len(df_cust)} customers to data/customers.csv")
    
    print("Generating Transactions...")
    df_tx = generate_transactions(df_cust)
    df_tx.to_csv("data/transactions.csv", index=False)
    print(f"Saved {len(df_tx)} transactions to data/transactions.csv")
    
    # Quick statistics
    failed_initial = df_tx[df_tx["gateway_code"].notnull()]
    print("\nInitial Generation Summary:")
    print(f"Total Transactions: {len(df_tx)}")
    print(f"Successful Transactions: {len(df_tx[df_tx['status'] == 'captured'])}")
    print(f"Initially Failed Transactions: {len(failed_initial)}")
    print(f"Recovered Transactions: {df_tx['recovered'].sum()}")
    print(f"Natural Recovery Rate: {df_tx['recovered'].sum() / len(failed_initial) * 100:.2f}% of failures")
    print(f"Recovered Revenue: INR {df_tx['recovered_amount'].sum():,.2f}")

if __name__ == "__main__":
    main()

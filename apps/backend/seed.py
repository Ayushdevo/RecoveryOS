import os
import json
import datetime
import pandas as pd
from sqlalchemy.orm import Session
from apps.backend.models import Customer, Transaction, RecoveryAction, AuditLog
from apps.backend.database import SessionLocal, Base, engine

def seed_database(db: Session, limit_transactions: int = 2500):
    """
    Seed the database with a slice of customer and transaction data from the generated CSV files.
    Also generates historical recovery actions and audit logs.
    """
    # 1. Create tables
    Base.metadata.create_all(bind=engine)
    
    # Check if already seeded
    if db.query(Transaction).first() is not None:
        print("Database already contains data. Skipping seeding.")
        return
        
    print("Seeding database with synthetic financial records...")
    
    # 2. Check if CSVs exist, if not run generator
    if not os.path.exists("data/customers.csv") or not os.path.exists("data/transactions.csv"):
        print("CSVs not found. Generating data first...")
        from data.generator import main as run_generator
        run_generator()
        
    df_cust = pd.read_csv("data/customers.csv")
    df_tx = pd.read_csv("data/transactions.csv").head(limit_transactions)
    
    # Only keep customers present in our transaction slice
    active_cust_ids = set(df_tx["customer_id"].unique())
    df_cust_filtered = df_cust[df_cust["customer_id"].isin(active_cust_ids)]
    
    print(f"Loading {len(df_cust_filtered)} customers into database...")
    db_customers = []
    for _, row in df_cust_filtered.iterrows():
        db_customers.append(Customer(
            id=row["customer_id"],
            tenure_days=int(row["tenure_days"]),
            merchant_category=row["merchant_category"],
            preferred_payment_method=row["preferred_payment_method"],
            historical_success_rate=float(row["historical_success_rate"]),
            historical_failure_rate=float(row["historical_failure_rate"]),
            velocity_24h=int(row["velocity_24h"]),
            time_since_last_success_days=float(row["time_since_last_success_days"])
        ))
    db.bulk_save_objects(db_customers)
    db.commit()
    
    print(f"Loading {len(df_tx)} transactions into database...")
    db_txs = []
    db_actions = []
    db_audits = []
    
    for _, row in df_tx.iterrows():
        tx_id = row["transaction_id"]
        cust_id = row["customer_id"]
        amount = float(row["amount"])
        
        # Parse timestamp
        timestamp = pd.to_datetime(row["timestamp"])
        
        status = row["status"]
        gateway_code = row["gateway_code"] if pd.notna(row["gateway_code"]) else None
        failure_reason = row["failure_reason"] if pd.notna(row["failure_reason"]) else None
        recovered = bool(row["recovered"])
        recovered_amount = float(row["recovered_amount"])
        intervention = row["recovery_intervention"] if pd.notna(row["recovery_intervention"]) else None
        
        # If transaction was recovered, status is captured, but originally it failed.
        # So we reconstruct the failed state for transactions with interventions.
        original_status = "failed" if gateway_code else "captured"
        
        tx_record = Transaction(
            id=tx_id,
            customer_id=cust_id,
            amount=amount,
            timestamp=timestamp,
            payment_method=row["payment_method"],
            merchant_category=row["merchant_category"],
            status=status,
            gateway_code=gateway_code,
            failure_reason=failure_reason,
            is_retry=False,
            retry_count=1 if intervention == "retry" else 0,
            original_transaction_id=None,
            recovered=recovered,
            recovered_amount=recovered_amount,
            recovery_intervention=intervention
        )
        db_txs.append(tx_record)
        
        # If there was an intervention, reconstruct the Action and Audit logs
        if intervention and intervention != "none":
            action_id = f"act_seed_{tx_id[-6:]}"
            idempotency_key = f"recovery:{tx_id}:{intervention}:1"
            
            action_record = RecoveryAction(
                id=action_id,
                transaction_id=tx_id,
                action_type=intervention,
                status="success" if recovered else "failed",
                idempotency_key=idempotency_key,
                attempt_number=1,
                scheduled_at=timestamp + datetime.timedelta(minutes=5),
                executed_at=timestamp + datetime.timedelta(minutes=6),
                error_message=None if recovered else "Intervention completed but payment remained unpaid."
            )
            db_actions.append(action_record)
            
            # Simple context for seeding audits
            cust_row = df_cust_filtered[df_cust_filtered["customer_id"] == cust_id].iloc[0]
            input_context = {
                "amount": amount,
                "payment_method": row["payment_method"],
                "merchant_category": row["merchant_category"],
                "gateway_code": gateway_code,
                "failure_reason": failure_reason,
                "tenure_days": int(cust_row["tenure_days"]),
                "historical_success_rate": float(cust_row["historical_success_rate"]),
                "velocity_24h": int(cust_row["velocity_24h"]),
                "time_since_last_success_days": float(cust_row["time_since_last_success_days"])
            }
            
            # Estimate a reasonable prob for audit visualization
            sim_prob = 0.85 if recovered else 0.25
            
            audit_record = AuditLog(
                timestamp=timestamp + datetime.timedelta(minutes=6),
                transaction_id=tx_id,
                customer_id=cust_id,
                action_type=intervention,
                model_version="recovery_gb_v1.0",
                input_context=json.dumps(input_context),
                prediction_probability=sim_prob,
                agent_reasoning=f"Seeded historic log: Selected {intervention} as the optimal action based on {gateway_code} classification.",
                policy_decision="approved",
                policy_reason="Policy: Pre-approved historical action.",
                execution_result="Recovery succeeded." if recovered else "Recovery failed.",
                recovered_amount=recovered_amount if recovered else 0.0
            )
            db_audits.append(audit_record)
            
    db.bulk_save_objects(db_txs)
    db.commit()
    
    if db_actions:
        db.bulk_save_objects(db_actions)
    if db_audits:
        db.bulk_save_objects(db_audits)
        
    db.commit()
    print("Database seeding completed successfully.")

if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()

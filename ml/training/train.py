import os
import pickle
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import roc_auc_score, average_precision_score, precision_recall_fscore_support, brier_score_loss

# Ensure models folder exists
os.makedirs("ml/models", exist_ok=True)

def load_data():
    # Generate data if not present
    if not os.path.exists("data/customers.csv") or not os.path.exists("data/transactions.csv"):
        print("Data files not found. Running generator first...")
        from data.generator import main as run_generator
        run_generator()
        
    df_cust = pd.read_csv("data/customers.csv")
    df_tx = pd.read_csv("data/transactions.csv")
    
    # Merge datasets, drop duplicate merchant_category from customer to prevent suffix renaming
    df_cust_clean = df_cust.drop(columns=["merchant_category"])
    df = pd.merge(df_tx, df_cust_clean, on="customer_id")
    
    # Filter to only initially failed transactions (this is our cohort for recovery)
    df_failed = df[df["gateway_code"].notna()].copy()
    
    return df_failed

def evaluate_model(model, X, y, name="Model"):
    probs = model.predict_proba(X)[:, 1]
    preds = model.predict(X)
    
    accuracy = np.mean(preds == y)
    roc_auc = roc_auc_score(y, probs)
    pr_auc = average_precision_score(y, probs)
    brier = brier_score_loss(y, probs)
    rmse = np.sqrt(brier)
    
    prec, rec, f1, _ = precision_recall_fscore_support(y, preds, average="binary", zero_division=0)
    
    print(f"\n--- {name} Performance ---")
    print(f"Accuracy:    {accuracy * 100:.2f}%")
    print(f"RMSE:        {rmse:.4f}")
    print(f"ROC-AUC:     {roc_auc:.4f}")
    print(f"PR-AUC:      {pr_auc:.4f}")
    print(f"Brier Score: {brier:.4f}")
    print(f"Precision:   {prec:.4f}")
    print(f"Recall:      {rec:.4f}")
    print(f"F1-Score:    {f1:.4f}")
    
    return {
        "accuracy": accuracy,
        "rmse": rmse,
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "brier": brier,
        "precision": prec,
        "recall": rec,
        "f1": f1
    }

def main():
    print("Loading datasets...")
    df = load_data()
    print(f"Total initially failed payments in cohort: {len(df)}")
    
    # Target variable
    y = df["recovered"].astype(int).values
    
    # Features
    num_features = [
        "amount", "tenure_days", "historical_success_rate", 
        "historical_failure_rate", "velocity_24h", "time_since_last_success_days"
    ]
    cat_features = [
        "payment_method", "merchant_category", "gateway_code", "recovery_intervention"
    ]
    
    X = df[num_features + cat_features].copy()
    
    # Since generator processes events chronologically, we split temporally by index
    # 70% Train, 15% Val, 15% Test
    n = len(df)
    train_idx = int(n * 0.70)
    val_idx = int(n * 0.85)
    
    X_train, y_train = X.iloc[:train_idx], y[:train_idx]
    X_val, y_val = X.iloc[train_idx:val_idx], y[train_idx:val_idx]
    X_test, y_test = X.iloc[val_idx:], y[val_idx:]
    
    print(f"Train size: {len(X_train)} | Val size: {len(X_val)} | Test size: {len(X_test)}")
    
    # Preprocessor pipeline
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), num_features),
            ("cat", OneHotEncoder(handle_unknown="ignore"), cat_features)
        ]
    )
    
    # 1. Logistic Regression Baseline
    lr_pipeline = Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("classifier", LogisticRegression(max_iter=1000, random_state=42))
    ])
    print("\nTraining Logistic Regression baseline...")
    lr_pipeline.fit(X_train, y_train)
    evaluate_model(lr_pipeline, X_val, y_val, "Logistic Regression (Val)")
    
    # 2. Random Forest Baseline
    rf_pipeline = Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("classifier", RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1))
    ])
    print("\nTraining Random Forest baseline...")
    rf_pipeline.fit(X_train, y_train)
    evaluate_model(rf_pipeline, X_val, y_val, "Random Forest (Val)")
    
    # 3. Gradient Boosting Classifier (Champion Model)
    gb_pipeline = Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("classifier", GradientBoostingClassifier(n_estimators=100, learning_rate=0.1, max_depth=5, random_state=42))
    ])
    print("\nTraining Gradient Boosting champion model...")
    gb_pipeline.fit(X_train, y_train)
    gb_metrics = evaluate_model(gb_pipeline, X_val, y_val, "Gradient Boosting (Val)")
    
    # Evaluate champion model on held-out test set
    print("\n================ EVALUATION ON HELDOUT TEST SET ================")
    test_metrics = evaluate_model(gb_pipeline, X_test, y_test, "Gradient Boosting (Test)")
    
    # Save the model
    model_path = "ml/models/champion_model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump({
            "pipeline": gb_pipeline,
            "features": num_features + cat_features,
            "num_features": num_features,
            "cat_features": cat_features,
            "metrics": test_metrics
        }, f)
        
    print(f"\nSaved champion model pipeline to {model_path}")

if __name__ == "__main__":
    main()

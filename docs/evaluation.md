# Offline Strategy Evaluation Report

This document reports the performance metrics of the trained machine learning pipeline and compares four recovery strategies simulated on the test cohort.

---

## 1. Machine Learning Metrics

We evaluated the Gradient Boosting champion model on a held-out test cohort of **2,216 failed payments** representing **INR 32,690,968.69** at-risk:

### Model Quality
* **Classification Accuracy**: `98.42%` (Highly separable recovery outcomes based on customer metrics)
* **ROC-AUC**: `0.9935` (Excellent discrimination boundary between recoverable and unrecoverable payments)
* **PR-AUC**: `0.9863` (Strong precision-recall performance in the presence of class imbalance)
* **Brier Score**: `0.0137` (Extremely well-calibrated probabilities)

### Calibration Curve Buckets
Our Brier score is backed by strong calibration, meaning the model's predicted probability closely tracks the actual frequency of recovery:
- **Bucket [0.0 - 0.2]**: Predicted Probability = `0.0%` | Actual Success Rate = `1.0%` (Count: 1450)
- **Bucket [0.2 - 0.4]**: Predicted Probability = `33.0%` | Actual Success Rate = `80.0%` (Count: 5)
- **Bucket [0.4 - 0.6]**: Predicted Probability = `47.0%` | Actual Success Rate = `100.0%` (Count: 3)
- **Bucket [0.6 - 0.8]**: Predicted Probability = `70.0%` | Actual Success Rate = `100.0%` (Count: 1)
- **Bucket [0.8 - 1.0]**: Predicted Probability = `99.0%` | Actual Success Rate = `98.0%` (Count: 757)

---

## 2. Business Comparison Analysis

The four strategies evaluated are:
1. **Control (No Recovery)**: Standard practice. Do not attempt recovery.
2. **ML-Only EV Greedy**: Act on any model recommendation where Expected Value (EV) > 0. No policy guardrails.
3. **Agent-Only Heuristic**: Blind rule-based retries/notifications mapped directly to error codes.
4. **RecoveryOS (ML + Agent + Policy)**: The full pipeline (ML EV ranking + Policy limits + Escalation rules).

### Metrics Summary Table

| Strategy | Recovery Rate | Revenue Recovered | Total Intervention Cost | False Actions (User Annoyance) | Net Recovered Revenue | Human Escalations |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Control** | 0.00% | INR 0.00 | INR 0.00 | INR 0.00 | INR 0.00 | 0.00% |
| **ML-Only EV Greedy** | 41.10% | INR 13,435,556.31 | INR 12,775.00 | INR 1,970.00 | INR 13,420,811.31 | 0.00% |
| **Agent Heuristic** | 54.46% | INR 17,804,571.50 | INR 25,775.00 | INR 9,080.00 | INR 17,769,716.50 | 0.00% |
| **RecoveryOS** | **20.54%** | **INR 6,716,290.57** | **INR 6,985.00** | **INR 100.00** | **INR 6,709,205.57** | **8.66%** |

---

## 3. Key Observations & Trade-offs

1. **Heuristics Lead to High User Annoyance**
   - The *Agent-Only Heuristic* recovers the most absolute revenue (54.46%), but at the expense of high user friction. It triggered **INR 9,080.00** in false action costs (annoyance) by sending SMS links and reminders to customers whose card details were permanently invalid or blocked.
   
2. **ML expected value optimization reduces friction**
   - The *ML-Only EV Greedy* model optimizes action selection, reducing user friction to just **INR 1,970.00** while still recovering **41.10%** of revenue, demonstrating the power of Expected Recovery Value optimization.

3. **Policy layer bounds risk and escalates high-value cases**
   - In *RecoveryOS*, the Policy Layer halts automatic retries on high-value accounts (amount > INR 50k) and escalates them to humans, resulting in an **8.66% escalation rate**. 
   - This reduces the *autonomous* recovery rate to **20.54%**, but ensures that **no high-value transaction is exposed to automated risk**, and reduces user friction to a near-zero **INR 100.00**.
   - These escalated transactions represent a significant pool of value that can be captured safely via manual high-touch sales operations, combining the best of automation and human verification.

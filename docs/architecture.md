# Architecture Specification: RecoveryOS

RecoveryOS uses a decoupled, layered architecture to process payment failure streams. 
This ensures that non-deterministic AI models can recommend actions, but cannot bypass strict financial rules.

```
       [Webhook/API Event Stream]
                   │
                   ▼
┌──────────────────────────────────────┐
│            AGENT LAYER               │
│  - Diagnosis Agent (FastAPI/Gemini)  │
│  - Recovery Planner (FastAPI/Gemini) │
└──────────────────┬───────────────────┘
                   │ Diagnosed Event + Recommended Action
                   ▼
┌──────────────────────────────────────┐
│               ML LAYER               │
│  - Gradient Boosting Classifier      │
│  - Expected Value (EV) Calculation   │
└──────────────────┬───────────────────┘
                   │ EV + Success Probabilities
                   ▼
┌──────────────────────────────────────┐
│             POLICY LAYER             │
│  - Deterministic Python Rules        │
│  - Limits, Suppression, Cooldowns   │
└──────────────────┬───────────────────┘
                   │ Filtered / Approved Action
                   ▼
┌──────────────────────────────────────┐
│           EXECUTION LAYER            │
│  - Idempotent API Wrapper            │
│  - Backoffs & Retries (HTTPX)        │
└──────────────────┬───────────────────┘
                   │ Gateway Response Payload
                   ▼
┌──────────────────────────────────────┐
│          VERIFICATION LAYER          │
│  - Verification Agent (Gemini)       │
│  - Audit Database Logger             │
└──────────────────────────────────────┘
```

---

## 1. Core Layers

### ML Layer
Responsible for predicting the probability of successful recovery for each candidate intervention (None, Retry, Reminder, Link) and computing the Expected Recovery Value (EV) based on transaction amounts, gateway costs, and customer annoyance parameters.
- **Model**: Gradient Boosting Classifier (scikit-learn).
- **Features**: Customer tenure, historical success/failure rate, 24h attempt velocity, time since last successful payment, merchant category, transaction amount, payment method, gateway error code, candidate intervention type.

### Agent Layer
Responsible for high-level semantic reasoning:
- **Diagnosis Agent**: Translates raw gateway reason strings and codes into a unified failure classification: `transient_network`, `insufficient_funds`, `auth_failure`, `system_down`, or `permanent_rejection`.
- **Planner Agent**: Interprets ML rankings, customer behavior, and merchant vertical details to select the optimal recovery channel and generate a natural-language explanation.
- **Verification Agent**: Parses raw gateway API callbacks or webhook notifications to confirm that the payment has captured successfully.

### Policy Layer (The Guardrail)
Deterministic Python logic that intercepts all agent recommendations. The agent cannot write directly to the database or invoke third-party APIs without passing through this filter:
- **Rule 1 (Escalation)**: Transaction amount > INR 50,000 immediately halts automation and flags `HUMAN_APPROVAL_REQUIRED`.
- **Rule 2 (Retry limit)**: Max automatic retries is capped at 2. If it fails twice, it flags `HUMAN_ESCALATION_REQUIRED`.
- **Rule 3 (Contact suppression)**: If a notification was sent to this customer in the last 24 hours, any new contact action is rejected.
- **Rule 4 (Probability threshold)**: Rejects automatic actions with success probabilities < 30%.
- **Rule 5 (EV filter)**: Rejects actions where Expected Value $\le 0$.

### Execution Layer
Handles communication with simulated banking APIs.
- **Idempotency**: All executions require a unique key: `recovery:{transaction_id}:{action_type}:{attempt_number}`. If a call is made with an existing key, the executor returns the cached response from the database.
- **Resilience**: Network timeouts are handled with exponential backoff retries (3 attempts).

---

## 2. Relational Database Schema

```
  ┌──────────────────┐
  │     CUSTOMER     │
  └────────┬─────────┘
           │ 1
           │
           │ *
  ┌────────▼─────────┐         * ┌──────────────────┐
  │   TRANSACTION    ├──────────►│  RECOVERY_ACTION │
  └────────┬─────────┘           └──────────────────┘
           │ 1
           │
           │ *
  ┌────────▼─────────┐
  │    AUDIT_LOG     │
  └──────────────────┘
```

* **Customer**: ID, tenure, merchant category, payment preferences, historic rates, velocity.
* **Transaction**: ID, customer link, amount, status, gateway reason, retry counter, recovery indicators.
* **RecoveryAction**: Action link, scheduled/executed timestamps, status (scheduled, executing, success, failed, rejected_by_policy), idempotency key.
* **AuditLog**: Context snapshot (JSON), model scores, agent justifications, policy clearance decisions, execution status.

# Synthetic Payment Data Engine

To evaluate RecoveryOS without exposing real-world financial records or credentials, this engine simulates realistic merchant environments, transaction patterns, and payment failure modes.

## Schema
Data is split into two relational components:

### 1. Customers (`customers.csv`)
* `customer_id`: Unique identifier (`cust_XXXXXX`).
* `tenure_days`: Age of the customer relationship in days (exponential distribution).
* `merchant_category`: Merchant industry vertical (`SaaS`, `E-commerce`, `Edtech`, `Financial Services`, `Gaming`).
* `preferred_payment_method`: `UPI`, `card`, `netbanking`, or `wallet`.
* `historical_success_rate`: The baseline success rate of payment attempts (0.0 to 1.0).
* `historical_failure_rate`: `1.0 - historical_success_rate`.
* `velocity_24h`: Transaction attempts in the last 24 hours (Poisson distribution).
* `time_since_last_success_days`: Elapsed time since a successful transaction.

### 2. Transactions (`transactions.csv`)
* `transaction_id`: Unique identifier (`pay_XXXXXX`).
* `customer_id`: Link to the customer profile.
* `amount`: Transaction amount (modeled dynamically by vertical).
* `timestamp`: Precise date and time of the attempt.
* `payment_method`: The method chosen for the specific attempt.
* `merchant_category`: Category of the transaction.
* `status`: Current outcome (`captured` or `failed`).
* `gateway_code`: Detailed failure code returned by the payment processor.
* `failure_reason`: Human-readable error description.
* `is_retry`: True if this is an automated/manual retry.
* `retry_count`: Total retries executed for the original transaction.
* `original_transaction_id`: Link to the initial failure.
* `recovered`: True if a recovery action eventually led to successful settlement.
* `recovered_amount`: Amount successfully recovered.
* `recovery_intervention`: The historical intervention applied (`retry`, `reminder`, `link`, `none`).

## Failure Reason Classifications

1. **Transient Errors** (e.g., `GATEWAY_ERROR_ISSUER_DOWN`, `GATEWAY_ERROR_TIMED_OUT`)
   * *Mechanism*: Network disruption or bank issue.
   * *Recoverability*: High (60% - 80%) via automated retry.

2. **User Errors** (e.g., `BAD_REQUEST_PAYMENT_OTP_INCORRECT`, `BAD_REQUEST_PAYMENT_CANCELLED_BY_USER`)
   * *Mechanism*: User failed input or cancelled.
   * *Recoverability*: Moderate (35% - 50%) via payment link or email/sms reminders.

3. **Permanent Errors** (e.g., `BAD_REQUEST_PAYMENT_CARD_DECLINED`, `BAD_REQUEST_PAYMENT_CARD_BLOCKED`)
   * *Mechanism*: Blocked card or insufficient funds.
   * *Recoverability*: Low (5% - 15%) via payment links offering alternative payment methods.

## Reproducibility
Seeding is pinned:
```python
random.seed(42)
np.random.seed(42)
```
This guarantees identical evaluation files across any system.

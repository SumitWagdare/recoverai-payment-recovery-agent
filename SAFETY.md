# Safety & Guardrails

Automated systems interacting with customers and processing payments represent a high-risk surface area. RecoverAI is built around a philosophy of **Defense in Depth**.

## Core Principles
1. **Never communicate blindly.**
2. **Never retry infinitely.**
3. **Always log the reason.**

## Guardrail Implementations

### 1. Max Retries (Anti-Spam / Anti-Fee)
Payment gateways often charge micro-fees for every attempt. Furthermore, repeated retries on permanent failures (e.g., expired cards) will result in merchant account penalties.
- **Implementation**: The system tracks `retry_count`. If it hits `MAX_RETRIES` (default 3), the agent intercepts the AI's recommendation to `retry_later` and forces a fallback to `send_payment_link`.

### 2. Cooldown Periods (Rate Limiting)
Rapidly retrying a failed payment will almost always result in consecutive failures.
- **Implementation**: A minimum of 4 hours (`COOLDOWN_HOURS`) must pass between automated actions for a specific payment.

### 3. Duplicate Contact Prevention (Anti-Harassment)
If a customer has multiple failed payments (e.g., two different subscriptions failing on the same day due to an expired card), they should not receive multiple identical emails requesting a new card.
- **Implementation**: Before recommending a customer-facing action (`send_payment_link`, `request_alt_method`), the agent scans the audit log. If the customer was contacted within the last 24 hours (`CONTACT_COOLDOWN_HOURS`), the action is blocked and logged.

### 4. Mandatory Human Approval
AI should not have unilateral authority over high-risk decisions.
- **Implementation**: 
  - **High Value**: Any action on a payment over ₹10,000 is held for approval.
  - **Customer Facing**: Any action that communicates externally is held.
  - **Escalations**: System errors and suspected fraud are held.
  Only low-value, internal retries are `auto_approved`.

### 5. Deterministic Explainability
Black-box ML models are unacceptable for financial workflows.
- **Implementation**: The AI decision engine is strictly rule-based. Every single recommendation outputs a human-readable `reasoning` string detailing *why* the classification was made and *why* the action was chosen, which is stored immutably in the audit log.

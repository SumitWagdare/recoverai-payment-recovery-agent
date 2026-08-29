"""
RecoverAI — AI Decision Engine

Rule-based classifier and action recommender for failed payments.
No external API keys required — all logic is deterministic and explainable.

⚠️ SAFETY: This module never triggers real payment retries or
customer communications. All actions are recommendations only.
"""

from datetime import timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

# ── Failure Classification Rules ──────────────────────────────────────────────

FAILURE_CATEGORIES = {
    "bank_server_down":       ("temporary",              0.92),
    "network_timeout":        ("temporary",              0.88),
    "insufficient_funds":     ("customer_action_needed", 0.90),
    "card_expired":           ("customer_action_needed", 0.95),
    "upi_pin_not_set":        ("customer_action_needed", 0.93),
    "payment_cancelled":      ("customer_action_needed", 0.80),
    "invalid_card":           ("permanent",              0.94),
    "emandate_debit_failed":  ("permanent",              0.85),
    "risk_check_failed":      ("system_error",           0.87),
    "authentication_failed":  ("system_error",           0.82),
}

REASONING_TEMPLATES = {
    "bank_server_down": (
        "The issuing bank's server was temporarily unavailable. "
        "This is typically a transient issue that resolves within a few hours."
    ),
    "network_timeout": (
        "The payment request timed out due to network issues between "
        "the payment gateway and the bank. This is usually temporary."
    ),
    "insufficient_funds": (
        "The customer's account did not have sufficient funds to complete "
        "this payment. The customer needs to add funds or use an alternative method."
    ),
    "card_expired": (
        "The customer's card has expired. They need to update their card "
        "details or use a different payment method."
    ),
    "upi_pin_not_set": (
        "The customer has not set up their UPI PIN, which is required "
        "to authorize UPI payments. They need to configure their UPI app."
    ),
    "payment_cancelled": (
        "The customer actively cancelled the payment during the authorization "
        "flow. This may indicate hesitation or a UX friction point."
    ),
    "invalid_card": (
        "The card number provided is invalid or has been permanently blocked. "
        "The customer must use a different card."
    ),
    "emandate_debit_failed": (
        "The e-mandate debit instruction was rejected by the customer's bank. "
        "This may require re-registration of the mandate."
    ),
    "risk_check_failed": (
        "The payment was flagged by the risk assessment system. "
        "This requires manual review before proceeding."
    ),
    "authentication_failed": (
        "The payment authentication (3DS / OTP) failed. This could be "
        "due to incorrect credentials or a bank-side issue."
    ),
}


def classify_failure(payment: dict) -> dict:
    """
    Classify a failed payment by its root cause.

    Returns:
        {
            "category": "temporary"|"customer_action_needed"|"permanent"|"system_error",
            "confidence": float  (0.0 – 1.0),
            "reasoning": str
        }
    """
    reason = payment.get("failure_reason", "unknown")

    if reason in FAILURE_CATEGORIES:
        category, base_confidence = FAILURE_CATEGORIES[reason]
    else:
        category, base_confidence = "system_error", 0.50

    # ── Confidence adjustments ────────────────────────────────────────────
    retry_count = payment.get("retry_count", 0)
    if retry_count > 0 and category == "temporary":
        # Repeated same failure ⇒ higher confidence in classification
        base_confidence = min(0.98, base_confidence + retry_count * 0.02)

    segment = payment.get("customer_segment", "regular")
    if segment == "premium" and category == "customer_action_needed":
        base_confidence = max(0.60, base_confidence - 0.05)

    reasoning = REASONING_TEMPLATES.get(
        reason,
        f"Unknown failure reason: '{reason}'. Manual investigation recommended.",
    )

    return {
        "category": category,
        "confidence": round(base_confidence, 2),
        "reasoning": reasoning,
    }


def recommend_action(payment: dict, classification: dict) -> dict:
    """
    Recommend one bounded recovery action based on the failure classification.

    Returns:
        {
            "action": "retry_later"|"send_payment_link"|"request_alt_method"|"escalate_to_support",
            "reasoning": str,
            "requires_approval": bool,
            "priority": "low"|"medium"|"high"|"critical"
        }
    """
    category = classification["category"]
    reason = payment.get("failure_reason", "unknown")
    retry_count = payment.get("retry_count", 0)
    segment = payment.get("customer_segment", "regular")
    amount = payment.get("amount", 0)

    # 1. Temporary failures → retry if budget remains
    if category == "temporary":
        if retry_count < 3:
            return {
                "action": "retry_later",
                "reasoning": (
                    f"Failure is temporary ({reason}). "
                    f"{3 - retry_count} retries remaining. "
                    f"Scheduling retry with exponential back-off."
                ),
                "requires_approval": amount > 10000,
                "priority": "medium" if amount <= 5000 else "high",
            }
        return {
            "action": "send_payment_link",
            "reasoning": (
                f"Temporary failure ({reason}) persisted after {retry_count} retries. "
                f"Sending a fresh payment link for the customer to retry at their convenience."
            ),
            "requires_approval": True,
            "priority": "high",
        }

    # 2. Customer-action failures → link or alt method
    if category == "customer_action_needed":
        if reason in ("insufficient_funds", "payment_cancelled"):
            return {
                "action": "send_payment_link",
                "reasoning": (
                    f"Customer action required ({reason}). Sending a payment link "
                    f"so the customer can complete payment when ready."
                ),
                "requires_approval": True,
                "priority": "medium",
            }
        return {
            "action": "request_alt_method",
            "reasoning": (
                f"The current payment method cannot succeed ({reason}). "
                f"Requesting the customer to use an alternative payment method."
            ),
            "requires_approval": True,
            "priority": "medium" if segment != "churning" else "high",
        }

    # 3. Permanent failures → alt method or escalate
    if category == "permanent":
        if retry_count >= 2 or segment == "churning":
            return {
                "action": "escalate_to_support",
                "reasoning": (
                    f"Permanent failure ({reason}) with {retry_count} previous attempts. "
                    f"Customer segment: {segment}. Escalating to human support."
                ),
                "requires_approval": True,
                "priority": "critical" if segment == "premium" else "high",
            }
        return {
            "action": "request_alt_method",
            "reasoning": (
                f"Payment method has a permanent issue ({reason}). "
                f"Asking the customer to provide an alternative payment method."
            ),
            "requires_approval": True,
            "priority": "medium",
        }

    # 4. System errors → always escalate
    if category == "system_error":
        return {
            "action": "escalate_to_support",
            "reasoning": (
                f"System-level failure ({reason}). Requires investigation by the "
                f"technical support team. Auto-recovery is not safe."
            ),
            "requires_approval": True,
            "priority": "critical" if reason == "risk_check_failed" else "high",
        }

    # Fallback
    return {
        "action": "escalate_to_support",
        "reasoning": "Unrecognized failure pattern. Escalating for manual review.",
        "requires_approval": True,
        "priority": "high",
    }

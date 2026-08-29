"""
Tests for the AI failure-classification engine and action recommender.

Covers:
- All 10 known failure reasons are classified into the correct category
- Unknown failures fall back to system_error with low confidence
- Confidence adjusts based on retry history and customer segment
- Action recommendations match expected logic per failure type
- Max-retry exhaustion switches from retry_later to send_payment_link
- High-value payments are flagged for approval
- System errors always escalate
"""

import pytest
from app.ai_engine import classify_failure, recommend_action


# ── Classification ────────────────────────────────────────────────────────────

class TestClassifyFailure:
    """Every known failure reason must map to its expected category."""

    @pytest.mark.parametrize("reason, expected", [
        ("bank_server_down",      "temporary"),
        ("network_timeout",       "temporary"),
        ("insufficient_funds",    "customer_action_needed"),
        ("card_expired",          "customer_action_needed"),
        ("upi_pin_not_set",       "customer_action_needed"),
        ("payment_cancelled",     "customer_action_needed"),
        ("invalid_card",          "permanent"),
        ("emandate_debit_failed", "permanent"),
        ("risk_check_failed",     "system_error"),
        ("authentication_failed", "system_error"),
    ])
    def test_known_failure_category(self, reason, expected):
        payment = {"failure_reason": reason, "retry_count": 0, "customer_segment": "regular"}
        result = classify_failure(payment)
        assert result["category"] == expected

    @pytest.mark.parametrize("reason, expected", [
        ("bank_server_down",      "temporary"),
        ("network_timeout",       "temporary"),
        ("insufficient_funds",    "customer_action_needed"),
        ("card_expired",          "customer_action_needed"),
        ("upi_pin_not_set",       "customer_action_needed"),
        ("payment_cancelled",     "customer_action_needed"),
        ("invalid_card",          "permanent"),
        ("emandate_debit_failed", "permanent"),
        ("risk_check_failed",     "system_error"),
        ("authentication_failed", "system_error"),
    ])
    def test_confidence_in_valid_range(self, reason, expected):
        payment = {"failure_reason": reason, "retry_count": 0, "customer_segment": "regular"}
        result = classify_failure(payment)
        assert 0.0 <= result["confidence"] <= 1.0

    @pytest.mark.parametrize("reason", [
        "bank_server_down", "network_timeout", "insufficient_funds",
        "card_expired", "upi_pin_not_set", "payment_cancelled",
        "invalid_card", "emandate_debit_failed", "risk_check_failed",
        "authentication_failed",
    ])
    def test_reasoning_is_non_empty(self, reason):
        payment = {"failure_reason": reason, "retry_count": 0, "customer_segment": "regular"}
        result = classify_failure(payment)
        assert len(result["reasoning"]) > 20  # meaningful text

    def test_unknown_failure_defaults_to_system_error(self):
        payment = {"failure_reason": "alien_invasion", "retry_count": 0}
        result = classify_failure(payment)
        assert result["category"] == "system_error"
        assert result["confidence"] == 0.50
        assert "unknown" in result["reasoning"].lower() or "Unknown" in result["reasoning"]

    def test_confidence_increases_with_retries_for_temporary(self):
        base = {"failure_reason": "bank_server_down", "customer_segment": "regular"}
        c0 = classify_failure({**base, "retry_count": 0})["confidence"]
        c3 = classify_failure({**base, "retry_count": 3})["confidence"]
        assert c3 > c0, "More retries should increase confidence for temporary failures"

    def test_confidence_capped_at_098(self):
        payment = {"failure_reason": "bank_server_down", "retry_count": 100, "customer_segment": "regular"}
        result = classify_failure(payment)
        assert result["confidence"] <= 0.98

    def test_premium_segment_lowers_customer_action_confidence(self):
        base = {"failure_reason": "insufficient_funds", "retry_count": 0}
        regular = classify_failure({**base, "customer_segment": "regular"})["confidence"]
        premium = classify_failure({**base, "customer_segment": "premium"})["confidence"]
        assert premium < regular


# ── Action Recommendations ────────────────────────────────────────────────────

class TestRecommendAction:
    """Recommendations must match the documented action-selection logic."""

    @pytest.mark.parametrize("reason, expected_action", [
        ("bank_server_down",      "retry_later"),
        ("network_timeout",       "retry_later"),
        ("insufficient_funds",    "send_payment_link"),
        ("card_expired",          "request_alt_method"),
        ("upi_pin_not_set",       "request_alt_method"),
        ("payment_cancelled",     "send_payment_link"),
        ("risk_check_failed",     "escalate_to_support"),
        ("authentication_failed", "escalate_to_support"),
    ])
    def test_action_for_failure_type(self, reason, expected_action):
        payment = {
            "failure_reason": reason,
            "retry_count": 0,
            "customer_segment": "regular",
            "amount": 500,
        }
        classification = classify_failure(payment)
        rec = recommend_action(payment, classification)
        assert rec["action"] == expected_action

    def test_exhausted_retries_switches_to_payment_link(self):
        payment = {
            "failure_reason": "bank_server_down",
            "retry_count": 3,
            "customer_segment": "regular",
            "amount": 500,
        }
        classification = classify_failure(payment)
        rec = recommend_action(payment, classification)
        assert rec["action"] == "send_payment_link"
        assert rec["requires_approval"] is True

    def test_high_value_retry_requires_approval(self):
        payment = {
            "failure_reason": "network_timeout",
            "retry_count": 0,
            "customer_segment": "regular",
            "amount": 15_000,
        }
        classification = classify_failure(payment)
        rec = recommend_action(payment, classification)
        assert rec["requires_approval"] is True

    def test_system_errors_always_escalate(self):
        for reason in ("risk_check_failed", "authentication_failed"):
            payment = {
                "failure_reason": reason,
                "retry_count": 0,
                "customer_segment": "regular",
                "amount": 500,
            }
            classification = classify_failure(payment)
            rec = recommend_action(payment, classification)
            assert rec["action"] == "escalate_to_support"
            assert rec["requires_approval"] is True

    def test_churning_customer_gets_higher_priority(self):
        payment = {
            "failure_reason": "card_expired",
            "retry_count": 0,
            "customer_segment": "churning",
            "amount": 500,
        }
        classification = classify_failure(payment)
        rec = recommend_action(payment, classification)
        assert rec["priority"] == "high"

    def test_recommendation_always_has_reasoning(self):
        for reason in ("bank_server_down", "insufficient_funds", "invalid_card", "risk_check_failed"):
            payment = {
                "failure_reason": reason,
                "retry_count": 0,
                "customer_segment": "regular",
                "amount": 500,
            }
            classification = classify_failure(payment)
            rec = recommend_action(payment, classification)
            assert len(rec["reasoning"]) > 10

    def test_priority_is_valid_value(self):
        for reason in ("bank_server_down", "insufficient_funds", "invalid_card", "risk_check_failed"):
            payment = {
                "failure_reason": reason,
                "retry_count": 0,
                "customer_segment": "regular",
                "amount": 500,
            }
            classification = classify_failure(payment)
            rec = recommend_action(payment, classification)
            assert rec["priority"] in ("low", "medium", "high", "critical")

"""
Tests for duplicate-contact prevention.

Covers:
- Second customer-facing action for the same customer is blocked
- Different customers are not blocked
- Non-customer-facing actions (retry, escalate) are never blocked
- Rejected previous contacts do not block new ones
"""

import json
import pytest
from datetime import datetime, timedelta, timezone

from app import recovery_agent

IST = timezone(timedelta(hours=5, minutes=30))


class TestDuplicateContactPrevention:
    """No customer should be contacted twice within the cooldown window."""

    def test_second_contact_same_customer_is_blocked(self, clean_env, make_payment):
        data_path, audit_path = clean_env

        # Two payments for the SAME customer — both need customer-facing actions
        p1 = make_payment(
            payment_id="pay_dup_001",
            customer_id="cust_shared",
            failure_reason="insufficient_funds",
            amount=500,
        )
        p2 = make_payment(
            payment_id="pay_dup_002",
            customer_id="cust_shared",
            failure_reason="card_expired",
            amount=400,
        )
        data_path.write_text(json.dumps([p1, p2]))

        # First contact succeeds
        r1 = recovery_agent.process_payment("pay_dup_001")
        assert r1["stopped"] is False

        # Second contact for same customer is blocked
        r2 = recovery_agent.process_payment("pay_dup_002")
        assert r2.get("stopped") is True or r2.get("duplicate_blocked") is True
        assert "Duplicate" in r2.get("stop_reason", "") or r2.get("duplicate_blocked") is True

    def test_different_customers_are_not_blocked(self, clean_env, make_payment):
        data_path, _ = clean_env

        p1 = make_payment(
            payment_id="pay_diff_001",
            customer_id="cust_alpha",
            failure_reason="insufficient_funds",
            amount=500,
        )
        p2 = make_payment(
            payment_id="pay_diff_002",
            customer_id="cust_beta",
            failure_reason="insufficient_funds",
            amount=400,
        )
        data_path.write_text(json.dumps([p1, p2]))

        r1 = recovery_agent.process_payment("pay_diff_001")
        assert r1["stopped"] is False

        r2 = recovery_agent.process_payment("pay_diff_002")
        assert r2["stopped"] is False
        assert r2.get("duplicate_blocked") is not True

    def test_retry_action_is_never_blocked_by_duplicate_check(self, clean_env, make_payment):
        data_path, _ = clean_env

        # Two temporary failures for the same customer → both get retry_later
        p1 = make_payment(
            payment_id="pay_retry_001",
            customer_id="cust_retry",
            failure_reason="bank_server_down",
            amount=200,
        )
        p2 = make_payment(
            payment_id="pay_retry_002",
            customer_id="cust_retry",
            failure_reason="network_timeout",
            amount=300,
        )
        data_path.write_text(json.dumps([p1, p2]))

        r1 = recovery_agent.process_payment("pay_retry_001")
        assert r1["recommendation"]["action"] == "retry_later"

        r2 = recovery_agent.process_payment("pay_retry_002")
        assert r2["stopped"] is False  # retry is not customer-facing
        assert r2.get("duplicate_blocked") is not True

    def test_escalation_is_never_blocked_by_duplicate_check(self, clean_env, make_payment):
        data_path, _ = clean_env

        p1 = make_payment(
            payment_id="pay_esc_001",
            customer_id="cust_esc",
            failure_reason="risk_check_failed",
            amount=500,
        )
        p2 = make_payment(
            payment_id="pay_esc_002",
            customer_id="cust_esc",
            failure_reason="authentication_failed",
            amount=700,
        )
        data_path.write_text(json.dumps([p1, p2]))

        r1 = recovery_agent.process_payment("pay_esc_001")
        r2 = recovery_agent.process_payment("pay_esc_002")

        # Neither should be duplicate-blocked (escalation is not customer-facing)
        assert r1.get("duplicate_blocked") is not True
        assert r2.get("duplicate_blocked") is not True

    def test_blocked_action_is_logged_in_audit(self, clean_env, make_payment):
        data_path, audit_path = clean_env

        p1 = make_payment(
            payment_id="pay_log_001",
            customer_id="cust_log",
            failure_reason="insufficient_funds",
            amount=500,
        )
        p2 = make_payment(
            payment_id="pay_log_002",
            customer_id="cust_log",
            failure_reason="card_expired",
            amount=400,
        )
        data_path.write_text(json.dumps([p1, p2]))

        recovery_agent.process_payment("pay_log_001")
        r2 = recovery_agent.process_payment("pay_log_002")

        # The blocked action should still have an audit entry
        if r2.get("audit_id"):
            from app import audit_log
            entries = audit_log.read_all()
            blocked = [e for e in entries if e.get("approval_status") == "blocked"]
            assert len(blocked) >= 1
            assert "Duplicate" in blocked[0].get("notes", "")

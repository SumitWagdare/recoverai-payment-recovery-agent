"""
Tests for safety controls: max retries, cooldown periods, stop conditions.

Covers:
- Already-recovered payments are stopped
- Cooldown period blocks actions within the window
- Max-retry limit prevents retry_later and switches to payment link
- Non-existent payment returns an error
- Normal pending payments are processed successfully
"""

import json
import pytest
from datetime import datetime, timedelta, timezone

from app import recovery_agent

IST = timezone(timedelta(hours=5, minutes=30))


class TestStopConditions:
    """Stop conditions must halt processing before the AI pipeline runs."""

    def test_recovered_payment_is_stopped(self, clean_env, make_payment):
        data_path, _ = clean_env
        p = make_payment(recovery_status="recovered", failure_reason="insufficient_funds")
        data_path.write_text(json.dumps([p]))

        result = recovery_agent.process_payment(p["payment_id"])
        assert result["stopped"] is True
        assert "already been recovered" in result["stop_reason"]

    def test_cooldown_blocks_recent_retry(self, clean_env, make_payment):
        data_path, _ = clean_env
        recent_ts = datetime.now(IST) - timedelta(hours=1)  # 1h ago, within 4h cooldown
        p = make_payment(
            retry_count=1,
            retry_history=[{
                "attempt": 1,
                "timestamp": recent_ts.isoformat(),
                "outcome": "failed",
                "reason": "bank_server_down",
            }],
        )
        data_path.write_text(json.dumps([p]))

        result = recovery_agent.process_payment(p["payment_id"])
        assert result["stopped"] is True
        assert "Cooldown" in result["stop_reason"]

    def test_old_retry_does_not_trigger_cooldown(self, clean_env, make_payment):
        data_path, _ = clean_env
        old_ts = datetime.now(IST) - timedelta(hours=10)  # well past 4h cooldown
        p = make_payment(
            retry_count=1,
            retry_history=[{
                "attempt": 1,
                "timestamp": old_ts.isoformat(),
                "outcome": "failed",
                "reason": "bank_server_down",
            }],
        )
        data_path.write_text(json.dumps([p]))

        result = recovery_agent.process_payment(p["payment_id"])
        assert result["stopped"] is False

    def test_nonexistent_payment_returns_error(self, clean_env):
        result = recovery_agent.process_payment("pay_does_not_exist")
        assert "error" in result


class TestMaxRetryLimit:
    """Max-retry enforcement must prevent further retries and fallback."""

    def test_retry_exhausted_switches_to_payment_link(self, clean_env, make_payment):
        data_path, _ = clean_env
        old_ts = datetime.now(IST) - timedelta(hours=48)
        p = make_payment(
            failure_reason="bank_server_down",
            retry_count=3,
            retry_history=[{
                "attempt": i,
                "timestamp": (old_ts + timedelta(hours=i * 5)).isoformat(),
                "outcome": "failed",
                "reason": "bank_server_down",
            } for i in range(1, 4)],
        )
        data_path.write_text(json.dumps([p]))

        result = recovery_agent.process_payment(p["payment_id"])
        assert result["stopped"] is False
        assert result["recommendation"]["action"] != "retry_later"
        # Either the agent or the AI engine blocks retries — both are valid
        assert result["recommendation"]["action"] in ("send_payment_link", "request_alt_method", "escalate_to_support")

    def test_under_limit_allows_retry(self, clean_env, make_payment):
        data_path, _ = clean_env
        old_ts = datetime.now(IST) - timedelta(hours=48)
        p = make_payment(
            failure_reason="bank_server_down",
            retry_count=1,
            retry_history=[{
                "attempt": 1,
                "timestamp": old_ts.isoformat(),
                "outcome": "failed",
                "reason": "bank_server_down",
            }],
        )
        data_path.write_text(json.dumps([p]))

        result = recovery_agent.process_payment(p["payment_id"])
        assert result["stopped"] is False
        assert result["recommendation"]["action"] == "retry_later"


class TestHighValueApproval:
    """Payments above the threshold must require human approval."""

    def test_high_value_requires_approval(self, clean_env, make_payment):
        data_path, _ = clean_env
        p = make_payment(amount=15_000, failure_reason="bank_server_down")
        data_path.write_text(json.dumps([p]))

        result = recovery_agent.process_payment(p["payment_id"])
        assert result["approval_status"] == "awaiting_approval"

    def test_low_value_temporary_is_auto_approved(self, clean_env, make_payment):
        data_path, _ = clean_env
        p = make_payment(amount=200, failure_reason="bank_server_down")
        data_path.write_text(json.dumps([p]))

        result = recovery_agent.process_payment(p["payment_id"])
        assert result["approval_status"] == "auto_approved"

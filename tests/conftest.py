"""
Shared pytest fixtures for RecoverAI tests.

All tests use temporary data and audit files so the real
dataset is never touched.
"""

import json
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import recovery_agent, audit_log

IST = timezone(timedelta(hours=5, minutes=30))


@pytest.fixture
def clean_env(tmp_path):
    """
    Provide a fully isolated test environment:
    - temporary synthetic_payments.json
    - temporary audit_log.jsonl
    Patches module-level paths so no real data is touched.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    data_path = data_dir / "synthetic_payments.json"
    audit_path = data_dir / "audit_log.jsonl"
    data_path.write_text("[]")
    audit_path.touch()

    with patch.object(recovery_agent, "DATA_PATH", data_path), \
         patch.object(audit_log, "AUDIT_LOG_PATH", audit_path):
        yield data_path, audit_path


@pytest.fixture
def make_payment():
    """Factory fixture — returns a helper that creates test payments."""
    _counter = [0]

    def _make(**overrides):
        _counter[0] += 1
        base = {
            "payment_id": f"pay_test_{_counter[0]:03d}",
            "amount": 500.00,
            "currency": "INR",
            "payment_method": "upi",
            "failure_reason": "bank_server_down",
            "retry_count": 0,
            "retry_history": [],
            "customer_segment": "regular",
            "customer_id": f"cust_test_{_counter[0]:03d}",
            "timestamp": (datetime.now(IST) - timedelta(hours=10)).isoformat(),
            "recovery_status": "pending",
        }
        base.update(overrides)
        return base

    return _make
